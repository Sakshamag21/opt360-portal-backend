
INSERT INTO {destination_table} 
WITH tab1 AS (
    select opt_id, count(*) as no_of_packets 
    from strot.operator360.opt_oddhour_anomalous_ens_eid_daily
    where date(event_timestamp)>= date('{min_pkt_date}') and date(event_timestamp)< date('{max_pkt_date}')
    group by 1
)
select opt_id as entity_id,
        '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
        '{FEATURE_NAME}' AS feature_name,
        '{FEATURE_VERSION}' AS feature_version,
        no_of_packets as feature_value,
        current_timestamp as timestamp,
        cast(Null as Varchar) as comments
    from tab1 where no_of_packets>0
    