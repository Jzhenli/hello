"""Rule Engine API routes"""

import copy
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.rules import (
    RuleCreateRequest,
    RuleUpdateRequest,
    RuleResponse,
    RuleListResponse,
    RuleOperationResponse,
    PipelineCreateRequest,
    PipelineResponse,
    PipelineListResponse,
    PipelineOperationResponse,
    ChannelCreateRequest,
    ChannelResponse,
    ChannelListResponse,
    ChannelOperationResponse,
    RuleEngineStatusResponse,
    BindChannelsRequest,
)
from ...rule_engine.orchestrator import RuleEngineOrchestrator
from ...rule_engine.pipeline import PipelineConfig, PipelineLocation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["Rule Engine"])
security = HTTPBearer()

DEFAULT_API_TOKEN = "xagent_47808"

_rule_engine: Optional[RuleEngineOrchestrator] = None


def set_rule_engine(rule_engine: RuleEngineOrchestrator) -> None:
    global _rule_engine
    _rule_engine = rule_engine


def get_rule_engine() -> RuleEngineOrchestrator:
    if _rule_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Rule Engine not initialized"
        )
    return _rule_engine


def verify_api_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    expected_token = os.environ.get("XAGENT_API_TOKEN", DEFAULT_API_TOKEN)
    
    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    return token


