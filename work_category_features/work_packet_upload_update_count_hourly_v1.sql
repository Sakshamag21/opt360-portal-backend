insert into {destination_table}
    with tab1 as(
        select upper(session_operatorid) as opt_id, enrolment_eid, date_trunc('hour', event_timestamp) AS pkt_timestamp,event_timestamp
        from flink_stream.stream_enu.ens_packet_enriched 
        where date(event_timestamp)= date(current_timestamp - interval '1' hour) 
          and hour(event_timestamp)= hour(current_timestamp - interval '1' hour) and upper(session_operatorid)!='SSUP_OPERATOR' and (enrolment_type!='N' and enrolment_type!='New') 
    ),
    tab2 as (
        select opt_id, pkt_timestamp, count(*) as coun
        from tab1
        group by opt_id , pkt_timestamp
    ),
    tab3 as (
        select opt_id, pkt_timestamp,coun from tab2
    )
    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      pkt_timestamp AS "timestamp",
      'last_updated_timestamp: ' || CAST(current_timestamp AT TIME ZONE 'Asia/Kolkata' AS VARCHAR) AS comments
      from tab3
