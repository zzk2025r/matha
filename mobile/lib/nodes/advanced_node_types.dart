// Matha 可视化编程器 - 高级节点类型
// 包括循环、函数、列表操作等复杂节点

import 'package:flutter/material.dart';
import 'node_types.dart';

/// 高级节点类型定义
class AdvancedNodeTypes {
  /// 注册所有高级节点
  static void registerAll() {
    _registerLoopNodes();
    _registerFunctionNodes();
    _registerListNodes();
    _registerStringNodes();
    _registerMathAdvancedNodes();
  }

  /// 注册循环节点
  static void _registerLoopNodes() {
    debugPrint('[高级节点] 注册循环节点...');
    // FOR 循环节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'for_loop',
      label: 'FOR 循环',
      description: '对列表中的每个元素执行操作',
      inputs: [
        PortDefinition('list', 'list', true, '输入列表'),
        PortDefinition('index', 'number', true, '起始索引', defaultValue: 0),
        PortDefinition('step', 'number', true, '步长', defaultValue: 1),
      ],
      outputs: [
        PortDefinition('item', 'any', false, '当前元素'),
        PortDefinition('index', 'number', false, '当前索引'),
        PortDefinition('done', 'boolean', false, '循环完成'),
      ],
      category: '控制流',
      icon: Icons.repeat,
    ));

    // WHILE 循环节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'while_loop',
      label: 'WHILE 循环',
      description: '当条件为真时重复执行',
      inputs: [
        PortDefinition('condition', 'boolean', true, '循环条件'),
        PortDefinition('body_start', 'any', true, '循环体入口'),
      ],
      outputs: [
        PortDefinition('body_end', 'any', false, '循环体出口'),
        PortDefinition('done', 'boolean', false, '循环完成'),
      ],
      category: '控制流',
      icon: Icons.autorenew,
    ));

    // 迭代器节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'iterator',
      label: '迭代器',
      description: '生成迭代器对象',
      inputs: [
        PortDefinition('source', 'any', true, '源数据'),
      ],
      outputs: [
        PortDefinition('next', 'any', false, '下一个元素'),
        PortDefinition('has_next', 'boolean', false, '是否有下一个'),
      ],
      category: '控制流',
      icon: Icons.arrow_forward,
    ));
  }

  /// 注册函数节点
  static void _registerFunctionNodes() {
    debugPrint('[高级节点] 注册函数节点...');
    // 函数定义节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'function_def',
      label: '函数定义',
      description: '定义一个可复用的函数',
      inputs: [
        PortDefinition('param_1', 'any', true, '参数 1'),
        PortDefinition('param_2', 'any', true, '参数 2'),
      ],
      outputs: [
        PortDefinition('function', 'function', false, '函数对象'),
      ],
      category: '函数',
      icon: Icons.functions,
    ));

    // 函数调用节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'function_call',
      label: '函数调用',
      description: '调用已定义的函数',
      inputs: [
        PortDefinition('func', 'function', true, '函数对象'),
        PortDefinition('arg_1', 'any', true, '参数 1'),
        PortDefinition('arg_2', 'any', true, '参数 2'),
      ],
      outputs: [
        PortDefinition('result', 'any', false, '返回值'),
      ],
      category: '函数',
      icon: Icons.play_arrow,
    ));

    // Lambda 节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'lambda',
      label: 'Lambda',
      description: '定义匿名函数',
      inputs: [
        PortDefinition('input', 'any', true, '输入'),
      ],
      outputs: [
        PortDefinition('output', 'any', false, '输出'),
      ],
      category: '函数',
      icon: Icons.code,
    ));
  }

  /// 注册列表操作节点
  static void _registerListNodes() {
    // 创建列表节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_create',
      label: '创建列表',
      description: '创建一个新列表',
      inputs: [
        PortDefinition('item_1', 'any', true, defaultValue: null, '元素 1'),
        PortDefinition('item_2', 'any', true, defaultValue: null, '元素 2'),
        PortDefinition('item_3', 'any', true, defaultValue: null, '元素 3'),
      ],
      outputs: [
        PortDefinition('list', 'list', false, '列表'),
      ],
      category: '列表',
      icon: Icons.format_list_bulleted,
    ));

    // 列表追加节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_append',
      label: '追加元素',
      description: '向列表添加元素',
      inputs: [
        PortDefinition('list', 'list', true, '原列表'),
        PortDefinition('item', 'any', true, '要添加的元素'),
      ],
      outputs: [
        PortDefinition('new_list', 'list', false, '新列表'),
      ],
      category: '列表',
      icon: Icons.add_to_queue,
    ));

    // 列表索引节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_index',
      label: '列表索引',
      description: '获取列表中的元素',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
        PortDefinition('index', 'number', true, defaultValue: 0, '索引'),
      ],
      outputs: [
        PortDefinition('item', 'any', false, '元素值'),
      ],
      category: '列表',
      icon: Icons.grid_on,
    ));

    // 列表切片节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_slice',
      label: '列表切片',
      description: '获取列表的子序列',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
        PortDefinition('start', 'number', true, '起始索引', defaultValue: 0),
        PortDefinition('end', 'number', true, '结束索引', defaultValue: -1),
      ],
      outputs: [
        PortDefinition('slice', 'list', false, '切片结果'),
      ],
      category: '列表',
      icon: Icons.cut,
    ));

    // 列表长度节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_length',
      label: '列表长度',
      description: '获取列表长度',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
      ],
      outputs: [
        PortDefinition('length', 'number', false, '长度'),
      ],
      category: '列表',
      icon: Icons.straighten,
    ));

    // 列表合并节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_merge',
      label: '合并列表',
      description: '合并两个列表',
      inputs: [
        PortDefinition('list1', 'list', true, '列表 1'),
        PortDefinition('list2', 'list', true, '列表 2'),
      ],
      outputs: [
        PortDefinition('merged', 'list', false, '合并结果'),
      ],
      category: '列表',
      icon: Icons.merge_type,
    ));

    // 列表反转节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_reverse',
      label: '反转列表',
      description: '反转列表顺序',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
      ],
      outputs: [
        PortDefinition('reversed', 'list', false, '反转结果'),
      ],
      category: '列表',
      icon: Icons.swap_horiz,
    ));

    // 列表过滤节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_filter',
      label: '过滤列表',
      description: '根据条件过滤列表',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
        PortDefinition('condition', 'boolean', true, '过滤条件'),
      ],
      outputs: [
        PortDefinition('filtered', 'list', false, '过滤结果'),
      ],
      category: '列表',
      icon: Icons.filter_list,
    ));

    // 列表映射节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_map',
      label: '映射列表',
      description: '对列表每个元素应用函数',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
        PortDefinition('func', 'function', true, '映射函数'),
      ],
      outputs: [
        PortDefinition('mapped', 'list', false, '映射结果'),
      ],
      category: '列表',
      icon: Icons.transform,
    ));

    // 列表排序节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'list_sort',
      label: '排序列表',
      description: '对列表进行排序',
      inputs: [
        PortDefinition('list', 'list', true, '列表'),
        PortDefinition('reverse', 'boolean', true, '降序', defaultValue: false),
      ],
      outputs: [
        PortDefinition('sorted', 'list', false, '排序结果'),
      ],
      category: '列表',
      icon: Icons.sort,
    ));
  }

  /// 注册字符串操作节点
  static void _registerStringNodes() {
    debugPrint('[高级节点] 注册字符串操作节点...');
    // 字符串拼接节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_concat',
      label: '拼接字符串',
      description: '拼接多个字符串',
      inputs: [
        PortDefinition('str1', 'string', true, '字符串 1'),
        PortDefinition('str2', 'string', true, '字符串 2'),
      ],
      outputs: [
        PortDefinition('result', 'string', false, '拼接结果'),
      ],
      category: '字符串',
      icon: Icons.text_fields,
    ));

    // 字符串分割节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_split',
      label: '分割字符串',
      description: '按分隔符分割字符串',
      inputs: [
        PortDefinition('str', 'string', true, '字符串'),
        PortDefinition('delimiter', 'string', true, '分隔符', defaultValue: ','),
      ],
      outputs: [
        PortDefinition('parts', 'list', false, '分割结果'),
      ],
      category: '字符串',
      icon: Icons.text_fields,
    ));

    // 字符串替换节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_replace',
      label: '替换字符串',
      description: '替换字符串中的子串',
      inputs: [
        PortDefinition('str', 'string', true, '原字符串'),
        PortDefinition('old', 'string', true, '被替换子串'),
        PortDefinition('new', 'string', true, '新子串'),
      ],
      outputs: [
        PortDefinition('result', 'string', false, '替换结果'),
      ],
      category: '字符串',
      icon: Icons.swap_horiz,
    ));

    // 字符串长度节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_length',
      label: '字符串长度',
      description: '获取字符串长度',
      inputs: [
        PortDefinition('str', 'string', true, '字符串'),
      ],
      outputs: [
        PortDefinition('length', 'number', false, '长度'),
      ],
      category: '字符串',
      icon: Icons.straighten,
    ));

    // 字符串转大写节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_upper',
      label: '转大写',
      description: '将字符串转为大写',
      inputs: [
        PortDefinition('str', 'string', true, '字符串'),
      ],
      outputs: [
        PortDefinition('result', 'string', false, '大写结果'),
      ],
      category: '字符串',
      icon: Icons.title,
    ));

    // 字符串转小写节点
    NodeRegistry.register(NodeDefinition(
      nodeType: 'string_lower',
      label: '转小写',
      description: '将字符串转为小写',
      inputs: [
        PortDefinition('str', 'string', true, '字符串'),
      ],
      outputs: [
        PortDefinition('result', 'string', false, '小写结果'),
      ],
      category: '字符串',
      icon: Icons.title,
    ));
  }

  /// 注册高级数学节点
  static void _registerMathAdvancedNodes() {
    debugPrint('[高级节点] 注册高级数学节点...');
    // 绝对值
    NodeRegistry.register(NodeDefinition(
      nodeType: 'math_abs',
      label: '绝对值',
      description: '求绝对值',
      inputs: [PortDefinition('x', 'number', true, '')],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.calculate,
    ));

    // 取整
    NodeRegistry.register(NodeDefinition(
      nodeType: 'math_round',
      label: '四舍五入',
      description: '四舍五入到整数',
      inputs: [PortDefinition('x', 'number', true, '')],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.calculate,
    ));

    // 随机数
    NodeRegistry.register(NodeDefinition(
      nodeType: 'math_random',
      label: '随机数',
      description: '生成随机数',
      inputs: [
        PortDefinition('min', 'number', true, '', defaultValue: 0),
        PortDefinition('max', 'number', true, '', defaultValue: 100),
      ],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.casino,
    ));

    // 阶乘
    NodeRegistry.register(NodeDefinition(
      nodeType: 'math_factorial',
      label: '阶乘',
      description: '计算阶乘',
      inputs: [PortDefinition('n', 'number', true, '')],
      outputs: [PortDefinition('result', 'number', false, '')],
      category: '数学',
      icon: Icons.calculate,
    ));
  }
}

