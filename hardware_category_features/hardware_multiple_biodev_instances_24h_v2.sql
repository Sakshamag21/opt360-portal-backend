
    INSERT INTO {destination_table} 
    with tab1 as(
        SELECT
            upper(enrl_oper_code) as opt_id,
            bio_dev_modality as mod,
            bio_dev_snum as snum,
            enrl_client_machine_id as machine
        FROM flink_stream.stream_enu.bi_enu_enrlraw_v2
        where date(event_timestamp)>=date('{min_pkt_date}') and date(event_timestamp)< date('{max_pkt_date}') and bio_dev_modality!='Face' and enrl_client_machine_id not like '%SSUP%'
    ),
    tab2 as(
        select opt_id,count(distinct snum) as diff_bio_dev, array_distinct(array_agg(machine)) as diff_machines
        from tab1 
        where snum is not null and opt_id is not null
        group by 1 order by 2 desc, cardinality(diff_machines) desc
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          diff_bio_dev as feature_value,
          current_timestamp as timestamp,
          cast(array_join(diff_machines,',') as Varchar) as comments
        from tab2
        where diff_bio_dev>5
    