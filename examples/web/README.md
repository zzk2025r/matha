# Web 开发示例

## 1. 简单 HTTP 服务器

```matha
# 创建 Web 服务器
server = create_web_server(host="127.0.0.1", port=8080)

# 处理请求
app = create_web_app()
add_route(app, "/", lambda req: "Hello, World!")
add_route(app, "/api/data", lambda req: json_dumps({"data": [1, 2, 3]}))

# 启动服务器
start_server(server)
```

## 2. WebSocket 聊天

```matha
# 创建 WebSocket 服务器
ws_server = create_websocket_server()

# 处理连接
on_connect(ws_server, lambda client: print("Client connected"))
on_message(ws_server, lambda client, msg: broadcast(ws_server, msg))
on_disconnect(ws_server, lambda client: print("Client disconnected"))
```

## 3. REST API

```matha
# 创建 API 应用
app = create_web_app()

# GET /api/users
add_route(app, "/api/users", lambda req: get_users())

# POST /api/users
add_route(app, "/api/users", lambda req: create_user(req.body))

# PUT /api/users/:id
add_route(app, "/api/users/:id", lambda req: update_user(req.params.id, req.body))

# DELETE /api/users/:id
add_route(app, "/api/users/:id", lambda req: delete_user(req.params.id))
```

## 4. 数据库集成

```matha
# 创建数据库
db = create_database()
connect(db, "sqlite:///mydb.db")

# 查询
result = query(db, "SELECT * FROM users WHERE age > 18")

# 插入
insert(db, "users", {"name": "Alice", "age": 30})
```

## 5. 静态文件服务

```matha
# 创建 Web 服务器
server = create_web_server()
add_static_files(server, "public/")
```

---

*Matha v4.5 | Web 开发示例*