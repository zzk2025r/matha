# -*- coding: utf-8 -*-
"""AST × VM 覆盖矩阵守门测试 —— 阶段 2 交付件，删除「转译 exec」路径的前置闸门。

计划把这份矩阵列为「最大烂尾风险」的对策：不先证明 VM 覆盖了 parser 能产出的
全部 AST 节点，就不许删 `convert(...,"matha","python") + exec()` 路径。因此这里
断言的是**覆盖面本身**，而不是某个具体语法能跑：

  1. 归档快照（`docs/ast_vm_gap.md` / `.json`）与当前代码一致 —— 文档不许过期。
  2. 阻塞缺口（编译器不认识 ∧ 语料里真出现）为 0，且相对快照只减不增。
  3. 指令码面 VM ↔ native 双向一致 —— VM 发的每个 OP 机器码后端都得发射，
     否则「vm ↔ native 逐位对拍」这句话是空的。
  4. 自举报告点名的历史缺口（`暂不支持求值: GlobalIdStmt`）已闭合。
  5. golden 用例全部有 vm 主链基线，且 vm ↔ interp 逐字节一致（复用门禁本体，
     不在测试里重写一套弱化版比较逻辑）。

矩阵重建要遍历全部 `.matha` 语料，故整体只算一次（模块级 fixture）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import ast_vm_matrix as matrix  # noqa: E402

JSON_PATH = ROOT / "docs" / "ast_vm_gap.json"
MD_PATH = ROOT / "docs" / "ast_vm_gap.md"
GOLDEN_DIR = ROOT / "golden_tests"


@pytest.fixture(scope="module")
def built() -> dict:
    """当场重算矩阵（不读快照），供各断言复用。"""
    return matrix.build_matrix()


# ============================================================
# 1. 快照不失效
# ============================================================

def test_snapshot_files_exist():
    assert JSON_PATH.exists(), f"缺少矩阵快照 {JSON_PATH}，先跑 --write"
    assert MD_PATH.exists(), f"缺少矩阵文档 {MD_PATH}，先跑 --write"


def test_snapshot_matches_current_code(built):
    """归档 JSON 必须等于当前代码重算结果（除时间戳）。

    不一致说明矩阵变了却没更新文档 —— 一份过期的覆盖矩阵比没有更危险，
    因为它会被当成「已覆盖」的证据。"""
    archived = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert matrix._strip(archived) == matrix._strip(built), (
        "docs/ast_vm_gap.json 已与代码脱节，请运行："
        "python scripts/ast_vm_matrix.py --write")


def test_markdown_matches_snapshot(built):
    archived = MD_PATH.read_text(encoding="utf-8")
    assert archived == matrix.render_markdown(built), (
        "docs/ast_vm_gap.md 与矩阵不同步，请运行："
        "python scripts/ast_vm_matrix.py --write")


# ============================================================
# 2. 阻塞缺口：为 0 且只减不增
# ============================================================

def test_no_blocking_ast_gap(built):
    blocking = [r["node"] for r in built["rows"]
                if r["vm"] == "missing" and r["used_in"]]
    assert not blocking, (
        f"parser 会产出、语料里在用、但 VM 编译期不认识的节点：{blocking}；"
        f"补齐前不得移除任何 exec 兜底路径")


def test_every_ast_node_is_classified(built):
    """每个 AST 节点都必须有归类，不允许 `unknown` 混进统计。"""
    bad = [r["node"] for r in built["rows"] if r["vm"] not in ("emits", "noop", "missing")]
    assert not bad, f"矩阵存在未归类节点：{bad}"
    assert built["totals"]["emits"] + built["totals"]["noop"] + built["totals"]["missing"] \
        == built["totals"]["nodes"] == len(built["rows"])


def test_gap_count_does_not_grow_vs_snapshot(built):
    """棘轮：阻塞缺口集合只允许缩小。"""
    archived = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    old = {r["node"] for r in archived["rows"] if r["vm"] == "missing" and r["used_in"]}
    new = {r["node"] for r in built["rows"] if r["vm"] == "missing" and r["used_in"]}
    assert not new - old, f"新增阻塞缺口：{sorted(new - old)}"


def test_bootstrap_report_gap_closed(built):
    """自举报告曾报 `暂不支持求值: GlobalIdStmt`，此处锁定它已闭合。"""
    rows = {r["node"]: r for r in built["rows"]}
    assert "GlobalIdStmt" in rows, "GlobalIdStmt 已从 AST 节点表消失（若为重命名，请同步本测试）"
    assert rows["GlobalIdStmt"]["vm"] == "noop", (
        f"GlobalIdStmt 应降级为编译期空操作，实际 {rows['GlobalIdStmt']['vm']!r}")


# ============================================================
# 3. 指令码面 VM ↔ native
# ============================================================

def test_opcode_surface_parity(built):
    """VM 发射的每个 OP，native 后端都必须实现（否则 vm↔native 对拍不可信）。"""
    gaps = [r["opcode"] for r in built["opcodes"] if r["vm"] == "yes" and r["native"] != "yes"]
    assert not gaps, f"native 后端缺指令码：{gaps}"
    assert built["totals"]["opcode_native_gap"] == 0
    assert built["totals"]["opcode_vm"] == built["totals"]["opcode_native"] \
        == built["totals"]["opcodes"]


def test_opcode_surface_not_empty(built):
    """码面表本身要有内容 —— 空表会让上一条断言变成假的通过。"""
    assert built["totals"]["opcodes"] >= 30, f"指令码面异常小：{built['totals']}"


# ============================================================
# 4. golden 主链基线（复用门禁本体，不另写比较逻辑）
# ============================================================

def test_every_golden_case_has_vm_baseline():
    """每个用例都必须有 vm 主链基线，否则「逐字节锁定」漏了该用例。"""
    cases = sorted(p.stem for p in (GOLDEN_DIR / "cases").glob("*.matha"))
    assert cases, "golden_tests/cases 下无用例"
    missing = [s for s in cases if not (GOLDEN_DIR / "vm" / f"{s}.out").exists()]
    assert not missing, f"缺少 vm 主链基线：{missing}（跑 run_golden_tests.py --update）"


def test_golden_gate_passes(capsys):
    """vm 主链 ↔ interp 对照逐字节一致（计划验收标准 4 的第三项）。"""
    sys.path.insert(0, str(GOLDEN_DIR))
    import run_golden_tests as gt  # noqa: E402

    code = gt.main([])
    out = capsys.readouterr().out
    assert code == 0, f"golden 门禁未通过（退出码 {code}）：\n{out}"
    assert "0 失败" in out, f"门禁报告未声明零失败：\n{out}"
