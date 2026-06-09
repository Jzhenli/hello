# MQTT 客户适配器可插拔方案

## 一、背景与问题

当前 `MQTTClientPlugin` 只有一个 `MQTTClientAdapter`，数据格式硬编码。面对多个私有云客户，每个客户有不同的上行/下行数据格式，存在以下问题：

1. **上行格式固定**：不同客户要求不同的 JSON 结构（字段名、嵌套方式、时间戳格式等）
2. **下行格式固定**：`DownlinkHandler` 硬编码了命令解析（`asset/data`）和响应格式（`status/error`）
3. **扩展困难**：新增客户格式需要修改已有代码，容易引入回归问题
4. **无法配置驱动**：无法通过配置切换数据格式

### 现状架构

```
┌─────────────────────────────────────────────────────┐
│                  NorthPluginBase                     │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │ _data_adapter│◄───│ _create_data_adapter()   │   │
│  └──────┬───────┘    └──────────────────────────┘   │
│         │                                            │
│    adapt_readings()  ──► adapter.adapt_upload()      │
│    adapt_command()   ──► adapter.adapt_command()     │
│    parse_response()  ──► adapter.parse_response()    │
└─────────────────────────────────────────────────────┘
         ▲
         │ 继承
┌────────┴────────────────────────────────────────────┐
│              MQTTClientPlugin                        │
│  _create_data_adapter() → MQTTClientAdapter(唯一)   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │           DownlinkHandler                     │   │
│  │  handle_message():                            │   │
│  │    硬编码 asset/data 解析                      │   │
│  │    硬编码 {"status":"success/error"} 响应格式  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**问题点**：

- `MQTTClientAdapter` 是唯一实现，格式固定
- `DownlinkHandler` 硬编码了下行命令解析和响应格式
- `DataAdapter` Protocol 缺少下行命令解析和响应格式化方法

## 二、设计目标

| 目标 | 说明 |
|------|------|
| **加客户低侵入** | 新增客户格式只需在 `adapters/` 下加一个文件，并在注册列表加一行 |
| **配置驱动** | 部署时通过 `adapter: customer_a` 一行配置切换 |
| **格式隔离** | 每个客户的格式逻辑独立，互不干扰 |
| **协议复用** | MQTT 连接/重连/订阅/发布逻辑完全复用，只换数据格式 |
| **向后兼容** | 现有部署无需任何改动，默认行为不变 |
| **低门槛** | 客户适配器只需覆盖与默认格式不同的方法 |
| **接口隔离** | MQTT 专有方法不污染全局 `DataAdapter` Protocol |
| **启动零开销** | 按需导入，不使用 MQTT 插件时不加载适配器模块 |
| **类型安全** | 使用 Protocol 进行静态类型检查，IDE 可追踪依赖 |

## 三、目标架构

```
┌──────────────────────────────────────────────────────────────┐
│                     MQTTClientPlugin                          │
│                                                               │
│  _create_data_adapter() ──► AdapterRegistry.get("customer_a")│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  DownlinkHandler                         │ │
│  │  handle_message():                                       │ │
│  │    adapter.parse_command(raw) → 统一 {asset, data}       │ │
│  │    adapter.format_result(result, raw) → 客户专属响应格式  │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    AdapterRegistry                            │
│  "standard"    → StandardMQTTAdapter   (当前默认)            │
│  "customer_a"  → CustomerAAdapter      (客户A)               │
│  "customer_b"  → CustomerBAdapter      (客户B)               │
│  "customer_c"  → CustomerCAdapter      (客户C)               │
│  显式注册 + 按需导入（启动零开销）                            │
└──────────────────────────────────────────────────────────────┘
```

## 四、详细设计

### 4.1 目录结构

```
mqtt_client/
├── __init__.py              # 不变
├── adapter.py               # 重构：MQTTClientAdapter 继承基类，注册为 "standard"
├── adapters/                # 新增：客户适配器包
│   ├── __init__.py          #   注册表 + 显式注册 + 按需导入
│   ├── base.py              #   基类（提供默认实现 + MQTT 扩展接口 + 配置验证）
│   ├── protocol.py          #   协议定义（类型安全）
│   ├── exceptions.py        #   异常定义
│   └── customer_a.py        #   客户A适配器（示例）
├── constants.py             # 不变
├── downlink.py              # 微调：格式逻辑委托给适配器
├── types.py                 # 新增：DownlinkResult 等共享类型定义
└── plugin.py                # 微调：根据配置选择适配器
```

### 4.2 DataAdapter Protocol 不变，MQTT 扩展接口定义在基类中

**关键决策**：`parse_command`、`format_result`、`to_json` 是 MQTT 下行场景专有的方法，不应加入全局 `DataAdapter` Protocol（该 Protocol 被 XNC 等其他北向插件共享）。这些方法作为 `MQTTAdapterBase` 的扩展接口，由 `DownlinkHandler` 通过适配器实例直接调用。

全局 `DataAdapter` Protocol（`xcore/transform/adapter.py`）**保持不变**：

```python
class DataAdapter(Protocol):
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any: ...
    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any: ...
    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]: ...
