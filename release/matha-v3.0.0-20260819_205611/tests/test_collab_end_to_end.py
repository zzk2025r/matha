# -*- coding: utf-8 -*-
"""
Matha 协作功能端到端测试（TCP JSON 协议版）。

测试场景：
  1. 多客户端连接同一房间
  2. 用户加入/离开通知
  3. 编辑操作广播
  4. 光标位置同步
  5. 实时聊天消息
  6. Ping/Pong 心跳
  7. 错误处理
"""
import asyncio
import json
import struct
import socket
import threading
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.collab_test_server import CollabServer, test_clients


class TestCollabServerTCP(unittest.TestCase):
    """协作功能 TCP 测试。"""

    PORT = 8767

    @classmethod
    def setUpClass(cls):
        """启动测试服务器。"""
        cls.server = CollabServer(port=cls.PORT, debug=False)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """关闭服务器。"""
        cls.server.stop()

    def _connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.PORT))
        sock.settimeout(5.0)
        return sock

    def _send_recv(self, sock, msg: dict) -> dict:
        body = json.dumps(msg).encode()
        sock.sendall(struct.pack("!I", len(body)) + body)
        # 读取第一个消息
        buf = b""
        while len(buf) < 4:
            chunk = sock.recv(4 - len(buf))
            if not chunk:
                return {"type": "timeout"}
            buf += chunk
        msg_len = struct.unpack("!I", buf[:4])[0]
        while len(buf) < 4 + msg_len:
            chunk = sock.recv(4 + msg_len - len(buf))
            if not chunk:
                break
            buf += chunk
        try:
            return json.loads(buf[4:])
        except json.JSONDecodeError:
            return {"type": "error"}

    def _drain(self, sock) -> list[dict]:
        """读取所有待处理消息。"""
        msgs = []
        sock.settimeout(0.1)
        buf = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 4:
                    msg_len = struct.unpack("!I", buf[:4])[0]
                    if len(buf) < 4 + msg_len:
                        break
                    payload = buf[4:4 + msg_len]
                    buf = buf[4 + msg_len:]
                    try:
                        msgs.append(json.loads(payload.decode()))
                    except Exception:
                        pass
        except socket.timeout:
            pass
        return msgs

    def test_single_connect(self):
        """测试单客户端连接。"""
        sock = self._connect()
        resp = self._send_recv(sock, {"type": "join", "data": {"room": "room1"}})
        self.assertEqual(resp["type"], "join")
        self.assertEqual(resp["data"]["room"], "room1")
        self.assertEqual(resp["data"]["user_count"], 1)
        sock.close()

    def test_two_clients_join_room(self):
        """测试两个客户端加入同一房间。"""
        sock_a = self._connect()
        sock_b = self._connect()

        resp_a = self._send_recv(sock_a, {"type": "join", "data": {"room": "room2"}})
        self.assertEqual(resp_a["type"], "join")
        self.assertEqual(resp_a["data"]["users"], [resp_a["data"]["user_id"]])

        resp_b = self._send_recv(sock_b, {"type": "join", "data": {"room": "room2"}})
        self.assertEqual(resp_b["type"], "join")
        self.assertIn(resp_b["data"]["user_id"], resp_b["data"]["users"])
        self.assertEqual(resp_b["data"]["user_count"], 2)

        sock_a.close()
        sock_b.close()

    def test_edit_broadcast(self):
        """测试编辑操作广播。"""
        sock_a = self._connect()
        sock_b = self._connect()

        self._send_recv(sock_a, {"type": "join", "data": {"room": "room3"}})
        self._send_recv(sock_b, {"type": "join", "data": {"room": "room3"}})

        self._send_recv(sock_a, {
            "type": "edit",
            "data": {"operation": "insert", "text": "Hello"}
        })

        # B 应收到广播
        msgs_b = self._drain(sock_b)
        edit_msgs = [m for m in msgs_b if m.get("type") == "edit"]
        self.assertTrue(len(edit_msgs) > 0)
        self.assertEqual(edit_msgs[0]["data"]["edit"]["text"], "Hello")

        sock_a.close()
        sock_b.close()

    def test_cursor_sync(self):
        """测试光标位置同步。"""
        sock_a = self._connect()
        sock_b = self._connect()

        self._send_recv(sock_a, {"type": "join", "data": {"room": "room4"}})
        self._send_recv(sock_b, {"type": "join", "data": {"room": "room4"}})

        self._send_recv(sock_a, {
            "type": "cursor",
            "data": {"x": 100.0, "y": 200.0}
        })

        msgs_b = self._drain(sock_b)
        cursor_msgs = [m for m in msgs_b if m.get("type") == "cursor"]
        self.assertTrue(len(cursor_msgs) > 0)
        self.assertAlmostEqual(cursor_msgs[0]["data"]["x"], 100.0)
        self.assertAlmostEqual(cursor_msgs[0]["data"]["y"], 200.0)

        sock_a.close()
        sock_b.close()

    def test_chat_message(self):
        """测试聊天消息。"""
        sock_a = self._connect()
        sock_b = self._connect()

        self._send_recv(sock_a, {"type": "join", "data": {"room": "room5"}})
        self._send_recv(sock_b, {"type": "join", "data": {"room": "room5"}})

        self._send_recv(sock_a, {
            "type": "chat",
            "data": {"message": "Hello everyone!"}
        })

        msgs_b = self._drain(sock_b)
        chat_msgs = [m for m in msgs_b if m.get("type") == "chat"]
        self.assertTrue(len(chat_msgs) > 0)
        self.assertEqual(chat_msgs[0]["data"]["message"], "Hello everyone!")

        sock_a.close()
        sock_b.close()

    def test_ping_pong(self):
        """测试 Ping/Pong 心跳。"""
        sock = self._connect()
        self._send_recv(sock, {"type": "join", "data": {"room": "room6"}})

        resp = self._send_recv(sock, {"type": "ping"})
        self.assertEqual(resp["type"], "pong")
        self.assertIn("timestamp", resp["data"])

        sock.close()

    def test_leave_room(self):
        """测试离开房间。"""
        sock_a = self._connect()
        sock_b = self._connect()

        self._send_recv(sock_a, {"type": "join", "data": {"room": "room7"}})
        self._send_recv(sock_b, {"type": "join", "data": {"room": "room7"}})

        # A 离开
        self._send_recv(sock_a, {"type": "leave"})
        sock_a.close()

        # B 应收到用户离开通知
        msgs_b = self._drain(sock_b)
        leave_msgs = [m for m in msgs_b if m.get("type") == "broadcast"]
        self.assertTrue(len(leave_msgs) > 0)
        self.assertEqual(leave_msgs[0]["data"]["event"], "user_left")

        sock_b.close()

    def test_unknown_message(self):
        """测试未知消息类型。"""
        sock = self._connect()
        # 发送未知类型
        body = json.dumps({"type": "unknown_type", "data": {}}).encode()
        sock.sendall(struct.pack("!I", len(body)) + body)

        # 服务器可能不响应或返回错误
        sock.settimeout(1.0)
        try:
            buf = sock.recv(4096)
            if buf:
                msg_len = struct.unpack("!I", buf[:4])[0]
                data = json.loads(buf[4:4 + msg_len])
                self.assertIn(data.get("type"), ("error", "unknown_type"))
        except socket.timeout:
            pass  # 服务器不响应是合理的

        sock.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
