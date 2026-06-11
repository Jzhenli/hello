from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import re


class NorthChannelStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


class NorthChannelProtocol(str, Enum):
    MQTT = "mqtt"
    XNC = "xnc"
    HTTP = "http"
    CUSTOM = "custom"


class NorthChannelConnection(BaseModel):
    """连接配置 - 扁平结构，根据protocol字段确定具体字段"""
    
    # MQTT字段
    broker: Optional[str] = Field(None, description="MQTT Broker地址")
    client_id: Optional[str] = Field(None, description="MQTT客户端ID")
    topic: Optional[str] = Field(None, description="发布主题")
    command_topic: Optional[str] = Field(None, description="命令订阅主题")
    publish_mode: Optional[str] = Field(None, description="发布模式 single/batch")
    command_timeout: Optional[float] = Field(None, description="命令超时时间(秒)")
    qos: Optional[int] = Field(None, ge=0, le=2, description="QoS级别")
    keepalive: Optional[int] = Field(None, description="保活时间(秒)")
    clean_session: Optional[bool] = Field(None, description="清除会话")
    will_topic: Optional[str] = Field(None, description="遗嘱主题")
    will_message: Optional[str] = Field(None, description="遗嘱消息")
    will_qos: Optional[int] = Field(None, ge=0, le=2, description="遗嘱QoS")
    will_retain: Optional[bool] = Field(None, description="遗嘱保留")
    
    # XNC字段
    local_port: Optional[int] = Field(None, description="本地监听端口")
    remote_host: Optional[str] = Field(None, description="远程主机地址")
    remote_port: Optional[int] = Field(None, description="远程端口")
    reconnect_interval: Optional[int] = Field(None, description="重连间隔(秒)")
    
    # HTTP字段
    endpoint: Optional[str] = Field(None, description="HTTP端点URL")
    method: Optional[str] = Field(None, description="HTTP方法")
    headers: Optional[Dict[str, str]] = Field(None, description="请求头")
    timeout: Optional[int] = Field(None, description="超时时间(秒)")
    
    # 通用字段
    port: Optional[int] = Field(None, description="端口号")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")


class NorthChannelAdapter(BaseModel):
    """适配器配置"""
    type: str = Field(default="default", description="适配器类型")
    adapter: Optional[str] = Field(None, description="适配器名称(如 standard/C001)")

    # XNC适配器配置
    mapping_config: Optional[Dict[str, Any]] = Field(None, description="设备映射配置")

    # HTTP适配器配置
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP请求头")

    # 其他适配器配置
    config: Optional[Dict[str, Any]] = Field(None, description="其他适配器配置")


class NorthChannelUploadStrategy(BaseModel):
    immediate_upload: bool = Field(default=True, description="立即上传")
    batch_size: int = Field(default=100, description="批量大小")
    interval: int = Field(default=5, description="上传间隔(秒)")
    retry_times: int = Field(default=3, description="重试次数")
    retry_interval: Optional[int] = Field(default=5, description="重试间隔(秒)")


class NorthChannelStatistics(BaseModel):
    upload_rate: float = Field(default=0.0, description="上传速率(条/分)")
    success_rate: float = Field(default=0.0, description="成功率(%)")
    backlog_count: int = Field(default=0, description="积压数量")
    last_upload_time: Optional[str] = Field(None, description="最后上传时间")
    total_uploaded: int = Field(default=0, description="总上传数")
    total_failed: int = Field(default=0, description="总失败数")
    connection_uptime: float = Field(default=0.0, description="连接运行时间(秒)")


class NorthChannelConfig(BaseModel):
    id: str = Field(..., description="通道ID")
    name: str = Field(..., description="通道名称")
    description: Optional[str] = Field(None, description="通道描述")
    enabled: bool = Field(default=True, description="是否启用")
    protocol: NorthChannelProtocol = Field(..., description="协议类型")
    status: NorthChannelStatus = Field(
        default=NorthChannelStatus.OFFLINE,
        description="通道状态"
    )
    
    connection: NorthChannelConnection = Field(..., description="连接配置")
    adapter: NorthChannelAdapter = Field(
        default_factory=NorthChannelAdapter,
        description="数据适配器"
    )
    upload_strategy: NorthChannelUploadStrategy = Field(
        default_factory=NorthChannelUploadStrategy,
        description="上传策略"
    )
    
    statistics: Optional[NorthChannelStatistics] = Field(None, description="统计信息")
    
    tags: List[str] = Field(default_factory=list, description="标签列表")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Channel ID cannot be empty')
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Channel ID can only contain letters, numbers, underscores, and hyphens')
        return v.strip()
    
    model_config = ConfigDict(extra="allow")


class NorthChannelCreateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    channel_id: str = Field(..., description="通道ID")
    requires_restart: bool = Field(default=False, description="是否需要重启")


class NorthChannelUpdateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    channel_id: str = Field(..., description="通道ID")
    updated_fields: List[str] = Field(default_factory=list, description="更新的字段")


class NorthChannelListResponse(BaseModel):
    count: int = Field(..., description="通道总数")
    channels: List[NorthChannelConfig] = Field(..., description="通道列表")


class ConnectionTestRequest(BaseModel):
    channel_id: Optional[str] = Field(None, description="通道ID")
    connection: NorthChannelConnection = Field(..., description="连接配置")
    protocol: NorthChannelProtocol = Field(..., description="协议类型")


class ConnectionTestResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    latency: Optional[float] = Field(None, description="延迟(毫秒)")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")
