insert into {destination_table}
with tab1 as (
    select * from strot.operator360.features_work_v1 
    where date(timestamp)= date(current_date - interval '0' day) and feature_id ='work_machineip_isp_change_count_daily_v1'
),
tab1_1 as (
    select *, row_number() over(partition by entity_id order by timestamp desc) as rn from strot.operator360.features_work_v1 where feature_id='work_machineip_isp_change_count_cumulative_v1' 
),
tab1_2 as (
    select * from tab1_1 where rn=1
),
tab2 as (
    select t2.*, coalesce(t1.feature_value,0) as cumulative 
    from tab1_2 t1 right join tab1 t2 on t1.entity_id = t2.entity_id and t1.feature_id='work_machineip_isp_change_count_cumulative_v1'
)

SELECT
entity_id AS entity_id,
'{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
'{FEATURE_NAME}' AS feature_name,
'{FEATURE_VERSION}' AS feature_version,
cumulative + feature_value AS feature_value,
current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
'' AS comments
from tab2 order by 5 desc 