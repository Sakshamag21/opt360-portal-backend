"""Standalone backfill for instance-level and category-level scores.

Reimplements every scoring method from instance_scoring_methods.py and
category_scoring_methods.py in pandas, driven entirely by Trino - no
pyspark, no import of anything in this folder. Built for days where a data
loss meant no score got generated at all, and the normal daily job has
already moved past that date.

Key difference from the live Spark jobs: those always compute "as of right
now", so a date filter like `timestamp >= current_date - N` has an implicit
upper bound of "now". A backfill for a past date has no such implicit
bound, so every window here is explicitly anchored to --date instead
(`>= target_date - N` AND `<= target_date`) - otherwise a backfill would
silently leak data from *after* the day it's supposed to represent into
that day's score.

Usage:
    python backfill_scores.py --feature-name work_machine_change_score --feature-version 2 --date 2026-08-05
    python backfill_scores.py --feature-name work_machine_change_score --feature-version 2 --start-date 2026-08-01 --end-date 2026-08-07
    python backfill_scores.py --all --date 2026-08-05                     # every PROD scoring feature in the registry
    python backfill_scores.py --all --date 2026-08-05 --dry-run
    python backfill_scores.py --feature-name risk_score --feature-version 3 --date 2026-08-05 --force
"""
from __future__ import annotations

import argparse
import ast
import logging
import math
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from trino.dbapi import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_scores")

TRINO_HOST = "10.10.116.75"
TRINO_PORT = 8080
TRINO_USER = "opt360_backfill_script"
IST = ZoneInfo("Asia/Kolkata")
_SAFE_TABLE_RE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+){0,2}$")


# ─────────────────────────────────────────────────────────────────────────
# Trino I/O
# ─────────────────────────────────────────────────────────────────────────
def trino_query_df(sql: str) -> pd.DataFrame:
    logger.debug("TRINO QUERY: %s", sql)
    conn = connect(host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER)
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description] if cur.description else []
    df = pd.DataFrame(rows, columns=cols)
    logger.debug("TRINO QUERY returned %d row(s), %d column(s)", len(df), len(cols))
    return df


def trino_execute(sql: str) -> None:
    logger.debug("TRINO EXECUTE: %s", sql[:2000] + ("... [truncated]" if len(sql) > 2000 else ""))
    conn = connect(host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER)
    cur = conn.cursor()
    cur.execute(sql)
    cur.fetchall()  # Trino requires draining the result set even for DML
    logger.debug("TRINO EXECUTE complete")


