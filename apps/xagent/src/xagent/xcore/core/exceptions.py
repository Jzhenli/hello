"""XAgent统一异常体系

提供清晰的异常层次结构，便于错误处理和调试。
"""


class XAgentError(Exception):
    """XAgent基础异常类
    
    所有XAgent自定义异常的基类。
    """
    
    def __init__(self, message: str = "An error occurred in XAgent"):
        self.message = message
        super().__init__(self.message)


class ConfigurationError(XAgentError):
    """配置相关异常
    
    当配置文件格式错误、配置项缺失或配置值无效时抛出。
    """
    
    def __init__(self, message: str = "Configuration error", config_key: str = None):
        self.config_key = config_key
        if config_key:
            message = f"{message} (key: {config_key})"
        super().__init__(message)


class PluginError(XAgentError):
    """插件相关异常基类
    
    所有插件异常的基类。
    """
    
    def __init__(self, message: str = "Plugin error", plugin_name: str = None):
        self.plugin_name = plugin_name
        if plugin_name:
            message = f"{message} (plugin: {plugin_name})"
        super().__init__(message)


class PluginLoadError(PluginError):
    """插件加载失败异常
    
    当插件无法被加载时抛出，例如：
    - 插件文件不存在
    - 插件类未找到
    - 插件依赖缺失
    """
    
    def __init__(self, plugin_name: str, reason: str):
        message = f"Failed to load plugin '{plugin_name}': {reason}"
        super().__init__(message, plugin_name)
        self.reason = reason


class PluginStartError(PluginError):
    """插件启动失败异常
    
    当插件启动过程中发生错误时抛出，例如：
    - 连接设备失败
    - 初始化资源失败
    - 配置验证失败
    """
    
    def __init__(self, plugin_name: str, reason: str):
        message = f"Failed to start plugin '{plugin_name}': {reason}"
        super().__init__(message, plugin_name)
        self.reason = reason


class PluginStopError(PluginError):
    """插件停止失败异常
    
    当插件停止过程中发生错误时抛出。
    """
    
    def __init__(self, plugin_name: str, reason: str):
        message = f"Failed to stop plugin '{plugin_name}': {reason}"
        super().__init__(message, plugin_name)
        self.reason = reason


class PluginDependencyError(PluginError):
    """插件依赖错误异常
    
    当插件依赖未满足时抛出，例如：
    - 依赖的插件未启动
    - 依赖的服务不可用
    """
    
    def __init__(self, plugin_name: str, dependency: str, reason: str = None):
        message = f"Plugin '{plugin_name}' dependency error: '{dependency}' not satisfied"
        if reason:
            message = f"{message} - {reason}"
        super().__init__(message, plugin_name)
        self.dependency = dependency
        self.reason = reason


class StorageError(XAgentError):
    """存储相关异常
    
    当存储操作失败时抛出，例如：
    - 数据库连接失败
    - 写入失败
    - 查询失败
    """
    
    def __init__(self, message: str = "Storage error", operation: str = None):
        self.operation = operation
        if operation:
            message = f"{message} (operation: {operation})"
        super().__init__(message)


class ValidationError(XAgentError):
    """验证错误异常
    
    当数据验证失败时抛出，例如：
    - 数据格式错误
    - 数据范围超出限制
    - 必填字段缺失
    """
    
    def __init__(self, message: str = "Validation error", field: str = None, value: any = None):
        self.field = field
        self.value = value
        if field:
            message = f"{message} (field: {field}, value: {value})"
        super().__init__(message)


class InitializationError(XAgentError):
    """初始化错误异常
    
    当组件初始化失败时抛出。
    """
    
    def __init__(self, component: str, reason: str):
        message = f"Failed to initialize '{component}': {reason}"
        super().__init__(message)
        self.component = component
        self.reason = reason


class ServiceError(XAgentError):
    """服务相关异常
    
    当服务操作失败时抛出。
    """
    
    def __init__(self, service_name: str, operation: str, reason: str):
        message = f"Service '{service_name}' failed during '{operation}': {reason}"
        super().__init__(message)
        self.service_name = service_name
        self.operation = operation
        self.reason = reason
