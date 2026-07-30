insert into {destination_table}
    with tab1 as (
        select entity_id, feature_value,row_number() over(partition by entity_id order by timestamp desc) as rn
        from {destination_table}
        where feature_id='{FEATURE_NAME}_v{FEATURE_VERSION}' and date(timestamp)<date(CURRENT_TIMESTAMP)
    ),
    tab2 as (
        select * from tab1 where rn=1
    ),
    tab3 as (
        select entity_id, feature_value 
        from {destination_table}
        where feature_id='{dependent_feature_id}' and date(timestamp)=date(current_timestamp)
    ),
    tab4 as (
        select t1.entity_id, t1.feature_value as curr_val, coalesce(t2.feature_value,0) as cum_val
        from tab3 t1 left join tab2 t2 on t1.entity_id=t2.entity_id 
    )
    SELECT
      entity_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      curr_val + cum_val AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      '' as comments
      from tab4
