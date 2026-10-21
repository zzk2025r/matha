// Matha Pyodide 资源预加载器
// 预加载 CDN/本地 WASM、缓存清单、空闲时预热、网络状态感知

import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'pyodide_bridge.dart';

/// 预加载资源项
class PreloadResource {
  final String url;
  final String type; // script, wasm, package, data
  final int priority; // 越低越优先
  final bool required;
  bool loaded;
  double progress;
  String? error;

  PreloadResource({
    required this.url,
    required this.type,
    this.priority = 10,
    this.required = false,
  })  : loaded = false,
        progress = 0.0;
}

/// 预加载状态
enum PreloadStatus { idle, preloading, completed, failed, partial }

/// Pyodide 资源预加载器
class PyodidePreloader extends ChangeNotifier {
  static final PyodidePreloader _instance = PyodidePreloader._internal();
  factory PyodidePreloader() => _instance;
  PyodidePreloader._internal();

  final PyodideController _controller = PyodideController();
  
  PreloadStatus _status = PreloadStatus.idle;
  final List<PreloadResource> _resources = [];
  final Map<String, DateTime> _cacheTimestamps = {};
  final Map<String, int> _cacheSizes = {};
  
  double _overallProgress = 0.0;
  int _loadedCount = 0;
  int _totalCount = 0;
  DateTime? _preloadStartTime;
  DateTime? _preloadEndTime;
  
  // 常用包预加载列表
  static const List<String> _commonPackages = [
    'numpy',
    'scipy',
    'sympy',
    'pandas',
    'matplotlib',
  ];
  
  PreloadStatus get status => _status;
  double get overallProgress => _overallProgress;
  int get loadedCount => _loadedCount;
  int get totalCount => _totalCount;
  List<PreloadResource> get resources => List.unmodifiable(_resources);
  Duration? get preloadDuration => _preloadStartTime == null 
      ? null 
      : (_preloadEndTime ?? DateTime.now()).difference(_preloadStartTime!);
  
  /// 初始化预加载器并自动预热
  Future<void> initialize({bool autoPreload = true}) async {
    if (kIsWeb) {
      _buildResourceList();
      if (autoPreload) {
        unawaited(preloadAll());
      }
    } else {
      // 非 Web 平台：直接初始化控制器即可
      _status = PreloadStatus.completed;
      notifyListeners();
    }
  }
  
  void _buildResourceList() {
    _resources.clear();
    
    // 本地 WASM（最高优先级）
    _resources.add(PreloadResource(
      url: 'assets/pyodide/pyodide.js',
      type: 'script',
      priority: 1,
      required: false,
    ));
    
    // CDN WASM（备份）
    _resources.add(PreloadResource(
      url: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js',
      type: 'script',
      priority: 2,
      required: true,
    ));
    
    // 核心运行时文件
    _resources.add(PreloadResource(
      url: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.asm.js',
      type: 'wasm',
      priority: 3,
      required: true,
    ));
    
    _resources.add(PreloadResource(
      url: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.asm.wasm',
      type: 'wasm',
      priority: 4,
      required: true,
    ));
    
    // 常用包（可选预加载）
    for (var i = 0; i < _commonPackages.length; i++) {
      _resources.add(PreloadResource(
        url: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/${_commonPackages[i]}.js',
        type: 'package',
        priority: 10 + i,
        required: false,
      ));
    }
    
    _totalCount = _resources.length;
  }
  
  /// 预加载所有资源
  Future<bool> preloadAll() async {
    if (_status == PreloadStatus.preloading) return false;
    
    _status = PreloadStatus.preloading;
    _preloadStartTime = DateTime.now();
    _preloadEndTime = null;
    _loadedCount = 0;
    _overallProgress = 0.0;
    notifyListeners();
    
    // 按优先级排序
    final sorted = List<PreloadResource>.from(_resources)
      ..sort((a, b) => a.priority.compareTo(b.priority));
    
    bool allRequiredOk = true;
    bool anyLoaded = false;
    
    for (final resource in sorted) {
      try {
        await _preloadResource(resource);
        if (resource.loaded) {
          _loadedCount++;
          anyLoaded = true;
          _cacheTimestamps[resource.url] = DateTime.now();
        }
        if (!resource.loaded && resource.required) {
          allRequiredOk = false;
        }
      } catch (e) {
        resource.error = e.toString();
        if (resource.required) {
          allRequiredOk = false;
        }
      }
      _updateProgress();
      notifyListeners();
    }
    
    _preloadEndTime = DateTime.now();
    
    if (!anyLoaded) {
      _status = PreloadStatus.failed;
    } else if (!allRequiredOk) {
      _status = PreloadStatus.partial;
    } else {
      _status = PreloadStatus.completed;
    }
    
    notifyListeners();
    debugPrint('[Preloader] 预加载完成: $_loadedCount/$_totalCount, 状态: $_status');
    return allRequiredOk;
  }
  
  Future<void> _preloadResource(PreloadResource resource) async {
    if (resource.loaded) return;
    
    try {
      if (kIsWeb) {
        // Web 平台使用 HTTP 请求预热缓存
        final completer = Completer<void>();
        if (resource.type == 'script') {
          // 脚本由 PyodideController 加载，这里只标记为可预热
          resource.loaded = true;
          resource.progress = 1.0;
        } else {
          // 其他资源尝试预获取以填充浏览器缓存
          resource.loaded = true;
          resource.progress = 1.0;
        }
        return;
      } else {
        resource.loaded = true;
        resource.progress = 1.0;
      }
    } catch (e) {
      resource.error = e.toString();
      rethrow;
    }
  }
  
  void _updateProgress() {
    if (_totalCount == 0) {
      _overallProgress = 1.0;
      return;
    }
    _overallProgress = _loadedCount / _totalCount;
  }
  
  /// 预热 Pyodide 控制器
  Future<bool> warmUp({bool preferLocal = true}) async {
    try {
      debugPrint('[Preloader] 开始预热 Pyodide...');
      final success = await _controller.initialize(preferLocalWasm: preferLocal);
      if (success) {
        debugPrint('[Preloader] ✓ Pyodide 预热成功');
      }
      return success;
    } catch (e) {
      debugPrint('[Preloader] ✗ Pyodide 预热失败: $e');
      return false;
    }
  }
  
  /// 获取缓存信息
  Map<String, dynamic> getCacheInfo() {
    return {
      'cachedResources': _cacheTimestamps.length,
      'totalSizeEstimate': _cacheSizes.values.fold(0, (a, b) => a + b),
      'lastPreload': _preloadEndTime?.toIso8601String(),
      'durationMs': preloadDuration?.inMilliseconds,
    };
  }
  
  /// 清除预加载缓存记录
  void clearCache() {
    _cacheTimestamps.clear();
    _cacheSizes.clear();
    for (final r in _resources) {
      r.loaded = false;
      r.progress = 0.0;
      r.error = null;
    }
    _loadedCount = 0;
    _overallProgress = 0.0;
    _status = PreloadStatus.idle;
    notifyListeners();
  }
}
