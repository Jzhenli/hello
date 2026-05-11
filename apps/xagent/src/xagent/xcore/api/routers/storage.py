"""Storage API routes"""

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_storage, get_cleanup_task
from ...storage import StorageInterface

router = APIRouter(tags=["Storage"])


@router.get("/api/storage/size")
async def get_storage_size(storage: StorageInterface = Depends(get_storage)):
    size_info = await storage.get_storage_size()
    return size_info


@router.get("/api/storage/cleanup/stats")
async def get_cleanup_stats(cleanup_task = Depends(get_cleanup_task)):
    if cleanup_task is None:
        return {
            "enabled": False,
            "message": "Data cleanup is disabled (retention_days=0)"
        }
    
    return {"enabled": True, **cleanup_task.get_stats()}


@router.post("/api/storage/cleanup/trigger")
async def trigger_cleanup(cleanup_task = Depends(get_cleanup_task)):
    if cleanup_task is None:
        raise HTTPException(
            status_code=400,
            detail="Data cleanup is disabled (retention_days=0)"
        )
    
    if cleanup_task.is_running():
        raise HTTPException(
            status_code=409,
            detail="Cleanup task is already running"
        )
    
    deleted = await cleanup_task.execute()
    
    return {
        "success": True,
        "deleted": deleted,
        "stats": cleanup_task.get_stats()
    }


@router.post("/api/storage/vacuum")
async def vacuum_storage(storage: StorageInterface = Depends(get_storage)):
    try:
        await storage.vacuum()
        size_info = await storage.get_storage_size()
        return {
            "success": True,
            "message": "VACUUM completed successfully",
            "storage_size": size_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VACUUM failed: {str(e)}")
