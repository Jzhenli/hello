import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional

from ..models.north_channel import (
    NorthChannelCreate,
    NorthChannelUpdate,
    NorthChannelResponse,
    NorthChannelCreateResponse,
    NorthChannelUpdateResponse,
    NorthChannelListResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
)
from ..services.north_channel_service import NorthChannelService
from ..dependencies import get_metadata_manager, get_app_state
from .config import verify_api_token
from ...core.metadata import MetadataManager
from ...core.event_bus import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["North Channels"])


def _get_event_bus() -> Optional[EventBus]:
    state = get_app_state()
    if state.gateway and hasattr(state.gateway, "event_bus"):
        return state.gateway.event_bus
    return None


def _get_orchestrator():
    state = get_app_state()
    if state.gateway and hasattr(state.gateway, "container"):
        try:
            from ...services.orchestration.north_channel_orchestrator import NorthChannelOrchestrator
            return state.gateway.container.try_resolve(NorthChannelOrchestrator)
        except Exception:
            pass
    return None


def get_north_channel_service(
    metadata_manager: MetadataManager = Depends(get_metadata_manager),
) -> NorthChannelService:
    if metadata_manager is None:
        raise HTTPException(status_code=500, detail="MetadataManager not initialized")
    event_bus = _get_event_bus()
    orchestrator = _get_orchestrator()
    return NorthChannelService(metadata_manager, event_bus, orchestrator)


def handle_value_error(e: ValueError) -> HTTPException:
    error_msg = str(e)
    if "not found" in error_msg:
        return HTTPException(status_code=404, detail=error_msg)
    elif "already exists" in error_msg:
        return HTTPException(status_code=409, detail=error_msg)
    else:
        return HTTPException(status_code=400, detail=error_msg)


@router.post(
    "/",
    response_model=NorthChannelCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    channel: NorthChannelCreate,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        created = await service.create_channel(channel.model_dump(), user="api")
        return NorthChannelCreateResponse(
            success=True,
            message=f"Channel '{created['name']}' created successfully",
            channel_id=created["id"],
            requires_restart=False,
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error creating channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=NorthChannelListResponse)
async def list_channels(
    status: Optional[str] = Query(None, description="Filter by status"),
    plugin_name: Optional[str] = Query(None, description="Filter by plugin name"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled"),
    service: NorthChannelService = Depends(get_north_channel_service),
):
    channels = await service.list_channels(status=status, enabled=enabled, plugin_name=plugin_name)
    return NorthChannelListResponse(
        count=len(channels),
        channels=[NorthChannelResponse(**c) for c in channels],
    )


@router.get("/{channel_id}", response_model=NorthChannelResponse)
async def get_channel(
    channel_id: int,
    service: NorthChannelService = Depends(get_north_channel_service),
):
    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    return NorthChannelResponse(**channel)


@router.put("/{channel_id}", response_model=NorthChannelUpdateResponse)
async def update_channel(
    channel_id: int,
    updates: NorthChannelUpdate,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        update_data = updates.model_dump(exclude_none=True)
        updated = await service.update_channel(channel_id, update_data, user="api")
        return NorthChannelUpdateResponse(
            success=True,
            message=f"Channel '{channel_id}' updated successfully",
            channel_id=channel_id,
            updated_fields=list(update_data.keys()),
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error updating channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        await service.delete_channel(channel_id, user="api")
        return {"success": True, "message": f"Channel '{channel_id}' deleted successfully"}
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error deleting channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{channel_id}/toggle", response_model=NorthChannelUpdateResponse)
async def toggle_channel(
    channel_id: int,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        updated = await service.toggle_channel(channel_id, user="api")
        return NorthChannelUpdateResponse(
            success=True,
            message=f"Channel '{channel_id}' toggled successfully",
            channel_id=channel_id,
            updated_fields=["enabled"],
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error toggling channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    request: ConnectionTestRequest,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        if request.channel_id:
            result = await service.test_connection(request.channel_id)
        else:
            result = {
                "success": True,
                "message": "Manual connection test not supported, use channel_id",
            }
        return ConnectionTestResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            latency=result.get("latency"),
            details=result.get("details"),
        )
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return ConnectionTestResponse(success=False, message=f"Connection test failed: {str(e)}")


@router.get("/{channel_id}/statistics")
async def get_channel_statistics(
    channel_id: int,
    service: NorthChannelService = Depends(get_north_channel_service),
):
    statistics = await service.get_channel_statistics(channel_id)
    if not statistics:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    return statistics


@router.post("/{channel_id}/restart")
async def restart_channel(
    channel_id: int,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    try:
        result = await service.restart_channel(channel_id)
        return result
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error restarting channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch")
async def batch_create_channels(
    channels: List[NorthChannelCreate],
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    result = await service.batch_create_channels(
        [c.model_dump() for c in channels], user="api"
    )
    return result


@router.post("/export")
async def export_channels(
    channel_ids: Optional[List[int]] = Query(None),
    service: NorthChannelService = Depends(get_north_channel_service),
):
    return await service.export_channels(channel_ids)


@router.post("/import")
async def import_channels(
    data: dict,
    overwrite: bool = Query(False),
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token),
):
    channels_data = data.get("channels", [])
    if not channels_data:
        raise HTTPException(status_code=400, detail="No channels data provided")
    return await service.import_channels(data, overwrite=overwrite, user="api")