def _sql_str(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def _assert_safe_table_name(table: str, context: str) -> None:
    """destination_table/source_table come straight out of the registry and
    get spliced into raw SQL (DELETE/INSERT included) with no other
    escaping - table identifiers can't be parameterized the way values can
    in the trino client used here. This is the one guard against a
    corrupted or malicious registry row turning into arbitrary SQL, since
    everything downstream of this trusts the string completely."""
    if not table or not _SAFE_TABLE_RE.match(table):
        raise ValueError(f"Refusing to use unsafe-looking table name for {context}: {table!r}")


# ─────────────────────────────────────────────────────────────────────────
# dependent_features parser - ported as-is from instances_main.py /
# category_main.py (ast.literal_eval first, smart-split fallback), so a
# feature's params parse identically here to how the live job parses them.
# Deliberately NOT imported from those files - this script has zero
# dependency on anything in this folder.
# ─────────────────────────────────────────────────────────────────────────
def _smart_split(s: str) -> list[str]:
    items, current, depth = [], [], 0
    for ch in s:
        if ch in "{[":
            depth += 1
            current.append(ch)
        elif ch in "}]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            item = "".join(current).strip().strip("'").strip('"')
            if item:
                items.append(item)
            current = []
        else:
            current.append(ch)
    if current:
        item = "".join(current).strip().strip("'").strip('"')
        if item:
            items.append(item)
    return items


def _parse_nested_dict(dict_str: str) -> dict:
    inner = dict_str.strip()[1:-1]
    result = {}
    for item in _smart_split(inner):
        if ":" in item:
            k, v = item.split(":", 1)
            key, value = k.strip(), v.strip()
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value
    return result


def _parse_nested_list(list_str: str) -> list[str]:
    inner = list_str.strip()[1:-1]
    return [x.strip() for x in inner.split(",")]


def parse_dependent_features(dep_val) -> dict:
    params = {}
    if isinstance(dep_val, list):
        items = dep_val
    elif isinstance(dep_val, str):
        try:
            parsed = ast.literal_eval(dep_val)
            items = parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            items = _smart_split(dep_val.strip().strip("[]"))
    else:
        items = []

    for item in items:
        if not (isinstance(item, str) and ":" in item):
            continue
        k, v = item.split(":", 1)
        key, value = k.strip(), v.strip()
        if value == "False":
            params[key] = False
        elif value == "True":
            params[key] = True
        elif value.startswith("[") and value.endswith("]"):
            params[key] = _parse_nested_list(value)
        elif value.startswith("{") and value.endswith("}"):
            params[key] = _parse_nested_dict(value)
        else:
            try:
                params[key] = int(value)
            except ValueError:
                params[key] = value
    return params


def _f(v, default=0.0) -> float:
    """float() that tolerates the parser leaving decimal values as strings
    (matches how rank_scoring/etc. cast range_start/range_end at use-site
    in the original code)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _b(v, default=False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() == "true"


# ─────────────────────────────────────────────────────────────────────────
# Registry lookup
# ─────────────────────────────────────────────────────────────────────────
def get_registry_row(feature_name: str, feature_version) -> dict | None:
    logger.info("Looking up registry row: feature_name=%s version=%s", feature_name, feature_version)
    sql = (
        "SELECT feature_name, version, feature_id, destination_table, source_table, "
        "dependent_features, status "
        "FROM strot.operator360.opt360_features "
        f"WHERE feature_name = {_sql_str(feature_name)} AND version = {_sql_str(feature_version)}"
    )
    df = trino_query_df(sql)
    if df.empty:
        logger.warning("No registry row found for feature_name=%s version=%s", feature_name, feature_version)
        return None
    row = df.iloc[0].to_dict()
    logger.info("Registry row: feature_id=%s status=%s destination_table=%s source_table=%s",
                row.get("feature_id"), row.get("status"), row.get("destination_table"), row.get("source_table"))
    logger.debug("Registry row dependent_features (raw): %s", row.get("dependent_features"))
    return row


def list_all_scoring_features() -> list[dict]:
    """Every PROD registry row whose dependent_features looks like a score
    definition (has scoring_method - instance level - or scoring_function -
    category level), for --all."""
    sql = (
        "SELECT feature_name, version, feature_id, destination_table, source_table, "
        "dependent_features, status "
        "FROM strot.operator360.opt360_features "
        "WHERE status = 'PROD' "
        "AND (dependent_features LIKE '%scoring_method%' OR dependent_features LIKE '%scoring_function%')"
    )
    logger.info("Discovering all PROD scoring features from the registry...")
    df = trino_query_df(sql)
    records = df.to_dict("records")
    logger.info("Registry scan found %d PROD scoring feature(s): %s",
                len(records), [f"{r['feature_name']}/v{r['version']}" for r in records])
    return records


# ─────────────────────────────────────────────────────────────────────────
# Source data access
# ─────────────────────────────────────────────────────────────────────────
def load_feature_values(source_table: str, feature_ids: list[str], min_date: date, max_date: date) -> pd.DataFrame:
    """entity_id, feature_id, feature_value, timestamp for feature_id(s) in
    [min_date, max_date] inclusive - the explicit backfill-safe replacement
    for the live jobs' open-ended '>= cutoff' filters."""
    _assert_safe_table_name(source_table, "load_feature_values source_table")
    logger.info("Loading feature_id(s)=%s from %s for window [%s, %s]",
                feature_ids, source_table, min_date, max_date)
    ids_sql = ", ".join(_sql_str(f) for f in feature_ids)
    sql = (
        "SELECT entity_id, feature_id, CAST(feature_value AS DOUBLE) AS feature_value, timestamp "
        f"FROM {source_table} "
        f"WHERE feature_id IN ({ids_sql}) "
        f"AND date(timestamp) >= DATE {_sql_str(min_date.isoformat())} "
        f"AND date(timestamp) <= DATE {_sql_str(max_date.isoformat())}"
    )
    df = trino_query_df(sql)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        logger.info("Loaded %d row(s), %d distinct entity_id(s), timestamp range [%s, %s]",
                    len(df), df["entity_id"].nunique(), df["timestamp"].min(), df["timestamp"].max())
    else:
        logger.warning("No rows found for feature_id(s)=%s in [%s, %s] - source data may be missing/incomplete "
                        "for this window, this is the most common reason a backfill comes back EMPTY", feature_ids, min_date, max_date)
    return df


def load_feature_values_asof(source_table: str, feature_name_or_id_col: str, feature_ids: list[str],
                              as_of_date: date, latest_only: bool = True) -> pd.DataFrame:
    """For category scoring: latest row per (entity_id, feature_name) as of
    as_of_date, mirroring softmax_scoring/weighted_average/max_scoring's
    row_number()-partitioned read of features_risk_v1."""
    _assert_safe_table_name(source_table, "load_feature_values_asof source_table")
    logger.info("Loading feature_id(s)=%s from %s as of %s (latest_only=%s)",
                feature_ids, source_table, as_of_date, latest_only)
    ids_sql = ", ".join(_sql_str(f) for f in feature_ids)
    sql = (
        "SELECT entity_id, feature_id, feature_name, CAST(feature_value AS DOUBLE) AS feature_value, timestamp "
        f"FROM {source_table} "
        f"WHERE feature_id IN ({ids_sql}) "
        f"AND date(timestamp) <= DATE {_sql_str(as_of_date.isoformat())}"
    )
    df = trino_query_df(sql)
    if df.empty:
        logger.warning("No rows found for feature_id(s)=%s as of %s", feature_ids, as_of_date)
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if latest_only:
        before = len(df)
        df = df.sort_values("timestamp").groupby(["entity_id", "feature_id"], as_index=False).last()
        logger.info("Collapsed %d row(s) to %d latest-per-(entity_id, feature_id) row(s)", before, len(df))
    found_ids = sorted(df["feature_id"].unique())
    missing_ids = sorted(set(feature_ids) - set(found_ids))
    if missing_ids:
        logger.warning("These feature_id(s) contributed ZERO rows as of %s and will be silently absent "
                        "from the weighted combination: %s", as_of_date, missing_ids)
    return df


# ─────────────────────────────────────────────────────────────────────────
# Instance-level scoring methods (pandas port of instance_scoring_methods.py)
# ─────────────────────────────────────────────────────────────────────────
def multiple_col_to_one_pd(source_table: str, feature_id, target_date: date,
                            period_in_days: float = 1, agg_method: str = None, weights: dict = None) -> pd.DataFrame:
    if agg_method is None:
        period_in_days = 1
    agg_method_upper = (agg_method or "SUM").upper()
    if agg_method_upper == "WEIGHTED_AVERAGE" and weights is None:
        raise ValueError("Weights mapping must be provided when agg_method is weighted_average")

    feature_ids = [feature_id] if isinstance(feature_id, str) else list(feature_id)
    min_date = target_date - timedelta(days=int(_f(period_in_days, 1)))

    df = load_feature_values(source_table, feature_ids, min_date, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "final_value"])

    agg_func = {"MAX": "max", "MIN": "min", "AVERAGE": "mean"}.get(agg_method_upper, "sum")
    pivot = df.pivot_table(index="entity_id", columns="feature_id", values="feature_value",
                            aggfunc=agg_func, fill_value=0.0)
    for fid in feature_ids:
        if fid not in pivot.columns:
            pivot[fid] = 0.0
    pivot = pivot[feature_ids]

    if agg_method_upper == "SUM":
        pivot["final_value"] = pivot[feature_ids].sum(axis=1)
    elif agg_method_upper == "AVERAGE":
        present = (df.pivot_table(index="entity_id", columns="feature_id", values="feature_value",
                                   aggfunc="count", fill_value=0)
                   .reindex(columns=feature_ids, fill_value=0))
        total_present = present.sum(axis=1).replace(0, np.nan)
        pivot["final_value"] = (pivot[feature_ids].sum(axis=1) / total_present).fillna(0.0)
    elif agg_method_upper == "MAX":
        pivot["final_value"] = pivot[feature_ids].max(axis=1)
    elif agg_method_upper == "MIN":
        pivot["final_value"] = pivot[feature_ids].min(axis=1)
    elif agg_method_upper == "WEIGHTED_AVERAGE":
        weight_total = sum(_f(weights.get(fid, 0.0)) for fid in feature_ids)
        if weight_total == 0:
            raise ZeroDivisionError("The total sum of provided weights for the target features cannot be zero.")
        weighted = sum(pivot[fid] * _f(weights.get(fid, 0.0)) for fid in feature_ids)
        pivot["final_value"] = weighted / weight_total
    else:
        raise NotImplementedError(f"Unsupported aggregation method: {agg_method}")

    return pivot.reset_index()[["entity_id", "final_value"]]


