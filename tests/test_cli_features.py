# -*- coding: utf-8 -*-
"""CLI 特性开关（`matha --feature NAME[=on|off]` / `matha features`）测试。

覆盖默认关闭、CLI 开启、强制关闭与灰度推进的最小用例（先跑非核心模块验证）。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features
from src.interp import MathaRuntimeError, interpret
from src.matha_main import main

_BLOCK_SRC = """func sum_list(xs: List) -> Int = (xs) => {
  s = 0
  for x in xs {
    s = s + x
  }
  return s
}
[sum_list([1, 2, 3, 4])]
"""


@pytest.fixture(autouse=True)
def _isolate():
    keys = ("MATHA_FEATURE_SCOPED_BLOCKS", "MATHA_FEATURES")
    saved = {k: os.environ.pop(k, None) for k in keys}
    features.clear_feature()
    try:
        yield
    finally:
        features.clear_feature()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@pytest.fixture
def block_file(tmp_path):
    p = tmp_path / "block.matha"
    p.write_text(_BLOCK_SRC, encoding="utf-8")
    return str(p)


def test_features_list_default_off(capsys):
    assert main(["features"]) == 0
    out = capsys.readouterr().out
    assert "SCOPED_BLOCKS" in out and "off" in out


def test_features_list_reflects_cli_flag(capsys):
    assert main(["--feature", "SCOPED_BLOCKS", "features"]) == 0
    assert "on" in capsys.readouterr().out


def test_cli_off_override_beats_earlier_set():
    features.set_feature("SCOPED_BLOCKS", True)
    assert main(["--feature", "SCOPED_BLOCKS=off", "features"]) == 0
    assert features.scoped_blocks() is False


def test_cli_on_sets_flag():
    # `--feature` 经 CLI 落到进程内开关（优先级最高于环境变量）
    assert main(["--feature", "SCOPED_BLOCKS", "features"]) == 0
    assert features.scoped_blocks() is True


def test_noncore_module_gated_by_flag(block_file):
    """灰度推进：非核心模块先开开关验证，随后回退默认（关闭）行为。

    注：`matha run` 的自举解析路径在本环境受 `调用捕获` 缺失所阻（既有限制），
    故此处直接经 Python 解释器执行同一模块源。
    """
    src = Path(block_file).read_text(encoding="utf-8")
    # 默认关闭 → 块内 `s = 0` 解析为等于比较 → 运行失败
    with pytest.raises(MathaRuntimeError):
        interpret(src)
    features.set_feature("SCOPED_BLOCKS", True)
    out, _ = interpret(src)
    assert out == [10]


def test_help_mentions_feature(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    assert "feature" in capsys.readouterr().out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
