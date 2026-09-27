"""
Backfill every cumulative Operator360 feature for the last N days (default 30)
into the Iceberg feature tables (via Trino) and the ClickHouse feature store.

Why a separate script instead of re-running the feature tasks:
  * Every cumulative SQL stamps rows with `current_timestamp`, so re-running
    them for past dates would put all 30 days on today's date.
  * work_machineip_isp_change_count_cumulative reads `current_date` and the
    latest cumulative row ever, so it can't be replayed for a past day at all.
  * Cumulative day D is built on top of day D-1, so days must be rebuilt
    strictly in order, after deleting the old rows for the window.

For each feature this script:
  1. Pre-flight: checks the daily feature it depends on has rows for every day
     in the window, and that no cumulative rows exist after the window.
  2. Deletes the feature's Iceberg rows inside the window.
  3. Rebuilds day by day, oldest first, with "timestamp" pinned to
     '<day> 23:59:59 Asia/Kolkata'. Rows before the window seed day 1.
  4. Deletes the feature's ClickHouse rows inside the window and re-pushes each
     day with process_single_feature_to_clickhouse (same path as the pipeline).
  5. Moves last_successful_run forward to the window end (never backwards).

Dry run is the default; nothing is written without --execute.

Logging: INFO goes to the console; everything at DEBUG (including the full SQL
of every statement, Trino query ids and timings) goes to
<log-dir>/backfill_cumulative_<timestamp>.log. Grep the file for "FAILED" or
"ERROR". Every failure logs the feature, the day, the step, the Trino query id
and the exact --features/--start-date to resume from. A per-feature summary
table is printed at the end.

Run from the dags root on an Airflow worker (needs Trino/ClickHouse/MySQL access):
    cd /opt/airflow/dags
    python -m operator360.utils.backfill_cumulative_features                # dry run
    python -m operator360.utils.backfill_cumulative_features --execute      # write
    python -m operator360.utils.backfill_cumulative_features --execute \
        --features work_operator_name_unique_count_cumulative --start-date 2026-09-10
"""
import argparse
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import clickhouse_connect
from trino.dbapi import connect

from operator360.clickhouse_serving_layer.opt360_clickhouse_feature_store_test import (
    CH_HOST, CH_USER, CH_PASSWORD, CH_DATABASE, CH_TABLE,
    process_single_feature_to_clickhouse,
)

logger = logging.getLogger("backfill_cumulative_features")

TRINO_HOST = "10.10.116.75"
TRINO_PORT = "8080"
TRINO_USER = "opt360job"

IST = ZoneInfo("Asia/Kolkata")
STAGING_REGISTRY = "strot.operator360_stagging.opt360_features"
PROD_REGISTRY = "strot.operator360.opt360_features"

for _proxy in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
    os.environ.pop(_proxy, None)

DAGS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK_DIR = os.path.join(DAGS_ROOT, "operator360", "work_category_features")
BIO_DIR = os.path.join(DAGS_ROOT, "operator360", "bio_packet_fraud_features")

# Replaces work_machineip_isp_change_count_cumulative_v1.sql for backfill: the
# original reads current_date and the newest cumulative row with no date bound.
MACHINEIP_ISP_CUMULATIVE_BACKFILL_SQL = """
insert into {destination_table}
with daily as (
    select entity_id, feature_value from (
        select entity_id, feature_value,
               row_number() over(partition by entity_id order by "timestamp" desc) as rn
        from strot.operator360.features_work_v1
        where feature_id = 'work_machineip_isp_change_count_daily_v1'
          and date("timestamp") = date('{as_of_date}')
    ) where rn = 1
),
prior as (
    select entity_id, feature_value from (
        select entity_id, feature_value,
               row_number() over(partition by entity_id order by "timestamp" desc) as rn
        from strot.operator360.features_work_v1
        where feature_id = 'work_machineip_isp_change_count_cumulative_v1'
          and date("timestamp") < date('{as_of_date}')
    ) where rn = 1
)
SELECT
  d.entity_id AS entity_id,
  '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
  '{FEATURE_NAME}' AS feature_name,
  '{FEATURE_VERSION}' AS feature_version,
  coalesce(p.feature_value, 0) + d.feature_value AS feature_value,
  current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
  '' AS comments
from daily d left join prior p on d.entity_id = p.entity_id
"""

