from __future__ import annotations
from datetime import datetime
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.models.baseoperator import chain
from trino.dbapi import connect
trino_host="10.10.116.75"
trino_port=8080
trino_user="opt360_feature_metadata"


# Define your layers as a dict of lists
LAYERS = {
    "layer_1": ["dag_l1_ingest", "dag_l1_validate", "dag_l1_quality"],
    "layer_2": ["dag_l2_transform", "dag_l2_enrich"],
    "layer_3": ["dag_l3_report", "dag_l3_publish"],
}







def trino(query, host=trino_host, port=trino_port, user=trino_user):
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
            df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}


df_source_table= trino('''
    select feature_id, source_table 
    from strot.operator360.opt360_features
    where status='PROD' and feature_id not like %score%'                   
''')



with DAG(
    dag_id="controller_pipeline",
    schedule=None,                       # manual / external trigger
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["controller", "orchestration"],
) as dag:

    start = EmptyOperator(task_id="start")
    end   = EmptyOperator(task_id="end")

    # Fail handler – fires if ANY task fails
    fail_handler = EmptyOperator(
        task_id="fail_handler",
        trigger_rule="one_failed",
    )

    previous_gate = start

    for layer_name, dag_ids in LAYERS.items():
        # Trigger all DAGs in this layer in PARALLEL
        triggers = []
        for child_dag_id in dag_ids:
            t = TriggerDagRunOperator(
                task_id=f"trigger_{layer_name}_{child_dag_id}",
                trigger_dag_id=child_dag_id,
                wait_for_completion=True,     # block until child finishes
                deferrable=True,              # async wait (frees worker slot)
                poke_interval=30,
                reset_dag_run=True,           # re-run if already exists
                allowed_states=["success"],
                failed_states=["failed"],
            )
            triggers.append(t)
            t >> fail_handler

        gate = EmptyOperator(
            task_id=f"gate_{layer_name}",
            trigger_rule="all_success",   
        )

        previous_gate >> triggers
        chain(*[triggers], gate)  
        previous_gate = gate

    previous_gate >> end
    fail_handler >> end