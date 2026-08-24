import subprocess
import sys
import os
import importlib
import json
import boto3

package = "strot_query"
try:
    importlib.import_module(package)
except ImportError:
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        '--no-cache-dir',
        '--index-url', 'http://10.10.206.59:8080/repository/pypi-local/simple',
        '--trusted-host', '10.10.206.59',
        package
    ])
    importlib.invalidate_caches()
    globals()[package] = importlib.import_module(package)

import pendulum
import requests
import time
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.models import Variable
import logging
from airflow.exceptions import AirflowSkipException
from airflow.utils.trigger_rule import TriggerRule
import pytz
from zoneinfo import ZoneInfo
import strot_query as sq
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


JOB_NAME = "operator_packet_store"
DESC = "Dag for filling the operator to packet mapping data"
BASE_URL = "http://10.10.118.51:8089"
INGEST_URL = f"{BASE_URL}/optid/batch_put"
BATCH_SIZE = 1000

CEPH_ENDPOINT_URL = "http://10.10.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-data-platform-test"
CEPH_CACHE_PREFIX = "cache/airflow/operator360" 


logger = logging.getLogger("operator_packet_store")
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')


# ---------------------------------------------------------------------------
# S3 / Ceph Helper Functions
# ---------------------------------------------------------------------------
def get_s3_client():
    """Create and return a boto3 S3 client configured for Ceph."""
    return boto3.client(
        's3',
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY,
    )


def get_run_date_str():
    """Return the data date (yesterday) as YYYY-MM-DD string, used for partitioning."""
    return (pendulum.now('UTC') - timedelta(days=1)).strftime('%Y-%m-%d')


def save_summary_to_s3(run_date_str, summary_dict):
    """
    Save the ingestion summary as a JSON file in S3.
    Path: <prefix>/operator_eid_store/dt=<YYYY-MM-DD>/summary.json
    """
    s3_client = get_s3_client()
    key = f"{CEPH_CACHE_PREFIX}/operator_eid_store/dt={run_date_str}/summary.json"

    def default_serializer(o):
        if isinstance(o, (datetime, pendulum.DateTime)):
            return o.isoformat()
        try:
            return str(o)
        except Exception:
            return None

    try:
        s3_client.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=key,
            Body=json.dumps(summary_dict, default=default_serializer, indent=2).encode('utf-8'),
            ContentType='application/json',
        )
        logger.info(f"Saved summary to s3://{CEPH_BUCKET_NAME}/{key}")
        return key
    except Exception as e:
        logger.error(f"Failed to save summary to S3: {e}")
        return None


# ---------------------------------------------------------------------------
# Core Pipeline Functions
# ---------------------------------------------------------------------------
def fetch_data_from_trino():
    logger.info(f"Fetching data from Trino for date: yesterday...")
    query = f'''
    select
        enrolment_eid,
        upper(session_operatorid) as opt_id,
        substr(enrolment_eid, 15) as timestamp_str
    from flink_stream.stream_enu.ens_packet_enriched
    where cast(event_timestamp as date) = DATE (current_date - interval '1' day)
    '''
    try:
        # Assuming sq is globally available from your environment
        results = sq.query(query, host='10.10.116.39')['df']

        if hasattr(results, 'to_dict') and hasattr(results, 'iterrows'):
            results = results.to_dict('records')

        logger.info(f"Fetched {len(results)} records from Trino for yesterday.")
        if len(results) > 0:
            logger.debug(f"First record type is {type(results[0])}")
            logger.debug(f"First record value: {results[0]}")
        return results
    except Exception as e:
        logger.error(f"Trino query failed for yesterday: {e}")
        return []


