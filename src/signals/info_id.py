
import logging
from typing import Dict, Any

from utils.response import Response
from enums.queries import SignalQueries as Queries
from utils.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_feature_signals(signal_id: str) -> Dict[str, Any]:
    """
    Retrieve information about a specific signal based on its ID and associated feature ID.

    Args:
        signal_id (str): The unique identifier of the associated feature.

    Returns:
        Dict: A Response dictionary containing the signal information or an error message.
    """
    try:
        query = Queries.RETRIEVE_SIGNAL_BY_ID
        params = (signal_id,)
        result = db.execute_query(query, params)
        
        # Handle None or failed database query
        if result is None:
            logger.error(f"Database query failed for signal_id: {signal_id}")
            return Response.error("Failed to retrieve signals from database")
        
        # Handle empty result
        if not result or len(result) == 0:
            logger.info(f"No active signals found for signal_id: {signal_id}")
            return Response.success("No active signals found", {"signals": [], "count": 0})
        
        logger.info(f"Retrieved {len(result)} signals for signal_id: {signal_id}")
        return Response.success(
            "Signals retrieved successfully", 
            {"signals": result, "count": len(result)}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving signals for signal_id {signal_id}: {str(e)}")
        return Response.error(f"An error occurred while retrieving signals: {str(e)}")