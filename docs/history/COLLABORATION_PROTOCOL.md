# Matha 协作功能集成文档

> 版本：v1.0  
> 生成日期：2026-08-19  
> 测试状态：✅ 8/8 通过

---

## 一、协议概述

### 1.1 消息格式

```
+------------------+------------------+
|  Length (4 bytes) |  JSON Payload    |
|  Big-Endian       |  UTF-8 Encoded   |
+------------------+------------------+
```

- **Length**：4 字节无符号整数（`struct.pack(">I", len(payload))`），表示 JSON body 的字节数
- **JSON Payload**：标准 JSON 对象，包含 `type` 字段标识消息类型

### 1.2 字节序

所有多字节整数使用 **Big-Endian** 编码（网络字节序），确保跨平台兼容性。

---

## 二、消息类型详解

### 2.1 服务端 → 客户端（下行消息）

| 类型 | 说明 | 关键字段 |
|------|------|----------|
| `welcome` | 连接成功后发送 | `user_id`, `name`, `color`, `message` |
| `joined` | 加入房间确认 | `room_id`, `users` |
| `room_joined` | 房间广播（通知其他人） | `room_id`, `users`, `state`, `message` |
| `edit` | 编辑操作广播 | `op`, `user_name`, `user_color` |
| `cursor_move` | 光标位置广播 | `user_id`, `user_name`, `user_color`, `position` |
| `chat_message` | 聊天消息广播 | `message`（含 user_id/user_name/content） |
| `pong` | 心跳响应 | `timestamp` |
| `user_left` | 用户离开广播 | `user_id`, `name`, `users` |
| `user_disconnected` | 连接断开广播 | `user_id`, `name`, `users` |
| `error` | 错误响应 | `message` |

### 2.2 客户端 → 服务端（上行消息）

| 类型 | 说明 | 关键字段 |
|------|------|----------|
| `join` | 加入房间 | `room_id` |
| `leave` | 离开房间 | — |
| `edit` | 发送编辑操作 | `op`（含 action/text/pos 等） |
| `cursor` | 更新光标位置 | `position` |
| `chat` | 发送聊天消息 | `content` |
| `ping` | 心跳请求 | — |

---

## 三、消息示例

### 3.1 连接握手

```
← [welcome] {"type":"welcome","user_id":"a1b2c3d4","name":"用户_a1b2c3d4","color":"#4a90d9","message":"欢迎 用户_a1b2c3d4！连接成功。"}
```

### 3.2 加入房间

```
→ [join]     {"type":"join","room_id":"room_A"}
← [joined]   {"type":"joined","room_id":"room_A","users":[{"id":"a1b2c3d4","name":"用户_a1b2c3d4"}]}
← [room_joined] {"type":"room_joined","room_id":"room_A","users":[...],"state":"","message":"用户_a1b2c3d4 加入了房间"}
```

### 3.3 编辑操作

```
→ [edit]     {"type":"edit","op":{"action":"insert","text":"Hello","pos":0}}
← [edit]     {"type":"edit","op":{"id":"uuid","action":"insert","text":"Hello","pos":0,"user_id":"a1b2c3d4","timestamp":"..."},"user_name":"用户_a1b2c3d4","user_color":"#4a90d9"}
```

### 3.4 光标同步

```
→ [cursor]   {"type":"cursor","position":42}
← [cursor_move] {"type":"cursor_move","user_id":"a1b2c3d4","user_name":"用户_a1b2c3d4","user_color":"#4a90d9","position":42}
```

### 3.5 聊天消息

```
→ [chat]     {"type":"chat","content":"大家好！"}
← [chat_message] {"type":"chat_message","message":{"id":"uuid","room":"room_A","user_id":"a1b2c3d4","user_name":"用户_a1b2c3d4","content":"大家好！","timestamp":"..."}}
```

### 3.6 心跳

```
→ [ping]     {"type":"ping"}
← [pong]     {"type":"pong","timestamp":"..."}
```

### 3.7 离开房间

```
→ [leave]    {"type":"leave"}
← [user_left] {"type":"user_left","user_id":"a1b2c3d4","name":"用户_a1b2c3d4","users":[...]}
```

---

## 四、房间模型

### 4.1 数据结构

```python
class User:
    id: str          # UUID 前 8 位
    name: str        # 显示名称（如 "用户_a1b2c3d4"）
    room: str        # 当前所在房间 ID
    cursor_pos: int  # 光标位置
    color: str       # 光标颜色（随机生成）
    connected_at: str # 连接时间 ISO 格式

class ChatMessage:
    id: str
    room: str
    user_id: str
    user_name: str
    content: str
    timestamp: str
```

### 4.2 房间状态

```python
rooms: Dict[str, Set[str]]     # room_id → 用户ID集合
room_state: Dict[str, str]     # room_id → 文档内容
chats: Dict[str, List[ChatMessage]]  # room_id → 消息历史
```

### 4.3 用户加入流程

```
1. 用户发送 join(room_id)
2. 服务端：
   a. 离开旧房间（如果有）
   b. 加入新房间（创建若不存在）
   c. 发送 joined 确认给本人
   d. 广播 room_joined 给其他成员
3. 用户收到 joined 和 room_joined 消息
```

### 4.4 用户离开流程

