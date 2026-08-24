# Operator360 — System Architecture

Operator360 is a **fraud/risk-scoring pipeline for UIDAI (Aadhaar) enrolment operators** — the field agents who
operate biometric enrolment/update stations. It continuously turns raw enrolment-packet, authentication, and
sync event streams into per-operator behavioral "features," normalizes those into statistical "scores," combines
scores per fraud category, and rolls everything up into one daily `risk_score` per operator, which then drives a
`risk_bucket` (Critical/High/Medium/Low/No), Kafka-based real-time "signals," and (for the worst offenders)
automated suspension events. Evidence for the domain: table/field names like `enrolment_eid`, `session_operatorid`,
`bio_dev_snum`, `uidmasterv1`, alert emails to `@uidai.net.in`, and terminology (EID = enrolment ID, RO = Regional
Office, EA = Enrolment Agency, UC = "Update Client").

Everything runs as **Apache Airflow DAGs** (Airflow 3), computing over **Trino/Iceberg** tables backed by a
**Flink** streaming layer (`flink_stream.*` catalogs = raw event streams materialized into Trino-queryable
tables), with heavier scoring jobs executed as **PySpark jobs on Kubernetes**. Orchestration state, idempotency
markers, audit logs, and inter-DAG "did this succeed" status all flow through a shared **Ceph S3** bucket
(`prd-bi-data-platform-test`) rather than Airflow XCom, because scoring tasks run as Kubernetes pods that XCom
can't easily reach. Final results land in **MySQL** (`operator360.opt_master`, the master operator registry) and
are served to a UI/BI layer via **ClickHouse**.

The whole codebase exists in **two parallel generations**: an original **v1** pipeline and a **v2** pipeline that
adds retry-until-midnight resilience and duplicate-write protection. Both are live and wired to their own,
separately-named DAGs — v2 does not replace v1's DAG ids, it runs alongside them.

> **Security note:** several files hardcode plaintext credentials (Ceph S3 access/secret keys, MySQL passwords,
> ClickHouse password) directly in source (`utils/s3_audit_logger.py`, `utils/pipeline_status.py`,
> `pkt_store/opt_store.py`, `mndc/*.py`, `clickhouse_serving_layer/*.py`, `scoring_methods/head_*.py`, and others).
> The same Ceph key pair and the same MySQL `Data_platform_W` account recur across ~15 files. This document
> intentionally does not repeat those literal values — see the source files directly if you need them.

---

## 1. The three-layer pipeline model

The core mental model, defined by `utils/pipeline_status.py` and mirrored in `expected_metadata_layers.json`
(a docs-only file — the DAG code is the real source of truth):

```
Layer 1  →  Layer 2            →  Layer 3
Features    Instance scoring       Category scoring
(hourly/    (normalizes each       (combines instance scores per
 daily per  raw feature into a     category into 1 category_score;
 category)  0-1ish "score")        combines all 5 category_scores
                                    into 1 final risk_score)
```

- **Layer 1** — six category DAGs, each independent, each computing dozens of raw behavioral counts/incidents
  per operator: `auth_category_features`, `bio_packet_fraud_features`, `document_features_combined`,
  `hardware_category_features`, `sustxn_category_feature`, `work_category_feature`. Plain `PythonOperator`
  tasks running Trino `INSERT INTO … SELECT` statements.
- **Layer 2** — one DAG, `instance_risk_scoring`, that takes each raw feature and normalizes it (rank, z-score,
  Wilson score, exponential decay, etc.) into a bounded score. Runs as Kubernetes-pod Spark jobs.
- **Layer 3** — one DAG, `combined_risk_scoring`, that combines a category's instance scores into
  `<category>_category_score`, then combines all 5 category scores into the final `risk_score`. Also
  Kubernetes-pod Spark jobs.

A category only reaches Layer 2 if it passed Layer 1 (all its non-skipped, non-hourly tasks succeeded), and only
reaches Layer 3 if it passed Layer 2. `risk_score` itself only computes if **all 5** category scores succeeded
that run.

Note: **document** has no separate Layer-2 instance-scoring step of its own — `document_category_score` is
computed directly inside the Layer-2 DAG (`instances_scoring_dag.py`), since document QC features apparently
don't need per-feature normalization before being combined.

---

## 2. Orchestration — `controller_pipeline` (v1) / `controller_pipeline_v2`

`operator_dag_manager.py` and `operator_dag_manager_v2.py` are the top-level orchestrators. Neither runs any
business logic itself — they trigger the six Layer-1 DAGs, wait, judge pass/fail per category, then trigger
Layer 2, wait, judge, then trigger Layer 3.

### v1 — `controller_pipeline` (`operator_dag_manager.py`)

