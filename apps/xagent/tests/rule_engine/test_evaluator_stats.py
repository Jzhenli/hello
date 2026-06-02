"""Tests for RuleEvaluator statistics interception"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

from xagent.xcore.statistics import StatisticsManager, StatsRecorder
from xagent.xcore.rule_engine.evaluator import RuleEvaluator
from xagent.xcore.rule_engine.plugins import RulePlugin
from xagent.xcore.rule_engine.base import (
    RuleContext,
    RuleEvaluationResult,
    RuleResult,
)


class MockRulePlugin(RulePlugin):
    """Mock 规则插件用于测试"""
    
    __plugin_name__ = "mock_rule"
    __plugin_type__ = "rule.mock"
    
    def __init__(self, should_trigger: bool = True, should_fail: bool = False):
        super().__init__()
        self.should_trigger = should_trigger
        self.should_fail = should_fail
        self.call_count = 0
        self._plugin_info = Mock()
    
    @property
    def plugin_info(self):
        return self._plugin_info
    
    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        return True
    
    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        self.call_count += 1
        
        if self.should_fail:
            raise RuntimeError("Mock evaluation error")
        
        return RuleEvaluationResult(
            result=RuleResult.TRIGGERED if self.should_trigger else RuleResult.NOT_TRIGGERED,
            triggered=self.should_trigger
        )


class MockPluginManager:
    """Mock 插件管理器"""
    
    def get_plugin(self, plugin_type: str, name: str):
        return None


class TestRuleEvaluatorStatsInterception:
    """RuleEvaluator 统计拦截测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def stats_recorder(self, stats_manager):
        """创建 StatsRecorder 实例"""
        return StatsRecorder(stats_manager)
    
    @pytest.fixture
    def evaluator(self, stats_recorder):
        """创建带 StatsRecorder 的 RuleEvaluator 实例"""
        evaluator = RuleEvaluator(
            plugin_manager=MockPluginManager(),
            stats_recorder=stats_recorder
        )
        return evaluator
    
    @pytest.fixture
    def evaluator_no_stats(self):
        """创建不带 StatsRecorder 的 RuleEvaluator 实例"""
        return RuleEvaluator(plugin_manager=MockPluginManager())
    
    @pytest.fixture
    def rule_context(self):
        """创建规则上下文"""
        return RuleContext(
            rule_id="test_rule",
            rule_name="Test Rule",
            asset="device_001"
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_with_stats_records_success(self, evaluator, stats_manager, rule_context):
        """测试成功评估记录统计"""
        mock_plugin = MockRulePlugin(should_trigger=True)
        evaluator._rule_plugins["test_rule"] = mock_plugin
        
        result = await evaluator.evaluate("test_rule", rule_context)
        
        assert result.triggered == True
        
        stats = stats_manager.get_operation_stats("rule", "mock_rule")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
        assert stats["triggered"] == True
    
    @pytest.mark.asyncio
    async def test_evaluate_with_stats_records_failure(self, evaluator, stats_manager, rule_context):
        """测试失败评估记录统计"""
        mock_plugin = MockRulePlugin(should_fail=True)
        evaluator._rule_plugins["failing_rule"] = mock_plugin
        
        with pytest.raises(RuntimeError):
            await evaluator.evaluate("failing_rule", rule_context)
        
        stats = stats_manager.get_operation_stats("rule", "mock_rule")
        assert stats is not None
        assert stats["total_failed"] == 1
    
    @pytest.mark.asyncio
    async def test_evaluate_with_stats_not_triggered(self, evaluator, stats_manager, rule_context):
        """测试未触发的评估记录统计"""
        mock_plugin = MockRulePlugin(should_trigger=False)
        evaluator._rule_plugins["not_triggered_rule"] = mock_plugin
        
        result = await evaluator.evaluate("not_triggered_rule", rule_context)
        
        assert result.triggered == False
        
        stats = stats_manager.get_operation_stats("rule", "mock_rule")
        assert stats is not None
        assert stats["triggered"] == False
    
    @pytest.mark.asyncio
    async def test_evaluate_without_stats_recorder(self, evaluator_no_stats, rule_context):
        """测试无 StatsRecorder 时的评估"""
        mock_plugin = MockRulePlugin(should_trigger=True)
        evaluator_no_stats._rule_plugins["test_rule"] = mock_plugin
        
        result = await evaluator_no_stats.evaluate("test_rule", rule_context)
        
        assert result.triggered == True
        assert mock_plugin.call_count == 1
    
    @pytest.mark.asyncio
    async def test_evaluate_rule_not_found(self, evaluator):
        """测试规则不存在的情况"""
        context = RuleContext(rule_id="nonexistent", rule_name="Nonexistent")
        
        result = await evaluator.evaluate("nonexistent_rule", context)
        
        assert result.result == RuleResult.ERROR
        assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_set_stats_recorder(self, evaluator_no_stats, stats_recorder):
        """测试动态设置 StatsRecorder"""
        evaluator_no_stats.set_stats_recorder(stats_recorder)
        
        assert evaluator_no_stats._stats_recorder is stats_recorder
    
    @pytest.mark.asyncio
    async def test_evaluate_records_duration(self, evaluator, stats_manager, rule_context):
        """测试评估耗时记录"""
        mock_plugin = MockRulePlugin(should_trigger=True)
        evaluator._rule_plugins["duration_rule"] = mock_plugin
        
        await evaluator.evaluate("duration_rule", rule_context)
        
        stats = stats_manager.get_operation_stats("rule", "mock_rule")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_multiple_evaluations_accumulate(self, evaluator, stats_manager, rule_context):
        """测试多次评估累加统计"""
        mock_plugin = MockRulePlugin(should_trigger=True)
        evaluator._rule_plugins["multi_rule"] = mock_plugin
        
        for _ in range(5):
            await evaluator.evaluate("multi_rule", rule_context)
        
        stats = stats_manager.get_operation_stats("rule", "mock_rule")
        assert stats is not None
        assert stats["total_uploaded"] == 5
        assert stats["triggered"] == 5