```
1. 用户发送 leave
2. 服务端：
   a. 从房间移除用户
   b. 若房间空则删除房间
   c. 广播 user_left 给剩余成员
3. 用户关闭连接
```

---

## 五、并发模型

### 5.1 线程架构

```
┌─────────────────────────────────────────┐
│           Main Thread                   │
│  ┌─────────────────────────────────┐   │
│  │  Accept Loop (socket.accept)    │   │
│  │  └─→ 为每个连接创建新线程       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Room Broadcast Threads         │   │
│  │  └─→ 广播消息给房间成员         │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 5.2 线程安全

- 所有共享状态（users, rooms）通过 `threading.Lock()` 保护
- 广播操作在锁外执行，避免阻塞其他操作
- 使用 `threading.Thread(daemon=True)` 确保子线程不阻止进程退出

---

## 六、测试用例

### 6.1 测试环境

```python
# 测试服务器
server = ThreadedCollabServer().start()
# 端口：动态分配（find_free_port）
# 协议：JSON over TCP（4字节长度前缀）
```

### 6.2 测试矩阵

| 测试用例 | 描述 | 预期行为 | 状态 |
|----------|------|----------|------|
| `test_single_connect` | 单客户端连接 | 收到 welcome 消息 | ✅ |
| `test_two_clients_join_room` | 两个客户端加入同一房间 | 双方收到 joined，一人收到 room_joined | ✅ |
| `test_edit_broadcast` | 编辑操作广播 | 另一方收到 edit 消息，内容一致 | ✅ |
| `test_cursor_sync` | 光标位置同步 | 另一方收到 cursor_move，position=42 | ✅ |
| `test_chat_message` | 聊天消息广播 | 另一方收到 chat_message，content 一致 | ✅ |
| `test_ping_pong` | 心跳机制 | 收到 pong 响应 | ✅ |
| `test_leave_room` | 离开房间广播 | 另一方收到 user_left | ✅ |
| `test_unknown_message` | 未知消息类型 | 收到 error 响应 | ✅ |

### 6.3 测试结果

```
Ran 8 tests in 0.860s
OK
```

---

## 七、客户端接入指南

### 7.1 Python 客户端

```python
import asyncio, json, struct

async def connect(host, port):
    reader, writer = await asyncio.open_connection(host, port)

    async def send(data):
        payload = json.dumps(data).encode()
        writer.write(struct.pack(">I", len(payload)) + payload)
        await writer.drain()

    async def recv():
        header = await reader.readexactly(4)
        length = struct.unpack(">I", header)[0]
        payload = b""
        while len(payload) < length:
            chunk = await reader.readexactly(length - len(payload))
            payload += chunk
        return json.loads(payload.decode())

    # 接收欢迎消息
    msg = await recv()
    assert msg["type"] == "welcome"
    user_id = msg["user_id"]

    # 加入房间
    await send({"type": "join", "room_id": "room_A"})
    joined = await recv()
    assert joined["type"] == "joined"

    # 发送编辑
    await send({"type": "edit", "op": {"action": "insert", "text": "Hello", "pos": 0}})

    # 接收广播
    edit_msg = await recv()
    assert edit_msg["type"] == "edit"
    assert edit_msg["op"]["text"] == "Hello"

    writer.close()
```

### 7.2 JavaScript 客户端（Node.js）

```javascript
const net = require('net');
const client = net.createConnection(8765, '127.0.0.1');

let buffer = Buffer.alloc(0);

client.on('data', (data) => {
    buffer = Buffer.concat([buffer, data]);
    while (buffer.length >= 4) {
        const length = buffer.readUInt32BE(0);
        if (buffer.length < 4 + length) break;
        const payload = buffer.slice(4, 4 + length);
        buffer = buffer.slice(4 + length);
        const msg = JSON.parse(payload.toString());
        console.log('Received:', msg.type);
    }
});

client.on('connect', () => {
    // 等待 welcome
});

function send(msg) {
    const payload = Buffer.from(JSON.stringify(msg));
    const header = Buffer.alloc(4);
    header.writeUInt32BE(payload.length, 0);
    client.write(Buffer.concat([header, payload]));
}

send({ type: 'join', room_id: 'room_A' });
```

---

## 八、故障排查

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 连接被拒绝 | 服务器未启动 | 先启动服务器再连接客户端 |
| 消息不完整 | TCP 粘包/拆包 | 确保完整读取 4 字节长度前缀后再读 payload |
| JSON 解析失败 | 编码不一致 | 确保使用 UTF-8 编码 |
| 收不到广播 | 未加入房间 | 先发送 join 消息加入房间 |
| 连接断开 | 客户端超时 | 定期发送 ping 保持连接 |

### 8.2 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查服务器状态
import requests
resp = requests.get("http://localhost:8766/api/rooms")
print(resp.json())
```

---

## 九、扩展方向

### 9.1 待实现功能

- [ ] 真实 WebSocket 后端（替代 TCP）
- [ ] 光标位置插值（平滑移动）
- [ ] 文档冲突解决（CRDT）
- [ ] 历史记录回滚
- [ ] 权限系统（owner/editor/viewer）
- [ ] 文件分享
- [ ] 语音/视频通话

### 9.2 性能优化

- 批量消息合并
- 消息压缩（gzip）
- 连接池管理
- 房间分片

---

*文档生成完毕。所有测试通过，协议实现稳定。*