# category decides how dates are templated, matching each pipeline's runner:
#   work -> insert_work_features_test.run_one_feature: min=D, max=D+1
#   bio  -> insert_bio_packet_fraud_incidents.run_one_feature: min=D-1, max=D
# daily_feature_id is the input that must exist for each day (None = raw tables).
CUMULATIVE_FEATURES = {
    "work_operator_name_unique_count_cumulative": {
        "category": "work", "version": 1, "registry": STAGING_REGISTRY,
        "sql_path": os.path.join(WORK_DIR, "work_operator_name_unique_count_cumulative_v1.sql"),
        "daily_feature_id": None,
    },
    "work_machineip_isp_change_count_cumulative": {
        "category": "work", "version": 1, "registry": STAGING_REGISTRY,
        "sql_template": MACHINEIP_ISP_CUMULATIVE_BACKFILL_SQL,
        "daily_feature_id": "work_machineip_isp_change_count_daily_v1",
    },
    "work_packet_upload_count_child_enrolment_cumulative": {
        "category": "work", "version": 1, "registry": STAGING_REGISTRY,
        "sql_path": os.path.join(WORK_DIR, "work_packet_upload_count_child_enrolment_cumulative_v1.sql"),
        "daily_feature_id": None,
    },
    "work_packet_upload_count_adult_enrolment_cumulative": {
        "category": "work", "version": 1, "registry": STAGING_REGISTRY,
        "sql_path": os.path.join(WORK_DIR, "work_packet_upload_count_adult_enrolment_cumulative_v1.sql"),
        "daily_feature_id": None,
    },
    "bio_packet_finger_toe_print_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_finger_toe_print_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_finger_toe_print_count_daily_v1",
    },
    "bio_packet_face_pop_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_face_pop_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_face_pop_count_daily_v1",
    },
    "bio_packet_face_nonhuman_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_face_nonhuman_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_face_non_human_count_daily_v1",
    },
    "bio_packet_iris_swap_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_iris_swap_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_iris_swap_count_daily_v1",
    },
    "bio_packet_iris_flipped_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_iris_flipped_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_iris_flipped_count_daily_v1",
    },
    "bio_packet_iris_pop_count_cumulative": {
        "category": "bio", "version": 1, "registry": PROD_REGISTRY,
        "sql_path": os.path.join(BIO_DIR, "bio_packet_iris_pop_count_cumulative.sql"),
        "daily_feature_id": "bio_packet_iris_pop_count_daily_v1",
    },
}

_NOW_EXPR = re.compile(r"current_timestamp\s+AT\s+TIME\s+ZONE\s+'Asia/Kolkata'", re.IGNORECASE)
_WALL_CLOCK = re.compile(r"\b(current_timestamp|current_date|localtimestamp|now\s*\()", re.IGNORECASE)


class StepError(RuntimeError):
    """A failure with the context needed to find it in the logs and resume."""

    def __init__(self, step, feature, day=None, query_id=None, cause=None):
        self.step, self.feature, self.day, self.query_id = step, feature, day, query_id
        where = f"step={step} feature={feature}" + (f" day={day}" if day else "")
        qid = f" trino_query_id={query_id}" if query_id else ""
        super().__init__(f"{where}{qid}: {type(cause).__name__}: {cause}")


class TrinoQueryError(RuntimeError):
    def __init__(self, query_id, cause):
        self.query_id = query_id
        super().__init__(f"{type(cause).__name__}: {cause}")


def _short(sql, limit=160):
    one_line = " ".join(sql.split())
    return one_line if len(one_line) <= limit else one_line[:limit] + "..."


def trino(query, label="query"):
    """Runs one statement. Returns rows for SELECT/WITH, else the affected-row count
    Trino reports for INSERT/DELETE/UPDATE (None if it doesn't report one)."""
    is_read = query.strip().lower().startswith(("select", "with"))
    logger.debug("Trino %s starting: %s\n%s", label, _short(query), query)
    t0 = time.monotonic()
    query_id = None
    conn = None
    try:
        conn = connect(host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER)
        cur = conn.cursor()
        cur.execute(query)
        query_id = getattr(cur, "query_id", None)
        rows = cur.fetchall()  # for DML this also blocks until the write commits
        elapsed = time.monotonic() - t0
        if is_read:
            logger.debug("Trino %s ok in %.1fs query_id=%s rows=%d", label, elapsed, query_id, len(rows))
            return rows
        affected = rows[0][0] if rows and rows[0] and isinstance(rows[0][0], int) else None
        logger.debug("Trino %s ok in %.1fs query_id=%s affected_rows=%s", label, elapsed, query_id, affected)
        return affected
    except Exception as e:
        elapsed = time.monotonic() - t0
        logger.error("Trino %s FAILED after %.1fs query_id=%s host=%s:%s user=%s error=%s: %s\nSQL:\n%s",
                     label, elapsed, query_id, TRINO_HOST, TRINO_PORT, TRINO_USER,
                     type(e).__name__, e, query)
        raise TrinoQueryError(query_id, e) from e
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Ignoring error closing Trino connection", exc_info=True)


