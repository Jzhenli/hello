# MQTT 客户端适配器可插拔方案（简化版）

> **设计原则**：简单优于复杂，实用优于完美，渐进优于一步到位

## 一、背景与问题

### 1.1 当前问题

当前 `MQTTClientPlugin` 只有一个 `MQTTClientAdapter`，数据格式硬编码。面对多个私有云客户，每个客户有不同的上行/下行数据格式，存在以下问题：

1. **上行格式固定**：不同客户要求不同的 JSON 结构（字段名、嵌套方式、时间戳格式等）
2. **下行格式固定**：`DownlinkHandler` 硬编码了命令解析（`asset/data`）和响应格式（`status/error`）
3. **扩展困难**：新增客户格式需要修改已有代码，容易引入回归问题
4. **无法配置驱动**：无法通过配置切换数据格式

### 1.2 现状架构

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

---

## 二、设计目标

| 目标 | 说明 | 优先级 |
|------|------|--------|
| **加客户低侵入** | 新增客户格式只需在 `adapters/` 下加一个文件，并在注册列表加一行 | 高 |
| **配置驱动** | 部署时通过 `adapter: customer_a` 一行配置切换 | 高 |
| **格式隔离** | 每个客户的格式逻辑独立，互不干扰 | 高 |
| **协议复用** | MQTT 连接/重连/订阅/发布逻辑完全复用，只换数据格式 | 高 |
| **向后兼容** | 现有部署无需任何改动，默认行为不变 | 高 |
| **低门槛** | 客户适配器只需覆盖与默认格式不同的方法 | 高 |
| **接口隔离** | MQTT 专有方法不污染全局 `DataAdapter` Protocol | 中 |
| **简单优先** | 避免过度抽象，符合轻量级项目特点 | 高 |

---

## 三、目标架构

