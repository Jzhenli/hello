"""Plugin Loader - Dynamic plugin discovery and lifecycle management

此文件保持向后兼容性，所有功能已重构到plugin子模块。
请使用 from xagent.xcore.core.plugin import ... 替代此模块的导入。
"""

import warnings

warnings.warn(
    "Importing from 'xagent.xcore.core.plugin_loader' is deprecated, "
    "use 'xagent.xcore.core.plugin' instead. "
    "This compatibility module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

from .plugin import (
    PluginType,
    PluginStatus,
    PluginInfo,
    SystemHealthStatus,
    PluginDiscovery,
    PluginRegistry,
    PluginLifecycle,
    PluginLoader,
)

__all__ = [
    "PluginType",
    "PluginStatus",
    "PluginInfo",
    "SystemHealthStatus",
    "PluginDiscovery",
    "PluginRegistry",
    "PluginLifecycle",
    "PluginLoader",
]