def rank_scoring_pd(source_table: str, feature_id, target_date: date, range_start=0.0, range_end=1.0,
                     is_inverse=False, apply_threshold=False, threshold=None, require_aggregation=False,
                     method=None, weights=None, **kwargs) -> pd.DataFrame:
    if feature_id is None or source_table is None:
        raise RuntimeError("feature_id and fraud_table must be defined")

    req_agg = _b(require_aggregation)
    range_start, range_end = _f(range_start, 0.0), _f(range_end, 1.0)

    if method == "weighted_average" and not isinstance(feature_id, str) and weights is not None:
        combined = multiple_col_to_one_pd(source_table, feature_id, target_date,
                                           period_in_days=30, agg_method="weighted_average", weights=weights)
        df_latest = combined.rename(columns={"final_value": "feature_value"})
    else:
        if req_agg:
            min_date = target_date - timedelta(days=30)
            df = load_feature_values(source_table, [feature_id], min_date, target_date)
            if df.empty:
                return pd.DataFrame(columns=["entity_id", "score"])
            df_latest = df.groupby("entity_id", as_index=False)["feature_value"].sum()
        else:
            # The live Spark job finds the overall max(date) with no lower
            # bound at all - safe there since "now" already caps it. A
            # 365-day lookback is used here instead of an unbounded scan;
            # if this feature's last real data is older than that, this
            # will come back EMPTY even though older data technically
            # exists - logged explicitly so that reads as "check further
            # back manually" rather than "silently wrong".
            lookback_start = target_date - timedelta(days=365)
            df = load_feature_values(source_table, [feature_id], lookback_start, target_date)
            if df.empty:
                logger.warning("rank_scoring: no data for %s in the last 365 days up to %s - if this feature's "
                                "last real data is older than %s, this will incorrectly come back empty; "
                                "check further back manually", feature_id, target_date, lookback_start)
                return pd.DataFrame(columns=["entity_id", "score"])
            max_ts_date = df["timestamp"].dt.date.max()
            logger.info("rank_scoring: latest-day snapshot for %s as of %s is %s", feature_id, target_date, max_ts_date)
            df_latest = df[df["timestamp"].dt.date == max_ts_date][["entity_id", "feature_value"]]

    if df_latest.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    if apply_threshold and threshold is not None:
        threshold = _f(threshold)
        if is_inverse:
            df_latest["adjusted_value"] = df_latest["feature_value"].clip(upper=threshold)
        else:
            df_latest["adjusted_value"] = df_latest["feature_value"].clip(lower=threshold)
    else:
        df_latest["adjusted_value"] = df_latest["feature_value"]

    total_count = len(df_latest)
    if total_count == 0:
        return pd.DataFrame(columns=["entity_id", "score"])

    if total_count <= 1:
        df_latest["score"] = range_end
    else:
        ascending = bool(is_inverse)
        df_latest["rank"] = df_latest["adjusted_value"].rank(method="min", ascending=ascending)
        max_rank = df_latest["rank"].max()
        if max_rank <= 1:
            df_latest["score"] = range_end
        else:
            df_latest["score"] = range_end - ((df_latest["rank"] - 1) / (max_rank - 1)) * (range_end - range_start)

    df_latest["score"] = df_latest["score"].clip(lower=min(range_start, range_end), upper=max(range_start, range_end))
    return df_latest[["entity_id", "score"]]


