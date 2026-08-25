// Matha 可视化编程器 - 节点类型定义
// 核心数据结构：Node, NodeDefinition, PortDefinition, NodeRegistry, NodeType

import 'dart:ui';
import 'package:flutter/material.dart';

/// 节点端口方向
enum PortDirection { input, output }

/// 节点类型类（类似枚举但支持元数据）
class NodeType {
  final String id;
  final String label;
  final String category;

  const NodeType._(this.id, this.label, this.category);

  // 数学运算
  static const MATH_ADD      = NodeType._('math_add',      '加法',      '数学');
  static const MATH_SUBTRACT = NodeType._('math_subtract', '减法',      '数学');
  static const MATH_MULTIPLY = NodeType._('math_multiply', '乘法',      '数学');
  static const MATH_DIVIDE   = NodeType._('math_divide',   '除法',      '数学');
  static const MATH_SIN      = NodeType._('math_sin',      '正弦',      '数学');
  static const MATH_COS      = NodeType._('math_cos',      '余弦',      '数学');
  static const MATH_TAN      = NodeType._('math_tan',      '正切',      '数学');
  static const MATH_PI       = NodeType._('math_pi',       'π 常量',    '数学');
  static const MATH_E        = NodeType._('math_e',        'e 常量',    '数学');
  static const MATH_SQRT     = NodeType._('math_sqrt',     '平方根',    '数学');
  static const MATH_POWER    = NodeType._('math_power',    '幂运算',    '数学');
  static const MATH_FACTORIAL= NodeType._('math_factorial','阶乘',      '数学');
  static const MATH_ABS      = NodeType._('math_abs',      '绝对值',    '数学');
  static const MATH_FLOOR    = NodeType._('math_floor',    '向下取整',  '数学');
  static const MATH_CEIL     = NodeType._('math_ceil',     '向上取整',  '数学');
  static const MATH_ROUND    = NodeType._('math_round',    '四舍五入',  '数学');
  static const MATH_MOD      = NodeType._('math_mod',      '取模',      '数学');
  static const MATH_LOG      = NodeType._('math_log',      '对数',      '数学');
  static const MATH_LOG10    = NodeType._('math_log10',    '常用对数',  '数学');
  static const MATH_RANDOM   = NodeType._('math_random',   '随机数',    '数学');

  // 逻辑运算
  static const LOGIC_AND     = NodeType._('logic_and',     '与',        '逻辑');
  static const LOGIC_OR      = NodeType._('logic_or',      '或',        '逻辑');
  static const LOGIC_NOT     = NodeType._('logic_not',     '非',        '逻辑');
  static const LOGIC_EQUAL   = NodeType._('logic_equal',   '等于',      '逻辑');
  static const LOGIC_NEQ     = NodeType._('logic_neq',     '不等于',    '逻辑');
  static const LOGIC_GT      = NodeType._('logic_gt',      '大于',      '逻辑');
  static const LOGIC_LT      = NodeType._('logic_lt',      '小于',      '逻辑');
  static const LOGIC_GTE     = NodeType._('logic_gte',     '大于等于',  '逻辑');
  static const LOGIC_LTE     = NodeType._('logic_lte',     '小于等于',  '逻辑');

  // 变量与数据
  static const STRING      = NodeType._('string',      '字符串',  '数据');
  static const NUMBER      = NodeType._('number',      '数字',    '数据');
  static const BOOLEAN     = NodeType._('boolean',     '布尔',    '数据');
  static const VARIABLE    = NodeType._('variable',    '变量',    '数据');
  static const ASSIGN      = NodeType._('assign',      '赋值',    '数据');
  static const SEQUENCE    = NodeType._('sequence',    '序列',    '数据');
  static const LIST        = NodeType._('list',        '列表',    '数据');
  static const DICTIONARY  = NodeType._('dictionary',  '字典',    '数据');
  static const NULL_VALUE  = NodeType._('null_value',  '空值',    '数据');

  // 控制流
  static const IF         = NodeType._('if',         '条件判断', '控制流');
  static const ELSE       = NodeType._('else',       '否则',     '控制流');
  static const FOR        = NodeType._('for',        'FOR循环',  '控制流');
  static const WHILE      = NodeType._('while',      'WHILE循环','控制流');
  static const BREAK      = NodeType._('break',      '中断',     '控制流');
  static const CONTINUE   = NodeType._('continue',   '继续',     '控制流');
  static const RETURN     = NodeType._('return',     '返回',     '控制流');

  // 函数
  static const FUNCTION      = NodeType._('function',      '函数定义', '函数');
  static const FUNCTION_CALL = NodeType._('function_call', '函数调用', '函数');
  static const LAMBDA        = NodeType._('lambda',        'Lambda',   '函数');
  static const MAP           = NodeType._('map',           'Map',      '函数');
  static const FILTER        = NodeType._('filter',        'Filter',   '函数');
  static const REDUCE        = NodeType._('reduce',        'Reduce',   '函数');

