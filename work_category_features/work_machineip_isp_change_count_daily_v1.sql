insert into {destination_table}
with tab3 as (
    select opt_id, eid as sid, uc_event_timestamp as event_timestamp, carrier_name 
    from strot.operator360.uc_machineip_isp_map where date(uc_event_timestamp)=date(current_date - interval '1' day) and machine_ip_address is not Null 
    and carrier_name is not Null and carrier_name!='nan' 
    and eid is not Null and eid!=''
),
tab4 as (
    select opt_id, sid, event_timestamp, carrier_name, lag(carrier_name) over(partition by opt_id order by event_timestamp) as prev_carrier_name 
    from tab3 
    where carrier_name is not Null
),
tab5 as (
    select opt_id, date(event_timestamp) as date, carrier_name , prev_carrier_name
    from tab4 
    where prev_carrier_name is not Null and carrier_name != prev_carrier_name
),
tab6 as (
    select opt_id, date, count(*) as no_of_changes, array_distinct(flatten(array_agg(array[carrier_name,prev_carrier_name]))) as distinct_carrier_used 
    from tab5
    group by 1,2
)

SELECT
opt_id AS entity_id,
'{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
'{FEATURE_NAME}' AS feature_name,
'{FEATURE_VERSION}' AS feature_version,
no_of_changes AS feature_value,
current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
'distinct_isps: [ ' || CAST(array_join(distinct_carrier_used, ',') AS VARCHAR) || ']'AS comments
from tab6 