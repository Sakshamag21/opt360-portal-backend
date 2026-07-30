import requests
from datetime import datetime, timedelta,date
import pandas as pd
# import strot_query as sq
from trino.dbapi import connect
import logging
import os
import sys
import uuid
from kafka import KafkaProducer
import json
from decimal import Decimal
from uuid import UUID

trino_host = "10.10.116.75"
trino_port = "8080"
trino_user = "signal_mechanism"

logger = logging.getLogger(__name__)


MNDC_KAFKA_BROKERS = ['10.81.105.201:9092',
                '10.81.107.175:9092',
                '10.81.105.118:9092',
                '10.81.107.107:9092',
                '10.81.104.91:9092',
                '10.81.107.23:9092',
                '10.81.106.216:9092',
                '10.81.104.124:9092',
                '10.81.106.173:9092',
                '10.81.107.141:9092',
                '10.81.107.4:9092']

# HDC_KAFKA_BROKERS = ['10.10.122.211:9092',
#                 '10.10.122.212:9092',
#                 '10.10.122.213:9092',
#                 '10.10.122.215:9092',
#                 '10.10.122.216:9092',
#                 '10.10.122.224:9092',
#                 '10.10.122.225:9092',
#                 '10.10.122.226:9092',
#                 '10.10.122.227:9092']


def trino(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        q_lower = query.strip().lower()
        logger.info(f"Trino: executing query => {query}")
        conn = connect(host=host, port=port, user=user)
        cur = conn.cursor()
        cur.execute(query)
        # Only fetch results for SELECT/SHOW/DESCRIBE/EXPLAIN queries
        if q_lower.startswith(("select", "with", "show", "describe", "explain")):
            body = cur.fetchall()
            if not body:
                logger.info("Trino: query returned 0 rows")
                return {"query": query, "success": 1, "data": body}
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            logger.info(f"Trino: query returned {len(df)} rows; columns={cols}")
            return {"query": query, "success": 1, "data": (cols, body), "df": df}
        else:
            # DML/DDL executed successfully
            logger.info("Trino: statement executed successfully (no result set)")
            return {"query": query, "success": 1}
    except Exception as e:
        logger.exception(f"Trino: query failed: {e}")
        return {"query": query, "success": 0, "msg": str(e)}
    

def json_serializer(obj):
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8')
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def serialize_value(v):
    """Custom serializer that handles UUID and other complex types"""
    if isinstance(v, dict):
        return json.dumps(v, default=json_serializer).encode('utf-8')
    elif isinstance(v, str):
        return v.encode('utf-8')
    else:
        return json.dumps(v, default=json_serializer).encode('utf-8')


def create_kafka_producer(bootstrap_servers=MNDC_KAFKA_BROKERS):
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda k: str(k).encode('utf-8'),
        value_serializer=serialize_value,
        linger_ms=100,
        retries=5,
        retry_backoff_ms=1000,
        acks='all',
        batch_size=65536
    )
    print(bootstrap_servers)

    # print(producer)
    return producer

def push_messages_to_kafka(messages, topic_name, bootstrap_servers=MNDC_KAFKA_BROKERS):
    producer = create_kafka_producer(bootstrap_servers)
    
    try:
        for idx, message in enumerate(messages):
            # Optional: Use entity_id as key for partitioning
            key = None
            if 'eventId' in message:
                key = str(message['eventId'])
            
            # Send message to Kafka
            # print(message)
            future = producer.send(
                topic_name,
                key=str(message['eventId']),
                value=message
            )
            
            # Wait for message to be sent (synchronous)
            # record_metadata = future.get(timeout=10)
            
            # print(f"Message {idx + 1} sent successfully:")
            # print(f"  Topic: {record_metadata.topic}")
            # print(f"  Partition: {record_metadata.partition}")
            # print(f"  Offset: {record_metadata.offset}")
            
    except Exception as e:
        print(f"Error sending messages to Kafka: {e}")
        raise
    finally:
        # Ensure all messages are sent before closing
        producer.flush()
        producer.close()
        print(f"\nAll {len(messages)} messages sent successfully!")


