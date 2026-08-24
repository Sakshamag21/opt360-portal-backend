from __future__ import annotations

import heapq

import polars as pl

import strot_query as sq

# --------------------------------------------------------------------------
# 1. Extract — reduce to intervals inside Trino, nothing else
# --------------------------------------------------------------------------

EXTRACT_SQL = """
SELECT
    machine_code,
    sid,
    MIN(last_updated_date) AS start_ts,
    MAX(last_updated_date) AS end_ts,
    COUNT(*)               AS event_cnt
FROM flink_stream.stream_uc.request_tracker_cdc_v2
WHERE last_updated_date >= TIMESTAMP '{start}'
  AND last_updated_date <  TIMESTAMP '{end}'
  AND sid          IS NOT NULL
  AND machine_code IS NOT NULL
GROUP BY machine_code, sid
"""


def load(start: str, end: str) -> pl.DataFrame:
    pdf = sq.query(EXTRACT_SQL.format(start=start, end=end))

    if 'df' not in pdf:
        print(f"Error in pdf: {pdf}")

    pdf=pdf['df']

    df = pl.from_pandas(pdf)

    df = df.with_columns(
        pl.col("start_ts").cast(pl.Datetime("us")),
        pl.col("end_ts").cast(pl.Datetime("us")),
    )

    return df.sort(["machine_code", "start_ts", "sid"])


# --------------------------------------------------------------------------
# 2a. Flag version — vectorised, no Python loop
# --------------------------------------------------------------------------


def flag_parallel(df: pl.DataFrame) -> pl.DataFrame:
    """Mark each sid as parallel or not. Single linear pass over sorted data.

    prior_max_end is the running max of every end_ts seen earlier on this
    machine. Comparing against LAG(end_ts) alone would miss a long-running
    sid two rows back that is still open.
    """
    return df.with_columns(
        prior_max_end=pl.col("end_ts").cum_max().shift(1).over("machine_code"),
        next_start=pl.col("start_ts").shift(-1).over("machine_code"),
    ).with_columns(
        is_parallel=(
            (pl.col("prior_max_end") >= pl.col("start_ts")).fill_null(False)
            | (pl.col("next_start") <= pl.col("end_ts")).fill_null(False)
        )
    )


# --------------------------------------------------------------------------
# 2b. Pair version — classic sweep line with a min-heap on end_ts
# --------------------------------------------------------------------------


def parallel_pairs(df: pl.DataFrame) -> pl.DataFrame:
    """Emit every overlapping (sid, parallel_sid) pair once.

    Walk intervals in start order. Keep an 'active' heap of intervals whose
    end_ts has not yet passed the current start_ts. Anything still active
    when a new interval opens overlaps it, by definition.

    Each interval is pushed once and popped once, so the heap work is
    O(S log S) with a tiny constant — a machine runs 1-3 concurrent
    enrolments, so the active set stays small — plus O(K) to emit.
    """
    rows = df.select(
        "machine_code", "sid", "start_ts", "end_ts", "event_cnt"
    ).iter_rows()

    out: list[tuple] = []
    active: list[tuple] = []  # min-heap keyed on end_ts
    current_machine = None

    for machine, sid, start, end, cnt in rows:
        if machine != current_machine:
            active.clear()
            current_machine = machine

        # Evict intervals that closed before this one opened.
        # `<` means a session ending exactly when the next starts is NOT
        # parallel; switch to `<=` if touching should count as overlap.
        while active and active[0][0] < start:
            heapq.heappop(active)

        # Everything left in the heap is concurrent with this interval.
        for a_end, a_sid, a_start in active:
            out.append(
                (
                    machine,
                    a_sid,
                    a_start,
                    a_end,
                    sid,
                    start,
                    end,
                    max(a_start, start),  # overlap_start
                    min(a_end, end),      # overlap_end
                )
            )

        heapq.heappush(active, (end, sid, start))

    return pl.DataFrame(
        out,
        schema=[
            "machine_code",
            "sid",
            "sid_start",
            "sid_end",
            "parallel_sid",
            "parallel_start",
            "parallel_end",
            "overlap_start",
            "overlap_end",
        ],
        orient="row",
    )


# --------------------------------------------------------------------------
# 2c. Concurrency depth — how many sids were open at once
# --------------------------------------------------------------------------


def max_concurrency(df: pl.DataFrame) -> pl.DataFrame:
    """Peak simultaneous enrolments per machine, via +1/-1 event stream.

    Pure Polars, O(S log S) sort and O(S) scan. Tells you whether a machine
    ran 2 sessions or 15 — a far stronger signal than the boolean flag.
    """
    opens = df.select(
        "machine_code", pl.col("start_ts").alias("ts"), pl.lit(1).alias("delta")
    )
    closes = df.select(
        "machine_code", pl.col("end_ts").alias("ts"), pl.lit(-1).alias("delta")
    )

    return (
        pl.concat([opens, closes])
        # closes (-1) sort before opens (+1) at equal ts, so back-to-back
        # sessions don't register a phantom overlap
        .sort(["machine_code", "ts", "delta"])
        .with_columns(depth=pl.col("delta").cum_sum().over("machine_code"))
        .group_by("machine_code")
        .agg(
            max_concurrent=pl.col("depth").max(),
            total_sids=(pl.col("delta") == 1).sum(),
        )
        .sort("max_concurrent", descending=True)
    )


# --------------------------------------------------------------------------
# 3. Driver
# --------------------------------------------------------------------------

if __name__ == "__main__":
    intervals = load("2026-08-19 00:00:00", "2026-08-20 00:00:00")
    print(f"{intervals.height:,} sid intervals loaded")

    flagged = flag_parallel(intervals)
    n_par = flagged["is_parallel"].sum()
    print(f"{n_par:,} sids flagged parallel ({n_par / flagged.height:.1%})")

    pairs = parallel_pairs(intervals)
    print(f"{pairs.height:,} overlapping pairs")
    print(pairs.head(20))

    depth = max_concurrency(intervals)
    print(depth.head(20))