- **Schedule:** hourly (`0 * * * *`), `max_active_runs=1`.
- Every hourly tick triggers all 6 Layer-1 DAGs (`TriggerDagRunOperator`, `wait_for_completion=True`,
  concurrency capped by `max_active_tasks=2`). Layer-1 tasks internally gate themselves by `frequency`
  (hourly features run every tick; daily/weekly features check an `is_daily_run` flag).
- `compute_run_mode` checks whether the current tick's IST hour equals `LAYER1_PROMOTION_HOUR = 17` (5 PM IST).
  Only on that one tick per day does the pipeline "promote" — judge Layer 1's daily-cadence results, and if any
  category passed, cascade into Layer 2 → Layer 3. Every other hourly tick, Layer 1 runs (for hourly-cadence
  features only) and the rest of the DAG skips via `gate_promotion`.
- `judge_layer1`/`judge_layer2` read every task's S3-reported status (`read_layer_status`, keyed by
  `pipeline_run_id`+`dag_id`) and compute a per-category verdict via `compute_category_verdicts`: a category
  passes only if it has ≥1 relevant (non-skipped, non-hourly) entry and *all* of them succeeded.
- `generate_daily_report` (fires once per promotion tick, `trigger_rule=all_done` so it runs even on failure)
  builds a long human-readable report — per-category verdict at each layer, task durations, failure diagnostics
  with direct Airflow log links, and a **data-presence sanity check**: it queries
  `strot.operator360.features_risk_v1` directly for `risk_score` rows today, because Layer 3 tasks report
  "success" purely from their shell exit code — `category_main.py` can exit 0 while writing nothing (see §6.3
  for the actual bug behind this). The report is uploaded to S3 under `reports/controller_pipeline/...`.
- **A structural limitation of v1:** if a category fails at the 5 PM promotion tick, it's done for the day — the
  next hourly ticks run Layer 1 again but `gate_promotion` skips judgement/Layer 2/3 until tomorrow's promotion
  hour.

### v2 — `controller_pipeline_v2` (`operator_dag_manager_v2.py`)

Same Layer 1→2→3 shape, entirely separate `dag_id`s throughout (so v1 is untouched and keeps running), plus one
major addition: **hourly retry-until-midnight** for categories that failed the promotion run.

- **Schedule:** hourly, offset 30 min (`30 * * * *`); promotion hour is **10 AM IST** (`LAYER1_PROMOTION_HOUR = 10`,
  earlier than v1's 5 PM).
- `judge_layer1` writes a **daily pending-retry state** JSON to S3 (`daily_pending/{date}.json`), keyed by
  calendar date rather than run id — this is what lets a failure "carry forward" across ticks instead of being
  judged once and forgotten. For each still-failing category it records the *exact* child DagRun id that
  Layer 1 created.
- `retry_pending_categories` runs on **every** hourly tick (`trigger_rule=all_done`, independent of whether the
  promotion path ran/skipped/failed that tick). For each pending category, instead of triggering a whole new
  Layer-1 DagRun, it clears only the **failed task instances** on the *original* DagRun
  (`_clear_failed_tasks_and_wait`, `only_failed=True`) and lets the scheduler re-run just those — this is what
  prevents a retry from re-inserting duplicate rows for features that already succeeded (since every feature SQL
  is a plain `INSERT` with no dedup).
- If a retry makes a category newly valid, `_cascade_layer2_layer3` re-triggers **brand-new** Layer 2 and Layer 3
  DagRuns with the full `valid_today` category set (not just the newly-recovered one) — this is unavoidable
  because Layer 3's `risk_score` task only fires when all 5 category tasks in the *same* DagRun succeeded. The
  code's own docstring flags the consequence as an open problem: categories that already scored successfully
  earlier in the day get **re-scored and duplicated** in this cascade, since Layer 2/3's Spark writes are pure
  appends. `utils/pipeline_status_v2.py`'s idempotency gates are a partial mitigation (skip a task if it already
  succeeded for that `pipeline_run_id`) but don't fully solve the cascade-duplication case.
- A supplementary `retry_update_*.txt` report is uploaded to S3 whenever a retry tick changes anything, alongside
  the same-shaped daily report v1 produces (now also including a "today's retry state" section).

---

## 3. Layer 1 — Feature computation (per category)

All six category DAGs share one design, differing only in which SQL templates and which local "feature runner"
module they use.

### 3.1 The shared feature-runner pattern

Every category's `FEATURES` dict maps a feature key to config: `feature_name`, `feature_version`, `feature_id`,
`sql_local_path`, `dependencies` (other FEATURES keys that must run first), `signal_exists` (push to Kafka?),
and a cadence (`is_daily` for auth/bio/document/hardware, or `frequency` ∈ {hourly, daily, weekly} for
sustxn/work).