```

MQTT 专有扩展接口定义在 `MQTTAdapterBase` 中（见 4.3 节），`DownlinkHandler` 通过 `self._adapter` 调用，鸭子类型保证兼容。

### 4.3 适配器基类 — `adapters/base.py`

提供所有方法的默认实现（等同于当前 Standard 格式），客户适配器只需覆盖与默认格式不同的方法。

```python
"""MQTT Adapter Base - 提供默认实现，客户适配器可选择性覆盖"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, ClassVar

from xagent.xcore.storage.interface import Reading

logger = logging.getLogger(__name__)


class MQTTAdapterBase:
    """
    MQTT 适配器基类

    提供 DataAdapter Protocol 三个核心方法的默认实现，
    以及 MQTT 专有扩展方法（parse_command / format_result / to_json）。

    客户适配器只需覆盖与默认格式不同的方法。
    """

    # ===== 类级元信息（子类可覆盖） =====
    __adapter_name__: ClassVar[str] = ""
    __adapter_description__: ClassVar[str] = ""
    __adapter_config_schema__: ClassVar[Dict[str, Any]] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        errors = self.validate_config(self.config)
        if errors:
            raise ValueError(f"Invalid config for {self.__class__.__name__}: {errors}")

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> List[str]:
        """
        验证配置

        子类可覆盖以添加自定义验证逻辑。
        返回错误列表，空列表表示验证通过。
        """
        errors = []

        # 如果定义了 schema，进行基础验证
        schema = cls.__adapter_config_schema__
        if schema:
            for key, spec in schema.items():
                if spec.get("required", False) and key not in config:
                    errors.append(f"'{key}' is required")

        return errors

    @classmethod
    def get_description(cls) -> str:
        """获取适配器描述"""
        return cls.__adapter_description__ or f"MQTT adapter: {cls.__name__}"

    # ===== DataAdapter Protocol 核心方法 =====

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """适配上传数据 - 默认实现：单条/批量格式"""
        try:
            if not readings:
                return None
            if len(readings) == 1:
                return self._adapt_single_reading(readings[0], context)
            else:
                return self._adapt_batch_readings(readings, context)
        except Exception as e:
            logger.error(f"Error adapting upload data: {e}")
            return None

    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        context = context or {}
        device_status_map = context.get("device_status_map", {})

        payload = {
            "asset": reading.asset,
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": reading.data,
        }

        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status

        if reading.tags:
            payload["tags"] = reading.tags
        if reading.standard_points:
            payload["standard_points"] = reading.standard_points

        return payload

    def _adapt_batch_readings(self, readings: List[Reading], context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "count": len(readings),
            "readings": [self._adapt_single_reading(r, context) for r in readings],
            "timestamp": self._format_timestamp(readings[0].timestamp) if readings else None,
        }

    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """适配下行命令 - 默认实现：标准 {asset, data} 格式"""
        return {
            "asset": command_data.get("asset", ""),
            "data": command_data.get("data", {}),
            "timestamp": context.get("timestamp"),
        }

    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析响应数据 - 默认实现：支持 dict/bytes/str"""
        try:
            if isinstance(response, dict):
                return response
            if isinstance(response, bytes):
                try:
                    return json.loads(response.decode("utf-8"))
                except json.JSONDecodeError:
                    return {"raw": response.decode("utf-8")}
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    return {"raw": response}
            return {"raw": str(response)}
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {"raw": str(response), "error": str(e)}

    # ===== MQTT 专有扩展方法 =====

    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析下行命令 - 将客户特有的命令格式转换为统一内部格式

        Args:
            raw: 客户下发的原始命令字典

        Returns:
            统一格式: {"asset": str, "data": Dict[str, Any]}
        """
        return {
            "asset": raw.get("asset", ""),
            "data": raw.get("data", {}),
        }

    def format_result(self, result: "DownlinkResult") -> Dict[str, Any]:
        """
        格式化命令执行结果 - 将内部结果转换为客户要求的响应格式

        Args:
            result: DownlinkResult 对象，包含 success/asset/data/error/raw_command 字段

        Returns:
            客户要求的响应字典
        """
        response = {"timestamp": time.time()}
        if result.success:
            response["status"] = "success"
            if result.asset:
                response["asset"] = result.asset
            if result.data:
                response["data"] = result.data
        else:
            response["status"] = "error"
            if result.error:
                response["error"] = result.error
        return response

    def to_json(self, payload: Any) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(payload, ensure_ascii=False)

    # ===== 可覆盖的工具方法 =====

    def _format_timestamp(self, timestamp: float) -> Any:
        """格式化时间戳 - 子类可覆盖以支持不同格式

        默认返回原始 Unix 时间戳。
        """
        return timestamp
```

**设计要点**：

1. `adapt_upload` 保留 try/except 异常处理，返回 None 表示适配失败
2. `_format_timestamp` 提取为可覆盖的方法，`_adapt_batch_readings` 也会调用它，避免子类遗漏批量模式的时间戳格式化
3. `parse_command` / `format_result` / `to_json` 作为 MQTT 专有扩展，不污染全局 `DataAdapter` Protocol
4. `format_result` 参数类型为 `DownlinkResult`（定义在 `types.py`，见 4.4 节），避免层级依赖
5. `__adapter_description__` / `__adapter_config_schema__` 提供适配器元信息，支持自描述
6. `validate_config` 提供配置验证，子类可覆盖以添加自定义验证逻辑

### 4.4 共享类型定义 — `types.py`

将 `DownlinkResult` 从 `downlink.py` 提取到独立模块，避免 `adapters/base.py` 与 `downlink.py` 之间的循环依赖。

```python
"""MQTT Client Shared Types - 共享类型定义"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DownlinkResult:
    """下行命令执行结果"""
    success: bool
    asset: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_command: Optional[Dict[str, Any]] = None  # 保留原始命令，供 format_result 使用
