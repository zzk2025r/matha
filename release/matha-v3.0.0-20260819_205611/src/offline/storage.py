# -*- coding: utf-8 -*-
"""Matha 离线模式数据存储模块

提供 SQLite 本地数据存储功能：
  - REPL 历史记录持久化
  - 用户偏好设置存储
  - 计算结果缓存
  - 离线补全词库

使用方式：
  from src.offline.storage import OfflineStorage
  storage = OfflineStorage()
  storage.save_history("x = 1 + 2", "3")
"""
from __future__ import annotations
import sqlite3
import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """历史记录条目"""
    id: int
    code: str
    output: str
    timestamp: str
    is_success: bool


@dataclass
class UserPreference:
    """用户偏好设置"""
    key: str
    value: str
    updated_at: str


class OfflineStorage:
    """
    离线模式数据存储

    使用 SQLite 本地数据库存储：
    - REPL 历史记录
    - 用户偏好设置
    - 计算结果缓存
    - 离线补全词库
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化离线存储

        Args:
            db_path: 数据库文件路径，默认为 ~/.matha/data.db
        """
        if db_path is None:
            # 默认路径
            home = Path.home()
            db_path = str(home / '.matha' / 'data.db')

        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            # 确保目录存在
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            logger.info(f"数据库已连接: {self._db_path}")
        return self._conn

    def _init_database(self) -> None:
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # REPL 历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                output TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_success INTEGER DEFAULT 1
            )
        ''')

        # 用户偏好设置表
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
                input_hash TEXT NOT NULL,
                input_code TEXT NOT NULL,
                output TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(input_hash)
            )
        ''')

        # 离线补全词库表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completion_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                category TEXT,
                usage_count INTEGER DEFAULT 0,
                UNIQUE(word)
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_input_hash ON result_cache(input_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_words_word ON completion_words(word)')

        conn.commit()
        logger.info("数据库初始化完成")

    # ============================================================
    # REPL 历史记录
    # ============================================================

    def save_history(self, code: str, output: str, is_success: bool = True) -> int:
        """
        保存历史记录

        Args:
            code: 输入代码
            output: 输出结果
            is_success: 是否执行成功

        Returns:
            新记录的 ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO history (code, output, is_success) VALUES (?, ?, ?)',
            (code, output, 1 if is_success else 0)
        )
        conn.commit()
        return cursor.lastrowid

    def get_history(self, limit: int = 50, offset: int = 0) -> List[HistoryEntry]:
        """
        获取历史记录

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            历史记录列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM history ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (limit, offset)
        )
        rows = cursor.fetchall()
        return [HistoryEntry(**dict(row)) for row in rows]

    def clear_history(self) -> int:
        """清空历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM history')
        conn.commit()
        return cursor.rowcount

    def get_history_count(self) -> int:
        """获取历史记录总数"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM history')
        return cursor.fetchone()[0]

    # ============================================================
    # 用户偏好设置
    # ============================================================

    def save_preference(self, key: str, value: str) -> None:
        """
        保存用户偏好设置

        Args:
            key: 设置键
            value: 设置值
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()

    def get_preference(self, key: str, default: str = '') -> str:
        """
        获取用户偏好设置

        Args:
            key: 设置键
            default: 默认值

        Returns:
            设置值
        """
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

    # ============================================================
    # 计算结果缓存
    # ============================================================

    def cache_result(self, code: str, output: str) -> bool:
        """
        缓存计算结果

        Args:
            code: 输入代码
            output: 输出结果

        Returns:
            是否缓存成功
        """
        import hashlib
        code_hash = hashlib.md5(code.encode()).hexdigest()

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT OR REPLACE INTO result_cache (input_hash, input_code, output) VALUES (?, ?, ?)',
                (code_hash, code, output)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"缓存结果失败: {e}")
            return False

    def get_cached_result(self, code: str) -> Optional[str]:
        """
        获取缓存的计算结果

        Args:
            code: 输入代码

        Returns:
            缓存的输出，不存在则返回 None
        """
        import hashlib
        code_hash = hashlib.md5(code.encode()).hexdigest()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT output FROM result_cache WHERE input_hash = ?', (code_hash,))
        row = cursor.fetchone()
        return row['output'] if row else None

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM result_cache')
        return {'cached_results': cursor.fetchone()['count']}

    # ============================================================
    # 离线补全词库
    # ============================================================

    def add_completion_word(self, word: str, category: str = 'default') -> None:
        """
        添加补全词

        Args:
            word: 词汇
            category: 类别
        """
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

    def get_completion_words(self, category: Optional[str] = None, limit: int = 100) -> List[str]:
        """
        获取补全词列表

        Args:
            category: 按类别筛选
            limit: 返回数量限制

        Returns:
            词汇列表（按使用次数排序）
        """
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
        """
        批量添加补全词

        Args:
            words: 词汇列表
            category: 类别

        Returns:
            添加的数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(
            'INSERT OR IGNORE INTO completion_words (word, category) VALUES (?, ?)',
            [(word, category) for word in words]
        )
        conn.commit()
        return cursor.rowcount

    # ============================================================
    # 数据库管理
    # ============================================================

    def get_db_size(self) -> float:
        """获取数据库文件大小（MB）"""
        if os.path.exists(self._db_path):
            size_bytes = os.path.getsize(self._db_path)
            return size_bytes / 1024 / 1024
        return 0.0

    def backup(self, backup_path: str) -> bool:
        """
        备份数据库

        Args:
            backup_path: 备份文件路径

        Returns:
            是否备份成功
        """
        try:
            import shutil
            shutil.copy2(self._db_path, backup_path)
            logger.info(f"数据库已备份到: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return False

    def restore(self, backup_path: str) -> bool:
        """
        恢复数据库

        Args:
            backup_path: 备份文件路径

        Returns:
            是否恢复成功
        """
        try:
            import shutil
            shutil.copy2(backup_path, self._db_path)
            self._conn = None  # 重置连接
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


# ============================================================
# 全局单例
# ============================================================

_storage: Optional[OfflineStorage] = None


def get_storage() -> OfflineStorage:
    """获取全局存储实例（单例）"""
    global _storage
    if _storage is None:
        _storage = OfflineStorage()
    return _storage


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  Matha 离线存储测试")
    print("=" * 60)

    with OfflineStorage() as storage:
        # 测试历史记录
        print("\n1. 测试历史记录...")
        history_id = storage.save_history("x = 1 + 2", "3", is_success=True)
        print(f"   保存历史记录 ID: {history_id}")

        history = storage.get_history(limit=10)
        print(f"   获取历史记录: {len(history)} 条")

        # 测试偏好设置
        print("\n2. 测试偏好设置...")
        storage.save_preference("theme", "dark")
        theme = storage.get_preference("theme")
        print(f"   主题设置: {theme}")

        # 测试结果缓存
        print("\n3. 测试结果缓存...")
        storage.cache_result("2 + 2", "4")
        cached = storage.get_cached_result("2 + 2")
        print(f"   缓存结果: {cached}")

        # 测试补全词库
        print("\n4. 测试补全词库...")
        storage.add_batch_words(["matrix", "mean", "variance", "sum"], category="math")
        words = storage.get_completion_words(category="math", limit=10)
        print(f"   数学类词汇: {words}")

        # 统计信息
        print("\n5. 数据库统计...")
        print(f"   历史记录数: {storage.get_history_count()}")
        print(f"   缓存统计: {storage.get_cache_stats()}")
        print(f"   数据库大小: {storage.get_db_size():.3f} MB")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
