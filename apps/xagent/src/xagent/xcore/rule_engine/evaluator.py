"""Rule Evaluator

负责调度规则插件进行规则评估。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import (
    RuleContext,
    RuleEvaluationResult,
    RuleResult,
    AggregationSubscription,
    AggregationType,
    SubscriptionMode,
)
from .plugins import RulePlugin
from .manager import PluginManager

logger = logging.getLogger(__name__)


class RuleEvaluator:
    """规则评估器

    负责调度规则插件进行规则评估。
    支持与聚合引擎集成，在评估时注入聚合数据。

    Attributes:
        plugin_manager: 插件管理器
        aggregation_engine: 聚合引擎（可选）
        _rule_plugins: 规则插件实例字典
        _rule_configs: 规则配置字典
        _subscriptions: 规则关联的聚合订阅字典
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        aggregation_engine: Any = None,
    ):
        """初始化规则评估器

        Args:
            plugin_manager: 插件管理器
            aggregation_engine: 聚合引擎（可选）
        """
        self.plugin_manager = plugin_manager
        self.aggregation_engine = aggregation_engine
        self._rule_plugins: Dict[str, RulePlugin] = {}
        self._rule_configs: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, List[str]] = {}

    def load_rule(self, rule_config: Dict[str, Any]) -> bool:
        """加载规则

        Args:
            rule_config: 规则配置，包含:
                - id: 规则ID
                - name: 规则名称
                - plugin: 插件配置
                    - name: 插件名称
                    - config: 插件配置
                - data_subscriptions: 数据订阅配置列表（可选）

        Returns:
            是否加载成功
        """
        rule_id = rule_config.get("id")
        if not rule_id:
            logger.error("Rule config missing 'id' field")
            return False

        plugin_config = rule_config.get("plugin", {})
        plugin_name = plugin_config.get("name")
        config = plugin_config.get("config", {})

        if not plugin_name:
            logger.error(f"Rule {rule_id} missing plugin name")
            return False

        full_plugin_name = f"rule_engine.rule:{plugin_name}"

        try:
            plugin = self.plugin_manager.get_instance(full_plugin_name, config)

            if not isinstance(plugin, RulePlugin):
                logger.error(f"Plugin {plugin_name} is not a RulePlugin")
                return False

            self._rule_plugins[rule_id] = plugin
            self._rule_configs[rule_id] = rule_config

            self._setup_subscriptions(rule_id, rule_config)

            logger.info(f"Loaded rule: {rule_id} with plugin {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load rule {rule_id}: {e}")
            return False

    def _setup_subscriptions(
        self, rule_id: str, rule_config: Dict[str, Any]
    ) -> None:
        """为规则创建聚合订阅

        Args:
            rule_id: 规则ID
            rule_config: 规则配置
        """
        if not self.aggregation_engine:
            return

        subscription_configs = rule_config.get("data_subscriptions", [])
        sub_ids = []

        for sub_config in subscription_configs:
            try:
                subscription = AggregationSubscription(
                    subscription_id=(
                        f"{rule_id}_{sub_config['asset']}"
                        f"_{sub_config['point']}"
                    ),
                    rule_id=rule_id,
                    asset=sub_config["asset"],
                    point_name=sub_config["point"],
                    mode=SubscriptionMode(
                        sub_config.get("mode", "single")
                    ),
                    window_size=sub_config.get("window_size", 300),
                    window_type=sub_config.get("window_type", "sliding"),
                    aggregation_type=AggregationType(
                        sub_config.get("aggregation", "none")
                    ),
                    min_data_points=sub_config.get("min_data_points", 1),
                    max_data_points=sub_config.get("max_data_points", 10000),
                    data_quality_filter=sub_config.get(
                        "data_quality_filter", "good"
                    ),
                )
                self.aggregation_engine.register(subscription)
                sub_ids.append(subscription.subscription_id)
            except Exception as e:
                logger.error(
                    f"Failed to create subscription for rule {rule_id}: {e}"
                )

        self._subscriptions[rule_id] = sub_ids

    def unload_rule(self, rule_id: str) -> None:
        """卸载规则

        Args:
            rule_id: 规则ID
        """
        self._cleanup_subscriptions(rule_id)

        if rule_id in self._rule_plugins:
            plugin = self._rule_plugins.pop(rule_id)
            if hasattr(plugin, 'shutdown'):
                plugin.shutdown()
            self._rule_configs.pop(rule_id, None)
            logger.info(f"Unloaded rule: {rule_id}")

    def _cleanup_subscriptions(self, rule_id: str) -> None:
        """清理规则关联的聚合订阅

        Args:
            rule_id: 规则ID
        """
        sub_ids = self._subscriptions.pop(rule_id, [])

        if self.aggregation_engine:
            for sub_id in sub_ids:
                try:
                    self.aggregation_engine.unregister(sub_id)
                except Exception as e:
                    logger.error(
                        f"Failed to unregister subscription {sub_id}: {e}"
                    )

    async def evaluate(
        self,
        rule_id: str,
        context: RuleContext,
    ) -> RuleEvaluationResult:
        """评估规则，注入聚合数据

        Args:
            rule_id: 规则ID
            context: 评估上下文

        Returns:
            评估结果
        """
        plugin = self._rule_plugins.get(rule_id)

        if not plugin:
            logger.warning(f"Rule not found: {rule_id}")
            return RuleEvaluationResult(
                result=RuleResult.ERROR,
                triggered=False,
                error=f"Rule not found: {rule_id}"
            )

        await self._inject_aggregation_data(rule_id, context)

        try:
            result = plugin.evaluate(context)
            logger.debug(
                f"Rule {rule_id} evaluated: "
                f"result={result.result.value}, triggered={result.triggered}"
            )
            return result

        except Exception as e:
            logger.error(f"Rule evaluation error for {rule_id}: {e}")
            return RuleEvaluationResult(
                result=RuleResult.ERROR,
                triggered=False,
                error=str(e)
            )

    async def _inject_aggregation_data(
        self, rule_id: str, context: RuleContext
    ) -> None:
        """注入聚合数据到评估上下文

        Args:
            rule_id: 规则ID
            context: 评估上下文
        """
        if not self.aggregation_engine:
            return

        sub_ids = self._subscriptions.get(rule_id, [])
        if not sub_ids:
            return

        if context.aggregation_data is None:
            context.aggregation_data = {}

        tasks = [
            self.aggregation_engine.get_aggregation_result(sub_id)
            for sub_id in sub_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sub_id, agg_result in zip(sub_ids, results):
            if isinstance(agg_result, Exception):
                logger.error(
                    f"Failed to get aggregation result for {sub_id}: "
                    f"{agg_result}"
                )
                continue

            key = f"{agg_result.asset}:{agg_result.point_name}"
            context.aggregation_data[key] = agg_result

            if (
                agg_result.asset == context.asset
                and agg_result.point_name == context.point_name
            ):
                context.window_min = agg_result.min_value
                context.window_max = agg_result.max_value
                context.window_avg = agg_result.avg_value
                context.window_count = agg_result.data_points

                if agg_result.first_value is not None:
                    context.history_values = [
                        agg_result.first_value,
                        agg_result.last_value,
                    ]

    def get_loaded_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取已加载的规则

        Returns:
            规则配置字典
        """
        return self._rule_configs.copy()

    def is_rule_loaded(self, rule_id: str) -> bool:
        """检查规则是否已加载

        Args:
            rule_id: 规则ID

        Returns:
            是否已加载
        """
        return rule_id in self._rule_plugins

    def get_rule_plugin(self, rule_id: str) -> Optional[RulePlugin]:
        """获取规则插件实例

        Args:
            rule_id: 规则ID

        Returns:
            规则插件实例
        """
        return self._rule_plugins.get(rule_id)

    def get_subscriptions(self, rule_id: str) -> List[str]:
        """获取规则关联的订阅ID列表

        Args:
            rule_id: 规则ID

        Returns:
            订阅ID列表
        """
        return self._subscriptions.get(rule_id, []).copy()

    def shutdown(self) -> None:
        """关闭评估器"""
        for rule_id in list(self._rule_plugins.keys()):
            self.unload_rule(rule_id)

        logger.info("Rule evaluator shutdown complete")
