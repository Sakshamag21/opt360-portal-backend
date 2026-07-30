INSERT INTO {destination_table} 
    WITH tab1 AS (
        SELECT refid
        FROM flink_stream.stream_enu.enu_sfc_raw_v1 
        WHERE date(event_timestamp)>= date('{min_pkt_date}') and date(event_timestamp)<= date('{max_pkt_date}') and is_packet_unsystematic= True
    ),
    tab2 AS (
        SELECT DISTINCT 
            t2.edata_sid AS eid, 
            t2.edata_refid AS refid 
        FROM tab1 t1 
        LEFT JOIN (select edata_refid,edata_sid from flink_stream.stream_enu.enu_globalprocessaudit where date(ets)>=date('{min_pkt_date}') and date(ets)<= date('{max_pkt_date}') ) t2 
        ON t1.refid = t2.edata_refid
        where t1.refid is not null
    ),
    tab3 as (
        SELECT 
            UPPER(t2.session_operatorid) AS opt_id, 
            COUNT(t2.enrolment_eid) AS unsystematic_instances 
        FROM tab2 t1 
        JOIN (select enrolment_eid,session_operatorid from flink_stream.stream_enu.ens_packet_enriched where date(event_timestamp)>=date('{min_pkt_date}') and date(event_timestamp)<= date('{max_pkt_date}')) t2 
        ON t1.eid = t2.enrolment_eid 
        WHERE 
            session_operatorid IS NOT NULL 
        GROUP BY UPPER(t2.session_operatorid)
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          unsystematic_instances as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(Null as Varchar) as comments
        from tab3
    