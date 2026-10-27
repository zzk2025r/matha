# Pyodide 在 Flutter WebView 中的集成指南

> 生成时间：2025-07-26
> 版本：4.4.8

---

## 一、集成步骤

### 步骤 1：添加依赖

**pubspec.yaml**
```yaml
dependencies:
  flutter:
    sdk: flutter
  # WebView 支持
  flutter_inappwebview: ^6.0.0
  # Pyodide 桥接
  webview_flutter: ^4.8.0
  
dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0
```

### 步骤 2：创建 Pyodide 桥接类

**lib/pyodide/pyodide_bridge.dart**
```dart
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'dart:async';

class PyodideBridge {
  static const String _pyodideUrl =
      'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js';

  InAppWebView? _webView;
  bool _isLoaded = false;
  final List<Function> _loadCallbacks = [];

  // 单例
  static final PyodideBridge _instance = PyodideBridge._internal();
  factory PyodideBridge() => _instance;
  PyodideBridge._internal();

  // 初始化 Pyodide
  Future<bool> initialize({String? microPython = false}) async {
    if (_isLoaded) return true;

    try {
      // 加载 Pyodide CDN
      await _loadPyodideScript();
      
      // 初始化 Pyodide
      _isLoaded = true;
      
      // 执行回调
      for (final callback in _loadCallbacks) {
        callback();
      }
      _loadCallbacks.clear();
      
      return true;
    } catch (e) {
      debugPrint('Pyodide 初始化失败: $e');
      return false;
    }
  }

  // 加载 Pyodide 脚本
  Future<void> _loadPyodideScript() async {
    // 在实际实现中，这里需要：
    // 1. 创建 WebView
    // 2. 加载 Pyodide CDN
    // 3. 等待 Pyodide 初始化完成
    // 4. 准备执行环境
  }

  // 执行 Python 代码
  Future<String> runCode(String code, {bool showError = true}) async {
    if (!_isLoaded) {
      await initialize();
    }

    try {
      // 在实际实现中，这里需要：
      // 1. 通过 JavaScript 桥接调用 Python
      // 2. 等待执行完成
      // 3. 返回结果
      return '模拟结果: $code';
    } catch (e) {
      if (showError) {
        return '错误: $e';
      }
      return '';
    }
  }

  // 安装包
  Future<void> installPackage(String packageName) async {
    if (!_isLoaded) {
      await initialize();
    }
    try {
      // 在实际实现中，调用 pyodide.loadPackage(packageName)
      debugPrint('安装包: $packageName');
    } catch (e) {
      debugPrint('安装包失败: $e');
    }
  }

  // 设置变量
  void setVariable(String name, dynamic value) {
    if (_isLoaded) {
      // 在实际实现中，通过 JS 桥接设置 Python 变量
      debugPrint('设置变量: $name = $value');
    }
  }

  // 获取变量
  dynamic getVariable(String name) {
    if (_isLoaded) {
      // 在实际实现中，通过 JS 桥接获取 Python 变量
      return null;
    }
    return null;
  }

  // 检查是否已加载
  bool get isLoaded => _isLoaded;

  // 添加加载回调
  void addLoadCallback(Function callback) {
    if (_isLoaded) {
      callback();
    } else {
      _loadCallbacks.add(callback);
    }
  }

  // 卸载 Pyodide
  void destroy() {
    _isLoaded = false;
    _loadCallbacks.clear();
  }
}
```

### 步骤 3：创建 Pyodide WebView 页面

**lib/pages/pyodide_page.dart**
```dart
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import '../pyodide/pyodide_bridge.dart';

class PyodidePage extends StatefulWidget {
  const PyodidePage({super.key});

  @override
  State<PyodidePage> createState() => _PyodidePageState();
}

class _PyodidePageState extends State<PyodidePage> {
  final PyodideBridge _pyodide = PyodideBridge();
  InAppWebView? _webView;
  bool _isLoading = true;
  String _output = '';
  final TextEditingController _codeController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _initializePyodide();
  }

  Future<void> _initializePyodide() async {
    setState(() => _isLoading = true);
    
    final success = await _pyodide.initialize();
    
    setState(() => _isLoading = false);
    
    if (success) {
      _output = 'Pyodide 已加载';
    } else {
      _output = 'Pyodide 加载失败';
    }
  }

  Future<void> _runCode() async {
    final code = _codeController.text;
    if (code.isEmpty) return;

    setState(() => _isLoading = true);
    
    final result = await _pyodide.runCode(code);
    
    setState(() {
      _output = result;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pyodide Python 运行时'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // 代码输入
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: TextField(
                    controller: _codeController,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      hintText: '输入 Python 代码...',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                // 执行按钮
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: _runCode,
                          icon: const Icon(Icons.play_arrow),
                          label: const Text('运行'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _codeController.clear(),
                          icon: const Icon(Icons.clear),
                          label: const Text('清空'),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                // 输出显示
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.all(16),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: SingleChildScrollView(
                      child: Text(
                        _output,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }
}
```

### 步骤 4：在主应用中集成

