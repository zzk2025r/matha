# -*- coding: utf-8 -*-
"""协作功能 IPC 模拟服务器端到端测试（threading 版）。

由于 asyncio 事件循环在不同线程中的调度问题，
使用 threading + socket 来测试协作逻辑。
"""
import json
import struct
import socket
import sys
import threading
import unittest
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ============================================================
# 最小协作服务器（threading 版）
# ============================================================

class ThreadedCollabServer:
    """基于 threading 的协作模拟服务器。"""

    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self._sock = None
        self._threads = {}
        self._lock = threading.Lock()
        self._users = {}
        self._rooms = {}

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self.port = self._sock.getsockname()[1]
        self._sock.listen(5)
        self._server_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._server_thread.start()
        return self

    def _accept_loop(self):
        while True:
            try:
                conn, addr = self._sock.accept()
                t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                t.start()
            except OSError:
                break

    def _handle_client(self, conn, addr):
        user_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._users[user_id] = {"conn": conn, "room": "", "name": f"用户_{user_id}"}

        def send(msg):
            data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
            conn.sendall(struct.pack(">I", len(data)) + data)

        send({"type": "welcome", "user_id": user_id, "name": f"用户_{user_id}"})

        while True:
            try:
                header = conn.recv(4)
            except (ConnectionResetError, OSError):
                break
            if not header:
                break
            if len(header) < 4:
                break
            length = struct.unpack(">I", header)[0]
            payload = b""
            while len(payload) < length:
                chunk = conn.recv(length - len(payload))
                if not chunk:
                    break
                payload += chunk
            if len(payload) < length:
                break
            msg = json.loads(payload.decode())
            self._dispatch(user_id, msg, send)

        with self._lock:
            user = self._users.pop(user_id, None)
            if user and user["room"]:
                room = user["room"]
                self._rooms.get(room, set()).discard(user_id)
        conn.close()

    def _dispatch(self, user_id, msg, send):
        t = msg.get("type", "")
        if t == "join":
            self._handle_join(user_id, msg, send)
        elif t == "leave":
            self._handle_leave(user_id, send)
        elif t == "edit":
            self._handle_edit(user_id, msg, send)
        elif t == "cursor":
            self._handle_cursor(user_id, msg, send)
        elif t == "chat":
            self._handle_chat(user_id, msg, send)
        elif t == "ping":
            send({"type": "pong"})
        else:
            send({"type": "error", "message": f"未知类型: {t}"})

    def _handle_join(self, user_id, msg, send):
        room_id = msg.get("room_id", "default")
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return
            if user["room"]:
                old = user["room"]
                if old in self._rooms:
                    self._rooms[old].discard(user_id)
                    if not self._rooms[old]:
                        del self._rooms[old]
            user["room"] = room_id
            self._rooms.setdefault(room_id, set()).add(user_id)
            members = list(self._rooms[room_id])
            user_list = [{"id": uid, "name": self._users[uid]["name"]} for uid in members if uid in self._users]

        send({"type": "joined", "room_id": room_id, "users": user_list})
        for uid in members:
            if uid != user_id and uid in self._users:
                def _s(u=uid, m=user_list):
                    self._users[u]["conn"].sendall(
                        struct.pack(">I", len(json.dumps({"type": "room_joined", "room_id": room_id, "users": m}).encode()))
                        + json.dumps({"type": "room_joined", "room_id": room_id, "users": m}).encode()
                    )
                threading.Thread(target=_s, daemon=True).start()

    def _handle_leave(self, user_id, send):
        with self._lock:
            user = self._users.get(user_id)
            if not user or not user["room"]:
                return
            room_id = user["room"]
            user["room"] = ""
            self._rooms.get(room_id, set()).discard(user_id)
            if not self._rooms.get(room_id):
                del self._rooms[room_id]
            members = list(self._rooms.get(room_id, set()))
            user_list = [{"id": uid, "name": self._users[uid]["name"]} for uid in members if uid in self._users]

        # 通知其他成员
        for uid in members:
            if uid != user_id and uid in self._users:
                def _s(u=uid, m=user_list, uid2=user_id, n=user["name"]):
                    data = json.dumps({"type": "user_left", "user_id": uid2, "name": n, "users": m}).encode()
                    self._users[u]["conn"].sendall(struct.pack(">I", len(data)) + data)
                threading.Thread(target=_s, daemon=True).start()

    def _handle_edit(self, user_id, msg, send):
        with self._lock:
            user = self._users.get(user_id)
            if not user or not user["room"]:
                send({"type": "error", "message": "请先加入房间"})
                return
            room_id = user["room"]
            members = list(self._rooms.get(room_id, set()))

        op = msg.get("op", {})
        op["id"] = str(uuid.uuid4())
        op["user_id"] = user_id
        data = json.dumps({"type": "edit", "op": op, "user_name": user["name"]}).encode()

        for uid in members:
            if uid != user_id and uid in self._users:
                c = self._users[uid]["conn"]
                try:
                    c.sendall(struct.pack(">I", len(data)) + data)
                except:
                    pass

    def _handle_cursor(self, user_id, msg, send):
        with self._lock:
            user = self._users.get(user_id)
            if not user or not user["room"]:
                return
            room_id = user["room"]
            members = list(self._rooms.get(room_id, set()))
            user["cursor_pos"] = msg.get("position", 0)

        data = json.dumps({
            "type": "cursor_move", "user_id": user_id,
            "user_name": user["name"], "position": user["cursor_pos"],
        }).encode()
        for uid in members:
            if uid != user_id and uid in self._users:
                try:
                    self._users[uid]["conn"].sendall(struct.pack(">I", len(data)) + data)
                except:
                    pass

    def _handle_chat(self, user_id, msg, send):
        with self._lock:
            user = self._users.get(user_id)
            if not user or not user["room"]:
                send({"type": "error", "message": "请先加入房间"})
                return
            room_id = user["room"]
            members = list(self._rooms.get(room_id, set()))

        content = msg.get("content", "")
        data = json.dumps({
            "type": "chat_message",
            "message": {"user_id": user_id, "user_name": user["name"], "content": content},
        }).encode()
        for uid in members:
            if uid != user_id and uid in self._users:
                try:
                    self._users[uid]["conn"].sendall(struct.pack(">I", len(data)) + data)
                except:
                    pass

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except:
                pass


