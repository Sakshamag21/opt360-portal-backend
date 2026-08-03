"""
Operator360 risk-score consistency audit.

For every operator in opt_master (MySQL), checks that its overall risk_score
is "justified" by at least one of its six ClickHouse risk_analysis category
scores (document / hardware / biometrics / work / suspicious / authentication):

  1. At least one category score must be within DEVIATION_THRESHOLD of
     risk_score (abs difference <= threshold).
  2. If the matching category is document, biometrics, or suspicious, the
     operator's count of anomalous rows in operator360.anomalous_packets_v2_rmt
     for that category must meet the minimum required for that category's own
     score, per BRACKETS (see .env.example) — a higher category score demands
     more anomalous EIDs/SIDs backing it, not just "at least one".
  3. Independently of 1/2: an operator in a high-severity risk_bucket (see
     HIGH_SEVERITY_BUCKETS in .env.example, default "critical") must have at
     least one anomalous row across document/biometrics/suspicious combined.
     A "Critical" operator with zero anomalous evidence anywhere is a bigger
     red flag than a single bracket miss, and doesn't depend on risk_analysis
     existing at all — it's checked from opt_master.risk_bucket directly.

Flags every operator that fails any condition, with the specific reason(s).
Reads connection details from .env (see .env.example) via python-dotenv.

Usage:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in real values
    python risk_audit.py
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass, field

import clickhouse_connect
import pymysql
from dotenv import load_dotenv

CATEGORIES = [
    ("document", "document_category_score"),
    ("hardware", "hardware_category_score"),
    ("biometrics", "biometrics_category_score"),
    ("work", "work_category_score"),
    ("suspicious", "suspicious_category_score"),
    ("authentication", "authentication_category_score"),
]
CATEGORIES_REQUIRING_ANOMALOUS_EVIDENCE = {"document", "biometrics", "suspicious"}

# Default bracket table: (lower_bound_inclusive, min_anomalous_count), ascending
# by lower_bound. A category score falls into the highest bracket whose
# lower_bound it meets or exceeds — e.g. a suspicious_category_score of 0.6
# falls in the [0.50, ...) bracket, requiring >= 7 anomalous rows for
# "suspicious". Overridable via BRACKETS in .env.
DEFAULT_BRACKETS = [(0.00, 1), (0.25, 3), (0.50, 7), (0.75, 15)]


def parse_brackets(raw: str) -> list[tuple[float, int]]:
    """Parses BRACKETS env value 'lower:count,lower:count,...' into a sorted
    list of (lower_bound, min_count) pairs. Falls back to DEFAULT_BRACKETS if
    raw is empty."""
    if not raw:
        return DEFAULT_BRACKETS

    brackets = []
    for pair in raw.split(","):
        lower_str, count_str = pair.split(":")
        brackets.append((float(lower_str), int(count_str)))
    brackets.sort(key=lambda b: b[0])
    return brackets


def required_anomalous_count(score: float, brackets: list[tuple[float, int]]) -> int:
    """The minimum anomalous-row count required for a category with this
    score, per brackets. Score below every bracket's lower_bound requires 0."""
    required = 0
    for lower_bound, min_count in brackets:
        if score >= lower_bound:
            required = min_count
        else:
            break
    return required


def parse_bucket_set(raw: str) -> set[str]:
    """Parses HIGH_SEVERITY_BUCKETS ('critical,high') into a lowercased set."""
    return {b.strip().lower() for b in raw.split(",") if b.strip()}


@dataclass
class OperatorResult:
    opt_id: str
    name: str
    ro: str
    risk_score: float | None
    risk_bucket: str
    category_scores: dict
    matching_categories: list = field(default_factory=list)
    evidence_checks: dict = field(default_factory=dict)  # code -> (score, actual, required)
    reasons: list = field(default_factory=list)

    @property
    def status(self):
        return "FAIL" if self.reasons else "PASS"


