"""Command-related models"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass
class ControlCommand:
    command_id: str
    target_service: str
    target_asset: str
    operation: str
    parameters: Dict[str, Any]
    status: CommandStatus = CommandStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expiry: Optional[float] = None
