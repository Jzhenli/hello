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
# 导入适配器模块以触发装饰器注册
# 新增客户只需在这里添加一行导入

from .standard import StandardAdapter  # noqa: F401 - 标准适配器
from .customer_a import CustomerAAdapter  # noqa: F401 - 客户A
# from .customer_b import CustomerBAdapter  # noqa: F401 - 客户B
# from .customer_c import CustomerCAdapter  # noqa: F401 - 客户C
