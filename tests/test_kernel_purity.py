# -*- coding: utf-8 -*-
"""内核纯净守门测试 —— 阶段 0 交付件，整个去依赖重构的契约执行者。

四组断言：
  1. 审计器自身可信（内核清单里的文件都存在、能被解析）。
  2. 静态 import 违规不得超出棘轮基线（只允许减少）。
  2c. 核心目录子进程/并行/宿主逃逸红线（AST 级零容许）。
  3. 运行时 sys.modules 不得出现第三方重型库。
  4. 运行时 sys.modules 不得出现领域/插件层。

本测试是只减不增的棘轮：修复了违规就运行
    python scripts/dep_audit.py --write-baseline --write-report
收紧基线，否则残留条目会掩盖回退。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.dep_audit import (  # noqa: E402
    BASELINE_PATH,
    KERNEL_FILES,
    audit,
    audit_plugins,
    kernel_files,
    load_baseline,
    plugin_files,
)

THIRD_PARTY_FORBIDDEN = ("numpy", "sympy", "scipy", "numba", "tree_sitter", "ctypes")


# ============================================================
# 1. 审计器自身
# ============================================================

def test_kernel_file_list_is_not_stale():
    """KERNEL_FILES 里声明的文件必须真实存在（防止重构后清单与代码脱节）。"""
    missing = [f for f in KERNEL_FILES if not (ROOT / f).exists()]
    assert not missing, f"内核清单存在失效条目：{missing}；请同步 scripts/dep_audit.py"


def test_kernel_glob_catches_new_packages():
    """src/kernel/ 一旦建立就必须自动纳入审计范围。"""
    kernel_dir = ROOT / "src" / "kernel"
    created_dir = not kernel_dir.exists()
    kernel_dir.mkdir(parents=True, exist_ok=True)
    probe = kernel_dir / "_purity_probe.py"
    probe.write_text("import json\n", encoding="utf-8")
    try:
        found = {p.relative_to(ROOT).as_posix() for p in kernel_files()}
        assert "src/kernel/_purity_probe.py" in found
    finally:
        probe.unlink(missing_ok=True)
        if created_dir:
            kernel_dir.rmdir()


def test_kernel_files_are_parseable():
    """内核文件必须可被 ast 解析（守门测试自身不能因语法错误而静默跳过）。"""
    violations, edges, imports_by_file = audit()
    assert imports_by_file, "审计未覆盖任何文件"
    assert len(imports_by_file) >= len(KERNEL_FILES), "部分内核文件未被审计"


# ============================================================
# 2. 静态 import 棘轮
# ============================================================

def test_kernel_imports_within_ratchet():
    """内核静态依赖违规不得超出棘轮基线 —— 只允许减少，不允许新增。"""
    baseline = load_baseline()
    assert baseline is not None, (
        "缺少棘轮基线 tests/kernel_purity_baseline.json，"
        "请运行：python scripts/dep_audit.py --write-baseline"
    )
    violations, _, _ = audit()
    allowed = set(baseline.get("keys", []))
    new = [v for v in violations if v.key not in allowed]
    if new:
        detail = "\n".join(
            f"  {v.file}:{v.lineno} -> {v.imported} [{v.kind}]" for v in new
        )
        pytest.fail(
            f"内核新增 {len(new)} 条依赖违规（内核不得依赖第三方库 / 领域插件 / "
            f"遗留后端 / 宿主逃逸）：\n{detail}\n"
            f"若这是预期改动，请评估是否应改走 src/plugin_api 或 src/kernel，"
            f"确认后再运行 --write-baseline 收紧。"
        )
    removed = [k for k in baseline.get("entries", [])
               if k not in {v.as_baseline_entry() for v in violations}]
    if removed:
        print(f"\n[内核棘轮] {len(removed)} 条违规已修复，可运行 --write-baseline 收紧基线：")
        for k in removed:
            print(f"  - {k}")


def test_baseline_json_shape():
    """基线文件格式自检。"""
    if not BASELINE_PATH.exists():
        pytest.skip("基线尚未生成")
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert "keys" in payload and "entries" in payload
    assert len(payload["keys"]) == len(set(payload["keys"]))


# ============================================================
# 2b. 插件层 → 内核 的反向守卫（零容许，无基线）
# ============================================================

def test_plugin_layer_files_are_audited():
    """插件目录存在且能被解析（否则下面的零容许守卫会因空集而假绿）。"""
    files = plugin_files()
    assert len(files) >= 50, f"插件层文件数异常 ({len(files)})，审计作用域可能写错了"


def test_plugin_layer_does_not_touch_kernel_internals():
    """支线不得 import 内核私有名字，也不得读 vm / interp 的私有成员。

    这一条零容许（无棘轮基线）：联邦架构的契约边界只能变硬，不能变软。
    插件需要新能力时，应扩展 src.plugin_api.PluginContext 的公开方法。
    """
    bad = audit_plugins()
    if bad:
        detail = "\n".join(
            f"  {b.file}:{b.lineno} -> {b.target}.{b.detail} [{b.kind}]" for b in bad
        )
        pytest.fail(
            "插件层越界访问核心私有成员（只能通过 src.plugin_api 公开接口交互）：\n"
            + detail
        )


def test_domain_manifest_is_not_stale():
    """领域清单必须存在且含符号索引（semantic / 懒解析都依赖它）。"""
    manifest = ROOT / "src" / "domains" / "manifest.json"
    assert manifest.exists(), "缺少 src/domains/manifest.json，请运行 scripts/gen_domain_manifest.py"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload.get("protocol_version") == 1
    plugins = payload.get("plugins", [])
    assert len(plugins) >= 50, f"清单插件数异常：{len(plugins)}"
    symbols = {s for p in plugins for s in p["symbols"]}
    assert len(symbols) > 1000, f"清单符号数异常：{len(symbols)}"


# ============================================================
# 2c. 核心目录子进程/并行红线（验收标准 2）
# ============================================================

#: 核心主线所在文件/目录（与验收标准逐字对齐）
CORE_PATHS = (
    "src/lexer.py",
    "src/parser.py",
    "src/ast_nodes.py",
    "src/kernel",
    "src/mbc",
)

#: 核心必须单线程确定、且不驱动外部进程（由验收标准 2 直接反推）
#: 注：`importlib` 不在列——`src/kernel/symbolic/__init__.py` 用它做包内惰性
#: 加载（PEP 562），属标准库内部组装；真正要堵的是子进程/并行，包括
#: 反射式拉入（下方同时检查 `__import__`/`import_module` 的字面参数）。
CORE_FORBIDDEN_MODULES = (
    "subprocess", "multiprocessing", "threading", "concurrent", "socket", "ctypes",
)

#: 核心身份文件（少一个就是审计作用域写错，不得默不作声地空集假绿）
CORE_MUST_HAVE = (
    "src/lexer.py", "src/parser.py", "src/ast_nodes.py",
    "src/kernel/exec_api.py", "src/mbc/vm.py", "src/mbc/compiler.py", "src/mbc/native.py",
)


def _core_sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rel in CORE_PATHS:
        p = ROOT / rel
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*.py"))
        for f in files:
            # utf-8-sig：源文件里的 BOM 不能成为绕门手段
            out.append((f.relative_to(ROOT).as_posix(), f.read_text(encoding="utf-8-sig")))
    return out


def test_core_paths_exist_and_are_nontrivial():
    """核心清单不得与代码脱节（否则下面的零容许守卫会空集假绿）。"""
    missing = [rel for rel in CORE_PATHS if not (ROOT / rel).exists()]
    assert not missing, f"核心路径不存在：{missing}"
    names = {name for name, _ in _core_sources()}
    absent = [rel for rel in CORE_MUST_HAVE if rel not in names]
    assert not absent, f"核心审计作用域缺少主线文件：{absent}"


def test_core_has_no_subprocess_or_threads():
    """核心目录内不得出现子进程/线程/并行/宿主逃逸（验收标准 2）。

    并行解析属 `src/plugins/parallel_parser.py`，外部工具链子进程属
    `src/plugins/toolchain_*.py`；核心解析/编译/执行必须单线程确定。

    用 AST 而非全文 grep：否则注释/文档里提及 `threading` 一词会误报，
    而真正的动态导入（`__import__` / `importlib.import_module`）会被漏掉。
    """
    import ast

    bad: list[str] = []
    for name, text in _core_sources():
        tree = ast.parse(text, filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in CORE_FORBIDDEN_MODULES:
                        bad.append(f"{name}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if node.level == 0 and root in CORE_FORBIDDEN_MODULES:
                    bad.append(f"{name}:{node.lineno} from {node.module} import ...")
            elif isinstance(node, ast.Call):
                fn = node.func
                callee = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if callee in {"__import__", "import_module"} and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        if first.value.split(".")[0] in CORE_FORBIDDEN_MODULES:
                            bad.append(f"{name}:{node.lineno} 动态导入 {first.value}")
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr == "system":
                    bad.append(f"{name}:{node.lineno} os.system")
    assert not bad, "核心目录存在子进程/并行/宿主逃逸：\n" + "\n".join(bad)


# ============================================================
# 3 & 4. 运行时隔离检查（独立子进程，避免污染其他测试的 sys.modules）
# ============================================================

_RUNTIME_SNIPPET = """
import json, sys
import src.mbc.vm as vm
vm._default_builtins()          # 强制触发内建注册（惰性 import 在此发生）
PREFIX = ('numpy','sympy','scipy','numba','tree_sitter','ctypes','src.')
mods = sorted(m for m in sys.modules if m.startswith(PREFIX))
print(json.dumps(mods))
"""


def _runtime_modules() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-c", _RUNTIME_SNIPPET],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"内核运行时检查子进程失败：\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def runtime_modules() -> list[str]:
    return _runtime_modules()


def test_runtime_loads_no_third_party(runtime_modules):
    """VM 内建注册后，sys.modules 中不得出现任何第三方重型库。"""
    bad = [m for m in runtime_modules if m.startswith(THIRD_PARTY_FORBIDDEN)]
    assert not bad, f"内核运行时拖入第三方库：{bad}"


_INTERP_SNIPPET = """
import json, sys
import src.interp as I
I.Interpreter()                 # 旧 eager 注册在此发生（如果还在，会拉入 40+ 领域模块）
mods = sorted(m for m in sys.modules if m.startswith('src.domains'))
print(json.dumps(mods))
"""


def test_legacy_backend_no_longer_eagerly_imports_domains():
    """树走式后端降级为诊断插件后，创建解释器不得再 eager import 任何领域模块。

    阶段 1 第 2 项的实质证明点：领域符号只在内建表被真正取用时才加载。
    """
    proc = subprocess.run(
        [sys.executable, "-c", _INTERP_SNIPPET],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"子进程失败：\n{proc.stderr}"
    loaded = json.loads(proc.stdout.strip().splitlines()[-1])
    assert not loaded, f"创建解释器时 eager 加载了领域模块：{loaded}"


def test_runtime_loads_no_domain_modules(runtime_modules):
    """内核运行时不得加载任何领域/插件模块（联邦式架构的地基）。"""
    bad = [m for m in runtime_modules if m == "src.domains" or m.startswith("src.domains.")]
    assert not bad, f"内核运行时拖入领域插件：{bad}"


def test_runtime_kernel_surface_is_small(runtime_modules):
    """内核 import 面必须保持在极小规模：只允许核心主线 + 内核模块。

    这条是「轻量化」的量化护栏 —— 一旦有人往内核里塞新依赖，加载的 src.*
    数量会立刻上涨。上限随阶段 1 建立 src/kernel/ 后适度收紧。
    """
    allowed_prefixes = (
        "src", "src.tokens", "src.lexer", "src.ast_nodes", "src.ast_ext",
        "src.custom_ops", "src.features", "src.formula_schema", "src.kernel.math_builtin",
        "src.kernel.regex_builtin", "src.text_encoding", "src.parser",
        "src.kernel", "src.mbc",
    )
    loaded = [m for m in runtime_modules if m.startswith("src.")]
    unexpected = [
        m for m in loaded
        if not any(m == p or m.startswith(p + ".") for p in allowed_prefixes)
    ]
    # 领域层单独由 test_runtime_loads_no_domain_modules 负责，这里排除以免重复归因。
    unexpected = [m for m in unexpected if not m.startswith("src.domains")]
    assert not unexpected, f"内核加载了预期之外的 src.* 模块：{unexpected}"
