// Matha 代码执行器 - 平台自动适配
// Web 平台调用 Pyodide 执行 Python/Matha 代码；VM/iOS/Android 使用本地模拟实现

import 'math_executor_stub.dart' if (dart.library.html) 'math_executor_web.dart' as impl;

/// Matha 执行结果
class MathExecuteResult {
  final String output;
  final bool isSuccess;
  final String? error;

  const MathExecuteResult({
    required this.output,
    required this.isSuccess,
    this.error,
  });
}

/// 执行 Matha/Python 代码（平台自适应）
Future<MathExecuteResult> executeMathCode(String code) => impl.executeMathCode(code);

/// 本地模拟执行输出（离线/非 Web 平台回退）
String simulateOutput(String code) {
  if (code.contains('matrix') || code.contains('multiply')) return 'Matrix([[5, 8], [11, 14]])';
  if (code.contains('mean') || code.contains('平均')) return '42.5';
  if (code.contains('sum') || code.contains('求和')) return '100';
  return '执行完成';
}