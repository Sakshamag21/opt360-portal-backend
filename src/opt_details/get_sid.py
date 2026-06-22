
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
    # Ensure endpoint format is safe
    endpoint = rocksdb_config.endpoint if rocksdb_config.endpoint.startswith('/') else '/' + rocksdb_config.endpoint
    endpoint_url = f"http://{rocksdb_config.host}:{rocksdb_config.port}{endpoint}"
    print(endpoint_url)
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
        
        if response_data.get('status') == 'OK' and response_data.get('found') == 1:
            item_values = response_data['items'][0]['values'][0]
            opt_id = item_values['opt_id']
            pkt_type = item_values['pkt_type']
            
            # Call your function. Note: If it returns a custom Response object, 
            # ensure it actually has a .json() method. If it's a dict, use operator_details directly.
            operator_response = get_operator_details(opt_id)
            
            # Handling both cases: if get_operator_details returns a dict or a Response object
            operator_details = operator_response.json() if hasattr(operator_response, 'json') else operator_response
            
            if operator_details.get('status') == 'OK':
                operator_data = operator_details.get('operator')
                
                # Safety check: if 'operator' is a list from db.execute_query, 
                # we need to modify the first dictionary element inside it.
                if isinstance(operator_data, list) and len(operator_data) > 0:
                    record = operator_data[0]
                    record['pktType'] = pkt_type
                    record['sid'] = sid
                    return Response.success("Operator details retrieved successfully", {"operator": operator_data})
                
                elif isinstance(operator_data, dict):
                    operator_data['pktType'] = pkt_type
                    operator_data['sid'] = sid
                    return Response.success("Operator details retrieved successfully", {"operator": operator_data})
                
                return Response.error(f"No operator record data found for opt_id: {opt_id}")
                
            return Response.error(f"Failed to get operator details for opt_id: {opt_id}")
            
        return Response.error(f"SID {sid} not found in RocksDB")
        
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network error verification failed for SID {sid}: {str(req_err)}")
        return Response.error(f"Network error: {str(req_err)}")
    except Exception as e:
        logger.error(f"Error processing SID {sid}: {str(e)}")
        return Response.error(f"An unexpected error occurred: {str(e)}")                
                
            
            
        
        
    
