"""统计管理器 - 集中管理所有统计功能

支持多种统计场景：
1. 北向通道上传统计
2. 数据采集趋势统计
3. 设备性能统计
4. 系统资源统计
5. 数据质量统计
6. 自定义统计

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
from ..utils.system_monitor import get_system_monitor
from ..utils.constants import SystemDefaults, TimeConstants

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
        point_count: int,
        successful_count: Optional[int] = None
    ) -> None:
        """记录数据采集
        
        用于统计：
        - 按小时的采集趋势
        - 按设备的采集分布
        - 采集成功率
        
        Args:
            device_id: 设备ID
            point_count: 采集的点位数量
            successful_count: 成功采集的点位数量，None 时默认等于 point_count
        """
        if not self._enabled:
            return
        
        if successful_count is None:
            successful_count = point_count
        
        success = successful_count > 0 if point_count > 0 else True
        
        hour_key = f"collection:{datetime.now().strftime('%Y-%m-%d:%H')}"  # 本地时间
        hour_collector = self._get_or_create_collector(hour_key)
        await hour_collector.record(point_count, success=success)
        
        device_key = f"device:{device_id}"
        device_collector = self._get_or_create_collector(device_key)
        await device_collector.record(point_count, success=success)
    
    async def get_hourly_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取按小时的采集趋势
        
        用于 Dashboard 趋势图
        
        Args:
            hours: 小时数，默认 24
            
        Returns:
            趋势数据列表，每项包含 time(本地时间字符串)、value 和 timestamp
        """
        now = datetime.now()  # 使用本地时间（适合局域网场景）
        trend = []

        # 从 hours-1 小时前到当前小时（包含当前小时）
        for i in range(hours - 1, -1, -1):
            hour = now - timedelta(hours=i)
            hour_start = datetime(hour.year, hour.month, hour.day, hour.hour)
            hour_end = hour_start + timedelta(hours=1)
            
            try:
                # 从数据库查询该小时的采集数量
                count = await self._storage.count_readings_in_range(
                    hour_start.timestamp(),
                    hour_end.timestamp()
                )
                trend.append({
                    "time": hour.strftime('%H:00'),  # 本地时间字符串
                    "value": count,
                    "timestamp": int(hour_start.timestamp())  # 整点时间戳
                })
            except Exception as e:
                logger.warning(f"Failed to get hourly count for {hour}: {e}")
                trend.append({
                    "time": hour.strftime('%H:00'),
                    "value": 0,
                    "timestamp": int(hour_start.timestamp())
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
    
    async def record_operation(
        self,
        category: str,
        name: str,
        success: bool = True,
        count: int = 1,
        duration: float = 0.0,
        **extra
    ) -> None:
        """记录操作统计（通用方法）
        
        适用于 Rule、Delivery、Filter 等插件类型的统计。
        统一入口，简化调用。
        
        Args:
            category: 分类（如 rule, delivery, filter, south, north）
            name: 操作名称（如 threshold_rule, webhook, dedup）
            success: 是否成功
            count: 操作计数
            duration: 耗时（秒）
            **extra: 额外指标（如 triggered, filtered_count 等）
        """
        if not self._enabled:
            return
        
        key = f"plugin:{category}:{name}"
        collector = self._get_or_create_collector(key)
        await collector.record(count, success)
        
        extra_metrics = {}
        if duration > 0:
            extra_metrics["total_duration"] = duration
            extra_metrics["call_count"] = 1
            extra_metrics["avg_duration"] = duration
        
        for k, v in extra.items():
            if v is not None:
                extra_metrics[k] = v
        
        if extra_metrics:
            collector.record_extra(extra_metrics)
    
    def get_operation_stats(
        self,
        category: str,
        name: str
    ) -> Optional[Dict[str, Any]]:
        """获取操作统计信息
        
        Args:
            category: 分类
            name: 操作名称
            
        Returns:
            统计信息字典
        """
        key = f"plugin:{category}:{name}"
        if key in self._collectors:
            return self._collectors[key].get_stats()
        return None
    
    def get_all_plugin_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有插件统计信息
        
        Returns:
            插件统计信息字典，key 格式为 "category:name"
        """
        result = {}
        for key, collector in self._collectors.items():
            if key.startswith("plugin:"):
                parts = key.split(":", 2)
                if len(parts) == 3:
                    category, name = parts[1], parts[2]
                    result[f"{category}:{name}"] = collector.get_stats()
        return result
    
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
    
    # ===== 系统资源统计 =====
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统资源统计
        
        Returns:
            系统资源统计信息，包括CPU、内存、磁盘使用率等
        """
        try:
            # 使用SystemMonitor获取系统指标（单例+共享线程池）
            monitor = get_system_monitor()
            metrics = await monitor.get_system_metrics()
            
            # 获取采集统计
            total_readings = await self._get_total_readings()
            today_readings = await self._get_today_readings()
            
            return {
                "cpu_usage": round(metrics["cpu_usage"], 2),
                "memory_usage": round(metrics["memory"].percent, 2),
                "disk_usage": round(metrics["disk"].percent, 2),
                "uptime": int(metrics["uptime"]),
                "total_readings": total_readings,
                "today_readings": today_readings,
                "connection_count": metrics["connections"],
                "process_count": metrics["process_count"],
                "load_average": metrics["load_avg"]
            }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return SystemDefaults.get_default_system_stats()
    
    async def _get_total_readings(self) -> int:
        """获取总采集量"""
        if not self._storage:
            return 0
        
        try:
            stats = await self._storage.get_stats()
            return stats.get("total_readings", 0)
        except Exception as e:
            logger.error(f"Failed to get total readings: {e}")
            return 0
    
    async def _get_today_readings(self) -> int:
        """获取今日采集量"""
        if not self._storage:
            return 0
        
        try:
            # 计算今天开始的时间戳（本地时间）
            now = datetime.now()
            today_start = datetime(now.year, now.month, now.day).timestamp()
            
            # 查询今天的采集量
            count = await self._storage.count_readings_since(today_start)
            return count
        except Exception as e:
            logger.error(f"Failed to get today readings: {e}")
            return 0
    
    # ===== 数据质量统计 =====
    
    async def get_quality_stats(self) -> Dict[str, Any]:
        """获取数据质量统计
        
        Returns:
            数据质量统计信息，包括良好、不良、不确定数据点数
        """
        if not self._storage:
            return SystemDefaults.get_default_quality_stats()
        
        try:
            # 从存储中获取数据质量统计
            quality_stats = await self._storage.get_quality_stats()
            
            total = quality_stats.get("total", 0)
            good = quality_stats.get("good", 0)
            bad = quality_stats.get("bad", 0)
            uncertain = quality_stats.get("uncertain", 0)
            
            quality_rate = (good / total * 100) if total > 0 else 0
            
            return {
                "good": good,
                "bad": bad,
                "uncertain": uncertain,
                "total": total,
                "quality_rate": round(quality_rate, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get data quality stats: {e}")
            return SystemDefaults.get_default_quality_stats()
    
    # ===== 数据采集趋势统计 =====
    
    async def get_collection_stats(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        interval: str = "hour"
    ) -> Dict[str, Any]:
        """获取数据采集统计
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            interval: 统计间隔
            
        Returns:
            采集统计数据，包括趋势、总数、平均速率
        """
        # 默认查询最近24小时
        if not end_time:
            end_time = time.time()
        if not start_time:
            start_time = end_time - TimeConstants.SECONDS_PER_DAY  # 24小时前
        
        # 参数验证
        if start_time < 0 or end_time < 0:
            logger.error(f"Invalid timestamp: start_time={start_time}, end_time={end_time}")
            return SystemDefaults.get_default_collection_stats()
        
        if start_time > end_time:
            logger.error(f"start_time ({start_time}) cannot be greater than end_time ({end_time})")
            return SystemDefaults.get_default_collection_stats()
        
        if interval not in ("hour", "day"):
            logger.error(f"Invalid interval: {interval}, must be 'hour' or 'day'")
            return SystemDefaults.get_default_collection_stats()
        
        try:
            # 使用已有的 get_hourly_trend 方法
            if interval == "hour":
                # 使用四舍五入避免时间差导致的取整误差
                hours = round((end_time - start_time) / TimeConstants.SECONDS_PER_HOUR)
                hours = max(1, hours)  # 至少1小时
                trend = await self.get_hourly_trend(hours=hours)
                
                stats = []
                
                for item in trend:
                    # 直接使用 trend 中已计算好的 timestamp，确保一致性
                    stats.append({
                        "time": item["time"],  # 本地时间字符串
                        "count": item["value"],
                        "timestamp": item["timestamp"]
                    })
                
                total_count = sum(s["count"] for s in stats)
                avg_rate = total_count / len(stats) if stats else 0
                
                return {
                    "stats": stats,
                    "total_count": total_count,
                    "avg_rate": round(avg_rate, 2)
                }
            else:
                # 按天统计
                return await self._get_daily_collection_stats(start_time, end_time)
                
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return SystemDefaults.get_default_collection_stats()
    
    async def _get_daily_collection_stats(
        self,
        start_time: float,
        end_time: float
    ) -> Dict[str, Any]:
        """获取按天的采集统计
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            按天统计的采集数据
        """
        if not self._storage:
            return SystemDefaults.get_default_collection_stats()
        
        try:
            # 计算天数
            days = int((end_time - start_time) / TimeConstants.SECONDS_PER_DAY)
            
            stats = []
            for i in range(days):
                day_start = start_time + (i * TimeConstants.SECONDS_PER_DAY)
                day_end = day_start + TimeConstants.SECONDS_PER_DAY
                
                # 查询当天的采集量
                count = await self._storage.count_readings_in_range(day_start, day_end)
                
                day_date = datetime.fromtimestamp(day_start)
                stats.append({
                    "time": day_date.strftime('%Y-%m-%d'),
                    "count": count,
                    "timestamp": int(day_start)
                })
            
            total_count = sum(s["count"] for s in stats)
            avg_rate = total_count / len(stats) if stats else 0
            
            return {
                "stats": stats,
                "total_count": total_count,
                "avg_rate": round(avg_rate, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get daily collection stats: {e}")
            return SystemDefaults.get_default_collection_stats()
