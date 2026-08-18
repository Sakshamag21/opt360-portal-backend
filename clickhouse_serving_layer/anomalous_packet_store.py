import subprocess
import sys
import importlib
for package in ["pyarrow", "geoip2", "pandas",'polars']:
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


from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
import polars as pl
import pandas as pd
from trino.dbapi import connect
from airflow.models.baseoperator import chain
import mysql.connector
import clickhouse_connect
import logging
import time
from datetime import date, datetime, timedelta

# -----------------------------------------------------------------------------
# Logging setup
# -----------------------------------------------------------------------------
# In Airflow, the standard `logging.getLogger(...)` is automatically hooked into
# the task instance logger, so logs appear in the Airflow UI under task logs.
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Connection / config constants
# -----------------------------------------------------------------------------
trino_host = "10.10.116.75"
trino_catalog_iceberg = 'strot'
trino_port = 8080
trino_user = "airflow_dag_op"
connection_url = "10.10.108.224"
admin_user = "Data_platform_W"
admin_password = "Dataplat_7634"
database_name = 'operator360'
table_name = 'anomalous_packets_v3_dist'
full_table_name = f'{database_name}.{table_name}'
ch_columns = [
    "ro_name", "opt_id", "packet_eid", "enrolment_type", "created_date",
    "station_id", "machine_code", "pkt_source", "anomaly_type",
    "feature_group", "comments", "updated_at"
]


def run_query(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        start_time = time.time()
        conn = connect(
            host=host,
            port=port,
            user=user
        )
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time = time.time()
        if not body:
            return {"query": query, "success": 1, "data": body, "execution_time": end_time - start_time}
        else:
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df, "execution_time": end_time - start_time}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}


def show_dbs(query, host=connection_url, admin_user=admin_user, admin_password=admin_password):
    logger.info("Executing MySQL query on host=%s, user=%s", host, admin_user)
    logger.debug("MySQL query:\n%s", query)
    try:
        connection = mysql.connector.connect(
            host=host,
            user=admin_user,
            password=admin_password
        )
        cursor = connection.cursor()
        cursor.execute(query)

        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        connection.close()
        logger.info("MySQL query returned %d rows with columns: %s", len(results), columns)

        # FIX: Convert every value to a string (except None values) before giving to Polars.
        # This prevents ALL type mismatch errors (dates, floats, zero-dates, etc.)
        safe_results = [
            [str(item) if item is not None else None for item in row]
            for row in results
        ]

        # Because all items are now strings, Polars will load them safely as Utf8 (String) columns
        df = pl.DataFrame(safe_results, schema=columns, orient="row")
        logger.debug("MySQL result Polars frame preview:\n%s", df.head())
        return df
    except Exception:
        logger.exception("MySQL query execution failed.")
        raise


