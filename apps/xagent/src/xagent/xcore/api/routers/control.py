"""Control API routes"""

import uuid
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_command_executor
from ..models.control import (
    ControlCommandRequest,
    ControlCommandResponse,
    ControlCommandStatusResponse
)
from ..services.command_executor import CommandExecutor

router = APIRouter(tags=["Control"])


@router.post("/api/control", response_model=ControlCommandResponse)
async def submit_control_command(
    command: ControlCommandRequest,
    executor: CommandExecutor = Depends(get_command_executor)
):
    command_id = str(uuid.uuid4())
    
    success = await executor.submit_command(
        command_id=command_id,
        target_service=command.target_service,
        target_asset=command.target_asset,
        operation=command.operation,
        parameters=command.parameters,
        expiry=command.expiry
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to submit command")
    
    return ControlCommandResponse(
        command_id=command_id,
        status="ACCEPTED",
        message="Command accepted for execution"
    )


@router.get("/api/control/{command_id}", response_model=ControlCommandStatusResponse)
async def get_command_status(
    command_id: str,
    executor: CommandExecutor = Depends(get_command_executor)
):
    cmd_status = executor.get_command_status(command_id)
    if cmd_status is None:
        raise HTTPException(status_code=404, detail="Command not found")
    
    return ControlCommandStatusResponse(**cmd_status)
