import logging
import time
from typing import Dict, Any, List  
import requests
from utils.response import Response
from enums.queries import OperatorDetailQueries as Queries
from utils.database import db
from config.config import config
from opt_details.info import get_operator_details
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sid_details(sids: List):
    # Start timer to track execution time
    start_time = time.time()
    
    # Log how many SIDs we are attempting to fetch details for
    logger.info(f"Fetching details for {len(sids)} SIDs from RocksDB SID store...")

    # 1. Fallback: Configuration missing
    rocksdb_config_sid_store = config.get('rocksdb_sid_store')
    if not rocksdb_config_sid_store:
        logger.error("Fallback triggered: RocksDB SID store configuration is missing.")
        return Response.error("RocksDB configuration missing")

    endpoint = rocksdb_config_sid_store.get('endpoint') 
    endpoint_url = f"http://{rocksdb_config_sid_store.get('host')}:{rocksdb_config_sid_store.get('port')}{endpoint}"
    logger.info(f"Connecting to RocksDB SID store endpoint: {endpoint_url}")
    
    payload = {
        'sids': sids
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=10)
        
        # 2. Fallback: HTTP Status Code Error
        if response.status_code != 200:
            elapsed_time = time.time() - start_time
            logger.error(
                f"Fallback triggered: RocksDB SID store returned non-200 status code: {response.status_code}. "
                f"Response: {response.text}. Executed in {elapsed_time:.4f}s"
            )
            return Response.error(f"RocksDB SID store request failed with status {response.status_code}")
        
        # 3. Fallback: JSON Decode Error
        try:
            response_data = response.json()
        except ValueError as json_err:
            elapsed_time = time.time() - start_time
            logger.error(
                f"Fallback triggered: Failed to decode JSON response from RocksDB SID store. "
                f"Error: {json_err}. Raw response: {response.text}. Executed in {elapsed_time:.4f}s"
            )
            return Response.error("Invalid JSON response from RocksDB SID store")
        
        logger.debug(f"RocksDB response payload: {response_data}")
        
        # Define the exact expected structure
        expected_keys = ['sid', 'opt_id', 'pkt_type', 'station_id', 'machine_code', 'created_at']
        
        # Helper function to ensure exact structure and fill missing keys with None
        def format_item(item_dict):
            return {key: item_dict.get(key) for key in expected_keys}
        
        # Helper function to create a null structure for missing SIDs
        def create_null_item(sid):
            return {
                'sid': sid,
                'opt_id': None,
                'pkt_type': None,
                'station_id': None,
                'machine_code': None,
                'created_at': None
            }

        # 4. Business Logic Check: Status OK
        if response_data.get('status') == 'OK':
            items_from_rocksdb = response_data.get('items', [])
            
            # Create a lookup map: { 'sid_value': {item_data} }
            rocksdb_map = {
                item.get('sid'): item 
                for item in items_from_rocksdb 
                if isinstance(item, dict) and item.get('sid')
            }
            
            # Build the final list: Match the original requested sids list perfectly
            final_sids_info = []
            for sid in sids:
                if sid in rocksdb_map:
                    # SID found, format it to exact structure
                    final_sids_info.append(format_item(rocksdb_map[sid]))
                else:
                    # SID missing in RocksDB response, append null structure
                    final_sids_info.append(create_null_item(sid))
            
            elapsed_time = time.time() - start_time
            logger.info(
                f"Successfully processed details. Requested: {len(sids)}, "
                f"Found: {len(items_from_rocksdb)}. Executed in {elapsed_time:.4f}s"
            )
            return Response.success("SID details retrieved successfully", {"sids_info": final_sids_info})
        
        # 5. Fallback: API responded successfully, but status not OK (Return full list with nulls)
        else:
            elapsed_time = time.time() - start_time
            logger.warning(
                f"Fallback triggered: RocksDB status not OK. Status: {response_data.get('status')}. "
                f"Returning null values for all {len(sids)} requested sids. Executed in {elapsed_time:.4f}s"
            )
            
            # Even if status is not OK, return the full list of requested sids with null values
            final_sids_info = [create_null_item(sid) for sid in sids]
            return Response.success("No SID details found", {"sids_info": final_sids_info})
            
    except requests.exceptions.Timeout:
        # 6. Fallback: Timeout
        elapsed_time = time.time() - start_time
        logger.error(f"Fallback triggered: Request timed out while connecting to RocksDB SID endpoint {endpoint_url}. Executed in {elapsed_time:.4f}s")
        return Response.error("Request to RocksDB SID store timed out")
        
    except requests.exceptions.RequestException as req_err:
        # 7. Fallback: General Network Error
        elapsed_time = time.time() - start_time
        logger.error(f"Fallback triggered: Network error occurred while fetching SID details. Error: {req_err}. Executed in {elapsed_time:.4f}s")
        return Response.error(f"Network error: {str(req_err)}")
        
    except Exception as e:
        # 8. Fallback: Unhandled Exception
        elapsed_time = time.time() - start_time
        logger.exception(f"Fallback triggered: An unexpected error occurred while fetching SID details. Error: {e}. Executed in {elapsed_time:.4f}s")
        return Response.error(f"An unexpected error occurred: {str(e)}")