### 3.1 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                     MQTTClientPlugin                          │
│                                                               │
│  _create_data_adapter() ──► get_adapter("customer_a")        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  DownlinkHandler                         │ │
│  │  handle_message():                                       │ │
│  │    adapter.parse_command(raw) → 统一 {asset, data}       │ │
│  │    adapter.format_result(result) → 客户专属响应格式       │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    AdapterRegistry                            │
│  "standard"    → MQTTClientAdapter   (当前默认)              │
│  "customer_a"  → CustomerAAdapter      (客户A)               │
│  "customer_b"  → CustomerBAdapter      (客户B)               │
│  显式导入注册（简化版，去掉按需导入）                         │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
mqtt_client/
├── __init__.py              # 不变
├── adapter.py               # 重构：基类 + 标准适配器 + 类型定义（合并）
├── adapters/                # 新增：客户适配器包
│   ├── __init__.py          #   注册表（简化版）
│   └── customer_a.py        #   客户A适配器（示例）
├── constants.py             # 不变
├── downlink.py              # 微调：格式逻辑委托给适配器
└── plugin.py                # 微调：根据配置选择适配器
```

**文件数量**：从原方案的 7 个文件简化为 **3 个核心文件**（adapter.py + adapters/__init__.py + adapters/customer_a.py）

---

## 四、详细设计

### 4.1 核心文件：`adapter.py`

**职责**：基类 + 标准实现 + 共享类型定义（合并到一个文件）

```python
"""MQTT Adapter - 基类 + 标准实现 + 共享类型"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from xagent.xcore.storage.interface import Reading

logger = logging.getLogger(__name__)


# ===== 类型协议定义（可选，用于IDE类型检查） =====
@runtime_checkable
class MQTTAdapterProtocol(Protocol):
    """
    MQTT适配器协议 - 用于IDE类型提示和静态检查

    注意：这是可选的类型提示，不强制实现。
    鸭子类型保证运行时兼容性。
    """
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any: ...
    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]: ...
    def format_result(self, result: "DownlinkResult") -> Dict[str, Any]: ...
    def to_json(self, payload: Any) -> str: ...


# ===== 异常处理装饰器 =====
def _handle_adapter_errors(func):
    """
    适配器方法异常处理装饰器

    用法：
        @_handle_adapter_errors
        def adapt_upload(self, readings, context):
            # 无需try/except，装饰器会处理
            ...

    注意：adapt_upload基类已内置异常处理，子类覆盖时可选使用此装饰器
    """
    from functools import wraps
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__} error: {e}")
            return None
    return wrapper


# ===== 共享类型定义 =====
@dataclass
class DownlinkResult:
    """
    下行命令执行结果
    
    Attributes:
        success: 执行是否成功
        asset: 资产/设备ID
        data: 命令数据
        error: 错误信息
        raw_command: 原始命令（供format_result使用）
    """
    success: bool
    asset: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_command: Optional[Dict[str, Any]] = None


# ===== 适配器基类 =====
class MQTTAdapterBase:
    """
    MQTT 适配器基类
    
    提供所有方法的默认实现（等同于当前 Standard 格式），
    客户适配器只需覆盖与默认格式不同的方法。
    
    设计要点：
    - 使用鸭子类型，不强制Protocol（轻量级项目足够）
    - 异常处理统一在基类中，子类只需关注业务逻辑
    - 保留DataAdapter Protocol兼容性（adapt_command、parse_response）
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器
        
        Args:
            config: 适配器配置字典
        """
        self.config = config or {}
    
    # ===== 上行：数据上传 =====
    
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """
        适配上传数据 - 默认实现：单条/批量格式
        
        Args:
            readings: Reading 对象列表
            context: 上下文信息（包含 device_status_map 等）
        
        Returns:
            适配后的数据，单条返回字典，多条返回批量格式
            失败返回 None
        """
        try:
            if not readings:
                return None
            
            if len(readings) == 1:
                return self._adapt_single_reading(readings[0], context)
            else:
                return {
                    "count": len(readings),
                    "readings": [self._adapt_single_reading(r, context) for r in readings],
                    "timestamp": self._format_timestamp(readings[0].timestamp),
                }
        except Exception as e:
            logger.error(f"adapt_upload error: {e}")
            return None
    
    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        单条数据适配 - 子类可覆盖
        
        Args:
            reading: Reading 对象
            context: 上下文信息
        
        Returns:
            适配后的字典
        """
        context = context or {}
        device_status_map = context.get("device_status_map", {})
        
        payload = {
            "asset": reading.asset,
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": reading.data,
        }
        
        # 添加设备状态
        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status
        
        return payload
    
    def _format_timestamp(self, timestamp: float) -> Any:
        """
        时间戳格式化 - 子类可覆盖以支持不同格式
        
        Args:
            timestamp: Unix 时间戳
        
        Returns:
            格式化后的时间戳（默认返回原始值）
        """
        return timestamp
    
    # ===== 下行：命令解析与响应 =====
    
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
    
    def format_result(self, result: DownlinkResult) -> Dict[str, Any]:
        """
        格式化命令执行结果 - 将内部结果转换为客户要求的响应格式

        Args:
            result: DownlinkResult 对象

        Returns:
            客户要求的响应字典
        """
        import time
        # 使用当前时间戳，确保响应始终包含有效的时间信息
        response = {"timestamp": self._format_timestamp(time.time())}

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
    
    # ===== 工具方法 =====
    
    def to_json(self, payload: Any) -> str:
        """
        序列化为 JSON 字符串
        
        Args:
            payload: 待序列化的数据
        
        Returns:
            JSON 字符串
        """
        return json.dumps(payload, ensure_ascii=False)
    
    # ===== DataAdapter Protocol 兼容方法 =====
    
    def adapt_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        适配下行命令数据（保持 DataAdapter Protocol 兼容）
        
        注意：此方法用于上行方向的命令构造，不应用于下行解析场景
        
        Args:
            command_data: 命令数据
            context: 上下文信息
        
        Returns:
            适配后的命令数据
        """
        return {
            "asset": command_data.get("asset", ""),
            "data": command_data.get("data", {}),
            "timestamp": context.get("timestamp"),
        }
    
    def parse_response(self, response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析响应数据（保持 DataAdapter Protocol 兼容）
        
        Args:
            response: 原始响应（dict、bytes、str 或其他类型）
            context: 上下文信息
        
        Returns:
            解析后的字典
        """
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


