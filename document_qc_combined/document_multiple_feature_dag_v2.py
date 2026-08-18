# v2: identical to document_multiple_feature_dag.py except dag_id/job_name,
# so operator_dag_manager_v2.py's retry orchestration can trigger it in
# isolation from the v1 pipeline. See operator_dag_manager_v2.py for the
# retry logic.
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import DAG, TriggerRule
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException

from operator360.document_qc_combined.insert_document_features import run_one_feature
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
from operator360.utils.s3_audit_logger import audit_to_s3
from operator360.utils.pipeline_status import report_status, parse_bool
from operator360.utils.pipeline_status_v2 import skip_if_already_succeeded

job_name = "document_features_combined_v2"
category = "document"
desc = "Run all the  Document Features"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    "doc_qc_error_al_incidents_count_daily": {
        "feature_name": "doc_qc_error_al_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_al_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_doe2_incidents_count_daily": {
        "feature_name": "doc_qc_error_doe2_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_doe2_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_hpm_incidents_count_daily": {
        "feature_name": "doc_qc_error_hpm_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_hpm_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_doe1_incidents_count_daily": {
        "feature_name": "doc_qc_error_doe1_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_doe1_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_be_incidents_count_daily": {
        "feature_name": "doc_qc_error_be_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_be_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_pop_incidents_count_daily": {
        "feature_name": "doc_qc_error_pop_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_pop_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_de_incidents_count_daily": {
        "feature_name": "doc_qc_error_de_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_de_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_incidents_count_daily": {
        "feature_name": "doc_qc_error_incidents_count_daily",
        "feature_version": 1,
        "feature_id":"doc_qc_error_incidents_count_daily_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_total_daily_feature_query.sql",
        "dependencies":[],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_pop_incidents_count_cumulative": {
        "feature_name": "doc_qc_error_pop_incidents_count_cumulative",
        "feature_version": 1,
        "feature_id":"doc_qc_error_pop_incidents_count_cumulative_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_cumulative_daily_feature.sql",
        "dependencies":["doc_qc_error_pop_incidents_count_daily"],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_doe1_incidents_count_cumulative": {
        "feature_name": "doc_qc_error_doe1_incidents_count_cumulative",
        "feature_version": 1,
        "feature_id":"doc_qc_error_doe1_incidents_count_cumulative_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_cumulative_daily_feature.sql",
        "dependencies":["doc_qc_error_doe1_incidents_count_daily"],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_al_incidents_count_monthly": {
        "feature_name": "doc_qc_error_al_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_al_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_al_incidents_count_daily'],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_doe2_incidents_count_monthly": {
        "feature_name": "doc_qc_error_doe2_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_doe2_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_doe2_incidents_count_daily'],
        "signal_exists":True,
        "is_daily":True
    },
    "doc_qc_error_hpm_incidents_count_monthly": {
        "feature_name": "doc_qc_error_hpm_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_hpm_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_hpm_incidents_count_daily'],
        "signal_exists":False,
        "is_daily":True
    },
    "doc_qc_error_doe1_incidents_count_monthly": {
        "feature_name": "doc_qc_error_doe1_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_doe1_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_doe1_incidents_count_daily'],
        "signal_exists":True,
        "is_daily":True
    },
    "doc_qc_error_be_incidents_count_monthly": {
        "feature_name": "doc_qc_error_be_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_be_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_be_incidents_count_daily'],
        "signal_exists":True,
        "is_daily":True
    },
    "doc_qc_error_pop_incidents_count_monthly": {
        "feature_name": "doc_qc_error_pop_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_pop_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_pop_incidents_count_daily'],
        "signal_exists":True,
        "is_daily":True
    },
    "doc_qc_error_de_incidents_count_monthly": {
        "feature_name": "doc_qc_error_de_incidents_count_monthly",
        "feature_version": 1,
        "feature_id":"doc_qc_error_de_incidents_count_monthly_v1",
        "sql_local_path": "/opt/airflow/dags/operator360/document_qc_combined/qc_monthly_feature_query.sql",
        "dependencies":['doc_qc_error_de_incidents_count_daily'],
        "signal_exists":True,
        "is_daily":True
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
def run_single_features(feature_name, feature_version,feature_id,  sql_file, end_date, is_daily=False, data_interval_start=None, pipeline_run_id=None, is_daily_run=None, log_url=None, try_number=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    if is_daily:
        # This DAG has no hourly-cadence features, so is_daily just means
        # "only actually run on the manager's once-a-day promotion tick".
        if not parse_bool(is_daily_run):
            logger.info("Skipping %s - not the daily promotion run", feature_name)
            raise AirflowSkipException("Skipping - not the daily promotion run")

        # Raw Data Check - only reached on the promotion tick.
        logger.info("Verifying raw data availability for feature_id: %s", feature_id)

        source_tables_res = get_source_tables(category="doc")

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
    "execution_timeout": timedelta(minutes=20),
    "email": ["techexe16.yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}

with DAG(
    dag_id=job_name,
    default_args={
        **default_args,
        "start_date": datetime(2025, 1, 1, tzinfo=ZoneInfo("Asia/Kolkata")),  # FIX: past date
    },
    description=desc,
    schedule=None,
    catchup=False,
    max_active_runs=3,
    max_active_tasks=10,  # FIX: increase to allow parallelism
    tags=["Operator360", "Document Category", "v2"],
    params={"business_consumer": "Operator360"},
) as dag:

    tasks = {}

    # --- Create all tasks ---
    for key, cfg in FEATURES.items():
        task = PythonOperator(
            task_id=f"run_{key}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg["feature_id"],
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ data_interval_start | ds }}",
                "is_daily": cfg["is_daily"],
                "data_interval_start": "{{ data_interval_start }}",
                "pipeline_run_id": "{{ dag_run.conf.get('pipeline_run_id') or run_id }}",
                "is_daily_run": "{{ dag_run.conf.get('is_daily_run', 'true') }}",
                "log_url": "{{ ti.log_url }}",
                "try_number": "{{ ti.try_number }}",
            },
        )
        tasks[key] = task

        if cfg["signal_exists"]:
            signal_task = PythonOperator(
                task_id=f"signal_{key}",
                python_callable=run_signals,
                op_kwargs={"feature_id": cfg["feature_id"]},
            )
            tasks[f"signal_{key}"] = signal_task  # FIX: consistent naming

    # --- Only set REAL dependencies ---
    for key, cfg in FEATURES.items():
        # Feature-to-feature dependencies (e.g., monthly depends on daily)
        for dep in cfg.get("dependencies", []):
            if dep in tasks:
                tasks[dep] >> tasks[key]

        # Feature-to-signal dependencies
        if cfg["signal_exists"] and f"signal_{key}" in tasks:
            tasks[key] >> tasks[f"signal_{key}"]

    # ❌ REMOVED: the sequential chaining loop entirely
