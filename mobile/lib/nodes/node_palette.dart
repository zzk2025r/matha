// Matha 可视化编程器 - 节点调色板
// 显示可添加的节点列表

import 'package:flutter/material.dart';
import 'node_types.dart';

class NodePalette extends StatelessWidget {
  final NodeType nodeType;
  final Function(NodeType) onAddNode;

  const NodePalette({
    super.key,
    required this.nodeType,
    required this.onAddNode,
  });

  @override
  Widget build(BuildContext context) {
    final nodes = NodeRegistry.get_by_category(nodeType.toString().split('.').last);
    
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '选择 ${nodeType.toString().split('.').last} 节点',
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
                  onTap: () => onAddNode(node.nodeType),
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
              Icon(_getIcon(NodeType.values.firstWhere((t) => t.id == node.nodeType, orElse: () => NodeType.MATH_ADD)), size: 32, color: _getColor(node.category)),
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

  IconData _getIcon(NodeType type) {
    switch (type) {
      case NodeType.MATH_ADD:
      case NodeType.MATH_SUBTRACT:
      case NodeType.MATH_MULTIPLY:
      case NodeType.MATH_DIVIDE:
        return Icons.calculate;
      case NodeType.MATH_SIN:
      case NodeType.MATH_COS:
      case NodeType.MATH_TAN:
        return Icons.science;
      case NodeType.LOGIC_AND:
      case NodeType.LOGIC_OR:
      case NodeType.LOGIC_NOT:
        return Icons.compare_arrows;
      case NodeType.VARIABLE:
      case NodeType.ASSIGN:
        return Icons.variable_channel;
      case NodeType.INPUT:
        return Icons.input;
      case NodeType.OUTPUT:
        return Icons.output;
      case NodeType.IF:
        return Icons.flow_chart;
      case NodeType.MATRIX_CREATE:
        return Icons.grid_on;
      case NodeType.STATS_MEAN:
        return Icons.analytics;
      case NodeType.MATH_PI:
      case NodeType.MATH_E:
        return Icons.constant;
      case NodeType.SEQUENCE:
        return Icons.format_list_numbered;
      default:
        return Icons.help;
    }
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
