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
        current_file = Path(__file__)
        
        logger.info(f"Current discovery.py location: {current_file}")
        
        self._ensure_submodules_registered()
        
        try:
            import xagent.plugins
            plugins_package_path = Path(xagent.plugins.__file__).parent
            logger.info(f"Found plugins package via import: {plugins_package_path}")
            return str(plugins_package_path)
        except Exception as e:
            logger.warning(f"Could not import xagent.plugins: {e}")
        
        possible_paths = [
            current_file.parent.parent.parent.parent / "plugins",
            current_file.parent.parent.parent.parent.parent / "plugins",
            current_file.parent.parent.parent / "plugins",
        ]
        
        logger.info(f"Searching for plugin directories...")
        
        for path in possible_paths:
            try:
                logger.info(f"  Checking: {path}")
                if path.exists() and path.is_dir():
                    logger.info(f"Found plugin directory: {path}")
                    return str(path)
            except PermissionError:
                logger.warning(f"No permission to access: {path}")
                continue
            except Exception as e:
                logger.warning(f"Error checking path {path}: {e}")
                continue
        
        default_path = possible_paths[0]
        logger.warning(f"Plugin directory not found, using default: {default_path}")
        return str(default_path)
    
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
    
    def _ensure_submodules_registered(self) -> bool:
        """确保编译环境下的子模块被注册到 sys.modules
        
        当使用 Nuitka --include-package 编译时，子模块被编译进 .pyd
        但不会自动注册到 sys.modules，导致 import 失败。
        此方法通过遍历已加载模块的属性来注册子模块。
        
        Returns:
            是否成功注册了 plugins 子模块
        """
        if "xagent.plugins" in sys.modules:
            return True
        
        if "xagent" not in sys.modules:
            try:
                import xagent
            except ImportError:
                return False
        
        xagent_module = sys.modules.get("xagent")
        if xagent_module is None:
            return False
        
        def register_submodules(parent_module, parent_name):
            for attr_name in dir(parent_module):
                if attr_name.startswith('_'):
                    continue
                try:
                    attr = getattr(parent_module, attr_name)
                    if hasattr(attr, '__name__') and hasattr(attr, '__path__'):
                        full_name = f"{parent_name}.{attr_name}"
                        if full_name not in sys.modules:
                            sys.modules[full_name] = attr
                            logger.debug(f"Registered submodule: {full_name}")
                        register_submodules(attr, full_name)
                except Exception:
                    continue
        
        register_submodules(xagent_module, "xagent")
        
        return "xagent.plugins" in sys.modules

    def _discover_via_import(self, discovered: Dict[str, Type]) -> None:
        """通过导入机制发现插件（用于压缩包环境）
        
        Args:
            discovered: 已发现的插件字典
        """
        import pkgutil
        
        self._ensure_submodules_registered()
        
        try:
            import xagent.plugins
        except ImportError as e:
            logger.error(f"Failed to import xagent.plugins after registration: {e}")
            return
        
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
