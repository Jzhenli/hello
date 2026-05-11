"""Data API routes"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..dependencies import get_storage
from ...storage import StorageInterface

router = APIRouter(tags=["Data"])


@router.get("/api/data/readings")
async def get_readings(
    asset: Optional[str] = Query(None),
    start_time: Optional[float] = Query(None),
    end_time: Optional[float] = Query(None),
    limit: int = Query(default=100, le=1000),
    active_only: bool = Query(default=True),
    storage: StorageInterface = Depends(get_storage)
):
    readings = await storage.query(
        asset=asset,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        active_only=active_only
    )
    return {"count": len(readings), "readings": [r.to_dict() for r in readings]}


@router.delete("/api/data/readings")
async def delete_readings(
    before_timestamp: float = Query(...),
    storage: StorageInterface = Depends(get_storage)
):
    deleted = await storage.delete_old_readings(before_timestamp)
    return {"success": True, "deleted": deleted}
