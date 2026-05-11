"""Platform-specific initialization and utilities."""

import platform
import sys
from typing import Optional


def setup_platform() -> None:
    """Setup platform-specific configurations."""
    if platform.system() == "Windows":
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())


def get_platform_name() -> str:
    """Get the current platform name."""
    return platform.system()


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def get_python_version() -> str:
    """Get the Python version string."""
    return sys.version


def get_platform_info() -> dict:
    """Get comprehensive platform information."""
    return {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version,
    }