def zscore_pd(source_table: str, feature_id, target_date: date, is_multiple_col=False, period_in_days=30.0,
              aggregation_method=None, weights=None, require_aggregation=False,
              range_start=0.0, range_end=1.0, **kwargs) -> pd.DataFrame:
    range_start = _f(range_start, 0.0)
    agg = (aggregation_method if is_multiple_col else "SUM") if _b(require_aggregation) else None
    combined = multiple_col_to_one_pd(source_table, feature_id, target_date, period_in_days=period_in_days,
                                       agg_method=agg, weights=weights if is_multiple_col else None)
    if combined.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    mean_val = combined["final_value"].mean()
    stddev_val = combined["final_value"].std(ddof=0)
    if not stddev_val or math.isnan(stddev_val) or stddev_val == 0.0:
        stddev_val = 1.0
    combined["score"] = (combined["final_value"] - mean_val) / stddev_val
    return combined[["entity_id", "score"]]


def winsorized_zscoring_pd(source_table: str, feature_id, target_date: date, is_multiple_col=False,
                            period_in_days=30.0, aggregation_method=None, weights=None,
                            winsorize_percentile=0.99, sigmoid_scale=0.5, **kwargs) -> pd.DataFrame:
    combined = multiple_col_to_one_pd(source_table, feature_id, target_date, period_in_days=period_in_days,
                                       agg_method=aggregation_method if is_multiple_col else None,
                                       weights=weights if is_multiple_col else None)
    if combined.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    values = combined["final_value"]
    mean_val = values.mean()
    stddev_val = values.std(ddof=0)
    stddev_val = stddev_val if stddev_val and stddev_val > 0 else 1.0
    percentile_threshold = values.quantile(_f(winsorize_percentile, 0.99))

    capped = values.clip(upper=percentile_threshold)
    is_extreme = values > percentile_threshold
    zscore_vals = (capped - mean_val) / stddev_val
    sigmoid_scale = _f(sigmoid_scale, 0.5)
    score_sigmoid = 1.0 / (1.0 + np.exp(-sigmoid_scale * zscore_vals))
    score = np.where(is_extreme, 0.99, score_sigmoid)
    score = np.clip(score, 0.0, 1.0)

    combined["score"] = score
    return combined[["entity_id", "score"]]


