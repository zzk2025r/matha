# -*- coding: utf-8 -*-
"""自动定义 / 自动注册（虚拟代码引擎）回归测试。

覆盖用户诉求：
  1. 每当出现未定义变量时，自动正确地赋予定义（定义功能）。
  2. 每当出现未定义函数时，自动注册并可调用。
  3. 当出现从未出现的定义时，自动正确地注册（注册功能）。

默认的裸解释器保持严格语义（抛 MathaRuntimeError），只有接入虚拟代码
引擎（MathaEngine / MathaSystem）或显式开启 auto_heal 时才自愈。
"""
import sys
sys.path.insert(0, r'D:\trae')

import pytest

from src.interp import Interpreter, VirtualSymbol, interpret, MathaRuntimeError
from src.parser import parse
from src.virtual_code import get_virtual_registry, reset_virtual_registry


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_virtual_registry()
    yield
    reset_virtual_registry()


def _healing_interp():
    i = Interpreter()
    i.attach_virtual_registry(get_virtual_registry())
    return i


# ─── 定义功能：未定义变量自动赋予定义 ────────────────────────────────────────

def test_default_interpreter_stays_strict_on_undefined_variable():
    """未接入引擎时保持严格：仍抛「未定义变量」。"""
    with pytest.raises(MathaRuntimeError):
        interpret('输出(从未定义_x)')


def test_undefined_variable_auto_defined():
    i = _healing_interp()
    i.run(parse('let a = 从未定义 + 1\n输出(a)'))
    assert '从未定义' in i.env
    assert isinstance(i.env['从未定义'], VirtualSymbol)
    assert i.auto_defined, i.auto_defined


def test_undefined_variable_can_be_used_in_expressions():
    """自动定义的变量可参与运算而不崩溃，产生新的宽容值。"""
    i = _healing_interp()
    i.run(parse('输出(幽灵变量 * 2 + 3)'))
    assert i.outputs
    assert isinstance(i.outputs[-1], VirtualSymbol)


# ─── 定义功能：未定义函数自动注册 ────────────────────────────────────────────

def test_undefined_function_auto_registered_and_callable():
    i = _healing_interp()
    i.run(parse('输出(未知函数(1, 2, 3))'))
    assert '未知函数' in i.builtins
    assert isinstance(i.builtins['未知函数'], VirtualSymbol)
    assert i.outputs and isinstance(i.outputs[-1], VirtualSymbol)


def test_undefined_function_registered_in_engine():
    i = _healing_interp()
    i.run(parse('未知函数(5)'))
    vr = get_virtual_registry()
    assert vr.has('未知函数')


# ─── 注册功能：新定义自动注册 ────────────────────────────────────────────────

def test_new_function_definition_auto_registered():
    i = _healing_interp()
    i.run(parse('func 方(x: Int) -> Int = (x) => x * x\n输出(方(4))'))
    assert get_virtual_registry().has('方')
    assert any(r['name'] == '方' for r in i.auto_registered)


def test_new_binding_auto_registered():
    i = _healing_interp()
    i.run(parse('let 圆周率近似 = 3\n输出(圆周率近似)'))
    assert get_virtual_registry().has('圆周率近似')


# ─── 审计与统计 ──────────────────────────────────────────────────────────────

def test_auto_define_recorded_with_kind():
    i = _healing_interp()
    i.run(parse('输出(幻影)'))
    kinds = {r['name']: r['kind'] for r in i.auto_defined}
    assert kinds.get('幻影') == '变量'


def test_engine_stats_reflect_registration():
    i = _healing_interp()
    i.run(parse('func 恒等(x: Int) -> Int = (x) => x\n输出(恒等(1))'))
    stats = get_virtual_registry().get_stats()
    assert stats['virtual_created'] >= 1
    assert stats['total_codes'] >= 1


# ─── 定义简写 / 嵌套 let-rec-in-lambda（解析器回归）──────────────────────────

def test_let_shorthand_function_keeps_params():
    """`let f(x) = body` 无返回类型简写：params 必须保留（定义功能）。"""
    out, _ = interpret('输出(let f(x) = x + 1 in f(5))')
    assert out[-1] == 6


def test_let_rec_in_lambda_does_not_leak_in():
    """lambda 体内的 `let rec f(...) -> T = ... in f(...)` 不得泄漏顶层声明。"""
    src = (
        'func 查找环境链(envs: List, name: String) -> Value = (envs, name) =>\n'
        '  let env = envs[0] in\n'
        '  let rec _lookup(e: List) -> Value =\n'
        '    e = [] ? (envs = [] ? 错误("未定义变量") : _lookup(envs[1:]))\n'
        '    : e[0][0] = name ? e[0][1] : _lookup(e[1:])\n'
        '  in _lookup(env)\n'
    )
    prog = parse(src)
    assert len(prog.decls) == 1, [type(d).__name__ for d in prog.decls]
    i = Interpreter()
    i.run(prog)
    assert '查找环境链' in i.funcs


def test_none_is_null_constant():
    """Matha 源码中的 None 别名应解析为空值（定义功能）。"""
    out, _ = interpret('let n = None\n输出(n = None)')
    assert out[-1] is True


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            reset_virtual_registry()
            t()
            passed += 1
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
        finally:
            reset_virtual_registry()
    print(f"\n自动定义/自动注册测试: {passed}/{passed + failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
