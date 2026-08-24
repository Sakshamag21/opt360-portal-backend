"""
Airflow 3 DAG: Operator Risk Analysis → ClickHouse

Pulls operator risk metadata from MySQL (opt_master),
fetches the latest category scores from Trino (strot.operator360.features_risk_v1),
compares MySQL `risk_score` against the maximum category score per operator,
and pushes qualifying rows to ClickHouse `operator360.risk_analysis`.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import clickhouse_connect
import mysql.connector
import pandas as pd
import polars as pl
from trino.dbapi import connect

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


# --------------------------------------------------------------------------- #
# Connection configuration
# --------------------------------------------------------------------------- #
TRINO_HOST = "10.10.116.39"
TRINO_HOST_FALLBACK = "10.10.116.75"
TRINO_PORT = 8080
TRINO_USER = "opt_master_updt"
TRINO_CATALOG_ICEBERG = "strot"

MYSQL_HOST = "10.10.106.159"
MYSQL_USER = "Data_platform_W"
MYSQL_PASSWORD = "Dataplat_7634"

CH_HOST = "10.10.120.86"
CH_USER = "default"
CH_PASSWORD = "qwerty"
CH_DATABASE = "default"
CH_TABLE = "risk_analysis"

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Generic DB helpers
# --------------------------------------------------------------------------- #
def _fetch_mysql_query(query, host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD):
    """Execute a MySQL query and return a Polars DataFrame."""
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


def _run_trino(query, host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER):
    """Run a Trino query and return a dict containing result data and metadata."""
    try:
        start_time = time.time()
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time = time.time()

        if not body:
            return {
                "query": query,
                "success": 1,
                "data": body,
                "execution_time": end_time - start_time,
            }

        cols = [i[0] for i in cur.description]
        df = pd.DataFrame(body, columns=cols)
        return {
            "query": query,
            "success": 1,
            "data": (cols, body),
            "df": df,
            "execution_time": end_time - start_time,
        }
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}


# --------------------------------------------------------------------------- #
# Logging config (module-level; Airflow will also capture task logs)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="risk_categories.log",
    filemode="w",
)


# --------------------------------------------------------------------------- #
# DAG default args
# --------------------------------------------------------------------------- #
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 8, 20, tzinfo=ZoneInfo("Asia/Kolkata")),
    "email": ["techexecutive16-yp25@uidai.net.in"],
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 1,
}


# --------------------------------------------------------------------------- #
# Business-logic functions
# --------------------------------------------------------------------------- #
def fetch_category_scores(trino_host: str = TRINO_HOST_FALLBACK):
    query = """
    WITH tab1 AS (
        SELECT 
            entity_id, 
            feature_id, 
            feature_value,
            ROW_NUMBER() OVER (PARTITION BY entity_id, feature_id ORDER BY timestamp DESC) as rn
        FROM strot.operator360.features_risk_v1 
        WHERE feature_id LIKE '%category%'
    ),
    tab2 AS (
        SELECT entity_id, feature_id, feature_value 
        FROM tab1 
        WHERE rn = 1
    )
    SELECT 
        entity_id,
        MAX(CASE WHEN feature_id = 'auth_category_score_v2' THEN feature_value END)     AS auth_category_score_v2,
        MAX(CASE WHEN feature_id = 'document_category_score_v2' THEN feature_value END) AS document_category_score_v2,
        MAX(CASE WHEN feature_id = 'bio_category_score_v2' THEN feature_value END)      AS bio_category_score_v2,
        MAX(CASE WHEN feature_id = 'sustxn_category_score_v2' THEN feature_value END)   AS sustxn_category_score_v2,
        MAX(CASE WHEN feature_id = 'work_category_score_v2' THEN feature_value END)     AS work_category_score_v2,
        MAX(CASE WHEN feature_id = 'hardware_category_score_v2' THEN feature_value END) AS hardware_category_score_v2
    FROM tab2
    GROUP BY entity_id
    """
    data = _run_trino(query, host=trino_host)
    if "df" not in data:
        return None
    return data["df"]


def fetch_operators():
    """Fetch opt_id -> {name, ro, risk_score, risk_bucket} from MySQL opt_master."""
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        port=3306,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database="operator360",
    )
    operators = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, ro, risk_score, risk_bucket "
                "FROM opt_master WHERE risk_bucket IS NOT NULL"
            )
            for opt_id, name, ro, risk_score, risk_bucket in cur:
                operators[opt_id] = {
                    "name": name,
                    "ro": ro,
                    "risk_score": float(risk_score) if risk_score is not None else None,
                    "risk_bucket": risk_bucket or "",
                }
    finally:
        conn.close()
    return operators


def evaluate(operators, category_scores, ch_client):
    """
    Compare each operator's MySQL `risk_score` against the maximum of its six
    Trino category scores. If |risk_score - max_category| <= 0.1, push the
    category scores to ClickHouse `operator360.risk_analysis`.
    """
    if category_scores is None or len(category_scores) == 0:
        logger.warning("category_scores is empty/None; nothing to evaluate.")
        return {"processed": 0, "pushed": 0}

    df = category_scores.copy()
    df["entity_id"] = df["entity_id"].astype(str).str.strip()

    category_columns = [
        "auth_category_score_v2",
        "document_category_score_v2",
        "bio_category_score_v2",
        "sustxn_category_score_v2",
        "work_category_score_v2",
        "hardware_category_score_v2",
    ]
    for col in category_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            logger.error(f"Missing expected column in category_scores: {col}")
            df[col] = pd.NA

    cat_indexed = df.groupby("entity_id", as_index=True).first()

    rows_to_insert = []
    counters = {
        "processed": 0,
        "pushed": 0,
        "skipped_no_match": 0,
        "skipped_no_risk_score": 0,
        "skipped_no_cat_values": 0,
        "skipped_out_of_tolerance": 0,
    }

    TOLERANCE = 0.1
    now_utc = datetime.now(ZoneInfo("UTC"))

    for opt_id, meta in operators.items():
        opt_id_str = str(opt_id).strip()
        risk_score = meta.get("risk_score")

        if risk_score is None:
            counters["skipped_no_risk_score"] += 1
            continue

        if opt_id_str not in cat_indexed.index:
            counters["skipped_no_match"] += 1
            continue

        row = cat_indexed.loc[opt_id_str]

        cat_vals = []
        for col in category_columns:
            v = row.get(col)
            if pd.notna(v):
                try:
                    cat_vals.append(float(v))
                except (TypeError, ValueError):
                    pass

        if not cat_vals:
            counters["skipped_no_cat_values"] += 1
            continue

        max_cat = max(cat_vals)
        counters["processed"] += 1

        if abs(risk_score - max_cat) <= TOLERANCE:
            def _safe(c):
                v = row.get(c)
                try:
                    return float(v) if pd.notna(v) else 0.0
                except (TypeError, ValueError):
                    return 0.0

            ro_name = (meta.get("ro") or "").strip()

            rows_to_insert.append([
                ro_name,
                opt_id_str,
                _safe("document_category_score_v2"),
                _safe("work_category_score_v2"),
                _safe("auth_category_score_v2"),
                _safe("sustxn_category_score_v2"),
                _safe("bio_category_score_v2"),
                _safe("hardware_category_score_v2"),
                now_utc,
            ])
            counters["pushed"] += 1
        else:
            counters["skipped_out_of_tolerance"] += 1
            logger.debug(
                f"opt_id={opt_id_str} risk_score={risk_score} "
                f"max_cat={max_cat} diff={abs(risk_score - max_cat):.4f} "
                f"exceeds tolerance={TOLERANCE}"
            )

    if rows_to_insert:
        try:
            ch_client.insert(
                "operator360.risk_analysis",
                rows_to_insert,
                column_names=[
                    "ro_name",
                    "opt_id",
                    "document_category_score",
                    "work_category_score",
                    "authentication_category_score",
                    "suspicious_category_score",
                    "biometrics_category_score",
                    "hardware_category_score",
                    "updated_at",
                ],
            )
            logger.info(f"Inserted {len(rows_to_insert)} rows into operator360.risk_analysis")
        except Exception:
            logger.exception("ClickHouse insert failed.")
            raise
    else:
        logger.info("No rows qualified for insertion into ClickHouse.")

    logger.info(f"Evaluate summary: {counters}")
    return counters


# --------------------------------------------------------------------------- #
# Airflow 3 task callables
# --------------------------------------------------------------------------- #
def _task_fetch_operators(**context):
    """Pull operator risk metadata from MySQL opt_master."""
    operators = fetch_operators()
    logger.info(f"Fetched {len(operators)} operators from MySQL opt_master.")
    return operators


def _task_fetch_category_scores(**context):
    """Pull the latest category scores per entity from Trino."""
    df = fetch_category_scores()
    if df is None:
        logger.warning("Trino returned no category scores.")
        return None
    logger.info(f"Fetched category scores for {len(df)} entities from Trino.")
    return df


def _task_evaluate_and_push(**context):
    """Join MySQL + Trino data and push qualifying rows to ClickHouse."""
    ti = context["ti"]
    operators = ti.xcom_pull(task_ids="fetch_operators")
    category_scores = ti.xcom_pull(task_ids="fetch_category_scores")

    if not operators:
        logger.warning("No operators fetched; skipping evaluation.")
        return {"processed": 0, "pushed": 0}

    ch_client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=8123,
        database=CH_DATABASE,
        username=CH_USER,
        password=CH_PASSWORD,
    )

    try:
        results = evaluate(operators, category_scores, ch_client)
        logger.info(f"Final evaluation results: {results}")
        return results
    finally:
        try:
            ch_client.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# DAG definition
# --------------------------------------------------------------------------- #
with DAG(
    dag_id="operator_risk_analysis_to_clickhouse",
    description="Evaluate operator risk vs Trino category scores and push to ClickHouse",
    default_args=default_args,
    schedule="0 16 * * *",          # every 6 hours
    catchup=False,
    max_active_runs=1,
    tags=["operator360", "risk", "clickhouse", "trino", "mysql"],
    doc_md=__doc__,
) as dag:

    fetch_operators_task = PythonOperator(
        task_id="fetch_operators",
        python_callable=_task_fetch_operators,
    )

    fetch_category_scores_task = PythonOperator(
        task_id="fetch_category_scores",
        python_callable=_task_fetch_category_scores,
    )

    evaluate_and_push_task = PythonOperator(
        task_id="evaluate_and_push",
        python_callable=_task_evaluate_and_push,
    )

    # fetch_operators and fetch_category_scores run in parallel;
    # both must complete before evaluate_and_push.
    [fetch_operators_task, fetch_category_scores_task] >> evaluate_and_push_task