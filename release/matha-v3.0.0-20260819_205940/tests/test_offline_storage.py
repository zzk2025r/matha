# -*- coding: utf-8 -*-
"""Matha 离线存储测试"""
import unittest
import sys
from pathlib import Path
import tempfile
import os

_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from offline.storage import OfflineStorage, HistoryEntry


class TestOfflineStorage(unittest.TestCase):
    """测试离线存储"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = OfflineStorage(db_path=self.db_path)

    def tearDown(self):
        """清理测试环境"""
        self.storage.close()
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_history(self):
        """测试历史记录保存和获取"""
        # 保存
        history_id = self.storage.save_history("x = 1 + 2", "3", is_success=True)
        self.assertIsInstance(history_id, int)
        self.assertGreater(history_id, 0)

        # 获取
        history = self.storage.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].code, "x = 1 + 2")
        self.assertEqual(history[0].output, "3")
        self.assertTrue(history[0].is_success)

    def test_history_count(self):
        """测试历史记录计数"""
        self.storage.save_history("a = 1", "1")
        self.storage.save_history("b = 2", "2")
        count = self.storage.get_history_count()
        self.assertEqual(count, 2)

    def test_clear_history(self):
        """测试清空历史记录"""
        self.storage.save_history("x = 1", "1")
        self.storage.save_history("y = 2", "2")
        cleared = self.storage.clear_history()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.storage.get_history_count(), 0)

    def test_save_preference(self):
        """测试偏好设置保存"""
        self.storage.save_preference("theme", "dark")
        theme = self.storage.get_preference("theme")
        self.assertEqual(theme, "dark")

    def test_get_default_preference(self):
        """测试获取默认偏好"""
        value = self.storage.get_preference("nonexistent", "default_value")
        self.assertEqual(value, "default_value")

    def test_get_all_preferences(self):
        """测试获取所有偏好"""
        self.storage.save_preference("key1", "value1")
        self.storage.save_preference("key2", "value2")
        prefs = self.storage.get_all_preferences()
        self.assertEqual(len(prefs), 2)
        self.assertEqual(prefs["key1"], "value1")
        self.assertEqual(prefs["key2"], "value2")

    def test_cache_result(self):
        """测试结果缓存"""
        cached = self.storage.cache_result("2 + 2", "4")
        self.assertTrue(cached)

        result = self.storage.get_cached_result("2 + 2")
        self.assertEqual(result, "4")

    def test_cache_not_found(self):
        """测试缓存未找到"""
        result = self.storage.get_cached_result("nonexistent")
        self.assertIsNone(result)

    def test_cache_stats(self):
        """测试缓存统计"""
        self.storage.cache_result("1 + 1", "2")
        self.storage.cache_result("2 + 2", "4")
        stats = self.storage.get_cache_stats()
        self.assertEqual(stats["cached_results"], 2)

    def test_add_completion_word(self):
        """测试添加补全词"""
        self.storage.add_completion_word("matrix", "math")
        words = self.storage.get_completion_words(category="math")
        self.assertIn("matrix", words)

    def test_add_batch_words(self):
        """测试批量添加补全词"""
        words = ["mean", "variance", "std"]
        count = self.storage.add_batch_words(words, "stats")
        self.assertEqual(count, 3)

        retrieved = self.storage.get_completion_words(category="stats")
        self.assertEqual(len(retrieved), 3)
        self.assertIn("mean", retrieved)

    def test_increment_word_usage(self):
        """测试增加词汇使用次数"""
        self.storage.add_completion_word("test_word")
        self.storage.increment_word_usage("test_word")
        words = self.storage.get_completion_words()
        self.assertIn("test_word", words)

    def test_db_size(self):
        """测试数据库大小获取"""
        size = self.storage.get_db_size()
        self.assertGreaterEqual(size, 0)

    def test_backup_and_restore(self):
        """测试备份和恢复"""
        self.storage.save_history("x = 1", "1")

        backup_path = os.path.join(self.temp_dir, 'backup.db')
        success = self.storage.backup(backup_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(backup_path))

        # 修改数据
        self.storage.save_history("y = 2", "2")

        # 恢复
        success = self.storage.restore(backup_path)
        self.assertTrue(success)
        self.assertEqual(self.storage.get_history_count(), 1)


class TestOfflineStorageIntegration(unittest.TestCase):
    """离线存储集成测试"""

    def test_context_manager(self):
        """测试上下文管理器"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'test.db')

        with OfflineStorage(db_path=db_path) as storage:
            storage.save_history("test", "result")
            self.assertEqual(storage.get_history_count(), 1)

        # 连接应该已关闭
        self.assertIsNone(storage._conn)

        # 清理
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
