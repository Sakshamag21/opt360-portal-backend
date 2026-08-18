"""
Shared status-reporting and category-gating helpers for the layered
operator360 pipeline (controller_pipeline -> Layer 1 feature DAGs ->
Layer 2 instance scoring -> Layer 3 category scoring).

Reporting goes through Ceph S3 (not XCom) so the same mechanism works for
both PythonOperator tasks (Layer 1) and KubernetesPodOperator tasks
(Layer 2/3) without needing any change to the external pod scripts
(head_instance_scoring.py / head_combined_risk_scoring.py).
"""
import functools
import json
import logging
import traceback
from datetime import datetime, timezone

import boto3
from airflow.exceptions import AirflowSkipException
from airflow.providers.standard.operators.python import PythonOperator

from operator360.utils.s3_audit_logger import (
    CEPH_ACCESS_KEY,
    CEPH_BUCKET_NAME,
    CEPH_CACHE_PREFIX,
    CEPH_ENDPOINT_URL,
    CEPH_SECRET_KEY,
)

logger = logging.getLogger(__name__)


# ---------------- Layer / category topology ----------------
DAG_ID_TO_CATEGORY = {
    "auth_category_features": "auth",
    "bio_packet_fraud_features": "bio",
    "document_features_combined": "document",
    "hardware_category_features": "hardware",
    "sustxn_category_feature": "sustxn",
    "work_category_feature": "work",
}
LAYER1_DAG_IDS = list(DAG_ID_TO_CATEGORY)
LAYER2_DAG_ID = "instance_risk_scoring"
LAYER3_DAG_ID = "combined_risk_scoring"

# Layer-2/3 FEATURES dict keys are consistently prefixed by category
# (e.g. "sustxn_oddhour_pkts_score", "work_category_score"), except for
# Layer 3's final "risk_score" aggregate, which has no single category.
CATEGORY_PREFIXES = ["sustxn", "auth", "hardware", "work", "bio", "document"]


def infer_category(feature_key: str):
    """Returns the category prefix for a Layer-2/3 FEATURES key, or None if
    none matches (e.g. Layer 3's "risk_score", which isn't category-gated)."""
    for prefix in CATEGORY_PREFIXES:
        if feature_key == prefix or feature_key.startswith(prefix + "_"):
            return prefix
    return None


def parse_bool(value, default: bool = False) -> bool:
    """Normalizes a bool that may have crossed a Jinja template boundary
    (where it always arrives as the string "True"/"False", not a native
    bool - Jinja's render() always returns str unless the DAG opts into
    native-object templating, which this repo doesn't)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


# ---------------- S3 status read/write ----------------
def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY,
    )


def sanitize_run_id(pipeline_run_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(pipeline_run_id))


def status_key(pipeline_run_id: str, dag_id: str, task_key: str) -> str:
    safe_run_id = sanitize_run_id(pipeline_run_id)
    return f"{CEPH_CACHE_PREFIX}/manager_status/{safe_run_id}/{dag_id}/{task_key}.json"


def status_prefix(pipeline_run_id: str, dag_id: str) -> str:
    safe_run_id = sanitize_run_id(pipeline_run_id)
    return f"{CEPH_CACHE_PREFIX}/manager_status/{safe_run_id}/{dag_id}/"


def write_status(
    pipeline_run_id: str,
    dag_id: str,
    task_key: str,
    category: str,
    status: str,
    error: str = None,
    cadence: str = None,
    error_type: str = None,
    traceback_str: str = None,
    log_url: str = None,
    try_number=None,
) -> None:
    key = status_key(pipeline_run_id, dag_id, task_key)
    payload = {
        "task_key": task_key,
        "dag_id": dag_id,
        "category": category,
        "status": status,
        "error": error,
        "error_type": error_type,
        "traceback": traceback_str,
        "cadence": cadence,
        "log_url": log_url,
        "try_number": try_number,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=key,
            Body=json.dumps(payload).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error("Failed to write pipeline status to S3. Key: %s. Error: %s", key, e)


def read_layer_status(pipeline_run_id: str, dag_id: str) -> list:
    """Returns the list of status records written by every task of `dag_id`
    for this pipeline_run_id."""
    prefix = status_prefix(pipeline_run_id, dag_id)
    results = []
    try:
        s3 = _get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=CEPH_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                try:
                    resp = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=obj["Key"])
                    results.append(json.loads(resp["Body"].read().decode("utf-8")))
                except Exception as e:
                    logger.error("Failed to read pipeline status object %s: %s", obj["Key"], e)
    except Exception as e:
        logger.error("Failed to list pipeline status under %s: %s", prefix, e)
    return results


def compute_category_verdicts(entries: list, category_key: str = "category", exclude_cadences=("hourly",)) -> dict:
    """Groups status records by category and decides pass/fail per category.
    A category is valid only if it has at least one relevant entry and every
    relevant entry succeeded. Two kinds of entries are excluded from being
    "relevant" rather than counted as failures:
      - skipped entries (e.g. a weekly feature on a non-Monday run)
      - hourly-cadence entries (they run every manager tick and are not
        part of the once-daily judgement, even on the promotion-hour tick
        where they run alongside the daily-cadence features)."""
    by_category = {}
    for entry in entries:
        by_category.setdefault(entry.get(category_key), []).append(entry)

    verdicts = {}
    for category, cat_entries in by_category.items():
        relevant = [
            e for e in cat_entries
            if e.get("status") != "skipped" and e.get("cadence") not in exclude_cadences
        ]
        verdicts[category] = bool(relevant) and all(e.get("status") == "success" for e in relevant)
    return verdicts


# ---------------- Layer-1 PythonOperator status decorator ----------------
def report_status(dag_id: str, category: str):
    """Decorator for Layer-1 feature callables. Reports success/failed/skipped
    to S3 under manager_status/{pipeline_run_id}/{dag_id}/{feature_id}.json,
    including the full traceback and a direct link to this task instance's
    Airflow log so a failure can be diagnosed from the status record alone,
    without having to go hunt through 6 different child DAGs' task logs.

    Requires the wrapped callable to receive `feature_id` and
    `pipeline_run_id` via kwargs (already the case for every Layer-1
    run_single_features op_kwargs); `log_url` and `try_number` are optional.
    Re-raises unchanged so existing Airflow task state / alerting behavior
    (retries, email_on_failure, ...) is untouched."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            feature_id = kwargs.get("feature_id") or kwargs.get("feature_name", "unknown_feature")
            pipeline_run_id = kwargs.get("pipeline_run_id")
            log_url = kwargs.get("log_url")
            try_number = kwargs.get("try_number")
            # Cadence comes from whichever config style this DAG uses -
            # "frequency" (sustxn/work: daily/weekly/hourly) or "is_daily"
            # (auth/bio/document/hardware - always daily-cadence there).
            cadence = kwargs.get("frequency") or ("daily" if kwargs.get("is_daily", True) else "always")
            status = "unknown"
            error_reason = None
            error_type = None
            traceback_str = None
            try:
                result = func(*args, **kwargs)
                status = "success"
                return result
            except AirflowSkipException:
                status = "skipped"
                raise
            except Exception as e:
                status = "failed"
                error_reason = str(e)[:2000]
                error_type = type(e).__name__
                traceback_str = traceback.format_exc()[-4000:]
                raise
            finally:
                if pipeline_run_id:
                    write_status(
                        pipeline_run_id=pipeline_run_id,
                        dag_id=dag_id,
                        task_key=feature_id,
                        category=category,
                        status=status,
                        error=error_reason,
                        cadence=cadence,
                        error_type=error_type,
                        traceback_str=traceback_str,
                        log_url=log_url,
                        try_number=try_number,
                    )
                else:
                    logger.warning(
                        "report_status: missing pipeline_run_id for %s/%s, skipping S3 status write",
                        dag_id, feature_id,
                    )

        return wrapper

    return decorator


