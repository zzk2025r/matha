// Matha 可视化编程器 - 编辑器工具栏
// 提供添加节点、清空、导出、导入等功能

import 'package:flutter/material.dart';
import 'node_types.dart';

class EditorToolbar extends StatelessWidget {
  final Function(NodeType) onAddNode;
  final VoidCallback onClear;
  final VoidCallback onExport;
  final VoidCallback onImport;
  final int nodeCount;
  final int connectionCount;

  const EditorToolbar({
    super.key,
    required this.onAddNode,
    required this.onClear,
    required this.onExport,
    required this.onImport,
    required this.nodeCount,
    required this.connectionCount,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outlineVariant)),
      ),
      child: Row(
        children: [
          // 标题
          const Text(
            'Matha 节点编辑器',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const Spacer(),
          
          // 统计信息
          _StatChip(label: '节点', value: nodeCount.toString()),
          const SizedBox(width: 8),
          _StatChip(label: '连线', value: connectionCount.toString()),
          const SizedBox(width: 16),
          
          // 添加节点菜单
          PopupMenuButton<NodeType>(
            icon: const Icon(Icons.add_circle_outline),
            tooltip: '添加节点',
            onSelected: (type) => onAddNode(type),
            itemBuilder: (context) => [
              const PopupMenuItem(value: NodeType.MATH_ADD, child: Text('数学运算')),
              const PopupMenuItem(value: NodeType.LOGIC_AND, child: Text('逻辑运算')),
              const PopupMenuItem(value: NodeType.VARIABLE, child: Text('变量')),
              const PopupMenuItem(value: NodeType.INPUT, child: Text('输入')),
              const PopupMenuItem(value: NodeType.OUTPUT, child: Text('输出')),
              const PopupMenuItem(value: NodeType.IF, child: Text('条件判断')),
              const PopupMenuItem(value: NodeType.MATRIX_CREATE, child: Text('矩阵')),
              const PopupMenuItem(value: NodeType.STATS_MEAN, child: Text('统计')),
            ],
          ),
          
          const SizedBox(width: 8),
          
          // 清空
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: '清空',
            onPressed: onClear,
          ),
          
          // 导出
          IconButton(
            icon: const Icon(Icons.download),
            tooltip: '导出',
            onPressed: onExport,
          ),
          
          // 导入
          IconButton(
            icon: const Icon(Icons.upload),
            tooltip: '导入',
            onPressed: onImport,
          ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;

  const _StatChip({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text('$label: $value'),
      visualDensity: VisualDensity.compact,
      backgroundColor: Theme.of(context).colorScheme.secondaryContainer,
    );
  }
}
