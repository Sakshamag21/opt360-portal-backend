INSERT INTO {destination_table} 
    with tab1 as (
            select enrl_client_machine_id as mach_id, upper(enrl_oper_code) as opt_id, date(enrl_end_date) as date 
            from flink_stream.stream_enu.bi_enu_enrlraw_v2
            where date(enrl_end_date)>=date('{min_pkt_date}') and date(enrl_end_date)<=date('{max_pkt_date}') and enrl_eid not like '000000%'
        ),
        tab2 as (
            select opt_id, mach_id, date , count(*) as coun from tab1 where opt_id!='SELECT'
            group by opt_id ,mach_id, date
        ),
        tab3 as (
            select opt_id, array_agg(mach_id) as day_mach_id, date, array_agg(coun) as daily_coun from tab2
            group by opt_id, date
        ),
        tab14 as (
            select *,cardinality(day_mach_id) as total_mach , 
            reduce (daily_coun, cast(0 as bigint), (s,x) -> s+x, s->s ) as packet_count 
            from tab3 where cardinality(day_mach_id) >=2
        ),
        tab5 AS (
            SELECT 
                opt_id, 
                ARRAY_DISTINCT(ARRAY_AGG(ele)) AS unique_mach_id, 
                SUM(packet_count) AS packet_count
            FROM tab14
            CROSS JOIN UNNEST(day_mach_id) AS t(ele)
            GROUP BY opt_id
        )

    select opt_id as entity_id,
          '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          packet_count as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(array_join(unique_mach_id,',') as Varchar) as comments
        from tab5
    