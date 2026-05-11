"""Write-Behind Buffer - Batch write optimization for storage layer"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .interface import StorageInterface, Reading

logger = logging.getLogger(__name__)


@dataclass
class BufferStats:
    total_writes: int = 0
    total_flushes: int = 0
    buffer_size: int = 0
    last_flush: Optional[datetime] = None
    pending_count: int = 0


class WriteBehindBuffer:
    def __init__(
        self,
        storage: StorageInterface,
        batch_size: int = 100,
        flush_interval: float = 5.0
    ):
        self.storage = storage
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._buffer: List[Reading] = []
        self._lock = asyncio.Lock()
        self._running: bool = False
        self._flush_task: Optional[asyncio.Task] = None
        self._stats = BufferStats(buffer_size=batch_size)

    async def start(self):
        if self._running:
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"Write-Behind Buffer started (batch_size={self.batch_size}, interval={self.flush_interval}s)")

    async def stop(self):
        if not self._running:
            return
        
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        await self.flush()
        logger.info("Write-Behind Buffer stopped")

    async def write(self, reading: Reading) -> bool:
        async with self._lock:
            self._buffer.append(reading)
            self._stats.pending_count = len(self._buffer)
            
            if len(self._buffer) >= self.batch_size:
                await self._do_flush()
        
        return True

    async def write_batch(self, readings: List[Reading]) -> int:
        async with self._lock:
            self._buffer.extend(readings)
            self._stats.pending_count = len(self._buffer)
            
            if len(self._buffer) >= self.batch_size:
                await self._do_flush()
        
        return len(readings)

    async def flush(self) -> int:
        async with self._lock:
            return await self._do_flush()

    async def _do_flush(self) -> int:
        if not self._buffer:
            return 0
        
        readings_to_flush = self._buffer.copy()
        self._buffer.clear()
        self._stats.pending_count = 0
        
        try:
            count = await self.storage.save_batch(readings_to_flush)
            self._stats.total_writes += count
            self._stats.total_flushes += 1
            self._stats.last_flush = datetime.now()
            logger.debug(f"Flushed {count} readings to storage")
            return count
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
            self._buffer.extend(readings_to_flush)
            self._stats.pending_count = len(self._buffer)
            return 0

    async def _flush_loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    def get_stats(self) -> BufferStats:
        return self._stats

    def get_pending_count(self) -> int:
        return len(self._buffer)

    async def query(
        self,
        asset: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Reading]:
        return await self.storage.query(
            asset=asset,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

    async def delete_old_readings(self, before_timestamp: float) -> int:
        return await self.storage.delete_old_readings(before_timestamp)

    async def delete_old_readings_batch(
        self,
        before_timestamp: float,
        batch_size: int = 10000
    ) -> int:
        return await self.storage.delete_old_readings_batch(before_timestamp, batch_size)

    async def get_storage_size(self) -> Dict[str, Any]:
        return await self.storage.get_storage_size()

    async def vacuum_storage(self) -> None:
        return await self.storage.vacuum()

    async def get_stats_from_storage(self) -> Dict[str, Any]:
        return await self.storage.get_stats()
