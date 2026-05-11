"""Core Compatibility Adapter

统一处理规则引擎对 core 模块的可选依赖。
将散布在各模块中的 try/except ImportError 模式集中管理，
提供一致的接口和类型回退。
"""

import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from xagent.xcore.core.event_bus import EventBus, EventType, Event
    from xagent.xcore.core.interfaces import ILifecycle
    HAS_CORE = True
except ImportError:
    HAS_CORE = False

    class EventType(str, Enum):
        SYSTEM_ERROR = "SYSTEM_ERROR"
        PLUGIN_STATUS_CHANGED = "PLUGIN_STATUS_CHANGED"
        DATA_ANOMALY = "DATA_ANOMALY"
        CONFIG_RELOADED = "CONFIG_RELOADED"
        DATA_RECEIVED = "DATA_RECEIVED"
        COMMAND_RECEIVED = "COMMAND_RECEIVED"
        WRITE_COMPLETED = "WRITE_COMPLETED"
        RULE_TRIGGERED = "RULE_TRIGGERED"
        RULE_EVALUATED = "RULE_EVALUATED"
        NOTIFICATION_DELIVERED = "NOTIFICATION_DELIVERED"

    @dataclass
    class Event:
        event_type: EventType
        data: Any = None
        timestamp: float = field(default_factory=time.time)
        event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    class EventBus:
        async def publish(self, event: Event) -> None:
            pass

        def subscribe(self, event_type: EventType, callback: Callable) -> None:
            pass

        def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
            pass

    class ILifecycle(ABC):
        @abstractmethod
        async def start(self) -> None:
            pass

        @abstractmethod
        async def stop(self) -> None:
            pass

        @property
        def is_running(self) -> bool:
            return False


ILifecycleBase = ILifecycle


def is_reading(obj: Any) -> bool:
    """检查对象是否为 Reading 实例"""
    try:
        from xagent.xcore.domain.models.reading import Reading
        return isinstance(obj, Reading)
    except ImportError:
        return False


def reading_to_reading_set(reading: Any) -> Optional[Any]:
    """将 Reading 转换为 ReadingSet，失败返回 None"""
    try:
        from xagent.xcore.domain.models.reading import Reading
        if isinstance(reading, Reading):
            from .base import ReadingSet
            
            quality = None
            if reading.standard_points:
                quality = {}
                for sp in reading.standard_points:
                    point_name = sp.get("point_name", "")
                    if point_name:
                        quality[point_name] = sp.get("quality", "good")
            
            return ReadingSet(
                asset=reading.asset,
                timestamp=reading.timestamp,
                points=dict(reading.data),
                quality=quality,
                metadata={
                    "service_name": reading.service_name,
                    "tags": reading.tags,
                    "device_status": reading.device_status,
                }
            )
    except ImportError:
        pass
    return None


def reading_set_to_reading(reading_set: Any) -> Optional[Any]:
    """将 ReadingSet 转换为 Reading，失败返回 None"""
    try:
        from xagent.xcore.domain.models.reading import Reading
        from .base import ReadingSet
        if isinstance(reading_set, ReadingSet):
            metadata = reading_set.metadata or {}
            standard_points = []
            if reading_set.quality:
                for point_name, quality in reading_set.quality.items():
                    standard_points.append({
                        "point_name": point_name,
                        "quality": quality,
                        "value": reading_set.points.get(point_name),
                    })
            
            return Reading(
                asset=reading_set.asset,
                timestamp=reading_set.timestamp,
                service_name=metadata.get("service_name", ""),
                data=dict(reading_set.points),
                tags=metadata.get("tags", []),
                standard_points=standard_points,
                device_status=metadata.get("device_status"),
            )
    except ImportError:
        pass
    return None
