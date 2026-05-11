"""Unified logging configuration module for XAgent"""

import io
import logging
import sys
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import LoggingConfig


def _ensure_utf8_encoding() -> None:
    """
    Ensure stdout and stderr use UTF-8 encoding on Windows.
    
    This fixes garbled Chinese characters in Windows system error messages
    (e.g., WinError 1225: "远程计算机拒绝网络连接").
    """
    if sys.platform != 'win32':
        return
    
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and stream.encoding != 'utf-8':
            stream.reconfigure(encoding='utf-8')


class ColorCodes:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GREY = "\033[90m"


LEVEL_COLORS = {
    logging.DEBUG: ColorCodes.CYAN,
    logging.INFO: ColorCodes.GREEN,
    logging.WARNING: ColorCodes.YELLOW,
    logging.ERROR: ColorCodes.RED,
    logging.CRITICAL: ColorCodes.RED + ColorCodes.BOLD,
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to log output in console."""
    
    def __init__(self, fmt: str = None, datefmt: str = None, use_color: bool = True):
        super().__init__(fmt, datefmt)
        self.use_color = use_color
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_color and record.levelno in LEVEL_COLORS:
            original_levelname = record.levelname
            original_name = record.name
            original_asctime = record.asctime if hasattr(record, 'asctime') else None
            
            color = LEVEL_COLORS[record.levelno]
            record.levelname = f"{color}{record.levelname}{ColorCodes.RESET}"
            record.name = f"{ColorCodes.CYAN}{record.name}{ColorCodes.RESET}"
            
            asctime = self.formatTime(record, self.datefmt)
            record.asctime = f"{ColorCodes.GREY}{asctime}{ColorCodes.RESET}"
            
            try:
                result = super().format(record)
            finally:
                record.levelname = original_levelname
                record.name = original_name
                if original_asctime:
                    record.asctime = original_asctime
            
            return result
        
        return super().format(record)


def setup_logging(config: 'LoggingConfig') -> None:
    """
    Initialize the logging system based on configuration.
    
    Args:
        config: LoggingConfig instance containing logging settings
    """
    log_level = getattr(logging, config.level.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    root_logger.handlers.clear()
    
    if config.console:
        _ensure_utf8_encoding()
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = ColoredFormatter(
            fmt=config.format,
            datefmt=config.date_format,
            use_color=config.color
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    if config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            filename=config.file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            fmt=config.format,
            datefmt=config.date_format
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    
    logging.getLogger("pymodbus.logging").setLevel(logging.ERROR)
    logging.getLogger("pymodbus").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """
    [DEPRECATED] Get a logger instance with the given name.
    
    This function is deprecated. Use logging.getLogger(name) directly instead.
    All modules in the project already use logging.getLogger(__name__) directly.
    
    Args:
        name: Logger name, typically __name__
        
    Returns:
        logging.Logger instance
    """
    warnings.warn(
        "get_logger() is deprecated. Use logging.getLogger(name) directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return logging.getLogger(name)
