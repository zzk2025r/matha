# -*- coding: utf-8 -*-
"""软件应用开发领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.software_app import (
    http_get, http_post, db_query, db_insert, db_update, db_delete,
    jwt_encode, jwt_decode, bcrypt_hash, bcrypt_verify,
    cache_get, cache_set, cache_invalidate,
    queue_enqueue, queue_dequeue,
)


class TestSoftwareApp(unittest.TestCase):
    def test_http_get(self):
        result = http_get("http://example.com")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["method"], "GET")

    def test_http_post(self):
        result = http_post("http://example.com/api", {"key": "value"})
        self.assertEqual(result["status"], 201)

    def test_db_crud(self):
        from src.domains.software_app import _get_db
        # 使用同一个默认数据库实例
        db = _get_db()
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER)")
        row_id = db_insert("users", {"name": "Alice", "age": 30})
        self.assertGreater(row_id, 0)
        rows = db_query("users")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice")
        self.assertTrue(db_update("users", row_id, {"age": 31}))
        self.assertTrue(db_delete("users", row_id))
        self.assertEqual(len(db_query("users")), 0)

    def test_jwt_encode_decode(self):
        token = jwt_encode({"sub": "1234", "name": "Alice"})
        self.assertIsInstance(token, str)
        decoded = jwt_decode(token)
        self.assertEqual(decoded["sub"], "1234")

    def test_bcrypt_hash_verify(self):
        hashed = bcrypt_hash("secret_password")
        self.assertTrue(bcrypt_verify("secret_password", hashed))
        self.assertFalse(bcrypt_verify("wrong_password", hashed))

    def test_cache(self):
        cache_set("key1", "value1", ttl=60.0)
        self.assertEqual(cache_get("key1"), "value1")
        self.assertTrue(cache_invalidate("key1"))
        self.assertIsNone(cache_get("key1"))

    def test_queue(self):
        queue_enqueue(1)
        queue_enqueue(2)
        queue_enqueue(3)
        self.assertEqual(queue_dequeue(), 1)
        self.assertEqual(queue_dequeue(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
