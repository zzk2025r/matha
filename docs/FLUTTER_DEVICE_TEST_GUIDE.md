# Matha Flutter 真机测试环境配置指南

## 一、Flutter 环境安装

### 1.1 下载安装 Flutter SDK

```powershell
# 方式A: 直接下载（推荐）
# 访问 https://flutter.dev/docs/get-started/install/windows
# 下载 Flutter SDK，解压到 C:\src\flutter

# 方式B: Git clone
cd C:\src
git clone https://github.com/flutter/flutter.git -b stable
```

### 1.2 配置环境变量

```powershell
# 添加到 ~/.bashrc 或系统环境变量
$env:PATH = "$env:PATH;C:\src\flutter\bin"

# 验证安装
flutter --version
flutter doctor
```

### 1.3 运行 Flutter Doctor 检查

```powershell
flutter doctor
```

**期望输出：**
```
[√] Flutter (Channel stable, x.x.x)
[√] Android toolchain - develop for Android devices
[√] Chrome - develop for the web
[√] VS Code / Android Studio
[√] Connected device
```

---

## 二、设备连接

### 2.1 Android 真机

```powershell
# 1. 启用开发者选项
#   设置 → 关于手机 → 连续点击"版本号"7次

# 2. 启用 USB 调试
#   设置 → 开发者选项 → USB 调试 → 开启

# 3. 连接手机，授权调试
#   手机端会弹出"允许USB调试"对话框，点击允许

# 4. 检查设备
flutter devices
```

**期望输出：**
```
1 connected device:
Pixel 6 (mobile) • <DEVICE_ID> • android-arm64 • Android 14
```

### 2.2 iOS 真机（需要 Mac）

```bash
# 1. 安装 Xcode
# 2. 连接 iPhone，信任电脑
# 3. 在 Xcode 中签署开发者证书
# 4. 检查设备
flutter devices
```

### 2.3 Web 浏览器

```powershell
flutter devices
# 应显示 Chrome / Edge
```

---

## 三、Matha Flutter 项目配置

### 3.1 进入 Flutter 目录

```powershell
cd d:\trae\flutter_app
```

### 3.2 获取依赖

```powershell
flutter pub get
```

### 3.3 配置 pyodide 桥接

**文件：** `lib/pyodide/pyodide_bridge.dart`

```dart
import 'package:pyodide_dart/pyodide_dart.dart';

class MathaPyodideBridge {
  static PyodideInterface? _pyodide;

  static Future<void> initialize() async {
    if (_pyodide != null) return;
    _pyodide = await PyodideDart.loadPyodide({
      "packageIndex": {
        "matha-core": "https://your-server/matha-core-3.0.0-py3-none-any.whl",
      },
    });
  }

  static Future<dynamic> execute(String code) async {
    await initialize();
    return _pyodide!.runPython(code);
  }
}
```

### 3.4 运行测试

```powershell
# 运行到 Android 真机
flutter run -d <DEVICE_ID>

# 运行到 Web
flutter run -d chrome

# 构建发布包
flutter build apk --release
flutter build web --release
```

---

## 四、常见问题排查

| 问题 | 解决方案 |
|------|---------|
| `flutter: command not found` | 重新配置 PATH 环境变量 |
| `No devices found` | 检查 USB 调试是否开启，重新插拔 |
| `Permission denied` | 手机授权 USB 调试 |
| `Android SDK not found` | 运行 `flutter doctor --android-licenses` |
| `pyodide 加载失败` | 检查 WHL 文件 URL 是否可访问 |
| `证书签名失败 (iOS)` | 在 Xcode 中更新开发者证书 |

---

## 五、完整测试流程

```powershell
# 1. 构建 WASM 包
python matha_wasm/build_wasm.py

# 2. 启动 HTTP 服务器提供 WHL 文件
cd matha_wasm/dist
python -m http.server 8080

# 3. 在另一个终端运行 Flutter
cd d:\trae\flutter_app
flutter run -d chrome  # 或 -d <DEVICE_ID>
```
