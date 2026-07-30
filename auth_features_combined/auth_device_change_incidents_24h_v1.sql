INSERT INTO {destination_table} 
    with tab1 as (
        select upper(opt_id) as opt_id, 
        case when auth_type like '%F%' then 'F'
             when auth_type like '%I%' then 'I'
             when auth_type like '%P%' then 'P'
             end as main_auth_type
        , event_timestamp, device_code
        from flink_stream.operator360.opt_auth_txn_v3 
        where date(event_timestamp)>=date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}') and (auth_type like '%F%' or auth_type like '%P%' or auth_type like '%I%') and device_code is not Null and device_code!=''
    ),
    tab2 as (
        select opt_id, main_auth_type, event_timestamp, device_code , lag(device_code) over (partition by opt_id, main_auth_type, date(event_timestamp) order by event_timestamp) as prev_device_code
        from tab1
    ),
    tab3 as (
        select opt_id, main_auth_type , count(*) as no_of_same_modality_device_change , array_distinct(array_agg(device_code)) as device_codes
        from tab2 
        where device_code!=prev_device_code and prev_device_code is not Null 
        group by 1,2
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_Iris_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          no_of_same_modality_device_change as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(device_codes as Varchar) as comments
        from tab1
        where main_auth_type='I'
    union All
    select opt_id as entity_id,
          '{FEATURE_NAME}_Finger_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          no_of_same_modality_device_change as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(device_codes as Varchar) as comments
        from tab1
        where main_auth_type='F'
    union All
    select opt_id as entity_id,
          '{FEATURE_NAME}_Face_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          no_of_same_modality_device_change as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(device_codes as Varchar) as comments
        from tab1
        where main_auth_type='P'
    