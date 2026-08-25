# Matha 移动端应用剩余开发待办事项

> 生成时间：2025-07-26
> 版本：4.4.16
> 状态：进行中

---

## 一、Pyodide 实际集成 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| Pyodide 桥接层框架 | 完整的 JS interop 实现 | ✅ |
| 代码执行 | runCode() 方法 | ✅ |
| 包管理 | installPackage() 方法 | ✅ |
| 变量操作 | setVariable/getVariable | ✅ |
| 进度监控 | initProgress 属性 | ✅ |
| 错误处理 | 完整的异常捕获 | ✅ |
| Matha 代码包装 | runMathaCode() | ✅ |
| **日志埋点** | **详细执行日志** | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| WebAssembly 打包 | 将 Matha 打包为 WASM | 2 天 | 🔲 |
| 资源预加载 | 预编译常用包 | 1 天 | 🔲 |
| 内存管理 | 优化内存使用 | 1 天 | 🔲 |

---

## 二、协作功能 ✅ 框架已创建

### 已创建文件

| 文件 | 功能 | 状态 |
|------|------|------|
| [mobile/lib/collab/collab_engine.dart](file:///d:/trae/mobile/lib/collab/collab_engine.dart) | CRDT 协作引擎 | ✅ |
| [mobile/lib/collab/session_manager.dart](file:///d:/trae/mobile/lib/collab/session_manager.dart) | 会话管理 | ✅ |
| [mobile/lib/collab/cursor_sync.dart](file:///d:/trae/mobile/lib/collab/cursor_sync.dart) | 光标同步 | ✅ |
| [mobile/lib/collab/permission_system.dart](file:///d:/trae/mobile/lib/collab/permission_system.dart) | 权限系统 | ✅ |
| [mobile/lib/collab/comment_system.dart](file:///d:/trae/mobile/lib/collab/comment_system.dart) | 评论系统 | ✅ |

### 待实现功能（重点）

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| **WebSocket 连接** | **实现实时通信** | **2 天** | **🔲** |
| 邀请系统 | 通过链接邀请 | 0.5 天 | ✅ 框架已创建 |
| 实时聊天 | 会话内聊天 | 1 天 | ✅ 框架已创建 |
| 变更历史 | 操作历史记录 | 1 天 | 🔲 |
| 语音通话 | 会话内语音 | 2 天 | 🔲 |
| 屏幕共享 | 共享编辑界面 | 2 天 | 🔲 |
| 审计日志 | 操作审计追踪 | 1 天 | 🔲 |

### 邀请系统实现步骤 ✅

**文件**：[mobile/lib/collab/invite_system.dart](file:///d:/trae/mobile/lib/collab/invite_system.dart)

```
1. 创建邀请
   ↓
   调用 InviteManager.createInvite()
   ↓
   生成邀请链接: https://matha.app/invite/{inviteId}?doc={documentId}
   ↓
   设置权限类型（编辑/评论/查看）
   ↓
   设置过期时间和最大使用次数
   ↓
2. 分享邀请
   ↓
   复制链接
   ↓
   发送消息/邮件
   ↓
3. 接受邀请
   ↓
   解析邀请链接
   ↓
   调用 InviteManager.acceptInvite()
   ↓
   加入会话
   ↓
   分配权限
   ↓
4. 管理邀请
   ↓
   撤销邀请
   ↓
   查看使用记录
   ↓
   监控过期状态
```

### 实时聊天实现步骤 ✅

**文件**：[mobile/lib/collab/chat_system.dart](file:///d:/trae/mobile/lib/collab/chat_system.dart)

```
1. 初始化聊天会话
   ↓
   调用 ChatManager.getOrCreateSession()
   ↓
   创建或获取会话对象
   ↓
2. 发送消息
   ↓
   调用 ChatManager.sendMessage()
   ↓
   创建 ChatMessage 对象
   ↓
   支持文本/代码/图片类型
   ↓
   支持 @提及功能
   ↓
   发送到服务器（WebSocket）
   ↓
3. 接收消息
   ↓
   监听 messageStream
   ↓
   更新消息列表
   ↓
   显示未读数
   ↓
4. 交互功能
   ↓
   添加表情反应
   ↓
   删除消息
   ↓
   标记已读
   ↓
5. 输入状态
   ↓
   监听 typingStream
   ↓
   显示"正在输入..."
   ↓
   实时同步光标位置
```

### WebSocket 连接实现步骤

```
1. 添加依赖
   pubspec.yaml: web_socket_channel: ^3.0.0

2. 创建 WebSocket 连接管理器
   mobile/lib/collab/websocket_manager.dart ✅ 已创建

3. 实现连接生命周期管理
   - 连接建立（connect）
   - 消息发送/接收（sendOp, _handleRemoteOp）
   - 断线重连（reconnect）
   - 心跳检测（_startHeartbeat）

4. 实现 CRDT 操作同步
   - 本地操作推送到服务器
   - 远程操作订阅和合并
   - 冲突解决

5. 集成到协作引擎
   - 替换 TODO 标记的 WebSocket 实现
   - 添加连接状态回调
```

---

## 三、WebAssembly 打包（重点）

### 实现步骤

```
1. 准备 Matha Python 环境
   - 安装 Emscripten
   - 配置 Python 编译环境

2. 创建 WebAssembly 构建脚本
   mobile/assets/pyodide/build_wasm.sh

3. 打包 Matha 核心模块
   - calculus_symbolic
   - linear_algebra
   - probability_stats
   - graph

4. 优化 WASM 输出
   - 代码压缩
   - 内存优化
   - 懒加载

5. 集成到 Pyodide
   - 修改 pyodide_bridge.dart
   - 添加本地 WASM 加载路径
```

### 关键配置

```bash
# Emscripten 安装
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk
./emsdk install latest
./emsdk activate latest

# 编译 Python for WebAssembly
emconfigure ./configure --enable-framework
emmake make -j$(nproc)

# 打包 Matha
python -m pyodide pack --output matha-wasm.tar
```

---

## 四、SQLite 完整实现 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| 数据库框架 | sqflite 集成 | ✅ |
| 表结构定义 | 7 张表 | ✅ |
| CRUD 操作 | 增删改查 | ✅ |
| 索引优化 | 10+ 索引 | ✅ |
| 数据迁移 | 版本升级支持 | ✅ |
| 加密存储 | AES 加密 | ✅ |
| 数据库维护 | 备份/优化 | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 查询性能优化 | 复杂查询优化 | 0.5 天 | 🔲 |
| 数据压缩 | 大文件压缩 | 0.5 天 | 🔲 |

---

## 五、远程 API 完整实现 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| HTTP 客户端 | Dio 集成 | ✅ |
| 认证系统 | JWT Token 管理 | ✅ |
| 错误处理 | 网络异常处理 | ✅ |
| 重试机制 | 指数退避重试 | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 文件上传 | 大文件分片上传 | 1 天 | 🔲 |
| 实时同步 | WebSocket 双向通信 | 2 天 | 🔲 |
| 离线队列 | 断网时队列管理 | 1 天 | 🔲 |

---

## 六、移动端 UI 完善 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| 主界面 | 模式选择、编辑器 | ✅ |
| 代码编辑器 | 基础编辑功能 | ✅ |
| 结果面板 | 卡片式布局 | ✅ |
| 历史面板 | 底部抽屉 | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 语法高亮 | 代码着色 | 1 天 | 🔲 |
| 自动补全 | 智能提示 | 1 天 | 🔲 |
| 结果可视化 | 矩阵/图表展示 | 1 天 | 🔲 |
| 触摸手势 | 滑动、长按、缩放 | 1 天 | 🔲 |
| 主题切换 | 深色/浅色模式 | 0.5 天 | 🔲 |
| 字体调节 | 可调节代码字体 | 0.5 天 | 🔲 |

---

## 七、离线 IDE 功能 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| 本地存储 | SQLite 数据库 | ✅ |
| 缓存管理 | 常用函数缓存 | ✅ |
| 离线文档 | 本地 API 文档 | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 离线执行 | 无需网络运行 | 2 天 | 🔲 |
| 离线帮助 | help 命令离线可用 | 0.5 天 | 🔲 |
| 离线补全 | 本地补全词库 | 1 天 | 🔲 |

---

## 八、可视化编程器增强 ✅ 进行中

### 已完成

| 功能 | 描述 | 状态 |
|------|------|------|
| 节点编辑器 | 拖拽式界面 | ✅ |
| 节点类型 | 48 种节点 | ✅ |
| 连线系统 | 数据流连接 | ✅ |
| 执行引擎 | 拓扑排序 | ✅ |
| 编辑器增强 | 搜索、分组、布局 | ✅ |
| 日志埋点 | 详细执行日志 | ✅ |

### 待完成

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 撤销/重做 | 操作历史 | 2 天 | 🔲 |
| 复制粘贴 | 节点复制 | 1 天 | 🔲 |
| 多选操作 | 框选节点 | 1 天 | 🔲 |
| 节点对齐 | 自动对齐 | 1 天 | 🔲 |
| 连线优化 | 自动路由 | 2 天 | 🔲 |

---

## 九、测试待办事项

### 🔴 高优先级

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| Pyodide 测试 | 集成测试 | 1 天 | 🔲 |
| 协作功能测试 | 端到端测试 | 1 天 | 🔲 |
| WebSocket 测试 | 实时通信测试 | 1 天 | 🔲 |
| 真机测试 | Android/iOS | 1 天 | 🔲 |

### 🟡 中优先级

| 功能 | 描述 | 预估时间 | 状态 |
|------|------|----------|------|
| 性能测试 | 基准测试 | 0.5 天 | 🔲 |
| 兼容性测试 | 多设备测试 | 1 天 | 🔲 |

---

## 十、总工作量估算

| 类别 | 预估时间 |
|------|----------|
| Pyodide 实际集成 | 4 天 |
| 协作功能 | 11 天 |
| SQLite 完整实现 | 2 天 |
| 远程 API 完整实现 | 4 天 |
| UI 完善 | 4 天 |
| 离线 IDE | 4 天 |
| 可视化编程器增强 | 7 天 |
| 测试 | 4 天 |
| **总计** | **44 天** |

---

## 十一、开发路线图

### 当前阶段（Week 9）：协作功能
- [x] CRDT 引擎框架
- [x] 会话管理
- [x] 光标同步
- [x] 权限系统
- [x] 评论系统
- [x] 日志埋点
- [ ] **WebSocket 连接** ⬅️ 下一步
- [ ] 邀请系统

### 下一阶段（Week 10-11）：Pyodide 集成
- [ ] **WebAssembly 打包** ⬅️ 重点
- [ ] 资源预加载
- [ ] 内存管理优化

### 再下一阶段（Week 12）：测试发布
- [ ] 单元测试
- [ ] 集成测试
- [ ] 真机测试
- [ ] 应用商店发布

---

**计划完成时间**：2025-10-15
**当前状态**：框架完成，核心功能待实现
