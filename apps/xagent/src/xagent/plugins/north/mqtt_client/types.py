"""MQTT适配器核心类型定义

所有类型都是纯数据容器，不包含业务逻辑。
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PublishPacket:
    """发布包 - 自包含的发布单元

    topic 和 payload 绑定在一起，调用方不需要知道
    "这个数据该发到哪个topic"，消除错配可能。
    """

    topic: str
    payload: Dict[str, Any]


@dataclass
class CommandData:
    """解析后的命令

    requires_reply 由适配器根据协议决定：
    - property_down: 需要回复
    - connect_reply / disconnect_reply: 不需要回复（是云平台对我们请求的回复）
    """

    asset: str
    data: Dict[str, Any]
    command_type: str = "write_property"
    requires_reply: bool = True


@dataclass
class ResponsePacket:
    """响应包 - 自包含的响应单元

    topic 和 payload 绑定在一起，调用方不需要知道
    "响应该发到哪个topic"。
    """

    topic: str
    payload: Dict[str, Any]


@dataclass
class CommandResult:
    """命令执行结果（框架产生，适配器消费）"""

    success: bool
    asset: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class CommandContext:
    """命令上下文（适配器格式化响应时需要的额外信息）

    替代 **kwargs，提供类型安全的上下文传递。
    """

    raw_command: Dict[str, Any]
    topic: str
    topic_type: str
