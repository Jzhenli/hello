import json
import logging
import os
from typing import Any, Dict, List, Optional

from .models import Direction, PointMapping, ValueTransform

logger = logging.getLogger(__name__)


class DBMappingRegistry:

    def __init__(self, db: Any, channel_id: int, cache_path: Optional[str] = None):
        self._db = db
        self._channel_id = channel_id
        self._cache_path = cache_path

        self._forward: Dict[str, PointMapping] = {}
        self._by_oid: Dict[int, PointMapping] = {}
        self._by_vdid: Dict[str, int] = {}
        self._by_vdid_reverse: Dict[int, str] = {}

    async def load(self) -> None:
        try:
            await self._load_from_db()
            if self._forward:
                if self._cache_path:
                    self._persist_to_local()
                logger.info(
                    f"Loaded {len(self._forward)} point mappings from DB "
                    f"(channel_id={self._channel_id})"
                )
            elif self._cache_path:
                logger.warning("DB returned empty, falling back to local cache")
                await self._load_from_local()
            else:
                logger.warning("No mappings found and no cache configured")
        except Exception as e:
            logger.warning(f"DB load failed: {e}")
            if self._cache_path:
                await self._load_from_local()
            else:
                logger.warning("No cache path configured, starting with empty mapping")

    async def reload(self) -> None:
        new_forward: Dict[str, PointMapping] = {}
        new_by_oid: Dict[int, PointMapping] = {}
        new_by_vdid: Dict[str, int] = {}
        new_by_vdid_reverse: Dict[int, str] = {}

        try:
            rows = await self._query_mappings()
            for row in rows:
                mapping = self._row_to_mapping(row)
                key = mapping.namespaced_name
                new_forward[key] = mapping
                if mapping.protocol_oid is not None:
                    new_by_oid[mapping.protocol_oid] = mapping
                new_by_vdid[mapping.device_id] = mapping.protocol_vdid
                new_by_vdid_reverse[mapping.protocol_vdid] = mapping.device_id
        except Exception as e:
            logger.error(f"Reload failed, keeping current mapping: {e}")
            return

        self._forward = new_forward
        self._by_oid = new_by_oid
        self._by_vdid = new_by_vdid
        self._by_vdid_reverse = new_by_vdid_reverse

        if self._cache_path:
            self._persist_to_local()

        logger.info(
            f"Reloaded {len(self._forward)} point mappings "
            f"(channel_id={self._channel_id})"
        )

    def lookup_forward(self, point_name: str, device_id: str) -> Optional[PointMapping]:
        return self._forward.get(f"{device_id}.{point_name}")

    def lookup_reverse(self, oid: int) -> Optional[PointMapping]:
        return self._by_oid.get(oid)

    def lookup_device_by_vdid(self, vdid: int) -> Optional[str]:
        return self._by_vdid_reverse.get(vdid)

    def lookup_vdid_by_device(self, device_id: str) -> Optional[int]:
        return self._by_vdid.get(device_id)

    def get_vd_id(self, device_id: str) -> Optional[int]:
        return self._by_vdid.get(device_id)

    def get_oid(self, point_name: str, device_id: str) -> Optional[int]:
        mapping = self.lookup_forward(point_name, device_id)
        return mapping.protocol_oid if mapping else None

    def get_pid_by_type(self, pid_type: str) -> int:
        if not self._forward:
            return 103 if pid_type == "point_error" else 85
        first = next(iter(self._forward.values()))
        return first.pid_error if pid_type == "point_error" else first.pid_value

    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        return self._by_vdid_reverse.get(vdid)

    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        mapping = self._by_oid.get(oid)
        return mapping.standard_name if mapping else None

    def get_device_id_by_oid(self, oid: int) -> Optional[str]:
        mapping = self._by_oid.get(oid)
        return mapping.device_id if mapping else None

    def transform_value(
        self, point_name: str, device_id: str, value: Any, direction: Direction
    ) -> Any:
        mapping = self.lookup_forward(point_name, device_id)
        if mapping is None or mapping.value_transform is None:
            return value
        if direction == Direction.UPLOAD:
            return mapping.value_transform.forward(value)
        return mapping.value_transform.reverse(value)

    @property
    def mapping_count(self) -> int:
        return len(self._forward)

    async def _load_from_db(self) -> None:
        rows = await self._query_mappings()
        for row in rows:
            mapping = self._row_to_mapping(row)
            self._register(mapping)

    async def _query_mappings(self) -> List[Dict[str, Any]]:
        cursor = await self._db.execute(
            """
            SELECT m.asset, m.point_name, m.protocol_oid, m.protocol_vdid,
                   m.pid_value, m.pid_error, m.value_transform, m.protocol_config
            FROM north_point_mapping m
            LEFT JOIN point_registry p
                ON m.asset = p.asset AND m.point_name = p.point_name
            WHERE m.channel_id = ?
              AND m.status = 'active'
              AND m.enabled = 1
              AND (p.status IS NULL OR p.status != 'deleted')
            """,
            (self._channel_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def _register(self, mapping: PointMapping) -> None:
        key = mapping.namespaced_name
        self._forward[key] = mapping
        if mapping.protocol_oid is not None:
            self._by_oid[mapping.protocol_oid] = mapping
        self._by_vdid[mapping.device_id] = mapping.protocol_vdid
        self._by_vdid_reverse[mapping.protocol_vdid] = mapping.device_id

    def _persist_to_local(self) -> None:
        if not self._cache_path:
            return
        try:
            data: Dict[str, Any] = {"channel_id": self._channel_id, "mappings": []}
            for mapping in self._forward.values():
                entry: Dict[str, Any] = {
                    "asset": mapping.device_id,
                    "point_name": mapping.standard_name,
                    "protocol_oid": mapping.protocol_oid,
                    "protocol_vdid": mapping.protocol_vdid,
                    "pid_value": mapping.pid_value,
                    "pid_error": mapping.pid_error,
                }
                if mapping.value_transform:
                    entry["value_transform"] = mapping.value_transform.to_json()
                if mapping.protocol_config:
                    entry["protocol_config"] = mapping.protocol_config
                data["mappings"].append(entry)

            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Persisted mapping cache to {self._cache_path}")
        except Exception as e:
            logger.error(f"Failed to persist mapping cache: {e}")

    async def _load_from_local(self) -> None:
        if not self._cache_path or not os.path.exists(self._cache_path):
            logger.warning("No local cache available, starting with empty mapping")
            return
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for entry in data.get("mappings", []):
                vt = ValueTransform.from_json(entry.get("value_transform"))
                pc = entry.get("protocol_config")
                if isinstance(pc, str):
                    try:
                        pc = json.loads(pc)
                    except (json.JSONDecodeError, TypeError):
                        pc = None
                mapping = PointMapping(
                    standard_name=entry["point_name"],
                    protocol_oid=entry["protocol_oid"],
                    device_id=entry["asset"],
                    protocol_vdid=entry["protocol_vdid"],
                    pid_value=entry.get("pid_value", 85),
                    pid_error=entry.get("pid_error", 103),
                    value_transform=vt,
                    protocol_config=pc,
                )
                self._register(mapping)

            logger.info(
                f"Loaded {len(self._forward)} mappings from local cache "
                f"({self._cache_path})"
            )
        except Exception as e:
            logger.error(f"Failed to load from local cache: {e}")

    @staticmethod
    def _row_to_mapping(row: Dict[str, Any]) -> PointMapping:
        vt = ValueTransform.from_json(row.get("value_transform"))
        pc = row.get("protocol_config")
        if isinstance(pc, str):
            try:
                pc = json.loads(pc)
            except (json.JSONDecodeError, TypeError):
                pc = None
        return PointMapping(
            standard_name=row["point_name"],
            protocol_oid=row["protocol_oid"],
            device_id=row["asset"],
            protocol_vdid=row["protocol_vdid"],
            pid_value=row.get("pid_value") or 85,
            pid_error=row.get("pid_error") or 103,
            value_transform=vt,
            protocol_config=pc,
        )
