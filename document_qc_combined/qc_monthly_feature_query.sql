insert into {destination_table}
    with tab1 as (
        select entity_id, sum(feature_value) as coun {eids_required}
        from {destination_table}
        where feature_id='{dependent_feature_id}' and 
        month(timestamp)= month(CURRENT_TIMESTAMP) and year(timestamp)= year(CURRENT_TIMESTAMP)
        group by entity_id
    )
    SELECT
      entity_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      {req_comments}
      from tab1
    