```

**设计要点**：

- `raw_command` 字段保留原始客户命令，使 `format_result` 可以访问原始命令中的额外信息（如命令类型、消息ID等），而不仅限于解析后的 `{asset, data}`
- 独立模块避免 `base.py` → `downlink.py` 的层级依赖

### 4.5 异常定义 — `adapters/exceptions.py`

定义适配器相关的异常类型，提供友好的错误信息。

```python
"""MQTT Adapter Exceptions - 适配器相关异常"""

from typing import List


class AdapterError(Exception):
    """适配器基础异常"""
    pass


class AdapterNotFoundError(AdapterError):
    """适配器未找到"""
    def __init__(self, name: str, available: List[str]):
        self.name = name
        self.available = available
        super().__init__(f"Adapter '{name}' not found. Available: {available}")


class AdapterLoadError(AdapterError):
    """适配器加载失败"""
    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f"Failed to load adapter '{name}': {reason}")


class AdapterConfigError(AdapterError):
    """适配器配置错误"""
    def __init__(self, name: str, errors: List[str]):
        self.name = name
        self.errors = errors
        super().__init__(f"Invalid config for adapter '{name}': {errors}")
```

### 4.6 协议定义 — `adapters/protocol.py`

定义 MQTT 适配器协议，提供类型安全检查。

```python
"""MQTT Adapter Protocol - 类型定义"""

from typing import Any, Dict, List, Protocol, runtime_checkable

from xagent.xcore.storage.interface import Reading


@runtime_checkable
class MQTTAdapterProtocol(Protocol):
    """
    MQTT 适配器协议 - 定义必须实现的方法

    使用 @runtime_checkable 装饰器，支持 isinstance() 检查。
    静态类型检查器（如 mypy）会验证实现类是否满足协议。
    """

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any: ...
    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any: ...
    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]: ...
    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]: ...
    def format_result(self, result: "DownlinkResult") -> Dict[str, Any]: ...
    def to_json(self, payload: Any) -> str: ...
```

### 4.7 适配器注册表 — `adapters/__init__.py`

采用**显式注册 + 按需导入**方案，避免启动时自动发现带来的性能开销。

```python
"""MQTT Adapter Registry - 显式注册 + 按需导入 + 类型安全"""

import logging
from typing import Any, Dict, Type, Callable, Optional, List, Tuple

from .exceptions import AdapterNotFoundError, AdapterLoadError, AdapterConfigError

logger = logging.getLogger(__name__)

# 注册表
_REGISTRY: Dict[str, Type] = {}
_IMPORTERS: Dict[str, Callable[[], None]] = {}