def load_config():
    load_dotenv()

    def require(key):
        val = os.environ.get(key, "")
        if not val or val == "CHANGE_ME":
            sys.exit(f"Missing/unset {key} in .env — copy .env.example to .env and fill it in.")
        return val

    return {
        "mysql": {
            "host": require("MYSQL_HOST"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": require("MYSQL_USER"),
            "password": require("MYSQL_PASSWORD"),
            "database": os.environ.get("MYSQL_DATABASE", "operator360"),
        },
        "clickhouse": {
            "host": require("CLICKHOUSE_HOST"),
            "port": int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            "database": require("CLICKHOUSE_DATABASE"),
            "username": require("CLICKHOUSE_USERNAME"),
            "password": require("CLICKHOUSE_PASSWORD"),
            "secure": os.environ.get("CLICKHOUSE_SECURE", "false").lower() == "true",
        },
        "deviation_threshold": float(os.environ.get("DEVIATION_THRESHOLD", "0.05")),
        "brackets": parse_brackets(os.environ.get("BRACKETS", "")),
        "high_severity_buckets": parse_bucket_set(os.environ.get("HIGH_SEVERITY_BUCKETS", "critical")),
        "output_csv": os.environ.get("OUTPUT_CSV", "risk_audit_report.csv"),
    }


def fetch_operators(mysql_cfg):
    """opt_id -> {name, ro, risk_score, risk_bucket}, every row in opt_master."""
    conn = pymysql.connect(
        host=mysql_cfg["host"],
        port=mysql_cfg["port"],
        user=mysql_cfg["user"],
        password=mysql_cfg["password"],
        database=mysql_cfg["database"],
        cursorclass=pymysql.cursors.SSCursor,  # streams rows, opt_master can be large
    )
    operators = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, ro, risk_score, risk_bucket FROM opt_master")
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


def fetch_category_scores(ch_client):
    """opt_id -> {category_code: score}, latest risk_analysis row per operator."""
    cols = ", ".join(f"argMax({col}, updated_at) AS {col}" for _, col in CATEGORIES)
    query = f"SELECT opt_id, {cols} FROM risk_analysis GROUP BY opt_id"

    result = ch_client.query(query)
    scores = {}
    for row in result.result_rows:
        opt_id = row[0]
        scores[opt_id] = {code: row[i + 1] for i, (code, _) in enumerate(CATEGORIES)}
    return scores


def fetch_anomalous_category_counts(ch_client):
    """(opt_id, category_code) -> count of anomalous packets in that category."""
    query = """
        SELECT opt_id, lower(anomaly_type) AS category, count() AS cnt
        FROM operator360.anomalous_packets_v2_rmt
        WHERE lower(anomaly_type) IN ('document', 'biometrics', 'suspicious')
        GROUP BY opt_id, category
    """
    result = ch_client.query(query)
    return {(row[0], row[1]): row[2] for row in result.result_rows}


def evaluate(operators, category_scores, anomalous_counts, threshold, brackets, high_severity_buckets):
    results = []
    for opt_id, op in operators.items():
        res = OperatorResult(
            opt_id=opt_id,
            name=op["name"] or "",
            ro=op["ro"] or "",
            risk_score=op["risk_score"],
            risk_bucket=op["risk_bucket"],
            category_scores=category_scores.get(opt_id, {}),
        )

        # --- Checks 1 & 2: risk_score <-> category-score deviation + brackets.
        # Skipped (but not fatal to the rest of the function) when there's no
        # risk_score or no risk_analysis row to compare against.
        if res.risk_score is None:
            res.reasons.append("no_risk_score")
        elif opt_id not in category_scores:
            res.reasons.append("no_risk_analysis_data")
        else:
            for code, score in res.category_scores.items():
                if score is not None and abs(score - res.risk_score) <= threshold:
                    res.matching_categories.append(code)

            if not res.matching_categories:
                res.reasons.append(
                    f"no_category_within_{threshold}_of_risk_score_{res.risk_score:.4f}"
                )
            else:
                for code in res.matching_categories:
                    if code not in CATEGORIES_REQUIRING_ANOMALOUS_EVIDENCE:
                        continue
                    score = res.category_scores[code]
                    required = required_anomalous_count(score, brackets)
                    actual = anomalous_counts.get((opt_id, code), 0)
                    res.evidence_checks[code] = (score, actual, required)
                    if actual < required:
                        res.reasons.append(
                            f"insufficient_anomalous_evidence_for_{code}"
                            f"_score={score:.4f}_has={actual}_needs>={required}"
                        )

        # --- Check 3: high-severity bucket with zero anomalous evidence at
        # all. Independent of 1/2 — runs purely off opt_master.risk_bucket,
        # so it still fires even when there's no risk_analysis row to compare.
        if res.risk_bucket.strip().lower() in high_severity_buckets:
            total_evidence = sum(
                anomalous_counts.get((opt_id, code), 0)
                for code in CATEGORIES_REQUIRING_ANOMALOUS_EVIDENCE
            )
            if total_evidence == 0:
                res.reasons.append(
                    f"high_severity_bucket_{res.risk_bucket}_zero_anomalous_evidence"
                )

        results.append(res)
    return results


def write_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["opt_id", "name", "ro", "risk_score", "risk_bucket"]
        header += [f"{code}_score" for code, _ in CATEGORIES]
        header += ["matching_categories", "evidence_detail", "status", "reasons"]
        writer.writerow(header)

        for r in results:
            evidence_detail = ";".join(
                f"{code}:score={score:.4f},has={actual},needs>={required}"
                for code, (score, actual, required) in r.evidence_checks.items()
            )
            row = [r.opt_id, r.name, r.ro, r.risk_score, r.risk_bucket]
            row += [r.category_scores.get(code) for code, _ in CATEGORIES]
            row += [
                ";".join(r.matching_categories),
                evidence_detail,
                r.status,
                ";".join(r.reasons),
            ]
            writer.writerow(row)


def print_summary(results, threshold, output_csv):
    total = len(results)
    failing = [r for r in results if r.status == "FAIL"]

    reason_counts = {}
    for r in failing:
        for reason in r.reasons:
            if reason.startswith("insufficient_anomalous_evidence_for_"):
                # Strip the per-operator score=/has=/needs>= suffix so all
                # operators failing the same category bucket together.
                key = reason.split("_score=", 1)[0]
            elif reason.startswith("no_category_within"):
                key = "no_category_within_threshold"
            elif reason.startswith("high_severity_bucket_") and reason.endswith("_zero_anomalous_evidence"):
                # Strip the specific bucket name/casing so "Critical" and
                # "critical" (or any other configured bucket) bucket together.
                key = "high_severity_bucket_zero_anomalous_evidence"
            else:
                key = reason
            reason_counts[key] = reason_counts.get(key, 0) + 1

    print(f"\nOperator360 risk-score consistency audit (deviation threshold = {threshold})")
    print(f"{'=' * 70}")
    print(f"Total operators checked : {total}")
    print(f"Passing                 : {total - len(failing)}")
    print(f"Failing                 : {len(failing)}")

    if reason_counts:
        print("\nFailure breakdown:")
        for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>6}  {reason}")

    if failing:
        print(f"\nFirst {min(20, len(failing))} failing operators:")
        print(f"  {'opt_id':<24} {'risk_score':>10}  reasons")
        for r in failing[:20]:
            rs = f"{r.risk_score:.4f}" if r.risk_score is not None else "NULL"
            print(f"  {r.opt_id:<24} {rs:>10}  {', '.join(r.reasons)}")

    print(f"\nFull report written to: {output_csv}")


