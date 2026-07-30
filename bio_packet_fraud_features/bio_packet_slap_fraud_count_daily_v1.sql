INSERT INTO {destination_table}
    SELECT
      t.opt_id AS entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      t.instances AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      CAST(array_join(t.sids, ',') AS VARCHAR) AS comments
    FROM (
      SELECT
        upper(operatorid) AS opt_id,
        count(sid) AS instances,
        array_agg(sid) AS sids
      FROM flink_stream.stream_enu.enu_bfc_analytics_raw_v1
      WHERE date(eventtimestamp) >= date('{min_pkt_date}') and date(eventtimestamp)< date('{max_pkt_date}')
        AND modelname = 'UNSYSTEMATIC_MANUAL_CHECK'
        AND haserror = true
        AND modality = 'FINGER'
        {filter_condition}
		    AND operatorid IS NOT NULL
      GROUP BY upper(operatorid)
    ) t