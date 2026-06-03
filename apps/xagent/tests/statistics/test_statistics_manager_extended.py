"""Tests for StatisticsManager extended methods (system stats, data quality, collection stats)"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from xagent.xcore.statistics import StatisticsManager


class TestStatisticsManagerExtended:
    """StatisticsManager 扩展方法测试用例"""

    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})

    @pytest.fixture
    def mock_storage(self):
        """创建 mock storage"""
        storage = AsyncMock()
        storage.get_stats = AsyncMock(return_value={
            "total_readings": 10000,
            "total_devices": 5
        })
        storage.count_readings_since = AsyncMock(return_value=500)
        storage.get_quality_stats = AsyncMock(return_value={
            "good": 950,
            "bad": 30,
            "uncertain": 20,
            "total": 1000
        })
        storage.count_readings_in_range = AsyncMock(return_value=100)
        return storage

    # ===== 系统资源统计测试 =====

    @pytest.mark.asyncio
    async def test_get_system_stats_basic(self, stats_manager):
        """测试基本的系统统计获取"""
        stats = await stats_manager.get_system_stats()

        # 验证返回的字段
        assert "cpu_usage" in stats
        assert "memory_usage" in stats
        assert "disk_usage" in stats
        assert "uptime" in stats
        assert "total_readings" in stats
        assert "today_readings" in stats
        assert "connection_count" in stats
        assert "process_count" in stats
        assert "load_average" in stats

        # 验证数据类型
        assert isinstance(stats["cpu_usage"], float)
        assert isinstance(stats["memory_usage"], float)
        assert isinstance(stats["disk_usage"], float)
        assert isinstance(stats["uptime"], int)
        assert isinstance(stats["load_average"], list)
        assert len(stats["load_average"]) == 3

    @pytest.mark.asyncio
    async def test_get_system_stats_with_storage(self, stats_manager, mock_storage):
        """测试带存储的系统统计获取"""
        stats_manager._storage = mock_storage

        stats = await stats_manager.get_system_stats()

        # 验证从存储获取的数据
        assert stats["total_readings"] == 10000
        assert stats["today_readings"] == 500

        # 验证调用了正确的方法
        mock_storage.get_stats.assert_called_once()
        mock_storage.count_readings_since.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_stats_no_storage(self, stats_manager):
        """测试无存储时的系统统计"""
        stats_manager._storage = None

        stats = await stats_manager.get_system_stats()

        # 应该返回默认值
        assert stats["total_readings"] == 0
        assert stats["today_readings"] == 0

    @pytest.mark.asyncio
    async def test_get_system_stats_error_handling(self, stats_manager, mock_storage):
        """测试系统统计的错误处理"""
        # 模拟存储异常
        mock_storage.get_stats.side_effect = Exception("Storage error")
        mock_storage.count_readings_since.side_effect = Exception("Storage error")
        stats_manager._storage = mock_storage

        # 应该不会抛出异常，而是返回默认值
        stats = await stats_manager.get_system_stats()

        assert stats["total_readings"] == 0
        assert stats["today_readings"] == 0

    # ===== 数据质量统计测试 =====

    @pytest.mark.asyncio
    async def test_get_quality_stats_basic(self, stats_manager, mock_storage):
        """测试基本的数据质量统计"""
        stats_manager._storage = mock_storage

        stats = await stats_manager.get_data_quality_stats()

        # 验证返回的字段
        assert "good" in stats
        assert "bad" in stats
        assert "uncertain" in stats
        assert "total" in stats
        assert "quality_rate" in stats

        # 验证计算的质量率
        assert stats["good"] == 950
        assert stats["bad"] == 30
        assert stats["uncertain"] == 20
        assert stats["total"] == 1000
        assert stats["quality_rate"] == 95.0  # 950/1000 * 100

    @pytest.mark.asyncio
    async def test_get_data_quality_stats_no_storage(self, stats_manager):
        """测试无存储时的数据质量统计"""
        stats_manager._storage = None

        stats = await stats_manager.get_data_quality_stats()

        # 应该返回默认值
        assert stats["good"] == 0
        assert stats["bad"] == 0
        assert stats["uncertain"] == 0
        assert stats["total"] == 0
        assert stats["quality_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_data_quality_stats_zero_total(self, stats_manager, mock_storage):
        """测试总数据为零时的质量统计"""
        mock_storage.get_quality_stats.return_value = {
            "good": 0,
            "bad": 0,
            "uncertain": 0,
            "total": 0
        }
        stats_manager._storage = mock_storage

        stats = await stats_manager.get_data_quality_stats()

        # 避免除零错误
        assert stats["quality_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_data_quality_stats_error_handling(self, stats_manager, mock_storage):
        """测试数据质量统计的错误处理"""
        mock_storage.get_quality_stats.side_effect = Exception("Quality stats error")
        stats_manager._storage = mock_storage

        stats = await stats_manager.get_data_quality_stats()

        # 应该返回默认值
        assert stats["good"] == 0
        assert stats["quality_rate"] == 0.0

    # ===== 数据采集趋势统计测试 =====

    @pytest.mark.asyncio
    async def test_get_collection_stats_default_params(self, stats_manager):
        """测试默认参数的采集统计"""
        stats = await stats_manager.get_collection_stats()

        # 验证返回的字段
        assert "stats" in stats
        assert "total_count" in stats
        assert "avg_rate" in stats

        # 验证默认查询24小时
        assert isinstance(stats["stats"], list)

    @pytest.mark.asyncio
    async def test_get_collection_stats_custom_range(self, stats_manager):
        """测试自定义时间范围的采集统计"""
        end_time = time.time()
        start_time = end_time - 7200  # 2小时前

        stats = await stats_manager.get_collection_stats(
            start_time=start_time,
            end_time=end_time,
            interval="hour"
        )

        assert "stats" in stats
        assert "total_count" in stats
        assert "avg_rate" in stats

    @pytest.mark.asyncio
    async def test_get_collection_stats_with_trend_data(self, stats_manager):
        """测试有趋势数据的采集统计"""
        # 先记录一些数据
        for i in range(5):
            await stats_manager.record_data_collection(
                device_id=f"device_{i}",
                point_count=10
            )

        stats = await stats_manager.get_collection_stats(interval="hour")

        # 验证统计数据
        assert stats["total_count"] >= 0
        assert stats["avg_rate"] >= 0

    @pytest.mark.asyncio
    async def test_get_collection_stats_error_handling(self, stats_manager):
        """测试采集统计的错误处理"""
        # 模拟异常情况
        with patch.object(stats_manager, 'get_hourly_trend', side_effect=Exception("Trend error")):
            stats = await stats_manager.get_collection_stats()

            # 应该返回默认值
            assert stats["stats"] == []
            assert stats["total_count"] == 0
            assert stats["avg_rate"] == 0.0

    # ===== 内部方法测试 =====

    @pytest.mark.asyncio
    async def test_get_total_readings(self, stats_manager, mock_storage):
        """测试获取总采集量"""
        stats_manager._storage = mock_storage

        total = await stats_manager._get_total_readings()

        assert total == 10000
        mock_storage.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_total_readings_no_storage(self, stats_manager):
        """测试无存储时获取总采集量"""
        stats_manager._storage = None

        total = await stats_manager._get_total_readings()

        assert total == 0

    @pytest.mark.asyncio
    async def test_get_today_readings(self, stats_manager, mock_storage):
        """测试获取今日采集量"""
        stats_manager._storage = mock_storage

        today = await stats_manager._get_today_readings()

        assert today == 500
        mock_storage.count_readings_since.assert_called_once()

        # 验证传入的时间戳是今天开始
        call_args = mock_storage.count_readings_since.call_args
        timestamp = call_args[0][0]

        # 验证时间戳是今天0点
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected_timestamp = today_start.timestamp()

        # 允许1秒的误差
        assert abs(timestamp - expected_timestamp) < 1

    @pytest.mark.asyncio
    async def test_get_today_readings_no_storage(self, stats_manager):
        """测试无存储时获取今日采集量"""
        stats_manager._storage = None

        today = await stats_manager._get_today_readings()

        assert today == 0

    @pytest.mark.asyncio
    async def test_get_daily_collection_stats(self, stats_manager, mock_storage):
        """测试按天统计采集数据"""
        stats_manager._storage = mock_storage

        end_time = time.time()
        start_time = end_time - 86400 * 3  # 3天前

        stats = await stats_manager._get_daily_collection_stats(start_time, end_time)

        # 验证返回的数据结构
        assert "stats" in stats
        assert "total_count" in stats
        assert "avg_rate" in stats

        # 验证调用了存储方法
        assert mock_storage.count_readings_in_range.call_count == 3

    @pytest.mark.asyncio
    async def test_get_daily_collection_stats_no_storage(self, stats_manager):
        """测试无存储时的按天统计"""
        stats_manager._storage = None

        end_time = time.time()
        start_time = end_time - 86400

        stats = await stats_manager._get_daily_collection_stats(start_time, end_time)

        # 应该返回默认值
        assert stats["stats"] == []
        assert stats["total_count"] == 0
        assert stats["avg_rate"] == 0.0