Each feature becomes a `PythonOperator` (`run_single_features`) wrapped in three stacked decorators:

```
@skip_if_already_succeeded(dag_id=job_name)   # v2 only — outermost, skips a re-run that already landed
@audit_to_s3(dag_id=job_name)                 # appends a run record to one S3 JSON file per DAG
@report_status(dag_id=job_name, category=category)  # writes per-task success/fail/skip to S3 for the controller to judge
def run_single_features(...): ...
```

Inside, before touching any SQL: a cadence gate (skip if not the right frequency/day), then a **raw-data
availability check** — `raw_table_validation.get_source_tables(category)` maps `feature_id → source_table` via
the `strot.operator360.opt360_features` registry, and `check_raw_tables(source_table)` confirms yesterday's data
actually landed (cached in S3 for 20h to avoid re-querying Trino every task). If the raw table is empty, the
task raises rather than silently computing over nothing.

The actual SQL execution is delegated to a **`run_one_feature(feature_name, feature_version, sql_file,
end_date)`** helper — but this helper is **not shared globally**; three different implementations exist:

| Runner module | Used by | Notable behavior |
|---|---|---|
| `work_category_features/insert_work_features.py` | work, sustxn, **and** auth, hardware (cross-category reuse) | Generic: registry lookup → parses `dependent_features` into a date window or `period_in_days` → `.format()`s the SQL template → executes |
| `document_qc_combined/insert_document_features.py` | document only | Same base pattern, plus branches on `is_cumulative`/`is_monthly` (detected by substring match on `feature_name`!) to build different template params, and an opt-in `eid_collection` mode that carries enrolment-ID evidence into `comments` |
| `bio_packet_fraud_features/insert_bio_packet_fraud_incidents.py` | bio only | Simplest — flat `.format()` substitution only, no cumulative/monthly branching; bio's cumulative SQL files implement that logic themselves |

All three ultimately look up the same central registry table, **`strot.operator360.opt360_features`**
(columns: `destination_table`, `dependent_features`, `update_window`, `feature_name`, `version`, `status`,
`source_table`) via Trino. This registry is the single source of truth mapping a `(feature_name, version)` pair
to where it reads from, where it writes to, and its templating parameters — critically including a
**`filter_condition`** string that most SQL templates inject verbatim, which is how one generic SQL file serves
dozens of differently-named features (see §3.3).

Output rows share one schema everywhere: `entity_id` (usually `upper(opt_id)`), `feature_id`, `feature_name`,
`feature_version`, `feature_value`, `timestamp`, `comments` (often evidence — a joined list of device/machine
IDs or packet EIDs).

If `signal_exists` is true, a downstream `signal_{key}` task calls
`signal_mechanism/signals_producer.py`'s `get_signals_info` + `push_signals_kafka` to push qualifying values
(feature_value > a configured threshold) onto Kafka topic `OPT360.SIGNALS.V1` as real-time fraud signals.

### 3.2 v1 vs v2 differences (Layer 1)

For four of six categories (**auth, hardware, bio, sustxn**) the v2 DAG is a byte-for-byte clone of v1 — same
`FEATURES` dict, same task graph — with only infrastructure changes: separate `dag_id`, the outer
`skip_if_already_succeeded` decorator, and an active `execution_timeout` (commented out in v1). Each v2 file's
header comment says as much explicitly, confirming v2 exists purely so `operator_dag_manager_v2.py`'s retry
mechanism can target it in isolation from v1.

Two categories have **real behavioral differences** in v2, not just infra:

- **`work`**: v2's `FEATURES` dict **drops the three `*_cumulative` packet-upload counters**
  (`work_packet_upload_{new,total,update}_count_cumulative`) entirely — not disabled, just absent. Anything
  downstream expecting those cumulative counts to be fresh from the v2 path won't get them.
- **`document`**: v2 **drops both `*_cumulative`** QC-error counters (`doc_qc_error_{pop,doe1}_incidents_count_cumulative`)
  — commented out rather than removed, but functionally the same gap.

### 3.3 Per-category feature catalog

**Auth** (`auth_features_combined/`, `auth_category_features` DAG, 6 features, uses the work-module's
generic runner) — reads `flink_stream.operator360.opt_auth_txn_v3`:

- `auth_device_change_incidents` — count of `error_code='300'` auth failures per operator/24h.
- `auth_modality_change_incidents` — counts consecutive auth attempts by an operator that switch biometric
  modality (finger/iris/face), via `LAG()` over ordered attempts.
