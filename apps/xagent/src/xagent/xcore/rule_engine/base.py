"""Rule Engine Base Models and Interfaces

定义插件化规则引擎的核心数据模型和接口。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from xagent.xcore.domain.models.reading import Reading


@dataclass
class PluginDependency:
    """插件依赖
    
    描述插件之间的依赖关系。
    
    Attributes:
        plugin_name: 依赖的插件名称
        version_constraint: 版本约束，如 ">=1.0,<2.0"
        optional: 是否可选依赖
    """
    
    plugin_name: str
    version_constraint: str = "*"
    optional: bool = False


@dataclass
class PluginMetadata:
    """插件元数据
    
    所有插件必须提供元数据，用于描述插件能力。
    与 core.plugin.types.PluginInfo（运行时状态）不同，
    PluginMetadata 侧重于插件的静态描述信息。
    
    Attributes:
        name: 插件名称（唯一标识）
        version: 版本号
        description: 描述
        author: 作者
        plugin_type: 插件类型: rule/delivery/filter
        min_core_version: 最低核心版本要求
        config_version: 配置格式版本
        deprecated: 是否已废弃
        successor: 后继插件名称（废弃时使用）
        dependencies: 依赖列表
        icon: 节点图标
        color: 节点颜色
        category: 节点分类
        display_name: 显示名称
        node_type: Vue Flow 节点类型
        input_types: 接受的输入类型
        output_types: 输出类型
        preview_template: 节点预览模板
        config_schema: 配置 Schema
        default_config: 默认配置
    """
    
    name: str
    version: str
    description: str
    author: str = ""
    plugin_type: str = ""
    
    min_core_version: str = "1.0.0"
    config_version: str = "1.0"
    deprecated: bool = False
    successor: str = ""
    
    dependencies: List[PluginDependency] = field(default_factory=list)
    
    icon: str = "⚙️"
    color: str = "#6366f1"
    category: str = "general"
    display_name: str = ""
    node_type: str = ""
    
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    
    preview_template: str = ""
    
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginRegistration:
    """插件注册信息
    
    存储插件注册时的完整信息。
    
    Attributes:
        plugin_class: 插件类
        info: 插件元数据
        config_schema: 配置 Schema
    """
    
    plugin_class: type
    info: PluginMetadata
    config_schema: Dict[str, Any] = field(default_factory=dict)


class RuleResult(Enum):
    """规则评估结果"""
    
    NOT_TRIGGERED = "not_triggered"
    TRIGGERED = "triggered"
    ERROR = "error"


@dataclass
class AggregationResult:
    """聚合结果
    
    存储数据窗口聚合计算的结果。
    
    Attributes:
        subscription_id: 订阅ID
        asset: 设备ID
        point_name: 点位名称
        value: 聚合后的值
        aggregation_type: 聚合类型
        window_start: 窗口开始时间
        window_end: 窗口结束时间
        data_points: 数据点数
        min_value: 最小值
        max_value: 最大值
        avg_value: 平均值
        sum_value: 求和
        first_value: 第一个值
        last_value: 最后一个值
        stddev_value: 标准差
        quality: 数据质量
        quality_ratio: good 数据占比
    """
    
    subscription_id: str
    asset: str
    point_name: str
    
    value: Any = None
    aggregation_type: 'AggregationType' = None
    
    window_start: float = 0
    window_end: float = 0
    data_points: int = 0
    
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    sum_value: Optional[float] = None
    first_value: Optional[float] = None
    last_value: Optional[float] = None
    stddev_value: Optional[float] = None
    
    quality: str = "good"
    quality_ratio: float = 1.0


@dataclass
class RuleContext:
    """规则评估上下文
    
    包含规则评估所需的所有数据。
    
    Attributes:
        rule_id: 规则ID
        rule_name: 规则名称
        asset: 设备ID
        point_name: 点位名称
        current_value: 当前值
        timestamp: 时间戳
        history_values: 历史值列表
        history_timestamps: 历史时间戳列表
        window_min: 窗口最小值
        window_max: 窗口最大值
        window_avg: 窗口平均值
        window_count: 窗口数据点数
        aggregation_data: 多点位聚合数据
        device_status: 设备状态
        metadata: 其他元数据
    """
    
    rule_id: str
    rule_name: str
    
    asset: str = ""
    point_name: str = ""
    current_value: Any = None
    timestamp: float = 0
    
    history_values: Optional[List[Any]] = None
    history_timestamps: Optional[List[float]] = None
    
    window_min: Optional[float] = None
    window_max: Optional[float] = None
    window_avg: Optional[float] = None
    window_count: int = 0
    
    aggregation_data: Optional[Dict[str, AggregationResult]] = None
    
    device_status: str = "online"
    
    metadata: Optional[Dict[str, Any]] = None
    
    def get_aggregation(self, asset: str, point_name: str) -> Optional[AggregationResult]:
        """获取指定点位的聚合结果
        
        Args:
            asset: 设备ID
            point_name: 点位名称
        
        Returns:
            聚合结果，不存在返回 None
        """
        if not self.aggregation_data:
            return None
        key = f"{asset}:{point_name}"
        return self.aggregation_data.get(key)
    
    def get_window_value(
        self, 
        asset: str, 
        point_name: str, 
        agg_type: str = "avg"
    ) -> Optional[float]:
        """获取指定点位的窗口聚合值
        
        Args:
            asset: 设备ID
            point_name: 点位名称
            agg_type: 聚合类型 (min/max/avg/sum/count/first/last)
        
        Returns:
            聚合值
        """
        agg_result = self.get_aggregation(asset, point_name)
        if not agg_result:
            return None
        
        attr_map = {
            "min": "min_value",
            "max": "max_value",
            "avg": "avg_value",
            "sum": "sum_value",
            "count": "data_points",
            "first": "first_value",
            "last": "last_value"
        }
        
        attr = attr_map.get(agg_type, "avg_value")
        return getattr(agg_result, attr, None)


@dataclass
class RuleEvaluationResult:
    """规则评估结果
    
    Attributes:
        result: 评估结果枚举
        triggered: 是否触发
        reason: 触发原因
        details: 详细信息
        error: 错误信息
    """
    
    result: RuleResult
    triggered: bool = False
    reason: str = ""
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DeliveryStatus(Enum):
    """交付状态"""
    
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    PENDING = "pending"


@dataclass
class Notification:
    """通知对象
    
    Attributes:
        notification_id: 通知ID
        rule_id: 规则ID
        rule_name: 规则名称
        title: 标题
        message: 消息内容
        level: 级别: critical/warning/info/debug
        asset: 设备ID
        point_name: 点位名称
        current_value: 当前值
        threshold: 阈值
        triggered_at: 触发时间
        recovered_at: 恢复时间
        recipients: 收件人列表
        metadata: 其他元数据
    """
    
    notification_id: str
    rule_id: str
    rule_name: str
    
    title: str
    message: str
    level: str = "info"
    
    asset: str = ""
    point_name: str = ""
    current_value: Any = None
    threshold: Any = None
    
    triggered_at: float = 0
    recovered_at: Optional[float] = None
    
    recipients: Optional[List[str]] = None
    
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DeliveryResult:
    """交付结果
    
    Attributes:
        status: 交付状态
        success: 是否成功
        message: 结果消息
        error: 错误信息
        retry_count: 重试次数
        delivered_at: 交付时间
    """
    
    status: DeliveryStatus
    success: bool = False
    message: str = ""
    error: Optional[str] = None
    retry_count: int = 0
    delivered_at: float = 0


@dataclass
class ReadingSet:
    """数据集
    
    用于过滤器管道的数据结构。
    与 storage.Reading 互转：
    - ReadingSet.asset ↔ Reading.asset
    - ReadingSet.points ↔ Reading.data
    - ReadingSet.quality ↔ Reading.standard_points 中的 quality
    - ReadingSet.metadata ↔ Reading.service_name/tags/device_status
    
    Attributes:
        asset: 设备ID
        timestamp: 时间戳
        points: 点位数据 {point_name: value}
        quality: 质量信息 {point_name: quality}
        metadata: 元数据
    """
    
    asset: str
    timestamp: float
    points: Dict[str, Any]
    quality: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_reading(self) -> "Reading":
        from xagent.xcore.domain.models.reading import Reading
        
        standard_points = []
        if self.quality:
            for point_name, quality in self.quality.items():
                standard_points.append({
                    "point_name": point_name,
                    "quality": quality,
                    "value": self.points.get(point_name),
                })
        
        metadata = self.metadata or {}
        return Reading(
            asset=self.asset,
            timestamp=self.timestamp,
            service_name=metadata.get("service_name", ""),
            data=dict(self.points),
            tags=metadata.get("tags", []),
            standard_points=standard_points,
            device_status=metadata.get("device_status"),
        )
    
    @classmethod
    def from_reading(cls, reading: "Reading") -> "ReadingSet":
        """从存储层 Reading 创建 ReadingSet
        
        Args:
            reading: 存储层 Reading 实例
            
        Returns:
            ReadingSet 实例
        """
        quality = None
        if reading.standard_points:
            quality = {}
            for sp in reading.standard_points:
                point_name = sp.get("point_name", "")
                if point_name:
                    quality[point_name] = sp.get("quality", "good")
        
        return cls(
            asset=reading.asset,
            timestamp=reading.timestamp,
            points=dict(reading.data),
            quality=quality,
            metadata={
                "service_name": reading.service_name,
                "tags": reading.tags,
                "device_status": reading.device_status,
            }
        )
    
    def to_standard_points(self) -> list:
        """转换为 StandardDataPoint 列表
        
        Returns:
            StandardDataPoint 实例列表
        """
        from xagent.xcore.transform.standard_point import StandardDataPoint
        
        result = []
        for point_name, value in self.points.items():
            quality = "good"
            if self.quality and point_name in self.quality:
                quality = self.quality[point_name]
            
            result.append(StandardDataPoint(
                device_id=self.asset,
                point_name=point_name,
                value=value,
                data_type=_infer_data_type(value),
                timestamp=self.timestamp,
                quality=quality,
                metadata=self.metadata or {},
            ))
        return result
    
    @classmethod
    def from_standard_points(
        cls,
        points: list,
        asset: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> "ReadingSet":
        """从 StandardDataPoint 列表创建 ReadingSet
        
        Args:
            points: StandardDataPoint 实例列表
            asset: 覆盖设备ID（默认取第一个点的 device_id）
            timestamp: 覆盖时间戳（默认取第一个点的 timestamp）
            
        Returns:
            ReadingSet 实例
        """
        if not points:
            return cls(asset=asset or "", timestamp=timestamp or 0, points={})
        
        first = points[0]
        result_asset = asset or first.device_id
        result_timestamp = timestamp or first.timestamp
        
        data = {}
        quality = {}
        for p in points:
            data[p.point_name] = p.value
            quality[p.point_name] = p.quality
        
        return cls(
            asset=result_asset,
            timestamp=result_timestamp,
            points=data,
            quality=quality,
        )


def _infer_data_type(value: Any) -> str:
    """推断数据类型"""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


class AggregationType(Enum):
    """聚合类型"""
    
    NONE = "none"
    MIN = "min"
    MAX = "max"
    AVG = "avg"
    SUM = "sum"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"
    DELTA = "delta"
    STDDEV = "stddev"


class SubscriptionMode(Enum):
    """订阅模式"""
    
    SINGLE = "single"
    WINDOW = "window"


@dataclass
class AggregationSubscription:
    """聚合订阅配置
    
    Attributes:
        subscription_id: 订阅ID
        rule_id: 关联的规则ID
        asset: 设备ID
        point_name: 点位名称
        mode: 订阅模式
        window_size: 窗口大小（秒）
        window_type: 窗口类型: sliding/tumbling
        aggregation_type: 聚合类型
        min_data_points: 最少数据点数
        max_data_points: 最大数据点数
        data_quality_filter: 数据质量过滤: good/all
    """
    
    subscription_id: str
    rule_id: str
    
    asset: str
    point_name: str
    
    mode: SubscriptionMode = SubscriptionMode.SINGLE
    
    window_size: int = 300
    window_type: str = "sliding"
    
    aggregation_type: AggregationType = AggregationType.NONE
    
    min_data_points: int = 1
    max_data_points: int = 10000
    data_quality_filter: str = "good"
