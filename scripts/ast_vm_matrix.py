# -*- coding: utf-8 -*-
"""生成 AST × VM 覆盖矩阵 ``docs/ast_vm_gap.md``（重构阶段 2 第 4 项）。

为什么必须先有这张表
--------------------
主执行链归一到 mbc 的前提是：**VM 能编译旧程序实际用到的每一个 AST 构造**。
不先把缺口列清楚就删转译执行路径，会让大量 `.matha` 当场不可运行。

本脚本做三件事：

1. 枚举 `src/ast_nodes.py` 里的全部 AST 节点（节点宇宙）；
2. 用真实程序统计「哪些节点真的被用到」——解析 `matha/`、`examples/`、
   `golden_tests/`、`tests/` 下所有 `.matha`，收集出现过的节点类型；
3. 静态判定各后端的支持面：
     - `src/mbc/compiler.py` 的 isinstance 分派 + `_NOOP_STMTS` / `_STMT_NODES`
       + `src/ast_ext.py` 注册的扩展规则  →  VM 支持
     - `src/mbc/native.py` 的 isinstance 分派  →  机器码支持（对拍前置条件）
     - `src/interp.py` 的 isinstance 分派  →  遗留诊断后端支持

「真实用到 ∧ VM 不支持」= 必须补齐的缺口；其余为低优先。支持面判定是静态的，
只作为**排序与追踪**依据，逐项落地仍以 golden 对拍为准。

用法：
    python scripts/ast_vm_matrix.py                # 打印统计
    python scripts/ast_vm_matrix.py --write        # 写 docs/ast_vm_gap.md + .json
    python scripts/ast_vm_matrix.py --check        # 与已归档 JSON 比对（缺口不得增加）
"""
from __future__ import annotations

import argparse
import ast as _ast
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MD_PATH = ROOT / "docs" / "ast_vm_gap.md"
JSON_PATH = ROOT / "docs" / "ast_vm_gap.json"

#: 用于统计「真实用到」的 .matha 语料目录
CORPUS_DIRS: tuple[str, ...] = ("matha", "examples", "golden_tests", "tests", "stdlib")

NODES_FILE = "src/ast_nodes.py"
COMPILER_FILE = "src/mbc/compiler.py"
NATIVE_FILE = "src/mbc/native.py"
INTERP_FILE = "src/interp.py"
AST_EXT_FILE = "src/ast_ext.py"


# ============================================================
# 一、节点宇宙
# ============================================================

def all_node_names() -> list[str]:
    """src/ast_nodes.py 中所有 @dataclass 顶层类名。"""
    tree = _ast.parse((ROOT / NODES_FILE).read_text(encoding="utf-8"),
                      filename=NODES_FILE)
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, _ast.ClassDef) and any(
                isinstance(d, _ast.Name) and d.id == "dataclass" for d in node.decorator_list):
            out.append(node.name)
    return sorted(out)


# ============================================================
# 二、后端支持面（静态）
# ============================================================

def _ast_refs(node: _ast.AST) -> set[str]:
    """子树里所有 `ast.XXX` 属性访问的类名。"""
    return {sub.attr for sub in _ast.walk(node)
            if isinstance(sub, _ast.Attribute)
            and isinstance(sub.value, _ast.Name) and sub.value.id == "ast"
            and sub.attr[:1].isupper()}


def _handled_nodes(rel: str) -> tuple[set[str], set[str]]:
    """精确判定一个文件「处理了哪些 AST 节点」，返回 (分派集, 显式无码集)。

    只信两处：
      1. `isinstance(x, ast.Foo)` / `isinstance(x, (ast.Foo, ast.Bar))` 的**类型参数**；
      2. 全大写常量赋值（分派表、节点清单）的**右值**。
    函数体里 `ast.Foo(...)` 这类**构造子节点**不算处理 —— 否则 `_emit_iteration`
    把 ForStmt 重新组装一下就会被误认为「VM 支持 ForStmt」。

    只有名字为 `_NOOP_STMTS` 的表才算「有意无码」；其余上表（如 `_STMT_NODES`）
    只是分类清单，其中的节点仍会发射代码，归为已处理。
    """
    path = ROOT / rel
    if not path.exists():
        return set(), set()
    tree = _ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    dispatched: set[str] = set()
    tables: set[str] = set()
    noop: set[str] = set()
    for node in _ast.walk(tree):
        if (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name)
                and node.func.id in ("isinstance", "issubclass")
                and len(node.args) >= 2):
            dispatched |= _ast_refs(node.args[1])
        elif isinstance(node, _ast.Compare):       # type(x) is ast.Foo
            for comp in node.comparators:
                dispatched |= _ast_refs(comp)
        elif isinstance(node, _ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], _ast.Name) \
                and node.targets[0].id.isupper():
            refs = _ast_refs(node.value)
            tables |= refs
            if node.targets[0].id == "_NOOP_STMTS":
                noop = refs
    return dispatched | tables, noop


