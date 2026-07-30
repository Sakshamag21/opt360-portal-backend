INSERT INTO {destination_table} 
    with tab1 as (
        select
            upper(enrl_oper_code) as opt_id,
            cast(sum(case when enrl_dob_status='DECLARED' then 1 else 0 end) as double) as dec,
            cast(sum(case when enrl_dob_status='APPROXIMATE' then 1 else 0 end) as double) as approx,
            cast(sum(case when enrl_dob_status='VERIFIED' then 1 else 0 end) as double) as ver 
        from flink_stream.stream_enu.bi_enu_enrlraw_v2 where event_timestamp>=date('{min_pkt_date}') and date(event_timestamp)<date('{max_pkt_date}') group by 1 order by dec+approx desc
    )
    select opt_id as entity_id,
          '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          dec as feature_value,
          current_timestamp as timestamp,
          cast(Null as Varchar) as comments
        from tab1
        where dec+approx+ver>=1000