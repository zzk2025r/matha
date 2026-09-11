# -*- coding: utf-8 -*-
"""============================================================
   Matha 自举引导层（Python 宿主侧薄引导）
   ============================================================
   职责：
     1. 加载 Matha 核心模块（词法器/语法器/标准库/运行时引擎）
     2. 校验自举闭环：模块可加载、命名空间隔离、纯函数语义正确
     3. 向外部（CLI/REPL/VM/编译器）暴露一个"已装载 Matha 运行时"的解释器

   边界（重要）：
     当前 Matha 词法器/解释器是用 Matha 写的、跑在 Python 宿主解释器上，
     属于「二级解释」。宿主 AST 解释器的环境模型（每次调用全量环境快照）
     在执行深柯里化递归（如词法器逐字符主循环）时性能与栈深度不可接受。
     因此本阶段的自举目标是——
       模块可加载 ✓  命名空间隔离 ✓  Matha 纯函数语义正确 ✓
     而在宿主上跑完整的 Matha 词法/解释递归，留给 VM 字节码执行（task #19）
     与原生二进制编译（Matha 的最终目标，跳过 C 中转）。

   用法：
     from matha_bootstrap import bootstrap, 自检
     interp, loaded = bootstrap()
     print(自检(interp))
   ============================================================"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.interp import Interpreter
from src.parser import parse

MATHA_DIR = PROJECT_ROOT / "matha"

# 核心模块（按依赖顺序）：(中文模块名, 源文件相对 matha/ 的路径)
CORE_MODULES: list[tuple[str, str]] = [
    ("词法器", "lexer.matha"),
    ("语法器", "parser.matha"),
    ("标准库", "stdlib.matha"),
    ("运行时引擎", "runtime/matha_runtime.matha"),
]


def bootstrap(interp: Interpreter | None = None, debug: bool = False
              ) -> tuple[Interpreter, list[str]]:
    """加载全部核心 Matha 模块，返回 (解释器, 已加载模块名列表)。"""
    interp = interp if interp is not None else Interpreter(debug=debug)
    loaded: list[str] = []
    for name, rel in CORE_MODULES:
        path = MATHA_DIR / rel
        if not path.exists():
            raise FileNotFoundError(f"核心模块缺失: {path}")
        source = path.read_text(encoding="utf-8")
        interp.run(parse(source))
        if name in interp.modules:
            loaded.append(name)
        else:
            raise RuntimeError(f"模块 '{name}' 加载后未注册（请检查 module 声明）")
    return interp, loaded


def _call(interp: Interpreter, mod: str, fn: str, *args):
    """调用某 Matha 模块内的函数（closure/FuncDef 统一入口）。"""
    target = interp.modules[mod][fn]
    return interp._call_func_or_closure(target, list(args))


def 自检(interp: Interpreter | None = None) -> dict:
    """运行自举闭环健康检查，返回结果报告。"""
    interp, loaded = bootstrap(interp)
    report: dict = {"已加载模块": loaded, "检查": [], "全部通过": True}

    def 用例(mod: str, fn: str, args: list, 期望):
        try:
            得 = _call(interp, mod, fn, *args)
            ok = (得 == 期望)
            report["检查"].append(
                {"项": f"{mod}.{fn}{tuple(args)}", "得": 得, "期望": 期望, "通过": ok})
            if not ok:
                report["全部通过"] = False
        except Exception as e:  # noqa: BLE001
            report["检查"].append(
                {"项": f"{mod}.{fn}{tuple(args)}", "错误": f"{type(e).__name__}: {e}", "通过": False})
            report["全部通过"] = False

    # —— 运行时引擎：组合数学 / 数论（纯 Matha 实现）——
    用例("运行时引擎", "factorial", [5], 120)
    用例("运行时引擎", "perm", [5, 2], 20)
    用例("运行时引擎", "comb", [5, 2], 10)
    用例("运行时引擎", "gcd", [48, 36], 12)
    用例("运行时引擎", "is_prime", [17], True)
    用例("运行时引擎", "is_prime", [4], False)
    用例("运行时引擎", "sieve", [20], [2, 3, 5, 7, 11, 13, 17, 19])
    # —— 词法器：纯辅助函数（Matha 代码可运行、结果正确）——
    用例("词法器", "是数字码", [53], True)   # '5'
    用例("词法器", "是数字码", [43], False)  # '+'
    用例("词法器", "是字母码", [120], True)  # 'x'
    # —— 标准库：字符串 / 列表工具 ——
    用例("标准库", "find", ["bc", "abcd"], 1)
    用例("标准库", "list_sort", [[3, 1, 2]], [1, 2, 3])
    用例("标准库", "list_reverse", [[1, 2, 3]], [3, 2, 1])
    return report


def _打印报告(report: dict) -> int:
    print("=== Matha 自举闭环自检 ===")
    print("已加载模块:", "、".join(report["已加载模块"]))
    for c in report["检查"]:
        if c.get("通过"):
            print(f"  ✓ {c['项']} = {c['得']!r}")
        else:
            print(f"  ✗ {c['项']}  得={c.get('得')!r} 期望={c.get('期望')!r} {c.get('错误','')}")
    print("结果:", "全部通过 ✓" if report["全部通过"] else "存在失败 ✗")
    return 0 if report["全部通过"] else 1


if __name__ == "__main__":
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    sys.exit(_打印报告(自检()))
