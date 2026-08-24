import boto3
import json
import pendulum
from datetime import datetime, timedelta
import mysql.connector
import time
import pandas as pd
import logging

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.exceptions import AirflowSkipException, AirflowException
from trino.dbapi import connect

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------
trino_host = "10.10.116.75"
trino_catalog_iceberg = 'strot'
trino_port = 8080
trino_user = "opt_master_updt"
connection_url = "10.81.108.109"
admin_user = "Data_platform_W"
admin_password = "Dataplat_7634"

# S3 / Ceph Config (Must match the previous DAG)
CEPH_ENDPOINT_URL = "http://10.81.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-data-platform-test"
CEPH_CACHE_PREFIX = "cache/airflow/operator360" 


# ---------------------------------------------------------------------------
# S3 Check Function
# ---------------------------------------------------------------------------
def check_s3_report_success(**kwargs):
    """
    Reads the summary.json from S3 for yesterday's date.
    Skips the DAG if the file doesn't exist or status is not 'SUCCESS'.
    Fails the DAG if there is an actual connection error to S3.
    """
    run_date_str = (pendulum.now('UTC') - timedelta(days=1)).strftime('%Y-%m-%d')
    s3_key = f"{CEPH_CACHE_PREFIX}/operator_eid_store/dt={run_date_str}/summary.json"
    
    logger.info(f"Checking for S3 report at: s3://{CEPH_BUCKET_NAME}/{s3_key}")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY,
    )
    
    try:
        response = s3_client.get_object(Bucket=CEPH_BUCKET_NAME, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        summary = json.loads(content)
        
        status = summary.get('status')
        logger.info(f"Found report for {run_date_str}. Status: {status}")
        
        if status == 'SUCCESS':
            logger.info("S3 check passed. Proceeding with MySQL update.")
            return True
        else:
            # If status is FAILED, PARTIAL, or NO_DATA, we skip the downstream task
            raise AirflowSkipException(f"Skipping DAG because S3 report status is '{status}', not 'SUCCESS'.")
            
    except s3_client.exceptions.NoSuchKey:
        raise AirflowSkipException(f"Skipping DAG because S3 report was not found at {s3_key}")
    except s3_client.exceptions.ClientError as e:
        # Handle 404s from boto3 gracefully as a Skip
        if e.response['Error']['Code'] == '404' or 'NoSuchKey' in str(e):
            raise AirflowSkipException(f"Skipping DAG because S3 report was not found at {s3_key}")
        logger.error(f"S3 ClientError while checking report: {e}")
        raise AirflowException(f"Failed to access S3 report: {e}")
    except Exception as e:
        # If S3 is down or credentials are wrong, fail the task so it alerts/retries
        logger.error(f"Unexpected error checking S3 report: {e}")
        raise AirflowException(f"Unexpected error reading S3 report: {e}")


# ---------------------------------------------------------------------------
# Core Pipeline Functions
# ---------------------------------------------------------------------------
def write_data_to_mysql(query, data=None, many=False, host=connection_url, database='operator360', admin_user=admin_user, admin_password=admin_password):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=admin_user,
            password=admin_password,
            database=database
        )
        cursor = connection.cursor()

        if data is not None:
            if many:
                cursor.executemany(query, data)
            else:
                cursor.execute(query, tuple(data))
        else:
            cursor.execute(query)

        connection.commit()
        logger.info(f"Successfully updated {cursor.rowcount} rows.")
        cursor.close()
        connection.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        # Raise AirflowException so the task fails and triggers alerts/retries
        raise AirflowException(f"Database error: {e}")


def trino(query, host=trino_host, port=trino_port, user=trino_user):
    """Execute a Trino query and return a dict containing the result or error."""
    logger.info(f"[TRINO] Connecting to host={host}:{port} user={user}")
    preview = query.strip()[:500].replace("\n", " ")
    logger.info(f"[TRINO] Executing query (preview): {preview}{'...' if len(query.strip()) > 500 else ''}")
    try:
        start_time = time.time()
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time = time.time()
        execution_time = round(end_time - start_time, 3)
        logger.info(f"[TRINO] Query executed successfully in {execution_time}s | rows_returned={len(body)}")

        if not body:
            logger.info("[TRINO] Query returned no rows.")
            return {"query": query, "success": 1, "data": body, "execution_time": execution_time}
        else:
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            logger.info(f"[TRINO] Columns: {cols}")
            return {"query": query, "success": 1, "data": (cols, body), "df": df, "execution_time": execution_time}
    except Exception as e:
        logger.error(f"[TRINO] Query FAILED with error: {e}", exc_info=True)
        # Raise AirflowException so the task fails immediately
        raise AirflowException(f"Trino query failed: {e}")


def main():
    last_pkt = trino(f'''
        select upper(session_operatorid) as opt_id, max(event_timestamp) as pkt_timestamp
        from flink_stream.stream_enu.ens_packet_enriched where session_operatorid!='ssup_operator' 
        and date(event_timestamp)=date(current_date - interval '1' day) 
        group by 1
    ''')
    
    # If Trino fails, it raises AirflowException above, so we won't reach here.
    # But keeping a safety check:
    if 'df' not in last_pkt:
        logger.error(f'Error in last_packet processing in trino, {last_pkt}')
        raise AirflowException("Trino did not return a dataframe.")
        
    last_pkt = last_pkt['df']
    
    data = list(zip(
        last_pkt['opt_id'].astype(str), 
        last_pkt['pkt_timestamp'].astype(str)
    ))
    
    query = """
        INSERT INTO operator360.opt_master (id, last_packet_timestamp)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE 
        last_packet_timestamp = VALUES(last_packet_timestamp)
    """
    
    batch_size = 10000
    total_records = len(data)
    
    if total_records == 0:
        logger.info("No new records found to update.")
        return

    logger.info(f"Starting bulk update for {total_records} records...")

    for i in range(0, total_records, batch_size):
        batch = data[i : i + batch_size]
        write_data_to_mysql(query, data=batch, many=True)
        logger.info(f"Processed {min(i + batch_size, total_records)} / {total_records} records")

    logger.info("Bulk update completed!")


# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 8, 12),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
}

dag = DAG(
    'opt360_last_packet_timestamp',
    default_args=default_args,
    description='DAG to update the last packet timestamp in opt_master if previous S3 report is SUCCESS',
    schedule_interval="0 3 * * *",
    catchup=False,
    concurrency=1,
    tags=['operator360', 'opt_master']
)

# Task 1: Check S3 for success status
check_s3_status_task = PythonOperator(
    task_id='check_s3_status_task',
    python_callable=check_s3_report_success,
    dag=dag,
)

# Task 2: Update MySQL (Will only run if Task 1 does not skip)
updt_packet_timestamp = PythonOperator(
    task_id='updt_packet_timestamp',
    python_callable=main,
    dag=dag,
)

updt_packet_timestamp