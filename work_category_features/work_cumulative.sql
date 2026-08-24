with tab1 as (
    select entity_id as opt_id, feature_id, feature_value
    from strot.operator360.features_work_v1 where feature_id='{dependent_featureid}' and date(timestamp) = current_date
),
tab2 as (
    select opt_id, feature_id, max(feature_value) as feature_value
    from tab1 
    group by 1,2
),
tab3 as (
    select entity_id as opt_id, feature_id, feature_value, row_number() over(partition by feature_id order  by timestamp) as rn
    from strot.operator360.features_work_v1 where feature_id='{FEATURE_NAME}_v{FEATURE_VERSION}' and date(timestamp)<current_date
),
tab4 as(
    select * from tab3 where rn=1
),
tab5 as (
    select t1.opt_id, t1.feature_value as base_feature_value, coalesce(t2.feature_value,0) as cum_feature_value
    from tab2 t1 left join tab4 t2 on t1.opt_id=t2.opt_id 
)

 SELECT
  opt_id AS entity_id,
  '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
  '{FEATURE_NAME}' AS feature_name,
  '{FEATURE_VERSION}' AS feature_version,
  base_feature_value + cum_feature_value AS feature_value,
  current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
  '' AS comments
  from tab5
