from __future__ import annotations

import pendulum
import logging
import time
import pandas as pd
import polars as pl
import clickhouse_connect
from trino.dbapi import connect
import mysql.connector
from datetime import timedelta

# Airflow imports
from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# --- Configuration ---
TRINO_HOST = "10.10.116.75"
TRINO_PORT = 8080
TRINO_USER = "airflow_dag_op"

MYSQL_HOST = "10.10.106.159"
MYSQL_USER = "Data_platform_W"
MYSQL_PASSWORD = "Dataplat_7634"

CH_HOST = '10.10.120.86'
CH_USER = 'default'
CH_PASSWORD = 'qwerty'
CH_DATABASE = 'default'
CH_TABLE = 'opt360_feature_store_test_v1'

ENTITY_BATCH_SIZE = 1000

# --- Helper Functions (Stateless Utilities) ---

def chunked(seq, size):
    """Yield successive chunks of length `size` from a list."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def _run_trino_query(query, host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER):
    """Run a Trino query and return a Pandas DataFrame."""
    start_time = time.time()
    conn = None
    try:
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        df = pd.DataFrame(body, columns=cols) if cols else pd.DataFrame()
        return {"success": 1, "df": df, "execution_time": time.time() - start_time}
    except Exception as e:
        logger.exception("Trino query failed")
        return {"success": 0, "msg": str(e), "df": pd.DataFrame(), "execution_time": time.time() - start_time}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def _fetch_mysql_query(query, host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD):
    """Execute MySQL query and return a Polars DataFrame."""
    connection = None
    try:
        connection = mysql.connector.connect(host=host, user=user, password=password)
        cursor = connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        safe_results = [
            [str(item) if item is not None else None for item in row]
            for row in results
        ]
        return pl.DataFrame(safe_results, schema=columns, orient="row") if columns else pl.DataFrame()
    except Exception:
        logger.exception("MySQL query execution failed.")
        raise
    finally:
        if connection:
            try:
                connection.close()
            except Exception:
                pass

def _get_feature_group(feature_id):
    prefix = feature_id.split('_')[0] if '_' in feature_id else feature_id
    mapping = {
        'auth': 'Authentication',
        'bio': 'Biometrics',
        'work': 'Work',
        'harware': 'Hardware',
        'sustxn': 'Suspicious Transaction',
        'doc': "Document",
    }
    return mapping.get(prefix, prefix)

def _build_trino_query(dest_table, entity_ids_batch):
    entity_ids_str = ", ".join(f"'{e}'" for e in entity_ids_batch)
    return f"""
        SELECT entity_id, feature_value, timestamp
        FROM (
            SELECT entity_id, feature_value, timestamp,
                ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY timestamp DESC) AS rn
            FROM {dest_table}
            WHERE entity_id IN ({entity_ids_str})
        )
        WHERE rn = 1
    """

# --- Plain Python Functions ---

def get_feature_list() -> list[dict]:
    """Fetches feature configurations from Trino."""
    resp = _run_trino_query("""
        SELECT feature_id, destination_table, description
        FROM strot.operator360.opt360_features 
        WHERE status = 'PROD'
          AND destination_table != 'flink_stream.operator360.features_auth_v1' 
          AND destination_table IS NOT NULL 
          AND feature_id NOT LIKE '%category%'
          AND feature_id NOT LIKE '%zscore%' 
          AND feature_id NOT LIKE '%risk_score%'
        ORDER BY feature_id ASC
    """)
    
    if not resp.get("success"):
        raise ValueError(f"Failed to fetch feature configs: {resp.get('msg')}")
    
    features = resp["df"].to_dict(orient='records')
    logger.info(f"Found {len(features)} features to process.")
    return features

def get_risk_buckets() -> list[str]:
    """Returns the list of risk buckets to process."""
    return ['Critical', 'High', 'Medium', 'Low', 'No']

def process_feature_for_bucket(feature: dict, risk_bucket: str):
    """Processes a single feature for a single risk bucket with batched entity IDs."""
    feature_id = feature['feature_id']
    dest_table = feature['destination_table']
    description = feature['description']

    if pd.isna(dest_table) or not dest_table:
        return

    logger.info(f"Processing feature: {feature_id} for bucket: {risk_bucket}")

    # 1. Fetch Entity IDs from MySQL
    mysql_query = f"""
        SELECT id FROM operator360.opt_master
        WHERE is_active = true AND risk_bucket = '{risk_bucket}'
    """
    data_df = _fetch_mysql_query(mysql_query)
    entity_ids = data_df['id'].to_list()

    if not entity_ids:
        logger.info(f"No entities for bucket {risk_bucket}; skipping feature {feature_id}.")
        return

    # 2. Initialize ClickHouse Client
    ch_client = clickhouse_connect.get_client(
        host=CH_HOST, username=CH_USER, password=CH_PASSWORD, database=CH_DATABASE
    )

    # 3. Batched entity_id processing via Trino
    batch_dfs = []
    for batch_idx, batch in enumerate(chunked(entity_ids, ENTITY_BATCH_SIZE), start=1):
        trino_query = _build_trino_query(dest_table, batch)
        resp = _run_trino_query(trino_query)

        if not resp.get("success"):
            logger.error(f"Trino query error for {feature_id} batch {batch_idx}: {resp.get('msg')}")
            continue

        if not resp["df"].empty:
            batch_dfs.append(resp["df"])

    if not batch_dfs:
        logger.info(f"No data found for {feature_id} in bucket {risk_bucket}.")
        return

    result_df = pd.concat(batch_dfs, ignore_index=True)

    # 4. Transform (Vectorized)
    feature_name = feature_id.replace('_', ' ')
    feature_group = _get_feature_group(feature_id)
    desc_safe = '' if pd.isna(description) else description

    result_df['feature_id'] = feature_id
    result_df['feature_name'] = feature_name
    result_df['description'] = desc_safe
    result_df['feature_group'] = feature_group
    result_df = result_df.rename(columns={'timestamp': 'last_updated_at'})
    result_df['last_updated_at'] = pd.to_datetime(result_df['last_updated_at'], errors='coerce')

    result_df = result_df.drop_duplicates(
        subset=['entity_id', 'feature_id'], keep='last'
    ).reset_index(drop=True)

    result_df = result_df[[
        'entity_id', 'feature_id', 'feature_value', 'feature_name',
        'description', 'last_updated_at', 'feature_group'
    ]]

    # 5. Upload to ClickHouse
    try:
        ch_client.insert_df(CH_TABLE, result_df)
        logger.info(f"Successfully uploaded {len(result_df)} rows to ClickHouse for {feature_id} ({risk_bucket}).")
    except Exception as e:
        logger.exception(f"ClickHouse insert failed for {feature_id} ({risk_bucket})")
        raise

def opt360_pipeline_dag():
    """Main execution function wrapped by the PythonOperator."""
    features = get_feature_list()
    buckets = get_risk_buckets()
    
    for risk_bucket in buckets:
        for feature in features:
            try:
                process_feature_for_bucket(feature=feature, risk_bucket=risk_bucket)
            except Exception as e:
                logger.error(f"Error processing feature {feature.get('feature_id')} for risk bucket {risk_bucket}: {e}")
                raise

# --- DAG Definition ---

with DAG(
    dag_id="opt360_clickhouse_feature_store",
    schedule="0 13 * * *",
    start_date=pendulum.datetime(2026, 8, 20, tz="Asia/Kolkata"),
    catchup=False,
    tags=["Operator360", "feature_store", "clickhouse"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    description="Ingests opt360 features from Trino into ClickHouse batched by Risk Bucket"
) as dag:
    
    process_features_list = PythonOperator(
        task_id='process_features_list',
        python_callable=opt360_pipeline_dag,
    )

    process_features_list