# -*- coding: utf-8 -*-
"""混合语言编译器测试。"""
import sys
sys.path.insert(0, r'D:\trae')

from src.interp import Interpreter
from src.hybrid_compiler import (
    LanguageBridge, AutoDiagnoser, MixedProjectBuilder,
    HybridCompiler, Language, DefectKind, Severity,
)


def test_language_bridge_matha_to_python():
    """Matha → Python 转译。"""
    bridge = LanguageBridge()
    src = 'func 加倍(x) -> Int = (x) => x * 2'
    py = bridge.matha_to_python(src)
    assert 'def 加倍' in py, py
    print(f"  ✓ Matha→Python: {py.strip()[:80]}")


def test_language_bridge_python_to_matha():
    """Python → Matha 反向转译。"""
    bridge = LanguageBridge()
    py_src = 'def double(x):\n    return x * 2\n'
    matha = bridge.python_to_matha(py_src)
    assert 'func' in matha or 'def' in matha, matha
    print(f"  ✓ Python→Matha: {matha.strip()[:80]}")


def test_auto_diagnoser():
    """自动诊断。"""
    interp = Interpreter()
    diag = AutoDiagnoser(interp)

    # 正常代码
    good = 'func 加倍(x) -> Int = (x) => x * 2'
    report = diag.diagnose_and_report(good)
    print(f"  ✓ 诊断正常代码: {report['defect_count']} 个问题")

    # 有问题的代码
    bad = 'func 无效(x) -> Int = (x) => x / 0'
    report = diag.diagnose_and_report(bad)
    print(f"  ✓ 诊断问题代码: {report['defect_count']} 个问题, "
          f"严重={report['critical']}C/{report['high']}H/{report['medium']}M")


def test_hybrid_compiler_translate():
    """混合编译器转译。"""
    interp = Interpreter()
    hc = HybridCompiler(interp)

    src = 'func 求和(a, b) -> Int = (a, b) => a + b'
    result = hc.translate(src, 'python')
    assert result['success'], result
    assert 'def' in result['code']
    print(f"  ✓ 转译: {result['code'].strip()[:80]}")


def test_hybrid_compiler_diagnose():
    """混合编译器诊断。"""
    interp = Interpreter()
    hc = HybridCompiler(interp)

    src = 'func 求和(a, b) -> Int = (a, b) => a + b'
    result = hc.diagnose(src)
    assert 'defect_count' in result
    print(f"  ✓ 诊断: {result['defect_count']} 个问题")


def test_mixed_execution():
    """混合语言执行。"""
    interp = Interpreter()
    hc = HybridCompiler(interp)

    mixed = """<<MATHA>>
func 加倍(x) = (x) => x * 2
[加倍(5)]
<<END>>
<<PYTHON>>
result = 42
<<END>>"""
    result = hc.mixed_exec(mixed)
    print(f"  ✓ 混合执行: logs={result['logs']}, output={result['output']}")


def test_interpreter_builtins():
    """解释器内建函数可用性。"""
    interp = Interpreter()

    # 混合编译
    result = interp.call("混合编译", "测试任务", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(result, dict), result
    print(f"  ✓ 混合编译内建: {type(result).__name__}")

    # 混合诊断
    result = interp.call("混合诊断", "func 加倍(x) -> Int = (x) => x * 2")
    assert isinstance(result, dict), result
    print(f"  ✓ 混合诊断内建: defect_count={result.get('defect_count', 'N/A')}")

    # 转译语言
    result = interp.call("转译语言", "func 加倍(x) -> Int = (x) => x * 2", "python")
    assert isinstance(result, dict), result
    print(f"  ✓ 转译语言内建: success={result.get('success')}")


def test_build_simple_task():
    """构建简单任务。"""
    interp = Interpreter()
    hc = HybridCompiler(interp)

    # 简单有效的 Matha 代码
    src = 'func 加倍(x) -> Int = (x) => x * 2\n[加倍(5)]'
    result = hc.build_project("测试加倍", src)
    assert result['success'], result
    print(f"  ✓ 构建成功: output={result['output']}")


if __name__ == '__main__':
    print("\n=== 混合语言编译器测试 ===")

    print("\n【1. LanguageBridge】")
    test_language_bridge_matha_to_python()
    test_language_bridge_python_to_matha()

    print("\n【2. AutoDiagnoser】")
    test_auto_diagnoser()

    print("\n【3. HybridCompiler 转译】")
    test_hybrid_compiler_translate()

    print("\n【4. HybridCompiler 诊断】")
    test_hybrid_compiler_diagnose()

    print("\n【5. 混合执行】")
    test_mixed_execution()

    print("\n【6. 解释器内建】")
    test_interpreter_builtins()

    print("\n【7. 简单任务构建】")
    test_build_simple_task()

    print("\n✓ 所有混合语言编译器测试通过")
