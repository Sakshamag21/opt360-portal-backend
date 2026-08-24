INSERT INTO {destination_table} 
    with tab1 as (
        select upper(opt_id) as opt_id, 
        case when auth_type like '%F%' then 'F'
             when auth_type like '%I%' then 'I'
             when auth_type like '%P%' then 'P'
             end as main_auth_type
        , event_timestamp
        from flink_stream.operator360.opt_auth_txn_v3 
        where date(event_timestamp)>=date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}') and (auth_type like '%F%' or auth_type like '%P%' or auth_type like '%I%')
    ),
    tab2 as (
        select opt_id, main_auth_type, event_timestamp, lag(main_auth_type) over (partition by opt_id, date(event_timestamp) order by event_timestamp) as prev_auth_type
        from tab1
    ),
    tab3 as (
        select opt_id, count(*) as no_of_modality_changes , array_distinct(array_agg(main_auth_type)) as device_codes
        from tab2 
        where main_auth_type!=prev_auth_type and prev_auth_type is not Null 
        group by 1
    )
    select opt_id as entity_id,
          '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          no_of_modality_changes as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(array_join(device_codes,',') as Varchar) as comments
        from tab3
    