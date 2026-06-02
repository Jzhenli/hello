"""Tests for FilterPipeline statistics interception"""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Any, Dict

from xagent.xcore.statistics import StatisticsManager, StatsRecorder
from xagent.xcore.rule_engine.pipeline import (
    FilterPipelineExecutor,
    PipelineManager,
    PipelineConfig,
    PipelineMetrics,
    PipelineLocation,
)
from xagent.xcore.rule_engine.plugins import RuleFilterPlugin
from xagent.xcore.rule_engine.base import ReadingSet


class MockFilterPlugin(RuleFilterPlugin):
    """Mock 过滤器插件用于测试"""
    
    __plugin_name__ = "mock_filter"
    __plugin_type__ = "filter.mock"
    
    def __init__(self, filter_ratio: float = 0.5, should_fail: bool = False):
        super().__init__()
        self.filter_ratio = filter_ratio
        self.should_fail = should_fail
        self.call_count = 0
        self._plugin_info = Mock()
    
    @property
    def plugin_info(self):
        return self._plugin_info
    
    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        return True
    
    def filter(self, data: ReadingSet) -> ReadingSet:
        self.call_count += 1
        
        if self.should_fail:
            raise RuntimeError("Mock filter error")
        
        total_points = len(data.points)
        keep_count = int(total_points * (1 - self.filter_ratio))
        
        filtered_points = {}
        for i, (key, value) in enumerate(data.points.items()):
            if i < keep_count:
                filtered_points[key] = value
        
        return ReadingSet(
            asset=data.asset,
            timestamp=data.timestamp,
            points=filtered_points,
            quality=data.quality,
            metadata=data.metadata
        )


class MockPluginManager:
    """Mock 插件管理器"""
    
    def __init__(self, plugins: List[RuleFilterPlugin] = None):
        self._plugins = plugins or []
    
    def get_filter_plugins(self):
        return self._plugins