@router.get("/status", response_model=RuleEngineStatusResponse)
async def get_rule_engine_status(
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    status = engine.get_status()
    return RuleEngineStatusResponse(**status)


# ==================== Rules ====================

@router.get("", response_model=RuleListResponse)
async def list_rules(
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    all_rules = engine.get_all_rules()
    rules = []
    for rule_id, rule_config in all_rules.items():
        rules.append(RuleResponse(
            id=rule_id,
            name=rule_config.get("name", rule_id),
            description=rule_config.get("description"),
            enabled=rule_config.get("enabled", True),
            plugin=rule_config.get("plugin", {}),
            data_subscriptions=rule_config.get("data_subscriptions"),
            notification=rule_config.get("notification"),
            pipeline_id=engine.get_rule_pipeline(rule_id),
            channel_ids=engine.get_rule_channels(rule_id),
        ))
    
    return RuleListResponse(count=len(rules), rules=rules)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    rule_config = engine.get_rule_config(rule_id)
    if not rule_config:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    
    return RuleResponse(
        id=rule_id,
        name=rule_config.get("name", rule_id),
        description=rule_config.get("description"),
        enabled=rule_config.get("enabled", True),
        plugin=rule_config.get("plugin", {}),
        data_subscriptions=rule_config.get("data_subscriptions"),
        notification=rule_config.get("notification"),
        pipeline_id=engine.get_rule_pipeline(rule_id),
        channel_ids=engine.get_rule_channels(rule_id),
    )


@router.post("", response_model=RuleOperationResponse)
async def create_rule(
    request: RuleCreateRequest,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if engine.is_rule_loaded(request.id):
        raise HTTPException(
            status_code=409,
            detail=f"Rule '{request.id}' already exists"
        )
    
    rule_config = {
        "id": request.id,
        "name": request.name,
        "description": request.description,
        "enabled": request.enabled,
        "plugin": request.plugin.model_dump(),
        "data_subscriptions": [s.model_dump() for s in request.data_subscriptions] if request.data_subscriptions else None,
        "notification": request.notification.model_dump() if request.notification else None,
    }
    
    success = await engine.add_rule_async(
        rule_config=rule_config,
        pipeline_id=request.pipeline_id,
        channel_ids=request.channel_ids,
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create rule '{request.id}'"
        )
    
    return RuleOperationResponse(
        success=True,
        message=f"Rule '{request.id}' created successfully",
        rule_id=request.id,
    )


@router.put("/{rule_id}", response_model=RuleOperationResponse)
async def update_rule(
    rule_id: str,
    request: RuleUpdateRequest,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    existing_config = engine.get_rule_config(rule_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    
    updated_config = copy.deepcopy(existing_config)
    
    if request.name is not None:
        updated_config["name"] = request.name
    if request.description is not None:
        updated_config["description"] = request.description
    if request.enabled is not None:
        updated_config["enabled"] = request.enabled
    if request.plugin is not None:
        updated_config["plugin"] = request.plugin.model_dump()
    if request.data_subscriptions is not None:
        updated_config["data_subscriptions"] = [s.model_dump() for s in request.data_subscriptions]
    if request.notification is not None:
        updated_config["notification"] = request.notification.model_dump()
    
    current_pipeline_id = engine.get_rule_pipeline(rule_id)
    current_channel_ids = engine.get_rule_channels(rule_id)
    
    await engine.remove_rule_async(rule_id)
    
    success = await engine.add_rule_async(
        rule_config=updated_config,
        pipeline_id=request.pipeline_id if request.pipeline_id is not None else current_pipeline_id,
        channel_ids=request.channel_ids if request.channel_ids is not None else current_channel_ids,
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update rule '{rule_id}'"
        )
    
    return RuleOperationResponse(
        success=True,
        message=f"Rule '{rule_id}' updated successfully",
        rule_id=rule_id,
    )


@router.delete("/{rule_id}", response_model=RuleOperationResponse)
async def delete_rule(
    rule_id: str,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if not engine.is_rule_loaded(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    
    success = await engine.remove_rule_async(rule_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete rule '{rule_id}'"
        )
    
    return RuleOperationResponse(
        success=True,
        message=f"Rule '{rule_id}' deleted successfully",
        rule_id=rule_id,
    )


# ==================== Pipelines ====================

@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    pipelines = []
    for pipeline_id in engine.get_all_pipeline_ids():
        pipeline = engine.get_pipeline(pipeline_id)
        if pipeline:
            pipelines.append(PipelineResponse(
                pipeline_id=pipeline_id,
                filters=pipeline.get_filters(),
                continue_on_error=pipeline.config.continue_on_error,
                log_errors=pipeline.config.log_errors,
                max_retries=pipeline.config.max_retries,
                retry_delay=pipeline.config.retry_delay,
                retry_backoff=pipeline.config.retry_backoff,
                timeout_per_filter=pipeline.config.timeout_per_filter,
                location=pipeline.config.location.value,
                service_name=pipeline.config.service_name,
                error_callback_plugin=pipeline.config.error_callback_plugin,
                error_callback_config=pipeline.config.error_callback_config,
                enable_metrics=pipeline.config.enable_metrics,
            ))
    
    return PipelineListResponse(count=len(pipelines), pipelines=pipelines)


@router.post("/pipelines", response_model=PipelineOperationResponse)
async def create_pipeline(
    request: PipelineCreateRequest,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if engine.is_pipeline_exists(request.pipeline_id):
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline '{request.pipeline_id}' already exists"
        )
    
    location = PipelineLocation.SOUTH
    if request.location == "north":
        location = PipelineLocation.NORTH
    
    config = PipelineConfig(
        pipeline_id=request.pipeline_id,
        filters=[f.model_dump() for f in request.filters],
        continue_on_error=request.continue_on_error,
        log_errors=request.log_errors,
        max_retries=request.max_retries,
        retry_delay=request.retry_delay,
        retry_backoff=request.retry_backoff,
        timeout_per_filter=request.timeout_per_filter,
        location=location,
        service_name=request.service_name,
        error_callback_plugin=request.error_callback_plugin,
        error_callback_config=request.error_callback_config,
        enable_metrics=request.enable_metrics,
    )
    
    success = await engine.add_pipeline_async(config)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create pipeline '{request.pipeline_id}'"
        )
    
    return PipelineOperationResponse(
        success=True,
        message=f"Pipeline '{request.pipeline_id}' created successfully",
        pipeline_id=request.pipeline_id,
    )


@router.delete("/pipelines/{pipeline_id}", response_model=PipelineOperationResponse)
async def delete_pipeline(
    pipeline_id: str,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if not engine.is_pipeline_exists(pipeline_id):
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    
    success = await engine.remove_pipeline_async(pipeline_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete pipeline '{pipeline_id}'"
        )
    
    return PipelineOperationResponse(
        success=True,
        message=f"Pipeline '{pipeline_id}' deleted successfully",
        pipeline_id=pipeline_id,
    )


# ==================== Channels ====================

@router.get("/channels", response_model=ChannelListResponse)
async def list_channels(
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    all_channels = engine.get_all_channel_configs()
    channels = []
    for channel_id, channel_config in all_channels.items():
        channels.append(ChannelResponse(
            channel_id=channel_id,
            plugin_name=channel_config.get("plugin_name", ""),
            config=channel_config.get("config", {}),
        ))
    
    return ChannelListResponse(count=len(channels), channels=channels)


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine)
):
    channel_config = engine.get_channel_config(channel_id)
    if not channel_config:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    
    return ChannelResponse(
        channel_id=channel_id,
        plugin_name=channel_config.get("plugin_name", ""),
        config=channel_config.get("config", {}),
    )


@router.post("/channels", response_model=ChannelOperationResponse)
async def create_channel(
    request: ChannelCreateRequest,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if engine.is_channel_registered(request.channel_id):
        raise HTTPException(
            status_code=409,
            detail=f"Channel '{request.channel_id}' already exists"
        )
    
    success = await engine.add_delivery_channel_async(
        channel_id=request.channel_id,
        plugin_name=request.plugin_name,
        config=request.config,
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create channel '{request.channel_id}'"
        )
    
    return ChannelOperationResponse(
        success=True,
        message=f"Channel '{request.channel_id}' created successfully",
        channel_id=request.channel_id,
    )


@router.delete("/channels/{channel_id}", response_model=ChannelOperationResponse)
async def delete_channel(
    channel_id: str,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if not engine.is_channel_registered(channel_id):
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    
    success = await engine.unregister_channel(channel_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete channel '{channel_id}'"
        )
    
    return ChannelOperationResponse(
        success=True,
        message=f"Channel '{channel_id}' deleted successfully",
        channel_id=channel_id,
    )


# ==================== Rule-Channel Binding ====================

@router.post("/{rule_id}/channels", response_model=RuleOperationResponse)
async def bind_rule_channels(
    rule_id: str,
    request: BindChannelsRequest,
    engine: RuleEngineOrchestrator = Depends(get_rule_engine),
    token: str = Depends(verify_api_token)
):
    if not engine.is_rule_loaded(rule_id):
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    
    for channel_id in request.channel_ids:
        if not engine.is_channel_registered(channel_id):
            raise HTTPException(
                status_code=400,
                detail=f"Channel '{channel_id}' not found"
            )
    
    engine.bind_rule_channels(rule_id, request.channel_ids)
    
    return RuleOperationResponse(
        success=True,
        message=f"Channels bound to rule '{rule_id}' successfully",
        rule_id=rule_id,
    )
