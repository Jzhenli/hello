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
    
    扩展点：
    - test_connection(): 协议相关的连通性测试，由 Service 层委托调用
    - get_channel_info(): 返回通道运行时信息，供编排层查询
    - build_plugin_config(): 从通道数据库记录构建插件配置，供编排层使用
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
        self._channel_id: Optional[int] = config.get("channel_id")
        
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
    
    @property
    def channel_id(self) -> Optional[int]:
        return self._channel_id
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass
    
    def shutdown(self) -> None:
        if self._running:
            self._running = False

    @abstractmethod
    def _create_data_adapter(self) -> Any:
        pass

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def send(self, readings: List[Reading]) -> int:
        pass

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试与远端的连通性
        
        子类应覆写此方法实现协议相关的连通性测试。
        默认实现尝试 connect + disconnect。
        
        Returns:
            {"success": bool, "message": str, "latency": float|None, "details": dict|None}
        """
        start = time.time()
        try:
            ok = await self.connect()
            latency = round((time.time() - start) * 1000, 2)
            if ok:
                await self.disconnect()
                return {"success": True, "message": "Connection test passed", "latency": latency}
            return {"success": False, "message": "Connection refused", "latency": latency}
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            return {"success": False, "message": str(e), "latency": latency}

    def get_channel_info(self) -> Dict[str, Any]:
        """
        返回通道运行时信息，供编排层查询
        
        子类可覆写此方法返回协议特有的运行时信息。
        """
        return {
            "plugin_name": self.__plugin_name__,
            "channel_id": self._channel_id,
            "connected": self._connected,
            "running": self._running,
        }

    @classmethod
    def build_plugin_config(cls, channel_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        从通道数据库记录构建插件配置
        
        编排层调用此方法将数据库中的通道记录转换为插件构造函数所需的 config 字典。
        子类应覆写此方法以提取协议特有的配置字段。
        
        Args:
            channel_record: north_channel_registry 的一行记录（dict）
        
        Returns:
            插件配置字典
        """
        config: Dict[str, Any] = {}
        if channel_record.get("config"):
            config.update(channel_record["config"])
        config["channel_id"] = channel_record.get("id")
        for key in ("remote_host", "remote_port", "local_port"):
            if channel_record.get(key) is not None:
                config[key] = channel_record[key]
        return config

    async def start(self) -> None:
        if self._running:
            return
        
        success = await self.connect()
        if success:
            self._running = True
            logger.info(f"North plugin started: {self._service_name}")
        else:
            raise PluginStartError(self._service_name, "Failed to connect")

    async def stop(self) -> None:
        if not self._running:
            return
        
        await self.disconnect()
        self._running = False
        logger.info(f"North plugin stopped: {self._service_name}")

    async def handle_command(self, command_data: Dict[str, Any]) -> bool:
        logger.warning(f"handle_command not implemented for {self._service_name}")
        return False

    async def fetch_and_send(self, batch_size: int = 100) -> int:
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
        if not self._data_adapter:
            return command_data
        
        context = context or {}
        return self._data_adapter.adapt_command(command_data, context)

    def parse_response(
        self, 
        response: Any, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self._data_adapter:
            return {"raw": response}
        
        context = context or {}
        return self._data_adapter.parse_response(response, context)

    async def _handle_write_completed(self, event: Event) -> None:
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
        if not self._running:
            return 0
        
        return await self.send(readings)
