# -*- coding: utf-8 -*-
"""锁定 B+C：VM 对列表推导改为显式报错（不再静默返回空列表），
且覆盖矩阵不再把它假报为 `emits`。

背景（定性实测坐实的无声缺陷）：
  parser 接受 `[expr for x in iter ...]` 并产出 ``ast.ListComp``，但
  ``src/mbc/compiler.py`` 的 ListComp 分支先 `code.append((OP.BUILD_LIST, 0))`
  再 `pass` —— 于是 VM 把任意列表推导静默编译成空列表 `[]`，无任何报错。
  这违背「缺口必须显式失败、绝不返回假成功」的内核红线。

B：ListComp 分支改为 ``raise``「不支持列表推导」。
C：``scripts/ast_vm_matrix.py`` 精准豁免该「识别但故意报错」节点，
   覆盖矩阵不再标 `emits`（降为 `missing`，used_in=0 不构成阻塞缺口）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import features  # noqa: E402
from src.kernel import exec_api  # noqa: E402


def _run_vm(src: str):
    features.set_feature("SCOPED_BLOCKS", True)
    outs, err = exec_api.run_checked(src, mode="vm")
    features.clear_feature()
    return outs, err


# 三种规范写法（parser 实际接受的语法：基本 / 带 if 过滤 / 内联）
_CASES = {
    "基本": """
nums = [1, 2, 3, 4]
squares = [x * x for x in nums]
[ squares ]
""",
    "过滤": """
nums = [1, 2, 3, 4]
big = [x for x in nums if x > 2]
[ big ]
""",
    "内联": """
[ [i + i for i in [1, 2, 3]] ]
""",
}


@pytest.mark.parametrize("label", list(_CASES))
def test_listcomp_vm_raises_not_silent_empty(label):
    """核心锁：列表推导不得再静默返回空列表，必须显式报错。"""
    outs, err = _run_vm(_CASES[label])
    # 修复前此处会得到 (…,[[]]) 且 err=None —— 那正是被禁止的假成功
    assert err is not None, f"{label}：VM 对列表推导静默通过（应报错）"
    assert "列表推导" in str(err), f"{label}：错误文案未点明列表推导不支持：{err}"
    # 也不该悄悄产出内容
    assert outs == [], f"{label}：报错前不应已产出任何输出：{outs}"


def test_listcomp_run_propagates():
    """非 checked 门面 `run()` 必须把该编译期不支持异常向上抛。"""
    features.set_feature("SCOPED_BLOCKS", True)
    with pytest.raises(Exception) as ei:
        exec_api.run("[ [x for x in [1, 2, 3]] ]", mode="vm")
    features.clear_feature()
    assert "列表推导" in str(ei.value)


def test_matrix_listcomp_not_emits():
    """C：覆盖矩阵不得再把 ListComp 假报为 emits（降为 missing）。"""
    from scripts import ast_vm_matrix as matrix

    built = matrix.build_matrix()
    rows = {r["node"]: r for r in built["rows"]}
    assert "ListComp" in rows
    assert rows["ListComp"]["vm"] != "emits", (
        "ListComp 仍被标为 emits（覆盖假阳性未消除）")
    assert rows["ListComp"]["vm"] == "missing"
    assert rows["ListComp"]["used_in"] == 0, "语料不应使用列表推导，否则将成为阻塞缺口"


def test_matrix_structdef_still_emits():
    """C 的爆炸半径护栏：定点豁免只针对 ListComp，绝不连带降级 StructDef。

    StructDef 声明位分支体是 `pass`（构造子在别处产 dict），与 ListComp 同属
    「isinstance 分支存在但体内不产码」；若用通用启发式会把它误降为 missing，
    而其 used_in=3 会凭空造出阻塞缺口。此锁确保它仍为 emits。
    """
    from scripts import ast_vm_matrix as matrix

    built = matrix.build_matrix()
    rows = {r["node"]: r for r in built["rows"]}
    assert rows["StructDef"]["vm"] == "emits", (
        "StructDef 被误降级；C 的豁免必须精准只含 ListComp")
