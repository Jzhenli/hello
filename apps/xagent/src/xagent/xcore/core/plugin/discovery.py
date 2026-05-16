"""插件发现模块

负责动态发现和加载插件类。
"""

import importlib
import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..paths import get_plugins_dir

logger = logging.getLogger(__name__)


class PluginDiscovery:
    """插件发现器
    
    负责在文件系统中发现和加载插件类。
    """
    
    def __init__(
        self,
        plugin_dirs: Optional[List[str]] = None,
        module_prefix: str = "xagent.plugins."
    ):
        """初始化插件发现器
        
        Args:
            plugin_dirs: 插件目录列表，如果为None则使用默认目录
            module_prefix: 模块名前缀，用于动态加载时的模块命名
        """
        self.module_prefix = module_prefix
        self.plugin_dirs = plugin_dirs if plugin_dirs is not None else [
            self._get_default_plugin_dir()
        ]
    
    def _get_default_plugin_dir(self) -> str:
        """获取默认插件目录路径
        
        Returns:
            默认插件目录的绝对路径
        """
        plugins_dir = get_plugins_dir()
        logger.info(f"Plugin directory: {plugins_dir}")
        
        if plugins_dir.exists() and plugins_dir.is_dir():
            return str(plugins_dir)
        
        logger.warning(f"Plugin directory not found: {plugins_dir}")
        return str(plugins_dir)
    
    def discover_plugins(self) -> Dict[str, Type]:
        """发现所有插件类
        
        扫描插件目录，发现并加载所有可用的插件类。
        
        Returns:
            插件类字典，key为"plugin_type:plugin_name"，value为插件类
        """
        discovered = {}
        
        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            
            try:
                if plugin_path.exists() and plugin_path.is_dir():
                    self._scan_directory(plugin_path, discovered)
                else:
                    logger.info(f"Plugin path may be in compressed format, trying import-based discovery: {plugin_path}")
                    self._discover_via_import(discovered)
            except Exception as e:
                logger.warning(f"Error scanning plugin directory {plugin_path}: {e}")
                logger.info("Falling back to import-based discovery")
                try:
                    self._discover_via_import(discovered)
                except Exception as e2:
                    logger.error(f"Import-based discovery also failed: {e2}")
        
        logger.info(f"Discovered {len(discovered)} plugin classes")
        return discovered
    
    def _scan_directory(self, plugin_path: Path, discovered: Dict[str, Type]) -> None:
        """扫描目录寻找插件

        仅扫描名为 plugin.py 的文件作为插件入口，避免加载辅助模块。
        辅助模块（constants、converter、adapter 等）会在 plugin.py 被
        exec_module 时作为依赖自动加载，无需单独扫描。

        Args:
            plugin_path: 要扫描的插件目录
            discovered: 已发现的插件字典
        """
        for item in plugin_path.rglob("plugin.py"):
            self._load_module_from_file(item, plugin_path, discovered)

        for item in plugin_path.rglob("*.pyd"):
            self._load_module_from_file(item, plugin_path, discovered)

        for item in plugin_path.rglob("*.so"):
            self._load_module_from_file(item, plugin_path, discovered)
    
    def _load_module_from_file(
        self, 
        py_file: Path, 
        plugin_path: Path, 
        discovered: Dict[str, Type]
    ) -> None:
        """从文件加载模块
        
        Args:
            py_file: Python文件路径
            plugin_path: 插件根目录
            discovered: 已发现的插件字典
        """
        relative_path = py_file.relative_to(plugin_path)
        module_path = str(relative_path.with_suffix('')).replace('\\', '.').replace('/', '.')
        
        if py_file.suffix in (".pyd", ".so"):
            module_path = re.sub(
                r'\.(?:cpython|cp|pypy|cython)-\d+[a-z]*-[\w-]+$',
                '',
                module_path,
                flags=re.IGNORECASE
            )
        
        module_name = f"{self.module_prefix}{module_path}"
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                logger.warning(f"Failed to create spec for {py_file}")
                return
            
            self._discover_classes_in_module(module, module_name, discovered, set())
                    
        except Exception as e:
            logger.error(f"Error loading plugin {py_file}: {e}", exc_info=True)
    
    def _discover_classes_in_module(
        self, 
        module: Any, 
        module_name: str, 
        discovered: Dict[str, Type],
        visited: set
    ) -> None:
        """递归发现模块中的插件类
        
        Args:
            module: 要扫描的模块
            module_name: 模块名称
            discovered: 已发现的插件字典
            visited: 已访问的模块集合
        """
        if module_name in visited:
            return
        visited.add(module_name)
        
        if hasattr(module, '__all__'):
            names_to_check = module.__all__
        else:
            names_to_check = dir(module)
        
        for name in names_to_check:
            try:
                obj = getattr(module, name)
                
                if inspect.isclass(obj):
                    self._try_register_plugin_class(obj, module_name, discovered)
                elif inspect.ismodule(obj) and hasattr(obj, '__name__'):
                    if obj.__name__.startswith(module_name + '.'):
                        self._discover_classes_in_module(obj, obj.__name__, discovered, visited)
            except Exception:
                logger.debug(f"Error inspecting attribute {name} in module {module_name}", exc_info=True)
                continue
    
    def _try_register_plugin_class(
        self, 
        obj: Any, 
        module_name: str, 
        discovered: Dict[str, Type]
    ) -> None:
        """尝试注册插件类
        
        Args:
            obj: 要检查的对象
            module_name: 模块名称
            discovered: 已发现的插件字典
        """
        if not hasattr(obj, '__plugin_type__'):
            return
        
        obj_module = obj.__module__
        
        if obj_module != module_name and not obj_module.startswith(module_name + '.'):
            return
        
        if inspect.isabstract(obj):
            return
        
        plugin_type = obj.__plugin_type__
        plugin_name = getattr(obj, '__plugin_name__', None) or obj.__name__.lower()
        key = f"{plugin_type}:{plugin_name}"
        
        if key in discovered:
            return
        
        discovered[key] = obj
        logger.debug(f"Discovered plugin class: {key}")
    
    def _discover_via_import(self, discovered: Dict[str, Type]) -> None:
        """通过导入机制发现插件（用于压缩包环境）
        
        Args:
            discovered: 已发现的插件字典
        """
        import pkgutil
        import xagent.plugins
        
        logger.info("Starting import-based plugin discovery")
        
        for importer, modname, ispkg in pkgutil.walk_packages(
            path=xagent.plugins.__path__,
            prefix='xagent.plugins.',
            onerror=lambda name: logger.warning(f"Error importing {name}")
        ):
            try:
                module = importlib.import_module(modname)
                logger.debug(f"Imported module: {modname}")
                
                for name in dir(module):
                    try:
                        obj = getattr(module, name)
                        if inspect.isclass(obj) and hasattr(obj, '__plugin_type__'):
                            self._try_register_plugin_class(obj, modname, discovered)
                    except Exception:
                        logger.debug(f"Error inspecting class {name} in module {modname}", exc_info=True)
                        continue
            except Exception as e:
                logger.warning(f"Failed to import module {modname}: {e}")
                continue
        
        logger.info(f"Import-based discovery completed, found {len(discovered)} plugins")
