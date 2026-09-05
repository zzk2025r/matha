// Matha 可视化编程器 - 编辑器增强功能
// 包括搜索、分组、自动布局等功能

import 'dart:math';
import 'package:flutter/material.dart';
import 'node_types.dart';
import 'connection_system.dart';

/// 编辑器增强控制器
class EditorEnhancements extends ChangeNotifier {

  // ========== 搜索功能 ==========
  
  /// 搜索节点
  List<NodeSearchResult> searchNodes(String keyword) {
    if (keyword.isEmpty) return [];
    
    final results = <NodeSearchResult>[];
    final lowerKeyword = keyword.toLowerCase();
    
    // 搜索已注册的节点类型
    for (final entry in NodeRegistry.get_all().entries) {
      final definition = entry.value;
      if (definition.label.toLowerCase().contains(lowerKeyword) ||
          definition.nodeType.toLowerCase().contains(lowerKeyword) ||
          definition.category.toLowerCase().contains(lowerKeyword)) {
        results.add(NodeSearchResult(
          type: definition.nodeType,
          label: definition.label,
          category: definition.category,
          matchType: _getMatchType(definition, lowerKeyword),
        ));
      }
    }
    
    return results;
  }
  
  String _getMatchType(NodeDefinition definition, String keyword) {
    if (definition.label.toLowerCase().contains(keyword)) return 'label';
    if (definition.nodeType.toLowerCase().contains(keyword)) return 'type';
    if (definition.category.toLowerCase().contains(keyword)) return 'category';
    return 'other';
  }

  // ========== 分组功能 ==========
  
  final Map<String, NodeGroup> _groups = {};
  final Map<String, String> _nodeGroupMap = {};
  
  /// 创建节点组
  String createGroup(String name, List<String> nodeIds) {
    final groupId = DateTime.now().millisecondsSinceEpoch.toString();
    _groups[groupId] = NodeGroup(
      id: groupId,
      name: name,
      nodeIds: nodeIds,
      createdAt: DateTime.now(),
    );
    
    for (final nodeId in nodeIds) {
      _nodeGroupMap[nodeId] = groupId;
    }
    
    notifyListeners();
    return groupId;
  }
  
  /// 将节点添加到组
  void addNodeToGroup(String groupId, String nodeId) {
    if (_groups.containsKey(groupId)) {
      _groups[groupId]!.nodeIds.add(nodeId);
      _nodeGroupMap[nodeId] = groupId;
      notifyListeners();
    }
  }
  
  /// 从组中移除节点
  void removeNodeFromGroup(String groupId, String nodeId) {
    _groups[groupId]?.nodeIds.remove(nodeId);
    _nodeGroupMap.remove(nodeId);
    notifyListeners();
  }
  
  /// 获取节点所属组
  String? getGroupForNode(String nodeId) {
    return _nodeGroupMap[nodeId];
  }
  
  /// 获取所有组
  Map<String, NodeGroup> get groups => Map.from(_groups);
  
  /// 删除组
  void deleteGroup(String groupId) {
    final group = _groups[groupId];
    if (group != null) {
      for (final nodeId in group.nodeIds) {
        _nodeGroupMap.remove(nodeId);
      }
      _groups.remove(groupId);
      notifyListeners();
    }
  }
  
  /// 清空所有组
  void clearAllGroups() {
    _groups.clear();
    _nodeGroupMap.clear();
    notifyListeners();
  }

  // ========== 自动布局功能 ==========
  
  /// 自动布局节点
  void autoLayout(
    Map<String, Offset> nodePositions,
    List<Connection> connections,
    LayoutAlgorithm algorithm,
  ) {
    final sortedNodes = _topologicalSort(nodePositions.keys.toList(), connections);
    
    switch (algorithm) {
      case LayoutAlgorithm.hierarchical:
        _hierarchicalLayout(sortedNodes, nodePositions);
        break;
      case LayoutAlgorithm.forceDirected:
        _forceDirectedLayout(nodePositions, connections);
        break;
      case LayoutAlgorithm.circle:
        _circleLayout(sortedNodes, nodePositions);
        break;
      case LayoutAlgorithm.grid:
        _gridLayout(sortedNodes, nodePositions);
        break;
    }
    
    notifyListeners();
  }
  
