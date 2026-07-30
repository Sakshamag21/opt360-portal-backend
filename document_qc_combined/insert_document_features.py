from datetime import datetime, timedelta, date
import logging
import pandas as pd
from trino.dbapi import connect
import os
import pytz

logger = logging.getLogger(__name__)

trino_host = "10.10.118.10"
trino_port = "8080"
trino_user = "opt360job"

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("https_proxy", None)
ist = pytz.timezone('Asia/Kolkata')


def trino(query, host=trino_host, port=trino_port, user=trino_user):
    q_lower = query.strip().lower()
    conn = connect(host=host, port=port, user=user)
    cur = conn.cursor()
    cur.execute(query)
    if q_lower.startswith(("select", "with", "show", "describe", "explain")):
        body = cur.fetchall()
        cols = [i[0] for i in cur.description] if cur.description else []
        df = pd.DataFrame(body, columns=cols) if cols else pd.DataFrame(body)
        return {"query": query, "success": 1, "data": (cols, body), "df": df}
    return {"query": query, "success": 1}

def load_sql_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _parse_dependent_features(dep_val):
    params = {}
    if isinstance(dep_val, list):
        items = dep_val
    elif isinstance(dep_val, str):
        s = dep_val.strip().strip("[]")
        items = [i.strip().strip("'").strip('"') for i in s.split(",") if i.strip()]
    else:
        items = []
    for item in items:
        if isinstance(item, str) and ":" in item:
            k, v = item.split(":", 1)
            params[k.strip()] = v.strip()
    return params

def run_one_feature(feature_name: str, feature_version: int, sql_file: str, end_date: str = None):
    q = (
        "SELECT destination_table, dependent_features, update_window "
        "FROM strot.operator360.opt360_features "
        f"WHERE feature_name = '{feature_name}' AND version = '{feature_version}'"
    )
    reg = trino(q)
    if 'df' not in reg:
        print(reg)
        raise ValueError(f"trino query failed, returned no df: {reg}")
    
    df = reg.get("df")
    if df is None or df.empty:
        raise ValueError(f"Feature not found in registry: {feature_name} v{feature_version}")

    row = df.iloc[0]
    destination_table = row.get("destination_table")
    params = _parse_dependent_features(row.get("dependent_features"))
    filter_condition = params.get("filter_condition", "")

    filter_clause = f"AND {filter_condition}" if str(filter_condition).strip() else ""
    
    is_cumulative = False
    if 'cumulative' in feature_name:
        is_cumulative = True
        
    is_monthly = False
    if 'monthly' in feature_name:
        is_monthly = True

    # Safely parse the end_date passed from Airflow, fallback to today IST
    if end_date:
        try:
            # Handle both 'YYYY-MM-DD' and 'YYYY-MM-DD 00:00:00' formats safely
            current_end_date = datetime.strptime(str(end_date).split(" ")[0], '%Y-%m-%d').date()
        except ValueError:
            current_end_date = datetime.now(ist).date()
    else:
        current_end_date = datetime.now(ist).date()

    if params.get("min_pkt_date"):
        # Strip off any time components if Trino returned a full timestamp
        min_pkt_date = str(params.get("min_pkt_date")).split(" ")[0]
        
        if params.get("max_pkt_date"):
            max_pkt_date = str(params.get("max_pkt_date")).split(" ")[0]
        else:
            max_pkt_date = current_end_date.strftime('%Y-%m-%d')
            
    elif params.get("period_in_days"):
        period_days = int(params["period_in_days"])
        # Calculate min_pkt_date based on the end_date from Airflow
        min_pkt_date = (current_end_date - timedelta(days=period_days)).strftime('%Y-%m-%d')
        max_pkt_date = current_end_date.strftime('%Y-%m-%d')
    elif is_cumulative == False and is_monthly == False:
        raise ValueError(f"{feature_name} missing min_pkt_date/period_in_days in dependent_features")

    eid_collection = params.get("eid_collection", "False")
    dependent_feature_id = params.get("dependent_feature_id", None)
    
    if (is_cumulative == True or is_monthly == True) and dependent_feature_id == None:
        raise ValueError(f"{feature_name} missing the dependent_feature_id as it is a cumulative feature")

    sql_template = load_sql_file(sql_file)
    print(sql_template)
    print("cumulative", is_cumulative)
    
    if is_monthly == True:
        if eid_collection == "True":
            insert_sql = sql_template.format(
                destination_table=destination_table,
                FEATURE_NAME=feature_name,
                FEATURE_VERSION=feature_version,
                dependent_feature_id=dependent_feature_id,
                eids_required= '''
                    ,
                    concat('eids:[', array_join(
                        array_agg(
                            distinct regexp_extract(comments, '\[([^\]]+)\]', 1)
                        ),
                        ','
                    ), ']') as merged_eids
                ''',
                req_comments="merged_eids  AS comments ",
            )
        else:
            insert_sql = sql_template.format(
                destination_table=destination_table,
                FEATURE_NAME=feature_name,
                FEATURE_VERSION=feature_version,
                dependent_feature_id=dependent_feature_id,
                eids_required='',
                req_comments=" ''  AS comments ",
            )
    
    elif is_cumulative == True:
        insert_sql = sql_template.format(
            destination_table=destination_table,
            FEATURE_NAME=feature_name,
            FEATURE_VERSION=feature_version,
            dependent_feature_id=dependent_feature_id,
        )
    else:
        if eid_collection == "True":
            insert_sql = sql_template.format(
                destination_table=destination_table,
                FEATURE_NAME=feature_name,
                FEATURE_VERSION=feature_version,
                min_pkt_date=min_pkt_date,
                max_pkt_date=max_pkt_date,
                filter_condition=filter_clause,
                eids_required=", array_distinct(array_agg(packeteid)) as eids",
                req_comments="'eids: [' || CAST(array_join(eids, ',') AS VARCHAR)  || ']'  AS comments ",
            )
        else:
            insert_sql = sql_template.format(
                destination_table=destination_table,
                FEATURE_NAME=feature_name,
                FEATURE_VERSION=feature_version,
                min_pkt_date=min_pkt_date,
                max_pkt_date=max_pkt_date,
                filter_condition=filter_clause,
                eids_required="",
                req_comments=" ''  AS comments ",
            )
        
    print(insert_sql)

    res = trino(insert_sql)
    if not res.get("success"):
        print(res)
        raise RuntimeError(res)   