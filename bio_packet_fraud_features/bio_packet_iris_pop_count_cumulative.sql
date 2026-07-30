INSERT INTO {destination_table}
    SELECT
      t.entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      t.cumulative_value AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      CAST(NULL AS VARCHAR) AS comments
    FROM (
        SELECT
          daily.entity_id,
          COALESCE(cumulative.max_feature_value, 0) + daily.feature_value AS cumulative_value
        FROM (
          SELECT entity_id, feature_value
          FROM {destination_table}
          WHERE feature_name = 'bio_packet_iris_pop_count_daily'
            AND date("timestamp") = CAST(date('{max_pkt_date}') AS DATE)
        ) daily
        LEFT JOIN (
          SELECT entity_id, MAX(feature_value) AS max_feature_value
          FROM {destination_table}
          WHERE feature_name = 'bio_packet_iris_pop_count_cumulative'
            AND entity_id IN (
              SELECT DISTINCT entity_id
              FROM {destination_table}
              WHERE feature_name = 'bio_packet_iris_pop_count_daily'
                AND date("timestamp") = CAST(date('{max_pkt_date}') AS DATE)
            )
            AND date("timestamp") < CAST(date('{max_pkt_date}') AS DATE)
          GROUP BY entity_id
        ) cumulative
          ON daily.entity_id = cumulative.entity_id
    ) t