data_anomaly_queries = [
    '''
    with tab1 as (
    select upper(operatorid) as opt_id,
    sid as packet_eid,
    date_parse(substring(sid, 15), '%Y%m%d%H%i%s') as created_date,
    machinecode as machine_code,
    JSON_FORMAT(
        CAST(
            MAP(
                ARRAY['Modality', 'Sub Type', 'Error Category', 'Error Reason Code'],
                ARRAY[modality, subtype, errorcategory, errorreasoncode]
            ) 
            AS JSON
        )
    ) AS comments,
    now() as updated_at
    from flink_stream.stream_enu.enu_bfc_analytics_raw_v1 where
    eventtimestamp is not null and haserror=True and modelname='UNSYSTEMATIC_MANUAL_CHECK'
    and date(eventtimestamp) >= date(current_date - interval '1' day)
    ),
    tab2 as (
    select t1.*, t2.enrolment_type, t2.pkt_source, t2.station_no as station_id
    from tab1 t1 left join flink_stream.stream_enu.ens_packet_enriched t2 on t1.packet_eid=t2.enrolment_eid and date(t2.event_timestamp)>=date(current_date - interval '7' day)
    )
    
    select * , 
    'bio_mfc_fraud' as anomaly_type, 
    'Biometrics' as feature_group
    from tab2 
    ''',
    '''
    select 
        opt_id, 
        eid as packet_eid, 
        enrolment_type, 
        date_created as created_date, 
        station_no as station_id, 
        station_machine_code as machine_code, 
        pkt_source, 
        'sustxn_res_namechange' as anomaly_type, 
        'Suspicious Transactions' as feature_group,
        CAST('' AS VARCHAR) as comments, 
        now() as updated_at 
    from strot.operator360.opt_namechange_anomalous_ot_eid_daily 
    where date_created is not null 
        and date(date_created) >= date(current_date - interval '1' day)
    ''',
    '''
    select 
        opt_id, 
        eid as packet_eid, 
        enrolment_type, 
        date_created as created_date, 
        station_no as station_id, 
        station_machine_code as machine_code, 
        pkt_source, 
        'Suspicious Transactions' as feature_group,
        'sustxn_outstate_pkts' as anomaly_type, 
        JSON_FORMAT(
            CAST(
                MAP(
                    ARRAY['machine_pincode', 'machine_district', 'machine_state', 'res_pincode', 'res_district', 'res_state'],
                    ARRAY[CAST(machine_pincode AS VARCHAR), machine_district, machine_state, CAST(res_pincode AS VARCHAR), res_district, res_state]
                ) 
                AS JSON
            )
        ) AS comments, 
        now() as updated_at 
    from strot.operator360.opt_outstate_anomalous_enu_eid_daily 
    where machine_state != res_state 
        and date_created is not null 
        and date(date_created) >= date(current_date - interval '1' day)
    ''',
    '''
    select 
        opt_id, 
        eid as packet_eid, 
        enrolment_type, 
        date_created as created_date, 
        station_no as station_id, 
        station_machine_code as machine_code, 
        pkt_source, 
        'sustxn_oddhour_pkts' as anomaly_type, 
        'Suspicious Transactions' as feature_group,
        CAST('' AS VARCHAR) as comments, 
        now() as updated_at 
    from strot.operator360.opt_oddhour_anomalous_ens_eid_daily 
    where date_created is not null 
        and date(date_created) >= date(current_date - interval '1' day)
    ''',
    '''
    select 
        upper(opt_id) as opt_id, 
        eid as packet_eid, 
        case when enrl_mode='UPDATE' then 'U' else 'N' end as enrolment_type, 
        timestamp as created_date, 
        station_code as station_id, 
        client_machine_id as machine_code, 
        coalesce(pkt_source,'') as pkt_source, 
        'work_parallel_pkts' as anomaly_type, 
        'Work' as feature_group,
        '' as comments, 
        now() as updated_at 
    from strot.operator360.txn_parallel_enrl_v1
    where 
        date(date_created) >= date(current_date - interval '1' day) 
    ''',
    '''
    with tab1 as (
        select 
            upper(operator_id) as opt_id, 
            packeteid as packet_eid, 
            packet_date as created_date, 
            'doc_qc_error_pkts' as anomaly_type, 
            'Document' as feature_group,
            JSON_FORMAT(
                CAST(
                    MAP(
                        ARRAY['Error Category', 'Priority', 'Description'],
                        ARRAY[CAST(error_category AS VARCHAR), cast(priority as varchar), description]
                    ) 
                    AS JSON
                )
            ) AS comments, 
            now() as updated_at 
        from strot.operator360.eid_qc_error_report_v2
        where 
            date(last_updated_at) >= date(current_date - interval '1' day) 
    ),
    tab2 as (
        select t1.*,
        t2.station_machine_code as machine_code,
        t2.enrolment_type,
        t2.station_no as station_id,
        t2.pkt_source as pkt_source
        from tab1 t1 left join flink_stream.stream_enu.ens_packet_enriched t2 
        on date(t2.event_timestamp)>=date(current_date- interval '60' day) and t1.packet_eid=t2.enrolment_eid 
    )
    select * from tab2 
    '''
]


