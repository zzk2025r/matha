// Matha Pyodide 桥接层 - 完整版
// 在 Flutter Web 中运行 Python 代码

import 'package:flutter_web_plugins/flutter_web_plugins.dart';
import 'package:flutter/material.dart';
import 'dart:html' as html;
import 'dart:async';
import 'dart:convert';

/// Pyodide 执行结果
class PyodideResult {
  final String output;
  final String? error;
  final double durationMs;

  const PyodideResult({
    required this.output,
    this.error,
    this.durationMs = 0.0,
  });

  bool get isSuccess => error == null;
  bool get isFailure => error != null;

  Map<String, dynamic> toMap() => {
    'output': output,
    'error': error,
    'durationMs': durationMs,
    'isSuccess': isSuccess,
  };

  factory PyodideResult.fromMap(Map<String, dynamic> map) => PyodideResult(
    output: map['output'] ?? '',
    error: map['error'],
    durationMs: map['durationMs'] ?? 0.0,
  );
}

/// Pyodide 包信息
class PyodidePackage {
  final String name;
  final String version;
  final bool isLoaded;

  const PyodidePackage({
    required this.name,
    required this.version,
    required this.isLoaded,
  });

  Map<String, dynamic> toMap() => {
    'name': name,
    'version': version,
    'isLoaded': isLoaded,
  };
}

/// Pyodide 桥接控制器
class PyodideController extends ChangeNotifier {
  static const String _pyodideVersion = '0.24.1';
  static const String _pyodideUrl = 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js';
  static const String _micropipUrl = 'https://pypi.org/project/micropip/';

  Pyodide? _pyodide;
  bool _isLoaded = false;
  bool _isInitializing = false;
  final List<Function> _loadCallbacks = [];
  final Map<String, String> _packages = {};
  final List<Map<String, dynamic>> _executionHistory = [];
  String? _lastError;
  double _initProgress = 0.0;

  // 单例
  static final PyodideController _instance = PyodideController._internal();
  factory PyodideController() => _instance;
  PyodideController._internal();

  static void registerWith(Registrar registrar) {
    // Flutter Web 插件注册
  }

  // ========== 初始化 ==========

  /// 初始化 Pyodide
  Future<bool> initialize({
    String? pyodideUrl,
    Map<String, String>? packages,
  }) async {
    if (_isLoaded) return true;
    if (_isInitializing) {
      // 等待已有的初始化完成
      return _waitForInitialization();
    }

    _isInitializing = true;
    _notifyProgress(0.1);
    debugPrint('[Pyodide] 开始初始化...');

    try {
      // 动态加载 Pyodide JS
      _notifyProgress(0.2);
      await _loadPyodideScript(pyodideUrl ?? _pyodideUrl);
      
      _notifyProgress(0.4);
      debugPrint('[Pyodide] 加载 Python 运行时...');
      
      // 初始化 Pyodide
      _pyodide = await _createPyodideInstance();
      _isLoaded = true;
      _isInitializing = false;
      
      _notifyProgress(0.8);
      debugPrint('[Pyodide] Python 运行时加载完成');
      
      // 加载可选包
      if (packages != null && packages.isNotEmpty) {
        await _loadPackages(packages);
      }
      
      _notifyProgress(1.0);
      debugPrint('[Pyodide] 初始化完成');
      
      // 执行回调
      for (final callback in _loadCallbacks) {
        callback();
      }
      _loadCallbacks.clear();
      
      notifyListeners();
      return true;
    } catch (e) {
      _isInitializing = false;
      _lastError = '初始化失败: $e';
      debugPrint('[Pyodide] $_lastError');
      _notifyProgress(0.0);
      notifyListeners();
      return false;
    }
  }

  /// 等待初始化完成
  Future<bool> _waitForInitialization() async {
    while (_isInitializing) {
      await Future.delayed(const Duration(milliseconds: 100));
    }
    return _isLoaded;
  }

