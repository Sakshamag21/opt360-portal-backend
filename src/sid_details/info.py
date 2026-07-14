import logging
from typing import Dict, Any, List  # Added List import
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
        # Added timeout=10 to prevent hanging indefinitely
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=10)
        
        # 2. Fallback: HTTP Status Code Error
        if response.status_code != 200:
            logger.error(
                f"Fallback triggered: RocksDB SID store returned non-200 status code: {response.status_code}. "
                f"Response: {response.text}"
            )
            return Response.error(f"RocksDB SID store request failed with status {response.status_code}")
        
        # 3. Fallback: JSON Decode Error
        try:
            response_data = response.json()
        except ValueError as json_err:
            logger.error(
                f"Fallback triggered: Failed to decode JSON response from RocksDB SID store. "
                f"Error: {json_err}. Raw response: {response.text}"
            )
            return Response.error("Invalid JSON response from RocksDB SID store")
        
        logger.debug(f"RocksDB response payload: {response_data}") # Changed to debug to avoid logging too much INFO in prod
        
        # 4. Business Logic Check: Status OK and items found
        if response_data.get('status') == 'OK' and response_data.get('found', 0) >= 1:
            items = response_data.get('items', [])
            logger.info(f"Successfully retrieved details for {len(items)} SIDs.")
            return Response.success("Operator details retrieved successfully", {"sids_info": items})
        
        # 5. Fallback: API responded successfully, but no SIDs were found
        else:
            logger.warning(
                f"Fallback triggered: No SID details found or status not OK. "
                f"Status: {response_data.get('status')}, Found: {response_data.get('found')}. "
                f"Returning empty sids_info."
            )
            return Response.success("No SID details found", {"sids_info": []})
            
    except requests.exceptions.Timeout:
        # 6. Fallback: Timeout
        logger.error(f"Fallback triggered: Request timed out while connecting to RocksDB SID endpoint {endpoint_url}")
        return Response.error("Request to RocksDB SID store timed out")
        
    except requests.exceptions.RequestException as req_err:
        # 7. Fallback: General Network Error
        logger.error(f"Fallback triggered: Network error occurred while fetching SID details. Error: {req_err}")
        return Response.error(f"Network error: {str(req_err)}")
        
    except Exception as e:
        # 8. Fallback: Unhandled Exception
        logger.exception(f"Fallback triggered: An unexpected error occurred while fetching SID details. Error: {e}")
        return Response.error(f"An unexpected error occurred: {str(e)}")