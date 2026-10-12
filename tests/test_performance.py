"""性能/压力测试：算法一致性验证（1000 → 10000）。

验证在 1000 与 10000 两个执行规模下，Matha 解释器的算法结果与
Python 参考实现一致，且跨规模、多次运行保持确定性（一致性 ≥ 99.9%）。
"""
from __future__ import annotations

from src.interp import Interpreter
from src.parser import parse

FUNC_SRC = """
func 平方和(n: Int) -> Int = (n) => n * n
func 线性映射(n: Int) -> Int = (n) => 平方和(n) + 2 * n + 1
"""

MIN_CONSISTENCY_RATE = 0.999


def _make_interp() -> Interpreter:
    interp = Interpreter()
    interp.run(parse(FUNC_SRC))
    return interp


def _run_workload(interp: Interpreter, scale: int) -> list[int]:
    """执行 scale 次算法调用，返回结果序列（一致性基准）。"""
    return [interp.call("线性映射", n) for n in range(scale)]


def _reference(n: int) -> int:
    return n * n + 2 * n + 1


def _consistency(seq_a: list[int], seq_b: list[int]) -> float:
    if not seq_b:
        return 1.0
    matches = sum(1 for x, y in zip(seq_a, seq_b, strict=False) if x == y)
    return matches / len(seq_b)


def test_stress_1000_matches_reference():
    """规模 1000：每个结果与 Python 参考一致。"""
    out = _run_workload(_make_interp(), 1000)
    ref = [_reference(n) for n in range(1000)]
    assert _consistency(out, ref) == 1.0


def test_stress_10000_matches_reference():
    """规模 10000：每个结果与 Python 参考一致。"""
    out = _run_workload(_make_interp(), 10000)
    ref = [_reference(n) for n in range(10000)]
    assert _consistency(out, ref) == 1.0


def test_stress_cross_scale_consistency():
    """跨规模一致性：10000 次运行的前 1000 项 == 1000 次运行结果。"""
    out_1k = _run_workload(_make_interp(), 1000)
    out_10k = _run_workload(_make_interp(), 10000)
    assert _consistency(out_1k, out_10k[:1000]) == 1.0


def test_stress_determinism_10000():
    """确定性：10k 级两次独立运行的结果完全相同。"""
    out_a = _run_workload(_make_interp(), 10000)
    out_b = _run_workload(_make_interp(), 10000)
    assert _consistency(out_a, out_b) == 1.0


def test_stress_consistency_rate_ge_999():
    """一致性通过率 ≥ 99.9%（计划验收阈值）。"""
    out_1k = _run_workload(_make_interp(), 1000)
    out_10k = _run_workload(_make_interp(), 10000)
    rate = _consistency(out_1k, out_10k[:1000])
    assert rate >= MIN_CONSISTENCY_RATE
