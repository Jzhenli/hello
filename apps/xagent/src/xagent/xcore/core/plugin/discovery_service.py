"""Plugin Discovery Service - Singleton service for one-time plugin discovery

This service ensures plugins are discovered only once during application lifecycle,
eliminating redundant file system scans and module imports.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type

from .discovery import PluginDiscovery

logger = logging.getLogger(__name__)


class PluginDiscoveryService:
    """Singleton service for one-time plugin discovery
    
    This service ensures that plugin discovery happens only once per application
    lifecycle. Multiple components can request plugin discovery without triggering
    redundant file system scans.
    
    Thread-safe implementation using asyncio.Lock for concurrent access.
    
    Attributes:
        _instance: Singleton instance
        _discovered: Cached discovery results
        _lock: Async lock for thread safety
    """
    
    _instance: Optional['PluginDiscoveryService'] = None
    _discovered: Optional[Dict[str, Type]] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def discover_once(self, plugin_dirs: List[str]) -> Dict[str, Type]:
        """Discover plugins once and cache results
        
        This method is idempotent - multiple calls will only perform discovery
        once and return cached results on subsequent calls.
        
        Args:
            plugin_dirs: List of plugin directories to scan
            
        Returns:
            Dictionary of discovered plugin classes {plugin_key: plugin_class}
        """
        if self._discovered is not None:
            logger.debug("Using cached plugin discovery results")
            return self._discovered
        
        async with self._lock:
            if self._discovered is not None:
                return self._discovered
            
            logger.info(f"Starting plugin discovery in {len(plugin_dirs)} directories")
            
            discovery = PluginDiscovery(plugin_dirs=plugin_dirs)
            self._discovered = discovery.discover_plugins()
            
            logger.info(f"Plugin discovery completed: {len(self._discovered)} plugins found")
            return self._discovered
    
    def get_discovered(self) -> Optional[Dict[str, Type]]:
        """Get cached discovery results without triggering discovery
        
        Returns:
            Cached plugin classes dictionary, or None if not discovered yet
        """
        return self._discovered
    
    def clear_cache(self) -> None:
        """Clear discovery cache
        
        This is primarily useful for testing purposes.
        In production, cache should persist for the application lifecycle.
        """
        self._discovered = None
        logger.debug("Plugin discovery cache cleared")
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance
        
        This is primarily useful for testing purposes.
        """
        if cls._instance is not None:
            cls._instance.clear_cache()
            cls._instance = None
            logger.debug("PluginDiscoveryService instance reset")
