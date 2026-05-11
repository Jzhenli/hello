"""Filter Pipeline

负责编排和执行过滤器插件。
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .base import ReadingSet
from .plugins import RuleFilterPlugin
from .manager import PluginManager

logger = logging.getLogger(__name__)


class PipelineLocation(Enum):
    """管道位置"""
    SOUTH = "south"
    NORTH = "north"


class FilterPipeline:
    """过滤器管道

    负责编排和执行过滤器插件。

    Attributes:
        plugin_manager: 插件管理器
        _filters: 过滤器实例列表
        _filter_configs: 过滤器配置列表
    """

    def __init__(self, plugin_manager: PluginManager):
        """初始化过滤器管道

        Args:
            plugin_manager: 插件管理器
        """
        self.plugin_manager = plugin_manager
        self._filters: List[RuleFilterPlugin] = []
        self._filter_configs: List[Dict[str, Any]] = []

    def add_filter(
        self,
        plugin_name: str,
        config: Dict[str, Any],
        order: int = 0
    ) -> bool:
        """添加过滤器

        Args:
            plugin_name: 过滤器插件名称
            config: 过滤器配置
            order: 执行顺序

        Returns:
            是否添加成功
        """
        full_plugin_name = f"rule_engine.filter:{plugin_name}"

        try:
            plugin = self.plugin_manager.get_instance(
                full_plugin_name, config
            )

            if not isinstance(plugin, RuleFilterPlugin):
                logger.error(f"Plugin {plugin_name} is not a RuleFilterPlugin")
                return False

            self._filters.append(plugin)
            self._filter_configs.append({
                "name": plugin_name,
                "config": config,
                "order": order
            })

            paired = list(zip(self._filters, self._filter_configs))
            paired.sort(key=lambda pair: pair[1].get("order", 0))
            self._filters = [p for p, _ in paired]
            self._filter_configs = [c for _, c in paired]

            logger.info(f"Added filter: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add filter {plugin_name}: {e}")
            return False

    def remove_filter(self, plugin_name: str) -> bool:
        """移除过滤器

        Args:
            plugin_name: 过滤器插件名称

        Returns:
            是否移除成功
        """
        for i, cfg in enumerate(self._filter_configs):
            if cfg["name"] == plugin_name:
                self._filters.pop(i)
                self._filter_configs.pop(i)
                logger.info(f"Removed filter: {plugin_name}")
                return True

        return False

    def execute(self, data: ReadingSet) -> ReadingSet:
        """执行过滤器管道

        Args:
            data: 输入数据

        Returns:
            过滤后的数据
        """
        result = data

        for plugin, cfg in zip(self._filters, self._filter_configs):
            try:
                result = plugin.filter(result)
                logger.debug(
                    f"Filter {cfg['name']} executed, "
                    f"points: {list(result.points.keys())}"
                )
            except Exception as e:
                logger.error(f"Filter {cfg['name']} failed: {e}")

                error_policy = (
                    cfg.get("config", {}).get("error_policy", "pass")
                )

                if error_policy == "drop":
                    return ReadingSet(
                        asset=data.asset,
                        timestamp=data.timestamp,
                        points={}
                    )

        return result

    async def execute_async(self, data: ReadingSet) -> ReadingSet:
        """异步执行过滤器管道

        Args:
            data: 输入数据

        Returns:
            过滤后的数据
        """
        return await asyncio.to_thread(self.execute, data)

    def execute_batch(self, data_list: List[ReadingSet]) -> List[ReadingSet]:
        """批量执行过滤器管道

        Args:
            data_list: 输入数据集列表

        Returns:
            过滤后的数据集列表
        """
        return [self.execute(data) for data in data_list]

    def get_filters(self) -> List[Dict[str, Any]]:
        """获取过滤器列表

        Returns:
            过滤器配置列表
        """
        return self._filter_configs.copy()

    def clear(self) -> None:
        """清空过滤器管道"""
        for plugin in self._filters:
            if hasattr(plugin, 'shutdown'):
                plugin.shutdown()

        self._filters.clear()
        self._filter_configs.clear()

        logger.info("Filter pipeline cleared")


class PipelineConfig:
    """管道配置

    Attributes:
        pipeline_id: 管道ID
        filters: 过滤器配置列表
        continue_on_error: 过滤器出错时是否继续
        log_errors: 是否记录错误
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        retry_backoff: 重试退避因子
        timeout_per_filter: 每个过滤器超时时间（秒）
        location: 管道位置（南向/北向）
        service_name: 服务名称
        error_callback_plugin: 错误回调插件名称
        error_callback_config: 错误回调插件配置
        enable_metrics: 是否启用指标收集
    """

    def __init__(
        self,
        pipeline_id: str,
        filters: Optional[List[Dict[str, Any]]] = None,
        continue_on_error: bool = False,
        log_errors: bool = True,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        timeout_per_filter: float = 30.0,
        location: PipelineLocation = PipelineLocation.SOUTH,
        service_name: str = "",
        error_callback_plugin: Optional[str] = None,
        error_callback_config: Optional[Dict[str, Any]] = None,
        enable_metrics: bool = True,
    ):
        self.pipeline_id = pipeline_id
        self.filters = filters or []
        self.continue_on_error = continue_on_error
        self.log_errors = log_errors
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.timeout_per_filter = timeout_per_filter
        self.location = location
        self.service_name = service_name
        self.error_callback_plugin = error_callback_plugin
        self.error_callback_config = error_callback_config or {}
        self.enable_metrics = enable_metrics


class PipelineMetrics:
    """管道指标收集器"""

    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.total_executions: int = 0
        self.successful_executions: int = 0
        self.failed_executions: int = 0
        self.total_processing_time: float = 0.0
        self.filter_metrics: Dict[str, Dict[str, Any]] = {}

    def record_execution(
        self,
        filter_name: str,
        success: bool,
        duration: float,
        error: Optional[str] = None,
    ) -> None:
        """记录单次过滤器执行指标"""
        self.total_executions += 1

        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1

        self.total_processing_time += duration

        if filter_name not in self.filter_metrics:
            self.filter_metrics[filter_name] = {
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "total_time": 0.0,
                "last_error": None,
            }

        fm = self.filter_metrics[filter_name]
        fm["executions"] += 1
        if success:
            fm["successes"] += 1
        else:
            fm["failures"] += 1
            fm["last_error"] = error
        fm["total_time"] += duration

    def get_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        avg_time = (
            self.total_processing_time / self.total_executions
            if self.total_executions > 0
            else 0.0
        )

        return {
            "pipeline_id": self.pipeline_id,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": (
                self.successful_executions / self.total_executions
                if self.total_executions > 0
                else 0.0
            ),
            "avg_processing_time": avg_time,
            "total_processing_time": self.total_processing_time,
            "filter_metrics": self.filter_metrics,
        }

    def reset(self) -> None:
        """重置指标"""
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.total_processing_time = 0.0
        self.filter_metrics.clear()


class FilterPipelineExecutor:
    """过滤器管道执行器

    支持重试、退避、错误回调、超时控制和指标收集。
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        config: PipelineConfig
    ):
        """初始化管道执行器

        Args:
            plugin_manager: 插件管理器
            config: 管道配置
        """
        self.plugin_manager = plugin_manager
        self.config = config
        self._filters: List[RuleFilterPlugin] = []
        self._filter_names: List[str] = []
        self._metrics: Optional[PipelineMetrics] = None
        self._error_callback: Optional[Callable] = None

        if config.enable_metrics:
            self._metrics = PipelineMetrics(config.pipeline_id)

    def initialize(self) -> None:
        """初始化管道，加载过滤器"""
        sorted_filters = sorted(
            self.config.filters,
            key=lambda f: f.get("order", 0)
        )

        for filter_config in sorted_filters:
            plugin_name = (
                filter_config.get("plugin") or filter_config.get("name")
            )
            config = filter_config.get("config", {})

            if not plugin_name:
                continue

            full_plugin_name = f"rule_engine.filter:{plugin_name}"

            try:
                plugin = self.plugin_manager.get_instance(
                    full_plugin_name, config
                )

                if isinstance(plugin, RuleFilterPlugin):
                    self._filters.append(plugin)
                    self._filter_names.append(plugin_name)
                    logger.debug(f"Loaded filter: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to load filter {plugin_name}: {e}")

        self._init_error_callback()

        logger.info(
            f"Pipeline initialized: {self.config.pipeline_id}, "
            f"filters={len(self._filters)}, "
            f"location={self.config.location.value}, "
            f"metrics={'on' if self._metrics else 'off'}"
        )

    def _init_error_callback(self) -> None:
        """初始化错误回调插件"""
        if not self.config.error_callback_plugin:
            return

        try:
            full_name = f"rule_engine.filter:{self.config.error_callback_plugin}"
            plugin = self.plugin_manager.get_instance(
                full_name, self.config.error_callback_config
            )
            if isinstance(plugin, RuleFilterPlugin):
                self._error_callback = plugin.filter
                logger.info(
                    f"Error callback plugin loaded: "
                    f"{self.config.error_callback_plugin}"
                )
        except Exception as e:
            logger.error(f"Failed to load error callback plugin: {e}")

    async def execute(self, data: ReadingSet) -> ReadingSet:
        """执行管道

        Args:
            data: 输入数据

        Returns:
            过滤后的数据
        """
        result = data

        for plugin, name in zip(self._filters, self._filter_names):
            result = await self._execute_with_retry(plugin, name, result)

        return result

    async def _execute_with_retry(
        self,
        plugin: RuleFilterPlugin,
        name: str,
        data: ReadingSet
    ) -> ReadingSet:
        """执行过滤器（带重试和退避机制）"""
        retries = 0
        delay = self.config.retry_delay
        last_error: Optional[Exception] = None

        while retries <= self.config.max_retries:
            start_time = time.monotonic()

            try:
                if self.config.timeout_per_filter > 0:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(plugin.filter, data),
                        timeout=self.config.timeout_per_filter
                    )
                else:
                    result = plugin.filter(data)

                duration = time.monotonic() - start_time

                if self._metrics:
                    self._metrics.record_execution(
                        name, True, duration
                    )

                return result

            except asyncio.TimeoutError as e:
                last_error = e
                duration = time.monotonic() - start_time

                if self._metrics:
                    self._metrics.record_execution(
                        name, False, duration, "timeout"
                    )

                if self.config.log_errors:
                    logger.error(
                        f"Filter {name} timeout after "
                        f"{self.config.timeout_per_filter}s"
                    )

            except Exception as e:
                last_error = e
                duration = time.monotonic() - start_time

                if self._metrics:
                    self._metrics.record_execution(
                        name, False, duration, str(e)
                    )

                if self.config.log_errors:
                    logger.error(f"Filter {name} failed: {e}")

            if retries < self.config.max_retries:
                retries += 1
                logger.info(
                    f"Retrying filter {name}, "
                    f"attempt {retries}/{self.config.max_retries}, "
                    f"delay={delay:.1f}s"
                )
                await asyncio.sleep(delay)
                delay *= self.config.retry_backoff
            else:
                break

        if last_error:
            await self._invoke_error_callback(name, data, last_error)

            if not self.config.continue_on_error:
                raise last_error

        return data

    async def _invoke_error_callback(
        self,
        filter_name: str,
        data: ReadingSet,
        error: Exception,
    ) -> None:
        """调用错误回调插件"""
        if not self._error_callback:
            return

        try:
            callback_data = ReadingSet(
                asset=data.asset,
                timestamp=data.timestamp,
                points={
                    "_error_filter": filter_name,
                    "_error_message": str(error),
                    "_original_asset": data.asset,
                }
            )
            await asyncio.to_thread(self._error_callback, callback_data)
        except Exception as e:
            logger.error(f"Error callback failed: {e}")

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """获取管道指标

        Returns:
            指标摘要字典，未启用指标时返回 None
        """
        if self._metrics:
            return self._metrics.get_summary()
        return None

    def reset_metrics(self) -> None:
        """重置管道指标"""
        if self._metrics:
            self._metrics.reset()

    def shutdown(self) -> None:
        """关闭管道"""
        for plugin in self._filters:
            if hasattr(plugin, 'shutdown'):
                plugin.shutdown()

        self._filters.clear()
        self._filter_names.clear()
        self._error_callback = None


