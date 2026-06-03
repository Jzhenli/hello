"""Tests for Storage extended methods (quality stats, readings count)"""

import pytest
import pytest_asyncio
import time
from datetime import datetime

from xagent.xcore.storage import SQLiteStorage, Reading


class TestStorageExtended:
    """Storage 扩展方法测试用例"""

    @pytest_asyncio.fixture
    async def storage(self, tmp_path):
        """创建临时存储实例"""
        db_path = tmp_path / "test.db"
        storage = SQLiteStorage()
        await storage.initialize({"database": str(db_path)})
        yield storage
        await storage.close()

    @pytest.fixture
    def sample_reading_data(self):
        """创建示例读数数据"""
        return {
            "timestamp": time.time(),
            "values": [
                {
                    "point_id": "point_001",
                    "value": 25.5,
                    "quality": "good"
                },
                {
                    "point_id": "point_002",
                    "value": 30.2,
                    "quality": "good"
                }
            ]
        }

    def _create_reading(self, device_id: str, timestamp: float, values: list) -> Reading:
        """创建 Reading 对象"""
        return Reading(
            asset=device_id,
            timestamp=timestamp,
            service_name="test_service",
            data=values,
            tags={}
        )

    # ===== 数据质量统计测试 =====

    @pytest.mark.asyncio
    async def test_get_quality_stats_empty_storage(self, storage):
        """测试空存储的质量统计"""
        stats = await storage.get_quality_stats()

        assert stats["good"] == 0
        assert stats["bad"] == 0
        assert stats["uncertain"] == 0
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_get_quality_stats_with_data(self, storage, sample_reading_data):
        """测试有数据的质量统计"""
        # 插入一些数据
        for i in range(5):
            reading = self._create_reading(
                f"device_{i}",
                sample_reading_data["timestamp"],
                sample_reading_data["values"]
            )
            await storage.save_batch([reading])

        stats = await storage.get_quality_stats()

        # 验证统计数据
        assert stats["total"] > 0
        assert stats["good"] >= 0
        assert stats["bad"] >= 0
        assert stats["uncertain"] >= 0

    @pytest.mark.asyncio
    async def test_get_quality_stats_after_close(self, storage):
        """测试存储关闭后的质量统计"""
        await storage.close()

        stats = await storage.get_quality_stats()

        # 应该返回默认值
        assert stats["good"] == 0
        assert stats["total"] == 0

    # ===== 采集量统计测试 =====

    @pytest.mark.asyncio
    async def test_count_readings_since_empty_storage(self, storage):
        """测试空存储的采集量统计"""
        timestamp = time.time() - 3600  # 1小时前
        count = await storage.count_readings_since(timestamp)

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_readings_since_with_data(self, storage, sample_reading_data):
        """测试有数据的采集量统计"""
        # 插入一些历史数据
        now = time.time()

        # 插入1小时前的数据
        reading1 = self._create_reading("device_001", now - 7200, sample_reading_data["values"])
        await storage.save_batch([reading1])

        # 插入当前数据
        reading2 = self._create_reading("device_002", now, sample_reading_data["values"])
        await storage.save_batch([reading2])

        # 统计最近1小时的数据
        count = await storage.count_readings_since(now - 3600)

        # 应该只统计到最近的数据
        assert count >= 1

    @pytest.mark.asyncio
    async def test_count_readings_since_specific_time(self, storage, sample_reading_data):
        """测试指定时间的采集量统计"""
        now = time.time()

        # 插入不同时间的数据
        timestamps = [
            now - 7200,  # 2小时前
            now - 3600,  # 1小时前
            now - 1800,  # 30分钟前
            now          # 现在
        ]

        for i, ts in enumerate(timestamps):
            reading = self._create_reading(f"device_{i}", ts, sample_reading_data["values"])
            await storage.save_batch([reading])

        # 统计最近1小时的数据
        count = await storage.count_readings_since(now - 3600)

        # 应该统计到最近1小时的3条数据
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_readings_since_after_close(self, storage):
        """测试存储关闭后的采集量统计"""
        await storage.close()

        timestamp = time.time() - 3600
        count = await storage.count_readings_since(timestamp)

        # 应该返回0
        assert count == 0

    # ===== 时间范围采集量统计测试 =====

    @pytest.mark.asyncio
    async def test_count_readings_in_range_empty_storage(self, storage):
        """测试空存储的时间范围统计"""
        start_time = time.time() - 7200
        end_time = time.time()

        count = await storage.count_readings_in_range(start_time, end_time)

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_readings_in_range_with_data(self, storage, sample_reading_data):
        """测试有数据的时间范围统计"""
        now = time.time()

        # 插入不同时间的数据
        timestamps = [
            now - 7200,  # 2小时前（不在范围内）
            now - 3600,  # 1小时前（在范围内）
            now - 1800,  # 30分钟前（在范围内）
            now          # 现在（在范围内）
        ]

        for i, ts in enumerate(timestamps):
            reading = self._create_reading(f"device_{i}", ts, sample_reading_data["values"])
            await storage.save_batch([reading])

        # 统计最近1小时的数据
        start_time = now - 3600
        end_time = now + 1  # 包含当前时间

        count = await storage.count_readings_in_range(start_time, end_time)

        # 应该统计到最近1小时的3条数据
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_readings_in_range_exact_boundary(self, storage, sample_reading_data):
        """测试时间范围边界条件"""
        now = time.time()

        # 插入边界时间的数据
        reading = self._create_reading("device_boundary", now, sample_reading_data["values"])
        await storage.save_batch([reading])

        # 测试包含边界
        count1 = await storage.count_readings_in_range(now, now + 1)
        assert count1 == 1

        # 测试不包含边界
        count2 = await storage.count_readings_in_range(now + 1, now + 2)
        assert count2 == 0

    @pytest.mark.asyncio
    async def test_count_readings_in_range_after_close(self, storage):
        """测试存储关闭后的时间范围统计"""
        await storage.close()

        start_time = time.time() - 3600
        end_time = time.time()

        count = await storage.count_readings_in_range(start_time, end_time)

        # 应该返回0
        assert count == 0

    # ===== 综合测试 =====

    @pytest.mark.asyncio
    async def test_combined_statistics_workflow(self, storage, sample_reading_data):
        """测试综合统计工作流"""
        now = time.time()

        # 插入多天的数据
        for day in range(3):
            for hour in range(24):
                reading = self._create_reading(
                    f"device_{day}_{hour}",
                    now - (day * 86400 + hour * 3600),
                    sample_reading_data["values"]
                )
                await storage.save_batch([reading])

        # 测试总采集量
        total_stats = await storage.get_stats()
        assert total_stats["total_readings"] > 0

        # 测试今日采集量
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_count = await storage.count_readings_since(today_start)
        assert today_count > 0

        # 测试时间范围统计
        start_time = now - 86400  # 最近24小时
        range_count = await storage.count_readings_in_range(start_time, now)
        assert range_count > 0

        # 测试数据质量
        quality_stats = await storage.get_quality_stats()
        assert quality_stats["total"] > 0
