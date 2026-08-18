"""v2 controller: same Layer 1 -> 2 -> 3 orchestration as operator_dag_manager.py,
plus an hourly retry mechanism for categories that failed the daily promotion
run. See plan: floating-riding-dolphin.md.

Key difference from v1: a category failing at the 8 AM promotion tick no
longer means it's done for the day. Every hourly tick for the rest of that
calendar day (IST), retry_pending_categories re-triggers whatever's still
pending, and if a retry succeeds, cascades into re-triggering Layer 2/3 so
the category still lands in *today's* risk_score - not tomorrow's.

This file is entirely standalone from operator_dag_manager.py: separate
dag_ids throughout (LAYER1_DAG_IDS_V2 etc., all defined locally below), so
v1 keeps running completely unmodified until v2 is validated.
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from trino.dbapi import connect

import boto3
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException
from airflow.models import TaskInstance, DagRun, DagBag
from airflow.utils.session import create_session
from airflow.utils.state import DagRunState
from airflow.api.common.trigger_dag import trigger_dag

from operator360.utils.pipeline_status import (
    read_layer_status,
    compute_category_verdicts,
)

logger = logging.getLogger(__name__)

# ─── S3 bucket for daily reports / pending-retry state ───────────────────────
CEPH_ENDPOINT_URL = "http://10.10.103.12:425"
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-master-events-25"
CEPH_CACHE_PREFIX = "cache/airflow/operator360"

# ─── v2 topology (local to this file - v1's pipeline_status.py constants are
# untouched, so v1 is never affected by anything in here) ────────────────────
DAG_ID_TO_CATEGORY_V2 = {
    "auth_category_features_v2": "auth",
    "bio_packet_fraud_features_v2": "bio",
    "document_features_combined_v2": "document",
    "hardware_category_features_v2": "hardware",
    "sustxn_category_feature_v2": "sustxn",
    "work_category_feature_v2": "work",
}
CATEGORY_TO_DAG_ID_V2 = {v: k for k, v in DAG_ID_TO_CATEGORY_V2.items()}
LAYER1_DAG_IDS_V2 = list(DAG_ID_TO_CATEGORY_V2)
LAYER2_DAG_ID_V2 = "instance_risk_scoring_v2"
LAYER3_DAG_ID_V2 = "combined_risk_scoring_v2"


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY,
    )


def _log_category_diagnostics(layer_name: str, category: str, dag_id: str, entries: list) -> None:
    """Logs exactly which task(s) caused `category` to be marked invalid in
    this layer, with the error, its type, and a direct link to that task
    instance's Airflow log."""

    logger.error("====== %s FAILURE DIAGNOSTICS for category='%s' (dag=%s) ======",
                 layer_name.upper(), category, dag_id)

    if not entries:
        logger.error(
            "REASON: No S3 status records found for this category. "
            "The DAG likely timed out, was OOM-killed, or crashed before it could write its status to S3. "
            "Check the Airflow task instance logs for the child DAG directly."
        )
        return

    bad_entries = [e for e in entries if e.get("status") != "success"]

    if not bad_entries:
        logger.error(
            "REASON: All reported tasks succeeded, but compute_category_verdicts still marked this category as invalid. "
            "This usually means a required feature/task didn't run at all (missing from S3 records)."
        )
        logger.info("Raw S3 entries evaluated: %s", entries)
        return

    for e in bad_entries:
        task_key = e.get("task_key", "UNKNOWN_TASK")
        status = e.get("status", "UNKNOWN_STATUS")
        error_type = e.get("error_type", "N/A")
        error_msg = e.get("error", "No error message provided in S3 record.")
        skip_reason = e.get("skip_reason", "")
        log_url = e.get("log_url", "No log URL provided")
        try_num = e.get("try_number", "N/A")

        logger.error("FAILED TASK -> task='%s' | status='%s' | try=%s", task_key, status, try_num)

        if status == "skipped":
            logger.error("SKIP REASON: %s", skip_reason or error_msg)
        else:
            logger.error("ERROR TYPE: %s", error_type)
            logger.error("ERROR MESSAGE: %s", error_msg)

        logger.error("Airflow Log URL: %s", log_url)
        logger.debug("Full raw entry dictionary: %s", e)


def _safe_get(entry, key, default="N/A"):
    if isinstance(entry, dict):
        return entry.get(key, default)
    return default


def _safe_read_status(run_id, dag_id):
    try:
        entries = read_layer_status(run_id, dag_id)
        if not isinstance(entries, list):
            return [{"error": f"Unexpected return type from read_layer_status: {type(entries)}"}]
        return entries
    except Exception as e:
        logger.warning("Daily Report: Failed to read S3 status for %s: %s", dag_id, e)
        return [{"error": f"Failed to read S3 status: {e}"}]


