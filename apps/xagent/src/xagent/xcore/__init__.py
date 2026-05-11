"""XAgent Core - Core components for XAgent Gateway"""

from .core import (
    ConfigManager,
    EventBus,
    Scheduler,
    PluginLoader,
    PluginType,
    PluginStatus,
)
from .storage import StorageInterface, Reading, SQLiteStorage, WriteBehindBuffer
from .plugins import (
    SouthPluginBase,
    NorthPluginBase,
    FilterPluginBase,
    FilterChain,
)
from .gateway import Gateway

__all__ = [
    "ConfigManager",
    "EventBus",
    "Scheduler",
    "PluginLoader",
    "PluginType",
    "PluginStatus",
    "StorageInterface",
    "Reading",
    "SQLiteStorage",
    "WriteBehindBuffer",
    "SouthPluginBase",
    "NorthPluginBase",
    "FilterPluginBase",
    "FilterChain",
    "Gateway",
]


def __getattr__(name):
    if name == "app":
        from .api import app
        return app
    if name == "create_app":
        from .api import create_app
        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
