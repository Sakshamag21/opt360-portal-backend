INSERT INTO {destination_table} 
    with tab1 as (
        select upper(opt_id) as opt_id, event_timestamp, upper(auth_result) as auth_result
        from flink_stream.operator360.opt_auth_txn_v3 
        where date(event_timestamp)>=date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}') and (HOUR(event_timestamp) < 8 OR HOUR(event_timestamp) >= 22 ) 
    ),
    tab2 as (
        select opt_id, 
               count(case when auth_result = 'Y' then 1 end) as count_Y,
               count(case when auth_result = 'N' then 1 end) as count_N,
               count(*) as no_of_transaction
        from tab1 
        group by opt_id
    )
    select opt_id as entity_id,
          '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          sum(no_of_transaction) as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          concat('Y: ', cast(sum(count_Y) as varchar), ', N: ', cast(sum(count_N) as varchar)) as comments
        from tab2 
        group by opt_id
    