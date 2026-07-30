INSERT INTO {destination_table} 
WITH tab1 AS (
    SELECT 
        opt_id, 
        start_date,
        end_date,
        eid
    FROM strot.operator360.txn_parallel_enrl_v1 where date(timestamp)>= date('{min_pkt_date}') and date(timestamp)<= date('{max_pkt_date}')
),
sorted_data AS (
    SELECT 
        opt_id,
        start_date,
        end_date,
        eid,
        LAG(end_date) OVER (PARTITION BY opt_id ORDER BY start_date, end_date DESC) AS prev_end
    FROM tab1
),
gap_detection AS (
    SELECT 
        opt_id,
        start_date,
        end_date,
        eid,
        CASE 
            WHEN prev_end IS NULL OR start_date > prev_end THEN 1 
            ELSE 0 
        END AS is_gap
    FROM sorted_data
),
group_assignment AS (
    SELECT 
        opt_id,
        start_date,
        end_date,
        eid,
        SUM(is_gap) OVER (PARTITION BY opt_id ORDER BY start_date, end_date DESC) AS group_id
    FROM gap_detection
),
merged_transactions AS (
    SELECT 
        opt_id,
        group_id,
        MIN(start_date) AS start_date,
        MAX(end_date) AS end_date
    FROM group_assignment
    GROUP BY opt_id, group_id
),
tab3 AS (
    SELECT 
        opt_id,
        COUNT(*) AS count
    FROM merged_transactions
    GROUP BY opt_id
)
    select opt_id as entity_id,
          '{FEATURE_NAME}_7d_v{FEATURE_VERSION}' AS feature_id,
          '{FEATURE_NAME}' AS feature_name,
          '{FEATURE_VERSION}' AS feature_version,
          count as feature_value,
          current_timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
          cast(Null as Varchar) as comments
        from tab3
    