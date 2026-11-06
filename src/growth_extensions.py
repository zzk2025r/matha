# -*- coding: utf-8 -*-
"""成长引擎 · opt-in 源码扩展（从核心 grow 管线迁出的破坏性改写）。

背景（见 KNOWN_ISSUES.md §7c / Tier 1 计划 S2/S3）：
  核心 `MathaGrowthEngine.grow` 的正确性闸门 P1 要求「名守恒」——改写后不得丢失原文
  已绑定的顶层名字。而「临时变量内联后删除其绑定」「删除未引用绑定」这类改写**结构性**
  违反名守恒（被删的名字正是它自身的绑定），永远过不了 P1 → 过去它们在核心管线里要么恒被拒
  （内存优化删 `temp_` 行）、要么恒 no-op（死代码消除把赋值自身 LHS 也算进 used）。

处置：把这两类能力从核心自动管线**移除**，改成本模块的 **opt-in 扩展**——由调用方显式经
`UnifiedGrowth.register_extension(name, fn)` 注册、`list_extensions()` 搜索、
`get_extension_callable(name)` 取回并调用。扩展**不走 P1**，改由「在一次性解释器上分别
运行原文与改写文、逐项比对可观测 outputs」自证语义等价：不等价（或任一运行出错）即原样
返回，绝不产出坏源码。

依赖方向：本扩展层可依赖内核/核心的公开接口（`MathaGrowthEngine` 的静态执行/替换助手）；
核心 `matha_growth` 不反向 import 本模块（单向）。
"""
from __future__ import annotations

import re

from src.matha_growth import MathaGrowthEngine as _G

__all__ = [
    "inline_single_use_temps",
    "optimize_temp_inlining",
    "remove_unused_top_bindings",
    "optimize_dead_code",
    "GROWTH_EXTENSIONS",
    "register_into",
]

# 内联右端限定为「简单 token」：标识符或纯数字字面量——避免重复求值副作用与优先级改变。
_SIMPLE_TOKEN = r'[^\W\d]\w*|\d+(?:\.\d*)?'


def inline_single_use_temps(source: str) -> tuple[str, int]:
    """原始变换：把「仅定义一次、右端为简单 token」的临时绑定内联到其使用点并删除定义行。

    返回 (result_source, inlined_count)。仅在满足以下全部条件时才内联某名字：
      ① 该行形态为 `name = <简单 token>`（右端全行锚定，非表达式/非函数调用）；
      ② `name` 在全文仅被赋值一次（无同名重绑定 → 逐点代入与自引用皆安全）；
      ③ 替换经词边界、避开字符串字面量。
    语义是否真的等价由上层 `optimize_temp_inlining` 经 outputs 对拍裁定，本函数只产出候选。
    """
    lines = source.split('\n')
    def_re = re.compile(rf'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*(?!=)({_SIMPLE_TOKEN})[ \t]*$')
    any_assign = re.compile(r'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*')

    counts: dict[str, int] = {}
    for ln in lines:
        m = any_assign.match(ln)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1

    inlined: dict[str, str] = {}
    kept_lines: list[str] = []
    for ln in lines:
        m = def_re.match(ln)
        if m and counts.get(m.group(1), 0) == 1:
            inlined[m.group(1)] = m.group(2)   # 记录 name→token，丢弃定义行
            continue
        kept_lines.append(ln)

    if not inlined:
        return source, 0

    out_lines: list[str] = []
    for ln in kept_lines:
        newline = ln
        for name, token in inlined.items():
            newline, _ = _G._sub_outside_strings(rf'\b{re.escape(name)}\b', token, newline)
        out_lines.append(newline)
    return '\n'.join(out_lines), len(inlined)


