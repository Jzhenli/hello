"""Startup steps definitions."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a startup step."""
    success: bool
    error_message: Optional[str] = None
    data: Optional[Any] = None
    
    @classmethod
    def ok(cls, data: Any = None) -> 'StepResult':
        """Create a successful result."""
        return cls(success=True, data=data)
    
    @classmethod
    def error(cls, message: str) -> 'StepResult':
        """Create an error result."""
        return cls(success=False, error_message=message)


class StartupStep:
    """Base class for startup steps."""
    
    def __init__(self, name: str):
        self.name = name
        self._progress_callback: Optional[Callable[[int], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int], None]) -> None:
        """Set the progress callback function."""
        self._progress_callback = callback
    
    async def execute(self, context: dict) -> StepResult:
        """Execute the step. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _update_progress(self, progress: int):
        """Update progress if callback is set."""
        if self._progress_callback:
            self._progress_callback(progress)


class LoadConfigStep(StartupStep):
    """Step to load configuration."""
    
    def __init__(self):
        super().__init__("Load Configuration")
    
    async def execute(self, context: dict) -> StepResult:
        try:
            config_manager = context.get('config_manager')
            if config_manager is None:
                from xagent.xcore.core import ConfigManager
                config_manager = ConfigManager()
                context['config_manager'] = config_manager
            
            config = context.get('config') or config_manager.load()
            context['config'] = config
            
            logger.info("Configuration loaded successfully")
            return StepResult.ok(config)
        except Exception as e:
            logger.exception(f"Error loading configuration: {e}")
            return StepResult.error(f"Failed to load configuration: {str(e)}")


class InitializeGatewayStep(StartupStep):
    """Step to initialize gateway."""
    
    def __init__(self):
        super().__init__("Initialize Gateway")
    
    async def execute(self, context: dict) -> StepResult:
        try:
            from xagent.xcore.gateway import Gateway
            
            config_manager = context.get('config_manager')
            gateway = Gateway(config_manager=config_manager)
            await gateway.initialize()
            
            context['gateway'] = gateway
            logger.info("Gateway initialized successfully")
            return StepResult.ok(gateway)
        except Exception as e:
            logger.exception(f"Error initializing gateway: {e}")
            return StepResult.error(f"Failed to initialize gateway: {str(e)}")


class StartCoreServicesStep(StartupStep):
    """Step to start gateway core services (without plugins)."""
    
    def __init__(self):
        super().__init__("Start Core Services")
    
    async def execute(self, context: dict) -> StepResult:
        try:
            gateway = context.get('gateway')
            if not gateway:
                return StepResult.error("Gateway not initialized")
            
            await gateway.start_core()
            logger.info("Gateway core services started successfully")
            return StepResult.ok()
        except Exception as e:
            logger.exception(f"Error starting core services: {e}")
            return StepResult.error(f"Failed to start core services: {str(e)}")


class StartPluginsStep(StartupStep):
    """Step to start plugins (can be run asynchronously)."""
    
    def __init__(self, async_mode: bool = True):
        super().__init__("Start Plugins")
        self.async_mode = async_mode
        self._plugin_task: Optional[asyncio.Task] = None
    
    async def execute(self, context: dict) -> StepResult:
        try:
            gateway = context.get('gateway')
            if not gateway:
                return StepResult.error("Gateway not initialized")
            
            if self.async_mode:
                self._plugin_task = asyncio.create_task(gateway.start_plugins())
                self._plugin_task.add_done_callback(self._on_task_done)
                logger.info("Plugin startup task scheduled in background")
                return StepResult.ok()
            else:
                await gateway.start_plugins()
                logger.info("Plugins started successfully")
                return StepResult.ok()
        except Exception as e:
            logger.exception(f"Error starting plugins: {e}")
            return StepResult.error(f"Failed to start plugins: {str(e)}")
    
    @staticmethod
    def _on_task_done(task: asyncio.Task):
        if task.cancelled():
            logger.warning("Plugin startup task was cancelled")
        elif task.exception():
            logger.error(f"Plugin startup task failed: {task.exception()}")


class StartWebServerStep(StartupStep):
    """Step to start web server."""
    
    def __init__(self, host: str, port: int):
        super().__init__("Start Web Service")
        self.host = host
        self.port = port
    
    async def execute(self, context: dict) -> StepResult:
        try:
            import uvicorn
            from xagent.xcore.api import app as fastapi_app
            
            config = context.get('config')
            log_level = config.logging.level.lower() if config else "info"
            
            uvicorn_config = uvicorn.Config(
                app=fastapi_app,
                host=self.host,
                port=self.port,
                reload=False,
                log_level=log_level,
                access_log=False,
                log_config=None
            )
            server = uvicorn.Server(uvicorn_config)
            
            asyncio.create_task(server.serve())
            
            context['server'] = server
            context['server_port'] = self.port
            context['server_host'] = self.host
            
            logger.info(f"Web server started on {self.host}:{self.port}")
            return StepResult.ok(server)
        except Exception as e:
            logger.exception(f"Error starting web server: {e}")
            return StepResult.error(f"Failed to start web service: {str(e)}")


class WaitForServerStep(StartupStep):
    """Step to wait for server to be ready."""
    
    def __init__(self, port: int, max_attempts: int = 50, interval: float = 0.1):
        super().__init__("Wait for Ready")
        self.port = port
        self.max_attempts = max_attempts
        self.interval = interval
    
    async def execute(self, context: dict) -> StepResult:
        for attempt in range(self.max_attempts):
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
                writer.close()
                await writer.wait_closed()
                logger.info("Server is ready!")
                return StepResult.ok()
            except (ConnectionRefusedError, OSError):
                await asyncio.sleep(self.interval)
        
        logger.error("Server failed to start in time")
        return StepResult.error("Server startup timed out")
