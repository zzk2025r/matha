# -*- coding: utf-8 -*-
"""A4：`return [x]` 语句位单元素列表被误当「打印括号」的回归锁。

历史缺口（docs/ast_vm_gap.md 第九节）：代码块内 `return [x]` 的操作数走
语句位解析，`[x]` 被判为输出命令 → 编译成 ReturnStmt(Output(x))，既打印又
返回裸值，使单元素列表无法作为返回值。

修复口径：`return` 紧邻的操作数是**表达式**，表达式位的 `[x]` 应为列表字面量
（与箭头 lambda 体 `=> [x]`、三元分支 `? [x] :` 同口径）。本测试锁定 return
后的单/多元素列表返回正确，且**不破坏**裸块尾 `[x]` 的输出命令约定。
"""
from __future__ import annotations

import src.ast_nodes as ast
from src.kernel import exec_api
from src import features
from src.parser import parse


def _outputs(src: str) -> list:
    features.clear_feature()
    features.set_feature("SCOPED_BLOCKS", True)
    outs, err = exec_api.run_checked(src, mode="vm")
    features.clear_feature()
    assert err is None, f"VM 运行报错：{err}"
    return list(outs)


def _single_el_list(src: str):
    """取 func 块体里 `return [...]` 的返回值表达式节点。"""
    tree = parse(src)
    func = next(d for d in tree.decls if isinstance(d, ast.FuncDef))
    block = func.body.body if isinstance(func.body, ast.Lambda) else func.body
    # 定位 CodeBlock 内的 ReturnStmt
    def find_ret(node):
        if isinstance(node, ast.ReturnStmt):
            return node
        for f in getattr(node, '__dataclass_fields__', {}) or {}:
            pass
        return None
    rets = [s for s in block.stmts if isinstance(s, ast.ReturnStmt)] if hasattr(block, 'stmts') else []
    return rets[0] if rets else None


def test_return_single_element_is_list_not_output():
    src = "func 单(x: Int) -> List = (x) => {\n  return [x]\n}\n"
    ret = _single_el_list(src)
    assert ret is not None, "未解析出 ReturnStmt"
    assert isinstance(ret.value, ast.ListLiteral), \
        f"return 后 [x] 应为 ListLiteral，实得 {type(ret.value).__name__}"
    assert len(ret.value.elements) == 1


def test_return_single_element_runtime():
    # 单元素列表返回：只应产生一次输出（外层打印返回值 [7]），不再有内层打印 7
    assert _outputs(
        "func 单(x: Int) -> List = (x) => {\n  return [x]\n}\n[单(7)]"
    ) == [[7]]


def test_return_multi_element_list_runtime():
    assert _outputs(
        "func 对(a: Int, b: Int) -> List = (a, b) => {\n  return [a, b]\n}\n[对(7, 8)]"
    ) == [[7, 8]]


def test_return_empty_list_runtime():
    assert _outputs(
        "func 空() -> List = () => {\n  return []\n}\n[空()]"
    ) == [[]]


def test_bare_block_tail_still_output_not_broken():
    # 裸块尾 [x]（无 return）仍是输出命令约定，不得被本次改动破坏
    outs = _outputs(
        "func 印(x: Int) -> Any = (x) => {\n  [x]\n}\n印(9)"
    )
    # 块内 [x] 打印 9；返回裸 9（无显式 return）→ 外层无再打印，仅一次输出
    assert outs == [9], f"裸块尾输出约定被破坏，实得 {outs}"
