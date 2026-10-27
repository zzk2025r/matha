# Matha 作为 Trae 自定义模型配置指南

> **版本：** v1.0  
> **更新日期：** 2026-09-11  
> **适用版本：** Matha v4.5.0+  
> **依赖：** Python 3.10+，`requests`（可选，用于测试）

---

## 一、概述

Matha 内置了 OpenAI 兼容的 API 服务（`src/openai_compat_server.py`），可将 Matha 的 AI 计算能力暴露为标准 OpenAI 接口，从而作为 **Trae 自定义模型** 使用。

支持的接口：
- `GET /v1/models` — 模型列表
- `POST /v1/chat/completions` — 对话补全（支持非流式 + 流式 SSE）
- `POST /v1/completions` — 文本补全

---

## 二、启动 Matha API 服务

### 2.1 一键启动（Windows）

双击项目根目录下的 `start_matha_server.bat`，或在命令行执行：

```powershell
cd d:\trae
.\start_matha_server.bat
```

### 2.2 命令行启动

```powershell
cd d:\trae
python -m src.openai_compat_server --port 8787
```

可选参数：
- `--host` — 监听地址，默认 `0.0.0.0`
- `--port` — 监听端口，默认 `8787`

### 2.3 启动成功标志

```
Matha OpenAI 兼容服务启动: http://0.0.0.0:8787/v1
  模型名: matha
  设备: Windows AMD64 | CPU: 4 逻辑核 / 4 物理核 | 内存: 16163 MB
推荐: 进程数=3, 线程数=16, 最大工作数=3
  说明: AI 助手调用经锁串行化（解释器非线程安全），HTTP 请求并发处理
  Trae 自定义模型配置:
    接口地址: http://localhost:8787/v1
    模型名:   matha
    API Key:  任意非空字符串
```

> 启动时会自动检测设备性能并显示推荐的线程/进程数（详见「六、自适应多线程」）。

---

## 三、Trae 自定义模型配置步骤

### 3.1 打开模型设置

1. 打开 Trae IDE
2. 点击左下角齿轮图标 **⚙️ 设置**
3. 左侧菜单选择 **模型**
4. 点击 **添加模型** 按钮

### 3.2 选择自定义配置

在弹出的窗口中，切换到 **「自定义配置」** 标签页。

### 3.3 填写配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| **API 格式** | `OpenAI Chat Completions 格式` | 必选 |
| **自定义请求地址** | `http://localhost:8787/v1` | **关闭**「完整 URL」开关 |
| **模型 ID** | `matha` | 与服务端模型名一致 |
| **模型展示名称** | `Matha`（可自定义） | Trae 中显示的名称 |
| **API 密钥** | `matha-local` | 任意非空字符串，本地无需鉴权 |

> ⚠️ **关键注意**：「自定义请求地址」填基础地址 `http://localhost:8787/v1`，**不要**带 `/chat/completions` 后缀。Trae 会自动拼接路径。务必关闭「完整 URL」开关。

### 3.4 保存并使用

1. 点击 **保存**
2. 在对话框右下角的模型切换器中选择 **Matha**
3. 开始对话

---

## 四、验证配置是否生效

### 4.1 验证服务端

```powershell
# 检查模型列表
curl http://localhost:8787/v1/models

# 测试对话
curl -X POST http://localhost:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer matha-local" `
  -d '{\"model\": \"matha\", \"messages\": [{\"role\": \"user\", \"content\": \"计算 1 到 10 的和\"}]}'
```

### 4.2 Python 验证脚本

```python
import requests

base = "http://localhost:8787/v1"
headers = {"Authorization": "Bearer matha-local"}

# 模型列表
models = requests.get(f"{base}/models", headers=headers).json()
print("模型:", [m["id"] for m in models["data"]])

# 对话
r = requests.post(f"{base}/chat/completions", headers=headers, json={
    "model": "matha",
    "messages": [{"role": "user", "content": "计算 1 到 10 的和"}]
}).json()
print("回复:", r["choices"][0]["message"]["content"])
```

### 4.3 在 Trae 中测试

在 Trae 对话框选择 Matha 模型后，输入：

```
计算 1 到 100 的和
```

预期回复：
```
✅ 计算结果：101.0

📋 分解步骤：
  1. 计算 1.0 + 100.0
```

---

## 五、支持的功能

### 5.1 自然语言数学计算

Matha AI 助手可解析自然语言数学指令，例如：
- `计算 1 到 100 的和` → 101
- `10 的阶乘` → 3628800
- `求 144 的平方根` → 12
- `解方程 x + 5 = 12` → x = 7

### 5.2 多轮对话

支持上下文连续对话：

```
用户: 5 + 3
助手: 8
用户: 再乘以 2
助手: 16
```

### 5.3 流式响应

Trae 可使用流式输出（SSE），Matha 服务已支持：

```python
r = requests.post(f"{base}/chat/completions", json={
    "model": "matha", "stream": True,
    "messages": [{"role": "user", "content": "3 的阶乘"}]
}, stream=True)
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data: "):
        print(line[6:])
