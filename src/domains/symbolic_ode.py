"""Matha 领域扩展模块：常微分方程求解（Ordinary Differential Equations）。

定位（内核纯净化 + 插件化重构的铺开件）：
  与 ``symbolic_calculus`` 同构 —— 内核只保留纯标准库的 ODE 引擎
  ``src.kernel.symbolic.ode``（可分离 / 一阶线性积分因子 / 二阶常系数齐次 /
  直接积分），覆盖面之外的**非线性一阶**（Riccati、齐次型 ``y'=(x+y)/x``、
  ``y'=x**2+y**2`` 等）与**高阶非齐次特解**显式抛 ``OdeUnsupported``；本插件
  把 sympy ``dsolve`` 作为**可选加速后端**，且**只在内核抛缺口的那一次调用里
  才 import**：

    * ``import src.domains.symbolic_ode``  → 不碰 sympy
    * VM 首次取用 ``解微分方程`` 而物化本插件 → 仍不碰 sympy
    * 调用 ``解微分方程``：先问内核引擎；内核能答（线性/可分离/常系数）
      全程不碰 sympy；仅当内核抛 ``OdeUnsupported`` 才在这一刻 ``import sympy``

  因此「sympy 是否被加载」等价于「是否真的调用到了内核覆盖不到的非线性 ODE」，
  启动成本恒为 0（取证口径见 tests/test_plugin_load.py）。

提供符号：
  ``解微分方程(方程串)(自变量)`` / ``ode``
      求解 ``dy/dx = f(x, y)`` 的通解，返回 ``y = ...`` 右端的标准串（积分常量 C1）。
      方程记法与内核一致：``y'(x)``、``y'``、``dy/dx``、``y(x)``、``y''`` 均可。
      函数名固定为 ``y``（与内核默认一致；覆盖 parity 文档全部非线性样例）。

已知边界（如实声明，不做静默降级）：
  * **本插件不导出裸 ``x`` / ``y``** —— 清单里的符号名会经 ``LazyBuiltinTable``
    成员判定被全局视为「已知符号」，那会把「未定义名即报错」这条内核契约改掉。
    方程以**字符串**整体传入，内部变量不由插件绑定。
  * 符号名取 ``解微分方程``（及英文名 ``ode``）而**不是** ``求解``/``解``：
    避免与自举语料、其它领域顶层函数同名（符号卫生红线，实测同名会打挂自举 parser）。
  * 内核能解的线性/可分离/常系数方程**优先走内核**，输出与内核逐字同形；
    仅内核缺口（非线性）才回退 sympy，此时输出是 sympy 的打印串
    （如 ``Eq(y(x), x*(C1 + log(x)))``），与内核标准串不保证同形。
  * 少数非线性方程 sympy ``dsolve`` 也会失败（如需 Airy 特殊函数的一阶 Riccati
    ``y'=x**2+y**2`` 在某些 sympy 版本内部报 TypeError）——这类**显式抛错并指向
    parity 文档**，绝不返回「无法求解」之类假成功。能力对照见 docs/symbolic_parity.md。
"""

from __future__ import annotations

# ============================================================
# 后端一：内核符号引擎（纯标准库，零第三方依赖）
# ============================================================


def _kernel_ode(spec: str, var: str):
    """内核引擎求 ODE 通解；覆盖不到（非线性）时返回 None（不猜、不假成功）。"""
    from src.kernel.symbolic import solve_ode
    from src.kernel.symbolic.ode import OdeUnsupported
    func = "y"
    try:
        return solve_ode(str(spec), func, var)
    except OdeUnsupported:
        return None


# ============================================================
# 后端二：sympy（可选加速后端 —— 只在被调用的一刻 import）
# ============================================================


def _sympy_ode(spec: str, var: str) -> str:
    """懒加载 sympy ``dsolve`` 求解内核覆盖不到的非线性 ODE。

    红线：``import sympy`` 只能写在本函数体内。移到模块顶层会让「加载插件」
    等同于「拖入 40 MB 计算机代数系统」，直接违反内核纯净化的启动零成本约定。
    """
    try:
        import sympy as sp
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application, convert_xor,
        )
    except ImportError as e:                      # sympy 属 optional-dependencies.accelerated
        raise RuntimeError(
            f"内核 ODE 引擎未覆盖 {spec!r}（非线性一阶/高阶非齐次），且可选后端 "
            f"sympy 不可用（{e}）。安装：pip install sympy；能力缺口见 "
            f"docs/symbolic_parity.md 第 6 节。"
        ) from e

    func = "y"
    trans = standard_transformations + (implicit_multiplication_application, convert_xor)

    def _norm(s: str) -> str:
        # 把 Matha 记法 y'(x) / y''(x) 归一成 sympy 的 Derivative(y(x), x[, x])
        s = s.replace(f"{func}''({var})", f"Derivative({func}({var}), {var}, {var})")
        s = s.replace(f"{func}'({var})", f"Derivative({func}({var}), {var})")
        return s

    if "=" not in spec:
        raise ValueError(f"ODE 方程缺少等号，无法解析: {spec!r}")
    lhs, rhs = spec.split("=", 1)
    local = {var: sp.Symbol(var), func: sp.Function(func)}
    try:
        L = parse_expr(_norm(lhs), local_dict=local, transformations=trans)
        R = parse_expr(_norm(rhs), local_dict=local, transformations=trans)
        sol = sp.dsolve(sp.Eq(L, R), local[func](local[var]))
    except Exception as e:
        raise ValueError(
            f"sympy 亦未能求解 {spec!r}（{type(e).__name__}: {e}）；"
            f"这类方程需特殊函数/幂级数解，见 docs/symbolic_parity.md 第 6 节。"
        ) from e
    # 输出 ``y = <右端>`` 的右端，贴近内核返回口径
    try:
        return str(sp.solve(sp.Eq(sol.lhs, sol.rhs), local[func](local[var]))[0])
    except Exception:
        return str(sol)


# ============================================================
# 对外内建（柯里化：解微分方程(方程)(变量)，与 VM 的逐参应用一致）
# ============================================================


def 解微分方程(spec):
    """ODE 第一参：返回 ``f(自变量) -> 通解右端串``。

    路由：内核纯标准库引擎优先；仅当引擎抛 ``OdeUnsupported``（非线性缺口）
    才动态导入 sympy ``dsolve``。
    """
    text = str(spec)

    def _of(var):
        name = str(var)
        got = _kernel_ode(text, name)
        return got if got is not None else _sympy_ode(text, name)

    return _of


def _register_symbolic_ode(builtins: dict) -> None:
    """领域插件登记钩子（由 ``scripts/gen_domain_manifest.py`` 发现并写入清单）。

    只登记轻量 callable（内部才用 sympy），不触发任何第三方 import，
    也不注册裸单字母名（见模块 docstring 的边界说明）。
    """
    builtins["解微分方程"] = 解微分方程
    builtins["ode"] = 解微分方程


def _symbolic_ode_symtab_names() -> list[str]:
    return ["解微分方程", "ode"]
