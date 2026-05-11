import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional

from ..models.device import (
    DeviceConfig,
    PointConfig,
    DeviceStatus,
    DeviceCreateResponse,
    DeviceUpdateResponse,
    PointCreateResponse,
    DeviceListResponse,
    BatchOperationResult,
    DeviceReloadResponse,
    BatchDeviceReloadResponse
)
from ..services.device_service import DeviceService
from ..dependencies import get_app_state
from .config import verify_api_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Devices"])


def handle_value_error(e: ValueError) -> HTTPException:
    """统一处理 ValueError，返回合适的 HTTP 状态码
    
    Args:
        e: ValueError 异常
        
    Returns:
        HTTPException: 合适的 HTTP 异常
    """
    error_msg = str(e)
    
    if "not found" in error_msg:
        return HTTPException(status_code=404, detail=error_msg)
    elif "already exists" in error_msg:
        return HTTPException(status_code=409, detail=error_msg)
    elif "invalid" in error_msg or "cannot" in error_msg:
        return HTTPException(status_code=400, detail=error_msg)
    else:
        return HTTPException(status_code=400, detail=error_msg)


def get_device_service(state = Depends(get_app_state)):
    """获取设备服务实例"""
    if not state.gateway:
        raise HTTPException(
            status_code=500,
            detail="Gateway not initialized"
        )
    
    return DeviceService(
        config_dir=state.gateway.config_manager.paths.config_dir,
        metadata_manager=state.metadata_manager,
        plugin_loader=state.gateway.plugin_loader
    )


@router.post(
    "/", 
    response_model=DeviceCreateResponse, 
    status_code=status.HTTP_201_CREATED
)
async def create_device(
    device: DeviceConfig,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """创建新设备
    
    创建设备时会：
    1. 验证插件是否可用
    2. 创建设备配置文件
    3. 同步到数据库
    4. 加载插件实例
    
    Args:
        device: 设备配置
        
    Returns:
        创建的设备信息
        
    Raises:
        HTTPException: 400 - 设备已存在或插件不可用
        HTTPException: 500 - 内部服务器错误
    """
    try:
        created_device = await service.create_device(device)
        
        return DeviceCreateResponse(
            success=True,
            message=f"Device '{device.asset}' created successfully",
            asset=device.asset,
            plugin_id=f"{device.plugin.name}_{device.asset}",
            requires_reload=False
        )
    except ValueError as e:
        logger.error(f"Failed to create device: {e}")
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Unexpected error creating device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=DeviceListResponse)
async def list_devices(
    status: Optional[DeviceStatus] = Query(None, description="Filter by status"),
    plugin_name: Optional[str] = Query(None, description="Filter by plugin name"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    service: DeviceService = Depends(get_device_service)
):
    """列出所有设备
    
    支持按状态、插件名称、标签、启用状态过滤
    
    Args:
        status: 设备状态过滤
        plugin_name: 插件名称过滤
        tags: 标签过滤
        enabled: 启用状态过滤
        
    Returns:
        设备列表
    """
    devices = await service.list_devices(
        status=status,
        plugin_name=plugin_name,
        tags=tags,
        enabled=enabled
    )
    
    return DeviceListResponse(
        count=len(devices),
        devices=devices
    )


@router.get("/latest")
async def get_devices_latest(
    active_only: bool = Query(default=True),
    state = Depends(get_app_state)
):
    """获取所有设备的最新数据
    
    Args:
        active_only: 是否只返回活跃设备的数据
        
    Returns:
        设备最新数据列表
    """
    from ...storage import StorageInterface
    
    storage = state.gateway.storage if state.gateway else None
    if not storage:
        from ..dependencies import get_storage
        storage = await get_storage()
    
    readings = await storage.get_latest_readings_by_device(active_only=active_only)
    return {"count": len(readings), "devices": [r.to_dict() for r in readings]}


@router.get("/{asset}", response_model=DeviceConfig)
async def get_device(
    asset: str,
    service: DeviceService = Depends(get_device_service)
):
    """获取设备详情
    
    Args:
        asset: 设备资产标识
        
    Returns:
        设备配置
        
    Raises:
        HTTPException: 404 - 设备不存在
    """
    device = await service.get_device(asset)
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device '{asset}' not found"
        )
    return device


