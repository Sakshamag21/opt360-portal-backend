import logging
from typing import Dict, Any
import requests
from utils.response import Response
from enums.queries import OperatorDetailQueries as Queries
from utils.database import db
from config.config import config
from opt_details.info import get_operator_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sid_details(sid: str) -> Dict[str, Any]:
    rocksdb_config = config.get('rocksdb')
    if not rocksdb_config:
        return Response.error("RocksDB configuration missing")

    endpoint = rocksdb_config.get('endpoint') 
    endpoint_url = f"http://{rocksdb_config.get('host')}:{rocksdb_config.get('port')}{endpoint}"
    logger.info(f"Connecting to RocksDB endpoint: {endpoint_url}")
    
    payload = {
        'sids': [sid]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint_url, json=payload, headers=headers)
        response.raise_for_status()  # Catch HTTP errors (4xx, 5xx) early
        response_data = response.json()
        
        logger.info(f"RocksDB response payload: {response_data}")
        
        if response_data.get('status') == 'OK' and response_data.get('found') == 1:
            item_values = response_data['items'][0]['values'][0]
            opt_id = item_values['opt_id']
            pkt_type = item_values['pkt_type']
            
            operator_response = get_operator_details(opt_id)
            
            # Extract content if it's a Response object or keep as dict/list
            operator_details = operator_response.json() if hasattr(operator_response, 'json') else operator_response
            
            logger.info(f"Extracted operator_details structure: {operator_details}")
            
            operator_data = None
            is_valid_response = False

            # Case 1: Raw list returned directly (Matches your database log style)
            if isinstance(operator_details, list):
                operator_data = operator_details
                is_valid_response = True
                
            # Case 2: Dictionary wrapper standard handling
            elif isinstance(operator_details, dict):
                # Flexible validation (Check for 'status' == 'OK' OR standard success boolean flags)
                if operator_details.get('status') == 'OK' or operator_details.get('success') is True:
                    is_valid_response = True
                    # Look inside 'operator' key or fallback to a 'data' wrapper
                    operator_data = operator_details.get('operator') or operator_details.get('data')
                
                # If the wrapper didn't have a status key but directly contains 'operator' data
                elif 'operator' in operator_details:
                    is_valid_response = True
                    operator_data = operator_details.get('operator')

            if is_valid_response and operator_data:
                # Safety check: Handle if operator data is inside a list wrapper
                if isinstance(operator_data, list) and len(operator_data) > 0:
                    record = operator_data[0]
                    record['pktType'] = pkt_type
                    record['id'] = sid
                    record['idType']='sid'
                    return Response.success("Operator details retrieved successfully", {"operator": operator_data})
                
                # Handle if operator data is a direct dictionary
                elif isinstance(operator_data, dict):
                    operator_data['pktType'] = pkt_type
                    operator_data['id'] = sid
                    operator_data['idType']='sid'
                    return Response.success("Operator details retrieved successfully", {"operator": operator_data})
                
                return Response.error(f"No operator record data structure valid for opt_id: {opt_id}")
                
            return Response.error(f"Failed to validate operator details for opt_id: {opt_id}. Response payload keys mismatch.")
            
        return Response.error(f"SID {sid} not found in RocksDB")
        
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network error verification failed for SID {sid}: {str(req_err)}")
        return Response.error(f"Network error: {str(req_err)}")
    except Exception as e:
        logger.error(f"Error processing SID {sid}: {str(e)}", exc_info=True)
        return Response.error(f"An unexpected error occurred: {str(e)}")
