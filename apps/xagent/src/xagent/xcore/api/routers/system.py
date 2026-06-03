"""System API routes"""

import time
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..dependencies import get_storage, get_buffer, get_app_state, get_gateway, get_stats_manager
from ..models.system import HealthResponse
from ...storage import StorageInterface, WriteBehindBuffer
from ...statistics import StatisticsManager
from ...utils.system_monitor import get_system_monitor
from ...utils.constants import SystemDefaults

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


@router.get("/api/system/stats")
async def get_system_stats(
    stats_manager: Optional[StatisticsManager] = Depends(get_stats_manager)
):
    """获取系统统计信息
    
    返回系统资源使用情况和采集统计
    
    Returns:
        系统统计信息，包括：
        - cpu_usage: CPU使用率 (%)
        - memory_usage: 内存使用率 (%)
        - disk_usage: 磁盘使用率 (%)
        - uptime: 运行时长 (秒)
        - total_readings: 总采集量
        - today_readings: 今日采集量
        - connection_count: 连接数
        - process_count: 进程数
        - load_average: 负载均值
    """
    if stats_manager:
        return await stats_manager.get_system_stats()
    else:
        # 降级方案：直接获取基本统计
        return await _get_basic_system_stats()


@router.get("/api/data/quality")
async def get_data_quality(
    stats_manager: Optional[StatisticsManager] = Depends(get_stats_manager)
):
    """获取数据质量统计
    
    Returns:
        数据质量统计信息，包括：
        - good: 良好数据点数
        - bad: 不良数据点数
        - uncertain: 不确定数据点数
        - total: 总数据点数
        - quality_rate: 数据质量率 (%)
    """
    if stats_manager:
        return await stats_manager.get_quality_stats()
    else:
        return {
            "good": 0,
            "bad": 0,
            "uncertain": 0,
            "total": 0,
            "quality_rate": 0.0
        }


@router.get("/api/data/stats")
async def get_data_collection_stats(
    start_time: Optional[float] = Query(None, description="开始时间戳"),
    end_time: Optional[float] = Query(None, description="结束时间戳"),
    interval: str = Query("hour", description="统计间隔"),
    stats_manager: Optional[StatisticsManager] = Depends(get_stats_manager)
):
    """获取数据采集统计
    
    Args:
        start_time: 开始时间戳（可选）
        end_time: 结束时间戳（可选）
        interval: 统计间隔
        
    Returns:
        采集统计数据，包括：
        - stats: 趋势数据列表
        - total_count: 总采集量
        - avg_rate: 平均采集速率
    """
    if stats_manager:
        return await stats_manager.get_collection_stats(
            start_time=start_time,
            end_time=end_time,
            interval=interval
        )
    else:
        return {
            "stats": [],
            "total_count": 0,
            "avg_rate": 0.0
        }


async def _get_basic_system_stats():
    """基本系统统计（降级方案）
    
    当 StatisticsManager 不可用时，直接获取基本系统信息
    """
    try:
        # 使用SystemMonitor获取系统指标（单例+共享线程池）
        monitor = get_system_monitor()
        metrics = await monitor.get_system_metrics()
        
        return {
            "cpu_usage": round(metrics["cpu_usage"], 2),
            "memory_usage": round(metrics["memory"].percent, 2),
            "disk_usage": round(metrics["disk"].percent, 2),
            "uptime": int(metrics["uptime"]),
            "total_readings": 0,
            "today_readings": 0,
            "connection_count": metrics["connections"],
            "process_count": metrics["process_count"],
            "load_average": metrics["load_avg"]
        }
    except Exception as e:
        # 如果所有方法都失败，返回默认值
        return SystemDefaults.get_default_system_stats()
