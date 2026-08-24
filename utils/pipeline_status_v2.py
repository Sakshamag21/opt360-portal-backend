"""v2-only idempotency guard.

Every feature SQL file in this repo is a plain `INSERT INTO ... SELECT`
with no delete-first or merge, and Layer 2/3's Spark jobs write via
`.writeTo(table).append()` - also no dedup. Re-running anything that
already succeeded today inserts a second, duplicate row rather than
overwriting. The v2 retry mechanism's primary path for Layer 1
(operator_dag_manager_v2.py clearing only the specific failed task
instances) avoids that by construction; this module is what makes the same
"a task succeeds at most once a day" guarantee hold for Layer 2/3 as well,
where a same-day cascade has to re-trigger a brand-new DagRun that
necessarily includes categories that already scored (see
_cascade_layer2_layer3()'s docstring for why that's unavoidable there) -
and it's also a second, independent line of defense for Layer 1 itself, in
case a task is ever re-invoked some other way (a manual re-run, Airflow's
own per-task retries, a future bug).

Kept in its own file, separate from utils/pipeline_status.py, so v1 (and
every v1 DAG that imports pipeline_status.py) is completely unaffected.
"""
import functools
import json
import logging

import boto3
from botocore.exceptions import ClientError
from airflow.exceptions import AirflowSkipException
from airflow.providers.standard.operators.python import PythonOperator

from operator360.utils.pipeline_status import status_key
from operator360.utils.s3_audit_logger import (
    CEPH_ACCESS_KEY,
    CEPH_BUCKET_NAME,
    CEPH_ENDPOINT_URL,
    CEPH_SECRET_KEY,
)

logger = logging.getLogger(__name__)


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY,
    )


def already_succeeded(pipeline_run_id: str, dag_id: str, task_key: str) -> bool:
    """True if this exact task already reported success for this
    pipeline_run_id - i.e. this invocation is a re-run of work that already
    landed, and doing it again would just duplicate a row."""
    if not pipeline_run_id:
        return False
    key = status_key(pipeline_run_id, dag_id, task_key)
    try:
        s3 = _get_s3_client()
        resp = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=key)
        record = json.loads(resp["Body"].read().decode("utf-8"))
        return record.get("status") == "success"
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return False
        logger.warning("already_succeeded: S3 error checking %s: %s", key, e)
        return False
    except Exception as e:
        logger.warning("already_succeeded: failed checking %s: %s", key, e)
        return False


def skip_if_already_succeeded(dag_id: str):
    """Decorator for Layer-1 run_single_features-style callables. Raises
    AirflowSkipException immediately if this feature_id already has a
    success record for this pipeline_run_id, instead of re-running (and
    re-inserting) it. Apply as the OUTERMOST decorator so the check happens
    before audit_to_s3/report_status do any work either:

        @skip_if_already_succeeded(dag_id=job_name)
        @audit_to_s3(dag_id=job_name)
        @report_status(dag_id=job_name, category=category)
        def run_single_features(...): ...

    Relies on the same kwargs contract report_status() already depends on
    (feature_id/feature_name and pipeline_run_id passed via op_kwargs)."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            feature_id = kwargs.get("feature_id") or kwargs.get("feature_name", "unknown_feature")
            pipeline_run_id = kwargs.get("pipeline_run_id")
            if already_succeeded(pipeline_run_id, dag_id, feature_id):
                logger.info(
                    "%s/%s already succeeded for pipeline_run_id=%s - skipping to avoid a duplicate insert.",
                    dag_id, feature_id, pipeline_run_id,
                )
                raise AirflowSkipException(
                    f"{feature_id} already succeeded earlier today (pipeline_run_id={pipeline_run_id}) "
                    "- skipping to avoid inserting a duplicate row."
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def make_idempotency_gate(task_id: str, dag_id: str, task_key: str,
                           run_id_conf_key: str = "pipeline_run_id") -> PythonOperator:
    """Layer 2/3 equivalent of skip_if_already_succeeded(), as an upstream
    gate instead of a decorator - Layer 2/3 tasks are KubernetesPodOperators
    running a Spark job fetched from S3 at runtime, not a Python callable in
    this repo, so there's nothing to decorate. Wire this immediately before
    each KubernetesPodOperator task:

        gate = make_idempotency_gate(f"gate_dup_{task_id}", dag_id=job_name, task_key=task_id)
        gate >> task

    task_key must match exactly what wrap_shell_with_status_report() uses
    to report status for that task (its Airflow task_id, for how Layer 2/3
    are wired today) so this checks the same S3 object that task writes to.
    """

    def _gate(**context):
        dag_run = context.get("dag_run")
        conf = (dag_run.conf or {}) if dag_run else {}
        pipeline_run_id = conf.get(run_id_conf_key) or context.get("run_id")
        if already_succeeded(pipeline_run_id, dag_id, task_key):
            logger.info(
                "%s/%s already succeeded for pipeline_run_id=%s - skipping to avoid a duplicate row.",
                dag_id, task_key, pipeline_run_id,
            )
            raise AirflowSkipException(
                f"{task_key} already succeeded earlier today (pipeline_run_id={pipeline_run_id}) "
                "- skipping to avoid inserting a duplicate score row."
            )

    return PythonOperator(task_id=task_id, python_callable=_gate)