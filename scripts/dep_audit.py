#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 内核依赖审计器 —— 阶段 0 交付件。

目的：把「内核零外部依赖」从口头承诺变成可机器判定的契约。

做法：用标准库 `ast` 静态解析核心主线（词法/语法/AST/编译器/VM/native）的
每一个源文件，抽出全部 import 边并分类：

  stdlib        —— Python 标准库（用 sys.stdlib_module_names 判定，自动跟随版本）
  third_party   —— sympy/numpy/scipy/... 等第三方包，内核一律禁止
  escape_hatch  —— 标准库里能「逃向外层世界」的模块（subprocess/threading/...），
                   它们虽属标准库，但会让内核依赖外部进程与线程调度，同样禁止
  internal      —— src.* 内部依赖，再细分为：
                     kernel     允许（核心主线自身）
                     plugin     禁止（领域/插件，必须走 plugin_api 按需加载）
                     legacy     禁止（树走式解释器等，已降级为诊断后端）

输出一份违规清单 + 依赖方向图，并可与基线文件比对（棘轮机制）：
只允许违规减少，新增违规立即失败。

用法：
    python scripts/dep_audit.py                 # 审计并打印报告
    python scripts/dep_audit.py --write-report  # 同时写 docs/DEP_BASELINE.md
    python scripts/dep_audit.py --write-baseline # 把当前违规写成棘轮基线
    python scripts/dep_audit.py --json           # 机器可读输出
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ============================================================
# 核心主线定义
# ============================================================

#: 核心主线文件（内核 import 白名单的作用域）。阶段 1 新增的 src/kernel/ 会
#: 由 KERNEL_GLOBS 自动纳入，无需手工维护列表。
KERNEL_FILES: tuple[str, ...] = (
    "src/tokens.py",
    "src/lexer.py",
    "src/ast_nodes.py",
    "src/ast_ext.py",
    "src/custom_ops.py",
    "src/features.py",
    "src/formula_schema.py",
    "src/kernel/math_builtin.py",
    "src/kernel/regex_builtin.py",
    "src/text_encoding.py",
    "src/parser.py",
    "src/mbc/__init__.py",
    "src/mbc/cli.py",
    "src/mbc/compiler.py",
    "src/mbc/native.py",
    "src/mbc/native_regex.py",
    "src/mbc/native_time.py",
    "src/mbc/opcodes.py",
    "src/mbc/serial.py",
    "src/mbc/vm.py",
)
KERNEL_GLOBS: tuple[str, ...] = ("src/kernel/**/*.py",)

#: 允许出现在内核里的 src.* 模块（核心主线自身的模块名）。
KERNEL_MODULES: set[str] = {
    "src", "src.tokens", "src.lexer", "src.ast_nodes", "src.ast_ext",
    "src.custom_ops", "src.features", "src.formula_schema", "src.kernel.math_builtin",
    "src.kernel.regex_builtin", "src.text_encoding", "src.parser",
    "src.mbc", "src.mbc.cli", "src.mbc.compiler", "src.mbc.native",
    "src.mbc.native_regex", "src.mbc.native_time",
    "src.mbc.opcodes", "src.mbc.serial", "src.mbc.vm",
}

#: 明确禁止的第三方包（分类用；未列出的非标准库包同样按 third_party 处理）。
THIRD_PARTY_KNOWN: frozenset[str] = frozenset({
    "sympy", "numpy", "scipy", "numba", "tree_sitter", "cffi", "llvmlite",
    "torch", "tensorflow", "pandas", "matplotlib", "requests", "flask",
    "fastapi", "uvicorn", "pydantic", "pyinstaller", "PyInstaller",
})

#: 标准库中「向外逃逸」的模块：属标准库但内核不得使用，因为它们引入外部进程、
#: 外部工具链、宿主解释器执行能力或不可控并发调度。
#:   exec/eval 走 builtins，由 tests/test_kernel_purity.py 单独扫描源码文本。
ESCAPE_HATCH: frozenset[str] = frozenset({
    "subprocess", "threading", "concurrent", "concurrent.futures",
    "multiprocessing", "asyncio", "socket", "urllib", "http", "ssl",
    "ctypes", "cgitb", "ftplib", "smtplib", "telnetlib", "xmlrpc",
})

