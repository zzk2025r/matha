# -*- coding: utf-8 -*-
"""
Matha 协作功能 WebSocket 测试服务器（TCP JSON 协议版）。

使用 threading + TCP 协议实现（无需 websockets 库）。

协议格式：
  4字节 big-endian 长度前缀 + JSON body

消息类型：
  join  | leave | edit | cursor | chat | ping | pong | error | broadcast

用法：
    python tests/collab_test_server.py [--port 8765] [--debug]
"""
import asyncio
import json
import struct
import threading
import time
import argparse
import logging
import socket
import sys
from typing import Optional
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("collab_server")


# ============================================================
# 数据结构
# ============================================================

@dataclass
class User:
    ws: Optional[socket.socket] = None
    user_id: str = ""
    room: str = "default"
    cursor_x: float = 0.0
    cursor_y: float = 0.0
    joined_at: float = field(default_factory=time.time)
    locked: bool = field(default_factory=threading.Lock)


@dataclass
class Room:
    room_id: str = ""
    users: dict[str, User] = field(default_factory=dict)
    edit_log: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


# ============================================================
# 服务器
# ============================================================

class CollabServer:
    """TCP JSON 协作服务器。"""

    def __init__(self, port: int = 8765, debug: bool = False):
        self._port = port
        self._debug = debug
        self._rooms: dict[str, Room] = {}
        self._users: dict[str, User] = {}
        self._user_counter = 0
        self._server_socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._running = False
        self._start_time = time.time()

    def _log(self, msg: str) -> None:
        if self._debug:
            logger.debug(msg)
        else:
            logger.info(msg)

    def _next_user_id(self) -> str:
        self._user_counter += 1
        return f"user_{self._user_counter:03d}"

    def _send(self, sock: socket.socket, data: dict) -> None:
        """发送 JSON 消息（带 4 字节长度前缀）。"""
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            sock.sendall(struct.pack("!I", len(body)) + body)
        except (BrokenPipeError, OSError) as e:
            self._log(f"发送失败: {e}")

    def _broadcast(self, room: Room, sender_id: str, msg: dict, exclude: Optional[str] = None) -> None:
        """广播消息给同房间其他用户。"""
        for uid, user in room.users.items():
            if uid != sender_id and uid != exclude and user.ws:
                self._send(user.ws, msg)

    def _handle_join(self, sock: socket.socket, user_id: str, room_id: str) -> None:
        """处理加入房间。"""
        with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = Room(room_id=room_id)
                self._log(f"房间 {room_id} 已创建")
            room = self._rooms[room_id]
            user = User(ws=sock, user_id=user_id, room=room_id)
            self._users[user_id] = user
            room.users[user_id] = user

        # 广播加入通知
        self._broadcast(room, user_id, {
            "type": "broadcast",
            "data": {"event": "user_joined", "user_id": user_id}
        })

        # 发送当前用户列表
        self._send(sock, {
            "type": "join",
            "data": {
                "user_id": user_id,
                "room": room_id,
                "users": list(room.users.keys()),
                "user_count": len(room.users),
            }
        })
        self._log(f"用户 {user_id} 加入房间 {room_id} (共 {len(room.users)} 人)")

    def _handle_leave(self, user_id: str) -> None:
        """处理离开房间。"""
        with self._lock:
            user = self._users.pop(user_id, None)
            if not user:
                return
            room = self._rooms.get(user.room)
            if room:
                room.users.pop(user_id, None)
                self._broadcast(room, user_id, {
                    "type": "broadcast",
                    "data": {"event": "user_left", "user_id": user_id}
                })
                if not room.users:
                    del self._rooms[user.room]
                    self._log(f"房间 {user.room} 已销毁")
        self._log(f"用户 {user_id} 离开")

    def _handle_edit(self, sock: socket.socket, user_id: str, edit: dict) -> None:
        """处理编辑操作。"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return
            room = self._rooms.get(user.room)
            if not room:
                return

        entry = {"user_id": user_id, "edit": edit, "timestamp": time.time()}
        with self._lock:
            room.edit_log.append(entry)
            if len(room.edit_log) > 100:
                room.edit_log = room.edit_log[-100:]
        self._broadcast(room, user_id, {"type": "edit", "data": entry})

    def _handle_cursor(self, sock: socket.socket, user_id: str, x: float, y: float) -> None:
        """处理光标位置。"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return
            user.cursor_x = x
            user.cursor_y = y
            room = self._rooms.get(user.room)
            if not room:
                return
        self._broadcast(room, user_id, {
            "type": "cursor",
            "data": {"user_id": user_id, "x": x, "y": y}
        })

    def _handle_chat(self, sock: socket.socket, user_id: str, message: str) -> None:
        """处理聊天消息。"""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return
            room = self._rooms.get(user.room)
            if not room:
                return
        self._broadcast(room, user_id, {
            "type": "chat",
            "data": {"user_id": user_id, "message": message, "time": time.time()}
        })

    def _handle_ping(self, sock: socket.socket, user_id: str) -> None:
        self._send(sock, {
            "type": "pong",
            "data": {"timestamp": time.time(), "user_id": user_id}
        })

    def _handle_message(self, sock: socket.socket, user_id: str, data: dict) -> None:
        """消息分发。"""
        msg_type = data.get("type", "")
        msg_data = data.get("data", {})

        if msg_type == "join":
            self._handle_join(sock, user_id, msg_data.get("room", "default"))
        elif msg_type == "leave":
            self._handle_leave(user_id)
        elif msg_type == "edit":
            self._handle_edit(sock, user_id, msg_data)
        elif msg_type == "cursor":
            self._handle_cursor(sock, user_id, msg_data.get("x", 0), msg_data.get("y", 0))
        elif msg_type == "chat":
            self._handle_chat(sock, user_id, msg_data.get("message", ""))
        elif msg_type == "ping":
            self._handle_ping(sock, user_id)
        else:
            self._log(f"未知消息: {msg_type}")

    def _handle_client(self, sock: socket.socket, addr: tuple) -> None:
        """处理单个客户端连接。"""
        user_id = self._next_user_id()
        self._log(f"新连接: {user_id} from {addr}")

        try:
            sock.settimeout(30.0)
            buffer = b""
            while self._running:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    while len(buffer) >= 4:
                        msg_len = struct.unpack("!I", buffer[:4])[0]
                        if len(buffer) < 4 + msg_len:
                            break
                        payload = buffer[4:4 + msg_len]
                        buffer = buffer[4 + msg_len:]
                        try:
                            data = json.loads(payload.decode("utf-8"))
                            self._handle_message(sock, user_id, data)
                        except json.JSONDecodeError:
                            self._send(sock, {"type": "error", "data": {"message": "Invalid JSON"}})
                except socket.timeout:
                    continue
                except BrokenPipeError:
                    break
        except Exception as e:
            self._log(f"连接错误 {user_id}: {e}")
        finally:
            self._handle_leave(user_id)
            try:
                sock.close()
            except Exception:
                pass
            self._log(f"连接关闭: {user_id}")

    def start(self) -> None:
        """启动服务器。"""
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("0.0.0.0", self._port))
        self._server_socket.listen(50)
        self._log(f"服务器启动于 ws://localhost:{self._port}")

        try:
            while self._running:
                try:
                    sock, addr = self._server_socket.accept()
                    t = threading.Thread(target=self._handle_client, args=(sock, addr), daemon=True)
                    t.start()
                except socket.timeout:
                    continue
        except Exception as e:
            self._log(f"服务器错误: {e}")
        finally:
            self.stop()

    def stop(self) -> None:
        """停止服务器。"""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        stats = self.get_stats()
        self._log(f"服务器已停止 (运行时间: {stats['uptime']:.1f}s)")

    def get_stats(self) -> dict:
        return {
            "uptime": time.time() - self._start_time,
            "total_users": len(self._users),
            "active_rooms": len(self._rooms),
        }


