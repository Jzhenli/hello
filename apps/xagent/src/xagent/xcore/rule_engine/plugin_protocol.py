"""Rule Engine Plugin Manager Protocol

Defines the common interface for plugin managers used by rule engine components.
"""

from typing import Any, Dict, Optional, Protocol

from .base import PluginMetadata, PluginRegistration


class IRuleEnginePluginManager(Protocol):
    """规则引擎插件管理器接口
    
    定义规则引擎组件（Router、Pipeline、Evaluator）所需的共同接口。
    适用于 PluginManager 和 RuleEnginePluginManager。
    """
    
    def get_instance(self, plugin_name: str, config: Dict[str, Any]) -> Any:
        """获取或创建插件实例
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            
        Returns:
            插件实例
        """
        ...
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginMetadata]:
        """获取插件元数据
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件元数据，如果不存在返回 None
        """
        ...
    
    def get_plugin_class(self, plugin_key: str) -> Optional[type]:
        """获取插件类
        
        Args:
            plugin_key: 插件键
            
        Returns:
            插件类，如果不存在返回 None
        """
        ...
    
    def get_all_registrations(self) -> Dict[str, PluginRegistration]:
        """获取所有插件注册信息
        
        Returns:
            插件注册信息字典
        """
        ...