  // IO
  static const INPUT  = NodeType._('input',  '输入', 'IO');
  static const OUTPUT = NodeType._('output', '输出', 'IO');

  // 矩阵
  static const MATRIX_CREATE = NodeType._('matrix_create',  '创建矩阵', '矩阵');
  static const MATRIX_ADD    = NodeType._('matrix_add',     '矩阵加法', '矩阵');
  static const MATRIX_MULT   = NodeType._('matrix_mult',    '矩阵乘法', '矩阵');
  static const MATRIX_TRANS  = NodeType._('matrix_trans',   '矩阵转置', '矩阵');
  static const MATRIX_DET    = NodeType._('matrix_det',     '矩阵行列式','矩阵');
  static const MATRIX_INV    = NodeType._('matrix_inv',     '矩阵求逆', '矩阵');

  // 统计
  static const STATS_MEAN   = NodeType._('stats_mean',   '平均值', '统计');
  static const STATS_MEDIAN = NodeType._('stats_median', '中位数', '统计');
  static const STATS_MODE   = NodeType._('stats_mode',   '众数',   '统计');
  static const STATS_STD    = NodeType._('stats_std',    '标准差', '统计');
  static const STATS_VAR    = NodeType._('stats_var',    '方差',   '统计');
  static const STATS_SUM    = NodeType._('stats_sum',    '求和',   '统计');
  static const STATS_MAX    = NodeType._('stats_max',    '最大值', '统计');
  static const STATS_MIN    = NodeType._('stats_min',    '最小值', '统计');

  // 线性代数
  static const LINALG_IDENTITY = NodeType._('linalg_identity', '单位矩阵', '线性代数');
  static const LINALG_EIGEN    = NodeType._('linalg_eigen',    '特征值', '线性代数');
  static const LINALG_DECOMP   = NodeType._('linalg_decomp',   '分解',   '线性代数');

  // 高级
  static const CONSTANT   = NodeType._('constant',    '常量',    '高级');
  static const ADVANCED_MATH = NodeType._('advanced_math', '高等数学', '高级');
  static const SYMBOLIC   = NodeType._('symbolic',    '符号计算', '高级');

  @override
  String toString() => id;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is NodeType && runtimeType == other.runtimeType && id == other.id;

  @override
  int get hashCode => id.hashCode;
}

/// 节点端口定义
class PortDefinition {
  final String name;
  final String type;
  final bool optional;
  final String description;
  final dynamic defaultValue;

  const PortDefinition(
    this.name,
    this.type,
    this.optional,
    this.description, {
    this.defaultValue,
  });

  Map<String, dynamic> toMap() => {
    'name': name,
    'type': type,
    'optional': optional,
    'description': description,
    'default': defaultValue,
  };

  factory PortDefinition.fromMap(Map<String, dynamic> map) => PortDefinition(
    map['name'] as String,
    map['type'] as String,
    map['optional'] as bool,
    map['description'] as String? ?? '',
    defaultValue: map['default'],
  );
}

/// 节点定义
class NodeDefinition {
  final String nodeType;
  final String label;
  final String description;
  final List<PortDefinition> inputs;
  final List<PortDefinition> outputs;
  final String category;
  final IconData icon;
  final Map<String, dynamic>? defaultValues;

  const NodeDefinition({
    required this.nodeType,
    required this.label,
    required this.description,
    this.inputs = const [],
    this.outputs = const [],
    required this.category,
    required this.icon,
    this.defaultValues,
  });

  Map<String, dynamic> toMap() => {
    'nodeType': nodeType,
    'label': label,
    'description': description,
    'inputs': inputs.map((p) => p.toMap()).toList(),
    'outputs': outputs.map((p) => p.toMap()).toList(),
    'category': category,
    'icon': icon.codePoint,
    'defaultValues': defaultValues,
  };

  factory NodeDefinition.fromMap(Map<String, dynamic> map) => NodeDefinition(
    nodeType: map['nodeType'] as String,
    label: map['label'] as String,
    description: map['description'] as String,
    inputs: (map['inputs'] as List?)
            ?.map((p) => PortDefinition.fromMap(p as Map<String, dynamic>))
            .toList() ??
        [],
    outputs: (map['outputs'] as List?)
            ?.map((p) => PortDefinition.fromMap(p as Map<String, dynamic>))
            .toList() ??
        [],
    category: map['category'] as String,
    icon: IconData(map['icon'] as int, fontFamily: 'MaterialIcons'),
    defaultValues: map['defaultValues'] as Map<String, dynamic>?,
  );
}

/// 节点实例
class Node {
  final String id;
  final String nodeType;
  final Offset position;
  final Map<String, dynamic> values;
  final Map<String, dynamic> ports;

  const Node({
    required this.id,
    required this.nodeType,
    required this.position,
    this.values = const {},
    this.ports = const {},
  });

