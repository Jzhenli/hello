"""测试数据生成工具"""

import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any


class TestDataGenerator:
    """测试数据生成器"""

    @staticmethod
    def generate_reading(
        device_id: str = None,
        timestamp: float = None,
        point_count: int = 5
    ) -> Dict[str, Any]:
        """生成单个读数数据

        Args:
            device_id: 设备ID
            timestamp: 时间戳
            point_count: 点位数量

        Returns:
            读数数据字典
        """
        if device_id is None:
            device_id = f"device_{random.randint(1, 100)}"

        if timestamp is None:
            timestamp = time.time()

        values = []
        for i in range(point_count):
            values.append({
                "point_id": f"point_{i:03d}",
                "value": round(random.uniform(0, 100), 2),
                "quality": random.choice(["good", "good", "good", "bad", "uncertain"])
            })

        return {
            "device_id": device_id,
            "timestamp": timestamp,
            "values": values
        }

    @staticmethod
    def generate_readings_batch(
        count: int = 10,
        device_ids: List[str] = None,
        time_range_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """批量生成读数数据

        Args:
            count: 数据数量
            device_ids: 设备ID列表
            time_range_hours: 时间范围（小时）

        Returns:
            读数数据列表
        """
        if device_ids is None:
            device_ids = [f"device_{i:03d}" for i in range(1, 6)]

        readings = []
        now = time.time()

        for i in range(count):
            # 随机时间
            timestamp = now - random.uniform(0, time_range_hours * 3600)

            # 随机设备
            device_id = random.choice(device_ids)

            # 生成读数
            reading = TestDataGenerator.generate_reading(
                device_id=device_id,
                timestamp=timestamp,
                point_count=random.randint(1, 10)
            )

            readings.append(reading)

        # 按时间排序
        readings.sort(key=lambda x: x["timestamp"])

        return readings

    @staticmethod
    def generate_hourly_stats(hours: int = 24) -> List[Dict[str, Any]]:
        """生成小时统计数据

        Args:
            hours: 小时数

        Returns:
            小时统计数据列表
        """
        stats = []
        now = datetime.now()

        for i in range(hours):
            hour_time = now - timedelta(hours=i)
            stats.append({
                "time": hour_time.strftime("%H:00"),
                "count": random.randint(100, 500),
                "timestamp": hour_time.timestamp()
            })

        # 反转顺序（从早到晚）
        stats.reverse()

        return stats

    @staticmethod
    def generate_quality_stats(total: int = 1000) -> Dict[str, Any]:
        """生成数据质量统计

        Args:
            total: 总数据点数

        Returns:
            质量统计字典
        """
        good = int(total * random.uniform(0.9, 0.98))
        bad = int((total - good) * random.uniform(0.3, 0.5))
        uncertain = total - good - bad

        quality_rate = round((good / total) * 100, 2)

        return {
            "good": good,
            "bad": bad,
            "uncertain": uncertain,
            "total": total,
            "quality_rate": quality_rate
        }

    @staticmethod
    def generate_system_stats() -> Dict[str, Any]:
        """生成系统统计数据

        Returns:
            系统统计字典
        """
        return {
            "cpu_usage": round(random.uniform(20, 80), 2),
            "memory_usage": round(random.uniform(40, 90), 2),
            "disk_usage": round(random.uniform(30, 70), 2),
            "uptime": random.randint(3600, 86400 * 30),
            "total_readings": random.randint(10000, 100000),
            "today_readings": random.randint(100, 5000),
            "connection_count": random.randint(5, 50),
            "process_count": random.randint(10, 100),
            "load_average": [
                round(random.uniform(0, 2), 2),
                round(random.uniform(0, 2), 2),
                round(random.uniform(0, 2), 2)
            ]
        }

    @staticmethod
    def generate_collection_stats(hours: int = 24) -> Dict[str, Any]:
        """生成采集统计数据

        Args:
            hours: 小时数

        Returns:
            采集统计字典
        """
        stats = TestDataGenerator.generate_hourly_stats(hours)

        total_count = sum(s["count"] for s in stats)
        avg_rate = round(total_count / len(stats), 2)

        return {
            "stats": stats,
            "total_count": total_count,
            "avg_rate": avg_rate
        }


# 便捷函数
def generate_test_data(data_type: str = "reading", **kwargs) -> Any:
    """生成测试数据

    Args:
        data_type: 数据类型 (reading, readings_batch, hourly_stats, quality_stats, system_stats, collection_stats)
        **kwargs: 其他参数

    Returns:
        测试数据
    """
    generator = TestDataGenerator()

    if data_type == "reading":
        return generator.generate_reading(**kwargs)
    elif data_type == "readings_batch":
        return generator.generate_readings_batch(**kwargs)
    elif data_type == "hourly_stats":
        return generator.generate_hourly_stats(**kwargs)
    elif data_type == "quality_stats":
        return generator.generate_quality_stats(**kwargs)
    elif data_type == "system_stats":
        return generator.generate_system_stats()
    elif data_type == "collection_stats":
        return generator.generate_collection_stats(**kwargs)
    else:
        raise ValueError(f"Unknown data type: {data_type}")


if __name__ == "__main__":
    # 示例用法
    print("=== 单个读数 ===")
    print(generate_test_data("reading"))

    print("\n=== 批量读数 ===")
    readings = generate_test_data("readings_batch", count=5)
    for reading in readings:
        print(reading)

    print("\n=== 小时统计 ===")
    print(generate_test_data("hourly_stats", hours=5))

    print("\n=== 数据质量统计 ===")
    print(generate_test_data("quality_stats", total=1000))

    print("\n=== 系统统计 ===")
    print(generate_test_data("system_stats"))

    print("\n=== 采集统计 ===")
    print(generate_test_data("collection_stats", hours=5))
