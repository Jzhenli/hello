"""MQTT Adapter Registry - 适配器注册与加载

公共 API:
    - register: 装饰器，用于注册适配器
    - get_adapter: 获取适配器实例
    - list_adapters: 列出所有已注册的适配器
    - list_customer_codes: 列出所有客户编号映射
"""

from .registry import (
    register,
    get_adapter,
    list_adapters,
    list_customer_codes,
)

# 导入适配器模块以触发装饰器注册
# 新增客户只需在这里添加一行导入
from .standard import StandardAdapter  # noqa: F401
from .customer_a import CustomerAAdapter  # noqa: F401
# from .customer_b import CustomerBAdapter  # noqa: F401
# from .customer_c import CustomerCAdapter  # noqa: F401

__all__ = [
    "register",
    "get_adapter",
    "list_adapters",
    "list_customer_codes",
]
