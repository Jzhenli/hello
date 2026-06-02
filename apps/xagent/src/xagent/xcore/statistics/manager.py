"""统计管理器 - 集中管理所有统计功能

支持多种统计场景：
1. 北向通道上传统计
2. 数据采集趋势统计
3. 设备性能统计
4. 自定义统计

设计原则：
- 高内聚：所有统计逻辑集中管理
- 可扩展：支持自定义统计指标
- 高性能：内存收集 + 定期持久化
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, TYPE_CHECKING
from .collector import StatsCollector

if TYPE_CHECKING:
    from ..api.services.north_channel_service import NorthChannelService

logger = logging.getLogger(__name__)


class StatisticsManager:
    """通用统计管理器
    
    职责：
    1. 管理统计收集器的生命周期
    2. 提供统一的统计接口
    3. 协调统计数据的更新和持久化
    4. 支持多种统计场景
    """
    
    def __init__(self, storage=None, config: Optional[Dict[str, Any]] = None):
        """初始化统计管理器
        
        Args:
            storage: 存储接口（用于持久化统计数据）
            config: 配置字典
                - update_interval: 更新间隔（秒），默认 60
                - enabled: 是否启用统计，默认 True
                - persist_to_db: 是否持久化到数据库，默认 True
        """
        self._storage = storage
        self._collectors: Dict[str, StatsCollector] = {}
        self._config = config or {}
        
        self._update_interval = self._config.get('update_interval', 60)
        self._enabled = self._config.get('enabled', True)
        self._persist_to_db = self._config.get('persist_to_db', True)
        
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._exporters: List[Any] = []
        self._channel_service = None
    
    # ===== 生命周期管理 =====
    
    async def start(self) -> None:
        """启动统计管理器"""
        if self._running:
            logger.warning("Statistics manager already running")
            return
        
        self._running = True
        
        if self._persist_to_db:
            self._update_task = asyncio.create_task(self._persist_loop())
        
        logger.info(
            f"Statistics manager started "
            f"(interval={self._update_interval}s, enabled={self._enabled})"
        )
    
    async def stop(self) -> None:
        """停止统计管理器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Statistics manager stopped")
    
    # ===== 北向通道统计 =====
    
    def create_channel_collector(self, channel_id: str) -> StatsCollector:
        """创建通道统计收集器
        
        Args:
            channel_id: 通道ID
            
        Returns:
            StatsCollector: 统计收集器
        """
        return self._get_or_create_collector(f"channel:{channel_id}")
    
    async def record_channel_stats(
        self, 
        channel_id: str, 
        count: int, 
        success: bool
    ) -> None:
        """记录通道统计
        
        Args:
            channel_id: 通道ID
            count: 上传的数据条数
            success: 是否成功
        """
        if not self._enabled:
            return
        
        collector = self.create_channel_collector(channel_id)
        await collector.record(count, success)
    
    def get_channel_stats(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """获取通道统计信息
        
        Args:
            channel_id: 通道ID
            
        Returns:
            统计信息字典，如果不存在返回 None
        """
        key = f"channel:{channel_id}"
        if key in self._collectors:
            return self._collectors[key].get_stats()
        return None
    
    # ===== 数据采集趋势统计 =====
    
    async def record_data_collection(
        self, 
        device_id: str, 
        point_count: int
    ) -> None:
        """记录数据采集
        
        用于统计：
        - 按小时的采集趋势
        - 按设备的采集分布
        
        Args:
            device_id: 设备ID
            point_count: 采集的点位数量
        """
        if not self._enabled:
            return
        
        hour_key = f"collection:{datetime.now().strftime('%Y-%m-%d:%H')}"
        hour_collector = self._get_or_create_collector(hour_key)
        await hour_collector.record(point_count, success=True)
        
        device_key = f"device:{device_id}"
        device_collector = self._get_or_create_collector(device_key)
        await device_collector.record(point_count, success=True)
    
    async def get_hourly_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取按小时的采集趋势
        
        用于 Dashboard 趋势图
        
        Args:
            hours: 小时数，默认 24
            
        Returns:
            趋势数据列表，每项包含 time 和 value
        """
        now = datetime.now()
        trend = []
        
        for i in range(hours, 0, -1):
            hour = now - timedelta(hours=i)
            hour_key = f"collection:{hour.strftime('%Y-%m-%d:%H')}"
            
            if hour_key in self._collectors:
                stats = self._collectors[hour_key].get_stats()
                trend.append({
                    "time": hour.strftime('%H:00'),
                    "value": stats['total_uploaded']
                })
            else:
                trend.append({
                    "time": hour.strftime('%H:00'),
                    "value": 0
                })
        
        return trend
    
    def get_device_distribution(self) -> Dict[str, int]:
        """获取设备采集分布
        
        用于分析哪些设备采集量最大
        
        Returns:
            设备ID到采集量的映射
        """
        distribution = {}
        
        for key, collector in self._collectors.items():
            if key.startswith("device:"):
                device_id = key.split(":", 1)[1]
                stats = collector.get_stats()
                distribution[device_id] = stats['total_uploaded']
        
        return distribution
    
    # ===== 扩展功能 =====
    
    def register_exporter(self, exporter: Any) -> None:
        """注册统计导出器
        
        支持导出到：
        - Prometheus
        - InfluxDB
        - Grafana
        - 自定义监控系统
        
        Args:
            exporter: 导出器实例，需要实现 export(channel_id, stats) 方法
        """
        self._exporters.append(exporter)
        logger.info(f"Exporter registered: {exporter.__class__.__name__}")
    
    def set_channel_service(self, channel_service: "NorthChannelService") -> None:
        """设置北向通道服务
        
        Args:
            channel_service: NorthChannelService 实例
        """
        self._channel_service = channel_service
        logger.debug("Channel service set for statistics manager")
    
    def register_custom_collector(
        self, 
        name: str, 
        collector: StatsCollector
    ) -> None:
        """注册自定义统计收集器
        
        Args:
            name: 收集器名称
            collector: 统计收集器实例
        """
        key = f"custom:{name}"
        self._collectors[key] = collector
        logger.info(f"Custom collector registered: {name}")
    
    # ===== 内部方法 =====
    
    def _get_or_create_collector(self, key: str) -> StatsCollector:
        """获取或创建统计收集器"""
        if key not in self._collectors:
            self._collectors[key] = StatsCollector()
        return self._collectors[key]
    
    async def _persist_loop(self) -> None:
        """定期持久化统计数据"""
        while self._running:
            try:
                await asyncio.sleep(self._update_interval)
                
                if not self._storage:
                    continue
                
                for key, collector in self._collectors.items():
                    try:
                        stats = collector.get_stats()
                        
                        if key.startswith("channel:"):
                            channel_id = key.split(":", 1)[1]
                            await self._persist_channel_stats(channel_id, stats)
                        
                        await self._export_stats(key, stats)
                        
                    except Exception as e:
                        logger.error(f"Failed to persist stats for {key}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Persist loop error: {e}")
    
    async def _persist_channel_stats(
        self, 
        channel_id: str, 
        stats: Dict[str, Any]
    ) -> None:
        """持久化通道统计到数据库"""
        try:
            if self._channel_service and hasattr(self._channel_service, 'update_status'):
                from ..api.models.north_channel import NorthChannelStatus
                await self._channel_service.update_status(
                    channel_id,
                    NorthChannelStatus.ONLINE,
                    statistics=stats
                )
                logger.info(
                    f"Statistics updated for channel {channel_id}: "
                    f"rate={stats.get('upload_rate')}/min, "
                    f"success={stats.get('success_rate')}%"
                )
        except Exception as e:
            logger.error(f"Failed to persist channel stats for {channel_id}: {e}")
    
    async def _export_stats(self, key: str, stats: Dict[str, Any]) -> None:
        """导出统计数据到外部系统"""
        for exporter in self._exporters:
            try:
                if hasattr(exporter, 'export'):
                    await exporter.export(key, stats)
            except Exception as e:
                logger.error(f"Export failed for {key}: {e}")
    
    # ===== 状态查询 =====
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    @property
    def collector_count(self) -> int:
        """收集器数量"""
        return len(self._collectors)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有统计信息"""
        return {
            key: collector.get_stats()
            for key, collector in self._collectors.items()
        }
