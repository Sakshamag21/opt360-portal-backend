from datetime import datetime, timedelta, date
import logging
import pandas as pd
from trino.dbapi import connect
import os

logger = logging.getLogger(__name__)

trino_host = "10.10.116.75"
trino_port = "8080"
trino_user = "opt360job"

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("https_proxy", None)

period_map = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}

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

def run_one_feature(feature_name: str, feature_version: int, sql_file: str,end_date:str):
    q = (
        "SELECT destination_table, dependent_features, update_window "
        "FROM strot.operator360.opt360_features "
        f"WHERE feature_name = '{feature_name}' AND version = '{feature_version}'"
    )
    reg = trino(q)
    df = reg.get("df")
    if df is None or df.empty:
        raise ValueError(f"Feature not found in registry: {feature_name} v{feature_version}")

    row = df.iloc[0]
    destination_table = row.get("destination_table")
    params = _parse_dependent_features(row.get("dependent_features"))
    filter_condition = params.get("filter_condition", "")

    filter_clause = f"AND {filter_condition}" if str(filter_condition).strip() else ""
    
    print("end_date:",end_date)
    if params.get("min_pkt_date"):
        min_pkt_date = params.get("min_pkt_date")
        max_pkt_date = params.get("max_pkt_date") or end_date
    elif params.get("period_in_days"):
        period_raw = str(params.get("period_in_days")).strip().lower()
        if period_raw in period_map:
            period_days = period_map[period_raw]
        else:
            period_days = int(period_raw)
        max_pkt_date_obj = datetime.fromisoformat(end_date).date()
        min_pkt_date = (max_pkt_date_obj - timedelta(days=period_days)).isoformat()
        max_pkt_date = max_pkt_date_obj.isoformat()
    else:
        raise ValueError(f"{feature_name} missing min_pkt_date/period_in_days in dependent_features")

    print(min_pkt_date, max_pkt_date)
    sql_template = load_sql_file(sql_file)
    insert_sql = sql_template.format(
        destination_table=destination_table,
        FEATURE_NAME=feature_name,
        FEATURE_VERSION=feature_version,
        min_pkt_date=min_pkt_date,
        max_pkt_date=max_pkt_date,
        filter_condition=filter_clause,
    )

    res = trino(insert_sql)
    if not res.get("success"):
        raise RuntimeError(res)