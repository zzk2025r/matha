// Matha 代码执行器 - 本地模拟实现（VM / iOS / Android）

import 'math_executor.dart';

Future<MathExecuteResult> executeMathCode(String code) async {
  await Future<void>.delayed(const Duration(milliseconds: 100));
  return MathExecuteResult(output: simulateOutput(code), isSuccess: true);
}