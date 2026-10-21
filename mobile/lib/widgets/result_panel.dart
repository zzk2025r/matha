import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/math_provider.dart';

class ResultPanel extends StatelessWidget {
  const ResultPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MathProvider>();
    final results = provider.results;

    if (results.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.calculate,
              size: 64,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 16),
            Text(
              '暂无计算结果',
              style: TextStyle(
                color: Theme.of(context).colorScheme.outline,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '输入 Matha 代码并点击运行',
              style: TextStyle(
                color: Theme.of(context).colorScheme.outlineVariant,
                fontSize: 12,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: results.length,
      itemBuilder: (context, index) {
        final result = results[index];
        return _ResultCard(result: result);
      },
    );
  }
}

class _ResultCard extends StatelessWidget {
  final ResultItem result;

  const _ResultCard({required this.result});

  List<num>? _tryParseNumbers(String s) {
    try {
      // try JSON-like array
      final trimmed = s.trim();
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        // simple split
        final inner = trimmed.substring(1, trimmed.length - 1);
        final parts = inner.split(RegExp(r',\s*'));
        final nums = <num>[];
        for (final p in parts) {
          final t = p.trim();
          if (t.isEmpty) continue;
          final n = num.tryParse(t);
          if (n == null) return null;
          nums.add(n);
        }
        if (nums.isNotEmpty) return nums;
      }
    } catch (_) {}
    return null;
  }

  Widget _buildVisualization(BuildContext context) {
    final nums = _tryParseNumbers(result.output);
    if (nums == null || nums.isEmpty) return const SizedBox.shrink();
    if (nums.length == 1) {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text('值: ${nums[0]}', style: const TextStyle(fontSize: 13)),
      );
    }
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: SizedBox(
        height: 160,
        child: LineChart(
          LineChartData(
            gridData: const FlGridData(show: false),
            titlesData: const FlTitlesData(show: false),
            borderData: FlBorderData(show: false),
            lineBarsData: [
              LineChartBarData(
                spots: [
                  for (int i = 0; i < nums.length; i++)
                    FlSpot(i.toDouble(), nums[i].toDouble()),
                ],
                isCurved: true,
                color: Theme.of(context).colorScheme.primary,
                barWidth: 2,
                dotData: const FlDotData(show: true),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        leading: Icon(
          result.isSuccess ? Icons.check_circle : Icons.error,
          color: result.isSuccess
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.error,
        ),
        title: Text(
          result.code,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
          ),
        ),
        subtitle: Text(
          result.output.length > 60 ? '${result.output.substring(0, 60)}...' : result.output,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 13,
          ),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SelectableText(
                  result.output,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14,
                    color: result.isSuccess ? Colors.green : Theme.of(context).colorScheme.error,
                  ),
                ),
                _buildVisualization(context),
                if (result.duration != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      '耗时: ${result.duration?.toStringAsFixed(3)}ms',
                      style: TextStyle(
                        fontSize: 10,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    icon: const Icon(Icons.copy, size: 16),
                    label: const Text('复制'),
                    onPressed: () => _copyToClipboard(context, result.output),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _copyToClipboard(BuildContext context, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('已复制到剪贴板')),
    );
  }
}

class ResultItem {
  final String code;
  final String output;
  final bool isSuccess;
  final double? duration;

  const ResultItem({
    required this.code,
    required this.output,
    required this.isSuccess,
    this.duration,
  });
}
