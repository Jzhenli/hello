"""轻量级系统监控工具 - 适用于资源受限环境"""

import asyncio
import time
import platform
import os
import psutil
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from collections import namedtuple
import logging

logger = logging.getLogger(__name__)

# 安卓存储路径常量
ANDROID_STORAGE_PATHS = [
    '/data',              # 用户数据分区（优先）
    '/storage/emulated/0', # 安卓10+内部存储
    '/storage/sdcard0',   # 内部存储
    '/sdcard',            # 外部存储软链接
]


class SystemMonitor:
    """系统监控器 - 单例模式，共享线程池

    设计原则：
    - 单例模式：全局共享一个实例
    - 共享线程池：最多2个工作线程（轻量级网关不需要太多）
    - 非阻塞：所有psutil调用在线程池中执行
    - 跨平台：智能检测系统盘
    """

    _instance: Optional["SystemMonitor"] = None
    _executor: Optional[ThreadPoolExecutor] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 创建共享线程池，最多2个工作线程
            cls._executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="sys_monitor"
            )
            logger.info("SystemMonitor initialized with shared thread pool (max_workers=2)")
        return cls._instance

    async def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标（异步，非阻塞）

        Returns:
            系统指标字典，包含：
            - cpu_usage: CPU使用率
            - memory: 内存信息对象
            - disk: 磁盘信息对象
            - uptime: 运行时长
            - connections: 网络连接数
            - process_count: 进程数
            - load_avg: 负载均值
        """
        loop = asyncio.get_event_loop()

        def _collect_metrics():
            """收集系统指标（在线程池中执行）"""
            try:
                # CPU使用率（非阻塞方式）
                cpu_usage = psutil.cpu_percent(interval=0)

                # 内存使用率
                memory = psutil.virtual_memory()

                # 磁盘使用率（智能检测系统盘）
                disk = self._get_system_disk_usage()

                # 运行时长
                uptime = time.time() - psutil.boot_time()

                # 连接数和进程数
                connections = self._get_connection_count()
                process_count = len(psutil.pids())

                # 负载均值
                load_avg = self._get_load_average()

                return {
                    "cpu_usage": cpu_usage,
                    "memory": memory,
                    "disk": disk,
                    "uptime": uptime,
                    "connections": connections,
                    "process_count": process_count,
                    "load_avg": load_avg
                }
            except Exception as e:
                logger.error(f"Failed to collect system metrics: {e}")
                return self._get_default_metrics()

        # 在共享线程池中执行
        metrics = await loop.run_in_executor(self._executor, _collect_metrics)
        return metrics

    def _get_system_disk_usage(self):
        """智能获取系统盘使用情况

        Returns:
            磁盘使用信息对象
        """
        try:
            system = platform.system()

            if system == "Windows":
                # Windows: 优先使用系统盘（通常是C盘）
                return psutil.disk_usage('C:\\')
            elif system == "Linux":
                # Linux: 需要区分安卓和桌面Linux
                # 检测是否为安卓系统
                if self._is_android():
                    # 安卓: 优先使用数据分区（用户实际使用的存储）
                    return self._get_android_disk_usage()
                else:
                    # 桌面Linux: 使用根目录
                    return psutil.disk_usage('/')
            else:
                # 其他系统（macOS等）: 使用根目录
                return psutil.disk_usage('/')
        except Exception as e:
            logger.warning(f"Failed to get disk usage: {e}")
            # 返回一个模拟对象，避免崩溃
            FakeDisk = namedtuple('FakeDisk', ['total', 'used', 'percent'])
            return FakeDisk(total=0, used=0, percent=0.0)

    def _is_android(self) -> bool:
        """检测是否为安卓系统

        Returns:
            True表示安卓系统，False表示其他系统
        """
        # 检查ANDROID_ROOT环境变量（最可靠）
        if os.environ.get('ANDROID_ROOT'):
            return True

        # 检查安卓特有目录
        android_markers = ['/system/bin', '/system/app', '/system/build.prop']
        return all(os.path.exists(marker) for marker in android_markers[:2]) or os.path.exists(android_markers[2])

    def _get_android_disk_usage(self):
        """获取安卓系统的磁盘使用情况

        Returns:
            磁盘使用信息对象
        """
        for path in ANDROID_STORAGE_PATHS:
            try:
                if os.path.exists(path):
                    return psutil.disk_usage(path)
            except Exception:
                continue

        # 降级：使用根目录
        logger.warning("Android disk usage detection failed, using root")
        return psutil.disk_usage('/')

    def _get_connection_count(self) -> int:
        """获取网络连接数

        Returns:
            网络连接数
        """
        try:
            return len(psutil.net_connections())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # 权限不足或进程不存在时返回0
            return 0

    def _get_load_average(self) -> list:
        """获取系统负载均值

        Returns:
            负载均值列表 [1分钟, 5分钟, 15分钟]
        """
        try:
            return list(psutil.getloadavg())
        except (AttributeError, OSError):
            # Windows或某些系统不支持getloadavg
            return [0.0, 0.0, 0.0]

    def _get_default_metrics(self) -> Dict[str, Any]:
        """返回默认指标（错误时使用）

        Returns:
            默认指标字典
        """
        FakeMemory = namedtuple('FakeMemory', ['percent'])
        FakeDisk = namedtuple('FakeDisk', ['percent'])

        return {
            "cpu_usage": 0.0,
            "memory": FakeMemory(percent=0.0),
            "disk": FakeDisk(percent=0.0),
            "uptime": 0,
            "connections": 0,
            "process_count": 0,
            "load_avg": [0.0, 0.0, 0.0]
        }


# 全局单例实例
_system_monitor: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """获取系统监控器单例

    Returns:
        SystemMonitor实例
    """
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor
