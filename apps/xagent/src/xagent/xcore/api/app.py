"""XAgent Gateway API - FastAPI application"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .dependencies import get_app_state
from .routers import (
    system_router,
    data_router,
    storage_router,
    control_router,
    plugins_router,
    config_router,
    metadata_router,
    rules_router,
    devices_router
)

if TYPE_CHECKING:
    from ..gateway import Gateway

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("XAgent Gateway starting...")
    
    from ..gateway import Gateway
    
    state = get_app_state()
    
    if not state.is_initialized():
        gateway = Gateway()
        await gateway.initialize()
        await gateway.start_core()
        state._gateway_owned = True
    else:
        state._gateway_owned = False
    
    yield
    
    state = get_app_state()
    if state._gateway_owned and state.gateway:
        try:
            await state.gateway.stop()
        except Exception as e:
            logger.error(f"Error stopping gateway: {e}")
    
    logger.info("XAgent Gateway stopped")


app = FastAPI(
    title="XAgent Gateway API",
    description="Lightweight Python IoT Gateway",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(system_router)
app.include_router(data_router)
app.include_router(storage_router)
app.include_router(control_router)
app.include_router(plugins_router)
app.include_router(config_router)
app.include_router(metadata_router)
app.include_router(rules_router)
app.include_router(devices_router)

_static_dir = Path(__file__).parent.parent.parent / "resources" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
async def root():
    index_path = _static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": "XAgent Gateway",
        "version": "1.0.0",
        "status": "running"
    }


def create_app() -> FastAPI:
    return app
