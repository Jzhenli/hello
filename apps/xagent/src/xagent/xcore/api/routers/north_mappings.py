import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List

from ..models.north_channel import (
    NorthMappingCreate,
    NorthMappingUpdate,
    NorthMappingResponse,
    NorthMappingListResponse,
    NorthMappingCreateResponse,
    NorthMappingUpdateResponse,
    NorthMappingBatchCreateResponse,
    NorthMappingExportResponse,
)
from ..services.north_mapping_service import NorthMappingService
from ..dependencies import get_metadata_manager, get_app_state
from .config import verify_api_token
from ...core.metadata import MetadataManager
from ...core.event_bus import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels/{channel_id}/mappings", tags=["North Mappings"])


def _get_event_bus() -> Optional[EventBus]:
    state = get_app_state()
    if state.gateway and hasattr(state.gateway, "event_bus"):
        return state.gateway.event_bus
    return None


def get_north_mapping_service(
    metadata_manager: MetadataManager = Depends(get_metadata_manager),
) -> NorthMappingService:
    if metadata_manager is None:
        raise HTTPException(status_code=500, detail="MetadataManager not initialized")
    event_bus = _get_event_bus()
    return NorthMappingService(metadata_manager, event_bus)


def handle_value_error(e: ValueError) -> HTTPException:
    error_msg = str(e)
    if "not found" in error_msg:
        return HTTPException(status_code=404, detail=error_msg)
    elif "already exists" in error_msg:
        return HTTPException(status_code=409, detail=error_msg)
    else:
        return HTTPException(status_code=400, detail=error_msg)


@router.get("/", response_model=NorthMappingListResponse)
async def list_mappings(
    channel_id: int,
    asset: Optional[str] = Query(None, description="Filter by asset"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled"),
    service: NorthMappingService = Depends(get_north_mapping_service),
):
    mappings = await service.list_mappings(
        channel_id=channel_id, asset=asset, enabled=enabled
    )
    return NorthMappingListResponse(
        count=len(mappings),
        mappings=[NorthMappingResponse(**m) for m in mappings],
    )


@router.get("/{mapping_id}", response_model=NorthMappingResponse)
async def get_mapping(
    channel_id: int,
    mapping_id: int,
    service: NorthMappingService = Depends(get_north_mapping_service),
):
    mapping = await service.get_mapping(mapping_id)
    if not mapping or mapping.get("channel_id") != channel_id:
        raise HTTPException(status_code=404, detail=f"Mapping '{mapping_id}' not found")
    return NorthMappingResponse(**mapping)


@router.post(
    "/",
    response_model=NorthMappingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    channel_id: int,
    mapping: NorthMappingCreate,
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    data = mapping.model_dump()
    data["channel_id"] = channel_id
    if mapping.value_transform:
        data["value_transform"] = mapping.value_transform.model_dump()
    try:
        created = await service.create_mapping(data, user="api")
        return NorthMappingCreateResponse(
            success=True,
            message=f"Mapping created for asset={created['asset']}, point={created['point_name']}",
            mapping_id=created["id"],
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error creating mapping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{mapping_id}", response_model=NorthMappingUpdateResponse)
async def update_mapping(
    channel_id: int,
    mapping_id: int,
    updates: NorthMappingUpdate,
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    update_data = updates.model_dump(exclude_none=True)
    if updates.value_transform:
        update_data["value_transform"] = updates.value_transform.model_dump()
    try:
        updated = await service.update_mapping(mapping_id, update_data, user="api")
        return NorthMappingUpdateResponse(
            success=True,
            message=f"Mapping '{mapping_id}' updated successfully",
            mapping_id=mapping_id,
            updated_fields=list(update_data.keys()),
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error updating mapping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{mapping_id}")
async def delete_mapping(
    channel_id: int,
    mapping_id: int,
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    try:
        await service.delete_mapping(mapping_id, user="api")
        return {"success": True, "message": f"Mapping '{mapping_id}' deleted successfully"}
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error deleting mapping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch", response_model=NorthMappingBatchCreateResponse)
async def batch_create_mappings(
    channel_id: int,
    mappings: List[NorthMappingCreate],
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    data_list = []
    for m in mappings:
        d = m.model_dump()
        d["channel_id"] = channel_id
        if m.value_transform:
            d["value_transform"] = m.value_transform.model_dump()
        data_list.append(d)
    result = await service.batch_create_mappings(data_list, user="api")
    return NorthMappingBatchCreateResponse(**result)


@router.post("/import")
async def import_mappings(
    channel_id: int,
    data: dict,
    overwrite: bool = Query(False),
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    mappings_data = data.get("mappings", [])
    if not mappings_data:
        raise HTTPException(status_code=400, detail="No mappings data provided")
    return await service.import_mappings(
        {"mappings": mappings_data}, channel_id, overwrite=overwrite, user="api"
    )


@router.get("/export", response_model=NorthMappingExportResponse)
async def export_mappings(
    channel_id: int,
    service: NorthMappingService = Depends(get_north_mapping_service),
):
    return await service.export_mappings(channel_id)


@router.delete("/")
async def delete_all_mappings(
    channel_id: int,
    service: NorthMappingService = Depends(get_north_mapping_service),
    token: str = Depends(verify_api_token),
):
    count = await service.delete_mappings_by_channel(channel_id, user="api")
    return {"success": True, "message": f"Deleted {count} mappings for channel {channel_id}"}