def _op_mentions(rel: str, alias: str = "OP") -> set[str]:
    """文件里出现的 `OP.XXX` 指令码名。"""
    path = ROOT / rel
    if not path.exists():
        return set()
    tree = _ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    return {sub.attr for sub in _ast.walk(tree)
            if isinstance(sub, _ast.Attribute)
            and isinstance(sub.value, _ast.Name) and sub.value.id == alias
            and sub.attr.isupper()}


def opcode_surface() -> tuple[list[str], set[str], set[str]]:
    """(完整指令码清单, VM 已分派, native 已发射)。

    native 不是从 AST 而是从字节码发射机器码，所以 VM↔native 的平价面就是指令码集。
    """
    from src.mbc import opcodes as OP
    names = [n for n in dir(OP) if n.isupper() and isinstance(getattr(OP, n), (int, str))]
    vm = _op_mentions("src/mbc/vm.py")
    native = _op_mentions(NATIVE_FILE) | _op_mentions(NATIVE_FILE, "OP")
    return sorted(names), vm & set(names), native & set(names)


#: 根容器节点：不由 isinstance 分派，而是被 `compile_program(program)` 直接消费。
ROOT_NODES: frozenset[str] = frozenset({"Program"})


def compiler_supported(nodes: set[str]) -> tuple[set[str], set[str]]:
    """返回 (会发射字节码的节点, 编译期无码但被显式承认的节点)。

    `_NOOP_STMTS` 里的节点是「有意不产码」（标注/文件标记/类型节点等），与
    「不认识而报错」完全不同，因此分开统计。
    """
    dispatched, noop = _handled_nodes(COMPILER_FILE)
    ext_dispatch, _ext_tables = _handled_nodes(AST_EXT_FILE)
    mentioned = (dispatched | ext_dispatch) | ROOT_NODES
    emits = (nodes & mentioned) - noop
    return emits, nodes & noop


# ============================================================
# 三、真实语料
# ============================================================

def _walk_matha(node):
    """遍历 Matha AST（它不是 Python ast 节点，没有 `_fields`）。

    兼容 dataclass / list / tuple / dict / set，足以覆盖 `src/ast_nodes.py` 的字段形状。
    """
    import dataclasses as _dc

    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        if _dc.is_dataclass(cur) and not isinstance(cur, type):
            for f in _dc.fields(cur):
                stack.append(getattr(cur, f.name, None))
        elif isinstance(cur, (list, tuple, set)):
            stack.extend(cur)
        elif isinstance(cur, dict):
            stack.extend(cur.keys())
            stack.extend(cur.values())


def corpus_usage() -> tuple[dict[str, int], list[tuple[str, str]], int]:
    """解析全部 .matha 语料，返回 (节点名 -> 出现文件数, 解析失败清单, 成功文件数)。"""
    from src.parser import parse

    usage: dict[str, int] = {}
    failures: list[tuple[str, str]] = []
    n_files = 0
    for d in CORPUS_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.matha")):
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = parse(path.read_text(encoding="utf-8"))
            except Exception as e:
                failures.append((rel, f"{type(e).__name__}: {e}"))
                continue
            n_files += 1
            seen: set[str] = set()
            for node in _walk_matha(tree):
                name = type(node).__name__
                if name in NODE_SET and name not in seen:
                    seen.add(name)
                    usage[name] = usage.get(name, 0) + 1
    return usage, failures, n_files


NODE_SET: set[str] = set()


# ============================================================
# 四、矩阵
# ============================================================

