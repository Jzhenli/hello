"""统一的路径管理器，使用 platformdirs 管理所有应用路径"""

import logging
import shutil
import warnings
from pathlib import Path
from typing import Optional, Dict
from platformdirs import PlatformDirs

logger = logging.getLogger(__name__)


class AppPaths:
    """应用路径管理器"""
    
    APP_NAME = "XAgent"
    APP_AUTHOR = "adveco"
    
    _instance: Optional['AppPaths'] = None
    
    def __init__(self, custom_base_dir: Optional[Path] = None):
        """
        初始化路径管理器
        
        Args:
            custom_base_dir: 自定义基础目录（用于开发或测试）
        """
        self.platform_dirs = PlatformDirs(self.APP_NAME, self.APP_AUTHOR)
        self.custom_base_dir = custom_base_dir
        self._ensure_directories()
    
    @classmethod
    def get_instance(cls) -> 'AppPaths':
        """获取单例实例
        
        [DEPRECATED] 优先通过 DI 容器管理实例。后续应统一使用
        Container.resolve() 获取实例。
        """
        warnings.warn(
            "AppPaths.get_instance() is deprecated. Use DI container instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def initialize(cls, custom_base_dir: Optional[Path] = None) -> 'AppPaths':
        """初始化路径管理器
        
        如果已经初始化，返回现有实例（忽略 custom_base_dir 参数）。
        """
        if cls._instance is None:
            cls._instance = cls(custom_base_dir)
        return cls._instance
    
    def _ensure_directories(self):
        """确保所有必要的目录都存在"""
        directories = [
            self.config_dir,
            self.data_dir,
            self.log_dir,
            self.cache_dir,
            self.plugin_config_dir,
            self.device_config_dir,
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensuring directory exists: {directory}")
            except PermissionError:
                logger.warning(f"No permission to create directory: {directory}")
            except Exception as e:
                logger.warning(f"Error creating directory {directory}: {e}")
        
        self._copy_default_configs()
    
    @property
    def app_dir(self) -> Path:
        """应用根目录"""
        if self.custom_base_dir:
            return self.custom_base_dir
        return self.platform_dirs.user_config_path
    
    @property
    def config_dir(self) -> Path:
        """配置文件目录"""
        return self.app_dir / "config"
    
    @property
    def config_file(self) -> Path:
        """主配置文件路径"""
        return self.config_dir / "config.yaml"
    
    @property
    def data_dir(self) -> Path:
        """数据文件目录"""
        return self.app_dir / "data"
    
    @property
    def database_file(self) -> Path:
        """数据库文件路径"""
        return self.data_dir / "xagent.db"
    
    @property
    def log_dir(self) -> Path:
        """日志文件目录"""
        return self.app_dir / "logs"
    
    @property
    def log_file(self) -> Path:
        """主日志文件路径"""
        return self.log_dir / "xagent.log"
    
    @property
    def cache_dir(self) -> Path:
        """缓存文件目录"""
        return self.app_dir / "cache"
    
    @property
    def plugin_config_dir(self) -> Path:
        """插件配置目录"""
        return self.config_dir / "plugins"
    
    @property
    def device_config_dir(self) -> Path:
        """设备配置目录"""
        return self.config_dir / "devices"
    
    @property
    def packaged_resources_dir(self) -> Path:
        """打包资源目录（包含默认配置模板）"""
        return Path(__file__).parent.parent.parent / "resources"
    
    @property
    def site_config_dir(self) -> Optional[Path]:
        """系统级配置目录"""
        site_dir = self.platform_dirs.site_config_path
        if site_dir:
            return site_dir
        return None
    
    @property
    def site_config_file(self) -> Optional[Path]:
        """系统级配置文件路径"""
        if self.site_config_dir:
            return self.site_config_dir / "config.yaml"
        return None
    
    def get_plugin_config_file(self, plugin_name: str) -> Path:
        """获取插件配置文件路径"""
        return self.plugin_config_dir / f"{plugin_name}.yaml"
    
    def get_data_file(self, filename: str) -> Path:
        """获取数据文件路径"""
        return self.data_dir / filename
    
    def get_log_file(self, filename: str) -> Path:
        """获取日志文件路径"""
        return self.log_dir / filename
    
    def get_cache_file(self, filename: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / filename
    
    def resolve_path(self, path: str) -> Path:
        """
        解析路径，支持相对路径和特殊标记
        
        支持的标记：
        - ${config_dir} -> 配置目录
        - ${data_dir} -> 数据目录
        - ${log_dir} -> 日志目录
        - ${cache_dir} -> 缓存目录
        
        Args:
            path: 原始路径字符串
            
        Returns:
            解析后的绝对路径
        """
        if not path:
            return Path(path)
        
        # 替换特殊标记
        path = path.replace("${config_dir}", str(self.config_dir))
        path = path.replace("${data_dir}", str(self.data_dir))
        path = path.replace("${log_dir}", str(self.log_dir))
        path = path.replace("${cache_dir}", str(self.cache_dir))
        
        result = Path(path)
        
        # 如果是相对路径，相对于当前工作目录
        if not result.is_absolute():
            result = Path.cwd() / result
        
        return result
    
    def _copy_default_configs(self) -> None:
        """复制默认配置模板到用户配置目录
        
        如果用户配置目录中不存在对应的配置文件，则从打包资源目录复制。
        """
        resources_dir = self.packaged_resources_dir
        
        if not resources_dir.exists():
            logger.debug(f"Packaged resources directory not found: {resources_dir}")
            return
        
        plugin_count = self._copy_directory_contents(
            resources_dir / "config" / "plugins",
            self.plugin_config_dir,
            "plugin"
        )
        
        device_count = self._copy_directory_contents(
            resources_dir / "config" / "devices",
            self.device_config_dir,
            "device"
        )
        
        total = plugin_count + device_count
        if total > 0:
            logger.info(f"Copied {total} default config templates ({plugin_count} plugins, {device_count} devices)")
    
    def _copy_directory_contents(
        self,
        source_dir: Path,
        target_dir: Path,
        config_type: str
    ) -> int:
        """复制目录内容
        
        Args:
            source_dir: 源目录
            target_dir: 目标目录
            config_type: 配置类型（用于日志）
            
        Returns:
            复制的文件数量
        """
        if not source_dir.exists():
            logger.debug(f"Source directory not found: {source_dir}")
            return 0
        
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
        
        copied_count = 0
        for source_file in source_dir.glob("*.yaml"):
            target_file = target_dir / source_file.name
            
            if target_file.exists():
                logger.debug(f"{config_type} config already exists, skipping: {target_file}")
                continue
            
            try:
                shutil.copy2(source_file, target_file)
                logger.debug(f"Copied default {config_type} config: {source_file.name}")
                copied_count += 1
            except PermissionError:
                logger.warning(f"No permission to copy {config_type} config: {source_file}")
            except Exception as e:
                logger.warning(f"Error copying {config_type} config {source_file}: {e}")
        
        return copied_count
    
    def get_all_paths_info(self) -> dict:
        """获取所有路径信息（用于调试和日志）"""
        return {
            "app_dir": str(self.app_dir),
            "config_dir": str(self.config_dir),
            "config_file": str(self.config_file),
            "data_dir": str(self.data_dir),
            "database_file": str(self.database_file),
            "log_dir": str(self.log_dir),
            "log_file": str(self.log_file),
            "cache_dir": str(self.cache_dir),
            "plugin_config_dir": str(self.plugin_config_dir),
            "device_config_dir": str(self.device_config_dir),
            "packaged_resources_dir": str(self.packaged_resources_dir),
            "site_config_dir": str(self.site_config_dir) if self.site_config_dir else None,
        }
    
    def __repr__(self) -> str:
        return f"AppPaths(config_dir={self.config_dir}, data_dir={self.data_dir}, log_dir={self.log_dir})"


def get_paths() -> AppPaths:
    """获取路径管理器实例（便捷函数）"""
    if AppPaths._instance is None:
        AppPaths._instance = AppPaths()
    return AppPaths._instance
