INSERT INTO {destination_table} 
    WITH tab1 AS (
        SELECT
            upper(enrl_oper_code) AS opt_id,
            CAST(SUM(CASE WHEN enrl_dob_status='DECLARED' THEN 1 ELSE 0 END) AS DOUBLE) AS dec,
            CAST(SUM(CASE WHEN enrl_dob_status='APPROXIMATE' THEN 1 ELSE 0 END) AS DOUBLE) AS approx,
            CAST(SUM(CASE WHEN enrl_dob_status='VERIFIED' THEN 1 ELSE 0 END) AS DOUBLE) AS ver 
        FROM flink_stream.stream_enu.bi_enu_enrlraw_v2 
        WHERE date(processed_timestamp) >= date('{min_pkt_date}') 
          AND date(event_timestamp) >= date('{min_pkt_date}') 
          AND date(event_timestamp) < date('{max_pkt_date}')
        GROUP BY 1
    ),
    tab2 AS (
        -- Fetch the latest cumulative state per entity_id
        SELECT 
            entity_id, 
            comments
        FROM (
            SELECT 
                entity_id,
                comments,
                row_number() over(partition by entity_id order by "timestamp" desc) AS rn
            FROM {destination_table}
            WHERE feature_id = '{FEATURE_NAME}_v{FEATURE_VERSION}'
        ) t
        WHERE rn = 1
    ),
    tab3 AS (
        SELECT 
            t1.opt_id AS entity_id,
            CAST(COALESCE(t1.dec, 0.0) + COALESCE(CAST(json_extract_scalar(t2.comments, '$.dec') AS DOUBLE), 0.0) AS DOUBLE) AS dec,
            CAST(COALESCE(t1.approx, 0.0) + COALESCE(CAST(json_extract_scalar(t2.comments, '$.approx') AS DOUBLE), 0.0) AS DOUBLE) AS approx,
            CAST(COALESCE(t1.ver, 0.0) + COALESCE(CAST(json_extract_scalar(t2.comments, '$.ver') AS DOUBLE), 0.0) AS DOUBLE) AS ver
        FROM tab1 t1
        LEFT JOIN tab2 t2 ON t1.opt_id = t2.entity_id
    )
    SELECT 
        entity_id,
        '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
        '{FEATURE_NAME}' AS feature_name,
        '{FEATURE_VERSION}' AS feature_version,
        dec AS feature_value,
        current_timestamp AS "timestamp",
        '{dec:' || CAST(dec AS VARCHAR) || ',approx:' || CAST(approx AS VARCHAR) || ',ver:' || CAST(ver AS VARCHAR) || '}' AS comments
    FROM tab3
    WHERE dec + approx + ver >= 1000