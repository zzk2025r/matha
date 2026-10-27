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


def test_noncore_module_gated_by_flag(block_file, capsys):
    """灰度开关只影响遗留诊断后端，不影响主线 VM（实测记录，不是乐观推定）。

    实测两个事实（差异在解析层：开关决块内赋值生成 `Binding` 还是 `BinaryOp(op='=')`）：
      * `legacy-interp`：开关关时把 `s = 0` 当**比较**，块内 `s` 从未绑定 → 报
        「未定义变量 s」；开关开时当赋值 → [10]。
      * 主线 mbc VM：两种形状都按赋值编译，开关关也得到 [10]。

    主执行链已归一到 mbc，所以这里同时断言 CLI 端到端在两种开关下
    都能跑通（旧版本曾以此处「`matha run` 跑不通」为由只测解释器，现已修正）。
    """
    src = Path(block_file).read_text(encoding="utf-8")
    # 默认关闭：遗留后端失败，主线成功
    with pytest.raises(MathaRuntimeError):
        interpret(src)
    assert main(["run", block_file]) == 0
    assert capsys.readouterr().out.strip().endswith("10")

    features.set_feature("SCOPED_BLOCKS", True)
    out, _ = interpret(src)
    assert out == [10]
    assert main(["--feature", "SCOPED_BLOCKS", "run", block_file]) == 0
    assert capsys.readouterr().out.strip().endswith("10")


def test_scoped_blocks_flag_changes_assignment_node_only_in_source_layer(block_file):
    """该开关只改「块内赋值生成哪种节点」，主线 VM 对两种形状同价。

    实测：
      * 开关开 → 块内 `s = 0` 生成 `Binding(...)`；
      * 开关关 → 生成 `BinaryOp(op='=')`（遗留写法），解释器把它当比较，主线
        编译器把它当赋值——两边形状不同而主线输出与开关无关。

    把形状差异固定下来，以免今后有人拿「主线跳不过这个开关」当作 VM 的 bug：
    这是解释器侧的历史口径，而非语法分叉。
    """
    from src.kernel import exec_api
    from src.parser import parse

    src = Path(block_file).read_text(encoding="utf-8")
    features.clear_feature()
    off = repr(parse(src))
    features.set_feature("SCOPED_BLOCKS", True)
    on = repr(parse(src))
    assert "BinaryOp(op='=" in off and "Binding(target=Variable(name='s'" not in off
    assert "Binding(target=Variable(name='s'" in on
    # 主线：两种形状都能跑出结果，且与开关无关
    features.clear_feature()
    assert exec_api.run(src) == [10]
    features.set_feature("SCOPED_BLOCKS", True)
    assert exec_api.run(src) == [10]


def test_help_mentions_feature(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    assert "feature" in capsys.readouterr().out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
