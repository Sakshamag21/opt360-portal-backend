from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

from trino.dbapi import connect
from airflow.models.baseoperator import chain

from datetime import date,datetime,timedelta

trino_host="10.10.116.75"
trino_catalog_iceberg='strot'
trino_port=8080
trino_user="airflow_dag_op"

def run_query(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        conn = connect(
            host=host,
            port=port,
            user=user
        )
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        if not body:
            return {"query": query, "success": 1, "data": body}
        else:
            cols = [i[0] for i in cur.description]
            # df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body)}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}
    

sfc_tab_updt='''
MERGE INTO strot.operator360.opt_anomalous_sfc_eid_daily t 
USING (
    WITH tab1 AS (
        SELECT 
            refid, 
            CAST(is_finger_unsystematic AS BOOLEAN) as is_finger_unsystematic,
            CAST(is_iris_unsystematic AS BOOLEAN) as is_iris_unsystematic,
            CAST(is_finger_liveness_unsystematic AS BOOLEAN) as is_finger_liveness_unsystematic,
            CAST(is_iris_liveness_unsystematic AS BOOLEAN) as is_iris_liveness_unsystematic,
            CAST(is_face_liveness_unsystematic AS BOOLEAN) as is_face_liveness_unsystematic,
            CAST(is_packet_unsystematic AS BOOLEAN) as is_packet_unsystematic
        FROM prod_r_clickhouse.stream_enu.enrl_sfc 
        WHERE date(event_timestamp) >= date(current_date - interval '1' Day) 
            AND is_packet_unsystematic = 'true' 
    ),
    tab2 AS (
        SELECT DISTINCT 
            t2.edata_sid AS eid, 
            t1.* 
        FROM tab1 t1 
        LEFT JOIN (
            SELECT edata_refid, edata_sid 
            FROM flink_stream.stream_enu.enu_globalprocessaudit 
            WHERE date(ets) >= date(current_date - interval '7' Day)
        ) t2 ON t1.refid = t2.edata_refid
        WHERE t1.refid IS NOT NULL
    ),
    tab3 AS (
        SELECT 
            UPPER(t2.session_operatorid) AS opt_id, 
            t1.*
        FROM tab2 t1 
        JOIN (
            SELECT enrolment_eid, session_operatorid 
            FROM flink_stream.stream_enu.ens_packet_enriched 
            WHERE date(event_timestamp) >= date(current_date - interval '7' Day)
        ) t2 ON t1.eid = t2.enrolment_eid 
        WHERE session_operatorid IS NOT NULL 
    )
    SELECT DISTINCT * FROM tab3
) s
ON t.eid = s.eid
WHEN NOT MATCHED THEN 
INSERT (
    opt_id, eid, refid, 
    is_finger_unsystematic, is_iris_unsystematic, 
    is_finger_liveness_unsystematic, is_iris_liveness_unsystematic, 
    is_face_liveness_unsystematic, is_packet_unsystematic
) 
VALUES (
    s.opt_id, s.eid, s.refid, 
    s.is_finger_unsystematic, s.is_iris_unsystematic, 
    s.is_finger_liveness_unsystematic, s.is_iris_liveness_unsystematic, 
    s.is_face_liveness_unsystematic, s.is_packet_unsystematic
)'''
###SFC:- refid, sid, is_finger_unsystematic,is_iris_unsystematic, is_finger_liveness_unsystematic, is_iris_liveness_unsystematic, is_face_liveness_unsystematic,is_packet_unsystematic


###MFC:- refid, bio_fraud_is_fraudulent_disposition, bio_fraud_left_slap_overall_verdict,bio_fraud_right_slap_overall_verdict, bio_fraud_left_iris_overall_verdict, bio_fraud_right_iris_overall_verdict 
###      bio_fraud_face_overall_verdict, bio_fraud_both_thumbs_overall_verdict
mfc_tab_updt='''
MERGE INTO strot.operator360.opt_anomalous_mfc_eid_daily t 
USING (
    WITH tab1 AS (
        SELECT 
            CASE 
                WHEN bio_match_assigned_applicant_ref_id IS NOT NULL AND bio_match_assigned_applicant_ref_id != '' THEN bio_match_assigned_applicant_ref_id
                WHEN bio_match_assigned_candidate_ref_id IS NOT NULL AND bio_match_assigned_candidate_ref_id != '' THEN bio_match_assigned_candidate_ref_id
                WHEN face_dedup_assigned_applicant_ref_id IS NOT NULL AND face_dedup_assigned_applicant_ref_id != '' THEN face_dedup_assigned_applicant_ref_id
                WHEN bio_fraud_assigned_applicant_ref_id IS NOT NULL AND bio_fraud_assigned_applicant_ref_id != '' THEN bio_fraud_assigned_applicant_ref_id
                WHEN facial_verify_assigned_applicant_refid IS NOT NULL AND facial_verify_assigned_applicant_refid != '' THEN facial_verify_assigned_applicant_refid
                WHEN incoming_record_refid IS NOT NULL AND incoming_record_refid != '' THEN incoming_record_refid
                ELSE NULL
            END AS refid, 
            CAST(bio_fraud_is_fraudulent_disposition AS BOOLEAN) AS bio_fraud_is_fraudulent_disposition,
            bio_fraud_left_slap_overall_verdict,
            bio_fraud_right_slap_overall_verdict, 
            bio_fraud_left_iris_overall_verdict, 
            bio_fraud_right_iris_overall_verdict,
            bio_fraud_face_overall_verdict, 
            bio_fraud_both_thumbs_overall_verdict
        FROM prod_r_clickhouse.stream_enu.enrl_bfc_mfc 
        WHERE 
            bio_fraud_assigned_applicant_ref_id IS NOT NULL 
            AND bio_fraud_is_fraudulent_disposition = 'true'
            AND event_timestamp >= date(current_date - interval '6' Day)
    ),
    tab2 AS (
        SELECT DISTINCT 
            t2.edata_sid AS eid, 
            t1.*
        FROM tab1 t1 
        LEFT JOIN (
            SELECT edata_refid, edata_sid 
            FROM flink_stream.stream_enu.enu_globalprocessaudit 
            WHERE date(ets) >= date(current_date - interval '7' Day)
        ) t2 ON t1.refid = t2.edata_refid
        WHERE t1.refid IS NOT NULL
    ),
    tab3 AS (
        SELECT 
            UPPER(t2.session_operatorid) AS opt_id, 
            t1.*,
            ROW_NUMBER() OVER (PARTITION BY t1.eid ORDER BY t1.refid) AS rn
        FROM tab2 t1 
        JOIN (
            SELECT enrolment_eid, session_operatorid 
            FROM flink_stream.stream_enu.ens_packet_enriched 
            WHERE date(event_timestamp) >= date(current_date - interval '7' Day)
        ) t2 ON t1.eid = t2.enrolment_eid 
        WHERE session_operatorid IS NOT NULL 
    )
    SELECT 
        opt_id, 
        eid, 
        refid, 
        bio_fraud_is_fraudulent_disposition,
        bio_fraud_left_slap_overall_verdict,
        bio_fraud_right_slap_overall_verdict, 
        bio_fraud_left_iris_overall_verdict, 
        bio_fraud_right_iris_overall_verdict,
        bio_fraud_face_overall_verdict, 
        bio_fraud_both_thumbs_overall_verdict
    FROM tab3 
    WHERE rn = 1
) s 
ON s.eid = t.eid 
WHEN NOT MATCHED THEN 
INSERT (
    opt_id, eid, refid, 
    bio_fraud_is_fraudulent_disposition, 
    bio_fraud_left_slap_overall_verdict,
    bio_fraud_right_slap_overall_verdict, 
    bio_fraud_left_iris_overall_verdict, 
    bio_fraud_right_iris_overall_verdict,
    bio_fraud_face_overall_verdict, 
    bio_fraud_both_thumbs_overall_verdict
)
VALUES (
    s.opt_id, s.eid, s.refid, 
    s.bio_fraud_is_fraudulent_disposition, 
    s.bio_fraud_left_slap_overall_verdict,
    s.bio_fraud_right_slap_overall_verdict, 
    s.bio_fraud_left_iris_overall_verdict, 
    s.bio_fraud_right_iris_overall_verdict,
    s.bio_fraud_face_overall_verdict, 
    s.bio_fraud_both_thumbs_overall_verdict
)'''

qc_tab_updt='''
merge into strot.operator360.opt_anomalous_qc_eid_daily t using (
select distinct upper(operator_id) as opt_id, error_category ,packeteid as eid ,priority ,is_audited
from strot.operator360.eid_qc_error_report_v2 
where check_date>=date(current_date- interval '7' Day)
) s on s.eid=t.eid
when not matched then
insert(opt_id,error_category,eid,priority,is_audited)
values(s.opt_id,s.error_category,s.eid,s.priority,s.is_audited)
'''

name_tab_updt='''
merge into strot.operator360.opt_namechange_anomalous_ot_eid_daily t using(
with tab1 as(
    select uid,array_distinct(array_agg(upper(operator_id))) as opt_ids_success, count(*) as total_name_updates from strot.mysql_uid_v2.uid_origin_tracker_enriched where enr_date>=date('2020-01-01') and from_utf8(updt_resident_name)='10' group by 1 
),
tab1_2 as(
    select uid,total_name_updates, opt_id from tab1 , unnest(opt_ids_success) as e(opt_id) where total_name_updates>3
)
select t1.opt_id,t1.uid, t2.eid,t1.total_name_updates ,t2.enr_date 
from tab1_2 t1 left join strot.mysql_uid_v2.uid_origin_tracker_enriched t2 on t1.opt_id=upper(t2.operator_id) and t1.uid=t2.uid
where t2.enr_date>=date(current_date-interval '1' day) and from_utf8(t2.updt_resident_name)='10') s on t.eid=s.eid
when not matched then
insert(opt_id,eid,uid,total_name_updates,enr_date)
values(s.opt_id,s.eid,s.uid,s.total_name_updates,s.enr_date)
'''

outstate_tab_updt='''
merge into strot.operator360.opt_outstate_anomalous_enu_eid_daily t using (
with tab1 as (
    select 
        UPPER(session_operatorid) as opt_id, 
        enrolment_eid,
        machine_pincode,
        DATE(DATE_PARSE(SUBSTRING(enrolment_eid, 15), '%Y%m%d%H%i%s')) as packet_date
        from 
            flink_stream.stream_enu.ens_packet_enriched
        where 
            machine_pincode is not null 
            and DATE(DATE_PARSE(SUBSTRING(enrolment_eid, 15), '%Y%m%d%H%i%s')) >= DATE(CURRENT_DATE - INTERVAL '7' DAY)
),
tab2 as (
    select opt_id,enrolment_eid as eid,packet_date,machine_pincode,t2.district as machine_district, t2.state as machine_state
    from tab1 t1 join strot.misc_adhoc.pincode_ro_mapping t2 on t1.machine_pincode=cast(t2.pin_code as varchar)
),
tab3 as (
    select 
        t1.*,t2.uid
    from 
        tab2 t1 join strot.mysql_uid_v2.uid_origin_tracker_enriched t2
    on t1.eid=t2.eid
    where date(t2.enr_date) >= DATE(CURRENT_DATE - INTERVAL '7' DAY)
),
tab4 as (
    select 
        t1.*,t2.res_addr_pincode as res_pincode
    from 
        tab3 t1 join strot.mysql_uid_v2.uid_address t2
    on t1.uid=t2.uid
    
),
tab5 as (
    select 
        t1.*, t2.district as res_district, t2.state as res_state
    from tab4 t1 join strot.misc_adhoc.pincode_ro_mapping t2 on t1.res_pincode=cast(t2.pin_code as varchar)
)
select eid, max(opt_id) as opt_id, max(packet_date) as packet_date, max(machine_pincode) as machine_pincode,
max(machine_district) as machine_district, max(machine_state) as machine_state, max(uid) as uid,
max(res_pincode) as res_pincode, max(res_district) as res_district, max(res_state) as res_state
from tab5 where machine_state!=res_state 
group by 1
) s on s.eid=t.eid
when not matched then
insert(opt_id,eid,packet_date,machine_pincode,machine_district,machine_state,uid,res_pincode,res_district,res_state)
values(s.opt_id,s.eid,s.packet_date,s.machine_pincode,s.machine_district,s.machine_state,s.uid,s.res_pincode,s.res_district,s.res_state)
'''

oddhour_tab_updt='''
merge into strot.operator360.opt_oddhour_anomalous_ens_eid_daily t using (
WITH tab1 AS (
SELECT 
     UPPER(session_operatorid) as opt_id, 
    enrolment_eid as eid,
    event_timestamp,
    DATE_PARSE(SUBSTRING(enrolment_eid, 15), '%Y%m%d%H%i%s') as packet_timestamp
FROM flink_stream.stream_enu.ens_packet_enriched 
WHERE 
    event_timestamp >= DATE(current_date- interval '7' day) 
    AND (HOUR(DATE_PARSE(SUBSTRING(enrolment_eid, 15), '%Y%m%d%H%i%s')) < 6 OR HOUR(DATE_PARSE(SUBSTRING(enrolment_eid, 15), '%Y%m%d%H%i%s')) >= 22) 
    AND session_operatorid IS NOT NULL 
    AND session_operatorid NOT IN ('ssup_operator', 'mou_operator') 
)
select distinct * from tab1) s on t.eid=s.eid
when not matched then 
insert(opt_id,eid,event_timestamp,packet_timestamp)
values(s.opt_id,s.eid,s.event_timestamp,s.packet_timestamp)
'''

common_tab_enrichment='''
MERGE INTO {} s 
USING (
    SELECT * FROM (
        SELECT 
            date(t1.event_timestamp) as event_timestamp,
            t1.enrolment_type, 
            t1.enrolment_eid as eid,
            t1.pkt_source, 
            t1.station_no, 
            t1.station_machine_code,
            upper(t1.session_operatorid) as opt_id,
            date_parse(substring(t1.enrolment_eid,15),'%Y%m%d%H%i%s') as date_created,
            ARRAY[
                CASE WHEN t1.enrolment_is_mobile_updated = 1 THEN 'Mobile Updated' END,
                CASE WHEN t1.enrolment_is_name_updated = 1 THEN 'Name Updated' END,
                CASE WHEN t1.enrolment_is_address_updated = 1 THEN 'Address Updated' END,
                CASE WHEN t1.enrolment_is_gender_updated = 1 THEN 'Gender Updated' END,
                CASE WHEN t1.enrolment_is_dob_updated = 1 THEN 'Dob Updated' END,
                CASE WHEN t1.enrolment_is_email_updated = 1 THEN 'Email Updated' END,
                CASE WHEN t1.enrolment_is_biometric_updated = 1 THEN 'Biometric Updated' END,
                CASE WHEN t1.enrolment_is_photo_updated = 1 THEN 'Photo Updated' END,
                CASE WHEN t1.enrolment_is_mandatory_biometric_update = 1 THEN 'Mandatory Biometric Update' END,
                CASE WHEN t1.enrolment_is_child_enrolment = 1 THEN 'Child Enrolment' END,
                CASE WHEN t1.enrolment_is_whitelisted = 1 THEN 'Whitelisted' END,
                CASE WHEN t1.enrolment_is_nri_enrolment = 1 THEN 'Nri Enrolment' END,
                CASE WHEN t1.enrolment_is_lou = 1 THEN 'Lou' END,
                CASE WHEN t1.enrolment_is_document_updated = 1 THEN 'Document Updated' END
            ] as pkt_updt_type,
            '1' as anomaly_group,
            ROW_NUMBER() OVER (PARTITION BY t1.enrolment_eid ORDER BY t1.event_timestamp DESC) as rn
        FROM flink_stream.stream_enu.ens_packet_enriched t1 
        RIGHT JOIN {} t2 ON upper(t1.session_operatorid) = t2.opt_id 
            AND t1.enrolment_eid = t2.eid
        WHERE date(t1.event_timestamp) >= date(current_date - interval '10' day)
            AND t2.station_no IS NULL
    ) ranked
    WHERE rn = 1
) t 
ON s.eid = t.eid
WHEN MATCHED THEN UPDATE SET
    enrolment_type = t.enrolment_type,
    pkt_source = t.pkt_source,
    station_no = t.station_no,
    station_machine_code = t.station_machine_code,
    pkt_updt_type = t.pkt_updt_type,
    date_created = t.date_created,
    event_timestamp = t.event_timestamp
'''

default_args = {
    'owner': 'Saksham Agarwal',
    'depends_on_past': False,
    'start_date': datetime(2025, 12, 2),
    'email': ['techexe16.yp25@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1
}

dag = DAG(
    'opt_portal_individual_eid_table_updt',
    default_args=default_args,
    description='DAG to update all the eid tables',
    schedule='30 0 * * *',
    catchup=False
)

# sfc_tab_updt_dag = PythonOperator(
#                 task_id='sfc_tab_updt',
#                 python_callable=run_query,
#                 op_kwargs={'query':sfc_tab_updt},
#                 trigger_rule='all_done',
#                 dag=dag,
#                 )

# mfc_tab_updt_dag = PythonOperator(
#                 task_id='mfc_tab_updt',
#                 python_callable=run_query,
#                 op_kwargs={'query':mfc_tab_updt},
#                 trigger_rule='all_done',
#                 dag=dag,
#                 )

qc_tab_updt_dag = PythonOperator(
                task_id='qc_tab_updt',
                python_callable=run_query,
                op_kwargs={'query':qc_tab_updt},
                trigger_rule='all_done',
                dag=dag,
                )

name_tab_updt_dag = PythonOperator(
                task_id='name_tab_updt',
                python_callable=run_query,
                op_kwargs={'query':name_tab_updt},
                trigger_rule='all_done',
                dag=dag,
                )

oustate_tab_updt_dag = PythonOperator(
                task_id='oustate_tab_updt',
                python_callable=run_query,
                op_kwargs={'query':outstate_tab_updt},
                trigger_rule='all_done',
                dag=dag,
                )

oddhour_tab_updt_dag = PythonOperator(
                task_id='oddhour_tab_updt',
                python_callable=run_query,
                op_kwargs={'query':oddhour_tab_updt},
                trigger_rule='all_done',
                dag=dag,
                )

table_array=[
    #  'strot.operator360.opt_anomalous_sfc_eid_daily',
    #  'strot.operator360.opt_anomalous_mfc_eid_daily',
     'strot.operator360.opt_anomalous_qc_eid_daily',
     'strot.operator360.opt_namechange_anomalous_ot_eid_daily',
     'strot.operator360.opt_outstate_anomalous_enu_eid_daily',
     'strot.operator360.opt_oddhour_anomalous_ens_eid_daily'
]

combined_dag_tasks = []
for i, x in enumerate(table_array):
    updated_query = common_tab_enrichment.format(x, x)
    task_id = f'combined_table_{i}'  
    combined_dag = PythonOperator(
        task_id=task_id,
        python_callable=run_query,
        op_kwargs={'query': updated_query},
        trigger_rule='all_done',
        dag=dag,
    )
    combined_dag_tasks.append(combined_dag)

start = EmptyOperator(task_id='start', dag=dag)
end = EmptyOperator(task_id='end', dag=dag)



chain(
    start,
    [ qc_tab_updt_dag, name_tab_updt_dag, oustate_tab_updt_dag, oddhour_tab_updt_dag],
    combined_dag_tasks,
    end
)