# ===== 标准适配器（当前实现） =====
class MQTTClientAdapter(MQTTAdapterBase):
    """
    MQTT Client 标准适配器 - 默认格式
    
    保持原有行为不变，继承 MQTTAdapterBase，
    增加设备名映射、属性映射、时间戳格式化等增强功能。
    
    设计要点：
    - _map_device_name 和 _map_properties 仅用于上行方向（内部→客户）
    - 下行 parse_command 不做映射，避免语义错误
    - _format_timestamp 覆盖一处即可同时生效于单条和批量模式
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._timestamp_format = self.config.get("timestamp_format", "unix")
        self._include_metadata = self.config.get("include_metadata", True)
        self._include_quality = self.config.get("include_quality", True)
        self._property_mapping = self.config.get("property_mapping", {})
        self._device_name_mapping = self.config.get("device_name_mapping", {})
    
    def _adapt_single_reading(self, reading: Reading, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        覆盖基类方法，增加 mapping 和 metadata 功能
        """
        context = context or {}
        device_status_map = context.get("device_status_map", {})
        
        payload = {
            "asset": self._map_device_name(reading.asset),
            "timestamp": self._format_timestamp(reading.timestamp),
            "service_name": reading.service_name,
            "data": self._map_properties(reading.data),
        }
        
        # 添加设备状态
        if device_status_map and reading.asset in device_status_map:
            payload["device_status"] = device_status_map[reading.asset]
        elif reading.device_status:
            payload["device_status"] = reading.device_status
        
        # 添加 metadata
        if self._include_metadata:
            payload["tags"] = reading.tags
            if reading.standard_points:
                payload["standard_points"] = reading.standard_points
        
        # 添加 quality 信息
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
        """
        覆盖基类方法，增加 mapping 功能
        
        注意：仅用于上行方向的命令构造
        """
        return {
            "asset": self._map_device_name(command_data.get("asset", "")),
            "data": self._map_properties(command_data.get("data", {})),
            "timestamp": context.get("timestamp"),
        }
    
    def _format_timestamp(self, timestamp: float) -> Any:
        """
        覆盖基类方法，支持多种时间戳格式
        """
        if self._timestamp_format in ("iso", "iso8601"):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        elif self._timestamp_format == "milliseconds":
            return int(timestamp * 1000)
        return timestamp
    
    def _map_device_name(self, device_name: str) -> str:
        """
        映射设备名称（内部名称 → 客户名称，仅用于上行方向）
        
        Args:
            device_name: 原始设备名称
        
        Returns:
            映射后的设备名称
        """
        if self._device_name_mapping:
            return self._device_name_mapping.get(device_name, device_name)
        return device_name
    
    def _map_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        映射属性名称（内部名称 → 客户名称，仅用于上行方向）
        
        Args:
            data: 原始属性字典
        
        Returns:
            映射后的属性字典
        """
        if not self._property_mapping:
            return data
        
        mapped_data = {}
        for key, value in data.items():
            mapped_key = self._property_mapping.get(key, key)
            mapped_data[mapped_key] = value
        
        return mapped_data
```

**设计要点**：

1. **合并文件**：基类、标准实现、类型定义合并到一个文件，减少文件跳转
2. **鸭子类型 + 类型提示**：
   - 运行时使用鸭子类型，不强制实现Protocol
   - 提供`MQTTAdapterProtocol`用于IDE类型提示和静态检查（mypy、pyright）
   - 所有方法都有完整的类型注解，提升IDE自动补全体验
3. **异常处理统一**：
   - 基类`adapt_upload`已内置try/except异常处理
   - 提供`_handle_adapter_errors`装饰器供子类使用
   - 子类覆盖`adapt_upload`时，可选择：
     - 方式1：自行添加try/except（完全控制）
     - 方式2：使用装饰器（简化代码）
     - 方式3：不处理异常（依赖调用方捕获）
4. **接口隔离**：`parse_command`、`format_result` 作为 MQTT 专有方法，不污染全局 DataAdapter Protocol
5. **mapping 方向明确**：`_map_device_name` 和 `_map_properties` 仅用于上行方向，避免语义错误

---

### 4.2 注册表：`adapters/__init__.py`

**职责**：适配器注册与实例化（简化版，去掉按需导入、自定义异常、元信息）

```python
"""MQTT Adapter Registry - 简化版"""

import logging
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)

# 注册表
_REGISTRY: Dict[str, Type] = {}


def register(name: str):
    """
    装饰器：注册适配器类
    
    用法:
        @register("customer_a")
        class CustomerAAdapter(MQTTAdapterBase):
            ...
    
    Args:
        name: 适配器名称（用于配置中的 adapter 字段）
    
    Returns:
        装饰器函数
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
    
    Args:
        name: 适配器名称
        config: 适配器配置
    
    Returns:
        适配器实例
    
    Raises:
        ValueError: 适配器未找到
    """
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(f"Adapter '{name}' not found. Available: {available}")
    
    try:
        return _REGISTRY[name](config or {})
    except Exception as e:
        logger.error(f"Failed to create adapter '{name}': {e}")
        raise


def list_adapters() -> list:
    """列出所有已注册的适配器"""
    return sorted(_REGISTRY.keys())


# ===== 显式导入注册 =====
# 新增客户只需在这里添加一行导入

from ..adapter import MQTTClientAdapter
register("standard")(MQTTClientAdapter)

# 客户适配器导入（取消注释即可启用）
# from .customer_a import CustomerAAdapter  # 客户A
# from .customer_b import CustomerBAdapter  # 客户B
# from .customer_c import CustomerCAdapter  # 客户C
```

**设计要点**：

1. **去掉按需导入**：轻量级项目导入几个适配器模块的开销可忽略（毫秒级）
2. **去掉自定义异常**：用 `ValueError` + 日志足够，自定义异常对用户价值有限
3. **去掉元信息**：`__adapter_description__`、`__adapter_config_schema__` 等元信息在轻量级项目中用不上
4. **显式注册**：新增客户只需取消注释一行导入，清晰明了

---

### 4.3 客户适配器示例：`adapters/customer_a.py`

**职责**：客户A私有云的数据格式适配

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

import logging
from typing import Any, Dict, List

from xagent.xcore.storage.interface import Reading

from ..adapter import MQTTAdapterBase, DownlinkResult, register

logger = logging.getLogger(__name__)


@register("customer_a")
class CustomerAAdapter(MQTTAdapterBase):
    """
    客户A适配器 - 只需覆盖与默认格式不同的方法
    
    设计要点：
    - 继承 MQTTAdapterBase，自动获得默认实现
    - 只覆盖需要定制的方法：adapt_upload、parse_command、format_result
    - 其他方法（adapt_command、parse_response、to_json）使用基类默认实现
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self._sn_prefix = self.config.get("sn_prefix", "")
    
    # ===== 上行：覆盖 =====
    
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """
        客户A上行格式：{sn, ts, metrics}
        
        注意：自行实现完整逻辑，包含异常处理
        """
        try:
            if not readings:
                return None
            
            results = []
            for r in readings:
                results.append({
                    "sn": f"{self._sn_prefix}{r.asset}",
                    "ts": int(r.timestamp * 1000),  # 毫秒时间戳
                    "metrics": r.data,
                })
            
            # 单条返回对象，多条返回数组
            return results if len(results) > 1 else results[0]
        
        except Exception as e:
            logger.error(f"adapt_upload error: {e}")
            return None
    
    # ===== 下行：覆盖 =====
    
    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        客户A下行命令解析：{cmd, sn, params} → {asset, data}
        
        Args:
            raw: 客户A的命令格式 {"cmd": "set", "sn": "SN-001", "params": {"temp": 30}}
        
        Returns:
            统一内部格式 {"asset": "SN-001", "data": {"temp": 30}}
        """
        return {
            "asset": raw.get("sn", ""),
            "data": raw.get("params", {}),
        }
    
    def format_result(self, result: DownlinkResult) -> Dict[str, Any]:
        """
        客户A响应格式：{cmd_reply, sn, code, msg}
        
        利用 result.raw_command 获取原始命令信息（如 cmd 字段），
        动态构造响应的命令类型（如 set → set_reply）
        
        Args:
            result: DownlinkResult 对象
        
        Returns:
            客户A要求的响应格式
        """
        raw = result.raw_command or {}
        original_cmd = raw.get("cmd", "set")
        
        # 构造响应命令类型：set → set_reply
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

1. **极简**：只覆盖 3 个方法（`adapt_upload`、`parse_command`、`format_result`）
2. **无需定义元信息**：去掉 `__adapter_description__`、`__adapter_config_schema__`
3. **直接继承基类**：鸭子类型保证兼容，无需显式实现 Protocol
4. **利用 `raw_command`**：`format_result` 可访问原始命令信息，实现动态响应构造

---

### 4.4 下行处理器微调：`downlink.py`

**变更要点**：

1. `DownlinkResult` 改从 `adapter.py` 导入
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
from .adapter import DownlinkResult  # 从 adapter.py 导入

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
        """Handle incoming MQTT message"""
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
                    raw_command=command,  # 保留原始命令
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
                    raw_command=command,  # 保留原始命令
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
        """Publish command execution result"""
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

1. **移除 `adapt_command` 调用**：下行流程只需 `parse_command` 解析客户格式为内部格式
2. **`DownlinkResult` 保留 `raw_command`**：使 `format_result` 可以访问原始命令中的额外信息
3. **EventBus 直接使用 `parse_command` 结果**：不再经过 `adapt_command` 二次转换

---

### 4.5 插件微调：`plugin.py`

**变更要点**：`_create_data_adapter` 使用注册表，`config_schema` 新增 `adapter` 字段

```python
class MQTTClientPlugin(NorthPluginBase):
    """MQTT North Plugin - Bidirectional MQTT client"""
    
    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # ... 原有字段不变 ...
                "broker": {"type": "string", "default": DEFAULT_BROKER, "title": "Broker Address"},
                "port": {"type": "integer", "default": DEFAULT_PORT, "title": "Broker Port"},
                "topic": {"type": "string", "default": DEFAULT_TOPIC, "title": "Data Topic"},
                "command_topic": {"type": "string", "default": DEFAULT_COMMAND_TOPIC, "title": "Command Topic"},
                
                # 新增字段
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
        """创建数据适配器 - 使用注册表"""
        from .adapters import get_adapter
        
        adapter_name = self.config.get("adapter", "standard")
        adapter_config = self.config.get("adapter_config", {})
        
        try:
            return get_adapter(adapter_name, adapter_config)
        except ValueError as e:
            logger.warning(f"{e}. Falling back to standard adapter")
            return get_adapter("standard", adapter_config)
```

---

## 五、数据流全景

### 5.1 上行数据流

```
Reading ──► adapt_upload() ──► to_json() ──► MQTT publish

客户A: Reading → {"sn": "SN-001", "ts": 1717814400000, "metrics": {"temp": 25.5}}
客户B: Reading → {"device_id": "D001", "time": "2024-06-08T12:00:00Z", "properties": {"temp": 25.5}}
默认:  Reading → {"asset": "device1", "timestamp": 1717814400.0, "service_name": "...", "data": {"temp": 25.5}}
```

### 5.2 下行数据流

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

---

## 六、配置示例

### 6.1 客户A部署

```yaml
mqtt:
  broker: 192.168.1.100
  port: 1883
  topic: device/data/upload
  command_topic: device/cmd
  adapter: customer_a
  adapter_config:
    sn_prefix: "SN-"
```

### 6.2 客户B部署

```yaml
mqtt:
  broker: 10.0.0.50
  port: 8883
  topic: /api/v1/telemetry
  command_topic: /api/v1/command
  adapter: customer_b
  adapter_config:
    site_id: "factory-01"
```

### 6.3 默认部署（无特殊格式需求）

```yaml
mqtt:
  broker: localhost
  port: 1883
  topic: xagent/data
  command_topic: xagent/command
  adapter: standard  # 可省略，默认为 standard
  adapter_config:
    timestamp_format: "iso8601"
    property_mapping:
      temperature: temp
      humidity: humi
    device_name_mapping:
      device_01: SENSOR-001
```

---

## 七、新增客户适配器的步骤

### 7.1 步骤清单

1. 在 `adapters/` 下新建文件，如 `adapters/customer_c.py`
2. 继承 `MQTTAdapterBase`，用 `@register("customer_c")` 装饰
3. 覆盖与默认格式不同的方法（通常只需覆盖 `adapt_upload`、`parse_command`、`format_result`）
4. 在 `adapters/__init__.py` 中取消注释导入：`from .customer_c import CustomerCAdapter`
5. 部署配置中设置 `adapter: customer_c`

**改动量**：新增 1 个文件 + 取消注释 1 行代码。

### 7.2 最小客户适配器模板

```python
"""客户C私有云适配器"""

import logging
from typing import Any, Dict, List

from xagent.xcore.storage.interface import Reading
from ..adapter import MQTTAdapterBase, DownlinkResult, register

logger = logging.getLogger(__name__)


@register("customer_c")
class CustomerCAdapter(MQTTAdapterBase):
    """客户C适配器"""
    
    def __init__(self, config=None):
        super().__init__(config)
        # 从 config 中获取客户专属配置
        # self._site_id = self.config.get("site_id", "")
    
    def adapt_upload(self, readings: List[Reading], context: Dict[str, Any]) -> Any:
        """TODO: 实现客户C的上行格式"""
        # 示例：直接使用基类默认实现
        return super().adapt_upload(readings, context)
    
    def parse_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: 实现客户C的下行命令解析"""
        # 示例：直接使用基类默认实现
        return super().parse_command(raw)
    
    def format_result(self, result: DownlinkResult) -> Dict[str, Any]:
        """TODO: 实现客户C的响应格式"""
        # 示例：直接使用基类默认实现
        return super().format_result(result)
