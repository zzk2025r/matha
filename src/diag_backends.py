"""诊断后端装载层（CLI 侧，非内核）。

内核门面 `src/kernel/exec_api.py` 静态上不允许 import `src.interp`（见
`scripts/dep_audit.py` 的内核禁入清单），所以遗留解释器只能在被**显式指名**时
才由本层 import 进来 —— 它自己在模块尾部向门面登记 `legacy-interp`。

这解决了两个互相拉扯的需求：
  * `matha eval` 的启动成本里不能有 4,249 行的遗留解释器；
  * `matha --backend=legacy-interp run x.matha` 又必须真的能用（而不是因为
    「还没 import 所以不在候选里」被 argparse 拒掉）。

`BackendChoices` 因此是一个惰性容器：`in` 判定发现要的是诊断后端时，先把遗留层
import 进来（登记），再判定；`iter` 只列已登记的（默认只有主线 vm）。
"""
from __future__ import annotations

import importlib

#: 已知的诊断后端名 → 登记它的模块（import 即登记，无须额外调用）。
KNOWN_DIAGNOSTIC_MODES: dict[str, str] = {
    "legacy-interp": "src.interp",
}

_loaded: set[str] = set()


def ensure_registered(module: str) -> None:
    """import 指定模块以触发其向门面登记诊断后端（幂等）。

    不吞异常：登记失败说明遗留层本身坏了，此时明确报错比静默退回主线更诚实。
    """
    if module in _loaded:
        return
    importlib.import_module(module)
    _loaded.add(module)


def run_legacy(source: str, *, debug: bool | None = None) -> tuple[list, list[str]]:
    """用遗留树走式解释器执行源码，返回 ``(输出, 轨迹)``。

    存在理由（重构阶段 2 第 2 项）：本仓库十几个诊断/成长/AI 子系统都需要
    “跑一段源码并拿到逐字节输出”，以前它们各自 `from src.interp import
    interpret`，等于把「四条执行路径」在应用层重新分叉。现在集中到这里：
    要遗留语义就显式调用本函数，默认主线走 `src.kernel.exec_api.run()`。

    与 `exec_api.run(source, mode="legacy-interp")` 的差别：门面只返回输出，
    而这里保留 trace（这些调用方确实读它）。
    """
    ensure_registered("src.interp")
    from src.interp import interpret
    return interpret(source) if debug is None else interpret(source, debug=debug)


def new_interpreter(*, debug: bool | None = None):
    """构造遗留解释器实例（仅供需要内省/单步的调用方，不是执行主路）。"""
    ensure_registered("src.interp")
    from src.interp import Interpreter
    return Interpreter() if debug is None else Interpreter(debug=debug)


__all__ = [
    "BACKENDS", "KNOWN_DIAGNOSTIC_MODES", "BackendChoices",
    "describe_unknown", "ensure_registered", "new_interpreter",
    "registered_modes", "run_legacy",
]


def registered_modes() -> list[str]:
    """当前已在门面上登记、且可在进程内执行的后端。"""
    from src.kernel import exec_api
    return exec_api.runnable_modes()


class BackendChoices:
    """供 argparse `choices=` 与手工校验共用的惰性后端容器。"""

    def __contains__(self, name: object) -> bool:
        if name in registered_modes():
            return True
        module = KNOWN_DIAGNOSTIC_MODES.get(name) if isinstance(name, str) else None
        if module is None:
            return False
        ensure_registered(module)
        return name in registered_modes()

    def __iter__(self):
        return iter(registered_modes())

    def __repr__(self) -> str:  # argparse 报错时列候选用
        return "{" + ", ".join(sorted(set(registered_modes()) | set(KNOWN_DIAGNOSTIC_MODES))) + "}"


BACKENDS = BackendChoices()


def describe_unknown(name: str) -> str:
    """未知后端名的诊断文案（含可用清单）。"""
    return (f"未知执行后端 {name!r}；可用：{', '.join(sorted(set(registered_modes()) | set(KNOWN_DIAGNOSTIC_MODES)))}")
