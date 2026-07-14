import logging
from typing import Dict, Any, List
import requests
from utils.response import Response
from enums.queries import OperatorDetailQueries as Queries
from utils.database import db
from config.config import config
from opt_details.info import get_operator_details
from datetime import datetime, timezone
from sid_details.info import get_sid_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_all_sids_date(opt_id: str, date_str: str):
    rocksdb_config_operator_store = config.get('rocksdb_operator_store')
    if not rocksdb_config_operator_store:
        logger.error("Fallback triggered: RocksDB configuration missing")
        return Response.error("RocksDB configuration missing")

    endpoint = rocksdb_config_operator_store.get('endpoint') 
    endpoint_url = f"http://{rocksdb_config_operator_store.get('host')}:{rocksdb_config_operator_store.get('port')}{endpoint}"
    logger.info(f"Step 1: Connecting to RocksDB Operator store endpoint: {endpoint_url}")
    
    payload = {
        "opt_id": opt_id,
        "date": date_str
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Fallback triggered: Operator store returned non-200 status code: {response.status_code}. Response: {response.text}")
            return Response.error(f"Operator store request failed with status {response.status_code}")
        
        try:
            data = response.json()
        except ValueError as json_err:
            logger.error(f"Fallback triggered: Failed to decode JSON from Operator store. Error: {json_err}. Raw response: {response.text}")
            return Response.error("Invalid JSON response from Operator store")
        
        records = data.get("Results", [])
        
        if records:
            logger.info(f"Successfully fetched {len(records)} SIDs. Proceeding to Step 2: Fetching SID details.")
            
            # --- INTEGRATED GET_SID_DETAILS CALL ---
            sid_details_response = get_sid_details(records)
            
            # Safely attempt to extract the data dictionary from the Response object
            # (Assuming your Response object stores the payload in a `.data` attribute)
            details_data = {}
            if hasattr(sid_details_response, 'data') and isinstance(sid_details_response.data, dict):
                details_data = sid_details_response.data
            elif isinstance(sid_details_response, dict): # Fallback if Response is just a dict
                details_data = sid_details_response.get('data', {})
            
            # Extract the sids_info list, defaulting to empty list if missing
            sids_info = details_data.get("sids_info", [])
            
            return Response.success(
                f"SIDs and details retrieved successfully for operator id: {opt_id}, date={date_str}",
                {
                    "sids": records,          # The original list of SIDs
                    "sids_info": sids_info    # The detailed info fetched in Step 2
                }
            )
        else:
            logger.warning(f"Fallback triggered: No SIDs found for opt_id={opt_id}, date={date_str}.")
            return Response.success(
                f"No SIDs found for the operator id: {opt_id}, date={date_str}",
                {"sids": [], "sids_info": []}
            )
            
    except requests.exceptions.Timeout:
        logger.error(f"Fallback triggered: Request timed out while connecting to Operator endpoint {endpoint_url}")
        return Response.error("Request to Operator store timed out")
        
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Fallback triggered: Network error occurred while fetching SIDs. Error: {req_err}")
        return Response.error(f"Failed to connect to Operator store: {str(req_err)}")
        
    except Exception as e:
        logger.exception(f"Fallback triggered: An unexpected error occurred while fetching SIDs. Error: {e}")
        return Response.error(f"An unexpected error occurred: {str(e)}")








