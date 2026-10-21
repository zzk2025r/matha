// Matha Pyodide 离线帮助/补全服务
// 离线 API 文档、代码补全、语法提示、智能建议

import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// 补全项
class CompletionItem {
  final String label;
  final String kind;
  final String detail;
  final String documentation;
  final String insertText;
  final int sortText;

  const CompletionItem({
    required this.label,
    required this.kind,
    required this.detail,
    required this.documentation,
    required this.insertText,
    this.sortText = 0,
  });

  factory CompletionItem.fromJson(Map<String, dynamic> json) {
    return CompletionItem(
      label: json['label'] as String,
      kind: json['kind'] as String,
      detail: json['detail'] as String? ?? '',
      documentation: json['documentation'] as String? ?? '',
      insertText: json['insertText'] as String,
      sortText: json['sortText'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'label': label,
        'kind': kind,
        'detail': detail,
        'documentation': documentation,
        'insertText': insertText,
        'sortText': sortText,
      };
}

/// 补全结果
class CompletionResult {
  final List<CompletionItem> items;
  final bool isIncomplete;
  final DateTime timestamp;

  const CompletionResult({
    required this.items,
    this.isIncomplete = false,
    required this.timestamp,
  });
}

/// API 文档项
class ApiDocItem {
  final String name;
  final String module;
  final String signature;
  final String description;
  final String returnType;
  final List<String> examples;
  final List<String> params;

  const ApiDocItem({
    required this.name,
    required this.module,
    required this.signature,
    required this.description,
    required this.returnType,
    this.examples = const [],
    this.params = const [],
  });
}

/// Pyodide 离线补全器
class PyodideOfflineCompleter extends ChangeNotifier {
  static final PyodideOfflineCompleter _instance =
      PyodideOfflineCompleter._internal();
  factory PyodideOfflineCompleter() => _instance;
  PyodideOfflineCompleter._internal();

  bool _isLoaded = false;
  bool _isLoading = false;
  final Map<String, List<CompletionItem>> _completionsByModule = {};
  final Map<String, ApiDocItem> _apiDocs = {};
  final Map<String, List<String>> _keywords = {};
  final List<String> _recentCompletions = [];

  bool get isLoaded => _isLoaded;
  bool get isLoading => _isLoading;
  int get totalCompletions => _completionsByModule.values.fold<int>(
        0,
        (sum, list) => sum + list.length,
      );
  int get totalDocs => _apiDocs.length;

  /// 初始化离线补全库
  Future<void> initialize() async {
    if (_isLoaded || _isLoading) return;
    
    _isLoading = true;
    notifyListeners();
    
    try {
      await _loadBuiltinCompletions();
      await _loadMathCompletions();
      await _loadPythonKeywords();
      await _loadApiDocs();
      
      _isLoaded = true;
      _isLoading = false;
      debugPrint('[Completer] 离线补全库加载完成：${totalCompletions} 个补全项，${totalDocs} 个文档');
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      debugPrint('[Completer] 离线补全库加载失败: $e');
      notifyListeners();
    }
  }

  Future<void> _loadBuiltinCompletions() async {
    final builtinList = [
      CompletionItem(
        label: 'print',
        kind: 'function',
        detail: '内置函数',
        documentation: '输出对象到标准输出流',
        insertText: 'print()',
        sortText: 1,
      ),
      CompletionItem(
        label: 'len',
        kind: 'function',
        detail: '内置函数',
        documentation: '返回对象的长度',
        insertText: 'len()',
        sortText: 2,
      ),
      CompletionItem(
        label: 'range',
        kind: 'function',
        detail: '内置函数',
        documentation: '生成整数序列',
        insertText: 'range()',
        sortText: 3,
      ),
      CompletionItem(
        label: 'str',
        kind: 'function',
        detail: '内置函数',
        documentation: '将对象转换为字符串',
        insertText: 'str()',
        sortText: 4,
      ),
      CompletionItem(
        label: 'int',
        kind: 'function',
        detail: '内置函数',
        documentation: '将对象转换为整数',
        insertText: 'int()',
        sortText: 5,
      ),
      CompletionItem(
        label: 'float',
        kind: 'function',
        detail: '内置函数',
        documentation: '将对象转换为浮点数',
        insertText: 'float()',
        sortText: 6,
      ),
      CompletionItem(
        label: 'list',
        kind: 'function',
        detail: '内置函数',
        documentation: '创建列表',
        insertText: 'list()',
        sortText: 7,
      ),
      CompletionItem(
        label: 'dict',
        kind: 'function',
        detail: '内置函数',
        documentation: '创建字典',
        insertText: 'dict()',
        sortText: 8,
      ),
      CompletionItem(
        label: 'set',
        kind: 'function',
        detail: '内置函数',
        documentation: '创建集合',
        insertText: 'set()',
        sortText: 9,
      ),
      CompletionItem(
        label: 'abs',
        kind: 'function',
        detail: '内置函数',
        documentation: '返回绝对值',
        insertText: 'abs()',
        sortText: 10,
      ),
      CompletionItem(
        label: 'round',
        kind: 'function',
        detail: '内置函数',
        documentation: '四舍五入',
        insertText: 'round()',
        sortText: 11,
      ),
      CompletionItem(
        label: 'sum',
        kind: 'function',
        detail: '内置函数',
        documentation: '求和',
        insertText: 'sum()',
        sortText: 12,
      ),
      CompletionItem(
        label: 'max',
        kind: 'function',
        detail: '内置函数',
        documentation: '返回最大值',
        insertText: 'max()',
        sortText: 13,
      ),
      CompletionItem(
        label: 'min',
        kind: 'function',
        detail: '内置函数',
        documentation: '返回最小值',
        insertText: 'min()',
        sortText: 14,
      ),
    ];
    _completionsByModule['builtin'] = builtinList;
  }

  Future<void> _loadMathCompletions() async {
    final mathList = [
      CompletionItem(
        label: 'math.sqrt',
        kind: 'method',
        detail: 'math 模块',
        documentation: '计算平方根',
        insertText: 'math.sqrt()',
        sortText: 20,
      ),
      CompletionItem(
        label: 'math.sin',
        kind: 'method',
        detail: 'math 模块',
        documentation: '正弦函数',
        insertText: 'math.sin()',
        sortText: 21,
      ),
      CompletionItem(
        label: 'math.cos',
        kind: 'method',
        detail: 'math 模块',
        documentation: '余弦函数',
        insertText: 'math.cos()',
        sortText: 22,
      ),
      CompletionItem(
        label: 'math.tan',
        kind: 'method',
        detail: 'math 模块',
        documentation: '正切函数',
        insertText: 'math.tan()',
        sortText: 23,
      ),
      CompletionItem(
        label: 'math.pi',
        kind: 'variable',
        detail: 'math 模块',
        documentation: '圆周率 π',
        insertText: 'math.pi',
        sortText: 24,
      ),
      CompletionItem(
        label: 'math.e',
        kind: 'variable',
        detail: 'math 模块',
        documentation: '自然常数 e',
        insertText: 'math.e',
        sortText: 25,
      ),
      CompletionItem(
        label: 'math.exp',
        kind: 'method',
        detail: 'math 模块',
        documentation: '指数函数',
        insertText: 'math.exp()',
        sortText: 26,
      ),
      CompletionItem(
        label: 'math.log',
        kind: 'method',
        detail: 'math 模块',
        documentation: '自然对数',
        insertText: 'math.log()',
        sortText: 27,
      ),
      CompletionItem(
        label: 'math.log10',
        kind: 'method',
        detail: 'math 模块',
        documentation: '常用对数',
        insertText: 'math.log10()',
        sortText: 28,
      ),
      CompletionItem(
        label: 'math.floor',
        kind: 'method',
        detail: 'math 模块',
        documentation: '向下取整',
        insertText: 'math.floor()',
        sortText: 29,
      ),
      CompletionItem(
        label: 'math.ceil',
        kind: 'method',
        detail: 'math 模块',
        documentation: '向上取整',
        insertText: 'math.ceil()',
        sortText: 30,
      ),
    ];
    _completionsByModule['math'] = mathList;
  }

  Future<void> _loadPythonKeywords() async {
    _keywords['all'] = [
      'def', 'class', 'if', 'elif', 'else', 'for', 'while', 'break',
      'continue', 'return', 'try', 'except', 'finally', 'raise', 'assert',
      'import', 'from', 'as', 'in', 'is', 'not', 'and', 'or', 'pass',
      'lambda', 'global', 'nonlocal', 'with', 'yield', 'del', 'async',
      'await', 'True', 'False', 'None',
    ];
  }

  Future<void> _loadApiDocs() async {
    _apiDocs['print'] = const ApiDocItem(
      name: 'print',
      module: 'builtin',
      signature: 'print(*objects, sep=" ", end="\\n", file=sys.stdout)',
      description: '将对象打印到文本流文件，由 sep 分隔，由 end 结尾',
      returnType: 'None',
      params: ['*objects', 'sep', 'end', 'file', 'flush'],
    );
    _apiDocs['len'] = const ApiDocItem(
      name: 'len',
      module: 'builtin',
      signature: 'len(s)',
      description: '返回对象的长度（元素个数）',
      returnType: 'int',
    );
    _apiDocs['math.sqrt'] = const ApiDocItem(
      name: 'sqrt',
      module: 'math',
      signature: 'sqrt(x)',
      description: '返回 x 的平方根',
      returnType: 'float',
    );
    _apiDocs['math.sin'] = const ApiDocItem(
      name: 'sin',
      module: 'math',
      signature: 'sin(x)',
      description: '返回 x 的正弦值（弧度）',
      returnType: 'float',
    );
    _apiDocs['math.pi'] = const ApiDocItem(
      name: 'pi',
      module: 'math',
      signature: 'pi',
      description: '数学常数 π = 3.141592...',
      returnType: 'float',
    );
  }

  /// 获取补全建议
  Future<CompletionResult> getCompletions({
    required String code,
    required int position,
  }) async {
    if (!_isLoaded) {
      await initialize();
    }

    final items = <CompletionItem>[];
    final prefix = _extractPrefix(code, position).toLowerCase();

    // 收集所有模块的补全项
    for (final list in _completionsByModule.values) {
      for (final item in list) {
        if (prefix.isEmpty || item.label.toLowerCase().startsWith(prefix)) {
          items.add(item);
        }
      }
    }

    // 添加关键字
    final keywords = _keywords['all'] ?? [];
    for (final kw in keywords) {
      if (prefix.isEmpty || kw.toLowerCase().startsWith(prefix)) {
        items.add(CompletionItem(
          label: kw,
          kind: 'keyword',
          detail: '关键字',
          documentation: 'Python 关键字',
          insertText: kw,
        ));
      }
    }

    // 按 sortText 排序
    items.sort((a, b) => a.sortText.compareTo(b.sortText));

    // 记录最近使用
    for (final item in items.take(5)) {
      if (!_recentCompletions.contains(item.label)) {
        _recentCompletions.add(item.label);
        if (_recentCompletions.length > 20) {
          _recentCompletions.removeAt(0);
        }
      }
    }

    return CompletionResult(
      items: items.take(50).toList(),
      timestamp: DateTime.now(),
    );
  }

  String _extractPrefix(String code, int position) {
    if (position <= 0 || position > code.length) return '';
    int start = position - 1;
    while (start >= 0) {
      final c = code[start];
      if (c.isLetterOrNum || c == '.' || c == '_') {
        start--;
      } else {
        break;
      }
    }
    return code.substring(start + 1, position);
  }

  /// 获取 API 文档
  ApiDocItem? getApiDoc(String name) {
    return _apiDocs[name] ?? _apiDocs.values.firstWhere(
          (doc) => doc.name == name,
          orElse: () => _apiDocs[name]!,
        );
  }

  /// 搜索 API
  List<ApiDocItem> searchApi(String query) {
    final q = query.toLowerCase();
    return _apiDocs.values
        .where((doc) =>
            doc.name.toLowerCase().contains(q) ||
            doc.description.toLowerCase().contains(q) ||
            doc.module.toLowerCase().contains(q))
        .toList();
  }

  /// 清除最近补全历史
  void clearRecent() {
    _recentCompletions.clear();
    notifyListeners();
  }

  Map<String, dynamic> getStats() {
    return {
      'isLoaded': _isLoaded,
      'totalCompletions': totalCompletions,
      'totalDocs': totalDocs,
      'modules': _completionsByModule.keys.toList(),
      'recentCount': _recentCompletions.length,
    };
  }
}

extension on String {
  bool get isLetterOrNum {
    final code = this.codeUnitAt(0);
    return (code >= 48 && code <= 57) || // 0-9
        (code >= 65 && code <= 90) || // A-Z
        (code >= 97 && code <= 122); // a-z
  }
}