  /// 加载 Pyodide JS 脚本
  Future<void> _loadPyodideScript(String url) async {
    debugPrint('[Pyodide] ========== 开始加载 JS 脚本 ==========');
    debugPrint('[Pyodide] 脚本 URL: $url');
    
    // 检查是否已加载
    if (html.document.querySelector('script[src*="pyodide"]') != null) {
      debugPrint('[Pyodide] ✓ Pyodide JS 脚本已存在，跳过加载');
      debugPrint('[Pyodide] ========== 脚本加载完成 ==========');
      return;
    }

    // 创建脚本元素
    final script = html.ScriptElement()
      ..src = url
      ..type = 'text/javascript';
    
    debugPrint('[Pyodide] 创建 script 元素并添加到 head...');
    html.document.head!.append(script);
    
    // 等待加载完成
    debugPrint('[Pyodide] 等待脚本加载...');
    await script.onLoad.first;
    
    debugPrint('[Pyodide] ✓ JS 脚本加载完成');
    debugPrint('[Pyodide] ========== 脚本加载完成 ==========');
  }

  /// 创建 Pyodide 实例
  Future<Pyodide> _createPyodideInstance() async {
    debugPrint('[Pyodide] ========== 创建 Pyodide 实例 ==========');
    debugPrint('[Pyodide] 尝试获取 loadPyodide 函数...');
    
    final loadPyodide = html.window['loadPyodide'] as dynamic;
    if (loadPyodide == null) {
      debugPrint('[Pyodide] ✗ 错误: loadPyodide 函数未找到');
      throw Exception('Pyodide JS 未正确加载');
    }
    
    debugPrint('[Pyodide] ✓ loadPyodide 函数已找到，开始初始化...');
    final instance = await loadPyodide();
    
    debugPrint('[Pyodide] ✓ Pyodide 实例创建成功');
    debugPrint('[Pyodide] ========== 实例创建完成 ==========');
    return Pyodide._fromJs(instance);
  }

  // ========== 包管理 ==========

  /// 加载 Python 包
  Future<void> _loadPackages(Map<String, String> packages) async {
    if (_pyodide == null || !_isLoaded) return;
    
    debugPrint('[Pyodide] 加载包: ${packages.keys.join(", ")}');
    
    for (final entry in packages.entries) {
      try {
        await _pyodide!.loadPackage(entry.key);
        _packages[entry.key] = entry.value;
        debugPrint('[Pyodide] 包 ${entry.key} 加载成功');
      } catch (e) {
        debugPrint('[Pyodide] 包 ${entry.key} 加载失败: $e');
      }
    }
  }

  /// 获取已加载的包
  Map<String, String> get packages => Map.unmodifiable(_packages);

  /// 检查包是否已加载
  bool isPackageLoaded(String name) => _packages.containsKey(name);

  // ========== 代码执行 ==========

