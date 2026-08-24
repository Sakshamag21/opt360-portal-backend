# v2: identical to instances_scoring_dag.py except dag_id/job_name, so
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
import boto3

from operator360.utils.pipeline_status import infer_category, wrap_shell_with_status_report, make_category_gate
from operator360.utils.pipeline_status_v2 import make_idempotency_gate

job_name = "instance_risk_scoring_v2"
desc = "Run all the instance_risk_scoring"
signal_api_base_ip="10.10.116.60:8000"

CEPH_ENDPOINT_URL = "http://10.10.103.12:425"
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-data-platform-test"
CEPH_CACHE_PREFIX = "cache/airflow/operator360"

custom_toleration = k8s.V1Toleration(
    key="strot",
    operator='Equal',
    value='true',
    effect='NoSchedule'
)

FEATURES={
    "sustxn_res_mobilechange_score":{
        "feature_name":"sustxn_res_mobilechange_score",
        "feature_version":2,
        "feature_id":"sustxn_res_mobilechange_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "auth_failure_ratio_score":{
        "feature_name":"auth_failure_ratio_score",
        "feature_version":2,
        "feature_id":"auth_failure_ratio_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "hardware_machine_signature_change_score":{
        "feature_name":"hardware_machine_signature_change_score",
        "feature_version":2,
        "feature_id":"hardware_machine_signature_change_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_oddhour_pkts_score":{
        "feature_name":"sustxn_oddhour_pkts_score",
        "feature_version":2,
        "feature_id":"sustxn_oddhour_pkts_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_outstate_pkts_score":{
        "feature_name":"sustxn_outstate_pkts_score",
        "feature_version":2,
        "feature_id":"sustxn_outstate_pkts_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_opt_hof_score":{
        "feature_name":"work_opt_hof_score",
        "feature_version":2,
        "feature_id":"work_opt_hof_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_pob_declared_score":{
        "feature_name":"work_pob_declared_score",
        "feature_version":2,
        "feature_id":"work_pob_declared_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_machine_change_score":{
        "feature_name":"work_machine_change_score",
        "feature_version":2,
        "feature_id":"work_machine_change_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_opt_machinesync_score":{
        "feature_name":"work_opt_machinesync_score",
        "feature_version":2,
        "feature_id":"work_opt_machinesync_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "hardware_multiple_biodev_score":{
        "feature_name":"hardware_multiple_biodev_score",
        "feature_version":2,
        "feature_id":"hardware_multiple_biodev_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "auth_oddhour_txn_score":{
        "feature_name":"auth_oddhour_txn_score",
        "feature_version":2,
        "feature_id":"auth_oddhour_txn_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },

    "sustxn_parallel_enrolment_score":{
        "feature_name":"sustxn_parallel_enrolment_score",
        "feature_version":2,
        "feature_id":"sustxn_parallel_enrolment_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },



    "sustxn_res_namechange_score":{
        "feature_name":"sustxn_res_namechange_score",
        "feature_version":2,
        "feature_id":"sustxn_res_namechange_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "bio_mfc_fraud_score":{
        "feature_name":"bio_mfc_fraud_score",
        "feature_version":2,
        "feature_id":"bio_mfc_fraud_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_multiple_optname_score":{
        "feature_name":"work_multiple_optname_score",
        "feature_version":2,
        "feature_id":"work_multiple_optname_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },


    "work_multiple_optname_zscore":{
        "feature_name":"work_multiple_optname_zscore",
        "feature_version":2,
        "feature_id":"work_multiple_optname_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_oddhour_pkts_zscore":{
        "feature_name":"sustxn_oddhour_pkts_zscore",
        "feature_version":2,
        "feature_id":"sustxn_oddhour_pkts_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_machine_change_zscore":{
        "feature_name":"work_machine_change_zscore",
        "feature_version":2,
        "feature_id":"work_machine_change_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_opt_machinesync_zscore":{
        "feature_name":"work_opt_machinesync_zscore",
        "feature_version":2,
        "feature_id":"work_opt_machinesync_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "hardware_machine_signature_change_zscore":{
        "feature_name":"hardware_machine_signature_change_zscore",
        "feature_version":2,
        "feature_id":"hardware_machine_signature_change_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_pob_declared_zscore":{
        "feature_name":"work_pob_declared_zscore",
        "feature_version":2,
        "feature_id":"work_pob_declared_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_outstate_pkts_zscore":{
        "feature_name":"sustxn_outstate_pkts_zscore",
        "feature_version":2,
        "feature_id":"sustxn_outstate_pkts_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "bio_mfc_fraud_zscore":{
        "feature_name":"bio_mfc_fraud_zscore",
        "feature_version":2,
        "feature_id":"bio_mfc_fraud_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "bio_sfc_fraud_zscore":{
        "feature_name":"bio_sfc_fraud_zscore",
        "feature_version":2,
        "feature_id":"bio_sfc_fraud_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "work_opt_hof_zscore":{
        "feature_name":"work_opt_hof_zscore",
        "feature_version":2,
        "feature_id":"work_opt_hof_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "hardware_multiple_biodev_zscore":{
        "feature_name":"hardware_multiple_biodev_zscore",
        "feature_version":2,
        "feature_id":"hardware_multiple_biodev_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_res_namechange_zscore":{
        "feature_name":"sustxn_res_namechange_zscore",
        "feature_version":2,
        "feature_id":"sustxn_res_namechange_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },
    "sustxn_res_mobilechange_zscore":{
        "feature_name":"sustxn_res_mobilechange_zscore",
        "feature_version":2,
        "feature_id":"sustxn_res_mobilechange_zscore_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    },

    "document_category_score":{
        "feature_name":"document_category_score",
        "feature_version":2,
        "feature_id":"document_category_score_v2",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True,
        "dependent_feature_id":''
    }
}


def _get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY
    )



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
    schedule="0 5 * * *",  # triggered only by controller_pipeline_v2
    catchup=False,
    max_active_runs=3,
    max_active_tasks=1,
    tags=["Operator360","Instance Level Scoring","v2"]
) as dag:
    tasks = {}
    category_gates = {}
    idempotency_gates = {}  # key -> gate that skips this task if it already succeeded today

    for key, cfg in FEATURES.items():
        feature_category = infer_category(key)
        task_id = f'task-id-{cfg["feature_name"]}-{cfg["feature_version"]}'
        inner_cmd = f"""python3 -c "import boto3;session=boto3.session.Session(aws_access_key_id='9S0KLIQO7T2XCNGH4P4A',aws_secret_access_key='XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4');s3_client=session.client('s3',endpoint_url='http://10.10.103.12:425');s3_client.download_file('prd-bi-data-platform-uploads','sparkjobs/operator360/category_risk_scoring_combined/head_instance_scoring.py','/tmp/head_instance_scoring.py')" && python3 /tmp/head_instance_scoring.py {cfg["feature_name"]} {cfg["feature_version"]}"""
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
        # re-triggers this DAG with an expanded valid_categories list, this
        # skips any feature that already reported success for today's
        # pipeline_run_id instead of re-running the Spark job and appending
        # a duplicate score row for it.
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

        # current_task >> next_task