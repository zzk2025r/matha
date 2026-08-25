# -*- coding: utf-8 -*-
"""Matha 移动端离线同步测试

测试远程 API 客户端和冲突解决 UI
"""
import unittest
import sys
from pathlib import Path
import tempfile
import os
import json

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from offline.mobile_api_client import MathaAPIClient, APIResponse, SyncStatus, SyncRecord
from offline.sync import SyncConflictResolver, ConflictStrategy, SyncConflict


class TestAPIClient(unittest.TestCase):
    """测试 API 客户端"""

    def setUp(self):
        """设置测试环境"""
        self.client = MathaAPIClient(
            base_url="https://api.matha.test",
            api_key="test_key",
            timeout=5.0,
            max_retries=2,
        )

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.client.get_base_url(), "https://api.matha.test")
        self.assertFalse(self.client.is_authenticated())
        self.assertIsNone(self.client.get_token())

    def test_set_base_url(self):
        """测试设置基础 URL"""
        self.client.set_base_url("https://new.api.matha.test")
        self.assertEqual(self.client.get_base_url(), "https://new.api.matha.test")

    def test_clear_token(self):
        """测试清除令牌"""
        self.client._token = "test_token"
        self.client._is_authenticated = True
        self.client.clear_token()
        self.assertIsNone(self.client.get_token())
        self.assertFalse(self.client.is_authenticated())

    def test_constructor_defaults(self):
        """测试默认构造函数"""
        client = MathaAPIClient(base_url="https://default.api")
        self.assertEqual(client.get_base_url(), "https://default.api")
        self.assertEqual(client._timeout, 30.0)
        self.assertEqual(client._max_retries, 3)

    def test_callbacks(self):
        """测试回调注册"""
        callback_called = []

        def on_conflict(record):
            callback_called.append(record)

        def on_sync(action, record_id):
            callback_called.append((action, record_id))

        self.client.on_conflict(on_conflict)
        self.client.on_sync(on_sync)

        self.client._notify_conflict("history", "1", {"a": 1}, {"b": 2})
        self.client._notify_sync("push", "1")

        self.assertEqual(len(callback_called), 2)
        self.assertIsInstance(callback_called[0], SyncRecord)
        self.assertEqual(callback_called[1], ("push", "1"))


class TestAPIResponse(unittest.TestCase):
    """测试 API 响应"""

    def test_success_response(self):
        """测试成功响应"""
        response = APIResponse(status_code=200, data={"key": "value"})
        self.assertTrue(response.success)
        self.assertIsNone(response.error)
        self.assertFalse(response.is_conflict)

    def test_conflict_response(self):
        """测试冲突响应"""
        response = APIResponse(status_code=409, data={"conflict": True})
        self.assertFalse(response.success)
        self.assertTrue(response.is_conflict)

    def test_error_response(self):
        """测试错误响应"""
        response = APIResponse(status_code=500, error="Internal Error")
        self.assertFalse(response.success)
        self.assertTrue(response.error)


class TestSyncRecord(unittest.TestCase):
    """测试同步记录"""

    def test_create_record(self):
        """测试创建同步记录"""
        record = SyncRecord(
            id="1",
            record_type="history",
            action="push",
            local_data={"code": "x=1"},
        )
        self.assertEqual(record.id, "1")
        self.assertEqual(record.record_type, "history")
        self.assertEqual(record.status, SyncStatus.PENDING)

    def test_record_with_conflict(self):
        """测试带冲突的记录"""
        record = SyncRecord(
            id="2",
            record_type="history",
            action="push",
            local_data={"code": "x=1"},
            remote_data={"code": "x=2"},
            status=SyncStatus.CONFLICT,
        )
        self.assertEqual(record.status, SyncStatus.CONFLICT)
        self.assertTrue(record.remote_data is not None)


class TestSyncStatus(unittest.TestCase):
    """测试同步状态枚举"""

    def test_sync_status_values(self):
        """测试同步状态值"""
        self.assertEqual(SyncStatus.PENDING.value, "pending")
        self.assertEqual(SyncStatus.SYNCING.value, "syncing")
        self.assertEqual(SyncStatus.SUCCESS.value, "success")
        self.assertEqual(SyncStatus.CONFLICT.value, "conflict")
        self.assertEqual(SyncStatus.FAILED.value, "failed")
        self.assertEqual(SyncStatus.NETWORK_ERROR.value, "network_error")


class TestConflictResolver(unittest.TestCase):
    """测试冲突解决"""

    def setUp(self):
        self.resolver = SyncConflictResolver()

    def test_last_write_wins_remote_newer(self):
        conflict = SyncConflict(
            id="test:1",
            record_type="history",
            local_data={"value": "old", "timestamp": 100},
            remote_data={"value": "new", "timestamp": 200},
            local_timestamp=100,
            remote_timestamp=200,
            strategy=ConflictStrategy.LAST_WRITE_WINS,
        )
        result = self.resolver.resolve(conflict)
        self.assertEqual(result["value"], "new")

    def test_merge_strategy(self):
        conflict = SyncConflict(
            id="test:2",
            record_type="history",
            local_data={"a": 1, "b": 2},
            remote_data={"c": 3, "b": 20},
            local_timestamp=100,
            remote_timestamp=100,
            strategy=ConflictStrategy.MERGE,
        )
        result = self.resolver.resolve(conflict)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["c"], 3)


class TestSingleton(unittest.TestCase):
    """测试单例模式"""

    def test_get_api_client(self):
        from offline.mobile_api_client import get_api_client
        client1 = get_api_client()
        client2 = get_api_client()
        self.assertIs(client1, client2)

    def test_set_api_client(self):
        from offline.mobile_api_client import set_api_client, get_api_client
        new_client = MathaAPIClient(base_url="https://new.api")
        set_api_client(new_client)
        self.assertEqual(get_api_client().get_base_url(), "https://new.api")


if __name__ == '__main__':
    unittest.main()
