"""Configuration Manager with Pydantic models and hot-reload support"""

import os
import re
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable
from pydantic import BaseModel, Field
import yaml
from enum import Enum

from .paths import AppPaths, get_paths, get_resource_dir

logger = logging.getLogger(__name__)


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """将 Pydantic 模型转换为字典（兼容 v1 和 v2）
    
    Pydantic v1 使用 .dict()，v2 使用 .model_dump()。
    此函数自动检测并调用正确的方法。
    """
    if hasattr(model, 'model_dump'):
        return model.model_dump()
    return model.dict()


class PluginFailureStrategy(str, Enum):
    """插件启动失败处理策略"""
    FAIL_FAST = "fail_fast"
    CONTINUE = "continue"
    DEGRADED = "degraded"


class PluginImportance(str, Enum):
    """插件重要性"""
    CRITICAL = "critical"
    OPTIONAL = "optional"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False


class StorageConfig(BaseModel):
    type: str = "sqlite"
    database: str = "${data_dir}/xagent.db"
    wal_mode: bool = True
    batch_size: int = 100
    flush_interval: int = 5
    retention_days: int = Field(default=30, ge=0, description="Data retention period in days, 0 to disable auto cleanup")
    cleanup_interval: int = Field(default=3600, ge=60, description="Cleanup task interval in seconds")
    cleanup_batch_size: int = Field(default=10000, ge=100, description="Max records to delete per batch")


class PluginInstanceConfig(BaseModel):
    name: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    failure_strategy: Optional[PluginFailureStrategy] = None
    importance: PluginImportance = PluginImportance.OPTIONAL
    depends_on: List[str] = Field(default_factory=list)


class TransformerConfig(BaseModel):
    name: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class AdapterConfig(BaseModel):
    type: str = "generic_mqtt"
    config: Dict[str, Any] = Field(default_factory=dict)


class SouthPluginConfig(PluginInstanceConfig):
    transformer: Optional[TransformerConfig] = None


class NorthPluginConfig(PluginInstanceConfig):
    adapter: Optional[AdapterConfig] = None


class PluginsConfig(BaseModel):
    south: List[PluginInstanceConfig] = Field(default_factory=list)
    north: List[PluginInstanceConfig] = Field(default_factory=list)
    filter: List[PluginInstanceConfig] = Field(default_factory=list)
    failure_strategy: PluginFailureStrategy = PluginFailureStrategy.CONTINUE
    allow_partial_startup: bool = True


class SchedulerConfig(BaseModel):
    max_workers: int = 10
    task_timeout: int = 30


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "${log_dir}/xagent.log"
    max_bytes: int = Field(default=10 * 1024 * 1024, description="Max size of each log file in bytes")
    backup_count: int = Field(default=5, description="Number of backup log files to keep")
    console: bool = Field(default=True, description="Whether to output logs to console")
    date_format: str = Field(default="%Y-%m-%d %H:%M:%S", description="Date format for log messages")
    color: bool = Field(default=True, description="Whether to use colored output in console")


class MetricsConfig(BaseModel):
    enabled: bool = True
    port: int = 9090


class GatewayConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)