def build_matrix() -> dict:
    global NODE_SET
    nodes = all_node_names()
    NODE_SET = set(nodes)
    vm_ok, vm_noop = compiler_supported(NODE_SET)
    interp_handled, _interp_tables = _handled_nodes(INTERP_FILE)
    ops, vm_ops, native_ops = opcode_surface()
    usage, failures, n_files = corpus_usage()

    rows: list[dict] = []
    for name in nodes:
        state = ("emits" if name in vm_ok
                 else "noop" if name in vm_noop else "missing")
        rows.append({
            "node": name,
            "vm": state,
            "interp": "yes" if name in interp_handled else "no",
            "used_in": int(usage.get(name, 0)),
        })
    rows.sort(key=lambda r: (r["vm"] != "missing", -r["used_in"], r["node"]))
    op_rows = [{
        "opcode": o,
        "vm": "yes" if o in vm_ops else "no",
        "native": "yes" if o in native_ops else "no",
    } for o in ops]
    return {
        "_comment": (
            "AST × VM 覆盖矩阵快照，由 scripts/ast_vm_matrix.py --write 生成，请勿手改。"
            "vm ∈ emits（编译期发射字节码）/ noop（有意不产码：标注、类型、文件标记）/ "
            "missing（编译器不认识，运行到即报「暂不支持的节点」）。used_in = 语料里出现"
            "该节点的 .matha 文件数。缺口判定：vm=missing 且 used_in>0。"
        ),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/ast_vm_matrix.py",
        "corpus_dirs": list(CORPUS_DIRS),
        "unparseable": [{"file": f, "error": e} for f, e in failures],
        "totals": {
            "nodes": len(rows),
            "emits": sum(1 for r in rows if r["vm"] == "emits"),
            "noop": sum(1 for r in rows if r["vm"] == "noop"),
            "missing": sum(1 for r in rows if r["vm"] == "missing"),
            "blocking": sum(1 for r in rows if r["vm"] == "missing" and r["used_in"]),
            "corpus_files": n_files,
            "opcodes": len(op_rows),
            "opcode_vm": sum(1 for r in op_rows if r["vm"] == "yes"),
            "opcode_native": sum(1 for r in op_rows if r["native"] == "yes"),
            "opcode_native_gap": sum(1 for r in op_rows
                                     if r["vm"] == "yes" and r["native"] == "no"),
        },
        "rows": rows,
        "opcodes": op_rows,
    }


