"""Matha 领域扩展模块：符号微积分（Symbolic Calculus）。

定位（内核纯净化 + 插件化重构的样板件）：
  本插件是「重能力外移」的标准做法 —— 内核只保留纯标准库的符号引擎
  ``src.kernel.symbolic``，第三方计算机代数系统（sympy）作为**可选加速后端**
  留在插件层，并且**只在函数体内部 import**：

    * ``import src.domains.symbolic_calculus``   → 不碰 sympy
    * VM 首次取用 ``integrate`` 而物化本插件       → 仍不碰 sympy
    * 调用 ``integrate``：先问内核引擎；内核覆盖不到（返回 None）
      才在这一刻 ``import sympy``                  → 唯一入口

  因此「sympy 是否被加载」等价于「是否真的调用到了内核覆盖不到的积分」，
  启动成本恒为 0（见 tests/test_plugin_load.py 的子进程取证）。

提供符号：
  ``integrate(被积式)(积分变量)`` / ``积分``  不定积分，返回标准串（不含积分常数）
  ``符号原子(名称)``                          由名字造符号原子，如 ``x = 符号原子("x")``

被积式可传符号原子（``x ^ 2``）、字符串（``"exp(-x**2)"``）或数值。
积分变量可传符号原子或字符串。

已知边界（如实声明，不做静默降级）：
  * **本插件不导出裸 ``x``** —— 清单里出现的符号名会经 ``LazyBuiltinTable`` 的
    成员判定被全局视为「已知符号」，那会把「``x`` 未定义即报错」这条内核契约
    改掉（实测波及 tests/test_bootstrap_host.py 与 test_auto_debug_e2e 共 4 例）。
    符号变量一律由用户自己绑定：``x = 符号原子("x")``。
  * 造符号的内建名叫 ``符号原子``而**不是** ``符号``：``matha/stdlib_symbols.matha``
    已用 ``func 符号(...)`` 构建自举符号表，插件一旦导出同名 ``符号``，物化时的
    ``target.update(table)`` 会覆盖它，直接打挂自举 parser（实测：
    tests/test_bootstrap_host.py::test_bootstrap_interpret_custom_op）。
  * VM 的 ``*`` 运算符按类型白名单实现（数值/字符串/序列），符号原子的乘法
    需写成字符串形式 ``integrate("2*x")("x")``；``+ - / ^`` 对符号原子可用。
  * 回退到 sympy 时输出为 sympy 的打印串（如 ``sqrt(pi)*erf(x)/2``），
    与内核标准串不保证逐字同形；能力对照见 docs/symbolic_parity.md。
"""

from __future__ import annotations

# ============================================================
# 后端一：内核符号引擎（纯标准库，零第三方依赖）
# ============================================================


def _to_ast(obj):
    """把 Matha 侧的值归一成内核 Expr：符号原子直接用，字符串走内核解析器。"""
    from src.kernel.symbolic.expr import Expr, symbol_expr, to_expr
    if isinstance(obj, Expr):
        return obj
    if isinstance(obj, str):
        return symbol_expr(obj)
    return to_expr(obj)


def _var_name(obj) -> str:
    """积分变量名：接受符号原子（Var）与字符串两种写法。"""
    from src.kernel.symbolic.expr import Var
    if isinstance(obj, Var):
        return obj.name
    if isinstance(obj, str):
        return obj
    raise TypeError(f"积分变量应为符号或字符串，实得 {type(obj).__name__}: {obj!r}")


def _kernel_integrate(ast, var: str):
    """内核引擎求不定积分；覆盖不到时返回 None（不猜、不假成功）。"""
    from src.kernel.symbolic.integrate import integrate
    from src.kernel.symbolic.latex import to_str
    out = integrate(ast, var)
    return None if out is None else to_str(out)


# ============================================================
# 后端二：sympy（可选加速后端 —— 只在被调用的一刻 import）
# ============================================================


def _sympy_integrate(ast, var: str) -> str:
    """懒加载 sympy 求积分。

    红线：``import sympy`` 只能写在本函数体内。移到模块顶层会让「加载插件」
    等同于「拖入 40 MB 计算机代数系统」，直接违反内核纯净化的启动零成本约定。
    """
    try:
        import sympy
    except ImportError as e:                      # sympy 属 optional-dependencies.accelerated
        raise RuntimeError(
            f"内核符号引擎未覆盖 ∫({str(ast)})d{var}，且可选后端 sympy 不可用"
            f"（{e}）。安装：pip install sympy；或改用数值定积分。"
        ) from e
    from src.kernel.symbolic.latex import to_str
    # 内核标准串即 Python 可解析写法（x**3/3、exp(-x**2)），仅 ln 需换名
    expr_text = to_str(ast).replace("ln(", "log(")
    sym = sympy.sympify(expr_text)
    return str(sympy.integrate(sym, sympy.Symbol(var)))


# ============================================================
# 对外内建（柯里化：integrate(被积式)(变量)，与 VM 的逐参应用一致）
# ============================================================


def integrate(expr):
    """不定积分第一参：返回 ``f(变量) -> 标准串``。

    路由：内核纯标准库引擎优先；仅当引擎返回 None（能力缺口）才动态导入 sympy。
    """
    ast = _to_ast(expr)

    def _of(var):
        name = _var_name(var)
        got = _kernel_integrate(ast, name)
        return got if got is not None else _sympy_integrate(ast, name)

    return _of


def 符号原子(name: str):
    """按名字造符号原子：``u = 符号原子("u")``，随后可写 ``integrate(u ^ 2)(u)``。"""
    from src.kernel.symbolic.expr import symbolic
    return symbolic(str(name))


def _register_symbolic_calculus(builtins: dict) -> None:
    """领域插件登记钩子（由 ``scripts/gen_domain_manifest.py`` 发现并写入清单）。

    本函数只登记轻量对象（普通 Python callable，内部才用内核 Expr），
    不触发任何第三方 import，也不注册裸单字母名（见模块 docstring 的边界说明）。
    """
    builtins["integrate"] = integrate
    builtins["积分"] = integrate
    builtins["符号原子"] = 符号原子


def _symbolic_calculus_symtab_names() -> list[str]:
    return ["integrate", "积分", "符号原子"]
