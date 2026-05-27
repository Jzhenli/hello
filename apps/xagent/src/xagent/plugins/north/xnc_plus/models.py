import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Direction(Enum):
    UPLOAD = "upload"
    COMMAND = "command"


@dataclass
class ValueTransform:
    scale: float = 1.0
    offset: float = 0.0
    enum_map: Optional[Dict[Any, Any]] = None
    reverse_enum_map: Optional[Dict[Any, Any]] = None

    def forward(self, value: Any) -> Any:
        if self.enum_map:
            return self.enum_map.get(value, value)
        if isinstance(value, (int, float)):
            return value * self.scale + self.offset
        return value

    def reverse(self, value: Any) -> Any:
        if self.reverse_enum_map:
            return self.reverse_enum_map.get(value, value)
        if isinstance(value, (int, float)):
            return (value - self.offset) / self.scale
        return value

    def to_json(self) -> str:
        data: Dict[str, Any] = {"scale": self.scale, "offset": self.offset}
        if self.enum_map:
            data["enum_map"] = {str(k): v for k, v in self.enum_map.items()}
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: Optional[str]) -> Optional["ValueTransform"]:
        if not data:
            return None
        try:
            obj = json.loads(data)
            enum_map = obj.get("enum_map")
            reverse_enum = None
            if enum_map:
                reverse_enum = {v: k for k, v in enum_map.items()}
            return cls(
                scale=obj.get("scale", 1.0),
                offset=obj.get("offset", 0.0),
                enum_map=enum_map,
                reverse_enum_map=reverse_enum,
            )
        except (json.JSONDecodeError, TypeError):
            return None


@dataclass
class PointMapping:
    standard_name: str
    protocol_oid: int
    device_id: str
    protocol_vdid: int
    pid_value: int = 85
    pid_error: int = 103
    value_transform: Optional[ValueTransform] = None
    protocol_config: Optional[Dict[str, Any]] = None

    @property
    def namespaced_name(self) -> str:
        return f"{self.device_id}.{self.standard_name}"


@dataclass
class CommandMessage:
    device_id: str
    command_type: str
    points: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    reply_addr: tuple = ()
    sequence: int = 0
