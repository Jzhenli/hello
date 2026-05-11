"""Plugins API routes"""

from typing import List
from fastapi import APIRouter

from ..models.system import PluginInfoResponse

router = APIRouter(tags=["Plugins"])


@router.get("/api/plugins", response_model=List[PluginInfoResponse])
async def get_plugins():
    from ..app import app
    
    plugins = []
    
    plugin_loader = getattr(app.state, "plugin_loader", None)
    if plugin_loader:
        for p in plugin_loader.get_all_plugins():
            plugins.append(PluginInfoResponse(
                plugin_id=p.plugin_id,
                name=p.name,
                type=p.plugin_type.value,
                status=p.status.value,
                config=p.config
            ))
    else:
        plugins = [
            PluginInfoResponse(
                plugin_id="demo_sensor",
                name="demo_sensor",
                type="south",
                status="running",
                config={"interval": 1}
            )
        ]
    
    return plugins
