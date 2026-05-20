"""配置验证器

提供严格的配置验证规则，确保配置正确性和完整性。
"""

import logging
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """验证严重级别"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
    
    def add_info(self, message: str) -> None:
        self.info.append(message)
    
    def merge(self, other: 'ValidationResult') -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        if not other.is_valid:
            self.is_valid = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info
        }


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self._device_validators: Dict[str, Callable] = {}
        self._point_validators: Dict[str, Callable] = {}
        self._custom_rules: List[Callable] = []
    
    def register_device_validator(
        self,
        plugin_name: str,
        validator: Callable
    ) -> None:
        """注册设备验证器
        
        Args:
            plugin_name: 插件名称
            validator: 验证函数
        """
        self._device_validators[plugin_name] = validator
        logger.info(f"Registered device validator for {plugin_name}")
    
    def register_point_validator(
        self,
        data_type: str,
        validator: Callable
    ) -> None:
        """注册点位验证器
        
        Args:
            data_type: 数据类型
            validator: 验证函数
        """
        self._point_validators[data_type] = validator
        logger.info(f"Registered point validator for {data_type}")
    
    def add_custom_rule(
        self,
        rule: Callable
    ) -> None:
        """添加自定义验证规则
        
        Args:
            rule: 验证规则函数
        """
        self._custom_rules.append(rule)
        logger.info("Added custom validation rule")
    
    async def validate_device(
        self,
        device_config: Dict[str, Any]
    ) -> ValidationResult:
        """验证设备配置
        
        Args:
            device_config: 设备配置
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True)
        
        result = self._validate_device_basic(device_config, result)
        
        plugin_name = device_config.get('plugin_name', '')
        if plugin_name in self._device_validators:
            try:
                plugin_result = await self._device_validators[plugin_name](device_config)
                result.merge(plugin_result)
            except Exception as e:
                result.add_error(f"Plugin validator failed: {e}")
        
        for point in device_config.get('points', []):
            point_result = await self.validate_point(point, device_config)
            result.merge(point_result)
        
        for rule in self._custom_rules:
            try:
                rule_result = await rule(device_config)
                result.merge(rule_result)
            except Exception as e:
                result.add_error(f"Custom rule failed: {e}")
        
        return result
    
    async def validate_point(
        self,
        point_config: Dict[str, Any],
        device_config: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """验证点位配置
        
        Args:
            point_config: 点位配置
            device_config: 设备配置（可选）
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True)
        
        result = self._validate_point_basic(point_config, result)
        
        data_type = point_config.get('data_type', '')
        if data_type in self._point_validators:
            try:
                type_result = await self._point_validators[data_type](point_config, device_config)
                result.merge(type_result)
            except Exception as e:
                result.add_error(f"Data type validator failed: {e}")
        
        return result
    
    def _validate_device_basic(
        self,
        config: Dict[str, Any],
        result: ValidationResult
    ) -> ValidationResult:
        """基础设备验证"""
        if not config.get('asset'):
            result.add_error("Device asset is required")
        elif not re.match(r'^[a-zA-Z0-9_\-]+$', config['asset']):
            result.add_error(f"Invalid device asset name: {config['asset']}")
        
        if not config.get('plugin_name'):
            result.add_error("Plugin name is required")
        
        if config.get('enabled') is None:
            result.add_warning("Enabled field is missing, defaulting to true")
        
        status = config.get('status', 'active')
        valid_statuses = ['active', 'inactive', 'maintenance', 'error']
        if status not in valid_statuses:
            result.add_error(f"Invalid status: {status}, must be one of {valid_statuses}")
        
        plugin_config = config.get('plugin_config', {})
        if not isinstance(plugin_config, dict):
            result.add_error("Plugin config must be a dictionary")
        
        metadata = config.get('metadata', {})
        if not isinstance(metadata, dict):
            result.add_error("Metadata must be a dictionary")
        
        tags = config.get('tags', [])
        if not isinstance(tags, list):
            result.add_error("Tags must be a list")
        elif not all(isinstance(tag, str) for tag in tags):
            result.add_error("All tags must be strings")
        
        points = config.get('points', [])
        if not isinstance(points, list):
            result.add_error("Points must be a list")
        
        point_names = [p.get('name') for p in points if p.get('name')]
        if len(point_names) != len(set(point_names)):
            result.add_error("Duplicate point names found")
        
        return result
    
    def _validate_point_basic(
        self,
        config: Dict[str, Any],
        result: ValidationResult
    ) -> ValidationResult:
        """基础点位验证"""
        if not config.get('name'):
            result.add_error("Point name is required")
        elif not re.match(r'^[a-zA-Z0-9_\-]+$', config['name']):
            result.add_error(f"Invalid point name: {config['name']}")
        
        if not config.get('data_type'):
            result.add_error("Point data type is required")
        
        valid_data_types = [
            'bool', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64',
            'float32', 'float64', 'string', 'float32_swap'
        ]
        data_type = config.get('data_type', '')
        if data_type and data_type not in valid_data_types:
            result.add_warning(f"Unusual data type: {data_type}")
        
        if config.get('enabled') is None:
            result.add_info("Point enabled field is missing, defaulting to true")
        
        point_config = config.get('config', {})
        if not isinstance(point_config, dict):
            result.add_error("Point config must be a dictionary")
        
        metadata = config.get('metadata', {})
        if not isinstance(metadata, dict):
            result.add_error("Point metadata must be a dictionary")
        
        tags = config.get('tags', [])
        if not isinstance(tags, list):
            result.add_error("Point tags must be a list")
        
        return result


class ModbusValidator:
    """Modbus协议验证器"""
    
    @staticmethod
    async def validate_device(config: Dict[str, Any]) -> ValidationResult:
        """验证Modbus设备配置"""
        result = ValidationResult(is_valid=True)
        
        plugin_config = config.get('plugin_config', {})
        
        if 'host' not in plugin_config:
            result.add_error("Modbus host is required")
        
        port = plugin_config.get('port')
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                result.add_error(f"Invalid Modbus port: {port}")
        
        slave_id = plugin_config.get('slave_id')
        if slave_id is not None:
            if not isinstance(slave_id, int) or slave_id < 0 or slave_id > 255:
                result.add_error(f"Invalid Modbus slave ID: {slave_id}")
        
        timeout = plugin_config.get('timeout')
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                result.add_error(f"Invalid timeout: {timeout}")
        
        return result
    
    @staticmethod
    async def validate_point(
        point_config: Dict[str, Any],
        device_config: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """验证Modbus点位配置"""
        result = ValidationResult(is_valid=True)
        
        config = point_config.get('config', {})
        
        if 'address' not in config:
            result.add_error("Modbus address is required")
        elif not isinstance(config['address'], int) or config['address'] < 0:
            result.add_error(f"Invalid Modbus address: {config['address']}")
        
        register_type = config.get('register_type', 'holding')
        valid_types = ['holding', 'input', 'coil', 'discrete_input']
        if register_type not in valid_types:
            result.add_error(f"Invalid register type: {register_type}")
        
        count = config.get('count')
        if count is not None:
            if not isinstance(count, int) or count < 1:
                result.add_error(f"Invalid register count: {count}")
        
        data_type = point_config.get('data_type', '')
        expected_counts = {
            'int16': 1, 'uint16': 1,
            'int32': 2, 'uint32': 2, 'float32': 2,
            'int64': 4, 'uint64': 4, 'float64': 4
        }
        
        if data_type in expected_counts and count is not None:
            expected = expected_counts[data_type]
            if count != expected:
                result.add_warning(
                    f"Register count {count} doesn't match data type {data_type} (expected {expected})"
                )
        
        return result


class BACnetValidator:
    """BACnet协议验证器"""
    
    @staticmethod
    async def validate_device(config: Dict[str, Any]) -> ValidationResult:
        """验证BACnet设备配置"""
        result = ValidationResult(is_valid=True)
        
        plugin_config = config.get('plugin_config', {})
        
        if 'device_id' not in plugin_config:
            result.add_error("BACnet device ID is required")
        elif not isinstance(plugin_config['device_id'], int):
            result.add_error("BACnet device ID must be an integer")
        
        port = plugin_config.get('port', 47808)
        if not isinstance(port, int) or port < 1 or port > 65535:
            result.add_error(f"Invalid BACnet port: {port}")
        
        return result
    
    @staticmethod
    async def validate_point(
        point_config: Dict[str, Any],
        device_config: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """验证BACnet点位配置"""
        result = ValidationResult(is_valid=True)
        
        config = point_config.get('config', {})
        
        if 'object_type' not in config:
            result.add_error("BACnet object type is required")
        
        if 'object_instance' not in config:
            result.add_error("BACnet object instance is required")
        elif not isinstance(config['object_instance'], int):
            result.add_error("BACnet object instance must be an integer")
        
        return result


def create_default_validator() -> ConfigValidator:
    """创建默认验证器"""
    validator = ConfigValidator()
    
    validator.register_device_validator('modbus_tcp', ModbusValidator.validate_device)
    validator.register_device_validator('modbus_rtu', ModbusValidator.validate_device)
    validator.register_point_validator('int16', ModbusValidator.validate_point)
    validator.register_point_validator('uint16', ModbusValidator.validate_point)
    validator.register_point_validator('int32', ModbusValidator.validate_point)
    validator.register_point_validator('uint32', ModbusValidator.validate_point)
    validator.register_point_validator('int64', ModbusValidator.validate_point)
    validator.register_point_validator('uint64', ModbusValidator.validate_point)
    validator.register_point_validator('float32', ModbusValidator.validate_point)
    validator.register_point_validator('float64', ModbusValidator.validate_point)
    
    validator.register_device_validator('bacnet', BACnetValidator.validate_device)
    
    return validator
