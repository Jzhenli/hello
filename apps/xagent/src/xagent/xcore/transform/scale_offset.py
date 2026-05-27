"""Scale/Offset Transformer - Bidirectional value transformation with type inference"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ScaleOffsetTransformer:
    """
    Scale/Offset 双向转换器

    数学模型:
        正向(读取): physical = raw * scale + offset
        逆向(写入): raw = (physical - offset) / scale

    类型推导:
        有 scale/offset -> 结果一定是 float
        无 scale/offset -> 保持原始类型
    """

    def __init__(self, scale: Optional[float] = None, offset: Optional[float] = None):
        self._scale = scale
        self._offset = offset

    @property
    def has_transform(self) -> bool:
        return self._scale is not None or self._offset is not None

    @property
    def scale(self) -> Optional[float]:
        return self._scale

    @property
    def offset(self) -> Optional[float]:
        return self._offset

    @classmethod
    def from_point_config(
        cls,
        point_config: Dict[str, Any],
        config_getter: Optional[Callable] = None
    ) -> "ScaleOffsetTransformer":
        if config_getter:
            scale = config_getter(point_config, "scale")
            offset = config_getter(point_config, "offset")
        else:
            config = point_config.get("config", {})
            scale = config.get("scale") if config.get("scale") is not None else point_config.get("scale")
            offset = config.get("offset") if config.get("offset") is not None else point_config.get("offset")
        return cls(scale=scale, offset=offset)

    def forward(self, value: Any, base_type: Optional[str] = None) -> Any:
        """
        正向转换: raw -> physical
        raw * scale + offset

        有转换: 结果为 float
        无转换: 保持 base_type 对应的 Python 类型
        """
        if value is None:
            return None

        try:
            if self.has_transform:
                result = float(value)
                if self._scale is not None:
                    result = result * self._scale
                if self._offset is not None:
                    result = result + self._offset
                return result
            else:
                return self._cast_to_base_type(value, base_type)
        except (ValueError, TypeError) as e:
            logger.warning(f"ScaleOffset forward transform failed for {value}: {e}")
            return None

    def reverse(self, value: Any, base_type: Optional[str] = None) -> Any:
        """
        逆向转换: physical -> raw
        (value - offset) / scale

        Args:
            value: 要转换的值
            base_type: 基础数据类型，用于无转换时的类型转换

        Returns:
            转换后的值，有 scale/offset 时返回 float，否则按 base_type 转换
        """
        if value is None:
            return None

        try:
            if not self.has_transform:
                return self._cast_to_base_type(value, base_type)

            result = float(value)
            if self._offset is not None:
                result = result - self._offset
            if self._scale is not None:
                if self._scale == 0:
                    logger.error("Cannot reverse transform: scale is 0")
                    return None
                result = result / self._scale
            return result
        except (ValueError, TypeError) as e:
            logger.warning(f"ScaleOffset reverse transform failed for {value}: {e}")
            return None

    def infer_standard_type(self, base_type: str) -> str:
        """
        推导 standard_data_type

        有 scale/offset -> "float"
        无 scale/offset -> base_type
        """
        if self.has_transform:
            return "float"
        return base_type

    @staticmethod
    def _cast_to_base_type(value: Any, base_type: Optional[str]) -> Any:
        if base_type is None:
            return value

        if base_type in ("int", "uint16", "int16", "uint32", "int32", "uint64", "int64"):
            return int(value)
        elif base_type in ("float", "float32", "float32_swap", "float64"):
            return float(value)
        elif base_type == "bool":
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on", "active")
            elif isinstance(value, (int, float)):
                return value != 0
            return bool(value)
        elif base_type == "string":
            return str(value)
        return value