- `auth_oddhour_incidents` — auth transaction count in the 10pm–8am window (**signal-enabled**).
- `auth_biomismatch_incidents` — count of `sub_error_code='300-3'` events (**signal-enabled**).
- `auth_liveness_failure_incidents` (v1 and v2 feature_version, same SQL file) — despite the name, the SQL
  actually detects same-modality device-code changes (`LAG(device_code)` partitioned by operator+modality+day),
  emitted as three rows per operator (Iris/Finger/Face) via `UNION ALL`.

**Hardware** (`hardware_category_features/`, 2 features, serialized `max_active_tasks=1`):

- `hardware_multiple_biodev_instances` — counts distinct biometric device serial numbers (finger/iris, not face)
  used by an operator in the window; **only emits a row when the count exceeds 5** (a built-in noise threshold).
- `hardware_machine_change_instances` (**signal-enabled**) — fuzzy-joins operator packet activity against
  `flink_stream.analytics_enu.machine_hardware_trust_change` (a hardware "trust flag changed" event log) within
  a ±15-day window, flagging operators whose enrolment machine had a trust-change event near their activity.

**Document QC** (`document_qc_combined/`, 15 features driven by ~3 shared SQL templates, the only Layer-1 DAG
with `max_active_tasks=10` — the sequential-chaining pattern other categories use was explicitly removed here
per an in-code comment). Reads `strot.operator360.eid_qc_error_report_v2`, one raw QC-failure log covering 7
error types (AL, DOE1, DOE2, HPM, BE, POP, DE — QC failure category codes), plus a daily "total" rollup, 2
cumulative counters, and 7 month-to-date rollups. Notably: `qc_total_daily_feature_query.sql` (the
all-error-types daily sum) has **no explicit Airflow dependency** on the 7 per-type daily tasks finishing first
— a possible race condition, only avoided by the shared trigger cadence.

**Bio packet fraud** (`bio_packet_fraud_features/`, ~34 features off 3 shared templates keyed by modality —
face/iris/finger — reading `flink_stream.stream_enu.enu_bfc_analytics_raw_v1`, the "Biometric Fraud Check"
model-verdict stream). Covers non-human, proof-of-possession (POP), swap, flipped, mixed, adult-as-child, and
left/right-eye-specific variants, each with matching cumulative counters. One feature,
`bio_sfc_fraud_incidents`, exists in SQL but is commented out of both DAGs (deprecated/unfinished — it traces
"unsystematic packets" back to an operator via a 3-table refid→eid→operator join, a different mechanism than the
modality-based features).

**Suspicious transactions** ("sustxn", `sustxn_features_combined/`, 6 active features, force-chained
sequentially despite `max_active_tasks=5`):

- `sustxn_oddhour_pkts_instances` / `sustxn_outstate_pkts_instances` — each has a v2 feature that counts directly
  from a pre-computed anomaly table (`opt_oddhour_anomalous_ens_eid_daily` / `opt_outstate_anomalous_enu_eid_daily`),
  and a v1 feature that's a pure rollup-sum of v2's daily values over the window — the only case in the codebase
  where "v1/v2" means a genuine algorithm layering rather than an infra clone.
- `sustxn_parallel_enrolment_eid_count_daily` — distinct EID count from a pre-computed parallel-enrolment
  detection table (`txn_parallel_enrl_v1`).
- `sustxn_parallel_enrolment_instances_7d` (**weekly**) — merges overlapping/adjacent enrolment time ranges per
  operator into incident episodes (gap-detection via `LAG`, cumulative-sum clustering), counting distinct
  episodes rather than raw overlap count.
- Two disabled features (`sustxn_res_mobilechange_instances_count_cumulative`,
  `sustxn_res_namechange_instances_count_cumulative`) detect residents whose mobile number / name was changed
  excessively (>4 / >3 times) by the same operator — a resident-identity-tampering signal, present in SQL but
  not wired into either DAG.

**Work** (`work_category_features/`, 13 active features in v1 / 12 in v2, fully serialized
`max_active_runs=1, max_active_tasks=1`) — the largest and most heterogeneous set, reading mostly
`flink_stream.stream_enu.ens_packet_enriched`, `enu_uc_opt_action_v2`, and `bi_enu_enrlraw_v2`:

- `work_machine_change_instances` — flags an operator submitting packets from ≥2 distinct machines in one day.
- `work_machine_ip_change_instances_count_daily` / `work_machineip_isp_change_count_daily` — IP-address and
  ISP/carrier changes per operator via `LAG()` (the IP-change file orders its `LAG` *descending*, which looks
  like a "previous event" ordering bug relative to the ISP-change file's correct ascending order).
  `work_machineip_isp_change_count_cumulative` and its daily version both hardcode `current_date`, ignoring the
  runner's configurable date window (so backfills wouldn't actually shift the query).
- `work_machine_unique_count_daily` — distinct machines used per operator for acknowledgment-slip uploads.
- `work_machine_sync_gap` (disabled) — days since an operator's device last synced vs. its last packet — a
  stale/unauthorized-software risk signal.
