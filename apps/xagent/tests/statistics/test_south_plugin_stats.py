"""Tests for SouthPluginBase statistics functionality"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from xagent.xcore.plugins.south import SouthPluginBase
from xagent.xcore.statistics import StatisticsManager
from xagent.xcore.storage.interface import Reading
from xagent.xcore.core.event_bus import EventBus


class MockSouthPlugin(SouthPluginBase):
    """测试用的南向插件实现"""
    
    __plugin_name__ = "mock_south"
    
    def _create_data_converter(self) -> Any:
        return MagicMock()
    
    async def connect(self) -> bool:
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        self._connected = False
    
    async def poll(self) -> List[Reading]:
        return []


class TestSouthPluginStats:
    """SouthPluginBase 统计功能测试"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()
    
    @pytest.fixture
    def config(self):
        """创建插件配置"""
        return {
            "asset_name": "test_device",
            "points": [
                {"name": "point1", "address": 1},
                {"name": "point2", "address": 2},
            ]
        }
    
    @pytest.fixture
    def storage(self):
        """创建存储模拟"""
        return AsyncMock()
    
    @pytest.fixture
    def plugin(self, config, storage, event_bus):
        """创建插件实例"""
        return MockSouthPlugin(config, storage, event_bus)
    
    @pytest.fixture
    def stats_manager(self):
        """创建统计管理器"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    def test_initial_performance_stats(self, plugin):
        """测试初始性能统计状态"""
        assert plugin._performance_stats["total_polls"] == 0
        assert plugin._performance_stats["total_points_read"] == 0
        assert plugin._performance_stats["successful_points_read"] == 0
        assert plugin._performance_stats["last_poll_time"] == 0.0
        assert plugin._performance_stats["avg_poll_time"] == 0.0
        assert plugin._performance_stats["total_time"] == 0.0
        assert plugin._performance_stats["success_rate"] == 0.0
    
    def test_stats_manager_initial_none(self, plugin):
        """测试统计管理器初始为 None"""
        assert plugin._stats_manager is None
    
    def test_set_stats_manager(self, plugin, stats_manager):
        """测试设置统计管理器"""
        plugin.set_stats_manager(stats_manager)
        
        assert plugin._stats_manager is stats_manager
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_local(self, plugin):
        """测试本地性能统计更新"""
        await plugin._update_performance_stats(
            poll_duration=1.5,
            points_count=10,
            successful_count=8
        )
        
        assert plugin._performance_stats["total_polls"] == 1
        assert plugin._performance_stats["total_points_read"] == 10
        assert plugin._performance_stats["successful_points_read"] == 8
        assert plugin._performance_stats["last_poll_time"] == 1.5
        assert plugin._performance_stats["total_time"] == 1.5
        assert plugin._performance_stats["avg_poll_time"] == 1.5
        assert plugin._performance_stats["success_rate"] == 0.8
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_multiple_calls(self, plugin):
        """测试多次更新性能统计"""
        await plugin._update_performance_stats(1.0, 10, 10)
        await plugin._update_performance_stats(2.0, 20, 15)
        await plugin._update_performance_stats(1.5, 15, 12)
        
        assert plugin._performance_stats["total_polls"] == 3
        assert plugin._performance_stats["total_points_read"] == 45
        assert plugin._performance_stats["successful_points_read"] == 37
        assert plugin._performance_stats["total_time"] == 4.5
        assert plugin._performance_stats["avg_poll_time"] == 1.5
        assert abs(plugin._performance_stats["success_rate"] - 0.822) < 0.01
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_with_stats_manager(self, plugin, stats_manager):
        """测试带统计管理器的性能统计更新"""
        plugin.set_stats_manager(stats_manager)
        
        await plugin._update_performance_stats(
            poll_duration=1.5,
            points_count=10,
            successful_count=8
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert "test_device" in device_stats
        assert device_stats["test_device"] == 10
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_without_stats_manager(self, plugin):
        """测试无统计管理器时的性能统计更新"""
        await plugin._update_performance_stats(
            poll_duration=1.0,
            points_count=5,
            successful_count=5
        )
        
        assert plugin._performance_stats["total_polls"] == 1
        assert plugin._performance_stats["total_points_read"] == 5
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_zero_points(self, plugin, stats_manager):
        """测试零点位统计"""
        plugin.set_stats_manager(stats_manager)
        
        await plugin._update_performance_stats(
            poll_duration=0.1,
            points_count=0,
            successful_count=0
        )
        
        assert plugin._performance_stats["total_polls"] == 1
        assert plugin._performance_stats["total_points_read"] == 0
    
    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, plugin):
        """测试成功率计算"""
        await plugin._update_performance_stats(1.0, 100, 80)
        
        assert plugin._performance_stats["success_rate"] == 0.8
        
        await plugin._update_performance_stats(1.0, 100, 90)
        
        expected_rate = 170 / 200
        assert abs(plugin._performance_stats["success_rate"] - expected_rate) < 0.01
    
    @pytest.mark.asyncio
    async def test_avg_poll_time_calculation(self, plugin):
        """测试平均轮询时间计算"""
        await plugin._update_performance_stats(2.0, 10, 10)
        assert plugin._performance_stats["avg_poll_time"] == 2.0
        
        await plugin._update_performance_stats(4.0, 10, 10)
        assert plugin._performance_stats["avg_poll_time"] == 3.0
        
        await plugin._update_performance_stats(3.0, 10, 10)
        assert plugin._performance_stats["avg_poll_time"] == 3.0
    
    @pytest.mark.asyncio
    async def test_integration_with_stats_manager(self, plugin, stats_manager):
        """测试与 StatisticsManager 的集成"""
        plugin.set_stats_manager(stats_manager)
        
        for i in range(5):
            await plugin._update_performance_stats(
                poll_duration=1.0 + i * 0.1,
                points_count=20,
                successful_count=18 + i
            )
        
        assert plugin._performance_stats["total_polls"] == 5
        assert plugin._performance_stats["total_points_read"] == 100
        
        device_stats = stats_manager.get_device_distribution()
        assert device_stats["test_device"] == 100
        
        all_stats = stats_manager.get_all_stats()
        device_key = "device:test_device"
        assert device_key in all_stats


class TestSouthPluginStatsConsistency:
    """测试南向插件统计与北向插件的一致性"""
    
    @pytest.fixture
    def south_plugin(self):
        """创建南向插件"""
        config = {"asset_name": "device_001"}
        return MockSouthPlugin(config, AsyncMock(), EventBus())
    
    @pytest.fixture
    def stats_manager(self):
        """创建统计管理器"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    def test_set_stats_manager_signature(self, south_plugin, stats_manager):
        """测试 set_stats_manager 方法签名与 NorthPluginBase 一致"""
        assert hasattr(south_plugin, 'set_stats_manager')
        assert callable(south_plugin.set_stats_manager)
        
        south_plugin.set_stats_manager(stats_manager)
        assert south_plugin._stats_manager is stats_manager
    
    def test_stats_manager_attribute_name(self, south_plugin):
        """测试属性名与 NorthPluginBase 一致"""
        assert hasattr(south_plugin, '_stats_manager')
        assert south_plugin._stats_manager is None
    
    @pytest.mark.asyncio
    async def test_update_performance_stats_is_async(self, south_plugin):
        """测试 _update_performance_stats 是异步方法"""
        import inspect
        assert inspect.iscoroutinefunction(south_plugin._update_performance_stats)
        
        await south_plugin._update_performance_stats(1.0, 10, 10)
        
        assert south_plugin._performance_stats["total_polls"] == 1
