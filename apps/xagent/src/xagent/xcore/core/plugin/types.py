"""插件类型和状态定义

定义插件系统的核心类型和枚举。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PluginType(str, Enum):
    """插件类型枚举"""
    SOUTH = "south"
    NORTH = "north"
    FILTER = "filter"
    STORAGE = "storage"
    RULE_ENGINE_RULE = "rule_engine.rule"
    RULE_ENGINE_DELIVERY = "rule_engine.delivery"
    RULE_ENGINE_FILTER = "rule_engine.filter"


class PluginStatus(str, Enum):
    """插件状态枚举"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"


@dataclass
class PluginInfo:
    """插件信息
    
    存储单个插件的完整信息。
    
    Attributes:
        plugin_id: 插件唯一标识符
        name: 插件名称
        plugin_type: 插件类型
        instance: 插件实例
        status: 插件状态
        config: 插件配置
        loaded_at: 加载时间
        error_message: 错误信息
        task_id: 调度器任务ID
    """
    
    plugin_id: str
    name: str
    plugin_type: PluginType
    instance: Any
    status: PluginStatus = PluginStatus.STOPPED
    config: Dict[str, Any] = field(default_factory=dict)
    loaded_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    task_id: Optional[str] = None


@dataclass
class SystemHealthStatus:
    """系统健康状态
    
    记录整个插件系统的健康状态。
    
    Attributes:
        total_plugins: 插件总数
        running_plugins: 运行中的插件数
        failed_plugins: 失败的插件数
        stopped_plugins: 已停止的插件数
        plugin_details: 插件详细信息列表
    """
    
    total_plugins: int
    running_plugins: int
    failed_plugins: int
    stopped_plugins: int
    plugin_details: List[Dict[str, Any]]
