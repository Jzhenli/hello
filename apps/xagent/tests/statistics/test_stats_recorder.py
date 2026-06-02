"""Tests for StatisticsManager.record_operation() and StatsRecorder"""

import asyncio
import pytest

from xagent.xcore.statistics import StatisticsManager, StatsCollector, StatsRecorder


class TestStatisticsManagerRecordOperation:
    """StatisticsManager.record_operation() 测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def disabled_manager(self):
        """创建禁用的 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': False})
    
    @pytest.mark.asyncio
    async def test_record_operation_basic(self, stats_manager):
        """测试基本的操作记录"""
        await stats_manager.record_operation(
            category="rule",
            name="threshold_rule",
            success=True
        )
        
        stats = stats_manager.get_operation_stats("rule", "threshold_rule")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_record_operation_with_duration(self, stats_manager):
        """测试带耗时的操作记录"""
        await stats_manager.record_operation(
            category="delivery",
            name="webhook",
            success=True,
            duration=0.5
        )
        
        stats = stats_manager.get_operation_stats("delivery", "webhook")
        assert stats is not None
        assert stats["total_duration"] == 0.5
        assert stats["avg_duration"] == 0.5
        assert stats["call_count"] == 1
    
    @pytest.mark.asyncio
    async def test_record_operation_with_extra_metrics(self, stats_manager):
        """测试带额外指标的操作记录"""
        await stats_manager.record_operation(
            category="rule",
            name="expression_rule",
            success=True,
            triggered=True,
            result_type="triggered"
        )
        
        stats = stats_manager.get_operation_stats("rule", "expression_rule")
        assert stats is not None
        assert stats["triggered"] == True
        assert stats["result_type"] == "triggered"
    
    @pytest.mark.asyncio
    async def test_record_operation_failure(self, stats_manager):
        """测试失败的操作记录"""
        await stats_manager.record_operation(
            category="delivery",
            name="email",
            success=False
        )
        
        stats = stats_manager.get_operation_stats("delivery", "email")
        assert stats is not None
        assert stats["total_failed"] == 1
        assert stats["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_record_operation_disabled(self, disabled_manager):
        """测试禁用状态下的操作记录"""
        await disabled_manager.record_operation(
            category="rule",
            name="threshold_rule",
            success=True
        )
        
        stats = disabled_manager.get_operation_stats("rule", "threshold_rule")
        assert stats is None
    
    @pytest.mark.asyncio
    async def test_record_operation_multiple_calls(self, stats_manager):
        """测试多次调用累加"""
        success_count = 0
        for i in range(10):
            success = i % 3 != 0
            if success:
                success_count += 1
            await stats_manager.record_operation(
                category="filter",
                name="dedup",
                success=success
            )
        
        stats = stats_manager.get_operation_stats("filter", "dedup")
        assert stats is not None
        assert stats["total_uploaded"] == 10
        expected_rate = (success_count / 10) * 100
        assert stats["success_rate"] == pytest.approx(expected_rate, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_get_operation_stats_not_found(self, stats_manager):
        """测试获取不存在的操作统计"""
        stats = stats_manager.get_operation_stats("unknown", "unknown")
        assert stats is None
    
    @pytest.mark.asyncio
    async def test_get_all_plugin_stats(self, stats_manager):
        """测试获取所有插件统计"""
        await stats_manager.record_operation("rule", "threshold_rule", True)
        await stats_manager.record_operation("rule", "expression_rule", True)
        await stats_manager.record_operation("delivery", "webhook", True)
        await stats_manager.record_operation("filter", "dedup", True)
        
        all_stats = stats_manager.get_all_plugin_stats()
        
        assert "rule:threshold_rule" in all_stats
        assert "rule:expression_rule" in all_stats
        assert "delivery:webhook" in all_stats
        assert "filter:dedup" in all_stats
    
    @pytest.mark.asyncio
    async def test_get_all_plugin_stats_excludes_non_plugin(self, stats_manager):
        """测试 get_all_plugin_stats 排除非插件统计"""
        await stats_manager.record_operation("rule", "test_rule", True)
        await stats_manager.record_data_collection("device_001", 10)
        
        all_stats = stats_manager.get_all_plugin_stats()
        
        assert "rule:test_rule" in all_stats
        assert "device:device_001" not in all_stats
    
    @pytest.mark.asyncio
    async def test_record_operation_duration_accumulation(self, stats_manager):
        """测试耗时累加"""
        await stats_manager.record_operation("rule", "test", True, duration=0.1)
        await stats_manager.record_operation("rule", "test", True, duration=0.2)
        await stats_manager.record_operation("rule", "test", True, duration=0.3)
        
        stats = stats_manager.get_operation_stats("rule", "test")
        assert stats is not None
        assert stats["total_duration"] == pytest.approx(0.6)
        assert stats["call_count"] == 3
        assert stats["avg_duration"] == pytest.approx(0.2)


class TestStatsRecorder:
    """StatsRecorder 测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def recorder(self, stats_manager):
        """创建 StatsRecorder 实例"""
        return StatsRecorder(stats_manager)
    
    @pytest.fixture
    def recorder_no_manager(self):
        """创建无 StatisticsManager 的 StatsRecorder 实例"""
        return StatsRecorder(None)
    
    @pytest.mark.asyncio
    async def test_record_async_basic(self, recorder, stats_manager):
        """测试异步操作记录"""
        async def sample_operation():
            return "result"
        
        result = await recorder.record_async(
            category="rule",
            name="test_rule",
            coro=sample_operation()
        )
        
        assert result == "result"
        
        stats = stats_manager.get_operation_stats("rule", "test_rule")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_record_async_with_exception(self, recorder, stats_manager):
        """测试异步操作异常记录"""
        async def failing_operation():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            await recorder.record_async(
                category="rule",
                name="failing_rule",
                coro=failing_operation()
            )
        
        stats = stats_manager.get_operation_stats("rule", "failing_rule")
        assert stats is not None
        assert stats["total_failed"] == 1
    
    @pytest.mark.asyncio
    async def test_record_async_with_extra(self, recorder, stats_manager):
        """测试带额外指标的异步操作记录"""
        async def operation():
            return {"status": "ok"}
        
        result = await recorder.record_async(
            category="delivery",
            name="webhook",
            coro=operation(),
            channel_id="ch_001"
        )
        
        stats = stats_manager.get_operation_stats("delivery", "webhook")
        assert stats is not None
        assert stats["channel_id"] == "ch_001"
    
    @pytest.mark.asyncio
    async def test_record_async_no_manager(self, recorder_no_manager):
        """测试无 StatisticsManager 时的异步操作"""
        async def operation():
            return "result"
        
        result = await recorder_no_manager.record_async(
            category="rule",
            name="test",
            coro=operation()
        )
        
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_record_sync_basic(self, recorder, stats_manager):
        """测试同步操作记录"""
        def sample_operation():
            return 42
        
        result = recorder.record_sync(
            category="filter",
            name="test_filter",
            func=sample_operation
        )
        
        assert result == 42
        
        await asyncio.sleep(0.1)
        
        stats = stats_manager.get_operation_stats("filter", "test_filter")
        assert stats is not None
    
    @pytest.mark.asyncio
    async def test_record_sync_with_exception(self, recorder, stats_manager):
        """测试同步操作异常记录"""
        def failing_operation():
            raise RuntimeError("sync error")
        
        with pytest.raises(RuntimeError):
            recorder.record_sync(
                category="filter",
                name="failing_filter",
                func=failing_operation
            )
    
    @pytest.mark.asyncio
    async def test_record_sync_no_manager(self, recorder_no_manager):
        """测试无 StatisticsManager 时的同步操作"""
        def operation():
            return "sync_result"
        
        result = recorder_no_manager.record_sync(
            category="filter",
            name="test",
            func=operation
        )
        
        assert result == "sync_result"
    
    @pytest.mark.asyncio
    async def test_record_async_with_result_extractor(self, recorder, stats_manager):
        """测试带结果提取器的异步操作"""
        async def operation():
            return {"triggered": True, "value": 100}
        
        def extract_metrics(result):
            return {
                "triggered": result["triggered"],
                "value": result["value"]
            }
        
        result = await recorder.record_async_with_result(
            category="rule",
            name="threshold",
            coro=operation(),
            result_extractor=extract_metrics
        )
        
        assert result == {"triggered": True, "value": 100}
        
        stats = stats_manager.get_operation_stats("rule", "threshold")
        assert stats is not None
        assert stats["triggered"] == True
        assert stats["value"] == 100
    
    def test_set_stats_manager(self, recorder_no_manager, stats_manager):
        """测试动态设置 StatisticsManager"""
        recorder_no_manager.set_stats_manager(stats_manager)
        
        assert recorder_no_manager.stats_manager is stats_manager
    
    @pytest.mark.asyncio
    async def test_stats_manager_property(self, recorder, stats_manager):
        """测试 stats_manager 属性"""
        assert recorder.stats_manager is stats_manager
    
    @pytest.mark.asyncio
    async def test_record_async_coroutine_function(self, recorder, stats_manager):
        """测试传入协程函数"""
        async def operation():
            return "coroutine_result"
        
        result = await recorder.record_async(
            category="rule",
            name="test",
            coro=operation
        )
        
        assert result == "coroutine_result"
    
    @pytest.mark.asyncio
    async def test_record_async_callable(self, recorder, stats_manager):
        """测试传入可调用对象"""
        class CallableOp:
            def __call__(self):
                return "callable_result"
        
        result = await recorder.record_async(
            category="rule",
            name="test",
            coro=CallableOp()
        )
        
        assert result == "callable_result"
