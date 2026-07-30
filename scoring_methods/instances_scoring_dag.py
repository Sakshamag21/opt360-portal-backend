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
import boto3

job_name = "instance_risk_scoring"
desc = "Run all the instance_risk_scoring"
schedule = "0 11 * * *"
signal_api_base_ip="10.10.116.60:8000"

CEPH_ENDPOINT_URL = "http://10.10.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-master-events-25"
CEPH_CACHE_PREFIX = "cache/airflow/operator360" 

custom_toleration = k8s.V1Toleration(
    key="strot",
    operator='Equal',
    value='true',
    effect='NoSchedule'
)

DEPENDENT_FEATURE_DAG={
    "auth":"auth_category_features.json",
    "bio":"bio_packet_fraud_features.json",
    "sustxn":"sustxn_category_feature.json",
    "work":"work_category_feature.json",
    "hardware":"hardware_category_features.json",
    "document":"document_features_combined.json"
}

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
    max_active_tasks=5,
    tags=["Operator360","Instance Level Scoring"]
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
                f"""python3 -c "import boto3;session=boto3.session.Session(aws_access_key_id='9S0KLIQO7T2XCNGH4P4A',aws_secret_access_key='XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4');s3_client=session.client('s3',endpoint_url='http://10.10.103.12:425');s3_client.download_file('prd-bi-data-platform-uploads','sparkjobs/operator360/category_risk_scoring_combined/head_instance_scoring.py','/tmp/head_instance_scoring.py')" && python3 /tmp/head_instance_scoring.py {cfg["feature_name"]} {cfg["feature_version"]}"""
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
        
        # current_task >> next_task