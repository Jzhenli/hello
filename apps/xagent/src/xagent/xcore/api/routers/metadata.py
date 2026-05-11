"""Metadata API routes"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from ..dependencies import get_metadata_manager
from ...core.metadata import MetadataManager, RegistryStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["Metadata"])


@router.get("/devices")
async def list_devices(
    status: Optional[str] = Query(None, description="Filter by status: active or deleted"),
    mm: MetadataManager = Depends(get_metadata_manager)
):
    devices = await mm.get_all_devices(status=status)
    return {
        "count": len(devices),
        "devices": [d.to_dict() for d in devices]
    }


@router.get("/devices/active")
async def list_active_devices(
    mm: MetadataManager = Depends(get_metadata_manager)
):
    devices = await mm.get_all_active_devices()
    return {
        "count": len(devices),
        "devices": [d.to_dict() for d in devices]
    }


@router.get("/devices/{asset}")
async def get_device(
    asset: str,
    mm: MetadataManager = Depends(get_metadata_manager)
):
    device = await mm.get_device(asset)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{asset}' not found")
    return device.to_dict()


@router.get("/devices/{asset}/status")
async def get_device_status(
    asset: str,
    mm: MetadataManager = Depends(get_metadata_manager)
):
    status = await mm.get_device_status(asset)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Device '{asset}' not found")
    return {
        "asset": asset,
        "status": status
    }


@router.get("/devices/{asset}/points")
async def list_device_points(
    asset: str,
    status: Optional[str] = Query(None, description="Filter by status: active or deleted"),
    mm: MetadataManager = Depends(get_metadata_manager)
):
    device = await mm.get_device(asset)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{asset}' not found")
    
    points = await mm.get_device_points(asset, status=status)
    return {
        "asset": asset,
        "count": len(points),
        "points": [p.to_dict() for p in points]
    }


@router.get("/points/{asset}/{point_name}")
async def get_point(
    asset: str,
    point_name: str,
    mm: MetadataManager = Depends(get_metadata_manager)
):
    point = await mm.get_point(asset, point_name)
    if not point:
        raise HTTPException(
            status_code=404, 
            detail=f"Point '{point_name}' not found for device '{asset}'"
        )
    return point.to_dict()


@router.get("/stats")
async def get_metadata_stats(
    mm: MetadataManager = Depends(get_metadata_manager)
):
    active_devices = await mm.get_all_active_devices()
    all_devices = await mm.get_all_devices()
    deleted_devices = [d for d in all_devices if d.status == RegistryStatus.DELETED]
    
    points_stats = await mm.get_points_stats()
    
    return {
        "devices": {
            "total": len(all_devices),
            "active": len(active_devices),
            "deleted": len(deleted_devices)
        },
        "points": {
            "total": points_stats["total_points"],
            "active": points_stats["active_points"]
        }
    }