def register(name: str):
    """
    装饰器：注册适配器类

    用法:
        @register("customer_a")
        class CustomerAAdapter(MQTTAdapterBase):
            ...
    """
    def decorator(cls):
        if name in _REGISTRY:
            logger.warning(f"Overwriting adapter: {name}")
        _REGISTRY[name] = cls
        logger.debug(f"Registered adapter: {name} -> {cls.__name__}")
        return cls
    return decorator


def get_adapter(name: str, config: Optional[Dict[str, Any]] = None) -> Any:
    """
    获取适配器实例

    首次调用时自动按需导入对应模块。

    Args:
        name: 适配器名称
        config: 适配器配置

    Returns:
        适配器实例

    Raises:
        AdapterNotFoundError: 适配器未找到
        AdapterLoadError: 适配器加载失败
        AdapterConfigError: 配置验证失败
    """
    # 按需导入
    if name not in _REGISTRY and name in _IMPORTERS:
        try:
            logger.debug(f"Lazy importing adapter: {name}")
            _IMPORTERS[name]()
        except Exception as e:
            raise AdapterLoadError(name, str(e))

    # 检查是否注册
    if name not in _REGISTRY:
        raise AdapterNotFoundError(name, list_available())

    # 实例化
    try:
        return _REGISTRY[name](config or {})
    except ValueError as e:
        raise AdapterConfigError(name, [str(e)])


def list_adapters() -> List[str]:
    """列出已加载的适配器"""
    return sorted(_REGISTRY.keys())


def list_available() -> List[str]:
    """列出所有可用的适配器（包括未加载的）"""
    return sorted(set(_REGISTRY.keys()) | set(_IMPORTERS.keys()))


def get_adapter_info(name: str) -> Optional[Dict[str, Any]]:
    """
    获取适配器详细信息

    Returns:
        {
            "name": str,
            "class": str,
            "description": str,
            "config_schema": dict,
            "loaded": bool
        }
    """
    if name in _REGISTRY:
        cls = _REGISTRY[name]
        return {
            "name": name,
            "class": cls.__name__,
            "description": getattr(cls, "__adapter_description__", ""),
            "config_schema": getattr(cls, "__adapter_config_schema__", {}),
            "loaded": True,
        }
    elif name in _IMPORTERS:
        return {"name": name, "loaded": False}
    return None


# ===== 适配器导入注册 =====
# 新增客户只需在列表中添加一行元组 (name, module_path)

_ADAPTER_IMPORTS: List[Tuple[str, str]] = [
    ("standard", ".adapter"),           # 标准适配器
    ("customer_a", ".customer_a"),      # 客户A
    ("customer_b", ".customer_b"),      # 客户B
    # 新增客户只需在这里加一行: ("customer_c", ".customer_c"),
]

for _name, _module in _ADAPTER_IMPORTS:
    _IMPORTERS[_name] = lambda m=_module: __import__(m, package=__name__)
```

**设计要点**：

1. **显式注册**：在 `_ADAPTER_IMPORTS` 列表中显式声明所有适配器，新增客户只需加一行元组
2. **按需导入**：`get_adapter()` 首次调用时才导入对应模块，启动零开销
3. **类型安全**：配合 `MQTTAdapterProtocol` 进行静态类型检查
4. **友好错误**：自定义异常类提供清晰的错误信息
5. **可观测性**：`get_adapter_info()` 和 `list_available()` 支持调试和监控

### 4.8 现有 adapter.py 重构

将 `MQTTClientAdapter` 改为继承 `MQTTAdapterBase`，并注册为 `"standard"`。保留原有的 mapping / timestamp / metadata 增强功能。

```python
"""Generic MQTT Cloud Adapter - Standard format (default)"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from xagent.xcore.storage.interface import Reading

from .adapters import register
from .adapters.base import MQTTAdapterBase

logger = logging.getLogger(__name__)


@register("standard")
class MQTTClientAdapter(MQTTAdapterBase):
    """
    MQTT Client 标准适配器 - 默认格式

    保持原有行为不变，继承 MQTTAdapterBase，
    增加设备名映射、属性映射、时间戳格式化等增强功能。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
        self._property_mapping = self.config.get("property_mapping", {})
        self._device_name_mapping = self.config.get("device_name_mapping", {})

    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """覆盖基类方法，增加 mapping 和 metadata 功能"""
        context = context or {}
        device_status_map = context.get("device_status_map", {})

        payload = {
            "asset": self._map_device_name(reading.asset),
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": self._map_properties(reading.data),
        }

        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status

        if self._include_metadata:
            payload["tags"] = reading.tags
            if reading.standard_points:
                payload["standard_points"] = reading.standard_points

        if self._include_quality and reading.standard_points:
            quality_info = []
            for sp in reading.standard_points:
                if "quality" in sp:
                    quality_info.append({
                        "point_name": sp.get("point_name"),
                        "quality": sp.get("quality"),
                    })
            if quality_info:
                payload["quality"] = quality_info

        return payload

    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """覆盖基类方法，增加 mapping 功能"""
        return {
            "asset": self._map_device_name(command_data.get("asset", "")),
            "data": self._map_properties(command_data.get("data", {})),
            "timestamp": context.get("timestamp"),
        }

    def _format_timestamp(self, timestamp: float) -> Any:
        """覆盖基类方法，支持多种时间戳格式"""
        if self._timestamp_format in ("iso", "iso8601"):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        elif self._timestamp_format == "milliseconds":
            return int(timestamp * 1000)
        return timestamp

    def _map_device_name(self, device_name: str) -> str:
        """映射设备名称（内部名称 → 客户名称，仅用于上行方向）"""
        if self._device_name_mapping:
            return self._device_name_mapping.get(device_name, device_name)
        return device_name

    def _map_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """映射属性名称（内部名称 → 客户名称，仅用于上行方向）"""
        if not self._property_mapping:
            return data
        mapped_data = {}
        for key, value in data.items():
            mapped_key = self._property_mapping.get(key, key)
            mapped_data[mapped_key] = value
        return mapped_data
