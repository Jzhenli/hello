"""Config API routes"""

import os
import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse

from ..models.config import (
    ConfigUploadResponse,
    ConfigInfoResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
    ConfigReloadResponse,
    RestartRequest,
    RestartResponse,
    ConfigBackupInfo,
    ConfigBackupListResponse
)
from ..services.config_service import ConfigService
from ..dependencies import get_config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["Configuration"])
security = HTTPBearer()

DEFAULT_API_TOKEN = "xagent_47808"

_config_service = ConfigService()


def verify_api_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API Token"""
    token = credentials.credentials
    expected_token = os.environ.get("XAGENT_API_TOKEN", DEFAULT_API_TOKEN)
    
    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    return token


@router.get("/info", response_model=ConfigInfoResponse)
async def get_config_info():
    """Get configuration file information"""
    info = _config_service.get_config_info()
    return ConfigInfoResponse(**info)


@router.post("/upload", response_model=ConfigUploadResponse)
async def upload_config(
    file: UploadFile = File(...),
    validate_only: bool = False,
    create_backup: bool = True,
    token: str = Depends(verify_api_token)
):
    """Upload configuration file (YAML or ZIP format)
    
    Supports:
    - YAML format (.yaml, .yml): Single configuration file
    - ZIP format (.zip): Complete configuration directory with all files
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    if file.filename.endswith('.zip'):
        result = _config_service.upload_config_zip(file.file, validate_only, create_backup)
    elif file.filename.endswith(('.yaml', '.yml')):
        try:
            content = await file.read()
            content_str = content.decode('utf-8')
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read file content: {str(e)}"
            )
        
        result = _config_service.upload_config(content_str, validate_only, create_backup)
    else:
        raise HTTPException(
            status_code=400,
            detail="Configuration file must be YAML (.yaml, .yml) or ZIP (.zip) format"
        )
    
    if not result["success"] and result.get("validation_errors"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": result["message"],
                "errors": result["validation_errors"],
            }
        )
    
    return ConfigUploadResponse(**result)


@router.post("/reload", response_model=ConfigReloadResponse)
async def reload_configuration(
    config_manager = Depends(get_config_manager),
    token: str = Depends(verify_api_token)
):
    """Reload main configuration file
    
    This endpoint reloads the main configuration file (config.yaml) without restarting the application.
    Use this when only the main configuration has changed.
    
    Note: This does NOT reload device or plugin configurations. 
    Use POST /api/devices/reload for device-level changes.
    """
    try:
        reloaded = config_manager.reload()
        
        if reloaded:
            logger.info("Main configuration reloaded successfully")
            return ConfigReloadResponse(
                success=True,
                message="Main configuration reloaded successfully",
                scope="config",
                details={
                    "config_path": str(config_manager.config_path),
                    "reload_status": "success"
                }
            )
        else:
            logger.info("No configuration changes detected")
            return ConfigReloadResponse(
                success=True,
                message="No configuration changes detected",
                scope="config",
                details={
                    "config_path": str(config_manager.config_path),
                    "reload_status": "no_changes"
                }
            )
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload configuration: {str(e)}"
        )


@router.post("/validate", response_model=ConfigValidationResponse)
async def validate_config(request: ConfigValidationRequest):
    """Validate configuration file content"""
    is_valid, errors, warnings = _config_service.validate_content(request.config_content)
    
    return ConfigValidationResponse(
        valid=is_valid,
        errors=errors,
        warnings=warnings
    )


@router.get("/download")
async def download_config(
    output_format: str = "yaml",
    token: str = Depends(verify_api_token)
):
    """Download current configuration
    
    Args:
        output_format: Download format - "yaml" (single file) or "zip" (complete directory)
    
    Returns:
        - YAML format: Single config.yaml file
        - ZIP format: Complete configuration directory as ZIP archive
    """
    if output_format not in ["yaml", "zip"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'yaml' or 'zip'"
        )
    
    if output_format == "yaml":
        config_file = _config_service.config_file
        
        if not config_file.exists():
            raise HTTPException(
                status_code=404,
                detail="Configuration file not found"
            )
        
        return FileResponse(
            path=config_file,
            filename="config.yaml",
            media_type="application/x-yaml"
        )
    else:
        zip_path, error = _config_service.create_config_zip()
        
        if error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create configuration ZIP: {error}"
            )
        
        if not zip_path or not zip_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Configuration directory not found or empty"
            )
        
        return FileResponse(
            path=zip_path,
            filename=zip_path.name,
            media_type="application/zip"
        )


@router.get("/backups", response_model=ConfigBackupListResponse)
async def list_config_backups(token: str = Depends(verify_api_token)):
    """List configuration file backups"""
    backups = _config_service.list_backups()
    
    return ConfigBackupListResponse(
        backups=backups,
        total=len(backups)
    )


@router.post("/restore/{backup_name}")
async def restore_config_backup(
    backup_name: str,
    token: str = Depends(verify_api_token)
):
    """Restore a configuration backup"""
    result = _config_service.restore_backup(backup_name)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Restore failed")
        )
    
    return result


@router.post("/restart", response_model=RestartResponse)
async def restart_application(
    request: RestartRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_api_token)
):
    """Restart application"""
    result = await _config_service.schedule_restart(request.delay)
    
    background_tasks.add_task(result["task"], result["delay"])
    
    return RestartResponse(
        success=result["success"],
        message=result["message"],
        scheduled_at=result["scheduled_at"]
    )


@router.delete("/backups/cleanup")
async def cleanup_old_backups(
    keep_count: int = 10,
    token: str = Depends(verify_api_token)
):
    """Clean up old configuration backups"""
    return _config_service.cleanup_old_backups(keep_count)


@router.get("/paths")
async def get_application_paths(token: str = Depends(verify_api_token)):
    """Get application path information"""
    from ...core.paths import get_paths
    paths = get_paths()
    return paths.get_all_paths_info()
