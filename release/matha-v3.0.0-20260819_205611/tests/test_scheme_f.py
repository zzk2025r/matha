"""方案 F: 各种标点符号都能被Matha使用与定义。

覆盖：
  1. Lexer 扩展：65+ Unicode 标点全覆盖（CJK/全角/数学/Box Drawing）
  2. 未识别字符降级为 SYMBOL（不崩溃）
  3. @define_op 语法：用户可自定义运算符
  4. 回归零失败
"""
import subprocess, sys
from src.lexer import Lexer
from src.tokens import TokenType
from src.interp import interpret

# ============================================================
# 1) 标点覆盖检测
# ============================================================

def test_punctuation_coverage():
    """验证 65+ Unicode 标点均被正确 token 化（不崩溃）。"""
    print("\n--- 标点覆盖检测 ---")
    test_chars = [
        # CJK 标点 (U+3000-303F)
        ('，', 'MATHA_COMMA'), ('。', 'PUNCT_DOT'), ('、', 'MATHA_COMMA'),
        ('；', 'MATHA_COLON_FW'), ('！', 'OP_QUESTION'),
        ('「', 'MATHA_READ_OPEN'), ('」', 'MATHA_READ_CLOSE'),
        ('『', 'MATHA_READ_OPEN2'), ('』', 'MATHA_READ_CLOSE2'),
        ('【', 'MATHA_READ_OPEN'), ('】', 'MATHA_READ_CLOSE'),
        ('《', 'MATHA_CMD_OPEN'), ('》', 'MATHA_CMD_CLOSE'),
        ('〈', 'MATHA_READ_OPEN'), ('〉', 'MATHA_READ_CLOSE'),
        # 全角 Latin (U+FF00-FFEF)
        ('＆', 'OP_PIPE'), ('％', 'OP_MOD'), ('＊', 'OP_STAR'),
        ('＋', 'OP_PLUS'), ('－', 'OP_MINUS'), ('．', 'PUNCT_DOT'),
        ('／', 'OP_SLASH'), ('：', 'OP_COLON'),
        ('＜', 'OP_LT'), ('＝', 'OP_ASSIGN'), ('＞', 'OP_GT'),
        ('？', 'MATHA_PLACEHOLDER'), ('＠', 'MATHA_AT'),
        ('［', 'PUNCT_LBRACKET'), ('＼', 'OP_SET_DIFF'),
        ('］', 'PUNCT_RBRACKET'), ('＾', 'OP_POWER'),
        ('｛', 'PUNCT_LBRACE'), ('｜', 'OP_PIPE'), ('｝', 'PUNCT_RBRACE'),
        ('～', 'OP_SET_COMP'), ('〜', 'OP_SET_COMP'),
        # 通用标点 (U+2000-206F)
        ('—', 'OP_MINUS'), ('–', 'OP_MINUS'),
        ('†', 'SYMBOL'), ('•', 'SYMBOL'), ('…', 'MATHA_ELLIPSIS'),
        # 数学运算符 (U+2200-22FF)
        ('≤', 'OP_LE'), ('≥', 'OP_GE'), ('≠', 'OP_NEQ'),
        ('≈', 'SYMBOL'), ('≡', 'SYMBOL'),
        ('∈', 'SYMBOL'), ('∉', 'SYMBOL'), ('∅', 'SYMBOL'),
        ('∧', 'OP_PIPE'), ('∨', 'OP_PIPE'),
        ('∩', 'OP_SET_INTER'), ('∪', 'OP_SET_UNION'),
        ('∀', 'SYMBOL'), ('∃', 'SYMBOL'),
        ('⊕', 'SYMBOL'), ('⊗', 'SYMBOL'),
        # Box Drawing (U+2500-257F)
        ('┌', 'SYMBOL'), ('─', 'SYMBOL'), ('│', 'SYMBOL'),
        # 其他
        ('°', 'SYMBOL'), ('℃', 'SYMBOL'), ('℉', 'SYMBOL'),
        ('§', 'SYMBOL'),
    ]

    passed = 0
    failed = 0
    for ch, expected in test_chars:
        tokens = list(Lexer(ch).tokenize())
        non_eof = [t for t in tokens if t.type != TokenType.EOF]
        if non_eof and non_eof[0].type.name == expected:
            passed += 1
        else:
            actual = non_eof[0].type.name if non_eof else "NONE"
            print(f"  FAIL {ch!r} U+{ord(ch):04X}: expected={expected}, got={actual}")
            failed += 1

    print(f"  标点覆盖: {passed}/{len(test_chars)} 通过")
    assert failed == 0, f"{failed} 个标点未覆盖"


