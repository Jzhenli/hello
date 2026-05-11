"""Rule Engine Package

插件化规则引擎实现，支持规则评估、通知交付和数据过滤。
通过 RuleEngineOrchestrator 编排器与系统 EventBus 集成，
实现数据事件到规则评估的自动流转。
"""

from .base import (
    PluginMetadata,
    PluginDependency,
    PluginRegistration,
    RuleResult,
    RuleContext,
    RuleEvaluationResult,
    DeliveryStatus,
    Notification,
    DeliveryResult,
    ReadingSet,
    AggregationType,
    SubscriptionMode,
    AggregationSubscription,
    AggregationResult,
)

from .plugins import (
    RulePlugin,
    DeliveryPlugin,
    RuleFilterPlugin,
)

from .manager import PluginManager
from .evaluator import RuleEvaluator
from .pipeline import (
    FilterPipeline,
    PipelineConfig,
    PipelineLocation,
    PipelineMetrics,
    FilterPipelineExecutor,
    PipelineManager,
)
from .router import DeliveryRouter
from .aggregation import DataWindow, AggregationEngine
from .orchestrator import RuleEngineOrchestrator

__all__ = [
    "PluginMetadata",
    "PluginDependency",
    "PluginRegistration",
    "RuleResult",
    "RuleContext",
    "RuleEvaluationResult",
    "DeliveryStatus",
    "Notification",
    "DeliveryResult",
    "ReadingSet",
    "AggregationType",
    "SubscriptionMode",
    "AggregationSubscription",
    "AggregationResult",
    "RulePlugin",
    "DeliveryPlugin",
    "RuleFilterPlugin",
    "PluginManager",
    "RuleEvaluator",
    "FilterPipeline",
    "PipelineConfig",
    "PipelineLocation",
    "PipelineMetrics",
    "FilterPipelineExecutor",
    "PipelineManager",
    "DeliveryRouter",
    "DataWindow",
    "AggregationEngine",
    "RuleEngineOrchestrator",
]
