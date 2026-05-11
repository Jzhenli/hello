"""FastAPI dependencies for dependency injection"""

from typing import Any, Optional, TYPE_CHECKING
from functools import lru_cache

from fastapi import Depends, HTTPException

from ..storage import StorageInterface, SQLiteStorage, WriteBehindBuffer
from ..core.metadata import MetadataManager
from ..core.config import ConfigManager
from ..core.paths import get_paths
from .services.command_executor import CommandExecutor

if TYPE_CHECKING:
    from ..gateway import Gateway


class AppState:
    """Application state container"""
    
    def __init__(self):
        self.storage: Optional[SQLiteStorage] = None
        self.buffer: Optional[WriteBehindBuffer] = None
        self.metadata_manager: Optional[MetadataManager] = None
        self.command_executor: Optional[CommandExecutor] = None
        self.gateway: Optional["Gateway"] = None
        self.cleanup_task: Optional[Any] = None
        self._gateway_owned: bool = False
        self._config_manager: Optional[ConfigManager] = None
    
    def is_initialized(self) -> bool:
        """Check if the application state is initialized"""
        return self.storage is not None and self.buffer is not None
    
    def get_config_manager(self) -> ConfigManager:
        """Get or create ConfigManager instance"""
        if self._config_manager is None:
            paths = get_paths()
            self._config_manager = ConfigManager(paths=paths)
        return self._config_manager


@lru_cache()
def get_app_state() -> AppState:
    """Get singleton application state"""
    return AppState()


def get_storage(state: AppState = Depends(get_app_state)) -> StorageInterface:
    """Get storage instance via dependency injection"""
    if state.storage is None:
        raise HTTPException(status_code=500, detail="Storage not initialized")
    return state.storage


def get_buffer(state: AppState = Depends(get_app_state)) -> WriteBehindBuffer:
    """Get buffer instance via dependency injection"""
    if state.buffer is None:
        raise HTTPException(status_code=500, detail="Buffer not initialized")
    return state.buffer


def get_config_manager(state: AppState = Depends(get_app_state)) -> ConfigManager:
    """Get ConfigManager instance via dependency injection"""
    return state.get_config_manager()


def get_metadata_manager(state: AppState = Depends(get_app_state)) -> Optional[MetadataManager]:
    """Get metadata manager instance via dependency injection"""
    return state.metadata_manager


def get_command_executor(state: AppState = Depends(get_app_state)) -> CommandExecutor:
    """Get command executor instance via dependency injection"""
    if state.command_executor is None:
        raise HTTPException(status_code=500, detail="Command executor not initialized")
    return state.command_executor


def get_gateway(state: AppState = Depends(get_app_state)) -> Optional["Gateway"]:
    """Get gateway instance via dependency injection"""
    return state.gateway


def get_cleanup_task(state: AppState = Depends(get_app_state)) -> Optional[Any]:
    """Get cleanup task instance via dependency injection"""
    return state.cleanup_task


def set_gateway_storage(
    storage: SQLiteStorage,
    buffer: WriteBehindBuffer,
    metadata_manager: Optional[MetadataManager] = None,
    command_executor: Optional[CommandExecutor] = None,
    gateway: Optional["Gateway"] = None,
    cleanup_task: Optional[Any] = None
) -> None:
    """Set gateway storage instances (called during initialization)"""
    state = get_app_state()
    state.storage = storage
    state.buffer = buffer
    state.metadata_manager = metadata_manager
    state.command_executor = command_executor
    state.gateway = gateway
    state.cleanup_task = cleanup_task