  /// 拓扑排序
  List<String> _topologicalSort(List<String> nodeIds, List<Connection> connections) {
    final inDegree = <String, int>{};
    final adjacency = <String, List<String>>{};
    
    for (final id in nodeIds) {
      inDegree[id] = 0;
      adjacency[id] = [];
    }
    
    for (final conn in connections) {
      if (inDegree.containsKey(conn.fromNodeId) && inDegree.containsKey(conn.toNodeId)) {
        adjacency[conn.fromNodeId]!.add(conn.toNodeId);
        inDegree[conn.toNodeId] = (inDegree[conn.toNodeId] ?? 0) + 1;
      }
    }
    
    final queue = <String>[];
    for (final entry in inDegree.entries) {
      if (entry.value == 0) queue.add(entry.key);
    }
    
    final sorted = <String>[];
    while (queue.isNotEmpty) {
      final node = queue.removeAt(0);
      sorted.add(node);
      
      for (final neighbor in adjacency[node]!) {
        inDegree[neighbor] = inDegree[neighbor]! - 1;
        if (inDegree[neighbor] == 0) {
          queue.add(neighbor);
        }
      }
    }
    
    return sorted;
  }
  
  /// 层次布局
  void _hierarchicalLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    final level = <String, int>{};
    final nodePositions = <String, Offset>{};
    
    // 计算层级
    for (final nodeId in sortedNodes) {
      level[nodeId] = 0;
    }
    
    // BFS 计算层级
    final queue = <String>[];
    for (final nodeId in sortedNodes) {
      if (level[nodeId] == 0) queue.add(nodeId);
    }
    
    while (queue.isNotEmpty) {
      queue.removeAt(0);
      for (final _ in sortedNodes) {
        // 简化：假设 sortedNodes 已经按层级排序
      }
    }
    
    // 按层级排列
    final levels = <int, List<String>>{};
    for (final nodeId in sortedNodes) {
      final l = levels[level[nodeId] ?? 0] ?? [];
      l.add(nodeId);
      levels[level[nodeId] ?? 0] = l;
    }
    
    // 计算位置
    const spacingX = 220.0;
    const spacingY = 150.0;
    int col = 0;
    int row = 0;
    
    for (final entry in levels.entries) {
      final nodes = entry.value;
      for (int i = 0; i < nodes.length; i++) {
        nodePositions[nodes[i]] = Offset(col * spacingX, row * spacingY);
      }
      col += nodes.length;
      row++;
    }
    
    positions.clear();
    positions.addAll(nodePositions);
  }
  
  /// 力导向布局
  void _forceDirectedLayout(Map<String, Offset> positions, List<Connection> connections) {
    // 简化实现：圆形布局
    final nodeIds = positions.keys.toList();
    final centerX = 400.0;
    final centerY = 300.0;
    final radius = 200.0;
    
    for (int i = 0; i < nodeIds.length; i++) {
      final angle = (2 * pi * i / nodeIds.length) - pi / 2;
      positions[nodeIds[i]] = Offset(
        centerX + radius * cos(angle),
        centerY + radius * sin(angle),
      );
    }
  }
  
  /// 圆形布局
  void _circleLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    final centerX = 400.0;
    final centerY = 300.0;
    final radius = 180.0;
    
    for (int i = 0; i < sortedNodes.length; i++) {
      final angle = (2 * pi * i / sortedNodes.length) - pi / 2;
      positions[sortedNodes[i]] = Offset(
        centerX + radius * cos(angle),
        centerY + radius * sin(angle),
      );
    }
  }
  
  /// 网格布局
  void _gridLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    const cols = 4;
    const spacingX = 220.0;
    const spacingY = 150.0;
    const startX = 100.0;
    const startY = 100.0;
    
    for (int i = 0; i < sortedNodes.length; i++) {
      final col = i % cols;
      final row = i ~/ cols;
      positions[sortedNodes[i]] = Offset(
        startX + col * spacingX,
        startY + row * spacingY,
      );
    }
  }

  // ========== 快捷键支持 ==========
  
  /// 处理快捷键
  bool handleShortcut(String key) {
    switch (key) {
      case 'Delete':
      case 'Backspace':
        // 删除选中节点
        return true;
      case 'Escape':
        // 取消选择
        return true;
      case 'z':
        if (KeyboardModifiers.ctrl) {
          // 撤销
          return true;
        }
        return false;
      case 'y':
        if (KeyboardModifiers.ctrl) {
          // 重做
          return true;
        }
        return false;
      default:
        return false;
    }
  }
}

/// 节点分组
class NodeGroup {
  final String id;
  final String name;
  final List<String> nodeIds;
  final DateTime createdAt;
  final Color color;
  
  const NodeGroup({
    required this.id,
    required this.name,
    required this.nodeIds,
    required this.createdAt,
    this.color = Colors.blue,
  });
}

/// 键盘修饰符
class KeyboardModifiers {
  static bool ctrl = false;
  static bool shift = false;
  static bool alt = false;
}
