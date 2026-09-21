# One-off migration: repoint instance-scoring rows in the opt360_features
# registry (strot.operator360.opt360_features, Trino/Iceberg) from a raw
# daily/instances feature_id + require_aggregation:True (30-day rollup
# computed at score time) to the equivalent pre-computed *_cumulative
# feature_id + require_aggregation:False - same pattern already live for
# sustxn_res_namechange_score_v2 / sustxn_res_mobilechange_score_v2.
#
# Dry-run by default: prints current vs. intended dependent_features for
# every row and only writes with --apply. Each row's current value is
# re-read right before the UPDATE and compared against EXPECTED_OLD below;
# if it doesn't match (someone edited the registry since this script was
# written), that row is skipped unless --force is also passed.
import argparse
from trino.dbapi import connect

TRINO_HOST = "10.10.116.75"
TRINO_PORT = 8080
TRINO_USER = "opt360_feature_metadata"
TABLE = "strot.operator360.opt360_features"

MIGRATIONS = [
    {
        "feature_id": "sustxn_oddhour_pkts_score_v2",
        "expected_old": "[scoring_method:rank_scoring, feature_id:sustxn_oddhour_pkts_instances_24h_v2, range_start:0, range_end:1, require_aggregation:True, is_inverse:False, apply_threshold:False, period_in_days:30]",
        "new": "[scoring_method:rank_scoring, feature_id:sustxn_oddhour_pkts_cumulative_90d_v1, range_start:0, range_end:1, require_aggregation:False, is_inverse:False, apply_threshold:False]",
    },
    {
        "feature_id": "sustxn_oddhour_pkts_zscore_v2",
        "expected_old": "[scoring_method:zscore, feature_id:sustxn_oddhour_pkts_instances_24h_v2, require_aggregation:True, period_in_days:30, aggregation_method:sum]",
        "new": "[scoring_method:zscore, feature_id:sustxn_oddhour_pkts_cumulative_90d_v1, require_aggregation:False]",
    },
    {
        "feature_id": "sustxn_outstate_pkts_score_v2",
        "expected_old": "[scoring_method:rank_scoring, feature_id:sustxn_outstate_pkts_instances_24h_v2, range_start:0, range_end:1, require_aggregation:True, is_inverse:False, apply_threshold:False, period_in_days:30]",
        "new": "[scoring_method:rank_scoring, feature_id:sustxn_outstate_pkts_cumulative_90d_v1, range_start:0, range_end:1, require_aggregation:False, is_inverse:False, apply_threshold:False]",
    },
    {
        "feature_id": "sustxn_outstate_pkts_zscore_v2",
        "expected_old": "[scoring_method:zscore, feature_id:sustxn_outstate_pkts_instances_24h_v2, require_aggregation:True, period_in_days:30, aggregation_method:sum]",
        "new": "[scoring_method:zscore, feature_id:sustxn_outstate_pkts_cumulative_90d_v1, require_aggregation:False]",
    },
    {
        "feature_id": "hardware_multiple_biodev_score_v2",
        "expected_old": "[scoring_method:rank_scoring, feature_id:hardware_multiple_biodev_instances_24h_v2, range_start:0, range_end:1, require_aggregation:True, is_inverse:False, apply_threshold:False, period_in_days:30]",
        "new": "[scoring_method:rank_scoring, feature_id:hardware_multiple_biodev_instances_count_30d_v1, range_start:0, range_end:1, require_aggregation:False, is_inverse:False, apply_threshold:False]",
    },
    {
        "feature_id": "hardware_multiple_biodev_zscore_v2",
        "expected_old": "[scoring_method:zscore, feature_id:hardware_multiple_biodev_instances_24h_v2, require_aggregation:True, period_in_days:30]",
        "new": "[scoring_method:zscore, feature_id:hardware_multiple_biodev_instances_count_30d_v1, require_aggregation:False]",
    },
    {
        "feature_id": "document_category_score_v2",
        "expected_old": "[scoring_method:rank_scoring, feature_id:[doc_qc_error_doe1_incidents_count_daily_v1, doc_qc_error_pop_incidents_count_daily_v1], range_start:0, range_end:1, require_aggregation:True, is_inverse:False, apply_threshold:False, weights:{doc_qc_error_pop_incidents_count_daily_v1:2, doc_qc_error_doe1_incidents_count_daily_v1:2}, method:weighted_average]",
        "new": "[scoring_method:rank_scoring, feature_id:[doc_qc_error_doe1_incidents_count_cumulative_90d_v1, doc_qc_error_pop_incidents_count_cumulative_90d_v1], range_start:0, range_end:1, require_aggregation:False, is_inverse:False, apply_threshold:False, weights:{doc_qc_error_pop_incidents_count_cumulative_90d_v1:2, doc_qc_error_doe1_incidents_count_cumulative_90d_v1:2}, method:weighted_average]",
    },
    {
        "feature_id": "sustxn_parallel_enrolment_score_v2",
        "expected_old": "[scoring_method:rank_scoring, feature_id:sustxn_parallel_enrolment_eid_count_daily_v1, range_start:0.5, range_end:1, require_aggregation:True, is_inverse:False, apply_threshold:False]",
        "new": "[scoring_method:rank_scoring, feature_id:sustxn_parallel_enrolment_count_cumulative_90d_v1, range_start:0.5, range_end:1, require_aggregation:False, is_inverse:False, apply_threshold:False]",
    },
    {
        "feature_id": "auth_oddhour_txn_score_v2",
        "expected_old": "[scoring_method:winsorized_zscoring, feature_id:auth_oddhour_incidents_24h_v1, is_multiple_col:False, period_in_days:30]",
        "new": "[scoring_method:winsorized_zscoring, feature_id:auth_oddhour_incidents_count_cumulative_90d_v1, is_multiple_col:False]",
    },
]


