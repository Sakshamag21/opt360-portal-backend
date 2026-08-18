from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.models import Variable
from operator360.work_category_features.insert_work_features import run_one_feature
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
import logging
from airflow.exceptions import AirflowSkipException
from airflow.utils.trigger_rule import TriggerRule
from zoneinfo import ZoneInfo
from operator360.utils.s3_audit_logger import audit_to_s3
from operator360.utils.pipeline_status import report_status, parse_bool

job_name = "sustxn_category_feature"
category = "sustxn"
desc = "Run all the  Sustxn Features"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    "sustxn_oddhour_pkts_instances": {
        "feature_name": "sustxn_oddhour_pkts_instances",
        "feature_version": 1,
        "feature_id": "sustxn_oddhour_pkts_instances_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_oddhour_pkts_instances_24h_v1.sql",
        "dependencies": ["sustxn_oddhour_pkts_instances_2"],
        "signal_exists": False,
        "frequency": "daily"
    },
    "sustxn_oddhour_pkts_instances_2": {
        "feature_name": "sustxn_oddhour_pkts_instances",
        "feature_version": 2,
        "feature_id": "sustxn_oddhour_pkts_instances_24h_v2",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_oddhour_pkts_instances_24h_v2.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "sustxn_outstate_pkts_instances": {
        "feature_name": "sustxn_outstate_pkts_instances",
        "feature_version": 1,
        "feature_id": "sustxn_outstate_pkts_instances_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_outstate_pkts_instances_24h_v1.sql",
        "dependencies": ["sustxn_outstate_pkts_instances_2"],
        "signal_exists": False,
        "frequency": "daily"
    },
    "sustxn_outstate_pkts_instances_2": {
        "feature_name": "sustxn_outstate_pkts_instances",
        "feature_version": 2,
        "feature_id": "sustxn_outstate_pkts_instances_24h_v2",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_outstate_pkts_instances_24h_v2.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "sustxn_parallel_enrolment_instances": {
        "feature_name": "sustxn_parallel_enrolment_instances",
        "feature_version": 1,
        "feature_id": "sustxn_parallel_enrolment_instances_7d_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_parallel_enrolment_instances_7d_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "weekly"
    },
    "sustxn_parallel_enrolment_eid_count_daily": {
        "feature_name": "sustxn_parallel_enrolment_eid_count_daily",
        "feature_version": 1,
        "feature_id": "sustxn_parallel_enrolment_eid_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_parallel_enrolment_eid_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "weekly"
    },
    # "sustxn_res_mobilechange_instances_count_cumulative": {
    #     "feature_name": "sustxn_res_mobilechange_instances_count_cumulative",
    #     "feature_version": 2,
    #     "feature_id":"sustxn_res_mobilechange_instances_count_cumulative_v2",
    #     "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_res_mobilechange_instances_count_cumulative_v2.sql",
    #     "dependencies":[],
    #     "signal_exists":False,
    #     "frequency": "daily"
    # },
    # "sustxn_res_namechange_instances_count_cumulative": {
    #     "feature_name": "sustxn_res_namechange_instances_count_cumulative",
    #     "feature_version": 2,
    #     "feature_id":"sustxn_res_namechange_instances_count_cumulative_v2",
    #     "sql_local_path": "/opt/airflow/dags/operator360/sustxn_features_combined/sustxn_res_namechange_instances_count_cumulative_v2.sql",
    #     "dependencies":[],
    #     "signal_exists":False,
    #     "frequency": "daily"
    # }
}


def run_signals(feature_id):
    try:
        res_try = get_signals_info(feature_id)
        for signal_metadata in res_try:
            push_signals_kafka(signal_metadata)
    except Exception as e:
        print(f"Error in generating signal for feature id : {feature_id}, error: {e}")

@audit_to_s3(dag_id=job_name)
@report_status(dag_id=job_name, category=category)
def run_single_features(feature_name, feature_version, feature_id, sql_file, end_date, frequency="daily", data_interval_start=None, pipeline_run_id=None, is_daily_run=None, log_url=None, try_number=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    # To support backfills, evaluate the weekday of the DAG run's logical execution time
    if not data_interval_start:
        dt = datetime.now(ZoneInfo("Asia/Kolkata"))
    else:
        try:
            dt = datetime.fromisoformat(data_interval_start)
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
        except ValueError:
            logger.warning("Could not parse data_interval_start: %s. Falling back to current time.", data_interval_start)
            dt = datetime.now(ZoneInfo("Asia/Kolkata"))

    target_weekday = 0  # Monday
    is_daily_run = parse_bool(is_daily_run)

    if frequency == "hourly":
        # Runs every manager tick, regardless of promotion hour.
        pass
    elif frequency == "weekly":
        # Only actually runs on the promotion tick, and only on the
        # Monday-only business rule on top of that.
        if not is_daily_run:
            logger.info("Skipping weekly feature %s - not the daily promotion run", feature_name)
            raise AirflowSkipException("Skipping weekly task - not the daily promotion run")
        if dt.weekday() != target_weekday:
            logger.info("Skipping weekly feature %s - target weekday %d, logical weekday %d",
                        feature_name, target_weekday, dt.weekday())
            raise AirflowSkipException(
                f"Skipping weekly task - logical weekday is {dt.weekday()}, target is {target_weekday}"
            )
    else:  # "daily"
        if not is_daily_run:
            logger.info("Skipping daily feature %s - not the daily promotion run", feature_name)
            raise AirflowSkipException("Skipping daily task - not the daily promotion run")

    # ==========================================
    # RAW DATA CHECK INTEGRATION - only reached for hourly features (every
    # tick) or daily/weekly features on the promotion tick.
    # ==========================================
    logger.info("Verifying raw data availability for feature_id: %s", feature_id)
    
    if feature_id:
        source_tables_res = get_source_tables(category="sustxn")
        
        if not source_tables_res.get('success'):
            logger.error("Failed to fetch source tables metadata. Error: %s", source_tables_res.get('error'))
            raise RuntimeError(f"Metadata DB lookup failed. Error: {source_tables_res.get('error')}")
            
        mapping = source_tables_res 
        source_table = mapping.get(feature_id)
        
        if not source_table:
            logger.warning("No source_table found in metadata for feature_id=%s. Proceeding with feature run anyway.", feature_id)
        else:
            has_raw_data = check_raw_tables(source_table)
            if not has_raw_data:
                logger.error("Raw data missing for feature %s in table %s.", feature_name, source_table)
                raise RuntimeError(f"Raw data is missing for {source_table}. Cannot proceed with feature {feature_name}.")
    # ==========================================

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
    "start_date": datetime(2026, 5, 20, tzinfo=ZoneInfo("Asia/Kolkata")),
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
    schedule=None,  # triggered only by controller_pipeline
    catchup=False,
    max_active_runs=3,
    max_active_tasks=5,
    tags=["Operator360", "Sustxn Category"]
) as dag:

    tasks = {}

    for key, cfg in FEATURES.items():
        task = PythonOperator(
            task_id=f"run_{cfg['feature_id']}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg["feature_id"],
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ data_interval_start | ds}}",
                "frequency": cfg["frequency"],
                "data_interval_start": "{{ data_interval_start }}",
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

    # Apply dependencies defined in FEATURES
    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            for dep in cfg["dependencies"]:
                if dep in tasks:
                    tasks[dep] >> tasks[cfg['feature_id']]
        
        if "signal_exists" in cfg and cfg["signal_exists"]:
            if f"signals_{cfg['feature_id']}" in tasks:
                tasks[cfg['feature_id']] >> tasks[f"signals_{cfg['feature_id']}"]

    # Sequential execution with independence between groups
    task_list = list(tasks.values())

    # Track which tasks already have upstream dependencies
    tasks_with_dependencies = set()
    for key, cfg in FEATURES.items():
        # Mark feature tasks that have explicit dependencies
        if "dependencies" in cfg and cfg["dependencies"]:
            tasks_with_dependencies.add(tasks[cfg['feature_id']])
        
        # Mark signal tasks (they depend on their feature task)
        if cfg['signal_exists'] and f"signals_{key}" in tasks:
            tasks_with_dependencies.add(tasks[f"signals_{cfg['feature_id']}"])

    # Chain tasks sequentially, but use ALL_DONE for tasks without explicit dependencies
    for i in range(len(task_list) - 1):
        current_task = task_list[i]
        next_task = task_list[i + 1]
        
        # If next_task doesn't have explicit dependencies, use ALL_DONE trigger
        # This allows it to run even if the previous unrelated task failed
        if next_task not in tasks_with_dependencies:
            next_task.trigger_rule = TriggerRule.ALL_DONE
        
        current_task >> next_task