def main():
    cfg = load_config()

    print("Connecting to MySQL (opt_master)...")
    operators = fetch_operators(cfg["mysql"])
    print(f"  {len(operators)} operators loaded")

    print("Connecting to ClickHouse (risk_analysis, anomalous_packets_v2_rmt)...")
    ch_client = clickhouse_connect.get_client(
        host=cfg["clickhouse"]["host"],
        port=cfg["clickhouse"]["port"],
        database=cfg["clickhouse"]["database"],
        username=cfg["clickhouse"]["username"],
        password=cfg["clickhouse"]["password"],
        secure=cfg["clickhouse"]["secure"],
    )

    category_scores = fetch_category_scores(ch_client)
    print(f"  {len(category_scores)} operators have risk_analysis rows")

    anomalous_counts = fetch_anomalous_category_counts(ch_client)
    print(f"  {len(anomalous_counts)} (opt_id, category) pairs with anomalous packets")

    results = evaluate(
        operators,
        category_scores,
        anomalous_counts,
        cfg["deviation_threshold"],
        cfg["brackets"],
        cfg["high_severity_buckets"],
    )

    write_csv(results, cfg["output_csv"])
    print_summary(results, cfg["deviation_threshold"], cfg["output_csv"])


if __name__ == "__main__":
    main()
