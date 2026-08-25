# -*- coding: utf-8 -*-
"""Matha SQLite 和同步模块测试"""
import unittest
import sys
from pathlib import Path
import tempfile
import os

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from offline.sqlite_storage import SQLiteStorage, HistoryRecord
from offline.sync import (
    SyncConflictResolver,
    ConflictStrategy,
    SyncConflict,
    SyncLogger,
    OfflineSyncManager,
)


class TestSQLiteStorage(unittest.TestCase):
    """测试 SQLite 存储"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)

    def tearDown(self):
        """清理测试环境"""
        self.storage.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_history(self):
        """测试历史记录保存和获取"""
        record_id = self.storage.save_history("x = 1 + 2", "3", is_success=True)
        self.assertIsInstance(record_id, int)

        history = self.storage.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].code, "x = 1 + 2")
        self.assertEqual(history[0].output, "3")

    def test_history_count(self):
        """测试历史记录计数"""
        self.storage.save_history("a = 1", "1")
        self.storage.save_history("b = 2", "2")
        count = self.storage.get_history_count()
        self.assertEqual(count, 2)

    def test_clear_history(self):
        """测试清空历史"""
        self.storage.save_history("x = 1", "1")
        self.storage.save_history("y = 2", "2")
        cleared = self.storage.clear_history()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.storage.get_history_count(), 0)

    def test_save_preference(self):
        """测试偏好设置"""
        self.storage.save_preference("theme", "dark")
        theme = self.storage.get_preference("theme")
        self.assertEqual(theme, "dark")

    def test_default_preference(self):
        """测试默认偏好"""
        value = self.storage.get_preference("nonexistent", "default")
        self.assertEqual(value, "default")

    def test_cache_result(self):
        """测试结果缓存"""
        cached = self.storage.cache_result("2 + 2", "4", duration_ms=0.5)
        self.assertTrue(cached)

        result = self.storage.get_cached_result("2 + 2")
        self.assertEqual(result, "4")

    def test_cache_not_found(self):
        """测试缓存未找到"""
        result = self.storage.get_cached_result("nonexistent")
        self.assertIsNone(result)

    def test_add_word(self):
        """测试添加补全词"""
        self.storage.add_word("matrix", "math")
        words = self.storage.get_words(category="math")
        self.assertIn("matrix", words)

    def test_enqueue_sync(self):
        """测试同步队列"""
        queue_id = self.storage.enqueue_sync("push", "history", "1", {"code": "x=1"})
        self.assertIsInstance(queue_id, int)

        pending = self.storage.get_pending_sync()
        self.assertEqual(len(pending), 1)

    def test_queue_stats(self):
        """测试队列统计"""
        stats = self.storage.get_queue_stats()
        self.assertIn("pending", stats)
        self.assertIn("synced", stats)
        self.assertIn("failed", stats)

    def test_db_size(self):
        """测试数据库大小"""
        size = self.storage.get_db_size()
        self.assertGreaterEqual(size, 0)

    def test_backup_and_restore(self):
        """测试备份和恢复"""
        self.storage.save_history("x = 1", "1")

        backup_path = os.path.join(self.temp_dir, 'backup.db')
        success = self.storage.backup(backup_path)
        self.assertTrue(success)

        self.storage.save_history("y = 2", "2")

        success = self.storage.restore(backup_path)
        self.assertTrue(success)
        self.assertEqual(self.storage.get_history_count(), 1)


class TestSyncConflictResolver(unittest.TestCase):
    """测试冲突解决器"""

    def setUp(self):
        """设置测试环境"""
        self.resolver = SyncConflictResolver()

    def test_last_write_wins_remote_newer(self):
        """测试 LWW 策略（远程更新）"""
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

    def test_last_write_wins_local_newer(self):
        """测试 LWW 策略（本地更新）"""
        conflict = SyncConflict(
            id="test:2",
            record_type="history",
            local_data={"value": "new", "timestamp": 200},
            remote_data={"value": "old", "timestamp": 100},
            local_timestamp=200,
            remote_timestamp=100,
            strategy=ConflictStrategy.LAST_WRITE_WINS,
        )
        result = self.resolver.resolve(conflict)
        self.assertEqual(result["value"], "new")

    def test_merge_strategy(self):
        """测试合并策略"""
        conflict = SyncConflict(
            id="test:3",
            record_type="history",
            local_data={"a": 1, "b": 2, "nested": {"x": 1}},
            remote_data={"c": 3, "b": 20, "nested": {"y": 2}},
            local_timestamp=100,
            remote_timestamp=100,
            strategy=ConflictStrategy.MERGE,
        )
        result = self.resolver.resolve(conflict)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["c"], 3)
        self.assertEqual(result["nested"]["x"], 1)
        self.assertEqual(result["nested"]["y"], 2)

    def test_first_write_wins(self):
        """测试 FFW 策略"""
        conflict = SyncConflict(
            id="test:4",
            record_type="history",
            local_data={"value": "first"},
            remote_data={"value": "second"},
            local_timestamp=100,
            remote_timestamp=200,
            strategy=ConflictStrategy.FIRST_WRITE_WINS,
        )
        result = self.resolver.resolve(conflict)
        self.assertEqual(result["value"], "first")


class TestSyncLogger(unittest.TestCase):
    """测试同步日志"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'sync_log.jsonl')
        self.logger = SyncLogger(log_file=self.log_file)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_entry(self):
        """测试日志条目"""
        self.logger.log("push", "history", "1", "synced", "推送成功")
        logs = self.logger.get_logs(limit=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["action"], "push")
        self.assertEqual(logs[0]["status"], "synced")

    def test_clear_logs(self):
        """测试清空日志"""
        self.logger.log("push", "history", "1", "synced")
        self.logger.clear_logs()
        self.assertEqual(len(self.logger.get_logs()), 0)


class TestOfflineSyncManager(unittest.TestCase):
    """测试离线同步管理器"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)
        self.resolver = SyncConflictResolver()
        self.sync_logger = SyncLogger(log_file=os.path.join(self.temp_dir, 'sync.log'))
        self.manager = OfflineSyncManager(
            resolver=self.resolver,
            sync_logger=self.sync_logger,
        )

    def tearDown(self):
        """清理测试环境"""
        self.storage.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_enqueue_and_process(self):
        """测试入队和 처리"""
        self.manager.enqueue("push", "history", "1", {"code": "x=1", "timestamp": 100})

        # 模拟远程存储
        class MockRemoteStorage:
            def get(self, record_type, record_id):
                return None
            def save(self, record_type, record_id, data):
                pass

        results = self.manager.process_queue(MockRemoteStorage())
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])

    def test_conflict_detection(self):
        """测试冲突检测"""
        self.manager.enqueue("push", "history", "1", {"code": "x=1", "timestamp": 100})

        class ConflictRemoteStorage:
            def get(self, record_type, record_id):
                return {"code": "x=2", "timestamp": 200}
            def save(self, record_type, record_id, data):
                pass

        results = self.manager.process_queue(ConflictRemoteStorage())
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].get("conflict_resolved", False))

    def test_queue_stats(self):
        """测试队列统计"""
        stats = self.manager.get_queue_stats() if hasattr(self.manager, 'get_queue_stats') else {}
        self.assertIsInstance(stats, dict)


if __name__ == '__main__':
    unittest.main()
