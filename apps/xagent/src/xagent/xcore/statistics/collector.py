"""统计收集器 - 轻量级高性能统计收集

设计原则：
1. O(1) 时间复杂度：所有操作都是常数时间
2. 内存占用小：使用 __slots__ 优化，限制时间戳列表长度
3. 线程安全：使用 asyncio.Lock 保护共享状态
4. 容错性强：统计失败不影响主业务流程
"""

import time
import asyncio
from typing import Dict, Any


class StatsCollector:
    """轻量级统计收集器
    
    针对IoT边缘网关场景优化：
    - 使用 __slots__ 减少内存占用
    - 限制时间戳列表长度，避免内存泄漏
    - 所有操作 O(1) 时间复杂度
    - 异步锁保护，线程安全
    
    统计指标：
    - upload_rate: 最近1分钟的上传次数（条/分）
    - success_rate: 上传成功率（百分比）
    - total_uploaded: 总上传数据条数
    - total_failed: 总失败次数
    - extra_metrics: 额外指标（如 duration, triggered 等）
    """
    
    __slots__ = [
        '_total_uploaded',
        '_success_count', 
        '_failure_count',
        '_timestamps',
        '_lock',
        '_max_timestamps',
        '_extra_metrics'
    ]
    
    def __init__(self, max_timestamps: int = 120):
        """初始化统计收集器
        
        Args:
            max_timestamps: 最大保存的时间戳数量（默认120个，约2分钟数据）
        """
        self._total_uploaded = 0
        self._success_count = 0
        self._failure_count = 0
        self._timestamps: list = []
        self._lock = asyncio.Lock()
        self._max_timestamps = max_timestamps
        self._extra_metrics: Dict[str, Any] = {}
    
    async def record(self, count: int, success: bool) -> None:
        """记录一次上传操作
        
        时间复杂度: O(1)
        空间复杂度: O(1) - 受 max_timestamps 限制
        
        Args:
            count: 本次上传的数据条数
            success: 是否成功
        """
        async with self._lock:
            self._total_uploaded += count
            
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
            
            now = time.time()
            self._timestamps.append(now)
            
            if len(self._timestamps) > self._max_timestamps:
                self._timestamps = self._timestamps[-self._max_timestamps:]
    
    def record_extra(self, metrics: Dict[str, Any]) -> None:
        """记录额外指标（同步方法，用于非计数指标）
        
        Args:
            metrics: 额外指标字典
        """
        for key, value in metrics.items():
            if key not in self._extra_metrics:
                self._extra_metrics[key] = value
                if key.startswith("avg_") or key.endswith("_avg"):
                    self._extra_metrics[f"_count_{key}"] = 1
            elif isinstance(value, (int, float)) and isinstance(self._extra_metrics.get(key), (int, float)):
                if key.startswith("total_") or key.startswith("sum_"):
                    self._extra_metrics[key] += value
                elif key.startswith("avg_") or key.endswith("_avg"):
                    count_key = f"_count_{key}"
                    current_count = self._extra_metrics.get(count_key, 1) + 1
                    self._extra_metrics[count_key] = current_count
                    self._extra_metrics[key] = (
                        (self._extra_metrics[key] * (current_count - 1) + value) / current_count
                    )
                else:
                    self._extra_metrics[key] += value
            else:
                self._extra_metrics[key] = value
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        时间复杂度: O(1)
        
        Returns:
            Dict[str, Any]: 统计数据字典
        """
        now = time.time()
        
        recent_count = 0
        for ts in reversed(self._timestamps):
            if now - ts <= 60:
                recent_count += 1
            else:
                break
        
        total_operations = self._success_count + self._failure_count
        success_rate = 0.0
        if total_operations > 0:
            success_rate = (self._success_count / total_operations) * 100
        
        stats = {
            "upload_rate": recent_count,
            "success_rate": round(success_rate, 2),
            "total_uploaded": self._total_uploaded,
            "total_failed": self._failure_count,
            "backlog_count": 0
        }
        
        if self._extra_metrics:
            for key, value in self._extra_metrics.items():
                if not key.startswith("_count_"):
                    stats[key] = value
        
        return stats
    
    def reset(self) -> None:
        """重置统计数据
        
        用于测试或手动清理。
        """
        self._total_uploaded = 0
        self._success_count = 0
        self._failure_count = 0
        self._timestamps.clear()
        self._extra_metrics.clear()
    
    @property
    def total_uploaded(self) -> int:
        """获取总上传数"""
        return self._total_uploaded
    
    @property
    def success_count(self) -> int:
        """获取成功次数"""
        return self._success_count
    
    @property
    def failure_count(self) -> int:
        """获取失败次数"""
        return self._failure_count
