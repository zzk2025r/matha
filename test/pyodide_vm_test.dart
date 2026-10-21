// Pyodide VM 平台测试（不导入 dart:html 依赖的组件）
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/pyodide/pyodide_memory_manager.dart';
import 'package:matha_mobile/pyodide/file_chunk_uploader.dart';
import 'package:matha_mobile/pyodide/pyodide_offline_completer.dart';
import 'package:matha_mobile/pyodide/pyodide_preloader.dart';

void main() {
  group('PyodidePreloader 预加载器（VM）', () {
    test('单例', () {
      final p1 = PyodidePreloader();
      final p2 = PyodidePreloader();
      expect(identical(p1, p2), isTrue);
    });

    test('初始状态', () {
      final p = PyodidePreloader();
      expect(p.status, isA<PreloadStatus>());
      expect(p.overallProgress, isA<double>());
      expect(p.resources, isA<List>());
    });

    test('initialize 不崩溃', () async {
      final p = PyodidePreloader();
      await p.initialize(autoPreload: false);
      expect(p.resources, isA<List>());
    });

    test('getCacheInfo 返回结构正确', () {
      final p = PyodidePreloader();
      final info = p.getCacheInfo();
      expect(info, isA<Map<String, dynamic>>());
    });

    test('clearCache 不崩溃', () {
      final p = PyodidePreloader();
      expect(() => p.clearCache(), returnsNormally);
    });
  });

  group('PyodideMemoryManager 内存管理器', () {
    test('单例', () {
      final m1 = PyodideMemoryManager();
      final m2 = PyodideMemoryManager();
      expect(identical(m1, m2), isTrue);
    });

    test('初始状态和配置', () {
      final m = PyodideMemoryManager();
      expect(m.pressure, isA<MemoryPressure>());
      expect(m.autoCleanupEnabled, isA<bool>());
      m.setThresholds(warning: 60, critical: 85);
      m.configure(autoCleanup: true, gcOnCritical: false);
      expect(m.warningThreshold, 60);
    });

    test('监控启停', () {
      final m = PyodideMemoryManager();
      m.startMonitoring(interval: const Duration(seconds: 60));
      m.stopMonitoring();
      expect(true, isTrue);
    });

    test('清理回调注册', () {
      final m = PyodideMemoryManager();
      var x = 0;
      void cb() => x++;
      m.registerCleanupCallback(cb);
      m.unregisterCleanupCallback(cb);
      expect(x, 0);
    });

    test('performCleanup/triggerGC/clearVariables', () async {
      final m = PyodideMemoryManager();
      await m.performCleanup();
      await m.triggerGarbageCollection();
      await m.clearVariables(keepVariables: ['a']);
      expect(true, isTrue);
    });

    test('getSummary', () {
      final m = PyodideMemoryManager();
      final s = m.getSummary();
      expect(s.containsKey('pressure'), isTrue);
      expect(s.containsKey('autoCleanup'), isTrue);
    });

    test('MemoryStats', () {
      final s = MemoryStats(usedBytes: 10, totalBytes: 100, usagePercent: 10, timestamp: DateTime.now());
      expect(s.toMap()['usagePercent'], 10);
    });
  });

  group('FileChunkUploader 分片上传', () {
    test('单例', () {
      expect(identical(FileChunkUploader(), FileChunkUploader()), isTrue);
    });

    test('分片逻辑', () {
      final u = FileChunkUploader();
      final data = Uint8List(1024 * 512 + 100);
      final id = u.createTask(fileName: 't.bin', fileData: data, uploadUrl: 'http://x', chunkSize: 1024 * 256);
      final t = u.getTask(id)!;
      expect(t.chunks.length, 3);
      expect(t.chunks[0].startByte, 0);
      expect(t.chunks[2].endByte, data.length);
    });

    test('空文件和小文件', () {
      final u = FileChunkUploader();
      expect(u.createTask(fileName: 'e', fileData: Uint8List(0), uploadUrl: 'x').isNotEmpty, isTrue);
      final id2 = u.createTask(fileName: 's', fileData: Uint8List(50), uploadUrl: 'x');
      expect(u.getTask(id2)!.chunks.length, 1);
    });

    test('上传控制', () async {
      final u = FileChunkUploader();
      final id = u.createTask(fileName: 'b', fileData: Uint8List(200000), uploadUrl: 'x', chunkSize: 50000);
      u.startUpload(id);
      await Future.delayed(const Duration(milliseconds: 50));
      u.pauseUpload(id);
      u.cancelUpload(id);
      await u.retryFailed(id);
      u.clearCompleted();
      expect(u.getTask(id)!.status, isA<UploadStatus>());
    });

    test('统计', () {
      final u = FileChunkUploader();
      final s = u.getStats();
      expect(s['total'], isA<int>());
    });
  });

  group('PyodideOfflineCompleter 离线补全', () {
    test('单例', () {
      expect(identical(PyodideOfflineCompleter(), PyodideOfflineCompleter()), isTrue);
    });

    test('初始化和补全', () async {
      final c = PyodideOfflineCompleter();
      await c.initialize();
      expect(c.isLoaded, isTrue);
      expect(c.totalCompletions, greaterThan(10));
      
      final r1 = await c.getCompletions(code: 'pri', position: 3);
      expect(r1.items.any((e) => e.label == 'print'), isTrue);
      
      final r2 = await c.getCompletions(code: 'math.', position: 5);
      expect(r2.items.isNotEmpty, isTrue);
      
      final r3 = await c.getCompletions(code: 'def', position: 3);
      expect(r3.items.any((e) => e.label == 'def'), isTrue);
    });

    test('API搜索和文档', () {
      final c = PyodideOfflineCompleter();
      expect(c.searchApi('sqrt'), isA<List<ApiDocItem>>());
      expect(c.getStats()['isLoaded'], isA<bool>());
      c.clearRecent();
      expect(true, isTrue);
    });

    test('CompletionItem 序列化', () {
      const item = CompletionItem(label: 'x', kind: 'function', detail: 'd', documentation: 'doc', insertText: 'x()');
      final m = item.toJson();
      expect(CompletionItem.fromJson(m).label, 'x');
    });
  });
}
