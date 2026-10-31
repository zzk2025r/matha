# -*- coding: utf-8 -*-
"""阶段 5 第 1 项：单一版本源。

重构前同一份代码里同时存在 v4.3 / v4.4 / v4.4.57 / v4.5 / v4.6 / 1.0.0 六个
「版本号」：`matha --version`、`pip show matha`、README、MATHA_COMPARISON 互相
矛盾。本文件把「只有一个版本源」变成可机器判定的事实：

  1. `src/__version__.py` 内部自洽（`__version__` / `VERSION` / `VERSION_LABEL`
     / `VERSION_INFO` / `get_version()` / `version_info()` 同值）；
  2. 除该文件外，`src/**` 里不允许再出现「版本常量 = 版本字面量」；
  3. `pyproject.toml` 用 dynamic attr 指向它，且核心 `dependencies` 为空；
  4. `matha --version` 的可见输出就是它；
  5. 权威文档里出现的每一个 `vX.Y(.Z)` 都等于它。
"""
from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VER = importlib.import_module("src.__version__")

#: 权威文档：这些文件里不许出现与版本源不同的版本号
AUTHORITATIVE_DOCS = (
    ROOT / "README.md",
    ROOT / "MATHA_COMPARISON.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "KNOWN_ISSUES.md",
)

#: 只有这一处允许出现版本字面量
ONLY_SOURCE = ROOT / "src" / "__version__.py"

#: 承载版本号的常量名（值形如 4.6 / v4.6.0 才算违规）
VERSION_CONSTANTS = re.compile(
    r"^\s*(?:__version__|VERSION|VERSION_LABEL|SOFTWARE_VERSION|MATHA_VERSION"
    r"|APP_VERSION|CURRENT_VERSION|LATEST_VERSION)\s*[:=]\s*[\"']v?(\d+\.\d+[^\"']*)[\"']",
    re.M)

_VERSION_TOKEN = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b")


def test_version_source_is_self_consistent():
    v = VER.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", v), f"发布号应为 MAJOR.MINOR.PATCH：{v}"
    assert VER.VERSION == v
    assert VER.VERSION_LABEL == f"Matha v{v}"
    assert VER.VERSION_INFO == tuple(int(x) for x in v.split("."))
    assert VER.get_version() == v
    info = VER.version_info()
    assert info["version"] == v and info["label"] == VER.VERSION_LABEL
    assert isinstance(VER.KERNEL_PROTOCOL, int) and VER.KERNEL_PROTOCOL >= 1


def test_package_attribute_matches_the_source():
    import src

    assert src.__version__ == VER.__version__


def test_no_other_file_declares_a_version_literal():
    offenders = []
    for p in sorted((ROOT / "src").rglob("*.py")):
        if "__pycache__" in p.parts or p.resolve() == ONLY_SOURCE.resolve():
            continue
        for m in VERSION_CONSTANTS.finditer(p.read_text(encoding="utf-8",
                                                        errors="replace")):
            offenders.append(f"{p.relative_to(ROOT)}: {m.group(1)} = {m.group(2)!r}")
    assert not offenders, "版本常量出现在唯一版本源之外：\n" + "\n".join(offenders)


def test_pyproject_points_at_the_single_source():
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in txt, "pyproject 不该硬编码版本"
    assert 'version = {attr = "src.__version__.__version__"}' in txt
    assert re.search(r"^dependencies\s*=\s*\[\s*\]", txt, re.M), \
        "核心安装必须零第三方依赖"
    assert "sympy" not in txt.split("[project.optional-dependencies]")[0].split(
        "[tool")[0], "sympy 只能出现在 optional-dependencies"


def test_cli_reports_the_single_version():
    proc = subprocess.run([sys.executable, "-m", "src.matha_main", "--version"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert f"Matha v{VER.__version__}" in proc.stdout, proc.stdout


def test_authoritative_docs_carry_only_the_current_version():
    want = f"v{VER.__version__}"
    bad = []
    for doc in AUTHORITATIVE_DOCS:
        assert doc.is_file(), f"权威文档缺失：{doc}"
        for tok in set(_VERSION_TOKEN.findall(doc.read_text(encoding="utf-8",
                                                            errors="replace"))):
            if tok != want:
                bad.append(f"{doc.name}: {tok}")
    assert not bad, "文档版本号与唯一版本源不一致：\n" + "\n".join(sorted(bad))
