"""Data Cleanup Task - Automatic data retention management"""

import logging
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .interface import StorageInterface

logger = logging.getLogger(__name__)


@dataclass
class CleanupStats:
    total_cleanups: int = 0
    total_deleted: int = 0
    last_cleanup: Optional[datetime] = None
    last_deleted_count: int = 0
    last_cleanup_duration_ms: float = 0
    errors: int = 0
    last_error: Optional[str] = None


class DataCleanupTask:
    def __init__(
        self,
        storage: StorageInterface,
        retention_days: int,
        cleanup_batch_size: int = 10000
    ):
        self.storage = storage
        self.retention_days = retention_days
        self.cleanup_batch_size = cleanup_batch_size
        self._stats = CleanupStats()
        self._running = False

    async def execute(self) -> int:
        if self._running:
            logger.warning("Cleanup task already running, skipping")
            return 0
        
        self._running = True
        start_time = time.time()
        
        try:
            cutoff_timestamp = self._calculate_cutoff_timestamp()
            
            logger.info(
                f"Starting data cleanup: retention_days={self.retention_days}, "
                f"cutoff_timestamp={cutoff_timestamp}, "
                f"cutoff_datetime={datetime.fromtimestamp(cutoff_timestamp).isoformat()}"
            )
            
            deleted = await self.storage.delete_old_readings_batch(
                before_timestamp=cutoff_timestamp,
                batch_size=self.cleanup_batch_size
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            self._stats.total_cleanups += 1
            self._stats.total_deleted += deleted
            self._stats.last_cleanup = datetime.now()
            self._stats.last_deleted_count = deleted
            self._stats.last_cleanup_duration_ms = round(duration_ms, 2)
            
            logger.info(
                f"Data cleanup completed: deleted={deleted}, "
                f"duration_ms={duration_ms:.2f}"
            )
            
            return deleted
            
        except Exception as e:
            self._stats.errors += 1
            self._stats.last_error = str(e)
            logger.error(f"Data cleanup failed: {e}")
            return 0
        finally:
            self._running = False

    def _calculate_cutoff_timestamp(self) -> float:
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        return cutoff_date.timestamp()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_cleanups": self._stats.total_cleanups,
            "total_deleted": self._stats.total_deleted,
            "last_cleanup": self._stats.last_cleanup.isoformat() if self._stats.last_cleanup else None,
            "last_deleted_count": self._stats.last_deleted_count,
            "last_cleanup_duration_ms": self._stats.last_cleanup_duration_ms,
            "errors": self._stats.errors,
            "last_error": self._stats.last_error,
            "retention_days": self.retention_days,
            "cleanup_batch_size": self.cleanup_batch_size,
            "is_running": self._running
        }

    @property
    def is_running(self) -> bool:
        return self._running


_cleanup_task: Optional[DataCleanupTask] = None


def get_cleanup_task() -> Optional[DataCleanupTask]:
    """Get the global cleanup task instance.
    
    [DEPRECATED] Prefer using DI when possible.
    """
    warnings.warn(
        "get_cleanup_task() module-level accessor is deprecated. Use DI container instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _cleanup_task


def set_cleanup_task(task: DataCleanupTask) -> None:
    """Set the global cleanup task instance.
    
    [DEPRECATED] Prefer using DI when possible.
    """
    warnings.warn(
        "set_cleanup_task() module-level mutator is deprecated. Use DI container instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    global _cleanup_task
    _cleanup_task = task