def _format_entries_report(entries, indent="  "):
    lines = []
    if not entries:
        lines.append(f"{indent}⚠️  NO S3 STATUS RECORDS FOUND")
        lines.append(f"{indent}    The DAG likely crashed, timed out, or was OOM-killed before writing status to S3.")
        lines.append(f"{indent}    ACTION: Check the child DAG's Airflow task instance logs directly.")
        return lines

    bad_entries = [e for e in entries if _safe_get(e, "status") != "success"]
    good_entries = [e for e in entries if _safe_get(e, "status") == "success"]

    if bad_entries:
        lines.append(f"{indent}Failed/Skipped tasks ({len(bad_entries)}):")
        for e in bad_entries:
            task_key = _safe_get(e, "task_key")
            status = _safe_get(e, "status")
            error_type = _safe_get(e, "error_type")
            error_msg = _safe_get(e, "error", "No error message provided")
            skip_reason = _safe_get(e, "skip_reason")
            log_url = _safe_get(e, "log_url")
            try_num = _safe_get(e, "try_number")

            lines.append(f"{indent}  ✗ Task: {task_key}")
            lines.append(f"{indent}    Status: {status}  |  Try: {try_num}")
            if status == "skipped":
                lines.append(f"{indent}    Skip Reason: {skip_reason or error_msg}")
            else:
                lines.append(f"{indent}    Error Type: {error_type}")
                lines.append(f"{indent}    Error: {error_msg}")
            lines.append(f"{indent}    Log URL: {log_url}")
    else:
        lines.append(f"{indent}All reported tasks succeeded.")

    if good_entries:
        lines.append(f"{indent}Successful tasks ({len(good_entries)}):")
        for e in good_entries:
            lines.append(f"{indent}  ✓ {_safe_get(e, 'task_key')}")

    return lines


# ─── risk_score data-presence check (same idea as v1 - S3 status alone can't
# prove Layer 3 actually wrote anything) ──────────────────────────────────────
TRINO_REPORT_HOST = "10.10.116.75"
TRINO_REPORT_PORT = 8080
TRINO_REPORT_USER = "controller_pipeline_v2_report"


def _check_risk_score_data_written(date_str: str) -> dict:
    try:
        conn = connect(host=TRINO_REPORT_HOST, port=TRINO_REPORT_PORT, user=TRINO_REPORT_USER)
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM strot.operator360.features_risk_v1 "
            f"WHERE feature_name = 'risk_score' AND date(timestamp) = date('{date_str}')"
        )
        row_count = cur.fetchone()[0]
        return {"checked": True, "row_count": row_count, "error": None}
    except Exception as e:
        logger.error("risk_score data-presence check failed: %s", e)
        return {"checked": False, "row_count": None, "error": str(e)}


# ─── Daily pending-retry state (new in v2, S3-backed, keyed by calendar date
# rather than pipeline_run_id - this is what makes a failure "carry forward"
# to later hourly ticks instead of only ever being judged once) ──────────────
def _pending_state_key(date_str: str) -> str:
    return f"{CEPH_CACHE_PREFIX}/manager_status_v2/daily_pending/{date_str}.json"


def _read_pending_state(date_str: str) -> dict:
    s3 = _get_s3_client()
    key = _pending_state_key(date_str)
    try:
        resp = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return {"date": date_str, "original_pipeline_run_id": None, "categories": {}, "valid_today": []}
    except Exception as e:
        logger.error("Failed to read pending-retry state for %s: %s", date_str, e)
        return {"date": date_str, "original_pipeline_run_id": None, "categories": {}, "valid_today": []}


