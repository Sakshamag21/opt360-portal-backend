import subprocess
import sys
import os
import importlib

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
import json

def ingest_data():
    try:
        # Note: Added single quotes around yesterday in SQL so it executes as a valid string literal
        
        df = sq.query(f'''
        select enrolment_eid, upper(session_operatorid) as opt_id, 
        case when (enrolment_type='N' or enrolment_type='New') then 'N'
        else 'U' end as pkt_type,
        station_no as station_id,
        station_machine_code as machine_code,
        pkt_source, date_parse(substr(enrolment_eid, 15), '%Y%m%d%H%i%s') as created_at
        from flink_stream.stream_enu.ens_packet_enriched 
        where date(event_timestamp) = date(current_date - interval '1' day) 
        ''', host='10.10.116.75')
        # print(df)

        # print(df['df'].head())
        
        if 'df' not in df:
            print(df)
            
        df=df['df']

        if df.empty:
            logging.info(f"Date: yesterday | Result: SKIPPED (No data found in query)")
            return

        url = "http://10.10.118.47:8089/sid/batch_ingest"
        batch_size = 10000  
        total_rows = len(df)
        successful_batches = 0
        failed_batches = 0

        with requests.Session() as session:
            session.headers.update({
                "Content-Type": "application/json",
            })
            
            for i in range(0, total_rows, batch_size):
                chunk = df.iloc[i : i + batch_size]
                items_buffer = []
                
                for _, row in chunk.iterrows():
                    item = {
                        "sid": row["enrolment_eid"],
                        "value": {
                            "opt_id": row["opt_id"],
                            "pkt_type": row["pkt_type"],
                            "station_id": row['station_id'],
                            "created_at": str(row['created_at']),
                            "machine_code": row['machine_code'],
                            "pkt_source":row['pkt_source']
                        }
                    }
                    # print(item)
                    items_buffer.append(item)
                
                payload = {"items": items_buffer}
                
                try:
                    response = session.post(url, data=json.dumps(payload))
                    response.raise_for_status()
                    successful_batches += 1
                except Exception as batch_error:
                    failed_batches += 1
                    print(f"Date: yesterday | Batch starting at row {i} failed: {batch_error}")
                    logging.error(f"Date: yesterday | Batch starting at row {i} failed: {batch_error}")
            
            # Log the final verdict for this specific date
            if failed_batches == 0:
                logging.info(f"Date: yesterday | Result: SUCCESS | Rows processed: {total_rows} across {successful_batches} batches.")
            else:
                logging.warning(f"Date: yesterday | Result: PARTIAL SUCCESS | Successful batches: {successful_batches}, Failed batches: {failed_batches}")

    except Exception as e:
        logging.error(f"Date: yesterday | Result: FAILED | Execution exception: {e}")

default_args = {
    'owner': 'Saksham Agarwal',
    'depends_on_past': False,
    'start_date': pendulum.datetime(2026, 5, 7, tz="UTC"),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 2,
}

dag = DAG(
    'opt360_packet_store',
    default_args=default_args,
    description='DAG to check the operator360 enviroment and generate the health check report',
    schedule="30 2 * * *",
    catchup=False,
    max_active_tasks=1,
    max_active_runs=1,
    tags=['Operator360', 'packet_store']
)


pkt_store_task= PythonOperator(
    task_id='packet_store',
    python_callable=ingest_data,
    trigger_rule='all_done',
    dag=dag,
)

trigger_dag_b = TriggerDagRunOperator(
    task_id="trigger_operator_eid_store",
    trigger_dag_id="operator_eid_store"
)

pkt_store_task >> trigger_dag_b