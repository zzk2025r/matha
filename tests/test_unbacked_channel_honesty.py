# -*- coding: utf-8 -*-
"""P0 诚实边界锁（骨架体检 · 零缺陷闭环计划 P0-1 / P0-2）。

锁定两条「未背书 / 版本单一源」红线，防止悄悄回退：

1. **AI 前端未背书**（口径见 `docs/KNOWN_ISSUES.md` 第七节 7c）：
   `src/ai_assistant*.py`、`src/ai_framework.py`、`src/openai_compat_server.py`
   五个文件必须各自携带「未背书 / P2 降级」docstring 横幅，且不得被 L1 纯净
   内核链（`lexer`/`parser`/`ast_nodes`/`kernel/`/`mbc/`）在**模块顶层**导入
   ——它们只允许经宿主聚合入口 / CLI 子命令懒加载触达。

2. **mobile 版本单一源**（口径见 `docs/KNOWN_ISSUES.md` 第七节 7b）：
   mobile 构建 / 部署脚本不得再硬编旧版本号（曾为 4.4.16），必须从唯一版本源
   `src/__version__.py` 读取。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

#: KNOWN_ISSUES 7c 登记的未背书 AI 前端文件
AI_FRONTEND = (
    "ai_assistant.py",
    "ai_assistant_desktop.py",
    "ai_assistant_server.py",
    "ai_framework.py",
    "openai_compat_server.py",
)

_BANNER_MARKERS = ("未背书", "P2 降级")

#: L1 纯净内核链（顶层 import 这些 AI 模块即属越界）
_KERNEL_FILES = [SRC / "lexer.py", SRC / "parser.py", SRC / "ast_nodes.py"]
_KERNEL_DIRS = [SRC / "kernel", SRC / "mbc"]


def _head(text: str, n: int) -> str:
    return "\n".join(text.splitlines()[:n])


def test_ai_frontend_files_carry_unbacked_banner():
    """5 个 AI 前端文件都要在文件头 docstring 里标注未背书 / P2 降级。"""
    missing = []
    for name in AI_FRONTEND:
        p = SRC / name
        assert p.is_file(), f"AI 前端文件缺失：{p}"
        head = _head(p.read_text(encoding="utf-8", errors="replace"), 15)
        if not any(m in head for m in _BANNER_MARKERS):
            missing.append(name)
    assert not missing, (
        "AI 前端文件缺『未背书 / P2 降级』横幅（回归了未背书主张）："
        + ", ".join(missing))


def _top_level_imports_ai(path: Path) -> bool:
    """模块顶层（无缩进）出现对 AI 前端模块的 import 视为越界。

    缩进行（函数内 import）属宿主侧懒加载，是允许的真实接入方式，不算越界。
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:1].isspace():
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if (
            "import ai_assistant" in stripped
            or "import ai_framework" in stripped
            or "import openai_compat_server" in stripped
            or "from src import ai_" in stripped
            or "from src.ai_" in stripped
        ):
            return True
    return False


def test_kernel_chain_does_not_top_level_import_ai_frontend():
    """L1 内核纯净链不得在模块顶层导入未背书 AI 前端。"""
    files = list(_KERNEL_FILES)
    for d in _KERNEL_DIRS:
        files += sorted(d.rglob("*.py"))
    offenders = [
        str(p.relative_to(ROOT))
        for p in files
        if p.is_file()
        and "__pycache__" not in p.parts
        and _top_level_imports_ai(p)
    ]
    assert not offenders, (
        "L1 内核链在模块顶层导入了未背书 AI 前端（污染内核纯净边界）："
        + ", ".join(offenders))


#: mobile 构建 / 部署脚本（P0-1 版本漂移修复对象）
_MOBILE_SCRIPTS = (
    ROOT / "mobile" / "assets" / "pyodide" / "build_wasm.bat",
    ROOT / "mobile" / "assets" / "pyodide" / "build_wasm.sh",
    ROOT / "mobile" / "assets" / "deploy.bat",
    ROOT / "mobile" / "assets" / "deploy.sh",
)


def test_mobile_scripts_read_version_from_single_source():
    """mobile 脚本不得硬编旧版本号，必须引用唯一版本源读取。"""
    for p in _MOBILE_SCRIPTS:
        assert p.is_file(), f"mobile 脚本缺失：{p}"
        txt = p.read_text(encoding="utf-8", errors="replace")
        assert "4.4.16" not in txt, f"{p.name} 仍硬编旧版本号 4.4.16"
        assert "__version__.py" in txt, (
            f"{p.name} 未从唯一版本源 src/__version__.py 读取版本号")