```

**设计要点**：

1. **`parse_command` 不做 mapping**：`_map_device_name` 和 `_map_properties` 是正向映射（内部→客户），仅用于上行方向。下行 `parse_command` 直接透传，不做反向映射，避免语义错误。如果客户确实需要下行方向的名称映射，应在客户适配器中自行实现反向映射逻辑。
2. **`_adapt_batch_readings` 不需要覆盖**：基类已调用 `self._format_timestamp()`，子类覆盖 `_format_timestamp` 即可同时生效于单条和批量模式。
3. **`adapt_upload` 不需要覆盖**：基类已包含 try/except 异常处理。

### 4.9 客户适配器示例 — `adapters/customer_a.py`

```python
"""客户A私有云适配器

上行格式:
{
    "sn": "设备SN",
    "ts": 毫秒时间戳,
    "metrics": {"temp": 25.5, "humi": 60}
}

下行命令格式:
{
    "cmd": "set",
    "sn": "设备SN",
    "params": {"temp": 30}
}

下行响应格式:
{
    "cmd": "set_reply",
    "sn": "设备SN",
    "code": 0,
    "msg": "ok"
}
"""

from typing import Any, Dict, List

from xagent.xcore.storage.interface import Reading

from . import register
from .base import MQTTAdapterBase


@register("customer_a")
class CustomerAAdapter(MQTTAdapterBase):
    """客户A适配器 - 只需覆盖与默认格式不同的方法"""

    # ===== 元信息 =====
    __adapter_name__ = "customer_a"
    __adapter_description__ = "客户A私有云适配器 - 使用 SN/TS/Metrics 格式"
    __adapter_config_schema__ = {
        "sn_prefix": {
            "type": "string",
            "required": False,
            "default": "",
            "description": "设备SN前缀"
        },
    }

    def __init__(self, config=None):
        super().__init__(config)
        self._sn_prefix = self.config.get("sn_prefix", "")

    # ===== 上行：覆盖 =====

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        try:
            if not readings:
                return None
            results = []
            for r in readings:
                results.append({
                    "sn": f"{self._sn_prefix}{r.asset}",
                    "ts": int(r.timestamp * 1000),
                    "metrics": r.data,
                })
            return results if len(results) > 1 else results[0]
        except Exception as e:
            return None

    # ===== 下行：覆盖 =====

    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """客户A: {cmd, sn, params} → {asset, data}"""
        return {
            "asset": raw.get("sn", ""),
            "data": raw.get("params", {}),
        }

    def format_result(self, result) -> Dict[str, Any]:
        """客户A响应格式 - 利用 raw_command 获取原始命令类型"""
        raw = result.raw_command or {}
        original_cmd = raw.get("cmd", "set")
        reply_cmd = f"{original_cmd}_reply" if not original_cmd.endswith("_reply") else original_cmd

        if result.success:
            return {
                "cmd": reply_cmd,
                "sn": f"{self._sn_prefix}{result.asset}" if result.asset else "",
                "code": 0,
                "msg": "ok",
            }
        else:
            return {
                "cmd": reply_cmd,
                "sn": f"{self._sn_prefix}{result.asset}" if result.asset else "",
                "code": -1,
                "msg": result.error or "unknown error",
            }

    # ===== adapt_command / parse_response / to_json 使用基类默认实现 =====
