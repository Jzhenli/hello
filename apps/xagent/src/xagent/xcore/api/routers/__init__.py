"""API routers"""

from .system import router as system_router
from .data import router as data_router
from .storage import router as storage_router
from .control import router as control_router
from .plugins import router as plugins_router
from .config import router as config_router
from .metadata import router as metadata_router
from .rules import router as rules_router
from .devices import router as devices_router
from .users import router as users_router
from .north_channels import router as north_channels_router

__all__ = [
    "system_router",
    "data_router",
    "storage_router",
    "control_router",
    "plugins_router",
    "config_router",
    "metadata_router",
    "rules_router",
    "devices_router",
    "users_router",
    "north_channels_router",
]
