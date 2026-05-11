"""Command Executor Service - Async command execution system"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from collections import OrderedDict

from ..models.command import CommandStatus, ControlCommand
from ...core.plugin_loader import PluginType, PluginLoader

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Async command execution system"""
    
    def __init__(self, max_history: int = 100, default_timeout: float = 30.0):
        self.max_history = max_history
        self.default_timeout = default_timeout
        
        self._commands: OrderedDict[str, ControlCommand] = OrderedDict()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._plugin_loader: Optional[PluginLoader] = None

    def set_plugin_loader(self, plugin_loader: PluginLoader) -> None:
        self._plugin_loader = plugin_loader

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Command Executor started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Command Executor stopped")

    async def submit_command(
        self,
        command_id: str,
        target_service: str,
        target_asset: str,
        operation: str,
        parameters: Dict[str, Any],
        expiry: Optional[int] = None
    ) -> bool:
        expiry_timestamp = None
        if expiry:
            expiry_timestamp = time.time() + expiry
        
        command = ControlCommand(
            command_id=command_id,
            target_service=target_service,
            target_asset=target_asset,
            operation=operation,
            parameters=parameters,
            status=CommandStatus.ACCEPTED,
            expiry=expiry_timestamp
        )
        
        self._commands[command_id] = command
        self._enforce_history_limit()
        
        await self._queue.put(command)
        
        logger.info(f"Command submitted: {command_id} -> {target_service}.{operation}")
        return True

    async def _worker_loop(self):
        while self._running:
            try:
                command = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._execute_command(command)
            except asyncio.TimeoutError:
                self._cleanup_expired_commands()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in command worker loop: {e}")

    async def _execute_command(self, command: ControlCommand):
        if command.expiry and time.time() > command.expiry:
            command.status = CommandStatus.EXPIRED
            command.updated_at = time.time()
            logger.warning(f"Command expired: {command.command_id}")
            return
        
        command.status = CommandStatus.EXECUTING
        command.updated_at = time.time()
        
        logger.info(f"Executing command: {command.command_id}")
        
        try:
            result = await self._dispatch_to_plugin(command)
            
            command.result = result
            command.status = CommandStatus.COMPLETED
            command.updated_at = time.time()
            logger.info(f"Command completed: {command.command_id}")
            
        except asyncio.TimeoutError:
            command.status = CommandStatus.FAILED
            command.error = "Command timeout"
            command.updated_at = time.time()
            logger.error(f"Command timeout: {command.command_id}")
            
        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            command.updated_at = time.time()
            logger.error(f"Command failed: {command.command_id}, error: {e}")

    async def _dispatch_to_plugin(self, command: ControlCommand) -> Any:
        if self._plugin_loader is None:
            raise RuntimeError("Plugin loader not set")
        
        south_plugins = self._plugin_loader.get_plugins_by_type(PluginType.SOUTH)
        
        target_plugin = None
        for plugin in south_plugins:
            if plugin.name == command.target_service:
                target_plugin = plugin
                break
        
        if target_plugin is None:
            raise RuntimeError(f"Target service not found: {command.target_service}")
        
        instance = target_plugin.instance
        
        if command.operation == "write_setpoint":
            if not hasattr(instance, "write_setpoint"):
                raise AttributeError(f"Plugin {command.target_service} does not support write_setpoint")
            
            return await asyncio.wait_for(
                instance.write_setpoint(
                    command.target_asset,
                    command.parameters.get("point"),
                    command.parameters.get("value")
                ),
                timeout=self.default_timeout
            )
        
        elif command.operation == "execute_operation":
            if not hasattr(instance, "execute_operation"):
                raise AttributeError(f"Plugin {command.target_service} does not support execute_operation")
            
            return await asyncio.wait_for(
                instance.execute_operation(
                    command.target_asset,
                    command.operation,
                    command.parameters
                ),
                timeout=self.default_timeout
            )
        
        else:
            raise ValueError(f"Unknown operation: {command.operation}")

    def _cleanup_expired_commands(self):
        now = time.time()
        expired = [
            cmd_id for cmd_id, cmd in self._commands.items()
            if cmd.expiry and now > cmd.expiry and cmd.status in [CommandStatus.PENDING, CommandStatus.ACCEPTED]
        ]
        
        for cmd_id in expired:
            self._commands[cmd_id].status = CommandStatus.EXPIRED
            logger.debug(f"Command expired: {cmd_id}")

    def _enforce_history_limit(self):
        while len(self._commands) > self.max_history:
            self._commands.popitem(last=False)

    def get_command_status(self, command_id: str) -> Optional[Dict[str, Any]]:
        command = self._commands.get(command_id)
        if command is None:
            return None
        
        return {
            "command_id": command.command_id,
            "status": command.status.value,
            "result": command.result,
            "error": command.error,
            "created_at": command.created_at,
            "updated_at": command.updated_at
        }

    def get_command_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        commands = list(self._commands.values())[-limit:]
        return [
            {
                "command_id": c.command_id,
                "target_service": c.target_service,
                "operation": c.operation,
                "status": c.status.value,
                "created_at": c.created_at
            }
            for c in reversed(commands)
        ]
