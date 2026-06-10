"""
XAgent Gateway API - FastAPI Application

This module provides the main FastAPI application for XAgent Gateway,
including:
- Optimized static file serving with cache control
- SPA (Single Page Application) routing support
- Gateway lifecycle management
- RESTful API endpoints
"""

# ============================================================================
# Standard Library Imports
# ============================================================================
import logging
import re
from pathlib import Path
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

# ============================================================================
# Third-Party Imports
# ============================================================================
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ============================================================================
# Local Imports
# ============================================================================
from .dependencies import get_app_state
from ..core.paths import get_resource_dir
from .routers import (
    system_router,
    data_router,
    storage_router,
    control_router,
    plugins_router,
    config_router,
    metadata_router,
    rules_router,
    devices_router,
    users_router,
    north_channels_router
)

if TYPE_CHECKING:
    from ..gateway import Gateway


# ============================================================================
# Module-Level Constants & Logger
# ============================================================================
logger = logging.getLogger(__name__)


# ============================================================================
# Static Files with Optimized Cache Control
# ============================================================================


class CachedStaticFiles(StaticFiles):
    """StaticFiles with optimized cache control headers.

    Cache strategy:
    - HTML: no-cache (always validate with server)
    - JS/CSS with hash: max-age=31536000, immutable (never revalidate)
    - Other files: max-age=86400 (cache for 1 day)

    This eliminates the need for force-reload in desktop webview,
    improving startup performance and user experience.
    """

    # Pattern to match Vite's content-hash filenames: [name]-[hash].[ext]
    # Hash is typically 8-16 hex characters (e.g., index-BrCWtOIF.js)
    _HASH_PATTERN = re.compile(r'-[a-f0-9]{8,}\.')

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)

        # Set cache headers based on file type
        filename = path.split('/')[-1]

        if path.endswith('.html'):
            # HTML: no-cache, always validate
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        elif any(path.endswith(ext) for ext in ['.js', '.css']):
            if self._HASH_PATTERN.search(filename):
                # Hashed JS/CSS (e.g., index-BrCWtOIF.js): immutable, cache forever
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            else:
                # Non-hashed JS/CSS: short cache
                response.headers['Cache-Control'] = 'public, max-age=86400'
        else:
            # Other static files: cache for 1 day
            response.headers['Cache-Control'] = 'public, max-age=86400'

        return response


# ============================================================================
# SPA (Single Page Application) Server
# ============================================================================

class SPAServer:
    """SPA server with proper cache control and routing."""

    def __init__(self, static_dir: Path):
        self.static_dir = static_dir
        self.index_path = static_dir / "index.html"

    def serve_index(self) -> Response:
        """Serve SPA index.html with no-cache headers.

        Returns:
            Response: FileResponse with no-cache headers, or JSONResponse with app info
        """
        if not self.index_path.exists():
            return JSONResponse({
                "name": "XAgent Gateway",
                "version": "1.0.0",
                "status": "running"
            })

        response = FileResponse(str(self.index_path))
        # HTML should never be cached to ensure users get the latest version
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    def serve_static_file(self, path: str) -> Response:
        """Serve static file or return 404.

        Args:
            path: Relative path to the static file

        Returns:
            Response: FileResponse if file exists, otherwise JSONResponse with 404
        """
        file_path = self.static_dir / path
        if file_path.exists():
            return FileResponse(str(file_path))
        return JSONResponse({"detail": "Not found"}, status_code=404)

    def is_static_file_request(self, path: str) -> bool:
        """Check if path looks like a static file request (has file extension)."""
        return "." in path.split("/")[-1]

    def is_api_request(self, path: str) -> bool:
        """Check if path is an API request."""
        return path.startswith("api/")


# ============================================================================
# Application Lifecycle Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown.

    This context manager handles:
    - Gateway initialization and startup
    - Service dependency injection
    - Graceful shutdown on exit
    """
    logger.info("XAgent Gateway starting...")

    # Import here to avoid circular dependencies
    from ..gateway import Gateway
    from .services.north_channel_service import NorthChannelService

    # Initialize gateway if not already initialized
    state = get_app_state()
    if not state.is_initialized():
        gateway = Gateway()
        await gateway.initialize()
        await gateway.start_core()
        state._gateway_owned = True
        # Gateway.initialize() 已经设置了依赖注入，无需重复调用
    else:
        state._gateway_owned = False

    # Verify NorthChannelService availability
    if state.gateway:
        container = state.gateway.container
        north_channel_service = container.try_resolve(NorthChannelService)

        if north_channel_service:
            logger.info("NorthChannelService ready")
        else:
            logger.warning("NorthChannelService not available")
    else:
        logger.warning("Gateway not available")

    # Yield control to the application
    yield

    # Cleanup on shutdown
    state = get_app_state()
    if state._gateway_owned and state.gateway:
        try:
            await state.gateway.stop()
        except Exception as e:
            logger.error(f"Error stopping gateway: {e}")

    logger.info("XAgent Gateway stopped")


# ============================================================================
# FastAPI Application Instance
# ============================================================================

app = FastAPI(
    title="XAgent Gateway API",
    description="Lightweight Python IoT Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)


# ============================================================================
# API Routers Registration
# ============================================================================

app.include_router(system_router)
app.include_router(data_router)
app.include_router(storage_router)
app.include_router(control_router)
app.include_router(plugins_router)
app.include_router(config_router)
app.include_router(metadata_router)
app.include_router(rules_router)
app.include_router(devices_router)
app.include_router(users_router)
app.include_router(north_channels_router)


# ============================================================================
# SPA Routes & Static Files Mounting
# ============================================================================

# Initialize SPA server
_static_dir = get_resource_dir() / "static"
_spa_server = SPAServer(_static_dir)

# Mount static files with optimized cache control
if _static_dir.exists():
    app.mount("/static", CachedStaticFiles(directory=str(_static_dir), html=True), name="static")


@app.get("/")
async def root():
    """Serve SPA root page."""
    return _spa_server.serve_index()


@app.get("/{path:path}")
async def spa_fallback(path: str):
    """SPA fallback handler for client-side routing.

    Handles three scenarios:
    1. API routes that don't exist -> 404
    2. Static file requests -> serve file or 404
    3. SPA routes -> serve index.html (client-side routing)
    """
    # API routes that don't exist
    if _spa_server.is_api_request(path):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    # Static file requests (e.g., /assets/logo.png)
    if _spa_server.is_static_file_request(path):
        return _spa_server.serve_static_file(path)

    # All other routes serve SPA index (client-side routing)
    return _spa_server.serve_index()


# ============================================================================
# Application Factory
# ============================================================================

def create_app() -> FastAPI:
    """Factory function to create FastAPI application instance.

    Returns:
        FastAPI: Configured application instance
    """
    return app
