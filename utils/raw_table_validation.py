import pandas as pd
import boto3
import json
import time
from botocore.exceptions import ClientError
from trino.dbapi import connect
import logging

logger = logging.getLogger(__name__)

# --- Existing Configs ---
trino_host = "10.10.116.75"
trino_port = 8080
trino_user = "opt360_feature_metadata"

table_timestamp_column_mapping = {
    'flink_stream.stream_enu.ens_packet_enriched': 'event_timestamp',
    'flink_stream.stream_enu.bi_enu_enrlraw_v2': 'processed_timestamp',
    'flink_stream.analytics_enu.machine_hardware_trust_change': 'record_timestamp',
    'flink_stream.operator360.opt_auth_txn_v3': 'event_timestamp',
    'flink_stream.stream_enu.enu_uc_opt_action_v2': 'event_timestamp',  # Note: kept trailing space if intentional
    'flink_stream.stream_enu.enu_operator_sync_raw': 'event_timestamp',
    'strot.operator360.uc_machineip_isp_map': 'uc_event_timestamp',
    'strot.operator360.opt_oddhour_anomalous_ens_eid_daily': 'event_timestamp',
    'strot.operator360.opt_outstate_anomalous_enu_eid_daily': 'event_timestamp',
    'strot.operator360.txn_parallel_enrl_v1': 'timestamp',
    'flink_stream.mysql_uid_v2.uid_origin_tracker_enriched ': 'enr_date' , # Note: kept trailing space,
    'flink_stream.stream_enu.enu_bfc_analytics_raw_v1':'eventtimestamp',
    'strot.operator360.eid_qc_error_report_v2':'last_updated_at',
}

# --- Ceph S3 Cache Configuration ---
CEPH_ENDPOINT_URL = "http://10.10.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-data-platform-test"
CEPH_CACHE_PREFIX = "cache/airflow/operator360"

CACHE_TTL_SECONDS = 20 * 60 * 60  # 20 hours

# In-memory overlay for the current Airflow task process
_memory_cache = {}

def trino(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        q_lower = query.strip().lower()
        logger.info("Trino: executing query => %s", query)
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        
        # Only fetch results for SELECT/SHOW/DESCRIBE/EXPLAIN queries
        if q_lower.startswith(("select", "with", "show", "describe", "explain")):
            body = cur.fetchall()
            if not body:
                logger.info("Trino: query returned 0 rows")
                return {"query": query, "success": 1, "data": body}
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            logger.info("Trino: query returned %d rows; columns=%s", len(df), cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df}
        else:
            # DML/DDL executed successfully
            logger.info("Trino: statement executed successfully (no result set)")
            return {"query": query, "success": 1}
    except Exception as e:
        logger.exception("Trino: query failed: %s", e)
        return {"query": query, "success": 0, "msg": str(e)}


def _get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY
    )

def _get_s3_key(table_name: str) -> str:
    # Sanitize table name (replace dots with underscores) for clean S3 keys
    safe_table_name = table_name.replace('.', '_')
    # Remove any trailing/leading spaces just for the filename to be safe
    safe_table_name = safe_table_name.strip()
    return f"{CEPH_CACHE_PREFIX}/{safe_table_name}.json"


def _load_from_s3(s3_client, table_name: str) -> dict:
    key = _get_s3_key(table_name)
    try:
        response = s3_client.get_object(Bucket=CEPH_BUCKET_NAME, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        logger.error("[cache] S3 Error reading %s: %s", key, e)
        return None

def _save_to_s3(s3_client, table_name: str, data: dict):
    key = _get_s3_key(table_name)
    try:
        s3_client.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=key,
            Body=json.dumps(data).encode('utf-8'),
            ContentType='application/json'
        )
    except ClientError as e:
        logger.error("[cache] S3 Error writing %s: %s", key, e)


def _is_cache_valid(entry: dict) -> bool:
    if not entry or 'timestamp' not in entry:
        return False
    return (time.time() - entry['timestamp']) < CACHE_TTL_SECONDS


