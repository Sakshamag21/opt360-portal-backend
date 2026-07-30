INSERT INTO {destination_table} 
    with tab1 as (
        select  opt_id, count(*) as error_count from flink_stream.operator360.opt_auth_txn_v3
        where date(event_timestamp)>= date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}')
        and sub_error_code='300-3' group by opt_id 
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          error_count as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(Null as Varchar) as comments
        from tab1