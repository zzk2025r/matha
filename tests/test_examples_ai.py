# -*- coding: utf-8 -*-
"""examples/ai 可运行示例门禁锁（阶段 4-6）。

背景：examples/ai/README.md 历史上六个 Python 风格伪代码块
（create_neural_network(input_size=784)/nn.forward/create_convnet 等）
不是合法 Matha，无一可运行。本轮重写为四个真跑示例并挂本锁：
干净子进程经 exec_api 主执行链运行每个 .matha 文件，输出与手算值
对拍（遵「sys.modules 断言起子进程」纪律）。

预期输出（手算）：
  - neural_network：训练 100 轮真读数，前向/预测 ∈ (0,1)；
  - data_pipeline：准确率 0.8；两半等差列归一化后皆 [[0,0],[1,1]]；
  - genetic_algo：[50.0, "a b", "func f(x) = x + 3"]；
  - ai_framework：矩阵乘法 [[19,22],[43,50]]；张量 shape=(2,3) 全零。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "examples" / "ai"

_RUN_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = open(%r, encoding="utf-8").read()
out = exec_api.run(src)
%s
print("EXAMPLE_OK")
"""


def _run_example(name: str, asserts: str) -> None:
    snippet = _RUN_SNIPPET % (str(ROOT), str(AI_DIR / name), asserts)
    proc = subprocess.run([sys.executable, "-c", snippet],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "EXAMPLE_OK" in proc.stdout


def test_example_files_present():
    """漂移锁：四个示例 + 数据文件齐全（README 主张的文件面）。"""
    assert {p.name for p in AI_DIR.glob("*.matha")} == {
        "neural_network.matha", "data_pipeline.matha",
        "genetic_algo.matha", "ai_framework.matha",
    }
    assert (AI_DIR / "data.csv").is_file()


def test_neural_network_example():
    _run_example("neural_network.matha", """
r, fwd, pred = out
assert r.epochs_trained == 100 and len(r.loss_history) == 100
assert r.final_loss == r.loss_history[-1] <= r.loss_history[0]
assert isinstance(fwd, list) and len(fwd) == 1 and 0.0 < fwd[0] < 1.0
assert isinstance(pred, list) and len(pred) == 1 and 0.0 < pred[0] < 1.0
""")


def test_data_pipeline_example():
    _run_example("data_pipeline.matha", """
acc, parts = out
assert abs(acc - 0.8) < 1e-12
train, test = parts
assert train._data == [[0.0, 0.0], [1.0, 1.0]]
assert test._data == [[0.0, 0.0], [1.0, 1.0]]
""")


def test_genetic_algo_example():
    _run_example("genetic_algo.matha", """
assert out == [50.0, "a b", "func f(x) = x + 3"], out
""")


def test_ai_framework_example():
    _run_example("ai_framework.matha", """
mm, t = out
assert mm == [[19, 22], [43, 50]], mm
assert t.shape == (2, 3) and t.data == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
""")