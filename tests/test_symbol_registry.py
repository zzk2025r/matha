"""符号资源库宿主接入测试（Phase ③）"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import symbol_registry as sr


def test_counts_and_categories():
    assert sr.count() > 150
    assert sr.count() == len(sr.all_symbols())
    cats = sr.categories()
    assert cats == ["中文标点", "全角", "ASCII", "运算符", "数学", "希腊", "学科"]
    assert len(cats) == 7


def test_by_symbol_basic():
    pi = sr.by_symbol("π")
    assert pi is not None
    assert pi["中文名"] == "圆周率"
    assert pi["类别"] == "数学"
    assert "希腊" in pi["标签"]
    assert sr.by_symbol("∑") is not None
    assert sr.by_symbol("∞") is not None
    assert sr.by_symbol("℃") is not None
    assert sr.by_symbol("Ω") is not None


def test_by_category_matching():
    # 主类别匹配
    assert len(sr.by_category("数学")) > 0
    assert any(e["符号"] == "π" for e in sr.by_category("数学"))
    # 标签匹配（π 应出现在希腊类别查询中）
    assert any(e["符号"] == "π" for e in sr.by_category("希腊"))
    assert any(e["符号"] == "+" for e in sr.by_category("运算符"))
    assert any(e["符号"] == "，" for e in sr.by_category("中文标点"))


def test_definable_operators():
    d = set(sr.definable_operators())
    assert len(d) > 30
    for s in ["+", "-", "*", "/", "÷", "^", "**", "//"]:
        assert s in d
    for s in ["√", "∛", "∑", "∏"]:
        assert s in d
    for s in ["≈", "≠", "≡", "≤", "≥", "∝", "∈", "∉", "⊂", "⊇"]:
        assert s in d
    for s in ["⊥", "∥"]:
        assert s in d


def test_operator_declaration():
    assert sr.operator_declaration("π") == ""
    decl = sr.operator_declaration("≈")
    assert decl == "@define_op: ≈ = 5 | left"
    decl = sr.operator_declaration("+")
    assert decl == "@define_op: + = 5 | left"
    decl = sr.operator_declaration("∑")
    assert decl == "@define_op: ∑ = 3 | right"


def test_semantics():
    assert "求和" in sr.semantics("∑")
    assert "求积" in sr.semantics("∏")
    assert sr.semantics("NO_SUCH") == ""


def test_by_name_and_codepoint():
    assert sr.by_name("欧姆") is not None
    assert sr.by_name("欧姆")["符号"] == "Ω"
    assert sr.by_name("pi") is not None
    assert sr.by_name("pi")["符号"] == "π"
    # 别名匹配
    assert sr.by_name("派") is not None and sr.by_name("派")["符号"] == "π"
    # 码位：π → 960
    cp = sr.by_codepoint(960)
    assert cp is not None
    assert cp["符号"] == "π"


def test_caching_and_reload():
    before = sr.count()
    sr.clear_cache()
    after = sr.count()
    assert before == after
    # 重新加载后功能正常
    assert sr.by_symbol("∏") is not None
    assert sr.definable_operators() is not None
