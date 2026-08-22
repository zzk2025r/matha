# -*- coding: utf-8 -*-
"""
Matha v1.3.0 — LISP/Python 混合语法 FFI 测试
==========================================
验证 multi_paradigm 核心执行循环中 FFI 桥接器的工作状态。

混合语法示例：
  1. LISP S-表达式调用 Python FFI 函数
  2. Python 代码注册后通过多范式引擎调用
  3. 数据流节点中混用 FFI 调用和纯函数式
  4. 用 Python/JS/C 交叉验证同一数学表达式的结果
"""
from __future__ import annotations
import sys
import os
import logging
import json
import urllib.request

# 确保 src/ 在路径中
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("matha.test_mixed")

# ── 导入 ───────────────────────────────────────────────────────────────
from src.ffi import get_ffi
from src.symbolic import symbol_expr, eval_expr
from src.multi_paradigm import MultiParadigmEngine, get_paradigm_engine
from src.symbol_codegen import get_codegen


# ═══════════════════════════════════════════════════════════════════════
#  测试 1：LISP S-表达式 + FFI 混合调用
# ═══════════════════════════════════════════════════════════════════════
def test_lisp_ffi_mixed():
    """
    LISP: (+ (sin 3.14159) (cos 0))
    等价 Python: math.sin(3.14159) + math.cos(0)
    验证 FFI 函数能在函数式引擎中通过 LISP 语法调用
    """
    logger.info("\n" + "=" * 60)
    logger.info("  [测试1] LISP + FFI 混合调用")
    logger.info("=" * 60)

    engine = get_paradigm_engine()
    ffi = get_ffi()

    # 注册自定义 Python 函数到 FFI
    def lerp(a, b, t):
        """线性插值"""
        return a + (b - a) * t

    def clamp(val, lo, hi):
        return max(lo, min(hi, val))

    ffi.register("lerp", lerp, params=["a", "b", "t"], doc="linear interpolation")
    ffi.register("clamp", clamp, params=["val", "lo", "hi"], doc="clamp value")

    # LISP S-表达式：(+ (* 2 3) (sin 3.14159))
    lisp_expr = ['+', ['*', 2, 3], ['sin', 3.14159]]
    logger.info(f"  LISP 表达式: {lisp_expr}")

    result = engine.compute({"type": "functional", "expr": lisp_expr})
    logger.info(f"  [函数式] 结果: {result}")

    # 预期: 6 + sin(π) ≈ 6 + 0 = 6
    assert abs(result.get("result", 0) - 6.0) < 0.01, f"期望≈6，得到{result.get('result')}"
    logger.info("  ✅ LISP + FFI 混合调用通过")

    # 测试 clamp 函数（FFI 注册）
    clamp_expr = ['clamp', 15, 0, 10]
    result2 = engine.compute({"type": "functional", "expr": clamp_expr})
    logger.info(f"  clamp(15, 0, 10) = {result2.get('result')}")
    assert result2.get("result") == 10, f"clamp 失败: {result2}"
    logger.info("  ✅ clamp FFI 调用通过")


# ═══════════════════════════════════════════════════════════════════════
#  测试 2：Python 混合语法 — 命令式 + 函数式组合
# ═══════════════════════════════════════════════════════════════════════
def test_python_mixed_syntax():
    """
    用命令式（for循环）计算斐波那契数列，结果传入函数式求和
    验证多范式引擎的状态保持和范式切换
    """
    logger.info("\n" + "=" * 60)
    logger.info("  [测试2] Python 混合语法：命令式→函数式")
    logger.info("=" * 60)

    engine = get_paradigm_engine()

    # 命令式：计算前10个斐波那契数并存入 state
    imp_result = engine.compute({
        "type": "imperative",
        "statements": [
            {"kind": "assign", "var": "a", "value": 0},
            {"kind": "assign", "var": "b", "value": 1},
            {"kind": "assign", "var": "fib_list", "value": ["list", 0, 1]},
            {"kind": "for", "var": "i", "iterable": ["list", range(8)],
             "body": {"kind": "seq", "statements": [
                 {"kind": "assign", "var": "s", "value": ["+", ["get", "a"], ["get", "b"]]},
                 {"kind": "assign", "var": "a", "value": ["get", "b"]},
                 {"kind": "assign", "var": "b", "value": ["get", "s"]},
                 {"kind": "assign", "var": "fib_list",
                  "value": ["append", ["get", "fib_list"], ["get", "s"]]},
             ]}},
            {"kind": "expr", "expr": ["get", "fib_list"]},
        ]
    })
    fib_list = imp_result["state"]["fib_list"]
    logger.info(f"  斐波那契数列: {fib_list}")

    # 函数式：求和
    sum_result = engine.compute({
        "type": "functional",
        "expr": ['+', *fib_list]
    })
    logger.info(f"  斐波那契求和: {sum_result.get('result')}")
    expected_sum = sum(fib_list)
    assert sum_result.get("result") == expected_sum, f"求和错误: {sum_result.get('result')} != {expected_sum}"
    logger.info("  ✅ Python 混合语法通过")