def _write_pending_state(date_str: str, state: dict) -> None:
    s3 = _get_s3_client()
    key = _pending_state_key(date_str)
    try:
        s3.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=key,
            Body=json.dumps(state, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error("Failed to write pending-retry state for %s: %s", date_str, e)


# ─── Imperative trigger-and-wait, used by the retry path instead of a static
# TriggerDagRunOperator since which DAGs to (re-)trigger is only known at
# runtime ──────────────────────────────────────────────────────────────────
def _wait_for_dagrun(dag_id: str, run_id: str, timeout_seconds: float, poke_interval: int = 20) -> str:
    deadline = time.time() + timeout_seconds
    with create_session() as session:
        while time.time() < deadline:
            dr = (
                session.query(DagRun)
                .filter(DagRun.dag_id == dag_id, DagRun.run_id == run_id)
                .first()
            )
            if dr is not None and dr.state in ("success", "failed"):
                return dr.state
            time.sleep(poke_interval)
    logger.error("Timed out waiting for %s / %s to finish", dag_id, run_id)
    return "timeout"


def _clear_failed_tasks_and_wait(dag_id: str, run_id: str, timeout_seconds: float) -> str:
    """Retries a Layer-1 category by clearing ONLY the failed task instances
    on its existing DagRun and letting the scheduler re-run just those -
    instead of triggering a whole new DagRun of every feature in the
    category. This is what keeps a retry from re-inserting a duplicate row
    for every feature that already succeeded: those tasks are never touched,
    since none of the feature SQL is delete-first/merge (a plain re-run of
    an already-succeeded INSERT ... SELECT just adds a second copy of the
    row). The pipeline_status_v2.skip_if_already_succeeded() guard on each
    v2 feature function is a second, independent safety net in case this
    ever isn't precise enough (e.g. clearing more than intended)."""
    with create_session() as session:
        dr = session.query(DagRun).filter(DagRun.dag_id == dag_id, DagRun.run_id == run_id).first()
        if dr is None:
            logger.error("Retry (v2): could not find original DagRun for %s/%s to clear", dag_id, run_id)
            return "not_found"
        exec_date = dr.execution_date

    dag_bag = DagBag(read_dags_from_db=True)
    target_dag = dag_bag.get_dag(dag_id)
    if target_dag is None:
        logger.error("Retry (v2): could not load DAG definition for %s from DagBag", dag_id)
        return "dag_not_found"

    # only_failed=True clears exactly the task instances in a 'failed'
    # state for this run and leaves 'success'/'skipped' ones untouched -
    # skipped tasks (e.g. an hourly-cadence feature on a non-relevant tick,
    # or is_daily gating) are deliberately NOT retried here, since
    # compute_category_verdicts() already excludes them from judgement.
    target_dag.clear(
        start_date=exec_date,
        end_date=exec_date,
        only_failed=True,
        dag_run_state=DagRunState.QUEUED,
    )
    logger.info("Retry (v2): cleared failed task instances on %s/%s (execution_date=%s)", dag_id, run_id, exec_date)

    return _wait_for_dagrun(dag_id, run_id, timeout_seconds)


def _cascade_layer2_layer3(pipeline_run_id: str, valid_categories: list, logical_dt) -> dict:
    """Re-triggers Layer 2 then Layer 3 with the current full set of
    categories valid today, so a category that only just cleared a retry
    still makes it into today's risk_score. Returns a small summary dict for
    the retry report.

    NOTE: unlike the Layer-1 retry above, this still triggers brand-new
    Layer 2/3 DagRuns rather than clearing specific tasks - risk_score's
    Layer-3 task depends on all 5 category-score tasks completing within
    the SAME DagRun (make_category_gate() skips a category task outright if
    it isn't in that run's own conf.valid_categories, and skip propagates
    to risk_score's default trigger rule), so a run that only includes the
    newly-recovered category wouldn't let risk_score compute at all. That
    means this cascade re-scores every category in valid_categories, not
    just the new one - and since instances_main.py/category_main.py write
    via .writeTo(table).append() with no dedup, categories that already
    scored successfully earlier today WILL get a duplicate row here. Flagged
    to the user as an open problem; not fixed in this pass since a real fix
    needs either editing those Spark scripts (outside this repo) or
    reworking risk_score's all-5-categories-in-one-run dependency."""
    summary = {"layer2_run_id": None, "layer2_valid": [], "layer3_run_id": None, "layer3_triggered": False}

    l2_run_id = f"retry_l2_{pipeline_run_id}_{int(time.time())}"
    summary["layer2_run_id"] = l2_run_id
    logger.info("Retry cascade: re-triggering %s (run_id=%s) with valid_categories=%s",
                LAYER2_DAG_ID_V2, l2_run_id, valid_categories)
    trigger_dag(
        dag_id=LAYER2_DAG_ID_V2,
        run_id=l2_run_id,
        conf={"pipeline_run_id": pipeline_run_id, "valid_categories": valid_categories},
        logical_date=logical_dt,
        replace_microseconds=False,
    )
    _wait_for_dagrun(LAYER2_DAG_ID_V2, l2_run_id, LAYER_WAIT_TIMEOUT.total_seconds())

    l2_entries = read_layer_status(pipeline_run_id, LAYER2_DAG_ID_V2)
    l2_verdicts = compute_category_verdicts(l2_entries)
    l2_valid = [c for c in valid_categories if l2_verdicts.get(c)]
    summary["layer2_valid"] = l2_valid

    if not l2_valid:
        logger.warning("Retry cascade: no categories passed Layer 2 after retry - not triggering Layer 3")
        return summary

    l3_run_id = f"retry_l3_{pipeline_run_id}_{int(time.time())}"
    summary["layer3_run_id"] = l3_run_id
    summary["layer3_triggered"] = True
    logger.info("Retry cascade: re-triggering %s (run_id=%s) with valid_categories=%s",
                LAYER3_DAG_ID_V2, l3_run_id, l2_valid)
    trigger_dag(
        dag_id=LAYER3_DAG_ID_V2,
        run_id=l3_run_id,
        conf={"pipeline_run_id": pipeline_run_id, "valid_categories": l2_valid},
        logical_date=logical_dt,
        replace_microseconds=False,
    )
    _wait_for_dagrun(LAYER3_DAG_ID_V2, l3_run_id, LAYER_WAIT_TIMEOUT.total_seconds())
    return summary


def _generate_retry_report(date_str: str, state: dict, newly_valid: list, cascade_summary: dict | None) -> None:
    """Small supplementary report uploaded whenever a retry tick changes
    anything, so a same-day recovery is visible without waiting for the next
    full daily report. Separate file from the main daily report - doesn't
    replace it, just supplements it."""
    L = []
    L.append("=" * 90)
    L.append(f"  RETRY UPDATE — controller_pipeline_v2 — {date_str}")
    L.append("=" * 90)
    L.append(f"  Time (IST):            {datetime.now(ZoneInfo('Asia/Kolkata'))}")
    L.append(f"  Newly valid this tick: {newly_valid or 'NONE'}")
    L.append(f"  Valid today (total):   {state.get('valid_today', [])}")
    L.append(f"  Still pending:         {list(state.get('categories', {}).keys()) or 'NONE'}")
    for cat, info in state.get("categories", {}).items():
        L.append(f"    - {cat}: attempts={info.get('attempts')}, last_attempt_at={info.get('last_attempt_at')}")
    if cascade_summary:
        L.append("")
        L.append("  Layer 2/3 cascade triggered by this retry:")
        L.append(f"    Layer 2 run_id:    {cascade_summary.get('layer2_run_id')}")
        L.append(f"    Layer 2 valid:     {cascade_summary.get('layer2_valid')}")
        L.append(f"    Layer 3 triggered: {cascade_summary.get('layer3_triggered')}")
        L.append(f"    Layer 3 run_id:    {cascade_summary.get('layer3_run_id')}")
    L.append("=" * 90)
    report_text = "\n".join(L)
    logger.info("Retry Report:\n%s", report_text)

    ts = int(time.time())
    s3_key = f"reports/controller_pipeline_v2/{date_str.replace('-', '/')}/retry_update_{ts}.txt"
    try:
        s3 = _get_s3_client()
        s3.put_object(Bucket=CEPH_BUCKET_NAME, Key=s3_key, Body=report_text.encode("utf-8"), ContentType="text/plain")
        logger.info("Retry Report uploaded to: s3://%s/%s", CEPH_BUCKET_NAME, s3_key)
    except Exception as e:
        logger.error("Retry Report: failed to upload to S3: %s", e)


def _generate_daily_report(**context):
    """Same structure/purpose as v1's report, pointed at the v2 topology,
    plus a 'today's retry state' section. Fires once/day on the promotion
    tick, same as v1; retry_pending_categories uploads its own supplementary
    reports for anything that happens later in the day."""
    ti = context["ti"]
    run_id = context["run_id"]
    dag_run = context["dag_run"]
    logical_dt = context["data_interval_start"]

    is_daily_run = ti.xcom_pull(task_ids="compute_run_mode", key="is_daily_run")
    if is_daily_run is None:
        ist_hour = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).hour
        if ist_hour == LAYER1_PROMOTION_HOUR:
            is_daily_run = True
        else:
            raise AirflowSkipException("Not a daily promotion run (is_daily_run=None, IST hour != promotion hour)")
    if not is_daily_run:
        raise AirflowSkipException("Not a daily promotion run — no report generated.")

    date_str = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    logger.info("Daily Report (v2): Generating comprehensive report for run_id=%s date=%s", run_id, date_str)

    task_states = {}
    task_timings = {}
    with create_session() as session:
        task_instances = session.query(TaskInstance).filter(
            TaskInstance.dag_id == dag_run.dag_id,
            TaskInstance.run_id == run_id,
        ).all()
        for ti_inst in task_instances:
            tid = ti_inst.task_id
            task_states[tid] = ti_inst.state or "UNKNOWN"
            if ti_inst.start_date and ti_inst.end_date:
                task_timings[tid] = str(ti_inst.end_date - ti_inst.start_date).split(".")[0]
            else:
                task_timings[tid] = "N/A"

    layer1_valid = ti.xcom_pull(task_ids="judge_layer1", key="valid_categories") or []
    layer1_results = ti.xcom_pull(task_ids="judge_layer1", key="layer1_results") or {}
    layer2_valid = ti.xcom_pull(task_ids="judge_layer2", key="valid_categories") or []
    layer2_results = ti.xcom_pull(task_ids="judge_layer2", key="layer2_results") or {}

    all_layer1_status = {d: _safe_read_status(run_id, d) for d in LAYER1_DAG_IDS_V2}
    layer2_status = _safe_read_status(run_id, LAYER2_DAG_ID_V2)
    layer3_status = _safe_read_status(run_id, LAYER3_DAG_ID_V2)
    risk_score_check = _check_risk_score_data_written(date_str)
    pending_state = _read_pending_state(date_str)

    L = []
    L.append("=" * 110)
    L.append("  DAILY PIPELINE REPORT (v2) — controller_pipeline_v2")
    L.append("=" * 110)
    L.append(f"  Run ID:                        {run_id}")
    L.append(f"  Logical Date (Data Interval):  {logical_dt}")
    L.append(f"  IST Date:                      {date_str}")
    L.append("")

    L.append("-" * 110)
    L.append("  LAYER 1 — CATEGORY PROGRESSION (as of the promotion tick)")
    L.append("-" * 110)
    for child_dag_id in LAYER1_DAG_IDS_V2:
        category = DAG_ID_TO_CATEGORY_V2.get(child_dag_id, "UNKNOWN")
        entries = all_layer1_status.get(child_dag_id, [])
        l1_result = layer1_results.get(category, {})
        is_valid = l1_result.get("valid", False) if isinstance(l1_result, dict) else False
        L.append(f"  ┌─ DAG: {child_dag_id}  (category={category})")
        L.append(f"  │  Verdict: {'✓ PASSED' if is_valid else '✗ FAILED (queued for hourly retry)'}")
        L.extend(_format_entries_report(entries, indent="  │  "))
        L.append(f"  └{'─' * 100}")
    L.append("")

    L.append("-" * 110)
    L.append("  TODAY'S RETRY STATE (updates throughout the day, not just at report time)")
    L.append("-" * 110)
    L.append(f"  Valid today so far:  {pending_state.get('valid_today', [])}")
    L.append(f"  Still pending retry: {list(pending_state.get('categories', {}).keys()) or 'NONE'}")
    for cat, info in pending_state.get("categories", {}).items():
        L.append(f"    - {cat}: attempts={info.get('attempts')}, last_attempt_at={info.get('last_attempt_at')}")
    L.append("  (Retries run every hour until midnight IST; check retry_update_*.txt reports for same-day updates.)")
    L.append("")

    L.append("-" * 110)
    L.append("  LAYER 2 / LAYER 3 (promotion tick)")
    L.append("-" * 110)
    L.append(f"  Categories PASSED Layer 2:  {layer2_valid if layer2_valid else 'NONE'}")
    L.append(f"  Layer 2 Verdicts:           {layer2_results}")
    L.append(f"  Layer 3 S3 Status Records:  {len(layer3_status)}")
    L.extend(_format_entries_report(layer3_status, indent="  "))
    L.append("")

    L.append(f"  risk_score data-presence check (features_risk_v1, {date_str}):")
    if not risk_score_check["checked"]:
        L.append(f"    ⚠️  Could not verify - query failed: {risk_score_check['error']}")
    elif risk_score_check["row_count"] > 0:
        L.append(f"    ✓ {risk_score_check['row_count']} risk_score row(s) found for {date_str}.")
    else:
        L.append(f"    ✗ ZERO risk_score rows found for {date_str} as of this report.")
        L.append(f"      (May still be corrected later today by a retry cascade - check retry_update_*.txt.)")
    L.append("")
    L.append("=" * 110)
    L.append("  END OF REPORT")
    L.append("=" * 110)

    report_text = "\n".join(L)
    logger.info("Daily Report (v2):\n%s", report_text)

    date_path = logical_dt.strftime("%Y/%m/%d")
    s3_key = f"reports/controller_pipeline_v2/{date_path}/daily_report_{run_id}.txt"
    try:
        s3 = _get_s3_client()
        s3.put_object(Bucket=CEPH_BUCKET_NAME, Key=s3_key, Body=report_text.encode("utf-8"), ContentType="text/plain")
        report_uri = f"s3://{CEPH_BUCKET_NAME}/{s3_key}"
        logger.info("Daily Report (v2) uploaded to: %s", report_uri)
        ti.xcom_push(key="daily_report_uri", value=report_uri)
        return report_uri
    except Exception as e:
        logger.error("Daily Report (v2): failed to upload to S3: %s", e)
        return None


