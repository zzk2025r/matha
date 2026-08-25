import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/math_provider.dart';

class CodeEditor extends StatefulWidget {
  const CodeEditor({super.key});

  @override
  State<CodeEditor> createState() => _CodeEditorState();
}

class _CodeEditorState extends State<CodeEditor> {
  late TextEditingController _controller;
  late FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _focusNode = FocusNode();
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MathProvider>();
    return Container(
      margin: const EdgeInsets.all(8),
      child: Column(
        children: [
          // 工具栏
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
            ),
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.format_bold),
                  onPressed: () => _insertText('**'),
                  tooltip: '加粗',
                ),
                IconButton(
                  icon: const Icon(Icons.format_italic),
                  onPressed: () => _insertText('*'),
                  tooltip: '斜体',
                ),
                const Spacer(),
                TextButton(
                  onPressed: provider.clearCode,
                  child: const Text('清空'),
                ),
              ],
            ),
          ),
          // 代码编辑器
          Expanded(
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              maxLines: null,
              keyboardType: TextInputType.multiline,
              textInputAction: TextInputAction.newline,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
              ),
              decoration: InputDecoration(
                hintText: provider.mode == 'nl' ? '输入自然语言指令...' : '输入 Matha 表达式...',
                border: const OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(8)),
                ),
                filled: true,
                fillColor: Theme.of(context).colorScheme.surface,
                contentPadding: const EdgeInsets.all(12),
              ),
              onSubmitted: (value) {
                if (value.trim().isNotEmpty) {
                  provider.executeCode(value);
                }
              },
            ),
          ),
          // 快捷命令
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              _QuickCommandChip(label: '矩阵', onTap: () => provider.insertSnippet('matrix')),
              _QuickCommandChip(label: '统计', onTap: () => provider.insertSnippet('statistics')),
              _QuickCommandChip(label: '微积分', onTap: () => provider.insertSnippet('calculus')),
              _QuickCommandChip(label: '概率', onTap: () => provider.insertSnippet('probability')),
              _QuickCommandChip(label: '图算法', onTap: () => provider.insertSnippet('graph')),
            ],
          ),
        ],
      ),
    );
  }

  void _insertText(String text) {
    final selection = _controller.selection;
    final textBefore = _controller.text.substring(0, selection.start);
    final textAfter = _controller.text.substring(selection.end);
    _controller.text = '$textBefore$text$textAfter';
    _controller.selection = TextSelection(
      baseOffset: textBefore.length + text.length,
      extentOffset: textBefore.length + text.length,
    );
    FocusScope.of(context).requestFocus(_focusNode);
  }
}

class _QuickCommandChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _QuickCommandChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(label),
      onDeleted: onTap,
      deleteIcon: const Icon(Icons.close, size: 16),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}
