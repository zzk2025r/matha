# -*- coding: utf-8 -*-
"""联邦插件契约测试（重构阶段 1）。

覆盖计划里的四条契约：
  1. `src/plugin_api.py` 协议 —— `MathaPlugin` / `PluginContext` / 适配层；
  2. 清单驱动的懒加载 —— 枚举与名字查询不 import 任何领域模块；
  3. 显式加载语法 `@：【加载领域】，X` 与未加载引用的编译期诊断；
  4. 插件层不得访问内核私有成员（与 `test_kernel_purity.py` 互补）。

需要断言 `sys.modules` 的用例一律起子进程，避免同进程内其它测试先把领域模块带进来。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from src.kernel import exec_api                      # noqa: E402
from src.plugin_api import (                         # noqa: E402
    LEVEL_ERROR,
    LEVEL_WARNING,
    MathaPlugin,
    LegacyModulePlugin,
    PluginContext,
    PluginResolver,
    PROTOCOL_VERSION,
    get_resolver,
)

MANIFEST = ROOT / "src" / "domains" / "manifest.json"


def _run_snippet(code: str) -> str:
    """在干净解释器里执行一段 Python，返回 stdout。"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


# ============================================================
# 一、清单
# ============================================================

def test_manifest_exists_and_declares_protocol():
    assert MANIFEST.exists(), "缺少插件清单，请运行 scripts/gen_domain_manifest.py"
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert payload["generator"] == "scripts/gen_domain_manifest.py"
    # 81 个领域模块全部保留为插件；清单里至少要有 79 个可用插件
    assert len(payload["plugins"]) >= 79
    assert payload["unavailable"] == [], f"存在不可用插件：{payload['unavailable']}"


def test_manifest_distinguishes_registered_from_declared():
    """可加载符号与仅声明符号必须分开，否则诊断会指向取不到的名字。"""
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for p in payload["plugins"]:
        assert "symbols" in p and "declared_symbols" in p
        assert set(p["declared_symbols"]).isdisjoint(set(p["symbols"]))


def test_resolver_indexes_all_symbols_without_importing():
    before = set(sys.modules)
    resolver = get_resolver()
    names = resolver.names()
    symbols = resolver.known_symbols()
    leaked = sorted(m for m in set(sys.modules) - before if m.startswith("src.domains."))
    assert leaked == [], f"读取清单不该 import 领域模块：{leaked}"
    assert len(names) >= 79
    assert len(symbols) > 2000


# ============================================================
# 二、契约协议
# ============================================================

def test_legacy_plugin_satisfies_protocol():
    resolver = get_resolver()
    plugin = resolver.plugin("mech_design")
    assert plugin is not None
    assert isinstance(plugin, MathaPlugin), "适配层必须满足 MathaPlugin 协议"
    assert plugin.name == "mech_design"
    assert plugin.legacy is True


def test_exports_include_non_callable_constants():
    """旧 eager 注册允许常量表；契约不得因为值不可调用而静默丢符号。"""
    plugin = get_resolver().plugin("mech_design")
    exports = plugin.exports()
    assert "公差系数_IT10" in exports, f"常量型符号被丢弃：{len(exports)} 项"
    assert exports["公差系数_IT10"] == 64.0


def test_context_rejects_bad_names_and_duplicates():
    ctx = PluginContext("t_demo")
    assert ctx.register_builtin("", lambda: 1) is False
    assert ctx.register_builtin("f", lambda: 1) is True
    assert ctx.register_builtin("f", lambda: 2) is False          # 重复且不许覆盖
    assert ctx.register_builtin("f", lambda: 2, override=True) is True
    levels = [d.level for d in ctx.diagnostics]
    assert LEVEL_ERROR in levels and LEVEL_WARNING in levels


def test_context_exposes_no_core_internals():
    """契约红线：上下文不持有 VM / Interpreter，也不暴露栈与全局表的可写入口。"""
    forbidden = {"vm", "frames", "stack", "_stack", "globals", "interp", "engine"}
    ctx = PluginContext("t_demo")
    public = {a for a in dir(ctx) if not a.startswith("__")}
    assert forbidden.isdisjoint(public), f"上下文泄漏内核内部：{public & forbidden}"
    # builtins 是只读 Mapping，不是可变 dict
    assert not isinstance(ctx.builtins, dict)


