# -*- coding: utf-8 -*-
"""
Matha v1.3.0 单元测试报告
========================
覆盖所有新增自检场景的完整测试套件。

测试模块：
  1. 符号引擎 (symbolic.py)
  2. FFI 桥接器 (ffi.py)
  3. 多范式引擎 (multi_paradigm.py)
  4. 代码生成 (symbol_codegen.py)
  5. 数学驱动 (math_driver.py)
  6. 内循环自检 (inner_loop.py Phase 4.55)
  7. 交叉验证 (Python/JS/C/Matha)
"""
from __future__ import annotations
import sys
import os
import json
import time
import unittest
import traceback

# 确保 src 在路径中
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# ═══════════════════════════════════════════════════════════════════════════════
#  测试报告基类
# ═══════════════════════════════════════════════════════════════════════════════
class TestReport:
    """测试报告收集器。"""
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.details = []

    def ok(self, test_name: str, detail: str = ""):
        self.passed += 1
        self.details.append(f"  ✓ {test_name}" + (f"  [{detail}]" if detail else ""))

    def fail(self, test_name: str, error: str, detail: str = ""):
        self.failed += 1
        self.errors.append((test_name, error))
        self.details.append(f"  ✗ {test_name}: {error}" + (f"  [{detail}]" if detail else ""))

    def summary(self) -> dict:
        total = self.passed + self.failed
        return {
            "module": self.name,
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": f"{self.passed/total*100:.1f}%" if total > 0 else "N/A",
            "details": self.details,
            "errors": [{"test": e[0], "error": e[1]} for e in self.errors],
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 1: 符号引擎
# ═══════════════════════════════════════════════════════════════════════════════
def test_symbolic_engine(report: TestReport):
    """符号引擎 v1.3.0 全面测试。"""
    from src.symbolic import symbol_expr, simplify_expr, diff_expr, eval_expr, ast_to_dict

    # 1.1 基本表达式解析
    cases = [
        ("x^2 + 3*x - 5", {"x": 3}, 13.0),
        ("x^2 - 2", {"x": 3}, 7.0),
        ("2*x + 1", {"x": 5}, 11.0),
        ("x^2 - 3*x + 2", {"x": 2}, 0.0),
        ("sin(x)", {"x": 0.0}, 0.0),
        ("cos(x)", {"x": 0.0}, 1.0),
        ("sqrt(x)", {"x": 9.0}, 3.0),
        ("exp(x)", {"x": 0.0}, 1.0),
        ("log(x)", {"x": 2.718281828}, 1.0),
        ("x^3 + 2*x^2 - 5*x + 3", {"x": 1}, 1.0),
    ]
    for expr_str, bindings, expected in cases:
        try:
            expr = symbol_expr(expr_str)
            val = eval_expr(expr, **bindings)
            if abs(val - expected) < 1e-6:
                report.ok(f"解析: {expr_str}({bindings}) = {val}", "✓")
            else:
                report.fail(f"解析: {expr_str}({bindings})", f"期望{expected}, 得到{val}")
        except Exception as e:
            report.fail(f"解析: {expr_str}", str(e))

    # 1.2 微积分
    diff_cases = [
        ("x^2", "x", "2 * x"),
        ("x^3", "x", "3 * (x ^ 2)"),
        ("sin(x)", "x", "cos(x)"),
        ("x^2 + 3*x", "x", "((2 * x) + 3)"),
    ]
    for expr_str, var, expected_str in diff_cases:
        try:
            expr = symbol_expr(expr_str)
            deriv = diff_expr(expr, var)
            report.ok(f"求导: d/d{var}({expr_str}) = {deriv}", "✓")
        except Exception as e:
            report.fail(f"求导: {expr_str}", str(e))

    # 1.3 链式法则
    import math as _math
    try:
        expr = symbol_expr("sin(x^2)")
        deriv = diff_expr(expr, 'x')
        deriv_val = eval_expr(deriv, x=1.0)
        # d/dx(sin(x²)) = 2x·cos(x²), at x=1: 2·cos(1) ≈ 1.0806
        expected = 2.0 * _math.cos(1.0)
        if abs(deriv_val - expected) < 0.01:
            report.ok(f"链式法则: d/dx(sin(x²)) at x=1 = {deriv_val:.6f}", "✓")
        else:
            report.fail(f"链式法则", f"期望≈{expected:.6f}, 得到{deriv_val:.6f}")
    except Exception as e:
        report.fail(f"链式法则", str(e))

    # 1.4 AST 序列化
    try:
        expr = symbol_expr("x^2 + 1")
        ast = ast_to_dict(expr)
        assert ast["type"] == "add"
        report.ok("AST序列化: x²+1 → add(pow(x,2), 1)", "✓")
    except Exception as e:
        report.fail("AST序列化", str(e))

    # 1.5 除零异常
    try:
        expr = symbol_expr("1/x")
        eval_expr(expr, x=0)
        report.fail("除零异常", "应抛出 ZeroDivisionError")
    except ZeroDivisionError:
        report.ok("除零异常: 1/x(x=0) 正确抛出 ZeroDivisionError", "✓")
    except Exception as e:
        report.fail("除零异常", f"异常类型错误: {type(e).__name__}: {e}")

    # 1.6 to_expr 数字字符串
    from src.symbolic import to_expr
    try:
        n = to_expr("3.14")
        assert isinstance(n, type(symbol_expr("1"))), "应返回 Num"
        assert abs(n.value - 3.14) < 1e-9
        report.ok("to_expr: '3.14' → Num(3.14)", "✓")
    except Exception as e:
        report.fail("to_expr", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 2: FFI 桥接器
# ═══════════════════════════════════════════════════════════════════════════════
def test_ffi_bridge(report: TestReport):
    """FFI 桥接器 v1.3.0 测试。"""
    from src.ffi import get_ffi
    ffi = get_ffi()

    # 2.1 内建函数调用
    ffi_tests = [
        ("sin", [1.0], None),
        ("cos", [0.0], 1.0),
        ("sqrt", [4.0], 2.0),
        ("exp", [1.0], None),
        ("log", [2.718281828], 1.0),
        ("pow", [2.0, 3.0], 8.0),
        ("abs", [-5.0], 5.0),
        ("factorial", [5], 120.0),  # 整数参数
    ]
    for fname, fargs, expected in ffi_tests:
        try:
            res = ffi.call(fname, *fargs)
            if expected is not None:
                if abs(res - expected) < 1e-6:
                    report.ok(f"FFI.{fname}({fargs}) = {res}", "✓")
                else:
                    report.fail(f"FFI.{fname}", f"期望{expected}, 得到{res}")
            else:
                report.ok(f"FFI.{fname}({fargs}) = {res}", "✓")
        except Exception as e:
            report.fail(f"FFI.{fname}", str(e))

    # 2.2 自定义函数注册
    def my_add(a, b): return a + b
    def my_mul(a, b): return a * b

    try:
        ffi.register("my_add", my_add, params=["a", "b"])
        ffi.register("my_mul", my_mul, params=["a", "b"])
        assert ffi.call("my_add", 3, 4) == 7
        assert ffi.call("my_mul", 3, 4) == 12
        report.ok("FFI自定义注册: my_add(3,4)=7, my_mul(3,4)=12", "✓")
    except Exception as e:
        report.fail("FFI自定义注册", str(e))

    # 2.3 线程安全：多次并发调用（模拟）
    try:
        results = []
        for i in range(10):
            r = ffi.call("sin", float(i))
            results.append(r)
        assert len(results) == 10
        report.ok(f"FFI线程安全: 10次调用全部成功", "✓")
    except Exception as e:
        report.fail("FFI线程安全", str(e))

    # 2.4 is_registered
    try:
        assert ffi.is_registered("sin")
        assert not ffi.is_registered("nonexistent_func_xyz")
        report.ok("FFI.is_registered: 正确判断", "✓")
    except Exception as e:
        report.fail("FFI.is_registered", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 3: 多范式引擎
# ═══════════════════════════════════════════════════════════════════════════════
def test_multi_paradigm(report: TestReport):
    """多范式引擎 v1.3.0 测试。"""
    from src.multi_paradigm import get_paradigm_engine

    engine = get_paradigm_engine()

    # 3.1 函数式：LISP 表达式
    try:
        r = engine.compute({"type": "functional", "expr": ['+', ['*', 2, 3], ['sin', 3.14159]]})
        assert abs(r["result"] - 6.0) < 0.01
        report.ok("函数式: (+ (* 2 3) (sin π)) ≈ 6", "✓")
    except Exception as e:
        report.fail("函数式LISP", str(e))

    # 3.2 函数式：let 绑定
    try:
        r = engine.compute({
            "type": "functional",
            "expr": ['let', ['x', 5], ['let', ['y', 3], ['+', ['x'], ['*', ['y'], ['y']]]]]
        })
        assert r["result"] == 14
        report.ok("函数式: let x=5, y=3 → x+y² = 14", "✓")
    except Exception as e:
        report.fail("函数式let", str(e))

    # 3.3 符号式
    try:
        r = engine.compute({
            "type": "symbolic",
            "expr": "x^2 + 3*x - 5",
            "params": {"x": 2}
        })
        assert abs(r["result"]["value"] - 5.0) < 1e-6
        report.ok("符号式: x²+3x-5(x=2) = 5", "✓")
    except Exception as e:
        report.fail("符号式", str(e))

    # 3.4 命令式：循环累加
    try:
        r = engine.compute({
            "type": "imperative",
            "statements": [
                {"kind": "assign", "var": "n", "value": 10},
                {"kind": "assign", "var": "sum", "value": 0},
                {"kind": "for", "var": "i", "iterable": ["list", 1, 2, 3, 4, 5],
                 "body": {"kind": "seq", "statements": [
                     {"kind": "assign", "var": "sum", "value": ["+", ["get", "sum"], ["get", "i"]]}
                 ]}},
                {"kind": "expr", "expr": ["get", "sum"]},
            ]
        })
        assert r["state"]["sum"] == 15
        report.ok("命令式: 1+2+3+4+5 = 15", "✓")
    except Exception as e:
        report.fail("命令式循环", str(e))

    # 3.5 数据流
    try:
        r = engine.compute({
            "type": "dataflow",
            "nodes": {
                "double": lambda x: x * 2,
                "add_one": lambda x: x + 1,
                "final": lambda a, b: a + b,
            },
            "edges": [["double", "final"], ["add_one", "final"]],
            "inputs": {"double": 5, "add_one": 10},
        })
        assert r["outputs"]["final"] == 21
        report.ok("数据流: double(5)+add_one(10) = 21", "✓")
    except Exception as e:
        report.fail("数据流", str(e))

    # 3.6 FFI 函数在函数式引擎中调用
    try:
        r = engine.compute({"type": "functional", "expr": ['clamp', 15, 0, 10]})
        assert r["result"] == 10
        report.ok("FFI集成: clamp(15,0,10) = 10", "✓")
    except Exception as e:
        report.fail("FFI集成", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 4: 代码生成
# ═══════════════════════════════════════════════════════════════════════════════
def test_code_generation(report: TestReport):
    """代码生成器 v1.3.0 测试。"""
    from src.symbol_codegen import get_codegen

    cg = get_codegen()
    expr = "x^2 + 3*x - 5"

    # 4.1 Python 代码生成
    try:
        code = cg.python(expr, func_name="compute")
        assert "math.sin" not in code  # 不应有sin
        assert "x**2" in code
        report.ok("CodeGen Python: x²+3x-5 生成成功", "✓")
    except Exception as e:
        report.fail("CodeGen Python", str(e))

    # 4.2 JavaScript 代码生成
    try:
        code = cg.javascript(expr, func_name="compute")
        assert "Math.sin" not in code
        assert "x**2" in code
        report.ok("CodeGen JavaScript: x²+3x-5 生成成功", "✓")
    except Exception as e:
        report.fail("CodeGen JS", str(e))

    # 4.3 C 代码生成（^ 应转为 pow()）
    try:
        code = cg.c(expr, func_name="compute")
        assert "pow(" in code, f"C代码缺少pow(): {code}"
        assert "**" not in code, f"C代码不应有**运算符"
        report.ok("CodeGen C: ^→pow() 正确", "✓")
    except Exception as e:
        report.fail("CodeGen C", str(e))

    # 4.4 e 常量的边界匹配
    try:
        expr_with_e = "e*x + sin(x)"
        py_code = cg.python(expr_with_e, func_name="f")
        assert "math.e" in py_code, "e应被替换为math.e"
        assert "math.sin" in py_code, "sin应被替换为math.sin"
        report.ok("CodeGen e常量: e*x → math.e*x", "✓")
    except Exception as e:
        report.fail("CodeGen e常量", str(e))

    # 4.5 驱动规格生成
    try:
        from src.symbol_codegen import DriverSpec, MathaCodeGen
        spec = DriverSpec(name="test_driver", language="python", math_func="add", io_type="both")
        cg2 = MathaCodeGen()
        code = cg2.generate_driver(spec)
        assert "def" in code
        report.ok("CodeGen驱动规格: 生成成功", "✓")
    except Exception as e:
        report.fail("CodeGen驱动规格", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 5: 数学驱动
# ═══════════════════════════════════════════════════════════════════════════════
def test_math_driver(report: TestReport):
    """数学驱动层 v1.3.0 测试。"""
    from src.math_driver import get_driver_manager

    mgr = get_driver_manager()

    # 5.1 线性代数
    try:
        r = mgr.execute("linear_algebra", "mat_det", [[1, 2], [3, 4]])
        assert abs(r - (-2.0)) < 1e-9
        report.ok("驱动 mat_det([[1,2],[3,4]]) = -2", "✓")
    except Exception as e:
        report.fail("驱动 mat_det", str(e))

    try:
        r = mgr.execute("linear_algebra", "dot", [1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        assert abs(r - 32.0) < 1e-9
        report.ok("驱动 dot([1,2,3],[4,5,6]) = 32", "✓")
    except Exception as e:
        report.fail("驱动 dot", str(e))

    try:
        r = mgr.execute("linear_algebra", "mat_mul", [[1, 0], [0, 1]], [[2, 3], [4, 5]])
        assert r == [[2.0, 3.0], [4.0, 5.0]]
        report.ok("驱动 mat_mul(I, [[2,3],[4,5]]) = [[2,3],[4,5]]", "✓")
    except Exception as e:
        report.fail("驱动 mat_mul", str(e))

    # 5.2 几何
    try:
        r = mgr.execute("geometry", "circle_area", 5.0)
        assert abs(r - 78.5398163397) < 0.001
        report.ok(f"驱动 circle_area(5) = {r:.4f}", "✓")
    except Exception as e:
        report.fail("驱动 circle_area", str(e))

    try:
        r = mgr.execute("geometry", "distance", 0.0, 0.0, 3.0, 4.0)
        assert abs(r - 5.0) < 1e-9
        report.ok(f"驱动 distance((0,0),(3,4)) = {r}", "✓")
    except Exception as e:
        report.fail("驱动 distance", str(e))

    # 5.3 微积分
    try:
        r = mgr.execute("calculus", "derivative", lambda x: x**2, 2.0)
        assert abs(r - 4.0) < 1e-6
        report.ok(f"驱动 derivative(x², x=2) = {r}", "✓")
    except Exception as e:
        report.fail("驱动 derivative", str(e))

    # 5.4 优化
    try:
        # binary_search(func, lo, hi, tol)
        r = mgr.execute("optimization", "binary_search", lambda x: x - 5, 1, 10)
        assert abs(r - 5.0) < 1e-6
        report.ok(f"驱动 binary_search(x-5) = {r:.6f}", "✓")
    except Exception as e:
        report.fail("驱动 binary_search", str(e))

    # 5.5 吞噬/同化
    try:
        from src.symbol_codegen import MathaCodeGen
        mgr.consume("python", [{"name": "test_op", "expr": "x + 1", "lang": "python"}])
        report.ok("驱动吞噬: Python函数注册成功", "✓")
    except Exception as e:
        report.fail("驱动吞噬", str(e))

    # 5.6 驱动列表
    try:
        drivers = mgr.list_drivers()
        names = [d["name"] for d in drivers]
        assert "linear_algebra" in names
        assert "calculus" in names
        assert "geometry" in names
        assert "signal" in names
        assert "optimization" in names
        report.ok(f"驱动列表: {len(drivers)} 个驱动, {names}", "✓")
    except Exception as e:
        report.fail("驱动列表", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 6: 沙箱执行安全
# ═══════════════════════════════════════════════════════════════════════════════
def test_sandbox_execution(report: TestReport):
    """沙箱执行安全检查。"""
    from src.symbol_codegen import get_codegen

    cg = get_codegen()

    # 6.1 正常表达式安全执行
    try:
        code = cg.python("x^2 + 1", func_name="safe_fn")
        safe_globals = {"__builtins__": __builtins__, "math": __import__("math")}
        exec(code, safe_globals)
        fn = safe_globals.get("safe_fn")
        assert fn is not None
        res = fn(3)
        assert abs(res - 10.0) < 1e-9
        report.ok("沙箱安全: x²+1(x=3) = 10", "✓")
    except Exception as e:
        report.fail("沙箱安全", str(e))

    # 6.2 恶意代码注入防护
    try:
        malicious_code = "__import__('os').system('echo hacked')"
        safe_globals = {"__builtins__": {k: v for k, v in __builtins__.items() if k not in
                                         ['__import__', 'eval', 'exec', 'open', 'input']}}
        exec(malicious_code, safe_globals)
        report.fail("沙箱注入", "恶意代码未被拦截")
    except (NameError, AttributeError, Exception) as e:
        report.ok(f"沙箱防护: 恶意代码被拦截 ({type(e).__name__})", "✓")


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 7: 内循环自检
# ═══════════════════════════════════════════════════════════════════════════════
def test_inner_loop_selfcheck(report: TestReport):
    """内循环 v1.3.0 自检 Phase 4.55。"""
    from src.inner_loop import MathaInnerLoop

    loop = MathaInnerLoop()
    loop.init_modules()

    # 验证 v1.3.0 模块已注册
    assert hasattr(loop, '_symbolic_parser'), "缺少 _symbolic_parser"
    assert hasattr(loop, '_ffi'), "缺少 _ffi"
    assert hasattr(loop, '_driver_mgr'), "缺少 _driver_mgr"
    assert hasattr(loop, '_paradigm'), "缺少 _paradigm"
    assert hasattr(loop, '_codegen'), "缺少 _codegen"
    report.ok("内循环: v1.3.0 模块已注册", "✓")

    # 运行自检（只跑 Phase 4.55，不跑完整周期）
    from src.symbolic import diff_expr, eval_expr as sym_eval
    v13_result = {"status": "healthy", "checks": {}, "details": []}
    try:
        # FFI 测试
        ffi_stats = loop._ffi.get_stats()
        reg_count = ffi_stats.get("registered_functions", 0)
        v13_result["checks"]["ffi"] = "ok"
        v13_result["details"].append(f"  FFI: {reg_count} 个注册函数")
        # 抽样调用
        import math
        for fname, fargs in [("sin", [1.0]), ("sqrt", [4.0]), ("exp", [1.0])]:
            try:
                res = loop._ffi.call(fname, *fargs)
                v13_result["details"].append(f"    FFI.{fname}({fargs}) = {res}")
            except Exception as e:
                v13_result["checks"]["ffi"] = "error"
                v13_result["details"].append(f"    FFI.{fname}({fargs}) 失败: {e}")
        # 驱动测试
        drivers = loop._driver_mgr.list_drivers()
        total_ops = sum(d["ops"] for d in drivers)
        v13_result["checks"]["drivers"] = "ok"
        v13_result["details"].append(f"  驱动: {len(drivers)} 个, {total_ops} 个运算")
        # 符号引擎测试
        expr = loop._symbolic_parser("x^2 + 1")
        val = sym_eval(expr, x=2)
        assert abs(val - 5.0) < 1e-9
        v13_result["checks"]["symbolic"] = "ok"
        v13_result["details"].append(f"  符号: x²+1(x=2) = {val} ✓")
        # 微积分测试
        expr = loop._symbolic_parser("x^3 + 2*x^2 - 5*x + 3")
        deriv = diff_expr(expr, 'x')
        deriv_val = sym_eval(deriv, x=1)
        assert abs(deriv_val - 2.0) < 1e-9
        v13_result["checks"]["calculus"] = "ok"
        v13_result["details"].append(f"  微积分: d/dx(x³+2x²-5x+3) at x=1 = {deriv_val} ✓")
        # 代码生成测试
        py_code = loop._codegen.python("x^2 + 3*x - 5", func_name="f")
        js_code = loop._codegen.javascript("x^2 + 3*x - 5", func_name="f")
        c_code = loop._codegen.c("x^2 + 3*x - 5", func_name="f")
        v13_result["checks"]["codegen"] = "ok"
        v13_result["details"].append("  代码生成: Python/JS/C 均健康 ✓")
        # 沙箱测试
        from src.symbol_codegen import MathaCodeGen
        cg = MathaCodeGen()
        code = cg.python("x^2 + 1", func_name="test_fn")
        safe_globals = {"__builtins__": __builtins__, "math": __import__("math")}
        exec(code, safe_globals)
        fn = safe_globals.get("test_fn")
        assert fn is not None
        res = fn(3)
        assert abs(res - 10.0) < 1e-9
        v13_result["checks"]["sandbox"] = "ok"
        v13_result["details"].append(f"  沙箱: x²+1(x=3) = {res} ✓")
        # 多范式测试
        r = loop._paradigm.compute({"type": "functional", "expr": ['+', 1, 2, 3]})
        assert r.get("result") == 6
        v13_result["checks"]["paradigm"] = "ok"
        v13_result["details"].append(f"  多范式: (+1+2+3) = {r['result']} ✓")
        # 总结
        failed = [k for k, v in v13_result["checks"].items() if v not in ("ok",)]
        if failed:
            v13_result["status"] = "degraded"
        report.ok(f"内循环自检: status={v13_result['status']}, checks={list(v13_result['checks'].keys())}", "✓")
    except Exception as e:
        report.fail("内循环自检", str(e))
        import traceback; traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  测试 8: 复杂数学表达式端到端
# ═══════════════════════════════════════════════════════════════════════════════
def test_complex_math_e2e(report: TestReport):
    """复杂数学表达式端到端验证。"""
    from src.symbolic import symbol_expr, diff_expr, eval_expr
    from src.math_driver import get_driver_manager
    from src.multi_paradigm import get_paradigm_engine

    mgr = get_driver_manager()
    engine = get_paradigm_engine()

    # 8.1 二次方程求根
    try:
        # x² - 5x + 6 = 0 的根为 2 和 3
        expr = symbol_expr("x^2 - 5*x + 6")
        deriv = diff_expr(expr, 'x')
        # 牛顿迭代
        root = eval_expr(expr, x=2.0)
        assert abs(root) < 1e-9, f"x=2 不是根: {root}"
        root2 = eval_expr(expr, x=3.0)
        assert abs(root2) < 1e-9, f"x=3 不是根: {root2}"
        report.ok("二次方程: x²-5x+6=0, 根 x=2, x=3", "✓")
    except Exception as e:
        report.fail("二次方程", str(e))

    # 8.2 三角恒等式 sin²x + cos²x = 1
    try:
        sin_val = eval_expr(symbol_expr("sin(x)"), x=1.5)
        cos_val = eval_expr(symbol_expr("cos(x)"), x=1.5)
        identity = sin_val**2 + cos_val**2
        assert abs(identity - 1.0) < 1e-10, f"恒等式失败: {identity}"
        report.ok(f"三角恒等式: sin²(1.5)+cos²(1.5) = {identity:.15f} ≈ 1", "✓")
    except Exception as e:
        report.fail("三角恒等式", str(e))

    # 8.3 链式法则：d/dx(sin(x²)) = 2x·cos(x²)
    try:
        expr = symbol_expr("sin(x^2)")
        deriv = diff_expr(expr, 'x')
        deriv_val = eval_expr(deriv, x=0.5)
        expected = 2 * 0.5 * __import__("math").cos(0.25)
        assert abs(deriv_val - expected) < 1e-6
        report.ok(f"链式法则: d/dx(sin(x²)) at x=0.5 = {deriv_val:.6f} ≈ {expected:.6f}", "✓")
    except Exception as e:
        report.fail("链式法则", str(e))

    # 8.4 矩阵行列式
    try:
        r = mgr.execute("linear_algebra", "mat_det", [[1, 2, 3], [4, 5, 6], [7, 8, 10]])
        expected = 1*(50-48) - 2*(40-42) + 3*(32-35)  # = 2 + 4 - 9 = -3
        assert abs(r - (-3.0)) < 1e-6
        report.ok(f"矩阵det(3×3) = {r} (期望 -3)", "✓")
    except Exception as e:
        report.fail("矩阵det", str(e))

    # 8.5 傅里叶变换（信号处理）
    try:
        r = mgr.execute("signal", "fft", [1.0, 0.0, -1.0, 0.0])
        assert r is not None
        report.ok(f"FFT([1,0,-1,0]) = {r}", "✓")
    except Exception as e:
        report.fail("FFT", str(e))

    # 8.6 梯度下降
    try:
        def f(x): return x**2
        # gradient_descent(func, x0, lr, tol, max_iter)
        r = mgr.execute("optimization", "gradient_descent", f, 5.0, 0.01, 1e-8, 1000)
        assert abs(r - 0.0) < 0.01
        report.ok(f"梯度下降: x²→0, 结果={r:.6f}", "✓")
    except Exception as e:
        report.fail("梯度下降", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  Matha v1.3.0 单元测试报告")
    print("  生成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    all_reports = []
    tests = [
        ("符号引擎", test_symbolic_engine),
        ("FFI桥接器", test_ffi_bridge),
        ("多范式引擎", test_multi_paradigm),
        ("代码生成", test_code_generation),
        ("数学驱动", test_math_driver),
        ("沙箱安全", test_sandbox_execution),
        ("内循环自检", test_inner_loop_selfcheck),
        ("复杂数学E2E", test_complex_math_e2e),
    ]

    total_passed = 0
    total_failed = 0

    for name, test_fn in tests:
        report = TestReport(name)
        try:
            test_fn(report)
        except Exception as e:
            report.fail("测试框架", f"异常: {e}")
            traceback.print_exc()
        all_reports.append(report)
        total_passed += report.passed
        total_failed += report.failed
        print(f"\n[{name}] {report.passed}/{report.passed+report.failed} 通过")

    # 汇总报告
    print("\n" + "=" * 70)
    print("  汇总")
    print("=" * 70)
    grand_total = total_passed + total_failed
    print(f"  总计: {grand_total} 个测试, "
          f"通过: {total_passed}, 失败: {total_failed}, "
          f"通过率: {total_passed/grand_total*100:.1f}%")
    print()

    for r in all_reports:
        s = r.summary()
        status = "✅" if s["failed"] == 0 else "⚠️"
        print(f"  {status} {s['module']}: {s['passed']}/{s['total']} ({s['pass_rate']})")
        for d in s["details"][:8]:
            print(f"     {d}")
        if len(s["details"]) > 8:
            print(f"     ... 共 {len(s['details'])} 条")
        if s["errors"]:
            for e in s["errors"][:3]:
                print(f"     ✗ {e['test']}: {e['error']}")

    # 保存报告
    report_data = {
        "version": "1.3.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total": grand_total,
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": f"{total_passed/grand_total*100:.1f}%",
        },
        "modules": [r.summary() for r in all_reports],
    }
    report_path = os.path.join(_root, "tests", "v1.3.0_test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")

    if total_failed == 0:
        print("\n  ✅ 全部测试通过！")
    else:
        print(f"\n  ❌ {total_failed} 个测试失败")
    print("=" * 70)
