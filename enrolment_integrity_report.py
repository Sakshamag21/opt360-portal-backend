"""
Operator & Machine Integrity Monitoring — monthly report
========================================================

Every rule is computed TWICE, on two independent entity keys that are never
mixed:

    BY OPERATOR (operator_id)   — "is this person behaving impossibly?"
    BY MACHINE  (station_machine_code) — "is this client behaving impossibly?"

  R1A  Parallel Enrolment  by operator  — operator opened a packet before their
       previous packet closed. `cross_machine=True` means the two packets were
       on different clients: one human cannot be at two stations at once.
  R1B  Parallel Enrolment  by machine   — machine opened a packet before its
       previous packet closed. `cross_operator=True` means two credentials ran
       concurrently on one client: shared login or a cloned/virtualised client.

  R2A  IP change   by operator — distinct source IPs per operator, rolling window
  R2B  IP change   by machine  — distinct source IPs per machine, rolling window
  R3A  Device churn by operator — distinct machines per operator, rolling window
  R3B  Operator churn by machine — distinct operators per machine, rolling window
       (the true mirror of R3A; "distinct machines per machine" is always 1)

Requires: polars >= 1.0, xlsxwriter (Excel export only).

    python enrolment_integrity_report.py --input events.parquet --month 2026-06

FIRST RUN: `--discover` prints the real stage/stage_status strings. Put them in
STAGE_CFG before trusting any R1 output.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import polars as pl

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

TS_FORMAT: str | None = None  # None = infer; else e.g. "%Y-%m-%d %H:%M:%S"

STAGE_CFG = {
    "packet_stages": ["PacketCreation"],
    "start_status": ["START", "STARTED", "INITIATED"],
    # Both success and failure close a session — either way the client is free.
    "end_status": ["COMPLETE", "COMPLETED", "SUCCESS", "FAILED", "ABORTED", "CANCELLED"],
}

THRESHOLDS = {
    # R1 — shared by both keys.
    "parallel_min_overlap_seconds": 30,   # absorbs client/server clock skew
    "assumed_session_max_minutes": 120,   # caps packets with no end event

    # R2A — IPs per operator
    "ip_by_opt_burst_window": "1h",  "ip_by_opt_burst_distinct": 3,
    "ip_by_opt_daily_window": "24h", "ip_by_opt_daily_distinct": 5,

    # R2B — IPs per machine. A fixed station should be far more stable than a
    # person, so these are deliberately tighter.
    "ip_by_mc_burst_window": "1h",   "ip_by_mc_burst_distinct": 2,
    "ip_by_mc_daily_window": "24h",  "ip_by_mc_daily_distinct": 3,

    # R3A — machines per operator
    "mc_by_opt_burst_window": "4h",  "mc_by_opt_burst_distinct": 2,
    "mc_by_opt_daily_window": "24h", "mc_by_opt_daily_distinct": 3,

    # R3B — operators per machine. Shift handover on a shared station is normal,
    # so the daily bar sits higher than the burst bar.
    "opt_by_mc_burst_window": "1h",  "opt_by_mc_burst_distinct": 2,
    "opt_by_mc_daily_window": "24h", "opt_by_mc_daily_distinct": 4,
}

WEIGHTS = {"parallel": 5.0, "ip": 2.0, "churn": 3.0}

OPERATOR_CTX = ["operator_name", "ea_name", "reg_name", "registrar",
                "subdistrict", "district", "state", "pincode", "ro"]
MACHINE_CTX = ["ea_name", "reg_name", "registrar",
               "subdistrict", "district", "state", "pincode", "ro"]
ALL_CTX = ["operator_name"] + MACHINE_CTX

ENTITY_LABEL = {"opt": "operator_id", "machine": "station_machine_code"}


def _present(df: pl.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


# ---------------------------------------------------------------------------
# 0. PREPARATION
# ---------------------------------------------------------------------------

def discover_stage_values(df: pl.DataFrame, top: int = 60) -> pl.DataFrame:
    """Run once. Copy the real strings into STAGE_CFG."""
    return (
        df.group_by(["stage", "stage_status"])
          .agg(events=pl.len(), txns=pl.col("txn_id").n_unique())
          .sort("events", descending=True)
          .head(top)
    )


def prepare(df: pl.DataFrame, month: str | None = None) -> pl.DataFrame:
    out = (
        df.with_columns(
            event_ts=pl.col("event_timestamp").str.to_datetime(
                format=TS_FORMAT, strict=False),
            opt=pl.coalesce(
                pl.col("operator_id").cast(pl.Utf8).str.strip_chars(),
                pl.col("operator_uid").cast(pl.Int64).cast(pl.Utf8)),
            machine=pl.col("station_machine_code").cast(pl.Utf8).str.strip_chars(),
            ip=pl.col("machine_ip_address").cast(pl.Utf8).str.strip_chars(),
        )
        .filter(
            pl.col("event_ts").is_not_null()
            & pl.col("opt").is_not_null()
            & pl.col("machine").is_not_null()
        )
    )
    if "event_id" in out.columns:
        out = out.unique(subset=["event_id"], keep="first")

    if month:
        lo = datetime.strptime(month + "-01", "%Y-%m-%d")
        hi = datetime(lo.year + (lo.month == 12), (lo.month % 12) + 1, 1)
        out = out.filter((pl.col("event_ts") >= lo) & (pl.col("event_ts") < hi))

    return out.with_columns(event_date=pl.col("event_ts").dt.date())


# ---------------------------------------------------------------------------
# 1. SESSION TABLE — one row per packet, entity-agnostic
# ---------------------------------------------------------------------------

def build_sessions(df: pl.DataFrame) -> pl.DataFrame:
    """One row per txn_id. Operator and machine are ATTRIBUTES here, not part
    of the key, so the same table can be re-keyed either way downstream."""
    cfg = STAGE_CFG
    ctx = _present(df, ALL_CTX)
    is_start = pl.col("stage_status").is_in(cfg["start_status"])
    is_end = pl.col("stage_status").is_in(cfg["end_status"])

    packets = df.filter(pl.col("stage").is_in(cfg["packet_stages"]))

    return (
        packets.group_by("txn_id")
        .agg(
            start_ts=pl.col("event_ts").filter(is_start).min(),
            end_ts=pl.col("event_ts").filter(is_end).max(),
            last_seen=pl.col("event_ts").max(),
            n_events=pl.len(),
            opt=pl.col("opt").drop_nulls().first(),
            machine=pl.col("machine").drop_nulls().first(),
            ip=pl.col("ip").drop_nulls().first(),
            # >1 here means the packet itself changed hands mid-flight.
            n_operators_on_packet=pl.col("opt").n_unique(),
            n_machines_on_packet=pl.col("machine").n_unique(),
            resident_sid=pl.col("resident_sid").drop_nulls().first(),
            **{c: pl.col(c).drop_nulls().first() for c in ctx},
        )
        .filter(pl.col("start_ts").is_not_null())
        .with_columns(
            never_completed=pl.col("end_ts").is_null(),
            end_ts_eff=pl.coalesce(pl.col("end_ts"), pl.col("last_seen"),
                                   pl.col("start_ts")),
        )
        .with_columns(
            end_ts_eff=pl.min_horizontal(
                pl.col("end_ts_eff"),
                pl.col("start_ts").dt.offset_by(
                    f"{THRESHOLDS['assumed_session_max_minutes']}m"),
            )
        )
        .with_columns(
            duration_min=((pl.col("end_ts_eff") - pl.col("start_ts"))
                          .dt.total_seconds() / 60).round(2),
            event_date=pl.col("start_ts").dt.date(),
        )
    )


# ---------------------------------------------------------------------------
# 2. RULE 1 — PARALLEL ENROLMENT, keyed on ONE entity at a time
# ---------------------------------------------------------------------------

def detect_parallel(sessions: pl.DataFrame, key: str, rule_name: str) -> pl.DataFrame:
    """Overlapping packets within a single entity.

    `key` is "opt" or "machine" — never both. The other entity is carried as an
    attribute and compared, so the output tells you whether the concurrency
    stayed inside one client/one login or crossed over.

    cum_max (not the previous row's end) is what catches a third packet opening
    inside a still-open first packet after the second already closed.
    """
    other = "machine" if key == "opt" else "opt"
    cross = "cross_machine" if key == "opt" else "cross_operator"
    min_ov = THRESHOLDS["parallel_min_overlap_seconds"]
    ctx = _present(sessions, OPERATOR_CTX if key == "opt" else MACHINE_CTX)

    flagged = (
        sessions.sort([key, "start_ts"])
        .with_columns(
            prior_end=pl.col("end_ts_eff").cum_max().shift(1).over(key),
            prior_txn=pl.col("txn_id").shift(1).over(key),
            prior_start=pl.col("start_ts").shift(1).over(key),
            prior_other=pl.col(other).shift(1).over(key),
            prior_ip=pl.col("ip").shift(1).over(key),
            seq=pl.int_range(pl.len()).over(key),
        )
        .filter(pl.col("seq") > 0)
        .with_columns(
            overlap_seconds=(pl.col("prior_end") - pl.col("start_ts")).dt.total_seconds()
        )
        .filter(pl.col("overlap_seconds") > min_ov)
        .with_columns(
            rule=pl.lit(rule_name),
            entity_type=pl.lit(ENTITY_LABEL[key]),
            overlap_minutes=(pl.col("overlap_seconds") / 60).round(2),
            **{cross: pl.col(other) != pl.col("prior_other")},
        )
        .with_columns(
            # Concurrency that crosses the other entity is the impossible case,
            # so it outranks a long same-entity overlap.
            severity=pl.when(pl.col(cross)).then(pl.lit("HIGH"))
            .when(pl.col("overlap_seconds") > 900).then(pl.lit("HIGH"))
            .when(pl.col("overlap_seconds") > 300).then(pl.lit("MEDIUM"))
            .otherwise(pl.lit("LOW")),
        )
        .rename({key: "entity_id"})
    )

    front = ["rule", "entity_type", "entity_id", "severity", "event_date",
             cross, other, "prior_other", "txn_id", "prior_txn",
             "start_ts", "end_ts", "prior_start", "prior_end",
             "overlap_minutes", "duration_min", "never_completed",
             "ip", "prior_ip", "resident_sid"]
    return flagged.select(_present(flagged, front) + ctx).sort(
        ["entity_id", "start_ts"])


def rule_parallel_by_operator(s: pl.DataFrame) -> pl.DataFrame:
    return detect_parallel(s, "opt", "R1A_PARALLEL_BY_OPERATOR")


def rule_parallel_by_machine(s: pl.DataFrame) -> pl.DataFrame:
    return detect_parallel(s, "machine", "R1B_PARALLEL_BY_MACHINE")


# ---------------------------------------------------------------------------
# 3. RULES 2 & 3 — ROLLING DISTINCT CARDINALITY, one entity at a time
# ---------------------------------------------------------------------------

def rolling_distinct_alerts(
    df: pl.DataFrame,
    entity: str,          # "opt" or "machine" — the thing being watched
    value_col: str,       # "ip", "machine", or "opt" — the thing being counted
    window: str,
    threshold: int,
    rule_name: str,
) -> pl.DataFrame:
    """Count distinct `value_col` seen by one `entity` in a trailing window.

    A raw rolling filter emits one row per qualifying event, so a single burst
    would be reported dozens of times; alerts are collapsed to the daily peak
    per entity.
    """
    ctx = _present(df, OPERATOR_CTX if entity == "opt" else MACHINE_CTX)

    raw = (
        df.filter(pl.col(value_col).is_not_null() & (pl.col(value_col) != ""))
        .sort([entity, "event_ts"])
        .rolling(index_column="event_ts", period=window, group_by=entity,
                 closed="right")
        .agg(
            n_distinct=pl.col(value_col).n_unique(),
            values=pl.col(value_col).unique(),
            n_events=pl.len(),
            window_start=pl.col("event_ts").min(),
        )
        .filter(pl.col("n_distinct") >= threshold)
        .rename({"event_ts": "window_end"})
        .with_columns(event_date=pl.col("window_end").dt.date())
    )
    if raw.height == 0:
        return raw.rename({entity: "entity_id"}) if entity in raw.columns else raw

    episodes = (
        raw.sort([entity, "event_date", "n_distinct", "window_end"])
        .group_by([entity, "event_date"])
        .agg(
            peak_distinct=pl.col("n_distinct").max(),
            peak_window_start=pl.col("window_start").last(),
            peak_window_end=pl.col("window_end").last(),
            values=pl.col("values").last(),
            events_in_window=pl.col("n_events").last(),
            alerting_events=pl.len(),
        )
        .with_columns(
            rule=pl.lit(rule_name),
            entity_type=pl.lit(ENTITY_LABEL[entity]),
            counted=pl.lit(ENTITY_LABEL.get(value_col, value_col)),
            window=pl.lit(window),
            threshold=pl.lit(threshold, dtype=pl.Int32),
            distinct_values=pl.col("values").cast(pl.List(pl.Utf8))
                              .list.sort().list.join(", "),
            severity=pl.when(pl.col("peak_distinct") >= threshold * 2)
            .then(pl.lit("HIGH"))
            .when(pl.col("peak_distinct") > threshold).then(pl.lit("MEDIUM"))
            .otherwise(pl.lit("LOW")),
        )
        .drop("values")
    )

    if ctx:
        lookup = df.group_by(entity).agg(
            **{c: pl.col(c).drop_nulls().first() for c in ctx})
        episodes = episodes.join(lookup, on=entity, how="left")

    episodes = episodes.rename({entity: "entity_id"})
    front = ["rule", "entity_type", "entity_id", "severity", "event_date",
             "counted", "peak_distinct", "threshold", "window",
             "peak_window_start", "peak_window_end",
             "events_in_window", "alerting_events", "distinct_values"]
    return episodes.select(front + ctx).sort(
        ["peak_distinct", "entity_id"], descending=[True, False])


def _two_tier(df, entity, value_col, prefix, name) -> pl.DataFrame:
    t = THRESHOLDS
    burst = rolling_distinct_alerts(
        df, entity, value_col, t[f"{prefix}_burst_window"],
        t[f"{prefix}_burst_distinct"], f"{name}_BURST")
    daily = rolling_distinct_alerts(
        df, entity, value_col, t[f"{prefix}_daily_window"],
        t[f"{prefix}_daily_distinct"], f"{name}_DAILY")
    parts = [x for x in (burst, daily) if x.height > 0]
    if not parts:
        return burst
    return pl.concat(parts, how="diagonal_relaxed")


def rule_ip_by_operator(df):   # R2A
    return _two_tier(df, "opt", "ip", "ip_by_opt", "R2A_IP_BY_OPERATOR")

def rule_ip_by_machine(df):    # R2B
    return _two_tier(df, "machine", "ip", "ip_by_mc", "R2B_IP_BY_MACHINE")

def rule_devices_by_operator(df):   # R3A
    return _two_tier(df, "opt", "machine", "mc_by_opt", "R3A_DEVICES_BY_OPERATOR")

def rule_operators_by_machine(df):  # R3B
    return _two_tier(df, "machine", "opt", "opt_by_mc", "R3B_OPERATORS_BY_MACHINE")


# ---------------------------------------------------------------------------
# 4. RISK REGISTERS — one per entity, built the same way
# ---------------------------------------------------------------------------

def entity_risk_register(
    ev: pl.DataFrame,
    entity: str,
    parallel: pl.DataFrame,
    ip_alerts: pl.DataFrame,
    churn_alerts: pl.DataFrame,
) -> pl.DataFrame:
    other = "machine" if entity == "opt" else "opt"
    ctx = _present(ev, OPERATOR_CTX if entity == "opt" else MACHINE_CTX)

    base = ev.group_by(entity).agg(
        total_events=pl.len(),
        packets=pl.col("txn_id").n_unique(),
        active_days=pl.col("event_date").n_unique(),
        distinct_ips=pl.col("ip").n_unique(),
        **{f"distinct_{other}s": pl.col(other).n_unique()},
        first_activity=pl.col("event_ts").min(),
        last_activity=pl.col("event_ts").max(),
        **{c: pl.col(c).drop_nulls().first() for c in ctx},
    ).rename({entity: "entity_id"})

    def _count(d: pl.DataFrame, name: str) -> pl.DataFrame:
        if d.height == 0 or "entity_id" not in d.columns:
            return pl.DataFrame(schema={"entity_id": pl.Utf8,
                                        name: pl.UInt32,
                                        f"{name}_days": pl.UInt32})
        return d.group_by("entity_id").agg(
            **{name: pl.len(), f"{name}_days": pl.col("event_date").n_unique()})

    cnt_cols = ["parallel_alerts", "parallel_alerts_days",
                "ip_alerts", "ip_alerts_days",
                "churn_alerts", "churn_alerts_days"]

    reg = (
        base.join(_count(parallel, "parallel_alerts"), on="entity_id", how="left")
        .join(_count(ip_alerts, "ip_alerts"), on="entity_id", how="left")
        .join(_count(churn_alerts, "churn_alerts"), on="entity_id", how="left")
        .with_columns(pl.col(cnt_cols).fill_null(0))
    )

    # Cross-entity concurrency is the physically impossible subset — surface it.
    cross_col = "cross_machine" if entity == "opt" else "cross_operator"
    if parallel.height and cross_col in parallel.columns:
        xc = (parallel.filter(pl.col(cross_col))
              .group_by("entity_id").agg(cross_entity_alerts=pl.len()))
        reg = reg.join(xc, on="entity_id", how="left").with_columns(
            pl.col("cross_entity_alerts").fill_null(0))
    else:
        reg = reg.with_columns(cross_entity_alerts=pl.lit(0, dtype=pl.UInt32))

    return (
        reg.with_columns(
            entity_type=pl.lit(ENTITY_LABEL[entity]),
            rules_triggered=(
                (pl.col("parallel_alerts") > 0).cast(pl.Int32)
                + (pl.col("ip_alerts") > 0).cast(pl.Int32)
                + (pl.col("churn_alerts") > 0).cast(pl.Int32)
            ),
            # Per-100-packets so high-throughput entities aren't punished for volume.
            risk_score=(
                (WEIGHTS["parallel"] * pl.col("parallel_alerts")
                 + WEIGHTS["ip"] * pl.col("ip_alerts_days")
                 + WEIGHTS["churn"] * pl.col("churn_alerts_days"))
                / pl.max_horizontal(pl.col("packets"), pl.lit(1)) * 100
            ).round(2),
            parallel_rate_pct=(
                pl.col("parallel_alerts")
                / pl.max_horizontal(pl.col("packets"), pl.lit(1)) * 100
            ).round(2),
        )
        .with_columns(
            priority=pl.when(pl.col("cross_entity_alerts") > 0)
            .then(pl.lit("P0_IMPOSSIBLE"))
            .when(pl.col("rules_triggered") >= 2).then(pl.lit("P1_INVESTIGATE"))
            .when(pl.col("rules_triggered") == 1).then(pl.lit("P2_REVIEW"))
            .otherwise(pl.lit("P3_CLEAR"))
        )
        .sort(["cross_entity_alerts", "rules_triggered", "risk_score"],
              descending=True)
    )


def daily_trend(named: dict[str, pl.DataFrame]) -> pl.DataFrame:
    parts = [
        d.group_by("event_date").agg(alerts=pl.len(),
                                     entities=pl.col("entity_id").n_unique())
         .with_columns(rule=pl.lit(name))
        for name, d in named.items() if d.height and "entity_id" in d.columns
    ]
    if not parts:
        return pl.DataFrame(schema={"event_date": pl.Date, "rule": pl.Utf8,
                                    "alerts": pl.UInt32, "entities": pl.UInt32})
    return pl.concat(parts, how="diagonal_relaxed").sort(["event_date", "rule"])


def entity_rollup(reg: pl.DataFrame, level: str) -> pl.DataFrame:
    if level not in reg.columns:
        return pl.DataFrame()
    return (
        reg.group_by(level).agg(
            entities=pl.len(),
            flagged=(pl.col("rules_triggered") > 0).sum(),
            p0_impossible=(pl.col("priority") == "P0_IMPOSSIBLE").sum(),
            p1_investigate=(pl.col("priority") == "P1_INVESTIGATE").sum(),
            parallel_alerts=pl.col("parallel_alerts").sum(),
            ip_alerts=pl.col("ip_alerts").sum(),
            churn_alerts=pl.col("churn_alerts").sum(),
            packets=pl.col("packets").sum(),
        )
        .with_columns(
            flagged_pct=(pl.col("flagged") / pl.col("entities") * 100).round(1))
        .sort("flagged", descending=True)
    )


# ---------------------------------------------------------------------------
# 5. ORCHESTRATION + EXPORT
# ---------------------------------------------------------------------------

def run_report(df: pl.DataFrame, month: str | None = None) -> dict[str, pl.DataFrame]:
    ev = prepare(df, month)
    sess = build_sessions(ev)

    r1a = rule_parallel_by_operator(sess)
    r1b = rule_parallel_by_machine(sess)
    r2a = rule_ip_by_operator(ev)
    r2b = rule_ip_by_machine(ev)
    r3a = rule_devices_by_operator(ev)
    r3b = rule_operators_by_machine(ev)

    reg_opt = entity_risk_register(ev, "opt", r1a, r2a, r3a)
    reg_mc = entity_risk_register(ev, "machine", r1b, r2b, r3b)

    def n_ent(d):
        return d["entity_id"].n_unique() if d.height and "entity_id" in d.columns else 0

    summary = pl.DataFrame({
        "section": (["Scope"] * 6 + ["By operator_id"] * 8
                    + ["By station_machine_code"] * 8 + ["Data quality"] * 3),
        "metric": [
            "Period", "Events analysed", "Packets analysed",
            "Distinct operators", "Distinct machines", "Distinct source IPs",
            "R1A parallel alerts", "R1A operators affected",
            "  of which cross-machine (impossible)",
            "R2A IP-change alerts", "R2A operators affected",
            "R3A device-churn alerts", "R3A operators affected",
            "Operators P0/P1",
            "R1B parallel alerts", "R1B machines affected",
            "  of which cross-operator (shared login)",
            "R2B IP-change alerts", "R2B machines affected",
            "R3B operator-churn alerts", "R3B machines affected",
            "Machines P0/P1",
            "Packets with no completion event",
            "Packets touched by >1 operator",
            "Packets touched by >1 machine",
        ],
        "value": [
            month or "all data", f"{ev.height:,}", f"{sess.height:,}",
            f"{ev['opt'].n_unique():,}", f"{ev['machine'].n_unique():,}",
            f"{ev['ip'].n_unique():,}",
            f"{r1a.height:,}", f"{n_ent(r1a):,}",
            f"{int(r1a['cross_machine'].sum()) if r1a.height else 0:,}",
            f"{r2a.height:,}", f"{n_ent(r2a):,}",
            f"{r3a.height:,}", f"{n_ent(r3a):,}",
            f"{int(reg_opt['priority'].is_in(['P0_IMPOSSIBLE','P1_INVESTIGATE']).sum()):,}",
            f"{r1b.height:,}", f"{n_ent(r1b):,}",
            f"{int(r1b['cross_operator'].sum()) if r1b.height else 0:,}",
            f"{r2b.height:,}", f"{n_ent(r2b):,}",
            f"{r3b.height:,}", f"{n_ent(r3b):,}",
            f"{int(reg_mc['priority'].is_in(['P0_IMPOSSIBLE','P1_INVESTIGATE']).sum()):,}",
            f"{int(sess['never_completed'].sum()):,}",
            f"{int((sess['n_operators_on_packet'] > 1).sum()):,}",
            f"{int((sess['n_machines_on_packet'] > 1).sum()):,}",
        ],
    })

    out = {
        "01_Summary": summary,
        "02_Operator_Risk_Register": reg_opt,
        "03_Machine_Risk_Register": reg_mc,
        "04_R1A_Parallel_by_Operator": r1a,
        "05_R1B_Parallel_by_Machine": r1b,
        "06_R2A_IP_by_Operator": r2a,
        "07_R2B_IP_by_Machine": r2b,
        "08_R3A_Devices_by_Operator": r3a,
        "09_R3B_Operators_by_Machine": r3b,
        "10_Daily_Trend": daily_trend({
            "R1A_parallel_by_operator": r1a, "R1B_parallel_by_machine": r1b,
            "R2A_ip_by_operator": r2a, "R2B_ip_by_machine": r2b,
            "R3A_devices_by_operator": r3a, "R3B_operators_by_machine": r3b,
        }),
    }
    for lvl, sheet in (("reg_name", "11_Operators_by_Registrar"),
                       ("ea_name", "12_Operators_by_EA"),
                       ("district", "13_Operators_by_District")):
        t = entity_rollup(reg_opt, lvl)
        if t.height:
            out[sheet] = t
    t = entity_rollup(reg_mc, "district")
    if t.height:
        out["14_Machines_by_District"] = t
    return out


def _excel_safe(df: pl.DataFrame) -> pl.DataFrame:
    fixes = {n: pl.col(n).cast(pl.List(pl.Utf8)).list.join(", ")
             for n, d in df.schema.items() if isinstance(d, pl.List)}
    return df.with_columns(**fixes) if fixes else df


def export(tables: dict[str, pl.DataFrame], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    if out_path.suffix.lower() == ".xlsx":
        import xlsxwriter
        with xlsxwriter.Workbook(str(out_path)) as wb:
            for sheet, tbl in tables.items():
                if tbl.height == 0:
                    tbl = pl.DataFrame({"note": ["No alerts for this rule in period."]})
                _excel_safe(tbl).write_excel(
                    workbook=wb, worksheet=sheet[:31], autofit=True,
                    header_format={"bold": True, "bg_color": "#1F3864",
                                   "font_color": "#FFFFFF", "font_name": "Arial"},
                    dtype_formats={pl.Datetime: "yyyy-mm-dd hh:mm:ss",
                                   pl.Date: "yyyy-mm-dd"},
                )
    else:
        out_path.mkdir(parents=True, exist_ok=True)
        for sheet, tbl in tables.items():
            _excel_safe(tbl).write_csv(out_path / f"{sheet}.csv")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--month", help="YYYY-MM; omit for all rows")
    ap.add_argument("--out", default="integrity_report.xlsx")
    ap.add_argument("--discover", action="store_true",
                    help="print stage/stage_status combinations and exit")
    args = ap.parse_args()

    p = Path(args.input)
    df = pl.read_parquet(p) if p.suffix == ".parquet" else pl.read_csv(
        p, infer_schema_length=10000)

    if args.discover:
        with pl.Config(tbl_rows=60):
            print(discover_stage_values(df))
        return

    tables = run_report(df, args.month)
    with pl.Config(tbl_rows=40, fmt_str_lengths=60):
        print(tables["01_Summary"])
    print(f"\nWritten: {export(tables, args.out)}")


if __name__ == "__main__":
    main()
