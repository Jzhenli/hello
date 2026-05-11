"""Modbus Data Converter - Converts Modbus register data to standard format (shared by TCP and RTU)"""

import logging
import struct
from typing import Any, Dict, List, Optional

from .constants import (
    MODBUS_TO_STANDARD_TYPE,
    BYTE_ORDER_BIG,
    BYTE_ORDER_LITTLE,
    WORD_ORDER_BIG,
    WORD_ORDER_LITTLE,
)

logger = logging.getLogger(__name__)

MODBUS_ERROR_MESSAGES = {
    10: "device_offline",
}


class ModbusConverter:
    """
    Modbus 数据转换器 - 符合 DataConverter 协议

    将 Modbus 设备原始数据转换为标准格式。
    TCP 和 RTU 共享此转换器，因为数据编码方式完全相同。
    """

    @staticmethod
    def _get_point_config(point: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取点位配置字段（优先从 config 子对象读取，兼容顶层读取）"""
        point_config = point.get("config", {})
        if key in point_config:
            return point_config[key]
        if key in point:
            return point[key]
        return default

    def get_supported_data_types(self) -> List[str]:
        """获取支持的数据类型"""
        return [
            "bool",
            "uint16", "int16",
            "uint32", "int32",
            "float32", "float32_swap", "float64",
            "uint64", "int64",
            "string"
        ]

    def convert(
        self,
        raw_data: Dict[str, Any],
        point_configs: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: 原始数据字典
            point_configs: 点位配置列表
            context: 上下文信息
                - device_id: 设备ID
                - connection_status: 连接状态

        Returns:
            标准数据点字典列表
        """
        if not raw_data or not point_configs:
            return []

        device_id = context.get("device_id", "unknown")
        connection_status = context.get("connection_status", "connected")
        timestamp = context.get("timestamp")

        points = []

        for point_config in point_configs:
            point_name = point_config.get("name")
            if not point_name:
                continue

            raw_value = raw_data.get(point_name)

            data_type = self._get_point_config(point_config, "data_type", "uint16")
            unit = self._get_point_config(point_config, "unit")
            scale = self._get_point_config(point_config, "scale")
            offset = self._get_point_config(point_config, "offset")

            converted_value = None
            quality = "bad"
            error_code = None

            if connection_status != "connected":
                error_code = 10
                if raw_value is not None:
                    converted_value = self._convert_value(raw_value, data_type, scale, offset)
            elif raw_value is not None:
                converted_value = self._convert_value(raw_value, data_type, scale, offset)
                quality = self._assess_quality(
                    converted_value,
                    point_config,
                    connection_status
                )
            else:
                error_code = 10

            metadata = {
                "address": self._get_point_config(point_config, "address"),
                "register_type": self._get_point_config(point_config, "register_type", "holding"),
                "slave_id": self._get_point_config(point_config, "slave_id"),
                "raw_value": raw_value
            }

            if scale is not None:
                metadata["scale"] = scale
            if offset is not None:
                metadata["offset"] = offset
            if error_code is not None:
                metadata["error_code"] = error_code
                metadata["error_message"] = MODBUS_ERROR_MESSAGES.get(error_code, "unknown_error")

            point_data = {
                "device_id": device_id,
                "point_name": point_name,
                "value": converted_value,
                "data_type": data_type,
                "standard_data_type": MODBUS_TO_STANDARD_TYPE.get(data_type, "string"),
                "unit": unit,
                "quality": quality,
                "metadata": metadata
            }

            if timestamp:
                point_data["timestamp"] = timestamp

            points.append(point_data)

        return points

    def _convert_value(
        self,
        raw_value: Any,
        data_type: str,
        scale: Optional[float] = None,
        offset: Optional[float] = None
    ) -> Any:
        """转换值类型并应用缩放和偏移"""
        if raw_value is None:
            return None

        value = raw_value

        try:
            if scale is not None:
                value = float(value) * scale
            if offset is not None:
                value = float(value) + offset

            if data_type == "bool":
                value = bool(value)
            elif data_type in ("uint16", "int16", "uint32", "int32", "uint64", "int64"):
                value = int(value)
            elif data_type in ("float32", "float32_swap", "float64", "float"):
                value = float(value)

            return value
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert value {raw_value}: {e}")
            return None

    def _assess_quality(
        self,
        value: Any,
        point_config: Dict[str, Any],
        connection_status: str
    ) -> str:
        if connection_status != "connected":
            return "bad"

        if value is None:
            return "bad"

        metadata = point_config.get("metadata", {})
        config = point_config.get("config", {})

        min_value = self._get_range_value(metadata, config, "min_value", "min")
        max_value = self._get_range_value(metadata, config, "max_value", "max")

        if min_value is not None and max_value is not None:
            try:
                if not (min_value <= value <= max_value):
                    return "uncertain"
            except TypeError:
                pass

        return "good"

    @staticmethod
    def _get_range_value(
        metadata: Dict[str, Any],
        point_config: Dict[str, Any],
        primary_key: str,
        fallback_key: str
    ) -> Any:
        if primary_key in metadata and metadata[primary_key] is not None:
            return metadata[primary_key]
        if fallback_key in metadata and metadata[fallback_key] is not None:
            return metadata[fallback_key]
        if primary_key in point_config and point_config[primary_key] is not None:
            return point_config[primary_key]
        return None

    def convert_register_value(self, registers: List[int], data_type: str) -> Any:
        """
        将寄存器值转换为指定类型（向后兼容方法）

        Args:
            registers: 寄存器值列表
            data_type: 目标数据类型

        Returns:
            转换后的值
        """
        return self.convert_register_value_with_order(registers, data_type, BYTE_ORDER_BIG, WORD_ORDER_BIG)

    def convert_register_value_with_order(
        self,
        registers: List[int],
        data_type: str,
        byte_order: str = BYTE_ORDER_BIG,
        word_order: str = WORD_ORDER_BIG
    ) -> Any:
        """
        将寄存器值转换为指定类型，支持字节序和字序配置

        Args:
            registers: 寄存器值列表
            data_type: 目标数据类型
            byte_order: 字节序 ("big" 或 "little")
            word_order: 字序 ("big" 或 "little")

        Returns:
            转换后的值

        字节序/字序说明:
            - byte_order="big": 寄存器内高字节在前 (AB CD)
            - byte_order="little": 寄存器内低字节在前 (BA DC)
            - word_order="big": 高字寄存器在前 (reg0=高字, reg1=低字)
            - word_order="little": 低字寄存器在前 (reg0=低字, reg1=高字)

        注意:
            对于 uint16/int16 单寄存器类型，byte_order="little" 会交换寄存器内的高低字节。
            这用于某些非标准 Modbus 设备，标准 Modbus 协议中单寄存器通常为大端序。
        """
        try:
            if data_type == "bool":
                return bool(registers[0]) if registers else None

            elif data_type == "uint16":
                if not registers:
                    return None
                value = registers[0]
                if byte_order == BYTE_ORDER_LITTLE:
                    value = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
                return value

            elif data_type == "int16":
                if not registers:
                    return None
                value = registers[0]
                if byte_order == BYTE_ORDER_LITTLE:
                    value = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
                return value if value < 32768 else value - 65536

            elif data_type == "uint32":
                if len(registers) >= 2:
                    if word_order == WORD_ORDER_LITTLE:
                        return (registers[1] << 16) | registers[0]
                    return (registers[0] << 16) | registers[1]
                return None

            elif data_type == "int32":
                if len(registers) >= 2:
                    if word_order == WORD_ORDER_LITTLE:
                        value = (registers[1] << 16) | registers[0]
                    else:
                        value = (registers[0] << 16) | registers[1]
                    return value if value < 2147483648 else value - 4294967296
                return None

            elif data_type == "float32":
                if len(registers) >= 2:
                    return self._convert_float32(registers, byte_order, word_order)
                return None

            elif data_type == "float32_swap":
                if len(registers) >= 2:
                    return self._convert_float32(registers, BYTE_ORDER_BIG, WORD_ORDER_LITTLE)
                return None

            elif data_type == "float64":
                if len(registers) >= 4:
                    return self._convert_float64(registers, byte_order, word_order)
                return None

            elif data_type == "uint64":
                if len(registers) >= 4:
                    if word_order == WORD_ORDER_LITTLE:
                        return (registers[3] << 48) | (registers[2] << 32) | (registers[1] << 16) | registers[0]
                    return (registers[0] << 48) | (registers[1] << 32) | (registers[2] << 16) | registers[3]
                return None

            elif data_type == "int64":
                if len(registers) >= 4:
                    if word_order == WORD_ORDER_LITTLE:
                        value = (registers[3] << 48) | (registers[2] << 32) | (registers[1] << 16) | registers[0]
                    else:
                        value = (registers[0] << 48) | (registers[1] << 32) | (registers[2] << 16) | registers[3]
                    return value if value < 9223372036854775808 else value - 18446744073709551616
                return None

            elif data_type == "string":
                chars = []
                for reg in registers:
                    if byte_order == BYTE_ORDER_LITTLE:
                        chars.append(chr(reg & 0xFF))
                        chars.append(chr((reg >> 8) & 0xFF))
                    else:
                        chars.append(chr((reg >> 8) & 0xFF))
                        chars.append(chr(reg & 0xFF))
                return ''.join(chars).rstrip('\x00')

            else:
                return registers[0] if registers else None

        except Exception as e:
            logger.error(f"Error converting register value: {e}")
            return None

    def _convert_float32(
        self,
        registers: List[int],
        byte_order: str,
        word_order: str
    ) -> Optional[float]:
        """转换 float32 类型"""
        if word_order == WORD_ORDER_LITTLE:
            reg0, reg1 = registers[1], registers[0]
        else:
            reg0, reg1 = registers[0], registers[1]

        if byte_order == BYTE_ORDER_LITTLE:
            packed = struct.pack('<HH', reg0, reg1)
        else:
            packed = struct.pack('>HH', reg0, reg1)

        return struct.unpack('>f' if byte_order == BYTE_ORDER_BIG else '<f', packed)[0]

    def _convert_float64(
        self,
        registers: List[int],
        byte_order: str,
        word_order: str
    ) -> Optional[float]:
        """转换 float64 类型"""
        if word_order == WORD_ORDER_LITTLE:
            regs = [registers[3], registers[2], registers[1], registers[0]]
        else:
            regs = [registers[0], registers[1], registers[2], registers[3]]

        if byte_order == BYTE_ORDER_LITTLE:
            packed = struct.pack('<HHHH', *regs)
            return struct.unpack('<d', packed)[0]
        else:
            packed = struct.pack('>HHHH', *regs)
            return struct.unpack('>d', packed)[0]
