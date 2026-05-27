import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from xagent.xcore.core.event_bus import EventBus, Event, EventType
from xagent.xcore.plugins.north import NorthPluginBase
from xagent.xcore.storage.interface import Reading

from .constants import (
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_PORT,
    DEFAULT_LOCAL_PORT,
    DEFAULT_BATCH_SIZE,
    DEFAULT_INTERVAL,
    DEFAULT_RECONNECT_INTERVAL,
    MAX_RECONNECT_INTERVAL,
)
from .handler import ProtobufHandler
from .mapping import StaticMapper, DynamicMapper
from .models import CommandMessage
from .transport import UDPTransport

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({"password", "secret", "token", "api_key", "secret_key", "access_key"})


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for k, v in config.items():
        if k.lower() in _SENSITIVE_KEYS:
            sanitized[k] = "***"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_config(v)
        else:
            sanitized[k] = v
    return sanitized


class XNCPlusPlugin(NorthPluginBase):
    __plugin_name__ = "xnc_plus"

    def _create_data_adapter(self) -> Any:
        return self._handler

    def __init__(self, config: Dict[str, Any], storage: Any, event_bus: EventBus):
        logger.info(
            f"Initializing XNC Plus plugin with config: {_sanitize_config(config)}"
        )

        self._remote_host = config.get("remote_host", DEFAULT_REMOTE_HOST)
        self._remote_port = config.get("remote_port", DEFAULT_REMOTE_PORT)
        self._local_port = config.get("local_port", DEFAULT_LOCAL_PORT)
        self._reconnect_interval = config.get(
            "reconnect_interval", DEFAULT_RECONNECT_INTERVAL
        )

        self._transport = UDPTransport(
            remote_host=self._remote_host,
            remote_port=self._remote_port,
            local_port=self._local_port,
        )

        static_mapper = StaticMapper(config.get("mapping_config", {}))
        persist_path = config.get("mapping_persist_path")
        self._mapper = DynamicMapper(static_mapper, persist_path)

        uuid_val = config.get("uuid", 0)
        batch_size = config.get("adapter_batch_size", 50)
        self._handler = ProtobufHandler(self._mapper, uuid=uuid_val, batch_size=batch_size)

        self._upload_task: Optional[asyncio.Task] = None
        self._reconnect_delay = self._reconnect_interval

        self._transport.set_command_handler(self._handle_command_data)

        super().__init__(config, storage, event_bus)

        logger.info(
            f"XNC Plus plugin initialized: "
            f"remote={self._remote_host}:{self._remote_port}, "
            f"local_port={self._local_port}"
        )

    async def connect(self) -> bool:
        result = await self._transport.connect()
        self._connected = result
        return result

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        self._connected = False

    async def start(self) -> None:
        await super().start()
        try:
            self._upload_task = asyncio.create_task(self._upload_loop())
        except Exception:
            self._running = False
            logger.error("Failed to create upload task, rolling back start")
            raise
        logger.info(f"XNC Plus plugin started: {self._service_name}")

    async def stop(self) -> None:
        if self._upload_task:
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass
            self._upload_task = None
        await super().stop()
        logger.info(f"XNC Plus plugin stopped: {self._service_name}")

    async def send(self, readings: List[Reading]) -> int:
        if not self._transport.is_connected or not readings:
            return 0

        context = {"timestamp": time.time()}
        packets = self._handler.encode_upload(readings, context)

        sent = 0
        for packet in packets:
            if self._transport.send(packet):
                sent += 1
            else:
                logger.warning(f"Failed to send packet {sent + 1}/{len(packets)}")

        if sent > 0:
            logger.info(f"Sent {sent} packets to {self._remote_host}:{self._remote_port}")
        return sent

    async def fetch_and_send(self, batch_size: int = 100) -> int:
        if not self.storage:
            return 0

        try:
            readings = await self.storage.query(limit=batch_size * 2)
            if not readings:
                return 0

            latest = self._dedup_readings(readings)[:batch_size]
            return await self.send(latest)
        except Exception as e:
            logger.error(f"Error fetching and sending readings: {e}", exc_info=True)
            return 0

    async def _upload_loop(self) -> None:
        logger.info(
            f"Upload loop started, interval={self._interval}s, batch_size={self._batch_size}"
        )
        while self._running:
            try:
                if not self._transport.is_connected:
                    logger.warning("Transport not connected, attempting reconnect...")
                    success = await self.connect()
                    if success:
                        self._reconnect_delay = self._reconnect_interval
                    else:
                        self._reconnect_delay = min(
                            self._reconnect_delay * 2, MAX_RECONNECT_INTERVAL
                        )
                        logger.warning(
                            f"Reconnect failed, next attempt in {self._reconnect_delay}s"
                        )
                        await asyncio.sleep(self._reconnect_delay)
                        continue

                await self.fetch_and_send(self._batch_size)
                await asyncio.sleep(self._interval)

            except asyncio.CancelledError:
                logger.info("Upload loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in upload loop: {e}")
                await asyncio.sleep(self._interval)

    async def _handle_command_data(self, data: bytes, addr: tuple) -> None:
        try:
            cmd = self._handler.decode_command(data, addr)
            if cmd is None:
                return

            logger.info(
                f"Received command: type={cmd.command_type}, "
                f"device={cmd.device_id}, addr={addr}"
            )

            event = Event(
                event_type=EventType.COMMAND_RECEIVED,
                data={
                    "asset": cmd.device_id,
                    "command": cmd.command_type,
                    "points": cmd.points,
                    "data": cmd.data,
                },
            )
            await self.event_bus.publish(event)

            response = self._handler.encode_response(cmd)
            if response:
                self._transport.send(response, addr=cmd.reply_addr)

        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)

    @staticmethod
    def _dedup_readings(readings: List[Reading]) -> List[Reading]:
        by_asset: Dict[str, Reading] = {}
        for r in readings:
            if r.asset not in by_asset or r.timestamp > by_asset[r.asset].timestamp:
                by_asset[r.asset] = r
        return list(by_asset.values())

    @classmethod
    def config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "remote_host": {"type": "string", "default": DEFAULT_REMOTE_HOST},
                "remote_port": {"type": "integer", "default": DEFAULT_REMOTE_PORT},
                "local_port": {"type": "integer", "default": DEFAULT_LOCAL_PORT},
                "batch_size": {"type": "integer", "default": DEFAULT_BATCH_SIZE},
                "interval": {"type": "integer", "default": DEFAULT_INTERVAL},
                "reconnect_interval": {
                    "type": "integer",
                    "default": DEFAULT_RECONNECT_INTERVAL,
                },
                "uuid": {"type": "integer", "default": 0},
                "mapping_config": {"type": "object"},
                "mapping_persist_path": {"type": "string"},
            },
        }

    @classmethod
    def capabilities(cls) -> List[str]:
        return ["upload", "command"]
