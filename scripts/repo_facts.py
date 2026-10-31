#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仓库实测事实（唯一数字来源）：文档里的每个数字都从这里取。

阶段 5 第 3 项「文档如实化」的配套工具。以前的 README / MATHA_COMPARISON 里
写着「通过率 100%」「综合评分 9.0/10」「87+ 领域模块」「缺陷已解决 271/271」，
全是手写愿望，与代码无关，也没人能复现。本脚本只做一件事：**数真实存在的东西**，
可被 `tests/test_doc_facts.py` 调用，文档与代码一旦漂移，测试就红。

用法：
  python scripts/repo_facts.py          # 人读表格
  python scripts/repo_facts.py --json   # 机器读（文档/测试用）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: `src/domains/` 里不是插件的文件（包初始化与注册表本体）
NON_PLUGIN_MODULES = {"__init__", "registry"}


def facts() -> dict[str, object]:
    import importlib

    # `src/__init__.py` 把包属性 `src.__version__` 绑成了字符串，故取模块对象
    ver = importlib.import_module("src.__version__")

    domains_dir = ROOT / "src" / "domains"
    domain_files = sorted(p.stem for p in domains_dir.glob("*.py"))
    plugin_files = [m for m in domain_files if m not in NON_PLUGIN_MODULES]

    manifest = json.loads((domains_dir / "manifest.json").read_text(encoding="utf-8"))
    golden_manifest = json.loads(
        (ROOT / "golden_tests" / "manifest.json").read_text(encoding="utf-8"))

    cases = sorted(p.stem for p in (ROOT / "golden_tests" / "cases").glob("*.matha"))

    return {
        "version": ver.__version__,
        "version_label": ver.VERSION_LABEL,
        "kernel_protocol": ver.KERNEL_PROTOCOL,
        "domain_files": len(domain_files),
        "domain_plugins": len(plugin_files),
        "manifest_plugins": len(manifest["plugins"]),
        "manifest_unavailable": len(manifest["unavailable"]),
        "kernel_plugins": len(list((ROOT / "src" / "plugins").glob("*.py"))),
        "stdlib_extensions": len(list((ROOT / "src" / "stdlib").glob("*.py"))),
        "matha_library_files": len(list((ROOT / "matha" / "library").glob("*.matha"))),
        "matha_files": len(list((ROOT / "matha").rglob("*.matha"))),
        "example_files": len(list((ROOT / "examples").rglob("*.matha"))),
        "golden_cases": len(cases),
        "golden_manifest_cases": len(golden_manifest["cases"]),
        "golden_native_gaps": len(golden_manifest.get("native_known_gaps", {})),
        "test_files": len(list((ROOT / "tests").glob("test_*.py"))),
        "core_py_lines": (sum(_lines(p) for p in (
            ROOT / "src" / "lexer.py", ROOT / "src" / "parser.py",
            ROOT / "src" / "ast_nodes.py"))
            + _dir_lines(ROOT / "src" / "kernel") + _dir_lines(ROOT / "src" / "mbc")),
        "third_party_deps": _pyproject_deps(),
    }


def _lines(p: Path) -> int:
    return len(p.read_text(encoding="utf-8", errors="replace").splitlines())


def _dir_lines(d: Path) -> int:
    return sum(_lines(p) for p in sorted(d.rglob("*.py"))
               if "__pycache__" not in p.parts)


def _pyproject_deps() -> list[str]:
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", txt, re.M | re.S)
    if not m:
        return ["<解析失败>"]
    return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="仓库实测事实")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    data = facts()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("=== 仓库实测事实（python scripts/repo_facts.py --json 取机器可读版）===")
    for k, v in data.items():
        print(f"{k:>24}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
