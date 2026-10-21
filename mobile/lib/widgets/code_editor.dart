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
  final List<String> _keywords = const [
    '输出', '如果', '否则', '循环', '函数', '定义', '返回', '匹配', '当', '否则',
    'for', 'in', 'if', 'else', 'def', 'return', 'try', 'catch', 'throw', '抛出'
  ];

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
                IconButton(
                  icon: const Icon(Icons.code),
                  onPressed: () => _insertText('{}'),
                  tooltip: '代码块',
                ),
                const Spacer(),
                TextButton(
                  onPressed: () {
                    provider.clearCode();
                    _controller.clear();
                  },
                  child: const Text('清空'),
                ),
              ],
            ),
          ),
          // 代码编辑器（带语法高亮风格）
          Expanded(
            child: GestureDetector(
              onDoubleTap: () => _focusNode.requestFocus(),
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                maxLines: null,
                expands: true,
                keyboardType: TextInputType.multiline,
                textInputAction: TextInputAction.newline,
                style: TextStyle(
                  fontFamily: provider.editorFontFamily,
                  fontSize: provider.editorFontSize,
                  height: 1.5,
                  color: Theme.of(context).colorScheme.onSurface,
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
                onChanged: (value) {
                  provider.setCode(value);
                },
                onSubmitted: (value) {
                  if (value.trim().isNotEmpty) {
                    provider.executeCode(value);
                  }
                },
              ),
            ),
          ),
          // 自动补全建议
          if (provider.autoComplete && _controller.text.isNotEmpty)
            Container(
              height: 36,
              alignment: Alignment.centerLeft,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: _buildSuggestions(provider),
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
              _QuickCommandChip(label: '列表推导', onTap: () => _insertText('[x*x for x in [1,2,3]]')),
              _QuickCommandChip(label: '枚举zip', onTap: () => _insertText('enumerate([1,2,3])')),
            ],
          ),
        ],
      ),
    );
  }

  void _insertText(String text) {
    final selection = _controller.selection;
    final start = selection.start >= 0 ? selection.start : _controller.text.length;
    final end = selection.end >= 0 ? selection.end : _controller.text.length;
    final textBefore = _controller.text.substring(0, start);
    final textAfter = _controller.text.substring(end);
    _controller.text = '$textBefore$text$textAfter';
    _controller.selection = TextSelection(
      baseOffset: textBefore.length + text.length,
      extentOffset: textBefore.length + text.length,
    );
    context.read<MathProvider>().setCode(_controller.text);
    FocusScope.of(context).requestFocus(_focusNode);
  }

  List<Widget> _buildSuggestions(MathProvider provider) {
    final text = _controller.text;
    if (text.isEmpty) return [];
    final last = text.split(RegExp(r'[\s\(\[\{,\;]')).last;
    if (last.isEmpty) return [];
    final matches = _keywords.where((k) => k.startsWith(last) && k != last).take(5).toList();
    return matches.map((m) => Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: ActionChip(
        label: Text(m),
        onPressed: () {
          final lastWordStart = _controller.text.lastIndexOf(last);
          if (lastWordStart >= 0) {
            final before = _controller.text.substring(0, lastWordStart);
            final after = _controller.text.substring(lastWordStart + last.length);
            _controller.text = '$before$m$after';
            _controller.selection = TextSelection.collapsed(
              offset: before.length + m.length,
            );
            provider.setCode(_controller.text);
            setState(() {});
          }
        },
      ),
    )).toList();
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