def optimize_temp_inlining(source: str) -> dict:
    """opt-in 扩展入口（S2）：临时变量内联，自带 outputs 对拍自证等价（不走 P1）。

    契约：只有当「原文可运行」且「改写文可运行」且两者可观测 outputs 逐项相等时才返回改写文；
    任一出错或不等价 → 原样返回原文（诚实降级，绝不产出坏源码）。返回值恒为可机读的 dict。
    """
    improved, n = inline_single_use_temps(source)
    if n == 0 or improved == source:
        return {"improved_source": source, "applied": 0, "equivalent": True,
                "note": "无可安全内联的临时变量"}
    o_out, o_err = _G._exec_outputs(source)
    i_out, i_err = _G._exec_outputs(improved)
    if o_err is not None or i_err is not None or o_out != i_out:
        return {"improved_source": source, "applied": 0, "equivalent": False,
                "note": "内联候选未通过 outputs 对拍，原样返回（不产出坏源码）"}
    return {"improved_source": improved, "applied": n, "equivalent": True,
            "note": f"临时变量内联 × {n}"}


def remove_unused_top_bindings(source: str) -> tuple[str, int]:
    """原始变换：删除「除自身定义行外全文再无引用」的顶层绑定 `name = <expr>`。

    返回 (result_source, removed_count)。判定「被引用」以词边界扫描其余各行
    （含注释/观察行，保守：宁可不删）。不判断右端是否有副作用——由上层
    `optimize_dead_code` 经 outputs 对拍兼面：若删除改变了可观测输出（如右端有副作用）则回退。
    旧核心 `_apply_dead_code_elimination` 因把自身 LHS 也算进 used → 恒 no-op，此为正修。
    """
    def_re = re.compile(r'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*(?!=)')
    result_lines = source.split('\n')
    removed = 0
    while True:
        removed_one = False
        for idx, ln in enumerate(result_lines):
            m = def_re.match(ln)
            if not m:
                continue
            name = m.group(1)
            rest = '\n'.join(result_lines[:idx] + result_lines[idx + 1:])
            if re.search(rf'\b{re.escape(name)}\b', rest):
                continue   # 仍被引用 → 不删
            result_lines.pop(idx)
            removed += 1
            removed_one = True
            break
        if not removed_one:
            break
    return '\n'.join(result_lines), removed


def optimize_dead_code(source: str) -> dict:
    """opt-in 扩展入口（S3）：删除未被引用的顶层绑定，自带 outputs 对拍自证等价（不走 P1）。

    删未用绑定同样破 P1 名守恒（被删名字正是它自身），故不入核心管线。本扩展删除后
    逐字比对原文/改写文可观测 outputs：任一出错或不等价 → 原样返回（右端有副作用等情形会被
    此守住）。返回恒为可机读 dict。
    """
    improved, n = remove_unused_top_bindings(source)
    if n == 0 or improved == source:
        return {"improved_source": source, "applied": 0, "equivalent": True,
                "note": "无可安全删除的未用顶层绑定"}
    o_out, o_err = _G._exec_outputs(source)
    i_out, i_err = _G._exec_outputs(improved)
    if o_err is not None or i_err is not None or o_out != i_out:
        return {"improved_source": source, "applied": 0, "equivalent": False,
                "note": "删绑定候选未通过 outputs 对拍，原样返回（不产出坏源码）"}
    return {"improved_source": improved, "applied": n, "equivalent": True,
            "note": f"未用顶层绑定删除 × {n}"}


# 已就绪的 opt-in 扩展（调用方按需经 register_into / UnifiedGrowth.register_extension 注册）。
GROWTH_EXTENSIONS: dict[str, object] = {
    "temp_var_inline": optimize_temp_inlining,   # S2
    "dead_binding_elimination": optimize_dead_code,   # S3
}


def register_into(unified) -> bool:
    """把本模块全部扩展注册进给定 `UnifiedGrowth` 实例（经既有 register_extension 面）。"""
    ok = True
    for name, fn in GROWTH_EXTENSIONS.items():
        ok = bool(unified.register_extension(name, fn)) and ok
    return ok