/// 节点执行函数映射
typedef NodeExecutor = Map<String, dynamic> Function(dynamic, Map<String, dynamic>, dynamic);

final Map<String, NodeExecutor> nodeExecuteFunctions = {
  // 循环节点
  'for_loop': (node, inputs, context) => {
    'item': inputs['list']?[inputs['index']?.toInt() ?? 0],
    'index': inputs['index'],
    'done': false,
  },
  'while_loop': (node, inputs, context) => {
    'body_end': inputs['body_start'],
    'done': !inputs['condition'],
  },
  'iterator': (node, inputs, context) => {
    'next': null,
    'has_next': inputs['source'] != null,
  },

  // 函数节点
  'function_def': (node, inputs, context) => {'function': node},
  'function_call': (node, inputs, context) => {'result': inputs['arg_1']},
  'lambda': (node, inputs, context) => {'output': inputs['input']},

  // 列表节点
  'list_create': (node, inputs, context) => {
    'list': [
      inputs['item_1'],
      if (inputs['item_2'] != null) inputs['item_2'],
      if (inputs['item_3'] != null) inputs['item_3'],
    ].where((e) => e != null).toList(),
  },
  'list_append': (node, inputs, context) {
    final list = List.from(inputs['list'] ?? []);
    list.add(inputs['item']);
    return {'new_list': list};
  },
  'list_index': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    final index = inputs['index']?.toInt() ?? 0;
    return {'item': list[index]};
  },
  'list_slice': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    final start = inputs['start']?.toInt() ?? 0;
    final end = inputs['end']?.toInt() ?? list.length;
    return {'slice': list.sublist(start, end)};
  },
  'list_length': (node, inputs, context) => {'length': (inputs['list'] ?? []).length},
  'list_merge': (node, inputs, context) {
    final list1 = inputs['list1'] ?? [];
    final list2 = inputs['list2'] ?? [];
    return {'merged': [...list1, ...list2]};
  },
  'list_reverse': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    return {'reversed': list.reversed.toList()};
  },
  'list_filter': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    return {'filtered': list};
  },
  'list_map': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    return {'mapped': list};
  },
  'list_sort': (node, inputs, context) {
    final list = inputs['list'] ?? [];
    list.sort();
    return {'sorted': list};
  },

  // 字符串节点
  'string_concat': (node, inputs, context) {
    final str1 = inputs['str1']?.toString() ?? '';
    final str2 = inputs['str2']?.toString() ?? '';
    return {'result': '$str1$str2'};
  },
  'string_split': (node, inputs, context) {
    final str = inputs['str']?.toString() ?? '';
    final delimiter = inputs['delimiter']?.toString() ?? ',';
    return {'parts': str.split(delimiter)};
  },
  'string_replace': (node, inputs, context) {
    final str = inputs['str']?.toString() ?? '';
    final old = inputs['old']?.toString() ?? '';
    final newStr = inputs['new']?.toString() ?? '';
    return {'result': str.replaceAll(old, newStr)};
  },
  'string_length': (node, inputs, context) {
    final str = inputs['str']?.toString() ?? '';
    return {'length': str.length};
  },
  'string_upper': (node, inputs, context) {
    final str = inputs['str']?.toString() ?? '';
    return {'result': str.toUpperCase()};
  },
  'string_lower': (node, inputs, context) {
    final str = inputs['str']?.toString() ?? '';
    return {'result': str.toLowerCase()};
  },

  // 高级数学节点
  'math_abs': (node, inputs, context) => {'result': (inputs['x'] ?? 0).abs()},
  'math_round': (node, inputs, context) => {'result': (inputs['x'] ?? 0).round()},
  'math_random': (node, inputs, context) {
    final min = inputs['min'] ?? 0;
    final max = inputs['max'] ?? 100;
    return {'result': min + (max - min) * DateTime.now().millisecondsSinceEpoch % 1000 / 1000};
  },
  'math_factorial': (node, inputs, context) {
    final n = inputs['n']?.toInt() ?? 0;
    int result = 1;
    for (int i = 2; i <= n; i++) result *= i;
    return {'result': result};
  },
};
