import logging
from typing import Dict, Any
from utils.response import Response
from enums.queries import OperatorDetailQueries as Queries
from utils.database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_operator_details(operator_id: str) -> Dict[str, Any]:
    try:
        query = Queries.GET_OPERATOR_METADATA
        params = (operator_id.upper(),)
        result = db.execute_query(query, params)
        print(result)

        if result is None:
            logger.error(f"Database query failed for Operator Id: {operator_id}")
            return Response.error(
                f"Failed to retrieve Operator Details for operator_id:{operator_id} from database"
            )

        if not result or len(result) == 0:
            logger.info(f"No operator found for Operator Id: {operator_id}")
            return Response.success(
                "No operator found for the Id",
                {"operator": []}
            )

        logger.info(f"Retrieved Operator successfully for Operator Id: {operator_id}")
        return Response.success(
            "Operator retrieved successfully",
            {"operator": result}
        )

    except Exception as e:
        logger.error(f"Error retrieving Operator for Operator Id {operator_id}: {str(e)}")
        return Response.error(f"An error occurred while retrieving Operator: {str(e)}")
