import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Set

from .constants import MAX_UDP_PACKET_SIZE

logger = logging.getLogger(__name__)

CommandCallback = Callable[[bytes, tuple], Awaitable[None]]


class _CommandProtocol(asyncio.DatagramProtocol):
    def __init__(self, transport: "UDPTransport"):
        self._transport = transport
        self.protocol_transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.protocol_transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if not self._transport._connected:
            return
        if self._transport._on_command is not None:
            task = asyncio.create_task(self._transport._on_command(data, addr))
            self._transport._command_tasks.add(task)
            task.add_done_callback(self._transport._command_tasks.discard)

    def error_received(self, exc: Exception) -> None:
        logger.error(f"UDP command listener error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        logger.info("UDP command listener connection closed")


class _SendProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.protocol_transport = transport

    def error_received(self, exc: Exception) -> None:
        logger.error(f"UDP send error: {exc}")


class UDPTransport:

    def __init__(
        self,
        remote_host: str,
        remote_port: int,
        local_port: int,
    ):
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._local_port = local_port

        self._send_transport: Optional[asyncio.DatagramTransport] = None
        self._command_transport: Optional[asyncio.DatagramTransport] = None
        self._command_protocol: Optional[_CommandProtocol] = None

        self._connected = False
        self._command_tasks: Set[asyncio.Task] = set()
        self._on_command: Optional[CommandCallback] = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._send_transport is not None

    def set_command_handler(self, handler: CommandCallback) -> None:
        self._on_command = handler

    async def connect(self) -> bool:
        try:
            await self._cleanup()

            loop = asyncio.get_running_loop()

            _, send_proto = await loop.create_datagram_endpoint(
                _SendProtocol,
                remote_addr=(self._remote_host, self._remote_port),
            )
            self._send_transport = send_proto.protocol_transport

            self._command_protocol = _CommandProtocol(self)
            _, cmd_proto = await loop.create_datagram_endpoint(
                lambda: self._command_protocol,
                local_addr=("0.0.0.0", self._local_port),
            )
            self._command_transport = cmd_proto.protocol_transport

            self._connected = True
            logger.info(
                f"UDP transport connected: "
                f"remote={self._remote_host}:{self._remote_port}, "
                f"local_port={self._local_port}"
            )
            return True

        except Exception as e:
            logger.error(f"UDP transport connection failed: {e}")
            await self._cleanup()
            return False

    async def disconnect(self) -> None:
        for task in self._command_tasks:
            task.cancel()
        if self._command_tasks:
            await asyncio.gather(*self._command_tasks, return_exceptions=True)
        self._command_tasks.clear()

        await self._cleanup()
        logger.info("UDP transport disconnected")

    async def _cleanup(self) -> None:
        self._connected = False

        if self._command_transport:
            try:
                self._command_transport.close()
            except Exception:
                pass
            finally:
                self._command_transport = None
                self._command_protocol = None

        if self._send_transport:
            try:
                self._send_transport.close()
            except Exception:
                pass
            finally:
                self._send_transport = None

    def send(self, data: bytes, addr: Optional[tuple] = None) -> bool:
        if not self._connected:
            logger.warning("Transport not connected, cannot send")
            return False

        if len(data) > MAX_UDP_PACKET_SIZE:
            logger.error(
                f"Packet too large: {len(data)} bytes, max {MAX_UDP_PACKET_SIZE} bytes"
            )
            return False

        try:
            if addr is not None and self._command_transport:
                self._command_transport.sendto(data, addr)
            elif self._send_transport:
                self._send_transport.sendto(data)
            else:
                logger.warning("No transport available for sending")
                return False
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
