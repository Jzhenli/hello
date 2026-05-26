"""Rule Engine Plugin Manager

专门用于规则引擎的插件管理器，从共享的插件注册表获取插件信息。
不再负责插件发现，专注于规则引擎插件的实例化和生命周期管理。
"""

import logging
from typing import Any, Dict, Optional, Type

from ..core.plugin.interfaces import IPluginRegistry
from .base import PluginMetadata, PluginRegistration

logger = logging.getLogger(__name__)


class RuleEnginePluginManager:
    """规则引擎插件管理器
    
    从共享的插件注册表获取规则引擎插件，不再自己进行插件发现。
    专注于规则引擎插件的实例化和生命周期管理。
    
    Attributes:
        _registry: 插件注册表接口
        _registrations: 规则引擎插件注册信息字典
        _instances: 插件实例字典
    """
    
    def __init__(self, registry: IPluginRegistry):
        """初始化规则引擎插件管理器
        
        Args:
            registry: 插件注册表接口，用于获取已发现的插件
        """
        self._registry = registry
        self._registrations: Dict[str, PluginRegistration] = {}
        self._instances: Dict[str, Any] = {}
    
    def discover_rule_plugins(self) -> Dict[str, PluginMetadata]:
        """发现规则引擎插件
        
        从共享的插件注册表中筛选出规则引擎插件。
        不会触发新的文件系统扫描，直接使用已缓存的结果。
        
        Returns:
            规则引擎插件元数据字典 {plugin_key: PluginMetadata}
        """
        all_plugins = self._registry.get_all_plugin_classes()
        rule_plugins = {}
        
        for key, plugin_class in all_plugins.items():
            plugin_type = getattr(plugin_class, '__plugin_type__', '')
            
            # 只处理规则引擎插件
            if not plugin_type.startswith('rule_engine.'):
                logger.debug(f"Skipping non-rule-engine plugin: {key}")
                continue
            
            # 检查是否有 plugin_info 方法
            if not hasattr(plugin_class, 'plugin_info'):
                logger.debug(f"Plugin {key} has no plugin_info, skipping")
                continue
            
            try:
                info = plugin_class.plugin_info()
                rule_plugins[key] = info
                
                # 创建插件注册信息
                self._registrations[key] = PluginRegistration(
                    plugin_class=plugin_class,
                    info=info,
                    config_schema=(
                        plugin_class.config_schema()
                        if hasattr(plugin_class, 'config_schema')
                        else {}
                    ),
                )
                
                logger.debug(f"Registered rule engine plugin: {key}")
            except Exception as e:
                logger.warning(f"Failed to get plugin info for {key}: {e}")
        
        logger.info(f"Discovered {len(rule_plugins)} rule engine plugins from registry")
        return rule_plugins
    
    def get_plugin_class(self, plugin_key: str) -> Optional[Type]:
        """获取插件类
        
        Args:
            plugin_key: 插件键（格式：'plugin_type:plugin_name'）
            
        Returns:
            插件类，如果不存在返回 None
        """
        registration = self._registrations.get(plugin_key)
        return registration.plugin_class if registration else None
    
    def get_plugin_info(self, plugin_key: str) -> Optional[PluginMetadata]:
        """获取插件元数据
        
        Args:
            plugin_key: 插件键
            
        Returns:
            插件元数据，如果不存在返回 None
        """
        registration = self._registrations.get(plugin_key)
        return registration.info if registration else None
    
    def get_plugin_schema(self, plugin_key: str) -> Dict[str, Any]:
        """获取插件配置 Schema
        
        Args:
            plugin_key: 插件键
            
        Returns:
            配置 Schema 字典
        """
        registration = self._registrations.get(plugin_key)
        return registration.config_schema if registration else {}
    
    def register_instance(self, instance_id: str, instance: Any) -> None:
        """注册插件实例
        
        Args:
            instance_id: 实例ID
            instance: 插件实例
        """
        self._instances[instance_id] = instance
        logger.debug(f"Registered plugin instance: {instance_id}")
    
    def unregister_instance(self, instance_id: str) -> bool:
        """注销插件实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            是否成功注销
        """
        if instance_id in self._instances:
            del self._instances[instance_id]
            logger.debug(f"Unregistered plugin instance: {instance_id}")
            return True
        return False
    
    def get_instance(self, instance_id: str) -> Optional[Any]:
        """获取插件实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            插件实例，如果不存在返回 None
        """
        return self._instances.get(instance_id)
    
    def get_all_instances(self) -> Dict[str, Any]:
        """获取所有插件实例
        
        Returns:
            所有插件实例字典
        """
        return self._instances.copy()
    
    def get_all_registrations(self) -> Dict[str, PluginRegistration]:
        """获取所有插件注册信息
        
        Returns:
            所有插件注册信息字典
        """
        return self._registrations.copy()
    
    def shutdown(self) -> None:
        """关闭插件管理器
        
        清理所有插件实例和注册信息。
        """
        # 清理所有插件实例
        for instance_id, instance in self._instances.items():
            try:
                if hasattr(instance, 'shutdown'):
                    instance.shutdown()
                elif hasattr(instance, 'stop'):
                    instance.stop()
            except Exception as e:
                logger.warning(f"Error shutting down plugin instance {instance_id}: {e}")
        
        self._instances.clear()
        self._registrations.clear()
        
        logger.info("Rule engine plugin manager shutdown complete")