def trino_cursor():
    conn = connect(host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER)
    return conn.cursor()


def fetch_current(cur, feature_id):
    cur.execute(
        f"SELECT dependent_features FROM {TABLE} WHERE feature_id = '{feature_id}'"
    )
    rows = cur.fetchall()
    if not rows:
        return None
    return rows[0][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    parser.add_argument("--force", action="store_true", help="Apply even if current value differs from expected_old")
    parser.add_argument("--touch-updated-by", action="store_true", help="Also set updated_by/updated_at (unverified column type - opt in)")
    parser.add_argument("--updated-by", default="saksham.nisg")
    args = parser.parse_args()

    cur = trino_cursor()

    for m in MIGRATIONS:
        feature_id = m["feature_id"]
        current = fetch_current(cur, feature_id)

        print(f"\n=== {feature_id} ===")
        if current is None:
            print("  SKIP: no row found in registry for this feature_id")
            continue

        print(f"  current : {current}")
        print(f"  new     : {m['new']}")

        matches_expected = current.strip() == m["expected_old"].strip()
        if not matches_expected:
            print("  WARNING: current value does not match expected_old on file.")
            if not args.force:
                print("  SKIP: rerun with --force to overwrite anyway.")
                continue

        if not args.apply:
            print("  (dry-run: no write performed)")
            continue

        new_escaped = m["new"].replace("'", "''")
        set_clauses = [f"dependent_features = '{new_escaped}'"]
        if args.touch_updated_by:
            # updated_at/updated_by in the CSV export look like formatted
            # strings ("19/8/2026, 11:50 AM"), not a native TIMESTAMP - the
            # exact column type wasn't verified against the live schema, so
            # this is opt-in and left for you to confirm the format first.
            set_clauses.append(f"updated_by = '{args.updated_by}'")
            set_clauses.append("updated_at = current_timestamp")
        update_sql = (
            f"UPDATE {TABLE} SET {', '.join(set_clauses)} "
            f"WHERE feature_id = '{feature_id}'"
        )
        cur.execute(update_sql)
        cur.fetchall()
        print("  APPLIED")

    print("\nDone." if args.apply else "\nDry-run complete. Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
