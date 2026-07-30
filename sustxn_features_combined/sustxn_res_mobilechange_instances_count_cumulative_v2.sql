INSERT INTO {destination_table} 
with tab1 as(
    select upper(operator_id) as opt_id,uid,count(*) as total_mobile_updates 
    from strot.mysql_uid_v2.uid_origin_tracker_enriched 
    where date(enr_date)>=date('{min_pkt_date}') and date(enr_date)<=date('{max_pkt_date}') 
    and from_utf8(updt_mobile_details)='10' and (enr_type!= 'N' or enr_type!='New')
    group by 1,2 order by 3 desc
),
tab2 as (
    select opt_id,array_distinct(array_agg(uid)) as uid_list,sum(total_mobile_updates) as sum_of_updates 
    from tab1 
    where total_mobile_updates>4 group by 1 order by 3 desc
)

select opt_id as entity_id,
        '{FEATURE_NAME}_24h_v{FEATURE_VERSION}' AS feature_id,
        '{FEATURE_NAME}' AS feature_name,
        '{FEATURE_VERSION}' AS feature_version,
        sum_of_updates as feature_value,
        current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
        cast(Null as Varchar) as comments
    from tab2
