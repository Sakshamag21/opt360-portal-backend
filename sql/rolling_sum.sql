WITH latest AS (

    SELECT *

    FROM (

        SELECT *,
               row_number() OVER (
                   PARTITION BY feature_id,
                                date(timestamp)
                   ORDER BY timestamp DESC
               ) rn

        FROM {table}

    )

    WHERE rn = 1

)

SELECT

    feature_id,

    SUM(feature_value) AS feature_value,

    '' AS comments,

    MAX(timestamp) AS feature_ts

FROM latest

WHERE timestamp >= current_date - interval '{window_days}' day

GROUP BY feature_id;