  /// 执行 Python 代码
  Future<PyodideResult> runCode(
    String code, {
    Map<String, dynamic>? globals,
    bool showError = true,
  }) async {
    debugPrint('[Pyodide] ========== 开始执行代码 ==========');
    debugPrint('[Pyodide] 代码长度: ${code.length} 字符');
    debugPrint('[Pyodide] 代码预览: ${code.substring(0, code.length > 50 ? 50 : code.length)}...');
    
    if (!_isLoaded) {
      debugPrint('[Pyodide] Pyodide 未加载，正在初始化...');
      await initialize();
    }

    if (_pyodide == null) {
      debugPrint('[Pyodide] ✗ Pyodide 实例为空，无法执行');
      return PyodideResult(
        output: '',
        error: 'Pyodide 未初始化',
      );
    }

    final startTime = DateTime.now().millisecondsSinceEpoch;
    
    try {
      // 设置全局变量
      if (globals != null) {
        debugPrint('[Pyodide] 设置全局变量: ${globals.keys.join(", ")}');
        for (final entry in globals.entries) {
          _pyodide!.setVariable(entry.key, entry.value);
        }
      }
      
      // 执行代码
      debugPrint('[Pyodide] 调用 runPythonAsync...');
      final result = await _pyodide!.runPythonAsync(code);
      final duration = DateTime.now().millisecondsSinceEpoch - startTime;
      
      debugPrint('[Pyodide] ✓ 执行完成，耗时: ${duration}ms');
      debugPrint('[Pyodide] 结果类型: ${result.runtimeType}');
      
      // 记录历史
      _executionHistory.add({
        'code': code,
        'result': result,
        'duration': duration,
        'timestamp': DateTime.now().toIso8601String(),
      });
      
      debugPrint('[Pyodide] ========== 代码执行完成 ==========');
      
      return PyodideResult(
        output: result?.toString() ?? '',
        durationMs: duration / 1000,
      );
    } catch (e, stackTrace) {
      final duration = DateTime.now().millisecondsSinceEpoch - startTime;
      _lastError = '执行错误: $e';
      
      debugPrint('[Pyodide] ✗ 执行失败，耗时: ${duration}ms');
      debugPrint('[Pyodide] 错误详情: $e');
      debugPrint('[Pyodide] 堆栈跟踪: $stackTrace');
      debugPrint('[Pyodide] ========== 代码执行失败 ==========');
      
      // 记录错误历史
      _executionHistory.add({
        'code': code,
        'error': _lastError,
        'duration': duration,
        'timestamp': DateTime.now().toIso8601String(),
      });
      
      if (showError) {
        return PyodideResult(
          output: '',
          error: _lastError,
          durationMs: duration / 1000,
        );
      }
      
      return PyodideResult(
        output: '',
        durationMs: duration / 1000,
      );
    }
  }

  /// 执行 Python 代码并返回 JSON 结果
  Future<Map<String, dynamic>> runCodeJson(
    String code, {
    Map<String, dynamic>? globals,
  }) async {
    debugPrint('[Pyodide] ========== 开始执行 JSON 代码 ==========');
    
    try {
      final result = await runCode(code, globals: globals);
      
      if (result.isFailure) {
        debugPrint('[Pyodide] ✗ 执行失败: ${result.error}');
        return {'success': false, 'error': result.error};
      }
      
      debugPrint('[Pyodide] 尝试解析 JSON 输出...');
      
      try {
        final decoded = jsonDecode(result.output);
        debugPrint('[Pyodide] ✓ JSON 解析成功');
        
        if (decoded is Map<String, dynamic>) {
          return decoded;
        } else {
          debugPrint('[Pyodide] ⚠ 输出不是 Map 类型，包装为成功结果');
          return {'success': true, 'data': decoded};
        }
      } on FormatException catch (e) {
        debugPrint('[Pyodide] ✗ JSON 解析失败: $e');
        debugPrint('[Pyodide] 原始输出: ${result.output}');
        return {
          'success': true,
          'output': result.output,
          'parseError': e.toString(),
        };
      } catch (e) {
        debugPrint('[Pyodide] ✗ 未知错误: $e');
        return {'success': true, 'output': result.output};
      }
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ 执行异常: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
      return {'success': false, 'error': e.toString()};
    }
  }

  /// 执行 Matha 代码（自动导入 Matha 模块）
  Future<PyodideResult> runMathaCode(String code) async {
    debugPrint('[Pyodide] ========== 开始执行 Matha 代码 ==========');
    debugPrint('[Pyodide] 代码长度: ${code.length} 字符');
    
    try {
      final wrappedCode = '''
import sys
import io

# 重定向输出
old_stdout = sys.stdout
sys.stdout = mystdout = io.StringIO()

# 导入 Matha 核心模块
try:
    from src.stdlib import calculus_symbolic, linear_algebra, probability_stats, graph
except ImportError as e:
    print(f"Import error: {e}", file=mystdout)
    import traceback
    traceback.print_exc(file=mystdout)

# 执行用户代码
try:
    $code
except Exception as e:
    print(f"Execution error: {e}", file=mystdout)
    import traceback
    traceback.print_exc(file=mystdout)

# 获取输出
output = mystdout.getvalue()
sys.stdout = old_stdout

# 返回结果
{"output": output, "success": True}
''';
      
      debugPrint('[Pyodide] 包装代码长度: ${wrappedCode.length} 字符');
      final result = await runCode(wrappedCode);
      
      debugPrint('[Pyodide] ========== Matha 代码执行完成 ==========');
      return result;
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ Matha 代码执行异常: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
      return PyodideResult(
        output: '',
        error: 'Matha 代码执行失败: $e',
      );
    }
  }

