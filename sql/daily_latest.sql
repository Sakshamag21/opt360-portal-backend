WITH latest AS (

    SELECT
        feature_id,
        feature_value,
        comments,
        timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY feature_id, DATE(timestamp)
            ORDER BY timestamp DESC
        ) AS rn

    FROM {table}

    WHERE DATE(timestamp) = CURRENT_DATE - INTERVAL '1' DAY

)

SELECT
    feature_id,
    feature_value,
    comments,
    timestamp AS feature_ts
FROM latest
WHERE rn = 1;