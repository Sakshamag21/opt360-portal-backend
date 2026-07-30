from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from zoneinfo import ZoneInfo
import operator360.bio_packet_fraud_features.insert_bio_packet_fraud_incidents as fn
from operator360.signal_mechanism.signals_producer import get_signals_info, push_signals_kafka
from operator360.utils.raw_table_validation import get_source_tables, check_raw_tables
from operator360.utils.s3_audit_logger import audit_to_s3

import logging
from airflow.exceptions import AirflowSkipException

job_name = "bio_packet_fraud_features"
desc = "Run all MFC fraud incident features"
schedule = "0 7 * * *"
signal_api_base_ip = "10.10.116.60:8000"

FEATURES = {
    "bio_packet_finger_toe_print_count_cumulative": {
        "feature_name": "bio_packet_finger_toe_print_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_finger_toe_print_count_cumulative.sql",
        "dependencies": ["bio_packet_finger_toe_print_count_daily"],
        "signal_exists": True,
        "feature_id": "bio_packet_finger_toe_print_count_cumulative_v1",
        "is_daily": True
    },
    "bio_packet_fraud_count_daily": {
        "feature_name": "bio_packet_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_face_fraud_count_daily": {
        "feature_name": "bio_packet_face_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_face_non_human_count_daily": {
        "feature_name": "bio_packet_face_non_human_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_face_pop_count_daily": {
        "feature_name": "bio_packet_face_pop_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_face_pop_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_face_pop_count_cumulative": {
        "feature_name": "bio_packet_face_pop_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_pop_count_cumulative.sql",
        "dependencies": ["bio_packet_face_pop_count_daily"],
        "signal_exists": True,
        "feature_id": "bio_packet_face_pop_count_cumulative_v1",
        "is_daily": True
    },
    "bio_packet_face_nonhuman_count_cumulative": {
        "feature_name": "bio_packet_face_nonhuman_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_nonhuman_count_cumulative.sql",
        "dependencies": ["bio_packet_face_non_human_count_daily"],
        "signal_exists": True,
        "feature_id": "bio_packet_face_nonhuman_count_cumulative_v1",
        "is_daily": True
    },
    "bio_packet_face_adult_as_child_count_daily": {
        "feature_name": "bio_packet_face_adult_as_child_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_face_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_fraud_count_daily": {
        "feature_name": "bio_packet_iris_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_mixed_count_daily": {
        "feature_name": "bio_packet_iris_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_non_human_count_daily": {
        "feature_name": "bio_packet_iris_non_human_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_swap_count_daily": {
        "feature_name": "bio_packet_iris_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_iris_swap_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_iris_swap_count_cumulative": {
        "feature_name": "bio_packet_iris_swap_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_swap_count_cumulative.sql",
        "dependencies": ["bio_packet_iris_swap_count_daily"],
        "signal_exists": True,
        "feature_id": "bio_packet_iris_swap_count_cumulative_v1",
        "is_daily": True
    },
    "bio_packet_iris_flipped_count_daily": {
        "feature_name": "bio_packet_iris_flipped_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_iris_flipped_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_iris_flipped_count_cumulative": {
        "feature_name": "bio_packet_iris_flipped_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_flipped_count_cumulative.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_iris_flipped_count_cumulative",
        "is_daily": True
    },
    "bio_packet_iris_pop_count_daily": {
        "feature_name": "bio_packet_iris_pop_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_iris_pop_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_iris_pop_count_cumulative": {
        "feature_name": "bio_packet_iris_pop_count_cumulative",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_pop_count_cumulative.sql",
        "dependencies": ["bio_packet_iris_pop_count_daily"],
        "signal_exists": True,
        "feature_id": "bio_packet_iris_pop_count_cumulative_v1",
        "is_daily": True
    },
    "bio_packet_iris_right_fraud_count_daily": {
        "feature_name": "bio_packet_iris_right_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_right_non_human_count_daily": {
        "feature_name": "bio_packet_iris_right_non_human_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_right_swap_count_daily": {
        "feature_name": "bio_packet_iris_right_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_right_mixed_count_daily": {
        "feature_name": "bio_packet_iris_right_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_right_pop_count_daily": {
        "feature_name": "bio_packet_iris_right_pop_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_left_fraud_count_daily": {
        "feature_name": "bio_packet_iris_left_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_left_non_human_count_daily": {
        "feature_name": "bio_packet_iris_left_non_human_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_left_pop_count_daily": {
        "feature_name": "bio_packet_iris_left_pop_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_left_swap_count_daily": {
        "feature_name": "bio_packet_iris_left_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_iris_left_mixed_count_daily": {
        "feature_name": "bio_packet_iris_left_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_iris_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_finger_fraud_count_daily": {
        "feature_name": "bio_packet_finger_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_finger_toe_print_count_daily": {
        "feature_name": "bio_packet_finger_toe_print_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_finger_toe_print_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_finger_swap_count_daily": {
        "feature_name": "bio_packet_finger_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_finger_mixed_count_daily": {
        "feature_name": "bio_packet_finger_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_right_fraud_count_daily": {
        "feature_name": "bio_packet_slap_right_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_right_toe_print_count_daily": {
        "feature_name": "bio_packet_slap_right_toe_print_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_slap_right_toe_print_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_slap_right_mixed_count_daily": {
        "feature_name": "bio_packet_slap_right_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_right_swap_count_daily": {
        "feature_name": "bio_packet_slap_right_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_left_toe_print_count_daily": {
        "feature_name": "bio_packet_slap_left_toe_print_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "bio_packet_slap_left_toe_print_count_daily_v1",
        "is_daily": True
    },
    "bio_packet_slap_left_mixed_count_daily": {
        "feature_name": "bio_packet_slap_left_mixed_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_left_fraud_count_daily": {
        "feature_name": "bio_packet_slap_left_fraud_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_packet_slap_left_swap_count_daily": {
        "feature_name": "bio_packet_slap_left_swap_count_daily",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_packet_slap_fraud_count_daily_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
    "bio_sfc_fraud_incidents": {
        "feature_name": "bio_sfc_fraud_incidents_v1",
        "feature_version": 1,
        "sql_local_path": "/opt/airflow/dags/operator360/bio_packet_fraud_features/bio_sfc_fraud_incidents_v1.sql",
        "dependencies": [],
        "signal_exists": False,
        "feature_id": "",
        "is_daily": True
    },
}


def run_signals(feature_id):
    try:
        res_try = get_signals_info(feature_id)
        for signal_metadata in res_try:
            print(push_signals_kafka(signal_metadata))
    except Exception as e:    
        print(f"Error in generating signal for feature id : {feature_id}, error: {e}")

@audit_to_s3(dag_id=job_name)
def run_single_features(feature_name, feature_version, feature_id, sql_file, end_date, is_daily=True, data_interval_start=None):
    logger = logging.getLogger(f"running {feature_name}:v{feature_version}")

    if is_daily:
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
            
        target_hour = 7  # Run at 7 AM as per schedule
        
        if dt.hour != target_hour:
            logger.info("Skipping daily feature %s - logical hour is %d, not %d", 
                       feature_name, dt.hour, target_hour)
            print(f'Skipping feature {feature_name}')
            raise AirflowSkipException(f"Skipping daily task - logical hour is {dt.hour}, not {target_hour} AM")
        
        # ==========================================
        # RAW DATA CHECK INTEGRATION (Only runs if is_daily is True and it is 7 AM)
        # ==========================================
        logger.info("Daily check passed. Verifying raw data availability for feature_id: %s", feature_id)
        
        if feature_id:
            source_tables_res = get_source_tables(category="bio")
            
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
        # ==========================================

    print(f"Executing feature {feature_name}")
    try:
        logger.info("Running feature %s v%s with sql=%s and end_date=%s",
                    feature_name, feature_version, sql_file, end_date)
        
        fn.run_one_feature(
            feature_name=feature_name,
            feature_version=feature_version,
            sql_file=sql_file,
            end_date=end_date
        )
        logger.info("Feature executed successfully %s v%s", feature_name, feature_version)
    except Exception as e:
        logger.exception("Feature %s failed: %s", feature_name, e)
        raise


default_args = {
    "owner": "Saksham Agarwal",
    "depends_on_past": False,
    "start_date": datetime(2026, 4, 13, tzinfo=ZoneInfo("Asia/Kolkata")),
    "email": ["junior.devfsd6-tc@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}

with DAG(
    dag_id=job_name,
    default_args=default_args,
    description=desc,
    catchup=False,
    max_active_runs=1,
    max_active_tasks=3,
    tags=["Operator360", "Bio Category"],
) as dag:

    tasks = {}

    for key, cfg in FEATURES.items():
        task = PythonOperator(
            task_id=f"run_{key}",
            python_callable=run_single_features,
            op_kwargs={
                "feature_name": cfg["feature_name"],
                "feature_version": cfg["feature_version"],
                "feature_id": cfg["feature_id"],
                "sql_file": cfg["sql_local_path"],
                "end_date": "{{ ds }}",
                "is_daily": cfg["is_daily"],
                "data_interval_start": "{{ data_interval_start }}"
            }
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

    for key, cfg in FEATURES.items():
        if "dependencies" in cfg and cfg["dependencies"]:
            for dep in cfg["dependencies"]:
                if dep in tasks:
                    tasks[dep] >> tasks[key]

        if "signal_exists" in cfg and cfg["signal_exists"]:
            tasks[key] >> tasks[f"signals_{key}"]