```

---

## 六、自适应多线程配置

Matha 会根据设备性能自动调整线程/进程数，无需手动配置。

### 6.1 自动检测

启动服务时会显示：

```
设备: Windows AMD64 | CPU: 4 逻辑核 / 4 物理核 | 内存: 16163 MB
推荐: 进程数=3, 线程数=16, 最大工作数=3
```

### 6.2 自适应规则

| 设备规格 | 进程数 | 线程数 |
|----------|--------|--------|
| ≤2 物理核 | 1 | `cpu_cores × 2` |
| ≤4 物理核 | `物理核 - 1` | `cpu_cores × 4` |
| >4 物理核 | `物理核 - 1` | `cpu_cores × 4` |

> 内存 < 2GB 时线程数限制为 `cpu_cores × 2`，避免 OOM。

### 6.3 手动覆盖（环境变量）

如需强制指定并行度，设置以下环境变量后再启动服务：

```powershell
# Windows PowerShell
$env:MATHA_PROCESS_WORKERS = "2"
$env:MATHA_THREAD_WORKERS = "8"
python -m src.openai_compat_server --port 8787
```

| 环境变量 | 说明 |
|----------|------|
| `MATHA_PROCESS_WORKERS` | 进程池大小（CPU 密集型任务） |
| `MATHA_THREAD_WORKERS` | 线程池大小（IO 密集型任务） |
| `MATHA_CPU_CORES` | 覆盖检测的逻辑核心数 |
| `MATHA_MAX_WORKERS` | 最大工作进程数 |

---

## 七、常见问题

### Q1: Trae 连接超时

**原因**：Matha 服务未启动或端口被占用。

**解决**：
1. 确认服务已启动：`curl http://localhost:8787/v1/models`
2. 检查端口占用：`netstat -ano | findstr 8787`
3. 更换端口：`python -m src.openai_compat_server --port 8788`

### Q2: 「期望 200 状态码」错误

**原因**：Trae 配置的请求地址不正确。

**解决**：
- 地址填 `http://localhost:8787/v1`（不要带 `/chat/completions`）
- 关闭「完整 URL」开关

### Q3: 响应慢或卡住

**原因**：解释器非线程安全，AI 助手调用经锁串行化。

**解决**：
- 这是预期行为，单次请求正常应在 1 秒内返回
- 如持续超时，检查是否有大量并发请求

### Q4: 如何后台运行服务

**Windows**：
```powershell
# 使用 Start-Process 后台启动
Start-Process python -ArgumentList "-m", "src.openai_compat_server", "--port", "8787" -WindowStyle Hidden
```

**Linux/macOS**：
```bash
nohup python -m src.openai_compat_server --port 8787 &
```

---

## 八、架构说明

```
┌─────────────────────────────────────────────────┐
│                   Trae IDE                       │
│  ┌───────────────────────────────────────────┐  │
│  │  自定义模型 (matha)                        │  │
│  │  API: http://localhost:8787/v1            │  │
│  └────────────────┬──────────────────────────┘  │
└───────────────────┼─────────────────────────────┘
                    │ HTTP (OpenAI 兼容)
                    ▼
┌─────────────────────────────────────────────────┐
│        openai_compat_server.py (端口 8787)       │
│  ┌───────────────────────────────────────────┐  │
│  │  ThreadingHTTPServer (并发 HTTP 请求)      │  │
│  └────────────────┬──────────────────────────┘  │
│                   │ _INTERP_LOCK (串行化)        │
│                   ▼                              │
│  ┌───────────────────────────────────────────┐  │
│  │  MathaAIAssistant + Interpreter            │  │
│  │  (自然语言解析 → Matha 代码 → 执行)         │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

- **HTTP 层**：`ThreadingHTTPServer` 并发处理请求，使用 daemon 线程
- **AI 层**：`MathaAIAssistant` 将自然语言转为 Matha 代码并执行
- **锁机制**：`_INTERP_LOCK` 保护非线程安全的解释器，确保同一时刻只有一个 AI 调用

---

## 九、相关文件

| 文件 | 说明 |
|------|------|
| `src/openai_compat_server.py` | OpenAI 兼容 API 服务 |
| `src/device_config.py` | 设备性能检测与自适应配置 |
| `src/ai_assistant.py` | AI 助手核心逻辑 |
| `src/ai_assistant_server.py` | Matha 原生 REST API（非 OpenAI 兼容） |
| `src/parser_pool.py` | 进程池/线程池解析器 |
| `start_matha_server.bat` | Windows 一键启动脚本 |

---

## 十、更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-09-11 | v1.0 | 初始版本，支持 OpenAI 兼容 API 与自适应多线程 |
