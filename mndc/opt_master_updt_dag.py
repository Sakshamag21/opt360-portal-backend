from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime
from trino.dbapi import connect
from airflow.utils.dates import days_ago
import mysql.connector
import time
import pandas as pd
import json
import logging
import re
import pandas as pd

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _log_separator(title: str = ""):
    """Print a clearly visible separator block in the logs."""
    border = "=" * 90
    logger.info(border)
    if title:
        logger.info(f"  {title}")
        logger.info(border)


# ---------------------------------------------------------------------------
# Connection / config
# ---------------------------------------------------------------------------
trino_host = "10.10.116.75"
trino_catalog_iceberg = 'strot'
trino_port = 8080
trino_user = "opt_master_updt"
mysql_connection_url = "10.81.108.109"
mysql_admin_user = "Data_platform_W"
mysql_admin_password = "Dataplat_7634"
anomaly_code = [
    "work_opt_machinesync",
    "sustxn_oddhour_pkts",
    "bio_mfc_fraud",
    "sustxn_res_mobilechange",
    "work_machine_change",
    "hardware_multiple_biodev",
    "sustxn_outstate_pkts",
    "work_opt_hof",
    "bio_sfc_fraud",
    "work_multiple_optname",
    "sustxn_res_namechange",
    "hardware_machine_change",
    "work_pob_declared",
    "doc_qc_error"
]

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 4, 30),
    'email': ['techexecutive16-yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
}

dag = DAG(
    'opt_master_updt_dag',
    default_args=default_args,
    description='DAG to insert error eids into qc error report according feb 2025',
    schedule_interval="0 9 * * *",
    catchup=False,
    concurrency=1,
    tags=['operator360', 'opt_master']
)


# ---------------------------------------------------------------------------
# Low-level helpers (with logging)
# ---------------------------------------------------------------------------
def trino(query, host=trino_host, port=trino_port, user=trino_user):
    """Execute a Trino query and return a dict containing the result or error."""
    logger.info(f"[TRINO] Connecting to host={host}:{port} user={user}")
    # Avoid logging the full query if it's huge — log first 500 chars
    preview = query.strip()[:500].replace("\n", " ")
    logger.info(f"[TRINO] Executing query (preview): {preview}{'...' if len(query.strip()) > 500 else ''}")
    try:
        start_time = time.time()
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time = time.time()
        execution_time = round(end_time - start_time, 3)
        logger.info(f"[TRINO] Query executed successfully in {execution_time}s | rows_returned={len(body)}")

        if not body:
            logger.info("[TRINO] Query returned no rows.")
            return {"query": query, "success": 1, "data": body, "execution_time": execution_time}
        else:
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            logger.info(f"[TRINO] Columns: {cols}")
            return {"query": query, "success": 1, "data": (cols, body), "df": df, "execution_time": execution_time}
    except Exception as e:
        logger.error(f"[TRINO] Query FAILED with error: {e}", exc_info=True)
        return {"query": query, "success": 0, "msg": str(e)}