def day_ts(day):
    return f"TIMESTAMP '{day:%Y-%m-%d} 23:59:59 Asia/Kolkata'"


def day_start_ts(day):
    return f"TIMESTAMP '{day:%Y-%m-%d} 00:00:00 Asia/Kolkata'"


def parse_dependent_features(dep_val):
    params = {}
    if isinstance(dep_val, list):
        items = dep_val
    elif isinstance(dep_val, str):
        items = [i.strip().strip("'").strip('"') for i in dep_val.strip().strip("[]").split(",") if i.strip()]
    else:
        items = []
    for item in items:
        if isinstance(item, str) and ":" in item:
            k, v = item.split(":", 1)
            params[k.strip()] = v.strip()
    return params


def load_registry(name, cfg):
    logger.info("[%s] Looking up registry row in %s (version=%s)", name, cfg["registry"], cfg["version"])
    rows = trino(
        f"SELECT destination_table, dependent_features FROM {cfg['registry']} "
        f"WHERE feature_name = '{name}' AND version = '{cfg['version']}'",
        label=f"{name}:registry",
    )
    if not rows or not rows[0][0]:
        raise ValueError(f"{name} v{cfg['version']} not found in {cfg['registry']} "
                         f"(or destination_table is empty)")
    if len(rows) > 1:
        logger.warning("[%s] %d registry rows match; using the first (destination_table=%s)",
                       name, len(rows), rows[0][0])
    destination_table, params = rows[0][0], parse_dependent_features(rows[0][1])
    logger.info("[%s] destination_table=%s dependent_features=%s", name, destination_table, params)
    return destination_table, params


def render_sql(name, cfg, destination_table, params, day):
    template = cfg.get("sql_template")
    if template is None:
        path = cfg["sql_path"]
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{name}: SQL file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            template = f.read()
        logger.debug("[%s] Loaded SQL template %s (%d chars)", name, path, len(template))
    else:
        logger.debug("[%s] Using built-in backfill SQL template", name)

    if cfg["category"] == "work":
        min_pkt_date, max_pkt_date = day, day + timedelta(days=1)
    else:
        min_pkt_date, max_pkt_date = day - timedelta(days=1), day

    filter_condition = params.get("filter_condition", "")
    logger.debug("[%s] Rendering for day=%s min_pkt_date=%s max_pkt_date=%s filter_condition=%r",
                 name, day, min_pkt_date, max_pkt_date, filter_condition)
    try:
        sql = template.format(
            destination_table=destination_table,
            FEATURE_NAME=name,
            FEATURE_VERSION=cfg["version"],
            min_pkt_date=f"{min_pkt_date:%Y-%m-%d}",
            max_pkt_date=f"{max_pkt_date:%Y-%m-%d}",
            as_of_date=f"{day:%Y-%m-%d}",
            filter_condition=f"AND {filter_condition}" if str(filter_condition).strip() else "",
            eids_required="",
            req_comments=" ''  AS comments ",
            dependent_feature_id=params.get("dependent_feature_id", ""),
        )
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"{name}: SQL template has a placeholder this script doesn't fill "
                         f"(or an unescaped brace): {type(e).__name__}: {e}") from e

    sql, n = _NOW_EXPR.subn(day_ts(day), sql)
    if n != 1:
        raise ValueError(f"{name}: expected exactly one \"current_timestamp AT TIME ZONE 'Asia/Kolkata'\", found {n}")
    leftover = _WALL_CLOCK.search(sql)
    if leftover:
        raise ValueError(f"{name}: SQL still depends on wall-clock time ({leftover.group(0)}); "
                         f"add a backfill-safe sql_template for it")
    logger.debug("[%s] Rendered SQL for %s with timestamp pinned to %s", name, day, day_ts(day))
    return sql


