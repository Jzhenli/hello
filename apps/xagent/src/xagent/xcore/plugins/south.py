"""South Plugin - Base class for data acquisition plugins"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional
import time

from ..storage.interface import Reading
from ..core.event_bus import EventBus, EventType, Event
from ..core.plugin_loader import PluginType
from ..core.exceptions import PluginStartError
from ..core.interfaces import IPlugin
from ..transform import StandardDataPoint

logger = logging.getLogger(__name__)


class SouthPluginBase(IPlugin):
    """
    南向插件基类
    
    所有南向插件必须继承此类，并实现必要的抽象方法。
    实现 IPlugin 接口，与规则引擎插件体系统一生命周期管理。
    """
    
    __plugin_type__ = PluginType.SOUTH.value
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
        self._device_online = False
        self._asset_name = config.get("asset_name", "unknown")
        self._service_name = self.__plugin_name__ or self.__class__.__name__
        
        self._data_converter = self._create_data_converter()
        
        if event_bus:
            event_bus.subscribe(EventType.COMMAND_RECEIVED, self._handle_command_event)
    
    @property
    def plugin_type(self) -> str:
        return self.__plugin_type__
    
    @property
    def plugin_name(self) -> str:
        return self._service_name
    
    def initialize(self, config: Dict[str, Any]) -> None:
        pass

    @staticmethod
    def _get_point_config(point: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取点位配置字段（优先从 config 子对象读取，兼容顶层读取）"""
        point_config = point.get("config", {})
        if key in point_config:
            return point_config[key]
        if key in point:
            return point[key]
        return default
    
    def shutdown(self) -> None:
        if self._running:
            self._running = False

    @abstractmethod
    def _create_data_converter(self) -> Any:
        """
        创建数据转换器
        
        返回一个符合 DataConverter 协议的对象。
        子类必须实现此方法。
        
        Returns:
            数据转换器实例
        """
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        连接设备
        
        Returns:
            连接是否成功
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开设备连接"""
        pass

    @abstractmethod
    async def poll(self) -> List[Reading]:
        """
        轮询数据
        
        Returns:
            Reading 对象列表
        """
        pass

    async def start(self) -> None:
        """启动插件"""
        if self._running:
            return
        
        success = await self.connect()
        if success:
            self._running = True
            logger.info(f"South plugin started: {self._service_name}")
        else:
            raise PluginStartError(self._service_name, "Failed to connect")

    async def stop(self) -> None:
        """停止插件"""
        if not self._running:
            return
        
        await self.disconnect()
        self._running = False
        logger.info(f"South plugin stopped: {self._service_name}")

    async def write_setpoint(self, asset: str, point: str, value: Any) -> bool:
        """
        写入点位值
        
        Args:
            asset: 资产名称
            point: 点位名称
            value: 写入值
        
        Returns:
            写入是否成功
        """
        logger.warning(f"write_setpoint not implemented for {self._service_name}")
        return False

    def get_device_status(self) -> str:
        """
        获取设备状态
        
        Returns:
            "online" 或 "offline"
        """
        if self._running and self._connected and self._device_online:
            return "online"
        return "offline"
    
    async def _create_offline_reading(self) -> List[Reading]:
        """
        创建离线 Reading 并写入存储和发布事件
        
        当设备不可达时调用，创建一个所有点位值为 None 的 Reading，
        自动写入存储并发布 DATA_RECEIVED 事件。
        
        Returns:
            包含单个离线 Reading 的列表
        """
        raw_data = {point.get("name", ""): None for point in self.config.get("points", [])}
        points_data = self.convert_data(raw_data, self.config.get("points", []), context={
            "device_id": self._asset_name,
            "connection_status": "disconnected"
        })
        
        if points_data:
            from ..transform import StandardDataPoint
            standard_points = [StandardDataPoint(**p) for p in points_data]
            reading = self.create_reading_from_points(standard_points)
        else:
            reading = self.create_reading(raw_data)
        
        reading.device_status = "offline"
        
        if self.storage:
            await self.storage.write(reading)
        
        if self.event_bus:
            event = Event(
                event_type=EventType.DATA_RECEIVED,
                data=reading.to_dict()
            )
            await self.event_bus.publish(event)
        
        return [reading]

    def create_reading(
        self, 
        data: Dict[str, Any], 
        tags: Optional[List[str]] = None
    ) -> Reading:
        """
        创建 Reading 对象
        
        Args:
            data: 数据字典
            tags: 标签列表
        
        Returns:
            Reading 对象
        """
        reading = Reading(
            asset=self._asset_name,
            timestamp=time.time(),
            service_name=self._service_name,
            data=data,
            tags=tags or []
        )
        reading.device_status = self.get_device_status()
        return reading

    def create_reading_from_points(
        self, 
        points: List[StandardDataPoint]
    ) -> Reading:
        """
        从标准数据点创建 Reading
        
        Args:
            points: 标准数据点列表
        
        Returns:
            Reading 对象
        """
        data = {p.point_name: p.value for p in points}
        reading = self.create_reading(data)
        reading.standard_points = [p.to_dict() for p in points]
        reading.device_status = self.get_device_status()
        return reading

    async def publish_readings(self, readings: List[Reading]) -> None:
        """
        发布数据接收事件
        
        Args:
            readings: Reading 列表
        """
        for reading in readings:
            event = Event(
                event_type=EventType.DATA_RECEIVED,
                data=reading.to_dict()
            )
            await self.event_bus.publish(event)

    async def on_write_completed(
        self,
        asset: str,
        data: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        写入完成回调
        
        Args:
            asset: 资产名称
            data: 写入数据
            tags: 标签列表
        
        Returns:
            是否成功
        """
        reading = self.create_reading(data, tags)
        
        if self.storage:
            await self.storage.write(reading)
            if hasattr(self.storage, 'flush'):
                await self.storage.flush()
        
        event = Event(
            event_type=EventType.WRITE_COMPLETED,
            data={
                "asset": asset,
                "service_name": self._service_name,
                "reading": reading.to_dict()
            }
        )
        await self.event_bus.publish(event)
        
        return True

    def convert_data(
        self,
        raw_data: Dict[str, Any],
        point_configs: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        使用转换器转换数据
        
        Args:
            raw_data: 原始数据字典
            point_configs: 点位配置列表
            context: 上下文信息
        
        Returns:
            标准数据点字典列表
        """
        if not self._data_converter:
            logger.warning(f"No data converter for {self._service_name}")
            return []
        
        context = context or {}
        if "device_id" not in context:
            context["device_id"] = self._asset_name
        if "connection_status" not in context:
            context["connection_status"] = "connected" if self._connected else "disconnected"
        
        return self._data_converter.convert(raw_data, point_configs, context)

    async def _handle_command_event(self, event: Event) -> None:
        """
        处理命令事件
        
        Args:
            event: 命令事件
        """
        try:
            command_data = event.data
            asset = command_data.get("asset")
            data = command_data.get("data")
            
            if not asset or not data:
                logger.warning("Invalid command event: missing asset or data")
                return
            
            if asset != self._asset_name:
                logger.debug(f"Ignoring command for asset {asset}, this plugin handles {self._asset_name}")
                return
            
            logger.info(f"Received command for asset {asset}: {data}")
            
            written_points = {}
            
            if "value" in data:
                success = await self.write_setpoint(asset, asset, data["value"])
                if success:
                    written_points[asset] = data["value"]
            else:
                for point_name, value in data.items():
                    success = await self.write_setpoint(asset, point_name, value)
                    if success:
                        written_points[point_name] = value
            
            if written_points:
                await self.on_write_completed(asset, written_points)
                
        except Exception as e:
            logger.error(f"Error handling command event: {e}", exc_info=True)


class ModbusPluginMixin:
    """Mixin for Modbus-based south plugins"""
    
    async def read_coils(self, address: int, count: int) -> List[bool]:
        raise NotImplementedError
    
    async def read_discrete_inputs(self, address: int, count: int) -> List[bool]:
        raise NotImplementedError
    
    async def read_holding_registers(self, address: int, count: int) -> List[int]:
        raise NotImplementedError
    
    async def read_input_registers(self, address: int, count: int) -> List[int]:
        raise NotImplementedError
    
    async def write_single_coil(self, address: int, value: bool) -> bool:
        raise NotImplementedError
    
    async def write_single_register(self, address: int, value: int) -> bool:
        raise NotImplementedError
