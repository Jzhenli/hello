"""Tests for DeliveryRouter statistics interception"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

from xagent.xcore.statistics import StatisticsManager, StatsRecorder
from xagent.xcore.rule_engine.router import DeliveryRouter
from xagent.xcore.rule_engine.plugins import DeliveryPlugin
from xagent.xcore.rule_engine.base import (
    Notification,
    DeliveryResult,
    DeliveryStatus,
)


class MockDeliveryPlugin(DeliveryPlugin):
    """Mock 交付插件用于测试"""
    
    __plugin_name__ = "mock_delivery"
    __plugin_type__ = "delivery.mock"
    
    def __init__(self, should_succeed: bool = True, delay: float = 0):
        super().__init__()
        self.should_succeed = should_succeed
        self.delay = delay
        self.call_count = 0
        self.last_notification = None
        self._plugin_info = Mock()
    
    @property
    def plugin_info(self):
        return self._plugin_info
    
    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        return True
    
    async def test_connection(self) -> bool:
        return True
    
    async def deliver(self, notification: Notification) -> DeliveryResult:
        self.call_count += 1
        self.last_notification = notification
        
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        
        if not self.should_succeed:
            raise RuntimeError("Mock delivery error")
        
        return DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            success=True
        )


class MockPluginManager:
    """Mock 插件管理器"""
    
    def get_plugin(self, plugin_type: str, name: str):
        return None


class TestDeliveryRouterStatsInterception:
    """DeliveryRouter 统计拦截测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def stats_recorder(self, stats_manager):
        """创建 StatsRecorder 实例"""
        return StatsRecorder(stats_manager)
    
    @pytest.fixture
    def router(self, stats_recorder):
        """创建带 StatsRecorder 的 DeliveryRouter 实例"""
        router = DeliveryRouter(
            plugin_manager=MockPluginManager(),
            stats_recorder=stats_recorder
        )
        return router
    
    @pytest.fixture
    def router_no_stats(self):
        """创建不带 StatsRecorder 的 DeliveryRouter 实例"""
        return DeliveryRouter(plugin_manager=MockPluginManager())
    
    @pytest.fixture
    def notification(self):
        """创建测试通知"""
        return Notification(
            notification_id="test-001",
            rule_id="rule-001",
            rule_name="Test Rule",
            title="Test Notification",
            message="Test message",
            level="warning"
        )
    
    @pytest.mark.asyncio
    async def test_deliver_with_stats_records_success(self, router, stats_manager, notification):
        """测试成功交付记录统计"""
        mock_plugin = MockDeliveryPlugin(should_succeed=True)
        router._delivery_plugins["test_channel"] = mock_plugin
        router._channel_configs["test_channel"] = {"name": "test_channel"}
        
        result = await router.deliver(["test_channel"], notification)
        
        assert result["test_channel"].success == True
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_deliver_with_stats_records_failure(self, router, stats_manager, notification):
        """测试失败交付记录统计"""
        mock_plugin = MockDeliveryPlugin(should_succeed=False)
        router._delivery_plugins["failing_channel"] = mock_plugin
        router._channel_configs["failing_channel"] = {"name": "failing_channel"}
        
        result = await router.deliver(["failing_channel"], notification)
        
        assert result["failing_channel"].success == False
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert stats["total_failed"] == 1
    
    @pytest.mark.asyncio
    async def test_deliver_without_stats_recorder(self, router_no_stats, notification):
        """测试无 StatsRecorder 时的交付"""
        mock_plugin = MockDeliveryPlugin(should_succeed=True)
        router_no_stats._delivery_plugins["test_channel"] = mock_plugin
        router_no_stats._channel_configs["test_channel"] = {"name": "test_channel"}
        
        result = await router_no_stats.deliver(["test_channel"], notification)
        
        assert result["test_channel"].success == True
        assert mock_plugin.call_count == 1
    
    @pytest.mark.asyncio
    async def test_deliver_records_duration(self, router, stats_manager, notification):
        """测试交付耗时记录"""
        mock_plugin = MockDeliveryPlugin(should_succeed=True, delay=0.1)
        router._delivery_plugins["slow_channel"] = mock_plugin
        router._channel_configs["slow_channel"] = {"name": "slow_channel"}
        
        await router.deliver(["slow_channel"], notification)
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert "total_duration" in stats
        assert stats["total_duration"] >= 0.1
    
    @pytest.mark.asyncio
    async def test_deliver_multiple_channels(self, router, stats_manager, notification):
        """测试多渠道交付"""
        mock_plugin1 = MockDeliveryPlugin(should_succeed=True)
        mock_plugin2 = MockDeliveryPlugin(should_succeed=True)
        
        router._delivery_plugins["channel_1"] = mock_plugin1
        router._delivery_plugins["channel_2"] = mock_plugin2
        router._channel_configs["channel_1"] = {"name": "channel_1"}
        router._channel_configs["channel_2"] = {"name": "channel_2"}
        
        result = await router.deliver(["channel_1", "channel_2"], notification)
        
        assert result["channel_1"].success == True
        assert result["channel_2"].success == True
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert stats["total_uploaded"] == 2
    
    @pytest.mark.asyncio
    async def test_deliver_channel_not_found(self, router, notification):
        """测试渠道不存在的情况"""
        result = await router.deliver(["nonexistent_channel"], notification)
        
        assert "nonexistent_channel" in result
        assert result["nonexistent_channel"].success == False
    
    @pytest.mark.asyncio
    async def test_set_stats_recorder(self, router_no_stats, stats_recorder):
        """测试动态设置 StatsRecorder"""
        router_no_stats.set_stats_recorder(stats_recorder)
        
        assert router_no_stats._stats_recorder is stats_recorder
    
    @pytest.mark.asyncio
    async def test_deliver_records_channel_id(self, router, stats_manager, notification):
        """测试交付记录渠道 ID"""
        mock_plugin = MockDeliveryPlugin(should_succeed=True)
        router._delivery_plugins["ch_001"] = mock_plugin
        router._channel_configs["ch_001"] = {"name": "ch_001"}
        
        await router.deliver(["ch_001"], notification)
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert stats.get("channel_id") == "ch_001"
    
    @pytest.mark.asyncio
    async def test_multiple_deliveries_accumulate(self, router, stats_manager, notification):
        """测试多次交付累加统计"""
        mock_plugin = MockDeliveryPlugin(should_succeed=True)
        router._delivery_plugins["multi_channel"] = mock_plugin
        router._channel_configs["multi_channel"] = {"name": "multi_channel"}
        
        for _ in range(3):
            await router.deliver(["multi_channel"], notification)
        
        stats = stats_manager.get_operation_stats("delivery", "mock_delivery")
        assert stats is not None
        assert stats["total_uploaded"] == 3
