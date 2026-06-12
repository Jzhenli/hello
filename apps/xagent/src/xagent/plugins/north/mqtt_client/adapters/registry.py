"""MQTT Adapter Registry - 适配器注册机制"""

import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# 注册表（模块私有）
_REGISTRY: Dict[str, Type] = {}
# 客户编号 → 适配器名称 映射（模块私有）
_CODE_REGISTRY: Dict[str, str] = {}


def register(name: str, customer_code: Optional[str] = None):
    """
    装饰器：注册适配器类

    用法:
        @register("customer_a", customer_code="C001")
        class CustomerAAdapter(MQTTAdapterBase):
            ...

    Args:
        name: 适配器名称（内部标识）
        customer_code: 客户编号（配置中可使用此编号代替适配器名称）

    Returns:
        装饰器函数
    """
    def decorator(cls):
        if name in _REGISTRY:
            logger.warning(f"Overwriting adapter: {name}")
        _REGISTRY[name] = cls
        logger.debug(f"Registered adapter: {name} -> {cls.__name__}")

        if customer_code:
            if customer_code in _CODE_REGISTRY:
                logger.warning(f"Overwriting customer code: {customer_code}")
            _CODE_REGISTRY[customer_code] = name
            logger.debug(f"Registered customer code: {customer_code} -> {name}")

        return cls
    return decorator


def get_adapter(name_or_code: str, config: Optional[Dict[str, Any]] = None) -> Any:
    """
    获取适配器实例

    支持通过适配器名称或客户编号查找：
    - 先按客户编号查找
    - 未找到则按适配器名称查找

    Args:
        name_or_code: 适配器名称或客户编号
        config: 适配器配置

    Returns:
        适配器实例

    Raises:
        ValueError: 适配器未找到
    """
    # 先按客户编号查找，再按适配器名称查找
    if name_or_code in _CODE_REGISTRY:
        adapter_name = _CODE_REGISTRY[name_or_code]
    elif name_or_code in _REGISTRY:
        adapter_name = name_or_code
    else:
        available_adapters = list(_REGISTRY.keys())
        available_codes = list(_CODE_REGISTRY.keys())
        raise ValueError(
            f"Adapter '{name_or_code}' not found. "
            f"Available adapters: {available_adapters}, "
            f"customer codes: {available_codes}"
        )

    try:
        return _REGISTRY[adapter_name](config or {})
    except Exception as e:
        logger.error(f"Failed to create adapter '{adapter_name}': {e}")
        raise


def list_adapters() -> list:
    """列出所有已注册的适配器名称"""
    return sorted(_REGISTRY.keys())


def list_customer_codes() -> Dict[str, str]:
    """列出所有客户编号映射 {code: adapter_name}"""
    return dict(_CODE_REGISTRY)


def get_adapter_class(name_or_code: str) -> Optional[Type]:
    """
    获取适配器类（不实例化）

    支持通过适配器名称或客户编号查找。

    Args:
        name_or_code: 适配器名称或客户编号

    Returns:
        适配器类，未找到返回 None
    """
    # 先按客户编号查找，再按适配器名称查找
    if name_or_code in _CODE_REGISTRY:
        adapter_name = _CODE_REGISTRY[name_or_code]
    elif name_or_code in _REGISTRY:
        adapter_name = name_or_code
    else:
        return None

    return _REGISTRY.get(adapter_name)


def get_adapter_info() -> List[Dict[str, Any]]:
    """
    获取所有适配器信息

    Returns:
        适配器信息列表，每项包含:
        - name: 适配器名称
        - customer_code: 客户编号（可能为None）
        - has_defaults: 是否有默认配置
    """
    result = []

    for name, cls in _REGISTRY.items():
        # 查找对应的客户编号
        customer_code = None
        for code, adapter_name in _CODE_REGISTRY.items():
            if adapter_name == name:
                customer_code = code
                break

        # 检查是否有默认配置
        has_defaults = hasattr(cls, "DEFAULT_CONFIG") and cls.DEFAULT_CONFIG is not None

        result.append({
            "name": name,
            "customer_code": customer_code,
            "has_defaults": has_defaults
        })

    return result