def preflight(name, cfg, destination_table, start, end):
    """Returns a list of (kind, message); empty means OK to proceed."""
    problems = []
    feature_id = f"{name}_v{cfg['version']}"
    logger.info("[%s] Pre-flight checks on %s", name, destination_table)

    existing = trino(
        f"SELECT date(\"timestamp\"), count(*) FROM {destination_table} WHERE feature_id = '{feature_id}' "
        f"AND \"timestamp\" >= {day_start_ts(start)} AND \"timestamp\" < {day_start_ts(end + timedelta(days=1))} "
        f"GROUP BY 1 ORDER BY 1",
        label=f"{name}:existing_rows",
    )
    logger.info("[%s] Existing rows in window (will be deleted): %d rows across %d days",
                name, sum(r[1] for r in existing), len(existing))
    for d, c in existing:
        logger.debug("[%s]   existing %s: %d rows", name, d, c)

    seed = trino(
        f"SELECT max(\"timestamp\"), count(DISTINCT entity_id) FROM {destination_table} "
        f"WHERE feature_id = '{feature_id}' AND \"timestamp\" < {day_start_ts(start)}",
        label=f"{name}:seed_rows",
    )
    if seed and seed[0][0] is not None:
        logger.info("[%s] Seed history before %s: latest row at %s, %d distinct entities",
                    name, start, seed[0][0], seed[0][1])
    else:
        logger.warning("[%s] No rows before %s; day 1 of the backfill starts from zero "
                       "(fine for features recomputed from raw data, suspicious for running totals)",
                       name, start)

    later = trino(
        f"SELECT count(*), max(\"timestamp\") FROM {destination_table} WHERE feature_id = '{feature_id}' "
        f"AND \"timestamp\" >= {day_start_ts(end + timedelta(days=1))}",
        label=f"{name}:later_rows",
    )
    later_count, later_max = later[0]
    if later_count:
        problems.append(("later_rows", f"{later_count} rows exist after {end} (latest {later_max}) and were "
                                       f"computed from the old history; extend --end-date to cover them "
                                       f"or pass --allow-later-rows"))
    else:
        logger.info("[%s] No rows after %s", name, end)

    daily_id = cfg["daily_feature_id"]
    if daily_id:
        rows = trino(
            f"SELECT date(\"timestamp\"), count(*) FROM {destination_table} "
            f"WHERE feature_id = '{daily_id}' "
            f"AND \"timestamp\" >= {day_start_ts(start)} AND \"timestamp\" < {day_start_ts(end + timedelta(days=1))} "
            f"GROUP BY 1",
            label=f"{name}:daily_input",
        )
        counts = {str(r[0]): r[1] for r in rows}
        for d in daterange(start, end):
            logger.debug("[%s]   daily input %s on %s: %d rows", name, daily_id, d, counts.get(f"{d:%Y-%m-%d}", 0))
        missing = [f"{d:%Y-%m-%d}" for d in daterange(start, end) if f"{d:%Y-%m-%d}" not in counts]
        if missing:
            problems.append(("missing_daily", f"daily input {daily_id} has no rows on: {', '.join(missing)} "
                                              f"(backfill it first or pass --allow-missing-daily)"))
        else:
            logger.info("[%s] Daily input %s present on all %d days (%d rows total)",
                        name, daily_id, len(counts), sum(counts.values()))
    else:
        logger.info("[%s] Reads raw tables directly; no daily input to check", name)
    return problems


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _query_id(e):
    return getattr(e, "query_id", None)