```

---

## 八、配置错误排查指南

虽然轻量级项目不需要复杂的schema验证，但以下常见配置错误需要注意：

### 8.1 常见错误及解决方案

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `Adapter 'xxx' not found` | 适配器名称错误或未注册 | 1. 检查`adapter`配置是否正确<br>2. 确认适配器已在`adapters/__init__.py`中导入 |
| `Failed to create adapter 'xxx'` | 适配器初始化失败 | 1. 检查`adapter_config`配置是否正确<br>2. 查看日志中的详细错误信息 |
| `Invalid command: missing asset or data` | 下行命令格式不匹配 | 1. 检查客户下发的命令格式<br>2. 确认`parse_command`方法正确解析 |
| `adapt_upload error` | 上行数据适配失败 | 1. 检查Reading数据格式<br>2. 查看日志中的详细错误信息 |

### 8.2 配置检查清单

```bash
# 1. 检查适配器是否已注册
python -c "from xagent.plugins.north.mqtt_client.adapters import list_adapters; print(list_adapters())"

# 2. 测试适配器实例化
python -c "from xagent.plugins.north.mqtt_client.adapters import get_adapter; adapter = get_adapter('customer_a', {'sn_prefix': 'SN-'}); print(adapter)"

# 3. 测试数据适配
python -c "
from xagent.plugins.north.mqtt_client.adapters import get_adapter
from xagent.xcore.storage.interface import Reading
adapter = get_adapter('customer_a', {'sn_prefix': 'SN-'})
reading = Reading(asset='device1', timestamp=1234567890.0, service_name='test', data={'temp': 25.5})
result = adapter.adapt_upload([reading], {})
print(result)
"
```

### 8.3 日志调试技巧

```yaml
# 在配置文件中启用DEBUG日志
logging:
  level: DEBUG
  loggers:
    xagent.plugins.north.mqtt_client: DEBUG
    xagent.plugins.north.mqtt_client.adapters: DEBUG
