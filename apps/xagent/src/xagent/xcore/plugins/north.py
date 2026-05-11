"""North Plugin - Base class for data upload plugins"""

import logging
import time
import warnings
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from ..storage.interface import Reading
from ..core.event_bus import EventBus, EventType, Event
from ..core.plugin_loader import PluginType
from ..core.exceptions import PluginStartError
from ..core.interfaces import IPlugin

logger = logging.getLogger(__name__)


class NorthPluginBase(IPlugin):
    """
    北向插件基类
    
    所有北向插件必须继承此类，并实现必要的抽象方法。
    实现 IPlugin 接口，与规则引擎插件体系统一生命周期管理。
    """
    
    __plugin_type__ = PluginType.NORTH.value
    __plugin_name__: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        """
        初始化插件
        
        Args:
            config: 插件配置字典
            storage: 存储对象（WriteBehindBuffer）
            event_bus: 事件总线
        """
        self.config = config
        self.storage = storage
        self.event_bus = event_bus
        
        self._running = False
        self._connected = False
        self._service_name = self.__plugin_name__ or self.__class__.__name__
        
        self._data_adapter = self._create_data_adapter()
        
        self._immediate_upload = config.get("immediate_upload", True)
        self._batch_size = config.get("batch_size", 100)
        self._interval = config.get("interval", 5)
        
        if self._immediate_upload and event_bus:
            event_bus.subscribe(EventType.WRITE_COMPLETED, self._handle_write_completed)
            logger.info(f"Immediate upload enabled for {self._service_name}")
    
    @property
    def plugin_type(self) -> str:
        return self.__plugin_type__
    
    @property
    def plugin_name(self) -> str:
        return self._service_name
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def shutdown(self) -> None:
        if self._running:
            self._running = False

    @abstractmethod
    def _create_data_adapter(self) -> Any:
        """
        创建数据适配器
        
        返回一个符合 DataAdapter 协议的对象。
        子类必须实现此方法。
        
        Returns:
            数据适配器实例
        """
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        连接云端/外部系统
        
        Returns:
            连接是否成功
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send(self, readings: List[Reading]) -> int:
        """
        发送数据
        
        Args:
            readings: Reading 对象列表
        
        Returns:
            成功发送的数量
        """
        pass

    async def start(self) -> None:
        """启动插件"""
        if self._running:
            return
        
        success = await self.connect()
        if success:
            self._running = True
            logger.info(f"North plugin started: {self._service_name}")
        else:
            raise PluginStartError(self._service_name, "Failed to connect")

    async def stop(self) -> None:
        """停止插件"""
        if not self._running:
            return
        
        await self.disconnect()
        self._running = False
        logger.info(f"North plugin stopped: {self._service_name}")

    async def handle_command(self, command_data: Dict[str, Any]) -> bool:
        """
        处理下行命令
        
        Args:
            command_data: 命令数据
        
        Returns:
            处理是否成功
        """
        logger.warning(f"handle_command not implemented for {self._service_name}")
        return False

    async def fetch_and_send(self, batch_size: int = 100) -> int:
        """
        从存储获取数据并发送
        
        Args:
            batch_size: 批量大小
        
        Returns:
            发送数量
        """
        if not self.storage:
            return 0
        
        readings = await self.storage.query(limit=batch_size)
        if not readings:
            return 0
        
        return await self.send(readings)

    def adapt_readings(
        self, 
        readings: List[Reading], 
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        使用适配器转换数据
        
        Args:
            readings: Reading 列表
            context: 上下文信息
        
        Returns:
            适配后的数据
        """
        if not self._data_adapter:
            logger.warning(f"No data adapter for {self._service_name}")
            return None
        
        context = context or {}
        if "timestamp" not in context:
            context["timestamp"] = time.time()
        
        return self._data_adapter.adapt_upload(readings, context)

    def adapt_command(
        self, 
        command_data: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        使用适配器转换命令
        
        Args:
            command_data: 命令数据
            context: 上下文信息
        
        Returns:
            适配后的命令
        """
        if not self._data_adapter:
            return command_data
        
        context = context or {}
        return self._data_adapter.adapt_command(command_data, context)

    def parse_response(
        self, 
        response: Any, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用适配器解析响应
        
        Args:
            response: 原始响应
            context: 上下文信息
        
        Returns:
            解析后的数据字典
        """
        if not self._data_adapter:
            return {"raw": response}
        
        context = context or {}
        return self._data_adapter.parse_response(response, context)

    async def _handle_write_completed(self, event: Event) -> None:
        """处理写入完成事件 - 触发立即上传"""
        if not self._running or not self._immediate_upload:
            return
        
        reading_dict = event.data.get("reading")
        if not reading_dict:
            return
        
        try:
            reading = Reading.from_dict(reading_dict)
            await self.trigger_immediate_upload([reading])
        except Exception as e:
            logger.error(f"Error handling WRITE_COMPLETED event: {e}")

    async def trigger_immediate_upload(self, readings: List[Reading]) -> int:
        """触发立即上传"""
        if not self._running:
            return 0
        
        return await self.send(readings)


class MQTTNorthPlugin(NorthPluginBase):
    """[DEPRECATED] Use plugins/north/mqtt_client plugin instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "MQTTNorthPlugin is deprecated. Use the standalone plugins/north/mqtt_client plugin instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
    
    async def publish(self, topic: str, payload: str, qos: int = 0) -> bool:
        raise NotImplementedError
    
    async def subscribe(self, topic: str, callback) -> None:
        raise NotImplementedError


class HTTPNorthPlugin(NorthPluginBase):
    """[DEPRECATED] Reserved for future standalone HTTP north plugin."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "HTTPNorthPlugin is deprecated and not fully implemented.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
    
    async def post(self, url: str, data: Any, headers: Optional[Dict] = None) -> Any:
        raise NotImplementedError