# ---------------- Layer-2/3 KubernetesPodOperator status wrapper ----------------
def wrap_shell_with_status_report(inner_cmd: str, dag_id: str, task_key: str, category: str) -> str:
    """Wraps a shell command so its exit code is captured and a status JSON
    is written to Ceph S3 afterward, regardless of whether inner_cmd
    succeeds or fails. No changes to the external pod scripts required.

    On failure the status record includes a direct link to this task
    instance's Airflow log (where the pod's own stdout/stderr already lands,
    since get_logs=True) - no need to duplicate pod output into S3.

    Expects PIPELINE_RUN_ID and TASK_LOG_URL env vars on the pod - wire them via
    KubernetesPodOperator(env_vars={
        "PIPELINE_RUN_ID": "{{ dag_run.conf.get('pipeline_run_id') or run_id }}",
        "TASK_LOG_URL": "{{ ti.log_url }}",
    }).
    """
    status_snippet = (
        "import boto3,json,os;"
        "run_id=os.environ.get('PIPELINE_RUN_ID','unknown_run');"
        "safe_run_id=''.join(c if c.isalnum() or c in '-_' else '_' for c in run_id);"
        "status='success' if os.environ.get('TASK_EXIT_CODE')=='0' else 'failed';"
        "log_url=os.environ.get('TASK_LOG_URL');"
        f"key='{CEPH_CACHE_PREFIX}/manager_status/'+safe_run_id+'/{dag_id}/{task_key}.json';"
        f"payload={{'task_key':'{task_key}','dag_id':'{dag_id}','category':'{category}','status':status,'error':None,'log_url':log_url}};"
        f"s3=boto3.client('s3',endpoint_url='{CEPH_ENDPOINT_URL}',aws_access_key_id='{CEPH_ACCESS_KEY}',aws_secret_access_key='{CEPH_SECRET_KEY}');"
        f"s3.put_object(Bucket='{CEPH_BUCKET_NAME}',Key=key,Body=json.dumps(payload).encode('utf-8'),ContentType='application/json')"
    )
    return (
        f"{inner_cmd}; "
        f"EXIT_CODE=$?; "
        f'TASK_EXIT_CODE=$EXIT_CODE python3 -c "{status_snippet}"; '
        f"exit $EXIT_CODE"
    )


# ---------------- Layer-2/3 category gate ----------------
def make_category_gate(task_id: str, category: str, valid_categories_conf_key: str = "valid_categories") -> PythonOperator:
    """A lightweight upstream gate for every task belonging to `category`.
    Skips (AirflowSkipException) if the triggering conf names a
    valid_categories list and `category` isn't in it. If the DAG is run
    standalone (no such conf key at all - e.g. manual test trigger),
    everything is treated as valid."""

    def _gate(**context):
        dag_run = context.get("dag_run")
        conf = (dag_run.conf or {}) if dag_run else {}
        valid_categories = conf.get(valid_categories_conf_key)
        if isinstance(valid_categories, str):
            try:
                valid_categories = json.loads(valid_categories)
            except (TypeError, ValueError):
                logger.warning(
                    "make_category_gate: could not parse valid_categories JSON string: %r", valid_categories
                )
                valid_categories = None
        if valid_categories is not None and category not in valid_categories:
            raise AirflowSkipException(
                f"category '{category}' not in valid_categories from upstream layer: {valid_categories}"
            )

    return PythonOperator(task_id=task_id, python_callable=_gate)