def ingest_bulk_data(records):
    batch = []
    total_ingested = 0
    batch_number = 1
    total_ingestion_time = 0.0
    failed_batches = []

    logger.info(f"Starting bulk ingestion: {len(records)} records in batches of {BATCH_SIZE}...")

    for row in records:
        enrolment_eid = None
        opt_id = None
        timestamp_str = None

        if isinstance(row, dict):
            enrolment_eid = row.get('enrolment_eid')
            opt_id = row.get('opt_id')
            timestamp_str = row.get('timestamp_str')
        elif isinstance(row, (list, tuple)):
            if len(row) >= 3:
                enrolment_eid = row[0]
                opt_id = row[1]
                timestamp_str = row[2]
        elif hasattr(row, '_tuple'):
            row_data = row._tuple()
            if len(row_data) >= 3:
                enrolment_eid = row_data[0]
                opt_id = row_data[1]
                timestamp_str = row_data[2]

        if not all([enrolment_eid, opt_id, timestamp_str]):
            logger.warning(f"Skipping row due to missing data or unexpected format: {type(row)} -> {row}")
            continue

        item = {
            "opt_id": opt_id,
            "timestamp": timestamp_str,
            "sid": enrolment_eid
        }
        batch.append(item)

        if len(batch) == BATCH_SIZE:
            payload = {"items": batch}
            headers = {"Content-Type": "application/json"}
            # print(INGEST_URL)
            try:
                start_time = time.perf_counter()
                response = requests.post(INGEST_URL, json=payload, headers=headers)
                end_time = time.perf_counter()

                latency_ms = (end_time - start_time) * 1000
                total_ingestion_time += (end_time - start_time)

                if response.status_code == 200:
                    total_ingested += len(batch)
                    logger.info(f"Batch {batch_number} ingested | Latency: {latency_ms:.2f} ms | Progress: {total_ingested}/{len(records)}")
                else:
                    logger.error(f"Batch {batch_number} failed! HTTP Status: {response.status_code} | Server says: {response.text}")
                    failed_batches.append(batch_number)
                    break
            except requests.exceptions.ConnectionError:
                logger.error(f"Connection Error: Could not connect to server at {BASE_URL}.")
                failed_batches.append(batch_number)
                break

            batch = []
            batch_number += 1
            time.sleep(0.1)

    if batch:
        payload = {"items": batch}
        headers = {"Content-Type": "application/json"}
        try:
            start_time = time.perf_counter()
            print(INGEST_URL)
            response = requests.post(INGEST_URL, json=payload, headers=headers)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            total_ingestion_time += (end_time - start_time)

            if response.status_code == 200:
                total_ingested += len(batch)
                logger.info(f"Final Batch {batch_number} ingested | Latency: {latency_ms:.2f} ms | Progress: {total_ingested}/{len(records)}")
            else:
                logger.error(f"Final Batch {batch_number} failed! HTTP Status: {response.status_code}")
                failed_batches.append(batch_number)
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection Error: Could not connect to server at {BASE_URL}.")
            failed_batches.append(batch_number)

    logger.info(f"--- Ingestion Summary for batch ---")
    logger.info(f"Total records ingested: {total_ingested}")
    logger.info(f"Total ingestion time: {total_ingestion_time:.2f} seconds")
    
    throughput = round(total_ingested / total_ingestion_time, 2) if total_ingestion_time > 0 else 0

    return {
        "total_ingested": total_ingested,
        "total_records": len(records),
        "batch_size": BATCH_SIZE,
        "total_batches_processed": batch_number,
        "failed_batches": failed_batches,
        "total_ingestion_time_sec": round(total_ingestion_time, 2),
        "throughput_records_per_sec": throughput,
    }


def main():
    logger.info("Starting ingestion process...")
    run_date_str = get_run_date_str()
    logger.info(f"Run date (yesterday): {run_date_str}")

    try: 
        records = fetch_data_from_trino()
        if not records:
            logger.warning(f"No records returned for yesterday. Skipping ingestion.")
            # Save empty summary to S3 to indicate run completion with no data
            save_summary_to_s3(run_date_str, {
                "run_date": run_date_str,
                "status": "NO_DATA",
                "total_records": 0,
                "total_ingested": 0,
                "total_ingestion_time_sec": 0
            })
            return

        # Ingest data
        summary = ingest_bulk_data(records)
        summary["run_date"] = run_date_str
        summary["status"] = "SUCCESS" if summary["total_ingested"] == summary["total_records"] else "PARTIAL"
        
        # Save only the results/summary to S3
        save_summary_to_s3(run_date_str, summary)
        
        logger.info(f'Ingested {summary["total_ingested"]} rows out of {summary["total_records"]} rows')
        logger.info(f"Results saved to S3 under prefix: {CEPH_CACHE_PREFIX}/operator_eid_store/dt={run_date_str}/summary.json")
        
    except Exception as e:
        logger.error(f'error in ingestion or data fetching, {e}', exc_info=True)
        # Persist the failure summary to S3
        try:
            save_summary_to_s3(run_date_str, {
                "run_date": run_date_str,
                "status": "FAILED",
                "error": str(e),
            })
        except Exception as inner:
            logger.error(f"Could not write failure summary to S3: {inner}")


default_args = {
    'owner': 'Saksham Agarwal',
    'depends_on_past': False,
    'start_date': pendulum.datetime(2026, 8, 12, tz="UTC"),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
}

dag = DAG(
    'operator_eid_store',
    default_args=default_args,
    description='DAG to check the operator360 enviroment and generate the health check report',
    catchup=False,
    max_active_tasks=1,
    max_active_runs=1,
    tags=['Operator360', 'operator_eid_store']
)

opt_store_task= PythonOperator(
    task_id='opt_store_task_1',
    python_callable=main,
    trigger_rule='all_done',
    dag=dag,
)

opt_store_task    