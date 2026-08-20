# -*- coding: utf-8 -*-
"""
Matha 离线存储引擎

提供离线模式下的数据持久化与同步：
  - SQLite 本地存储
  - 变更日志（CRDT 友好）
  - 离线优先架构
  - 冲突自动解决
"""
from __future__ import annotations
import json
import sqlite3
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ChangeEntry:
    """变更日志条目（用于离线同步）"""
    id: str
    timestamp: float
    entity_type: str  # "node", "connection", "project"
    entity_id: str
    action: str  # "create", "update", "delete"
    data: dict
    client_id: str = ""
    version: int = 1


class OfflineStore:
    """离线存储引擎"""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(Path.home() / ".matha" / "offline.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._client_id = self._generate_client_id()
        self._init_db()

    def _generate_client_id(self) -> str:
        """生成客户端唯一 ID"""
        try:
            import uuid
            return uuid.uuid4().hex[:12]
        except Exception:
            return f"client_{int(time.time())}"

    def _init_db(self) -> None:
        """初始化数据库表"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                data TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS changes (
                id TEXT PRIMARY KEY,
                timestamp REAL,
                entity_type TEXT,
                entity_id TEXT,
                action TEXT,
                data TEXT,
                client_id TEXT,
                version INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_time ON changes(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_queue(status)
        """)
        self._conn.commit()
        logger.info(f"离线存储初始化完成: {self._db_path}")

    # ── 项目操作 ────────────────────────────────────────────────────────────

    def save_project(self, project_id: str, name: str, data: dict) -> bool:
        """保存项目（离线优先）"""
        now = time.time()
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO projects (id, name, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, name, json.dumps(data), now, now),
            )
            self._conn.commit()
            self._log_change("project", project_id, "update", data)
            logger.info(f"项目已保存: {project_id}")
            return True
        except Exception as e:
            logger.error(f"保存项目失败: {e}")
            return False

    def load_project(self, project_id: str) -> Optional[dict]:
        """加载项目"""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "data": json.loads(row["data"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None
        except Exception as e:
            logger.error(f"加载项目失败: {e}")
            return None

    def list_projects(self) -> List[dict]:
        """列出所有项目"""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "updated_at": row["updated_at"],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"列出项目失败: {e}")
            return []

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        try:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除项目失败: {e}")
            return False

    # ── 变更日志 ────────────────────────────────────────────────────────────

    def _log_change(self, entity_type: str, entity_id: str, action: str, data: dict) -> None:
        """记录变更（用于离线同步）"""
        import uuid
        change_id = uuid.uuid4().hex
        entry = ChangeEntry(
            id=change_id,
            timestamp=time.time(),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            data=data,
            client_id=self._client_id,
        )
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT INTO changes (id, timestamp, entity_type, entity_id, action, data, client_id, version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.id, entry.timestamp, entry.entity_type, entry.entity_id,
                    entry.action, json.dumps(entry.data), entry.client_id, entry.version,
                ),
            )
            self._conn.commit()

            # 加入同步队列
            cursor.execute(
                "INSERT OR REPLACE INTO sync_queue (id, change_id, status, created_at) "
                "VALUES (?, ?, 'pending', ?)",
                (uuid.uuid4().hex, entry.id, time.time()),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"记录变更失败: {e}")

    def get_pending_changes(self, limit: int = 100) -> List[ChangeEntry]:
        """获取待同步的变更"""
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """SELECT c.* FROM changes c
                   JOIN sync_queue sq ON c.id = sq.change_id
                   WHERE sq.status = 'pending'
                   ORDER BY c.timestamp ASC
                   LIMIT ?""",
                (limit,),
            )
            return [
                ChangeEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    action=row["action"],
                    data=json.loads(row["data"]),
                    client_id=row["client_id"],
                    version=row["version"],
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"获取待同步变更失败: {e}")
            return []

    def mark_synced(self, change_id: str) -> bool:
        """标记变更已同步"""
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE sync_queue SET status = 'synced' WHERE change_id = ?",
                (change_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"标记同步失败: {e}")
            return False

    def get_sync_stats(self) -> dict:
        """获取同步统计"""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM changes")
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) as pending FROM sync_queue WHERE status = 'pending'")
            pending = cursor.fetchone()["pending"]
            return {"total_changes": total, "pending_sync": pending}
        except Exception:
            return {"total_changes": 0, "pending_sync": 0}

    # ── 冲突解决（LWW - Last Writer Wins）───────────────────────────────────

    def resolve_conflict(self, local_data: dict, remote_data: dict, local_ts: float, remote_ts: float) -> dict:
        """最后写入者获胜冲突解决策略"""
        winner = local_data if local_ts >= remote_ts else remote_data
        loser = remote_data if local_ts >= remote_ts else local_data
        logger.info(
            f"冲突解决: local_ts={local_ts:.3f} remote_ts={remote_ts:.3f} -> "
            f"winner={'local' if local_ts >= remote_ts else 'remote'}"
        )
        return {
            "resolved": winner,
            "strategy": "lww",
            "local_timestamp": local_ts,
            "remote_timestamp": remote_ts,
            "conflict": True,
        }

    def close(self) -> None:
        """关闭存储"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# 全局单例
_store: Optional[OfflineStore] = None


def get_offline_store() -> OfflineStore:
    """获取离线存储单例"""
    global _store
    if _store is None:
        _store = OfflineStore()
    return _store


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    with OfflineStore() as store:
        # 测试保存
        store.save_project("test_001", "测试项目", {"nodes": [], "connections": []})
        print(f"保存成功")

        # 测试加载
        project = store.load_project("test_001")
        print(f"加载: {project['name'] if project else 'None'}")

        # 测试变更日志
        store._log_change("node", "n1", "create", {"type": "math_add"})
        stats = store.get_sync_stats()
        print(f"同步状态: {stats}")

        # 测试冲突解决
        result = store.resolve_conflict(
            {"value": 1}, {"value": 2},
            time.time() - 1, time.time()
        )
        print(f"冲突解决: winner={result['resolved']}, strategy={result['strategy']}")

    print("离线存储测试完成")