def backfill_iceberg(name, cfg, destination_table, params, start, end, execute, stats):
    feature_id = f"{name}_v{cfg['version']}"
    total_days = (end - start).days + 1
    delete_sql = (
        f"DELETE FROM {destination_table} WHERE feature_id = '{feature_id}' "
        f"AND \"timestamp\" >= {day_start_ts(start)} AND \"timestamp\" < {day_start_ts(end + timedelta(days=1))}"
    )
    logger.info("[%s] Iceberg: deleting window rows: %s", name, _short(delete_sql, 400))
    if execute:
        try:
            deleted = trino(delete_sql, label=f"{name}:iceberg_delete")
        except Exception as e:
            raise StepError("iceberg_delete", name, query_id=_query_id(e), cause=e) from e
        stats["iceberg_deleted"] = deleted
        logger.info("[%s] Iceberg: deleted %s rows", name, deleted if deleted is not None else "(count not reported)")

    for i, day in enumerate(daterange(start, end), 1):
        try:
            sql = render_sql(name, cfg, destination_table, params, day)
        except Exception as e:
            raise StepError("render_sql", name, day=day, cause=e) from e
        if not execute:
            if day == start:
                logger.info("[%s] DRY RUN, SQL for %s:\n%s", name, day, sql)
            continue

        logger.info("[%s] Iceberg insert day %d/%d (%s)", name, i, total_days, day)
        t0 = time.monotonic()
        try:
            inserted = trino(sql, label=f"{name}:iceberg_insert:{day}")
        except Exception as e:
            logger.error("[%s] Iceberg insert FAILED on %s (day %d/%d). Days %s..%s are already "
                         "rebuilt; %s..%s have been deleted and are now missing. Later days depend "
                         "on this one, so this feature stops here. Resume with: "
                         "--execute --features %s --start-date %s --end-date %s",
                         name, day, i, total_days, start, day - timedelta(days=1), day, end,
                         name, day, end)
            raise StepError("iceberg_insert", name, day=day, query_id=_query_id(e), cause=e) from e

        stats["iceberg_days_done"] += 1
        stats["iceberg_inserted"] += inserted or 0
        stats["last_day_done"] = day
        logger.info("[%s] Iceberg %s: inserted %s rows in %.1fs",
                    name, day, inserted if inserted is not None else "(count not reported)",
                    time.monotonic() - t0)
        if inserted == 0:
            logger.warning("[%s] Iceberg %s: 0 rows inserted. Check the source/daily data for that day.",
                           name, day)


def backfill_clickhouse(name, cfg, start, end, execute, stats):
    feature_id = f"{name}_v{cfg['version']}"
    total_days = (end - start).days + 1
    delete_sql = (
        f"ALTER TABLE {CH_TABLE} DELETE WHERE feature_id = '{feature_id}' "
        f"AND toDate(last_updated_at) >= '{start:%Y-%m-%d}' AND toDate(last_updated_at) <= '{end:%Y-%m-%d}'"
    )
    logger.info("[%s] ClickHouse: deleting window rows: %s", name, delete_sql)
    if not execute:
        return

    try:
        logger.debug("[%s] Connecting to ClickHouse %s db=%s user=%s", name, CH_HOST, CH_DATABASE, CH_USER)
        ch = clickhouse_connect.get_client(host=CH_HOST, username=CH_USER, password=CH_PASSWORD, database=CH_DATABASE)
        before = ch.query(
            f"SELECT count() FROM {CH_TABLE} WHERE feature_id = '{feature_id}' "
            f"AND toDate(last_updated_at) >= '{start:%Y-%m-%d}' AND toDate(last_updated_at) <= '{end:%Y-%m-%d}'"
        ).result_rows[0][0]
        logger.info("[%s] ClickHouse: %d rows in window before delete", name, before)
        t0 = time.monotonic()
        ch.command(delete_sql, settings={"mutations_sync": 2})
        stats["ch_deleted"] = before
        logger.info("[%s] ClickHouse: delete mutation finished in %.1fs", name, time.monotonic() - t0)
    except Exception as e:
        logger.error("[%s] ClickHouse delete FAILED (host=%s table=%s): %s: %s",
                     name, CH_HOST, CH_TABLE, type(e).__name__, e)
        raise StepError("clickhouse_delete", name, cause=e) from e

    # Oldest first so the newest value is the last one written per entity.
    for i, day in enumerate(daterange(start, end), 1):
        logger.info("[%s] ClickHouse push day %d/%d (%s)", name, i, total_days, day)
        t0 = time.monotonic()
        try:
            pushed = process_single_feature_to_clickhouse(
                feature_name=name, feature_version=cfg["version"], run_date=f"{day:%Y-%m-%d}"
            )
        except Exception as e:
            logger.error("[%s] ClickHouse push FAILED on %s (day %d/%d): %s: %s. Iceberg is already done; "
                         "resume ClickHouse only with: --execute --skip-iceberg --features %s "
                         "--start-date %s --end-date %s",
                         name, day, i, total_days, type(e).__name__, e, name, day, end)
            raise StepError("clickhouse_push", name, day=day, cause=e) from e
        stats["ch_days_done"] += 1
        stats["ch_pushed"] += pushed or 0
        logger.info("[%s] ClickHouse %s: pushed %s rows in %.1fs", name, day, pushed, time.monotonic() - t0)
        if not pushed:
            logger.warning("[%s] ClickHouse %s: 0 rows pushed (no Iceberg rows that day for active "
                           "entities in operator360.opt_master?)", name, day)


