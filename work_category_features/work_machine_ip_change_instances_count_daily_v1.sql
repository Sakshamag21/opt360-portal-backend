insert into {destination_table}
    with tab1 as (
        select upper(operator_id) as opt_id, machine_ip_address, lag(machine_ip_address) over(partition by operator_id order by event_timestamp desc) as prev_machine_ip_address, event_timestamp 
        from flink_stream.stream_enu.enu_uc_opt_action_v2 
        where date(event_timestamp) >= date('{min_pkt_date}') and date(event_timestamp) < date('{max_pkt_date}') and machine_ip_address is not Null 
    ),
    tab2 as (
        select opt_id, count(*) as coun, array_distinct(array_agg(machine_ip_address)) as unique_machine_ip_address_used from tab1 
        where prev_machine_ip_address is not null and prev_machine_ip_address != '' and machine_ip_address!= prev_machine_ip_address
        group by 1
    ),
    tab3 as (
        select * from tab2 
    )

    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      'unique_machine_ids: ' || CAST(array_join(unique_machine_ip_address_used, ',') AS VARCHAR) AS comments
      from tab3
