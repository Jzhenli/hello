"""Tests for StatisticsManager.record_data_collection()"""

import asyncio
import pytest
from datetime import datetime

from xagent.xcore.statistics import StatisticsManager, StatsCollector


class TestStatisticsManager:
    """StatisticsManager 测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.mark.asyncio
    async def test_record_data_collection_basic(self, stats_manager):
        """测试基本的数据采集记录"""
        await stats_manager.record_data_collection(
            device_id="device_001",
            point_count=10
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert "device_001" in device_stats
        assert device_stats["device_001"] == 10
    
    @pytest.mark.asyncio
    async def test_record_data_collection_with_successful_count(self, stats_manager):
        """测试带成功计数的数据采集记录"""
        await stats_manager.record_data_collection(
            device_id="device_002",
            point_count=10,
            successful_count=8
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert "device_002" in device_stats
        assert device_stats["device_002"] == 10
        
        all_stats = stats_manager.get_all_stats()
        device_key = "device:device_002"
        assert device_key in all_stats
        assert all_stats[device_key]["total_uploaded"] == 10
    
    @pytest.mark.asyncio
    async def test_record_data_collection_full_params(self, stats_manager):
        """测试带完整参数的数据采集记录"""
        await stats_manager.record_data_collection(
            device_id="device_003",
            point_count=5,
            successful_count=5
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert device_stats["device_003"] == 5
    
    @pytest.mark.asyncio
    async def test_record_data_collection_zero_points(self, stats_manager):
        """测试零点位采集（失败情况）"""
        await stats_manager.record_data_collection(
            device_id="device_004",
            point_count=0,
            successful_count=0
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert device_stats.get("device_004", 0) == 0
    
    @pytest.mark.asyncio
    async def test_record_data_collection_partial_success(self, stats_manager):
        """测试部分成功的情况"""
        await stats_manager.record_data_collection(
            device_id="device_005",
            point_count=20,
            successful_count=15
        )
        
        device_stats = stats_manager.get_device_distribution()
        assert device_stats["device_005"] == 20
    
    @pytest.mark.asyncio
    async def test_record_data_collection_disabled(self):
        """测试禁用状态下的记录"""
        manager = StatisticsManager(storage=None, config={'enabled': False})
        
        await manager.record_data_collection(
            device_id="device_006",
            point_count=10
        )
        
        device_stats = manager.get_device_distribution()
        assert "device_006" not in device_stats
    
    @pytest.mark.asyncio
    async def test_hourly_trend(self, stats_manager):
        """测试小时趋势统计 - 验证数据被正确记录到当前小时的 collector"""
        for i in range(5):
            await stats_manager.record_data_collection(
                device_id=f"device_{i}",
                point_count=10
            )
        
        current_hour_key = f"collection:{datetime.now().strftime('%Y-%m-%d:%H')}"
        assert current_hour_key in stats_manager._collectors
        
        collector = stats_manager._collectors[current_hour_key]
        stats = collector.get_stats()
        assert stats["total_uploaded"] == 50
    
    @pytest.mark.asyncio
    async def test_multiple_devices_distribution(self, stats_manager):
        """测试多设备采集分布"""
        devices = ["modbus_001", "knx_001", "bacnet_001"]
        counts = [100, 50, 75]
        
        for device, count in zip(devices, counts):
            await stats_manager.record_data_collection(
                device_id=device,
                point_count=count
            )
        
        distribution = stats_manager.get_device_distribution()
        assert len(distribution) == 3
        assert distribution["modbus_001"] == 100
        assert distribution["knx_001"] == 50
        assert distribution["bacnet_001"] == 75
    
    @pytest.mark.asyncio
    async def test_collector_reuse(self, stats_manager):
        """测试收集器复用"""
        await stats_manager.record_data_collection("device_001", 10)
        await stats_manager.record_data_collection("device_001", 20)
        
        device_stats = stats_manager.get_device_distribution()
        assert device_stats["device_001"] == 30
    
    def test_get_or_create_collector(self, stats_manager):
        """测试获取或创建收集器"""
        collector1 = stats_manager._get_or_create_collector("test:001")
        collector2 = stats_manager._get_or_create_collector("test:001")
        
        assert collector1 is collector2
        assert isinstance(collector1, StatsCollector)
