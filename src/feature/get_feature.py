
import logging
from typing import Dict, Any

from enums.message import ErrorMessage, FeatureMessage
from utils.response import Response
from enums.queries import FeatureQueries as Queries
from utils.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_feature(request: dict) -> Dict[str, Any]:

    try:
        _validate_request(request)
        
        # Start with base query ending with WHERE
        query = Queries.GET_FEATURE_METADATA_GLOBAL
        params = []
        filters = []
        
        # feature_id is optional - if not provided, return all features
        if "feature_id" in request:
            filters.append("feature_name = %s")
            params.append(request["feature_id"])
        
        # Add optional filters - can be combined
        if "version" in request:
            filters.append("version = %s")
            params.append(request["version"])

        if "active" in request and request["active"] == True:
            filters.append("is_active = true")
        
        if "is_risk" in request and request["is_risk"] == True:
            filters.append("is_risk = true")

        if "status" in request:
            filters.append("status = %s")
            params.append(request["status"])
        
        # Build final query - if no filters, remove trailing WHERE
        if filters:
            query += " AND ".join(filters)
        else:
            # Remove trailing "WHERE " if no filters (return all features)
            if query.endswith("WHERE "):
                query = query[:-6]  # Remove last 6 characters "WHERE "
        
        params_tuple = tuple(params)
        logger.info(f"Query: {query}, Params: {params_tuple}")
        
        result = db.execute_query(query, params_tuple)

        if result is None:
            logger.error(f"Database query failed")
            return Response.error("Failed to retrieve features from database")
        
        if len(result) == 0:
            feature_id = request.get("feature_id", "N/A")
            logger.info(f"No features found with given criteria. Feature ID: {feature_id}")
            return Response.error(
                FeatureMessage.FEATTURE_NOT_FOUND.format(
                    feature_id=feature_id, 
                    version=request.get("version", "N/A")
                )
            )
        
        feature_id = request.get("feature_id", "All")
        logger.info(f"Feature(s) retrieved: {feature_id}, {len(result)} record(s)")
        return Response.success(
            FeatureMessage.FEATURE_RETRIEVED.format(
                feature_id=feature_id, 
                version=request.get("version", "N/A")
            ), 
            {"feature": result, "count": len(result)}
        )
        
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return Response.error(ErrorMessage.FIELD_NOT_FOUND.format(field=str(ve)))
    except Exception as e:
        logger.error(f"Unexpected error in get_feature: {str(e)}")
        return Response.error(f"An unexpected error occurred: {str(e)}")


def _validate_request(request: dict) -> bool:
    if request is None:
        raise ValueError("Request body is missing")
    # feature_id is optional - no validation needed if absent
    return True