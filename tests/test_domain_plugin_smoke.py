# -*- coding: utf-8 -*-
"""P3 领域插件最小烟雾门禁（骨架体检 · 零缺陷闭环计划 P3-10）。

背景：`src/domains/` 共 82 个领域插件，绝大多数是**声明式符号表**（常量 + 函数），
此前除 `test_plugin_contract.py`（通用契约 / 命名卫生）外，**没有按插件的专项用例**。
多数插件在测试里零引用，意味着「某插件 import 期抛错 / 导出被静默清空 /
manifest 声明符号与实际导出不符」这类回归不会被单独抓到。

本文件为每个插件补一条最小烟雾断言（口径与契约测试一致，不重复契约红线）：

  1. 插件能被物化（`plugin.exports()` 不抛异常）；
  2. 导出非空；
  3. manifest 里登记的每一枚**可加载符号**都能在导出中取到（声明 ↔ 实现一致）。

物化会 import 领域模块，按项目纪律（需要动 `sys.modules` 的断言一律起子进程，
见 `test_plugin_contract.py` 文档）把「全部插件物化」放进**单个子进程**执行，
避免把 82 个领域模块带进主 pytest 会话、污染懒加载/内核纯净相关用例的现场。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "domains" / "manifest.json"

#: 子进程内执行：物化全部插件，回吐 {插件名: 导出符号名排序列表} 的 JSON。
_SNIPPET = f"""
import json, sys
sys.path.insert(0, {str(ROOT)!r})
from src.plugin_api import get_resolver
d = json.load(open({str(MANIFEST)!r}, encoding='utf-8'))
r = get_resolver()
exports, errors = {{}}, []
for p in d['plugins']:
    try:
        exports[p['name']] = sorted(r.plugin(p['name']).exports().keys())
    except Exception as e:
        errors.append([p['name'], type(e).__name__, str(e)[:200]])
print(json.dumps({{'exports': exports, 'errors': errors}}))
"""


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _materialize_all_in_subprocess() -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"子进程物化失败：\n{proc.stderr[-800:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_every_domain_plugin_materializes_without_error():
    """每个插件都能被物化且不抛异常（import 期崩溃/坏依赖在此暴露）。"""
    payload = _materialize_all_in_subprocess()
    assert payload["errors"] == [], f"存在物化失败的插件：{payload['errors']}"


def test_every_plugin_exports_symbols_declared_in_manifest():
    """导出非空，且 manifest 的每一枚可加载符号都取得到（声明 ↔ 实现一致）。"""
    manifest = _manifest()
    payload = _materialize_all_in_subprocess()
    exports = payload["exports"]

    offenders: list[str] = []
    for p in manifest["plugins"]:
        name = p["name"]
        got = set(exports.get(name, []))
        declared = set(p["symbols"])
        if not got:
            offenders.append(f"{name}: 导出为空")
            continue
        missing = sorted(declared - got)
        if missing:
            offenders.append(f"{name}: 缺失符号 {missing[:5]}（共 {len(missing)}）")
    assert not offenders, "插件导出与清单声明漂移：\n" + "\n".join(offenders)


def test_plugin_count_matches_repo_facts():
    """烟雾覆盖面随插件数量增长——漏登记某插件会让本条先红。"""
    from scripts.repo_facts import facts

    manifest = _manifest()
    assert len(manifest["plugins"]) == facts()["domain_plugins"]
