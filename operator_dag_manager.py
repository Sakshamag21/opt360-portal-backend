from __future__ import annotations
import logging
import os
import boto3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from trino.dbapi import connect

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException
from airflow.models import TaskInstance
from airflow.utils.session import create_session

from operator360.utils.pipeline_status import (
    LAYER1_DAG_IDS,
    LAYER2_DAG_ID,
    LAYER3_DAG_ID,
    DAG_ID_TO_CATEGORY,
    read_layer_status,
    compute_category_verdicts,
)

logger = logging.getLogger(__name__)

# ─── S3 bucket for daily reports ─────────────────────────────────────────────
CEPH_ENDPOINT_URL = "http://10.10.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-master-events-25"
CEPH_CACHE_PREFIX = "cache/airflow/operator360" 


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


# ─── Daily report generator ──────────────────────────────────────────────────

TRINO_REPORT_HOST = "10.10.116.75"
TRINO_REPORT_PORT = 8080
TRINO_REPORT_USER = "controller_pipeline_report"


def _check_risk_score_data_written(logical_dt) -> dict:
    """Independent check that Layer 3 actually wrote risk_score rows today.

    S3 task status alone can't prove this: combined_risk_scoring's pods report
    status purely from their shell exit code, and category_main.py can exit 0
    without writing anything at all (e.g. its registry lookup matching zero
    rows) - so 'every Layer 3 task succeeded' does not imply 'risk_score was
    computed'. This queries the actual destination table instead of trusting
    process exit codes.
    """
    date_str = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
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
        logger.error("Daily Report: risk_score data-presence check failed: %s", e)
        return {"checked": False, "row_count": None, "error": str(e)}


