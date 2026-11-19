# -*- coding: utf-8 -*-
"""阶段 29d Track B 结构锁：docs/selfhost_matrix.json 快照轻锁（pytest 门禁）。

全量重跑对拍（--check）为重档 lane，不在常规 pytest 门禁：
  python scripts/selfhost_matrix.py --check
结构锁判据：快照在位 + 文件清单与语料枚举一致（五目录 rglob("*.matha")，
boot 链 5 文件排除）+ summary 六分类算术闭合 + 条目无 unknown 形态。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import selfhost_matrix as sm  # noqa: E402


def test_snapshot_structure():
    ok, msg = sm.structure_check()
    assert ok, msg


def test_boot_chain_files_excluded():
    files = sm.corpus_files()
    assert files, "语料枚举为空"
    for bf in sm.BOOT_FILES:
        assert bf not in files, f"boot 链文件不应入 sweep: {bf}"


def test_summary_arithmetic_closed():
    snap = sm.load_snapshot()
    s = snap["summary"]
    assert set(s.keys()) == {
        "files", "both_ok_equal", "both_ok_differ", "boot_err_host_ok",
        "boot_ok_host_err", "both_err", "timeout"}, f"summary 键形 {set(s.keys())}"
    total = sum(v for k, v in s.items() if k != "files")
    assert total == s["files"], f"汇总算术不闭合: {s}"
    assert s["files"] == len(snap["files"]), "files 计数与条目数不一致"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
