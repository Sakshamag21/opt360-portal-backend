insert into {destination_table}
    with tab1 as(
        SELECT
            upper(enrl_oper_code) as opt_id,
            enrl_oper_name
        FROM flink_stream.stream_enu.bi_enu_enrlraw_v2
        where event_timestamp>=date('{min_pkt_date}') and date(event_timestamp)< date('{max_pkt_date}') and upper(enrl_oper_code)!='SSUP_OPERATOR' and bio_dev_modality!='Face' and enrl_client_machine_id not like '%SSUP%'
        group by 1,2 
    ),
    tab2 as(
        select opt_id,array_agg(enrl_oper_name) as names from tab1 group by 1
    ),
    tab3 as(
        select opt_id,names,cardinality(names) as count_names from tab2 where cardinality(names) >= 1
    )

    SELECT
      opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      count_names AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      'names_used_by_operator: ' || CAST(array_join(names, ',') AS VARCHAR) AS comments
      from tab3