  NodeDefinition? get definition => NodeRegistry.get(nodeType);

  Map<String, dynamic> toMap() => {
    'id': id,
    'nodeType': nodeType,
    'position': [position.dx, position.dy],
    'values': values,
    'ports': ports,
  };

  factory Node.fromMap(Map<String, dynamic> map) => Node(
    id: map['id'] as String,
    nodeType: map['nodeType'] as String,
    position: Offset(
      (map['position'] as List).first.toDouble(),
      (map['position'] as List).last.toDouble(),
    ),
    values: (map['values'] as Map?)?.cast<String, dynamic>() ?? {},
    ports: (map['ports'] as Map?)?.cast<String, dynamic>() ?? {},
  );
}

/// 节点搜索的结果
class NodeSearchResult {
  final String type;
  final String label;
  final String category;
  final String matchType;

  const NodeSearchResult({
    required this.type,
    required this.label,
    required this.category,
    required this.matchType,
  });
}

/// 节点分组
class NodeGroup {
  final String id;
  final String name;
  final List<String> nodeIds;
  final DateTime createdAt;

  const NodeGroup({
    required this.id,
    required this.name,
    required this.nodeIds,
    required this.createdAt,
  });
}

/// 布局算法
enum LayoutAlgorithm { hierarchical, forceDirected, circle, grid }

/// 连接点信息
class PortInfo {
  final String nodeId;
  final String portName;
  final PortDirection direction;
  final Offset screenPosition;

  const PortInfo({
    required this.nodeId,
    required this.portName,
    required this.direction,
    required this.screenPosition,
  });
}

/// 节点注册表（全局单例）
class NodeRegistry {
  static final Map<String, NodeDefinition> _registry = {};

  /// 注册节点定义
  static void register(NodeDefinition definition) {
    _registry[definition.nodeType] = definition;
  }

  /// 获取节点定义
  static NodeDefinition? get(String nodeType) => _registry[nodeType];

  /// 获取所有已注册节点
  static Map<String, NodeDefinition> get_all() => Map.unmodifiable(_registry);

  /// 按类别获取节点
  static List<NodeDefinition> get_by_category(String category) {
    return _registry.values
        .where((def) => def.category == category)
        .toList();
  }

  /// 检查节点是否已注册
  static bool contains(String nodeType) => _registry.containsKey(nodeType);

  /// 清空注册表
  static void clear() => _registry.clear();

  /// 注册基础数学节点
  static void registerDefaults() {
    register(const NodeDefinition(
      nodeType: 'math_add',
      label: '加法',
      description: '两个数相加',
      inputs: [
        PortDefinition('a', 'number', false, ''),
        PortDefinition('b', 'number', false, ''),
      ],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.add,
    ));
    register(const NodeDefinition(
      nodeType: 'math_subtract',
      label: '减法',
      description: '两个数相减',
      inputs: [
        PortDefinition('a', 'number', false, ''),
        PortDefinition('b', 'number', false, ''),
      ],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.remove,
    ));
    register(const NodeDefinition(
      nodeType: 'math_multiply',
      label: '乘法',
      description: '两个数相乘',
      inputs: [
        PortDefinition('a', 'number', false, ''),
        PortDefinition('b', 'number', false, ''),
      ],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.add,
    ));
    register(const NodeDefinition(
      nodeType: 'math_divide',
      label: '除法',
      description: '两个数相除',
      inputs: [
        PortDefinition('a', 'number', false, ''),
        PortDefinition('b', 'number', false, ''),
      ],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.remove_circle,
    ));
    register(const NodeDefinition(
      nodeType: 'constant',
      label: '常量',
      description: '返回一个固定数值',
      inputs: [],
      outputs: [PortDefinition('value', 'number', false, '')],
      category: '高级',
      icon: Icons.calculate,
      defaultValues: {'value': 0.0},
    ));
    register(const NodeDefinition(
      nodeType: 'if',
      label: '条件分支',
      description: '根据条件选择输出',
      inputs: [
        PortDefinition('condition', 'boolean', false, ''),
        PortDefinition('then', 'any', false, ''),
        PortDefinition('else', 'any', false, ''),
      ],
      outputs: [PortDefinition('result', 'any', false, '')],
      category: '控制流',
      icon: Icons.arrow_right,
    ));
    register(const NodeDefinition(
      nodeType: 'output',
      label: '输出',
      description: '输出值到控制台',
      inputs: [PortDefinition('value', 'any', false, '')],
      outputs: [],
      category: 'IO',
      icon: Icons.output,
    ));
    register(const NodeDefinition(
      nodeType: 'input',
      label: '输入',
      description: '获取用户输入',
      inputs: [],
      outputs: [PortDefinition('value', 'any', false, '')],
      category: 'IO',
      icon: Icons.input,
      defaultValues: {'prompt': '请输入'},
    ));
  }
}
