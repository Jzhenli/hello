"""Backend manager for desktop application."""

import asyncio
import logging
from typing import Callable, List, Optional, Tuple

from ..config import DesktopConfig
from ..utils import find_available_port
from .steps import (
    StartupStep,
    LoadConfigStep,
    InitializeGatewayStep,
    StartCoreServicesStep,
    StartPluginsStep,
    StartWebServerStep,
    WaitForServerStep,
)

logger = logging.getLogger(__name__)


class BackendManager:
    """Manages backend services startup and shutdown."""

    def __init__(self, config: DesktopConfig):
        self.config = config
        self.gateway = None
        self.server = None
        self.server_port: int = config.server.port
        self.server_host: str = config.server.host
        self.socket: Optional[asyncio.Future] = None
        self._server_ready = asyncio.Event()
        self._context: dict = {}
        self._steps: List[StartupStep] = []

    async def wait_for_socket(self):
        """Wait for server socket to be available."""
        logger.info("Waiting for server socket...")
        await self._server_ready.wait()

        if self.server and self.server.servers:
            for server in self.server.servers:
                for socket in server.sockets:
                    self.socket.set_result(socket)
                    logger.info("Server socket is ready.")
                    return

    async def start(
        self,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Start backend services.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            self.socket = asyncio.Future()
            self._setup_steps()
            
            for i, step in enumerate(self._steps):
                if progress_callback:
                    progress_callback(i)
                
                await asyncio.sleep(0)
                
                result = await step.execute(self._context)
                
                if not result.success:
                    return False, result.error_message
            
            self.gateway = self._context.get('gateway')
            self.server = self._context.get('server')
            self.server_port = self._context.get('server_port', self.server_port)
            self.server_host = self._context.get('server_host', self.server_host)
            
            if self.server and self.server.started:
                self._server_ready.set()
            
            return True, None
            
        except Exception as e:
            logger.exception(f"Error starting backend: {e}")
            return False, str(e)

    def _setup_steps(self):
        """Setup startup steps."""
        from xagent.xcore.core import ConfigManager, setup_logging
        
        config_manager = ConfigManager()
        gateway_config = config_manager.load()
        
        setup_logging(gateway_config.logging)
        
        self._context['config_manager'] = config_manager
        self._context['config'] = gateway_config
        
        host = gateway_config.server.host
        port = find_available_port(
            gateway_config.server.port,
            self.config.server.max_port_attempts
        )
        
        logger.info(f"Using server configuration from resources/config/config.yaml: {host}:{port}")
        
        self._steps = [
            LoadConfigStep(),
            InitializeGatewayStep(),
            StartCoreServicesStep(),
            StartWebServerStep(
                host=host,
                port=port
            ),
            WaitForServerStep(
                port=port,
                max_attempts=self.config.server.max_wait_attempts,
                interval=self.config.server.wait_interval
            ),
            StartPluginsStep(async_mode=True),
        ]

    async def stop(self) -> bool:
        """Stop backend services."""
        if self.server:
            if not self.server.started:
                logger.info("Waiting for the server to finish starting...")
                if self.socket and not self.socket.done():
                    try:
                        await self.socket
                    except Exception:
                        logger.debug("Error waiting for socket", exc_info=True)

            logger.info("Shutting down web server...")
            await self.server.shutdown()

        if self.gateway:
            try:
                await self.gateway.stop()
                logger.info("Gateway stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping gateway: {e}")

        return True
