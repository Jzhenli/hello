"""System API routes"""

import time
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_storage, get_buffer, get_app_state, get_gateway
from ..models.system import HealthResponse
from ...storage import StorageInterface, WriteBehindBuffer

router = APIRouter(tags=["System"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=time.time()
    )


@router.get("/api/ready")
async def readiness_check():
    state = get_app_state()
    if not state.is_initialized():
        raise HTTPException(status_code=503, detail="Not ready")
    return {"status": "ready"}


@router.get("/api/stats")
async def get_stats(
    storage: StorageInterface = Depends(get_storage),
    buffer: WriteBehindBuffer = Depends(get_buffer)
):
    storage_stats = await storage.get_stats(include_device_status=True)
    buffer_stats = buffer.get_stats()
    
    return {
        "storage": storage_stats,
        "buffer": {
            "pending_count": buffer_stats.pending_count,
            "total_writes": buffer_stats.total_writes,
            "total_flushes": buffer_stats.total_flushes,
            "last_flush": buffer_stats.last_flush.isoformat() if buffer_stats.last_flush else None
        }
    }


@router.get("/api/system/startup-status")
async def get_startup_status(gateway = Depends(get_gateway)):
    status = {
        "core_started": False,
        "plugins_started": False,
        "total_plugins": 0,
        "load_success": 0,
        "start_success": 0,
        "failed": []
    }
    
    if gateway:
        status = gateway.get_plugin_startup_status()
    
    return status
