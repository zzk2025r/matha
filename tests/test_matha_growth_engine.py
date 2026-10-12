"""MathaGrowthEngine 三角恒等式（P4）规则单元测试。

覆盖 14 条验证：
  - sin²x + cos²x → 1（含/不含空格两种写法）
  - sin(π/2 - x) → cos(x)（π / pi / 3.14159 三种写法）
  - cos(π/2 - x) → sin(x)（π / pi / 3.14159 三种写法）
  - sin(2x) → 2·sin(x)·cos(x)（两种变量）
  - tan(x) → sin(x)/cos(x)（两种变量）
  - 组合规则同时生效 + 成长管线接线
"""
from __future__ import annotations

import pytest

from src.matha_growth import MathaGrowthEngine

TRIG_CASES = [
    ("sin(x)**2 + cos(x)**2", "1", "sin²x+cos²x=1"),
    ("sin(a)**2+cos(a)**2", "1", "sin²a+cos²a=1（无空格）"),
    ("sin(pi/2 - x)", "cos(x)", "sin(pi/2-x)=cos(x)"),
    ("sin(π/2 - x)", "cos(x)", "sin(π/2-x)=cos(x)"),
    ("sin(3.14159/2 - x)", "cos(x)", "sin(3.14159/2-x)=cos(x)"),
    ("cos(pi/2 - x)", "sin(x)", "cos(pi/2-x)=sin(x)"),
    ("cos(π/2 - x)", "sin(x)", "cos(π/2-x)=sin(x)"),
    ("cos(3.14159/2 - x)", "sin(x)", "cos(3.14159/2-x)=sin(x)"),
    ("sin(2x)", "2*sin(x)*cos(x)", "sin(2x)=2sin(x)cos(x)"),
    ("sin(2a)", "2*sin(a)*cos(a)", "sin(2a)=2sin(a)cos(a)"),
    ("tan(x)", "sin(x)/cos(x)", "tan(x)=sin(x)/cos(x)"),
    ("tan(a)", "sin(a)/cos(a)", "tan(a)=sin(a)/cos(a)"),
    ("y = sin(π/2 - t) + tan(t)", "y = cos(t) + sin(t)/cos(t)", "组合规则同源应用"),
]


@pytest.mark.parametrize("source,expected,reason", TRIG_CASES)
def test_trig_identity_rule(source: str, expected: str, reason: str) -> None:
    engine = MathaGrowthEngine()
    improved, count = engine._apply_trig_identities(source)
    assert count >= 1, f"{reason}: 规则未触发"
    assert improved == expected, f"{reason}: 期望 {expected}, 实得 {improved}"


def test_trig_identity_in_growth_pipeline() -> None:
    """三角恒等式已接入成长管线（第 1 轮迭代生效）。"""
    engine = MathaGrowthEngine()
    report = engine._single_growth_iteration("y = sin(x)**2 + cos(x)**2", 1)
    assert any("三角恒等式" in s for s in report.optimizations_applied)
    assert report.improved_source == "y = 1"


def test_trig_identity_no_side_effect() -> None:
    """非三角表达式不受影响。"""
    engine = MathaGrowthEngine()
    improved, count = engine._apply_trig_identities("y = x * 3 + 1")
    assert count == 0
    assert improved == "y = x * 3 + 1"
