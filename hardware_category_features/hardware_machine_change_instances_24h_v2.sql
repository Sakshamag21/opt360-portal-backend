INSERT INTO {destination_table} 
    with tab1 as(
        SELECT
        distinct
            machine_id,
            date(record_timestamp) as record_timestamp
        FROM flink_stream.analytics_enu.machine_hardware_trust_change
        where date(record_timestamp)>=date('2020-01-01')
    ),
    tab2 as(
        select 
            upper(t1.session_operatorid) as opt_id, 
            array_distinct(array_agg(t2.machine_id)) as fraud_machines,
            count(distinct t2.record_timestamp) as count_of_machine_frauds
        from (select session_operatorid,date(event_timestamp) as event_timestamp,date(date_parse(pkt_sync_time, '%Y-%m-%dT%H:%i:%s')) as pkt_sync_time,station_machine_code 
                from flink_stream.stream_enu.ens_packet_enriched where date(event_timestamp)>= date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}')
        ) t1 
        join tab1 t2 
            on record_timestamp<=event_timestamp and record_timestamp>=event_timestamp-INTERVAL '15' DAY and (pkt_sync_time>=t2.record_timestamp - INTERVAL '7' DAY and pkt_sync_time<t2.record_timestamp + INTERVAL '5' DAY) 
            and t1.station_machine_code=t2.machine_id 
        group by 1
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          count_of_machine_frauds as feature_value,
          current_timestamp as timestamp,
          'fraud_machines: ' || cast(array_join(fraud_machines,',') as Varchar) || ',number of packets: ' || cast(count_of_machine_frauds as varchar) as comments
        from tab2
    