def render_markdown(data: dict) -> str:
    t = data["totals"]
    lines: list[str] = []
    lines.append("# AST × VM 覆盖矩阵")
    lines.append("")
    lines.append("> 本文件由 `python scripts/ast_vm_matrix.py --write` 生成，请勿手改。")
    lines.append("> 机器可读快照见 `docs/ast_vm_gap.json`，守门测试见 `tests/test_ast_vm_gap.py`。")
    lines.append("")
    lines.append("## 一、为什么需要它")
    lines.append("")
    lines.append("主执行链归一到 mbc（删掉 `convert(...)+exec()` 转译路径）之前，必须先证明")
    lines.append("VM 覆盖旧程序真实用到的全部 AST 构造。这张表就是那份证据：")
    lines.append("")
    lines.append("- **节点宇宙**：`src/ast_nodes.py` 的全部 `@dataclass` 节点。")
    lines.append(f"- **语料**：{'、'.join('`' + d + '/**/*.matha`' for d in data['corpus_dirs'])}。")
    lines.append("- **vm 列**：`src/mbc/compiler.py` 的静态分派判定"
                  "（`emits` 发射字节码 / `noop` 有意不产码 / `missing` 不认识）。")
    lines.append("- **interp 列**：遗留诊断后端是否处理该节点（用于判断补齐前的回退能力）。")
    lines.append("")
    lines.append("VM↔native 的平价面不是 AST 而是**指令码**：`native.py` 从已编译的 mbc 模块")
    lines.append("发射机器码，因此另有一张指令码表（见第五节）。")
    lines.append("")
    lines.append("## 二、统计")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|---|---|")
    lines.append(f"| AST 节点总数 | {t['nodes']} |")
    lines.append(f"| VM 发射字节码 | {t['emits']} |")
    lines.append(f"| VM 有意无码 | {t['noop']} |")
    lines.append(f"| VM 不认识 | {t['missing']} |")
    lines.append(f"| **阻塞缺口（不认识 ∧ 语料用到）** | **{t['blocking']}** |")
    lines.append(f"| 指令码总数 / VM 已分派 / native 已发射 "
                  f"| {t['opcodes']} / {t['opcode_vm']} / {t['opcode_native']} |")
    lines.append(f"| **native 对拍风隙（VM 有、native 无）** | **{t['opcode_native_gap']}** |")
    lines.append(f"| 语料文件（解析成功） | {t['corpus_files']} |")
    lines.append(f"| 无法解析的语料文件 | {len(data['unparseable'])} |")
    lines.append("")
    lines.append("## 三、阻塞缺口（必须先补）")
    lines.append("")
    blocking = [r for r in data["rows"] if r["vm"] == "missing" and r["used_in"]]
    if not blocking:
        lines.append("无。VM 覆盖了语料用到的全部 AST 构造，可以移除转译执行路径。")
    else:
        lines.append("| 节点 | 语料文件数 | interp |")
        lines.append("|---|---|---|")
        for r in blocking:
            lines.append(f"| `{r['node']}` | {r['used_in']} | {r['interp']} |")
    lines.append("")
    lines.append("## 四、未被语料使用的缺口（低优先）")
    lines.append("")
    dormant = [r for r in data["rows"] if r["vm"] == "missing" and not r["used_in"]]
    if not dormant:
        lines.append("无。")
    else:
        lines.append("、".join(f"`{r['node']}`" for r in dormant))
    lines.append("")
    lines.append("## 五、全表")
    lines.append("")
    lines.append("| 节点 | VM | interp | 语料文件数 |")
    lines.append("|---|---|---|---|")
    for r in sorted(data["rows"], key=lambda x: x["node"]):
        lines.append(f"| `{r['node']}` | {r['vm']} | {r['interp']} | {r['used_in']} |")
    lines.append("")
    lines.append("## 六、指令码 × VM / native")
    lines.append("")
    ot = data["totals"]
    lines.append(f"指令码共 {ot['opcodes']} 条：VM 已分派 {ot['opcode_vm']}，"
                  f"native 已发射 {ot['opcode_native']}，"
                  f"**VM 有而 native 无 = {ot['opcode_native_gap']} 条**（对拍风隙）。")
    lines.append("")
    gap_ops = [r for r in data["opcodes"] if r["vm"] == "yes" and r["native"] == "no"]
    both_missing = [r for r in data["opcodes"] if r["vm"] == "no"]
    if gap_ops:
        lines.append("native 未实现（不能参与 VM↔native 对拍，必须显式标记）：")
        lines.append("")
        lines.append("、".join(f"`{r['opcode']}`" for r in gap_ops))
        lines.append("")
    if both_missing:
        lines.append("已定义但两端均未分派：")
        lines.append("")
        lines.append("、".join(f"`{r['opcode']}`" for r in both_missing))
        lines.append("")
    if not both_missing and not gap_ops:
        lines.append("无：两端指令码表面一致。")
        lines.append("")
    lines.append("## 七、全量指令码表")
    lines.append("")
    lines.append("| 指令码 | VM | native |")
    lines.append("|---|---|---|")
    for r in data["opcodes"]:
        lines.append(f"| `{r['opcode']}` | {r['vm']} | {r['native']} |")
    lines.append("")
    if data["unparseable"]:
        lines.append("## 八、无法解析的语料")
        lines.append("")
        lines.append("这些 `.matha` 连 parser 都过不了，属语法层缺口（与 VM 无关）：")
        lines.append("")
        lines.append("| 文件 | 错误 |")
        lines.append("|---|---|")
        for u in data["unparseable"]:
            err = u["error"].replace("|", "\\|")[:160]
            lines.append(f"| `{u['file']}` | {err} |")
        lines.append("")
    lines.append("## 九、写 `.matha` 标准库时踩到的语言口径")
    lines.append("")
    lines.append("本节是「VM 能发射」与「人能写对」之间的缝：阶段 4 把符号微积分")
    lines.append("重写成 `matha/library/*.matha` 时实测得到的词法/语法口径。它们不是")
    lines.append("缺陷（都有对应回归用例），但写库时违反就会拿到错的输出：")
    lines.append("")
    lines.append("| 口径 | 实例 | 库内做法 |")
    lines.append("|---|---|---|")
    lines.append("| **裸 `[x]` 出现在语句位仍当作「打印括号」**（输出单元）；但 `return` "
                 "紧邻操作数位的 `[x]` 已归一为**列表字面量**（不再既打印又返裸值）| "
                 "`func 包(x) -> List = (x) => { return [x] }` | `return [x]`→`[x]`、"
                 "`return []`→`[]`、`return [a, b]` 均为正常列表（黄金用例 `34_return_"
                 "list_literal` 三端锁定）；裸块尾 `[x]` 仍单次输出 |")
    lines.append("| `func` 缺 `-> 类型` 直接 ParseError | `func f(x) = …` | "
                 "一律写 `func f(x) -> Any = …` |")
    lines.append("| `if` 不能当表达式用 | `let y = if c {1} else {2}` | 先算再绑定 |")
    lines.append("| **列表推导 `[expr for x in iter if c ...]` VM 已编译**（旧版曾静默编译成空列表 `[]`）| "
                 "`[x * x for x in nums]` | 下沉为与 `for` 同构的下标循环 + `append` 累加（零新 opcode/新内建）；"
                 "多 `if` 取 AND；**仅单个 `for` 生成子句**（parser 语法即如此，非 Python 多 for 嵌套）；三端逐字节对齐 "
                 "interp（`tests/test_listcomp_vm.py` + 黄金用例 `35_list_comp` 锁定） |")
    lines.append("| `#：{…}` 记录面 mbc 不发射 | — | 标准库不用该语法 |")
    lines.append("| 无 `sorted/map/filter/join/gcd/split` 等内建 | — | "
                 "手写升序插入排序 + 欧几里得 `gcd` |")
    lines.append("")
    lines.append("（历史上本表还列有「三元/or 里 `==` 误析」与「无科学计数法字面量」"
                 "两条：前者已于语句位归一为 `(a==b)?x:y`（黄金用例 `32_ternary_eq_"
                 "precedence` 三端锁定），后者 `1e-15` 早已被 lexer/parser 支持"
                 "（黄金用例 `33_sci_notation` 三端锁定），均已删除不复发。）")
    lines.append("")
    lines.append("前两条属语法层语义易错点，已在 `tests/test_matha_stdlib_symbolic.py` "
                 "与 `matha/library/` 的实际使用中验证；本表随 `--write` 重生。")
    lines.append("")
    return "\n".join(lines) + "\n"


