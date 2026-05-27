import logging
import asyncio
from typing import Dict, List, Optional, Any

from ...config.config_repository import ConfigRepository
from ...services.audit_service import AuditService
from ...core.metadata import MetadataManager
from ...core.event_bus import EventBus, Event, EventType

logger = logging.getLogger(__name__)


class NorthMappingService:
    def __init__(
        self,
        metadata_manager: MetadataManager,
        event_bus: Optional[EventBus] = None,
    ):
        self._config_repo = ConfigRepository(metadata_manager.db)
        self._audit_service = AuditService(metadata_manager.db)
        self._event_bus = event_bus
        self._lock: Optional[asyncio.Lock] = None

    async def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def list_mappings(
        self,
        channel_id: Optional[int] = None,
        asset: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        return await self._config_repo.list_north_mappings(
            channel_id=channel_id, asset=asset, enabled=enabled
        )

    async def get_mapping(self, mapping_id: int) -> Optional[Dict[str, Any]]:
        return await self._config_repo.get_north_mapping(mapping_id)

    async def create_mapping(
        self, data: Dict[str, Any], user: Optional[str] = None
    ) -> Dict[str, Any]:
        channel = await self._config_repo.get_north_channel(data["channel_id"])
        if not channel:
            raise ValueError(f"Channel '{data['channel_id']}' not found")
        async with await self._get_lock():
            mapping = await self._config_repo.create_north_mapping(data, user)
        await self._audit_service.log_action(
            action="create",
            entity_type="north_mapping",
            entity_id=str(mapping["id"]),
            user=user,
            new_value=mapping,
        )
        await self._publish_mapping_changed(data["channel_id"])
        logger.info(
            f"North mapping created: channel={data['channel_id']}, "
            f"asset={data.get('asset')}, point={data.get('point_name')}"
        )
        return mapping

    async def update_mapping(
        self,
        mapping_id: int,
        updates: Dict[str, Any],
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with await self._get_lock():
            old = await self._config_repo.get_north_mapping(mapping_id)
            if not old:
                raise ValueError(f"Mapping '{mapping_id}' not found")
            updated = await self._config_repo.update_north_mapping(
                mapping_id, updates, user
            )
        await self._audit_service.log_action(
            action="update",
            entity_type="north_mapping",
            entity_id=str(mapping_id),
            user=user,
            old_value=old,
            new_value=updated,
        )
        await self._publish_mapping_changed(old["channel_id"])
        logger.info(f"North mapping updated: {mapping_id}")
        return updated

    async def delete_mapping(
        self, mapping_id: int, user: Optional[str] = None
    ) -> None:
        async with await self._get_lock():
            old = await self._config_repo.get_north_mapping(mapping_id)
            if not old:
                raise ValueError(f"Mapping '{mapping_id}' not found")
            await self._config_repo.delete_north_mapping(mapping_id, user)
        await self._audit_service.log_action(
            action="delete",
            entity_type="north_mapping",
            entity_id=str(mapping_id),
            user=user,
            old_value=old,
        )
        await self._publish_mapping_changed(old["channel_id"])
        logger.info(f"North mapping deleted: {mapping_id}")

    async def batch_create_mappings(
        self, mappings: List[Dict[str, Any]], user: Optional[str] = None
    ) -> Dict[str, Any]:
        result = await self._config_repo.batch_create_north_mappings(mappings, user)
        channel_ids = set(m.get("channel_id") for m in mappings if m.get("channel_id"))
        for cid in channel_ids:
            await self._publish_mapping_changed(cid)
        return result

    async def delete_mappings_by_channel(
        self, channel_id: int, user: Optional[str] = None
    ) -> int:
        count = await self._config_repo.delete_north_mappings_by_channel(
            channel_id, user
        )
        await self._publish_mapping_changed(channel_id)
        logger.info(f"Deleted {count} mappings for channel {channel_id}")
        return count

    async def import_mappings(
        self,
        data: Dict[str, Any],
        channel_id: int,
        overwrite: bool = False,
        user: Optional[str] = None,
    ) -> Dict[str, Any]:
        channel = await self._config_repo.get_north_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel '{channel_id}' not found")
        mappings_data = data.get("mappings", [])
        succeeded = 0
        failed = 0
        details = []
        for m in mappings_data:
            m["channel_id"] = channel_id
            try:
                existing = None
                all_m = await self._config_repo.list_north_mappings(channel_id=channel_id)
                existing = next(
                    (
                        x
                        for x in all_m
                        if x["asset"] == m.get("asset")
                        and x["point_name"] == m.get("point_name")
                    ),
                    None,
                )
                if existing:
                    if overwrite:
                        await self.update_mapping(existing["id"], m, user)
                        succeeded += 1
                        details.append(
                            {"asset": m.get("asset"), "point_name": m.get("point_name"), "action": "updated", "success": True}
                        )
                    else:
                        failed += 1
                        details.append(
                            {"asset": m.get("asset"), "point_name": m.get("point_name"), "action": "skipped", "success": False, "message": "Already exists"}
                        )
                else:
                    await self.create_mapping(m, user)
                    succeeded += 1
                    details.append(
                        {"asset": m.get("asset"), "point_name": m.get("point_name"), "action": "created", "success": True}
                    )
            except Exception as e:
                failed += 1
                details.append(
                    {"asset": m.get("asset"), "point_name": m.get("point_name"), "action": "failed", "success": False, "message": str(e)}
                )
        return {"total": len(mappings_data), "succeeded": succeeded, "failed": failed, "details": details}

    async def export_mappings(
        self, channel_id: int
    ) -> Dict[str, Any]:
        mappings = await self._config_repo.list_north_mappings(channel_id=channel_id)
        return {"channel_id": channel_id, "mappings": mappings}

    async def _publish_mapping_changed(self, channel_id: int) -> None:
        if self._event_bus:
            event = Event(
                event_type=EventType.NORTH_MAPPING_CHANGED,
                data={"channel_id": channel_id},
            )
            await self._event_bus.publish(event)
