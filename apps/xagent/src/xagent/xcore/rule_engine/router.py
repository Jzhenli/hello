"""Delivery Router

负责将通知路由到正确的交付插件。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import Notification, DeliveryResult, DeliveryStatus
from .plugins import DeliveryPlugin
from .manager import PluginManager

logger = logging.getLogger(__name__)


class DeliveryRouter:
    """交付路由器

    负责将通知路由到正确的交付插件。
    支持多渠道并行投递。

    Attributes:
        plugin_manager: 插件管理器
        _delivery_plugins: 交付插件实例字典
        _channel_configs: 渠道配置字典
    """

    def __init__(self, plugin_manager: PluginManager):
        """初始化交付路由器

        Args:
            plugin_manager: 插件管理器
        """
        self.plugin_manager = plugin_manager
        self._delivery_plugins: Dict[str, DeliveryPlugin] = {}
        self._channel_configs: Dict[str, Dict[str, Any]] = {}

    def register_channel(
        self,
        channel_id: str,
        plugin_name: str,
        config: Dict[str, Any]
    ) -> bool:
        """注册通知渠道

        Args:
            channel_id: 渠道ID
            plugin_name: 交付插件名称
            config: 渠道配置

        Returns:
            是否注册成功
        """
        full_plugin_name = f"rule_engine.delivery:{plugin_name}"

        try:
            plugin = self.plugin_manager.get_instance(
                full_plugin_name, config
            )

            if not isinstance(plugin, DeliveryPlugin):
                logger.error(
                    f"Plugin {plugin_name} is not a DeliveryPlugin"
                )
                return False

            self._delivery_plugins[channel_id] = plugin
            self._channel_configs[channel_id] = {
                "plugin_name": plugin_name,
                "config": config
            }

            logger.info(f"Registered delivery channel: {channel_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register channel {channel_id}: {e}")
            return False

    async def unregister_channel(self, channel_id: str) -> bool:
        """注销通知渠道

        Args:
            channel_id: 渠道ID

        Returns:
            是否注销成功
        """
        if channel_id in self._delivery_plugins:
            plugin = self._delivery_plugins.pop(channel_id)
            if hasattr(plugin, 'shutdown'):
                try:
                    await plugin.shutdown()
                except Exception as e:
                    logger.error(
                        f"Error shutting down channel {channel_id}: {e}"
                    )
            self._channel_configs.pop(channel_id, None)
            logger.info(f"Unregistered delivery channel: {channel_id}")
            return True

        return False

    async def deliver(
        self,
        channel_ids: List[str],
        notification: Notification
    ) -> Dict[str, DeliveryResult]:
        """并行发送通知到多个渠道

        使用 asyncio.gather 实现多渠道并行投递，
        单个渠道失败不影响其他渠道。

        Args:
            channel_ids: 渠道ID列表
            notification: 通知对象

        Returns:
            各渠道的交付结果
        """
        results: Dict[str, DeliveryResult] = {}

        pending_ids = []
        pending_tasks = []

        for channel_id in channel_ids:
            plugin = self._delivery_plugins.get(channel_id)
            if plugin:
                pending_ids.append(channel_id)
                pending_tasks.append(
                    self._deliver_to_channel(
                        plugin, channel_id, notification
                    )
                )
            else:
                results[channel_id] = DeliveryResult(
                    status=DeliveryStatus.FAILED,
                    success=False,
                    error=f"Channel not found: {channel_id}"
                )

        if pending_tasks:
            task_results = await asyncio.gather(
                *pending_tasks, return_exceptions=True
            )

            for channel_id, task_result in zip(pending_ids, task_results):
                if isinstance(task_result, Exception):
                    logger.error(
                        f"Delivery to {channel_id} failed: {task_result}"
                    )
                    results[channel_id] = DeliveryResult(
                        status=DeliveryStatus.FAILED,
                        success=False,
                        error=str(task_result)
                    )
                else:
                    results[channel_id] = task_result

        return results

    async def _deliver_to_channel(
        self,
        plugin: DeliveryPlugin,
        channel_id: str,
        notification: Notification
    ) -> DeliveryResult:
        """发送通知到单个渠道

        Args:
            plugin: 交付插件
            channel_id: 渠道ID
            notification: 通知对象

        Returns:
            交付结果
        """
        try:
            result = await plugin.deliver(notification)

            logger.info(
                f"Notification {notification.notification_id} "
                f"delivered to {channel_id}: success={result.success}"
            )

            return result

        except Exception as e:
            logger.error(f"Delivery error for {channel_id}: {e}")
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error=str(e)
            )

    async def deliver_to_channel(
        self,
        channel_id: str,
        notification: Notification
    ) -> DeliveryResult:
        """发送通知到单个渠道

        Args:
            channel_id: 渠道ID
            notification: 通知对象

        Returns:
            交付结果
        """
        plugin = self._delivery_plugins.get(channel_id)

        if not plugin:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                success=False,
                error=f"Channel not found: {channel_id}"
            )

        return await self._deliver_to_channel(
            plugin, channel_id, notification
        )

    async def test_channel(self, channel_id: str) -> bool:
        """测试渠道连接

        Args:
            channel_id: 渠道ID

        Returns:
            连接是否正常
        """
        plugin = self._delivery_plugins.get(channel_id)

        if not plugin:
            logger.warning(f"Channel not found: {channel_id}")
            return False

        try:
            result = await plugin.test_connection()
            logger.info(
                f"Channel {channel_id} test: "
                f"{'passed' if result else 'failed'}"
            )
            return result
        except Exception as e:
            logger.error(f"Channel {channel_id} test failed: {e}")
            return False

    def get_registered_channels(self) -> Dict[str, Dict[str, Any]]:
        """获取已注册的渠道

        Returns:
            渠道配置字典
        """
        return self._channel_configs.copy()

    def is_channel_registered(self, channel_id: str) -> bool:
        """检查渠道是否已注册

        Args:
            channel_id: 渠道ID

        Returns:
            是否已注册
        """
        return channel_id in self._delivery_plugins

    def get_channel_plugin(self, channel_id: str) -> Optional[DeliveryPlugin]:
        """获取渠道插件实例

        Args:
            channel_id: 渠道ID

        Returns:
            交付插件实例
        """
        return self._delivery_plugins.get(channel_id)

    async def shutdown(self) -> None:
        """关闭路由器"""
        for channel_id, plugin in self._delivery_plugins.items():
            try:
                if hasattr(plugin, 'shutdown'):
                    await plugin.shutdown()
            except Exception as e:
                logger.error(
                    f"Error shutting down channel {channel_id}: {e}"
                )

        self._delivery_plugins.clear()
        self._channel_configs.clear()

        logger.info("Delivery router shutdown complete")