- `work_operator_name_unique_count_cumulative` — accumulates distinct display-names ever used under one operator
  code by parsing/union-ing a CSV list stored in the previous row's `comments` field (name-spoofing detection).
- `work_pob_declared_instances` — cumulative counts of declared/approximate/verified date-of-birth statuses,
  parsed out of a JSON-like `comments` string; **only reports once an operator's cumulative total crosses 1000**
  (a hard business threshold suppressing low-volume noise).
- `work_packet_upload_{new,total,update}_count_{daily,hourly}` — six packet-volume counters
  (new/update/total × daily/hourly); `total_count_daily` is the one work feature with `signal_exists=True`.
  Hourly variants ignore the configurable window and hardcode "the last hour."
- Three `*_cumulative` packet-upload counters share one generic template (`work_cumulative.sql`) that joins
  today's daily value against the **earliest**-ever row of its own history (`ORDER BY timestamp ASC`) — inconsistent
  with every other cumulative implementation in the codebase, which all join against the *latest* prior value.
  This looks like a logic bug, not an intentional design choice.

**Cumulative-state implementations are inconsistent codebase-wide** — at least four different patterns exist
(work's earliest-row template, work's ISP-change bespoke latest-row join, document's `ROW_NUMBER`-based latest-row
join, bio's "latest value among today's active entities" join, and two self-referential comment-string-parsing
patterns for name/DOB tracking) with no shared cumulative mechanism.

---

## 4. Layer 2 — Instance scoring (`scoring_methods/`)

Layer 2/3 are **not** plain Airflow Python tasks — each is a `KubernetesPodOperator` that downloads a driver
script from Ceph S3 (`sparkjobs/operator360/category_risk_scoring_combined/...`) and runs it in a pod. The files
in this repo (`head_*.py`, `*_main.py`, `*_scoring_methods.py`) are the **source-of-truth copies uploaded to
S3** — they aren't executed by Airflow directly, but by `spark-submit` inside the pod.

Chain of execution: `KubernetesPodOperator → head_instance_scoring.py (downloaded, builds & runs spark-submit) →
instances_main.py (Spark driver, reads the opt360_features registry row) → dispatches by name into
instance_scoring_methods.py → writes {entity_id, feature_id, feature_value=score, timestamp} to destination_table`.

**DAG:** `instance_risk_scoring` (v1, `schedule=None`) / `instance_risk_scoring_v2` (`0 5 * * *` daily). ~25
features — one instance score plus a paired z-score for most Layer-1 features across auth/hardware/sustxn/work/bio,
e.g. `sustxn_oddhour_pkts_score` & `_zscore`, `hardware_multiple_biodev_score` & `_zscore`, etc. — plus
`document_category_score`, computed directly here since document has no separate instance-scoring step.

`instances_main.py` looks up the registry row for `(feature_name, feature_version)`, gets `source_table` (the
Layer-1 output table to score) and a `dependent_features` blob parsed into params including
**`scoring_method`** — the name of one of six functions in `instance_scoring_methods.py`, dynamically dispatched
via `globals()[name]`:

| Function | What it does |
|---|---|
| `rank_scoring` | Percentile rank of `feature_value` across all entities, linearly mapped into a configurable `[range_start, range_end]` |
| `winsorized_zscoring` | Caps outliers at the 99th percentile, z-scores, then squashes through a sigmoid (`1/(1+e^-0.5z)`); extreme outliers forced to 0.99 |
| `zscore` | Plain population z-score, stddev floored to 1.0 to avoid divide-by-zero |
| `log_based_scoring` | `log1p(value) / log1p(global_max)` scaled into a range — compresses long-tailed counts |
| `wilson_fraud_scoring` | Wilson score lower bound (95% CI) on a ratio feature pair (e.g. failures/total transactions) — statistically conservative for low-volume operators |
| `exponential_decay_scoring` | Time-decayed weighted sum (`exp(-0.1 × days_elapsed)`) over a lookback window, min-max normalized |

A shared helper, `multiple_col_to_one`, lets any of these combine several raw feature_ids first via
`SUM/MIN/MAX/AVERAGE/WEIGHTED_AVERAGE` before scoring.

v2 adds a per-task `make_idempotency_gate` (checks S3 for a prior success record before running) to prevent
duplicate score rows on a same-day retry cascade — necessary because the Spark write path is
`.writeTo(table).append()` with no dedup.

---

## 5. Layer 3 — Category & combined scoring