class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    
    @classmethod
    def get_instance(cls, config_path: Optional[str] = None, paths: Optional[AppPaths] = None) -> 'ConfigManager':
        """获取全局单例实例
        
        [DEPRECATED] 优先通过 DI 容器管理实例。此方法作为向后兼容的过渡方案，
        后续应统一使用 Container.resolve() 获取实例。
        """
        warnings.warn(
            "ConfigManager.get_instance() is deprecated. Use DI container instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if cls._instance is None:
            cls._instance = cls(config_path=config_path, paths=paths)
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None, paths: Optional[AppPaths] = None):
        self.paths = paths or get_paths()
        
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._find_config_path()
        
        self._config: Optional[GatewayConfig] = None
        self._last_modified: float = 0
        self._reload_callbacks: List[Callable] = []
        self._event_bus: Optional[Any] = None
    
    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（仅用于测试）"""
        cls._instance = None

    def _find_config_path(self) -> Path:
        """按优先级查找配置文件"""
        search_paths = self._get_config_search_paths()
        
        for desc, path in search_paths:
            try:
                if path and Path(path).exists():
                    logger.info(f"User Config File [{desc}]: {path}")
                    return Path(path)
            except PermissionError:
                logger.debug(f"Skipping path without access permission: {path}")
                continue
            except Exception as e:
                logger.debug(f"Error checking path {path}: {e}")
                continue
        
        # 如果都不存在，检查打包的默认配置
        packaged_config = get_resource_dir() / 'config' / 'config.yaml'
        if packaged_config.exists():
            # 复制打包的默认配置到用户配置目录
            default_path = self.paths.config_file
            try:
                default_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(packaged_config, default_path)
                logger.info(f"Default config copied to: {default_path}")
                return default_path
            except PermissionError:
                logger.warning(f"No permission to create config directory or copy config file: {default_path}")
            except Exception as e:
                logger.warning(f"Error copying default config: {e}")
        
        # 如果连打包的默认配置都不存在，创建默认配置
        default_path = self.paths.config_file
        logger.warning(f"Config file not found, will create default config at: {default_path}")
        self._create_default_config(default_path)
        
        return default_path
    
    def _get_config_search_paths(self) -> List[tuple]:
        """获取配置文件搜索路径列表（按优先级排序）"""
        paths = []
        
        # 1. 环境变量 XAGENT_CONFIG_PATH
        env_path = os.environ.get('XAGENT_CONFIG_PATH')
        if env_path:
            paths.append(("Environment variable XAGENT_CONFIG_PATH", env_path))
        
        # 2. 命令行参数 --config
        cli_path = self._get_cli_config_path()
        if cli_path:
            paths.append(("Command line argument --config", cli_path))
        
        # 3. 当前工作目录
        paths.append(("Current directory config/config.yaml", Path.cwd() / 'config' / 'config.yaml'))
        paths.append(("Current directory config.yaml", Path.cwd() / 'config.yaml'))
        
        # 4. 用户配置目录（使用路径管理器）
        paths.append(("User config directory", self.paths.config_file))
        
        # 5. 系统配置目录（使用路径管理器）
        if self.paths.site_config_file:
            paths.append(("System config directory", self.paths.site_config_file))
        
        # 注意：不再将打包的默认配置添加到搜索路径
        # 打包的默认配置将在 _find_config_path() 中作为 fallback 使用
        
        return paths
    
    def _get_cli_config_path(self) -> Optional[str]:
        """从命令行参数获取配置路径"""
        for i, arg in enumerate(sys.argv):
            if arg == '--config' and i + 1 < len(sys.argv):
                return sys.argv[i + 1]
            elif arg.startswith('--config='):
                return arg.split('=', 1)[1]
        return None
    
    def _create_default_config(self, config_path: Path):
        """创建默认配置文件"""
        default_config_content = """# XAgent Gateway Configuration
# 此文件由系统自动生成，请根据实际环境修改

server:
  host: "0.0.0.0"
  port: 8080
  debug: false

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "${log_dir}/xagent.log"
  max_bytes: 10485760
  backup_count: 5
  console: true
  date_format: "%Y-%m-%d %H:%M:%S"
  color: true

storage:
  type: "sqlite"
  database: "${data_dir}/xagent.db"
  wal_mode: true
  batch_size: 100
  flush_interval: 5
  retention_days: 1
  cleanup_interval: 300
  cleanup_batch_size: 10000

plugins:
  failure_strategy: continue
  allow_partial_startup: true
  
  south: []
  north: []
  filter: []

scheduler:
  max_workers: 10
  task_timeout: 30

metrics:
  enabled: true
  port: 9090
