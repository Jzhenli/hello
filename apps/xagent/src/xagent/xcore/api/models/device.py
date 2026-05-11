from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
from enum import Enum
import re


class PluginType(str, Enum):
    SOUTH = "south"
    NORTH = "north"
    FILTER = "filter"
    RULE = "rule"
    DELIVERY = "delivery"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class StandardDataType(str, Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"


class PluginConfig(BaseModel):
    name: str = Field(..., description="插件名称")
    type: PluginType = Field(..., description="插件类型")
    version: str = Field(default="1.0.0", description="插件版本")
    description: Optional[str] = Field(None, description="插件描述")
    enabled: bool = Field(default=True, description="是否启用")
    
    defaults: Dict[str, Any] = Field(
        default_factory=dict, 
        description="默认配置"
    )
    
    capabilities: List[str] = Field(
        default_factory=list,
        description="插件能力列表"
    )
    
    model_config = ConfigDict(extra="allow")


class PointConfig(BaseModel):
    name: str = Field(..., description="点位名称")
    description: Optional[str] = Field(None, description="点位描述")
    data_type: str = Field(..., description="协议特定数据类型（如 uint16, temperature, analogInput）")
    standard_data_type: Optional[StandardDataType] = Field(None, description="标准数据类型（bool/int/float/string），由插件自动推导")
    unit: Optional[str] = Field(None, description="单位")
    enabled: bool = Field(default=True, description="是否启用")
    
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="协议特定配置（如 Modbus 地址）"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="点位元数据（如报警阈值、范围）"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="标签列表"
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """验证点位名称"""
        if not v or not v.strip():
            raise ValueError('Point name cannot be empty')
        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$', v):
            raise ValueError('Point name can only contain letters, numbers, underscores, hyphens, and Chinese characters')
        return v.strip()
    
    model_config = ConfigDict(extra="allow")


class PluginReference(BaseModel):
    name: str = Field(..., description="插件名称")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="插件实例配置（覆盖默认值）"
    )


class DeviceConfig(BaseModel):
    asset: str = Field(..., description="设备资产标识")
    name: Optional[str] = Field(None, description="设备名称")
    description: Optional[str] = Field(None, description="设备描述")
    enabled: bool = Field(default=True, description="是否启用")
    status: DeviceStatus = Field(
        default=DeviceStatus.ACTIVE,
        description="设备状态"
    )
    
    plugin: PluginReference = Field(
        ...,
        description="引用的插件"
    )
    
    points: List[PointConfig] = Field(
        default_factory=list,
        description="点位列表"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="设备元数据"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="标签列表"
    )
    
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    @field_validator('asset')
    @classmethod
    def validate_asset(cls, v):
        """验证设备资产标识"""
        if not v or not v.strip():
            raise ValueError('Asset identifier cannot be empty')
        if len(v) > 64:
            raise ValueError('Asset identifier cannot exceed 64 characters')
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Asset identifier can only contain letters, numbers, underscores, and hyphens')
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Asset identifier cannot contain path traversal characters')
        return v.strip()
    
    model_config = ConfigDict(extra="allow")


class DeviceCreateResponse(BaseModel):
    success: bool
    message: str
    asset: str
    plugin_id: Optional[str] = None
    requires_reload: bool = True


class DeviceUpdateResponse(BaseModel):
    success: bool
    message: str
    asset: str
    updated_fields: List[str] = Field(default_factory=list)


class PointCreateResponse(BaseModel):
    success: bool
    message: str
    asset: str
    point_name: str
    requires_reload: bool = True


class DeviceListResponse(BaseModel):
    count: int
    devices: List[DeviceConfig]


class DeviceFilter(BaseModel):
    status: Optional[DeviceStatus] = None
    plugin_name: Optional[str] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None


class BatchOperationResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    details: List[Dict[str, Any]] = Field(default_factory=list)


class DeviceReloadResponse(BaseModel):
    success: bool
    message: str
    asset: Optional[str] = None
    reload_status: Optional[str] = None


class BatchDeviceReloadResponse(BaseModel):
    success: bool
    message: str
    total: int
    succeeded: int
    failed: int
    results: Dict[str, str] = Field(default_factory=dict)
