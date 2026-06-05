"""Config API routes"""

import os
import re
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends, Header
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
from ..dependencies import get_config_manager, get_app_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["Configuration"])
security = HTTPBearer()

DEFAULT_API_TOKEN = "xagent_47808"


def _get_config_service() -> ConfigService:
    """Get ConfigService with config_repo injected if available"""
    state = get_app_state()
    config_repo = None
    if state.metadata_manager:
        from ...config.config_repository import ConfigRepository
        config_repo = ConfigRepository(state.metadata_manager.db)
    return ConfigService(config_repo=config_repo)


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


def verify_api_token_from_query(token: str = None) -> str:
    """Verify API Token from query parameter (for file downloads)"""
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )

    expected_token = os.environ.get("XAGENT_API_TOKEN", DEFAULT_API_TOKEN)

    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )

    return token


def validate_backup_filename(filename: str) -> str:
    """验证备份文件名（防止路径遍历攻击）
    
    Args:
        filename: 文件名
        
    Returns:
        验证后的文件名
        
    Raises:
        HTTPException: 文件名无效
    """
    # 检查路径遍历字符
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: path traversal detected"
        )
    
    # 检查文件名格式（config_YYYYMMDD_HHMMSS.zip）
    if not re.match(r'^config_\d{8}_\d{6}\.zip$', filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename format"
        )
    
    return filename


@router.get("/info", response_model=ConfigInfoResponse)
async def get_config_info():
    """Get configuration file information"""
    info = _get_config_service().get_config_info()
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
        result = await _get_config_service().upload_config_zip(file.file, validate_only, create_backup)
    elif file.filename.endswith(('.yaml', '.yml')):
        try:
            content = await file.read()
            content_str = content.decode('utf-8')
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read file content: {str(e)}"
            )
        
        result = _get_config_service().upload_config(content_str, validate_only, create_backup)
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
    is_valid, errors, warnings = _get_config_service().validate_content(request.config_content)
    
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
        config_file = _get_config_service().config_file
        
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
        zip_path, error = _get_config_service().create_config_zip()
        
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
    backups = _get_config_service().list_backups()
    
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
    result = _get_config_service().restore_backup(backup_name)
    
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
    result = await _get_config_service().schedule_restart(request.delay)
    
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
    return _get_config_service().cleanup_old_backups(keep_count)


@router.get("/paths")
async def get_application_paths(token: str = Depends(verify_api_token)):
    """Get application path information"""
    from ...core.paths import get_paths
    paths = get_paths()
    return paths.get_all_paths_info()


# ==================== 配置备份相关API ====================

@router.post("/export")
async def export_config(token: str = Depends(verify_api_token)):
    """导出配置（手动备份）
    
    这就是手动备份API！
    
    使用场景：
    1. 定期备份配置
    2. 导入新配置前先备份当前配置
    3. 配置迁移到其他机器
    
    返回ZIP文件，包含：
    - config.db: 配置数据库（不包含历史数据）
    - config.yaml: 系统配置文件
    """
    service = _get_config_service()
    result = await service.export_config()
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Export failed")
        )
    
    return result


@router.get("/export/download/{filename}")
async def download_export(
    filename: str, 
    token: str = None,
    authorization: Optional[str] = Header(None)
):
    """下载导出的配置文件
    
    Args:
        filename: 文件名
        token: API token (通过URL参数传递)
        authorization: Authorization header (Bearer token)
    """
    # 优先从Authorization header获取token
    if authorization:
        if authorization.startswith('Bearer '):
            token = authorization[7:]
            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid Authorization header format"
                )
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid Authorization header format"
            )

    # 验证token
    verify_api_token_from_query(token)
    
    # 验证文件名（防止路径遍历）
    filename = validate_backup_filename(filename)
    
    service = _get_config_service()
    backup_dir = service.backup_dir
    backup_file = backup_dir / filename
    
    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=backup_file,
        filename=filename,
        media_type="application/zip"
    )


@router.post("/import")
async def import_config(
    file: UploadFile = File(...),
    auto_reload: bool = True,
    token: str = Depends(verify_api_token)
):
    """导入配置
    
    使用场景：空机器导入配置
    
    Args:
        file: 上传的ZIP文件
        auto_reload: 是否自动重载配置（默认True）
    
    自动重载会：
    1. 重载主配置文件（config.yaml）
    2. 重载所有设备插件
    
    如果auto_reload=False，需要手动调用：
    - POST /api/config/reload
    - POST /api/devices/reload
    """
    import tempfile
    import shutil
    from pathlib import Path
    
    # 文件大小限制（100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    # 保存上传文件
    temp_dir = Path(tempfile.mkdtemp())
    temp_file = temp_dir / file.filename
    
    try:
        content = await file.read()
        
        # 检查文件大小
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: max {MAX_FILE_SIZE // 1024 // 1024}MB"
            )
        
        with open(temp_file, 'wb') as f:
            f.write(content)
        
        # 导入配置
        service = _get_config_service()
        result = await service.import_config(str(temp_file), auto_reload=auto_reload)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Import failed")
            )
        
        return result
        
    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/list")
async def list_configs(token: str = Depends(verify_api_token)):
    """列出所有导出的配置"""
    service = _get_config_service()
    backup_dir = service.backup_dir
    
    if not backup_dir.exists():
        return {"configs": [], "total": 0}
    
    configs = []
    for backup_file in sorted(backup_dir.glob("config_*.zip"), reverse=True):
        stat = backup_file.stat()
        configs.append({
            "filename": backup_file.name,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {"configs": configs, "total": len(configs)}


@router.delete("/export/{filename}")
async def delete_config(filename: str, token: str = Depends(verify_api_token)):
    """删除导出的配置文件"""
    # 验证文件名（防止路径遍历）
    filename = validate_backup_filename(filename)
    
    service = _get_config_service()
    backup_dir = service.backup_dir
    backup_file = backup_dir / filename
    
    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    backup_file.unlink()
    
    return {"success": True, "message": f"Deleted {filename}"}
