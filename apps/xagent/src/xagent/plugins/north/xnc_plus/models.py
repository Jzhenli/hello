from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CommandMessage:
    device_id: str
    command_type: str
    points: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    reply_addr: tuple = ()
    sequence: int = 0
