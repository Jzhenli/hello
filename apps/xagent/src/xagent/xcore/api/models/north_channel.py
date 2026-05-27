from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class NorthChannelStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    ACTIVE = "active"
    UNKNOWN = "unknown"


class NorthChannelCreate(BaseModel):
    name: str = Field(..., description="通道名称")
    plugin_name: str = Field(default="xnc_plus", description="插件名称（决定协议类型）")
    remote_host: Optional[str] = Field(None, description="远程主机地址")
    remote_port: Optional[int] = Field(None, description="远程端口")
    local_port: Optional[int] = Field(None, description="本地监听端口")
    config: Dict[str, Any] = Field(default_factory=dict, description="扩展配置（协议特有参数放入此字段）")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Channel name cannot be empty")
        return v.strip()

    model_config = ConfigDict(extra="allow")


class NorthChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, description="通道名称")
    plugin_name: Optional[str] = Field(None, description="插件名称")
    remote_host: Optional[str] = Field(None, description="远程主机地址")
    remote_port: Optional[int] = Field(None, description="远程端口")
    local_port: Optional[int] = Field(None, description="本地监听端口")
    config: Optional[Dict[str, Any]] = Field(None, description="扩展配置")
    enabled: Optional[bool] = Field(None, description="是否启用")

    model_config = ConfigDict(extra="allow")


class NorthChannelResponse(BaseModel):
    id: int = Field(..., description="通道ID")
    name: str = Field(..., description="通道名称")
    plugin_name: str = Field(..., description="插件名称")
    remote_host: Optional[str] = Field(None, description="远程主机地址")
    remote_port: Optional[int] = Field(None, description="远程端口")
    local_port: Optional[int] = Field(None, description="本地监听端口")
    config: Dict[str, Any] = Field(default_factory=dict, description="扩展配置")
    enabled: bool = Field(default=True, description="是否启用")
    status: str = Field(default="active", description="状态")
    created_at: Optional[float] = Field(None, description="创建时间")
    updated_at: Optional[float] = Field(None, description="更新时间")
    runtime: Optional[Dict[str, Any]] = Field(None, description="运行时信息")

    model_config = ConfigDict(extra="allow")


class NorthChannelListResponse(BaseModel):
    count: int = Field(..., description="通道总数")
    channels: List[NorthChannelResponse] = Field(..., description="通道列表")


class NorthChannelCreateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    channel_id: int = Field(..., description="通道ID")
    requires_restart: bool = Field(default=False, description="是否需要重启")


class NorthChannelUpdateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    channel_id: int = Field(..., description="通道ID")
    updated_fields: List[str] = Field(default_factory=list, description="更新的字段")


class ConnectionTestRequest(BaseModel):
    channel_id: Optional[int] = Field(None, description="通道ID")
    remote_host: str = Field(default="127.0.0.1", description="远程主机地址")
    remote_port: int = Field(default=9000, description="远程端口")


class ConnectionTestResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    latency: Optional[float] = Field(None, description="延迟(毫秒)")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")


# ── North Point Mapping Models ───────────────────────────────


class ValueTransformModel(BaseModel):
    scale: float = Field(default=1.0, description="缩放系数")
    offset: float = Field(default=0.0, description="偏移量")
    enum_map: Optional[Dict[str, Any]] = Field(None, description="枚举映射表")

    model_config = ConfigDict(extra="allow")


class NorthMappingCreate(BaseModel):
    channel_id: int = Field(..., description="通道ID")
    asset: str = Field(..., description="设备资产标识")
    point_name: str = Field(..., description="标准点位名称")
    protocol_oid: Optional[int] = Field(None, description="协议OID（XNC专用）")
    protocol_vdid: Optional[int] = Field(None, description="协议虚拟设备ID（XNC专用）")
    pid_value: int = Field(default=85, description="值PID（XNC专用）")
    pid_error: int = Field(default=103, description="错误PID（XNC专用）")
    value_transform: Optional[ValueTransformModel] = Field(None, description="值变换配置")
    protocol_config: Optional[Dict[str, Any]] = Field(None, description="协议特有映射配置（JSON，不同插件解释不同）")
    enabled: bool = Field(default=True, description="是否启用")

    model_config = ConfigDict(extra="allow")


class NorthMappingUpdate(BaseModel):
    asset: Optional[str] = Field(None, description="设备资产标识")
    point_name: Optional[str] = Field(None, description="标准点位名称")
    protocol_oid: Optional[int] = Field(None, description="协议OID（XNC专用）")
    protocol_vdid: Optional[int] = Field(None, description="协议虚拟设备ID（XNC专用）")
    pid_value: Optional[int] = Field(None, description="值PID（XNC专用）")
    pid_error: Optional[int] = Field(None, description="错误PID（XNC专用）")
    value_transform: Optional[ValueTransformModel] = Field(None, description="值变换配置")
    protocol_config: Optional[Dict[str, Any]] = Field(None, description="协议特有映射配置")
    enabled: Optional[bool] = Field(None, description="是否启用")

    model_config = ConfigDict(extra="allow")


class NorthMappingResponse(BaseModel):
    id: int = Field(..., description="映射ID")
    channel_id: int = Field(..., description="通道ID")
    asset: str = Field(..., description="设备资产标识")
    point_name: str = Field(..., description="标准点位名称")
    protocol_oid: Optional[int] = Field(None, description="协议OID（XNC专用）")
    protocol_vdid: Optional[int] = Field(None, description="协议虚拟设备ID（XNC专用）")
    pid_value: int = Field(default=85, description="值PID（XNC专用）")
    pid_error: int = Field(default=103, description="错误PID（XNC专用）")
    value_transform: Optional[Dict[str, Any]] = Field(None, description="值变换配置")
    protocol_config: Optional[Dict[str, Any]] = Field(None, description="协议特有映射配置")
    enabled: bool = Field(default=True, description="是否启用")
    status: str = Field(default="active", description="状态")
    created_at: Optional[float] = Field(None, description="创建时间")
    updated_at: Optional[float] = Field(None, description="更新时间")

    model_config = ConfigDict(extra="allow")


class NorthMappingListResponse(BaseModel):
    count: int = Field(..., description="映射总数")
    mappings: List[NorthMappingResponse] = Field(..., description="映射列表")


class NorthMappingCreateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    mapping_id: int = Field(..., description="映射ID")


class NorthMappingUpdateResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    mapping_id: int = Field(..., description="映射ID")
    updated_fields: List[str] = Field(default_factory=list, description="更新的字段")


class NorthMappingBatchCreateResponse(BaseModel):
    total: int = Field(..., description="总数")
    succeeded: int = Field(..., description="成功数")
    failed: int = Field(..., description="失败数")
    details: List[Dict[str, Any]] = Field(default_factory=list, description="详情")


class NorthMappingImportRequest(BaseModel):
    mappings: List[NorthMappingCreate] = Field(..., description="映射列表")
    overwrite: bool = Field(default=False, description="是否覆盖已存在的映射")


class NorthMappingExportResponse(BaseModel):
    channel_id: int = Field(..., description="通道ID")
    mappings: List[Dict[str, Any]] = Field(..., description="映射列表")
