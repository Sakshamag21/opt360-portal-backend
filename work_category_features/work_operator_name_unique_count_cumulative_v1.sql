insert into {destination_table}
    with tab1 as(
        SELECT
            upper(enrl_oper_code) as opt_id,
            enrl_oper_name
        FROM flink_stream.stream_enu.bi_enu_enrlraw_v2
        where date(processed_timestamp) >= date('{min_pkt_date}')
            and date(event_timestamp) >= date('{min_pkt_date}')
            and date(event_timestamp) < date('{max_pkt_date}')
            and bio_dev_modality != 'Face'
            and enrl_client_machine_id not like '%SSUP%'
        group by 1,2
    ),
    tab2 as(
        select opt_id, array_agg(enrl_oper_name) as names from tab1 group by 1
    ),
    tab3 as(
        select entity_id, comments
        from (
            select entity_id,
                   comments,
                   row_number() over(partition by entity_id order by "timestamp" desc) as rn
            from strot.operator360.features_work_v1
            where feature_id = 'work_operator_name_unique_count_cumulative_v1' and date(timestamp) < date('{min_pkt_date}')
        ) t
        where rn = 1
    ),
    tab4 as(
        select
            t2.opt_id as entity_id,
            array_union(
                t2.names,
                case
                    when t3.comments is not null
                         and replace(t3.comments, 'names_used_by_operator: ', '') != ''
                    then split(
                        replace(t3.comments, 'names_used_by_operator: ', ''),
                        ','
                    )
                    else CAST(ARRAY[] AS ARRAY(VARCHAR))
                end
            ) as all_names
        from tab2 t2
        left join tab3 t3 on t2.opt_id = t3.entity_id
    )
    SELECT
      entity_id,
      '{FEATURE_NAME}_v{FEATURE_VERSION}' AS feature_id,
      '{FEATURE_NAME}' AS feature_name,
      '{FEATURE_VERSION}' AS feature_version,
      cardinality(all_names) AS feature_value,
      current_timestamp AT TIME ZONE 'Asia/Kolkata' AS "timestamp",
      'names_used_by_operator: ' || array_join(all_names, ',') AS comments
    from tab4