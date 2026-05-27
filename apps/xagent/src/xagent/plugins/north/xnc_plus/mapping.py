import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class IDMapper(ABC):

    @abstractmethod
    def get_vd_id(self, device_id: str) -> Optional[int]:
        ...

    @abstractmethod
    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        ...

    @abstractmethod
    def get_oid(self, point_name: str, device_id: str) -> Optional[int]:
        ...

    @abstractmethod
    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        ...

    @abstractmethod
    def get_device_id_by_oid(self, oid: int) -> Optional[str]:
        ...

    @abstractmethod
    def get_pid_by_type(self, pid_type: str) -> int:
        ...


class StaticMapper(IDMapper):

    PID_POINT_VALUE = 85
    PID_POINT_ERROR = 103

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        pid_config = self.config.get("pid", {})
        self._pid_point_value = pid_config.get("point_value", self.PID_POINT_VALUE)
        self._pid_point_error = pid_config.get("point_error", self.PID_POINT_ERROR)

        self._point_to_oid: Dict[str, int] = {}
        self._device_to_vdid: Dict[str, int] = {}
        self._reverse_oid: Dict[int, str] = {}
        self._reverse_vdid: Dict[int, str] = {}
        self._point_to_device: Dict[str, str] = {}

        self._load()

    def _load(self) -> None:
        mapping_file = self.config.get("device_mapping_file")
        if mapping_file and os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                for point_key, point_info in data.get("points", {}).items():
                    if not isinstance(point_info, dict):
                        continue
                    oid = point_info.get("oid")
                    if oid is not None:
                        if oid in self._reverse_oid and self._reverse_oid[oid] != point_key:
                            logger.warning(
                                f"oid conflict in mapping file: {oid} already mapped to "
                                f"{self._reverse_oid[oid]}, overwriting with {point_key}"
                            )
                        self._point_to_oid[point_key] = oid
                        self._reverse_oid[oid] = point_key
                        if "." in point_key:
                            device_id = point_key.split(".", 1)[0]
                            self._point_to_device[point_key] = device_id

                logger.info(f"Loaded mapping from {mapping_file}")
            except Exception as e:
                logger.error(f"Failed to load mapping file: {e}")

        for device_id, vdid in self.config.get("vdid_mapping", {}).items():
            if vdid in self._reverse_vdid and self._reverse_vdid[vdid] != device_id:
                logger.warning(
                    f"vdid conflict: {vdid} already mapped to "
                    f"{self._reverse_vdid[vdid]}, overwriting with {device_id}"
                )
            self._device_to_vdid[device_id] = vdid
            self._reverse_vdid[vdid] = device_id

        for key, oid in self.config.get("oid_mapping", {}).items():
            if not isinstance(oid, int):
                continue
            if key not in self._point_to_oid:
                if oid in self._reverse_oid and self._reverse_oid[oid] != key:
                    logger.warning(
                        f"oid conflict in config mapping: {oid} already mapped to "
                        f"{self._reverse_oid[oid]}, overwriting with {key}"
                    )
                self._point_to_oid[key] = oid
                self._reverse_oid[oid] = key
                if "." in key:
                    device_id = key.split(".", 1)[0]
                    self._point_to_device[key] = device_id

    def get_vd_id(self, device_id: str) -> Optional[int]:
        return self._device_to_vdid.get(device_id)

    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        return self._reverse_vdid.get(vdid)

    def get_oid(self, point_name: str, device_id: str) -> Optional[int]:
        namespaced = f"{device_id}.{point_name}"
        if namespaced in self._point_to_oid:
            return self._point_to_oid[namespaced]
        return self._point_to_oid.get(point_name)

    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        full_name = self._reverse_oid.get(oid)
        if not full_name:
            return None
        if "." in full_name:
            return full_name.split(".", 1)[1]
        return full_name

    def get_device_id_by_oid(self, oid: int) -> Optional[str]:
        full_name = self._reverse_oid.get(oid)
        if not full_name:
            return None
        if "." in full_name:
            return full_name.split(".", 1)[0]
        return self._point_to_device.get(full_name)

    def get_pid_by_type(self, pid_type: str) -> int:
        if pid_type == "point_error":
            return self._pid_point_error
        return self._pid_point_value


