"""BACnet South Plugin - Data acquisition and control for BACnet/IP devices using bacpypes3

心跳检测模式说明：
1. device_object (推荐，默认)：
   - 读取设备对象的标准属性（如 objectName, systemStatus）
   - 这是 BACnet 协议的标准做法，所有设备都必须支持
   - 配置示例：
     heartbeat_mode: "device_object"
     heartbeat_property: "objectName"  # 或 "systemStatus", "vendorName" 等
     heartbeat_timeout: 5.0
     heartbeat_retries: 3

2. none：
   - 不单独做心跳检测
   - 仅依赖连接状态和数据读取成功率
   - 配置示例：
     heartbeat_mode: "none"
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from xagent.xcore.plugins.south import SouthPluginBase
from xagent.xcore.storage.interface import Reading
from xagent.xcore.transform import StandardDataPoint

from .converter import BACnetConverter
from .constants import (
    DEFAULT_PORT,
    DEFAULT_DEVICE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL,
    HEARTBEAT_MODE_DEVICE_OBJECT,
    HEARTBEAT_MODE_NONE,
    DEFAULT_HEARTBEAT_MODE,
    DEFAULT_HEARTBEAT_PROPERTY,
    DEFAULT_HEARTBEAT_TIMEOUT,
    DEFAULT_HEARTBEAT_RETRIES,
)

logger = logging.getLogger(__name__)

BACNET_AVAILABLE = None
_Application = None
_DeviceObject = None
_NetworkPortObject = None
_ErrorRejectAbortNack = None


def _check_bacnet_available():
    global BACNET_AVAILABLE, _Application, _DeviceObject
    global _NetworkPortObject, _ErrorRejectAbortNack

    if BACNET_AVAILABLE is not None:
        return BACNET_AVAILABLE

    try:
        from bacpypes3.app import Application
        from bacpypes3.local.device import DeviceObject
        from bacpypes3.local.networkport import NetworkPortObject
        from bacpypes3.apdu import ErrorRejectAbortNack

        _Application = Application
        _DeviceObject = DeviceObject
        _NetworkPortObject = NetworkPortObject
        _ErrorRejectAbortNack = ErrorRejectAbortNack
        BACNET_AVAILABLE = True
    except ImportError:
        BACNET_AVAILABLE = False
        logger.warning("bacpypes3 not installed, BACnet plugin will not work. Install with: pip install bacpypes3")
    return BACNET_AVAILABLE


class BACnetPlugin(SouthPluginBase):
    """
    BACnet 南向插件
    
    支持 BACnet/IP 协议，可读写以下对象类型：
    - Analog Input/Output/Value
    - Binary Input/Output/Value
    - Multi-State Input/Output/Value
    
    心跳检测模式：
    - device_object: 读取设备对象的标准属性（推荐，默认）
    - none: 不单独做心跳检测
    """
    
    __plugin_name__ = "bacnet"
    
    POINT_TIMEOUT = 3.0
    POINT_RETRIES = 2
    POINT_RETRY_INTERVAL = 0.5
    RECONNECT_CHECK_INTERVAL = 5
    
    DEFAULT_MAX_CONCURRENT_READS = 20
    DEFAULT_BATCH_READ_ENABLED = True
    DEFAULT_BATCH_SIZE = 50
    
    def _create_data_converter(self) -> BACnetConverter:
        """创建数据转换器"""
        return BACnetConverter()
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: Any):
        super().__init__(config, storage, event_bus)
        
        self._host = config.get("host", "localhost")
        self._port = config.get("port", DEFAULT_PORT)
        self._device_id = config.get("device_id", DEFAULT_DEVICE_ID)
        self._timeout = config.get("timeout", DEFAULT_TIMEOUT)
        self._interval = config.get("interval", DEFAULT_INTERVAL)
        self._reconnect_interval = config.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL)
        
        self._heartbeat_mode = config.get("heartbeat_mode", DEFAULT_HEARTBEAT_MODE)
        self._heartbeat_timeout = config.get("heartbeat_timeout", DEFAULT_HEARTBEAT_TIMEOUT)
        self._heartbeat_retries = config.get("heartbeat_retries", DEFAULT_HEARTBEAT_RETRIES)
        self._heartbeat_property = config.get("heartbeat_property", DEFAULT_HEARTBEAT_PROPERTY)
        
        self._point_timeout = config.get("point_timeout", self.POINT_TIMEOUT)
        self._point_retries = config.get("point_retries", self.POINT_RETRIES)
        
        self._max_concurrent_reads = config.get("max_concurrent_reads", self.DEFAULT_MAX_CONCURRENT_READS)
        self._batch_read_enabled = config.get("batch_read_enabled", self.DEFAULT_BATCH_READ_ENABLED)
        self._batch_size = config.get("batch_size", self.DEFAULT_BATCH_SIZE)
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._device_supports_batch: Optional[bool] = None
        
        self._performance_stats = {
            "total_polls": 0,
            "total_points_read": 0,
            "successful_points_read": 0,
            "total_time": 0.0,
            "avg_poll_time": 0.0,
            "last_poll_time": 0.0,
            "success_rate": 0.0
        }
        
        self._points: List[Dict[str, Any]] = config.get("points", [])
        self._app: Any = None
        self._device_online = False
        self._offline_counter = 0
        self._last_reconnect_time: float = 0.0
        self._point_order: List[str] = []
        self._point_map: Dict[str, Dict[str, Any]] = {}
        self._write_points: Dict[str, Dict[str, Any]] = {}
        
        if not self._points:
            logger.warning(f"No points configured for BACnet device {self._asset_name}")
    
    async def connect(self) -> bool:
        if not _check_bacnet_available():
            logger.error("bacpypes3 is not installed. Install it with: pip install bacpypes3")
            return False
        
        try:
            logger.info(f"Connecting to BACnet device at {self._host}:{self._port}...")
            
            if not await self._create_client():
                logger.error(f"Failed to create BACnet client for {self._host}:{self._port}")
                self._connected = False
                await self._create_offline_reading()
                return False
            
            if await self._test_connection():
                self._connected = True
                self._device_online = True
                self._offline_counter = 0
                
                self._setup_point_mappings()
                
                logger.info(f"Connected to BACnet device {self._asset_name}")
                return True
            else:
                logger.error(f"Failed to connect to BACnet device at {self._host}:{self._port}")
                self._connected = False
                await self._create_offline_reading()
                return False
                
        except Exception as e:
            logger.error(f"BACnet connection error: {e}")
            self._connected = False
            await self._create_offline_reading()
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._app:
            try:
                if hasattr(self._app, 'close'):
                    await self._app.close()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self._app = None
                self._connected = False
                self._device_online = False
                self._offline_counter = 0
                self._point_order.clear()
                self._point_map.clear()
                self._write_points.clear()
                logger.info(f"Disconnected from BACnet device {self._asset_name}")
    
    async def poll(self) -> List[Reading]:
        """轮询数据"""
        poll_start = time.time()
        
        if not await self._ensure_connection():
            return await self._create_offline_reading()
        
        if not self._point_order:
            logger.warning("No points configured")
            return []
        
        try:
            if not await self._check_heartbeat():
                self._device_online = False
                self._connected = False
                logger.warning("Heartbeat check failed, device marked offline")
                
                if self._app:
                    try:
                        if hasattr(self._app, 'close'):
                            await self._app.close()
                    except Exception:
                        logger.debug("Error closing BACnet app during heartbeat failure", exc_info=True)
                    finally:
                        self._app = None
                
                return await self._create_offline_reading()
            
            self._device_online = True
            self._offline_counter = 0
            
            if self._device_supports_batch is None and self._batch_read_enabled:
                self._device_supports_batch = await self._probe_device_capabilities()
            
            if self._device_supports_batch and self._batch_read_enabled:
                logger.debug(f"Using batch read for {self._asset_name}")
                raw_data = await self._read_points_batch()
            else:
                logger.debug(f"Using concurrent read for {self._asset_name}")
                raw_data = await self._read_points_concurrent()
            
            points_data = self.convert_data(raw_data, self._points, context={
                "device_id": self._asset_name,
                "connection_status": "connected"
            })
            
            if not points_data:
                return []
            
            standard_points = [StandardDataPoint(**p) for p in points_data]
            reading = self.create_reading_from_points(standard_points)
            
            if self.storage:
                await self.storage.write(reading)
            
            await self.publish_readings([reading])
            
            poll_duration = time.time() - poll_start
            successful_count = sum(1 for p in points_data if p.get("quality") == "good")
            self._update_performance_stats(poll_duration, len(self._point_order), successful_count)
            
            logger.info(
                f"Poll completed for {self._asset_name}: "
                f"{len(self._point_order)} points in {poll_duration:.2f}s "
                f"(avg: {self._performance_stats['avg_poll_time']:.2f}s, "
                f"success_rate: {self._performance_stats['success_rate']:.1%})"
            )
            
            return [reading]
            
        except Exception as e:
            logger.error(f"Poll error: {e}")
            return await self._create_offline_reading()
    
    async def write_setpoint(self, asset: str, point: str, value: Any) -> bool:
        """写入点位值"""
        if not self._connected or not self._app:
            logger.error("Not connected to BACnet device")
            return False
        
        write_info = self._write_points.get(point)
        if not write_info:
            logger.error(f"Point {point} not found or not writable")
            return False
        
        try:
            success = await self._write_point_value(write_info, value)
            if success:
                logger.info(f"Successfully wrote {value} to {point}")
            else:
                logger.error(f"Failed to write {value} to {point}")
            return success
            
        except Exception as e:
            logger.error(f"Write error for {point}: {e}")
            return False
    
    async def _create_client(self) -> bool:
        if not _check_bacnet_available():
            return False
        
        try:
            device_object = _DeviceObject(
                objectIdentifier=("device", self._device_id),
                objectName=f"XAgent_{self._asset_name}",
            )
            
            local_address = "0.0.0.0"
            
            network_port_object = _NetworkPortObject(
                local_address,
                objectIdentifier=("network-port", 1),
                objectName="NetworkPort-1",
            )
            
            self._app = _Application.from_object_list(
                [device_object, network_port_object]
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to create BACnet client: {e}")
            return False
    
    async def _test_connection(self) -> bool:
        """测试连接"""
        if not self._app:
            return False
        
        try:
            if self._heartbeat_mode == HEARTBEAT_MODE_DEVICE_OBJECT:
                return await self._check_device_object()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def _check_device_object(self) -> bool:
        """
        通过读取设备对象的标准属性来检查设备是否在线
        
        读取 device 对象的标准属性（如 objectName, systemStatus 等）
        这是 BACnet 协议的标准做法，比读取普通点位更可靠
        """
        if not self._app:
            return False
        
        try:
            device_address = f"{self._host}:{self._port}"
            object_identifier = f"device,{self._device_id}"
            
            response = await asyncio.wait_for(
                self._app.read_property(
                    device_address,
                    object_identifier,
                    self._heartbeat_property
                ),
                timeout=self._heartbeat_timeout
            )
            
            if _ErrorRejectAbortNack and isinstance(response, _ErrorRejectAbortNack):
                logger.warning(
                    f"Device object check failed - "
                    f"device_address={device_address}, "
                    f"device_id={self._device_id}, "
                    f"property={self._heartbeat_property}, "
                    f"error={response}"
                )
                return False
            
            if response is not None:
                logger.debug(f"Device object check successful, {self._heartbeat_property}={response}")
                return True
            else:
                logger.warning("Device object check failed: no response")
                return False
                
        except asyncio.TimeoutError:
            logger.warning(f"Device object check timeout after {self._heartbeat_timeout}s")
            return False
        except Exception as e:
            logger.error(f"Device object check failed: {e}")
            return False
    
    async def _check_heartbeat(self) -> bool:
        """
        执行心跳检测
        
        根据配置的心跳模式选择不同的检测方式：
        - device_object: 读取设备对象的标准属性（推荐）
        - none: 跳过心跳检测
        """
        if self._heartbeat_mode == HEARTBEAT_MODE_NONE:
            return True
        
        if self._heartbeat_mode == HEARTBEAT_MODE_DEVICE_OBJECT:
            for attempt in range(self._heartbeat_retries):
                if await self._check_device_object():
                    return True
                if attempt < self._heartbeat_retries - 1:
                    await asyncio.sleep(1.0)
            return False
        
        return True
    
    async def _ensure_connection(self) -> bool:
        """确保连接可用，使用基于时间间隔的重连策略"""
        if self._connected and self._app:
            return True
        
        now = time.time()
        elapsed = now - self._last_reconnect_time
        
        if elapsed >= self._reconnect_interval:
            self._last_reconnect_time = now
            self._offline_counter += 1
            logger.info(f"Attempting reconnect (attempt {self._offline_counter})")
            return await self.connect()
        
        return False
    
    def _setup_point_mappings(self) -> None:
        """设置点位映射"""
        self._point_order.clear()
        self._point_map.clear()
        self._write_points.clear()
        
        for point in self._points:
            point_name = point.get("name")
            if not point_name:
                continue
            
            object_type = self._get_point_config(point, "object_type")
            object_instance = self._get_point_config(point, "object_instance")
            writable = self._get_point_config(point, "writable", False)
            
            if not object_type or object_instance is None:
                logger.warning(f"Missing object_type or object_instance for point {point_name}")
                continue
            
            point_info = {
                "name": point_name,
                "object_type": object_type,
                "object_instance": object_instance,
                "property_id": self._get_point_config(point, "property_id", "presentValue"),
                "config": point
            }
            
            self._point_map[point_name] = point_info
            self._point_order.append(point_name)
            
            if writable:
                self._write_points[point_name] = point_info
    
    async def _read_with_retry(
        self,
        point_info: Dict[str, Any],
        timeout: float,
        max_retries: int,
        retry_interval: float
    ) -> Any:
        """带重试的读取"""
        for attempt in range(max_retries + 1):
            try:
                value = await asyncio.wait_for(
                    self._read_point_value(point_info),
                    timeout=timeout
                )
                return value
            except asyncio.TimeoutError:
                logger.warning(
                    f"Point {point_info['name']} timeout after {timeout}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_interval)
            except Exception as e:
                logger.error(f"Error reading point {point_info['name']}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_interval)
        
        return None
    
    async def _read_points_concurrent(
        self, 
        point_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        并发读取点位 - 性能优化方案
        
        Args:
            point_names: 要读取的点位名称列表，None表示读取所有点位
        
        Returns:
            点位数据字典
        """
        if point_names is None:
            point_names = self._point_order
        
        if not point_names:
            return {}
        
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent_reads)
        
        async def read_single_point(point_name: str) -> tuple:
            """读取单个点位（带信号量控制）"""
            async with self._semaphore:
                point_info = self._point_map.get(point_name)
                if not point_info:
                    return (point_name, None)
                
                value = await self._read_with_retry(
                    point_info,
                    self._point_timeout,
                    self._point_retries,
                    self.POINT_RETRY_INTERVAL
                )
                return (point_name, value)
        
        tasks = [read_single_point(name) for name in point_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_data = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in concurrent read: {result}")
                continue
            point_name, value = result
            raw_data[point_name] = value
        
        return raw_data
    
    def _update_performance_stats(self, poll_duration: float, points_count: int, successful_count: int = 0):
        """更新性能统计"""
        self._performance_stats["total_polls"] += 1
        self._performance_stats["total_points_read"] += points_count
        self._performance_stats["successful_points_read"] += successful_count
        self._performance_stats["total_time"] += poll_duration
        self._performance_stats["last_poll_time"] = poll_duration
        
        if self._performance_stats["total_polls"] > 0:
            self._performance_stats["avg_poll_time"] = (
                self._performance_stats["total_time"] / 
                self._performance_stats["total_polls"]
            )
        
        if self._performance_stats["total_points_read"] > 0:
            self._performance_stats["success_rate"] = (
                self._performance_stats["successful_points_read"] /
                self._performance_stats["total_points_read"]
            )
    
    async def _probe_device_capabilities(self) -> bool:
        """
        探测设备是否支持ReadPropertyMultiple服务
        
        Returns:
            True: 支持批量读取
            False: 不支持，需要降级
        """
        if not self._app or not self._points:
            self._device_supports_batch = False
            return False
        
        try:
            test_points = self._points[:3]
            
            read_access_spec = []
            for point in test_points:
                object_type = self._get_point_config(point, "object_type")
                object_instance = self._get_point_config(point, "object_instance")
                property_id = self._get_point_config(point, "property_id", "presentValue")
                
                if not object_type or object_instance is None:
                    continue
                    
                read_access_spec.append({
                    "object_identifier": f"{object_type},{object_instance}",
                    "property_references": [property_id]
                })
            
            if not read_access_spec:
                self._device_supports_batch = False
                return False
            
            device_address = f"{self._host}:{self._port}"
            
            logger.info(f"Probing device {self._asset_name} for ReadPropertyMultiple support...")
            
            if not hasattr(self._app, 'read_property_multiple'):
                logger.warning("bacpypes3 library does not support read_property_multiple")
                self._device_supports_batch = False
                return False
            
            response = await asyncio.wait_for(
                self._app.read_property_multiple(
                    device_address,
                    read_access_spec
                ),
                timeout=5.0
            )
            
            if response and not (_ErrorRejectAbortNack and isinstance(response, _ErrorRejectAbortNack)):
                logger.info(f"Device {self._asset_name} supports ReadPropertyMultiple")
                self._device_supports_batch = True
                return True
            else:
                logger.warning(f"Device {self._asset_name} returned error for ReadPropertyMultiple")
                self._device_supports_batch = False
                return False
                
        except asyncio.TimeoutError:
            logger.warning(f"Device {self._asset_name} timeout during capability probe")
            self._device_supports_batch = False
            return False
        except Exception as e:
            logger.warning(f"Device {self._asset_name} does not support ReadPropertyMultiple: {e}")
            self._device_supports_batch = False
            return False
    
    async def _read_points_batch(self) -> Dict[str, Any]:
        """
        批量读取点位 - 使用ReadPropertyMultiple
        
        Returns:
            点位数据字典
        """
        raw_data = {}
        
        try:
            total_points = len(self._point_order)
            batch_count = (total_points + self._batch_size - 1) // self._batch_size
            
            logger.debug(
                f"Reading {total_points} points in {batch_count} batches "
                f"(batch_size={self._batch_size})"
            )
            
            for batch_idx in range(batch_count):
                start_idx = batch_idx * self._batch_size
                end_idx = min(start_idx + self._batch_size, total_points)
                batch_points = self._point_order[start_idx:end_idx]
                
                point_to_obj_id: Dict[str, str] = {}
                read_access_spec = []
                for point_name in batch_points:
                    point_info = self._point_map.get(point_name)
                    if not point_info:
                        continue
                    
                    object_type = point_info.get("object_type")
                    object_instance = point_info.get("object_instance")
                    property_id = point_info.get("property_id", "presentValue")
                    
                    obj_id = f"{object_type},{object_instance}"
                    point_to_obj_id[point_name] = obj_id
                    read_access_spec.append({
                        "object_identifier": obj_id,
                        "property_references": [property_id]
                    })
                
                if not read_access_spec:
                    continue
                
                device_address = f"{self._host}:{self._port}"
                
                try:
                    response = await asyncio.wait_for(
                        self._app.read_property_multiple(
                            device_address,
                            read_access_spec
                        ),
                        timeout=self._point_timeout * 2
                    )
                    
                    if response and not (_ErrorRejectAbortNack and isinstance(response, _ErrorRejectAbortNack)):
                        for point_name, obj_id in point_to_obj_id.items():
                            if obj_id in response:
                                value = response[obj_id]
                                if hasattr(value, 'value'):
                                    raw_data[point_name] = value.value
                                else:
                                    raw_data[point_name] = value
                            else:
                                raw_data[point_name] = None
                                logger.warning(f"Point {point_name} not in batch response")
                    else:
                        logger.warning(
                            f"Batch read failed for batch {batch_idx + 1}/{batch_count}, "
                            f"falling back to concurrent read"
                        )
                        batch_data = await self._read_points_concurrent(batch_points)
                        raw_data.update(batch_data)
                        
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Batch read timeout for batch {batch_idx + 1}/{batch_count}, "
                        f"falling back to concurrent read"
                    )
                    batch_data = await self._read_points_concurrent(batch_points)
                    raw_data.update(batch_data)
                    
                except Exception as e:
                    logger.error(f"Batch read error: {e}, falling back to concurrent read")
                    batch_data = await self._read_points_concurrent(batch_points)
                    raw_data.update(batch_data)
            
            return raw_data
            
        except Exception as e:
            logger.error(f"Batch read failed completely: {e}")
            return await self._read_points_concurrent()
    
    async def _read_point_value(self, point_info: Dict[str, Any]) -> Any:
        """读取单个点位值 (bacpypes3)"""
        if not self._app:
            return None
        
        try:
            object_type = point_info.get("object_type")
            object_instance = point_info.get("object_instance")
            property_id = point_info.get("property_id", "presentValue")
            
            device_address = f"{self._host}:{self._port}"
            object_identifier = f"{object_type},{object_instance}"
            
            logger.debug(
                f"Reading point - device: {device_address}, "
                f"object: {object_identifier}, "
                f"property: {property_id}"
            )
            
            response = await self._app.read_property(
                device_address,
                object_identifier,
                property_id
            )
            
            if _ErrorRejectAbortNack and isinstance(response, _ErrorRejectAbortNack):
                logger.warning(
                    f"Error reading point {point_info.get('name')} - "
                    f"object: {object_identifier}, "
                    f"property: {property_id}, "
                    f"error: {response}"
                )
                return None
            
            if hasattr(response, 'value'):
                return response.value
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error reading point {point_info.get('name')} - "
                f"object_type: {point_info.get('object_type')}, "
                f"object_instance: {point_info.get('object_instance')}, "
                f"error_type: {type(e).__name__}, "
                f"error: {e}"
            )
            logger.debug("Traceback", exc_info=True)
            return None
    
    async def _write_point_value(self, point_info: Dict[str, Any], value: Any) -> bool:
        """写入单个点位值 (bacpypes3)"""
        if not self._app:
            return False
        
        try:
            object_type = point_info.get("object_type")
            object_instance = point_info.get("object_instance")
            property_id = point_info.get("property_id", "presentValue")
            
            device_address = f"{self._host}:{self._port}"
            object_identifier = f"{object_type},{object_instance}"
            
            response = await self._app.write_property(
                device_address,
                object_identifier,
                property_id,
                value
            )
            
            if _ErrorRejectAbortNack and isinstance(response, _ErrorRejectAbortNack):
                logger.error(f"Error writing point {point_info.get('name')}: {response}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing point {point_info.get('name')}: {e}")
            return False
    