  // ========== 变量操作 ==========

  /// 设置变量
  void setVariable(String name, dynamic value) {
    if (_pyodide != null && _isLoaded) {
      try {
        _pyodide!.setVariable(name, value);
        debugPrint('[Pyodide] ✓ 设置变量: $name = $value');
      } catch (e, stackTrace) {
        debugPrint('[Pyodide] ✗ 设置变量失败: $name');
        debugPrint('[Pyodide] 错误: $e');
        debugPrint('[Pyodide] 堆栈: $stackTrace');
      }
    }
  }

  /// 获取变量
  dynamic getVariable(String name) {
    if (_pyodide != null && _isLoaded) {
      try {
        final result = _pyodide!.getVariable(name);
        debugPrint('[Pyodide] ✓ 获取变量: $name');
        return result;
      } catch (e, stackTrace) {
        debugPrint('[Pyodide] ✗ 获取变量失败: $name');
        debugPrint('[Pyodide] 错误: $e');
        debugPrint('[Pyodide] 堆栈: $stackTrace');
        return null;
      }
    }
    return null;
  }

  /// 删除变量
  void deleteVariable(String name) {
    if (_pyodide != null && _isLoaded) {
      try {
        _pyodide!.runPythonAsync('del $name');
        debugPrint('[Pyodide] ✓ 删除变量: $name');
      } catch (e, stackTrace) {
        debugPrint('[Pyodide] ✗ 删除变量失败: $name');
        debugPrint('[Pyodide] 错误: $e');
        debugPrint('[Pyodide] 堆栈: $stackTrace');
      }
    }
  }

  /// 获取所有变量
  List<String> getVariables() {
    if (_pyodide != null && _isLoaded) {
      try {
        final result = _pyodide!.runPythonSync('list(globals().keys())');
        debugPrint('[Pyodide] ✓ 获取变量列表，数量: ${(result as List).length}');
        return (result as List).cast<String>();
      } catch (e, stackTrace) {
        debugPrint('[Pyodide] ✗ 获取变量列表失败');
        debugPrint('[Pyodide] 错误: $e');
        debugPrint('[Pyodide] 堆栈: $stackTrace');
        return [];
      }
    }
    return [];
  }

  // ========== 进度和状态 ==========

  /// 获取初始化进度 (0.0 - 1.0)
  double get initProgress => _initProgress;

  /// 获取最后错误
  String? get lastError => _lastError;

  /// 获取执行历史
  List<Map<String, dynamic>> get executionHistory => List.unmodifiable(_executionHistory);

  /// 清空执行历史
  void clearExecutionHistory() {
    _executionHistory.clear();
    notifyListeners();
  }

  // ========== 生命周期 ==========

  /// 销毁 Pyodide 实例
  void destroy() {
    if (_pyodide != null) {
      try {
        _pyodide!.runPythonSync('shutdown()');
      } catch (e) {
        debugPrint('[Pyodide] 销毁时出错: $e');
      }
    }
    _pyodide = null;
    _isLoaded = false;
    _isInitializing = false;
    _notifyProgress(0.0);
    notifyListeners();
    debugPrint('[Pyodide] 已销毁');
  }

  /// 检查是否已加载
  bool get isLoaded => _isLoaded;

  /// 检查是否正在初始化
  bool get isInitializing => _isInitializing;

  // ========== 内部方法 ==========

