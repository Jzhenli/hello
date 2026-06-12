import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status, Body
from typing import List, Optional, Dict, Any

from ..models.north_channel import (
    NorthChannelConfig,
    NorthChannelCreateResponse,
    NorthChannelUpdateResponse,
    NorthChannelListResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    NorthChannelStatus,
    NorthChannelProtocol
)
from ..services.north_channel_service import NorthChannelService
from ..dependencies import get_app_state, AppState
from .config import verify_api_token

# 导入适配器注册表的公开函数
from xagent.plugins.north.mqtt_client.adapters.registry import (
    get_adapter_class,
    get_adapter_info
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["North Channels"])

_north_channel_service: Optional[NorthChannelService] = None


async def get_north_channel_service(state: AppState = Depends(get_app_state)) -> NorthChannelService:
    """获取北向通道服务实例
    
    从应用状态获取数据库连接和插件加载器来初始化服务。
    使用单例模式避免重复创建和初始化。
    """
    global _north_channel_service
    
    if _north_channel_service is None:
        if not state.metadata_manager:
            raise HTTPException(
                status_code=500,
                detail="Metadata manager not initialized"
            )
        
        plugin_loader = None
        if state.gateway:
            plugin_loader = state.gateway.plugin_loader
        
        _north_channel_service = NorthChannelService(
            db=state.metadata_manager.db,
            plugin_loader=plugin_loader
        )
        
        await _north_channel_service.initialize()
    
    return _north_channel_service


def handle_value_error(e: ValueError) -> HTTPException:
    """统一处理 ValueError，返回合适的 HTTP 状态码"""
    error_msg = str(e)
    
    if "not found" in error_msg:
        return HTTPException(status_code=404, detail=error_msg)
    elif "already exists" in error_msg:
        return HTTPException(status_code=409, detail=error_msg)
    elif "invalid" in error_msg or "cannot" in error_msg:
        return HTTPException(status_code=400, detail=error_msg)
    else:
        return HTTPException(status_code=400, detail=error_msg)


