insert into {destination_table}
    with tab1 as (
        select  operator_id, count(*) as coun {eids_required}
        from strot.operator360.eid_qc_error_report_v2
        where date(last_updated_at)>= date('{min_pkt_date}') and date(last_updated_at)<date('{max_pkt_date}')
        {filter_condition} 
        group by operator_id
    )
    SELECT
      upper(operator_id) AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      coun AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      {req_comments}
      from tab1