def main():
    logger.info("=" * 80)
    logger.info("Starting anomalous packets DAG run for table: %s", full_table_name)
    logger.info("=" * 80)

    try:
        client = clickhouse_connect.get_client(
            host="10.10.120.86",
            port=8123,
            username="default",
            password="qwerty"
        )
        logger.info("Connected to ClickHouse at 10.10.120.86:8123")
    except Exception:
        logger.exception("Failed to connect to ClickHouse.")
        raise

    logger.info("Fetching RO Master data from MySQL...")
    pdf_master = show_dbs('''
        SELECT
            UPPER(TRIM(id)) AS opt_id,
            TRIM(ro) AS ro_name
        FROM operator360.opt_master
        WHERE risk_bucket IS NOT NULL AND TRIM(risk_bucket) != ''
    ''')
    logger.info("RO Master rows fetched: %d", pdf_master.height)
    logger.debug("RO Master preview:\n%s", pdf_master.head())

    # Ensure opt_id is clean for joining
    pdf_master = pdf_master.with_columns(pl.col("opt_id").str.strip_chars())

    dfs_to_insert = []
    total_queries = len(data_anomaly_queries)

    logger.info("Fetching anomaly data from Trino (%d queries)...", total_queries)
    for i, query in enumerate(data_anomaly_queries, 1):
        logger.info("Executing anomaly query %d/%d ...", i, total_queries)
        try:
            df_pandas = run_query(query, host='10.10.116.75')
            if 'df' in df_pandas:
                df_pandas = df_pandas['df']
            else:
                df_pandas = pd.DataFrame()

            # Skip if query returns no data
            if df_pandas.empty:
                logger.warning("Query %d/%d returned no data. Skipping.", i, total_queries)
                continue

            # Convert to Polars for safe manipulation
            df_pl = pl.DataFrame(df_pandas)
            logger.info("Query %d/%d returned %d rows.", i, total_queries, df_pl.height)

            # Clean opt_id for joining
            df_pl = df_pl.with_columns(pl.col("opt_id").str.strip_chars().str.to_uppercase())

            # Join with MySQL Master data to get ro_name
            df_pl = df_pl.join(pdf_master, on="opt_id", how="left")
            null_ro_count = df_pl.select(pl.col("ro_name").is_null().sum()).item()
            if null_ro_count:
                logger.warning("Query %d: %d rows had no matching RO in master; filling with ''.", i, null_ro_count)

            # Fill any nulls in ro_name with empty string
            df_pl = df_pl.with_columns(pl.col("ro_name").fill_null(""))

            # Add missing feature_group column expected by ClickHouse schema
            if "feature_group" not in df_pl.columns:
                logger.info("Query %d: 'feature_group' column missing; adding empty column.", i)
                df_pl = df_pl.with_columns(pl.lit("").cast(pl.Utf8).alias("feature_group"))

            # Ensure the columns are in the exact same order as ClickHouse
            df_pl = df_pl.select(ch_columns)

            # Cast datetime columns to prevent ClickHouse insertion type errors
            df_pl = df_pl.with_columns([
                pl.col("created_date").cast(pl.Datetime("us")),
                pl.col("updated_at").cast(pl.Datetime("us"))
            ])

            dfs_to_insert.append(df_pl)
            logger.info("Query %d/%d processing complete.", i, total_queries)

        except Exception as e:
            logger.exception("Error executing query %d/%d: %s", i, total_queries, e)

    # Combine all Polars DataFrames and insert into ClickHouse
    if not dfs_to_insert:
        logger.warning("No data fetched from any Trino query. Nothing to insert.")
        return

    logger.info("Concatenating %d dataframes for final insert...", len(dfs_to_insert))
    df_final_pl = pl.concat(dfs_to_insert, how="diagonal_relaxed")
    logger.info("Total records fetched from Trino: %d", df_final_pl.height)
    logger.debug("Final frame preview:\n%s", df_final_pl.head(5))

    # Re-apply null-filling on the concatenated frame
    fill_exprs = []
    for col, dtype in zip(df_final_pl.columns, df_final_pl.dtypes):
        if dtype == pl.Utf8:
            fill_exprs.append(pl.col(col).fill_null("").cast(pl.Utf8))
        elif dtype == pl.Datetime:
            fill_exprs.append(pl.col(col).fill_null(pl.datetime(1970, 1, 1)).cast(pl.Datetime("us")))
        elif dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                       pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
            fill_exprs.append(pl.col(col).fill_null(0).cast(dtype))
        elif dtype in (pl.Float32, pl.Float64):
            fill_exprs.append(pl.col(col).fill_null(0.0).cast(dtype))
        elif dtype == pl.Boolean:
            fill_exprs.append(pl.col(col).fill_null(False).cast(pl.Boolean))
        else:
            fill_exprs.append(pl.col(col).cast(pl.Utf8).fill_null(""))

    df_final_pl = df_final_pl.with_columns(fill_exprs)

    # Force final schema to match ClickHouse exactly
    df_final_pl = df_final_pl.select(ch_columns)

    # Convert Polars DataFrame to Pandas (required by client.insert_df)
    df_final_pandas = df_final_pl.to_pandas()

    logger.info("Inserting DataFrame into %s ... rows: %d", full_table_name, len(df_final_pandas))
    try:
        client.insert_df(full_table_name, df_final_pandas)
        logger.info("ClickHouse insert completed successfully for table %s.", full_table_name)
    except Exception:
        logger.exception("ClickHouse insert failed for table %s.", full_table_name)
        raise

    logger.info("DAG run finished successfully.")


default_args = {
    'owner': 'Saksham Agarwal',
    'depends_on_past': False,
    'start_date': datetime(2026, 8, 5),
    'email': ['techexe16.yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="opt360_clickhouse_anomalous_packet_store",
    default_args=default_args,
    description="DAG to update the Clikhouse based Anomalous Packet Store",
    schedule="30 1 * * *",
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    tags=["operator360", "serving_layer"],
) as dag:

    updt_clickhouse_table = PythonOperator(
        task_id="updt_clickhouse_table",
        python_callable=main,
    )

    updt_clickhouse_table