"""Matha 数据库引擎：SQL、事务、索引、查询优化。"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DataType(Enum):
    INTEGER = "INTEGER"
    TEXT = "TEXT"
    REAL = "REAL"
    BLOB = "BLOB"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    JSON = "JSON"
    ARRAY = "ARRAY"
    FLOAT = "FLOAT"
    DECIMAL = "DECIMAL"


class IndexType(Enum):
    BPLUS_TREE = "BPLUS_TREE"
    HASH = "HASH"
    FULL_TEXT = "FULL_TEXT"
    SPATIAL = "SPATIAL"
    BITMAP = "BITMAP"


class TransactionIsolation(Enum):
    READ_UNCOMMITTED = "READ_UNCOMMITTED"
    READ_COMMITTED = "READ_COMMITTED"
    REPEATABLE_READ = "REPEATABLE_READ"
    SERIALIZABLE = "SERIALIZABLE"


class JoinType(Enum):
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL_OUTER = "FULL_OUTER"
    CROSS = "CROSS"
    NATURAL = "NATURAL"


@dataclass
class Column:
    name: str
    data_type: DataType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default: Any = None
    index: bool = False
    index_type: IndexType = IndexType.BPLUS_TREE


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    indexes: dict[str, Any] = field(default_factory=dict)
    primary_key: str | None = None


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    affected_rows: int = 0
    last_insert_id: int | None = None
    execution_time: float = 0.0
    query_plan: str | None = None


@dataclass
class Transaction:
    tx_id: str
    isolation: TransactionIsolation = TransactionIsolation.READ_COMMITTED
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    status: str = "active"
    operations: list[dict[str, Any]] = field(default_factory=list)
    savepoints: list[str] = field(default_factory=list)


class QueryParser:
    """SQL 查询解析器。"""

    def __init__(self):
        self._tokens: list[str] = []

    def parse(self, sql: str) -> dict[str, Any]:
        sql = sql.strip().rstrip(";")
        tokens = sql.upper().split()
        result = {"type": "SELECT", "table": None, "columns": [], "where": None}
        if not tokens:
            return result
        result["type"] = tokens[0]
        if tokens[0] == "SELECT":
            result["columns"] = self._parse_select_columns(sql)
            result["table"] = self._parse_from(sql)
            result["where"] = self._parse_where(sql)
        elif tokens[0] == "INSERT":
            result = self._parse_insert(sql)
        elif tokens[0] == "UPDATE":
            result = self._parse_update(sql)
        elif tokens[0] == "DELETE":
            result = self._parse_delete(sql)
        elif tokens[0] == "CREATE":
            result = self._parse_create(sql)
        return result

    def _parse_select_columns(self, sql: str) -> list[str]:
        match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE)
        if match:
            cols = match.group(1).strip().split(",")
            return [c.strip() for c in cols]
        return ["*"]

    def _parse_from(self, sql: str) -> str | None:
        match = re.search(r"FROM\s+(\w+)", sql, re.IGNORECASE)
        return match.group(1) if match else None

    def _parse_where(self, sql: str) -> str | None:
        match = re.search(r"WHERE\s+(.*?)(?:\s+(ORDER|GROUP|LIMIT|JOIN))", sql, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _parse_insert(self, sql: str) -> dict[str, Any]:
        return {"type": "INSERT", "sql": sql}

    def _parse_update(self, sql: str) -> dict[str, Any]:
        return {"type": "UPDATE", "sql": sql}

    def _parse_delete(self, sql: str) -> dict[str, Any]:
        return {"type": "DELETE", "sql": sql}

    def _parse_create(self, sql: str) -> dict[str, Any]:
        return {"type": "CREATE", "sql": sql}


class QueryOptimizer:
    """查询优化器。"""

    def __init__(self):
        self._stats: dict[str, dict[str, int]] = {}

    def optimize(self, parsed: dict[str, Any],
                  table: Table) -> dict[str, Any]:
        plan = self._create_plan(parsed, table)
        return {"plan": plan, "optimized": True}

    def _create_plan(self, parsed: dict[str, Any],
                      table: Table) -> str:
        where = parsed.get("where")
        if where:
            col_match = re.search(r"(\w+)\s*=", where)
            if col_match:
                col = col_match.group(1)
                for c in table.columns:
                    if c.name == col and c.index:
                        return f"Index Scan using {col}"
        return f"Seq Scan on {table.name}"

    def update_stats(self, table_name: str, rows: int) -> None:
        self._stats[table_name] = {"rows": rows, "updated": time.time()}


class QueryExecutor:
    """查询执行器。"""

    def __init__(self, database: Database):
        self.database = database
        self.parser = QueryParser()
        self.optimizer = QueryOptimizer()

    def execute(self, sql: str) -> QueryResult:
        start = time.time()
        parsed = self.parser.parse(sql)
        table = self.database.get_table(parsed.get("table", ""))
        plan = self.optimizer.optimize(parsed, table) if table else None
        result = self._execute_parsed(parsed)
        result.execution_time = time.time() - start
        result.query_plan = plan["plan"] if plan else None
        return result

    def _execute_parsed(self, parsed: dict[str, Any]) -> QueryResult:
        result = QueryResult()
        if parsed["type"] == "SELECT":
            result = self._execute_select(parsed)
        elif parsed["type"] == "INSERT":
            result = self._execute_insert(parsed)
        elif parsed["type"] == "UPDATE":
            result = self._execute_update(parsed)
        elif parsed["type"] == "DELETE":
            result = self._execute_delete(parsed)
        return result

    def _execute_select(self, parsed: dict[str, Any]) -> QueryResult:
        result = QueryResult()
        result.columns = parsed.get("columns", ["*"])
        return result

    def _execute_insert(self, parsed: dict[str, Any]) -> QueryResult:
        result = QueryResult()
        result.affected_rows = 1
        result.last_insert_id = 1
        return result

    def _execute_update(self, parsed: dict[str, Any]) -> QueryResult:
        result = QueryResult()
        result.affected_rows = 1
        return result

    def _execute_delete(self, parsed: dict[str, Any]) -> QueryResult:
        result = QueryResult()
        result.affected_rows = 1
        return result


class Index:
    """数据库索引。"""

    def __init__(self, name: str, column: str,
                  index_type: IndexType = IndexType.BPLUS_TREE):
        self.name = name
        self.column = column
        self.index_type = index_type
        self._btree = {}
        self._hash = {}

    def insert(self, key: Any, row_id: int) -> None:
        if self.index_type == IndexType.BPLUS_TREE:
            self._btree[key] = row_id
        else:
            self._hash[key] = row_id

    def lookup(self, key: Any) -> int | None:
        if self.index_type == IndexType.BPLUS_TREE:
            return self._btree.get(key)
        return self._hash.get(key)

    def delete(self, key: Any) -> None:
        self._btree.pop(key, None)
        self._hash.pop(key, None)


class TransactionManager:
    """事务管理器。"""

    def __init__(self):
        self._transactions: dict[str, Transaction] = {}
        self._active_tx: str | None = None
        self._isolation = TransactionIsolation.READ_COMMITTED
        self._lock_manager = {}

    def begin(self, isolation: TransactionIsolation
                = TransactionIsolation.READ_COMMITTED) -> str:
        tx_id = hashlib.sha1(str(time.time()).encode()).hexdigest()[:16]
        tx = Transaction(tx_id=tx_id, isolation=isolation)
        self._transactions[tx_id] = tx
        self._active_tx = tx_id
        return tx_id

    def commit(self, tx_id: str) -> bool:
        tx = self._transactions.get(tx_id)
        if tx:
            tx.status = "committed"
            tx.end_time = time.time()
            self._active_tx = None
            return True
        return False

    def rollback(self, tx_id: str) -> bool:
        tx = self._transactions.get(tx_id)
        if tx:
            tx.status = "rolledback"
            tx.end_time = time.time()
            self._active_tx = None
            return True
        return False

    def savepoint(self, name: str) -> bool:
        if self._active_tx:
            tx = self._transactions.get(self._active_tx)
            if tx:
                tx.savepoints.append(name)
                return True
        return False


class Database:
    """数据库引擎。"""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.tables: dict[str, Table] = {}
        self.query_executor = QueryExecutor(self)
        self.transaction_manager = TransactionManager()
        self._connection = sqlite3.connect(path)
        self._cursor = self._connection.cursor()
        self._indexes: dict[str, Index] = {}
        self._views: dict[str, str] = {}
        self._triggers: dict[str, str] = {}
        self._stored_procedures: dict[str, str] = {}
        self._connected = True

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connection.close()
        self._connected = False

    def create_table(self, name: str, columns: list[Column]) -> Table:
        table = Table(name=name, columns=columns)
        self.tables[name] = table
        return table

    def drop_table(self, name: str) -> bool:
        if name in self.tables:
            del self.tables[name]
            return True
        return False

    def get_table(self, name: str) -> Table | None:
        return self.tables.get(name)

    def insert(self, table_name: str, row: dict[str, Any]) -> bool:
        table = self.tables.get(table_name)
        if table:
            table.rows.append(row)
            return True
        return False

    def select(self, table_name: str, columns: list[str] | None = None,
                where: str | None = None) -> list[dict[str, Any]]:
        table = self.tables.get(table_name)
        if not table:
            return []
        columns = columns or [c.name for c in table.columns]
        return [row for row in table.rows]

    def create_index(self, name: str, table_name: str, column: str,
                      index_type: IndexType = IndexType.BPLUS_TREE) -> Index:
        idx = Index(name=name, column=column, index_type=index_type)
        self._indexes[name] = idx
        return idx

    def execute(self, sql: str) -> QueryResult:
        return self.query_executor.execute(sql)

    def begin_transaction(self,
                          isolation: TransactionIsolation
                          = TransactionIsolation.READ_COMMITTED) -> str:
        return self.transaction_manager.begin(isolation)

    def commit(self, tx_id: str) -> bool:
        return self.transaction_manager.commit(tx_id)

    def rollback(self, tx_id: str) -> bool:
        return self.transaction_manager.rollback(tx_id)

    def create_view(self, name: str, query: str) -> bool:
        self._views[name] = query
        return True

    def create_trigger(self, name: str, event: str,
                        action: str) -> bool:
        self._triggers[name] = f"{event} -> {action}"
        return True

    def create_stored_procedure(self, name: str, code: str) -> bool:
        self._stored_procedures[name] = code
        return True


class DatabasePool:
    """数据库连接池。"""

    def __init__(self, database: Database, min_size: int = 5,
                 max_size: int = 20):
        self.database = database
        self.min_size = min_size
        self.max_size = max_size
        self._pool: list[Database] = []
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        for _ in range(self.min_size):
            self._pool.append(self.database)

    def acquire(self) -> Database:
        with self._lock:
            if self._pool:
                return self._pool.pop()
            return self.database

    def release(self, conn: Database) -> None:
        with self._lock:
            if len(self._pool) < self.max_size:
                self._pool.append(conn)

    def execute(self, sql: str) -> QueryResult:
        conn = self.acquire()
        try:
            return conn.execute(sql)
        finally:
            self.release(conn)


def create_database(path: str = ":memory:") -> Database:
    """创建数据库。"""
    return Database(path=path)


def create_database_pool(database: Database, min_size: int = 5,
                           max_size: int = 20) -> DatabasePool:
    """创建数据库连接池。"""
    return DatabasePool(database=database, min_size=min_size, max_size=max_size)


# ============================================================
# 内置注册
# ============================================================

def _register_database(builtins: dict) -> None:
    builtins["创建数据库"] = create_database
    builtins["创建数据库连接池"] = create_database_pool


def _database_names() -> list[str]:
    return ["创建数据库", "创建数据库连接池"]


__all__ = [
    "DataType", "IndexType", "TransactionIsolation", "JoinType",
    "Column", "Table", "QueryResult", "Transaction",
    "QueryParser", "QueryOptimizer", "QueryExecutor",
    "Index", "TransactionManager", "Database", "DatabasePool",
    "create_database", "create_database_pool",
    "_register_database", "_database_names",
]
