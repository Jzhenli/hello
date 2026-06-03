"""系统常量定义"""


class TimeConstants:
    """时间相关常量"""

    # 一小时的秒数
    SECONDS_PER_HOUR = 3600

    # 一天的秒数
    SECONDS_PER_DAY = 86400


class DataConstants:
    """数据相关常量"""

    # 数据量阈值(决定扫描策略)
    QUALITY_STATS_THRESHOLD = 10000

    # 采样记录数限制
    QUALITY_STATS_SAMPLE_LIMIT = 1000


class SystemDefaults:
    """系统统计默认值

    用于统一管理系统统计相关的默认值，避免在多处重复定义
    """

    # CPU使用率默认值
    CPU_USAGE = 0.0

    # 内存使用率默认值
    MEMORY_USAGE = 0.0

    # 磁盘使用率默认值
    DISK_USAGE = 0.0

    # 运行时长默认值
    UPTIME = 0

    # 总采集量默认值
    TOTAL_READINGS = 0

    # 今日采集量默认值
    TODAY_READINGS = 0

    # 连接数默认值
    CONNECTION_COUNT = 0

    # 进程数默认值
    PROCESS_COUNT = 0

    # 负载均值默认值
    LOAD_AVERAGE = [0.0, 0.0, 0.0]

    @classmethod
    def get_default_system_stats(cls) -> dict:
        """获取默认系统统计

        Returns:
            默认系统统计字典
        """
        return {
            "cpu_usage": cls.CPU_USAGE,
            "memory_usage": cls.MEMORY_USAGE,
            "disk_usage": cls.DISK_USAGE,
            "uptime": cls.UPTIME,
            "total_readings": cls.TOTAL_READINGS,
            "today_readings": cls.TODAY_READINGS,
            "connection_count": cls.CONNECTION_COUNT,
            "process_count": cls.PROCESS_COUNT,
            "load_average": cls.LOAD_AVERAGE.copy()
        }

    @classmethod
    def get_default_quality_stats(cls) -> dict:
        """获取默认质量统计

        Returns:
            默认质量统计字典
        """
        return {
            "good": 0,
            "bad": 0,
            "uncertain": 0,
            "total": 0,
            "quality_rate": 0.0
        }

    @classmethod
    def get_default_collection_stats(cls) -> dict:
        """获取默认采集统计

        Returns:
            默认采集统计字典
        """
        return {
            "stats": [],
            "total_count": 0,
            "avg_rate": 0.0
        }