```

**设计要点**：

- `__adapter_description__` 提供适配器描述，用于调试和文档
- `__adapter_config_schema__` 定义配置 schema，支持配置验证
- `format_result` 通过 `result.raw_command` 获取原始命令信息（如 `cmd` 字段），动态构造响应的命令类型（如 `set` → `set_reply`），无需硬编码
- `adapt_upload` 自行实现，不调用基类，因此自行包含 try/except

### 4.10 DownlinkHandler 微调

`downlink.py` 改动要点：

1. `DownlinkResult` 改从 `types.py` 导入
2. 下行流程只调 `parse_command`，移除 `adapt_command` 调用
3. `DownlinkResult` 保留原始命令
4. `_publish_result` 委托适配器 `format_result`

```python
"""MQTT Downlink Handler - Handles incoming commands and publishes results"""

import json
import logging
import time
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from xagent.xcore.core.event_bus import EventBus, Event, EventType
from .types import DownlinkResult

if TYPE_CHECKING:
    import aiomqtt

logger = logging.getLogger(__name__)


class DownlinkHandler:
    """
    MQTT Downlink Handler

    Responsibilities:
    - Parse incoming MQTT messages (委托适配器)
    - Publish commands to EventBus
    - Send response/result back to MQTT (委托适配器)

    Does NOT handle:
    - MQTT connection management
    - Topic subscription
    - Lifecycle management
    """

    def __init__(
        self,
        event_bus: EventBus,
        adapter: Any,
        command_timeout: float = 30.0
    ):
        self._event_bus = event_bus
        self._adapter = adapter
        self._command_timeout = command_timeout

    async def handle_message(
        self,
        message: "aiomqtt.Message",
        publish_callback: Optional[Callable[[str, str], None]] = None,
        result_topic: Optional[str] = None
    ) -> DownlinkResult:
        try:
            payload = message.payload.decode("utf-8")
            logger.info(f"Received command: {payload}")

            command = json.loads(payload)

            # 委托适配器解析命令格式
            parsed = self._adapter.parse_command(command)
            asset = parsed.get("asset")
            data = parsed.get("data")

            if not asset or not data:
                logger.warning("Invalid command: missing asset or data after parsing")
                result = DownlinkResult(
                    success=False,
                    error="Invalid command: missing asset or data",
                    raw_command=command,
                )
            else:
                # 直接使用 parse_command 的结果发布到 EventBus
                await self._event_bus.publish(Event(
                    event_type=EventType.COMMAND_RECEIVED,
                    data={"asset": asset, "data": data}
                ))

                result = DownlinkResult(
                    success=True,
                    asset=asset,
                    data=data,
                    raw_command=command,
                )
                logger.info(f"Command executed successfully for asset {asset}")

            if publish_callback and result_topic:
                await self._publish_result(publish_callback, result_topic, result)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON command: {e}")
            result = DownlinkResult(success=False, error=f"Invalid JSON: {str(e)}")

            if publish_callback and result_topic:
                await self._publish_result(publish_callback, result_topic, result)

            return result

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            result = DownlinkResult(success=False, error=str(e))

            if publish_callback and result_topic:
                await self._publish_result(publish_callback, result_topic, result)

            return result

    async def _publish_result(
        self,
        publish_callback: Callable[[str, str], None],
        result_topic: str,
        result: DownlinkResult
    ) -> None:
        try:
            # 委托适配器格式化结果
            response = self._adapter.format_result(result)
            payload = json.dumps(response, ensure_ascii=False)
            await publish_callback(result_topic, payload)

            logger.debug(f"Published result to {result_topic}")

        except Exception as e:
            logger.error(f"Failed to publish command result: {e}")
```

**设计要点**：

1. **移除 `adapt_command` 调用**：下行流程只需 `parse_command` 解析客户格式为内部格式，`adapt_command` 用于上行方向的命令构造，不应在下行流程中使用
2. **`DownlinkResult` 保留 `raw_command`**：使 `format_result` 可以访问原始命令中的额外信息
3. **EventBus 直接使用 `parse_command` 结果**：不再经过 `adapt_command` 二次转换

### 4.11 Plugin 微调

`plugin.py` 改两处：`_create_data_adapter` 和 `config_schema`。

```python
class MQTTClientPlugin(NorthPluginBase):

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # ... 原有字段不变 ...
                "adapter": {
                    "type": "string",
                    "default": "standard",
                    "title": "Adapter Name",
                    "description": "数据适配器名称，对应 adapters/ 目录下的客户适配器"
                },
                "adapter_config": {
                    "type": "object",
                    "default": {},
                    "title": "Adapter Config",
                    "description": "适配器专属配置，不同适配器支持不同参数"
                },
            },
        }

    def _create_data_adapter(self) -> Any:
        from .adapters import get_adapter

        adapter_name = self.config.get("adapter", "standard")
        adapter_config = self.config.get("adapter_config", {})

        try:
            return get_adapter(adapter_name, adapter_config)
        except ValueError as e:
            logger.error(f"{e}. Falling back to standard adapter")
            return get_adapter("standard", adapter_config)
