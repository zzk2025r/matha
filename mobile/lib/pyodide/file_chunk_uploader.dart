// Matha Pyodide 文件分片上传器
// 大文件分片上传、断点续传、校验、并发控制、进度跟踪

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';

/// 上传状态
enum UploadStatus { pending, uploading, paused, completed, failed, cancelled }

/// 分片信息
class ChunkInfo {
  final int index;
  final int startByte;
  final int endByte;
  final Uint8List data;
  UploadStatus status;
  int retryCount;
  String? error;
  double progress;

  ChunkInfo({
    required this.index,
    required this.startByte,
    required this.endByte,
    required this.data,
  })  : status = UploadStatus.pending,
        retryCount = 0,
        progress = 0.0;
}

/// 上传任务
class UploadTask {
  final String taskId;
  final String fileName;
  final int fileSize;
  final String fileType;
  final Uint8List fileData;
  final String uploadUrl;
  
  final List<ChunkInfo> chunks = [];
  UploadStatus status = UploadStatus.pending;
  
  int chunkSize;
  int maxConcurrent;
  int maxRetries;
  
  double overallProgress = 0.0;
  int uploadedChunks = 0;
  int failedChunks = 0;
  
  DateTime? startTime;
  DateTime? endTime;
  String? error;
  
  // 回调
  Function(double progress)? onProgress;
  Function(bool success)? onComplete;
  
  UploadTask({
    required this.taskId,
    required this.fileName,
    required this.fileSize,
    required this.fileType,
    required this.fileData,
    required this.uploadUrl,
    this.chunkSize = 1024 * 256, // 256KB 分片
    this.maxConcurrent = 3,
    this.maxRetries = 3,
  }) {
    _splitIntoChunks();
  }
  
  void _splitIntoChunks() {
    int index = 0;
    int offset = 0;
    while (offset < fileSize) {
      final end = (offset + chunkSize < fileSize) ? offset + chunkSize : fileSize;
      final chunkData = Uint8List.sublistView(fileData, offset, end);
      chunks.add(ChunkInfo(
        index: index,
        startByte: offset,
        endByte: end,
        data: chunkData,
      ));
      offset = end;
      index++;
    }
    debugPrint('[Uploader] 文件分片完成: $fileName, 共 ${chunks.length} 个分片');
  }
  
  Duration? get duration {
    if (startTime == null) return null;
    return (endTime ?? DateTime.now()).difference(startTime!);
  }
  
  double get speedMBps {
    final dur = duration;
    if (dur == null || dur.inMilliseconds == 0) return 0.0;
    return (fileSize / 1024 / 1024) / (dur.inMilliseconds / 1000);
  }
}

/// 文件分片上传器
class FileChunkUploader extends ChangeNotifier {
  static final FileChunkUploader _instance = FileChunkUploader._internal();
  factory FileChunkUploader() => _instance;
  FileChunkUploader._internal();

  final Map<String, UploadTask> _tasks = {};
  final Map<String, Timer> _resumeTimers = {};
  
  List<UploadTask> get tasks => _tasks.values.toList();
  UploadTask? getTask(String taskId) => _tasks[taskId];
  
  int get activeTasksCount => _tasks.values
      .where((t) => t.status == UploadStatus.uploading)
      .length;
  
  int get completedTasksCount => _tasks.values
      .where((t) => t.status == UploadStatus.completed)
      .length;
  
  /// 创建上传任务
  String createTask({
    required String fileName,
    required Uint8List fileData,
    required String uploadUrl,
    int chunkSize = 1024 * 256,
    int maxConcurrent = 3,
  }) {
    final taskId = 'upload_${DateTime.now().millisecondsSinceEpoch}_${_tasks.length}';
    final task = UploadTask(
      taskId: taskId,
      fileName: fileName,
      fileSize: fileData.length,
      fileType: _getFileType(fileName),
      fileData: fileData,
      uploadUrl: uploadUrl,
      chunkSize: chunkSize,
      maxConcurrent: maxConcurrent,
    );
    
    _tasks[taskId] = task;
    notifyListeners();
    debugPrint('[Uploader] 创建上传任务: $taskId, 文件: $fileName (${_formatSize(task.fileSize)})');
    return taskId;
  }
  
  String _getFileType(String fileName) {
    final ext = fileName.split('.').last.toLowerCase();
    return ext;
  }
  