def _safe_get(entry, key, default="N/A"):
    """Safely get a value from an entry that might not be a dict."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return default


def _safe_read_status(run_id, dag_id):
    """Read S3 status, always returning a list."""
    try:
        entries = read_layer_status(run_id, dag_id)
        if not isinstance(entries, list):
            return [{"error": f"Unexpected return type from read_layer_status: {type(entries)}"}]
        return entries
    except Exception as e:
        logger.warning("Daily Report: Failed to read S3 status for %s: %s", dag_id, e)
        return [{"error": f"Failed to read S3 status: {e}"}]


def _format_entries_report(entries, indent="  "):
    """Format a list of S3 status entries into report lines."""
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


def _generate_daily_report(**context):
    """Generates a comprehensive daily pipeline report and uploads to S3.

    Captures the full state of the pipeline at the end of a daily run:
    - Task instance states and durations
    - Per-category verdicts at each layer (Layer 1 → 2 → 3)
    - Detailed failure diagnostics (error messages, log URLs)
    - Gate decisions and why they passed/skipped
    - Category progression matrix
    - Overall pipeline verdict with recommended actions
    """
    ti = context["ti"]
    run_id = context["run_id"]
    dag_run = context["dag_run"]
    logical_dt = context["data_interval_start"]

    # ── 1. Determine if this is a daily run ──────────────────────────────
    is_daily_run = ti.xcom_pull(task_ids="compute_run_mode", key="is_daily_run")

    if is_daily_run is None:
        # compute_run_mode may have failed — check IST hour directly
        ist_hour = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).hour
        if ist_hour == LAYER1_PROMOTION_HOUR:
            logger.warning(
                "Daily Report: compute_run_mode XCom is None, but IST hour=%d matches "
                "promotion hour. Generating failure report.", ist_hour)
            is_daily_run = True
        else:
            raise AirflowSkipException(
                "Not a daily promotion run (is_daily_run=None, IST hour != promotion hour)")

    if not is_daily_run:
        raise AirflowSkipException("Not a daily promotion run — no report generated.")

    logger.info("Daily Report: Generating comprehensive report for run_id=%s", run_id)

    # ── 2. Collect task instance states & timings ────────────────────────
    task_states = {}
    task_timings = {}
    task_log_urls = {}
    with create_session() as session:
        task_instances=session.query(TaskInstance).filter(
            TaskInstance.dag_id == dag_run.dag_id,
            TaskInstance.run_id==run_id    
        ).all()
        for ti_inst in task_instances:
            tid = ti_inst.task_id
            task_states[tid] = ti_inst.state or "UNKNOWN"
            if ti_inst.start_date and ti_inst.end_date:
                dur = ti_inst.end_date - ti_inst.start_date
                task_timings[tid] = str(dur).split(".")[0]  # strip microseconds
            else:
                task_timings[tid] = "N/A"
            try:
                task_log_urls[tid] = ti_inst.log_url
            except Exception:
                task_log_urls[tid] = "N/A"

    # ── 3. Pull XCom data from judge tasks ───────────────────────────────
    layer1_valid = ti.xcom_pull(task_ids="judge_layer1", key="valid_categories") or []
    layer1_results = ti.xcom_pull(task_ids="judge_layer1", key="layer1_results") or {}
    layer2_valid = ti.xcom_pull(task_ids="judge_layer2", key="valid_categories") or []
    layer2_results = ti.xcom_pull(task_ids="judge_layer2", key="layer2_results") or {}

    # ── 4. Re-read S3 status for all layers ──────────────────────────────
    all_layer1_status = {}
    for child_dag_id in LAYER1_DAG_IDS:
        all_layer1_status[child_dag_id] = _safe_read_status(run_id, child_dag_id)

    layer2_status = _safe_read_status(run_id, LAYER2_DAG_ID)
    layer3_status = _safe_read_status(run_id, LAYER3_DAG_ID)

    # ── 4b. Verify Layer 3 actually wrote data (S3 status can't tell us this) ──
    risk_score_check = _check_risk_score_data_written(logical_dt)

    # ── 5. Build the report ──────────────────────────────────────────────
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    L = []  # report lines

    # ── Header ──
    L.append("=" * 110)
    L.append("  DAILY PIPELINE REPORT — controller_pipeline")
    L.append("=" * 110)
    L.append("")
    L.append(f"  Run ID:                        {run_id}")
    L.append(f"  DAG Run State:                 {dag_run.state}")
    L.append(f"  Run Type:                      {getattr(dag_run, 'run_type', 'N/A')}")
    L.append(f"  External Trigger:              {getattr(dag_run, 'external_trigger', 'N/A')}")
    L.append(f"  Logical Date (Data Interval):  {logical_dt}")
    L.append(f"  IST Logical Date:              {logical_dt.astimezone(ZoneInfo('Asia/Kolkata'))}")
    L.append(f"  Report Generated At (IST):     {ist_now}")
    L.append(f"  Is Daily Run:                  {is_daily_run}")
    L.append(f"  Promotion Hour (IST):          {LAYER1_PROMOTION_HOUR}:00")
    L.append(f"  DAG Run Conf:                  {dag_run.conf}")
    L.append("")

    # ── Task Instance States ──
    L.append("-" * 110)
    L.append("  TASK INSTANCE STATES")
    L.append("-" * 110)

    layer1_task_ids = [f"trigger_layer1_{d}" for d in LAYER1_DAG_IDS]
    control_task_ids = [
        "start", "compute_run_mode", "gate_promotion", "judge_layer1",
        "gate_after_layer1", "trigger_layer2", "judge_layer2",
        "gate_after_layer2", "trigger_layer3", "fail_handler",
        "generate_daily_report", "end",
    ]

    L.append("\n  [Layer 1 Trigger Tasks]")
    for tid in layer1_task_ids:
        state = task_states.get(tid, "NOT_RUN")
        dur = task_timings.get(tid, "N/A")
        L.append(f"    {tid:55s}  State: {state:20s}  Duration: {dur}")

    L.append("\n  [Control & Judgement Tasks]")
    for tid in control_task_ids:
        state = task_states.get(tid, "NOT_RUN")
        dur = task_timings.get(tid, "N/A")
        L.append(f"    {tid:55s}  State: {state:20s}  Duration: {dur}")
    L.append("")

    # ── Layer 1 Details ──
    L.append("-" * 110)
    L.append("  LAYER 1: FEATURE EXTRACTION")
    L.append("-" * 110)
    L.append(f"  Total Layer 1 DAGs configured:  {len(LAYER1_DAG_IDS)}")
    L.append(f"  Categories that PASSED Layer 1: {layer1_valid if layer1_valid else 'NONE'}")
    L.append(f"  Layer 1 Results Summary:        {layer1_results}")
    L.append("")

    for child_dag_id in LAYER1_DAG_IDS:
        category = DAG_ID_TO_CATEGORY.get(child_dag_id, "UNKNOWN")
        entries = all_layer1_status.get(child_dag_id, [])
        trigger_state = task_states.get(f"trigger_layer1_{child_dag_id}", "NOT_RUN")
        l1_result = layer1_results.get(category, {})
        is_valid = l1_result.get("valid", False) if isinstance(l1_result, dict) else False

        # Try to get child DAG run ID from trigger task XCom
        child_run_id = None
        try:
            child_run_id = ti.xcom_pull(task_ids=f"trigger_layer1_{child_dag_id}")
        except Exception:
            pass

        L.append(f"  ┌─ DAG: {child_dag_id}")
        L.append(f"  │  Category:              {category}")
        L.append(f"  │  Trigger Task State:    {trigger_state}")
        if child_run_id:
            L.append(f"  │  Child DAG Run ID:      {child_run_id}")
        L.append(f"  │  Category Verdict:      {'✓ PASSED' if is_valid else '✗ FAILED'}")
        L.append(f"  │  S3 Status Records:     {len(entries)}")
        L.extend(_format_entries_report(entries, indent="  │  "))
        L.append(f"  └{'─' * 100}")
        L.append("")

    # ── Gate After Layer 1 ──
    L.append("-" * 110)
    L.append("  GATE: AFTER LAYER 1 (gate_after_layer1)")
    L.append("-" * 110)
    gate_l1_state = task_states.get("gate_after_layer1", "NOT_RUN")
    L.append(f"  Gate State: {gate_l1_state}")
    if gate_l1_state == "skipped":
        L.append(f"  REASON: No categories passed Layer 1 validation.")
        L.append(f"  IMPACT: Layer 2 (instance scoring) and Layer 3 (category scoring) were SKIPPED.")
        L.append(f"  ACTION: Review Layer 1 failures above. Fix feature extraction issues before re-running.")
    elif gate_l1_state == "success":
        L.append(f"  RESULT: {len(layer1_valid)} category(ies) promoted to Layer 2: {layer1_valid}")
    elif gate_l1_state in ("upstream_failed", "NOT_RUN"):
        L.append(f"  REASON: Upstream task(s) failed or did not run. judge_layer1 may have encountered an error.")
        L.append(f"  ACTION: Check judge_layer1 task logs for exceptions.")
    L.append("")

    # ── Layer 2 Details ──
    L.append("-" * 110)
    L.append("  LAYER 2: INSTANCE SCORING")
    L.append("-" * 110)
    l2_trigger_state = task_states.get("trigger_layer2", "NOT_RUN")
    l2_judge_state = task_states.get("judge_layer2", "NOT_RUN")
    L.append(f"  Trigger Layer 2 State:      {l2_trigger_state}")
    L.append(f"  Judge Layer 2 State:        {l2_judge_state}")
    L.append(f"  Categories from Layer 1:    {layer1_valid}")
    L.append(f"  Categories PASSED Layer 2:  {layer2_valid if layer2_valid else 'NONE'}")
    L.append(f"  Layer 2 Verdicts:           {layer2_results}")
    L.append(f"  S3 Status Records:          {len(layer2_status)}")
    L.append("")

    if layer2_status:
        l2_by_cat = {}
        for e in layer2_status:
            cat = _safe_get(e, "category", "UNKNOWN")
            l2_by_cat.setdefault(cat, []).append(e)

        for cat in sorted(l2_by_cat.keys()):
            cat_entries = l2_by_cat[cat]
            L.append(f"  Category: {cat}")
            L.extend(_format_entries_report(cat_entries, indent="    "))
            L.append("")
    else:
        L.append(f"  ⚠️  No S3 status records found for Layer 2.")
        if l2_trigger_state in ("skipped", "upstream_failed", "NOT_RUN"):
            L.append(f"      Layer 2 was not triggered or did not complete.")
        L.append("")

    # ── Gate After Layer 2 ──
    L.append("-" * 110)
    L.append("  GATE: AFTER LAYER 2 (gate_after_layer2)")
    L.append("-" * 110)
    gate_l2_state = task_states.get("gate_after_layer2", "NOT_RUN")
    L.append(f"  Gate State: {gate_l2_state}")
    if gate_l2_state == "skipped":
        L.append(f"  REASON: No categories passed Layer 2 instance scoring validation.")
        L.append(f"  IMPACT: Layer 3 (category scoring) was SKIPPED.")
        L.append(f"  ACTION: Review Layer 2 failures above. Check instance scoring tasks.")
    elif gate_l2_state == "success":
        L.append(f"  RESULT: {len(layer2_valid)} category(ies) promoted to Layer 3: {layer2_valid}")
    elif gate_l2_state in ("upstream_failed", "NOT_RUN"):
        L.append(f"  REASON: Upstream task(s) failed or did not run. judge_layer2 may have encountered an error.")
        L.append(f"  ACTION: Check judge_layer2 task logs for exceptions.")
    L.append("")

    # ── Layer 3 Details ──
    L.append("-" * 110)
    L.append("  LAYER 3: CATEGORY SCORING")
    L.append("-" * 110)
    l3_trigger_state = task_states.get("trigger_layer3", "NOT_RUN")
    L.append(f"  Trigger Layer 3 State:      {l3_trigger_state}")
    L.append(f"  Categories from Layer 2:    {layer2_valid}")
    L.append(f"  S3 Status Records:          {len(layer3_status)}")
    L.append("")

    if layer3_status:
        L.extend(_format_entries_report(layer3_status, indent="  "))
    else:
        if l3_trigger_state in ("skipped", "upstream_failed", "NOT_RUN"):
            L.append(f"  ⚠️  Layer 3 was not triggered or did not complete.")
        else:
            L.append(f"  ⚠️  No S3 status records found for Layer 3 despite trigger task state: {l3_trigger_state}")
            L.append(f"      Layer 3 DAG may have crashed before writing status to S3.")
    L.append("")

    L.append(f"  risk_score data-presence check (features_risk_v1, today):")
    if not risk_score_check["checked"]:
        L.append(f"    ⚠️  Could not verify - query failed: {risk_score_check['error']}")
    elif risk_score_check["row_count"] > 0:
        L.append(f"    ✓ {risk_score_check['row_count']} risk_score row(s) found for today.")
    else:
        L.append(f"    ✗ ZERO risk_score rows found for today, despite S3 task status above.")
        L.append(f"      Every Layer 3 pod can exit 0 without writing anything - see category_main.py.")
    L.append("")

    # ── Category Progression Matrix ──
    L.append("-" * 110)
    L.append("  CATEGORY PROGRESSION MATRIX")
    L.append("-" * 110)
    all_categories = sorted(set(DAG_ID_TO_CATEGORY.values()))
    L.append(f"  {'Category':<35s} {'Layer 1':<15s} {'Layer 2':<15s} {'Layer 3':<15s}")
    L.append(f"  {'-'*35} {'-'*15} {'-'*15} {'-'*15}")
    for cat in all_categories:
        l1_pass = cat in layer1_valid
        l2_pass = cat in layer2_valid
        l3_pass = (layer3_status and any(
            _safe_get(e, "status") == "success" and _safe_get(e, "category") == cat
            for e in layer3_status
        ))

        l1_str = "✓ PASSED" if l1_pass else "✗ FAILED"
        if l1_pass:
            l2_str = "✓ PASSED" if l2_pass else "✗ FAILED"
        else:
            l2_str = "— (blocked)"
        if l2_pass:
            l3_str = "✓ PASSED" if l3_pass else "✗ FAILED"
        else:
            l3_str = "— (blocked)"

        L.append(f"  {cat:<35s} {l1_str:<15s} {l2_str:<15s} {l3_str:<15s}")
    L.append("")

    # ── Overall Pipeline Verdict ──
    L.append("=" * 110)
    L.append("  OVERALL PIPELINE VERDICT")
    L.append("=" * 110)

    pipeline_status = "UNKNOWN"
    stopped_at = "UNKNOWN"
    impact = ""
    action = ""

    if task_states.get("compute_run_mode") not in ("success",):
        pipeline_status = "✗ FAILED AT COMPUTE_RUN_MODE"
        stopped_at = "compute_run_mode"
        impact = "Could not determine if this is a daily run. No layers executed."
        action = "Check compute_run_mode task logs. Verify data_interval_start and IST timezone conversion."
    elif task_states.get("gate_promotion") == "skipped":
        pipeline_status = "✗ SKIPPED (NOT A DAILY RUN)"
        stopped_at = "gate_promotion"
        impact = "This was an hourly run, not a daily promotion run. Layer 1 ran for hourly features only."
        action = "No action needed. Daily report should not have been generated (this is unexpected)."
    elif not layer1_valid:
        pipeline_status = "✗ FAILED AT LAYER 1"
        stopped_at = "Layer 1 — Feature Extraction"
        failed_cats = [c for c in all_categories if c not in layer1_valid]
        impact = (f"No categories passed Layer 1. {len(failed_cats)} category(ies) failed: {failed_cats}. "
                  f"Instance scoring and category scoring did NOT run.")
        action = ("Review Layer 1 failure details above. Check which features/tasks failed or didn't run. "
                  "Check child DAG logs. Common causes: task failures, missing required features, "
                  "DAG timeouts, OOM kills.")
    elif not layer2_valid:
        pipeline_status = "✗ FAILED AT LAYER 2"
        stopped_at = "Layer 2 — Instance Scoring"
        impact = (f"No categories passed Layer 2 instance scoring. Category scoring (Layer 3) did NOT run.")
        action = ("Review Layer 2 failure details above. Check instance scoring tasks for errors. "
                  "Common causes: scoring task failures, data quality issues, missing dependencies.")
    elif l3_trigger_state == "success" and layer3_status:
        bad_l3 = [e for e in layer3_status if _safe_get(e, "status") != "success"]
        if bad_l3:
            pipeline_status = "⚠ PARTIAL FAILURE AT LAYER 3"
            stopped_at = "Layer 3 — Category Scoring (some tasks failed)"
            impact = (f"Layer 3 ran but {len(bad_l3)} task(s) failed. "
                      f"Categories that reached Layer 3: {layer2_valid}")
            action = "Review Layer 3 failure details above. Some category scores may be incomplete."
        elif risk_score_check["checked"] and risk_score_check["row_count"] == 0:
            # Every Layer 3 pod reported "success" purely from its shell exit
            # code - that does not mean it wrote anything. Confirmed here
            # against the actual destination table instead of trusting exit
            # codes, so this can't be papered over by the branch below.
            pipeline_status = "✗ LAYER 3 SUCCEEDED BUT WROTE NO risk_score ROWS"
            stopped_at = "Layer 3 — Category Scoring (silent no-op)"
            impact = ("All Layer 3 tasks reported success, but strot.operator360.features_risk_v1 has "
                      "zero risk_score rows for today. category_main.py exits 0 even when its registry "
                      "lookup matches nothing, so a clean-looking S3 status here does not mean risk_score "
                      "was actually computed.")
            action = ("Check category_main.py: it hardcodes feature_name='document_category_score', "
                      "feature_version=1 instead of using the feature_name/feature_version passed in via "
                      "sys.argv, so every category task (and risk_score itself) scores the wrong - and "
                      "non-existent - registry row. Fix that hardcoding, then re-run.")
        else:
            pipeline_status = "✓ COMPLETED SUCCESSFULLY"
            stopped_at = "N/A — Pipeline completed all layers"
            impact = f"All layers executed successfully. Categories scored: {layer2_valid}"
            if not risk_score_check["checked"]:
                impact += " (Note: risk_score data-presence check could not run - see Layer 3 section above.)"
            action = "No action needed. Pipeline completed successfully."
    elif l3_trigger_state == "failed":
        pipeline_status = "✗ FAILED AT LAYER 3"
        stopped_at = "Layer 3 — Category Scoring"
        impact = "Layer 3 DAG failed to trigger or complete."
        action = "Check trigger_layer3 task logs. Check Layer 3 child DAG logs."
    elif l3_trigger_state in ("skipped", "upstream_failed", "NOT_RUN"):
        pipeline_status = "✗ STOPPED BEFORE LAYER 3"
        stopped_at = "Gate After Layer 2 or earlier"
        impact = "Pipeline did not reach Layer 3."
        action = "Review gate_after_layer2 state and Layer 2 results above."
    else:
        pipeline_status = f"? UNKNOWN (trigger_layer3 state: {l3_trigger_state})"
        stopped_at = "Unknown"
        impact = "Could not determine pipeline status."
        action = "Check all task states above and Airflow UI for more details."

    L.append(f"  Status:      {pipeline_status}")
    L.append(f"  Stopped At:  {stopped_at}")
    L.append(f"  Impact:      {impact}")
    L.append(f"  Action:      {action}")
    L.append("")

    # ── Failure Summary (quick reference) ──
    L.append("-" * 110)
    L.append("  FAILURE SUMMARY (Quick Reference)")
    L.append("-" * 110)
    total_failures = 0
    for child_dag_id in LAYER1_DAG_IDS:
        entries = all_layer1_status.get(child_dag_id, [])
        bad = [e for e in entries if _safe_get(e, "status") != "success"]
        if bad:
            total_failures += len(bad)
            L.append(f"  Layer 1 / {child_dag_id}:")
            for e in bad:
                L.append(f"    ✗ {_safe_get(e, 'task_key')}: {_safe_get(e, 'status')} — {_safe_get(e, 'error', _safe_get(e, 'skip_reason', 'N/A'))}")
    l2_bad = [e for e in layer2_status if _safe_get(e, "status") != "success"]
    if l2_bad:
        total_failures += len(l2_bad)
        L.append(f"  Layer 2 / {LAYER2_DAG_ID}:")
        for e in l2_bad:
            L.append(f"    ✗ {_safe_get(e, 'task_key')}: {_safe_get(e, 'status')} — {_safe_get(e, 'error', _safe_get(e, 'skip_reason', 'N/A'))}")
    l3_bad = [e for e in layer3_status if _safe_get(e, "status") != "success"]
    if l3_bad:
        total_failures += len(l3_bad)
        L.append(f"  Layer 3 / {LAYER3_DAG_ID}:")
        for e in l3_bad:
            L.append(f"    ✗ {_safe_get(e, 'task_key')}: {_safe_get(e, 'status')} — {_safe_get(e, 'error', _safe_get(e, 'skip_reason', 'N/A'))}")
    if total_failures == 0:
        L.append("  No failures detected across all layers.")
    else:
        L.append(f"\n  Total failed/skipped tasks across all layers: {total_failures}")
    L.append("")

    # ── DAG Configuration ──
    L.append("-" * 110)
    L.append("  DAG CONFIGURATION")
    L.append("-" * 110)
    L.append(f"  LAYER1_MAX_PARALLEL:       {LAYER1_MAX_PARALLEL}")
    L.append(f"  LAYER_WAIT_TIMEOUT:        {LAYER_WAIT_TIMEOUT}")
    L.append(f"  LAYER1_PROMOTION_HOUR:     {LAYER1_PROMOTION_HOUR}:00 IST")
    L.append(f"  Layer 1 DAG IDs:           {LAYER1_DAG_IDS}")
    L.append(f"  Layer 2 DAG ID:            {LAYER2_DAG_ID}")
    L.append(f"  Layer 3 DAG ID:            {LAYER3_DAG_ID}")
    L.append(f"  Schedule:                  0 * * * * (hourly)")
    L.append(f"  Max Active Runs:           1")
    L.append("")

    # ── Task Log URLs (for quick navigation) ──
    L.append("-" * 110)
    L.append("  TASK LOG URLS (for quick navigation)")
    L.append("-" * 110)
    for tid in layer1_task_ids + control_task_ids:
        url = task_log_urls.get(tid, "N/A")
        state = task_states.get(tid, "NOT_RUN")
        if state not in ("success", "skipped", "NOT_RUN"):
            L.append(f"  {tid:55s}  [{state}]")
            L.append(f"    {url}")
    L.append("")

    L.append("=" * 110)
    L.append("  END OF REPORT")
    L.append("=" * 110)

    report_text = "\n".join(L)

    # ── 6. Log the full report ───────────────────────────────────────────
    logger.info("Daily Report:\n%s", report_text)

    # ── 7. Upload to S3 ──────────────────────────────────────────────────
    date_str = logical_dt.strftime("%Y/%m/%d")
    s3_key = f"reports/controller_pipeline/{date_str}/daily_report_{run_id}.txt"

    try:
        s3_client = boto3.client(
        's3',
        endpoint_url=CEPH_ENDPOINT_URL,
        aws_access_key_id=CEPH_ACCESS_KEY,
        aws_secret_access_key=CEPH_SECRET_KEY
    )
        s3_client.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=s3_key,
            Body=report_text.encode("utf-8"),
            ContentType="text/plain",
        )
        report_uri = f"s3://{CEPH_BUCKET_NAME}/{s3_key}"
        logger.info("Daily Report uploaded to: %s", report_uri)
        ti.xcom_push(key="daily_report_uri", value=report_uri)
        return report_uri
    except Exception as e:
        logger.error("Daily Report: Failed to upload to S3 (bucket=%s, key=%s): %s",
                     CEPH_BUCKET_NAME, s3_key, e)
        logger.error("Daily Report: Full report content was logged above. Check task logs if S3 is unavailable.")
        ti.xcom_push(key="daily_report_uri", value=None)
        return None


# ─── DAG definition ─────────────────────────────────────────────────────────

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "execution_timeout": timedelta(minutes=40),
    "email": ["techexe16.yp25@uidui.net.in"],
    "email_on_failure": True,
    "retries": 0,
}

LAYER1_MAX_PARALLEL = 2
LAYER_WAIT_TIMEOUT = timedelta(minutes=90)
LAYER1_PROMOTION_HOUR = 8


with DAG(
    dag_id="controller_pipeline",
    default_args=default_args,
    description="Layered orchestrator: Layer 1 feature DAGs (hourly) -> Layer 2 instance scoring -> Layer 3 category scoring (both once/day)",
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    # Caps how many of this DAG run's tasks execute concurrently. The only
    # real concurrency in this graph is the 6 Layer-1 category triggers (see
    # below) - everything else is already serialized by explicit >> edges -
    # so in practice this just throttles Layer 1 to LAYER1_MAX_PARALLEL at a
    # time, without wiring any dependency between the categories themselves.
    max_active_tasks=LAYER1_MAX_PARALLEL,
    tags=["controller", "orchestration", "operator360"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end", trigger_rule="all_done")

    fail_handler = EmptyOperator(task_id="fail_handler", trigger_rule="one_failed")

    pipeline_run_id_tpl = "{{ run_id }}"

    
    def _compute_run_mode(**context):
        logical_dt = context.get("data_interval_start")
        if logical_dt is None:
            raise RuntimeError(
                "data_interval_start not found in context. "
                f"Available keys: {list(context.keys())}"
            )
        
        try:
            if hasattr(logical_dt, "in_timezone"):
                ist_hour = logical_dt.in_timezone("Asia/Kolkata").hour
            else:
                ist_hour = logical_dt.astimezone(ZoneInfo("Asia/Kolkata")).hour
        except Exception as e:
            raise RuntimeError(
                f"Timezone conversion failed. dt={logical_dt!r}, type={type(logical_dt)}, error={e}"
            ) from e

        is_daily_run = ist_hour == LAYER1_PROMOTION_HOUR
        logger.info("Compute Run Mode: logical_dt=%s, IST_hour=%s, is_daily_run=%s",
                    logical_dt, ist_hour, is_daily_run)
        context["ti"].xcom_push(key="is_daily_run", value=is_daily_run)
        return is_daily_run
    
    compute_run_mode = PythonOperator(task_id="compute_run_mode", python_callable=_compute_run_mode)

    # ---------------- Layer 1: feature DAGs ----------------
    # Six independent category triggers - none of them depends on any other,
    # since nothing declares such a dependency (there's no per-category
    # "Features map" at this level, just LAYER1_DAG_IDS). Concurrency is
    # capped by the DAG-level max_active_tasks=LAYER1_MAX_PARALLEL set above,
    # not by wiring categories to wait on each other.
    layer1_triggers = []
    for child_dag_id in LAYER1_DAG_IDS:
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
        logger.info("Gate Promotion: is_daily_run pulled from XCom: %s", is_daily_run)
        if not is_daily_run:
            logger.info("Gate Promotion: Skipping as it is NOT the daily promotion hour.")
            raise AirflowSkipException(
                "Not the daily promotion hour - Layer 1 ran for hourly-cadence features only, "
                "skipping judgement and Layer 2/3 this tick"
            )
        logger.info("Gate Promotion: Proceeding to Layer 1 judgement.")

    gate_promotion = PythonOperator(task_id="gate_promotion", python_callable=_gate_promotion)
    layer1_triggers >> gate_promotion

    def _judge_layer1(**context):
        ti = context["ti"]
        run_id = context["run_id"]
        valid_categories = []
        layer1_results = {}

        logger.info("Judge Layer 1: Starting judgement for run_id: %s", run_id)

        for child_dag_id in LAYER1_DAG_IDS:
            logger.info("Judge Layer 1: Reading S3 status for child_dag_id: %s", child_dag_id)
            entries = read_layer_status(run_id, child_dag_id)

            logger.info("Judge Layer 1: S3 status file contents for %s (count=%d): %s",
                        child_dag_id, len(entries), entries)

            verdicts = compute_category_verdicts(entries)
            logger.info("Judge Layer 1: Computed verdicts for %s: %s", child_dag_id, verdicts)

            category = DAG_ID_TO_CATEGORY[child_dag_id]
            is_valid = bool(verdicts.get(category))
            layer1_results[category] = {"valid": is_valid, "reported_features": len(entries)}

            if is_valid:
                valid_categories.append(category)
                logger.info("Judge Layer 1: Category '%s' -> PASSED.", category)
            else:
                logger.error("Judge Layer 1: Category '%s' -> FAILED. Analyzing failures...", category)
                _log_category_diagnostics("Layer1", category, child_dag_id, entries)

        logger.info("Layer1 judgement complete - valid categories: %s", valid_categories or "NONE")
        ti.xcom_push(key="valid_categories", value=valid_categories)
        ti.xcom_push(key="layer1_results", value=layer1_results)
        return valid_categories

    judge_layer1 = PythonOperator(
        task_id="judge_layer1",
        python_callable=_judge_layer1,
    )
    gate_promotion >> judge_layer1

    def _gate_after_layer1(**context):
        valid_categories = context["ti"].xcom_pull(task_ids="judge_layer1", key="valid_categories") or []
        logger.info("Gate After Layer 1: Valid categories pulled from XCom: %s", valid_categories)
        if not valid_categories:
            logger.warning("Gate After Layer 1: No categories passed Layer 1 - skipping Layer 2 and Layer 3")
            raise AirflowSkipException("No categories passed Layer 1 - skipping Layer 2 and Layer 3")
        logger.info("Gate After Layer 1: Proceeding to Layer 2 with valid categories: %s", valid_categories)

    gate_after_layer1 = PythonOperator(task_id="gate_after_layer1", python_callable=_gate_after_layer1)

    # ---------------- Layer 2: instance scoring ----------------
    trigger_layer2 = TriggerDagRunOperator(
        task_id="trigger_layer2",
        trigger_dag_id=LAYER2_DAG_ID,
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

        logger.info("Judge Layer 2: Starting judgement for run_id: %s. Categories valid from L1: %s", run_id, layer1_valid)

        entries = read_layer_status(run_id, LAYER2_DAG_ID)

        logger.info("Judge Layer 2: S3 status file contents for %s (count=%d): %s",
                    LAYER2_DAG_ID, len(entries), entries)

        verdicts = compute_category_verdicts(entries)
        logger.info("Judge Layer 2: Computed verdicts: %s", verdicts)

        entries_by_category = {}
        for e in entries:
            entries_by_category.setdefault(e.get("category"), []).append(e)

        valid_categories = []
        for category in layer1_valid:
            if verdicts.get(category):
                valid_categories.append(category)
                logger.info("Judge Layer 2: Category '%s' -> PASSED.", category)
            else:
                logger.error("Judge Layer 2: Category '%s' -> FAILED. Analyzing failures...", category)
                _log_category_diagnostics("Layer2", category, LAYER2_DAG_ID, entries_by_category.get(category, []))

        logger.info("Layer2 judgement complete - valid categories: %s", valid_categories or "NONE")
        ti.xcom_push(key="valid_categories", value=valid_categories)
        ti.xcom_push(key="layer2_results", value=verdicts)
        return valid_categories

    judge_layer2 = PythonOperator(
        task_id="judge_layer2",
        python_callable=_judge_layer2,
        trigger_rule="all_done",
    )

    def _gate_after_layer2(**context):
        valid_categories = context["ti"].xcom_pull(task_ids="judge_layer2", key="valid_categories") or []
        logger.info("Gate After Layer 2: Valid categories pulled from XCom: %s", valid_categories)
        if not valid_categories:
            logger.warning("Gate After Layer 2: No categories passed Layer 2 - skipping Layer 3")
            raise AirflowSkipException("No categories passed Layer 2 - skipping Layer 3")
        logger.info("Gate After Layer 2: Proceeding to Layer 3 with valid categories: %s", valid_categories)

    gate_after_layer2 = PythonOperator(task_id="gate_after_layer2", python_callable=_gate_after_layer2)

    # ---------------- Layer 3: category scoring ----------------
    trigger_layer3 = TriggerDagRunOperator(
        task_id="trigger_layer3",
        trigger_dag_id=LAYER3_DAG_ID,
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

    # ---------------- Daily Report ----------------
    generate_daily_report = PythonOperator(
        task_id="generate_daily_report",
        python_callable=_generate_daily_report,
        trigger_rule="all_done",   # fires regardless of upstream success/failure/skip
    )

    # ---------------- Wiring ----------------
    start >> compute_run_mode
    judge_layer1 >> gate_after_layer1 >> trigger_layer2
    trigger_layer2 >> judge_layer2 >> gate_after_layer2 >> trigger_layer3

    # Report runs after all terminal tasks, then feeds into end
    trigger_layer3 >> generate_daily_report
    fail_handler >> generate_daily_report
    generate_daily_report >> end
    
    
    