```

## 五、数据流全景

### 上行数据流

```
Reading ──► adapt_upload() ──► to_json() ──► MQTT publish

客户A: Reading → {"sn": "SN-001", "ts": 1717814400000, "metrics": {"temp": 25.5}}
客户B: Reading → {"device_id": "D001", "time": "2024-06-08T12:00:00Z", "properties": {"temp": 25.5}}
默认:  Reading → {"asset": "device1", "timestamp": 1717814400.0, "service_name": "...", "data": {"temp": 25.5}}
```

### 下行数据流

```
MQTT message ──► parse_command() ──► {"asset": ..., "data": ...}
                       │
                  EventBus ──► 内部处理
                       │
             format_result(result) ──► MQTT publish (result topic)
                       │
             result.raw_command 保留原始命令，供 format_result 使用

客户A: {"cmd":"set","sn":"SN-001","params":{"temp":30}}
         → parse_command → {"asset":"SN-001","data":{"temp":30}}
         → EventBus
         → format_result(result) → {"cmd":"set_reply","sn":"SN-001","code":0,"msg":"ok"}

客户B: {"device_id":"D001","method":"write","properties":{"temp":30}}
         → parse_command → {"asset":"D001","data":{"temp":30}}
         → EventBus
         → format_result(result) → {"device_id":"D001","method":"write_reply","result":"success"}

默认:  {"asset":"device1","data":{"temp":30}}
         → parse_command → {"asset":"device1","data":{"temp":30}}
         → EventBus
         → format_result(result) → {"timestamp":1717814400.0,"status":"success","asset":"device1","data":{"temp":30}}
```

## 六、配置示例

```yaml
# ===== 客户A部署 =====
mqtt:
  broker: 192.168.1.100
  port: 1883
  topic: device/data/upload
  command_topic: device/cmd
  adapter: customer_a
  adapter_config:
    sn_prefix: "SN-"

# ===== 客户B部署 =====
mqtt:
  broker: 10.0.0.50
  port: 8883
  topic: /api/v1/telemetry
  command_topic: /api/v1/command
  adapter: customer_b
  adapter_config:
    site_id: "factory-01"

# ===== 无特殊格式需求（默认） =====
mqtt:
  broker: localhost
  port: 1883
  topic: xagent/data
  command_topic: xagent/command
  adapter: standard
  adapter_config:
    timestamp_format: "iso8601"
    property_mapping:
      temperature: temp
      humidity: humi
    device_name_mapping:
      device_01: SENSOR-001
```

## 七、变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `xcore/transform/adapter.py` | **不变** | DataAdapter Protocol 保持原样，不新增 MQTT 专有方法 |
| `mqtt_client/types.py` | 新增 | `DownlinkResult` 等共享类型定义，含 `raw_command` 字段 |
| `mqtt_client/adapters/__init__.py` | 新增 | 适配器注册表 + 显式注册 + 按需导入 |
| `mqtt_client/adapters/base.py` | 新增 | 适配器基类，提供默认实现 + MQTT 扩展接口 + 配置验证 |
| `mqtt_client/adapters/protocol.py` | 新增 | MQTT 适配器协议定义（类型安全） |
| `mqtt_client/adapters/exceptions.py` | 新增 | 适配器相关异常定义 |
| `mqtt_client/adapters/customer_a.py` | 新增 | 客户适配器示例 |
| `mqtt_client/adapter.py` | 修改 | `MQTTClientAdapter` 继承 `MQTTAdapterBase`，注册为 `"standard"` |
| `mqtt_client/downlink.py` | 修改 | 委托适配器 + 移除 `adapt_command` 调用 + `DownlinkResult` 保留原始命令 |
| `mqtt_client/plugin.py` | 修改 | `_create_data_adapter` 使用注册表，`config_schema` 新增 `adapter` 字段 |

## 八、新增客户适配器的步骤

1. 在 `adapters/` 下新建文件，如 `adapters/customer_c.py`
2. 继承 `MQTTAdapterBase`，用 `@register("customer_c")` 装饰
3. 定义元信息（`__adapter_description__`、`__adapter_config_schema__`）
4. 覆盖与默认格式不同的方法（通常只需覆盖 `adapt_upload`、`parse_command`、`format_result`）
5. 在 `adapters/__init__.py` 的 `_ADAPTER_IMPORTS` 列表中添加一行：`("customer_c", ".customer_c")`
6. 部署配置中设置 `adapter: customer_c`

**改动量**：新增 1 个文件 + 修改 1 行代码。

### 最小客户适配器模板

```python
"""客户C私有云适配器"""

