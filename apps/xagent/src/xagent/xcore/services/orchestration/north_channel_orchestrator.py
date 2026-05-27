import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...config.config_repository import ConfigRepository
from ...core.event_bus import EventBus, Event, EventType
from ...core.plugin_loader import PluginType

if TYPE_CHECKING:
    from ...core.plugin_loader import PluginLoader
    from ...core.metadata import MetadataManager

logger = logging.getLogger(__name__)


class NorthChannelOrchestrator:
    """
    北向通道编排器
    
    职责：桥接 north_channel_registry 数据库记录与运行时 NorthPlugin 实例
    
    - 通道创建/启用 → 加载并启动插件实例
    - 通道禁用/删除 → 停止并卸载插件实例
    - 通道更新 → 重载插件实例
    - 连通性测试 → 委托给插件实例的 test_connection()
    - 系统启动 → 从数据库加载所有启用的通道并启动
    
    设计原则：
    - 通过 plugin_name 查找插件类（零修改自动发现）
    - 通过 build_plugin_config() 将通道记录转换为插件配置
    - 通过 channel_id 关联通道记录与插件实例
    """

    def __init__(
        self,
        metadata_manager: "MetadataManager",
        plugin_loader: "PluginLoader",
        event_bus: Optional[EventBus] = None,
    ):
        self._metadata_manager = metadata_manager
        self._plugin_loader = plugin_loader
        self._event_bus = event_bus
        self._config_repo = ConfigRepository(metadata_manager.db)
        self._instances: Dict[int, Any] = {}

    async def load_enabled_channels(self) -> None:
        channels = await self._config_repo.list_north_channels(enabled=True)
        for ch in channels:
            try:
                await self.start_channel(ch["id"])
            except Exception as e:
                logger.error(f"Failed to start channel {ch['id']} ({ch.get('name')}): {e}")
        logger.info(f"North channel orchestrator loaded {len(self._instances)} channels")

    async def start_channel(self, channel_id: int) -> Any:
        if channel_id in self._instances:
            logger.warning(f"Channel {channel_id} already running")
            return self._instances[channel_id]

        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        if not channel.get("enabled"):
            raise ValueError(f"Channel '{channel_id}' is disabled")

        plugin_name = channel.get("plugin_name", "xnc_plus")
        plugin_class = self._resolve_plugin_class(plugin_name)
        if plugin_class is None:
            raise ValueError(f"Plugin '{plugin_name}' not found for channel {channel_id}")

        plugin_config = plugin_class.build_plugin_config(channel)

        plugin_info = await self._plugin_loader.load_plugin(
            PluginType.NORTH, plugin_name, plugin_config
        )
        if plugin_info is None:
            raise RuntimeError(f"Failed to load plugin '{plugin_name}' for channel {channel_id}")

        await self._plugin_loader.start_plugin(plugin_info.plugin_id)

        instance = plugin_info.instance
        self._instances[channel_id] = instance

        logger.info(
            f"Channel {channel_id} ({channel.get('name')}) started "
            f"with plugin {plugin_name} (id={plugin_info.plugin_id})"
        )
        return instance

    async def stop_channel(self, channel_id: int) -> None:
        instance = self._instances.pop(channel_id, None)
        if instance is None:
            return

        plugins = self._plugin_loader.get_all_plugins()
        for plugin in plugins:
            if plugin.instance is instance:
                await self._plugin_loader.stop_plugin(plugin.plugin_id)
                await self._plugin_loader.unload_plugin(plugin.plugin_id)
                logger.info(f"Channel {channel_id} stopped (plugin_id={plugin.plugin_id})")
                return

        if hasattr(instance, "stop"):
            await instance.stop()
        logger.info(f"Channel {channel_id} stopped (direct)")

    async def restart_channel(self, channel_id: int) -> Any:
        await self.stop_channel(channel_id)
        return await self.start_channel(channel_id)

    async def reload_channel(self, channel_id: int) -> Any:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")

        if channel_id in self._instances:
            if channel.get("enabled"):
                return await self.restart_channel(channel_id)
            else:
                await self.stop_channel(channel_id)
                return None
        else:
            if channel.get("enabled"):
                return await self.start_channel(channel_id)
            return None

    async def test_connection(self, channel_id: int) -> Dict[str, Any]:
        instance = self._instances.get(channel_id)
        if instance and hasattr(instance, "test_connection"):
            return await instance.test_connection()

        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")

        plugin_name = channel.get("plugin_name", "xnc_plus")
        plugin_class = self._resolve_plugin_class(plugin_name)
        if plugin_class and hasattr(plugin_class, "test_connection"):
            return {"success": False, "message": "Channel not running, cannot test connection"}

        return {"success": False, "message": f"No test_connection for plugin '{plugin_name}'"}

    def get_channel_instance(self, channel_id: int) -> Optional[Any]:
        return self._instances.get(channel_id)

    def get_all_running_channels(self) -> Dict[int, Any]:
        return dict(self._instances)

    def get_channel_info(self, channel_id: int) -> Optional[Dict[str, Any]]:
        instance = self._instances.get(channel_id)
        if instance and hasattr(instance, "get_channel_info"):
            return instance.get_channel_info()
        return None

    async def stop_all(self) -> None:
        for channel_id in list(self._instances.keys()):
            try:
                await self.stop_channel(channel_id)
            except Exception as e:
                logger.error(f"Error stopping channel {channel_id}: {e}")
        self._instances.clear()

    def _resolve_plugin_class(self, plugin_name: str) -> Optional[type]:
        try:
            plugin_classes = self._plugin_loader.discover_plugins()
            key = f"north:{plugin_name}"
            if key in plugin_classes:
                return plugin_classes[key]
            if plugin_name in plugin_classes:
                return plugin_classes[plugin_name]
            for k, cls in plugin_classes.items():
                if hasattr(cls, "__plugin_name__") and cls.__plugin_name__ == plugin_name:
                    return cls
            return None
        except Exception as e:
            logger.error(f"Failed to resolve plugin class for '{plugin_name}': {e}")
            return None
