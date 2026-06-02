"""Tests for StatsCollector extra metrics functionality"""

import pytest

from xagent.xcore.statistics import StatsCollector


class TestStatsCollectorExtraMetrics:
    """StatsCollector 额外指标测试用例"""
    
    @pytest.fixture
    def collector(self):
        """创建 StatsCollector 实例"""
        return StatsCollector()
    
    def test_record_extra_basic(self, collector):
        """测试基本的额外指标记录"""
        collector.record_extra({"triggered": True, "duration": 0.5})
        
        stats = collector.get_stats()
        assert stats["triggered"] == True
        assert stats["duration"] == 0.5
    
    def test_record_extra_multiple_calls_accumulate(self, collector):
        """测试多次记录额外指标会累加"""
        collector.record_extra({"triggered": 1})
        collector.record_extra({"triggered": 1})
        
        stats = collector.get_stats()
        assert stats["triggered"] == 2
    
    def test_record_extra_total_prefix(self, collector):
        """测试 total_ 前缀的累加"""
        collector.record_extra({"total_duration": 0.5})
        collector.record_extra({"total_duration": 0.3})
        
        stats = collector.get_stats()
        assert stats["total_duration"] == 0.8
    
    def test_record_extra_sum_prefix(self, collector):
        """测试 sum_ 前缀的累加"""
        collector.record_extra({"sum_values": 10})
        collector.record_extra({"sum_values": 5})
        
        stats = collector.get_stats()
        assert stats["sum_values"] == 15
    
    def test_record_extra_avg_prefix(self, collector):
        """测试 avg_ 前缀的平均值计算"""
        collector.record_extra({"avg_time": 0.1})
        collector.record_extra({"avg_time": 0.3})
        
        stats = collector.get_stats()
        assert stats["avg_time"] == pytest.approx(0.2)
    
    def test_record_extra_avg_suffix(self, collector):
        """测试 _avg 后缀的平均值计算"""
        collector.record_extra({"duration_avg": 1.0})
        collector.record_extra({"duration_avg": 2.0})
        collector.record_extra({"duration_avg": 3.0})
        
        stats = collector.get_stats()
        assert stats["duration_avg"] == pytest.approx(2.0)
    
    def test_record_extra_mixed_types(self, collector):
        """测试混合类型的指标"""
        collector.record_extra({"count": 1})
        collector.record_extra({"count": 2})
        collector.record_extra({"name": "test"})
        
        stats = collector.get_stats()
        assert stats["count"] == 3
        assert stats["name"] == "test"
    
    def test_record_extra_overwrite_non_numeric(self, collector):
        """测试非数值类型的覆盖"""
        collector.record_extra({"status": "pending"})
        collector.record_extra({"status": "completed"})
        
        stats = collector.get_stats()
        assert stats["status"] == "completed"
    
    def test_record_extra_with_base_stats(self, collector):
        """测试额外指标与基础统计共存"""
        import asyncio
        
        asyncio.run(collector.record(10, True))
        collector.record_extra({"triggered": True})
        
        stats = collector.get_stats()
        assert stats["total_uploaded"] == 10
        assert stats["success_rate"] == 100.0
        assert stats["triggered"] == True
    
    def test_get_stats_excludes_internal_count_keys(self, collector):
        """测试 get_stats 排除内部计数键"""
        collector.record_extra({"avg_time": 0.5})
        
        stats = collector.get_stats()
        assert "avg_time" in stats
        assert "_count_avg_time" not in stats
    
    def test_reset_clears_extra_metrics(self, collector):
        """测试 reset 清空额外指标"""
        collector.record_extra({"triggered": True})
        collector.reset()
        
        stats = collector.get_stats()
        assert "triggered" not in stats
    
    def test_record_extra_none_value(self, collector):
        """测试 None 值的处理"""
        collector.record_extra({"value": None})
        
        stats = collector.get_stats()
        assert stats.get("value") is None
    
    def test_record_extra_complex_scenario(self, collector):
        """测试复杂场景"""
        import asyncio
        
        asyncio.run(collector.record(100, True))
        asyncio.run(collector.record(50, False))
        
        collector.record_extra({
            "total_duration": 1.5,
            "triggered": 5,
            "avg_latency": 0.1
        })
        collector.record_extra({
            "total_duration": 0.5,
            "triggered": 3,
            "avg_latency": 0.2
        })
        
        stats = collector.get_stats()
        assert stats["total_uploaded"] == 150
        assert stats["total_failed"] == 1
        assert stats["total_duration"] == 2.0
        assert stats["triggered"] == 8
        assert stats["avg_latency"] == pytest.approx(0.15)
