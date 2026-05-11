"""Rule Engine Orchestrator

编排规则引擎各子组件，实现数据事件到规则评估的自动流转。
实现 ILifecycle 接口，与系统框架统一设计。

数据流:
  DATA_RECEIVED -> FilterPipeline -> AggregationEngine -> RuleEvaluator -> DeliveryRouter
                                                                             |
                                                                    RULE_TRIGGERED event
"""

import asyncio
import copy
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import (
    ReadingSet,
    RuleContext,
    Notification,
)
from .manager import PluginManager
from .evaluator import RuleEvaluator
from .pipeline import PipelineManager, PipelineConfig
from .router import DeliveryRouter
from .aggregation import AggregationEngine
from ._core_compat import HAS_CORE, EventType, Event, ILifecycleBase, is_reading, reading_to_reading_set

if TYPE_CHECKING:
    from .persistence import RulePersistenceManager

logger = logging.getLogger(__name__)


class RuleEngineOrchestrator(ILifecycleBase):
    """规则引擎编排器

    编排 FilterPipeline、AggregationEngine、RuleEvaluator、DeliveryRouter
    四大子组件，通过 EventBus 实现数据事件到规则评估的自动流转。
    实现 ILifecycle 接口，可由系统框架统一管理启动/停止。

    事件流转:
        1. 订阅 DATA_RECEIVED 事件
        2. 数据经 FilterPipeline 过滤
        3. 过滤后数据送入 AggregationEngine 更新窗口
        4. 对每条关联规则执行 RuleEvaluator.evaluate()
        5. 触发的规则生成 Notification 并交付
        6. 发布 RULE_TRIGGERED / RULE_EVALUATED 事件

    Attributes:
        plugin_manager: 插件管理器
        event_bus: 事件总线
        evaluator: 规则评估器
        router: 交付路由器
        pipeline_manager: 管道管理器
        aggregation_engine: 聚合引擎
        persistence_manager: 持久化管理器
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        plugin_dirs: Optional[List[str]] = None,
        persistence_manager: Optional["RulePersistenceManager"] = None,
    ):
        """初始化规则引擎编排器

        Args:
            event_bus: 事件总线实例，为 None 时内部创建
            plugin_dirs: 插件目录列表
            persistence_manager: 持久化管理器实例
        """
        self.plugin_manager = PluginManager(plugin_dirs=plugin_dirs)
        self._event_bus = event_bus
        self.aggregation_engine = AggregationEngine()
        self.evaluator = RuleEvaluator(
            plugin_manager=self.plugin_manager,
            aggregation_engine=self.aggregation_engine,
        )
        self.router = DeliveryRouter(self.plugin_manager)
        self.pipeline_manager = PipelineManager(self.plugin_manager)
        self._persistence_manager = persistence_manager

        self._running: bool = False
        self._rule_pipeline_map: Dict[str, str] = {}
        self._rule_channel_map: Dict[str, List[str]] = {}
        self._rule_configs: Dict[str, Dict[str, Any]] = {}

    @property
    def event_bus(self) -> Optional[Any]:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: Optional[Any]) -> None:
        self._event_bus = value

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动规则引擎编排器"""
        if self._running:
            return

        self._running = True

        if self._event_bus and HAS_CORE:
            self._event_bus.subscribe(
                EventType.DATA_RECEIVED, self._on_data_received
            )
            logger.info("RuleEngine subscribed to DATA_RECEIVED events")

        await self._restore_from_persistence()

        logger.info("Rule Engine Orchestrator started")

    async def _restore_from_persistence(self) -> None:
        """从持久化存储恢复规则、渠道、管道"""
        if not self._persistence_manager:
            logger.debug("No persistence manager, skip restoration")
            return

        try:
            channels = await self._persistence_manager.load_all_channels()
            for channel_id, channel in channels.items():
                self.router.register_channel(
                    channel_id, channel.plugin_name, channel.config
                )
            logger.info(f"Restored {len(channels)} channels from persistence")

            pipelines = await self._persistence_manager.load_all_pipelines()
            for pipeline_id, pipeline in pipelines.items():
                try:
                    config = PipelineConfig(
                        pipeline_id=pipeline_id,
                        filters=pipeline.filters,
                        continue_on_error=pipeline.config.get("continue_on_error", False),
                        log_errors=pipeline.config.get("log_errors", True),
                        max_retries=pipeline.config.get("max_retries", 0),
                        retry_delay=pipeline.config.get("retry_delay", 1.0),
                        retry_backoff=pipeline.config.get("retry_backoff", 2.0),
                        timeout_per_filter=pipeline.config.get("timeout_per_filter", 30.0),
                        location=self._parse_pipeline_location(pipeline.config.get("location", "south")),
                        service_name=pipeline.config.get("service_name", ""),
                        error_callback_plugin=pipeline.config.get("error_callback_plugin"),
                        error_callback_config=pipeline.config.get("error_callback_config"),
                        enable_metrics=pipeline.config.get("enable_metrics", True),
                    )
                    self.pipeline_manager.create_pipeline(config)
                except Exception as e:
                    logger.error(f"Failed to restore pipeline {pipeline_id}: {e}")
            logger.info(f"Restored {len(pipelines)} pipelines from persistence")

            rules = await self._persistence_manager.load_all_rules()
            for rule_id, rule in rules.items():
                rule_config = {
                    "id": rule.id,
                    "name": rule.name,
                    "description": rule.description,
                    "enabled": rule.enabled,
                    "plugin": rule.plugin_config,
                    "data_subscriptions": rule.data_subscriptions,
                    "notification": rule.notification_config,
                }
                self.evaluator.load_rule(rule_config)
                self._rule_configs[rule_id] = rule_config
                if rule.pipeline_id:
                    self._rule_pipeline_map[rule_id] = rule.pipeline_id
                if rule.channel_ids:
                    self._rule_channel_map[rule_id] = rule.channel_ids
            logger.info(f"Restored {len(rules)} rules from persistence")

        except Exception as e:
            logger.error(f"Failed to restore from persistence: {e}")

    def _parse_pipeline_location(self, location: str):
        """解析管道位置"""
        from .pipeline import PipelineLocation
        if location == "north":
            return PipelineLocation.NORTH
        return PipelineLocation.SOUTH

    async def stop(self) -> None:
        """停止规则引擎编排器"""
        if not self._running:
            return

        self._running = False

        if self._event_bus and HAS_CORE:
            self._event_bus.unsubscribe(
                EventType.DATA_RECEIVED, self._on_data_received
            )

        self.evaluator.shutdown()
        await self.router.shutdown()
        self.pipeline_manager.shutdown()
        self.aggregation_engine.clear()
        self.plugin_manager.shutdown()

        logger.info("Rule Engine Orchestrator stopped")

    async def _on_data_received(self, event: Any) -> None:
        """处理 DATA_RECEIVED 事件

        事件数据格式:
            {
                "asset": "device_001",
                "points": {"temperature": 25.5, "humidity": 60},
                "timestamp": 1700000000.0,
                "quality": {"temperature": "good"}
            }

        或 ReadingSet 对象。

        Args:
            event: Event 对象
        """
        if not self._running:
            return

        try:
            data = event.data if hasattr(event, 'data') else event
            reading = self._to_reading_set(data)
            if not reading:
                return

            await self._process_reading(reading)

        except Exception as e:
            logger.error(f"Error processing data event: {e}", exc_info=True)

    def _to_reading_set(self, data: Any) -> Optional[ReadingSet]:
        if isinstance(data, ReadingSet):
            return data

        result = reading_to_reading_set(data)
        if result is not None:
            return result

        if isinstance(data, dict):
            return ReadingSet(
                asset=data.get("asset", ""),
                timestamp=data.get("timestamp", time.time()),
                points=data.get("points", {}),
                quality=data.get("quality"),
                metadata=data.get("metadata"),
            )

        logger.warning(f"Unsupported data type: {type(data)}")
        return None

    async def _process_reading(self, reading: ReadingSet) -> None:
        """处理单条数据：过滤 -> 聚合 -> 规则评估 -> 通知

        Args:
            reading: 数据集
        """
        filtered = await self._apply_filters(reading)
        if not filtered or not filtered.points:
            return

        self._update_aggregation(filtered)

        await self._evaluate_rules(filtered)

    async def _apply_filters(self, reading: ReadingSet) -> Optional[ReadingSet]:
        """对数据应用过滤器管道

        Args:
            reading: 原始数据

        Returns:
            过滤后的数据，如果所有管道都无过滤则返回原始数据
        """
        if not self.pipeline_manager.pipeline_ids:
            return reading

        result = reading
        for pipeline_id in self.pipeline_manager.pipeline_ids:
            try:
                result = await self.pipeline_manager.execute(pipeline_id, result)
            except Exception as e:
                logger.error(f"Pipeline {pipeline_id} error: {e}")

        return result

    def _update_aggregation(self, reading: ReadingSet) -> None:
        """更新聚合引擎的数据窗口

        Args:
            reading: 过滤后的数据
        """
        timestamp = reading.timestamp
        for point_name, value in reading.points.items():
            self.aggregation_engine.on_data(
                asset=reading.asset,
                point_name=point_name,
                value=value,
                timestamp=timestamp,
            )

    async def _evaluate_rules(self, reading: ReadingSet) -> None:
        """对数据评估所有关联规则

        使用 asyncio.gather 并行评估所有规则，
        单条规则评估失败不影响其他规则。

        Args:
            reading: 过滤后的数据
        """
        loaded_rules = self.evaluator.get_loaded_rules()

        tasks = []
        for rule_id, rule_config in loaded_rules.items():
            tasks.append(
                self._evaluate_rule_for_reading(rule_id, rule_config, reading)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                rule_ids = list(loaded_rules.keys())
                rule_id = rule_ids[i] if i < len(rule_ids) else "unknown"
                logger.error(f"Error evaluating rule {rule_id}: {result}")

    async def _evaluate_rule_for_reading(
        self,
        rule_id: str,
        rule_config: Dict[str, Any],
        reading: ReadingSet,
    ) -> None:
        """对单条数据评估单条规则

        Args:
            rule_id: 规则ID
            rule_config: 规则配置
            reading: 数据集
        """
        data_subs = rule_config.get("data_subscriptions", [])
        if data_subs:
            matched_points = {
                sub.get("point") for sub in data_subs
                if sub.get("asset") == reading.asset
                and sub.get("point") in reading.points
            }
            if not matched_points:
                return
            points_to_evaluate = {
                k: v for k, v in reading.points.items()
                if k in matched_points
            }
        else:
            points_to_evaluate = reading.points

        for point_name, value in points_to_evaluate.items():
            context = RuleContext(
                rule_id=rule_id,
                rule_name=rule_config.get("name", rule_id),
                asset=reading.asset,
                point_name=point_name,
                current_value=value,
                timestamp=reading.timestamp,
                metadata=reading.metadata,
            )

            result = await self.evaluator.evaluate(rule_id, context)

            await self._publish_evaluation_event(rule_id, result)

            if result.triggered:
                await self._handle_triggered_rule(
                    rule_id, rule_config, context, result
                )

    async def _publish_evaluation_event(
        self, rule_id: str, result: Any
    ) -> None:
        """发布规则评估事件

        Args:
            rule_id: 规则ID
            result: 评估结果
        """
        if not self._event_bus or not HAS_CORE:
            return

        try:
            event = Event(
                event_type=EventType.RULE_EVALUATED,
                data={
                    "rule_id": rule_id,
                    "triggered": result.triggered,
                    "result": result.result.value,
                    "reason": result.reason,
                },
            )
            await self._event_bus.publish(event)
        except Exception as e:
            logger.debug(f"Failed to publish evaluation event: {e}")

    async def _handle_triggered_rule(
        self,
        rule_id: str,
        rule_config: Dict[str, Any],
        context: RuleContext,
        result: Any,
    ) -> None:
        """处理触发的规则：生成通知并交付

        Args:
            rule_id: 规则ID
            rule_config: 规则配置
            context: 评估上下文
            result: 评估结果
        """
        notification = self._create_notification(
            rule_id, rule_config, context, result
        )

        channel_ids = self._rule_channel_map.get(rule_id, [])
        if channel_ids:
            try:
                results = await self.router.deliver(channel_ids, notification)
                success = all(r.success for r in results.values())

                if success and self._event_bus and HAS_CORE:
                    event = Event(
                        event_type=EventType.NOTIFICATION_DELIVERED,
                        data={
                            "notification_id": notification.notification_id,
                            "rule_id": rule_id,
                            "channels": channel_ids,
                        },
                    )
                    await self._event_bus.publish(event)

            except Exception as e:
                logger.error(
                    f"Failed to deliver notification for rule {rule_id}: {e}"
                )

        if self._event_bus and HAS_CORE:
            try:
                event = Event(
                    event_type=EventType.RULE_TRIGGERED,
                    data={
                        "rule_id": rule_id,
                        "rule_name": rule_config.get("name", rule_id),
                        "asset": context.asset,
                        "point_name": context.point_name,
                        "current_value": context.current_value,
                        "reason": result.reason,
                        "triggered_at": time.time(),
                    },
                )
                await self._event_bus.publish(event)
            except Exception as e:
                logger.debug(f"Failed to publish triggered event: {e}")

    def _create_notification(
        self,
        rule_id: str,
        rule_config: Dict[str, Any],
        context: RuleContext,
        result: Any,
    ) -> Notification:
        """创建通知对象

        Args:
            rule_id: 规则ID
            rule_config: 规则配置
            context: 评估上下文
            result: 评估结果

        Returns:
            通知对象
        """
        import uuid

        notification_config = rule_config.get("notification", {})

        return Notification(
            notification_id=str(uuid.uuid4()),
            rule_id=rule_id,
            rule_name=rule_config.get("name", rule_id),
            title=notification_config.get(
                "title",
                f"Rule alert: {rule_config.get('name', rule_id)}"
            ),
            message=notification_config.get(
                "message",
                result.reason or f"Rule {rule_id} triggered"
            ),
            level=notification_config.get("level", "warning"),
            asset=context.asset,
            point_name=context.point_name,
            current_value=context.current_value,
            threshold=notification_config.get("threshold"),
            triggered_at=time.time(),
            recipients=notification_config.get("recipients"),
            metadata={
                "details": result.details,
                "rule_config": {
                    k: v for k, v in rule_config.items()
                    if k not in ("plugin", "data_subscriptions", "notification")
                },
            },
        )

    def add_rule(
        self,
        rule_config: Dict[str, Any],
        pipeline_id: Optional[str] = None,
        channel_ids: Optional[List[str]] = None,
    ) -> bool:
        """添加规则

        Args:
            rule_config: 规则配置
            pipeline_id: 关联的过滤器管道ID
            channel_ids: 通知交付渠道ID列表

        Returns:
            是否添加成功
        """
        rule_id = rule_config.get("id")
        if not rule_id:
            logger.error("Rule config missing 'id'")
            return False

        success = self.evaluator.load_rule(rule_config)
        if not success:
            return False

        self._rule_configs[rule_id] = rule_config

        if pipeline_id:
            self._rule_pipeline_map[rule_id] = pipeline_id

        if channel_ids:
            self._rule_channel_map[rule_id] = channel_ids

        logger.info(
            f"Rule added: {rule_id}, "
            f"pipeline={pipeline_id}, channels={channel_ids}"
        )
        return True

    async def add_rule_async(
        self,
        rule_config: Dict[str, Any],
        pipeline_id: Optional[str] = None,
        channel_ids: Optional[List[str]] = None,
    ) -> bool:
        """异步添加规则（带持久化）

        Args:
            rule_config: 规则配置
            pipeline_id: 关联的过滤器管道ID
            channel_ids: 通知交付渠道ID列表

        Returns:
            是否添加成功
        """
        rule_id = rule_config.get("id")
        if not rule_id:
            logger.error("Rule config missing 'id'")
            return False

        if self._persistence_manager:
            from .persistence import RuleRecord
            rule = RuleRecord(
                id=rule_id,
                name=rule_config.get("name", rule_id),
                description=rule_config.get("description"),
                enabled=rule_config.get("enabled", True),
                plugin_config=rule_config.get("plugin", {}),
                data_subscriptions=rule_config.get("data_subscriptions"),
                notification_config=rule_config.get("notification"),
                pipeline_id=pipeline_id,
                channel_ids=channel_ids or [],
            )
            success = await self._persistence_manager.save_rule(rule)
            if not success:
                logger.error(f"Failed to persist rule {rule_id}")
                return False

        success = self.add_rule(rule_config, pipeline_id, channel_ids)
        if not success and self._persistence_manager:
            await self._persistence_manager.delete_rule(rule_id)
            return False

        return True

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        Args:
            rule_id: 规则ID

        Returns:
            是否移除成功
        """
        if not self.evaluator.is_rule_loaded(rule_id):
            return False

        self.evaluator.unload_rule(rule_id)
        self._rule_configs.pop(rule_id, None)
        self._rule_pipeline_map.pop(rule_id, None)
        self._rule_channel_map.pop(rule_id, None)

        logger.info(f"Rule removed: {rule_id}")
        return True

    async def remove_rule_async(self, rule_id: str) -> bool:
        """异步移除规则（带持久化）

        Args:
            rule_id: 规则ID

        Returns:
            是否移除成功
        """
        if not self.evaluator.is_rule_loaded(rule_id):
            return False

        if self._persistence_manager:
            success = await self._persistence_manager.delete_rule(rule_id)
            if not success:
                logger.error(f"Failed to delete rule {rule_id} from persistence")
                return False

        return self.remove_rule(rule_id)

    def add_pipeline(self, config: PipelineConfig) -> None:
        """添加过滤器管道

        Args:
            config: 管道配置
        """
        self.pipeline_manager.create_pipeline(config)

    async def add_pipeline_async(self, config: PipelineConfig) -> bool:
        """异步添加过滤器管道（带持久化）

        Args:
            config: 管道配置

        Returns:
            是否添加成功
        """
        if self._persistence_manager:
            from .persistence import PipelineRecord
            pipeline = PipelineRecord(
                id=config.pipeline_id,
                filters=config.filters,
                config={
                    "continue_on_error": config.continue_on_error,
                    "log_errors": config.log_errors,
                    "max_retries": config.max_retries,
                    "retry_delay": config.retry_delay,
                    "retry_backoff": config.retry_backoff,
                    "timeout_per_filter": config.timeout_per_filter,
                    "location": config.location.value,
                    "service_name": config.service_name,
                    "error_callback_plugin": config.error_callback_plugin,
                    "error_callback_config": config.error_callback_config,
                    "enable_metrics": config.enable_metrics,
                },
            )
            success = await self._persistence_manager.save_pipeline(pipeline)
            if not success:
                logger.error(f"Failed to persist pipeline {config.pipeline_id}")
                return False

        try:
            self.pipeline_manager.create_pipeline(config)
            return True
        except Exception as e:
            logger.error(f"Failed to add pipeline: {e}")
            if self._persistence_manager:
                await self._persistence_manager.delete_pipeline(config.pipeline_id)
            return False

    def add_delivery_channel(
        self,
        channel_id: str,
        plugin_name: str,
        config: Dict[str, Any],
    ) -> bool:
        """添加通知交付渠道

        Args:
            channel_id: 渠道ID
            plugin_name: 交付插件名称
            config: 渠道配置

        Returns:
            是否添加成功
        """
        return self.router.register_channel(channel_id, plugin_name, config)

    async def add_delivery_channel_async(
        self,
        channel_id: str,
        plugin_name: str,
        config: Dict[str, Any],
    ) -> bool:
        """异步添加通知交付渠道（带持久化）

        Args:
            channel_id: 渠道ID
            plugin_name: 交付插件名称
            config: 渠道配置

        Returns:
            是否添加成功
        """
        if self._persistence_manager:
            from .persistence import ChannelRecord
            channel = ChannelRecord(
                id=channel_id,
                plugin_name=plugin_name,
                config=config,
            )
            success = await self._persistence_manager.save_channel(channel)
            if not success:
                logger.error(f"Failed to persist channel {channel_id}")
                return False

        success = self.router.register_channel(channel_id, plugin_name, config)
        if not success and self._persistence_manager:
            await self._persistence_manager.delete_channel(channel_id)
            return False

        return True

    async def remove_pipeline_async(self, pipeline_id: str) -> bool:
        """异步移除过滤器管道（带持久化）

        Args:
            pipeline_id: 管道ID

        Returns:
            是否移除成功
        """
        if pipeline_id not in self.pipeline_manager.pipeline_ids:
            return False

        if self._persistence_manager:
            success = await self._persistence_manager.delete_pipeline(pipeline_id)
            if not success:
                logger.error(f"Failed to delete pipeline {pipeline_id} from persistence")
                return False

        try:
            self.pipeline_manager.remove_pipeline(pipeline_id)
            return True
        except Exception as e:
            logger.error(f"Failed to remove pipeline: {e}")
            return False

    async def unregister_channel(self, channel_id: str) -> bool:
        """注销渠道（带持久化）

        Args:
            channel_id: 渠道ID

        Returns:
            是否注销成功
        """
        if channel_id not in self.router._channel_configs:
            return False

        if self._persistence_manager:
            success = await self._persistence_manager.delete_channel(channel_id)
            if not success:
                logger.error(f"Failed to delete channel {channel_id} from persistence")
                return False

        return await self.router.unregister_channel(channel_id)

    def bind_rule_channels(
        self, rule_id: str, channel_ids: List[str]
    ) -> None:
        """绑定规则到通知渠道

        Args:
            rule_id: 规则ID
            channel_ids: 渠道ID列表
        """
        self._rule_channel_map[rule_id] = channel_ids

    def get_status(self) -> Dict[str, Any]:
        """获取规则引擎状态

        Returns:
            状态字典
        """
        return {
            "running": self._running,
            "loaded_rules": len(self.evaluator.get_loaded_rules()),
            "registered_channels": len(self.router.get_registered_channels()),
            "active_pipelines": self.pipeline_manager.pipeline_count,
            "aggregation_subscriptions": len(
                self.aggregation_engine.get_all_subscriptions()
            ),
            "event_bus_connected": self._event_bus is not None,
        }

    def get_all_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取所有规则配置

        Returns:
            规则配置字典的副本
        """
        return copy.deepcopy(self._rule_configs)

    def get_rule_config(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取单个规则配置

        Args:
            rule_id: 规则ID

        Returns:
            规则配置的深拷贝，不存在返回 None
        """
        config = self._rule_configs.get(rule_id)
        return copy.deepcopy(config) if config else None

    def get_rule_pipeline(self, rule_id: str) -> Optional[str]:
        """获取规则关联的管道ID

        Args:
            rule_id: 规则ID

        Returns:
            管道ID，不存在返回 None
        """
        return self._rule_pipeline_map.get(rule_id)

    def get_rule_channels(self, rule_id: str) -> Optional[List[str]]:
        """获取规则关联的渠道ID列表

        Args:
            rule_id: 规则ID

        Returns:
            渠道ID列表的副本，不存在返回 None
        """
        channels = self._rule_channel_map.get(rule_id)
        return list(channels) if channels else None

    def get_all_channel_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有渠道配置

        Returns:
            渠道配置字典的副本
        """
        return copy.deepcopy(self.router._channel_configs)

    def get_channel_config(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """获取单个渠道配置

        Args:
            channel_id: 渠道ID

        Returns:
            渠道配置的深拷贝，不存在返回 None
        """
        config = self.router._channel_configs.get(channel_id)
        return copy.deepcopy(config) if config else None

    def get_all_pipeline_ids(self) -> List[str]:
        """获取所有管道ID列表

        Returns:
            管道ID列表
        """
        return list(self.pipeline_manager.pipeline_ids)

    def get_pipeline(self, pipeline_id: str) -> Optional[Any]:
        """获取管道实例

        Args:
            pipeline_id: 管道ID

        Returns:
            管道实例，不存在返回 None
        """
        return self.pipeline_manager.get_pipeline(pipeline_id)

    def is_rule_loaded(self, rule_id: str) -> bool:
        """检查规则是否已加载

        Args:
            rule_id: 规则ID

        Returns:
            是否已加载
        """
        return self.evaluator.is_rule_loaded(rule_id)

    def is_channel_registered(self, channel_id: str) -> bool:
        """检查渠道是否已注册

        Args:
            channel_id: 渠道ID

        Returns:
            是否已注册
        """
        return channel_id in self.router._channel_configs

    def is_pipeline_exists(self, pipeline_id: str) -> bool:
        """检查管道是否存在

        Args:
            pipeline_id: 管道ID

        Returns:
            是否存在
        """
        return pipeline_id in self.pipeline_manager.pipeline_ids
