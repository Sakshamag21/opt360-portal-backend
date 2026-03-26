

import logging

from typing import List, Dict, Any, Optional

from utils.response import Response
from enums.message import SignalMessage 
from enums.queries import SignalQueries as Queries
from utils.database import db
# Configure logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_signal(request: dict) -> Response :

    try:
        _validate_request(request)

        result = check_signal_exists(request["id"], request["feature_id"])
        
        # Handle version: result is a list with dict, max_version can be None if no records exist
        if result and len(result) > 0 and result[0].get('max_version') is not None:
            version = int(result[0].get('max_version'))
        else:
            version = 0
        
        new_version = version + 1
        logger.info(f"Creating signal {request['id']} with version {new_version}")
        query = Queries.CREATE_SIGNAL
        params = (
            request["id"],
            request["name"],
            new_version,
            request["description"],
            request["feature_id"],
            request["feature_version"],
            request["threshold"],
            request["severity_level"],
            request["user"]
        )
        
        result = db.execute_write(query, params)
        
        # Check if database write was successful
        if result is None:
            return Response.error("Failed to create signal in database")
     
        return Response.success(SignalMessage.SIGNAL_CREATED.format(
            id=request["id"],
            feature_id=request["feature_id"],
            feature_version=request["feature_version"],
            threshold=request["threshold"],
            severity_level=request["severity_level"]
        ))

    except ValueError as ve:
        return Response.error(str(ve))
    except Exception as e:
        return Response.error(f"An unexpected error occurred: {str(e)}")
    

def check_signal_exists(signal_id: str, feature_id: str) -> Optional[List[Dict[str, Any]]]:
    query = Queries.RETRIEVE_SIGNAL_VERSION
    params = (signal_id, feature_id)
    result = db.execute_query(query, params)
    return result
    # if result and result[0][0] > 0:
    #     raise ValueError(f"Signal with ID {signal_id} already exists")

def _validate_request(request: dict) -> bool:
    required_fields = ["id", "name", "description", "feature_id", "feature_version", "threshold", "severity_level", "user"] 
    for field in required_fields:
        if field not in request:
            raise ValueError(SignalMessage.SIGNAL_VALUE_MISSING.format(field=field))
    return True
