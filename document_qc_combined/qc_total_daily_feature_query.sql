insert into {destination_table}
    with tab1 as (
        select  entity_id, sum(feature_value) as coun
        from strot.operator360.opt_features_test
        where date(timestamp)=date('{max_pkt_date}')
        and feature_name like '%doc_qc%'
        group by entity_id
    )
    SELECT
      entity_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      ''  AS comments 
      from tab1
