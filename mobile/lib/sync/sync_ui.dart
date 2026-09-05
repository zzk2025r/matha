// Matha 移动端离线同步 UI
// 冲突解决对话框和同步进度界面

import 'package:flutter/material.dart';
import 'offline_sync_manager.dart';

class ConflictResolutionDialog extends StatelessWidget {
  final SyncTask task;
  final Map<String, dynamic> localData;
  final Map<String, dynamic> remoteData;
  final VoidCallback onResolve;

  const ConflictResolutionDialog({
    super.key,
    required this.task,
    required this.localData,
    required this.remoteData,
    required this.onResolve,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('检测到数据冲突'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '记录类型: ${task.recordType}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              '记录 ID: ${task.recordId}',
              style: const TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 16),
            const Text('本地版本:', style: TextStyle(fontWeight: FontWeight.bold)),
            _DataPreview(data: localData),
            const SizedBox(height: 8),
            const Text('远程版本:', style: TextStyle(fontWeight: FontWeight.bold)),
            _DataPreview(data: remoteData),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => _resolveConflict(context, 'local'),
          child: const Text('保留本地'),
        ),
        TextButton(
          onPressed: () => _resolveConflict(context, 'remote'),
          child: const Text('使用远程'),
        ),
        TextButton(
          onPressed: () => _resolveConflict(context, 'merge'),
          child: const Text('合并'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
      ],
    );
  }

  void _resolveConflict(BuildContext context, String strategy) {
    Navigator.pop(context);
    onResolve();
  }
}

class _DataPreview extends StatelessWidget {
  final Map<String, dynamic> data;

  const _DataPreview({required this.data});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        _formatData(data),
        style: const TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
        ),
      ),
    );
  }

  String _formatData(Map<String, dynamic> data) {
    return data.entries.map((e) => '${e.key}: ${e.value}').join('\n');
  }
}

class SyncProgressIndicator extends StatelessWidget {
  final int pending;
  final int synced;
  final int failed;
  final bool isSyncing;

  const SyncProgressIndicator({
    super.key,
    required this.pending,
    required this.synced,
    required this.failed,
    required this.isSyncing,
  });

  @override
  Widget build(BuildContext context) {
    final total = pending + synced + failed;
    final progress = total > 0 ? synced / total : 0.0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        LinearProgressIndicator(
          value: progress,
          minHeight: 8,
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _StatItem(label: '待同步', count: pending, color: Colors.orange),
            _StatItem(label: '已同步', count: synced, color: Colors.green),
            _StatItem(label: '失败', count: failed, color: Colors.red),
          ],
        ),
        if (isSyncing)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text('同步中...', style: TextStyle(fontSize: 12)),
          ),
      ],
    );
  }
}

class _StatItem extends StatelessWidget {
  final String label;
  final int count;
  final Color color;

  const _StatItem({
    required this.label,
    required this.count,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          '$count',
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.bold,
            fontSize: 16,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 10),
        ),
      ],
    );
  }
}

class SyncLogPanel extends StatelessWidget {
  final List<SyncLogEntry> logs;

  const SyncLogPanel({super.key, required this.logs});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 200,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: logs.isEmpty
          ? const Center(child: Text('暂无同步日志'))
          : ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: logs.length,
              itemBuilder: (context, index) {
                final log = logs[logs.length - 1 - index];
                return _SyncLogItem(log: log);
              },
            ),
    );
  }
}

class _SyncLogItem extends StatelessWidget {
  final SyncLogEntry log;

  const _SyncLogItem({required this.log});

  @override
  Widget build(BuildContext context) {
    final color = _getLogLevelColor(log.level);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Icon(
            _getLogLevelIcon(log.level),
            size: 16,
            color: color,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '[${log.recordType}] ${log.message}',
              style: TextStyle(
                fontSize: 12,
                color: color,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text(
            _formatTime(log.timestamp),
            style: const TextStyle(fontSize: 10, color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Color _getLogLevelColor(String level) {
    switch (level) {
      case 'success':
        return Colors.green;
      case 'warning':
        return Colors.orange;
      case 'error':
        return Colors.red;
      default:
        return Colors.blue;
    }
  }

  IconData _getLogLevelIcon(String level) {
    switch (level) {
      case 'success':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'error':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  String _formatTime(DateTime time) {
    return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:${time.second.toString().padLeft(2, '0')}';
  }
}
