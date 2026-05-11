"""插件启动结果模型"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PluginStartupResult:
    """插件启动结果
    
    记录插件启动过程中的状态信息。
    
    Attributes:
        name: 插件名称
        plugin_type: 插件类型
        success: 是否成功
        error_message: 错误信息（如果失败）
        stage: 启动阶段（load/start）
        plugin_id: 插件实例ID（可选）
    """
    
    name: str
    plugin_type: str
    success: bool
    error_message: Optional[str] = None
    stage: str = "load"
    plugin_id: Optional[str] = None
    
    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return (
            f"PluginStartupResult({status} {self.name}/{self.plugin_type} "
            f"stage={self.stage})"
        )
