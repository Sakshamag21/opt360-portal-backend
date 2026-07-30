insert into {destination_table}
with tab1 as (
    select opt_id, count(distinct eid) as eids_count
    from strot.operator360.txn_parallel_enrl_v1
    where date(timestamp)>=date('{min_pkt_date}') and date(timestamp)< date('{max_pkt_date}')
    group by 1
)
select opt_id as entity_id,
    '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
    '{FEATURE_NAME}' AS feature_name,
    '{FEATURE_VERSION}' AS feature_version,
    eids_count as feature_value,
    current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
    cast(Null as Varchar) as comments
from tab1
