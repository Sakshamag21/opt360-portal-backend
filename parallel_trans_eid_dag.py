from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
from trino.dbapi import connect

# --- Airflow 3 imports ---
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.empty import EmptyOperator

log = logging.getLogger(__name__)

# ---------------- Trino connection config ----------------
TRINO_HOST = "10.10.116.75"
TRINO_PORT = 8080
TRINO_USER = "airflow_dag_op"
TRINO_CATALOG_ICEBERG = "strot"


# ---------------- Trino helper ----------------
def trino_execute(query, host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER):
    """Execute a query on Trino and return a result dict."""
    try:
        q_lower = query.strip().lower()
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)

        if q_lower.startswith(("select", "with", "show", "describe", "explain")):
            body = cur.fetchall()
            if not body:
                return {"query": query, "success": 1, "data": body}
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df}
        # DML/DDL
        return {"query": query, "success": 1}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}


# ---------------- Parameterised SQL ----------------
def build_merge_query(partition_date: str) -> str:
    """Build the MERGE statement for a specific partition date (yyyy-MM-dd)."""
    return f"""
    merge into strot.operator360.txn_parallel_enrl_v1 t using(
    WITH enrollment_base AS (
        SELECT DISTINCT
            enrl_ref_id,
            enrl_eid,
            enrl_mode,
            enrl_start_date,
            enrl_end_date,
            enrl_status,
            cast(enrl_birth_year as varchar) as enrl_birth_year,
            enrl_dist_name,
            enrl_state_name,
            enrl_pincode,
            enrl_oper_code,
            enrl_oper_name,
            enrl_reg_code,
            enrl_reg_name,
            enrl_agency_code,
            enrl_agency_name,
            enrl_client_machine_id,
            enrl_station_code,
            enrl_client_version,
            enrl_gps_lat,
            enrl_gps_long,
            event_timestamp,
            client_type
        FROM flink_stream.stream_enu.bi_enu_enrlraw_v2
        WHERE date(event_timestamp) = date('{partition_date}')
        AND enrl_status LIKE '%SUCCESS%'
        AND enrl_client_version != '2.0.0.0'
    ),
    overlapping_pairs AS (
        SELECT DISTINCT t1.enrl_eid as eid
        FROM enrollment_base t1
        INNER JOIN enrollment_base t2
            ON t1.enrl_oper_code = t2.enrl_oper_code
            AND t1.enrl_client_machine_id = t2.enrl_client_machine_id
            AND t1.enrl_station_code = t2.enrl_station_code
            AND t1.enrl_client_version = t2.enrl_client_version
            AND t1.enrl_start_date < t2.enrl_start_date
            AND t1.enrl_end_date > t2.enrl_end_date
            AND t1.enrl_eid != t2.enrl_eid
        UNION
        SELECT DISTINCT t2.enrl_eid as eid
        FROM enrollment_base t1
        INNER JOIN enrollment_base t2
            ON t1.enrl_oper_code = t2.enrl_oper_code
            AND t1.enrl_client_machine_id = t2.enrl_client_machine_id
            AND t1.enrl_station_code = t2.enrl_station_code
            AND t1.enrl_client_version = t2.enrl_client_version
            AND t1.enrl_start_date < t2.enrl_start_date
            AND t1.enrl_end_date > t2.enrl_end_date
            AND t1.enrl_eid != t2.enrl_eid
    ),
    tab2 AS (
        SELECT
            t1.enrl_ref_id as refid,
            t1.enrl_eid as eid,
            t1.enrl_mode,
            t1.enrl_start_date as start_date,
            t1.enrl_end_date as end_date,
            t1.enrl_status as status,
            cast(t1.enrl_birth_year as varchar) as birth_year,
            t1.enrl_dist_name as dist_name,
            t1.enrl_state_name as state_name,
            t1.enrl_pincode as pincode,
            upper(t1.enrl_oper_code) as opt_id,
            t1.enrl_oper_name as oper_name,
            t1.enrl_reg_code as reg_code,
            t1.enrl_reg_name as reg_name,
            t1.enrl_agency_code as agency_code,
            t1.enrl_agency_name as agency_name,
            t1.enrl_client_machine_id as client_machine_id,
            t1.enrl_station_code as station_code,
            t1.enrl_client_version as client_version,
            t1.enrl_gps_lat as gps_lat,
            t1.enrl_gps_long as gps_long,
            t1.event_timestamp as timestamp,
            t1.client_type as pkt_source
        FROM enrollment_base t1
        INNER JOIN overlapping_pairs op
            ON t1.enrl_eid = op.eid
    )
    SELECT * FROM tab2
    ) s on s.eid = t.eid
    when not matched then
    insert(refid,eid,enrl_mode,start_date,end_date,status,birth_year,dist_name,
           state_name,pincode,opt_id,oper_name,reg_code,reg_name,agency_code,
           agency_name,client_machine_id,client_version,gps_lat,gps_long,
           station_code,timestamp,pkt_source)
    values(s.refid,s.eid,s.enrl_mode,s.start_date,s.end_date,s.status,s.birth_year,
           s.dist_name,s.state_name,s.pincode,s.opt_id,s.oper_name,s.reg_code,
           s.reg_name,s.agency_code,s.agency_name,s.client_machine_id,s.client_version,
           s.gps_lat,s.gps_long,s.station_code,s.timestamp,s.pkt_source)
    """


