insert into {destination_table}
    with tab1 as(
        select upper(session_operatorid) as opt_id, enrolment_eid, parse_datetime(substr(enrolment_eid, 15),'yyyyMMddHHmmss') as pkt_timestamp,event_timestamp
        from flink_stream.stream_enu.ens_packet_enriched 
        where date(event_timestamp)>= date('{min_pkt_date}') and date(event_timestamp)< date('{max_pkt_date}') and upper(session_operatorid)!='SSUP_OPERATOR' and (enrolment_type!='N' and enrolment_type!='New') 
    ),
    tab2 as (
        select opt_id, enrolment_eid, date(pkt_timestamp) as pkt_date, event_timestamp from tab1
    ),
    tab3 as (
        select opt_id, count(*) as coun
        from tab2 
        group by opt_id 
    ),
    tab4 as (
        select opt_id,coun from tab3
    )

    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      '' AS comments
      from tab4

