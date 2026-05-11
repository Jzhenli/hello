"""System-related Pydantic models"""

from typing import Any, Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    version: str = "1.0.0"


class PluginInfoResponse(BaseModel):
    plugin_id: str
    name: str
    type: str
    status: str
    config: Dict[str, Any] = Field(default_factory=dict)
