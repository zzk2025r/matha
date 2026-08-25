import 'package:flutter/material.dart';
import '../widgets/code_editor.dart';
import '../widgets/result_panel.dart';
import '../widgets/history_panel.dart';
import '../providers/math_provider.dart';
import 'package:provider/provider.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Matha'),
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: () => _showHistoryPanel(context),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => _showSettings(context),
          ),
        ],
      ),
      body: Column(
        children: [
          // 模式选择器
          _ModeSelector(),
          // 代码编辑器
          const Expanded(
            flex: 3,
            child: CodeEditor(),
          ),
          // 分隔线
          const Divider(height: 1),
          // 结果面板
          const Expanded(
            flex: 2,
            child: ResultPanel(),
          ),
        ],
      ),
      bottomNavigationBar: _BottomActionBar(),
    );
  }

  void _showHistoryPanel(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => const HistoryPanel(),
    );
  }

  void _showSettings(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => const SettingsDialog(),
    );
  }
}

class _ModeSelector extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MathProvider>();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Text('模式:', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(width: 8),
          Expanded(
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'expr', label: Text('表达式'), icon: Icon(Icons.calculate)),
                ButtonSegment(value: 'nl', label: Text('自然语言'), icon: Icon(Icons.chat)),
                ButtonSegment(value: 'intent', label: Text('意图'), icon: Icon(Icons.search)),
              ],
              selected: {provider.mode},
              onSelectionChanged: (modes) {
                provider.setMode(modes.first);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _BottomActionBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MathProvider>();
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              decoration: const InputDecoration(
                hintText: '输入 Matha 代码...',
                prefixIcon: Icon(Icons.code),
                border: OutlineInputBorder(),
              ),
              onSubmitted: (value) {
                if (value.trim().isNotEmpty) {
                  provider.executeCode(value);
                }
              },
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            icon: const Icon(Icons.play_arrow),
            onPressed: () {
              final code = provider.currentCode;
              if (code.trim().isNotEmpty) {
                provider.executeCode(code);
              }
            },
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.clear),
            onPressed: provider.clearResults,
            tooltip: '清空结果',
          ),
        ],
      ),
    );
  }
}

class SettingsDialog extends StatelessWidget {
  const SettingsDialog({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.read<MathProvider>();
    return AlertDialog(
      title: const Text('设置'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            title: const Text('深色模式'),
            trailing: Switch(
              value: provider.isDarkMode,
              onChanged: (value) => provider.toggleDarkMode(),
            ),
          ),
          ListTile(
            title: const Text('显示行号'),
            trailing: Switch(
              value: provider.showLineNumbers,
              onChanged: (value) => provider.setShowLineNumbers(value),
            ),
          ),
          const Divider(),
          ListTile(
            title: const Text('自动补全'),
            trailing: Switch(
              value: provider.autoComplete,
              onChanged: (value) => provider.setAutoComplete(value),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ],
    );
  }
}
