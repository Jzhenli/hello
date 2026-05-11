"""Scheduler - Task scheduler for managing periodic and async tasks"""

import asyncio
import logging
import warnings
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    POLLING = "Polling"
    UPLOAD = "Upload"
    MAINTENANCE = "Maintenance"
    CUSTOM = "Custom"


class TaskStatus(str, Enum):
    """[DEPRECATED] TaskStatus is not used externally and will be removed in a future version."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    task_type: TaskType
    callback: Callable
    interval: Optional[float] = None
    initial_delay: float = 0
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 3
    _task: Optional[asyncio.Task] = None


class Scheduler:
    def __init__(self, max_workers: int = 10, task_timeout: int = 30):
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running_tasks: Set[str] = set()
        self._running: bool = False
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_workers)

    async def start(self):
        self._running = True
        logger.info(f"Scheduler started with {self.max_workers} max workers")

    async def stop(self):
        self._running = False
        await self.cancel_all()
        logger.info("Scheduler stopped")

    def add_task(
        self,
        name: str,
        callback: Callable,
        task_type: TaskType = TaskType.CUSTOM,
        interval: Optional[float] = None,
        initial_delay: float = 0,
        *args,
        **kwargs
    ) -> str:
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            task_type=task_type,
            callback=callback,
            interval=interval,
            initial_delay=initial_delay,
            args=args,
            kwargs=kwargs
        )
        
        if interval is not None and interval > 0:
            from datetime import timedelta
            task.next_run = datetime.now() + timedelta(seconds=initial_delay)
        
        self._tasks[task_id] = task
        logger.info(f"Task added: {name} ({task_id}) type={task_type.value}")
        return task_id

    async def start_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                logger.warning(f"Task {task_id} not found")
                return False
            
            task = self._tasks[task_id]
            if task._task is not None and not task._task.done():
                logger.warning(f"Task {task_id} is already running")
                return False
            
            task.status = TaskStatus.RUNNING
            self._running_tasks.add(task_id)
            
            if task.interval is not None and task.interval > 0:
                task._task = asyncio.create_task(self._run_periodic(task))
            else:
                task._task = asyncio.create_task(self._run_once(task))
            
            logger.info(f"Task started: {task.name} ({task_id})")
            return True

    async def stop_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task._task is not None and not task._task.done():
                task._task.cancel()
                try:
                    await task._task
                except asyncio.CancelledError:
                    pass
            
            task.status = TaskStatus.CANCELLED
            self._running_tasks.discard(task_id)
            logger.info(f"Task stopped: {task.name} ({task_id})")
            return True

    async def cancel_all(self):
        task_ids = list(self._tasks.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)

    async def _run_once(self, task: ScheduledTask):
        async with self._semaphore:
            try:
                logger.debug(f"Executing task: {task.name}")
                task.last_run = datetime.now()
                
                if asyncio.iscoroutinefunction(task.callback):
                    await asyncio.wait_for(
                        task.callback(*task.args, **task.kwargs),
                        timeout=self.task_timeout
                    )
                else:
                    await asyncio.wait_for(
                        asyncio.to_thread(task.callback, *task.args, **task.kwargs),
                        timeout=self.task_timeout
                    )
                
                task.status = TaskStatus.COMPLETED
                task.error_count = 0
                logger.debug(f"Task completed: {task.name}")
                
            except asyncio.TimeoutError:
                task.error_count += 1
                task.status = TaskStatus.FAILED
                logger.error(f"Task timeout: {task.name}")
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                logger.info(f"Task cancelled: {task.name}")
                raise
            except Exception as e:
                task.error_count += 1
                task.status = TaskStatus.FAILED
                logger.error(f"Task failed: {task.name}, error: {e}", exc_info=True)
            finally:
                self._running_tasks.discard(task.task_id)

    async def _run_periodic(self, task: ScheduledTask):
        if task.initial_delay > 0:
            await asyncio.sleep(task.initial_delay)
        
        while self._running and task.error_count < task.max_errors:
            await self._run_once(task)
            
            if task.interval and task.interval > 0:
                await asyncio.sleep(task.interval)
            else:
                break
        
        if task.error_count >= task.max_errors:
            logger.error(f"Task {task.name} exceeded max errors, stopping")

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks.values())

    def get_running_tasks(self) -> List[ScheduledTask]:
        return [self._tasks[tid] for tid in self._running_tasks if tid in self._tasks]

    def get_tasks_by_type(self, task_type: TaskType) -> List[ScheduledTask]:
        return [t for t in self._tasks.values() if t.task_type == task_type]

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
