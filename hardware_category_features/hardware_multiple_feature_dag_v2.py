# v2: identical to hardware_multiple_feature_dag.py except dag_id/job_name,
# so operator_dag_manager_v2.py's retry orchestration can trigger it in
# isolation from the v1 pipeline. See operator_dag_manager_v2.py for the
# retry logic.
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.models import Variable
from operator360.work_category_features.insert_work_features import run_one_feature
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
import logging
from airflow.exceptions import AirflowSkipException
from airflow.utils.trigger_rule import TriggerRule
import pytz
from zoneinfo import ZoneInfo

# Import functions from your checking module
# Adjust the import path based on where you saved the file in your Airflow plugins/dags folder
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
from operator360.utils.s3_audit_logger import audit_to_s3
from operator360.utils.pipeline_status import report_status, parse_bool
from operator360.utils.pipeline_status_v2 import skip_if_already_succeeded

job_name = "hardware_category_features_v2"
category = "hardware"
desc = "Run all the  Hardware Features"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    "hardware_multiple_biodev_instances": {
        "feature_name": "hardware_multiple_biodev_instances",
        "feature_version": 2,
        "feature_id": "hardware_multiple_biodev_instances_24h_v2",
        "sql_local_path": "/opt/airflow/dags/operator360/hardware_category_features/hardware_multiple_biodev_instances_24h_v2.sql",
        "dependencies": [],
        "signal_exists": False,
        "is_daily": True
    },
    "hardware_machine_change_instances": {
        "feature_name": "hardware_machine_change_instances",
        "feature_version": 2,
        "feature_id": "hardware_machine_change_instances_24h_v2",
        "sql_local_path": "/opt/airflow/dags/operator360/hardware_category_features/hardware_machine_change_instances_24h_v2.sql",
        "dependencies": [],
        "signal_exists": True,
        "is_daily": True
    }
}

def run_signals(feature_id):
    try:
        res_try = get_signals_info(feature_id)
        for signal_metadata in res_try:
            push_signals_kafka(signal_metadata)
    except Exception as e:
        print(f"Error in generating signal for feature id : {feature_id}, error: {e}")

@skip_if_already_succeeded(dag_id=job_name)
@audit_to_s3(dag_id=job_name)
@report_status(dag_id=job_name, category=category)
def run_single_features(feature_name, feature_version, feature_id, sql_file, end_date, is_daily=True, data_interval_start=None, pipeline_run_id=None, is_daily_run=None, log_url=None, try_number=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    if is_daily:
        # This DAG has no hourly-cadence features, so is_daily just means
        # "only actually run on the manager's once-a-day promotion tick".
        if not parse_bool(is_daily_run):
            logger.info("Skipping %s - not the daily promotion run", feature_name)
            raise AirflowSkipException("Skipping - not the daily promotion run")

        # Raw Data Check - only reached on the promotion tick.
        logger.info("Verifying raw data availability for feature_id: %s", feature_id)

        source_tables_res = get_source_tables(category="hardware")

        if not source_tables_res.get('success'):
            logger.error("Failed to fetch source tables metadata. Error: %s", source_tables_res.get('error'))
            raise AirflowSkipException("Skipped because metadata DB lookup failed.")

        mapping = source_tables_res
        source_table = mapping.get(feature_id)

        if not source_table:
            logger.warning("No source_table found in metadata for feature_id=%s. Proceeding with feature run anyway.", feature_id)
        else:
            has_raw_data = check_raw_tables(source_table)
            if not has_raw_data:
                logger.warning("Skipping feature %s because raw table %s has no data for yesterday.", feature_name, source_table)
                raise AirflowSkipException(f"Skipping task because raw data is missing for {source_table}")

    # Proceed to run the actual feature
    print(f"Executing feature {feature_name}")
    try:
        logger.info("Running feature %s v%s with sql=%s, end_date=%s",
                    feature_name, feature_version, sql_file, end_date)
        run_one_feature(
            feature_name=feature_name,
            feature_version=feature_version,
            sql_file=sql_file,
            end_date=end_date
        )
        logger.info("Feature executed successfully %s v%s at end_date %s", feature_name, feature_version, end_date)
    except Exception as e:
        logger.exception("Feature %s failed: %s", feature_name, e)
        raise

default_args = {
    "owner": "Saksham Agarwal",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 21, tzinfo=ZoneInfo("Asia/Kolkata")),
    "execution_timeout": timedelta(minutes=40),
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
    max_active_runs=1,
    max_active_tasks=1,
    tags=["Operator360", "Hardware Category", "v2"]
) as dag:

    tasks = {}

    for key, cfg in FEATURES.items():
        feature_id = cfg['feature_id']

        task = PythonOperator(
            task_id=f"run_{feature_id}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg["feature_id"],  # Passed feature_id here so we can look it up
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ data_interval_start | ds}}",
                "is_daily": cfg["is_daily"],
                "data_interval_start": "{{data_interval_start}}",
                "pipeline_run_id": "{{ dag_run.conf.get('pipeline_run_id') or run_id }}",
                "is_daily_run": "{{ dag_run.conf.get('is_daily_run', 'true') }}",
                "log_url": "{{ ti.log_url }}",
                "try_number": "{{ ti.try_number }}",
            },
        )
        tasks[cfg['feature_id']] = task

        if cfg['signal_exists']:
            signal_task = PythonOperator(
                task_id=f"signal_{cfg['feature_id']}",
                python_callable=run_signals,
                op_kwargs={
                    "feature_id": cfg["feature_id"]
                },
            )
            tasks[f"signals_{cfg['feature_id']}"] = signal_task

    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            for dep in cfg["dependencies"]:
                if dep in tasks:
                    tasks[dep] >> tasks[cfg['feature_id']]

        if "signal_exists" in cfg and cfg["signal_exists"]:
            if f"signals_{cfg['feature_id']}" in tasks:
                tasks[cfg['feature_id']] >> tasks[f"signals_{cfg['feature_id']}"]

    task_list = list(tasks.values())

    tasks_with_dependencies = set()
    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            tasks_with_dependencies.add(tasks[cfg['feature_id']])

        if cfg['signal_exists'] and f"signals_{key}" in tasks:
            tasks_with_dependencies.add(tasks[f"signals_{cfg['feature_id']}"])

    for i in range(len(task_list) - 1):
        current_task = task_list[i]
        next_task = task_list[i + 1]

        if next_task not in tasks_with_dependencies:
            next_task.trigger_rule = TriggerRule.ALL_DONE

        current_task >> next_task
