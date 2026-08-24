# v2: identical to work_multiple_feature_dag.py except dag_id/job_name, so
# operator_dag_manager_v2.py's retry orchestration can trigger it in isolation
# from the v1 pipeline. See operator_dag_manager_v2.py for the retry logic.
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from operator360.work_category_features.insert_work_features import run_one_feature
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
from operator360.utils.s3_audit_logger import audit_to_s3
from operator360.utils.pipeline_status import report_status, parse_bool
from operator360.utils.pipeline_status_v2 import skip_if_already_succeeded
import logging
from airflow.exceptions import AirflowSkipException
from airflow.utils.trigger_rule import TriggerRule

job_name = "work_category_feature_v2"
category = "work"
desc = "Run all the  Work Features"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    # "work_machine_id_change_instances_count_daily": {
    #     "feature_name": "work_machine_id_change_instances_count_daily",
    #     "feature_version": 2,
    #     "feature_id": "work_machine_id_change_instances_count_daily_v2",
    #     "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machine_id_change_instances_count_daily_v2.sql",
    #     "dependencies": [],
    #     "signal_exists": False,
    #     "frequency": "daily"
    # },
    "work_pob_declared_instances": {
        "feature_name": "work_pob_declared_instances",
        "feature_version": 1,
        "feature_id": "work_pob_declared_instances_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_pob_declared_instances_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_machine_change_instances": {
        "feature_name": "work_machine_change_instances",
        "feature_version": 1,
        "feature_id": "work_machine_change_instances_24h_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machine_change_instances_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_machine_ip_change_instances_count_daily": {
        "feature_name": "work_machine_ip_change_instances_count_daily",
        "feature_version": 1,
        "feature_id": "work_machine_ip_change_instances_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machine_ip_change_instances_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_machine_unique_count_daily": {
        "feature_name": "work_machine_unique_count_daily",
        "feature_version": 1,
        "feature_id": "work_machine_unique_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machine_unique_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_operator_name_unique_count_cumulative": {
        "feature_name": "work_operator_name_unique_count_cumulative",
        "feature_version": 1,
        "feature_id": "work_operator_name_unique_count_cumulative_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_operator_name_unique_count_cumulative_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_packet_upload_new_count_daily": {
        "feature_name": "work_packet_upload_new_count_daily",
        "feature_version": 1,
        "feature_id": "work_packet_upload_new_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_new_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_packet_upload_new_count_hourly": {
        "feature_name": "work_packet_upload_new_count_hourly",
        "feature_version": 1,
        "feature_id": "work_packet_upload_new_count_hourly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_new_count_hourly_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "hourly"
    },
    "work_packet_upload_total_count_daily": {
        "feature_name": "work_packet_upload_total_count_daily",
        "feature_version": 1,
        "feature_id": "work_packet_upload_total_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_total_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": True,
        "frequency": "daily"
    },
    "work_packet_upload_total_count_hourly": {
        "feature_name": "work_packet_upload_total_count_hourly",
        "feature_version": 1,
        "feature_id": "work_packet_upload_total_count_hourly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_total_count_hourly_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "hourly"
    },
    "work_packet_upload_update_count_daily": {
        "feature_name": "work_packet_upload_update_count_daily",
        "feature_version": 1,
        "feature_id": "work_packet_upload_update_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_update_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_packet_upload_update_count_hourly": {
        "feature_name": "work_packet_upload_update_count_hourly",
        "feature_version": 1,
        "feature_id": "work_packet_upload_update_count_hourly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_packet_upload_update_count_hourly_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "hourly"
    },
    # "work_machine_sync_gap": {
    #     "feature_name": "work_machine_sync_gap",
    #     "feature_version": 1,
    #     "feature_id": "work_machine_sync_gap_v1",
    #     "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machine_sync_gap_v2.sql",
    #     "dependencies": [],
    #     "signal_exists": False,
    #     "frequency": "daily"
    # },
    "work_machineip_isp_change_count_daily": {
        "feature_name": "work_machineip_isp_change_count_daily",
        "feature_version": 1,
        "feature_id": "work_machineip_isp_change_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machineip_isp_change_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "frequency": "daily"
    },
    "work_machineip_isp_change_count_cumulative": {
        "feature_name": "work_machineip_isp_change_count_cumulative",
        "feature_version": 1,
        "feature_id": "work_machineip_isp_change_count_cumulative_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/work_category_features/work_machineip_isp_change_count_cumulative_v1.sql",
        "dependencies": ["work_machineip_isp_change_count_daily"],
        "signal_exists": False,
        "frequency": "daily"
    },
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
def run_single_features(feature_name, feature_version, feature_id, sql_file, end_date, frequency="daily", data_interval_start=None, pipeline_run_id=None, is_daily_run=None, log_url=None, try_number=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    # Use Airflow's logical execution time instead of wall-clock time for backfill safety
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
        # The manager triggers this DAG every hour specifically so these
        # keep running on their real cadence - always eligible, and their
        # S3-reported status is excluded from the daily category judgement.
        pass
    elif frequency == "weekly":
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
        source_tables_res = get_source_tables(category="work")

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

    try:
        logger.info("Running feature %s v%s with sql=%s", feature_name, feature_version, sql_file)
        run_one_feature(
            feature_name=feature_name,
            feature_version=feature_version,
            sql_file=sql_file,
            end_date=end_date
        )
        logger.info("Feature executed successfully %s v%s", feature_name, feature_version)
    except Exception as e:
        logger.exception("Feature %s failed: %s", feature_name, e)
        raise  # Re-raise so Airflow marks the task as Failed


default_args = {
    "owner": "Saksham Agarwal",
    "depends_on_past": False,
    "start_date": datetime(2026, 4, 13),
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
    max_active_runs=1,
    max_active_tasks=1,
    tags=["Operator360", "Work Category", "v2"]
) as dag:

    tasks = {}

    # 1. Define all tasks and assign standard trigger rules
    for key, cfg in FEATURES.items():
        feature_id = cfg['feature_id']

        task = PythonOperator(
            task_id=f"run_{feature_id}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg["feature_id"],
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ ds }}",
                "frequency": cfg["frequency"],
                "data_interval_start": "{{ data_interval_start }}",
                "pipeline_run_id": "{{ dag_run.conf.get('pipeline_run_id') or run_id }}",
                "is_daily_run": "{{ dag_run.conf.get('is_daily_run', 'true') }}",
                "log_url": "{{ ti.log_url }}",
                "try_number": "{{ ti.try_number }}",
            },
        )
        tasks[feature_id] = task

        if cfg['signal_exists']:
            signal_task = PythonOperator(
                task_id=f"signal_{feature_id}",
                python_callable=run_signals,
                op_kwargs={
                    "feature_id": feature_id
                },
                # Default rule is ALL_SUCCESS. If upstream fails, this is skipped!
                trigger_rule=TriggerRule.ALL_SUCCESS
            )
            tasks[f"signals_{feature_id}"] = signal_task

    # 2. Map explicit Feature-to-Feature and Feature-to-Signal relationships cleanly
    for key, cfg in FEATURES.items():
        feature_id = cfg['feature_id']

        # Inter-feature cross dependencies
        if "dependencies" in cfg and cfg["dependencies"]:
            for dep in cfg["dependencies"]:
                if dep in tasks:
                    tasks[dep] >> tasks[feature_id]

        # Direct parent-child feature to signal mapping
        if cfg['signal_exists']:
            signal_key = f"signals_{feature_id}"
            if signal_key in tasks:
                tasks[feature_id] >> tasks[signal_key]