@router.post(
    "/",
    response_model=NorthChannelCreateResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_channel(
    channel: NorthChannelConfig,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """创建北向通道
    
    Args:
        channel: 通道配置
        
    Returns:
        创建的通道信息
        
    Raises:
        HTTPException: 400 - 通道已存在或配置无效
        HTTPException: 500 - 内部服务器错误
    """
    try:
        created_channel = await service.create_channel(channel)
        
        return NorthChannelCreateResponse(
            success=True,
            message=f"Channel '{channel.id}' created successfully",
            channel_id=channel.id,
            requires_restart=False
        )
    except ValueError as e:
        logger.error(f"Failed to create channel: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error creating channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=NorthChannelListResponse)
async def list_channels(
    status: Optional[NorthChannelStatus] = Query(None, description="Filter by status"),
    protocol: Optional[NorthChannelProtocol] = Query(None, description="Filter by protocol"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    service: NorthChannelService = Depends(get_north_channel_service)
):
    """列出所有北向通道
    
    支持按状态、协议、标签、启用状态过滤
    
    Args:
        status: 状态过滤
        protocol: 协议过滤
        tags: 标签过滤
        enabled: 启用状态过滤
        
    Returns:
        通道列表
    """
    channels = await service.list_channels(
        status=status,
        protocol=protocol,
        tags=tags,
        enabled=enabled
    )
    
    return NorthChannelListResponse(
        count=len(channels),
        channels=channels
    )


@router.get("/{channel_id}", response_model=NorthChannelConfig)
async def get_channel(
    channel_id: str,
    service: NorthChannelService = Depends(get_north_channel_service)
):
    """获取通道详情
    
    Args:
        channel_id: 通道ID
        
    Returns:
        通道配置
        
    Raises:
        HTTPException: 404 - 通道不存在
    """
    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_id}' not found"
        )
    
    return channel


@router.put("/{channel_id}", response_model=NorthChannelUpdateResponse)
async def update_channel(
    channel_id: str,
    updates: dict,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """更新通道配置
    
    Args:
        channel_id: 通道ID
        updates: 更新内容
        
    Returns:
        更新结果
        
    Raises:
        HTTPException: 404 - 通道不存在
        HTTPException: 400 - 更新内容无效
    """
    try:
        updated_channel = await service.update_channel(channel_id, updates)
        
        return NorthChannelUpdateResponse(
            success=True,
            message=f"Channel '{channel_id}' updated successfully",
            channel_id=channel_id,
            updated_fields=list(updates.keys())
        )
    except ValueError as e:
        logger.error(f"Failed to update channel: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error updating channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """删除通道
    
    Args:
        channel_id: 通道ID
        
    Returns:
        删除结果
        
    Raises:
        HTTPException: 404 - 通道不存在
    """
    try:
        await service.delete_channel(channel_id)
        return {"success": True, "message": f"Channel '{channel_id}' deleted successfully"}
    except ValueError as e:
        logger.error(f"Failed to delete channel: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error deleting channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{channel_id}/toggle", response_model=NorthChannelUpdateResponse)
async def toggle_channel(
    channel_id: str,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """切换通道启用状态
    
    Args:
        channel_id: 通道ID
        
    Returns:
        更新结果
    """
    try:
        updated_channel = await service.toggle_channel(channel_id)
        
        return NorthChannelUpdateResponse(
            success=True,
            message=f"Channel '{channel_id}' toggled successfully",
            channel_id=channel_id,
            updated_fields=["enabled"]
        )
    except ValueError as e:
        logger.error(f"Failed to toggle channel: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error toggling channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    request: ConnectionTestRequest,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """测试连接
    
    Args:
        request: 连接测试请求
        
    Returns:
        测试结果
    """
    try:
        if request.channel_id:
            result = await service.test_connection(request.channel_id)
        else:
            result = await service.test_connection(request.channel_id or "temp")
        
        return ConnectionTestResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            latency=result.get("latency"),
            details=result.get("details")
        )
    except Exception as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return ConnectionTestResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )


@router.get("/{channel_id}/statistics")
async def get_channel_statistics(
    channel_id: str,
    service: NorthChannelService = Depends(get_north_channel_service)
):
    """获取通道统计信息
    
    Args:
        channel_id: 通道ID
        
    Returns:
        统计信息
    """
    statistics = await service.get_channel_statistics(channel_id)
    if not statistics:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_id}' not found"
        )
    
    return statistics


@router.post("/{channel_id}/restart")
async def restart_channel(
    channel_id: str,
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """重启通道
    
    Args:
        channel_id: 通道ID
        
    Returns:
        重启结果
    """
    try:
        result = await service.restart_channel(channel_id)
        return result
    except ValueError as e:
        logger.error(f"Failed to restart channel: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error restarting channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch")
async def batch_create_channels(
    channels: List[NorthChannelConfig],
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """批量创建通道
    
    Args:
        channels: 通道列表
        
    Returns:
        批量操作结果
    """
    result = await service.batch_create_channels(channels)
    return result


@router.post("/export")
async def export_channels(
    request_body: Optional[dict] = Body(None),
    service: NorthChannelService = Depends(get_north_channel_service)
):
    """导出通道配置
    
    Args:
        request_body: 请求体，包含 channel_ids 字段
        
    Returns:
        导出的配置数据
    """
    channel_ids = None
    if request_body and "channel_ids" in request_body:
        channel_ids = request_body.get("channel_ids")
    
    all_channels = await service.list_channels()
    
    if channel_ids:
        channels_to_export = [c for c in all_channels if c.id in channel_ids]
    else:
        channels_to_export = all_channels
    
    return {
        "channels": [c.model_dump(exclude_none=True) for c in channels_to_export]
    }


@router.post("/import")
async def import_channels(
    data: dict,
    overwrite: bool = Query(False, description="是否覆盖已存在的通道"),
    service: NorthChannelService = Depends(get_north_channel_service),
    token: str = Depends(verify_api_token)
):
    """导入通道配置
    
    Args:
        data: 导入的配置数据
        overwrite: 是否覆盖已存在的通道
        
    Returns:
        导入结果
    """
    channels_data = data.get("channels", [])
    
    if not channels_data:
        raise HTTPException(status_code=400, detail="No channels data provided")
    
    channels = []
    for channel_data in channels_data:
        try:
            channel = NorthChannelConfig(**channel_data)
            channels.append(channel)
        except Exception as e:
            logger.error(f"Invalid channel data: {e}")
    
    if overwrite:
        for channel in channels:
            if await service.get_channel(channel.id):
                await service.delete_channel(channel.id)
    
    result = await service.batch_create_channels(channels)
    return result


@router.get("/adapters/list")
async def list_adapters() -> Dict[str, Any]:
    """列出所有可用的适配器

    Returns:
        适配器列表，包含名称、客户编号和描述
    """
    # 通过注册表公开函数获取适配器信息
    adapter_info_list = get_adapter_info()

    adapters = []
    for info in adapter_info_list:
        name = info["name"]
        customer_code = info["customer_code"]
        has_defaults = info["has_defaults"]

        adapters.append({
            "name": name,
            "customer_code": customer_code,
            "description": f"客户编号: {customer_code}" if customer_code else name,
            "has_defaults": has_defaults
        })

    return {"adapters": adapters}


@router.get("/adapters/{adapter_code}/defaults")
async def get_adapter_defaults(adapter_code: str) -> Dict[str, Any]:
    """获取适配器默认配置

    Args:
        adapter_code: 适配器名称或客户编号（如 C001 或 customer_a）

    Returns:
        适配器默认配置

    Raises:
        HTTPException: 404 - 适配器不存在或没有默认配置
    """
    # 通过注册表公开函数获取适配器类
    adapter_cls = get_adapter_class(adapter_code)
    if not adapter_cls:
        raise HTTPException(
            status_code=404,
            detail=f"Adapter '{adapter_code}' not found"
        )

    # 获取默认配置
    defaults = getattr(adapter_cls, "DEFAULT_CONFIG", None)
    if defaults is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adapter '{adapter_code}' has no default configuration"
        )

    # 获取适配器名称
    adapter_name = adapter_cls.__name__.replace("Adapter", "").lower() if adapter_cls.__name__.endswith("Adapter") else adapter_cls.__name__

    return {
        "adapter_code": adapter_code,
        "adapter_name": adapter_name,
        "defaults": defaults
    }
