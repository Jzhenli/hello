"""插件注册表模块

管理已加载的插件类和实例。
"""

import logging
import warnings
from typing import Any, Dict, List, Optional, Type

from .types import PluginType, PluginStatus, PluginInfo, SystemHealthStatus

logger = logging.getLogger(__name__)


class PluginRegistry:
    """插件注册表
    
    管理已发现的插件类和已加载的插件实例。
    """
    
    def __init__(self):
        """初始化插件注册表"""
        self._plugin_classes: Dict[str, Type] = {}
        self._plugins: Dict[str, PluginInfo] = {}
        self._plugin_counters: Dict[str, int] = {}
    
    def register_plugin_class(
        self, 
        plugin_type: Any, 
        name: str, 
        plugin_class: Type
    ) -> None:
        """注册插件类
        
        Args:
            plugin_type: 插件类型（PluginType枚举或字符串）
            name: 插件名称
            plugin_class: 插件类
        """
        if isinstance(plugin_type, str):
            type_str = plugin_type
        else:
            type_str = plugin_type.value
        
        key = f"{type_str}:{name}"
        self._plugin_classes[key] = plugin_class
        logger.info(f"Registered plugin class: {key}")
    
    def get_plugin_class(self, plugin_type: Any, name: str) -> Optional[Type]:
        """获取插件类
        
        Args:
            plugin_type: 插件类型
            name: 插件名称
            
        Returns:
            插件类，如果不存在返回None
        """
        if isinstance(plugin_type, str):
            type_str = plugin_type
        else:
            type_str = plugin_type.value
        
        key = f"{type_str}:{name}"
        result = self._plugin_classes.get(key)
        # DEBUG
        if result is None:
            logger.debug(f"[DEBUG] get_plugin_class MISS: key={key!r} type(plugin_type)={type(plugin_type).__name__}")
            logger.debug(f"[DEBUG] _plugin_classes has {len(self._plugin_classes)} keys: {list(self._plugin_classes.keys())[:5]}...")
        return result
    
    def has_plugin_class(self, plugin_type: Any, name: str) -> bool:
        """检查插件类是否已注册
        
        Args:
            plugin_type: 插件类型
            name: 插件名称
            
        Returns:
            如果已注册返回True
        """
        return self.get_plugin_class(plugin_type, name) is not None
    
    def set_plugin_classes(self, plugin_classes: Dict[str, Type]) -> None:
        """设置插件类字典
        
        Args:
            plugin_classes: 插件类字典
        """
        # DEBUG
        logger.debug(f"[DEBUG] set_plugin_classes: {len(plugin_classes)} classes, registry_id={id(self)}")
        logger.debug(f"[DEBUG] keys: {list(plugin_classes.keys())[:5]}...")
        self._plugin_classes = plugin_classes
    
    def register_plugin_instance(self, plugin_info: PluginInfo) -> None:
        """注册插件实例
        
        Args:
            plugin_info: 插件信息
        """
        self._plugins[plugin_info.plugin_id] = plugin_info
        logger.debug(f"Registered plugin instance: {plugin_info.plugin_id}")
    
    def unregister_plugin_instance(self, plugin_id: str) -> bool:
        """注销插件实例
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            如果成功注销返回True
        """
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            logger.debug(f"Unregistered plugin instance: {plugin_id}")
            return True
        return False
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件信息，如果不存在返回None
        """
        return self._plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        return [p for p in self._plugins.values() if p.plugin_type == plugin_type]

    def get_plugin_by_asset(self, asset_name: str) -> Optional[PluginInfo]:
        warnings.warn(
            "get_plugin_by_asset() is deprecated, use get_plugins_by_type() or iterate get_all_plugins() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        for p in self._plugins.values():
            if p.name == asset_name or p.plugin_id.endswith(f"_{asset_name}"):
                return p
        return None
    
    def get_all_plugins(self) -> List[PluginInfo]:
        """获取所有插件
        
        Returns:
            所有插件信息列表
        """
        return list(self._plugins.values())
    
    def get_running_plugins(self) -> List[PluginInfo]:
        """获取所有运行中的插件
        
        Returns:
            运行中的插件信息列表
        """
        return [p for p in self._plugins.values() if p.status == PluginStatus.RUNNING]
    
    def get_failed_plugins(self) -> List[PluginInfo]:
        """获取所有失败的插件
        
        Returns:
            失败的插件信息列表
        """
        return [
            plugin_info for plugin_info in self._plugins.values()
            if plugin_info.status == PluginStatus.ERROR
        ]
    
    def get_health_status(self) -> SystemHealthStatus:
        """获取系统健康状态
        
        Returns:
            系统健康状态
        """
        total = len(self._plugins)
        running = sum(
            1 for p in self._plugins.values() 
            if p.status == PluginStatus.RUNNING
        )
        failed = sum(
            1 for p in self._plugins.values() 
            if p.status == PluginStatus.ERROR
        )
        stopped = sum(
            1 for p in self._plugins.values() 
            if p.status == PluginStatus.STOPPED
        )
        
        details = []
        for plugin_id, plugin_info in self._plugins.items():
            details.append({
                "plugin_id": plugin_id,
                "name": plugin_info.name,
                "type": plugin_info.plugin_type.value,
                "status": plugin_info.status.value,
                "error_message": plugin_info.error_message,
                "loaded_at": plugin_info.loaded_at.isoformat()
            })
        
        return SystemHealthStatus(
            total_plugins=total,
            running_plugins=running,
            failed_plugins=failed,
            stopped_plugins=stopped,
            plugin_details=details
        )
    
    def generate_plugin_id(self, plugin_type: Any, name: str, config: Dict[str, Any]) -> str:
        """生成插件ID
        
        Args:
            plugin_type: 插件类型
            name: 插件名称
            config: 插件配置
            
        Returns:
            唯一的插件ID
        """
        if isinstance(plugin_type, str):
            type_str = plugin_type
        else:
            type_str = plugin_type.value
        
        key = f"{type_str}:{name}"
        
        asset_name = config.get('asset_name') if config else None
        if asset_name:
            return f"{name}_{asset_name}"
        else:
            if key not in self._plugin_counters:
                self._plugin_counters[key] = 0
            self._plugin_counters[key] += 1
            return f"{name}_{self._plugin_counters[key]}"
    
    def clear(self) -> None:
        """清空注册表"""
        self._plugin_classes.clear()
        self._plugins.clear()
        self._plugin_counters.clear()
        logger.debug("Plugin registry cleared")
