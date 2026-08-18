# v2: identical to combined_scoring_dag.py except dag_id/job_name, so
# operator_dag_manager_v2.py's retry orchestration can trigger it in isolation
# from the v1 pipeline. Same Spark scripts/S3 paths as v1 - only the Airflow
# dag_id changes. See operator_dag_manager_v2.py for the retry logic.
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime, timedelta
from airflow.models import Variable
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
import logging
from airflow.exceptions import AirflowSkipException
import requests
from airflow.utils.trigger_rule import TriggerRule
import pytz
from kubernetes.client import models as k8s

from operator360.utils.pipeline_status import infer_category, wrap_shell_with_status_report, make_category_gate
from operator360.utils.pipeline_status_v2 import make_idempotency_gate

job_name = "combined_risk_scoring_v2"
desc = "Run all the combined_risk_score"
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
        "feature_id":"work_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "bio_category_score":{
        "feature_name":"bio_category_score",
        "feature_version":2,
        "feature_id":"bio_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "hardware_category_score":{
        "feature_name":"hardware_category_score",
        "feature_version":2,
        "feature_id":"hardware_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "sustxn_category_score":{
        "feature_name":"sustxn_category_score",
        "feature_version":2,
        "feature_id":"sustxn_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "auth_category_score":{
        "feature_name":"auth_category_score",
        "feature_version":2,
        "feature_id":"auth_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "risk_score":{
        "feature_name":"risk_score",
        "feature_version":3,
        "feature_id":"risk_score_v3",
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
    "execution_timeout": timedelta(minutes=20),
    "email": ["techexe16.yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}

with DAG(
    dag_id=job_name,
    default_args=default_args,
    description=desc,
    schedule=None,  # triggered only by controller_pipeline_v2
    catchup=False,
    max_active_runs=3,
    max_active_tasks=2,
    tags=["Operator360","Category Level Scoring","v2"]
) as dag:
    tasks = {}
    category_gates = {}
    idempotency_gates = {}  # key -> gate that skips this task if it already succeeded today

    for key, cfg in FEATURES.items():
        feature_category = infer_category(key)  # None for risk_score - no gate, no skip
        task_id = f'task-id-{cfg["feature_name"]}-{cfg["feature_version"]}'
        inner_cmd = f"""python3 -c "import boto3;session=boto3.session.Session(aws_access_key_id='9S0KLIQO7T2XCNGH4P4A',aws_secret_access_key='XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4');s3_client=session.client('s3',endpoint_url='http://10.10.103.12:425');s3_client.download_file('prd-bi-data-platform-uploads','sparkjobs/operator360/category_risk_scoring_combined/head_combined_risk_scoring.py','/tmp/head_combined_risk_scoring.py')" && python3 /tmp/head_combined_risk_scoring.py {cfg["feature_name"]} {cfg["feature_version"]}"""
        task = KubernetesPodOperator(
            namespace='strot-spark',
            service_account_name='strot-service-account',
            image='harbor-registry-prod.uidai.gov.in/data-platform/pyspark_duckdb:4.0.7',
            config_file='/opt/airflow/dags/gpu_kubeconfig_hdc',
            name= f'zzzz-{cfg["feature_name"]}-{cfg["feature_version"]}',
            task_id=task_id,
            cmds=["/bin/bash","-c"],
            arguments=[
                wrap_shell_with_status_report(inner_cmd, dag_id=job_name, task_key=task_id, category=feature_category)
            ],
            env_vars={
                "PIPELINE_RUN_ID": "{{ dag_run.conf.get('pipeline_run_id') or run_id }}",
                "TASK_LOG_URL": "{{ ti.log_url }}",
            },
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

        # A task should succeed at most once a day: if a same-day cascade
        # re-triggers this DAG (necessarily including every category valid
        # today, not just a newly-recovered one - see
        # _cascade_layer2_layer3()'s docstring in operator_dag_manager_v2.py
        # for why), this skips any category/risk_score task that already
        # reported success for today's pipeline_run_id instead of
        # re-running the Spark job and appending a duplicate score row.
        idempotency_gate = make_idempotency_gate(f"gate_dup_{task_id}", dag_id=job_name, task_key=task_id)
        idempotency_gates[key] = idempotency_gate
        idempotency_gate >> task

        if feature_category:
            if feature_category not in category_gates:
                category_gates[feature_category] = make_category_gate(f"gate_{feature_category}", feature_category)
            category_gates[feature_category] >> idempotency_gate

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
                    tasks[dep] >> idempotency_gates[key]

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
