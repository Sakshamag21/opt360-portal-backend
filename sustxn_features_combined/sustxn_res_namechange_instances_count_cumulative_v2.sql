INSERT INTO {destination_table} 
    with tab1 as(
        select uid,array_distinct(array_agg(upper(operator_id))) as opt_ids_success, count(*) as total_name_updates 
        from strot.mysql_uid_v2.uid_origin_tracker_enriched 
        where date(enr_date)>=date('{min_pkt_date}') and date(enr_date)<= date('{max_pkt_date}') 
        and from_utf8(updt_resident_name)='10'  and (enr_type!= 'N' or enr_type!='New')
        group by 1 order by 3 desc
    ),
    tab1_2 as(
        select 
            uid,
            total_name_updates,
            opt_id
        from tab1
        CROSS JOIN UNNEST(opt_ids_success) AS t(opt_id)
        where total_name_updates > 3
    ),
    tab2 as(
        select opt_id,array_distinct(array_agg(uid)) as uid_list, count(distinct uid) as count_uid from tab1_2 group by 1
    )

    select opt_id as entity_id,
          '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          count_uid as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(Null as Varchar) as comments
        from tab2
    