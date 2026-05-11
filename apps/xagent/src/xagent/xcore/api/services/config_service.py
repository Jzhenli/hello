"""Config Service - Business logic for configuration management"""

import os
import sys
import logging
import shutil
import asyncio
import subprocess
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

import yaml

from ...core.paths import AppPaths, get_paths
from ...core.config import GatewayConfig

logger = logging.getLogger(__name__)


class ConfigService:
    """Configuration management service
    
    Encapsulates all configuration-related business logic,
    keeping route handlers thin and focused on HTTP concerns.
    """
    
    MAX_ZIP_SIZE = 100 * 1024 * 1024
    MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024
    MAX_FILE_COUNT = 1000
    CHUNK_SIZE = 8192
    
    def __init__(self, paths: Optional[AppPaths] = None):
        self._paths = paths or get_paths()
    
    @property
    def config_file(self) -> Path:
        return self._paths.config_file
    
    @property
    def backup_dir(self) -> Path:
        return self._paths.config_dir / "backups"
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get configuration file information"""
        config_file = self.config_file
        exists = config_file.exists()
        
        info = {
            "config_path": str(config_file),
            "exists": exists,
            "is_default": False,
        }
        
        if exists:
            stat = config_file.stat()
            info["size"] = stat.st_size
            info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        return info
    
    def validate_content(self, content: str) -> Tuple[bool, List[str], List[str]]:
        """Validate configuration file content
        
        Returns:
            (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        try:
            config_dict = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return False, [f"YAML parse error: {str(e)}"], []
        
        try:
            GatewayConfig(**config_dict)
        except Exception as e:
            errors.append(f"Config validation error: {str(e)}")
            return False, errors, warnings
        
        if 'storage' in config_dict:
            db_path = config_dict['storage'].get('database', '')
            if db_path and not db_path.startswith(('${', '/', '~', '.\\', './')):
                warnings.append(f"Database path should use absolute path or path marker: {db_path}")
        
        if 'logging' in config_dict:
            log_file = config_dict['logging'].get('file')
            if log_file and not log_file.startswith(('${', '/', '~', '.\\', './')):
                warnings.append(f"Log file path should use absolute path or path marker: {log_file}")
        
        return True, errors, warnings
    
    def upload_config(
        self,
        content_str: str,
        validate_only: bool = False,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """Upload and save configuration file (YAML format)
        
        Returns:
            Result dict with success, message, config_path, requires_restart, validation_errors
        """
        is_valid, errors, warnings = self.validate_content(content_str)
        
        if not is_valid:
            return {
                "success": False,
                "message": "Configuration validation failed",
                "config_path": "",
                "requires_restart": False,
                "validation_errors": errors,
            }
        
        if validate_only:
            return {
                "success": True,
                "message": "Configuration validation passed (validate-only mode)",
                "config_path": "",
                "requires_restart": False,
                "validation_errors": warnings,
            }
        
        config_file = self.config_file
        
        if create_backup and config_file.exists():
            self._create_backup(config_file)
        
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        logger.info(f"Configuration saved: {config_file}")
        
        return {
            "success": True,
            "message": "Configuration uploaded successfully, restart required",
            "config_path": str(config_file),
            "requires_restart": True,
            "validation_errors": warnings,
        }
    
    def upload_config_zip(
        self,
        zip_file: BinaryIO,
        validate_only: bool = False,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """Upload and extract configuration directory from ZIP file
        
        Args:
            zip_file: Binary file-like object containing ZIP data
            validate_only: Only validate without saving
            create_backup: Create backup before overwriting
            
        Returns:
            Result dict with success, message, config_path, requires_restart, validation_errors
        """
        try:
            zip_file.seek(0, 2)
            zip_size = zip_file.tell()
            zip_file.seek(0)
            
            if zip_size > self.MAX_ZIP_SIZE:
                return {
                    "success": False,
                    "message": f"ZIP file too large (max {self.MAX_ZIP_SIZE // 1024 // 1024}MB)",
                    "config_path": "",
                    "requires_restart": False,
                    "validation_errors": [f"ZIP file size {zip_size // 1024 // 1024}MB exceeds maximum allowed size"],
                }
            
            with zipfile.ZipFile(zip_file, 'r') as zf:
                file_list = zf.namelist()
                
                if len(file_list) > self.MAX_FILE_COUNT:
                    return {
                        "success": False,
                        "message": f"Too many files in ZIP (max {self.MAX_FILE_COUNT})",
                        "config_path": "",
                        "requires_restart": False,
                        "validation_errors": [f"ZIP contains {len(file_list)} files, maximum allowed is {self.MAX_FILE_COUNT}"],
                    }
                
                total_uncompressed_size = sum(info.file_size for info in zf.infolist())
                if total_uncompressed_size > self.MAX_UNCOMPRESSED_SIZE:
                    return {
                        "success": False,
                        "message": f"Uncompressed size too large (max {self.MAX_UNCOMPRESSED_SIZE // 1024 // 1024}MB)",
                        "config_path": "",
                        "requires_restart": False,
                        "validation_errors": [f"Uncompressed size {total_uncompressed_size // 1024 // 1024}MB exceeds maximum"],
                    }
                
                main_config_path = self._find_main_config(file_list)
                
                if not main_config_path:
                    return {
                        "success": False,
                        "message": "ZIP file must contain config.yaml or config.yml in root directory",
                        "config_path": "",
                        "requires_restart": False,
                        "validation_errors": ["Missing main configuration file (config.yaml) in root directory"],
                    }
                
                validation_errors = []
                validation_warnings = []
                files_to_extract = []
                
                for file_path in file_list:
                    if file_path.endswith('/') or file_path.startswith('__MACOSX/'):
                        continue
                    
                    if file_path.endswith(('.yaml', '.yml')):
                        try:
                            with zf.open(file_path) as f:
                                content_bytes = b''
                                while True:
                                    chunk = f.read(self.CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    content_bytes += chunk
                                content = content_bytes.decode('utf-8')
                            
                            try:
                                yaml.safe_load(content)
                            except yaml.YAMLError as e:
                                validation_errors.append(f"Invalid YAML syntax in {file_path}: {str(e)}")
                                continue
                            
                            if file_path == main_config_path:
                                is_valid, errors, warnings = self.validate_content(content)
                                if not is_valid:
                                    validation_errors.extend(errors)
                                validation_warnings.extend(warnings)
                            
                            files_to_extract.append(file_path)
                        except UnicodeDecodeError as e:
                            validation_errors.append(f"File encoding error in {file_path}: must be UTF-8")
                        except Exception as e:
                            validation_errors.append(f"Failed to read {file_path}: {str(e)}")
                
                if validation_errors:
                    return {
                        "success": False,
                        "message": "Configuration validation failed",
                        "config_path": "",
                        "requires_restart": False,
                        "validation_errors": validation_errors,
                    }
                
                if validate_only:
                    return {
                        "success": True,
                        "message": f"Configuration validation passed (validate-only mode). {len(files_to_extract)} files found.",
                        "config_path": "",
                        "requires_restart": False,
                        "validation_errors": validation_warnings,
                        "files_count": len(files_to_extract),
                    }
                
                if create_backup:
                    self._create_backup_directory()
                
                config_dir = self._paths.config_dir
                extracted_count = 0
                
                for file_path in files_to_extract:
                    target_path = config_dir / file_path
                    
                    if not self._is_safe_path(config_dir, target_path):
                        logger.warning(f"Skipping unsafe path: {file_path}")
                        continue
                    
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        with zf.open(file_path) as source, open(target_path, 'wb') as target:
                            while True:
                                chunk = source.read(self.CHUNK_SIZE)
                                if not chunk:
                                    break
                                target.write(chunk)
                        extracted_count += 1
                    except PermissionError as e:
                        logger.error(f"Permission denied writing {file_path}: {e}")
                        validation_warnings.append(f"Permission denied for {file_path}, skipped")
                    except Exception as e:
                        logger.error(f"Failed to extract {file_path}: {e}")
                        validation_warnings.append(f"Failed to extract {file_path}: {str(e)}")
                
                logger.info(
                    f"Extracted configuration files",
                    extra={
                        "files_count": extracted_count,
                        "config_dir": str(config_dir),
                    }
                )
                
                changes = self._analyze_config_changes(files_to_extract)
                reload_strategy = self._determine_reload_strategy(changes)
                
                requires_restart = reload_strategy["type"] == "restart"
                
                return {
                    "success": True,
                    "message": f"Configuration uploaded successfully ({extracted_count} files)",
                    "config_path": str(config_dir),
                    "requires_restart": requires_restart,
                    "validation_errors": validation_warnings,
                    "files_count": extracted_count,
                    "changes": changes,
                    "reload_strategy": reload_strategy,
                }
                
        except zipfile.BadZipFile as e:
            logger.warning(f"Invalid ZIP file: {e}")
            return {
                "success": False,
                "message": "Invalid ZIP file format",
                "config_path": "",
                "requires_restart": False,
                "validation_errors": ["The uploaded file is not a valid ZIP archive"],
            }
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return {
                "success": False,
                "message": "Permission denied when writing configuration files",
                "config_path": "",
                "requires_restart": False,
                "validation_errors": ["Insufficient permissions to write configuration files"],
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading ZIP config: {e}", exc_info=True)
            return {
                "success": False,
                "message": "An unexpected error occurred",
                "config_path": "",
                "requires_restart": False,
                "validation_errors": ["Please contact system administrator"],
            }
    
    def create_config_zip(self) -> Tuple[Optional[Path], Optional[str]]:
        """Create a ZIP file containing the entire configuration directory
        
        Returns:
            Tuple of (zip_file_path, error_message)
        """
        config_dir = self._paths.config_dir
        
        if not config_dir.exists():
            return None, "Configuration directory does not exist"
        
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"config_backup_{timestamp}.zip"
            zip_path = temp_dir / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in config_dir.rglob('*'):
                    if file_path.is_file():
                        if file_path.parent.name == 'backups':
                            continue
                        
                        arcname = file_path.relative_to(config_dir)
                        zf.write(file_path, arcname)
            
            final_path = Path(tempfile.gettempdir()) / zip_filename
            shutil.move(str(zip_path), str(final_path))
            
            logger.info(f"Created configuration ZIP: {final_path}")
            return final_path, None
            
        except Exception as e:
            logger.error(f"Failed to create config ZIP: {e}")
            return None, str(e)
        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
    
    def _is_safe_path(self, base_dir: Path, target_path: Path) -> bool:
        """Check if target path is within base directory
        
        Args:
            base_dir: Base directory that paths should be contained within
            target_path: Target path to check
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            resolved_target = target_path.resolve()
            resolved_base = base_dir.resolve()
            
            return str(resolved_target).startswith(str(resolved_base))
        except Exception:
            return False
    
    def _find_main_config(self, file_list: List[str]) -> Optional[str]:
        """Find main configuration file in ZIP file list
        
        Args:
            file_list: List of file paths in ZIP archive
            
        Returns:
            Path to main config file if found, None otherwise
        """
        for file_path in file_list:
            if file_path.endswith('/') or file_path.startswith('__MACOSX/'):
                continue
            
            normalized = os.path.normpath(file_path)
            basename = os.path.basename(normalized)
            
            if basename in ['config.yaml', 'config.yml']:
                if normalized.count(os.sep) <= 1:
                    return file_path
        
        return None
    
    def _analyze_config_changes(self, files: List[str]) -> Dict[str, Any]:
        """Analyze configuration file changes
        
        Analyzes a list of file paths from an uploaded ZIP and categorizes
        them into main config, plugins, and devices.
        
        Args:
            files: List of file paths in the uploaded ZIP
            
        Returns:
            Dict containing:
            - main_config: bool - Whether main config file is present
            - plugins: List[str] - List of plugin names
            - devices: List[str] - List of device asset names
            - total_files: int - Total number of files
        """
        changes = {
            "main_config": False,
            "plugins": [],
            "devices": [],
            "total_files": len(files)
        }
        
        for file_path in files:
            if file_path.endswith('/') or file_path.startswith('__MACOSX/'):
                continue
            
            normalized = os.path.normpath(file_path)
            parts = normalized.split(os.sep)
            
            if len(parts) == 1 and parts[0] in ['config.yaml', 'config.yml']:
                changes["main_config"] = True
            elif len(parts) >= 2 and parts[0] == 'plugins':
                plugin_name = Path(normalized).stem
                if plugin_name not in changes["plugins"]:
                    changes["plugins"].append(plugin_name)
            elif len(parts) >= 2 and parts[0] == 'devices':
                device_name = Path(normalized).stem
                if device_name not in changes["devices"]:
                    changes["devices"].append(device_name)
        
        return changes
    
    def _determine_reload_strategy(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Determine reload strategy based on configuration changes
        
        Args:
            changes: Configuration changes analysis result
            
        Returns:
            Dict containing reload strategy information
        """
        if changes["devices"] and not changes["plugins"]:
            return {
                "type": "plugin_reload",
                "level": "device",
                "affected": changes["devices"],
                "reason": "Device point configuration changed",
                "suggestion": "Use POST /api/devices/reload to reload affected devices"
            }
        
        if changes["main_config"] and not changes["plugins"] and not changes["devices"]:
            return {
                "type": "hot_reload",
                "level": "config",
                "reason": "Main configuration changed",
                "suggestion": "Use POST /api/config/reload to reload configuration"
            }
        
        if changes["plugins"]:
            affected_devices = self._get_affected_devices(changes["plugins"])
            if affected_devices:
                return {
                    "type": "plugin_reload",
                    "level": "device",
                    "affected": affected_devices,
                    "reason": "Plugin default configuration changed",
                    "suggestion": "Use POST /api/devices/reload to reload affected devices"
                }
        
        if self._check_critical_config_changed(changes):
            return {
                "type": "restart",
                "level": "application",
                "reason": "Critical configuration changed (database, storage, etc.)",
                "suggestion": "Please restart the application"
            }
        
        return {
            "type": "hot_reload",
            "level": "config",
            "reason": "Configuration changed",
            "suggestion": "Use POST /api/config/reload to reload configuration"
        }
    
    def _get_affected_devices(self, plugin_names: List[str]) -> List[str]:
        """Get devices that use the specified plugins
        
        Args:
            plugin_names: List of plugin names
            
        Returns:
            List of affected device asset names
        """
        affected_devices = []
        devices_dir = self._paths.device_config_dir
        
        if not devices_dir.exists():
            return affected_devices
        
        for device_file in devices_dir.glob("*.yaml"):
            try:
                with open(device_file, 'r', encoding='utf-8') as f:
                    import yaml
                    config = yaml.safe_load(f)
                    if config and 'plugin' in config:
                        plugin_name = config['plugin'].get('name', '')
                        if plugin_name in plugin_names:
                            affected_devices.append(device_file.stem)
            except Exception as e:
                logger.warning(f"Failed to read device config {device_file}: {e}")
        
        return affected_devices
    
    def _check_critical_config_changed(self, changes: Dict[str, Any]) -> bool:
        """Check if critical configuration has changed
        
        Args:
            changes: Configuration changes analysis result
            
        Returns:
            True if critical config changed, False otherwise
        """
        if not changes["main_config"]:
            return False
        
        try:
            config_file = self._paths.config_file
            if not config_file.exists():
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                import yaml
                config = yaml.safe_load(f)
            
            if not config:
                return False
            
            critical_keys = ['storage', 'database']
            for key in critical_keys:
                if key in config:
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Failed to check critical config: {e}")
            return False
    
    def _create_backup(self, config_file: Path) -> Path:
        """Create a backup of the current configuration file"""
        backup_dir = self.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config_{timestamp}.yaml"
        
        shutil.copy2(config_file, backup_file)
        logger.info(f"Configuration backup created: {backup_file}")
        
        return backup_file
    
    def _create_backup_directory(self) -> Path:
        """Create a backup of the entire configuration directory"""
        backup_dir = self.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config_backup_{timestamp}.zip"
        
        config_dir = self._paths.config_dir
        
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in config_dir.rglob('*'):
                if file_path.is_file():
                    if file_path.parent.name == 'backups':
                        continue
                    
                    arcname = file_path.relative_to(config_dir)
                    zf.write(file_path, arcname)
        
        logger.info(f"Configuration directory backup created: {backup_file}")
        
        return backup_file
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all configuration backups (both YAML and ZIP)"""
        backup_dir = self.backup_dir
        
        if not backup_dir.exists():
            return []
        
        backups = []
        for backup_file in sorted(backup_dir.glob("config_*"), reverse=True):
            if backup_file.is_file() and backup_file.suffix in ['.yaml', '.zip']:
                stat = backup_file.stat()
                backup_type = "directory" if backup_file.suffix == '.zip' else "file"
                backups.append({
                    "backup_path": str(backup_file),
                    "backup_name": backup_file.name,
                    "backup_type": backup_type,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                })
        
        return backups
    
    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore a configuration backup (YAML or ZIP)
        
        Args:
            backup_name: Backup file name (not path)
        
        Returns:
            Result dict with success, message, requires_restart
        """
        if ".." in backup_name or "/" in backup_name or "\\" in backup_name:
            return {"success": False, "error": "Invalid backup file name"}
        
        backup_file = self.backup_dir / backup_name
        
        if not backup_file.exists():
            return {"success": False, "error": f"Backup file not found: {backup_name}"}
        
        if backup_file.suffix == '.zip':
            return self._restore_zip_backup(backup_file)
        else:
            return self._restore_yaml_backup(backup_file)
    
    def _restore_yaml_backup(self, backup_file: Path) -> Dict[str, Any]:
        """Restore a YAML configuration backup"""
        config_file = self.config_file
        
        if config_file.exists():
            self._create_backup(config_file)
        
        shutil.copy2(backup_file, config_file)
        logger.info(f"Configuration restored: {backup_file}")
        
        return {
            "success": True,
            "message": "Configuration restored, restart required",
            "requires_restart": True,
        }
    
    def _restore_zip_backup(self, backup_file: Path) -> Dict[str, Any]:
        """Restore a ZIP configuration backup"""
        try:
            self._create_backup_directory()
            
            config_dir = self._paths.config_dir
            restored_count = 0
            
            with zipfile.ZipFile(backup_file, 'r') as zf:
                for file_path in zf.namelist():
                    if file_path.endswith('/') or file_path.startswith('__MACOSX/'):
                        continue
                    
                    target_path = config_dir / file_path
                    
                    if not self._is_safe_path(config_dir, target_path):
                        logger.warning(f"Skipping unsafe path: {file_path}")
                        continue
                    
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        with zf.open(file_path) as source, open(target_path, 'wb') as target:
                            while True:
                                chunk = source.read(self.CHUNK_SIZE)
                                if not chunk:
                                    break
                                target.write(chunk)
                        restored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to restore {file_path}: {e}")
            
            logger.info(
                f"Configuration directory restored from ZIP",
                extra={
                    "backup_file": str(backup_file),
                    "files_count": restored_count,
                }
            )
            
            return {
                "success": True,
                "message": f"Configuration directory restored ({restored_count} files), restart required",
                "requires_restart": True,
            }
            
        except Exception as e:
            logger.error(f"Failed to restore ZIP backup: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to restore backup: {str(e)}",
            }
    
    def cleanup_old_backups(self, keep_count: int = 10) -> Dict[str, Any]:
        """Clean up old configuration backups (both YAML and ZIP)"""
        backup_dir = self.backup_dir
        
        if not backup_dir.exists():
            return {"success": True, "deleted": 0, "message": "No backups to clean up"}
        
        backup_files = sorted(
            [f for f in backup_dir.glob("config_*") if f.is_file() and f.suffix in ['.yaml', '.zip']],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        deleted_count = 0
        for backup_file in backup_files[keep_count:]:
            backup_file.unlink()
            deleted_count += 1
            logger.info(f"Deleted old backup: {backup_file}")
        
        return {
            "success": True,
            "deleted": deleted_count,
            "kept": len(backup_files) - deleted_count,
            "message": f"Cleaned up {deleted_count} old backup files",
        }
    
    async def schedule_restart(self, delay: int) -> Dict[str, Any]:
        """Schedule an application restart
        
        Args:
            delay: Delay in seconds before restart
        
        Returns:
            Result dict with success, message, scheduled_at
        """
        async def delayed_restart(delay: int):
            await asyncio.sleep(delay)
            
            logger.info("Restarting application...")
            
            python = sys.executable
            script = sys.argv[0]
            
            try:
                if sys.platform == "win32":
                    subprocess.Popen(
                        [python, script],
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    subprocess.Popen([python, script])
                
                logger.info("New process started, shutting down current process")
                os._exit(0)
                
            except Exception as e:
                logger.error(f"Restart failed: {e}")
        
        scheduled_time = datetime.now().isoformat()
        
        return {
            "success": True,
            "message": f"Application will restart in {delay} seconds",
            "scheduled_at": scheduled_time,
            "task": delayed_restart,
            "delay": delay,
        }
