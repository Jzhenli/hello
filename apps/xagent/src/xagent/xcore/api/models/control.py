"""Control-related Pydantic models"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ControlCommandRequest(BaseModel):
    target_service: str
    target_asset: str
    operation: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expiry: Optional[int] = None


class ControlCommandResponse(BaseModel):
    command_id: str
    status: str
    message: str


class ControlCommandStatusResponse(BaseModel):
    command_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float