@router.put("/{asset}", response_model=DeviceUpdateResponse)
async def update_device(
    asset: str,
    updates: dict,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """更新设备配置
    
    支持部分更新，只需提供要修改的字段
    
    Args:
        asset: 设备资产标识
        updates: 更新内容
        
    Returns:
        更新结果
        
    Raises:
        HTTPException: 404 - 设备不存在
        HTTPException: 400 - 更新内容无效
    """
    try:
        updated_device = await service.update_device(asset, updates)
        
        updated_fields = list(updates.keys())
        
        return DeviceUpdateResponse(
            success=True,
            message=f"Device '{asset}' updated successfully",
            asset=asset,
            updated_fields=updated_fields
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        elif "already exists" in error_msg or "invalid" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error updating device {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{asset}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    asset: str,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """删除设备
    
    删除设备会：
    1. 停止插件实例
    2. 删除配置文件
    3. 从数据库软删除
    
    Args:
        asset: 设备资产标识
        
    Raises:
        HTTPException: 404 - 设备不存在
    """
    try:
        await service.delete_device(asset)
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Error deleting device {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{asset}/points", 
    response_model=PointCreateResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_point_to_device(
    asset: str,
    point: PointConfig,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """向设备添加点位
    
    Args:
        asset: 设备资产标识
        point: 点位配置
        
    Returns:
        添加结果
        
    Raises:
        HTTPException: 404 - 设备不存在
        HTTPException: 400 - 点位已存在
    """
    try:
        await service.add_point(asset, point)
        
        return PointCreateResponse(
            success=True,
            message=f"Point '{point.name}' added to device '{asset}'",
            asset=asset,
            point_name=point.name,
            requires_reload=False
        )
    except ValueError as e:
        if "not found" in str(e):
            raise handle_value_error(e)
        else:
            raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Error adding point to device {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{asset}/points", response_model=List[PointConfig])
async def list_device_points(
    asset: str,
    service: DeviceService = Depends(get_device_service)
):
    """列出设备的所有点位
    
    Args:
        asset: 设备资产标识
        
    Returns:
        点位列表
        
    Raises:
        HTTPException: 404 - 设备不存在
    """
    device = await service.get_device(asset)
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device '{asset}' not found"
        )
    return device.points


@router.delete(
    "/{asset}/points/{point_name}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_point_from_device(
    asset: str,
    point_name: str,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """从设备移除点位
    
    Args:
        asset: 设备资产标识
        point_name: 点位名称
        
    Raises:
        HTTPException: 404 - 设备或点位不存在
    """
    try:
        await service.remove_point(asset, point_name)
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Error removing point {point_name} from device {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{asset}/points/{point_name}", response_model=PointCreateResponse)
async def update_point(
    asset: str,
    point_name: str,
    updates: dict,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """更新点位配置
    
    Args:
        asset: 设备资产标识
        point_name: 点位名称
        updates: 更新内容
        
    Returns:
        更新结果
        
    Raises:
        HTTPException: 404 - 设备或点位不存在
    """
    try:
        await service.update_point(asset, point_name, updates)
        
        return PointCreateResponse(
            success=True,
            message=f"Point '{point_name}' updated in device '{asset}'",
            asset=asset,
            point_name=point_name,
            requires_reload=False
        )
    except ValueError as e:
        raise handle_value_error(e)
    except Exception as e:
        logger.error(f"Error updating point {point_name} in device {asset}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/batch", response_model=BatchOperationResult)
async def batch_create_devices(
    devices: List[DeviceConfig],
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """批量创建设备
    
    Args:
        devices: 设备列表
        
    Returns:
        批量操作结果
    """
    result = await service.batch_create_devices(devices)
    
    return BatchOperationResult(
        total=result['total'],
        succeeded=result['succeeded'],
        failed=result['failed'],
        details=result['details']
    )


@router.post("/reload", response_model=BatchDeviceReloadResponse)
async def reload_devices(
    assets: Optional[List[str]] = None,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """Reload device plugins (hot reload)
    
    This endpoint reloads device plugins without restarting the application.
    Use this when device point configurations have changed.
    
    Args:
        assets: List of device asset names to reload. If None, reloads all enabled devices.
        
    Returns:
        Reload results for each device
    """
    try:
        result = await service.reload_devices(assets)
        
        return BatchDeviceReloadResponse(
            success=True,
            message=f"Reloaded {result['succeeded']}/{result['total']} devices successfully",
            **result
        )
    except Exception as e:
        logger.error(f"Failed to reload devices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload devices: {str(e)}"
        )


@router.post("/{asset}/reload", response_model=DeviceReloadResponse)
async def reload_device(
    asset: str,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """Reload a single device plugin (hot reload)
    
    This endpoint reloads a specific device plugin without restarting the application.
    Use this when a device's point configuration has changed.
    
    Args:
        asset: Device asset name
        
    Returns:
        Reload result
    """
    try:
        await service.reload_device(asset)
        
        logger.info(f"Device {asset} reloaded successfully")
        
        return DeviceReloadResponse(
            success=True,
            message=f"Device '{asset}' reloaded successfully",
            asset=asset,
            reload_status="success"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to reload device {asset}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload device {asset}: {str(e)}"
        )


@router.post("/export")
async def export_devices(
    assets: Optional[List[str]] = None,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """导出设备配置
    
    Args:
        assets: 要导出的设备列表，None 表示导出所有
        
    Returns:
        导出的设备配置
    """
    return await service.export_devices(assets)


@router.post("/import", response_model=BatchOperationResult)
async def import_devices(
    data: dict,
    overwrite: bool = False,
    service: DeviceService = Depends(get_device_service),
    token: str = Depends(verify_api_token)
):
    """导入设备配置
    
    Args:
        data: 导入的设备配置
        overwrite: 是否覆盖已存在的设备
        
    Returns:
        导入结果
    """
    result = await service.import_devices(data, overwrite)
    
    return BatchOperationResult(
        total=result['total'],
        succeeded=result['succeeded'],
        failed=result['failed'],
        details=result['details']
    )
