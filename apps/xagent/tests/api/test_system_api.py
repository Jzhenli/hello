"""Tests for System API routes (system stats, data quality, collection stats)"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from unittest.mock import AsyncMock, patch

from xagent.xcore.api.routers import system


class TestSystemAPI:
    """System API 测试用例"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        app.include_router(system.router)
        return app

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app, base_url="http://test")

    @pytest.fixture
    def mock_stats_manager(self):
        """创建 mock StatisticsManager"""
        manager = AsyncMock()

        # 设置默认返回值
        manager.get_system_stats = AsyncMock(return_value={
            "cpu_usage": 45.5,
            "memory_usage": 62.3,
            "disk_usage": 38.7,
            "uptime": 86400,
            "total_readings": 10000,
            "today_readings": 500,
            "connection_count": 12,
            "process_count": 8,
            "load_average": [0.5, 0.8, 1.2]
        })

        manager.get_quality_stats = AsyncMock(return_value={
            "good": 950,
            "bad": 30,
            "uncertain": 20,
            "total": 1000,
            "quality_rate": 95.0
        })

        manager.get_collection_stats = AsyncMock(return_value={
            "stats": [
                {
                    "time": "10:00",
                    "count": 245,
                    "timestamp": 1714285200
                },
                {
                    "time": "11:00",
                    "count": 312,
                    "timestamp": 1714288800
                }
            ],
            "total_count": 557,
            "avg_rate": 278.5
        })

        return manager

    # ===== 系统统计 API 测试 =====

    def test_get_system_stats_success(self, client, mock_stats_manager):
        """测试成功获取系统统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            response = client.get("/api/system/stats")

            assert response.status_code == 200
            data = response.json()

            # 验证返回的字段
            assert "cpu_usage" in data
            assert "memory_usage" in data
            assert "disk_usage" in data
            assert "uptime" in data
            assert "total_readings" in data
            assert "today_readings" in data
            assert "connection_count" in data
            assert "process_count" in data
            assert "load_average" in data

            # 验证数据值（允许一定误差，因为实际会调用psutil）
            assert isinstance(data["cpu_usage"], (int, float))
            assert isinstance(data["memory_usage"], (int, float))
            assert isinstance(data["disk_usage"], (int, float))
            assert isinstance(data["uptime"], int)
            assert isinstance(data["load_average"], list)

    def test_get_system_stats_no_manager(self, client):
        """测试 StatisticsManager 不可用时的降级"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=None):
            response = client.get("/api/system/stats")

            assert response.status_code == 200
            data = response.json()

            # 应该返回基本统计（降级方案）
            assert "cpu_usage" in data
            assert "memory_usage" in data
            assert "disk_usage" in data
            assert "uptime" in data

            # 采集统计应该是0
            assert data["total_readings"] == 0
            assert data["today_readings"] == 0

    def test_get_system_stats_error_handling(self, client, mock_stats_manager):
        """测试系统统计的错误处理"""
        mock_stats_manager.get_system_stats.side_effect = Exception("Stats error")

        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            # 应该不会抛出异常，而是使用降级方案
            response = client.get("/api/system/stats")

            assert response.status_code == 200
            data = response.json()
            
            # 验证返回了基本数据
            assert "cpu_usage" in data
            assert "memory_usage" in data

    # ===== 数据质量 API 测试 =====

    def test_get_data_quality_success(self, client, mock_stats_manager):
        """测试成功获取数据质量统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            response = client.get("/api/data/quality")

            assert response.status_code == 200
            data = response.json()

            # 验证返回的字段
            assert "good" in data
            assert "bad" in data
            assert "uncertain" in data
            assert "total" in data
            assert "quality_rate" in data

            # 验证数据类型
            assert isinstance(data["good"], int)
            assert isinstance(data["bad"], int)
            assert isinstance(data["uncertain"], int)
            assert isinstance(data["total"], int)
            assert isinstance(data["quality_rate"], (int, float))

    def test_get_data_quality_no_manager(self, client):
        """测试 StatisticsManager 不可用时的数据质量统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=None):
            response = client.get("/api/data/quality")

            assert response.status_code == 200
            data = response.json()

            # 应该返回默认值
            assert data["good"] == 0
            assert data["bad"] == 0
            assert data["uncertain"] == 0
            assert data["total"] == 0
            assert data["quality_rate"] == 0.0

    # ===== 数据采集统计 API 测试 =====

    def test_get_collection_stats_success(self, client, mock_stats_manager):
        """测试成功获取采集统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            response = client.get("/api/data/stats")

            assert response.status_code == 200
            data = response.json()

            # 验证返回的字段
            assert "stats" in data
            assert "total_count" in data
            assert "avg_rate" in data

            # 验证数据类型
            assert isinstance(data["stats"], list)
            assert isinstance(data["total_count"], (int, float))
            assert isinstance(data["avg_rate"], (int, float))

    def test_get_collection_stats_with_params(self, client, mock_stats_manager):
        """测试带参数的采集统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            params = {
                "start_time": 1714281600,
                "end_time": 1714288800,
                "interval": "hour"
            }

            response = client.get("/api/data/stats", params=params)

            assert response.status_code == 200
            data = response.json()

            # 验证返回数据
            assert "stats" in data
            assert "total_count" in data
            assert "avg_rate" in data

    def test_get_collection_stats_no_manager(self, client):
        """测试 StatisticsManager 不可用时的采集统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=None):
            response = client.get("/api/data/stats")

            assert response.status_code == 200
            data = response.json()

            # 应该返回默认值
            assert data["stats"] == []
            assert data["total_count"] == 0
            assert data["avg_rate"] == 0.0

    def test_get_collection_stats_interval_day(self, client, mock_stats_manager):
        """测试按天统计的采集统计"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            params = {"interval": "day"}

            response = client.get("/api/data/stats", params=params)

            assert response.status_code == 200
            data = response.json()

            # 验证返回数据
            assert "stats" in data
            assert "total_count" in data
            assert "avg_rate" in data

    # ===== 综合测试 =====

    def test_api_integration_workflow(self, client, mock_stats_manager):
        """测试 API 集成工作流"""
        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            # 1. 获取系统统计
            system_response = client.get("/api/system/stats")
            assert system_response.status_code == 200
            system_data = system_response.json()

            # 2. 获取数据质量
            quality_response = client.get("/api/data/quality")
            assert quality_response.status_code == 200
            quality_data = quality_response.json()

            # 3. 获取采集统计
            collection_response = client.get("/api/data/stats")
            assert collection_response.status_code == 200
            collection_data = collection_response.json()

            # 验证所有API都返回了数据
            assert "cpu_usage" in system_data
            assert "quality_rate" in quality_data
            assert "total_count" in collection_data

    def test_api_response_time(self, client, mock_stats_manager):
        """测试 API 响应时间"""
        import time

        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            start_time = time.time()
            response = client.get("/api/system/stats")
            end_time = time.time()

            assert response.status_code == 200
            # 响应时间应该小于2秒（考虑CI环境）
            assert (end_time - start_time) < 2.0

    def test_api_concurrent_requests(self, client, mock_stats_manager):
        """测试并发请求"""
        import concurrent.futures

        with patch('xagent.xcore.api.routers.system.get_stats_manager', return_value=mock_stats_manager):
            def make_request(endpoint):
                return client.get(endpoint)

            endpoints = [
                "/api/system/stats",
                "/api/data/quality",
                "/api/data/stats"
            ]

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(make_request, endpoint) for endpoint in endpoints]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            # 所有请求都应该成功
            for result in results:
                assert result.status_code == 200