def log_based_scoring_pd(source_table: str, feature_id: str, target_date: date, range_start=0.0, range_end=1.0,
                          period_in_days=30, threshold=0, **kwargs) -> pd.DataFrame:
    range_start, range_end = _f(range_start, 0.0), _f(range_end, 1.0)
    min_date = target_date - timedelta(days=int(_f(period_in_days, 30)))
    df = load_feature_values(source_table, [feature_id], min_date, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    agg = df.groupby("entity_id", as_index=False)["feature_value"].sum().rename(columns={"feature_value": "feature_val"})
    agg = agg[agg["feature_val"] > _f(threshold, 0)]
    if agg.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    global_max = agg["feature_val"].max()
    if not global_max or global_max <= 0:
        global_max = 1.0
    agg["score"] = range_start + (range_end - range_start) * (np.log1p(agg["feature_val"]) / np.log1p(global_max))
    agg["score"] = agg["score"].clip(lower=min(range_start, range_end), upper=max(range_start, range_end))
    return agg[["entity_id", "score"]]


def wilson_fraud_scoring_pd(source_table: str, feature_id_numerator: str, feature_id_denominator: str,
                             target_date: date, range_start=0.0, range_end=1.0, period_in_days=30,
                             **kwargs) -> pd.DataFrame:
    range_start, range_end = _f(range_start, 0.0), _f(range_end, 1.0)
    min_date = target_date - timedelta(days=int(_f(period_in_days, 30)))

    df_num = load_feature_values(source_table, [feature_id_numerator], min_date, target_date)
    df_den = load_feature_values(source_table, [feature_id_denominator], min_date, target_date)
    if df_num.empty or df_den.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    ups = df_num.groupby("entity_id", as_index=False)["feature_value"].sum().rename(columns={"feature_value": "ups"})
    n = df_den.groupby("entity_id", as_index=False)["feature_value"].sum().rename(columns={"feature_value": "n"})
    joined = ups.merge(n, on="entity_id", how="inner")
    joined = joined[joined["n"] > 0]
    if joined.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    z = 1.96
    p = joined["ups"] / joined["n"]
    nn = joined["n"]
    wilson_lower_bound = (
        p + (z**2 / (2 * nn)) - z * np.sqrt((p * (1 - p) / nn) + (z**2 / (4 * nn**2)))
    ) / (1 + (z**2 / nn))

    joined["score"] = range_start + (range_end - range_start) * wilson_lower_bound
    joined["score"] = joined["score"].clip(lower=min(range_start, range_end), upper=max(range_start, range_end))
    return joined[["entity_id", "score"]]


def exponential_decay_scoring_pd(source_table: str, feature_id: str, target_date: date, period_in_days: float,
                                  range_start=0.0, range_end=1.0, time_unit="days", decay_rate=0.1,
                                  **kwargs) -> pd.DataFrame:
    range_start, range_end = _f(range_start, 0.0), _f(range_end, 1.0)
    decay_rate = _f(decay_rate, 0.1)
    min_date = target_date - timedelta(days=int(_f(period_in_days, 30)))

    df = load_feature_values(source_table, [feature_id], min_date, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    df["date"] = df["timestamp"].dt.date
    daily = df.groupby(["entity_id", "date"], as_index=False).agg(
        feature_value=("feature_value", "max"), timestamp=("timestamp", "max")
    )

    time_divisor = 86400 if time_unit == "days" else 3600
    current_time = daily["timestamp"].max()
    daily["time_elapsed"] = (current_time - daily["timestamp"]).dt.total_seconds() / time_divisor
    daily["decay_weight"] = np.exp(-decay_rate * daily["time_elapsed"])
    daily["weighted_score"] = daily["feature_value"] * daily["decay_weight"]

    risk = daily.groupby("entity_id", as_index=False).agg(raw_risk_score=("weighted_score", "sum"))
    if risk.empty:
        return pd.DataFrame(columns=["entity_id", "score"])

    min_score, max_score = risk["raw_risk_score"].min(), risk["raw_risk_score"].max()
    if max_score > min_score:
        risk["score"] = range_start + ((risk["raw_risk_score"] - min_score) / (max_score - min_score)) * (range_end - range_start)
    else:
        risk["score"] = 0.5

    risk["score"] = risk["score"].clip(lower=min(range_start, range_end), upper=max(range_start, range_end))
    return risk[["entity_id", "score"]]


INSTANCE_METHODS = {
    "rank_scoring": rank_scoring_pd,
    "zscore": zscore_pd,
    "winsorized_zscoring": winsorized_zscoring_pd,
    "log_based_scoring": log_based_scoring_pd,
    "wilson_fraud_scoring": wilson_fraud_scoring_pd,
    "exponential_decay_scoring": exponential_decay_scoring_pd,
}


# ─────────────────────────────────────────────────────────────────────────
# Category-level scoring methods (pandas port of category_scoring_methods.py)
# These already take an explicit as-of date in the original code (max_date),
# so no extra backfill-safety changes are needed beyond passing target_date.
# ─────────────────────────────────────────────────────────────────────────
def softmax_scoring_pd(source_table: str, target_date: date, risk_weightage: dict,
                        softmax_weightage: float = 0.9, K: float = 4.0, **kwargs) -> pd.DataFrame:
    if not risk_weightage:
        raise ValueError("risk_weightage dictionary cannot be empty")
    softmax_weightage = _f(softmax_weightage, 0.9)
    if not 0 <= softmax_weightage <= 1:
        raise ValueError("softmax_weightage must be between 0 and 1")

    feature_ids = list(risk_weightage.keys())
    df = load_feature_values_asof(source_table, "feature_name", feature_ids, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "risk_value"])

    total_weight = sum(_f(v) for v in risk_weightage.values())
    normalized = {k: _f(v) / total_weight for k, v in risk_weightage.items()}
    df["norm_weight"] = df["feature_id"].map(normalized)
    df["exp_term"] = np.exp(_f(K, 4.0) * df["feature_value"])
    df["w_exp"] = df["norm_weight"] * df["exp_term"]
    df["weighted_exp_feature"] = df["norm_weight"] * df["feature_value"] * df["exp_term"]
    df["weighted_feature"] = df["norm_weight"] * df["feature_value"]

    summary = df.groupby("entity_id", as_index=False).agg(
        numerator=("weighted_exp_feature", "sum"),
        denominator=("w_exp", "sum"),
        weighted_mean=("weighted_feature", "sum"),
    )
    summary["softmax_avg"] = summary["numerator"] / summary["denominator"]
    summary["risk_value"] = (
        softmax_weightage * summary["softmax_avg"] + (1 - softmax_weightage) * summary["weighted_mean"]
    )
    return summary[["entity_id", "risk_value"]]


def weighted_average_pd(source_table: str, target_date: date, risk_weightage: dict, **kwargs) -> pd.DataFrame:
    if not risk_weightage:
        raise ValueError("risk_weightage dictionary cannot be empty")

    feature_ids = list(risk_weightage.keys())
    df = load_feature_values_asof(source_table, "feature_name", feature_ids, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "risk_value"])

    total_sum = sum(_f(v) for v in risk_weightage.values())
    weights = {k: _f(v) for k, v in risk_weightage.items()}
    df["weight"] = df["feature_id"].map(weights)
    df["weighted_risk_value"] = df["feature_value"] * df["weight"]
    df["normalized_risk_value"] = df["weighted_risk_value"] / total_sum

    return df.groupby("entity_id", as_index=False)["normalized_risk_value"].sum().rename(
        columns={"normalized_risk_value": "risk_value"}
    )


