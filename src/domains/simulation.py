"""Matha 领域扩展模块：建模仿真（Modeling & Simulation）。

数值积分双面回调：欧拉法 / 四阶龙格-库塔（RK4）。导函数是 Matha 函数值，
每一步经运行本体的 ``invoke_value`` 协议回调（宿主解释器与 VM 同名方法，
src/interp.py 与 src/mbc/vm.py）——「资源库当代码用」链路的数值核心：
资源里定义的动力学模型可被 仿真_欧拉 / 仿真_龙格库塔 直接调用。

注册面（三处，与 capability 同构）：
  * 宿主解释器：src/interp.py 内建表直接绑定运行本体；
  * VM 官方入口：src/kernel/exec_api._wire_plugin_runtime 经
    src.plugin_api.make_simulation_runtime 注入本模块 ``make_runtime``
    产物（setdefault，不覆盖程序自定义同名函数；惰性跳板，构造零 import）；
  * 领域清单：``_register_simulation`` 供 scripts/gen_domain_manifest.py 发现。

已知边界（如实声明，不做静默降级）：
  * 裸 VM（plugins="off" 或直接构造 src.mbc.vm.VM）无注入面 → 符号未定义；
  * ``@：【加载领域】，建模仿真`` 物化的是共享语境解释器版本：可回调宿主
    闭包（闭包元组自带捕获环境，跨解释器实例可调）；VM 闭包显式拒绝——
    VM Closure 只能由官方入口注入面的运行本体 ``invoke_value`` 执行；
  * 导函数每步回调，错误（含 Matha 层错误）原样传播，不吞不改。

用法（双面一致）::

    仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, "起点": 0, "终点": 2, "步数": 1000})
    → {"方法": "欧拉", "起点": 0.0, "终点": 2.0, "步数": 1000,
       "末态": <数值>, "轨迹": [[t, y], ...]}

向量状态：初值为列表（如 弹簧振子 [位移, 速度]），导函数返回等长列表；
轨迹条目为 [t, [分量...]]。步长 h = (终点 - 起点) / 步数；时间节点
t_k = 起点 + k·h（乘法形式，不做累加——双面浮点逐位一致）。
"""

from __future__ import annotations

import math

_SYMBOLS = ("仿真_欧拉", "仿真_龙格库塔")


# ============================================================
# 规格校验（错误消息双面逐字一致——纯 Python 侧抛出，不打印值本身）
# ============================================================

def _is_matha_fn(v) -> bool:
    """Matha/Python 可调用判定：宿主闭包元组 / VM Closure（鸭子判定）/
    Python 可调用。不 import 运行时模块（领域层延迟依赖）。"""
    if isinstance(v, tuple) and len(v) > 0 and v[0] == "__closure__":
        return True
    if callable(v):
        return True
    return type(v).__name__ == "Closure" and hasattr(v, "fn") and hasattr(v, "frame")