def clear_cache(table_name: str = None):
    """Force-clear cache for one table or all."""
    s3_client = _get_s3_client()
    if table_name:
        logger.info("Clearing S3 cache for table: %s", table_name)
        s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=_get_s3_key(table_name))
        _memory_cache.pop(table_name, None)
    else:
        logger.info("Clearing all S3 cache under prefix: %s", CEPH_CACHE_PREFIX)
        # Delete all objects under the prefix
        objects = s3_client.list_objects_v2(Bucket=CEPH_BUCKET_NAME, Prefix=f"{CEPH_CACHE_PREFIX}/")
        if 'Contents' in objects:
            for obj in objects['Contents']:
                s3_client.delete_object(Bucket=CEPH_BUCKET_NAME, Key=obj['Key'])
        _memory_cache.clear()


def check_raw_tables(table_name: str, use_cache: bool = True) -> bool:
    # 1. Check In-Memory Overlay (Fastest, specific to this Airflow task process)
    if use_cache and table_name in _memory_cache:
        entry = _memory_cache[table_name]
        if _is_cache_valid(entry):
            logger.info('[cache] MEMORY HIT for %s -> %s', table_name, entry["result"])
            return entry['result']

    # 2. Validate mapping BEFORE hitting S3 or Trino
    if table_name not in table_timestamp_column_mapping.keys():
        logger.warning("Table '%s' not found in mapping. Please add it to table_timestamp_column_mapping.", table_name)
        return True

    s3_client = _get_s3_client()

    # 3. Check S3 Cache
    if use_cache:
        entry = _load_from_s3(s3_client, table_name)
        if entry and _is_cache_valid(entry):
            logger.info('[cache] S3 HIT for %s -> %s (age=%ds)', table_name, entry["result"], int(time.time() - entry["timestamp"]))
            _memory_cache[table_name] = entry  # populate memory for next time in this process
            return entry['result']
        else:
            logger.info('[cache] MISS/EXPIRED for %s, querying Trino...', table_name)

    # 4. Query Trino
    ts_col = table_timestamp_column_mapping[table_name]
    
    logger.info("Querying Trino for row count in table %s for yesterday's data...", table_name)
    df_result = trino(f'''
        select count(*) as cnt 
        from {table_name} 
        where date({ts_col}) = date(current_date - interval '1' day)        
    ''')

    if 'df' not in df_result.keys():
        logger.error("Trino Error checking raw table %s: %s", table_name, df_result)
        return False

    row_count = df_result['df']['cnt'][0]

    if row_count == 0:
        logger.warning("No data found for previous date in table %s", table_name)
        result = False
    else:
        logger.info("Data found for previous date in table %s (rows=%d)", table_name, row_count)
        result = True

    # 5. Write back to S3 and Memory
    cache_entry = {
        'result': result,
        'timestamp': time.time(),
        'row_count': int(row_count),
    }
    _save_to_s3(s3_client, table_name, cache_entry)
    _memory_cache[table_name] = cache_entry

    return result


def get_source_tables(category: str) -> dict:
    df_source_table = None
    successful_host = None
    
    for host in ['10.10.116.75','10.10.116.39','10.10.118.35','10.10.118.10']:
        logger.info("Fetching source tables for category '%s' from Trino host: %s", category, host)
        df_source_table = trino(f'''
            select feature_id, source_table
            from strot.operator360.opt360_features
            where status='PROD' 
            and feature_id not like '%score%' 
            and feature_id like '{category}%'                
        ''', host=host)

        if 'df' not in df_source_table.keys():
            logger.warning("Failed to fetch from Trino host %s. Error: %s", host, df_source_table)
            continue
        else:
            successful_host = host
            break

    # Safety check in case all hosts failed
    if not df_source_table or 'df' not in df_source_table:
        logger.error("All Trino hosts failed for category '%s'. Unable to fetch source tables.", category)
        return {'success': False, 'error': 'All Trino hosts failed'}

    logger.info("Successfully fetched source tables from host %s", successful_host)
    
    df = df_source_table['df']
    mapping_featureid_source = {}
    
    for _, row in df.iterrows():
        mapping_featureid_source[row['feature_id']] = row['source_table']

    return {'success': True, **mapping_featureid_source}    