# ============================================================
# 简单 TCP 客户端
# ============================================================

class TCPClient:
    def __init__(self, sock):
        self.sock = sock
        self.closed = False

    def send(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.sock.sendall(struct.pack(">I", len(payload)) + payload)

    def recv(self, timeout=3):
        self.sock.settimeout(timeout)
        try:
            header = self.sock.recv(4)
            if not header or len(header) < 4:
                return None
            length = struct.unpack(">I", header)[0]
            payload = b""
            while len(payload) < length:
                chunk = self.sock.recv(length - len(payload))
                if not chunk:
                    break
                payload += chunk
            if len(payload) < length:
                return None
            return json.loads(payload.decode())
        except (socket.timeout, ConnectionResetError, OSError):
            return None

    def close(self):
        self.closed = True
        try:
            self.sock.close()
        except:
            pass


# ============================================================
# 测试
# ============================================================

class TestCollabServer(unittest.TestCase):
    def setUp(self):
        self.server = ThreadedCollabServer().start()
        self.addCleanup(self.server.close)
        time.sleep(0.1)

    def _connect(self):
        sock = socket.create_connection(("127.0.0.1", self.server.port), timeout=3)
        client = TCPClient(sock)
        msg = client.recv(timeout=3)
        self.assertIsNotNone(msg, "未能收到欢迎消息")
        self.assertEqual(msg["type"], "welcome")
        return client

    def test_single_connect(self):
        client = self._connect()
        # _connect 已经验证了 welcome 消息
        client.close()

    def test_two_clients_join_room(self):
        c1 = self._connect()
        c2 = self._connect()

        c1.send({"type": "join", "room_id": "room_A"})
        r1 = c1.recv(timeout=3)
        self.assertEqual(r1["type"], "joined")

        c2.send({"type": "join", "room_id": "room_A"})
        r2 = c2.recv(timeout=3)
        self.assertEqual(r2["type"], "joined")

        r1b = c1.recv(timeout=3)
        self.assertEqual(r1b["type"], "room_joined")
        self.assertEqual(len(r1b["users"]), 2)

        c1.close()
        c2.close()

    def test_edit_broadcast(self):
        c1 = self._connect()
        c2 = self._connect()

        c1.send({"type": "join", "room_id": "room_edit"})
        c1.recv(timeout=3)
        c2.send({"type": "join", "room_id": "room_edit"})
        c2.recv(timeout=3)
        c1.recv(timeout=3)

        c1.send({"type": "edit", "op": {"action": "insert", "text": "Hello", "pos": 0}})
        r = c2.recv(timeout=3)
        self.assertEqual(r["type"], "edit")
        self.assertEqual(r["op"]["text"], "Hello")

        c1.close()
        c2.close()

    def test_cursor_sync(self):
        c1 = self._connect()
        c2 = self._connect()

        c1.send({"type": "join", "room_id": "room_cursor"})
        c1.recv(timeout=3)
        c2.send({"type": "join", "room_id": "room_cursor"})
        c2.recv(timeout=3)
        c1.recv(timeout=3)

        c1.send({"type": "cursor", "position": 42})
        r = c2.recv(timeout=3)
        self.assertEqual(r["type"], "cursor_move")
        self.assertEqual(r["position"], 42)

        c1.close()
        c2.close()

    def test_chat_message(self):
        c1 = self._connect()
        c2 = self._connect()

        c1.send({"type": "join", "room_id": "room_chat"})
        c1.recv(timeout=3)
        c2.send({"type": "join", "room_id": "room_chat"})
        c2.recv(timeout=3)
        c1.recv(timeout=3)

        c1.send({"type": "chat", "content": "大家好！"})
        r = c2.recv(timeout=3)
        self.assertEqual(r["type"], "chat_message")
        self.assertEqual(r["message"]["content"], "大家好！")

        c1.close()
        c2.close()

    def test_ping_pong(self):
        client = self._connect()
        client.send({"type": "ping"})
        r = client.recv(timeout=3)
        self.assertEqual(r["type"], "pong")
        client.close()

    def test_leave_room(self):
        c1 = self._connect()
        c2 = self._connect()

        c1.send({"type": "join", "room_id": "room_leave"})
        r = c1.recv(timeout=3)
        self.assertEqual(r["type"], "joined")
        c2.send({"type": "join", "room_id": "room_leave"})
        r = c2.recv(timeout=3)
        self.assertEqual(r["type"], "joined")
        r = c1.recv(timeout=3)
        self.assertEqual(r["type"], "room_joined")

        c1.send({"type": "leave"})
        # c2 应该收到 user_left（可能先收到 room_joined 的后续消息）
        for _ in range(3):
            r = c2.recv(timeout=2)
            if r and r["type"] in ("user_left", "room_joined"):
                if r["type"] == "user_left":
                    break
        self.assertIsNotNone(r, "未能收到 leave 响应")
        self.assertEqual(r["type"], "user_left")

        c1.close()
        c2.close()

    def test_unknown_message(self):
        client = self._connect()
        client.send({"type": "unknown_type"})
        r = client.recv(timeout=3)
        self.assertEqual(r["type"], "error")
        client.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