def max_scoring_pd(source_table: str, target_date: date, risk_weightage: dict, **kwargs) -> pd.DataFrame:
    if not risk_weightage:
        raise ValueError("risk_weightage dictionary cannot be empty")

    feature_ids = list(risk_weightage.keys())
    df = load_feature_values_asof(source_table, "feature_name", feature_ids, target_date)
    if df.empty:
        return pd.DataFrame(columns=["entity_id", "risk_value"])

    return df.groupby("entity_id", as_index=False)["feature_value"].max().rename(
        columns={"feature_value": "risk_value"}
    )


CATEGORY_METHODS = {
    "softmax_scoring": softmax_scoring_pd,
    "weighted_average": weighted_average_pd,
    "max_scoring": max_scoring_pd,
}


# ─────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────
def existing_row_count(destination_table: str, feature_id: str, target_date: date) -> int:
    _assert_safe_table_name(destination_table, "existing_row_count destination_table")
    sql = (
        f"SELECT count(*) AS cnt FROM {destination_table} "
        f"WHERE feature_id = {_sql_str(feature_id)} AND date(timestamp) = DATE {_sql_str(target_date.isoformat())}"
    )
    df = trino_query_df(sql)
    count = int(df["cnt"].iloc[0]) if not df.empty else 0
    logger.info("Existing rows for %s @ %s in %s: %d", feature_id, target_date, destination_table, count)
    return count