class TestFilterPipelineStatsInterception:
    """FilterPipeline 统计拦截测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def stats_recorder(self, stats_manager):
        """创建 StatsRecorder 实例"""
        return StatsRecorder(stats_manager)
    
    @pytest.fixture
    def pipeline_config(self):
        """创建管道配置"""
        return PipelineConfig(
            pipeline_id="test_pipeline",
            filters=[{"name": "mock_filter"}],
            enable_metrics=True
        )
    
    @pytest.fixture
    def reading_set(self):
        """创建测试数据集"""
        points = {f"point_{i}": i for i in range(10)}
        return ReadingSet(
            asset="device_001",
            timestamp=1000.0,
            points=points,
            quality={f"point_{i}": "good" for i in range(10)}
        )
    
    @pytest.mark.asyncio
    async def test_filter_with_stats_records_success(self, stats_recorder, stats_manager, pipeline_config, reading_set):
        """测试成功过滤记录统计"""
        mock_plugin = MockFilterPlugin(filter_ratio=0.3)
        plugin_manager = MockPluginManager([mock_plugin])
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=pipeline_config,
            stats_recorder=stats_recorder
        )
        executor._filters = [mock_plugin]
        executor._filter_names = ["mock_filter"]
        
        result = await executor.execute(reading_set)
        
        assert len(result.points) == 7
        
        await asyncio.sleep(0.1)
        
        stats = stats_manager.get_operation_stats("filter", "mock_filter")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_filter_records_input_output_count(self, stats_recorder, stats_manager, pipeline_config, reading_set):
        """测试过滤记录输入输出数量"""
        mock_plugin = MockFilterPlugin(filter_ratio=0.4)
        plugin_manager = MockPluginManager([mock_plugin])
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=pipeline_config,
            stats_recorder=stats_recorder
        )
        executor._filters = [mock_plugin]
        executor._filter_names = ["mock_filter"]
        
        result = await executor.execute(reading_set)
        
        await asyncio.sleep(0.1)
        
        stats = stats_manager.get_operation_stats("filter", "mock_filter")
        assert stats is not None
        assert stats["input_count"] == 10
        assert stats["output_count"] == 6
        assert stats["filtered_count"] == 4
        assert stats["filter_rate"] == pytest.approx(0.4)
    
    @pytest.mark.asyncio
    async def test_filter_with_stats_records_failure(self, stats_recorder, stats_manager, reading_set):
        """测试失败过滤记录统计"""
        mock_plugin = MockFilterPlugin(should_fail=True)
        plugin_manager = MockPluginManager([mock_plugin])
        
        config = PipelineConfig(
            pipeline_id="failing_pipeline",
            filters=[{"name": "mock_filter"}],
            enable_metrics=True,
            continue_on_error=False
        )
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=config,
            stats_recorder=stats_recorder
        )
        executor._filters = [mock_plugin]
        executor._filter_names = ["mock_filter"]
        
        with pytest.raises(RuntimeError):
            await executor.execute(reading_set)
        
        await asyncio.sleep(0.1)
        
        stats = stats_manager.get_operation_stats("filter", "mock_filter")
        assert stats is not None
        assert stats["total_failed"] == 1
    
    @pytest.mark.asyncio
    async def test_filter_without_stats_recorder(self, pipeline_config, reading_set):
        """测试无 StatsRecorder 时的过滤"""
        mock_plugin = MockFilterPlugin(filter_ratio=0.5)
        plugin_manager = MockPluginManager([mock_plugin])
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=pipeline_config,
            stats_recorder=None
        )
        executor._filters = [mock_plugin]
        executor._filter_names = ["mock_filter"]
        
        result = await executor.execute(reading_set)
        
        assert len(result.points) == 5
        assert mock_plugin.call_count == 1
    
    @pytest.mark.asyncio
    async def test_filter_records_duration(self, stats_recorder, stats_manager, pipeline_config, reading_set):
        """测试过滤耗时记录"""
        mock_plugin = MockFilterPlugin(filter_ratio=0.2)
        plugin_manager = MockPluginManager([mock_plugin])
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=pipeline_config,
            stats_recorder=stats_recorder
        )
        executor._filters = [mock_plugin]
        executor._filter_names = ["mock_filter"]
        
        await executor.execute(reading_set)
        
        await asyncio.sleep(0.1)
        
        stats = stats_manager.get_operation_stats("filter", "mock_filter")
        assert stats is not None
        assert stats["total_uploaded"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_set_stats_recorder(self, pipeline_config):
        """测试动态设置 StatsRecorder"""
        mock_plugin = MockFilterPlugin()
        plugin_manager = MockPluginManager([mock_plugin])
        stats_manager = StatisticsManager(storage=None, config={'enabled': True})
        stats_recorder = StatsRecorder(stats_manager)
        
        executor = FilterPipelineExecutor(
            plugin_manager=plugin_manager,
            config=pipeline_config,
            stats_recorder=None
        )
        
        executor.set_stats_recorder(stats_recorder)
        
        assert executor._stats_recorder is stats_recorder


class TestPipelineManagerStatsInterception:
    """PipelineManager 统计拦截测试用例"""
    
    @pytest.fixture
    def stats_manager(self):
        """创建 StatisticsManager 实例"""
        return StatisticsManager(storage=None, config={'enabled': True})
    
    @pytest.fixture
    def stats_recorder(self, stats_manager):
        """创建 StatsRecorder 实例"""
        return StatsRecorder(stats_manager)
    
    @pytest.fixture
    def plugin_manager(self):
        """创建插件管理器"""
        return MockPluginManager([])
    
    def test_create_pipeline_with_stats_recorder(self, plugin_manager, stats_recorder):
        """测试创建带 StatsRecorder 的管道"""
        manager = PipelineManager(
            plugin_manager=plugin_manager,
            stats_recorder=stats_recorder
        )
        
        config = PipelineConfig(
            pipeline_id="test_pipeline",
            filters=[]
        )
        
        executor = manager.create_pipeline(config)
        
        assert executor._stats_recorder is stats_recorder
    
    def test_set_stats_recorder_propagates_to_pipelines(self, plugin_manager, stats_recorder):
        """测试设置 StatsRecorder 传播到已创建的管道"""
        manager = PipelineManager(plugin_manager=plugin_manager)
        
        config = PipelineConfig(
            pipeline_id="test_pipeline",
            filters=[]
        )
        
        executor = manager.create_pipeline(config)
        assert executor._stats_recorder is None
        
        manager.set_stats_recorder(stats_recorder)
        
        assert executor._stats_recorder is stats_recorder
    
    def test_set_stats_recorder_before_create(self, plugin_manager, stats_recorder):
        """测试在创建管道前设置 StatsRecorder"""
        manager = PipelineManager(plugin_manager=plugin_manager)
        manager.set_stats_recorder(stats_recorder)
        
        config = PipelineConfig(
            pipeline_id="test_pipeline",
            filters=[]
        )
        
        executor = manager.create_pipeline(config)
        
        assert executor._stats_recorder is stats_recorder