**DAG:** `combined_risk_scoring` (v1, `schedule=None`) / `combined_risk_scoring_v2` (`0 7 * * *` daily — after
Layer 2's 5 AM run). 6 tasks: `{auth,bio,hardware,sustxn,work}_category_score` plus `risk_score`. In v1,
`risk_score` explicitly depends (via Airflow `>>`) on all 5 category tasks; **v2 drops that explicit dependency
list**, relying only on `max_active_tasks=1` sequential ordering plus the category/idempotency gates — a real
behavioral difference, not just a rename.

Each category task is gated by `make_category_gate`, which skips it via `AirflowSkipException` if that category
isn't in the `valid_categories` list the controller passed down from Layer 2's judgement.

`category_main.py` (the Spark driver) looks up the registry row, parses `dependent_features` into
`params['scoring_function']` and `params['risk_weightage']` (a `{feature_id: weight}` dict), and dispatches to
one of three combination functions in `category_scoring_methods.py`:

| Function | Formula |
|---|---|
| `weighted_average` | `Σ(value_i × weight_i) / Σ(weight_i)` — plain weighted mean |
| `softmax_scoring` | Blends a softmax-weighted average (`exp(4×value)` term lets large values dominate) with the plain weighted mean, `0.9×softmax + 0.1×weighted_mean` by default — lets one severe signal push the category score up disproportionately |
| `max_scoring` | Just the maximum feature_value among the weighted set for that day — "worst signal wins" |

The same three functions serve **both** purposes: combining a category's instance scores into
`<category>_category_score`, and combining all 5 category scores into the final `risk_score` — which function and
which weight dict apply is entirely metadata-driven per feature row in `opt360_features`, not hardcoded per
category in this file. (`category_scoring_methods.py` does carry a `RISK_WEIGHTAGE` module constant, but it's
described as a fallback default — mixes feature ids from multiple categories together — not what actually drives
production scoring.)

**⚠ Known bug:** `category_main.py`'s `main()` hardcodes `feature_name='document_category_score'` and
`feature_version=1` immediately before its registry lookup, overriding whatever `feature_name`/`feature_version`
`head_combined_risk_scoring.py` actually passed on the command line (that CLI-parsing block is present but
commented out). As checked into this repo, every Layer-3 category/`risk_score` task would score the
`document_category_score` registry row instead of its own — meaning the pod can exit 0 having silently computed
the wrong thing (or nothing, if that lookup matches zero rows), which is exactly what `operator_dag_manager.py`'s
`_check_risk_score_data_written()` daily-report check exists to catch (§2, v1's `_generate_daily_report`).

Output everywhere: a numeric `feature_value` (rounded to 2 decimals), no tier/bucket — tiering happens
downstream (§6).

---

## 6. Serving layer, storage, and downstream consumers

### 6.1 `opt_master` (MySQL) — the operator master record

`mndc/opt_master_updt_dag.py` (`opt_master_updt_dag`, daily 9 AM) is a 7-task pipeline that keeps
`operator360.opt_master` (MySQL) up to date:

1. **`update_operator_metadata`** — joins UID-master tables (`user`/`organization`/`contact`/`regional_office`)
   to populate name/phone/email/RO/EA/registrar for each operator (upsert, only fills currently-`NULL`/`Unknown`
   fields so it doesn't clobber good data).
2. **`update_activeness`** — syncs `is_active` from the UID-master `user.user_status`.
3. **`update_risk_score`** — reads the latest `risk_score_v3` rows from `strot.operator360.features_risk_v1`,
   computes a **percentile-rank risk bucket**:
   `feature_value > 0.9 → Critical; else top 1% → High; top 20% → Medium; >0.01 → Low; else → No`, upserts
   `risk_score`/`risk_bucket` into `opt_master`.
4. **`update_sync_details`** / **`update_operator_sync_location`** — pulls device sync + GPS location events
   from two sources (ECMP and UC), converts DMS coordinates to decimal degrees, validates lat/lon bounds, writes
   a MySQL spatial `POINT` into `operator_sync_location`.
5. **`update_top_anomaly`** — for each of 14 known anomaly codes (`work_opt_machinesync`, `sustxn_oddhour_pkts`,
   `bio_mfc_fraud`, `hardware_machine_change`, `doc_qc_error`, etc.), finds operators who have that anomaly's
   score present and merges/ranks to pick the single anomaly code with the highest score per operator, writing it
   to `opt_master.top_anomaly` — a "primary reason this operator is risky" field.
6. **`update_opt360_features`** — mirrors the Trino `opt360_features` registry into a MySQL copy.
7. **`general_update`** — small cleanups (rename "New Delhi"→"Delhi", trim whitespace IDs, re-resolve any
   operator still stuck with `ro='Unknown'`).

`mndc/last_pkt_timesatmp_dag.py` (`opt360_last_packet_timestamp`, daily 3 AM) separately updates
`opt_master.last_packet_timestamp` — but only if a companion S3 status file from `pkt_store/opt_store.py`'s prior
run reports `SUCCESS` (cross-DAG dependency via an S3 JSON summary rather than Airflow sensors).

### 6.2 Packet stores (`pkt_store/`)

Two DAGs push raw operator/packet mapping data into an external key-value/store service (`strot_query` client
library, an HTTP batch-ingest API at `10.10.118.x:8089`), not into Trino/MySQL:

- `opt360_packet_store` (`pkt_store.py`, daily) — ingests yesterday's `(enrolment_eid → opt_id, pkt_type,
  station, machine, timestamp)` mappings, batched 10k at a time, then triggers `operator_eid_store`.
- `operator_eid_store` (`opt_store.py`, triggered) — the reverse index, `(enrolment_eid → opt_id, timestamp)`,
  batched 1k at a time; writes a run summary (SUCCESS/PARTIAL/FAILED/NO_DATA) to S3, which
  `opt360_last_packet_timestamp` (above) checks before proceeding.

### 6.3 ClickHouse serving layer (`clickhouse_serving_layer/`)

Three independent DAGs push data into ClickHouse for BI/UI consumption:

- **`opt360_clickhouse_feature_store`** (`features.py`, daily 1 PM) — for every PROD feature in the
  `opt360_features` registry × every risk bucket (Critical/High/Medium/Low/No), fetches the latest per-entity
  feature values from Trino for the operators in that bucket (batched MySQL `opt_master` lookups), and upserts
  into ClickHouse `opt360_feature_store_test_v1` — essentially materializing "all feature values, freshest
  first" for fast UI lookup.
- **`operator_risk_analysis_to_clickhouse`** (`risk_categories.py`, daily) — fetches the 6 category scores from
  Trino and `opt_master.risk_score`/`risk_bucket` from MySQL, **cross-checks that MySQL's risk_score is within
  0.1 of the max of the 6 category scores** (a consistency guard between the Layer-3 pipeline and the MySQL
  upsert pipeline — rows that fail this check are silently dropped, not flagged), then pushes qualifying rows
  into ClickHouse `operator360.risk_analysis`.
- **`opt360_clickhouse_anomalous_packet_store`** (`anomalous_packet_store.py`, daily 1:30 AM) — runs 6 hardcoded
  Trino queries pulling yesterday's flagged packets across categories (bio MFC fraud, sustxn name/outstate/oddhour
  anomalies, work parallel-enrolment, doc QC errors), joins each against `opt_master` for the RO name, and bulk
  inserts into ClickHouse `anomalous_packets_v3_dist` — a raw evidence table (as opposed to the aggregate
  feature/score tables) for investigators to drill into specific flagged packets.

### 6.4 Signals and suspension (`signal_mechanism/`, `opt_suspension_dag.py`)

`signal_mechanism/signals_producer.py` is the shared library (used by every Layer-1 signal-enabled feature) that:
looks up a feature's active signal configs from a signals API (`get_signals_info`), determines a
threshold/severity, queries today's feature values for entities crossing that threshold, and pushes JSON events
(`OPT360.SIGNALS.V1` Kafka topic) via a `KafkaProducer`. Warning/monitor-type signals (`_warning`/`_monitor` in
the signal id) compute an upper bound too, from the *next* threshold version, so only values in a specific band
trigger.

`opt_suspension_dag.py` (`operator_automated_suspension`, daily 5 PM) is a **Kafka consumer** on
`OPT360.SIGNALS.V1` that reacts to a fixed map of 7 known signal ids (biometric finger/toe-print fraud, QC
DOE1/POP errors, face non-human/POP, iris swap/flipped) — for each matching signal, checks the operator is still
active (`get_user_status` against the UID master), and if so emits a structured `CASE_DISPOSITION` fraud
investigation event (`fraud_investigation_event_v1.0` schema) to `DE.OPT360.OPERATOR_SUSPENSION.V1`, recommending
`SUSPEND`. This is the automated end of the pipeline — a high-confidence fraud signal can trigger an
operator-suspension case without human intervention.

### 6.5 Health/ops reporting

`opt360_checking_report.py` (`operator360_health_report`, daily 2 AM) builds a PDF (via `reportlab`) summarizing
feature registry health — status counts, per-feature row counts for yesterday (flagging zero-row features and
their last-updated date), signal counts, suspension-signal counts, `opt_master` update counts — and emails it
through an internal RCS messaging API. This is the human-facing "is the pipeline healthy" dashboard, separate
from the machine-readable daily reports the controller DAGs write to S3.

`utils/raw_table_validation.py` and `utils/s3_audit_logger.py` underpin the raw-data gating and audit-trail
logging described in §3.1; `utils/pipeline_status.py`/`pipeline_status_v2.py` underpin the controller
orchestration described in §2 (S3-based status reporting instead of XCom, category gating, idempotency).

---

## 7. Other standalone pipelines

- **`parallel_trans_eid_dag.py`** (`opt360_parallel_transactions_eid_updt`, daily 7:30 AM) — a Trino `MERGE`
  that detects operators running **overlapping enrolment sessions** (same operator+machine+station+client
  version, overlapping start/end time ranges) from `bi_enu_enrlraw_v2`, upserting results into
  `txn_parallel_enrl_v1` — the raw detection table that `sustxn_parallel_enrolment_*` features (§3.3) later
  aggregate. Supports ad hoc backfill via `dag_run.conf` (single date or date range).
- **`uc_ip_isp_enrichment_dag.py`** (`uc_isp_data_enrichment`, daily 2 AM) — enriches UC (Update Client) IP
  addresses with ASN/carrier via a local MaxMind GeoLite2 database, re-processing a rolling 3–28-day-old window
  (clearing and re-inserting each day's partition for idempotency), writing to
  `strot.operator360.uc_machineip_isp_map` — the table `work_machineip_isp_change_count_daily` (§3.3) reads from.

---

## 8. Summary: v1 vs v2 at a glance

| Aspect | v1 | v2 |
|---|---|---|
| Controller DAG | `controller_pipeline`, hourly, promotes at 17:00 IST | `controller_pipeline_v2`, hourly (offset :30), promotes at 10:00 IST |
| Retry on promotion-tick failure | None — category is stuck until tomorrow | Hourly retry-until-midnight, clears only failed tasks, cascades into same-day Layer 2/3 |
| Duplicate-write protection | None | `skip_if_already_succeeded` (Layer 1) / `make_idempotency_gate` (Layer 2/3) — but retry cascade can still duplicate category scores that already succeeded that day (documented, unresolved) |
| Layer-1 feature-set differences | — | `work`: drops 3 cumulative packet-upload features. `document`: drops 2 cumulative QC features. All other categories: identical |
| Layer-3 `risk_score` dependency | Explicit Airflow `>>` on all 5 category tasks | Implicit — relies on serialized execution + gates only |
| Layer-2 schedule | Triggered only by controller | Also has its own daily cron (`0 5 * * *`) |
| Layer-3 schedule | Triggered only by controller | Also has its own daily cron (`0 7 * * *`) |

---

## 9. Notable issues found during this review

1. **`scoring_methods/category_main.py`** hardcodes `feature_name='document_category_score'` / `feature_version=1`
   right before its registry lookup, overriding the CLI args every Layer-3 task actually passes — every
   category/`risk_score` task potentially scores the wrong registry row. This is exactly what the controller's
   `_check_risk_score_data_written` daily-report check was built to detect (§2, §5).
2. **`work_cumulative.sql`** joins today's value against the *earliest* historical row instead of the latest —
   inconsistent with every other cumulative pattern in the codebase and likely a logic bug.
3. **Several "daily"/"hourly" SQL files hardcode `current_date`/`current_timestamp`** instead of using the
   feature runner's configurable `min_pkt_date`/`max_pkt_date` window (`work_machineip_isp_change_count_{daily,
   cumulative}_v1.sql`, all `*_hourly_v1.sql` files) — backfills via `data_interval_start` silently don't affect
   these queries' actual date filter.
4. **`work_machine_ip_change_instances_count_daily_v1.sql`** orders its `LAG(machine_ip_address)` window by
   `event_timestamp DESC`, which looks backwards relative to the correct ascending order used in the equivalent
   ISP-change file — likely inverts "previous IP" semantics.
5. **v2's Layer 2/3 retry cascade can duplicate category/risk scores** for categories that already succeeded
   earlier the same day, because Layer 3 must re-trigger a whole new DagRun with the full valid-category set
   (not just the newly-recovered category) and Spark writes are append-only. Flagged in the code's own docstrings
   as an open problem.
6. **Hardcoded plaintext credentials** (Ceph S3 keys, MySQL passwords, ClickHouse password) are duplicated
   verbatim across roughly 15 files rather than centralized/externalized.
7. **Trino queries are built via raw Python string formatting**, not parameterized — SQL injection risk if any
   upstream field (e.g. registry `filter_condition`, or user-controlled `dag_run.conf` values in the backfill
   DAGs) is attacker-influenced. Low likelihood given these are internal batch pipelines, but worth noting.
8. **Inconsistent naming vs. behavior**: `auth_liveness_failure_incidents`' SQL doesn't measure liveness
   failures — it measures same-modality device-code changes. `sustxn_parallel_enrolment_eid_count_daily` is
   registered with `frequency: "weekly"` despite its name.
