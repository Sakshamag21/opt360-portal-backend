from airflow.sdk import DAG, TriggerRule
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
from zoneinfo import ZoneInfo
from kafka import KafkaProducer, KafkaConsumer
from dataclasses import dataclass, field
from typing import List, Optional
import uuid
import json
import logging
import pandas as pd
from trino.dbapi import connect
import time 

trino_host = "10.10.116.39"
trino_catalog_iceberg = 'strot'
trino_port = 8080
trino_user = "opt_master_updt"


def trino(query, host=trino_host, port=trino_port, user=trino_user):
    try:
        start_time = time.time()
        conn = connect(
            host=host,
            port=port,
            user=user
        )
        cur = conn.cursor()
        cur.execute(query)
        body = cur.fetchall()
        end_time = time.time()
        if not body:
            return {"query": query, "success": 1, "data": body, "execution_time": end_time - start_time}
        else:
            cols = [i[0] for i in cur.description]
            df = pd.DataFrame(body, columns=cols)
            return {"query": query, "success": 1, "data": (cols, body), "df": df, "execution_time": end_time - start_time}
    except Exception as e:
        return {"query": query, "success": 0, "msg": str(e)}


logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='suspension.log',   
    filemode='w'          
)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 5, tzinfo=ZoneInfo("Asia/Kolkata")),
    'email': ['techexecutive16-yp25@uidai.net.in', 'techexecutive22-yp23@uidai.net.in'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
}

