# Iceberg Views and Column Naming

## 1. Why use views?

| Benefit | How it helps our team | Example |
|---|---|---|
| Simplified data access | Consumers don't need to understand complex joins, filters, or underlying table structures. | Expose `operator_risk_summary` instead of requiring users to join multiple tables. |
| Consistent business logic | Define calculations and filters once, so different teams don't implement slightly different versions of the same metric. | A single definition of MBU used across dashboards and APIs. |
| Abstraction from underlying tables | Hide implementation details and let the underlying data model evolve without necessarily changing consumer queries. | Change source tables while keeping `analytics.operator_features` stable. |
| Reduced query duplication | Centralize common SQL logic instead of copying it into multiple dashboards, jobs, and services. | Reuse a standard filter for active operators. |
| Logical data layer | Create a clean interface between raw/curated tables and downstream consumers. | Raw data → curated tables → analytics views → consumers. |
| Easier schema management | Show relevant columns and rename technical fields to clearer business names. | Expose `operator_id` instead of an internal source-specific identifier. |
| Controlled data exposure | Expose selected columns or rows through the view definition, subject to catalog and access-control configuration. | Exclude internal metadata columns from a consumer-facing view. |
| Easier migration and compatibility | Keep a stable interface while reorganizing physical tables or migrating consumers incrementally. | Keep a familiar view name while changing the underlying table layout. |

## 2. View naming convention

### Suggested format

- **Fully qualified name:** `catalog.schema.view_name`
- **View name:** `business_entity[_qualifier][_result_type]`

### Examples

- `iceberg.analytics.operator_features`
- `iceberg.analytics.operator_risk_summary`
- `iceberg.analytics.operator_risk_by_region`

### Naming rules

- Use lowercase `snake_case`, for example `operator_risk_summary`, not `OperatorRiskSummary` or `operator-risk-summary`.
- Make the business meaning clear. Avoid names such as `view1`, `data_new`, `final2`, or names containing developer initials.
- Add a qualifier only when it adds useful meaning, such as `daily`, `hourly`, `by_region`, or `summary`.
- Avoid dates and arbitrary version suffixes such as `_v2` for routine updates. If a breaking change is needed, agree on how to version the view and migrate consumers.
- Do not add `vw_` by default. Use it only if a team tool or existing local convention requires it.
- If a time grain or unit could be unclear, include it in the name, for example `operator_activity_daily` or `response_time_ms`.

## 3. Column naming convention

Suggested default: use lowercase `snake_case` for every column, whether it comes from a table or a view. Keep names readable and consistent across related datasets.

| Column type / meaning | Suggested pattern | Examples |
|---|---|---|
| Identifier | `<entity>_id` | `operator_id`, `transaction_id` |
| Date | `<event_or_business>_date` | `event_date`, `report_date` |
| Timestamp | `<event_or_action>_at` | `created_at`, `event_at`, `updated_at` |
| Boolean flag | `is_<state>` or `has_<thing>` | `is_active`, `has_consent` |
| Count | `<thing>_count` | `event_count`, `retry_count` |
| Amount / numeric measure | A clear measure name, with currency where needed | `total_amount`, `revenue_usd` |
| Duration / measurement with unit | `<measure>_<unit>` | `response_time_ms`, `distance_km` |
| Percentage / rate | `<measure>_pct` or another explicitly agreed name | `success_rate_pct` |
| Category / status | `<entity>_type` or `<entity>_status` | `operator_type`, `payment_status` |
| Human-readable label | `<entity>_name` or `<entity>_description` | `operator_name`, `risk_description` |

### Column rules

- Prefer clear business terms over abbreviations. Use abbreviations only when they are well understood and agreed by the team.
- Use suffixes consistently: `_id` for identifiers, `_date` for dates, `_at` for timestamps, `_count` for counts, and unit suffixes such as `_ms` or `_km` when relevant.
- Be explicit about units and currency. Avoid generic names such as `duration`, `amount`, or `value` when their meaning could be misunderstood.
- Use the same name for the same concept across views where possible. For example, don't alternate between `operator_id` and `op_id` for the same identifier.
- Avoid spaces, hyphens, mixed casing, and reserved SQL keywords as column names.
- Avoid `SELECT *` in stable consumer-facing views. List output columns explicitly so schema changes do not silently alter the view contract.