def advance_last_successful_run(name, cfg, end, execute):
    sql = (
        f"UPDATE {STAGING_REGISTRY} SET last_successful_run = timestamp '{end:%Y-%m-%d} 00:00:00' "
        f"WHERE feature_name = '{name}' AND version = '{cfg['version']}' "
        f"AND (last_successful_run IS NULL OR last_successful_run < timestamp '{end:%Y-%m-%d} 00:00:00')"
    )
    logger.info("[%s] Advancing last_successful_run to %s (only if currently older)", name, end)
    if not execute:
        logger.debug("[%s] DRY RUN, would run: %s", name, sql)
        return
    try:
        updated = trino(sql, label=f"{name}:last_successful_run")
    except Exception as e:
        raise StepError("update_last_successful_run", name, query_id=_query_id(e), cause=e) from e
    if updated == 0:
        logger.info("[%s] last_successful_run already at or after %s; left unchanged", name, end)
    else:
        logger.info("[%s] last_successful_run updated (%s rows)", name, updated)


def main(argv=None):
    today = datetime.now(IST).date()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=30, help="window length ending at --end-date (default 30)")
    p.add_argument("--end-date", default=f"{today - timedelta(days=1):%Y-%m-%d}", help="last day, inclusive (default yesterday IST)")
    p.add_argument("--start-date", help="first day, inclusive; overrides --days (use to resume)")
    p.add_argument("--features", help="comma-separated feature names (default: all cumulative features)")
    p.add_argument("--skip-iceberg", action="store_true")
    p.add_argument("--skip-clickhouse", action="store_true")
    p.add_argument("--allow-later-rows", action="store_true", help="proceed even if rows exist after --end-date")
    p.add_argument("--allow-missing-daily", action="store_true", help="proceed even if a daily input has gaps")
    p.add_argument("--execute", action="store_true", help="actually write; without it this is a dry run")
    p.add_argument("--log-dir", default="backfill_logs", help="where the DEBUG log file goes (default ./backfill_logs)")
    p.add_argument("--verbose", action="store_true", help="also print DEBUG (full SQL, per-day counts) to the console")
    args = p.parse_args(argv)

    log_file = setup_logging(args.log_dir, args.verbose)
    try:
        return run(p, args, today, log_file)
    except Exception:
        logger.critical("Backfill aborted by an unexpected error:\n%s", traceback.format_exc())
        logger.critical("Full log: %s", log_file)
        return 2


