// Matha 可视化编程器 - 节点调色板
// 显示可添加的节点列表

import 'package:flutter/material.dart';
import 'node_types.dart';

class NodePalette extends StatelessWidget {
  final String category;
  final Function(NodeDefinition) onAddNode;

  const NodePalette({
    super.key,
    required this.category,
    required this.onAddNode,
  });

  @override
  Widget build(BuildContext context) {
    final nodes = NodeRegistry.get_by_category(category);
    
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '选择 $category 节点',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 1.5,
                crossAxisSpacing: 8,
                mainAxisSpacing: 8,
              ),
              itemCount: nodes.length,
              itemBuilder: (context, index) {
                final node = nodes[index];
                return _NodeCard(
                  node: node,
                  onTap: () => onAddNode(node),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _NodeCard extends StatelessWidget {
  final NodeDefinition node;
  final VoidCallback onTap;

  const _NodeCard({required this.node, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(_getIconFromDef(node), size: 32, color: _getColor(node.category)),
              const SizedBox(height: 4),
              Text(
                node.label,
                style: const TextStyle(fontSize: 12),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                '${node.inputs.length}入/${node.outputs.length}出',
                style: const TextStyle(fontSize: 9, color: Colors.grey),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getIconFromDef(NodeDefinition def) {
    final id = def.nodeType;
    if (id == NodeType.MATH_ADD.id || id == NodeType.MATH_SUBTRACT.id ||
        id == NodeType.MATH_MULTIPLY.id || id == NodeType.MATH_DIVIDE.id) {
      return Icons.calculate;
    }
    if (id == NodeType.MATH_SIN.id || id == NodeType.MATH_COS.id || id == NodeType.MATH_TAN.id) {
      return Icons.science;
    }
    if (id == NodeType.LOGIC_AND.id || id == NodeType.LOGIC_OR.id || id == NodeType.LOGIC_NOT.id) {
      return Icons.compare_arrows;
    }
    if (id == NodeType.VARIABLE.id || id == NodeType.ASSIGN.id) {
      return Icons.tune;
    }
    if (id == NodeType.INPUT.id) {
      return Icons.input;
    }
    if (id == NodeType.OUTPUT.id) {
      return Icons.output;
    }
    if (id == NodeType.IF.id) {
      return Icons.account_tree;
    }
    if (id == NodeType.MATRIX_CREATE.id) {
      return Icons.grid_on;
    }
    if (id == NodeType.STATS_MEAN.id) {
      return Icons.analytics;
    }
    if (id == NodeType.MATH_PI.id || id == NodeType.MATH_E.id) {
      return Icons.numbers;
    }
    if (id == NodeType.SEQUENCE.id) {
      return Icons.format_list_numbered;
    }
    return Icons.help;
  }

  Color _getColor(String category) {
    switch (category) {
      case '数学':
        return Colors.blue;
      case '逻辑':
        return Colors.green;
      case '变量':
        return Colors.orange;
      case '输入输出':
        return Colors.purple;
      case '控制流':
        return Colors.red;
      case '矩阵':
        return Colors.teal;
      case '统计':
        return Colors.pink;
      case '常量':
        return Colors.grey;
      case '序列':
        return Colors.indigo;
      default:
        return Colors.grey;
    }
  }
}
