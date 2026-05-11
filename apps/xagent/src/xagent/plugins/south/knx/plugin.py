"""KNX South Plugin - Data acquisition and control for KNX devices using xknx library"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from xagent.xcore.plugins.south import SouthPluginBase
from xagent.xcore.storage.interface import Reading
from xagent.xcore.transform import StandardDataPoint
from .converter import KNXConverter
from .constants import DATA_TYPE_MAPPING

logger = logging.getLogger(__name__)

KNX_AVAILABLE = None
_XKNX = None
_ConnectionConfig = None
_Switch = None
_BinarySensor = None
_Climate = None
_Light = None
_Cover = None
_Sensor = None
_GroupAddress = None
_XknxConnectionState = None


def _check_knx_available():
    global KNX_AVAILABLE, _XKNX, _ConnectionConfig
    global _Switch, _BinarySensor, _Climate, _Light, _Cover, _Sensor, _GroupAddress
    global _XknxConnectionState

    if KNX_AVAILABLE is not None:
        return KNX_AVAILABLE

    try:
        from xknx import XKNX
        from xknx.devices import Switch, BinarySensor, Climate, Light, Cover, Sensor
        from xknx.telegram import GroupAddress
        from xknx.io import ConnectionConfig
        from xknx.core.connection_manager import XknxConnectionState

        _XKNX = XKNX
        _ConnectionConfig = ConnectionConfig
        _Switch = Switch
        _BinarySensor = BinarySensor
        _Climate = Climate
        _Light = Light
        _Cover = Cover
        _Sensor = Sensor
        _GroupAddress = GroupAddress
        _XknxConnectionState = XknxConnectionState
        KNX_AVAILABLE = True
    except ImportError:
        KNX_AVAILABLE = False
        logger.warning("xknx not installed, KNX plugin will not work. Install with: pip install xknx")
    return KNX_AVAILABLE


class KNXPlugin(SouthPluginBase):
    """
    KNX 南向插件
    
    支持 KNX 协议，可读写以下数据类型：
    - Switch/Binary: 开关量
    - Climate: 温度
    - Light: 灯光（亮度、颜色）
    - Cover: 遮阳帘
    - Sensor: 通用传感器
    """
    
    __plugin_name__ = "knx"
    
    HEARTBEAT_TIMEOUT = 2.0
    HEARTBEAT_RETRIES = 2
    HEARTBEAT_RETRY_INTERVAL = 0.3
    POINT_TIMEOUT = 3.0
    POINT_RETRIES = 2
    POINT_RETRY_INTERVAL = 0.5
    
    DEFAULT_SYNC_MODE = "smart"
    DEFAULT_SYNC_INTERVAL = 60
    DEFAULT_MAX_CONCURRENT_SYNCS = 5
    
    def _create_data_converter(self) -> KNXConverter:
        """创建数据转换器"""
        return KNXConverter()
    
    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: Any):
        super().__init__(config, storage, event_bus)
        
        self._gateway_ip = config.get("gateway_ip", "192.168.1.100")
        self._gateway_port = config.get("gateway_port", 3671)
        self._local_ip = config.get("local_ip")
        self._route_back = config.get("route_back", False)
        self._reconnect_interval = config.get("reconnect_interval", 5)
        
        self._heartbeat_timeout = config.get("heartbeat_timeout", self.HEARTBEAT_TIMEOUT)
        self._heartbeat_retries = config.get("heartbeat_retries", self.HEARTBEAT_RETRIES)
        self._point_timeout = config.get("point_timeout", self.POINT_TIMEOUT)
        self._point_retries = config.get("point_retries", self.POINT_RETRIES)
        
        self._sync_mode = config.get("sync_mode", self.DEFAULT_SYNC_MODE)
        self._sync_interval = config.get("sync_interval", self.DEFAULT_SYNC_INTERVAL)
        self._max_concurrent_syncs = config.get("max_concurrent_syncs", self.DEFAULT_MAX_CONCURRENT_SYNCS)
        
        self._points: List[Dict[str, Any]] = config.get("points", [])
        self._xknx: Any = None
        self._device_online = False
        self._offline_counter = 0
        self._last_reconnect_time: float = 0.0
        self._devices: Dict[str, Any] = {}
        self._write_devices: Dict[str, Any] = {}
        self._point_order: List[str] = []
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._last_telegram_time: Dict[str, float] = {}
        
        self._performance_stats = {
            "total_polls": 0,
            "total_points_read": 0,
            "successful_points_read": 0,
            "total_time": 0.0,
            "avg_poll_time": 0.0,
            "last_poll_time": 0.0,
            "success_rate": 0.0,
        }
        
        if not self._points:
            logger.warning(f"No points configured for KNX device {self._asset_name}")
    
    async def _on_device_updated(self, device: Any) -> None:
        """xknx设备状态更新回调，用于维护_last_telegram_time"""
        device_name = device.name
        if device_name in self._devices:
            self._last_telegram_time[device_name] = time.time()
            logger.debug(f"Device {device_name} updated via telegram")
    
    async def connect(self) -> bool:
        if not _check_knx_available():
            logger.error("xknx is not installed. Install it with: pip install xknx")
            return False
        
        try:
            logger.info(f"Connecting to KNX gateway {self._gateway_ip}:{self._gateway_port}...")
            
            if _ConnectionConfig is None:
                logger.error("ConnectionConfig is not available")
                return False
            
            connection_config = _ConnectionConfig(
                gateway_ip=self._gateway_ip,
                gateway_port=self._gateway_port,
                local_ip=self._local_ip if self._local_ip else None,
                route_back=self._route_back,
                auto_reconnect=True,
                auto_reconnect_wait=self._reconnect_interval
            )
            
            if _XKNX is None:
                logger.error("XKNX is not available")
                return False
            
            self._xknx = _XKNX(
                connection_config=connection_config,
                device_updated_cb=self._on_device_updated
            )
            
            await self._xknx.start()
            
            self._connected = True
            self._device_online = False
            self._offline_counter = 0
            
            await self._setup_devices()
            
            logger.info(f"Connected to KNX gateway {self._gateway_ip}:{self._gateway_port}")
            logger.info("Waiting for first heartbeat to confirm device online status...")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to KNX gateway: {e}")
            self._connected = False
            self._device_online = False
            self._offline_counter = 0
            
            if self._xknx:
                try:
                    await self._xknx.stop()
                except Exception:
                    logger.debug("Error stopping xknx during connect failure", exc_info=True)
                finally:
                    self._xknx = None
            
            try:
                await self._create_offline_reading()
            except Exception:
                logger.debug("Error creating offline reading during connect failure", exc_info=True)
            
            return False
    
    async def _handle_connection_lost(self) -> None:
        """处理连接丢失 - 停止xknx并标记设备离线"""
        self._device_online = False
        self._connected = False
        
        if self._xknx:
            try:
                await self._xknx.stop()
            except Exception:
                logger.debug("Error stopping xknx during connection loss", exc_info=True)
            finally:
                self._xknx = None
        
        logger.warning(f"KNX device {self._asset_name} connection lost")
    
    async def disconnect(self) -> None:
        if self._xknx:
            try:
                await self._xknx.stop()
            except Exception as e:
                logger.error(f"Error disconnecting from KNX gateway: {e}")
            finally:
                self._xknx = None
                self._connected = False
                self._device_online = False
                self._offline_counter = 0
                self._devices.clear()
                self._write_devices.clear()
        
        logger.info(f"Disconnected from KNX gateway {self._gateway_ip}:{self._gateway_port}")
    
    async def _setup_devices(self) -> None:
        if not self._xknx or not self._points:
            return
        
        self._devices.clear()
        self._write_devices.clear()
        self._point_order.clear()
        
        for point in self._points:
            point_name = point.get("name")
            group_address = self._get_point_config(point, "group_address")
            status_address = self._get_point_config(point, "status_address")
            control_address = self._get_point_config(point, "control_address")
            data_type = point.get("data_type", "switch")
            writable = self._get_point_config(point, "writable", False)
            
            read_address = status_address or group_address
            write_address = control_address or group_address
            
            if not point_name:
                continue
            
            if not read_address and not write_address:
                logger.warning(f"No address configured for point {point_name}")
                continue
            
            try:
                device = await self._create_device(
                    point_name, 
                    read_address,
                    write_address,
                    data_type,
                    writable
                )
                if device:
                    self._devices[point_name] = {
                        "device": device,
                        "config": point,
                        "data_type": data_type,
                        "read_address": read_address,
                        "write_address": write_address
                    }
                    self._point_order.append(point_name)
                    if writable:
                        self._write_devices[point_name] = {
                            "device": device,
                            "config": point,
                            "data_type": data_type,
                            "address": write_address
                        }
                    logger.debug(f"Created device for point {point_name}: read={read_address}, write={write_address}")
            except Exception as e:
                logger.error(f"Error creating device for point {point_name}: {e}")
    
    async def _create_device(
        self, 
        name: str, 
        read_address: Optional[str],
        write_address: Optional[str],
        data_type: str,
        writable: bool = False
    ) -> Any:
        if not self._xknx:
            return None
        
        type_config = DATA_TYPE_MAPPING.get(data_type, DATA_TYPE_MAPPING["switch"])
        device_class_name = type_config["device_class"]
        
        try:
            read_ga = _GroupAddress(read_address) if read_address else None
            write_ga = _GroupAddress(write_address) if write_address else None
        except Exception as e:
            logger.error(f"Invalid group address: {e}")
            return None
        
        device = self._construct_device(device_class_name, name, read_ga, write_ga)
        
        if device:
            self._xknx.devices.add(device)
        
        return device
    
    def _construct_device(
        self, 
        device_class_name: str, 
        name: str, 
        read_ga: Any, 
        write_ga: Any
    ) -> Any:
        """根据设备类名构造xknx设备对象"""
        constructors = {
            "Switch": lambda: _Switch(
                self._xknx, name=name,
                group_address=write_ga, group_address_state=read_ga
            ),
            "BinarySensor": lambda: _BinarySensor(
                self._xknx, name=name,
                group_address_state=read_ga
            ),
            "Climate": lambda: _Climate(
                self._xknx, name=name,
                group_address_temperature=read_ga
            ),
            "Light": lambda: _Light(
                self._xknx, name=name,
                group_address_switch=write_ga, group_address_switch_state=read_ga
            ),
            "Cover": lambda: _Cover(
                self._xknx, name=name,
                group_address_position=write_ga, group_address_position_state=read_ga
            ),
        }
        
        factory = constructors.get(device_class_name)
        if factory:
            return factory()
        
        return _Sensor(self._xknx, name=name, group_address_state=read_ga)
    
    async def poll(self) -> List[Reading]:
        poll_start = time.time()
        
        if not self._connected or not self._xknx:
            logger.warning("KNX client not connected, attempting reconnect...")
            if not await self.connect():
                return await self._create_offline_reading()
        
        if not self._point_order:
            logger.warning("No points configured")
            return []
        
        if not self._device_online:
            self._offline_counter += 1
            now = time.time()
            elapsed = now - self._last_reconnect_time
            if elapsed >= self._reconnect_interval:
                self._last_reconnect_time = now
                logger.info(f"Attempting reconnect (counter={self._offline_counter})")
                if not await self.connect():
                    logger.warning("Reconnect attempt failed")
            else:
                logger.debug(f"Device offline, will attempt heartbeat (counter={self._offline_counter})")
        
        heartbeat_point = self._point_order[0]
        heartbeat_device_info = self._devices.get(heartbeat_point)
        
        if not heartbeat_device_info:
            logger.error(f"Heartbeat point {heartbeat_point} not found")
            return []
        
        heartbeat_success = await self._read_with_retry(
            heartbeat_device_info["device"],
            heartbeat_device_info["data_type"],
            self._heartbeat_timeout,
            self._heartbeat_retries,
            self.HEARTBEAT_RETRY_INTERVAL
        )
        
        if heartbeat_success is None:
            await self._handle_connection_lost()
            return await self._create_offline_reading()
        
        self._device_online = True
        self._offline_counter = 0
        logger.debug(f"Heartbeat point {heartbeat_point} success, device online")
        
        remaining_points = self._point_order[1:]
        
        if self._sync_mode == "passive":
            raw_data = await self._read_states_passive(remaining_points)
        elif self._sync_mode == "always":
            raw_data = await self._read_states_with_sync(remaining_points)
        else:
            raw_data = await self._read_states_smart(remaining_points)
        
        heartbeat_value = self._get_device_state(
            heartbeat_device_info["device"],
            heartbeat_device_info["data_type"]
        )
        
        raw_data[heartbeat_point] = heartbeat_value
        
        points_data = self.convert_data(raw_data, self._points, context={
            "device_id": self._asset_name,
            "connection_status": "connected" if self._connected else "disconnected"
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
            f"(avg: {self._performance_stats['avg_poll_time']:.2f}s, mode={self._sync_mode})"
        )
        
        return [reading]
    
    async def _read_with_retry(
        self,
        device: Any,
        data_type: str,
        timeout: float,
        max_retries: int,
        retry_interval: float
    ) -> Any:
        for attempt in range(max_retries + 1):
            try:
                value = await asyncio.wait_for(
                    self._read_device_value(device, data_type),
                    timeout=timeout
                )
                return value
            except asyncio.TimeoutError:
                logger.warning(f"Device {device.name if device else 'unknown'} timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    await asyncio.sleep(retry_interval)
            except Exception as e:
                logger.error(f"Error reading device: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_interval)
        
        return None
    
    async def _read_device_value(self, device: Any, data_type: str) -> Any:
        if not device:
            logger.debug(f"Device is None for data_type {data_type}")
            return None
        
        try:
            if _XknxConnectionState is None:
                return None
            conn_state = self._xknx.connection_manager.state
            if conn_state != _XknxConnectionState.CONNECTED:
                logger.warning(f"KNX not connected (state={conn_state.name}), cannot read device {device.name}")
                self._connected = False
                self._device_online = False
                return None
            
            logger.debug(f"Reading device {device.name}, data_type={data_type}")
            
            if hasattr(device, 'sync'):
                logger.debug(f"Calling sync on device {device.name}")
                await device.sync(wait_for_result=True)
                logger.debug(f"Sync completed for device {device.name}")
            
            value = self._extract_device_value(device, data_type)
            if value is None:
                logger.warning(f"Could not read value from device {device.name}")
            return value
                
        except Exception as e:
            logger.error(f"Error reading device value: {e}", exc_info=True)
            return None
    
    def _extract_device_value(self, device: Any, data_type: str) -> Any:
        """
        从xknx设备对象提取状态值
        
        使用 DATA_TYPE_MAPPING 中的 value_attr 字段确定读取方式：
        - "resolve": 调用 device.resolve_state()
        - "current_color": 读取 device.current_color 并转为字符串
        - 其他: 使用 getattr(device, value_attr, None)
        
        Args:
            device: xknx设备对象
            data_type: 数据类型
        
        Returns:
            设备状态值
        """
        if not device:
            return None
        
        type_info = DATA_TYPE_MAPPING.get(data_type, DATA_TYPE_MAPPING["switch"])
        value_attr = type_info.get("value_attr", "state")
        
        try:
            if value_attr == "resolve":
                if data_type in ("percent", "brightness"):
                    brightness = getattr(device, 'current_brightness', None)
                    if brightness is not None:
                        return brightness
                
                if hasattr(device, 'resolve_state'):
                    result = device.resolve_state()
                    if asyncio.iscoroutine(result):
                        logger.warning(f"resolve_state() returned coroutine for {device.name}")
                        return None
                    return result
                return getattr(device, 'state', None)
            elif value_attr == "current_color":
                color = getattr(device, 'current_color', None)
                return str(color) if color else None
            else:
                return getattr(device, value_attr, None)
        except Exception as e:
            logger.error(f"Error extracting device value for {data_type}: {e}")
            return None
    
    def _get_device_state(self, device: Any, data_type: str) -> Any:
        """直接读取设备状态（不发送KNX请求）"""
        return self._extract_device_value(device, data_type)
    
    async def write_setpoint(self, asset: str, point: str, value: Any) -> bool:
        if not self._connected or not self._xknx:
            logger.error("Not connected to KNX gateway")
            return False
        
        write_device_info = self._write_devices.get(point)
        if write_device_info:
            device = write_device_info["device"]
            data_type = write_device_info["data_type"]
            address = write_device_info["address"]
            
            try:
                success = await self._write_device_value(device, data_type, value)
                if success:
                    logger.info(f"Successfully wrote value {value} to point {point} at address {address}")
                else:
                    logger.error(f"Failed to write value {value} to point {point}")
                return success
            except Exception as e:
                logger.error(f"Error writing to point {point}: {e}")
                return False
        
        device_info = self._devices.get(point)
        if not device_info:
            logger.error(f"Point {point} not found in configuration")
            return False
        
        writable = self._get_point_config(device_info["config"], "writable", False)
        
        if not writable:
            logger.warning(f"Point {point} is not writable")
            return False
        
        device = device_info["device"]
        data_type = device_info["data_type"]
        address = device_info.get("write_address", "unknown")
        
        try:
            success = await self._write_device_value(device, data_type, value)
            if success:
                logger.info(f"Successfully wrote value {value} to point {point} at address {address}")
            else:
                logger.error(f"Failed to write value {value} to point {point}")
            return success
        except Exception as e:
            logger.error(f"Error writing to point {point}: {e}")
            return False
    
    async def _write_device_value(self, device: Any, data_type: str, value: Any) -> bool:
        if not device:
            return False
        
        try:
            if data_type in ("switch", "binary", "bool"):
                if hasattr(device, 'set_on') and hasattr(device, 'set_off'):
                    if value:
                        await device.set_on()
                    else:
                        await device.set_off()
                    return True
            elif data_type in ("percent", "brightness", "dimming"):
                if hasattr(device, 'set_brightness'):
                    await device.set_brightness(int(value))
                    return True
            elif data_type == "blinds":
                if hasattr(device, 'set_position'):
                    await device.set_position(int(value))
                    return True
            elif data_type == "color_rgb":
                if hasattr(device, 'set_color'):
                    await device.set_color(value)
                    return True
            elif data_type == "temperature":
                if hasattr(device, 'set_setpoint'):
                    await device.set_setpoint(float(value))
                    return True
            
            logger.warning(f"No write method available for data type {data_type} on device {device.name}")
            return False
            
        except Exception as e:
            logger.error(f"Error writing device value: {e}")
            return False
    
    async def _read_states_passive(self, point_names: List[str]) -> Dict[str, Any]:
        """
        被动模式：直接读取设备状态
        
        不发送任何KNX请求，仅读取xknx维护的设备状态。
        依赖设备主动上报状态变化。
        
        Args:
            point_names: 要读取的点位名称列表
        
        Returns:
            点位数据字典
        """
        raw_data = {}
        
        for point_name in point_names:
            device_info = self._devices.get(point_name)
            if not device_info:
                raw_data[point_name] = None
                continue
            
            value = self._get_device_state(
                device_info["device"],
                device_info["data_type"]
            )
            raw_data[point_name] = value
            
            if value is not None:
                logger.debug(f"[Passive] Read {point_name}: value={value}")
            else:
                logger.warning(f"[Passive] Point {point_name} has no state (device may not have reported)")
        
        return raw_data
    
    async def _read_states_with_sync(self, point_names: List[str]) -> Dict[str, Any]:
        """
        主动模式：并发sync后读取状态
        
        对所有点位发送GroupValueRead请求，使用并发优化。
        适用于需要最高实时性的场景。
        
        Args:
            point_names: 要读取的点位名称列表
        
        Returns:
            点位数据字典
        """
        if not point_names:
            return {}
        
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent_syncs)
        
        async def sync_and_read(point_name: str) -> tuple:
            """sync单个点位并读取状态"""
            async with self._semaphore:
                device_info = self._devices.get(point_name)
                if not device_info:
                    return (point_name, None)
                
                device = device_info["device"]
                data_type = device_info["data_type"]
                
                try:
                    if hasattr(device, 'sync'):
                        await device.sync(wait_for_result=True)
                        self._last_telegram_time[point_name] = time.time()
                        logger.debug(f"[Always] Synced {point_name}")
                except Exception as e:
                    logger.error(f"[Always] Sync failed for {point_name}: {e}")
                    return (point_name, None)
                
                value = self._get_device_state(device, data_type)
                return (point_name, value)
        
        tasks = [sync_and_read(name) for name in point_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_data = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[Always] Error in concurrent sync: {result}")
                continue
            point_name, value = result
            raw_data[point_name] = value
        
        return raw_data
    
    async def _read_states_smart(self, point_names: List[str]) -> Dict[str, Any]:
        """
        智能模式：按需sync
        
        根据上次更新时间判断是否需要sync：
        - 超过sync_interval分钟无更新的点位：主动sync
        - 其他点位：被动读取
        
        Args:
            point_names: 要读取的点位名称列表
        
        Returns:
            点位数据字典
        """
        if not point_names:
            return {}
        
        now = time.time()
        sync_threshold = self._sync_interval * 60
        
        points_to_sync = []
        points_passive = []
        
        for point_name in point_names:
            last_time = self._last_telegram_time.get(point_name, 0)
            if (now - last_time) > sync_threshold:
                points_to_sync.append(point_name)
            else:
                points_passive.append(point_name)
        
        if points_to_sync:
            logger.info(
                f"[Smart] Syncing {len(points_to_sync)} points "
                f"(last update > {self._sync_interval} minutes ago)"
            )
        
        sync_data = {}
        if points_to_sync:
            sync_data = await self._sync_points_concurrent(points_to_sync)
        
        passive_data = {}
        for point_name in points_passive:
            device_info = self._devices.get(point_name)
            if device_info:
                passive_data[point_name] = self._get_device_state(
                    device_info["device"],
                    device_info["data_type"]
                )
        
        return {**passive_data, **sync_data}
    
    async def _sync_points_concurrent(self, point_names: List[str]) -> Dict[str, Any]:
        """
        并发sync指定点位
        
        Args:
            point_names: 要sync的点位名称列表
        
        Returns:
            点位数据字典
        """
        if not point_names:
            return {}
        
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent_syncs)
        
        async def sync_single(point_name: str) -> tuple:
            async with self._semaphore:
                device_info = self._devices.get(point_name)
                if not device_info:
                    return (point_name, None)
                
                device = device_info["device"]
                data_type = device_info["data_type"]
                
                try:
                    if hasattr(device, 'sync'):
                        await device.sync(wait_for_result=True)
                        self._last_telegram_time[point_name] = time.time()
                except Exception as e:
                    logger.error(f"[Smart] Sync failed for {point_name}: {e}")
                    return (point_name, None)
                
                value = self._get_device_state(device, data_type)
                return (point_name, value)
        
        tasks = [sync_single(name) for name in point_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        raw_data = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[Smart] Error in concurrent sync: {result}")
                continue
            point_name, value = result
            raw_data[point_name] = value
        
        return raw_data
    
    def _update_performance_stats(self, poll_duration: float, points_count: int, successful_count: int = 0):
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
