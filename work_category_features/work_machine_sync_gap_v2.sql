insert into {destination_table}
    with tab1 as (
        select upper(session_operatorid) as opt_id, pkt_source, event_timestamp, row_number() over (partition by session_operatorid order by event_timestamp desc) as rn
        from flink_stream.stream_enu.ens_packet_enriched
        where date(event_timestamp) >= date('{min_pkt_date}') and date(event_timestamp) < date('{max_pkt_date}')
    ),
    tab2 as (
        select opt_id, pkt_source, event_timestamp as latest_ecmp_pkt_timestamp
        from tab1 
        where rn=1 and pkt_source='ECMP'
    ),
    tab3 as (
        select upper(operator_id) as opt_id , event_timestamp as latest_sync_timestamp, t2.latest_ecmp_pkt_timestamp ,row_number() over (partition by upper(operator_id) order by event_timestamp desc) as rn 
        from  flink_stream.stream_enu.enu_operator_sync_raw t1 right join tab2 t2 on upper(t1.operator_id) = t2.opt_id
    ),
    tab4 as (
        select * from tab3 where rn=1 
    ),
    tab5 as (
        select * ,
        date_diff('day', date(latest_sync_timestamp), date(latest_ecmp_pkt_timestamp)) as diff_between_sync_pkt,
        date_diff('day', date(latest_sync_timestamp), date(current_timestamp)) as days_since_last_sync
        from tab4 
    )

    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      days_since_last_sync AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      'lastest_sync_timestamp: ' || CAST( latest_sync_timestamp AS VARCHAR) || 'latest_ecmp_pkt_timestamp: ' || CAST(latest_ecmp_pkt_timestamp AS VARCHAR) || 'day difference between last sync and latest ecmp packet: ' || CAST( diff_between_sync_pkt AS VARCHAR) AS comments
      from tab5
