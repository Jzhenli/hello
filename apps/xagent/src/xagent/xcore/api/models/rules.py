"""Rule Engine API Pydantic models"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class PluginConfig(BaseModel):
    name: str = Field(..., description="Plugin name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Plugin configuration")


class DataSubscription(BaseModel):
    asset: str = Field(..., description="Asset name")
    point: str = Field(..., description="Point name")
    mode: Literal["single", "window"] = Field(default="single", description="Subscription mode")
    window_size: int = Field(default=300, description="Window size in seconds")
    window_type: Literal["sliding", "tumbling"] = Field(default="sliding", description="Window type")
    aggregation: Literal["none", "avg", "sum", "min", "max"] = Field(default="none", description="Aggregation type")
    min_data_points: int = Field(default=1, description="Minimum data points required")
    max_data_points: int = Field(default=10000, description="Maximum data points allowed")


class NotificationConfig(BaseModel):
    title: Optional[str] = Field(None, description="Notification title")
    message: Optional[str] = Field(None, description="Notification message template")
    level: Literal["info", "warning", "error", "critical"] = Field(default="warning", description="Notification level")
    threshold: Optional[Union[float, int, str]] = Field(None, description="Threshold value")
    recipients: Optional[List[str]] = Field(None, description="Recipient list")


class RuleCreateRequest(BaseModel):
    id: str = Field(..., description="Rule ID")
    name: str = Field(..., description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    enabled: bool = Field(default=True, description="Whether rule is enabled")
    plugin: PluginConfig = Field(..., description="Rule plugin configuration")
    data_subscriptions: Optional[List[DataSubscription]] = Field(default=None, description="Data subscriptions")
    notification: Optional[NotificationConfig] = Field(default=None, description="Notification configuration")
    pipeline_id: Optional[str] = Field(None, description="Associated filter pipeline ID")
    channel_ids: Optional[List[str]] = Field(None, description="Delivery channel IDs")


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    enabled: Optional[bool] = Field(None, description="Whether rule is enabled")
    plugin: Optional[PluginConfig] = Field(None, description="Rule plugin configuration")
    data_subscriptions: Optional[List[DataSubscription]] = Field(None, description="Data subscriptions")
    notification: Optional[NotificationConfig] = Field(None, description="Notification configuration")
    pipeline_id: Optional[str] = Field(None, description="Associated filter pipeline ID")
    channel_ids: Optional[List[str]] = Field(None, description="Delivery channel IDs")


class RuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    plugin: Dict[str, Any]
    data_subscriptions: Optional[List[Dict[str, Any]]] = None
    notification: Optional[Dict[str, Any]] = None
    pipeline_id: Optional[str] = None
    channel_ids: Optional[List[str]] = None


class FilterConfig(BaseModel):
    name: str = Field(..., description="Filter plugin name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Filter configuration")
    order: int = Field(default=0, description="Execution order")


class PipelineCreateRequest(BaseModel):
    pipeline_id: str = Field(..., description="Pipeline ID")
    filters: List[FilterConfig] = Field(default_factory=list, description="Filter configurations")
    continue_on_error: bool = Field(default=False, description="Continue on filter error")
    log_errors: bool = Field(default=True, description="Log filter errors")
    max_retries: int = Field(default=0, description="Maximum retries")
    retry_delay: float = Field(default=1.0, description="Retry delay in seconds")
    retry_backoff: float = Field(default=2.0, description="Retry backoff factor")
    timeout_per_filter: float = Field(default=30.0, description="Timeout per filter in seconds")
    location: Literal["south", "north"] = Field(default="south", description="Pipeline location")
    service_name: str = Field(default="", description="Service name")
    error_callback_plugin: Optional[str] = Field(None, description="Error callback plugin name")
    error_callback_config: Optional[Dict[str, Any]] = Field(None, description="Error callback plugin config")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")


class PipelineResponse(BaseModel):
    pipeline_id: str
    filters: List[Dict[str, Any]]
    continue_on_error: bool
    log_errors: bool
    max_retries: int
    retry_delay: float
    retry_backoff: float
    timeout_per_filter: float
    location: str
    service_name: str
    error_callback_plugin: Optional[str] = None
    error_callback_config: Optional[Dict[str, Any]] = None
    enable_metrics: bool


class ChannelCreateRequest(BaseModel):
    channel_id: str = Field(..., description="Channel ID")
    plugin_name: str = Field(..., description="Delivery plugin name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Channel configuration")


class ChannelResponse(BaseModel):
    channel_id: str
    plugin_name: str
    config: Dict[str, Any]


class RuleEngineStatusResponse(BaseModel):
    running: bool
    loaded_rules: int
    registered_channels: int
    active_pipelines: int
    aggregation_subscriptions: int
    event_bus_connected: bool


class RuleListResponse(BaseModel):
    count: int
    rules: List[RuleResponse]


class PipelineListResponse(BaseModel):
    count: int
    pipelines: List[PipelineResponse]


class ChannelListResponse(BaseModel):
    count: int
    channels: List[ChannelResponse]


class RuleOperationResponse(BaseModel):
    success: bool
    message: str
    rule_id: Optional[str] = None


class PipelineOperationResponse(BaseModel):
    success: bool
    message: str
    pipeline_id: Optional[str] = None


class ChannelOperationResponse(BaseModel):
    success: bool
    message: str
    channel_id: Optional[str] = None


class BindChannelsRequest(BaseModel):
    channel_ids: List[str] = Field(..., description="List of channel IDs to bind")