```

启用DEBUG日志后，可以看到：
- 适配器注册信息：`Registered adapter: customer_a -> CustomerAAdapter`
- 命令解析过程：`Received command: {...}`
- 响应格式化过程：`Published result to {...}`

---

## 九、向后兼容性

| 场景 | 影响 |
|------|------|
| 现有部署未配置 `adapter` | 默认值为 `"standard"`，行为完全等价于当前实现 |
| `MQTTClientAdapter` 类名 | 保留不变，外部引用不受影响 |
| `DataAdapter` Protocol | **不变**，不新增方法，不影响 XNC 等其他北向插件 |
| `downlink.py` 对 `"standard"` 适配器 | `parse_command` 和 `format_result` 的默认实现与原硬编码逻辑等价 |
| `DownlinkResult` 迁移到 `adapter.py` | `downlink.py` 改为从 `adapter.py` 导入，外部引用需同步更新 |

---

## 九、职责划分

| 层 | 文件 | 职责 | 是否因客户变化 |
|---|---|---|---|
| **格式层** | `adapter.py` | 基类 + 标准实现 + 类型定义 | 否 |
| **格式层** | `adapters/customer_x.py` | `adapt_upload` 上行格式<br>`parse_command` 下行命令解析<br>`format_result` 下行响应格式 | 是 |
| **协议层** | `downlink.py` | MQTT 消息接收、EventBus 分发、错误处理 | 否 |
| **插件层** | `plugin.py` | 生命周期、连接管理、选择适配器 | 否 |
| **注册层** | `adapters/__init__.py` | 适配器注册、实例化 | 否（新增客户取消注释一行） |

---

## 十、方案对比

### 10.1 与原方案对比

| 维度 | 原方案（7文件） | 简化方案（3文件） |
|------|----------------|------------------|
| **文件数量** | 7个 | 3个 |
| **代码行数** | ~600行 | ~300行 |
| **抽象层次** | Protocol + Base + Registry + Exceptions + Types | Base + Registry + 类型提示 |
| **类型安全** | Protocol + @runtime_checkable | 鸭子类型 + Protocol类型提示 + 完整类型注解 |
| **配置验证** | schema + validate_config | 无（YAGNI）+ 排查指南 |
| **错误处理** | 自定义异常类 | ValueError + 日志 + 装饰器 |
| **按需导入** | 有（lambda闭包） | 无（直接导入） |
| **扩展成本** | 1文件 + 1行注册 | 1文件 + 取消注释1行 |
| **学习曲线** | 较陡（需理解Protocol、注册表、按需导入） | 平缓（继承+覆盖即可） |
| **IDE体验** | 完整类型提示 | 完整类型提示（通过Protocol和类型注解） |

### 10.2 为什么简化？

**符合轻量级项目特点**：

1. **网关项目**：核心是数据转发，不是框架开发
2. **客户数量有限**：通常 3-5 个客户，不需要复杂的注册机制
3. **部署环境简单**：不需要动态发现、插件热加载

**去掉过度抽象**：

1. ❌ **强制Protocol**：运行时使用鸭子类型，但保留Protocol用于IDE类型提示
2. ❌ **Exceptions**：自定义异常对用户价值有限，ValueError + 日志足够
3. ❌ **Schema验证**：轻量级项目配置简单，启动时自然失败即可，提供排查指南
4. ❌ **按需导入**：导入几个适配器模块的开销可忽略（毫秒级）
5. ❌ **元信息**：`__adapter_description__`、`__adapter_config_schema__` 在轻量级项目中用不上
6. ✅ **类型注解**：保留完整类型注解，提升IDE体验和代码可维护性

**保留核心价值**：

- ✅ 可插拔：客户适配器独立文件
- ✅ 配置驱动：通过 `adapter` 字段切换
- ✅ 向后兼容：默认行为不变
- ✅ 扩展简单：新增客户 1 文件 + 取消注释 1 行

---

## 十一、变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `mqtt_client/adapter.py` | 重构 | 合并基类 + 标准实现 + 类型定义 |
| `mqtt_client/adapters/__init__.py` | 新增 | 注册表（简化版） |
| `mqtt_client/adapters/customer_a.py` | 新增 | 客户适配器示例 |
| `mqtt_client/downlink.py` | 修改 | 委托适配器 + 移除 `adapt_command` 调用 + `DownlinkResult` 保留原始命令 |
| `mqtt_client/plugin.py` | 修改 | `_create_data_adapter` 使用注册表，`config_schema` 新增 `adapter` 字段 |

---

## 十二、实施建议

### 阶段1：核心重构（1天）

1. 创建 `adapter.py`（基类 + 标准实现 + 类型）
2. 创建 `adapters/__init__.py`（简化注册表）
3. 修改 `downlink.py` 和 `plugin.py`
4. 运行测试，确保向后兼容

### 阶段2：客户适配器（按需）

1. 为每个客户创建 `adapters/customer_x.py`
2. 在 `adapters/__init__.py` 中取消注释导入
3. 编写客户专属测试

### 阶段3：文档与测试

1. 更新配置文档
2. 添加客户适配器模板
3. 编写集成测试

---

## 十三、关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 是否使用 Protocol？ | 可选，提供类型提示 | 运行时鸭子类型，IDE中提供Protocol用于类型检查和自动补全 |
| 是否自定义异常？ | 否，使用 ValueError | 自定义异常对用户价值有限，增加复杂度 |
| 是否配置验证？ | 否 | 轻量级项目配置简单，启动时自然失败即可，提供排查指南 |
| 是否按需导入？ | 否 | 导入几个适配器模块的开销可忽略（毫秒级） |
| `parse_command`/`format_result` 放在哪里？ | `MQTTAdapterBase` 扩展接口 | 不污染全局 `DataAdapter` Protocol |
| 下行流程是否调用 `adapt_command`？ | 否，只调 `parse_command` | `adapt_command` 语义是"内部→客户"构造 |
| `DownlinkResult` 放在哪里？ | `adapter.py` | 合并文件，减少文件跳转 |
| `parse_command` 是否做 mapping？ | 否 | mapping 是正向映射（内部→客户），反向使用语义错误 |
| `_format_timestamp` 如何复用？ | 提取为基类可覆盖方法 | 子类覆盖一处即可同时生效于单条和批量模式 |
| `DownlinkResult` 是否保留原始命令？ | 是，增加 `raw_command` 字段 | `format_result` 可能需要原始命令中的额外信息 |
| `format_result` 的 timestamp 如何处理？ | 使用当前时间戳 | 确保响应始终包含有效的时间信息，避免依赖raw_command |

---

## 十四、总结

**方案特点**：

1. **简单**：3 个文件，~300 行代码，学习曲线平缓
2. **实用**：保留核心价值，去掉过度抽象
3. **可扩展**：新增客户成本低（1 文件 + 取消注释 1 行）
4. **向后兼容**：默认行为不变，现有部署无需改动

**适用场景**：

- ✅ 轻量级网关项目
- ✅ 客户数量有限（3-10 个）
- ✅ 配置简单，不需要复杂的验证
- ✅ 不需要动态发现、插件热加载

**不适用场景**：

- ❌ 大型框架项目（建议使用原方案的完整抽象）
- ❌ 客户数量众多（>10 个，建议使用按需导入）
- ❌ 需要严格的配置验证（建议添加 schema 验证）

**演进路径**：

- 当前：简化方案（3 文件）
- 客户数量 > 10：添加按需导入
- 需要严格验证：添加 schema 验证
- 需要框架级抽象：演进为原方案（7 文件）