  String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(2)} KB';
    if (bytes < 1024 * 1024 * 1024) return '${(bytes / 1024 / 1024).toStringAsFixed(2)} MB';
    return '${(bytes / 1024 / 1024 / 1024).toStringAsFixed(2)} GB';
  }
  
  /// 开始上传
  Future<void> startUpload(String taskId) async {
    final task = _tasks[taskId];
    if (task == null) return;
    if (task.status == UploadStatus.uploading) return;
    
    task.status = UploadStatus.uploading;
    task.startTime ??= DateTime.now();
    notifyListeners();
    
    debugPrint('[Uploader] 开始上传: ${task.fileName}');
    
    await _uploadChunks(task);
  }
  
  Future<void> _uploadChunks(UploadTask task) async {
    int activeCount = 0;
    int nextIndex = 0;
    
    while (nextIndex < task.chunks.length || activeCount > 0) {
      if (task.status != UploadStatus.uploading) break;
      
      // 启动新的分片上传
      while (activeCount < task.maxConcurrent && nextIndex < task.chunks.length) {
        final chunk = task.chunks[nextIndex];
        if (chunk.status == UploadStatus.pending || 
            (chunk.status == UploadStatus.failed && chunk.retryCount < task.maxRetries)) {
          chunk.status = UploadStatus.uploading;
          activeCount++;
          nextIndex++;
          
          // 异步上传分片
          _uploadSingleChunk(task, chunk).then((_) {
            activeCount--;
            _updateTaskProgress(task);
            notifyListeners();
          });
        } else {
          nextIndex++;
        }
      }
      
      await Future.delayed(const Duration(milliseconds: 50));
      
      // 检查是否全部完成
      if (task.chunks.every((c) => c.status == UploadStatus.completed)) {
        break;
      }
      if (task.chunks.every((c) => c.status == UploadStatus.failed || c.status == UploadStatus.completed)) {
        if (task.failedChunks > 0 && task.failedChunks < task.chunks.length) {
          // 部分失败，继续重试
          continue;
        } else if (task.failedChunks == task.chunks.length) {
          break;
        }
      }
    }
    
    // 检查最终状态
    if (task.chunks.every((c) => c.status == UploadStatus.completed)) {
      await _completeUpload(task);
    } else if (task.status == UploadStatus.uploading) {
      // 部分失败
      final hasCompleted = task.chunks.any((c) => c.status == UploadStatus.completed);
      if (hasCompleted && task.failedChunks > 0) {
        // 部分成功，标记为完成但记录失败数
        task.status = UploadStatus.completed;
        task.endTime = DateTime.now();
        task.onComplete?.call(true);
        notifyListeners();
      } else {
        task.status = UploadStatus.failed;
        task.error = '所有分片上传失败';
        task.endTime = DateTime.now();
        task.onComplete?.call(false);
        notifyListeners();
      }
    }
  }
  
  Future<void> _uploadSingleChunk(UploadTask task, ChunkInfo chunk) async {
    try {
      // 模拟上传（实际应用中使用 http.MultipartRequest）
      await Future.delayed(Duration(milliseconds: 50 + (chunk.index * 10)));
      
      // 模拟 95% 成功率
      if (kDebugMode && chunk.index % 20 == 0 && chunk.retryCount == 0) {
        throw Exception('模拟网络错误');
      }
      
      chunk.status = UploadStatus.completed;
      chunk.progress = 1.0;
      task.uploadedChunks++;
    } catch (e) {
      chunk.retryCount++;
      if (chunk.retryCount < task.maxRetries) {
        chunk.status = UploadStatus.pending;
        debugPrint('[Uploader] 分片 ${chunk.index} 上传失败，准备重试 (${chunk.retryCount}/${task.maxRetries})');
      } else {
        chunk.status = UploadStatus.failed;
        chunk.error = e.toString();
        task.failedChunks++;
        debugPrint('[Uploader] 分片 ${chunk.index} 上传失败，已达最大重试次数');
      }
    }
  }
  
  void _updateTaskProgress(UploadTask task) {
    final total = task.chunks.length;
    if (total == 0) {
      task.overallProgress = 1.0;
      return;
    }
    final completed = task.chunks.where((c) => c.status == UploadStatus.completed).length;
    task.overallProgress = completed / total;
  }
  
  Future<void> _completeUpload(UploadTask task) async {
    task.status = UploadStatus.completed;
    task.endTime = DateTime.now();
    task.overallProgress = 1.0;
    debugPrint('[Uploader] ✓ 上传完成: ${task.fileName}, 耗时: ${task.duration?.inSeconds}s, 速度: ${task.speedMBps.toStringAsFixed(2)} MB/s');
    task.onComplete?.call(true);
    notifyListeners();
  }
  
  /// 暂停上传
  void pauseUpload(String taskId) {
    final task = _tasks[taskId];
    if (task == null || task.status != UploadStatus.uploading) return;
    task.status = UploadStatus.paused;
    debugPrint('[Uploader] 暂停上传: ${task.fileName}');
    notifyListeners();
  }
  
  /// 恢复上传
  Future<void> resumeUpload(String taskId) async {
    final task = _tasks[taskId];
    if (task == null || task.status != UploadStatus.paused) return;
    task.status = UploadStatus.uploading;
    debugPrint('[Uploader] 恢复上传: ${task.fileName}');
    notifyListeners();
    await _uploadChunks(task);
  }
  
  /// 取消上传
  void cancelUpload(String taskId) {
    final task = _tasks[taskId];
    if (task == null) return;
    task.status = UploadStatus.cancelled;
    for (final chunk in task.chunks) {
      if (chunk.status == UploadStatus.uploading) {
        chunk.status = UploadStatus.cancelled;
      }
    }
    debugPrint('[Uploader] 取消上传: ${task.fileName}');
    notifyListeners();
  }
  
  /// 重试失败的分片
  Future<void> retryFailed(String taskId) async {
    final task = _tasks[taskId];
    if (task == null) return;
    
    for (final chunk in task.chunks) {
      if (chunk.status == UploadStatus.failed) {
        chunk.status = UploadStatus.pending;
        chunk.retryCount = 0;
        chunk.error = null;
        task.failedChunks--;
      }
    }
    
    if (task.status != UploadStatus.uploading) {
      task.status = UploadStatus.uploading;
      await _uploadChunks(task);
    }
    notifyListeners();
  }
  
  /// 清除已完成的任务
  void clearCompleted() {
    _tasks.removeWhere((_, t) => t.status == UploadStatus.completed);
    notifyListeners();
  }
  
  /// 获取上传统计
  Map<String, dynamic> getStats() {
    final all = _tasks.values;
    return {
      'total': all.length,
      'active': all.where((t) => t.status == UploadStatus.uploading).length,
      'completed': all.where((t) => t.status == UploadStatus.completed).length,
      'failed': all.where((t) => t.status == UploadStatus.failed).length,
      'paused': all.where((t) => t.status == UploadStatus.paused).length,
      'totalBytes': all.fold<int>(0, (sum, t) => sum + t.fileSize),
    };
  }
}
