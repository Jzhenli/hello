"""统计模块 - 提供统一的统计管理功能

核心组件：
- StatisticsManager: 统计管理器，集中管理所有统计功能
- StatsCollector: 统计收集器，轻量级高性能收集器

使用示例：
    from xagent.xcore.statistics import StatisticsManager
    
    # 创建统计管理器
    stats_manager = StatisticsManager(storage=storage)
    await stats_manager.start()
    
    # 记录通道统计
    await stats_manager.record_channel_stats('channel_1', 10, success=True)
    
    # 记录数据采集
    await stats_manager.record_data_collection('device_1', 5)
    
    # 获取趋势数据
    trend = await stats_manager.get_hourly_trend(24)
"""

from .manager import StatisticsManager
from .collector import StatsCollector

__all__ = ['StatisticsManager', 'StatsCollector']
