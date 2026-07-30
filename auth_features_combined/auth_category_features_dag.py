import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from airflow.sdk import DAG, TriggerRule
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException

from operator360.work_category_features.insert_work_features import run_one_feature
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
from operator360.utils.s3_audit_logger import audit_to_s3

job_name = "auth_category_features"
desc = "Run all the  Auth Features"
schedule = "0 * * * *"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    "auth_device_change_incidents": {
        "feature_name": "auth_device_change_incidents",
        "feature_version": 1,
        "feature_id": "auth_device_change_incidents_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_device_change_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "is_daily": True
    },
    "auth_modality_change_incidents": {
        "feature_name": "auth_modality_change_incidents",
        "feature_version": 1,
        "feature_id": "auth_modality_change_incidents_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_modality_change_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "is_daily": True
    },
    "auth_oddhour_incidents": {
        "feature_name": "auth_oddhour_incidents",
        "feature_version": 1,
        "feature_id": "auth_oddhour_incidents_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_oddhour_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": True,
        "is_daily": True
    },
    "auth_biomismatch_incidents": {
        "feature_name": "auth_biomismatch_incidents",
        "feature_version": 1,
        "feature_id": "auth_biomismatch_incidents_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_biomismatch_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": True,
        "is_daily": True
    },
    # NOTE: Renamed key to _v1 to prevent overwriting in the dictionary
    "auth_liveness_failure_incidents_v1": {
        "feature_name": "auth_liveness_failure_incidents",
        "feature_version": 1,
        "feature_id": "auth_liveness_failure_incidents_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_liveness_failure_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "is_daily": True
    },
    # NOTE: Renamed key to _v2 to prevent overwriting in the dictionary
    "auth_liveness_failure_incidents_v2": {
        "feature_name": "auth_liveness_failure_incidents",
        "feature_version": 2,
        "feature_id": "auth_liveness_failure_incidents_24h_v2",
        "sql_local_path": "/opt/airflow/dags/operator360/auth_features_combined/auth_liveness_failure_incidents_24h_v1.sql",
        "dependencies": [],
        "signal_exists": True,
        "is_daily": True
    },
}


def run_signals(feature_id):
    try:
        res_try = get_signals_info(feature_id)
        for signal_metadata in res_try:
            push_signals_kafka(signal_metadata)
    except Exception as e:
        print(f"Error in generating signal for feature id : {feature_id}, error: {e}")

@audit_to_s3(dag_id=job_name)
def run_single_features(feature_name, feature_version, feature_id,  sql_file, end_date, is_daily=False, data_interval_start=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    if is_daily:
        # 1. Check if it's the right hour to run the daily task
        if not data_interval_start:
            raise ValueError("data_interval_start is missing for daily task check")
            
        try:
            dt = datetime.fromisoformat(data_interval_start)
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
        except ValueError:
            logger.warning("Could not parse data_interval_start: %s. Falling back to current time.", data_interval_start)
            dt = datetime.now(ZoneInfo("Asia/Kolkata"))
            
        target_hour = 6
        
        if dt.hour != target_hour:
            logger.info("Skipping daily feature %s - logical hour is %d, not %d", 
                        feature_name, dt.hour, target_hour)
            print(f'Skipping feature {feature_name}')
            raise AirflowSkipException(f"Skipping daily task - logical hour is {dt.hour}, not {target_hour} AM")
        
        # 2. Raw Data Check (ONLY runs if is_daily is True AND it is 6 AM)
        logger.info("Daily check passed. Verifying raw data availability for feature_id: %s", feature_id)
        
        source_tables_res = get_source_tables(category="auth")
        
        if not source_tables_res.get('success'):
            logger.error("Failed to fetch source tables metadata. Error: %s", source_tables_res.get('error'))
            raise AirflowSkipException("Skipped because metadata DB lookup failed.")
            
        mapping = source_tables_res.get('mapping', {})
        source_table = mapping.get(feature_id)
        
        if not source_table:
            logger.warning("No source_table found in metadata for feature_id=%s. Proceeding with feature run anyway.", feature_id)
        else:
            has_raw_data = check_raw_tables(source_table)
            if not has_raw_data:
                logger.warning("Skipping feature %s because raw table %s has no data for yesterday.", feature_name, source_table)
                raise AirflowSkipException(f"Skipping task because raw data is missing for {source_table}")
    
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
        raise  # Re-raise the exception so Airflow marks the task as Failed


default_args = {
    "owner": "Saksham Agarwal",
    "depends_on_past": False,
    "start_date": datetime(2026, 4, 13, tzinfo=ZoneInfo("Asia/Kolkata")),
    "email": ["techexe16.yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}

with DAG(
    dag_id=job_name,
    default_args=default_args,
    description=desc,
    catchup=False,
    max_active_runs=3,
    max_active_tasks=5,
    tags=["Operator360", "Auth Category"]
) as dag:

    tasks = {}

    for key, cfg in FEATURES.items():
        task = PythonOperator(
            task_id=f"run_{key}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg['feature_id'],
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ data_interval_start | ds }}",  # Airflow 3 preferred macro
                "is_daily": cfg["is_daily"],
                "data_interval_start": "{{ data_interval_start }}"  # Used for backfill hour check
            },
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
        # Mark feature tasks that have explicit dependencies
        if "dependencies" in cfg and cfg["dependencies"]:
            tasks_with_dependencies.add(tasks[key])
        
        # Mark signal tasks (they depend on their feature task)
        if cfg['signal_exists'] and f"signals_{key}" in tasks:
            tasks_with_dependencies.add(tasks[f"signals_{key}"])

    # Chain tasks sequentially, but use ALL_DONE for tasks without explicit dependencies
    # This allows it to run even if the previous unrelated task failed
    for i in range(len(task_list) - 1):
        current_task = task_list[i]
        next_task = task_list[i + 1]
        
        # If next_task doesn't have explicit dependencies, use ALL_DONE trigger
        # This allows it to run even if the previous unrelated task failed
        if next_task not in tasks_with_dependencies:
            next_task.trigger_rule = TriggerRule.ALL_DONE
        
        current_task >> next_task