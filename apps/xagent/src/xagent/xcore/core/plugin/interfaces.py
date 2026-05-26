"""Plugin Registry Interface

Defines the contract for plugin registry implementations.
"""

from typing import Dict, Optional, Protocol, Type


class IPluginRegistry(Protocol):
    """Plugin Registry Interface
    
    Defines the contract for plugin registry implementations.
    This interface allows different components to access plugin information
    without depending on specific implementation details.
    """
    
    def get_all_plugins(self) -> Dict[str, Type]:
        """Get all discovered plugin classes
        
        Returns:
            Dictionary of all plugin classes {plugin_key: plugin_class}
        """
        ...
    
    def get_plugins_by_type(self, plugin_type: str) -> Dict[str, Type]:
        """Get plugin classes filtered by type
        
        Args:
            plugin_type: Plugin type to filter by (e.g., 'south', 'north', 'rule_engine.rule')
            
        Returns:
            Dictionary of plugin classes matching the type
        """
        ...
    
    def get_plugin(self, plugin_key: str) -> Optional[Type]:
        """Get specific plugin class by key
        
        Args:
            plugin_key: Plugin key in format 'plugin_type:plugin_name'
            
        Returns:
            Plugin class, or None if not found
        """
        ...