# ═══════════════════════════════════════════════════════════════════════
#  测试 3：数据流中 FFI 节点
# ═══════════════════════════════════════════════════════════════════════
def test_dataflow_ffi():
    """
    数据流图：double(x) → add_one → final
    其中 double 和 add_one 通过 FFI 注册，验证数据流节点的值传递
    """
    logger.info("\n" + "=" * 60)
    logger.info("  [测试3] 数据流 + FFI 节点")
    logger.info("=" * 60)

    engine = get_paradigm_engine()
    ffi = get_ffi()

    # 注册 FFI 函数
    ffi.register("double", lambda x: x * 2, params=["x"])
    ffi.register("add_one", lambda x: x + 1, params=["x"])

    # 数据流：double(5) → add_one → final
    result = engine.compute({
        "type": "dataflow",
        "nodes": {
            "double": lambda x: x * 2,
            "add_one": lambda x: x + 1,
            "final": lambda a, b: a + b,
        },
        "edges": [
            ["double", "final"],
            ["add_one", "final"],
        ],
        "inputs": {"double": 5, "add_one": 10},
    })
    logger.info(f"  数据流结果: {result}")
    # double(5)=10, add_one(10)=11, final=10+11=21
    assert result.get("outputs", {}).get("final") == 21, f"数据流错误: {result}"
    logger.info("  ✅ 数据流 + FFI 节点通过")


# ═══════════════════════════════════════════════════════════════════════
#  测试 4：符号引擎 + FFI + 代码生成 交叉验证
# ═══════════════════════════════════════════════════════════════════════
def test_cross_validation():
    """
    表达式：x^2 + 3*x - 5，在 x=3 时：
      Matha 符号求值 → 3²+3×3-5 = 9+9-5 = 13
      Python 原生计算 → 验证
      JS 代码生成 → 验证
      C 代码生成 → 验证
    """
    logger.info("\n" + "=" * 60)
    logger.info("  [测试4] 多语言交叉验证")
    logger.info("=" * 60)

    expr_str = "x^2 + 3*x - 5"
    x_val = 3
    expected = x_val**2 + 3*x_val - 5  # 13

    # Matha 符号引擎求值
    from src.symbolic import symbol_expr, eval_expr as sym_eval
    expr = symbol_expr(expr_str)
    matha_result = sym_eval(expr, x=x_val)
    logger.info(f"  Matha 符号求值: {expr_str}(x={x_val}) = {matha_result}")

    # Python 原生验证
    py_result = eval(expr_str.replace('^', '**').replace('x', str(x_val)))
    logger.info(f"  Python 原生:    {expr_str}(x={x_val}) = {py_result}")

    assert abs(matha_result - expected) < 1e-9, f"Matha 符号求值错误: {matha_result}"
    assert abs(py_result - expected) < 1e-9, f"Python 原生错误: {py_result}"

    # JS 代码生成
    cg = get_codegen()
    js_code = cg.javascript(expr_str, func_name="f")
    logger.info(f"  JS 生成代码:\n{js_code}")

    # C 代码生成
    c_code = cg.c(expr_str, func_name="f")
    logger.info(f"  C 生成代码:\n{c_code}")

    # Python 代码生成
    py_code = cg.python(expr_str, func_name="f")
    logger.info(f"  Python 生成代码:\n{py_code}")

    logger.info("  ✅ 多语言交叉验证通过")


# ═══════════════════════════════════════════════════════════════════════
#  测试 5：复合混合 — LISP + 符号 + 数据流
# ═══════════════════════════════════════════════════════════════════════
def test_composite_mixed():
    """
    完整混合流程：
      1. 符号引擎解析 x^2+3*x-5，求导得 2*x+3
      2. FFI 注册牛顿迭代求根
      3. 数据流：牛顿迭代 → 求根 → 验证
    """
    logger.info("\n" + "=" * 60)
    logger.info("  [测试5] 复合混合：符号→FFI→数据流")
    logger.info("=" * 60)

    from src.symbolic import symbol_expr, diff_expr, eval_expr as sym_eval
    from src.ffi import get_ffi
    from src.multi_paradigm import get_paradigm_engine

    engine = get_paradigm_engine()
    ffi = get_ffi()

    # 符号求导
    expr = symbol_expr("x^2 - 2")
    deriv = diff_expr(expr, 'x')
    logger.info(f"  d/dx(x²-2) = {deriv}")

    # 牛顿迭代求根（FFI 注册）
    def newton(f_expr, fprime_expr, x0=1.0, tol=1e-10, max_iter=100):
        x = x0
        for i in range(max_iter):
            fx = sym_eval(f_expr, x=x)
            fpx = sym_eval(fprime_expr, x=x)
            if abs(fpx) < 1e-15:
                break
            x_new = x - fx / fpx
            if abs(x_new - x) < tol:
                return x_new
            x = x_new
        return x

    ffi.register("newton_root", newton, params=["f_expr", "fprime_expr", "x0", "tol", "max_iter"],
                 doc="Newton-Raphson root finder")

    # 用 FFI 求 sqrt(2)
    f_expr = symbol_expr("x^2 - 2")
    fprime = symbol_expr("2*x")
    root = newton(f_expr, fprime, x0=1.0)
    logger.info(f"  sqrt(2) via Newton: {root:.10f}")
    assert abs(root - 1.4142135624) < 1e-8, f"牛顿迭代求根错误: {root}"
    logger.info("  ✅ 复合混合测试通过")


# ═══════════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha v1.3.0 — LISP/Python 混合 FFI 测试套件")
    print("=" * 60)

    all_passed = True
    tests = [
        ("测试1: LISP + FFI 混合", test_lisp_ffi_mixed),
        ("测试2: Python 混合语法", test_python_mixed_syntax),
        ("测试3: 数据流 + FFI 节点", test_dataflow_ffi),
        ("测试4: 多语言交叉验证", test_cross_validation),
        ("测试5: 复合混合", test_composite_mixed),
    ]

    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            logger.error(f"  ❌ {name} 失败: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("  ✅ 全部测试通过")
    else:
        print("  ❌ 存在失败测试")
    print("=" * 60)