def delete_existing(destination_table: str, feature_id: str, target_date: date) -> None:
    _assert_safe_table_name(destination_table, "delete_existing destination_table")
    logger.warning("DELETING existing rows for feature_id=%s @ %s from %s (--force)",
                    feature_id, target_date, destination_table)
    sql = (
        f"DELETE FROM {destination_table} "
        f"WHERE feature_id = {_sql_str(feature_id)} AND date(timestamp) = DATE {_sql_str(target_date.isoformat())}"
    )
    trino_execute(sql)
    logger.info("Delete complete for feature_id=%s @ %s", feature_id, target_date)


def write_scores(destination_table: str, feature_id: str, feature_name: str, feature_version,
                  target_date: date, scores_df: pd.DataFrame, value_col: str, chunk_size: int = 500) -> int:
    _assert_safe_table_name(destination_table, "write_scores destination_table")
    if scores_df.empty:
        return 0
    ts = datetime.combine(target_date, datetime.min.time(), tzinfo=IST)
    rows = [
        (str(r["entity_id"]), feature_id, feature_name, str(feature_version),
         round(float(r[value_col]), 2), ts.isoformat())
        for _, r in scores_df.iterrows()
        if pd.notna(r[value_col])
    ]
    dropped = len(scores_df) - len(rows)
    if dropped:
        logger.warning("Dropping %d row(s) with a NaN/null %s before writing %s @ %s",
                        dropped, value_col, feature_id, target_date)
    logger.info("Writing %d row(s) for %s @ %s to %s (chunk_size=%d, %d chunk(s)) "
                "value range=[%.4f, %.4f]",
                len(rows), feature_id, target_date, destination_table, chunk_size,
                math.ceil(len(rows) / chunk_size) if rows else 0,
                min((r[4] for r in rows), default=0.0), max((r[4] for r in rows), default=0.0))

    written = 0
    total_chunks = math.ceil(len(rows) / chunk_size) if rows else 0
    for i in range(0, len(rows), chunk_size):
        chunk_num = i // chunk_size + 1
        batch = rows[i:i + chunk_size]
        values_sql = ", ".join(
            f"({_sql_str(eid)}, {_sql_str(fid)}, {_sql_str(fname)}, {_sql_str(fver)}, {val}, "
            f"TIMESTAMP {_sql_str(tsval)}, NULL)"
            for eid, fid, fname, fver, val, tsval in batch
        )
        sql = (
            f"INSERT INTO {destination_table} "
            "(entity_id, feature_id, feature_name, feature_version, feature_value, timestamp, comments) "
            f"VALUES {values_sql}"
        )
        trino_execute(sql)
        written += len(batch)
        logger.info("  chunk %d/%d: wrote %d row(s) (%d/%d total)",
                    chunk_num, total_chunks, len(batch), written, len(rows))
    return written