  void _notifyProgress(double progress) {
    _initProgress = progress;
    notifyListeners();
  }
}

/// Pyodide JS 包装类
class Pyodide {
  final dynamic _jsObject;

  Pyodide._fromJs(dynamic jsObj) : _jsObject = jsObj;

  /// 执行 Python 异步代码
  Future<dynamic> runPythonAsync(String code) async {
    try {
      // 尝试调用 Pyodide 的 runPythonAsync
      debugPrint('[Pyodide] 调用 runPythonAsync...');
      final result = await _jsObject.runPythonAsync(code);
      debugPrint('[Pyodide] ✓ runPythonAsync 执行成功');
      return result;
    } catch (e) {
      debugPrint('[Pyodide] ✗ runPythonAsync 失败，尝试 runPython...');
      // 降级到 runPython
      try {
        final result = _jsObject.runPython(code);
        debugPrint('[Pyodide] ✓ runPython 执行成功（降级模式）');
        return result;
      } catch (e2) {
        debugPrint('[Pyodide] ✗ runPython 也失败: $e2');
        throw Exception('Pyodide 执行错误: $e2');
      }
    }
  }

  /// 执行 Python 同步代码
  dynamic runPythonSync(String code) {
    try {
      debugPrint('[Pyodide] 调用 runPythonSync...');
      final result = _jsObject.runPython(code);
      debugPrint('[Pyodide] ✓ runPythonSync 执行成功');
      return result;
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ runPythonSync 失败');
      debugPrint('[Pyodide] 错误: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
      throw Exception('Pyodide 执行错误: $e');
    }
  }

  /// 设置变量
  void setVariable(String name, dynamic value) {
    try {
      debugPrint('[Pyodide] 设置 JS 变量: $name');
      _jsObject.globals.setItem(name, value);
      debugPrint('[Pyodide] ✓ 变量设置成功');
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ 变量设置失败: $name');
      debugPrint('[Pyodide] 错误: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
    }
  }

  /// 获取变量
  dynamic getVariable(String name) {
    try {
      debugPrint('[Pyodide] 获取 JS 变量: $name');
      final result = _jsObject.globals.getItem(name);
      debugPrint('[Pyodide] ✓ 变量获取成功');
      return result;
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ 变量获取失败: $name');
      debugPrint('[Pyodide] 错误: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
      return null;
    }
  }

  /// 加载包
  Future<void> loadPackage(String packageName) async {
    debugPrint('[Pyodide] ========== 开始加载包 ==========');
    debugPrint('[Pyodide] 包名: $packageName');
    
    try {
      // 尝试使用 micropip
      debugPrint('[Pyodide] 尝试使用 micropip 安装...');
      await _jsObject.runPythonAsync('import micropip; await micropip.install("$packageName")');
      debugPrint('[Pyodide] ✓ micropip 安装成功');
    } catch (e) {
      debugPrint('[Pyodide] ✗ micropip 安装失败: $e');
      debugPrint('[Pyodide] 尝试使用 loadPackage...');
      
      // 降级到 loadPackage
      try {
        await _jsObject.loadPackage(packageName);
        debugPrint('[Pyodide] ✓ loadPackage 安装成功');
      } catch (e2) {
        debugPrint('[Pyodide] ✗ loadPackage 也失败: $e2');
        throw Exception('包 $packageName 加载失败: $e2');
      }
    }
    
    debugPrint('[Pyodide] ========== 包加载完成 ==========');
  }

  /// 获取 Python 版本
  String getPythonVersion() {
    try {
      debugPrint('[Pyodide] 获取 Python 版本...');
      final result = _jsObject.runPythonSync('import sys; sys.version');
      debugPrint('[Pyodide] ✓ Python 版本: $result');
      return result;
    } catch (e, stackTrace) {
      debugPrint('[Pyodide] ✗ 获取 Python 版本失败');
      debugPrint('[Pyodide] 错误: $e');
      debugPrint('[Pyodide] 堆栈: $stackTrace');
      return 'unknown';
    }
  }
}
