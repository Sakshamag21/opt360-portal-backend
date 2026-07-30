import findspark
findspark.init()
from pyspark.sql import functions as F, Window
from pyspark.sql import SparkSession
import logging
import pandas as pd
import datetime as dt
import json
import ast
from trino.dbapi import connect
import re
from instance_scoring_methods import *
from trino.dbapi import connect
trino_host="10.10.116.75"
trino_port=8080
trino_user="opt360_feature_metadata"
logger = logging.getLogger(__name__)

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



def _parse_dependent_features(dep_val):
    params = {}
    
    if isinstance(dep_val, list):
        items = dep_val
    elif isinstance(dep_val, str):
        try:
            # Use ast.literal_eval to safely parse the string representation
            parsed = ast.literal_eval(dep_val)
            if isinstance(parsed, list):
                items = parsed
            else:
                items = []
        except (ValueError, SyntaxError):
            # Fallback to manual parsing if ast fails
            s = dep_val.strip().strip("[]")
            items = _smart_split(s)
    else:
        items = []
    
    for item in items:
        if isinstance(item, str):
            # Handle key:value pairs
            if ":" in item:
                k, v = item.split(":", 1)
                key = k.strip()
                value = v.strip()
                if value=='False':
                    value =False
                    params[key]=value
                elif value=='True':
                    value=True
                    params[key]=value
                else:
                    if value.startswith("[") and value.endswith("]"):
                        try:
                            print("outmdfbvdfkjvbkx  ifhdsfsdlkgfbdl")
                            if value.startswith("[") and value.endswith("]"):
                                print("in c jbvjcxbvoixbcvkncxvnvnlknvlxcnvlnxvklxblkvbvb")
                                parsed_val= _parse_nested_list(value)
                                print(parsed_val)
                                params[key]= parsed_val
                        except (ValueError, SyntaxError) as e:
                            params[key] = value
                            print(e)
                    else:
                        try:
                            # Check if value is a dict-like string
                            if value.startswith("{") and value.endswith("}"):
                                # Parse nested dict manually
                                parsed_val = _parse_nested_dict(value)
                                params[key] = parsed_val
                            else:
                                # Try to convert to int
                                params[key] = int(value)
                        except (ValueError, SyntaxError):
                            # Keep as string if conversion fails
                            params[key] = value
    
    return params

def _smart_split(s):
    """Split by comma but respect nested structures (braces)"""
    items = []
    current = []
    depth = 0
    
    for char in s:
        if char == "{":
            depth += 1
            current.append(char)
        elif char == "}":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            item = "".join(current).strip().strip("'").strip('"')
            if item:
                items.append(item)
            current = []
        else:
            current.append(char)
    
    if current:
        item = "".join(current).strip().strip("'").strip('"')
        if item:
            items.append(item)
    
    return items

def _parse_nested_dict(dict_str):
    """Parse a dict string like {key1:val1,key2:val2,...}"""
    # Remove outer braces
    inner = dict_str.strip()[1:-1]
    result = {}
    
    # Smart split respecting nested braces
    items = _smart_split(inner)
    
    for item in items:
        if ":" in item:
            k, v = item.split(":", 1)
            key = k.strip()
            value = v.strip()
            
            try:
                # Try to convert to int
                result[key] = int(value)
            except ValueError:
                # Keep as string if conversion fails
                result[key] = value
    
    return result

def _parse_nested_list(list_str):
    inner= list_str.strip()[1:-1]
    items= inner.split(',')

    res=[]
    for item in items:
        res.append(item)

    return res


def main(
    feature_name: str = "risk_score",
    destination_table: str = "strot.operator360.opt_features_test"
):
    try:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
        logger.info(f"Starting feature job (Spark-based): {feature_name}")
        import sys
        if len(sys.argv) >= 3:
            feature_name = sys.argv[1]
            feature_version= sys.argv[2]

        spark = get_spark(f"opt360_{feature_name}_automation")
        print(feature_name, feature_version)
        # Fetch registry metadata
        q = (f'''
            SELECT * 
             FROM strot.operator360.opt360_features 
             WHERE feature_name = '{feature_name}' and version= '{feature_version}'
        ''')
        reg = trino(q,host='10.10.116.75')
        print(reg)
        if 'df' not in reg:
            print(reg)
            return 
        df= reg.get('df')

        for index, row in df.iterrows():
            feature_name = row.get("feature_name")
            update_window=row.get("update_window")
            feature_version= row.get("version")
            current_destination_table = row.get("destination_table", destination_table)
            current_dependent_features = row.get("dependent_features")
            source_table= row.get("source_table")
            
            params = _parse_dependent_features(current_dependent_features)
            
            
            print(params)
            
            
            logger.info(f"Processing row {index}: feature={feature_name}, table={current_destination_table}, params={params}")
            spark=get_spark(feature_name)
            # for key,val in params.items():
            #     print(key,val)

            # print(params['risk_weightage'])
            print(params['scoring_method'],type(params['scoring_method']))
            scoring_function_name = params.get('scoring_method', '')
            if scoring_function_name == '':
                logger.error(f"For feature={feature_name} , version={feature_version}, no scoring function is defined, dependent_features={params}")
            print(f"source_table: {source_table}")

            scoring_func = globals()[scoring_function_name]
            if scoring_function_name:
                try:
                    risk_df=scoring_func(spark=spark,fraud_table=source_table, **params)
                    print(risk_df.sort(F.desc('score')).show())
                except Exception as e:
                    print(e)
                    return e

    
            # # risk_df=softmax_scoring(spark=spark,risk_weightage=params['risk_weightage'])

            # print(risk_df.show())
            
            risk_df= risk_df.select(
                F.col("entity_id"),
                F.lit(f"{feature_name}_v{feature_version}").alias("feature_id"),
                F.lit(feature_name).alias("feature_name"),
                F.lit(feature_version).alias("feature_version"),
                F.round(F.col("score"),2).cast("double").alias("feature_value"),
                F.from_utc_timestamp(F.current_timestamp(), "Asia/Kolkata").alias("timestamp"),
                F.lit('').alias("comments")
            )


            print(risk_df.show(5))
            print(current_destination_table)

            risk_df.writeTo(current_destination_table).append()

            # # spark.close()


    except Exception as e:
        print(f"Exception in score: {e}")


main()