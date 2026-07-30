from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime
from airflow.models import Variable
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
import logging
from airflow.exceptions import AirflowSkipException
import requests
from airflow.utils.trigger_rule import TriggerRule
import pytz
from kubernetes.client import models as k8s

job_name = "combined_risk_scoring"
desc = "Run all the combined_risk_score"
schedule = "0 12 * * *"
signal_api_base_ip="10.10.116.60:8000"


custom_toleration = k8s.V1Toleration(
    key="strot",
    operator='Equal',
    value='true',
    effect='NoSchedule'
)



FEATURES={
    "work_category_score":{
        "feature_name":"work_category_score",
        "feature_version":2,
        "feature_id":"work_category_score_24h_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "bio_category_score":{
        "feature_name":"bio_category_score",
        "feature_version":2,
        "feature_id":"bio_category_score_24h_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "hardware_category_score":{
        "feature_name":"hardware_category_score",
        "feature_version":2,
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "sustxn_category_score":{
        "feature_name":"sustxn_category_score",
        "feature_version":2,
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "auth_category_score":{
        "feature_name":"auth_category_score",
        "feature_version":2,
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "risk_score":{
        "feature_name":"risk_score",
        "feature_version":3,
        "dependencies":["work_category_score","bio_category_score","hardware_category_score","sustxn_category_score","auth_category_score"],
        "signal_exists":False,
        "is_daily":True
    }
    
}


def run_signals(feature_id):
    try:
        res_try=get_signals_info(feature_id)
        for signal_metadata in res_try:
            push_signals_kafka(signal_metadata)
    except Exception as e:
        print(f"Error in generating signal for feature id : {feature_id}, error: {e}")


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 12),
    "email": ["techexe16.yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}

with DAG(
    dag_id=job_name,
    default_args=default_args,
    description=desc,
    schedule=schedule,
    catchup=False,
    max_active_runs=3,
    max_active_tasks=2,
    tags=["Operator360","Category Level Scoring"]
) as dag:
    tasks = {}

    for key, cfg in FEATURES.items():
        task = KubernetesPodOperator(
            namespace='strot-spark',
            service_account_name='strot-service-account',
            image='harbor-registry-prod.uidai.gov.in/data-platform/pyspark_duckdb:4.0.7',
            config_file='/opt/airflow/dags/gpu_kubeconfig_hdc',
            name= f'zzzz-{cfg["feature_name"]}-{cfg["feature_version"]}',
            task_id=f'task-id-{cfg["feature_name"]}-{cfg["feature_version"]}',
            cmds=["/bin/bash","-c"],
            arguments=[
                f"""python3 -c "import boto3;session=boto3.session.Session(aws_access_key_id='9S0KLIQO7T2XCNGH4P4A',aws_secret_access_key='XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4');s3_client=session.client('s3',endpoint_url='http://10.10.103.12:425');s3_client.download_file('prd-bi-data-platform-uploads','sparkjobs/operator360/category_risk_scoring_combined/head_combined_risk_scoring.py','/tmp/head_combined_risk_scoring.py')" && python3 /tmp/head_combined_risk_scoring.py {cfg["feature_name"]} {cfg["feature_version"]}"""
            ],
            container_resources=k8s.V1ResourceRequirements(
                requests={"cpu": "1", "memory": "2Gi"},
                limits={"cpu": "1", "memory": "2Gi"}
            ),
            tolerations=[custom_toleration],
            in_cluster=False,
            get_logs=True,
            log_events_on_failure=True,
        )
        tasks[key] = task

        if cfg['signal_exists']:
            signal_task = PythonOperator(
                task_id=f"signal_{key}",
                python_callable=run_signals,
                op_kwargs={
                    "feature_id": cfg["feature_id"]
                },
            )
            tasks[f"signals_{key}"] = signal_task

    # Apply dependencies defined in FEATURES
    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            for dep in cfg["dependencies"]:
                if dep in tasks:
                    tasks[dep] >> tasks[key]
        
        if "signal_exists" in cfg and cfg["signal_exists"]:
            if f"signals_{key}" in tasks:
                tasks[key] >> tasks[f"signals_{key}"]

    # Sequential execution with independence between groups
    task_list = list(tasks.values())

    # Track which tasks already have upstream dependencies
    tasks_with_dependencies = set()
    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            tasks_with_dependencies.add(tasks[key])
        
        # Mark signal tasks (they depend on their feature task)
        if cfg['signal_exists'] and f"signals_{key}" in tasks:
            tasks_with_dependencies.add(tasks[f"signals_{key}"])

    # Chain tasks sequentially, but use ALL_DONE for tasks without explicit dependencies
    # for i in range(len(task_list) - 1):
    #     current_task = task_list[i]
    #     next_task = task_list[i + 1]
        
    #     if next_task not in tasks_with_dependencies:
    #         next_task.trigger_rule = TriggerRule.ALL_DONE
        
    #     current_task >> next_task