def _strip(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k != "generated_at"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AST × VM 覆盖矩阵")
    ap.add_argument("--write", action="store_true", help="写 docs/ast_vm_gap.md + .json")
    ap.add_argument("--check", action="store_true",
                    help="与已归档快照比对：阻塞缺口不得增加（棘轮）")
    args = ap.parse_args(argv)

    data = build_matrix()
    t = data["totals"]
    print(f"节点 {t['nodes']} | VM 发射 {t['emits']} | 无码 {t['noop']} | "
          f"不认识 {t['missing']} | 阻塞缺口 {t['blocking']} | "
          f"指令码 {t['opcodes']}（VM {t['opcode_vm']} / native {t['opcode_native']}）| "
          f"语料解析失败 {len(data['unparseable'])}")

    if args.check:
        if not JSON_PATH.exists():
            print("ERROR: 缺少快照，先运行 --write", file=sys.stderr)
            return 2
        old = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        old_block = {r["node"] for r in old["rows"]
                     if r["vm"] == "missing" and r["used_in"]}
        new_block = {r["node"] for r in data["rows"]
                     if r["vm"] == "missing" and r["used_in"]}
        grown = new_block - old_block
        if grown:
            print(f"ERROR: 阻塞缺口新增 {len(grown)} 项：{sorted(grown)}", file=sys.stderr)
            return 1
        if _strip(old) != _strip(data):
            print("提示：矩阵内容有变化（新增覆盖或语料漂移），请 --write 更新快照")
        print("OK: 阻塞缺口未增加")
        return 0

    if args.write:
        MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        MD_PATH.write_text(render_markdown(data), encoding="utf-8")
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        print(f"已写入 {MD_PATH.relative_to(ROOT)} 与 {JSON_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
