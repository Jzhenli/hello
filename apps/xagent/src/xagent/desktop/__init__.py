"""Desktop application module."""

from .app import main, XAgentDesktopApp
from .config import DesktopConfig
from .platform import setup_platform, is_windows, is_macos, is_linux
from .startup import BackendManager
from .ui import SplashScreen, ErrorScreen, WebViewManager
from .utils import find_available_port

__all__ = [
    'main',
    'XAgentDesktopApp',
    'DesktopConfig',
    'setup_platform',
    'is_windows',
    'is_macos',
    'is_linux',
    'BackendManager',
    'SplashScreen',
    'ErrorScreen',
    'WebViewManager',
    'find_available_port',
]
