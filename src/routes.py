"""
API Routes for Operator360 API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from config.config import config
import signals.create as signal_create
import signals.info as signal_info
import signals.info_id as signal_info_id
import feature.get_feature as feature_info
import opt_details.info as operator_info

# Create routers
health_router = APIRouter(prefix="", tags=["Health"])
signal_router = APIRouter(prefix="/signal", tags=["Signals"])
feature_router = APIRouter(prefix="/feature", tags=["Features"])
opt_router = APIRouter(prefix='/opt_details',tags=["Operator Details"])

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
            "path": "/api/opt_details/info/{operator_id}",
            "method": "GET",
            "tag": "Operator Details",
            "summary": "Get Operator Information",
            "description": "Get metadata related to the corresponding Operator Id",
            "parameters": [
                {
                    "name": "operator_id",
                    "in": "path",
                    "required": True,
                    "type": "string",
                    "description": "The unique identifier of the operator(in uppercase)"
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

@opt_router.post('/info/{operator_id}')
def get_operator_details(request: dict) -> Dict[str,Any]:
    
    return operator_info.get_operator_details(request=request)

# List of all routers to include in main app
routers = [
    health_router,
    signal_router,
    feature_router,
    opt_router
]
