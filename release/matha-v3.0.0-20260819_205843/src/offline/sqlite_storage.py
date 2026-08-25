# -*- coding: utf-8 -*-
"""Matha SQLite 本地存储模块

提供 SQLite 本地数据存储功能：
  - 历史记录存储
  - 偏好设置存储
  - 计算结果缓存
  - 离线补全词库
"""
from __future__ import annotations
import sqlite3
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class HistoryRecord:
    """历史记录"""
    id: int
    code: str
    output: str
    timestamp: str
    is_success: int


@dataclass
class PreferenceRecord:
    """偏好设置"""
    key: str
    value: str
    updated_at: str


class SQLiteStorage:
    """
    SQLite 本地存储

    提供持久化数据存储：
    - REPL 历史记录
    - 用户偏好设置
    - 计算结果缓存
    - 离线补全词库
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化存储

        Args:
            db_path: 数据库路径，默认为 ~/.matha/data.db
        """
        if db_path is None:
            db_path = str(Path.home() / '.matha' / 'data.db')

        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")  # 提高并发性能
            logger.info(f"数据库已连接: {self._db_path}")
        return self._conn

    def _init_database(self) -> None:
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                output TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_success INTEGER DEFAULT 1,
                mode TEXT DEFAULT 'matha'
            )
        ''')

        # 偏好设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 计算结果缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS result_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL UNIQUE,
                input_code TEXT NOT NULL,
                output TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_ms REAL
            )
        ''')

        # 离线补全词库表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completion_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'default',
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 同步队列表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                record_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                data TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                synced_at DATETIME
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_hash ON result_cache(input_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_words_word ON completion_words(word)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_queue(status)')

        conn.commit()
        logger.info("数据库表初始化完成")

    # ============================================================
    # 历史记录
    # ============================================================

    def save_history(self, code: str, output: str, is_success: bool = True,
                     mode: str = 'matha') -> int:
        """保存历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO history (code, output, is_success, mode) VALUES (?, ?, ?, ?)',
            (code, output, 1 if is_success else 0, mode)
        )
        conn.commit()
        return cursor.lastrowid

    def get_history(self, limit: int = 50, offset: int = 0) -> List[HistoryRecord]:
        """获取历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM history ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (limit, offset)
        )
        return [HistoryRecord(**dict(row)) for row in cursor.fetchall()]

    def get_history_count(self) -> int:
        """获取历史记录总数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM history')
        return cursor.fetchone()[0]

    def clear_history(self) -> int:
        """清空历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM history')
        conn.commit()
        return cursor.rowcount

    def delete_history(self, record_id: int) -> bool:
        """删除单条历史"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM history WHERE id = ?', (record_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ============================================================
    # 偏好设置
    # ============================================================

    def save_preference(self, key: str, value: str) -> None:
        """保存偏好设置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()

    def get_preference(self, key: str, default: str = '') -> str:
        """获取偏好设置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM preferences WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

    def get_all_preferences(self) -> Dict[str, str]:
        """获取所有偏好设置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM preferences')
        return {row['key']: row['value'] for row in cursor.fetchall()}

    def delete_preference(self, key: str) -> bool:
        """删除偏好设置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM preferences WHERE key = ?', (key,))
        conn.commit()
        return cursor.rowcount > 0

    # ============================================================
    # 计算结果缓存
    # ============================================================

    def cache_result(self, code: str, output: str, duration_ms: float = 0.0) -> bool:
        """缓存计算结果"""
        try:
            code_hash = hashlib.md5(code.encode()).hexdigest()
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO result_cache (input_hash, input_code, output, duration_ms) VALUES (?, ?, ?, ?)',
                (code_hash, code, output, duration_ms)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")
            return False

    def get_cached_result(self, code: str) -> Optional[str]:
        """获取缓存的计算结果"""
        try:
            code_hash = hashlib.md5(code.encode()).hexdigest()
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT output FROM result_cache WHERE input_hash = ?', (code_hash,))
            row = cursor.fetchone()
            return row['output'] if row else None
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
            return None

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM result_cache')
        return {'cached_results': cursor.fetchone()['count']}

    def clear_cache(self) -> int:
        """清空缓存"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM result_cache')
        conn.commit()
        return cursor.rowcount

    # ============================================================
    # 离线补全词库
    # ==================================================

    def add_word(self, word: str, category: str = 'default') -> None:
        """添加补全词"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO completion_words (word, category) VALUES (?, ?)',
            (word, category)
        )
        conn.commit()

    def increment_word_usage(self, word: str) -> None:
        """增加词汇使用次数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE completion_words SET usage_count = usage_count + 1 WHERE word = ?',
            (word,)
        )
        conn.commit()

    def get_words(self, category: Optional[str] = None, limit: int = 100) -> List[str]:
        """获取补全词列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute(
                'SELECT word FROM completion_words WHERE category = ? ORDER BY usage_count DESC LIMIT ?',
                (category, limit)
            )
        else:
            cursor.execute(
                'SELECT word FROM completion_words ORDER BY usage_count DESC LIMIT ?',
                (limit,)
            )
        return [row['word'] for row in cursor.fetchall()]

    def add_batch_words(self, words: List[str], category: str = 'default') -> int:
        """批量添加补全词"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(
            'INSERT OR IGNORE INTO completion_words (word, category) VALUES (?, ?)',
            [(word, category) for word in words]
        )
        conn.commit()
        return cursor.rowcount

    # ============================================================
    # 同步队列
    # ============================================================

    def enqueue_sync(self, action: str, record_type: str, record_id: str,
                     data: Dict[str, Any], priority: int = 0) -> int:
        """加入同步队列"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO sync_queue (action, record_type, record_id, data, priority)
               VALUES (?, ?, ?, ?, ?)''',
            (action, record_type, record_id, json.dumps(data, ensure_ascii=False), priority)
        )
        conn.commit()
        return cursor.lastrowid

    def get_pending_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待同步数据"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT * FROM sync_queue WHERE status = 'pending'
               ORDER BY priority DESC, created_at ASC LIMIT ?''',
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_synced(self, queue_id: int) -> bool:
        """标记为已同步"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE sync_queue SET status = 'synced', synced_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (queue_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def mark_failed(self, queue_id: int, error: str = '') -> bool:
        """标记为失败"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE sync_queue SET status = 'failed', retry_count = retry_count + 1
               WHERE id = ?''',
            (queue_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_queue_stats(self) -> Dict[str, int]:
        """获取队列统计"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'synced' THEN 1 ELSE 0 END) as synced,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM sync_queue
        ''')
        row = cursor.fetchone()
        return {
            'pending': row[0] or 0,
            'synced': row[1] or 0,
            'failed': row[2] or 0,
        }

    def clear_sync_queue(self) -> int:
        """清空同步队列"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sync_queue")
        conn.commit()
        return cursor.rowcount

    # ============================================================
    # 数据库管理
    # ============================================================

    def get_db_size(self) -> float:
        """获取数据库大小（MB）"""
        try:
            if Path(self._db_path).exists():
                return Path(self._db_path).stat().st_size / 1024 / 1024
        except Exception:
            pass
        return 0.0

    def backup(self, backup_path: str) -> bool:
        """备份数据库"""
        try:
            import shutil
            shutil.copy2(self._db_path, backup_path)
            logger.info(f"数据库已备份到: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return False

    def restore(self, backup_path: str) -> bool:
        """恢复数据库"""
        try:
            import shutil
            self.close()
            # 先备份当前数据库
            if os.path.exists(self._db_path):
                backup_current = self._db_path + '.bak'
                shutil.copy2(self._db_path, backup_current)
            # 恢复备份
            shutil.copy2(backup_path, self._db_path)
            self._conn = None
            self._init_database()
            logger.info(f"数据库已从 {backup_path} 恢复")
            return True
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return False

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("数据库连接已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()


# 全局单例
_storage: Optional[SQLiteStorage] = None


def get_storage() -> SQLiteStorage:
    """获取全局存储实例（单例）"""
    global _storage
    if _storage is None:
        _storage = SQLiteStorage()
    return _storage


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  Matha SQLite 存储测试")
    print("=" * 60)

    with SQLiteStorage() as storage:
        # 测试历史记录
        print("\n1. 测试历史记录...")
        record_id = storage.save_history("x = 1 + 2", "3", is_success=True)
        print(f"   保存记录 ID: {record_id}")

        history = storage.get_history(limit=10)
        print(f"   获取历史: {len(history)} 条")

        # 测试偏好设置
        print("\n2. 测试偏好设置...")
        storage.save_preference("theme", "dark")
        theme = storage.get_preference("theme")
        print(f"   主题: {theme}")

        # 测试结果缓存
        print("\n3. 测试结果缓存...")
        storage.cache_result("2 + 2", "4", duration_ms=0.5)
        cached = storage.get_cached_result("2 + 2")
        print(f"   缓存结果: {cached}")

        # 测试补全词库
        print("\n4. 测试补全词库...")
        storage.add_batch_words(["matrix", "mean", "variance"], category="math")
        words = storage.get_words(category="math")
        print(f"   数学词汇: {words}")

        # 测试同步队列
        print("\n5. 测试同步队列...")
        queue_id = storage.enqueue_sync("push", "history", str(record_id), {"code": "x=1"})
        print(f"   加入队列 ID: {queue_id}")

        stats = storage.get_queue_stats()
        print(f"   队列状态: {stats}")

        # 统计信息
        print("\n6. 数据库统计...")
        print(f"   历史记录数: {storage.get_history_count()}")
        print(f"   缓存统计: {storage.get_cache_stats()}")
        print(f"   数据库大小: {storage.get_db_size():.3f} MB")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