def backfill_one(feature_name: str, feature_version, target_date: date, dry_run: bool, force: bool) -> str:
    row = get_registry_row(feature_name, feature_version)
    if row is None:
        return f"SKIP  {feature_name} v{feature_version} @ {target_date}: not found in registry"

    feature_id = row["feature_id"]
    destination_table = row["destination_table"]
    source_table = row["source_table"]
    status = row.get("status")
    params = parse_dependent_features(row["dependent_features"])
    logger.info("Parsed dependent_features for %s: %s", feature_id, params)

    if status != "PROD":
        logger.warning("%s is Status='%s' (not PROD) - proceeding anyway since it was explicitly targeted", feature_id, status)

    existing = existing_row_count(destination_table, feature_id, target_date)
    if existing > 0 and not force:
        return f"SKIP  {feature_id} @ {target_date}: {existing} row(s) already present (use --force to replace)"

    scoring_method = params.get("scoring_method")
    scoring_function = params.get("scoring_function")

    try:
        if scoring_method:
            logger.info("%s @ %s: instance-level scoring_method='%s'", feature_id, target_date, scoring_method)
            func = INSTANCE_METHODS.get(scoring_method)
            if func is None:
                return (f"FAIL  {feature_id} @ {target_date}: unknown scoring_method '{scoring_method}' "
                        f"(not ported to this script - known: {sorted(INSTANCE_METHODS)})")
            call_kwargs = dict(params)
            call_kwargs.pop("scoring_method", None)
            logger.info("Calling %s(source_table=%s, target_date=%s, **%s)", scoring_method, source_table, target_date, call_kwargs)
            result = func(source_table=source_table, target_date=target_date, **call_kwargs)
            value_col = "score"
        elif scoring_function:
            logger.info("%s @ %s: category-level scoring_function='%s'", feature_id, target_date, scoring_function)
            func = CATEGORY_METHODS.get(scoring_function)
            if func is None:
                return (f"FAIL  {feature_id} @ {target_date}: unknown scoring_function '{scoring_function}' "
                        f"(not ported to this script - known: {sorted(CATEGORY_METHODS)})")
            call_kwargs = dict(params)
            call_kwargs.pop("scoring_function", None)
            logger.info("Calling %s(source_table=%s, target_date=%s, **%s)", scoring_function, source_table, target_date, call_kwargs)
            result = func(source_table=source_table, target_date=target_date, **call_kwargs)
            value_col = "risk_value"
        else:
            return f"SKIP  {feature_id} @ {target_date}: dependent_features has neither scoring_method nor scoring_function"
    except Exception as e:
        logger.exception("backfill failed for %s @ %s", feature_id, target_date)
        return f"FAIL  {feature_id} @ {target_date}: {e}"

    if result.empty:
        logger.warning("%s @ %s: scoring function returned 0 rows - most likely cause is no source data in the "
                        "computed window (see the load_feature_values warnings above), not a code error", feature_id, target_date)
        return f"EMPTY {feature_id} @ {target_date}: computed 0 rows (no source data in window) - nothing written"

    logger.info("%s @ %s: computed %d row(s), %s range=[%.4f, %.4f]",
                feature_id, target_date, len(result), value_col, result[value_col].min(), result[value_col].max())

    if dry_run:
        if existing > 0 and force:
            return (f"DRYRUN {feature_id} @ {target_date}: would DELETE {existing} existing row(s) then write "
                    f"{len(result)} row(s) to {destination_table}")
        return f"DRYRUN {feature_id} @ {target_date}: would write {len(result)} row(s) to {destination_table}"

    if existing > 0 and force:
        delete_existing(destination_table, feature_id, target_date)

    written = write_scores(destination_table, feature_id, feature_name, feature_version, target_date, result, value_col)
    return f"OK    {feature_id} @ {target_date}: wrote {written} row(s) to {destination_table}"


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--feature-name")
    p.add_argument("--feature-version")
    p.add_argument("--all", action="store_true", help="backfill every PROD scoring feature in the registry")
    p.add_argument("--date", help="single date, YYYY-MM-DD")
    p.add_argument("--start-date", help="YYYY-MM-DD")
    p.add_argument("--end-date", help="YYYY-MM-DD")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="delete and rewrite if data already exists for this date")
    p.add_argument("--verbose", action="store_true", help="log every Trino SQL statement (DEBUG level)")
    args = p.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

    if args.date:
        dates = [date.fromisoformat(args.date)]
    elif args.start_date and args.end_date:
        dates = list(daterange(date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)))
    else:
        p.error("pass either --date, or both --start-date and --end-date")
        return

    if args.all:
        targets = [(r["feature_name"], r["version"]) for r in list_all_scoring_features()]
    elif args.feature_name and args.feature_version:
        targets = [(args.feature_name, args.feature_version)]
    else:
        p.error("pass either --all, or both --feature-name and --feature-version")
        return

    total_jobs = len(dates) * len(targets)
    logger.info("Starting backfill run: %d date(s) x %d feature(s) = %d job(s) | dry_run=%s force=%s",
                len(dates), len(targets), total_jobs, args.dry_run, args.force)
    if args.force:
        logger.warning("--force is set: any (feature, date) that already has data will be DELETED and rewritten")

    results = []
    job_num = 0
    for target_date in dates:
        for feature_name, feature_version in targets:
            job_num += 1
            logger.info("=== [%d/%d] %s v%s @ %s ===", job_num, total_jobs, feature_name, feature_version, target_date)
            outcome = backfill_one(feature_name, feature_version, target_date, args.dry_run, args.force)
            logger.info(outcome)
            print(outcome)
            results.append(outcome)

    ok = sum(1 for r in results if r.startswith("OK"))
    dry = sum(1 for r in results if r.startswith("DRYRUN"))
    skip = sum(1 for r in results if r.startswith("SKIP"))
    empty = sum(1 for r in results if r.startswith("EMPTY"))
    fail = sum(1 for r in results if r.startswith("FAIL"))
    summary = f"Summary: {len(results)} total | ok={ok} dry_run={dry} skipped={skip} empty={empty} failed={fail}"
    logger.info(summary)
    print(f"\n{summary}")
    if fail:
        logger.error("%d job(s) failed - see FAIL lines above for details", fail)
        sys.exit(1)


if __name__ == "__main__":
    main()
