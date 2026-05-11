"""Plugin Manager

负责插件的发现、加载、实例化和生命周期管理。
复用 core/plugin/discovery.py 的插件发现能力，
保留规则引擎特有的版本兼容、依赖解析、热加载等功能。
"""

import asyncio
import importlib
import json
import logging
import sys
from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING

from .base import PluginMetadata, PluginRegistration

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from xagent.xcore.core.plugin.discovery import PluginDiscovery as _PluginDiscoveryCls
    from watchdog.observers import Observer as _ObserverCls

try:
    from xagent.xcore.core.plugin.discovery import PluginDiscovery
    _HAS_CORE_DISCOVERY = True
except ImportError:
    _HAS_CORE_DISCOVERY = False


class PluginManager:
    """插件管理器

    负责插件的发现、加载、实例化和生命周期管理。
    支持插件热加载、版本兼容性检查和依赖管理。

    复用 core/plugin/discovery.py 的 PluginDiscovery 进行插件发现，
    消除与 core 插件系统的重复代码。

    Attributes:
        plugin_dirs: 插件目录列表
        _discovery: 插件发现器（复用 core 模块）
        _registrations: 插件注册信息字典
        _instances: 插件实例字典
        _core_version: 核心版本号
        _file_watcher: 文件监控器
        _reload_callbacks: 重载回调列表
    """

    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        """初始化插件管理器

        Args:
            plugin_dirs: 插件目录列表
        """
        self.plugin_dirs = plugin_dirs or []
        self._registrations: Dict[str, PluginRegistration] = {}
        self._instances: Dict[str, Any] = {}
        self._core_version: str = "1.0.0"
        self._file_watcher: Optional["_ObserverCls"] = None
        self._reload_callbacks: List[Callable[[str], None]] = []

        if _HAS_CORE_DISCOVERY:
            self._discovery: Optional["_PluginDiscoveryCls"] = PluginDiscovery(
                plugin_dirs=self.plugin_dirs if self.plugin_dirs else None,
                module_prefix="rule_engine_plugins."
            )
        else:
            self._discovery: Optional["_PluginDiscoveryCls"] = None

    def discover(self) -> Dict[str, PluginMetadata]:
        """发现所有可用插件

        优先使用 core 的 PluginDiscovery，回退到内置简化发现。

        Returns:
            插件元数据字典 {plugin_name: PluginMetadata}
        """
        if self._discovery:
            return self._discover_via_core()
        return self._discover_builtin()

    def _discover_via_core(self) -> Dict[str, PluginMetadata]:
        """通过 core PluginDiscovery 发现插件"""
        discovered = {}
        assert self._discovery is not None
        discovered_classes = self._discovery.discover_plugins()

        for key, plugin_class in discovered_classes.items():
            try:
                info = plugin_class.plugin_info()
                discovered[key] = info

                self._registrations[key] = PluginRegistration(
                    plugin_class=plugin_class,
                    info=info,
                    config_schema=(
                        plugin_class.config_schema()
                        if hasattr(plugin_class, 'config_schema')
                        else {}
                    ),
                )

                logger.debug(f"Discovered plugin: {key}")
            except Exception as e:
                logger.warning(f"Failed to get plugin info for {key}: {e}")

        logger.info(f"Discovered {len(discovered)} plugins via core discovery")
        return discovered

    def _discover_builtin(self) -> Dict[str, PluginMetadata]:
        """内置简化发现（core 不可用时的回退方案）"""
        import importlib.util
        import inspect
        from pathlib import Path

        discovered = {}

        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue

            for item in plugin_path.rglob("*.py"):
                if item.name.startswith("_"):
                    continue

                relative_path = item.relative_to(plugin_path)
                module_path = str(relative_path.with_suffix('')).replace(
                    '\\', '.'
                ).replace('/', '.')
                module_name = f"rule_engine_plugins.{module_path}"

                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, item
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)

                        for name in dir(module):
                            try:
                                obj = getattr(module, name)
                                if not inspect.isclass(obj):
                                    continue
                                if not hasattr(obj, '__plugin_type__'):
                                    continue
                                if inspect.isabstract(obj):
                                    continue

                                plugin_type = obj.__plugin_type__
                                plugin_name = (
                                    getattr(obj, '__plugin_name__', None)
                                    or obj.__name__.lower()
                                )
                                key = f"{plugin_type}:{plugin_name}"

                                if key in discovered:
                                    continue

                                info = obj.plugin_info()
                                discovered[key] = info
                                self._registrations[key] = PluginRegistration(
                                    plugin_class=obj,
                                    info=info,
                                    config_schema=(
                                        obj.config_schema()
                                        if hasattr(obj, 'config_schema')
                                        else {}
                                    ),
                                )
                            except Exception:
                                logger.debug(f"Error processing class {name} in {item}", exc_info=True)
                                continue
                except Exception as e:
                    logger.error(f"Error loading plugin {item}: {e}")

        logger.info(f"Discovered {len(discovered)} plugins via builtin")
        return discovered

    def register(self, plugin_class: Type) -> None:
        """注册插件

        Args:
            plugin_class: 插件类
        """
        if not hasattr(plugin_class, '__plugin_type__'):
            raise ValueError(
                "Plugin class must have __plugin_type__ attribute"
            )

        plugin_type = plugin_class.__plugin_type__
        plugin_name = (
            getattr(plugin_class, '__plugin_name__', None)
            or plugin_class.__name__.lower()
        )
        key = f"{plugin_type}:{plugin_name}"

        try:
            info = plugin_class.plugin_info()
            self._registrations[key] = PluginRegistration(
                plugin_class=plugin_class,
                info=info,
                config_schema=(
                    plugin_class.config_schema()
                    if hasattr(plugin_class, 'config_schema')
                    else {}
                ),
            )
            logger.info(f"Registered plugin: {key}")
        except Exception as e:
            logger.error(f"Failed to register plugin {key}: {e}")
            raise

    def unregister(self, plugin_name: str) -> None:
        """注销插件

        同时关闭该插件的所有实例。

        Args:
            plugin_name: 插件名称（格式：type:name）
        """
        if plugin_name not in self._registrations:
            return

        keys_to_remove = [
            k for k in self._instances
            if k.startswith(f"{plugin_name}:")
        ]
        for k in keys_to_remove:
            self._shutdown_instance(self._instances.pop(k), k)

        del self._registrations[plugin_name]
        logger.info(f"Unregistered plugin: {plugin_name}")

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginMetadata]:
        """获取插件元数据

        Args:
            plugin_name: 插件名称

        Returns:
            插件元数据，不存在返回 None
        """
        registration = self._registrations.get(plugin_name)
        return registration.info if registration else None

    def get_instance(
        self,
        plugin_name: str,
        config: Dict[str, Any],
    ) -> Any:
        """获取插件实例

        Args:
            plugin_name: 插件名称
            config: 插件配置

        Returns:
            插件实例
        """
        registration = self._registrations.get(plugin_name)
        if not registration:
            raise ValueError(f"Plugin not found: {plugin_name}")

        instance_key = self._make_instance_key(plugin_name, config)

        if instance_key in self._instances:
            return self._instances[instance_key]

        plugin_class = registration.plugin_class
        instance = plugin_class()
        instance.initialize(config)

        self._instances[instance_key] = instance
        logger.debug(f"Created plugin instance: {instance_key}")

        return instance

    @staticmethod
    def _make_instance_key(
        plugin_name: str, config: Dict[str, Any]
    ) -> str:
        """生成插件实例缓存键

        使用 JSON 序列化确保嵌套 dict 和不同顺序的配置
        生成一致的缓存键。

        Args:
            plugin_name: 插件名称
            config: 插件配置

        Returns:
            实例缓存键
        """
        try:
            config_str = json.dumps(config, sort_keys=True)
        except (TypeError, ValueError):
            config_str = str(config)
        return f"{plugin_name}:{hash(config_str)}"

    def get_all_plugins(
        self, plugin_type: Optional[str] = None
    ) -> List[PluginMetadata]:
        """获取所有插件元数据

        Args:
            plugin_type: 插件类型过滤 (rule/delivery/filter)

        Returns:
            插件元数据列表
        """
        plugins = []

        for key, registration in self._registrations.items():
            if plugin_type:
                if registration.info.plugin_type != plugin_type:
                    continue
            plugins.append(registration.info)

        return plugins

    def validate_config(
        self,
        plugin_name: str,
        config: Dict[str, Any],
    ) -> bool:
        """验证插件配置

        使用 config_schema 进行静态验证，避免创建临时实例。

        Args:
            plugin_name: 插件名称
            config: 插件配置

        Returns:
            配置是否有效
        """
        registration = self._registrations.get(plugin_name)
        if not registration:
            return False

        schema = registration.config_schema
        if not schema:
            return True

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field_name in required:
            if field_name not in config:
                logger.error(
                    f"Config validation: missing required field "
                    f"'{field_name}' for {plugin_name}"
                )
                return False

        for key in config:
            if key not in properties:
                continue

            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            if expected_type and not self._check_type(
                config[key], expected_type
            ):
                logger.error(
                    f"Config validation: field '{key}' expected "
                    f"type '{expected_type}' for {plugin_name}"
                )
                return False

        return True

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """检查值是否符合预期的 JSON Schema 类型

        注意: Python 中 bool 是 int 的子类，需要特殊处理以避免
        布尔值错误通过 integer/number 类型校验。

        Args:
            value: 要检查的值
            expected_type: JSON Schema 类型字符串

        Returns:
            是否匹配
        """
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type in ("integer", "number"):
            if isinstance(value, bool):
                return False
            python_type = int if expected_type == "integer" else (int, float)
            return isinstance(value, python_type)
        type_map = {
            "string": str,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(expected_type)
        if python_type is None:
            return True
        return isinstance(value, python_type)

    def validate_compatibility(self, plugin_info: PluginMetadata) -> bool:
        """验证插件兼容性

        Args:
            plugin_info: 插件元数据

        Returns:
            是否兼容
        """
        if not self._version_gte(
            self._core_version, plugin_info.min_core_version
        ):
            logger.warning(
                f"Plugin {plugin_info.name} requires core version "
                f"{plugin_info.min_core_version}, "
                f"current is {self._core_version}"
            )
            return False

        if plugin_info.deprecated:
            logger.warning(
                f"Plugin {plugin_info.name} is deprecated, "
                f"consider using {plugin_info.successor}"
            )

        return True

    def resolve_dependencies(self) -> List[str]:
        """解析依赖，返回加载顺序

        使用拓扑排序解析依赖关系。

        Returns:
            插件名称列表（按加载顺序）
        """
        sorted_plugins = []
        visited = set()
        temp_visited = set()

        def visit(plugin_name: str):
            if plugin_name in temp_visited:
                raise ValueError(
                    f"Circular dependency detected: {plugin_name}"
                )

            if plugin_name in visited:
                return

            temp_visited.add(plugin_name)

            registration = self._registrations.get(plugin_name)
            if registration:
                for dep in registration.info.dependencies:
                    if not dep.optional:
                        dep_key = (
                            f"{registration.info.plugin_type}"
                            f":{dep.plugin_name}"
                        )
                        if dep_key in self._registrations:
                            visit(dep_key)

            temp_visited.remove(plugin_name)
            visited.add(plugin_name)
            sorted_plugins.append(plugin_name)

        for plugin_name in self._registrations:
            visit(plugin_name)

        return sorted_plugins

    def enable_hot_reload(self, enabled: bool = True) -> None:
        """启用/禁用插件热加载

        Args:
            enabled: 是否启用
        """
        if enabled and not self._file_watcher:
            self._file_watcher = self._create_file_watcher()
            if self._file_watcher:
                logger.info("Plugin hot reload enabled")
        elif not enabled and self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None
            logger.info("Plugin hot reload disabled")

    def _create_file_watcher(self) -> "Optional[_ObserverCls]":
        """创建文件监控器"""
        if not self.plugin_dirs:
            logger.warning("No plugin directories configured, hot reload disabled")
            return None

        try:
            from watchdog.observers import Observer  # type: ignore[import-untyped]
            from watchdog.events import (  # type: ignore[import-untyped]
                FileSystemEventHandler,
                FileModifiedEvent,
            )

            manager = self

            class PluginFileHandler(FileSystemEventHandler):  # type: ignore[misc]
                def on_modified(self, event):
                    if (
                        isinstance(event, FileModifiedEvent)
                        and event.src_path.endswith('.py')
                    ):
                        manager._reload_plugin_file(event.src_path)

            observer: "_ObserverCls" = Observer()
            scheduled = False
            for plugin_dir in self.plugin_dirs:
                from pathlib import Path
                if Path(plugin_dir).is_dir():
                    observer.schedule(
                        PluginFileHandler(),
                        plugin_dir,
                        recursive=True,
                    )
                    scheduled = True
                else:
                    logger.warning(
                        f"Plugin directory does not exist: {plugin_dir}"
                    )

            if not scheduled:
                logger.warning(
                    "No valid plugin directories found, hot reload disabled"
                )
                return None

            observer.start()
            return observer

        except ImportError:
            logger.warning(
                "watchdog not installed, hot reload disabled. "
                "Install with: pip install watchdog"
            )
            return None

    def _reload_plugin_file(self, file_path: str) -> None:
        """重新加载插件文件

        Args:
            file_path: 插件文件路径
        """
        logger.info(f"Reloading plugin file: {file_path}")

        affected_plugins = self._find_plugins_by_file(file_path)

        for plugin_name in affected_plugins:
            try:
                old_registration = self._registrations.get(plugin_name)
                if old_registration:
                    keys_to_remove = [
                        k for k in self._instances
                        if k.startswith(f"{plugin_name}:")
                    ]
                    for k in keys_to_remove:
                        instance = self._instances.pop(k, None)
                        self._shutdown_instance(instance, k)

                module_name = self._get_module_name(file_path)
                if module_name and module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])

                self.discover()

                logger.info(f"Plugin {plugin_name} reloaded successfully")

                self._emit_reload_event(plugin_name)

            except Exception as e:
                logger.error(f"Failed to reload plugin {plugin_name}: {e}")

    def _find_plugins_by_file(self, file_path: str) -> List[str]:
        """根据文件路径查找受影响的插件

        Args:
            file_path: 文件路径

        Returns:
            受影响的插件名称列表
        """
        affected = []
        for name, reg in self._registrations.items():
            module = reg.plugin_class.__module__
            file_module = module.replace('.', '/')
            if file_module in file_path or file_path.endswith(
                f"{file_module}.py"
            ):
                affected.append(name)
        return affected

    def _get_module_name(self, file_path: str) -> str:
        """从文件路径获取模块名

        Args:
            file_path: 文件路径

        Returns:
            模块名
        """
        for plugin_dir in self.plugin_dirs:
            if file_path.startswith(plugin_dir):
                rel_path = file_path[len(plugin_dir):].lstrip('/\\')
                return rel_path.replace(
                    '/', '.'
                ).replace('\\', '.')[:-3]
        return ""

    def _emit_reload_event(self, plugin_name: str) -> None:
        """触发插件重载事件

        Args:
            plugin_name: 插件名称
        """
        for callback in self._reload_callbacks:
            try:
                callback(plugin_name)
            except Exception as e:
                logger.error(
                    f"Reload callback error for {plugin_name}: {e}"
                )

    def on_reload(self, callback: Callable[[str], None]) -> None:
        """注册重载回调

        Args:
            callback: 回调函数，参数为插件名称
        """
        self._reload_callbacks.append(callback)

    def _version_gte(self, version1: str, version2: str) -> bool:
        try:
            from packaging import version
            return version.parse(version1) >= version.parse(version2)
        except Exception:
            logger.warning(
                f"Version comparison failed for '{version1}' >= '{version2}', "
                f"assuming incompatible for safety"
            )
            return False

    @staticmethod
    def _shutdown_instance(instance: Any, key: str = "") -> None:
        """关闭单个插件实例，处理同步和异步 shutdown

        对于异步 shutdown，优先尝试在已有事件循环中调度执行，
        否则使用线程安全的方式创建新事件循环执行。

        Args:
            instance: 插件实例
            key: 实例缓存键（用于日志）
        """
        if instance is None:
            return

        try:
            if not hasattr(instance, 'shutdown'):
                return

            result = instance.shutdown()

            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    try:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(result)
                        loop.close()
                    except Exception as e:
                        logger.error(
                            f"Error in async shutdown for {key}: {e}"
                        )
        except Exception as e:
            logger.error(f"Error shutting down instance {key}: {e}")

    def shutdown(self) -> None:
        """关闭插件管理器"""
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        for key, instance in self._instances.items():
            self._shutdown_instance(instance, key)

        self._instances.clear()
        self._registrations.clear()

        logger.info("Plugin manager shutdown complete")

    def get_config_schema(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件配置 Schema

        Args:
            plugin_name: 插件名称

        Returns:
            配置 Schema 字典
        """
        registration = self._registrations.get(plugin_name)
        if not registration:
            return {}

        return registration.config_schema