def _sql(val):
    """Safely format a Python value for inline SQL (handles None, escaping)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'NULL'
    escaped = str(val).replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def show_dbs(query, host=mysql_connection_url, admin_user=mysql_admin_user, admin_password=mysql_admin_password):
    """Execute a read-only query against MySQL and return the fetched rows."""
    logger.info(f"[MYSQL-READ] Connecting to host={host} user={admin_user}")
    preview = query.strip()[:300].replace("\n", " ")
    logger.info(f"[MYSQL-READ] Executing query (preview): {preview}")
    start_time = time.time()
    connection = mysql.connector.connect(
        host=host,
        user=admin_user,
        password=admin_password
    )
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    connection.close()
    elapsed = round(time.time() - start_time, 3)
    logger.info(f"[MYSQL-READ] Query executed in {elapsed}s | rows_returned={len(results)}")
    return results


def write_data_to_mysql(query, data=None, host=mysql_connection_url, database='operator360',
                       admin_user=mysql_admin_user, admin_password=mysql_admin_password):
    """Execute a write (INSERT/UPDATE) query against MySQL, optionally in batch."""
    try:
        rows_desc = len(data) if data else 1
        logger.info(f"[MYSQL-WRITE] Connecting to host={host} db={database} | rows_to_write={rows_desc}")
        start_time = time.time()
        connection = mysql.connector.connect(
            host=host,
            user=admin_user,
            password=admin_password,
            database=database
        )
        cursor = connection.cursor()

        if data:
            cursor.executemany(query, data)
            logger.info(f"[MYSQL-WRITE] executemany completed | rows_affected={cursor.rowcount}")
        else:
            cursor.execute(query)
            logger.info(f"[MYSQL-WRITE] execute completed | rows_affected={cursor.rowcount}")

        connection.commit()
        logger.info("[MYSQL-WRITE] Transaction committed.")
        cursor.close()
        connection.close()
        elapsed = round(time.time() - start_time, 3)
        logger.info(f"[MYSQL-WRITE] Write completed in {elapsed}s")
        return True
    except Exception as e:
        logger.error(f"[MYSQL-WRITE] Database error: {e}", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Mid-level helpers
# ---------------------------------------------------------------------------
def get_active_risk_data():
    _log_separator("get_active_risk_data: START")
    start = time.time()
    df = trino(f'''
        SELECT * 
         FROM strot.operator360.opt360_features 
         WHERE feature_id = 'risk_score_v3' 
    ''', host='10.10.116.75')

    if 'df' not in df:
        logger.error(f"[get_active_risk_data] Trino response did not contain 'df'. Response: {df}")
        logger.info(f"[get_active_risk_data] END (failure) | elapsed={round(time.time()-start,3)}s")
        return None

    df = df['df']
    logger.info(f"[get_active_risk_data] Rows fetched: {len(df)}")
    if len(df) == 0:
        logger.warning("[get_active_risk_data] No rows returned for feature_id='risk_score_v3'")
        logger.info(f"[get_active_risk_data] END (empty) | elapsed={round(time.time()-start,3)}s")
        return None

    row = df.iloc[0]
    feature_id = row.get("feature_id")
    destination_table = row.get("destination_table")
    logger.info(f"[get_active_risk_data] Active feature_id={feature_id} | destination_table={destination_table}")
    logger.info(f"[get_active_risk_data] END (success) | elapsed={round(time.time()-start,3)}s")
    return destination_table, feature_id


def get_latest_risk_engine_date(risk_destination_table: str = 'strot.operator360.features_risk_v1'):
    _log_separator("get_latest_risk_engine_date: START")
    start = time.time()
    logger.info(f"[get_latest_risk_engine_date] Querying latest date from {risk_destination_table}")
    df = trino(f'''
        with tab1 as(
            select distinct date(timestamp) as last_updated_date
            from {risk_destination_table}
            where feature_id='risk_score_v3'
        )
        select max(last_updated_date) as last_updated_date from tab1
        ''', host='10.10.116.75')

    if 'df' in df.keys():
        last_date = str(df['df']['last_updated_date'].iloc[0])
        logger.info(f"[get_latest_risk_engine_date] Latest risk engine date = {last_date}")
        logger.info(f"[get_latest_risk_engine_date] END (success) | elapsed={round(time.time()-start,3)}s")
        return last_date
    else:
        logger.error(f"[get_latest_risk_engine_date] Trino query failed. Falling back to '2025-12-6'. Response: {df}")
        logger.info(f"[get_latest_risk_engine_date] END (fallback) | elapsed={round(time.time()-start,3)}s")
        return '2025-12-6'


# ---------------------------------------------------------------------------
# Task 1: update_risk_score
# ---------------------------------------------------------------------------
def update_risk_score():
    _log_separator("TASK: update_risk_score START")
    task_start = time.time()

    try:
        active = get_active_risk_data()
        if not active:
            logger.error("[update_risk_score] Could not retrieve active risk data. Aborting task.")
            return
        destination_table, feature_id = active

        last_risk_engine_updt_date = get_latest_risk_engine_date(destination_table)
        logger.info(f"[update_risk_score] Using last_risk_engine_updt_date={last_risk_engine_updt_date}")

        logger.info("[update_risk_score] Querying risk data from Trino (with percentile bucketing).")
        risk_data = trino(f'''
            with base_data as (
                select 
                    entity_id, 
                    feature_value,
                    case when feature_value > 0.9 then 'Critical' else 'General' end as primary_group
                from strot.operator360.features_risk_v1  
                where date(timestamp) >= date('{last_risk_engine_updt_date}') 
                  and feature_id = 'risk_score_v3' 
                  and feature_value is not Null
            ),
            ranked_data as (
                select 
                    *,
                    percent_rank() over(partition by primary_group order by feature_value desc) as pct
                from base_data
            )
            select 
                entity_id, 
                feature_value,
                case 
                    when primary_group = 'Critical' then 'Critical'
                    when pct <= 0.01 then 'High'       
                    when pct <= 0.20 then 'Medium'     
                    when feature_value > 0.01 then 'Low'
                    else 'No'
                end as risk_bucket
            from ranked_data
            order by feature_value desc
        ''', host='10.10.116.75')

        if 'df' not in risk_data:
            logger.error(f"[update_risk_score] Trino query failed. Response: {risk_data}")
            return

        if len(risk_data['df']) == 0:
            logger.warning("[update_risk_score] No risk data returned. Nothing to update.")
            return

        df = risk_data['df']
        logger.info(f"[update_risk_score] Risk data rows fetched: {len(df)}")
        logger.info(f"[update_risk_score] Risk bucket distribution:\n{df['risk_bucket'].value_counts()}")

        bulk_query = """
            INSERT INTO operator360.opt_master (id, risk_score, risk_bucket, updated_at)
            VALUES (%s, %s, %s, CONVERT_TZ(NOW(), @@session.time_zone, '+05:30'))
            ON DUPLICATE KEY UPDATE
                risk_score = VALUES(risk_score),
                risk_bucket = VALUES(risk_bucket);
        """
        all_data = list(zip(
            df['entity_id'].astype(str),
            df['feature_value'].astype(float),
            df['risk_bucket'].astype(str)
        ))
        total_rows = len(all_data)
        logger.info(f"[update_risk_score] Prepared {total_rows} rows for upsert.")

        batch_size = 10000
        total_batches = (total_rows + batch_size - 1) // batch_size
        logger.info(f"[update_risk_score] Processing in {total_batches} batches of size {batch_size}.")

        success_batches = 0
        for i in range(0, total_rows, batch_size):
            batch = all_data[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"[update_risk_score] Batch {batch_num}/{total_batches} | rows {i} to {i + len(batch)}")
            t0 = time.time()
            ok = write_data_to_mysql(bulk_query, data=batch)
            if ok:
                success_batches += 1
                logger.info(f"[update_risk_score] Batch {batch_num} success in {round(time.time()-t0,3)}s")
            else:
                logger.error(f"[update_risk_score] Batch {batch_num} FAILED in {round(time.time()-t0,3)}s")

        logger.info(f"[update_risk_score] Summary: batches_total={total_batches} success={success_batches} "
                    f"failed={total_batches-success_batches}")
        logger.info(f"[update_risk_score] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_risk_score] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task 2: update_sync_details
# ---------------------------------------------------------------------------
def convert_dms_to_dd(dms_str):
    """
    Converts DMS string (e.g., 16°32'26.9604" N) to Decimal Degrees (float).
    If already a float, it returns it directly.
    """
    if dms_str is None or (isinstance(dms_str, float) and pd.isna(dms_str)):
        return None
        
    if isinstance(dms_str, (int, float)):
        return float(dms_str)
        
    dms_str = str(dms_str).strip()
    if not dms_str or dms_str.lower() == 'nan':
        return None

    # Match patterns like: 16°32'26.9604" N or 81°31'30.99612" E
    match = re.match(r'(\d+)[°\s]+(\d+)[\'\s]+([\d\.]+)["\s]*([NSEWnsew])', dms_str)
    if match:
        degrees = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        direction = match.group(4).upper()
        
        dd = degrees + minutes / 60 + seconds / 3600
        if direction in ['S', 'W']:
            dd = -dd
        return dd
    else:
        # Fallback: Try standard float conversion in case it's already decimal degrees
        try:
            return float(dms_str)
        except ValueError:
            return None


def update_sync_details():
    _log_separator("TASK: update_sync_details START")
    task_start = time.time()
    try:
        active = get_active_risk_data()
        if active:
            destination_table, feature_id = active
            last_risk_engine_updt_date = get_latest_risk_engine_date(destination_table)
            logger.info(f"[update_sync_details] last_risk_engine_updt_date={last_risk_engine_updt_date}")
        else:
            logger.warning("[update_sync_details] Active risk data not retrievable. Continuing with sync only.")
        # -------- ECMP sync --------
        _log_separator("update_sync_details: ECMP sync START")
        ecmp_start = time.time()
        ecmp_sync = trino('''
            select upper(operator_id) as opt_id, pincode, district, state, latitude, longitude,
                   machine_code, event_timestamp, client_version, client_type
            from flink_stream.stream_enu.enu_operator_sync_raw
            where event_timestamp>=date(current_timestamp - interval '1' day)
        ''')
        if 'df' in ecmp_sync and len(ecmp_sync['df']) > 0:
            df_ecmp = ecmp_sync['df']
            logger.info(f"[update_sync_details][ECMP] Rows fetched: {len(df_ecmp)}")
            success, failed = 0, 0
            for idx, row in df_ecmp.iterrows():
                ecmp_sync_upsert_query = f'''
                    INSERT INTO operator360.opt_master
                        (id, district, pincode, state, latitude, longitude, machine_code, last_sync_timestamp, client_type, client_version, updated_at)
                    VALUES
                        ('{row['opt_id']}', '{row['district']}', '{row['pincode']}', '{row['state']}',
                         '{row['latitude']}', '{row['longitude']}', '{row['machine_code']}',
                         cast('{row['event_timestamp']}' as datetime), '{row['client_type']}',
                         '{row['client_version']}', CONVERT_TZ(NOW(), @@session.time_zone, '+05:30'))
                    ON DUPLICATE KEY UPDATE
                        district = VALUES(district), pincode = VALUES(pincode), state = VALUES(state),
                        latitude = VALUES(latitude), longitude = VALUES(longitude),
                        machine_code = VALUES(machine_code), last_sync_timestamp = VALUES(last_sync_timestamp),
                        client_type = VALUES(client_type), client_version = VALUES(client_version),
                        updated_at = VALUES(updated_at)
                '''
                ok = write_data_to_mysql(ecmp_sync_upsert_query)
                if ok:
                    success += 1
                else:
                    failed += 1
                if (idx + 1) % 5000 == 0:
                    logger.info(f"[update_sync_details][ECMP] Progress: processed={idx+1}/{len(df_ecmp)} "
                                f"success={success} failed={failed}")
            logger.info(f"[update_sync_details][ECMP] DONE | rows={len(df_ecmp)} success={success} failed={failed} "
                        f"elapsed={round(time.time()-ecmp_start,3)}s")
        else:
            logger.warning("[update_sync_details][ECMP] No data returned from Trino.")
        # -------- UC sync --------
        _log_separator("update_sync_details: UC sync START")
        uc_start = time.time()
        uc_sync = trino('''
            with tab1 as (
                select upper(operator_id) as opt_id, resident_sid,
                row_number() over(partition by operator_id order by event_timestamp desc) as rw
                from flink_stream.stream_enu.enu_uc_opt_action_v2
                where event_timestamp>=date(current_timestamp - interval '1' day)
            ),
            tab2 as (select * from tab1 where rw=1),
            tab3 as (
                select upper(operator_id) as opt_id, resident_sid, max(district) as district,
                       max(pincode) as pincode, max(state) as state,
                       max(latitude) as latitude, max(longitude) as longitude,
                       max(station_machine_code) as machine_code, max(event_timestamp) as event_timestamp
                from flink_stream.stream_enu.enu_uc_opt_action_v2
                where event_timestamp>=date(current_timestamp - interval '1' day)
                group by 1,2
            ),
            tab4 as (
                select t1.* from tab3 t1
                right join tab2 t2 on t1.opt_id=t2.opt_id and t1.resident_sid=t2.resident_sid
            )
            select * from tab4 where opt_id is not Null order by opt_id
        ''', host='10.10.116.75')
        if 'df' in uc_sync and len(uc_sync['df']) > 0:
            df_uc = uc_sync['df']
            logger.info(f"[update_sync_details][UC] Rows fetched: {len(df_uc)}")
            success, failed = 0, 0
            for idx, row in df_uc.iterrows():
                uc_sync_upsert_query = f'''
                    INSERT INTO operator360.opt_master
                        (id, district, pincode, state, latitude, longitude, machine_code, last_sync_timestamp, client_type, updated_at)
                    VALUES
                        ('{row['opt_id']}', '{row['district']}', '{row['pincode']}', '{row['state']}',
                         '{row['latitude']}', '{row['longitude']}', '{row['machine_code']}',
                         cast('{row['event_timestamp']}' as datetime), 'UC',
                         CONVERT_TZ(NOW(), @@session.time_zone, '+05:30'))
                    ON DUPLICATE KEY UPDATE
                        district = VALUES(district), pincode = VALUES(pincode), state = VALUES(state),
                        latitude = VALUES(latitude), longitude = VALUES(longitude),
                        machine_code = VALUES(machine_code), last_sync_timestamp = VALUES(last_sync_timestamp),
                        client_type = 'UC', updated_at = VALUES(updated_at)
                '''
                ok = write_data_to_mysql(uc_sync_upsert_query)
                if ok:
                    success += 1
                else:
                    failed += 1
                if (idx + 1) % 5000 == 0:
                    logger.info(f"[update_sync_details][UC] Progress: processed={idx+1}/{len(df_uc)} "
                                f"success={success} failed={failed}")
            logger.info(f"[update_sync_details][UC] DONE | rows={len(df_uc)} success={success} failed={failed} "
                        f"elapsed={round(time.time()-uc_start,3)}s")
        else:
            logger.warning("[update_sync_details][UC] No data returned from Trino.")
        logger.info(f"[update_sync_details] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_sync_details] Unhandled exception: {e}")
        raise     


def update_operator_sync_location():
    _log_separator("TASK: update_operator_sync_location START")
    task_start = time.time()
    try:
        # -------- ECMP sync --------
        _log_separator("update_operator_sync_location: ECMP sync START")
        ecmp_start = time.time()
        ecmp_sync = trino('''
            select upper(operator_id) as operator_id, longitude, latitude, event_timestamp as last_Updated_Date
            from flink_stream.stream_enu.enu_operator_sync_raw
            where event_timestamp>=date(current_timestamp - interval '1' day)
        ''')
        
        if 'df' in ecmp_sync and len(ecmp_sync['df']) > 0:
            loc_data = ecmp_sync['df']
            logger.info(f"[update_operator_sync_location][ECMP] Rows fetched: {len(loc_data)}")
            
            # 1. Replace pandas NaNs with None
                        # 1. Replace pandas NaNs with None
            df = loc_data.astype(object).where(pd.notnull(loc_data), None)
            
            # 2. Prepare the data with validation
            data_to_insert = []
            skipped_rows = []
            for row in df[['operator_id', 'longitude', 'latitude', 'last_Updated_Date']].itertuples(index=False):
                operator_id = row.operator_id
                # Convert DMS to Decimal Degrees
                lon = convert_dms_to_dd(row.longitude)
                lat = convert_dms_to_dd(row.latitude)
                updated_at = row.last_Updated_Date

                # Explicit float conversion to ensure boundary checks work
                try:
                    lon = float(lon)
                    lat = float(lat)
                except (ValueError, TypeError):
                    lon = None
                    lat = None

                if lon is not None and lat is not None:
                    # Validate that both are within proper geographic bounds
                    if (-90 <= lat <= 90) and (-180 <= lon <= 180):
                        # FIX: MySQL SRID 4326 expects POINT(latitude longitude)
                        point_wkt = f'POINT({lat} {lon})'
                        data_to_insert.append((operator_id, point_wkt, updated_at))
                    else:
                        skipped_rows.append((operator_id, lon, lat))
                        
            logger.info(f"[update_operator_sync_location][ECMP] Prepared {len(data_to_insert)} valid rows. Skipped {len(skipped_rows)} invalid rows due to bad GPS data.")
            
            success, failed = 0, 0
            for idx, (operator_id, point_wkt, updated_at) in enumerate(data_to_insert):
                updt_str = updated_at if isinstance(updated_at, str) else str(updated_at)
                
                # FIX: Added 4326 as the SRID parameter to match the column's SRID
                ecmp_loc_upsert_query = f'''
                    INSERT INTO operator360.operator_sync_location
                        (opt_id, loc, updated_at)
                    VALUES
                        ('{operator_id}', 
                         ST_GeomFromText('{point_wkt}', 4326),
                         cast('{updt_str}' as datetime))
                    ON DUPLICATE KEY UPDATE
                        loc = VALUES(loc), 
                        updated_at = VALUES(updated_at)
                '''
                ok = write_data_to_mysql(ecmp_loc_upsert_query)
                if ok:
                    success += 1
                else:
                    failed += 1
                if (idx + 1) % 5000 == 0:
                    logger.info(f"[update_operator_sync_location][ECMP] Progress: processed={idx+1}/{len(data_to_insert)} "
                                f"success={success} failed={failed}")
            logger.info(f"[update_operator_sync_location][ECMP] DONE | rows={len(data_to_insert)} success={success} failed={failed} "
                        f"elapsed={round(time.time()-ecmp_start,3)}s")
        else:
            logger.warning("[update_operator_sync_location][ECMP] No data returned from Trino.")
            
        # -------- UC sync --------
        _log_separator("update_operator_sync_location: UC sync START")
        uc_start = time.time()
        uc_sync = trino('''
            with tab1 as (
                select upper(operator_id) as operator_id, resident_sid,
                row_number() over(partition by operator_id order by event_timestamp desc) as rw
                from flink_stream.stream_enu.enu_uc_opt_action_v2
                where event_timestamp>=date(current_timestamp - interval '1' day)
            ),
            tab2 as (select * from tab1 where rw=1),
            tab3 as (
                select upper(operator_id) as operator_id, resident_sid,
                       max(latitude) as latitude, max(longitude) as longitude,
                       max(event_timestamp) as last_Updated_Date
                from flink_stream.stream_enu.enu_uc_opt_action_v2
                where event_timestamp>=date(current_timestamp - interval '1' day)
                group by 1,2
            ),
            tab4 as (
                select t1.* from tab3 t1
                right join tab2 t2 on t1.operator_id=t2.operator_id and t1.resident_sid=t2.resident_sid
            )
            select * from tab4 where operator_id is not Null order by operator_id
        ''', host='10.10.116.75')
        
        if 'df' in uc_sync and len(uc_sync['df']) > 0:
            loc_data = uc_sync['df']
            logger.info(f"[update_operator_sync_location][UC] Rows fetched: {len(loc_data)}")
            
            # 1. Replace pandas NaNs with None
                        # 1. Replace pandas NaNs with None
            df = loc_data.astype(object).where(pd.notnull(loc_data), None)
            
            # 2. Prepare the data with validation
            data_to_insert = []
            skipped_rows = []
            for row in df[['operator_id', 'longitude', 'latitude', 'last_Updated_Date']].itertuples(index=False):
                operator_id = row.operator_id
                # Convert DMS to Decimal Degrees
                lon = convert_dms_to_dd(row.longitude)
                lat = convert_dms_to_dd(row.latitude)
                updated_at = row.last_Updated_Date

                # Explicit float conversion to ensure boundary checks work
                try:
                    lon = float(lon)
                    lat = float(lat)
                except (ValueError, TypeError):
                    lon = None
                    lat = None

                if lon is not None and lat is not None:
                    # Validate that both are within proper geographic bounds
                    if (-90 <= lat <= 90) and (-180 <= lon <= 180):
                        # FIX: MySQL SRID 4326 expects POINT(latitude longitude)
                        point_wkt = f'POINT({lat} {lon})'
                        data_to_insert.append((operator_id, point_wkt, updated_at))
                    else:
                        skipped_rows.append((operator_id, lon, lat))
                        
            logger.info(f"[update_operator_sync_location][UC] Prepared {len(data_to_insert)} valid rows. Skipped {len(skipped_rows)} invalid rows due to bad GPS data.")
            
            success, failed = 0, 0
            for idx, (operator_id, point_wkt, updated_at) in enumerate(data_to_insert):
                updt_str = updated_at if isinstance(updated_at, str) else str(updated_at)
                
                # FIX: Added 4326 as the SRID parameter to match the column's SRID
                uc_loc_upsert_query = f'''
                    INSERT INTO operator360.operator_sync_location
                        (opt_id, loc, updated_at)
                    VALUES
                        ('{operator_id}', 
                         ST_GeomFromText('{point_wkt}', 4326),
                         cast('{updt_str}' as datetime))
                    ON DUPLICATE KEY UPDATE
                        loc = VALUES(loc), 
                        updated_at = VALUES(updated_at)
                '''
                ok = write_data_to_mysql(uc_loc_upsert_query)
                if ok:
                    success += 1
                else:
                    failed += 1
                if (idx + 1) % 5000 == 0:
                    logger.info(f"[update_operator_sync_location][UC] Progress: processed={idx+1}/{len(data_to_insert)} "
                                f"success={success} failed={failed}")
            logger.info(f"[update_operator_sync_location][UC] DONE | rows={len(data_to_insert)} success={success} failed={failed} "
                        f"elapsed={round(time.time()-uc_start,3)}s")
        else:
            logger.warning("[update_operator_sync_location][UC] No data returned from Trino.")
            
        logger.info(f"[update_operator_sync_location] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_operator_sync_location] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task 3: update_top_anomaly
# ---------------------------------------------------------------------------
def update_top_anomaly():
    _log_separator("TASK: update_top_anomaly START")
    task_start = time.time()
    try:
        active = get_active_risk_data()
        if active:
            destination_table, feature_id = active
            last_risk_engine_updt_date = get_latest_risk_engine_date(destination_table)
            logger.info(f"[update_top_anomaly] last_risk_engine_updt_date={last_risk_engine_updt_date}")
        else:
            logger.error("[update_top_anomaly] Could not fetch active risk data. Aborting.")
            return

        logger.info("[update_top_anomaly] Fetching opt_store data (ro/district/state).")
        df_store = trino(f'''
            with tab1 as (
                select upper(opt_id) as opt_id, reg_ro_name as opt_ro 
                from strot.operator360.opt_details where reg_ro_name is not null
            ),
            tab2 as (
                select upper(id) as opt_id, district, state
                from mysql_dataplatform_read.operator360.opt_master
                where district is not Null and state is not Null
            )
            select t1.*, t2.district as opt_district, t2.state as opt_state
            from tab1 t1 right join tab2 t2 on t1.opt_id=t2.opt_id            
        ''')

        if 'df' in df_store.keys():
            df_store_pandas = df_store['df']
            logger.info(f"[update_top_anomaly] opt_store rows fetched: {len(df_store_pandas)}")
        else:
            df_store_pandas = pd.DataFrame()
            logger.warning("[update_top_anomaly] df_store returned no data. Aborting.")
            return

        all_merged_data = []
        total_codes = len(anomaly_code)
        logger.info(f"[update_top_anomaly] Iterating over {total_codes} anomaly codes.")

        for idx, code in enumerate(anomaly_code, start=1):
            logger.info(f"[update_top_anomaly] ({idx}/{total_codes}) Processing anomaly_code={code}")
            df_risk = trino(f'''
                WITH entity_with_i_score AS (
                    SELECT DISTINCT UPPER(entity_id) AS opt_id
                    FROM strot.operator360.features_risk_v1
                    WHERE DATE(timestamp) = DATE('{last_risk_engine_updt_date}')
                      AND feature_name = '{code}_score'
                      AND feature_value IS NOT NULL
                )
                SELECT 
                    UPPER(entity_id) AS opt_id,
                    MAX(CASE WHEN feature_name = 'risk_score' THEN COALESCE(feature_value, 0) END) AS risk_score,
                    MAX(CASE WHEN feature_name = '{code}_score' THEN COALESCE(feature_value, 0) END) AS anomaly_score
                FROM strot.operator360.features_risk_v1
                WHERE DATE(timestamp) = DATE('{last_risk_engine_updt_date}')
                  AND UPPER(entity_id) IN (SELECT opt_id FROM entity_with_i_score)
                  AND feature_name IN ('risk_score', '{code}_score')
                GROUP BY UPPER(entity_id)
            ''')

            if 'df' not in df_risk.keys():
                logger.warning(f"[update_top_anomaly] ({idx}/{total_codes}) No df returned for code={code}. Skipping.")
                continue
            if df_store_pandas.empty:
                logger.warning(f"[update_top_anomaly] ({idx}/{total_codes}) df_store_pandas is empty. Skipping code={code}.")
                continue

            df_risk_pandas = df_risk['df']
            logger.info(f"[update_top_anomaly] ({idx}/{total_codes}) risk rows fetched: {len(df_risk_pandas)}")
            if df_risk_pandas.empty:
                logger.info(f"[update_top_anomaly] ({idx}/{total_codes}) No risk rows. Skipping merge.")
                continue

            df_risk_pandas['anomaly_code_with_highest_score'] = code
            df_merged = df_store_pandas.merge(df_risk_pandas, on='opt_id', how='inner')

            if not df_merged.empty:
                logger.info(f"[update_top_anomaly] ({idx}/{total_codes}) Merged rows: {len(df_merged)}")
                all_merged_data.append(df_merged)
            else:
                logger.info(f"[update_top_anomaly] ({idx}/{total_codes}) Merge produced 0 rows.")

        if all_merged_data:
            logger.info(f"[update_top_anomaly] Concatenating {len(all_merged_data)} merged frames.")
            final_df = pd.concat(all_merged_data, ignore_index=True)
            final_df = final_df.rename(columns={'anomaly_score': 'highest_anomaly_code_score'})
            final_df = final_df.sort_values(by=['opt_id', 'highest_anomaly_code_score'], ascending=[True, False])
            columns_to_keep = [
                'opt_id', 'opt_ro', 'opt_district', 'opt_state',
                'risk_score', 'highest_anomaly_code_score', 'anomaly_code_with_highest_score'
            ]
            final_df = final_df[columns_to_keep]
            final_df = final_df.drop_duplicates(subset=['opt_id'], keep='first')
            final_df = final_df.reset_index(drop=True)
            logger.info(f"[update_top_anomaly] Final unique opt_ids to update: {len(final_df)}")
            logger.info(f"[update_top_anomaly] Top anomaly distribution:\n{final_df['anomaly_code_with_highest_score'].value_counts()}")
            logger.info(f"[update_top_anomaly] Sample:\n{final_df.head(10)}")

            if len(final_df) > 0:
                logger.info("[update_top_anomaly] Writing top anomaly updates to MySQL.")
                success, failed = 0, 0
                for idx, row in final_df.iterrows():
                    top_anomaly_update_query = f'''
                        update operator360.opt_master 
                        set top_anomaly= '{row['anomaly_code_with_highest_score']}',
                        updated_at=CONVERT_TZ(NOW(), @@session.time_zone, '+05:30')
                        where id= '{row['opt_id']}'
                    '''
                    ok = write_data_to_mysql(top_anomaly_update_query)
                    if ok:
                        success += 1
                    else:
                        failed += 1
                    if (idx + 1) % 1000 == 0:
                        logger.info(f"[update_top_anomaly] Progress: processed={idx+1}/{len(final_df)} "
                                    f"success={success} failed={failed}")
                logger.info(f"[update_top_anomaly] MySQL updates DONE | success={success} failed={failed}")
        else:
            logger.warning("[update_top_anomaly] No matching data found across any anomaly codes.")

        logger.info(f"[update_top_anomaly] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_top_anomaly] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task 4: update_opt360_features
# ---------------------------------------------------------------------------
def update_opt360_features():
    _log_separator("TASK: update_opt360_features START")
    task_start = time.time()
    try:
        logger.info("[update_opt360_features] Fetching opt360_features from Trino.")
        features = trino('''
            select * from strot.operator360.opt360_features
        ''')

        if 'df' not in features:
            logger.error(f"[update_opt360_features] Trino query failed. Response: {features}")
            return

        df = features['df']
        total = len(df)
        logger.info(f"[update_opt360_features] Features rows fetched: {total}")

        feature_updt_query = '''
            INSERT INTO operator360.features 
            (`id`, `name`, `description`, `data_type`, `status`, `is_active`, `is_risk`, `version`,
             `update_window`, `source_table`, `destination_table`, `source_query`,
             `dependent_features`, `category`, `created_at`, `created_by`, `updated_at`, `updated_by`)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
              `name` = VALUES(`name`),
              `description` = VALUES(`description`),
              `data_type` = VALUES(`data_type`),
              `status` = VALUES(`status`),
              `is_active` = VALUES(`is_active`),
              `is_risk` = VALUES(`is_risk`),
              `version` = VALUES(`version`),
              `update_window` = VALUES(`update_window`),
              `source_table` = VALUES(`source_table`),
              `destination_table` = VALUES(`destination_table`),
              `source_query` = VALUES(`source_query`),
              `dependent_features` = VALUES(`dependent_features`),
              `category` = VALUES(`category`),
              `created_at` = VALUES(`created_at`),
              `created_by` = VALUES(`created_by`),
              `updated_at` = VALUES(`updated_at`),
              `updated_by` = VALUES(`updated_by`)
        '''

        success, failed = 0, 0
        for idx, row in df.iterrows():
            feature_id = row['feature_id']
            is_active = int(row['is_active']) if pd.notna(row['is_active']) else 0
            is_risk = int(row['is_risk']) if pd.notna(row['is_risk']) else 0
            version = row['version']

            if pd.notna(row['created_at']):
                created_at = pd.Timestamp(row['created_at']).strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if pd.notna(row['updated_at']):
                updated_at = pd.Timestamp(row['updated_at']).strftime('%Y-%m-%d %H:%M:%S')
            else:
                updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            dependent_features = json.dumps(row['dependent_features']) if isinstance(row['dependent_features'], list) else row['dependent_features']

            values = (
                feature_id, row['feature_name'], row['description'], row['data_type'],
                row['status'], is_active, is_risk, version, row['update_window'],
                row['source_table'], row['destination_table'], row['query'],
                dependent_features, '', created_at, row['created_by'], updated_at, row['updated_by']
            )

            logger.info(f"[update_opt360_features] ({idx+1}/{total}) Upserting feature_id={feature_id} "
                        f"is_active={is_active} is_risk={is_risk} version={version}")
            ok = write_data_to_mysql(feature_updt_query, values)
            if ok:
                success += 1
            else:
                failed += 1

        logger.info(f"[update_opt360_features] Summary: total={total} success={success} failed={failed}")
        logger.info(f"[update_opt360_features] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_opt360_features] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task 5: update_operator_metadata
# ---------------------------------------------------------------------------
def update_operator_metadata(custom_id: str = ''):
    label = f"custom_id={custom_id}" if custom_id else "incremental"
    _log_separator(f"TASK: update_operator_metadata START ({label})")
    task_start = time.time()
    try:
        logger.info(f"[update_operator_metadata] Building query for {label}")
        query = '''
            with tab1 as (
                select upper(user_code) as opt_id, user_name, user_uid,
                user_key, user_org_key as ea_key, user_reg_org_key as reg_key, user_contact_key, ro_key
                from mysql_uidmasterv1.uidmasterv1_1.user 
        '''

        if custom_id != '':
            logger.info(f"[update_operator_metadata] Filtering for single user_id={custom_id}")
            query += f" where upper(id)='{custom_id}' "
        else:
            logger.info("[update_operator_metadata] Incremental: filtering last_updated_date >= 7 days ago.")
            query += " where last_updated_date >= date(current_date - interval '7' day) "

        query += '''
            ),
            tab2 as (
                select t1.org_name as ea_name, t1.org_code as ea_code, t2.*
                from mysql_uidmasterv1.uidmasterv1_1.organization t1 
                right join tab1 t2 on t1.org_key = t2.ea_key
            ),
            tab3 as (
                select t1.org_name as reg_name, t1.org_code as reg_code, t2.*
                from mysql_uidmasterv1.uidmasterv1_1.organization t1 
                right join tab2 t2 on t1.org_key = t2.reg_key
            ),
            tab4 as (
                select coalesce(t1.phone1, t1.phone2) as phone_number, 
                       coalesce(t1.email_id1, t1.email_id2) as email, t2.*
                from mysql_uidmasterv1.uidmasterv1_1.contact t1 
                right join tab3 t2 on t1.contact_key = t2.user_contact_key
            ),
            tab5 as (
                select t1.ro_name, t2.*
                from mysql_uidmasterv1.uidmasterv1_1.regional_office t1 
                right join tab4 t2 on t1.ro_key = t2.ro_key
            )
            select * from tab5
        '''

        result = trino(query)

        if 'df' not in result:
            logger.error(f"[update_operator_metadata] Trino query failed. Response: {result}")
            return

        df = result['df']
        if len(df) == 0:
            logger.warning(f"[update_operator_metadata] No rows returned ({label}). Nothing to update.")
            return

        logger.info(f"[update_operator_metadata] Rows fetched ({label}): {len(df)}")
        success, failed = 0, 0
        for idx, row in df.iterrows():
            uid_val = str(row['user_uid']) if row['user_uid'] is not None else None

            upsert_query = f'''
                INSERT INTO operator360.opt_master 
                    (id, uid, name, phone, email, reg, reg_code, ea, ea_code, ro, updated_at)
                VALUES 
                    ({_sql(row['opt_id'])}, {_sql(uid_val)}, {_sql(row['user_name'])},
                     {_sql(row['phone_number'])}, {_sql(row['email'])}, {_sql(row['reg_name'])},
                     {_sql(row['reg_code'])}, {_sql(row['ea_name'])}, {_sql(row['ea_code'])},
                     {_sql(row['ro_name'])}, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    uid = IF(uid IS NULL, VALUES(uid), uid),
                    name = IF(name IS NULL, VALUES(name), name),
                    phone = IF(phone IS NULL, VALUES(phone), phone),
                    email = IF(email IS NULL, VALUES(email), email),
                    reg = IF(reg IS NULL or reg='None' or reg='Unknown', VALUES(reg), reg),
                    reg_code = IF(reg IS NULL or reg='None' or reg='Unknown', VALUES(reg_code), reg_code),
                    ea = IF(ea IS NULL or ea='None' or ea='Unknown', VALUES(ea), ea),
                    ea_code = IF(ea IS NULL or ea='None' or ea='Unknown', VALUES(ea_code), ea_code),
                    ro = IF(ro IS NULL or ro='None' or ro='Unknown', VALUES(ro), ro),
                    updated_at = IF(uid IS NULL OR name IS NULL OR phone IS NULL OR email IS NULL OR 
                        reg IS NULL OR reg='None' OR reg='Unknown' OR 
                        ea IS NULL OR ea='None' OR ea='Unknown' OR 
                        ro IS NULL, CURRENT_TIMESTAMP, updated_at)
            '''
            ok = write_data_to_mysql(upsert_query)
            if ok:
                success += 1
            else:
                failed += 1
            if (idx + 1) % 2000 == 0:
                logger.info(f"[update_operator_metadata] Progress ({label}): processed={idx+1}/{len(df)} "
                            f"success={success} failed={failed}")

        logger.info(f"[update_operator_metadata] DONE ({label}) | rows={len(df)} success={success} failed={failed} "
                    f"elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_operator_metadata] Unhandled exception ({label}): {e}")
        raise


# ---------------------------------------------------------------------------
# Task 6: update_activeness
# ---------------------------------------------------------------------------
def update_activeness():
    _log_separator("TASK: update_activeness START")
    task_start = time.time()
    try:
        query = '''
            select upper(user_code) as opt_id,
                   case when user_status='1' then 1 else 0 end as status
            from mysql_uidmasterv1.uidmasterv1_1.user
            where date(last_updated_date) >= date(current_date - interval '30' day)
        '''
        df = trino(query)

        if 'df' not in df:
            logger.error(f"[update_activeness] Trino query failed. Response: {df}")
            return

        df = df['df']
        if len(df) == 0:
            logger.warning("[update_activeness] No rows fetched. Nothing to update.")
            return

        logger.info(f"[update_activeness] Rows fetched: {len(df)}")
        logger.info(f"[update_activeness] Status distribution:\n{df['status'].value_counts()}")

        success, failed = 0, 0
        for idx, r in df.iterrows():
            update_query = f'''
                update operator360.opt_master
                set `is_active`={r['status']}, updated_at= current_timestamp()
                where `id`= '{r['opt_id']}'
            '''
            ok = write_data_to_mysql(update_query)
            if ok:
                success += 1
            else:
                failed += 1
            if (idx + 1) % 2000 == 0:
                logger.info(f"[update_activeness] Progress: processed={idx+1}/{len(df)} success={success} failed={failed}")

        logger.info(f"[update_activeness] DONE | rows={len(df)} success={success} failed={failed} "
                    f"elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[update_activeness] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task 7: general_update
# ---------------------------------------------------------------------------
def general_update():
    _log_separator("TASK: general_update START")
    task_start = time.time()
    try:
        # Step 1: rename New Delhi -> Delhi
        logger.info("[general_update] Step 1: Updating ro='New Delhi' -> 'Delhi'.")
        updt_query1 = '''
        update operator360.opt_master
        set `ro`='Delhi'
        where `ro`='New Delhi';
        '''
        write_data_to_mysql(updt_query1)

        # Step 2: trim ids
        logger.info("[general_update] Step 2: Trimming whitespace from id column.")
        trim_query = '''
        UPDATE operator360.opt_master
        SET id = TRIM(id)
        WHERE id != TRIM(id);
        '''
        write_data_to_mysql(trim_query)

        # Step 3: resolve unknown ro
        logger.info("[general_update] Step 3: Fetching ids with ro='Unknown' for metadata refresh.")
        get_ids_query = "select id from operator360.opt_master where ro='Unknown'"
        ids_data = show_dbs(get_ids_query)
        logger.info(f"[general_update] Found {len(ids_data)} operators with ro='Unknown'.")

        if ids_data:
            processed = 0
            for idx, tup in enumerate(ids_data, start=1):
                opt_id = tup[0]
                logger.info(f"[general_update] ({idx}/{len(ids_data)}) Refreshing metadata for id={opt_id}")
                try:
                    update_operator_metadata(opt_id)
                    processed += 1
                except Exception as ex:
                    logger.error(f"[general_update] Failed refreshing id={opt_id}: {ex}")
            logger.info(f"[general_update] Metadata refresh summary: total={len(ids_data)} processed={processed}")

        logger.info(f"[general_update] END | total_elapsed={round(time.time()-task_start,3)}s")
    except Exception as e:
        logger.exception(f"[general_update] Unhandled exception: {e}")
        raise


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------
update_risk_score_task = PythonOperator(
    task_id='risk_score_updation',
    python_callable=update_risk_score,
    trigger_rule='all_done',
    dag=dag,
)

update_sync_details_task = PythonOperator(
    task_id='sync_details_updation',
    python_callable=update_sync_details,
    trigger_rule='all_done',
    dag=dag,
)


update_sync_location_task = PythonOperator(
    task_id='sync_location_updation',
    python_callable=update_operator_sync_location,
    trigger_rule='all_done',
    dag=dag,
)

update_opt360_features_task = PythonOperator(
    task_id='opt360_features_task',
    python_callable=update_opt360_features,
    trigger_rule='all_done',
    dag=dag,
)

update_top_anomaly_task = PythonOperator(
    task_id='update_top_anomaly',
    python_callable=update_top_anomaly,
    trigger_rule='all_done',
    dag=dag,
)

update_operator_metadata_task = PythonOperator(
    task_id='update_operator_metadata',
    python_callable=update_operator_metadata,
    trigger_rule='all_done',
    dag=dag,
)

general_update_task = PythonOperator(
    task_id='general_update',
    python_callable=general_update,
    trigger_rule='all_done',
    dag=dag,
)

update_activeness_task = PythonOperator(
    task_id='update_activeness',
    python_callable=update_activeness,
    trigger_rule='all_done',
    dag=dag,
)

update_operator_metadata_task >> update_activeness_task  >> \
    update_risk_score_task >> update_sync_details_task  >> update_sync_location_task >> general_update_task