# ─── DAG definition ─────────────────────────────────────────────────────────

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    # Raised from v1's 40min - the daily-promotion path is explicitly allowed
    # to take up to ~2 hours now, and these lightweight control tasks
    # shouldn't hard-fail on a slow-but-recovering S3/Trino call mid-run.
    "execution_timeout": timedelta(minutes=90),
    "email": ["techexe16.yp25@uidui.net.in"],
    "email_on_failure": True,
    "retries": 0,
}

LAYER1_MAX_PARALLEL = 2
LAYER_WAIT_TIMEOUT = timedelta(minutes=90)
LAYER1_PROMOTION_HOUR = 8


with DAG(
    dag_id="controller_pipeline_v2",
    default_args=default_args,
    description="v2: Layer 1->2->3 orchestrator with hourly retry-until-midnight for Layer 1 "
                "failures, cascading into same-day Layer 2/3 re-runs on a late success.",
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    max_active_tasks=LAYER1_MAX_PARALLEL,
    tags=["controller", "orchestration", "operator360", "v2"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end", trigger_rule="all_done")
    fail_handler = EmptyOperator(task_id="fail_handler", trigger_rule="one_failed")

    pipeline_run_id_tpl = "{{ run_id }}"

    def _compute_run_mode(**context):
        logical_dt = context.get("data_interval_start")
        if logical_dt is None:
            raise RuntimeError(f"data_interval_start not found in context. Available keys: {list(context.keys())}")
        try:
            if hasattr(logical_dt, "in_timezone"):
                ist_hour = logical_dt.in_timezone("Asia/Kolkata").hour
            else:
                ist_hour = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).hour
        except Exception as e:
            raise RuntimeError(f"Timezone conversion failed. dt={logical_dt!r}, type={type(logical_dt)}, error={e}") from e

        is_daily_run = ist_hour == LAYER1_PROMOTION_HOUR
        logger.info("Compute Run Mode (v2): logical_dt=%s, IST_hour=%s, is_daily_run=%s", logical_dt, ist_hour, is_daily_run)
        context["ti"].xcom_push(key="is_daily_run", value=is_daily_run)
        return is_daily_run

    compute_run_mode = PythonOperator(task_id="compute_run_mode", python_callable=_compute_run_mode)

    # ---------------- Layer 1: feature DAGs ----------------
    layer1_triggers = []
    for child_dag_id in LAYER1_DAG_IDS_V2:
        t = TriggerDagRunOperator(
            task_id=f"trigger_layer1_{child_dag_id}",
            trigger_dag_id=child_dag_id,
            conf={
                "pipeline_run_id": pipeline_run_id_tpl,
                "is_daily_run": (
                    "{{ 'true' if ti.xcom_pull(task_ids='compute_run_mode', key='is_daily_run') else 'false' }}"
                ),
            },
            execution_timeout=LAYER_WAIT_TIMEOUT,
            wait_for_completion=True,
            deferrable=False,
            poke_interval=30,
            reset_dag_run=True,
            allowed_states=["success", "failed"],
            failed_states=[],
        )
        layer1_triggers.append(t)
        compute_run_mode >> t
        t >> fail_handler

    def _gate_promotion(**context):
        is_daily_run = context["ti"].xcom_pull(task_ids="compute_run_mode", key="is_daily_run")
        if not is_daily_run:
            raise AirflowSkipException(
                "Not the daily promotion hour - Layer 1 ran for hourly-cadence features only, "
                "skipping judgement and Layer 2/3 this tick"
            )

    gate_promotion = PythonOperator(task_id="gate_promotion", python_callable=_gate_promotion)
    layer1_triggers >> gate_promotion

    def _judge_layer1(**context):
        ti = context["ti"]
        run_id = context["run_id"]
        logical_dt = context["data_interval_start"]
        date_str = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")

        valid_categories = []
        layer1_results = {}
        child_run_ids = {}  # category -> the child DagRun's own run_id (from the trigger task's XCom)

        for child_dag_id in LAYER1_DAG_IDS_V2:
            entries = read_layer_status(run_id, child_dag_id)
            verdicts = compute_category_verdicts(entries)
            category = DAG_ID_TO_CATEGORY_V2[child_dag_id]
            is_valid = bool(verdicts.get(category))
            layer1_results[category] = {"valid": is_valid, "reported_features": len(entries)}

            # TriggerDagRunOperator pushes the run_id of the DagRun it
            # created as its own XCom return value - captured here so a
            # later retry can clear tasks on that *exact* DagRun instead of
            # starting a brand new one.
            try:
                child_run_ids[category] = ti.xcom_pull(task_ids=f"trigger_layer1_{child_dag_id}")
            except Exception:
                child_run_ids[category] = None

            if is_valid:
                valid_categories.append(category)
            else:
                logger.error("Judge Layer 1 (v2): Category '%s' -> FAILED. Analyzing failures...", category)
                _log_category_diagnostics("Layer1", category, child_dag_id, entries)

        ti.xcom_push(key="valid_categories", value=valid_categories)
        ti.xcom_push(key="layer1_results", value=layer1_results)

        # Seed/update today's pending-retry state - this is what lets a
        # failure here get picked up by retry_pending_categories on later
        # hourly ticks instead of just being lost until tomorrow.
        state = _read_pending_state(date_str)
        if state.get("original_pipeline_run_id") is None:
            state["original_pipeline_run_id"] = run_id
        for category in valid_categories:
            state["categories"].pop(category, None)
            if category not in state["valid_today"]:
                state["valid_today"].append(category)
        for category in set(DAG_ID_TO_CATEGORY_V2.values()) - set(state["valid_today"]):
            entry = state["categories"].setdefault(category, {"attempts": 0})
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["last_attempt_at"] = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
            entry["last_pipeline_run_id"] = run_id
            if child_run_ids.get(category):
                entry["child_dag_run_id"] = child_run_ids[category]
            elif "child_dag_run_id" not in entry:
                logger.error(
                    "Judge Layer 1 (v2): no child_dag_run_id captured for category='%s' - "
                    "retry_pending_categories won't be able to target a clear for it.", category
                )
        _write_pending_state(date_str, state)

        logger.info("Layer1 judgement complete (v2) - valid: %s, pending for retry: %s",
                    valid_categories, list(state["categories"].keys()))
        return valid_categories

    judge_layer1 = PythonOperator(task_id="judge_layer1", python_callable=_judge_layer1)
    gate_promotion >> judge_layer1

    def _gate_after_layer1(**context):
        valid_categories = context["ti"].xcom_pull(task_ids="judge_layer1", key="valid_categories") or []
        if not valid_categories:
            raise AirflowSkipException("No categories passed Layer 1 - skipping Layer 2 and Layer 3")

    gate_after_layer1 = PythonOperator(task_id="gate_after_layer1", python_callable=_gate_after_layer1)

    # ---------------- Layer 2: instance scoring ----------------
    trigger_layer2 = TriggerDagRunOperator(
        task_id="trigger_layer2",
        trigger_dag_id=LAYER2_DAG_ID_V2,
        conf={
            "pipeline_run_id": pipeline_run_id_tpl,
            "valid_categories": "{{ ti.xcom_pull(task_ids='judge_layer1', key='valid_categories') | tojson }}",
        },
        execution_timeout=LAYER_WAIT_TIMEOUT,
        wait_for_completion=True,
        deferrable=False,
        poke_interval=30,
        reset_dag_run=True,
        allowed_states=["success", "failed"],
        failed_states=[],
    )
    trigger_layer2 >> fail_handler

    def _judge_layer2(**context):
        ti = context["ti"]
        run_id = context["run_id"]
        layer1_valid = ti.xcom_pull(task_ids="judge_layer1", key="valid_categories") or []

        entries = read_layer_status(run_id, LAYER2_DAG_ID_V2)
        verdicts = compute_category_verdicts(entries)

        entries_by_category = {}
        for e in entries:
            entries_by_category.setdefault(e.get("category"), []).append(e)

        valid_categories = []
        for category in layer1_valid:
            if verdicts.get(category):
                valid_categories.append(category)
            else:
                logger.error("Judge Layer 2 (v2): Category '%s' -> FAILED. Analyzing failures...", category)
                _log_category_diagnostics("Layer2", category, LAYER2_DAG_ID_V2, entries_by_category.get(category, []))

        ti.xcom_push(key="valid_categories", value=valid_categories)
        ti.xcom_push(key="layer2_results", value=verdicts)
        return valid_categories

    judge_layer2 = PythonOperator(task_id="judge_layer2", python_callable=_judge_layer2, trigger_rule="all_done")

    def _gate_after_layer2(**context):
        valid_categories = context["ti"].xcom_pull(task_ids="judge_layer2", key="valid_categories") or []
        if not valid_categories:
            raise AirflowSkipException("No categories passed Layer 2 - skipping Layer 3")

    gate_after_layer2 = PythonOperator(task_id="gate_after_layer2", python_callable=_gate_after_layer2)

    # ---------------- Layer 3: category scoring ----------------
    trigger_layer3 = TriggerDagRunOperator(
        task_id="trigger_layer3",
        trigger_dag_id=LAYER3_DAG_ID_V2,
        conf={
            "pipeline_run_id": pipeline_run_id_tpl,
            "valid_categories": "{{ ti.xcom_pull(task_ids='judge_layer2', key='valid_categories') | tojson }}",
        },
        execution_timeout=LAYER_WAIT_TIMEOUT,
        wait_for_completion=True,
        deferrable=False,
        poke_interval=30,
        reset_dag_run=True,
        allowed_states=["success", "failed"],
        failed_states=[],
    )
    trigger_layer3 >> fail_handler

    # ---------------- Daily Report (promotion tick only) ----------------
    generate_daily_report = PythonOperator(
        task_id="generate_daily_report",
        python_callable=_generate_daily_report,
        trigger_rule="all_done",
    )

    # ---------------- Retry orchestrator (every hourly tick) ----------------
    def _retry_pending_categories(**context):
        logical_dt = context["data_interval_start"]
        date_str = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")

        state = _read_pending_state(date_str)
        pending = state.get("categories", {})
        if not pending:
            logger.info("Retry (v2): nothing pending for %s", date_str)
            return

        original_run_id = state.get("original_pipeline_run_id") or context["run_id"]
        newly_valid = []

        for category in list(pending.keys()):
            child_dag_id = CATEGORY_TO_DAG_ID_V2[category]
            info = pending[category]
            child_dag_run_id = info.get("child_dag_run_id")

            if not child_dag_run_id:
                logger.error(
                    "Retry (v2): no child_dag_run_id recorded for category='%s' (dag=%s) - "
                    "judge_layer1 must not have captured it. Skipping this category this tick; "
                    "it stays pending and will be retried once a run_id is available.",
                    category, child_dag_id,
                )
                continue

            logger.info("Retry (v2): clearing failed tasks on %s/%s (category=%s)",
                        child_dag_id, child_dag_run_id, category)
            # Clears only the failed task instances on the EXISTING DagRun
            # from the original promotion attempt (or a prior retry) and
            # lets the scheduler re-run just those - already-succeeded
            # features in this same category are never touched, so this
            # can't insert a duplicate row for them. See
            # _clear_failed_tasks_and_wait()'s docstring for why.
            _clear_failed_tasks_and_wait(child_dag_id, child_dag_run_id, LAYER_WAIT_TIMEOUT.total_seconds())

            # report_status()'s S3 writes are keyed by (pipeline_run_id,
            # dag_id, feature_id) - since the retry reuses the *original*
            # pipeline_run_id, a retried feature's status simply overwrites
            # its original failed entry, so this reads the up-to-date picture.
            entries = read_layer_status(original_run_id, child_dag_id)
            verdicts = compute_category_verdicts(entries)
            is_valid = bool(verdicts.get(category))

            info["attempts"] = info.get("attempts", 0) + 1
            info["last_attempt_at"] = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()

            if is_valid:
                logger.info("Retry (v2): category '%s' now PASSES.", category)
                newly_valid.append(category)
                pending.pop(category, None)
                if category not in state["valid_today"]:
                    state["valid_today"].append(category)
            else:
                logger.info("Retry (v2): category '%s' still failing, will retry again next hour.", category)
                _log_category_diagnostics("Layer1-retry", category, child_dag_id, entries)

        _write_pending_state(date_str, state)

        cascade_summary = None
        if newly_valid:
            logger.info("Retry (v2): newly valid this tick: %s - cascading into Layer 2/3", newly_valid)
            cascade_summary = _cascade_layer2_layer3(original_run_id, state["valid_today"], logical_dt)

        if newly_valid or cascade_summary:
            _generate_retry_report(date_str, state, newly_valid, cascade_summary)

    retry_pending_categories = PythonOperator(
        task_id="retry_pending_categories",
        python_callable=_retry_pending_categories,
        trigger_rule="all_done",
        execution_timeout=timedelta(hours=2),
    )

    # ---------------- Wiring ----------------
    start >> compute_run_mode
    judge_layer1 >> gate_after_layer1 >> trigger_layer2
    trigger_layer2 >> judge_layer2 >> gate_after_layer2 >> trigger_layer3

    trigger_layer3 >> generate_daily_report
    fail_handler >> generate_daily_report

    # Runs on every hourly tick regardless of promotion-hour outcome
    # (trigger_rule=all_done), independent of whether gate_promotion/
    # judge_layer1/etc. ran, skipped, or failed this tick.
    compute_run_mode >> retry_pending_categories
    generate_daily_report >> retry_pending_categories
    retry_pending_categories >> end