#: 联邦契约层：内核与插件层之间唯一的合法桥。内核可以 import 它（它保证不
#: eager import 任何 src.domains.*，只读清单），但不得绕过它直接引用领域模块。
#: 且只有「宿主入口」文件允许引用契约（见 CONTRACT_IMPORTERS），解释器本体
# （parser / compiler / vm / native）连契约都不认识，插件对象一律由宿主注入。
CONTRACT_MODULES: set[str] = {"src.plugin_api"}
CONTRACT_IMPORTERS: set[str] = {"src/kernel/exec_api.py"}

#: src.* 中禁止被内核引用的前缀 → 归类标签。
PLUGIN_PREFIXES: tuple[str, ...] = (
    "src.domains", "src.plugins", "src.hardware", "src.intent",
    "src.optimization", "src.tools", "src.stdlib",
)
LEGACY_PREFIXES: tuple[str, ...] = (
    "src.interp", "src.vm", "src.m3v_vm", "src.interp_engine",
    "src.interp_stack", "src.interp_ic", "src.matha_bootstrap",
    "src.compiler", "src.hybrid_compiler", "src.bootstrap",
    "src.virtual_code", "src.matha_vm", "src.matha_runtime", "src.matha_engine",
    "src.matha_system", "src.unified", "src.repl", "src.symbolic",
    # src.deps / src.ffi / src.interop 已整件搬入 src/plugins/（工具链与外部
    # 能力探测不属遗留执行链，也不属内核），故不再列在这里。
    "src.formula_system",
)

#: 宿主逃逸调用：内核绝不借用宿主解释器执行代码（那是「转译执行」而非自举）。
HOST_EXEC_CALLS: frozenset[str] = frozenset({"exec", "eval", "__import__", "compile"})

# ============================================================
# 插件→内核方向的反向守卫（阶段 1 契约）
# ============================================================
#: 插件层（联邦支线）的作用域。
PLUGIN_GLOBS: tuple[str, ...] = ("src/domains/**/*.py", "src/plugins/**/*.py")

#: 核心主线对外只允许插件使用公开 API；引用这些模块的私有名字属越界。
CORE_MODULES: frozenset[str] = frozenset({
    "src.mbc.vm", "src.mbc.compiler", "src.mbc.native", "src.mbc.cli",
    "src.parser", "src.lexer", "src.ast_nodes", "src.interp",
})

#: 属性访问守卫：插件代码里出现 `vm._stack` / `interp._env` 这类越界读取。
CORE_LOCAL_NAMES: frozenset[str] = frozenset({
    "vm", "_vm", "interpreter", "interp", "engine", "compiler", "machine",
})

BASELINE_PATH = ROOT / "tests" / "kernel_purity_baseline.json"
REPORT_PATH = ROOT / "docs" / "DEP_BASELINE.md"


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Violation:
    """一条内核依赖违规。"""
    file: str          # 相对仓库根
    lineno: int
    imported: str      # 被导入的绝对模块名
    kind: str          # third_party | escape_hatch | plugin | legacy | host_exec
    nested: bool       # True = 位于函数体内（惰性 import）

    @property
    def key(self) -> str:
        """棘轮比对键：不含行号，避免无关的行号漂移造成假新增。"""
        return f"{self.file}|{self.kind}|{self.imported}"

    def as_baseline_entry(self) -> str:
        return f"{self.file}: {self.imported} ({self.kind})"


@dataclass
class Edge:
    """内核 → 被依赖模块 的一条 import 边（用于依赖方向图）。"""
    src_module: str
    dst_module: str
    lineno: int
    nested: bool


# ============================================================
# import 抽取
# ============================================================

def _collect_host_calls(tree: ast.Module) -> list[tuple[str, int]]:
    """抽取宿主逃逸调用：exec()/eval()/compile()/__import__()。

    方法定义（如 def eval(self, ...)）与属性调用（如 obj.eval()）不算 ——
    只有直接调用裸名字才是借宿主解释器执行代码。
    """
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in HOST_EXEC_CALLS:
                hits.append((node.func.id, node.lineno))
    return hits