"""
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(default_config_content)
            logger.info(f"Default config file created: {config_path}")
        except PermissionError:
            logger.error(f"No permission to create default config file: {config_path}")
            raise
        except Exception as e:
            logger.error(f"Error creating default config file: {e}")
            raise

    def _substitute_env_vars(self, content: str) -> str:
        """替换环境变量"""
        pattern = re.compile(r'\$\{([^}]+)\}')
        
        def replace(match):
            env_var = match.group(1)
            default_value = None
            if ':' in env_var:
                env_var, default_value = env_var.split(':', 1)
            value = os.environ.get(env_var, default_value)
            if value is None:
                # 如果是路径标记，先不替换，后面会处理
                if env_var in ['log_dir', 'data_dir', 'config_dir', 'cache_dir']:
                    return match.group(0)
                logger.warning(f"Environment variable {env_var} not found and no default provided")
                return match.group(0)
            return value
        
        return pattern.sub(replace, content)

    def _substitute_paths(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """替换路径标记"""
        if 'storage' in config_dict and 'database' in config_dict['storage']:
            config_dict['storage']['database'] = str(
                self.paths.resolve_path(config_dict['storage']['database'])
            )
        
        if 'logging' in config_dict and 'file' in config_dict['logging']:
            config_dict['logging']['file'] = str(
                self.paths.resolve_path(config_dict['logging']['file'])
            )
        
        return config_dict

    def load(self) -> GatewayConfig:
        # 如果配置已经加载且文件未修改，直接返回缓存的配置
        if self._config is not None:
            if self.config_path.exists():
                current_mtime = self.config_path.stat().st_mtime
                if current_mtime <= self._last_modified:
                    # 配置未修改，直接返回缓存
                    return self._config
            else:
                # 配置文件已修改，需要重新加载
                logger.info("Configuration file changed, reloading...")
        
        if not self.config_path.exists():
            logger.warning(f"Config file {self.config_path} not found, creating default config")
            self._create_default_config(self.config_path)
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = self._substitute_env_vars(content)
        config_dict = yaml.safe_load(content)
        
        # 替换路径标记
        config_dict = self._substitute_paths(config_dict)
        
        self._config = GatewayConfig(**config_dict)
        self._last_modified = self.config_path.stat().st_mtime
        
        logger.info(f"Configuration loaded from {self.config_path}")
        return self._config

    def reload(self) -> bool:
        if not self.config_path.exists():
            return False
        
        current_mtime = self.config_path.stat().st_mtime
        if current_mtime <= self._last_modified:
            return False
        
        logger.info("Configuration file changed, reloading...")
        old_config = self._config
        self.load()
        
        for callback in self._reload_callbacks:
            try:
                callback(old_config, self._config)
            except Exception as e:
                logger.error(f"Error in config reload callback: {e}")
        
        if self._event_bus:
            try:
                import asyncio
                from .event_bus import Event, EventType
                event = Event(
                    event_type=EventType.CONFIG_RELOADED,
                    data={
                        "old_config": model_to_dict(old_config) if old_config else None,
                        "new_config": model_to_dict(self._config) if self._config else None
                    }
                )
                asyncio.create_task(self._event_bus.publish(event))
            except Exception as e:
                logger.error(f"Error publishing CONFIG_RELOADED event: {e}")
        
        return True

    @property
    def config(self) -> GatewayConfig:
        if self._config is None:
            self.load()
        assert self._config is not None
        return self._config

    def register_reload_callback(self, callback: Callable):
        self._reload_callbacks.append(callback)

    def get_plugin_config(self, plugin_type: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        plugin_list = getattr(self.config.plugins, plugin_type, [])
        for plugin in plugin_list:
            if plugin.name == plugin_name:
                return plugin.config
        return None

    def is_plugin_enabled(self, plugin_type: str, plugin_name: str) -> bool:
        plugin_list = getattr(self.config.plugins, plugin_type, [])
        for plugin in plugin_list:
            if plugin.name == plugin_name:
                return plugin.enabled
        return False