# ============================================================
# 测试客户端
# ============================================================

def test_clients(port: int = 8765, count: int = 3) -> None:
    """运行测试客户端。"""
    import time as _time

    def client_task(client_id: str):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))
        sock.settimeout(10.0)

        def send(data: dict) -> dict:
            body = json.dumps(data).encode()
            sock.sendall(struct.pack("!I", len(body)) + body)
            # 读取响应
            buf = b""
            while len(buf) < 4:
                chunk = sock.recv(4 - len(buf))
                if not chunk:
                    break
                buf += chunk
            if len(buf) < 4:
                return {"type": "timeout"}
            msg_len = struct.unpack("!I", buf[:4])[0]
            while len(buf) < 4 + msg_len:
                chunk = sock.recv(4 + msg_len - len(buf))
                if not chunk:
                    break
                buf += chunk
            return json.loads(buf[4:])

        # 加入房间
        resp = send({"type": "join", "data": {"room": "test-room"}})
        print(f"[{client_id}] join: {resp}")

        # 发送聊天
        send({"type": "chat", "data": {"message": f"Hello from {client_id}!"}})

        # 模拟光标
        for i in range(3):
            send({"type": "cursor", "data": {"x": i * 10.0, "y": i * 5.0}})
            _time.sleep(0.05)

        # Ping
        pong = send({"type": "ping"})
        print(f"[{client_id}] pong: {pong}")

        # 离开
        send({"type": "leave"})
        sock.close()
        print(f"[{client_id}] done")

    threads = []
    for i in range(count):
        t = threading.Thread(target=client_task, args=(f"client_{chr(65+i)}",), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.1)

    for t in threads:
        t.join(timeout=5.0)
    print("测试完成 ✓")


# ============================================================
# 主函数
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Matha 协作测试服务器")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--test", action="store_true", help="运行测试客户端")
    args = parser.parse_args()

    server = CollabServer(port=args.port, debug=args.debug)

    if args.test:
        # 启动服务器线程
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.5)  # 等待服务器启动
        test_clients(args.port)
        server.stop()
        stats = server.get_stats()
        print(f"服务器统计: {stats}")
        return

    server.start()


if __name__ == "__main__":
    main()
