import boto3
import json
import functools
import logging
import os
from datetime import datetime, timezone
from botocore.config import Config
from airflow.exceptions import AirflowSkipException

logger = logging.getLogger(__name__)


CEPH_ENDPOINT_URL = "http://10.10.103.12:425" 
CEPH_ACCESS_KEY = "9S0KLIQO7T2XCNGH4P4A"
CEPH_SECRET_KEY = "XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4"
CEPH_BUCKET_NAME = "prd-bi-master-events-25"
CEPH_CACHE_PREFIX = "cache/airflow/operator360" 


def _get_s3_client():
    """
    Initializes and returns a boto3 S3 client configured for Ceph.
    """
    endpoint_url = CEPH_ENDPOINT_URL
    access_key = CEPH_ACCESS_KEY
    secret_key = CEPH_SECRET_KEY

    if not all([endpoint_url, access_key, secret_key]):
        logger.warning("Ceph S3 environment variables are not fully set. S3 logging will fail silently.")

    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key
    )

def append_json_to_s3( key: str, new_data: dict) -> bool:
    """
    Downloads an existing JSON array from S3, appends a new dictionary to it,
    and uploads it back. If the file doesn't exist, creates a new one.
    """
    try:
        s3 = _get_s3_client()
        existing_data = []
        
        # 1. Try to read the existing file
        try:
            response = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=key)
            content = response['Body'].read().decode('utf-8')
            existing_data = json.loads(content)
            
            # Ensure it's a list before appending
            if not isinstance(existing_data, list):
                existing_data = [existing_data]
                
        except s3.exceptions.NoSuchKey:
            # File doesn't exist yet, start with an empty list
            existing_data = []
        except Exception as read_err:
            # If JSON is corrupted, log it and start fresh to avoid breaking the pipeline
            logger.error(f"Could not read/parse existing JSON at {key}. Overwriting with new data. Error: {read_err}")
            existing_data = []

        # 2. Append the new metadata
        existing_data.append(new_data)
        
        # 3. Upload the combined data back to S3
        s3.put_object(
            Bucket=CEPH_BUCKET_NAME,
            Key=key,
            Body=json.dumps(existing_data, indent=4, default=str),
            ContentType='application/json'
        )
        return True
        
    except Exception as e:
        # The Observer Effect: We log the error but DO NOT raise it.
        logger.error(f"Failed to append audit metadata to Ceph S3. Key: {key}. Error: {e}")
        return False

def read_json_from_s3( key: str) -> list:
    """Reads the JSON array file from S3."""
    try:
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=CEPH_BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except s3.exceptions.NoSuchKey:
        logger.warning(f"File not found in Ceph S3. Bucket: {CEPH_BUCKET_NAME}, Key: {key}")
        return []
    except Exception as e:
        logger.error(f"Failed to read audit metadata from Ceph S3. Key: {key}. Error: {e}")
        return []

def audit_to_s3( dag_id: str):
    """
    Decorator to intercept function execution and log run metadata to Ceph S3.
    Appends to a SINGLE file per DAG.
    Only logs when the task actually runs (success or failure). Ignores skipped tasks.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # In Airflow 3, these are safely passed via op_kwargs
            feature_id = kwargs.get('feature_id', 'unknown_feature')
            feature_name = kwargs.get('feature_name', 'unknown_name')
            data_interval_start = kwargs.get('data_interval_start', datetime.now(timezone.utc).isoformat())
            
            try:
                dt_obj = datetime.fromisoformat(data_interval_start)
                logical_date_str = dt_obj.strftime('%Y-%m-%d')
            except Exception:
                logical_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            # ONE FILE PER DAG: Uses dag_id for the filename
            s3_key = f"{CEPH_CACHE_PREFIX}/{dag_id}.json"
            
            wall_clock_ts = datetime.now(timezone.utc).isoformat()
            status = "unknown"
            error_reason = None

            try:
                # Execute the actual feature function
                result = func(*args, **kwargs)
                status = "success"
                return result
                
            except AirflowSkipException:
                # If it's skipped, DO NOT log to S3. 
                # Just re-raise immediately to let Airflow mark it as skipped.
                raise
                
            except Exception as e:
                # Handle any other failure
                status = "failed"
                error_reason = str(e)[:2000]
                raise 
                
            finally:
                # ONLY append to S3 if the task actually ran and succeeded or failed.
                if status in ["success", "failed"]:
                    metadata_payload = {
                        "feature_id": feature_id,
                        "feature_name": feature_name,
                        "status": status,
                        "logical_date": logical_date_str,
                        "execution_timestamp": wall_clock_ts,
                        "error_reason": error_reason
                    }
                    
                    append_json_to_s3(
                        key=s3_key,
                        new_data=metadata_payload
                    )
        return wrapper
    return decorator