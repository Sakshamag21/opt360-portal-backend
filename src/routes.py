"""
API Routes for Operator360 API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from config.config import config
import signals.create as signal_create
import signals.info as signal_info
import feature.get_feature as feature_info

# Create routers
health_router = APIRouter(prefix="", tags=["Health"])
signal_router = APIRouter(prefix="/signal", tags=["Signals"])
feature_router = APIRouter(prefix="/feature", tags=["Features"])


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


# Feature Routes
@feature_router.post("/info/")
def get_feature_info(request: dict) -> Dict[str, Any]:
    """
    Get feature information
    
    Required fields in request body
    """
    return feature_info.get_feature(request=request)


# List of all routers to include in main app
routers = [
    health_router,
    signal_router,
    feature_router
]
