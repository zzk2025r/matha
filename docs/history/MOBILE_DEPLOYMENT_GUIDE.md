# Matha 移动端自动化部署指南

> 生成时间：2025-07-26
> 版本：4.4.16
> 状态：就绪

---

## 一、快速开始

### 1.1 一键部署（推荐）

```bash
# Linux/Mac
cd mobile/assets
bash deploy.sh

# Windows
cd mobile\assets
deploy.bat
```

### 1.2 手动部署

```bash
# 1. 安装 Flutter
# 下载地址: https://flutter.dev/docs/get-started/install

# 2. 安装 Python 依赖
pip install pyodide-pack websockets

# 3. 安装 Emscripten (仅 WASM 打包需要)
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk && ./emsdk install latest && ./emsdk activate latest

# 4. 构建 WASM
cd mobile/assets/pyodide
bash build_wasm.sh --full

# 5. 运行测试
python -B tests/run_all_tests.py

# 6. 构建 Flutter Web
cd mobile
flutter build web --release

# 7. 部署
cd build/web
python -m http.server 8080
```

---

## 二、环境要求

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| Flutter SDK | >= 3.0.0 | 移动端应用框架 |
| Dart SDK | >= 3.0.0 | Flutter 编程语言 |
| Python | >= 3.8 | WASM 打包工具 |
| Emscripten | latest | WebAssembly 编译 |
| Git | latest | 版本控制 |

---

## 三、脚本说明

### 3.1 build_wasm.sh/bat

**功能**：WebAssembly 打包脚本

**用法**：
```bash
# 完整构建（安装环境 + 编译 + 打包）
bash build_wasm.sh --full

# 仅打包（需要已安装环境）
bash build_wasm.sh --package

# 验证构建结果
bash build_wasm.sh --validate

# 清理构建文件
bash build_wasm.sh --clean
```

**输出文件**：
- `mobile/assets/pyodide/packages/matha-wasm.tar` - 打包好的 WASM 包
- `mobile/assets/pyodide/build_config.json` - 构建配置

### 3.2 deploy.sh/bat

**功能**：自动化部署脚本

**流程**：
1. 检查开发环境
2. 安装项目依赖
3. 构建 WebAssembly
4. 运行测试
5. 构建 Flutter 应用
6. 生成部署包

**输出目录**：`deploy/`

---

## 四、故障排查

### 4.1 WebSocket 连接失败

**日志特征**：
```
[WS] ========== 连接失败 ==========
[WS] 错误: Connection refused
[WS] 堆栈: ...
```

**排查步骤**：
1. 检查服务器地址是否正确
2. 确认服务器支持 WebSocket 协议
3. 检查防火墙设置
4. 查看浏览器控制台网络请求

**解决方案**：
```dart
// 修改服务器地址
final config = WebSocketConfig(
  serverUrl: 'wss://your-server.com/ws',
  documentId: 'doc_123',
  userId: 'user_456',
  userName: 'Test User',
);
```

### 4.2 Pyodide 加载超时

**日志特征**：
```
[Pyodide] ========== 开始执行代码 ==========
[Pyodide] 代码长度: 150 字符
[Pyodide] ✗ 执行失败，耗时: 5000ms
[Pyodide] 错误详情: TimeoutError: loadPyodide failed
```

**排查步骤**：
1. 检查网络连接
2. 确认 CDN 可访问
3. 增加超时时间
4. 查看浏览器控制台

**解决方案**：
```dart
// 增加超时时间
final controller = PyodideController();
await controller.initialize(
  pyodideUrl: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js',
  packages: {'numpy': '1.24.0'},
);
```

### 4.3 WASM 打包失败

**日志特征**：
```
[Matha WASM] [错误] 未找到命令: emcc
[Matha WASM] [错误] Python 版本需要 >= 3.8
```

**排查步骤**：
1. 确认 Emscripten 已安装
2. 检查 Python 版本
3. 查看构建日志
4. 确认目录权限

**解决方案**：
```bash
# 安装 Emscripten
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk
./emsdk install latest
./emsdk activate latest
source emsdk_env.sh

# 验证安装
emcc --version
```

---

## 五、测试指南

### 5.1 运行测试

```bash
# 运行所有测试
python -B tests/run_all_tests.py

# 运行特定测试
python -B -m unittest tests.test_* -v
```

### 5.2 故障模拟测试

访问 Flutter Web 应用的故障模拟页面：
```
http://localhost:8080/#/test/pyodide-failure
```

**测试场景**：
- 模拟 Pyodide 加载超时
- 模拟 WebSocket 连接失败
- 验证日志输出是否正确

---

## 六、部署到生产环境

### 6.1 Firebase 部署

```bash
# 安装 Firebase CLI
npm install -g firebase-tools

# 登录
firebase login

# 部署
firebase deploy --only hosting
```

### 6.2 Netlify 部署

```bash
# 安装 Netlify CLI
npm install -g netlify-cli

# 部署
netlify deploy --prod --dir=build/web
```

### 6.3 AWS S3 部署

```bash
# 安装 AWS CLI
# 配置凭证
aws configure

# 上传
aws s3 sync build/web/ s3://your-bucket-name/ --region us-east-1
```

---

## 七、性能优化建议

### 7.1 WASM 包优化

```bash
# 压缩 WASM 文件
emsdk activate latest
emcc -O3 input.c -o output.wasm

# 使用 wasm-opt 进一步优化
wasm-opt -O3 input.wasm -o output.optimized.wasm
```

### 7.2 加载优化

```dart
// 预加载常用包
await pyodide.loadPackagesFromImports('''
import numpy as np
import pandas as pd
''');

// 懒加载不常用包
void loadPackageLater(String packageName) async {
  await pyodide.loadPackage(packageName);
}
```

---

## 八、更新日志

### v4.4.16 (2025-07-26)

**新增功能**：
- WebSocket 连接管理器实现
- WebAssembly 打包脚本
- 自动化部署脚本
- 故障模拟测试页面

**修复问题**：
- 日志埋点完善
- 错误处理增强
- 超时时间配置

---

**文档版本**：4.4.16
**最后更新**：2025-07-26
