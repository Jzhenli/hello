import logging
import time
import asyncio
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from ...config.config_repository import ConfigRepository
from ...services.audit_service import AuditService
from ...core.metadata import MetadataManager
from ...core.event_bus import EventBus, Event, EventType

if TYPE_CHECKING:
    from ...services.orchestration.north_channel_orchestrator import NorthChannelOrchestrator

logger = logging.getLogger(__name__)


class NorthChannelService:
    def __init__(
        self,
        metadata_manager: MetadataManager,
        event_bus: Optional[EventBus] = None,
        orchestrator: Optional["NorthChannelOrchestrator"] = None,
    ):
        self._config_repo = ConfigRepository(metadata_manager.db)
        self._audit_service = AuditService(metadata_manager.db)
        self._event_bus = event_bus
        self._orchestrator = orchestrator
        self._lock: Optional[asyncio.Lock] = None

    async def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def list_channels(
        self,
        status: Optional[str] = None,
        enabled: Optional[bool] = None,
        plugin_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        channels = await self._config_repo.list_north_channels(
            status=status, enabled=enabled, plugin_name=plugin_name
        )
        if self._orchestrator:
            for ch in channels:
                info = self._orchestrator.get_channel_info(ch["id"])
                if info:
                    ch["runtime"] = info
        return channels

    async def get_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if channel and self._orchestrator:
            info = self._orchestrator.get_channel_info(channel_id)
            if info:
                channel["runtime"] = info
        return channel

    async def create_channel(
        self, data: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        async with await self._get_lock():
            channel = await self._config_repo.create_north_channel(data, user)
        await self._audit_service.log_action(
            action="create",
            entity_type="north_channel",
            entity_id=str(channel["id"]),
            user=user,
            new_value=channel,
        )
        logger.info(f"North channel created: {channel.get('name')} (id={channel.get('id')})")
        if self._orchestrator and channel.get("enabled"):
            try:
                await self._orchestrator.start_channel(channel["id"])
            except Exception as e:
                logger.warning(f"Failed to auto-start channel {channel['id']}: {e}")
        return channel

    async def update_channel(
        self,
        channel_id: int,
        updates: Dict[str, Any],
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with await self._get_lock():
            old = await self._config_repo.get_north_channel(channel_id)
            if not old:
                raise ValueError(f"Channel '{channel_id}' not found")
            updated = await self._config_repo.update_north_channel(
                channel_id, updates, user
            )
        await self._audit_service.log_action(
            action="update",
            entity_type="north_channel",
            entity_id=str(channel_id),
            user=user,
            old_value=old,
            new_value=updated,
        )
        logger.info(f"North channel updated: {channel_id}")
        if self._orchestrator:
            try:
                await self._orchestrator.reload_channel(channel_id)
            except Exception as e:
                logger.warning(f"Failed to reload channel {channel_id}: {e}")
        return updated

    async def delete_channel(
        self, channel_id: int, user: Optional[str] = None
    ) -> None:
        async with await self._get_lock():
            old = await self._config_repo.get_north_channel(channel_id)
            if not old:
                raise ValueError(f"Channel '{channel_id}' not found")
            await self._config_repo.delete_north_channel(channel_id, user)
        await self._audit_service.log_action(
            action="delete",
            entity_type="north_channel",
            entity_id=str(channel_id),
            user=user,
            old_value=old,
        )
        if self._orchestrator:
            try:
                await self._orchestrator.stop_channel(channel_id)
            except Exception as e:
                logger.warning(f"Failed to stop channel {channel_id}: {e}")
        await self._publish_mapping_changed(channel_id)
        logger.info(f"North channel deleted: {channel_id}")

    async def toggle_channel(
        self, channel_id: int, user: Optional[str] = None
    ) -> Dict[str, Any]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        return await self.update_channel(
            channel_id, {"enabled": not channel["enabled"]}, user
        )

    async def test_connection(self, channel_id: int) -> Dict[str, Any]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        if self._orchestrator:
            try:
                return await self._orchestrator.test_connection(channel_id)
            except Exception as e:
                return {"success": False, "message": f"Connection test failed: {e}"}
        return {"success": False, "message": "Orchestrator not available"}

    async def restart_channel(self, channel_id: int) -> Dict[str, Any]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        if self._orchestrator:
            try:
                await self._orchestrator.restart_channel(channel_id)
                return {"success": True, "message": f"Channel {channel_id} restarted"}
            except Exception as e:
                return {"success": False, "message": str(e)}
        logger.info(f"Restarting north channel: {channel_id}")
        return {"success": True, "message": f"Channel {channel_id} restart initiated"}

    async def get_channel_statistics(
        self, channel_id: int
    ) -> Optional[Dict[str, Any]]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            return None
        mappings = await self._config_repo.list_north_mappings(
            channel_id=channel_id, enabled=True
        )
        stats = {
            "channel_id": channel_id,
            "enabled": channel.get("enabled", False),
            "mapping_count": len(mappings),
        }
        if self._orchestrator:
            info = self._orchestrator.get_channel_info(channel_id)
            if info:
                stats["runtime"] = info
        return stats

    async def batch_create_channels(
        self, channels: List[Dict[str, Any]], user: Optional[str] = None
    ) -> Dict[str, Any]:
        succeeded = 0
        failed = 0
        details = []
        for ch in channels:
            try:
                await self.create_channel(ch, user)
                succeeded += 1
                details.append({"name": ch.get("name"), "success": True})
            except Exception as e:
                failed += 1
                details.append(
                    {"name": ch.get("name"), "success": False, "message": str(e)}
                )
        return {"total": len(channels), "succeeded": succeeded, "failed": failed, "details": details}

    async def export_channels(
        self, channel_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        all_channels = await self._config_repo.list_north_channels()
        if channel_ids:
            channels = [c for c in all_channels if c["id"] in channel_ids]
        else:
            channels = all_channels
        return {"channels": channels}

    async def import_channels(
        self,
        data: Dict[str, Any],
        overwrite: bool = False,
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        channels_data = data.get("channels", [])
        succeeded = 0
        failed = 0
        details = []
        for ch_data in channels_data:
            try:
                existing = None
                ch_name = ch_data.get("name")
                if ch_name:
                    all_ch = await self._config_repo.list_north_channels()
                    existing = next((c for c in all_ch if c["name"] == ch_name), None)
                if existing:
                    if overwrite:
                        await self.update_channel(existing["id"], ch_data, user)
                        succeeded += 1
                        details.append({"name": ch_name, "action": "updated", "success": True})
                    else:
                        failed += 1
                        details.append({"name": ch_name, "action": "skipped", "success": False, "message": "Already exists"})
                else:
                    await self.create_channel(ch_data, user)
                    succeeded += 1
                    details.append({"name": ch_name, "action": "created", "success": True})
            except Exception as e:
                failed += 1
                details.append({"name": ch_data.get("name"), "action": "failed", "success": False, "message": str(e)})
        return {"total": len(channels_data), "succeeded": succeeded, "failed": failed, "details": details}

    async def _publish_mapping_changed(self, channel_id: int) -> None:
        if self._event_bus:
            event = Event(
                event_type=EventType.NORTH_MAPPING_CHANGED,
                data={"channel_id": channel_id},
            )
            await self._event_bus.publish(event)
