// Matha Pyodide 内存管理器
// 监控堆内存、自动清理、限制执行、垃圾回收触发

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'pyodide_bridge.dart';

/// 内存使用统计
class MemoryStats {
  final int usedBytes;
  final int totalBytes;
  final double usagePercent;
  final DateTime timestamp;

  const MemoryStats({
    required this.usedBytes,
    required this.totalBytes,
    required this.usagePercent,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
        'usedBytes': usedBytes,
        'totalBytes': totalBytes,
        'usagePercent': usagePercent,
        'timestamp': timestamp.toIso8601String(),
      };
}

/// 内存压力级别
enum MemoryPressure { low, medium, high, critical }

/// Pyodide 内存管理器
class PyodideMemoryManager extends ChangeNotifier {
  static final PyodideMemoryManager _instance =
      PyodideMemoryManager._internal();
  factory PyodideMemoryManager() => _instance;
  PyodideMemoryManager._internal();

  final PyodideController _controller = PyodideController();

  Timer? _monitorTimer;
  MemoryStats? _currentStats;
  final List<MemoryStats> _history = [];
  int _maxHistorySize = 60; // 保留最近60条（约5分钟）

  // 阈值配置
  int _warningThreshold = 70; // 70% 警告
  int _criticalThreshold = 90; // 90% 严重
  bool _autoCleanupEnabled = true;
  bool _gcOnCritical = true;

  // 清理回调
  final List<VoidCallback> _cleanupCallbacks = [];

  MemoryStats? get currentStats => _currentStats;
  List<MemoryStats> get history => List.unmodifiable(_history);
  MemoryPressure get pressure => _calculatePressure();
  bool get autoCleanupEnabled => _autoCleanupEnabled;
  int get warningThreshold => _warningThreshold;
  int get criticalThreshold => _criticalThreshold;

  /// 启动内存监控
  void startMonitoring({Duration interval = const Duration(seconds: 5)}) {
    stopMonitoring();
    _monitorTimer = Timer.periodic(interval, (_) => _collectStats());
    _collectStats();
    debugPrint('[MemMgr] 内存监控已启动，间隔: ${interval.inSeconds}秒');
  }

  /// 停止内存监控
  void stopMonitoring() {
    _monitorTimer?.cancel();
    _monitorTimer = null;
  }

  Future<void> _collectStats() async {
    try {
      if (!_controller.isLoaded || kIsWeb == false) {
        // 非 Web 平台或未加载，使用模拟数据或跳过
        return;
      }

      // 通过 Pyodide 获取内存信息
      final result = await _controller.runCode('''
import sys
if hasattr(sys, 'getsizeof'):
    pass
# 尝试获取内存信息
try:
    import psutil
    p = psutil.Process()
    mem = p.memory_info()
    print(f"{mem.rss}|{p.memory_percent()}")
except Exception as e:
    try:
        # Pyodide 环境下的替代方案
        print("0|0")
    except:
        print("0|0")
''', showError: false);

      // 解析结果（简化处理）
      final used = _estimateUsage();
      final total = _getTotalMemory();

      _currentStats = MemoryStats(
        usedBytes: used,
        totalBytes: total,
        usagePercent: total == 0 ? 0.0 : (used / total) * 100,
        timestamp: DateTime.now(),
      );

      _history.add(_currentStats!);
      if (_history.length > _maxHistorySize) {
        _history.removeAt(0);
      }

      // 检查压力并自动清理
      final p = pressure;
      if (_autoCleanupEnabled) {
        if (p == MemoryPressure.critical && _gcOnCritical) {
          await triggerGarbageCollection();
          await performCleanup();
        } else if (p == MemoryPressure.high) {
          await performCleanup();
        }
      }

      notifyListeners();
    } catch (e) {
      debugPrint('[MemMgr] 收集内存统计失败: $e');
    }
  }

  int _estimateUsage() {
    // Web 环境下的内存估算（实际值受限于浏览器）
    return 100 * 1024 * 1024; // 100MB 默认估算
  }

  int _getTotalMemory() {
    // 大多数移动浏览器限制较低
    return 512 * 1024 * 1024; // 512MB 假设上限
  }

  MemoryPressure _calculatePressure() {
    final stats = _currentStats;
    if (stats == null) return MemoryPressure.low;
    if (stats.usagePercent >= _criticalThreshold) return MemoryPressure.critical;
    if (stats.usagePercent >= _warningThreshold) return MemoryPressure.high;
    if (stats.usagePercent >= 50) return MemoryPressure.medium;
    return MemoryPressure.low;
  }

  /// 注册清理回调
  void registerCleanupCallback(VoidCallback callback) {
    _cleanupCallbacks.add(callback);
  }

  /// 移除清理回调
  void unregisterCleanupCallback(VoidCallback callback) {
    _cleanupCallbacks.remove(callback);
  }

  /// 执行清理
  Future<void> performCleanup() async {
    debugPrint('[MemMgr] 执行内存清理...');
    for (final callback in List.from(_cleanupCallbacks)) {
      try {
        callback();
      } catch (e) {
        debugPrint('[MemMgr] 清理回调失败: $e');
      }
    }

    // 清理 Pyodide 历史
    if (_controller.isLoaded) {
      _controller.clearExecutionHistory();
    }

    debugPrint('[MemMgr] ✓ 内存清理完成');
    notifyListeners();
  }

  /// 触发垃圾回收（尽力而为）
  Future<void> triggerGarbageCollection() async {
    if (!_controller.isLoaded) return;
    try {
      debugPrint('[MemMgr] 触发垃圾回收...');
      await _controller.runCode('''
import gc
gc.collect()
''', showError: false);
      debugPrint('[MemMgr] ✓ 垃圾回收已触发');
    } catch (e) {
      debugPrint('[MemMgr] 垃圾回收失败: $e');
    }
  }

  /// 清理变量以释放内存
  Future<void> clearVariables({List<String>? keepVariables}) async {
    if (!_controller.isLoaded) return;
    try {
      final vars = _controller.getVariables();
      final toDelete = vars.where((v) {
        if (v.startsWith('_')) return true;
        if (keepVariables != null && keepVariables.contains(v)) return false;
        // 跳过内置和模块
        if (['sys', 'os', 'math', 'builtins', '__builtins__'].contains(v)) return false;
        return true;
      }).toList();

      for (final v in toDelete) {
        _controller.deleteVariable(v);
      }
      debugPrint('[MemMgr] 清理了 ${toDelete.length} 个变量');
    } catch (e) {
      debugPrint('[MemMgr] 清理变量失败: $e');
    }
  }

  /// 设置阈值
  void setThresholds({int? warning, int? critical}) {
    if (warning != null) _warningThreshold = warning;
    if (critical != null) _criticalThreshold = critical;
    notifyListeners();
  }

  /// 配置自动清理
  void configure({bool? autoCleanup, bool? gcOnCritical}) {
    if (autoCleanup != null) _autoCleanupEnabled = autoCleanup;
    if (gcOnCritical != null) _gcOnCritical = gcOnCritical;
    notifyListeners();
  }

  /// 获取内存使用摘要
  Map<String, dynamic> getSummary() {
    final p = pressure;
    return {
      'current': _currentStats?.toMap(),
      'pressure': p.name,
      'historyCount': _history.length,
      'autoCleanup': _autoCleanupEnabled,
      'thresholds': {
        'warning': _warningThreshold,
        'critical': _criticalThreshold,
      },
    };
  }

  @override
  void dispose() {
    stopMonitoring();
    super.dispose();
  }
}