class DynamicMapper(IDMapper):

    def __init__(
        self,
        static_mapper: StaticMapper,
        persist_path: Optional[str] = None,
    ):
        self._static = static_mapper
        self._persist_path = persist_path

        self._dynamic_point_to_oid: Dict[str, int] = {}
        self._dynamic_device_to_vdid: Dict[str, int] = {}
        self._dynamic_reverse_oid: Dict[int, str] = {}
        self._dynamic_reverse_vdid: Dict[int, str] = {}
        self._dynamic_point_to_device: Dict[str, str] = {}

        self._next_oid = 1
        self._next_vdid = 1

        if static_mapper._reverse_oid:
            self._next_oid = max(static_mapper._reverse_oid.keys()) + 1
        if static_mapper._reverse_vdid:
            self._next_vdid = max(static_mapper._reverse_vdid.keys()) + 1

        self._load_persisted()

    def _load_persisted(self) -> None:
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            for device_id, vdid in data.get("vdid_mapping", {}).items():
                if vdid in self._dynamic_reverse_vdid and self._dynamic_reverse_vdid[vdid] != device_id:
                    logger.warning(
                        f"persisted vdid conflict: {vdid} already mapped to "
                        f"{self._dynamic_reverse_vdid[vdid]}, overwriting with {device_id}"
                    )
                self._dynamic_device_to_vdid[device_id] = vdid
                self._dynamic_reverse_vdid[vdid] = device_id
                if vdid >= self._next_vdid:
                    self._next_vdid = vdid + 1

            for point_key, point_info in data.get("points", {}).items():
                if not isinstance(point_info, dict):
                    continue
                oid = point_info.get("oid")
                if oid is not None:
                    if oid in self._dynamic_reverse_oid and self._dynamic_reverse_oid[oid] != point_key:
                        logger.warning(
                            f"persisted oid conflict: {oid} already mapped to "
                            f"{self._dynamic_reverse_oid[oid]}, overwriting with {point_key}"
                        )
                    self._dynamic_point_to_oid[point_key] = oid
                    self._dynamic_reverse_oid[oid] = point_key
                    if oid >= self._next_oid:
                        self._next_oid = oid + 1
                    if "." in point_key:
                        device_id = point_key.split(".", 1)[0]
                        self._dynamic_point_to_device[point_key] = device_id

            for point_key, device_id in data.get("point_devices", {}).items():
                if point_key not in self._dynamic_point_to_device:
                    self._dynamic_point_to_device[point_key] = device_id

            logger.info(f"Loaded persisted mapping from {self._persist_path}")
        except Exception as e:
            logger.error(f"Failed to load persisted mapping: {e}")

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            data: Dict[str, Any] = {
                "vdid_mapping": dict(self._dynamic_device_to_vdid),
                "points": {},
                "point_devices": dict(self._dynamic_point_to_device),
            }
            all_keys = set(self._dynamic_point_to_oid.keys())
            for key in all_keys:
                data["points"][key] = {
                    "oid": self._dynamic_point_to_oid[key],
                }

            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.debug(f"Persisted mapping to {self._persist_path}")
        except Exception as e:
            logger.error(f"Failed to persist mapping: {e}")

    def get_vd_id(self, device_id: str) -> Optional[int]:
        static_vdid = self._static.get_vd_id(device_id)
        if static_vdid is not None:
            return static_vdid

        if device_id in self._dynamic_device_to_vdid:
            return self._dynamic_device_to_vdid[device_id]

        vdid = self._next_vdid
        self._dynamic_device_to_vdid[device_id] = vdid
        self._dynamic_reverse_vdid[vdid] = device_id
        self._next_vdid += 1
        logger.debug(f"Auto-assigned vdID {vdid} for device {device_id}")
        self._persist()
        return vdid

    def get_device_id_by_vdid(self, vdid: int) -> Optional[str]:
        result = self._static.get_device_id_by_vdid(vdid)
        if result is not None:
            return result
        return self._dynamic_reverse_vdid.get(vdid)

    def get_oid(self, point_name: str, device_id: str) -> Optional[int]:
        static_oid = self._static.get_oid(point_name, device_id)
        if static_oid is not None:
            return static_oid

        namespaced = f"{device_id}.{point_name}"

        if namespaced in self._dynamic_point_to_oid:
            return self._dynamic_point_to_oid[namespaced]

        oid = self._next_oid
        self._dynamic_point_to_oid[namespaced] = oid
        self._dynamic_reverse_oid[oid] = namespaced
        self._dynamic_point_to_device[namespaced] = device_id
        self._next_oid += 1
        logger.debug(f"Auto-assigned oid {oid} for point {namespaced}")
        self._persist()
        return oid

    def get_point_name_by_oid(self, oid: int) -> Optional[str]:
        result = self._static.get_point_name_by_oid(oid)
        if result is not None:
            return result
        full_name = self._dynamic_reverse_oid.get(oid)
        if not full_name:
            return None
        if "." in full_name:
            return full_name.split(".", 1)[1]
        return full_name

    def get_device_id_by_oid(self, oid: int) -> Optional[str]:
        result = self._static.get_device_id_by_oid(oid)
        if result is not None:
            return result
        full_name = self._dynamic_reverse_oid.get(oid)
        if not full_name:
            return None
        if "." in full_name:
            return full_name.split(".", 1)[0]
        return self._dynamic_point_to_device.get(full_name)

    def get_pid_by_type(self, pid_type: str) -> int:
        return self._static.get_pid_by_type(pid_type)