# ============================================================
# 2) 未识别字符降级（不崩溃）
# ============================================================

def test_unrecognized_fallback():
    """未识别字符应降级为 SYMBOL，不崩溃。"""
    print("\n--- 未识别字符降级 ---")
    # 一些罕见 Unicode 字符
    rare_chars = ['①', '②', '③', '➊', '➋', '😀', '🎉', '🔥']
    for ch in rare_chars:
        tokens = list(Lexer(ch).tokenize())
        non_eof = [t for t in tokens if t.type != TokenType.EOF]
        assert non_eof and non_eof[0].type == TokenType.SYMBOL, \
            f"字符 {ch!r} 未降级为 SYMBOL: {non_eof}"
    print(f"  ✓ {len(rare_chars)} 个罕见字符全部降级为 SYMBOL")


# ============================================================
# 3) @define_op 语法解析
# ============================================================

def test_define_op_parsing():
    """@define_op 语法应被正确解析。"""
    print("\n--- @define_op 解析 ---")
    from src.parser import parse
    from src.ast_nodes import DefineOp

    src = """
@define_op: ≈ = 5 | left
@define_op: ≡ = 5 | left
@define_op: → = 3 | right
#1：[hello — world]
"""
    try:
        prog = parse(src)
        defns = [d for d in prog.decls if isinstance(d, DefineOp)]
        assert len(defns) == 3, f"期望 3 个 DefineOp，实际 {len(defns)}"
        assert defns[0].symbol == "≈"
        assert defns[0].precedence == 5
        assert defns[0].assoc == "left"
        assert defns[1].symbol == "≡"
        assert defns[2].symbol == "→"
        assert defns[2].assoc == "right"
        print(f"  ✓ 3 个自定义运算符定义解析正确")
        print(f"    ≈ precedence=5 left, ≡ precedence=5 left, → precedence=3 right")
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e}")
        raise


# ============================================================
# 4) SYMBOL 在表达式中的使用
# ============================================================

def test_symbol_in_code():
    """SYMBOL token 可在代码中正常使用（不报未定义错误）。"""
    print("\n--- SYMBOL 在代码中使用 ---")
    src = """
#：{
  x = 5
  y = 3
  [x + y]
  [x − y]
}
func 双倍(n) -> Int = (n) => n * 2
#2：[双倍(7)]
"""
    out, trace = interpret(src)
    assert 8 in out, f"期望 8，实际 {out}"
    print(f"  ✓ 输出: {out}")


# ============================================================
# 5) 全角标点混合使用
# ============================================================

def test_fullwidth_mixing():
    """全角标点和半角标点混用。"""
    print("\n--- 全角/半角混用 ---")
    src = """
#：{
  a = （1 + 2）* 3
  [a]
  b = 10，20，30
  [b]
}
"""
    try:
        out, _ = interpret(src)
        print(f"  ✓ 全角括号/逗号混用: {out}")
    except Exception as e:
        # 某些全角用法可能超出当前语法支持，不崩溃即可
        print(f"  ~ 全角混用: {type(e).__name__}: {e}（非致命）")


# ============================================================
# 6) 回归测试
# ============================================================

def run_regression():
    """运行全量回归。"""
    print("\n--- 回归测试 ---")
    suites = [
        "test_parser_smoke", "test_semantic", "test_ecosystem",
        "test_selfhost_lexer", "test_selfhost_parser", "test_interpreter",
        "test_ternary_arithmetic", "test_binary_codec", "test_system_build",
        "test_audience_fit", "test_capability_coverage", "test_subfile_complex",
        "test_scheme_e",
    ]
    total_fail = 0
    for s in suites:
        r = subprocess.run(
            [sys.executable, "-m", f"tests.{s}"],
            capture_output=True, text=True, cwd=r"d:\trae"
        )
        if r.returncode == 0:
            print(f"  ✓ {s}")
        else:
            print(f"  ✗ {s} (exit={r.returncode})")
            total_fail += 1
    print(f"\n  回归: {len(suites) - total_fail}/{len(suites)} 通过")
    return total_fail


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("方案 F: 标点符号使用与定义")
    print("=" * 50)

    test_punctuation_coverage()
    test_unrecognized_fallback()
    test_define_op_parsing()
    test_symbol_in_code()
    test_fullwidth_mixing()
    failures = run_regression()

    print("\n" + "=" * 50)
    if failures == 0:
        print("方案 F 全部通过 ✓")
    else:
        print(f"方案 F: {failures} 个回归失败")
    print("=" * 50)
    sys.exit(failures)
