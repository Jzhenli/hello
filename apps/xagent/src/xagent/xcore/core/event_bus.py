"""Event Bus - Async message bus for component communication"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


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
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._dispatch_task: Optional[asyncio.Task] = None
        self._event_history: List[Event] = []
        self._max_history: int = 1000

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("Event Bus started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        logger.info("Event Bus stopped")

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type}: {callback.__name__}")

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type}: {callback.__name__}")

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)
        self._add_to_history(event)

    def _add_to_history(self, event: Event) -> None:
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event dispatch loop: {e}")

    async def _dispatch_event(self, event: Event) -> None:
        subscribers = self._subscribers.get(event.event_type, [])
        if not subscribers:
            logger.debug(f"No subscribers for event type: {event.event_type}")
            return

        logger.debug(f"Dispatching event {event.event_type} to {len(subscribers)} subscribers")
        
        tasks = []
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in event subscriber {callback.__name__}: {e}")
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    callback = subscribers[i] if i < len(subscribers) else None
                    name = getattr(callback, '__name__', 'unknown') if callback else 'unknown'
                    logger.error(f"Error in event subscriber {name}: {result}")

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        if event_type:
            filtered = [e for e in self._event_history if e.event_type == event_type]
        else:
            filtered = self._event_history
        return filtered[-limit:]

    def clear_history(self) -> None:
        self._event_history.clear()
