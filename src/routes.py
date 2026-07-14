"""
API Routes for Operator360 API
"""
from fastapi import APIRouter, HTTPException, Body, Request
from typing import Dict, Any, List
from utils.response import Response
from config.config import config
import signals.create as signal_create
import signals.info as signal_info
import signals.info_id as signal_info_id
import feature.get_feature as feature_info
import opt_details.info as operator_info
import opt_details.get_sid as sid_info
import sid_details.all_sids as sid_details
from datetime import datetime



# Create routers
health_router = APIRouter(prefix="", tags=["Health"])
signal_router = APIRouter(prefix="/signal", tags=["Signals"])
feature_router = APIRouter(prefix="/feature", tags=["Features"])
opt_router = APIRouter(prefix='/opt_details',tags=["Operator Details"])
sid_router= APIRouter(prefix='/sid_details',tags=["SID Details"])

# Health Check Routes
@health_router.get("/")
def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    db_config = config.database
    return {
        "status": "healthy",
        "service": "operator360-api",
        "database_host": db_config.get("host", "Not configured")
    }


@health_router.get("/health")
def detailed_health() -> Dict[str, Any]:
    """Detailed health check with database connection test"""
    from utils.database import db
    
    db_status = "connected" if db.test_connection() else "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "operator360-api",
        "database": db_status
    }


@health_router.get("/endpoints")
def get_endpoints_info() -> Dict[str, Any]:
    """
    Get information about all available API endpoints
    
    Returns a comprehensive list of all endpoints with their methods, paths, and descriptions.
    """
    endpoints = [
        {
            "path": "/api/",
            "method": "GET",
            "tag": "Health",
            "summary": "Health check endpoint",
            "description": "Basic health check to verify service is running",
            "parameters": [],
            "request_body": None
        },
        {
            "path": "/api/health",
            "method": "GET",
            "tag": "Health",
            "summary": "Detailed health check",
            "description": "Detailed health check with database connection test",
            "parameters": [],
            "request_body": None
        },
        {
            "path": "/api/endpoints",
            "method": "GET",
            "tag": "Health",
            "summary": "API endpoints information",
            "description": "Get information about all available API endpoints",
            "parameters": [],
            "request_body": None
        },
        {
            "path": "/api/signal/create",
            "method": "POST",
            "tag": "Signals",
            "summary": "Create a new signal",
            "description": "Create a new signal with specified parameters",
            "parameters": [],
            "request_body": {
                "required_fields": [
                    "id", "name", "description", "feature_id", 
                    "feature_version", "threshold", "severity_level", "user"
                ],
                "example": {
                    "id": "SIG001",
                    "name": "Sample Signal",
                    "description": "Signal description",
                    "feature_id": "FEAT001",
                    "feature_version": "1.0",
                    "threshold": 0.85,
                    "severity_level": "high",
                    "user": "admin"
                }
            }
        },
        {
            "path": "/api/signal/info/id/{signal_id}",
            "method": "GET",
            "tag": "Signals",
            "summary": "Get signals by signal ID",
            "description": "Get all active signals correcsponding to a signal id",
            "parameters": [
                {
                    "name": "signal_id",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "The identifier of the signal"
                }
            ],
            "request_body": None
        },
        {
            "path": "/api/signal/info/{feature_id}",
            "method": "GET",
            "tag": "Signals",
            "summary": "Get signals by feature ID",
            "description": "Get all active signals for a specific feature",
            "parameters": [
                {
                    "name": "feature_id",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "The unique identifier of the feature"
                }
            ],
            "request_body": None
        },
        {
            "path": "/api/feature/info/",
            "method": "POST",
            "tag": "Features",
            "summary": "Get feature information",
            "description": "Get feature information with optional filters",
            "parameters": [],
            "request_body": {
                "required_fields": [],
                "optional_fields": [
                    "feature_id", "version", "active", "is_risk", "status"
                ],
                "examples": [
                    {
                        "description": "Get all features",
                        "value": {}
                    },
                    {
                        "description": "Get specific feature",
                        "value": {"feature_id": "FEAT001"}
                    },
                    {
                        "description": "Get specific version",
                        "value": {"feature_id": "FEAT001", "version": "1.0"}
                    },
                    {
                        "description": "Get active features",
                        "value": {"active": True}
                    },
                    {
                        "description": "Get risky features",
                        "value": {"is_risk": True}
                    }
                ]
            }
        },
        {
            "path": "/api/opt_details/info",
            "method": "POST",
            "tag": "Operator Details",
            "summary": "Get Operator Information",
            "description": "Get metadata related to the corresponding Operator Id",
            "parameters": [],
            "request_body": {
                "required_fields": ["operator_id"],
                "example": {"operator_id": "OPT12345"}
            }
        },
        {
            "path": "/api/opt_details/sid/{sid}",
            "method": "GET",
            "tag": "Operator Details for SID",
            "summary": "Get Operator information corresponding to the particular SID",
            "description": "Get metadata of the Operator related to the corresponding SID",
            "parameters": [
                {
                    "name": "sid",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "The unique identifier of the packet"
                }
            ],
            "request_body": None
        },
        
    ]
    
    return {
        "service": "operator360-api",
        "version": "1.0.0",
        "base_url": "/api",
        "total_endpoints": len(endpoints),
        "endpoints": endpoints,
        "documentation": "/docs",
        "redoc": "/redoc"
    }


