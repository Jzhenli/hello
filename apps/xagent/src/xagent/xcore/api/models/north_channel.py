from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
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


class MQTTConnectionConfig(BaseModel):
    client_id: str = Field(..., description="MQTT客户端ID")
    topic: str = Field(..., description="发布主题")
    qos: int = Field(default=1, ge=0, le=2, description="QoS级别")
    keepalive: int = Field(default=60, description="保活时间(秒)")
    clean_session: bool = Field(default=True, description="清除会话")
    will_topic: Optional[str] = Field(None, description="遗嘱主题")
    will_message: Optional[str] = Field(None, description="遗嘱消息")
    will_qos: Optional[int] = Field(None, ge=0, le=2, description="遗嘱QoS")
    will_retain: Optional[bool] = Field(None, description="遗嘱保留")


class XNCConnectionConfig(BaseModel):
    local_port: int = Field(default=8888, description="本地监听端口")
    protocol: str = Field(default="protobuf", description="协议模式: protobuf/json")
    remote_host: Optional[str] = Field(default="127.0.0.1", description="远程主机地址")
    remote_port: Optional[int] = Field(default=9000, description="远程端口")
    reconnect_interval: int = Field(default=5, description="重连间隔(秒)")
    mapping_config: Optional[Dict[str, Any]] = Field(None, description="设备映射配置")


class HTTPConnectionConfig(BaseModel):
    endpoint: str = Field(..., description="HTTP端点URL")
    method: str = Field(default="POST", description="HTTP方法")
    headers: Optional[Dict[str, str]] = Field(None, description="请求头")
    timeout: int = Field(default=30, description="超时时间(秒)")


class NorthChannelConnection(BaseModel):
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口号")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    mqtt: Optional[MQTTConnectionConfig] = Field(None, description="MQTT配置")
    xnc: Optional[XNCConnectionConfig] = Field(None, description="XNC配置")
    http: Optional[HTTPConnectionConfig] = Field(None, description="HTTP配置")


class NorthChannelAdapter(BaseModel):
    type: str = Field(default="default", description="适配器类型")
    config: Dict[str, Any] = Field(default_factory=dict, description="适配器配置")


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