## 4. Possible schema layout

These are suggested schema roles. We should agree on a small set that fits our data architecture.

| Purpose | Possible schema | Example | Notes |
|---|---|---|---|
| Source-aligned physical data | `raw` | `raw.operator_events` | Keep close to source meaning and lineage. |
| Cleaned / standardized data | `staging` or `curated` | `staging.stg_operator_events` | Use `stg_` only if we agree to role-based prefixes. |
| Reusable intermediate logic | `intermediate` | `intermediate.int_operator_events_joined` | For reusable transformations, not every temporary query. |
| Stable consumer-facing views | `analytics` or `data_products` | `analytics.operator_features` | A likely default location for views used by analysts or applications. |
| Restricted data interfaces | `secure` or another governed schema | `secure.operator_features` | Access must be enforced through catalog and query-engine permissions; the name alone does not provide security. |

## 5. Optional role prefixes

These prefixes can describe a model's role, but they're optional. We should adopt them only if they fit the way our team organizes data.

| Prefix | Meaning | Example | Use it when |
|---|---|---|---|
| `stg_` | Staging / lightly standardized source | `stg_operator_events` | The object is close to the source with limited cleanup. |
| `int_` | Intermediate transformation | `int_operator_events_joined` | The object is a reusable intermediate result. |
| `fct_` | Fact / measurable business activity | `fct_operator_transactions` | The object represents business events or measurable activity. |
| `dim_` | Dimension / descriptive entity | `dim_operators` | The object describes an entity used in analysis. |
| `rpt_` | Reporting output | `rpt_operator_risk_summary` | The object is specifically shaped for reporting. |

Avoid mixing prefixes randomly. For example, don't use `vw_stg_operator_events` unless a tool or an agreed convention requires it.

## 6. Examples: preferred vs. avoid

| Prefer | Avoid | Why |
|---|---|---|
| `analytics.operator_risk_summary` | `analytics.vw1` | The purpose is clear. |
| `analytics.operator_activity_daily` | `analytics.operator_activity_new` | The grain is clear; “new” is vague. |
| `analytics.operator_risk_by_region` | `analytics.operator_risk_region_final2` | Avoid arbitrary lifecycle labels. |
| `operator_id` | `opid` or `OperatorID` | The preferred name is consistent and readable. |
| `created_at` | `created` or `create_timestamp_text` | The preferred name follows a consistent timestamp convention. |
| `response_time_ms` | `response_time` | The unit is explicit. |

## 7. What to document for each production view

For views that are used by downstream consumers, capture:

- **Purpose:** Business use and intended consumers.
- **Owner:** Owning team or role.
- **Dependencies:** Underlying tables and views.
- **Output contract:** Column names, data types, nullability assumptions, and row grain.
- **Operations:** Expected freshness and query cost/latency where relevant.
- **Lifecycle:** Change or deprecation plan if consumers may be affected.

## 8. How to choose tables to start with

We can use the Trino query history collector to identify the tables and columns most frequently used by upstream consumers, then prioritize those for migration.

Before changing existing objects, check downstream dependencies and consumers. It would be sensible to pilot the naming rules on a few representative datasets and validate compatibility with our Iceberg catalog and query engines.

## 9. Questions for the team

- Should `analytics` or `data_products` be the default schema for consumer-facing views?
- Do we want role prefixes (`stg_`, `int_`, `fct_`, `dim_`, `rpt_`), or should names stay business-first unless a prefix adds value?
- Should `_at` be the default suffix for timestamps? Are there existing conventions we need to preserve?
- Which unit, currency, and percentage suffixes should we standardize?
- Which existing views should we use for the pilot?
