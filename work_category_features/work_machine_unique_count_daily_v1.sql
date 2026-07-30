insert into {destination_table}
    with tab1 as (
        select upper(operator_id) as opt_id, array_distinct(array_agg(station_machine_code)) as unique_station_machine_code
        from flink_stream.stream_enu.enu_uc_opt_action_v2 
        where date(event_timestamp) >= date('{min_pkt_date}') and date(event_timestamp) < date('{max_pkt_date}') and station_machine_code is not Null and station_machine_code!='' and upper(stage)='ACKSLIPUPLOAD'
        group by 1
    ),
    tab2 as (
        select opt_id, unique_station_machine_code, cardinality(unique_station_machine_code) as number_of_unique_station_machine_code
        from tab1
    )

    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      number_of_unique_station_machine_code AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      'unique_station_machine_code: ' || CAST(array_join(unique_station_machine_code, ',') AS VARCHAR) AS comments
      from tab2
