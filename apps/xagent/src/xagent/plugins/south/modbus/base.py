"""Modbus Base Plugin - Template method pattern base class shared by TCP and RTU"""

import asyncio
import logging
import struct
import time
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from xagent.xcore.plugins.south import SouthPluginBase, ModbusPluginMixin
from xagent.xcore.storage.interface import Reading
from xagent.xcore.transform import StandardDataPoint
from .converter import ModbusConverter
from .constants import DEFAULT_SLAVE_ID, DEFAULT_TIMEOUT, DEFAULT_RECONNECT_INTERVAL, DEFAULT_MAX_GAP

logger = logging.getLogger(__name__)

_ModbusException = Exception
_ConnectionException = Exception


class ModbusBasePlugin(SouthPluginBase, ModbusPluginMixin):
    """
    Modbus 通用基类 - 模板方法模式

    封装所有协议无关的逻辑：
    - 三层连接检测（连接状态 + 心跳 + 数据轮询）
    - 点位分组与批量读取
    - 值提取与编码
    - 写操作
    - 性能统计
    - 自动重连

    子类只需实现协议专有的钩子方法：
    - _create_client()       → 创建协议客户端实例
    - _connect_client()      → 执行连接
    - _disconnect_client()   → 断开连接
    - _is_client_connected() → 检查连接状态
    - _get_connection_info() → 返回连接信息字典
    - _check_modbus_available() → 检查依赖是否可用
    """

    __plugin_name__ = None

    def _create_data_converter(self) -> ModbusConverter:
        return ModbusConverter()

    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: Any):
        super().__init__(config, storage, event_bus)

        self._slave_id = config.get("slave_id", DEFAULT_SLAVE_ID)
        self._timeout = config.get("timeout", DEFAULT_TIMEOUT)
        self._reconnect_interval = config.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL)

        self._heartbeat_address = config.get("heartbeat_address")
        self._heartbeat_timeout = config.get("heartbeat_timeout", 1.5)
        self._max_gap = config.get("max_gap", DEFAULT_MAX_GAP)

        self._points: List[Dict[str, Any]] = config.get("points", [])
        self._client: Optional[Any] = None

        self._offline_counter = 0
        self._last_heartbeat_time = 0
        self._last_reconnect_time: float = 0.0

        self._read_groups: List[Dict[str, Any]] = []
        self._group_points()

        self._performance_stats = {
            "total_polls": 0,
            "total_points_read": 0,
            "successful_points_read": 0,
            "last_poll_time": 0.0,
            "avg_poll_time": 0.0,
            "total_time": 0.0,
            "success_rate": 0.0,
        }

        if not self._points:
            logger.warning(f"No points configured for Modbus device {self._asset_name}")

    @abstractmethod
    def _create_client(self) -> Any:
        """创建协议专有的客户端实例（不执行连接）"""
        pass

    @abstractmethod
    async def _connect_client(self, client: Any) -> None:
        """使用已创建的客户端执行连接"""
        pass

    @abstractmethod
    async def _disconnect_client(self, client: Any) -> None:
        """断开客户端连接"""
        pass

    @abstractmethod
    def _is_client_connected(self, client: Any) -> bool:
        """检查客户端是否已连接"""
        pass

    @abstractmethod
    def _get_connection_info(self) -> Dict[str, Any]:
        """返回协议专有的连接信息"""
        pass

    @classmethod
    @abstractmethod
    def _check_modbus_available(cls) -> bool:
        """检查协议依赖是否可用"""
        pass

    async def connect(self) -> bool:
        if not self._check_modbus_available():
            logger.error("pymodbus is not installed. Install it with: pip install pymodbus")
            return False

        try:
            self._client = self._create_client()
            await self._connect_client(self._client)

            if self._is_client_connected(self._client):
                self._connected = True
                self._device_online = True
                self._offline_counter = 0
                logger.info(f"Connected to Modbus device: {self._asset_name}")
                return True
            else:
                logger.error(f"Failed to connect to Modbus device: {self._asset_name}")
                return False

        except Exception as e:
            logger.error(f"Error connecting to Modbus device: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._disconnect_client(self._client)
            except Exception as e:
                logger.error(f"Error disconnecting from Modbus device: {e}")
            finally:
                self._client = None
                self._connected = False

        logger.info(f"Disconnected from Modbus device: {self._asset_name}")

    @property
    def is_connected(self) -> bool:
        if self._client:
            return self._is_client_connected(self._client)
        return self._connected

    async def poll(self) -> List[Reading]:
        """
        从 Modbus 设备轮询数据（三层检测）

        第一层：连接状态检查
        第二层：心跳点位检查（可选）
        第三层：批量数据采集
        """
        poll_start = time.time()

        logger.debug(f"poll() called for device {self._asset_name}")

        if not await self._check_connection():
            logger.debug("poll: connection check failed, creating offline reading")
            readings = await self._create_offline_reading()
            poll_duration = time.time() - poll_start
            self._update_performance_stats(poll_duration, 0)
            return readings

        if self._heartbeat_address is not None:
            if not await self._check_heartbeat():
                logger.debug("poll: heartbeat check failed, creating offline reading")
                readings = await self._create_offline_reading()
                poll_duration = time.time() - poll_start
                self._update_performance_stats(poll_duration, 0)
                return readings
        else:
            self._device_online = True

        logger.debug("poll: proceeding with batch poll")
        readings = await self._poll_with_batch()

        poll_duration = time.time() - poll_start
        points_count = len(self._points)
        successful_count = 0
        if readings and hasattr(readings[0], 'standard_points') and readings[0].standard_points:
            successful_count = sum(
                1 for p in readings[0].standard_points
                if p.get("quality") == "good"
            )
        self._update_performance_stats(poll_duration, points_count, successful_count)

        logger.info(
            f"Poll completed for {self._asset_name}: "
            f"{points_count} points in {poll_duration:.2f}s "
            f"(avg: {self._performance_stats['avg_poll_time']:.2f}s)"
        )

        return readings

    async def _check_connection(self) -> bool:
        logger.debug(f"_check_connection: client={self._client is not None}, is_connected={self.is_connected}")

        if not self._client:
            logger.debug("_check_connection: no client, calling _handle_disconnected")
            return await self._handle_disconnected()

        if not self.is_connected:
            logger.debug("_check_connection: not connected, calling _handle_disconnected")
            return await self._handle_disconnected()

        logger.debug("_check_connection: connection OK")
        return True

    async def _handle_disconnected(self) -> bool:
        self._offline_counter += 1

        now = time.time()
        elapsed = now - self._last_reconnect_time

        if elapsed >= self._reconnect_interval:
            self._last_reconnect_time = now
            logger.info(f"Attempting to reconnect to {self._asset_name} "
                       f"(attempt {self._offline_counter})")
            if await self.connect():
                self._device_online = True
                logger.info(f"Device {self._asset_name} reconnected successfully")
                return True

        logger.debug(f"Device {self._asset_name} offline, skipping poll "
                    f"(offline counter: {self._offline_counter})")
        return False

    async def _persist_and_publish(self, reading: Reading) -> None:
        if self.storage:
            await self.storage.write(reading)
        if self.event_bus:
            await self.publish_readings([reading])

    async def _check_heartbeat(self) -> bool:
        if self._client is None:
            return False

        try:
            result = await asyncio.wait_for(
                self._client.read_holding_registers(
                    address=self._heartbeat_address,
                    count=1,
                    device_id=self._slave_id
                ),
                timeout=self._heartbeat_timeout
            )

            if result.isError():
                logger.warning(f"Heartbeat failed for {self._asset_name}: {result}")
                self._device_online = False
                return False

            self._last_heartbeat_time = time.time()
            self._device_online = True
            return True

        except asyncio.CancelledError:
            logger.warning(f"Heartbeat check cancelled for {self._asset_name}")
            self._device_online = False
            raise
        except asyncio.TimeoutError:
            logger.warning(f"Heartbeat timeout for {self._asset_name} "
                          f"(address={self._heartbeat_address}, timeout={self._heartbeat_timeout}s)")
            self._device_online = False
            return False
        except Exception as e:
            logger.error(f"Heartbeat error for {self._asset_name}: {e}")
            self._connected = False
            self._device_online = False
            return False

    async def _poll_with_batch(self) -> List[Reading]:
        if not self._read_groups:
            return []

        raw_data = {}

        for group in self._read_groups:
            group_data = await self._read_group(group)
            raw_data.update(group_data)

        context = {
            "device_id": self._asset_name,
            "connection_status": "connected"
        }

        points_data = self.convert_data(raw_data, self._points, context)

        if not points_data:
            return []

        self._device_online = True

        standard_points = [StandardDataPoint(**p) for p in points_data]
        reading = self.create_reading_from_points(standard_points)

        logger.debug(f"Created reading: {reading.to_dict()}")

        await self._persist_and_publish(reading)

        return [reading]

    async def _read_group(self, group: Dict[str, Any]) -> Dict[str, Any]:
        start_addr = group['start']
        count = group['count']
        register_type = group['register_type']
        points_config = group['points']

        result_data = {}

        if self._client is None:
            for point_config in points_config:
                point_name = point_config.get("name")
                if point_name:
                    result_data[point_name] = None
            return result_data

        try:
            if register_type == "coil":
                result = await self._client.read_coils(
                    address=start_addr,
                    count=count,
                    device_id=self._slave_id
                )
            elif register_type == "discrete_input":
                result = await self._client.read_discrete_inputs(
                    address=start_addr,
                    count=count,
                    device_id=self._slave_id
                )
            elif register_type == "holding":
                result = await self._client.read_holding_registers(
                    address=start_addr,
                    count=count,
                    device_id=self._slave_id
                )
            elif register_type == "input":
                result = await self._client.read_input_registers(
                    address=start_addr,
                    count=count,
                    device_id=self._slave_id
                )
            else:
                logger.warning(f"Unknown register type: {register_type}")
                for point_config in points_config:
                    point_name = point_config.get("name")
                    if point_name:
                        result_data[point_name] = None
                return result_data

            if result.isError():
                logger.error(f"Error reading group at address {start_addr}: {result}")
                for point_config in points_config:
                    point_name = point_config.get("name")
                    if point_name:
                        result_data[point_name] = None
                return result_data

            if register_type in ("coil", "discrete_input"):
                bits = result.bits[:count]
                return self._extract_values_from_bits(bits, points_config, start_addr)
            else:
                registers = result.registers
                return self._extract_values_from_registers(registers, points_config, start_addr)

        except asyncio.CancelledError:
            logger.warning(f"Read operation cancelled at address {start_addr}")
            for point_config in points_config:
                point_name = point_config.get("name")
                if point_name:
                    result_data[point_name] = None
            raise
        except asyncio.TimeoutError:
            logger.error(f"Timeout reading group at address {start_addr}")
            for point_config in points_config:
                point_name = point_config.get("name")
                if point_name:
                    result_data[point_name] = None
            return result_data
        except _ModbusException as e:
            logger.error(f"Modbus error reading group at address {start_addr}: {e}")
            self._connected = False
            for point_config in points_config:
                point_name = point_config.get("name")
                if point_name:
                    result_data[point_name] = None
            return result_data
        except Exception as e:
            logger.error(f"Unexpected error reading group at address {start_addr}: {e}")
            for point_config in points_config:
                point_name = point_config.get("name")
                if point_name:
                    result_data[point_name] = None
            return result_data

    def _group_points(self) -> None:
        if not self._points:
            return

        valid_points = [p for p in self._points if self._get_point_config(p, "address") is not None]
        if not valid_points:
            return

        type_groups = {}
        for p in valid_points:
            register_type = self._get_point_config(p, "register_type", "holding")
            type_groups.setdefault(register_type, []).append(p)

        groups = []

        for register_type, points_list in type_groups.items():
            sorted_points = sorted(points_list, key=lambda p: self._get_point_config(p, "address", 0))

            is_bit_type = register_type in ("coil", "discrete_input")

            first_count = 1 if is_bit_type else self._get_point_config(sorted_points[0], "count", 1)
            current_group = {
                'start': self._get_point_config(sorted_points[0], "address", 0),
                'count': first_count,
                'register_type': register_type,
                'points': [sorted_points[0]]
            }

            for point in sorted_points[1:]:
                addr = self._get_point_config(point, "address", 0)
                prev_end = current_group['start'] + current_group['count']

                if is_bit_type:
                    if addr - prev_end <= self._max_gap:
                        current_group['count'] = addr - current_group['start'] + 1
                        current_group['points'].append(point)
                    else:
                        groups.append(current_group)
                        current_group = {
                            'start': addr,
                            'count': 1,
                            'register_type': register_type,
                            'points': [point]
                        }
                else:
                    count = self._get_point_config(point, "count", 1)
                    if addr - prev_end <= self._max_gap:
                        new_end = addr + count
                        current_group['count'] = new_end - current_group['start']
                        current_group['points'].append(point)
                    else:
                        groups.append(current_group)
                        current_group = {
                            'start': addr,
                            'count': count,
                            'register_type': register_type,
                            'points': [point]
                        }

            groups.append(current_group)

        self._read_groups = groups

        logger.info(f"Grouped {len(self._points)} points into {len(groups)} read groups")
        for i, group in enumerate(groups):
            logger.debug(f"  Group {i+1}: address {group['start']}, count {group['count']}, "
                        f"{len(group['points'])} points, type {group['register_type']}")

    def _extract_values_from_bits(
        self,
        bits: List[bool],
        points_config: List[Dict[str, Any]],
        group_start: int
    ) -> Dict[str, Any]:
        result = {}

        for point_config in points_config:
            point_name = point_config.get("name", "unknown")
            addr = self._get_point_config(point_config, "address", 0)

            bit_offset = addr - group_start

            if bit_offset < 0 or bit_offset >= len(bits):
                logger.warning(f"Point {point_name} bit offset out of range: "
                             f"offset={bit_offset}, bits={len(bits)}")
                result[point_name] = None
                continue

            result[point_name] = bits[bit_offset]

        return result

    def _extract_values_from_registers(
        self,
        registers: List[int],
        points_config: List[Dict[str, Any]],
        group_start: int
    ) -> Dict[str, Any]:
        result = {}

        for point_config in points_config:
            point_name = point_config.get("name", "unknown")
            addr = self._get_point_config(point_config, "address", 0)
            count = self._get_point_config(point_config, "count", 1)
            data_type = point_config.get("data_type", "uint16")
            byte_order = self._get_point_config(point_config, "byte_order", "big")
            word_order = self._get_point_config(point_config, "word_order", "big")

            reg_offset = addr - group_start

            if reg_offset < 0 or reg_offset + count > len(registers):
                logger.warning(f"Point {point_name} offset out of range: "
                             f"offset={reg_offset}, count={count}, registers={len(registers)}")
                result[point_name] = None
                continue

            point_registers = registers[reg_offset:reg_offset + count]
            raw_value = self._data_converter.convert_register_value_with_order(
                point_registers, data_type, byte_order, word_order
            )

            result[point_name] = raw_value

        return result

    async def read_coils(self, address: int, count: int) -> List[bool]:
        if not self.is_connected or not self._client:
            raise _ConnectionException("Not connected to Modbus device")

        result = await self._client.read_coils(
            address=address,
            count=count,
            device_id=self._slave_id
        )

        if result.isError():
            raise _ModbusException(f"Error reading coils: {result}")

        return result.bits[:count]

    async def read_discrete_inputs(self, address: int, count: int) -> List[bool]:
        if not self.is_connected or not self._client:
            raise _ConnectionException("Not connected to Modbus device")

        result = await self._client.read_discrete_inputs(
            address=address,
            count=count,
            device_id=self._slave_id
        )

        if result.isError():
            raise _ModbusException(f"Error reading discrete inputs: {result}")

        return result.bits[:count]

    async def read_holding_registers(self, address: int, count: int) -> List[int]:
        if not self.is_connected or not self._client:
            raise _ConnectionException("Not connected to Modbus device")

        result = await self._client.read_holding_registers(
            address=address,
            count=count,
            device_id=self._slave_id
        )

        if result.isError():
            raise _ModbusException(f"Error reading holding registers: {result}")

        return result.registers

    async def read_input_registers(self, address: int, count: int) -> List[int]:
        if not self.is_connected or not self._client:
            raise _ConnectionException("Not connected to Modbus device")

        result = await self._client.read_input_registers(
            address=address,
            count=count,
            device_id=self._slave_id
        )

        if result.isError():
            raise _ModbusException(f"Error reading input registers: {result}")

        return result.registers

    async def write_single_coil(self, address: int, value: bool) -> bool:
        if not self.is_connected or not self._client:
            logger.error("Not connected to Modbus device")
            return False

        try:
            result = await self._client.write_coil(
                address=address,
                value=value,
                device_id=self._slave_id
            )

            if result.isError():
                logger.error(f"Error writing coil at address {address}: {result}")
                return False

            logger.info(f"Successfully wrote coil at address {address}: {value}")
            return True

        except Exception as e:
            logger.error(f"Error writing coil: {e}")
            return False

    async def write_single_register(self, address: int, value: int) -> bool:
        if not self.is_connected or not self._client:
            logger.error("Not connected to Modbus device")
            return False

        try:
            result = await self._client.write_register(
                address=address,
                value=value,
                device_id=self._slave_id
            )

            if result.isError():
                logger.error(f"Error writing register at address {address}: {result}")
                return False

            logger.info(f"Successfully wrote value {value} to address {address}")
            return True

        except Exception as e:
            logger.error(f"Error writing register: {e}")
            return False

    async def write_setpoint(self, asset: str, point: str, value: Any) -> bool:
        point_config = next(
            (p for p in self._points if p.get("name") == point),
            None
        )

        if not point_config:
            logger.error(f"Point {point} not found in configuration")
            return False

        address = self._get_point_config(point_config, "address")
        if address is None:
            logger.error(f"No address configured for point {point}")
            return False

        register_type = self._get_point_config(point_config, "register_type", "holding")
        data_type = point_config.get("data_type", "uint16")
        byte_order = self._get_point_config(point_config, "byte_order", "big")
        word_order = self._get_point_config(point_config, "word_order", "big")

        if register_type == "coil":
            if isinstance(value, bool):
                return await self.write_single_coil(address, value)
            else:
                return await self.write_single_coil(address, bool(value))

        registers = self._encode_value_to_registers(value, data_type, byte_order, word_order)
        if registers is None:
            return False

        if len(registers) == 1:
            return await self.write_single_register(address, registers[0])
        else:
            return await self.write_registers(address, registers)

    def _encode_value_to_registers(
        self,
        value: Any,
        data_type: str,
        byte_order: str = "big",
        word_order: str = "big"
    ) -> Optional[List[int]]:
        try:
            if data_type == "bool":
                return [1 if bool(value) else 0]

            elif data_type in ("uint16", "int16"):
                int_val = int(value)
                if data_type == "int16" and int_val < 0:
                    int_val = int_val & 0xFFFF
                reg_val = int_val & 0xFFFF
                if byte_order == "little":
                    reg_val = ((reg_val & 0xFF) << 8) | ((reg_val >> 8) & 0xFF)
                return [reg_val]

            elif data_type == "uint32":
                int_val = int(value) & 0xFFFFFFFF
                regs = [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]
                if word_order == "little":
                    regs = [regs[1], regs[0]]
                return regs

            elif data_type == "int32":
                int_val = int(value)
                if int_val < 0:
                    int_val = int_val & 0xFFFFFFFF
                regs = [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]
                if word_order == "little":
                    regs = [regs[1], regs[0]]
                return regs

            elif data_type == "float32":
                packed = struct.pack('>f' if byte_order == "big" else '<f', float(value))
                regs = list(struct.unpack('>HH', packed))
                if word_order == "little":
                    regs = [regs[1], regs[0]]
                return regs

            elif data_type == "float32_swap":
                packed = struct.pack('>f', float(value))
                regs = list(struct.unpack('>HH', packed))
                regs = [regs[1], regs[0]]
                return regs

            elif data_type == "float64":
                packed = struct.pack('>d' if byte_order == "big" else '<d', float(value))
                regs = list(struct.unpack('>HHHH', packed))
                if word_order == "little":
                    regs = [regs[3], regs[2], regs[1], regs[0]]
                return regs

            elif data_type == "uint64":
                int_val = int(value) & 0xFFFFFFFFFFFFFFFF
                regs = [
                    (int_val >> 48) & 0xFFFF,
                    (int_val >> 32) & 0xFFFF,
                    (int_val >> 16) & 0xFFFF,
                    int_val & 0xFFFF
                ]
                if word_order == "little":
                    regs = [regs[3], regs[2], regs[1], regs[0]]
                return regs

            elif data_type == "int64":
                int_val = int(value)
                if int_val < 0:
                    int_val = int_val & 0xFFFFFFFFFFFFFFFF
                regs = [
                    (int_val >> 48) & 0xFFFF,
                    (int_val >> 32) & 0xFFFF,
                    (int_val >> 16) & 0xFFFF,
                    int_val & 0xFFFF
                ]
                if word_order == "little":
                    regs = [regs[3], regs[2], regs[1], regs[0]]
                return regs

            elif data_type == "string":
                encoded = str(value).encode('ascii')
                while len(encoded) % 2:
                    encoded += b'\x00'
                regs = []
                for i in range(0, len(encoded), 2):
                    if byte_order == "little":
                        regs.append(encoded[i] | (encoded[i + 1] << 8))
                    else:
                        regs.append((encoded[i] << 8) | encoded[i + 1])
                return regs

            else:
                logger.warning(f"Unknown data_type '{data_type}', treating as uint16")
                return [int(value) & 0xFFFF]

        except (ValueError, TypeError, struct.error) as e:
            logger.error(f"Failed to encode value {value} as {data_type}: {e}")
            return None

    async def write_registers(self, address: int, values: List[int]) -> bool:
        if not self.is_connected or not self._client:
            logger.error("Not connected to Modbus device")
            return False

        try:
            result = await self._client.write_registers(
                address=address,
                values=values,
                device_id=self._slave_id
            )

            if result.isError():
                logger.error(f"Error writing registers at address {address}: {result}")
                return False

            logger.info(f"Successfully wrote values {values} to address {address}")
            return True

        except Exception as e:
            logger.error(f"Error writing registers: {e}")
            return False

    @property
    def connection_info(self) -> Dict[str, Any]:
        info = {
            "connected": self.is_connected,
            "slave_id": self._slave_id,
            "device_status": self.get_device_status(),
            "offline_counter": self._offline_counter,
            "groups_count": len(self._read_groups)
        }
        info.update(self._get_connection_info())
        return info

    def _update_performance_stats(self, poll_duration: float, points_count: int, successful_count: int = 0):
        self._performance_stats["total_polls"] += 1
        self._performance_stats["total_points_read"] += points_count
        self._performance_stats["successful_points_read"] += successful_count
        self._performance_stats["last_poll_time"] = poll_duration
        self._performance_stats["total_time"] += poll_duration

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
