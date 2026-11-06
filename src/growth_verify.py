# -*- coding: utf-8 -*-
"""成长引擎的语义验证后端 —— 自包含、可插拔、默认走 Matha 主链。

为什么要有这个模块（G-1 的成因，均为实测坐实，见 docs/KNOWN_ISSUES.md 第八节）：
原 ``MathaGrowthEngine._verify`` 借 ``CrossLanguageVerifier`` 做验证，而该验证器
的 ``"python"`` 前端实为 ``mir2_frontend.PythonFrontend``（其 ``compile`` 就是
``ast.parse``，属 Python 子集前端），注册前端集合里没有 matha。更要命的是调用
形态：``verify(algorithm: str, sources: dict[str, str])`` 被以两个位置参数调用，
于是每次抛 ``AttributeError: 'str' object has no attribute 'items'``，再被
``except Exception: return False`` 吞掉 —— 该字段对**任何**输入恒为 False，
连「同一份等价源码自比」也报不一致，不携带任何信息。

本模块把验证通路换到与输入域一致的语言上：用 Matha 主链（``src.parser`` +
``src.interp``）分别执行改写前后的两份源码，比对可观测 ``outputs``。

判据（保守口径，宁判 False 不误报 True）：

  1. 两侧都必须能解析并运行成功；
  2. 两侧都必须**有可观测输出**——无输出即无从验证，不判一致（G-2）；
  3. 输出逐项相等才判一致；
  4. **不设「同文即一致」捷径**：同文垃圾、同文无输出一律不判一致。

安全边界：解释器一律以 ``foreign_routing=False`` 构造，使 ``#：`` 全能前缀
（外来语言源码 → 外部解释器路由）在本通路上**结构性**不可执行。当前主链解析器
本就构造不出可执行的外来声明（``#：{ import os }`` 抛 ``ParseError``，
``#：符号 P = 5.0`` 退化为 ``MechUnit`` 并抛未定义名），这里仍把兜底做成硬约束，
而不是依赖一次实测结论。

后端按名字注册与切换；出厂唯一后端为 ``mainchain``，注册同名后端不静默覆盖。
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger("matha.growth.verify")

# ============================================================
# 机器可读口径（供诊断输出与测试锁使用）
# ============================================================

REASON_CONSISTENT = "consistent"
REASON_ORIG_ERROR = "original_unrunnable"
REASON_IMPROVED_ERROR = "improved_unrunnable"
REASON_ORIG_SILENT = "original_no_observable_output"
REASON_IMPROVED_SILENT = "improved_no_observable_output"
REASON_OUTPUTS_DIFFER = "outputs_differ"


@dataclass
class SemanticVerdict:
    """一次语义等价判定的完整结果。

    ``reason`` 让「为什么不一致」可被诊断与锁定，而不是像 G-1 那样把所有
    失败原因压成一个 False。
    """
    consistent: bool
    reason: str
    original_outputs: list | None = None
    improved_outputs: list | None = None
    detail: str = field(default="")


# ============================================================
# 主链执行
# ============================================================

def run_outputs(source: str) -> tuple[list | None, str | None]:
    """在一次性全新解释器上执行 Matha 源码，返回 ``(outputs, error | None)``。

    * 每次新建 ``Interpreter``：实例间不共享可变状态，杜绝用例互相污染。
    * ``foreign_routing=False``：结构性禁用 ``#：`` 外部语言路由（见模块文档）。
    * 解析或运行期异常一律如实捕获为 error 字符串并写入日志，**不静默压平**。
    """
    try:
        from src.interp import Interpreter
        from src.parser import parse
        interp = Interpreter(debug=False, foreign_routing=False)
        outputs, _trace = interp.run(parse(source))
        return list(outputs), None
    except Exception as ex:                                  # noqa: BLE001
        logger.debug("growth_verify 执行失败：%s", ex)
        return None, f"{type(ex).__name__}: {ex}"


# ============================================================
# 默认后端：Matha 主链
# ============================================================

def verify_mainchain(original: str, improved: str) -> SemanticVerdict:
    """按保守判据比较改写前后的可观测输出。"""
    o_out, o_err = run_outputs(original)
    if o_err is not None:
        return SemanticVerdict(False, REASON_ORIG_ERROR, detail=o_err)

    i_out, i_err = run_outputs(improved)
    if i_err is not None:
        return SemanticVerdict(False, REASON_IMPROVED_ERROR,
                               original_outputs=o_out, detail=i_err)

    # G-2：空对空不是证据。两侧都没输出时，语义差异无从观察，必须不判一致。
    if not o_out:
        return SemanticVerdict(False, REASON_ORIG_SILENT,
                               original_outputs=o_out, improved_outputs=i_out)
    if not i_out:
        return SemanticVerdict(False, REASON_IMPROVED_SILENT,
                               original_outputs=o_out, improved_outputs=i_out)

    if o_out == i_out:
        return SemanticVerdict(True, REASON_CONSISTENT, o_out, i_out)
    return SemanticVerdict(False, REASON_OUTPUTS_DIFFER, o_out, i_out)


# ============================================================
# 后端注册表（可插拔入口）
# ============================================================

_BACKENDS: dict[str, Callable[[str, str], SemanticVerdict]] = {}
_ACTIVE = "mainchain"


def register_backend(name: str,
                     fn: Callable[[str, str], SemanticVerdict],
                     *, override: bool = False) -> bool:
    """登记一个验证后端。同名默认拒绝，不静默覆盖。"""
    if not name or not callable(fn):
        return False
    if name in _BACKENDS and not override:
        logger.warning("growth_verify 后端 %r 已存在，拒绝覆盖", name)
        return False
    _BACKENDS[name] = fn
    return True


def available_backends() -> list[str]:
    return sorted(_BACKENDS)


def active_backend() -> str:
    return _ACTIVE


def set_active_backend(name: str) -> bool:
    """切换当前生效后端；未登记过的名字一律拒绝。"""
    global _ACTIVE
    if name not in _BACKENDS:
        logger.warning("growth_verify 后端 %r 未登记，保持 %r", name, _ACTIVE)
        return False
    _ACTIVE = name
    return True


register_backend("mainchain", verify_mainchain, override=True)


# ============================================================
# 对外入口
# ============================================================

def verify(original: str, improved: str) -> SemanticVerdict:
    """用当前生效后端做语义等价判定。"""
    return _BACKENDS[_ACTIVE](original, improved)


def is_semantically_consistent(original: str, improved: str) -> bool:
    """布尔便捷入口；判据与理由见 :func:`verify`。"""
    return verify(original, improved).consistent