def _is_num(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return True
    return isinstance(v, float) and math.isfinite(v)


def _parse_spec(spec):
    """规格校验与归一化：返回 (导函数, y0, t0, t1, n, 向量维度|None)。"""
    if not isinstance(spec, dict):
        raise ValueError("仿真: 规格须为字典（键：导函数/初值/起点/终点/步数）")
    f = spec.get("导函数")
    if f is None:
        raise ValueError("仿真: 规格缺少「导函数」")
    if not _is_matha_fn(f):
        raise ValueError("仿真: 「导函数」须为函数")
    if "初值" not in spec:
        raise ValueError("仿真: 规格缺少「初值」")
    y0 = spec["初值"]
    if isinstance(y0, list):
        if not y0 or not all(_is_num(x) for x in y0):
            raise ValueError("仿真: 「初值」列表须为非空数值列表")
        dim = len(y0)
    elif _is_num(y0):
        dim = None
    else:
        raise ValueError("仿真: 「初值」须为数值或数值列表")
    t0 = spec.get("起点", 0)
    if not _is_num(t0):
        raise ValueError("仿真: 「起点」须为数值")
    if "终点" not in spec:
        raise ValueError("仿真: 规格缺少「终点」")
    t1 = spec["终点"]
    if not _is_num(t1):
        raise ValueError("仿真: 「终点」须为数值")
    if t1 <= t0:
        raise ValueError("仿真: 「终点」须大于「起点」")
    n = spec.get("步数", 100)
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("仿真: 「步数」须为正整数")
    return f, y0, float(t0), float(t1), n, dim


def _check_dy(dy, dim):
    """导函数返回值形状校验（每步回调后）。"""
    if dim is None:
        if not _is_num(dy):
            raise ValueError("仿真: 导函数须返回数值（与标量初值同形）")
        return dy
    if not isinstance(dy, list) or len(dy) != dim or not all(_is_num(x) for x in dy):
        raise ValueError(f"仿真: 导函数须返回长度 {dim} 的数值列表（与向量初值同形）")
    return dy


def _advance(y, h, dy, dim):
    """欧拉推进：y + h·dy（列表形态产新列表，非就地）。"""
    if dim is None:
        return y + h * dy
    return [yi + h * dyi for yi, dyi in zip(y, dy)]


def _rk4_combine(y, h, k1, k2, k3, k4, dim):
    """RK4 合成：y + h/6·(k1 + 2k2 + 2k3 + k4)。"""
    if dim is None:
        return y + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return [yi + (h / 6.0) * (k1i + 2 * k2i + 2 * k3i + k4i)
            for yi, k1i, k2i, k3i, k4i in zip(y, k1, k2, k3, k4)]


def _integrate(method, call, spec):
    """统一积分入口。call(导函数, t, y) 由注册面注入（运行本体 invoke_value）。"""
    f, y0, t0, t1, n, dim = _parse_spec(spec)
    h = (t1 - t0) / n
    y = y0
    traj = [[t0, y]]
    for k in range(n):
        t = t0 + k * h
        if method == "龙格库塔":
            k1 = _check_dy(call(f, t, y), dim)
            k2 = _check_dy(call(f, t + h / 2.0, _advance(y, h / 2.0, k1, dim)), dim)
            k3 = _check_dy(call(f, t + h / 2.0, _advance(y, h / 2.0, k2, dim)), dim)
            k4 = _check_dy(call(f, t + h, _advance(y, h, k3, dim)), dim)
            y = _rk4_combine(y, h, k1, k2, k3, k4, dim)
        else:
            dy = _check_dy(call(f, t, y), dim)
            y = _advance(y, h, dy, dim)
        traj.append([t0 + (k + 1) * h, y])
    return {"方法": method, "起点": t0, "终点": t1, "步数": n,
            "末态": y, "轨迹": traj}


# ============================================================
# 公开入口（宿主解释器内建与 make_runtime 共用；runtime 须有 invoke_value）
# ============================================================

def integrate_euler(spec, runtime) -> dict:
    """仿真_欧拉(规格)：欧拉法数值积分，导函数经 runtime.invoke_value 回调。"""
    return _integrate("欧拉", lambda f, t, y: runtime.invoke_value(f, [t, y]), spec)


def integrate_rk4(spec, runtime) -> dict:
    """仿真_龙格库塔(规格)：四阶龙格-库塔，导函数经 runtime.invoke_value 回调。"""
    return _integrate("龙格库塔", lambda f, t, y: runtime.invoke_value(f, [t, y]), spec)


# ============================================================
# 清单物化面（共享语境解释器版本——与 capability 的 _context() 同构）
# ============================================================

_shared_context = None


def _context():
    global _shared_context
    if _shared_context is None:
        from src.interp import Interpreter
        _shared_context = Interpreter()
    return _shared_context


def _reject_vm_closure(f) -> None:
    if type(f).__name__ == "Closure" and hasattr(f, "fn") and hasattr(f, "frame"):
        raise ValueError(
            "仿真: 导函数为 VM 闭包——请经官方入口（src.kernel.exec_api）运行，"
            "注入面绑定运行本体回调；清单物化面只支持宿主闭包/Python 可调用")


def integrate_euler_plain(spec) -> dict:
    """清单物化面入口：共享语境解释器回调（VM 闭包显式拒绝）。"""
    _parse_spec(spec)  # 先走校验，缺键/非法值给出规格错误而非闭包错误
    _reject_vm_closure(spec.get("导函数"))
    return integrate_euler(spec, _context())


def integrate_rk4_plain(spec) -> dict:
    _parse_spec(spec)
    _reject_vm_closure(spec.get("导函数"))
    return integrate_rk4(spec, _context())


def make_runtime(runtime):
    """官方入口注入面：返回绑定运行本体的仿真内建。

    runtime 是运行中的 VM 或宿主解释器（二者均有同名 invoke_value 协议）。
    """
    return {
        "仿真_欧拉": lambda spec: integrate_euler(spec, runtime),
        "仿真_龙格库塔": lambda spec: integrate_rk4(spec, runtime),
    }


def _register_simulation(builtins: dict) -> None:
    """领域插件登记钩子（scripts/gen_domain_manifest.py 发现）。

    只登记轻量 callable，不触发任何 import；真实回调在调用时经共享语境
    解释器或官方入口注入面完成。
    """
    builtins["仿真_欧拉"] = integrate_euler_plain
    builtins["仿真_龙格库塔"] = integrate_rk4_plain


def _simulation_symtab_names() -> list[str]:
    return list(_SYMBOLS)


__all__ = [
    "integrate_euler", "integrate_rk4",
    "integrate_euler_plain", "integrate_rk4_plain",
    "make_runtime", "_register_simulation", "_simulation_symtab_names",
]
