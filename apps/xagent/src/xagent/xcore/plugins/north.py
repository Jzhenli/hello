"""North Plugin - Base class for data upload plugins (Template Method Pattern)"""

import asyncio
import logging
import time
import warnings
from abc import abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..storage.interface import Reading
from ..core.event_bus import EventBus, EventType, Event
from ..core.plugin_loader import PluginType
from ..core.exceptions import PluginStartError
from ..core.interfaces import IPlugin

if TYPE_CHECKING:
    from ..statistics import StatisticsManager

logger = logging.getLogger(__name__)


class NorthPluginBase(IPlugin):
    """
    北向插件基类 - 模板方法模式
    
    基类提供：
    - 生命周期管理（start/stop）
    - 上传循环模板
    - 重连策略（指数退避）
    - 数据去重
    - 即时上传支持
    
    子类只需实现钩子方法：
    - _do_connect(): 协议专有连接逻辑
    - _do_disconnect(): 协议专有断开逻辑
    - _do_send(): 协议专有发送逻辑
    - _create_data_adapter(): 创建数据适配器
    
    可选重写：
    - _do_subscribe(): 订阅命令主题
    - _do_handle_raw_command(): 处理原始命令
    - _supports_command(): 是否支持命令接收
    - _is_connection_error(): 判断连接错误
    """
    
    __plugin_type__ = PluginType.NORTH.value
    __plugin_name__: Optional[str] = None
    
    DEFAULT_IMMEDIATE_UPLOAD = True
    DEFAULT_BATCH_SIZE = 100
    DEFAULT_INTERVAL = 5
    DEFAULT_RETRY_COUNT = 3
    DEFAULT_RETRY_DELAY = 1
    DEFAULT_RECONNECT_INTERVAL = 5
    DEFAULT_RECONNECT_MAX_DELAY = 60
    
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
        
        self._service_name = config.get("channel_id") or self.__plugin_name__ or self.__class__.__name__
        
        self._data_adapter = self._create_data_adapter()

        upload = config.get("upload_strategy", {})
        self._immediate_upload = upload.get("immediate_upload", self.DEFAULT_IMMEDIATE_UPLOAD)
        self._batch_size = upload.get("batch_size", self.DEFAULT_BATCH_SIZE)
        self._interval = upload.get("interval", self.DEFAULT_INTERVAL)
        self._retry_count = upload.get("retry_count", self.DEFAULT_RETRY_COUNT)
        self._retry_delay = upload.get("retry_delay", self.DEFAULT_RETRY_DELAY)
        self._reconnect_interval = upload.get("reconnect_interval", self.DEFAULT_RECONNECT_INTERVAL)
        self._reconnect_max_delay = upload.get("reconnect_max_delay", self.DEFAULT_RECONNECT_MAX_DELAY)
        self._reconnect_attempts = 0
        self._reconnect_lock = asyncio.Lock()
        
        self._upload_task: Optional[asyncio.Task] = None
        self._command_task: Optional[asyncio.Task] = None
        
        self._stats_manager = None
        
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
    
    def set_stats_manager(self, stats_manager: "StatisticsManager") -> None:
        """设置统计管理器
        
        Args:
            stats_manager: StatisticsManager 实例
        """
        self._stats_manager = stats_manager
        logger.debug(f"Stats manager set for {self._service_name}")
    
    # ===== 子类必须实现的钩子方法 =====
    
    @abstractmethod
    def _create_data_adapter(self) -> Any:
        """创建数据适配器
        
        返回一个符合 DataAdapter 协议的对象。
        子类必须实现此方法。
        
        Returns:
            数据适配器实例
        """
        pass
    
    @abstractmethod
    async def _do_connect(self) -> bool:
        """执行协议专有的连接逻辑
        
        Returns:
            连接是否成功
        """
        pass
    
    @abstractmethod
    async def _do_disconnect(self) -> None:
        """执行协议专有的断开逻辑"""
        pass
    
    @abstractmethod
    async def _do_send(self, payload: Any) -> bool:
        """执行协议专有的发送逻辑
        
        Args:
            payload: 适配后的数据负载
            
        Returns:
            发送是否成功
        """
        pass
    
    # ===== 子类可选重写的钩子方法 =====
    
    async def _do_subscribe(self) -> None:
        """订阅命令主题（可选）
        
        MQTT 等需要订阅的协议重写此方法。
        在此方法中实现命令监听循环。
        """
        pass
    
    async def _do_handle_raw_command(self, raw_data: Any) -> None:
        """处理原始命令数据（可选）
        
        Args:
            raw_data: 原始命令数据（MQTT Message、UDP bytes 等）
        """
        pass
    
    def _supports_command(self) -> bool:
        """是否支持命令接收
        
        Returns:
            默认返回 True，不支持命令的插件重写返回 False
        """
        return True
    
    def _is_connection_error(self, exc: Exception) -> bool:
        """判断是否为连接错误
        
        Args:
            exc: 异常对象
            
        Returns:
            是否为连接错误
        """
        return isinstance(exc, ConnectionError)
    
    async def _on_connected(self) -> None:
        """连接成功回调（子类可重写）"""
        pass
    
    async def _on_disconnected(self) -> None:
        """断开连接回调（子类可重写）"""
        pass
    
    # ===== 基类提供的模板方法 =====
    
    async def connect(self) -> bool:
        """连接模板：重连策略 + 钩子调用
        
        Returns:
            连接是否成功
        """
        if self._connected:
            return True
        
        try:
            logger.info(f"Connecting {self._service_name}...")
            success = await self._do_connect()
            if success:
                self._connected = True
                self._reconnect_attempts = 0
                await self._on_connected()
                logger.info(f"{self._service_name} connected successfully")
            return success
        except Exception as e:
            logger.error(f"{self._service_name} connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """断开连接模板"""
        if not self._connected:
            return
        
        self._connected = False
        
        try:
            await self._do_disconnect()
            await self._on_disconnected()
            logger.info(f"{self._service_name} disconnected")
        except Exception as e:
            logger.error(f"{self._service_name} disconnect error: {e}")
    
    async def start(self) -> None:
        """启动模板：连接 + 上传循环 + 命令监听"""
        if self._running:
            logger.info(f"{self._service_name} already running")
            return
        
        success = await self.connect()
        if not success:
            raise PluginStartError(self._service_name, "Failed to connect")
        
        self._running = True
        self._upload_task = asyncio.create_task(self._upload_loop())
        
        if self._supports_command():
            self._command_task = asyncio.create_task(self._command_loop())
        
        logger.info(f"North plugin started: {self._service_name}")
    
    async def stop(self) -> None:
        """停止模板"""
        if not self._running:
            return
        
        self._running = False
        
        for task in [self._upload_task, self._command_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._upload_task = None
        self._command_task = None
        
        await self.disconnect()
        logger.info(f"North plugin stopped: {self._service_name}")
    
    async def _upload_loop(self) -> None:
        """上传循环模板：取数据 → 适配 → 发送 → 重试"""
        logger.info(f"{self._service_name} upload loop started, interval={self._interval}s")
        
        while self._running:
            try:
                if not self._connected:
                    if not await self._reconnect():
                        await asyncio.sleep(self._reconnect_interval)
                        continue
                
                await self.fetch_and_send(self._batch_size)
                await asyncio.sleep(self._interval)
                
            except asyncio.CancelledError:
                logger.info(f"{self._service_name} upload loop cancelled")
                break
            except Exception as e:
                logger.error(f"{self._service_name} upload loop error: {e}")
                await asyncio.sleep(self._reconnect_interval)
    
    async def _command_loop(self) -> None:
        """命令循环模板：调用子类的订阅实现"""
        logger.info(f"{self._service_name} command loop started")
        
        try:
            await self._do_subscribe()
        except asyncio.CancelledError:
            logger.info(f"{self._service_name} command loop cancelled")
        except Exception as e:
            logger.error(f"{self._service_name} command loop error: {e}")
    
    async def _reconnect(self) -> bool:
        """重连模板：指数退避
        
        Returns:
            重连是否成功
        """
        async with self._reconnect_lock:
            if self._connected:
                return True
            
            self._reconnect_attempts += 1
            delay = min(
                self._reconnect_interval * (2 ** (self._reconnect_attempts - 1)),
                self._reconnect_max_delay
            )
            
            logger.warning(
                f"{self._service_name} reconnecting in {delay}s "
                f"(attempt {self._reconnect_attempts})"
            )
            
            await asyncio.sleep(delay)
            await self.disconnect()
            
            success = await self.connect()
            if success:
                logger.info(f"{self._service_name} reconnected successfully")
            else:
                logger.warning(
                    f"{self._service_name} reconnect attempt {self._reconnect_attempts} failed"
                )
            
            return success
    
    async def send(self, readings: List[Reading]) -> int:
        """发送数据模板：适配 → 序列化 → 发送
        
        Args:
            readings: Reading 对象列表
            
        Returns:
            成功发送的数量
        """
        if not self._connected:
            if not await self._reconnect():
                return 0
        
        if not readings:
            return 0
        
        logger.debug(f"{self._service_name} sending {len(readings)} readings")
        
        device_status_map = {
            r.asset: r.device_status
            for r in readings
            if r.device_status
        }
        
        context = {
            "timestamp": time.time(),
            "device_status_map": device_status_map
        }
        
        payload = self.adapt_readings(readings, context)
        if payload is None:
            logger.warning(f"{self._service_name} failed to adapt readings")
            return 0
        
        success = await self._send_with_retry(payload)
        sent_count = len(readings) if success else 0
        
        if self._stats_manager:
            await self._stats_manager.record_channel_stats(
                self._service_name,
                sent_count,
                success=success
            )
        
        return sent_count
    
    async def _send_with_retry(self, payload: Any) -> bool:
        """带重试的发送
        
        Args:
            payload: 适配后的数据负载
            
        Returns:
            发送是否成功
        """
        for attempt in range(self._retry_count):
            try:
                return await self._do_send(payload)
            except Exception as e:
                if self._is_connection_error(e):
                    self._connected = False
                    logger.warning(f"{self._service_name} connection lost during send")
                    return False
                
                if attempt < self._retry_count - 1:
                    logger.warning(
                        f"{self._service_name} send attempt {attempt + 1} failed: {e}, retrying..."
                    )
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(
                        f"{self._service_name} send failed after {self._retry_count} attempts: {e}"
                    )
        
        return False
    
    async def fetch_and_send(self, batch_size: int = 100) -> int:
        """从存储获取数据并发送
        
        Args:
            batch_size: 批量大小
            
        Returns:
            发送数量
        """
        if not self.storage:
            logger.warning(f"{self._service_name} storage not available")
            return 0
        
        try:
            readings = await self.storage.query(limit=batch_size * 2)
            
            if not readings:
                return 0
            
            latest = self._dedup_latest_readings(readings, batch_size)
            logger.debug(
                f"{self._service_name} fetched {len(readings)} readings, "
                f"deduplicated to {len(latest)}"
            )
            
            return await self.send(latest)
            
        except Exception as e:
            logger.error(f"{self._service_name} fetch_and_send error: {e}")
            return 0
    
    # ===== 数据适配方法 =====
    
    def adapt_readings(
        self, 
        readings: List[Reading], 
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """使用适配器转换数据
        
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
        """使用适配器转换命令
        
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
        """使用适配器解析响应
        
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
    
    # ===== 即时上传支持 =====
    
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
        """触发立即上传
        
        Args:
            readings: Reading 列表
            
        Returns:
            发送数量
        """
        if not self._running:
            return 0
        
        return await self.send(readings)
    
    # ===== 命令处理 =====
    
    async def handle_command(self, command_data: Dict[str, Any]) -> bool:
        """处理下行命令
        
        Args:
            command_data: 命令数据
        
        Returns:
            处理是否成功
        """
        try:
            adapted = self.adapt_command(command_data, {"timestamp": time.time()})
            
            asset = adapted.get("asset", command_data.get("asset"))
            data = adapted.get("data", command_data.get("data", {}))
            
            await self.event_bus.publish(Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={"asset": asset, "data": data}
            ))
            
            logger.info(f"{self._service_name} command processed for {asset}")
            return True
            
        except Exception as e:
            logger.error(f"{self._service_name} command handling error: {e}")
            return False
    
    # ===== 辅助方法 =====
    
    @staticmethod
    def _dedup_latest_readings(readings: List[Reading], limit: int) -> List[Reading]:
        """按 asset 去重，保留每个 asset 时间戳最新的 Reading
        
        Args:
            readings: Reading 列表
            limit: 最大返回数量
            
        Returns:
            去重后的 Reading 列表
        """
        latest_by_asset: Dict[str, Reading] = {}
        for reading in readings:
            asset = reading.asset
            if asset not in latest_by_asset or reading.timestamp > latest_by_asset[asset].timestamp:
                latest_by_asset[asset] = reading
        return list(latest_by_asset.values())[:limit]


class MQTTNorthPlugin(NorthPluginBase):
    """[DEPRECATED] Use plugins/north/mqtt_client plugin instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "MQTTNorthPlugin is deprecated. Use the standalone plugins/north/mqtt_client plugin instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
    
    async def _do_connect(self) -> bool:
        raise NotImplementedError
    
    async def _do_disconnect(self) -> None:
        raise NotImplementedError
    
    async def _do_send(self, payload: Any) -> bool:
        raise NotImplementedError
    
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
    
    async def _do_connect(self) -> bool:
        raise NotImplementedError
    
    async def _do_disconnect(self) -> None:
        raise NotImplementedError
    
    async def _do_send(self, payload: Any) -> bool:
        raise NotImplementedError
    
    async def post(self, url: str, data: Any, headers: Optional[Dict] = None) -> Any:
        raise NotImplementedError
