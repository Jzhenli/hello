"""Aggregation Engine

负责对历史数据进行窗口聚合计算。
"""

import logging
import statistics
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    AggregationType,
    SubscriptionMode,
    AggregationSubscription,
    AggregationResult,
)

logger = logging.getLogger(__name__)


class DataWindow:
    """数据窗口

    使用环形缓冲区存储时间窗口内的数据点。
    支持内存限制和溢出处理。

    Attributes:
        window_size: 窗口大小（秒）
        max_points: 最大数据点数
        max_memory_mb: 最大内存使用量（MB）
    """

    def __init__(
        self,
        window_size: int,
        max_points: int = 10000,
        max_memory_mb: float = 100
    ):
        """初始化数据窗口

        Args:
            window_size: 窗口大小（秒）
            max_points: 最大数据点数
            max_memory_mb: 最大内存使用量（MB）
        """
        self.window_size = window_size
        self.max_points = max_points
        self.max_memory_mb = max_memory_mb

        self._values: deque = deque(maxlen=max_points)
        self._timestamps: deque = deque(maxlen=max_points)
        self._qualities: deque = deque(maxlen=max_points)

        self._total_added: int = 0
        self._overflow_count: int = 0

    def add(self, value: Any, timestamp: float, quality: str = "good") -> None:
        """添加数据点

        Args:
            value: 数据值
            timestamp: 时间戳
            quality: 数据质量
        """
        if self._estimate_memory() > self.max_memory_mb * 1024 * 1024:
            self._handle_overflow()

        self._values.append(value)
        self._timestamps.append(timestamp)
        self._qualities.append(quality)
        self._total_added += 1

        self._cleanup(timestamp)

    def _estimate_memory(self) -> int:
        """估算当前内存使用量（字节）"""
        return len(self._values) * 100

    def _handle_overflow(self) -> None:
        """处理内存溢出"""
        self._overflow_count += 1

        drop_count = max(1, len(self._values) // 10)
        for _ in range(drop_count):
            if self._values:
                self._values.popleft()
                self._timestamps.popleft()
                self._qualities.popleft()

        logger.warning(
            f"DataWindow memory overflow, dropped {drop_count} points, "
            f"total_overflows={self._overflow_count}"
        )

    def _cleanup(self, current_time: float) -> None:
        """清理过期数据"""
        cutoff = current_time - self.window_size

        while self._timestamps and self._timestamps[0] < cutoff:
            self._values.popleft()
            self._timestamps.popleft()
            self._qualities.popleft()

    def get_values(self, quality_filter: str = "good") -> List[Any]:
        """获取窗口内数据

        Args:
            quality_filter: 质量过滤

        Returns:
            数据值列表
        """
        if quality_filter == "all":
            return list(self._values)

        return [
            v for v, q in zip(self._values, self._qualities)
            if q == "good"
        ]

    def get_timestamps(self, quality_filter: str = "good") -> List[float]:
        """获取窗口内时间戳

        Args:
            quality_filter: 质量过滤

        Returns:
            时间戳列表
        """
        if quality_filter == "all":
            return list(self._timestamps)

        return [
            t for t, q in zip(self._timestamps, self._qualities)
            if q == "good"
        ]

    def get_statistics(self, quality_filter: str = "good") -> Dict[str, Any]:
        """计算统计值

        Args:
            quality_filter: 质量过滤

        Returns:
            统计值字典
        """
        values = self.get_values(quality_filter)

        if not values:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "sum": None,
                "stddev": None,
                "first": None,
                "last": None
            }

        numeric_values = [v for v in values if isinstance(v, (int, float))]

        result = {
            "count": len(values),
            "first": values[0],
            "last": values[-1]
        }

        if numeric_values:
            result.update({
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": statistics.mean(numeric_values),
                "sum": sum(numeric_values),
                "stddev": statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0
            })

        return result

    def get_window_range(self) -> tuple:
        """获取窗口时间范围"""
        if not self._timestamps:
            return (0, 0)
        return (self._timestamps[0], self._timestamps[-1])

    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存使用信息"""
        return {
            "current_points": len(self._values),
            "max_points": self.max_points,
            "estimated_memory_bytes": self._estimate_memory(),
            "max_memory_mb": self.max_memory_mb,
            "total_added": self._total_added,
            "overflow_count": self._overflow_count
        }

    def clear(self) -> None:
        """清空窗口"""
        self._values.clear()
        self._timestamps.clear()
        self._qualities.clear()


class AggregationEngine:
    """聚合引擎

    管理数据窗口，执行聚合计算。
    使用数据索引优化查找性能。

    Attributes:
        storage: 存储对象
        cache_ttl: SINGLE 模式结果缓存 TTL（秒）
        _windows: 数据窗口字典
        _subscriptions: 订阅字典
        _data_index: 数据索引
        _single_cache: SINGLE 模式结果缓存
    """

    def __init__(self, storage: Any = None, cache_ttl: float = 1.0):
        """初始化聚合引擎

        Args:
            storage: 存储对象
            cache_ttl: SINGLE 模式结果缓存 TTL（秒），默认 1.0 秒
        """
        self.storage = storage
        self.cache_ttl = cache_ttl
        self._windows: Dict[str, DataWindow] = {}
        self._subscriptions: Dict[str, AggregationSubscription] = {}
        self._data_index: Dict[str, List[str]] = {}
        self._single_cache: Dict[str, Tuple[float, AggregationResult]] = {}

    def register(self, subscription: AggregationSubscription) -> None:
        """注册聚合订阅

        Args:
            subscription: 聚合订阅配置
        """
        self._subscriptions[subscription.subscription_id] = subscription

        index_key = f"{subscription.asset}:{subscription.point_name}"
        if index_key not in self._data_index:
            self._data_index[index_key] = []
        self._data_index[index_key].append(subscription.subscription_id)

        if subscription.mode == SubscriptionMode.WINDOW:
            self._windows[subscription.subscription_id] = DataWindow(
                window_size=subscription.window_size,
                max_points=subscription.max_data_points
            )

        logger.info(
            f"Aggregation subscription registered: "
            f"{subscription.asset}/{subscription.point_name}, "
            f"mode={subscription.mode.value}, "
            f"agg={subscription.aggregation_type.value}"
        )

    def unregister(self, subscription_id: str) -> None:
        """取消注册

        Args:
            subscription_id: 订阅ID
        """
        sub = self._subscriptions.pop(subscription_id, None)
        if sub:
            index_key = f"{sub.asset}:{sub.point_name}"
            if index_key in self._data_index:
                self._data_index[index_key] = [
                    sid for sid in self._data_index[index_key]
                    if sid != subscription_id
                ]
                if not self._data_index[index_key]:
                    del self._data_index[index_key]

        window = self._windows.pop(subscription_id, None)
        if window:
            window.clear()

    def on_data(
        self,
        asset: str,
        point_name: str,
        value: Any,
        timestamp: float,
        quality: str = "good"
    ) -> None:
        """数据回调

        当新数据到达时，使用索引快速查找相关订阅并更新窗口。

        Args:
            asset: 设备ID
            point_name: 点位名称
            value: 数据值
            timestamp: 时间戳
            quality: 数据质量
        """
        index_key = f"{asset}:{point_name}"
        self._single_cache.pop(index_key, None)
        sub_ids = self._data_index.get(index_key, [])

        for sub_id in sub_ids:
            window = self._windows.get(sub_id)
            if window:
                window.add(value, timestamp, quality)

    async def get_aggregation_result(
        self, subscription_id: str
    ) -> AggregationResult:
        """获取聚合结果

        Args:
            subscription_id: 订阅ID

        Returns:
            聚合结果
        """
        sub = self._subscriptions.get(subscription_id)
        if not sub:
            raise ValueError(f"Subscription not found: {subscription_id}")

        if sub.mode == SubscriptionMode.SINGLE:
            return await self._get_single_result(sub)
        else:
            return self._get_window_result(sub)

    async def _get_single_result(
        self, sub: AggregationSubscription
    ) -> AggregationResult:
        """获取单次数据结果（带 TTL 缓存）"""
        cache_key = f"{sub.asset}:{sub.point_name}"
        now = time.monotonic()

        cached = self._single_cache.get(cache_key)
        if cached:
            cached_time, cached_result = cached
            if now - cached_time < self.cache_ttl:
                return cached_result

        latest = None
        timestamp = 0
        quality = "good"

        if self.storage:
            try:
                readings = await self.storage.query(
                    asset=sub.asset,
                    point_name=sub.point_name,
                    limit=1
                )
                if readings:
                    reading = readings[0]
                    latest = reading.data.get(sub.point_name)
                    timestamp = reading.timestamp
                    quality = getattr(reading, 'quality', None) or "good"
            except Exception as e:
                logger.error(
                    f"Failed to query storage for {sub.asset}:"
                    f"{sub.point_name}: {e}"
                )

        result = AggregationResult(
            subscription_id=sub.subscription_id,
            asset=sub.asset,
            point_name=sub.point_name,
            value=latest,
            aggregation_type=AggregationType.NONE,
            window_end=timestamp,
            data_points=1,
            quality=quality
        )

        self._single_cache[cache_key] = (now, result)

        return result

    def _get_window_result(
        self, sub: AggregationSubscription
    ) -> AggregationResult:
        """获取窗口聚合结果"""
        window = self._windows.get(sub.subscription_id)
        if not window:
            raise ValueError(f"Window not found: {sub.subscription_id}")

        stats = window.get_statistics(sub.data_quality_filter)
        window_range = window.get_window_range()

        agg_value = self._calculate_aggregation(stats, sub.aggregation_type)

        return AggregationResult(
            subscription_id=sub.subscription_id,
            asset=sub.asset,
            point_name=sub.point_name,
            value=agg_value,
            aggregation_type=sub.aggregation_type,
            window_start=window_range[0],
            window_end=window_range[1],
            data_points=stats["count"],
            min_value=stats.get("min"),
            max_value=stats.get("max"),
            avg_value=stats.get("avg"),
            sum_value=stats.get("sum"),
            first_value=stats.get("first"),
            last_value=stats.get("last"),
            stddev_value=stats.get("stddev")
        )

    def _calculate_aggregation(
        self,
        stats: Dict[str, Any],
        agg_type: AggregationType
    ) -> Any:
        """计算聚合值

        Args:
            stats: 统计值字典
            agg_type: 聚合类型

        Returns:
            聚合值
        """
        if agg_type == AggregationType.NONE:
            return stats.get("last")
        elif agg_type == AggregationType.MIN:
            return stats.get("min")
        elif agg_type == AggregationType.MAX:
            return stats.get("max")
        elif agg_type == AggregationType.AVG:
            return stats.get("avg")
        elif agg_type == AggregationType.SUM:
            return stats.get("sum")
        elif agg_type == AggregationType.COUNT:
            return stats.get("count")
        elif agg_type == AggregationType.FIRST:
            return stats.get("first")
        elif agg_type == AggregationType.LAST:
            return stats.get("last")
        elif agg_type == AggregationType.DELTA:
            first = stats.get("first")
            last = stats.get("last")
            if first is not None and last is not None:
                return last - first
            return None
        elif agg_type == AggregationType.STDDEV:
            return stats.get("stddev")
        else:
            return stats.get("last")

    def get_all_subscriptions(self) -> List[AggregationSubscription]:
        """获取所有订阅

        Returns:
            订阅列表
        """
        return list(self._subscriptions.values())

    def get_subscriptions_by_rule(
        self, rule_id: str
    ) -> List[AggregationSubscription]:
        """获取规则关联的订阅

        Args:
            rule_id: 规则ID

        Returns:
            订阅列表
        """
        return [
            sub for sub in self._subscriptions.values()
            if sub.rule_id == rule_id
        ]

    def get_window_info(
        self, subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取窗口信息

        Args:
            subscription_id: 订阅ID

        Returns:
            窗口信息
        """
        window = self._windows.get(subscription_id)
        if window:
            return window.get_memory_info()
        return None

    def clear(self) -> None:
        """清空所有数据"""
        for window in self._windows.values():
            window.clear()

        self._windows.clear()
        self._subscriptions.clear()
        self._data_index.clear()
        self._single_cache.clear()

        logger.info("Aggregation engine cleared")
