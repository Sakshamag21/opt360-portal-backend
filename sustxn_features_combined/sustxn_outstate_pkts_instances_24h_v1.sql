
INSERT INTO {destination_table} 
with tab1 as (
    select entity_id, feature_value 
    from strot.operator360.features_sustxn_v1
    where feature_id= 'sustxn_outstate_pkts_instances_24h_v2' and 
    date(timestamp)>= date('{min_pkt_date}') and date(timestamp)< date('{max_pkt_date}')
),
tab2 as (
    select entity_id, sum(feature_value) as total_count
    from tab1 
    group by 1
)
select entity_id as entity_id,
        '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
        '{FEATURE_NAME}' AS feature_name,
        '{FEATURE_VERSION}' AS feature_version,
        total_count as feature_value,
        current_timestamp as timestamp,
        cast(Null as Varchar) as comments
    from tab2 
    