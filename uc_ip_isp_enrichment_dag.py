import subprocess
import sys
import importlib
import time
import logging
from datetime import datetime, timedelta, date
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import pendulum
from trino.dbapi import connect
import logging

# Ensure required packages are installed
for package in ["pyarrow", "geoip2", "pandas"]:
    try:
        importlib.import_module(package)
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            '--no-cache-dir',
            '--index-url', 'http://10.10.206.59:8080/repository/pypi-proxy/simple',
            '--trusted-host', '10.10.206.59',
            package
        ])
        importlib.invalidate_caches()
        globals()[package] = importlib.import_module(package)

# Airflow 3 core imports
from airflow import DAG, task

# Your custom internal modules
import geoip2.database
import pandas as pd
MMDB_PATH = '/opt/airflow/dags/operator360/GeoLite2-ASN.mmdb'
trino_host = "10.10.116.75"
trino_catalog_iceberg = 'strot'
trino_port = 8080
trino_user = "airflow_dag_op"
logger = logging.getLogger(__name__)


def run_query(query, host=trino_host, port=trino_port, user=trino_user):
    logger.info("Executing Trino query on host=%s, port=%s, user=%s", host, port, user)
    logger.debug("Trino query:\n%s", query)
    try:
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        if not body:
            logger.info("Trino query returned 0 rows.")
            return {"query": query, "success": 1, "data": body}
        else:
            cols = [i[0] for i in cur.description]
            logger.info("Trino query returned %d rows with columns: %s", len(body), cols)
            return {"query": query, "success": 1, "data": (cols, body)}
    except Exception as e:
        logger.exception("Trino query execution failed: %s", e)
        return {"query": query, "success": 0, "msg": str(e)}



# --- Configuration ---
# NOTE: Ensure 'GeoLite2-ASN.mmdb' is present in the Airflow worker's working directory 
# or provide an absolute path here (e.g., '/opt/airflow/data/GeoLite2-ASN.mmdb')

default_args = {
    'depends_on_past': False,
    'start_date': pendulum.datetime(2026, 8, 5, tz="Asia/Kolkata"),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
}

with DAG(
    dag_id='uc_isp_data_enrichment',
    description='DAG to enrich UC IP data using local MaxMind GeoIP database',
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=['operator360', 'uc']
) as dag:

    @task
    def process_uc_isp_data():
        """Runs the local GeoIP enrichment and parallel inserts."""
        asn_reader = geoip2.database.Reader(MMDB_PATH)

        @lru_cache(maxsize=1_000_000)
        def get_ip_details(ip_address):
            try:
                r = asn_reader.asn(ip_address)
                return f"AS{r.autonomous_system_number}", r.autonomous_system_organization, None
            except Exception:
                return None, None, None

        def sql_val(val):
            if val is None: return "NULL"
            if isinstance(val, (pd.Timestamp, datetime)):
                return f"TIMESTAMP '{val.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
            if isinstance(val, date):
                return f"TIMESTAMP '{val.strftime('%Y-%m-%d 00:00:00')}'"
            if isinstance(val, (int, float)): return str(val)
            return "'" + str(val).replace("'", "''") + "'"

        def sql_timestamp(val):
            if val is None: return "NULL"
            return "TIMESTAMP '" + str(val).replace("'", "''").split('+')[0].strip() + "'"

        def execute_insert(chunk):
            values = ",".join(
                f"({sql_val(r[0])}, {sql_val(r[1])}, {sql_val(r[2])}, {sql_val(r[3])}, "
                f"{sql_val(r[4])}, {sql_val(r[5])}, {sql_val(r[6])}, {sql_timestamp(r[7])}, "
                f"{sql_val(r[8])}, {sql_val(r[9])}, {sql_val(r[10])}, {sql_val(r[11])}, "
                f"{sql_timestamp(r[12])}, {sql_val(r[13])})" for r in chunk)
            q = f"""INSERT INTO strot.operator360.uc_machineip_isp_map
                    (opt_id, machine_ip_address, asn_code, carrier_name, eid, uc_stage,
                     uc_event_id, uc_event_timestamp, ea_code, registrar_code, district,
                     state, last_updated_at, ip_state)
                    VALUES {values}"""
            run_query(q, host='10.10.116.75')

        def enrich(row, target_date):
            opt_id, ip, eid, uc_stage, uc_event_id, uc_ts, ea, reg, dist, state = row[:10]
            asn, carrier, ip_state = get_ip_details(ip)
            return [opt_id, ip, asn, carrier, eid, uc_stage, uc_event_id, uc_ts,
                    ea, reg, dist, state, target_date, ip_state]

        try:
            for i in range(3, 29):
                t0 = time.time()
                target_date = (datetime.now() - timedelta(days=i)).date()
                logging.info(f"--- day -{i} ({target_date}) ---")

                # Idempotency: clear existing partition
                run_query(
                    f"DELETE FROM strot.operator360.uc_machineip_isp_map "
                    f"WHERE date(last_updated_at) = date '{target_date}'",
                    host='10.10.116.75')

                fetch_query = f"""
                    SELECT upper(operator_id), machine_ip_address, resident_sid, stage,
                           event_id, event_timestamp, ea, registrar, district, state
                    FROM flink_stream.stream_enu.enu_uc_opt_action_v2
                    WHERE date(event_timestamp) = date(current_date - interval '{i}' day)
                """
                
                # Assuming run_query returns a dict with 'df' key
                query_result = run_query(fetch_query, host='10.10.116.75')
                if not query_result or 'df' not in query_result:
                    logging.info(f"No data dict returned for -{i}. ({time.time()-t0:.2f}s)")
                    continue
                    
                result = query_result['df']
                
                if result is None or result.empty:
                    logging.info(f"No data for -{i}. ({time.time()-t0:.2f}s)")
                    continue

                rows = list(result.itertuples(index=False, name=None))

                # Parallel enrichment (GeoIP is the bottleneck)
                with ThreadPoolExecutor(max_workers=16) as ex:
                    enriched = list(filter(None, ex.map(lambda r: enrich(r, target_date), rows)))

                # Parallel inserts with bigger batches
                BATCH = 100_000
                chunks = [enriched[j:j+BATCH] for j in range(0, len(enriched), BATCH)]

                with ThreadPoolExecutor(max_workers=3) as ex:
                    list(ex.map(execute_insert, chunks))  # list() surfaces errors

                logging.info(f"day -{i}: {len(enriched)}/{len(rows)} rows inserted in {time.time()-t0:.2f}s")
        finally:
            asn_reader.close()
            logging.info("MaxMind ASN Reader closed successfully.")

    # Invoke the task to register it in the DAG
    process_uc_isp_data()
    
