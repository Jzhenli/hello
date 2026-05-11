"""Config-related Pydantic models"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConfigUploadResponse(BaseModel):
    success: bool
    message: str
    config_path: str
    requires_restart: bool
    validation_errors: Optional[List[str]] = None
    files_count: Optional[int] = None
    changes: Optional[Dict[str, Any]] = None
    reload_strategy: Optional[Dict[str, Any]] = None


class ConfigReloadResponse(BaseModel):
    success: bool
    message: str
    scope: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ConfigInfoResponse(BaseModel):
    config_path: str
    exists: bool
    size: Optional[int] = None
    last_modified: Optional[str] = None
    is_default: bool


class ConfigValidationRequest(BaseModel):
    config_content: str


class ConfigValidationResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RestartRequest(BaseModel):
    delay: int = 5
    force: bool = False


class RestartResponse(BaseModel):
    success: bool
    message: str
    scheduled_at: str


class ConfigBackupInfo(BaseModel):
    backup_path: str
    backup_name: Optional[str] = None
    backup_type: Optional[str] = None
    created_at: str
    size: int


class ConfigBackupListResponse(BaseModel):
    backups: List[dict]
    total: int