def test_plugin_api_source_touches_no_core_private_members():
    """静态守卫：契约层不得读内核对象的私有成员（注释里的反面例子不算）。"""
    import ast

    tree = ast.parse((ROOT / "src" / "plugin_api.py").read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            base = node.value
            base_name = base.id if isinstance(base, ast.Name) else ""
            if base_name in {"vm", "interp", "engine"} and node.attr.startswith("_"):
                offenders.append(f"{base_name}.{node.attr}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else ""
            if mod and mod.startswith("src.domains"):
                offenders.append(mod)
            if isinstance(node, ast.ImportFrom) and node.module in {
                    "src.mbc.vm", "src.mbc.compiler", "src.interp", "src.parser"}:
                for alias in node.names:
                    if alias.name.startswith("_"):
                        offenders.append(f"{node.module}.{alias.name}")
    assert offenders == [], f"契约层越界访问内核内部：{offenders}"


# ============================================================
# 三、懒加载（子进程隔离）
# ============================================================

_EVAL_SNIPPET = """
import sys
from src.kernel import exec_api
out = exec_api.run_expr("sin(pi)")
assert out and abs(float(out[-1])) < 1e-9, out
leaked = sorted(m for m in sys.modules if m.startswith("src.domains"))
print("OUT", out)
print("LEAK", leaked)
"""


def test_eval_kernel_expr_loads_no_domain_modules():
    """验收标准 5 的前半：只用到内核内建时零领域 import。"""
    out = _run_snippet(_EVAL_SNIPPET)
    assert "LEAK []" in out, out


_LIST_SNIPPET = """
import io, json, sys
from src.plugin_api import get_resolver
plugins = get_resolver().list_plugins()
leaked = sorted(m for m in sys.modules if m.startswith("src.domains."))
print(json.dumps({"n": len(plugins), "leak": leaked}, ensure_ascii=False))
"""


def test_listing_plugins_has_zero_import_cost():
    """验收标准 6：枚举全部插件不产生 import 成本。"""
    payload = json.loads(_run_snippet(_LIST_SNIPPET).strip().splitlines()[-1])
    assert payload["n"] >= 79
    assert payload["leak"] == []


_CLI_SNIPPET = """
import sys
from src.matha_main import main
main(["--list-domains"])
leaked = sorted(m for m in sys.modules if m.startswith("src.domains."))
print("LEAK", leaked)
"""


def test_matha_list_domains_cli():
    out = _run_snippet(_CLI_SNIPPET)
    assert "领域插件" in out and "mech_design" in out
    assert "LEAK []" in out, out


# ============================================================
# 四、显式加载指令与编译期诊断
# ============================================================

CONST_SRC = "result = 公差系数_IT10\n#1：[result]\n"

_AUTO_SNIPPET = (
    "import json, sys\n"
    "from src.kernel import exec_api\n"
    "from src.plugin_api import get_resolver\n"
    f"src = {CONST_SRC!r}\n"
    "r = get_resolver()\n"
    "before = set(r.loaded())\n"
    "out = exec_api.run(src)\n"
    "leaked = sorted(m for m in sys.modules if m.startswith('src.domains.'))\n"
    "print(json.dumps({'out': [float(x) for x in out], "
    "'loaded': sorted(set(r.loaded()) - before), 'leaked': leaked}, "
    "ensure_ascii=False))\n"
)


def test_auto_mode_loads_only_the_needed_plugin():
    """auto 模式只按需加载那一个插件。

    必须在**干净子进程**里跑：同进程内先跑过的用例会把 mech_design 提前带进来，
    `loaded()` 的增量就变成空集，断言测的不再是「懒加载」而是测试顺序。
    """
    payload = json.loads(_run_snippet(_AUTO_SNIPPET).strip().splitlines()[-1])
    assert payload["out"] == [64.0], payload
    assert payload["loaded"] == ["mech_design"], payload
    assert payload["leaked"] == ["src.domains.mech_design"], payload


def test_explicit_directive_makes_symbol_available():
    src = "@：【加载领域】，机械设计\n" + CONST_SRC
    assert exec_api.run(src, plugins="strict") == [64.0]


def test_strict_mode_diagnoses_unloaded_domain_symbol():
    with pytest.raises(RuntimeError) as excinfo:
        exec_api.run(CONST_SRC, plugins="strict")
    msg = str(excinfo.value)
    assert "未加载" in msg and "mech_design" in msg
    assert "@：【加载领域】" in msg               # 必须给出可用写法


def test_plugins_off_does_not_consult_resolver():
    with pytest.raises(KeyError):
        exec_api.run(CONST_SRC, plugins="off")


def test_unknown_domain_gives_candidates_not_silent_success():
    src = "@：【加载领域】，mechanic\nresult = 1\n#1：[result]"
    with pytest.raises(RuntimeError) as excinfo:
        exec_api.run(src, plugins="strict")
    assert "mechanic" in str(excinfo.value)


def test_directive_is_the_only_new_syntax_and_old_writing_still_works():
    """`@：` 的既有写法（普通设定项）行为不变。"""
    assert exec_api.run("@：a=2，b=3\nresult = a + b\n#1：[result]") == [5]


def test_compiler_without_plugin_index_skips_check():
    from src.mbc.compiler import compile_source
    mod = compile_source(CONST_SRC)               # plugin_index=None → 不检查
    assert mod.main_code


# ============================================================
# 五、后端门面
# ============================================================

def test_available_modes_has_single_mainline():
    modes = exec_api.available_modes()
    assert modes["vm"].startswith("核心主线")
    assert set(modes) >= {"vm", "native"}


def test_native_mode_refuses_to_masquerade_as_executor():
    """机器码路径不得「模拟成功」：run(mode='native') 必须显式失败。"""
    with pytest.raises(RuntimeError) as excinfo:
        exec_api.run("result = 1", mode="native")
    assert "build_exe" in str(excinfo.value)


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        exec_api.run("result = 1", mode="nope")


def test_legacy_interp_backend_is_registered_explicitly():
    """树走式解释器只作为显式诊断后端存在。"""
    import src.interp  # noqa: F401  —— 注册发生在模块导入时
    modes = exec_api.available_modes()
    assert "legacy-interp" in modes
    assert "诊断" in modes["legacy-interp"]


def test_semantic_layer_reads_manifest_not_domain_code():
    """语义层只读清单，不再 import 领域代码（重构阶段 1 第 5 项）。"""
    import ast

    tree = ast.parse((ROOT / "src" / "semantic.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    assert [m for m in imported if m.startswith("src.domains")] == [], imported


def test_resolver_unregister_keeps_index_consistent():
    resolver = PluginResolver(MANIFEST)
    owners_before = resolver.owners_of("公差系数_IT10")
    assert resolver.unregister("mech_design") is True
    assert resolver.owners_of("公差系数_IT10") == []
    assert "公差系数_IT10" not in resolver.domain_symbol_index()
    assert resolver.unregister("mech_design") is False
    assert owners_before == ["mech_design"]


# ============================================================
# 六、符号命名卫生：插件不得改写内核与其它 .matha 源的名字空间
# ============================================================
#
# 两条硬规则，来自实际踩过的坑（新增插件「符号微积分」的第一版同时违反了两条）：
#   * 物化插件时执行的是 ``target.update(table)`` —— 同名即覆盖。若插件导出
#     ``符号``，会把 ``matha/stdlib_symbols.matha`` 的 ``func 符号(...)`` 抬掉，
#     自举 parser 直接碎（test_bootstrap_host::test_bootstrap_interpret_custom_op）。
#   * 清单里的符号名会经 ``LazyBuiltinTable.__contains__`` 在全进程生效。若插件
#     导出裸 ``x``，「未定义名即报错」这条内核契约就被改写，受影响的是所有
#     拿 x 做变量名的程序（test_bootstrap_host / test_auto_debug_e2e 共 4 例）。


def _manifest_indexed_symbols() -> set[str]:
    """清单里会被全局索引的符号名（可加载 + 仅声明），不触发任何领域 import。"""
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: set[str] = set()
    for p in payload["plugins"]:
        out |= set(p.get("symbols") or [])
        out |= set(p.get("declared_symbols") or [])
    return out


def _matha_top_level_names() -> tuple[set[str], list[str]]:
    """解析自举核心（``matha/*.matha``）与标准库（``matha/library/**``），
    返回（顶层声明名，解析失败的文件）。知识语料不在参评范围（旧写法尚未能解析）。"""
    from src.parser import parse

    files: list[Path] = sorted((ROOT / "matha").glob("*.matha"))
    files += sorted((ROOT / "matha" / "library").rglob("*.matha"))
    assert len(files) >= 30, f".matha 语料异常减少：只找到 {len(files)} 个文件"
    names: set[str] = set()
    unparsed: list[str] = []
    for f in files:
        try:
            prog = parse(f.read_text(encoding="utf-8"))
        except Exception:                              # 解析不了就无法断言无冲突
            unparsed.append(f.name)
            continue
        for d in getattr(prog, "decls", []):
            n = getattr(d, "name", None)
            if n:
                names.add(n)
    return names, unparsed


def test_matha_core_sources_still_parse_for_the_name_guard():
    """命名卫生门禁的前提：参评 .matha 源件件解得开（解不开不准静默跳过）。"""
    _, unparsed = _matha_top_level_names()
    assert unparsed == [], f"以下 .matha 无法解析，命名冲突门禁失效：{unparsed}"


def test_plugin_symbols_do_not_shadow_matha_source_names():
    """任何插件符号名都不得与 .matha 源码的顶层声明同名（同名会覆盖自举链）。"""
    names, _ = _matha_top_level_names()
    assert names, ".matha 顶层声明采集为空，门禁本身失效"
    clash = sorted(_manifest_indexed_symbols() & names)
    assert clash == [], f"插件符号与 .matha 顶层声明碰撞：{clash}"


def test_plugin_symbols_are_never_bare_single_letters():
    """插件不得导出单字母符号：那是用户变量最常用的名字，导出即改写全语言语义。"""
    import re

    bad = sorted(s for s in _manifest_indexed_symbols() if re.fullmatch(r"[A-Za-z]", s))
    assert bad == [], f"插件导出了裸单字母符号（污染未定义名契约）：{bad}"
