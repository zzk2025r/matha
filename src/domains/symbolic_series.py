"""Matha 领域扩展模块：级数求和（Series Summation）。

定位（内核纯净化 + 插件化重构的铺开件）：
  与 ``symbolic_calculus`` / ``symbolic_ode`` 同构 —— 内核只保留纯标准库的级数引擎
  ``src.kernel.symbolic.series``（麦克劳林/泰勒展开、Faulhaber 多项式求和、
  几何/望远镜闭式、π²/6 等常见闭式识别），覆盖面之外的**负整数幂求和**
  （调和级数 ``Σ1/n``、交错 ``Σ(-1)**n/n`` 等需 ``digamma``/对数闭式）显式抛
  ``SeriesUndetermined``；本插件把 sympy ``Sum.doit`` 作为**可选加速后端**，
  且**只在内核抛缺口的那一次调用里才 import**：

    * ``import src.domains.symbolic_series``   → 不碰 sympy
    * VM 首次取用 ``级数求和`` 而物化本插件       → 仍不碰 sympy
    * 调用 ``级数求和``：先问内核引擎；内核能答（Faulhaber/几何/闭式识别）
      全程不碰 sympy；仅当内核抛 ``SeriesUndetermined`` 才在这一刻 ``import sympy``

  因此「sympy 是否被加载」等价于「是否真的调用到了内核覆盖不到的级数」，
  启动成本恒为 0（取证口径见 tests/test_plugin_load.py）。

提供符号：
  ``级数求和(通项)(求和变量)(下界)(上界)`` / ``sum_series``
      求 ``Σ[下界, 上界] 通项``，返回标准串（闭式或数值）。柯里化：VM 的
      ``级数求和(a, b, c, d)`` 等价于逐参应用 ``级数求和(a)(b)(c)(d)``。
      上界写 ``"oo"`` / ``"∞"`` / ``"inf"``（或 ``1e999``）表示无穷级数。

已知边界（如实声明，不做静默降级）：
  * **本插件不导出裸 ``n`` / ``x``** —— 清单里的符号名会经 ``LazyBuiltinTable``
    成员判定被全局视为「已知符号」，会把「未定义名即报错」的内核契约改掉。
    通项以**字符串**整体传入，求和变量由第二参给出。
  * 符号名取 ``级数求和``（及英文名 ``sum_series``）而**不是** ``求和``/``Σ``：
    避免与自举语料、其它领域顶层函数同名（符号卫生红线）。
  * 内核能答的求和（Faulhaber/几何/π²/6 等）**优先走内核**，输出与内核逐字同形；
    仅内核缺口（负整数幂/交错调和等）才回退 sympy，此时输出为 sympy 打印串
    （如 ``137/60``、``-log(2)``），与内核标准串不保证同形。能力缺口见
    docs/symbolic_parity.md 第 5 节。发散级数（``Σ1/n`` 上界 ∞）sympy 给 ``oo``。
"""

from __future__ import annotations

_INF_TOKENS = {"oo", "∞", "inf", "+inf"}


def _is_inf(v) -> bool:
    try:
        if float(v) == float("inf"):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip().lower() in _INF_TOKENS


def _to_int(v) -> int:
    f = float(v)
    return int(round(f))


# ============================================================
# 后端一：内核符号引擎（纯标准库，零第三方依赖）
# ============================================================


def _kernel_sum(term: str, var: str, lower, upper):
    """内核引擎求级数和；覆盖不到（负整数幂等）时返回 None（不猜、不假成功）。"""
    from src.kernel.symbolic.series import sum_series
    from src.kernel.symbolic.expr import symbol_expr
    from src.kernel.symbolic.series import SeriesUndetermined
    from src.kernel.symbolic.latex import to_str

    up = None if (upper is None or _is_inf(upper)) else _to_int(upper)
    try:
        out = sum_series(symbol_expr(term), var, _to_int(lower), up)
    except SeriesUndetermined:
        return None
    if hasattr(out, "free_vars"):          # Expr
        return to_str(out)
    return str(out)                          # float/int


# ============================================================
# 后端二：sympy（可选加速后端 —— 只在被调用的一刻 import）
# ============================================================


def _sympy_sum(term: str, var: str, lower, upper) -> str:
    """懒加载 sympy ``Sum.doit`` 求内核覆盖不到的级数。

    红线：``import sympy`` 只能写在本函数体内（见模块 docstring）。
    """
    try:
        import sympy as sp
    except ImportError as e:                      # sympy 属 optional-dependencies.accelerated
        raise RuntimeError(
            f"内核级数引擎未覆盖 Σ({term})（负整数幂/交错调和等），且可选后端 "
            f"sympy 不可用（{e}）。安装：pip install sympy；能力缺口见 "
            f"docs/symbolic_parity.md 第 5 节。"
        ) from e

    sym = sp.Symbol(var)
    expr = sp.sympify(term.replace("^", "**"))
    lo = _to_int(lower)
    hi = sp.oo if (upper is None or _is_inf(upper)) else _to_int(upper)
    try:
        val = sp.Sum(expr, (sym, lo, hi)).doit()
    except Exception as e:
        raise ValueError(
            f"sympy 亦未能求和 Σ({term})（{type(e).__name__}: {e}）；"
            f"见 docs/symbolic_parity.md 第 5 节。"
        ) from e
    return str(val)


# ============================================================
# 对外内建（柯里化：级数求和(通项)(变量)(下界)(上界)）
# ============================================================


def 级数求和(term):
    """级数第一参（通项）：返回逐参应用的闭包链。

    路由：内核纯标准库引擎优先；仅当引擎抛 ``SeriesUndetermined`` 才动态导入 sympy。
    """
    text = str(term)

    def _var(var):
        name = str(var)

        def _lower(lower):
            def _upper(upper):
                got = _kernel_sum(text, name, lower, upper)
                return got if got is not None else _sympy_sum(text, name, lower, upper)

            return _upper

        return _lower

    return _var


def _register_symbolic_series(builtins: dict) -> None:
    """领域插件登记钩子（由 ``scripts/gen_domain_manifest.py`` 发现并写入清单）。

    只登记轻量 callable（内部才用 sympy），不触发任何第三方 import，
    也不注册裸单字母名（见模块 docstring 的边界说明）。
    """
    builtins["级数求和"] = 级数求和
    builtins["sum_series"] = 级数求和


def _symbolic_series_symtab_names() -> list[str]:
    return ["级数求和", "sum_series"]
