"""Desktop application configuration management."""

import warnings
from dataclasses import dataclass, field
from typing import List, Tuple


def get_version() -> str:
    """获取应用版本号
    
    从包元数据中获取版本号，如果失败则返回默认值。
    
    Returns:
        版本号字符串
    """
    try:
        from xagent import __version__
        return __version__
    except Exception:
        pass
    
    return "0.0.1"


@dataclass
class SplashStep:
    """Configuration for a startup step."""
    name: str
    progress: int


@dataclass
class SplashConfig:
    """Configuration for splash screen."""
    title: str = "XAgent Gateway"
    subtitle: str = "IoT Gateway Monitoring System"
    version: str = field(default_factory=get_version)
    steps: List[SplashStep] = field(default_factory=lambda: [
        SplashStep("Load Configuration", 20),
        SplashStep("Initialize Gateway", 40),
        SplashStep("Start Core Services", 60),
        SplashStep("Start Web Service", 80),
        SplashStep("Wait for Ready", 95),
        SplashStep("Done", 100),
    ])


@dataclass
class ErrorScreenConfig:
    """Configuration for error screen."""
    title: str = "Startup Failed"
    title_color: str = '#dc3545'
    message_color: str = '#666666'
    title_font_size: int = 20
    message_font_size: int = 13


@dataclass
class WindowConfig:
    """Configuration for main window."""
    title: str = "XAgent Gateway"
    width: int = 800
    height: int = 600


@dataclass
class ServerConfig:
    """Configuration for backend server.
    
    Note: host and port are now read from resources/config/config.yaml (server.host and server.port).
    These fields are kept for backward compatibility and max_port_attempts/max_wait_attempts.
    """
    host: str = "127.0.0.1"
    port: int = 8080
    max_port_attempts: int = 100
    max_wait_attempts: int = 50
    wait_interval: float = 0.1
    
    def __post_init__(self):
        if self.host != "127.0.0.1" or self.port != 8080:
            warnings.warn(
                "ServerConfig.host and ServerConfig.port are deprecated. "
                "Configure server.host and server.port in resources/config/config.yaml instead.",
                DeprecationWarning,
                stacklevel=2,
            )


@dataclass
class DesktopConfig:
    """Main configuration for desktop application."""
    formal_name: str = "XAgent Gateway"
    app_id: str = "com.adveco.xagent"
    app_name: str = "xagent"
    
    splash: SplashConfig = field(default_factory=SplashConfig)
    error_screen: ErrorScreenConfig = field(default_factory=ErrorScreenConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    
    @classmethod
    def default(cls) -> 'DesktopConfig':
        """Create default configuration."""
        return cls()