**lib/main.dart**
```dart
import 'package:flutter/material.dart';
import 'pages/pyodide_page.dart';

void main() {
  runApp(const MathaMobileApp());
}

class MathaMobileApp extends StatelessWidget {
  const MathaMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Matha',
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Matha 移动端'),
      ),
      body: Center(
        child: ElevatedButton(
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const PyodidePage()),
            );
          },
          child: const Text('打开 Python 运行时'),
        ),
      ),
    );
  }
}
```

---

## 二、依赖配置

### 2.1 pubspec.yaml 完整配置

```yaml
name: matha_mobile
description: Matha 移动端应用
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'
  flutter: '>=3.16.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.8
  
  # WebView
  flutter_inappwebview: ^6.0.0
  webview_flutter: ^4.8.0
  
  # 状态管理
  provider: ^6.1.2
  
  # 本地存储
  sqflite: ^2.3.3
  path_provider: ^2.1.4
  shared_preferences: ^2.3.3
  
  # HTTP 请求
  http: ^1.2.0
  dio: ^5.4.3+1
  
  # UI 组件
  flutter_syntax_view: ^4.1.0
  fl_chart: ^0.69.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0

flutter:
  uses-material-design: true
```

### 2.2 Android 配置

**android/app/src/main/AndroidManifest.xml**
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.INTERNET"/>
    <uses-permission android:name="android.ACCESS_NETWORK_STATE"/>
    
    <application
        android:usesCleartextTraffic="true"
        android:label="Matha"
        android:name="${applicationName}">
        <!-- 其他配置 -->
    </application>
</manifest>
```

### 2.3 iOS 配置

**ios/Runner/Info.plist**
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

---

## 三、性能优化建议

### 3.1 Pyodide 预加载

```dart
// 在应用启动时预加载 Pyodide
class PyodidePreloader {
  static final PyodideBridge _bridge = PyodideBridge();
  
  static Future<void> preload() async {
    // 后台预加载
    await _bridge.initialize();
    debugPrint('Pyodide 预加载完成');
  }
}

// 在 main() 中调用
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // 预加载 Pyodide
  await PyodidePreloader.preload();
  
  runApp(const MathaMobileApp());
}
```

### 3.2 内存管理

```dart
class PyodideMemoryManager {
  static const int _maxMemoryMb = 256; // 最大内存限制
  
  static Future<void> checkMemory() async {
    // 检查内存使用情况
    // 如果超出限制，清理 Pyodide 环境
  }
}
```

### 3.3 缓存策略

```dart
class PyodideCache {
  static final Map<String, String> _cache = {};
  
  static String? getCached(String code) {
    final hash = _hash(code);
    return _cache[hash];
  }
  
  static void setCached(String code, String result) {
    final hash = _hash(code);
    _cache[hash] = result;
  }
  
  static String _hash(String input) {
    // 简单的哈希实现
    int hash = 0;
    for (int i = 0; i < input.length; i++) {
      hash = ((hash << 5) - hash) + input.codeUnitAt(i);
      hash = hash & hash;
    }
    return hash.toString();
  }
}
```

---

## 四、常见问题

### Q1: Pyodide 加载失败怎么办？

```dart
// 添加重试机制
Future<bool> initializeWithRetry({int maxRetries = 3}) async {
  for (int i = 0; i < maxRetries; i++) {
    try {
      final success = await initialize();
      if (success) return true;
    } catch (e) {
      debugPrint('加载失败 (尝试 ${i + 1}/$maxRetries): $e');
    }
    await Future.delayed(Duration(seconds: 2 * (i + 1)));
  }
  return false;
}
```

### Q2: 如何处理 Python 异常？

```dart
Future<String> runCodeWithTryCatch(String code) async {
  try {
    final result = await _pyodide.runCode(code);
    return '结果: $result';
  } catch (e) {
    return '错误: $e';
  }
}
```

### Q3: 如何限制 Pyodide 内存使用？

```dart
// 在 Android 中限制 WebView 内存
WebViewPlatform.instance = WebViewPlatform.instance is InkWellWebViewPlatform
    ? InkWellWebViewPlatform()
    : WebViewPlatform.instance;
```

---

## 五、测试

### 5.1 单元测试

```dart
// test/pyodide_bridge_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/pyodide/pyodide_bridge.dart';

void main() {
  group('PyodideBridge', () {
    test('初始化返回 true', () async {
      final bridge = PyodideBridge();
      final result = await bridge.initialize();
      expect(result, true);
    });

    test('执行代码返回结果', () async {
      final bridge = PyodideBridge();
      await bridge.initialize();
      final result = await bridge.runCode('1 + 1');
      expect(result, contains('2'));
    });
  });
}
```

### 5.2 集成测试

```dart
// test_integration/pyodide_integration_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/main.dart';

void main() {
  testWidgets('Pyodide 集成测试', (WidgetTester tester) async {
    await tester.pumpWidget(const MathaMobileApp());
    
    // 查找按钮并点击
    await tester.tap(find.text('打开 Python 运行时'));
    await tester.pumpAndSettle();
    
    // 输入代码
    await tester.enterText(
      find.byType(TextField),
      'print("Hello, Matha!")',
    );
    
    // 点击运行
    await tester.tap(find.text('运行'));
    await tester.pumpAndSettle();
    
    // 验证输出
    expect(find.textContaining('Hello, Matha!'), findsOneWidget);
  });
}
```

---

**文档版本**：4.4.8
**更新时间**：2025-07-26
