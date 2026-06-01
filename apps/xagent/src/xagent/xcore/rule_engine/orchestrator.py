"""Rule Engine Orchestrator

编排规则引擎各子组件，实现数据事件到规则评估的自动流转。
实现 ILifecycle 接口，与系统框架统一设计。

数据流:
  DATA_RECEIVED -> FilterPipeline -> AggregationEngine -> RuleEvaluator -> DeliveryRouter
                                                                             |
                                                                    RULE_TRIGGERED event

定时规则流:
  Scheduler -> _on_schedule_tick -> RuleEvaluator -> DeliveryRouter -> RULE_TRIGGERED event
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
from .plugin_manager import RuleEnginePluginManager
from .evaluator import RuleEvaluator
from .pipeline import PipelineManager, PipelineConfig
from .router import DeliveryRouter
from .aggregation import AggregationEngine
from ._core_compat import HAS_CORE, EventType, Event, ILifecycleBase, is_reading, reading_to_reading_set

if TYPE_CHECKING:
    from .persistence import RulePersistenceManager
    from ..core.plugin.interfaces import IPluginRegistry

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
        plugin_manager: 规则引擎插件管理器
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
        plugin_registry: Optional["IPluginRegistry"] = None,
    ):
        """初始化规则引擎编排器

        Args:
            event_bus: 事件总线实例，为 None 时内部创建
            plugin_dirs: 插件目录列表（已废弃，保留向后兼容）
            persistence_manager: 持久化管理器实例
            plugin_registry: 插件注册表接口（必需）
        """
        if plugin_registry is None:
            raise ValueError(
                "plugin_registry is required. "
                "Please provide the shared plugin registry from PluginLoader."
            )
        
        # 使用新的 RuleEnginePluginManager
        self.plugin_manager = RuleEnginePluginManager(registry=plugin_registry)
        
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

        self._scheduler: Optional[Any] = None
        self._command_executor: Optional[Any] = None
        self._schedule_tasks: Dict[str, str] = {}
        self._schedule_tick_interval: int = 10
        self._rule_stats: Dict[str, Dict[str, Any]] = {}

    @property
    def event_bus(self) -> Optional[Any]:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: Optional[Any]) -> None:
        self._event_bus = value

    @property
    def is_running(self) -> bool:
        return self._running

    def set_scheduler(self, scheduler: Any) -> None:
        """注入系统调度器，用于定时规则评估"""
        self._scheduler = scheduler
        logger.info("Scheduler injected into Rule Engine Orchestrator")

    def set_command_executor(self, executor: Any) -> None:
        """注入命令执行器，用于规则触发后执行设备控制命令"""
        self._command_executor = executor
        logger.info("CommandExecutor injected into Rule Engine Orchestrator")

    async def start(self) -> None:
        """启动规则引擎编排器"""
        if self._running:
            return

        self._running = True

        # 从共享注册表获取规则引擎插件
        discovered = self.plugin_manager.discover_rule_plugins()
        logger.info(
            f"Plugin discovery completed: {len(discovered)} plugins found "
            f"({', '.join(discovered.keys()) if discovered else 'none'})"
        )

        if self._event_bus and HAS_CORE:
            self._event_bus.subscribe(
                EventType.DATA_RECEIVED, self._on_data_received
            )
            logger.info("RuleEngine subscribed to DATA_RECEIVED events")

        await self._restore_from_persistence()

        self._start_schedule_tick()

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
                success, error = self.evaluator.load_rule(rule_config)
                if success:
                    self._rule_configs[rule_id] = rule_config
                    if rule.pipeline_id:
                        self._rule_pipeline_map[rule_id] = rule.pipeline_id
                    if rule.channel_ids:
                        self._rule_channel_map[rule_id] = rule.channel_ids
                else:
                    logger.warning(f"Skipping rule {rule_id} from persistence: {error}")
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

        self._stop_schedule_tick()

        if self._event_bus and HAS_CORE:
            self._event_bus.unsubscribe(
                EventType.DATA_RECEIVED, self._on_data_received
            )

        self.evaluator.shutdown()
        await self.router.shutdown()
        self.pipeline_manager.shutdown()
        self.aggregation_engine.clear()
        await self.plugin_manager.shutdown()

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
                points=data.get("points", data.get("data", {})),
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
        stats = self._rule_stats.setdefault(rule_id, {"execution_count": 0, "last_triggered": None})
        stats["execution_count"] += 1
        stats["last_triggered"] = time.time()

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

        await self._execute_rule_actions(rule_id, rule_config, context)

    async def _execute_rule_actions(self, rule_id: str, rule_config: Dict[str, Any], context: RuleContext) -> None:
        """从规则配置中提取 action 节点并执行设备控制命令

        优先从 _visual_graph 中提取 action 节点配置，
        其次从 notification.metadata 中提取，
        最后从 plugin.config 中提取 action 相关字段。
        """
        action_items = self._extract_action_configs(rule_config)

        if not action_items:
            logger.debug(f"No action configs found for rule {rule_id}")
            return

        executor = self._command_executor
        if not executor:
            from xagent.plugins.delivery.action.plugin import _get_command_executor
            executor = _get_command_executor()
            if executor:
                self._command_executor = executor

        if not executor:
            logger.warning(f"CommandExecutor not available for rule {rule_id} actions")
            return

        for i, action in enumerate(action_items):
            target_service = action.get("target_service", "")
            target_asset = action.get("target_asset", "")
            operation = action.get("operation", "write_setpoint")
            parameters = action.get("parameters", {})
            point = action.get("point", "")
            value = action.get("value")

            if not target_service or not target_asset:
                logger.warning(
                    f"Missing target_service or target_asset in action {i} for rule {rule_id}: "
                    f"service={target_service}, asset={target_asset}"
                )
                continue

            if operation == "write_setpoint" and point:
                parameters = {"point": point, "value": value}

            try:
                command_id = f"rule-action-{rule_id}-{i}-{int(time.time())}"
                success = await executor.submit_command(
                    command_id=command_id,
                    target_service=target_service,
                    target_asset=target_asset,
                    operation=operation,
                    parameters=parameters,
                )

                if success:
                    logger.info(
                        f"Rule action executed: {rule_id} -> "
                        f"{target_service}.{target_asset}.{operation}"
                    )
                else:
                    logger.error(f"Rule action failed: {rule_id} -> {command_id}")
            except Exception as e:
                logger.error(f"Error executing rule action for {rule_id}: {e}", exc_info=True)

    def _extract_action_configs(self, rule_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从规则配置中提取所有 action 配置

        按优先级从多个位置提取:
        1. plugin.config._visual_graph 中的 action 节点
        2. notification.metadata 中的 action 配置
        3. plugin.config 中的 action 相关字段
        """
        actions = []

        plugin_config = rule_config.get("plugin", {}).get("config", {})
        visual_graph = plugin_config.get("_visual_graph", {})

        if visual_graph and isinstance(visual_graph, dict):
            nodes = visual_graph.get("nodes", [])
            for node in nodes:
                if node.get("type") == "action":
                    action_data = node.get("data", {}).get("action", {})
                    if action_data:
                        action_item = {
                            "target_service": action_data.get("targetService", ""),
                            "target_asset": action_data.get("target_asset", ""),
                            "operation": action_data.get("operation", "write_setpoint"),
                            "parameters": action_data.get("parameters", {}),
                            "point": action_data.get("parameters", {}).get("point", ""),
                            "value": action_data.get("parameters", {}).get("value"),
                            "delay": action_data.get("delay", 0),
                        }
                        if not action_item["target_service"] and action_item["target_asset"]:
                            action_item["target_service"] = action_item["target_asset"]
                        actions.append(action_item)

        if actions:
            return actions

        notification = rule_config.get("notification") or {}
        metadata = notification.get("metadata", {}) if isinstance(notification, dict) else {}
        action_config = metadata.get("action_config", {})
        if action_config:
            actions.append(action_config)
            return actions

        if plugin_config.get("target_service") or plugin_config.get("target_asset"):
            actions.append({
                "target_service": plugin_config.get("target_service", ""),
                "target_asset": plugin_config.get("target_asset", ""),
                "operation": plugin_config.get("operation", "write_setpoint"),
                "parameters": plugin_config.get("parameters", {}),
                "point": plugin_config.get("point", ""),
                "value": plugin_config.get("value"),
            })

        return actions

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
    ) -> tuple:
        """添加规则

        Args:
            rule_config: 规则配置
            pipeline_id: 关联的过滤器管道ID
            channel_ids: 通知交付渠道ID列表

        Returns:
            (是否添加成功, 错误信息)
        """
        rule_id = rule_config.get("id")
        if not rule_id:
            logger.error("Rule config missing 'id'")
            return False, "Rule config missing 'id'"

        success, load_error = self.evaluator.load_rule(rule_config)
        if not success:
            plugin_name = rule_config.get("plugin", {}).get("name", "unknown")
            error_msg = load_error or f"Failed to load rule plugin '{plugin_name}'"
            logger.error(f"Rule {rule_id}: {error_msg}")
            return False, error_msg

        self._rule_configs[rule_id] = rule_config

        if pipeline_id:
            self._rule_pipeline_map[rule_id] = pipeline_id

        if channel_ids:
            self._rule_channel_map[rule_id] = channel_ids

        self._register_schedule_rule(rule_id, rule_config)

        logger.info(
            f"Rule added: {rule_id}, "
            f"pipeline={pipeline_id}, channels={channel_ids}"
        )
        return True, None

    async def add_rule_async(
        self,
        rule_config: Dict[str, Any],
        pipeline_id: Optional[str] = None,
        channel_ids: Optional[List[str]] = None,
    ) -> tuple:
        """异步添加规则（带持久化）

        Args:
            rule_config: 规则配置
            pipeline_id: 关联的过滤器管道ID
            channel_ids: 通知交付渠道ID列表

        Returns:
            (是否添加成功, 错误信息)
        """
        rule_id = rule_config.get("id")
        if not rule_id:
            logger.error("Rule config missing 'id'")
            return False, "Rule config missing 'id'"

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
                return False, f"Failed to persist rule '{rule_id}' to database"

        success, error = self.add_rule(rule_config, pipeline_id, channel_ids)
        if not success and self._persistence_manager:
            await self._persistence_manager.delete_rule(rule_id)
            return False, error

        return True, None

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

        self._unregister_schedule_rule(rule_id)

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
            "schedule_rules": len(self._schedule_tasks),
            "scheduler_available": self._scheduler is not None,
        }

    def get_rule_stats(self, rule_id: str) -> Dict[str, Any]:
        """获取单条规则的执行统计"""
        return self._rule_stats.get(rule_id, {"execution_count": 0, "last_triggered": None})

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

    def _is_schedule_rule(self, rule_config: Dict[str, Any]) -> bool:
        """判断规则是否为定时规则"""
        plugin = rule_config.get("plugin", {})
        plugin_name = plugin.get("name", "") if isinstance(plugin, dict) else ""
        return plugin_name == "schedule_rule"

    def _register_schedule_rule(self, rule_id: str, rule_config: Dict[str, Any]) -> None:
        """注册定时规则的调度任务"""
        if not self._is_schedule_rule(rule_config):
            return

        plugin_config = rule_config.get("plugin", {}).get("config", {})
        trigger_type = plugin_config.get("trigger_type", "interval")

        if self._scheduler:
            interval = plugin_config.get("interval", 60)
            if trigger_type == "cron":
                interval = self._schedule_tick_interval

            try:
                from xagent.xcore.core.scheduler import TaskType
                task_id = self._scheduler.add_task(
                    name=f"schedule_rule_{rule_id}",
                    callback=self._create_schedule_callback(rule_id),
                    task_type=TaskType.CUSTOM,
                    interval=interval,
                )
                self._schedule_tasks[rule_id] = task_id
                asyncio.create_task(self._scheduler.start_task(task_id))
                logger.info(
                    f"Schedule rule registered: {rule_id}, "
                    f"type={trigger_type}, interval={interval}s"
                )
            except Exception as e:
                logger.error(f"Failed to register schedule rule {rule_id}: {e}")
        else:
            logger.warning(
                f"No scheduler available for schedule rule {rule_id}, "
                f"rule will only be evaluated on data events"
            )

    def _unregister_schedule_rule(self, rule_id: str) -> None:
        """注销定时规则的调度任务"""
        task_id = self._schedule_tasks.pop(rule_id, None)
        if task_id and self._scheduler:
            try:
                awaitable = self._scheduler.stop_task(task_id)
                if asyncio.iscoroutine(awaitable):
                    asyncio.create_task(awaitable)
                logger.info(f"Schedule rule unregistered: {rule_id}")
            except Exception as e:
                logger.warning(f"Failed to unregister schedule rule {rule_id}: {e}")

    def _create_schedule_callback(self, rule_id: str):
        """创建定时规则的回调函数"""
        async def _on_schedule_tick():
            if not self._running:
                return
            await self._evaluate_schedule_rule(rule_id)
        return _on_schedule_tick

    def _start_schedule_tick(self) -> None:
        """启动定时规则的全局 tick（用于无 Scheduler 时的回退）"""
        schedule_rules = {
            rid: cfg for rid, cfg in self._rule_configs.items()
            if self._is_schedule_rule(cfg) and rid not in self._schedule_tasks
        }

        if not schedule_rules:
            return

        if self._scheduler:
            for rule_id, rule_config in schedule_rules.items():
                self._register_schedule_rule(rule_id, rule_config)
        else:
            logger.info(
                f"No scheduler, {len(schedule_rules)} schedule rules "
                f"will use fallback tick"
            )
            self._schedule_fallback_task = asyncio.create_task(
                self._schedule_fallback_loop()
            )

    def _stop_schedule_tick(self) -> None:
        """停止定时规则调度"""
        for rule_id in list(self._schedule_tasks.keys()):
            self._unregister_schedule_rule(rule_id)

        fallback_task = getattr(self, '_schedule_fallback_task', None)
        if fallback_task and not fallback_task.done():
            fallback_task.cancel()

    async def _schedule_fallback_loop(self) -> None:
        """无 Scheduler 时的回退定时评估循环"""
        while self._running:
            try:
                schedule_rules = {
                    rid: cfg for rid, cfg in self._rule_configs.items()
                    if self._is_schedule_rule(cfg)
                }
                for rule_id in schedule_rules:
                    try:
                        await self._evaluate_schedule_rule(rule_id)
                    except Exception as e:
                        logger.error(f"Schedule fallback evaluation error for {rule_id}: {e}")

                await asyncio.sleep(self._schedule_tick_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schedule fallback loop error: {e}")
                await asyncio.sleep(self._schedule_tick_interval)

    async def _evaluate_schedule_rule(self, rule_id: str) -> None:
        """评估定时规则"""
        rule_config = self._rule_configs.get(rule_id)
        if not rule_config:
            return

        if not rule_config.get("enabled", True):
            return

        try:
            from datetime import datetime
            context = RuleContext(
                rule_id=rule_id,
                rule_name=rule_config.get("name", rule_id),
                asset="scheduler",
                point_name="tick",
                current_value=datetime.now().isoformat(),
                timestamp=time.time(),
            )

            result = await self.evaluator.evaluate(rule_id, context)

            if result.triggered:
                await self._handle_triggered_rule(
                    rule_id, rule_config, context, result
                )
                logger.info(f"Schedule rule triggered: {rule_id}")

        except Exception as e:
            logger.error(f"Error evaluating schedule rule {rule_id}: {e}")
