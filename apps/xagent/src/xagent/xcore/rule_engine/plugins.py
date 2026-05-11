"""Plugin Base Classes

定义规则引擎插件的基础类。
所有规则引擎插件基类统一实现 IPlugin 接口，
与核心插件体系保持一致的生命周期管理。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from .base import (
    PluginMetadata,
    RuleContext,
    RuleEvaluationResult,
    Notification,
    DeliveryResult,
    ReadingSet,
)
from ._core_compat import HAS_CORE

if HAS_CORE:
    from xagent.xcore.core.interfaces import IPlugin
else:
    IPlugin = ABC

logger = logging.getLogger(__name__)


class _RulePluginMixin(IPlugin if HAS_CORE else ABC):
    """规则引擎插件 IPlugin 适配混入类
    
    为规则引擎插件提供 IPlugin 接口的默认实现，
    使其与核心插件体系兼容。
    """
    
    @property
    def plugin_type(self) -> str:
        return self.__plugin_type__
    
    @property
    def plugin_name(self) -> str:
        return self.__plugin_name__


class RulePlugin(_RulePluginMixin):
    """规则插件基类
    
    所有规则插件必须继承此类，并实现必要的方法。
    同时实现了 IPlugin 接口，与核心插件体系统一。
    
    Attributes:
        __plugin_name__: 插件名称（子类必须定义）
        __plugin_type__: 插件类型（固定为 "rule"）
    """
    
    __plugin_name__: str = ""
    __plugin_type__: str = "rule_engine.rule"
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
    
    @classmethod
    @abstractmethod
    def plugin_info(cls) -> PluginMetadata:
        """返回插件元数据
        
        Returns:
            PluginMetadata: 插件元数据对象
        """
        pass
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        """返回配置项 JSON Schema
        
        用于可视化编辑器动态生成配置表单。
        
        Returns:
            JSON Schema 字典
        """
        return {}
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件
        
        Args:
            config: 插件配置
        """
        pass
    
    @abstractmethod
    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        """评估规则
        
        Args:
            context: 规则评估上下文
        
        Returns:
            RuleEvaluationResult: 评估结果
        """
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置
        
        Args:
            config: 插件配置
        
        Returns:
            配置是否有效
        """
        return True
    
    def get_preview_text(self, config: Dict[str, Any]) -> str:
        """获取节点预览文本
        
        用于可视化编辑器显示节点摘要。
        
        Args:
            config: 插件配置
        
        Returns:
            预览文本
        """
        return ""
    
    def shutdown(self) -> None:
        """关闭插件，释放资源"""
        pass


class DeliveryPlugin(_RulePluginMixin):
    """交付插件基类
    
    所有交付插件必须继承此类，并实现必要的方法。
    同时实现了 IPlugin 接口，与核心插件体系统一。
    
    Attributes:
        __plugin_name__: 插件名称（子类必须定义）
        __plugin_type__: 插件类型（固定为 "delivery"）
    """
    
    __plugin_name__: str = ""
    __plugin_type__: str = "rule_engine.delivery"
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
    
    @classmethod
    @abstractmethod
    def plugin_info(cls) -> PluginMetadata:
        """返回插件元数据
        
        Returns:
            PluginMetadata: 插件元数据对象
        """
        pass
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        """返回配置项 JSON Schema
        
        Returns:
            JSON Schema 字典
        """
        return {}
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件
        
        Args:
            config: 插件配置（渠道配置）
        """
        pass
    
    @abstractmethod
    async def deliver(self, notification: Notification) -> DeliveryResult:
        """发送通知
        
        Args:
            notification: 通知对象
        
        Returns:
            DeliveryResult: 交付结果
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接
        
        Returns:
            连接是否正常
        """
        pass
    
    async def shutdown(self) -> None:
        """关闭插件，释放资源"""
        pass


class RuleFilterPlugin(_RulePluginMixin):
    """规则引擎过滤器插件基类
    
    所有规则引擎过滤器插件必须继承此类，并实现必要的方法。
    同时实现了 IPlugin 接口，与核心插件体系统一。
    
    注意：此类与核心的 FilterPluginBase 是不同的体系，
    本类处理 ReadingSet 对象，FilterPluginBase 处理 Reading 对象。
    
    Attributes:
        __plugin_name__: 插件名称（子类必须定义）
        __plugin_type__: 插件类型（固定为 "rule_engine.filter"）
    """
    
    __plugin_name__: str = ""
    __plugin_type__: str = "rule_engine.filter"
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
    
    @classmethod
    @abstractmethod
    def plugin_info(cls) -> PluginMetadata:
        """返回插件元数据
        
        Returns:
            PluginMetadata: 插件元数据对象
        """
        pass
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        """返回配置项 JSON Schema
        
        Returns:
            JSON Schema 字典
        """
        return {}
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件
        
        Args:
            config: 插件配置
        """
        pass
    
    @abstractmethod
    def filter(self, data: ReadingSet) -> ReadingSet:
        """过滤数据
        
        Args:
            data: 输入数据集
        
        Returns:
            ReadingSet: 过滤后的数据集
        """
        pass
    
    def filter_batch(self, data_list: list) -> list:
        """批量过滤数据
        
        Args:
            data_list: 输入数据集列表
        
        Returns:
            List[ReadingSet]: 过滤后的数据集列表
        """
        return [self.filter(data) for data in data_list]
    
    def shutdown(self) -> None:
        """关闭插件，释放资源"""
        pass