with DAG(
    dag_id='operator_automated_suspension',
    default_args=default_args,
    description='DAG to send Kafka messages for suspension of the operator',
    schedule="0 17 * * *",
    catchup=False,
    max_active_tasks=1,
    tags=['operator360', 'suspension']
) as dag:

    consumer_brokers = ['10.81.105.201:9092',
                        '10.81.107.175:9092',
                        '10.81.105.118:9092',
                        '10.81.107.107:9092'
                    ]
    producer_brokers = ['10.81.105.201:9092',
                        '10.81.107.175:9092',
                        '10.81.105.118:9092',
                        '10.81.107.107:9092'
                    ]

    input_topic = 'OPT360.SIGNALS.V1'
    output_topic = 'DE.OPT360.OPERATOR_SUSPENSION.V1'

    SIGNAL_MAP = {
        "opt_bfc_toeprint_suspension": {
            "code": "OPERATOR_BIOMETRIC_FINGER_TOEPRINT_SUSPENSION",
            "remarks": "Operator making packets which have been identified for having error as Toe Print in Manual Fraud Check",
            "recommendedAction": "SUSPEND"
        },
        "opt_qc_doe1_suspension": {
            "code": "OPERATOR_QC_DOE1_SUSPENSION",
            "remarks": "Operator making packets which have been identified in DOE1 error category by QC",
            "recommendedAction": "SUSPEND"
        },
        "opt_qc_pop_suspension": {
            "code": "OPERATOR_QC_POP_SUSPENSION",
            "remarks": "Operator making packets which have been identified in Photo on Photo error category by QC",
            "recommendedAction": "SUSPEND"
        },
        "opt_bio_nonhuman_face_cumulative_count_1d_suspension": {
            "code": "OPERATOR_BIOMETRIC_FACE_NONHUMAN_SUSPENSION",
            "remarks": "Operator making packets which have been given Non Human verdict in Face modaltiy in MFC",
            "recommendedAction": "SUSPEND"
        },
        "opt_bio_pop_face_cumulative_count_1d_suspension": {
            "code": "OPERATOR_BIOMETRIC_FACE_POP_SUSPENSION",
            "remarks": "Operator making packets which have been given POP verdict in Face modaltiy in MFC",
            "recommendedAction": "SUSPEND"
        },
        "opt_bio_swap_iris_cumulative_count_1d_suspension": {
            "code": "OPERATOR_BIOMETRIC_IRIS_SWAP_SUSPENSION",
            "remarks": "Operator making packets which have been given Swap verdict in Iris modaltiy in MFC",
            "recommendedAction": "SUSPEND"
        },
        "opt_bio_flipped_iris_cumulative_count_1d_suspension": {
            "code": "OPERATOR_BIOMETRIC_IRIS_FLIPPED_SUSPENSION",
            "remarks": "Operator making packets which have been given Flipped verdict in Iris modaltiy in MFC",
            "recommendedAction": "SUSPEND"
        }
    }

    SEVERITY_MAP = {
        1: "NO_ACTION",
        2: "LOW",
        3: "MEDIUM",
        6: "HIGH",
        10: "CRITICAL"
    }

    @dataclass
    class Disposition:
        """Represents the disposition of a case"""
        code: str
        severityLevel: str
        recommendedAction: str

    @dataclass
    class Investigator:
        """Represents the investigator details"""
        id: str
        officeName: str

    @dataclass
    class Entity:
        """Represents an entity involved in the case"""
        entityType: str
        entityIdType: str
        entityId: str

    @dataclass
    class EvidenceReference:
        """Represents evidence reference"""
        evidenceId: str
        evidenceType: str
        description: str
        storageReference: str

    @dataclass
    class CaseDetails:
        """Represents case details"""
        source: str
        caseId: str
        caseRegistrationDate: str
        caseDispositionDate: str
        disposition: Disposition
        investigator: Investigator
        remarks: str
        entities: List[Entity] = field(default_factory=list)
        evidenceReferences: List[EvidenceReference] = field(default_factory=list)

    @dataclass
    class OutputEvent:
        """Represents the output event structure for CASE_DISPOSITION"""
        eventId: str
        eventVersion: str
        eventType: str
        eventTimestamp: str
        caseDetails: CaseDetails
        
        def to_dict(self) -> dict:
            """Convert the OutputEvent to a dictionary"""
            return {
                "$schema": "fraud_investigation_event_v1.0",
                "event": {
                    'eventId': self.eventId,
                    'eventVersion': self.eventVersion,
                    'eventType': self.eventType,
                    'eventTimestamp': self.eventTimestamp,
                    'caseDetails': {
                        'source': self.caseDetails.source,
                        'caseId': self.caseDetails.caseId,
                        'caseRegistrationDate': self.caseDetails.caseRegistrationDate,
                        'caseDispositionDate': self.caseDetails.caseDispositionDate,
                        'disposition': {
                            'code': self.caseDetails.disposition.code,
                            'severityLevel': self.caseDetails.disposition.severityLevel,
                            'recommendedAction': self.caseDetails.disposition.recommendedAction
                        },
                        'investigator': {
                            'id': self.caseDetails.investigator.id,
                            'officeName': self.caseDetails.investigator.officeName
                        },
                        'remarks': self.caseDetails.remarks,
                        'entities': [
                            {
                                'entityType': e.entityType,
                                'entityIdType': e.entityIdType,
                                'entityId': e.entityId
                            } for e in self.caseDetails.entities
                        ],
                        'evidenceReferences': [
                            {
                                'evidenceId': er.evidenceId,
                                'evidenceType': er.evidenceType,
                                'description': er.description,
                                'storageReference': er.storageReference
                            } for er in self.caseDetails.evidenceReferences
                        ]
                    }
                }
            }
        
        def to_json(self) -> str:
            """Convert the OutputEvent to JSON string"""
            return json.dumps(self.to_dict(), indent=2)
        
        @staticmethod
        def create_event(case_details: CaseDetails) -> 'OutputEvent':
            """Factory method to create an OutputEvent with auto-generated ID and timestamp"""
            return OutputEvent(
                eventId=str(uuid.uuid4()),
                eventVersion="1.0",
                eventType="CASE_DISPOSITION",
                eventTimestamp=datetime.now(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
                caseDetails=case_details
            )

    def main(poll_timeout_ms: int = 2000, max_idle_polls: int = 5, max_run_seconds: int = 3600):
        producer = KafkaProducer(bootstrap_servers=producer_brokers)
        consumer = KafkaConsumer(
            input_topic, 
            group_id='opt360.suspension', 
            bootstrap_servers=consumer_brokers, 
            auto_offset_reset='latest',
            enable_auto_commit=False,      # Commit manually after processing
            max_poll_records=500           # Process up to 500 messages per poll
        )
        
        idle_poll_count = 0
        start_time = time.time()
        total_processed = 0
        
        logging.info("Starting daily Kafka scan...")

        try:
            # Keep looping until we hit max idle polls or hard time limit (1 hour)
            while idle_poll_count < max_idle_polls and (time.time() - start_time) < max_run_seconds:
                records = consumer.poll(timeout_ms=poll_timeout_ms, max_records=500)
                
                if not records:
                    idle_poll_count += 1
                    continue
                
                # Reset idle counter because we found messages
                idle_poll_count = 0 
                
                for tp_partition, messages in records.items():
                    for message in messages:
                        try:
                            raw = message.value.decode('utf-8')
                            logging.info(f"Received message: {raw}")
                            message_data = json.loads(raw)['data']
                            output_message = process_message(message_data)
                            
                            if output_message is not None and isinstance(output_message, str):
                                producer.send(output_topic, output_message.encode('utf-8'))
                            elif output_message is not None:
                                producer.send(output_topic, json.dumps(output_message).encode('utf-8'))
                            
                            total_processed += 1
                        except json.JSONDecodeError as e:
                            logging.error(f"Error decoding JSON: {e}")
                        except KeyError as e:
                            logging.error(f"Missing key in message: {e}")
                        except Exception as e:
                            logging.error(f"Error processing message: {e}")

                # Commit offsets after successfully processing the batch
                producer.flush()
                consumer.commit()
                logging.info(f"Processed batch. Total processed so far: {total_processed}")
                
            logging.info(f"Daily scan complete. Total messages processed: {total_processed}. Exiting task.")

        except Exception as e:
            logging.error(f"Fatal error in main loop: {e}")
        finally:
            # Always close connections
            try:
                consumer.commit()
            except Exception:
                pass
            consumer.close()
            producer.flush()
            producer.close()

    def get_user_status(opt_id: str = None):
        try:
            if opt_id is None or opt_id == '':
                return 1
            df = trino(f'''
                select case when user_status='1' then 1 else 0 end as status from mysql_uidmasterv1.uidmasterv1_1.user where upper(user_code)='{opt_id}'      
            ''')
            
            if 'data' in df:
                return df['data'][1][0][0]
            else:
                print(df)
                return 1
                
        except Exception as e:
            print(f"Exception in get_user_status function: {e}")
            
    def process_message(message):
        try:
            if message["signalId"] in SIGNAL_MAP.keys():
                operator_status = get_user_status(message['entityId'])
                if operator_status == 1:
                    signal_config = SIGNAL_MAP[message['signalId']]
                    case_details = CaseDetails(
                        source="OPT360",
                        caseId=str(uuid.uuid4()),
                        caseRegistrationDate=datetime.now(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
                        caseDispositionDate=datetime.now(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
                        disposition=Disposition(
                            code=signal_config['code'],
                            severityLevel=SEVERITY_MAP[message['severityLevel']],
                            recommendedAction=signal_config['recommendedAction']
                        ),
                        investigator=Investigator(id='system', officeName='TC'),
                        remarks=signal_config['remarks'],
                        entities=[
                            Entity(
                                entityType=message['entityType'],
                                entityIdType="OPERATOR_ID",
                                entityId=message['entityId']
                            ) 
                        ]
                    )
                    output_event = OutputEvent.create_event(case_details)

                    return output_event.to_json()
                else:
                    print(f"Operator Inactive, opt_id:{message['entityId']}")
                    return None
        
        except KeyError as e:
            logging.error(f"Missing key in message: {e}")
            return json.dumps({"error": f"Missing key: {e}"})
        except Exception as e:
            logging.error(f"Error in process_message: {e}")
            return json.dumps({"error": str(e)})

        return None

    produce_suspension_message_task = PythonOperator(
        task_id='produce_suspension_message',
        python_callable=main,
        trigger_rule=TriggerRule.ALL_DONE,
    )