# Signal Routes
@signal_router.post("/create")
def create_signal(request: dict) -> Dict[str, Any]:
    """
    Create a new signal
    
    Required fields:
    - id: Signal ID
    - name: Signal name
    - version: Signal version
    - description: Signal description
    - feature_id: Associated feature ID
    - feature_version: Feature version
    - threshold: Signal threshold
    - severity_level: Severity level
    - user: User who created the signal
    """
    return signal_create.create_signal(request=request)


@signal_router.get("/info/{feature_id}")
def get_signal_info(feature_id: str) -> Dict[str, Any]:
    """
    Get all active signals for a specific feature
    
    Args:
        feature_id: The unique identifier of the feature
    """
    return signal_info.get_feature_signals(feature_id=feature_id)

@signal_router.get("/info/id/{signal_id}")
def get_signal_info_by_id(signal_id: str) -> Dict[str, Any]:
    """
    Get all active signals for a specific feature
    
    Args:
        feature_id: The unique identifier of the feature
    """
    return signal_info_id.get_feature_signals(signal_id=signal_id)


# Feature Routes
@feature_router.post("/info/")
def get_feature_info(request: dict) -> Dict[str, Any]:
    """
    Get feature information
    
    Required fields in request body
    """
    return feature_info.get_feature(request=request)


@opt_router.post('/info')
def get_operator_details(operator_id: str = Body(..., embed=True)) -> Dict[str,Any]:
    # Notice we use 'operator_id' directly, not 'request.operator_id'
    return operator_info.get_operator_details(operator_id=operator_id)
  
  

@opt_router.get('/sid/{sid}')
def get_sid_details(sid: str) -> Dict[str,Any]:
    return sid_info.get_sid_details(sid=sid)


@sid_router.post('/sids/all')
async def get_sids_details(request: Request):
    # 1. Read the raw JSON body from the FastAPI Request object
    try:
        data = await request.json()
    except Exception:
        return Response.error("Request body must be valid JSON")

    if not data:
        return Response.error("Request body must be valid JSON")

    opt_id = data.get('opt_id')
    date_str = data.get('date')

    # 2. Validate required parameters
    missing_params = []
    if not opt_id:
        missing_params.append('opt_id')
    if not date_str:
        missing_params.append('date')

    if missing_params:
        return Response.error(
            f"Missing required parameter(s): {', '.join(missing_params)}"
        )

    # 3. Validate date format
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        date_str = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return Response.error(
            f"Invalid date format: '{date_str}'. Expected format: YYYY-MM-DD"
        )

    # 4. Call your core function
    try:
        result = sid_details.get_all_sids_date(opt_id=opt_id, date_str=date_str)
        return result

    except Exception as e:
        return Response.error(f"An unexpected error occurred: {str(e)}")    
    
    
# List of all routers to include in main app
routers = [
    health_router,
    signal_router,
    feature_router,
    opt_router,
    sid_router
]
