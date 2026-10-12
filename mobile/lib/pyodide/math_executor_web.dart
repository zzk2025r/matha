// Matha 代码执行器 - Web 实现（调用 Pyodide 执行 Python/Matha 代码）

import 'math_executor.dart';
import 'pyodide_bridge.dart';

Future<MathExecuteResult> executeMathCode(String code) async {
  final controller = PyodideController();

  if (!controller.isLoaded) {
    await controller.initialize();
  }
  if (!controller.isLoaded) {
    return MathExecuteResult(
      output: '',
      isSuccess: false,
      error: controller.lastError ?? 'Pyodide 初始化失败',
    );
  }

  final result = await controller.runMathaCode(code);
  return MathExecuteResult(
    output: result.output,
    isSuccess: result.isSuccess,
    error: result.error,
  );
}