def setup_logging(log_dir, verbose):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.abspath(os.path.join(log_dir, f"backfill_cumulative_{datetime.now(IST):%Y%m%d_%H%M%S}.log"))
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s:%(funcName)s:%(lineno)d %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [console, file_handler]
    # Keep HTTP client chatter out of the log; the ClickHouse loader's own INFO logs stay.
    for noisy in ("urllib3", "trino", "clickhouse_connect"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file


def _fmt_summary(results):
    header = f"{'feature':<55} {'status':<9} {'ice_days':>8} {'ice_del':>9} {'ice_ins':>10} " \
             f"{'ch_days':>7} {'ch_del':>9} {'ch_push':>9} {'secs':>7}  error"
    lines = [header, "-" * len(header)]
    for name, s in results.items():
        lines.append(
            f"{name:<55} {s['status']:<9} {s['iceberg_days_done']:>8} {str(s['iceberg_deleted'] or '-'):>9} "
            f"{s['iceberg_inserted']:>10} {s['ch_days_done']:>7} {str(s['ch_deleted'] or '-'):>9} "
            f"{s['ch_pushed']:>9} {s['seconds']:>7.0f}  {s['error'] or ''}"
        )
    return "\n".join(lines)


def run(p, args, today, log_file):
    started = time.monotonic()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    start = (datetime.strptime(args.start_date, "%Y-%m-%d").date() if args.start_date
             else end - timedelta(days=args.days - 1))
    if start > end:
        p.error(f"start {start} is after end {end}")
    if end >= today:
        logger.warning("end date %s is today or later; that day's source data may be incomplete", end)

    names = [n.strip() for n in args.features.split(",")] if args.features else list(CUMULATIVE_FEATURES)
    unknown = [n for n in names if n not in CUMULATIVE_FEATURES]
    if unknown:
        p.error(f"unknown features: {unknown}. Known: {list(CUMULATIVE_FEATURES)}")

    logger.info("=" * 100)
    logger.info("%s backfill %s -> %s (%d days) for %d features",
                "EXECUTING" if args.execute else "DRY RUN", start, end, (end - start).days + 1, len(names))
    logger.info("Log file: %s", log_file)
    logger.info("Args: %s", vars(args))
    logger.info("Trino %s:%s user=%s | ClickHouse %s db=%s table=%s", TRINO_HOST, TRINO_PORT, TRINO_USER,
                CH_HOST, CH_DATABASE, CH_TABLE)
    logger.info("Features: %s", ", ".join(names))
    logger.info("=" * 100)

    allowed = {"later_rows"} if args.allow_later_rows else set()
    allowed |= {"missing_daily"} if args.allow_missing_daily else set()

    results = {
        name: {"status": "pending", "error": None, "seconds": 0.0, "last_day_done": None,
               "iceberg_deleted": None, "iceberg_inserted": 0, "iceberg_days_done": 0,
               "ch_deleted": None, "ch_pushed": 0, "ch_days_done": 0}
        for name in names
    }

    # Phase 1: resolve and validate everything before writing anything.
    logger.info("PHASE 1: pre-flight for %d features", len(names))
    plan = {}
    for name in names:
        cfg = CUMULATIVE_FEATURES[name]
        try:
            destination_table, params = load_registry(name, cfg)
            render_sql(name, cfg, destination_table, params, start)  # fail fast on template problems
            problems = preflight(name, cfg, destination_table, start, end)
        except Exception as e:
            logger.error("[%s] Pre-flight FAILED: %s: %s", name, type(e).__name__, e)
            logger.debug("[%s] Pre-flight traceback:\n%s", name, traceback.format_exc())
            results[name].update(status="error", error=f"preflight: {e}")
            continue
        for kind, msg in problems:
            if kind in allowed:
                logger.warning("[%s] Overridden by flag: %s", name, msg)
        blocking = [msg for kind, msg in problems if kind not in allowed]
        if blocking:
            for msg in blocking:
                logger.error("[%s] BLOCKED: %s", name, msg)
            results[name].update(status="blocked", error="; ".join(blocking))
        else:
            logger.info("[%s] Pre-flight OK", name)
            plan[name] = (cfg, destination_table, params)

    # Phase 2: write. One feature failing doesn't stop the others.
    logger.info("PHASE 2: backfilling %d features (%d blocked/errored in pre-flight)",
                len(plan), len(names) - len(plan))
    for n, (name, (cfg, destination_table, params)) in enumerate(plan.items(), 1):
        stats = results[name]
        logger.info("-" * 100)
        logger.info("[%s] START feature %d/%d", name, n, len(plan))
        t0 = time.monotonic()
        try:
            if args.skip_iceberg:
                logger.info("[%s] Skipping Iceberg (--skip-iceberg)", name)
            else:
                backfill_iceberg(name, cfg, destination_table, params, start, end, args.execute, stats)
                advance_last_successful_run(name, cfg, end, args.execute)
            if args.skip_clickhouse:
                logger.info("[%s] Skipping ClickHouse (--skip-clickhouse)", name)
            else:
                backfill_clickhouse(name, cfg, start, end, args.execute, stats)
            stats["status"] = "ok" if args.execute else "dry-run"
        except Exception as e:
            stats.update(status="FAILED", error=str(e))
            logger.error("[%s] FAILED: %s", name, e)
            logger.error("[%s] Traceback:\n%s", name, traceback.format_exc())
        stats["seconds"] = time.monotonic() - t0
        logger.info("[%s] END status=%s in %.0fs", name, stats["status"], stats["seconds"])

    logger.info("=" * 100)
    logger.info("SUMMARY (%s -> %s, total %.0fs)\n%s", start, end, time.monotonic() - started, _fmt_summary(results))
    bad = {n: s for n, s in results.items() if s["status"] not in ("ok", "dry-run")}
    for name, s in bad.items():
        logger.error("NOT DONE %s [%s]: %s", name, s["status"], s["error"])
    logger.info("Full DEBUG log (all SQL, query ids, per-day counts): %s", log_file)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