def _abs_name(node: ast.ImportFrom, cur_module: str, is_pkg: bool) -> str:
    """把相对 import 解析为绝对模块名。"""
    if node.level == 0:
        return node.module or ""
    parts = cur_module.split(".")
    if not is_pkg:
        parts = parts[:-1]
    drop = node.level - 1
    if drop:
        parts = parts[:-drop] if drop < len(parts) else []
    base = ".".join(parts)
    return f"{base}.{node.module}" if node.module else base or "src"


def _collect_imports(tree: ast.Module, path: Path, cur_module: str) -> list[tuple[str, int, bool]]:
    """返回 (绝对模块名, 行号, 是否位于函数体内)。

    函数体内的 import 单独标注：内核允许它「惰性」，但不允许它指向
    领域/插件/遗留模块 —— 惰性只是延迟违规，不是消除违规。
    """
    is_pkg = path.name == "__init__.py"
    found: list[tuple[str, int, bool]] = []

    def walk(node: ast.AST, nested: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(child, True)
                continue
            if isinstance(child, ast.Import):
                for alias in child.names:
                    found.append((alias.name, child.lineno, nested))
            elif isinstance(child, ast.ImportFrom):
                name = _abs_name(child, cur_module, is_pkg)
                found.append((name, child.lineno, nested))
                # from src.domains.x import y 会连带触发 src.domains.x 的 import，
                # 其父包链同样要计入（src.domains 本身即插件目录）。
                if name.startswith("src."):
                    segs = name.split(".")
                    for i in range(2, len(segs)):
                        found.append((".".join(segs[:i]), child.lineno, nested))
            else:
                walk(child, nested)

    walk(tree, False)
    return found


def classify(imported: str) -> tuple[str, str]:
    """返回 (分类, 违规种类)。分类 ∈ stdlib/third_party/escape_hatch/internal。

    违规种类 "contract" 不算违规：它是内核→联邦契约的合法桥边，但会被单独记录，
    以便「只有宿主入口引用契约」这条不变量可被审计。
    """
    top = imported.split(".")[0]
    if top == "src":
        if imported in KERNEL_MODULES or imported.startswith("src.kernel"):
            return "internal", "ok"
        if imported in CONTRACT_MODULES:
            return "internal", "contract"
        for pre in PLUGIN_PREFIXES:
            if imported == pre or imported.startswith(pre + "."):
                return "internal", "plugin"
        for pre in LEGACY_PREFIXES:
            if imported == pre or imported.startswith(pre + "."):
                return "internal", "legacy"
        # 未归类但明确在 src.* 之外围层 —— 保守视为遗留，避免内核悄悄扩张。
        return "internal", "legacy"
    if top in THIRD_PARTY_KNOWN:
        return "third_party", "third_party"
    if imported in ESCAPE_HATCH or top in ESCAPE_HATCH:
        return "escape_hatch", "escape_hatch"
    if top in sys.stdlib_module_names:
        return "stdlib", "ok"
    # 非标准库、非 src.*、不在已知清单：按第三方处理（宁可误报也不漏报）。
    return "third_party", "third_party"


# ============================================================
# 审计
# ============================================================

def kernel_files() -> list[Path]:
    """展开核心主线文件清单（显式列表 + glob 增量纳入）。"""
    files = {ROOT / f for f in KERNEL_FILES}
    for pattern in KERNEL_GLOBS:
        files.update(ROOT.glob(pattern))
    return sorted(p for p in files if p.exists())


def audit() -> tuple[list[Violation], list[Edge], dict[str, list[str]]]:
    """审计核心主线，返回 (违规, 依赖边, 每个内核文件的 import 清单)。"""
    violations: list[Violation] = []
    edges: list[Edge] = []
    imports_by_file: dict[str, list[str]] = {}

    for path in kernel_files():
        rel = path.relative_to(ROOT).as_posix()
        mod = rel[:-3].replace("/", ".").replace(".__init__", "")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
        except SyntaxError as exc:  # pragma: no cover
            raise SystemExit(f"内核文件解析失败 {rel}: {exc}") from exc

        names: list[str] = []
        for imported, lineno, nested in _collect_imports(tree, path, mod):
            if not imported:
                continue
            names.append(imported)
            cat, kind = classify(imported)
            if kind == "contract" and rel not in CONTRACT_IMPORTERS:
                violations.append(Violation(rel, lineno, imported, "contract_escape", nested))
            elif kind not in ("ok", "contract"):
                violations.append(Violation(rel, lineno, imported, kind, nested))
            if imported.startswith("src."):
                edges.append(Edge(mod, imported, lineno, nested))
        for callee, lineno in _collect_host_calls(tree):
            violations.append(Violation(rel, lineno, f"{callee}()", "host_exec", False))
        imports_by_file[rel] = sorted(set(names))

    violations.sort(key=lambda v: (v.file, v.lineno))
    violations = _dedupe_parent_chains(violations)
    return violations, edges, imports_by_file


def _dedupe_parent_chains(violations: list[Violation]) -> list[Violation]:
    """去掉同一 import 语句重复计入的父包边。

    `from src.domains.time_module import x` 会同时产生 `src.domains.time_module`
    与父包 `src.domains` 两条记录。它们属同一违规，只保留最具体的一条，
    否则统计会夸大违规数量。
    """
    kept: list[Violation] = []
    for v in violations:
        covered = any(
            o.file == v.file and o.lineno == v.lineno and o.kind == v.kind
            and o.imported.startswith(v.imported + ".")
            for o in violations
        )
        if not covered:
            kept.append(v)
    return kept


@dataclass
class BoundaryViolation:
    """插件层越界访问核心私有成员的一条记录。"""
    file: str
    lineno: int
    target: str      # 被越界访问的核心模块或对象
    detail: str      # 私有名（import 的名字 或 属性名）
    kind: str        # private_import | private_attr

    @property
    def key(self) -> str:
        return f"{self.file}|{self.kind}|{self.target}|{self.detail}"

    def as_baseline_entry(self) -> str:
        return f"{self.file}: {self.target}.{self.detail} ({self.kind})"


def plugin_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in PLUGIN_GLOBS:
        files.update(ROOT.glob(pattern))
    return sorted(p for p in files if p.exists())


def audit_plugins() -> list[BoundaryViolation]:
    """插件→内核方向的静态守卫（零容许：基线应为空）。

    联邦架构的对角线约束：支线只能通过 src.plugin_api 登记的公开接口与内核交互，
    不得 import 内核私有名字，也不得读 vm/interp 等核心对象的 `_xxx` 私有成员
    （那是把解释器栈、全局表变成插件的隐式输入，一旦改动就难以察觉地坏掉）。
    """
    out: list[BoundaryViolation] = []
    for path in plugin_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith("manifest.json"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
        except SyntaxError:
            continue                      # 领域模块自有的语法问题不属本守卫范围
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in CORE_MODULES:
                for alias in node.names:
                    if alias.name.startswith("_"):
                        out.append(BoundaryViolation(
                            rel, node.lineno, node.module, alias.name, "private_import"))
            elif isinstance(node, ast.Attribute):
                if (isinstance(node.value, ast.Name)
                        and node.value.id in CORE_LOCAL_NAMES
                        and node.attr.startswith("_")
                        and not node.attr.startswith("__")):
                    out.append(BoundaryViolation(
                        rel, node.lineno, node.value.id, node.attr, "private_attr"))
    out.sort(key=lambda v: (v.file, v.lineno))
    return out


# ============================================================
# 棘轮基线
# ============================================================

def load_baseline() -> dict | None:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return None


def diff_baseline(violations: list[Violation], baseline: dict) -> tuple[list[Violation], list[str]]:
    """与基线比对：返回 (基线外的新增违规, 已修复但仍在基线里的条目)。"""
    allowed = set(baseline.get("keys", []))
    new = [v for v in violations if v.key not in allowed]
    gone = [k for k in baseline.get("entries", []) if k not in {v.as_baseline_entry() for v in violations}]
    return new, gone


def write_baseline(violations: list[Violation]) -> None:
    payload = {
        "_comment": (
            "内核依赖棘轮基线。只允许条目减少，不允许增加。"
            "新增条目 = tests/test_kernel_purity.py 失败。"
            "重建：python scripts/dep_audit.py --write-baseline"
        ),
        "keys": sorted({v.key for v in violations}),
        "entries": sorted({v.as_baseline_entry() for v in violations}),
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ============================================================
# 报告
# ============================================================

KIND_LABEL = {
    "third_party": "第三方重型库（必须移除或降级为可选加速插件）",
    "escape_hatch": "标准库逃逸模块（外部进程 / 宿主执行 / 不可控并发）",
    "plugin": "领域/插件层（必须改走 plugin_api 按需加载）",
    "legacy": "遗留后端层（已降级，不得进入内核主链）",
    "host_exec": "宿主解释器逃逸（exec/eval/compile/__import__）",
    "contract_escape": "绕过宿主入口引用联邦契约（解释器本体不得认识插件层）",
}


def render_report(violations: list[Violation], edges: list[Edge],
                  imports_by_file: dict[str, list[str]],
                  boundary: list[BoundaryViolation] | None = None) -> str:
    lines: list[str] = []
    lines.append("# Matha 内核依赖基线")
    lines.append("")
    lines.append("> 本文件由 `python scripts/dep_audit.py --write-report` 生成，请勿手改。")
    lines.append("> 棘轮基线见 `tests/kernel_purity_baseline.json`，守门测试见 `tests/test_kernel_purity.py`。")
    lines.append("")
    lines.append("## 一、契约")
    lines.append("")
    lines.append("- **唯一执行主线**：`lexer -> parser -> ast_nodes -> mbc.compiler -> mbc.vm`（`mbc.native` 为可选机器码发射）。")
    lines.append("- **内核文件清单**：`KERNEL_FILES` + `src/kernel/**`（见 `scripts/dep_audit.py`）。")
    lines.append("- **允许**：Python 标准库中不向外逃逸的模块。")
    lines.append("- **禁止**：第三方包；`subprocess/threading/concurrent/multiprocessing/asyncio/socket/ctypes` 等逃逸模块；"
                  "`src.domains.*`（插件层）、`src.interp` 与 `src.compiler.*` 等遗留层。")
    lines.append("- **不视为违规的例外**：`mbc/native.py` 生成的 exe 调用 CRT（`_ecvt/rint/pow/fopen`）属 OS ABI 依赖，"
                  "与 Python 依赖无关，记录于此但不进入统计。")
    lines.append("")
    lines.append("## 二、审计范围")
    lines.append("")
    lines.append(f"- 内核文件数：{len(imports_by_file)}")
    lines.append(f"- 内核 import 边数：{len(edges)}")
    lines.append(f"- 违规条目：**{len(violations)}**")
    lines.append("")
    lines.append("## 三、违规清单（按类）")
    lines.append("")
    if not violations:
        lines.append("无。内核已达成零外部依赖。")
    else:
        by_kind: dict[str, list[Violation]] = {}
        for v in violations:
            by_kind.setdefault(v.kind, []).append(v)
        for kind in ("third_party", "escape_hatch", "plugin", "legacy",
                     "contract_escape", "host_exec"):
            vs = by_kind.get(kind)
            if not vs:
                continue
            lines.append(f"### {kind} — {KIND_LABEL[kind]}（{len(vs)} 条）")
            lines.append("")
            lines.append("| 文件 | 行 | 依赖 | 位置 |")
            lines.append("|---|---|---|---|")
            for v in vs:
                where = "函数体内(惰性)" if v.nested else "模块顶层"
                lines.append(f"| `{v.file}` | {v.lineno} | `{v.imported}` | {where} |")
            lines.append("")
    lines.append("## 四、内核 → 外部层 依赖方向")
    lines.append("")
    outward: dict[str, set[str]] = {}
    for e in edges:
        cat, kind = classify(e.dst_module)
        if kind in ("plugin", "legacy", "third_party", "escape_hatch", "contract"):
            outward.setdefault(e.src_module, set()).add(f"{e.dst_module} [{kind}]")
    if not outward:
        lines.append("无外逸边：核心主线不依赖任何插件层或遗留层。")
    else:
        lines.append("| 内核模块 | 外逸依赖 |")
        lines.append("|---|---|")
        for mod in sorted(outward):
            lines.append(f"| `{mod}` | {', '.join(sorted(outward[mod]))} |")
    lines.append("")
    lines.append("## 五、插件层 → 内核 反向守卫（零容许）")
    lines.append("")
    lines.append("联邦契约的对角线：领域插件只能通过 `src.plugin_api` 的公开接口与内核交互。")
    if not boundary:
        lines.append("无越界条目：插件层不 import 内核私有名字，也不读 vm / interp 的私有成员。")
    else:
        lines.append(f"越界条目：**{len(boundary)}**（应当为 0）")
        lines.append("")
        lines.append("| 文件 | 行 | 类型 | 对象 | 私有名 |")
        lines.append("|---|---|---|---|---|")
        for b in boundary:
            lines.append(f"| `{b.file}` | {b.lineno} | {b.kind} | `{b.target}` | `{b.detail}` |")
    lines.append("")
    lines.append("## 六、每个内核文件的 import 清单")
    lines.append("")
    for rel in sorted(imports_by_file):
        mods = [m for m in imports_by_file[rel] if not m.startswith("src.")]
        local = [m for m in imports_by_file[rel] if m.startswith("src.")]
        lines.append(f"### `{rel}`")
        lines.append("")
        lines.append(f"- 标准库/外部：{', '.join(f'`{m}`' for m in mods) or '无'}")
        lines.append(f"- src.*：{', '.join(f'`{m}`' for m in local) or '无'}")
        lines.append("")
    return "\n".join(lines) + "\n"


# ============================================================
# CLI
# ============================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Matha 内核依赖审计")
    ap.add_argument("--write-report", action="store_true", help="写 docs/DEP_BASELINE.md")
    ap.add_argument("--write-baseline", action="store_true", help="写 tests/kernel_purity_baseline.json")
    ap.add_argument("--check", action="store_true", help="与棘轮基线比对，有新增违规则退出码 1")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args(argv)

    violations, edges, imports_by_file = audit()
    boundary = audit_plugins()

    if args.json:
        print(json.dumps({
            "kernel_files": sorted(imports_by_file),
            "violations": [asdict(v) for v in violations],
            "edges": [asdict(e) for e in edges],
            "plugin_boundary": [asdict(b) for b in boundary],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"内核文件 {len(imports_by_file)} 个 | import 边 {len(edges)} 条 | 违规 {len(violations)} 条"
              f" | 插件越界 {len(boundary)} 条")
        for v in violations:
            print(f"  [{v.kind:<12}] {v.file}:{v.lineno} -> {v.imported}"
                  f"{'  (惰性)' if v.nested else ''}")
        for b in boundary:
            print(f"  [{b.kind:<12}] {b.file}:{b.lineno} -> {b.target}.{b.detail}")

    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            render_report(violations, edges, imports_by_file, boundary), encoding="utf-8")
        print(f"已写入 {REPORT_PATH.relative_to(ROOT)}")

    if args.write_baseline:
        write_baseline(violations)
        print(f"已写入 {BASELINE_PATH.relative_to(ROOT)}（{len(violations)} 条）")

    if args.check:
        baseline = load_baseline()
        if baseline is None:
            print("ERROR: 未找到棘轮基线，先运行 --write-baseline", file=sys.stderr)
            return 2
        new, gone = diff_baseline(violations, baseline)
        if gone:
            print(f"提示：基线中有 {len(gone)} 条已修复，请运行 --write-baseline 收紧基线")
        if new:
            print(f"ERROR: 发现 {len(new)} 条基线外新增内核违规：", file=sys.stderr)
            for v in new:
                print(f"  {v.file}:{v.lineno} -> {v.imported} [{v.kind}]", file=sys.stderr)
            return 1
        print("OK: 内核依赖未超出棘轮基线")
        if boundary:
            print(f"ERROR: 插件层越界访问内核私有成员 {len(boundary)} 条（零容许）：",
                  file=sys.stderr)
            for b in boundary:
                print(f"  {b.file}:{b.lineno} -> {b.target}.{b.detail} [{b.kind}]",
                      file=sys.stderr)
            return 1
        print("OK: 插件层未越界访问内核私有成员")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