class PipelineManager:
    """管道管理器

    管理多个过滤器管道。
    """

    def __init__(self, plugin_manager: PluginManager):
        """初始化管道管理器

        Args:
            plugin_manager: 插件管理器
        """
        self.plugin_manager = plugin_manager
        self._pipelines: Dict[str, FilterPipelineExecutor] = {}

    def create_pipeline(self, config: PipelineConfig) -> FilterPipelineExecutor:
        """创建管道

        Args:
            config: 管道配置

        Returns:
            管道执行器
        """
        executor = FilterPipelineExecutor(self.plugin_manager, config)
        executor.initialize()

        self._pipelines[config.pipeline_id] = executor
        return executor

    def get_pipeline(self, pipeline_id: str) -> Optional[FilterPipelineExecutor]:
        """获取管道

        Args:
            pipeline_id: 管道ID

        Returns:
            管道执行器
        """
        return self._pipelines.get(pipeline_id)

    async def execute(
        self,
        pipeline_id: str,
        data: ReadingSet
    ) -> ReadingSet:
        """执行指定管道

        Args:
            pipeline_id: 管道ID
            data: 输入数据

        Returns:
            过滤后的数据
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            logger.warning(f"Pipeline not found: {pipeline_id}")
            return data

        return await pipeline.execute(data)

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for pid, pipeline in self._pipelines.items():
            metrics = pipeline.get_metrics()
            if metrics:
                result[pid] = metrics
        return result

    @property
    def pipeline_count(self) -> int:
        return len(self._pipelines)

    @property
    def pipeline_ids(self) -> List[str]:
        return list(self._pipelines.keys())

    def remove_pipeline(self, pipeline_id: str) -> bool:
        """移除管道

        Args:
            pipeline_id: 管道ID

        Returns:
            是否移除成功
        """
        pipeline = self._pipelines.pop(pipeline_id, None)
        if pipeline:
            pipeline.shutdown()
            return True
        return False

    def shutdown(self) -> None:
        """关闭所有管道"""
        for pipeline in self._pipelines.values():
            pipeline.shutdown()

        self._pipelines.clear()
        logger.info("Pipeline manager shutdown complete")