# ---------------- Backfill-aware date resolver ----------------
def get_dates_to_process(**context) -> list[str]:
    """
    Resolve the list of partition dates (yyyy-MM-dd) to process.

    Priority:
      1. dag_run.conf['start_date'] and dag_run.conf['end_date']  -> range
      2. dag_run.conf['partition_date']                          -> single date
      3. data_interval_start (Airflow scheduling/backfill)       -> single date
    """
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}

    start_str = conf.get("start_date")
    end_str = conf.get("end_date")
    single_date = conf.get("partition_date")

    # ---- Range backfill ----
    if start_str and end_str:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        if start > end:
            start, end = end, start
        dates = []
        d = start
        while d <= end:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        log.info("Backfill range detected: %s", dates)
        return dates

    # ---- Single manual date ----
    if single_date:
        log.info("Single backfill date detected: %s", single_date)
        return [single_date]

    # ---- Normal scheduled run ----
    data_interval_start = context.get("data_interval_start")
    if data_interval_start:
        # For '30 7 * * *' schedule, data_interval_start = previous day 07:30
        partition_date = data_interval_start.strftime("%Y-%m-%d")
        log.info("Using data_interval_start partition date: %s", partition_date)
        return [partition_date]

    # Fallback (should not normally happen)
    partition_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    log.warning("Falling back to yesterday (UTC): %s", partition_date)
    return [partition_date]


# ---------------- Main callable ----------------
def run_parallel_trans_update(**context):
    """Run the MERGE for every resolved partition date."""
    dates = get_dates_to_process(**context)
    results = []

    for d in dates:
        log.info("Processing partition date: %s", d)
        query = build_merge_query(d)
        result = trino_execute(query)
        results.append({"date": d, **result})

        if result.get("success") == 0:
            log.error("FAILED for date %s :: %s", d, result.get("msg"))
        else:
            log.info("SUCCESS for date %s", d)

    # Surface a short summary in XCom for downstream/UI inspection
    return {
        "processed_dates": dates,
        "summary": [
            {"date": r.get("date"), "success": r.get("success")} for r in results
        ],
        "failures": [r for r in results if r.get("success") == 0],
    }


# ---------------- DAG definition ----------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 2, 12),
    "email": ["techexe16.yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="opt360_parallel_transactions_eid_updt",
    default_args=default_args,
    description="DAG to update all the parallel enrolments eids (Airflow 3 + Backfill)",
    schedule="30 7 * * *",
    catchup=False,
    max_active_runs=1,            # avoid overlapping MERGEs on same target
    max_active_tasks=1,
    tags=["trino", "operator360", "backfill"],
) as dag:

    start = EmptyOperator(task_id="start")

    parallel_trans_tab_updt = PythonOperator(
        task_id="parallel_trans_tab_updt",
        python_callable=run_parallel_trans_update,
        # Airflow 3 still injects context automatically when **kwargs is used.
    )

    end = EmptyOperator(task_id="end", trigger_rule="all_done")

    start >> parallel_trans_tab_updt >> end