from typing import Any, Dict, List
from xagent.xcore.storage.interface import Reading
from . import register
from .base import MQTTAdapterBase


@register("customer_c")
class CustomerCAdapter(MQTTAdapterBase):
    """客户C适配器"""

    # ===== 元信息 =====
    __adapter_name__ = "customer_c"
    __adapter_description__ = "客户C私有云适配器"
    __adapter_config_schema__ = {
        # 定义配置 schema
        # "site_id": {"type": "string", "required": True, "description": "站点ID"},
    }

    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        # TODO: 实现客户C的上行格式
        return super().adapt_upload(readings, context)

    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: 实现客户C的下行命令解析
        return super().parse_command(raw)

    def format_result(self, result) -> Dict[str, Any]:
        # TODO: 实现客户C的响应格式，可通过 result.raw_command 访问原始命令
        return super().format_result(result)
```

## 九、向后兼容性

| 场景 | 影响 |
|------|------|
| 现有部署未配置 `adapter` | 默认值为 `"standard"`，行为完全等价于当前实现 |
| `MQTTClientAdapter` 类名 | 保留不变，外部引用不受影响 |
| `DataAdapter` Protocol | **不变**，不新增方法，不影响 XNC 等其他北向插件 |
| `downlink.py` 对 `"standard"` 适配器 | `parse_command` 和 `format_result` 的默认实现与原硬编码逻辑等价 |
| `DownlinkResult` 迁移到 `types.py` | `downlink.py` 改为从 `types.py` 导入，外部引用需同步更新 |

## 十、职责划分

| 层 | 文件 | 职责 | 是否因客户变化 |
|---|---|---|---|
| **协议层** | `downlink.py` | MQTT 消息接收、EventBus 分发、错误处理 | 否 |
| **格式层** | `adapters/customer_x.py` | `adapt_upload` 上行格式<br>`parse_command` 下行命令解析<br>`format_result` 下行响应格式 | 是 |
| **插件层** | `plugin.py` | 生命周期、连接管理、选择适配器 | 否 |
| **注册层** | `adapters/__init__.py` | 适配器注册、按需导入、实例化 | 否（新增客户加一行） |
| **类型层** | `types.py` | `DownlinkResult` 等共享类型定义 | 否 |
| **异常层** | `adapters/exceptions.py` | 适配器相关异常定义 | 否 |
| **协议层** | `adapters/protocol.py` | MQTT 适配器协议定义（类型安全） | 否 |

## 十一、关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| `parse_command`/`format_result` 放在哪里？ | `MQTTAdapterBase` 扩展接口 | 不污染全局 `DataAdapter` Protocol，避免影响 XNC 等其他北向插件 |
| 下行流程是否调用 `adapt_command`？ | 否，只调 `parse_command` | `adapt_command` 语义是"内部→客户"构造，不应用于"客户→内部"解析场景 |
| `DownlinkResult` 放在哪里？ | 独立 `types.py` | 避免 `base.py` → `downlink.py` 循环依赖 |
| `parse_command` 是否做 mapping？ | 否 | `_map_device_name`/`_map_properties` 是正向映射（内部→客户），反向使用语义错误 |
| `_format_timestamp` 如何复用？ | 提取为基类可覆盖方法 | 子类覆盖一处即可同时生效于单条和批量模式 |
| `DownlinkResult` 是否保留原始命令？ | 是，增加 `raw_command` 字段 | `format_result` 可能需要原始命令中的额外信息（如命令类型、消息ID） |
| 适配器发现方式？ | 显式注册 + 按需导入 | 避免启动时自动发现的性能开销，支持静态分析，无安全风险 |
| 类型安全如何保证？ | `@runtime_checkable` Protocol | 支持静态类型检查，IDE 可追踪依赖 |
| 配置验证如何实现？ | `validate_config` + `__adapter_config_schema__` | 适配器自描述配置需求，提前发现配置错误 |
| 错误处理如何设计？ | 自定义异常类 | 提供友好的错误信息，便于问题定位 |