def get_signals_info(feature_id: str):
    mndc_api='10.81.116.49'
    print(feature_id)
    res= requests.get(f"http://10.10.116.60:8000/api/signal/info/{feature_id}")
    res=res.json()
    if res['success']==False:
        print(f"for feature id: {feature_id}, we get message {res['success']}")
    elif res['message']=='No active signals found' :
        print(f"For feature id: {feature_id}, no active signals found")
    elif res['message']=='Signals retrieved successfully':
        print(f"For feature id :{feature_id}, got {res['data']['count']} signals in signals db")
        return res['data']['signals']


def get_next_threshold(feature_id, signal_id,version):
    res_try= get_signals_info(feature_id)
    res_try_sorted=sorted(res_try,key=lambda x: x['version'])
    for dt in res_try_sorted:
        if dt['version']>version:
            return float(dt['threshold'])
    # print(res_try_sorted)
    return float('inf')

def push_signals_kafka(signals_metadata):
    
    feature_id=signals_metadata['feature_id']
    threshold= float(signals_metadata['threshold'])
    print(type(threshold))
    signal_name=signals_metadata['name']
    version=signals_metadata['version']
    signal_description=signals_metadata['description']
    signal_id=signals_metadata['id']
    severity_level=signals_metadata['severity_level']
    kafka_topic=signals_metadata['kafka_topic']
    kafka_topic = kafka_topic if kafka_topic else 'OPT360.SIGNALS.V1'
    is_warning_signal=False
    upper_threshold=float('inf')
    print(f"Running signal {signal_name}, {version}, {feature_id} with threshold {threshold} in kafka topic {kafka_topic} ")
    if '_warning' in signal_id or '_monitor' in signal_id: 
        is_warning_signal=True
        upper_threshold=get_next_threshold(feature_id, signal_id, version)
        print(threshold,type(threshold),upper_threshold,type(upper_threshold))

    print(is_warning_signal,"is_warning_signal or is_monitor_signal")

    
    messages=[]
    feature_metadata=trino(f'''
        select * from strot.operator360.opt360_features where feature_id='{feature_id}'
    ''')

    if 'df' in feature_metadata:

        print(feature_metadata['df'])
        for _,r in feature_metadata['df'].iterrows():
            destination_table= r['destination_table']
            feature_data= trino(f'''
                select * from {destination_table} where feature_id='{feature_id}' and date(timestamp)>=date(current_timestamp)
            ''')

            if 'df' not in feature_data:
                print(f"Error in signal_name:{signal_name} version:{version} which uses featue_id:{feature_id} at threshold:{threshold} : {feature_data}")
                break

            feature_data=feature_data['df']
            print("feature_data")
            print(feature_data.head())

            if len(feature_data)<=0:
                print(f"Feature data has 0 rows: {feature_data}")
                return {"status":"Success", "message":f"Feature data has 0 rows: {feature_data}"}

            feature_data= feature_data[(feature_data['feature_value']>threshold) & (feature_data['feature_value']<=upper_threshold)]
            # print("data")
            print(f'''Count of features to be pushed: {len(feature_data)} ''')

            if len(feature_data)<=0:
                print(f"No opt_id has crossed the threshold for name:{signal_name}, version:{version}")
                return {"status":"Success", "message":f"Feature data has 0 rows: {feature_data}"}
                
            for _,feature_row in feature_data.iterrows():
                message={
                "eventId": uuid.uuid4(),
                "eventTimestamp": int(datetime.now().timestamp()*1000),
                "eventVersion": version,
                "data":{
                    "featureId": feature_id,
                    "featureThreshold": threshold,
                    "featureName": r['feature_name'],
                    "featureValue":feature_row['feature_value'],
                    "entityType": "OPERATOR",
                    "entityId": feature_row['entity_id'],
                    "signalId": signal_id,
                    "signalName":signal_name,
                    "signalVersion":version,
                    "description":signal_description,
                    "severityLevel": severity_level,
                    "createdAt": int(feature_row['timestamp'].tz_localize('UTC').timestamp()*1000),
                    "comments":feature_row['comments']
                    }
                }

                messages.append(message)

        # print(len(messages))
        # print(messages)
        print(push_messages_to_kafka(messages=messages, topic_name='OPT360.SIGNALS.V1', bootstrap_servers=MNDC_KAFKA_BROKERS))

        return {"status":"Success","message":f"Pushed {len(messages)} signals"}

    else:
        # print(feature_metadata)
        return {"status":"Failed", "message":f"Error in feature metadata{feature_metadata}"}


