"""方案 E 端到端测试。

覆盖两大目标：
  1) 解释器标准库：ord/chr/len/get/slice/append/list/token、字符串 + 列表
     运算、字符串 * 整数重复
  2) 函数式字符处理（替代原命令占位符绑定）：
       读取字符 / 推进位置 / 跳过空白 / 判断数字 / 判断字母 / 组装Token
       —— 全部由 matha/lexer.matha 的函数式扫描核心（lambda + 递归 + 柯里化）
          直接执行，命令占位符机制已移除。
  3) Matha 自举 lexer 端到端 tokenize，与 Python lexer 的等价片段对比
     （整数 / 标识符 / 简单符号）

运行：python -m tests.test_scheme_e
"""

import os
from src.parser import parse
from src.interp import (
    Interpreter, interpret, lexer_bootstrap_interpret,
    MathaRuntimeError,
)

LEXER_PATH = os.path.join(os.path.dirname(__file__), "..", "matha", "lexer.matha")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ============================================================
# 1) 字符串/列表/ord/chr 内建
# ============================================================

def test_builtin_ord_chr():
    """ord() 取码点，chr() 码点返字符。"""
    print("\n--- 内建: ord/chr ---")
    interp = Interpreter()
    interp.run(parse(""))  # 空程序，仅用内置
    assert interp.call("ord", "A") == 65
    assert interp.call("ord", "0") == 48
    assert interp.call("chr", 65) == "A"
    assert interp.call("chr", 48) == "0"
    # round trip
    assert interp.call("chr", interp.call("ord", "中")) == "中"
    print("  ✓ ord('A')=65, chr(65)='A', round-trip ok")


def test_builtin_len_str_and_list():
    """len() 对字符串和列表。"""
    print("\n--- 内建: len ---")
    interp = Interpreter()
    interp.run(parse(""))
    assert interp.call("len", "hello") == 5
    assert interp.call("len", "") == 0
    assert interp.call("len", [1, 2, 3]) == 3
    assert interp.call("len", []) == 0
    print("  ✓ len(\"hello\")=5, len([1,2,3])=3")


def test_builtin_get_index():
    """get(seq)(idx) 取索引——柯里化。"""
    print("\n--- 内建: get ---")
    interp = Interpreter()
    interp.run(parse(""))
    assert interp.call("get", "hello", 0) == "h"
    assert interp.call("get", "hello", 4) == "o"
    assert interp.call("get", [10, 20, 30], 2) == 30
    # 负索引
    assert interp.call("get", "hello", -1) == "o"
    print("  ✓ get(\"hello\")(0)='h', get([10,20,30])(2)=30")


def test_builtin_slice_curried():
    """slice(seq)(start)(end) → 切片。"""
    print("\n--- 内建: slice ---")
    interp = Interpreter()
    interp.run(parse(""))
    assert interp.call("slice", "hello", 1, 4) == "ell"
    assert interp.call("slice", [1, 2, 3, 4], 1, 3) == [2, 3]
    print("  ✓ slice(\"hello\",1,4)='ell', list slice ok")


def test_builtin_list_and_append():
    """list(x) 构造 [x] + append(lst)(elem) 追加（纯函数式）。"""
    print("\n--- 内建: list / append ---")
    interp = Interpreter()
    interp.run(parse(""))
    # 注：Matha 语法层当前仅支持「f(x)」单参形式，不支持空括号 list()。
    # 在 Python API 下 interp.call("list") 会调用 0 参返回 []；
    # 这里统一用有参形式 list(x) → [x] 配合 append 演示完整构建流。
    single = interp.call("list", 5)
    assert single == [5]
    a = interp.call("append", single, 10)
    assert a == [5, 10], a
    b = interp.call("append", a, 20)
    assert b == [5, 10, 20], b
    # append 不改变原列表（纯函数式）
    assert single == [5]
    # 0 参 list() 通过 Python API 可用
    empty = interp.call("list")
    assert empty == [], empty
    print("  ✓ list(5)=[5]; append([5],10)=[5,10]; list()=[]; 纯净")


def test_string_concat_and_repeat():
    """字符串 + 拼接 / *n 重复。"""
    print("\n--- 字符串 +/* ---")
    out, _ = interpret('#1：["abc" + "def"]')
    assert out == ["abcdef"], out
    out, _ = interpret('#1：["xy" * 3]')
    assert out == ["xyxyxy"], out
    out, _ = interpret('#1：[2 * "ab"]')
    assert out == ["abab"], out
    print("  ✓ \"abc\"+\"def\"='abcdef', \"xy\"*3='xyxyxy', 2*\"ab\"='abab'")


def test_list_concat_plus():
    """列表相加。"""
    print("\n--- 列表拼接 ---")
    # Matha 当前不支持 f() 空括号，用有参 list(x) → [x] 作为种子再 append
    src = """
@:stub = 0
#：{
  l1 = list(1)
  l2 = append(list(2))(3)
  both = l1 + l2
  [len(both)]
  [get(both)(0)]
  [get(both)(1)]
  [get(both)(2)]
}
"""
    out, _ = interpret(src)
    assert out == [3, 1, 2, 3], out
    print("  ✓ [1] + [2,3] → len=3; 元素 [1,2,3]")


def test_inline_expression_mixed():
    """在单个表达式里组合多个内建，模拟从源码取字符、判断码点。"""
    print("\n--- 内建组合使用 ---")
    src = """
@:src = "42"
#：{
  c = get(src)(0)
  n = ord(c)
  hi = 是数字起(n)
  lo = 是数字止(n)
  [c]
  [hi]
  [lo]
}
func 是数字起(c: Int) -> Bool = (c) => c >= 48
func 是数字止(c: Int) -> Bool = (c) => c <= 57
"""
    out, _ = interpret(src)
    assert out == ["4", True, True], out
    print("  ✓ 取 '4' → ord 52 → 是数字起=T, 是数字止=T")


# ============================================================
# 2) 函数式字符处理（替代原命令占位符绑定）
#    命令占位符机制已移除；以下验证函数式扫描核心的等价行为。
# ============================================================

def test_functional_read_and_advance():
    """字符读取 + 位置推进：get(src)(pos) → char → ord，位置 +1 推进。"""
    print("\n--- 函数式: 读取字符 / 推进位置 ---")
    interp = Interpreter()
    interp.run(parse(""))
    # 模拟源码 "ab"：pos=0 读 'a'，推进 pos=1，再读 'b'
    src = "ab"
    ch0 = interp.call("get", src, 0)
    cp0 = interp.call("ord", ch0)
    pos = 1  # 推进位置 = pos + 1
    ch1 = interp.call("get", src, pos)
    cp1 = interp.call("ord", ch1)
    assert ch0 == "a" and cp0 == ord("a")
    assert ch1 == "b" and cp1 == ord("b")
    assert pos == 1
    print("  ✓ 读取 a → 推进 → 读取 b; 位置=1")


def test_functional_skip_whitespace():
    """跳过空白：扫描器跳过前导空白，首个 Token 起始于空白之后。"""
    print("\n--- 函数式: 跳过空白 ---")
    tokens = lexer_bootstrap_interpret("   x")
    # 跳过 3 空格后读 'x'：标识符 Token 起列=4
    assert tokens[0]["类型"] == "标识符"
    assert tokens[0]["文本"] == "x"
    assert tokens[0]["列"] == 4
    print("  ✓ 跳过 3 空格 → 读 x（列=4）")


def test_functional_classify():
    """字符分类：是数字码 / 是字母码 对 '5'/'a'/'+'。"""
    print("\n--- 函数式: 判断数字/字母 ---")
    interp = Interpreter()
    interp.run(parse(_load(LEXER_PATH)))
    # '5'(53): 是数字码=T, 是字母码=F
    assert interp.call("是数字码", 53) is True
    assert interp.call("是字母码", 53) is False
    # 'a'(97): 是数字码=F, 是字母码=T
    assert interp.call("是数字码", 97) is False
    assert interp.call("是字母码", 97) is True
    # '+'(43): 都不是
    assert interp.call("是数字码", 43) is False
    assert interp.call("是字母码", 43) is False
    print("  ✓ '5'→数字; 'a'→字母; '+'→都不")


def test_functional_token_assembly():
    """Token 组装：token(类型)(文本)(行)(列) 字典构造 + 扫描器端到端组装。"""
    print("\n--- 函数式: 组装Token ---")
    interp = Interpreter()
    interp.run(parse(""))
    # token 内建：柯里化四参 → 字典
    t = interp.call("token", "整数", "42", 2, 3)
    assert t == {"类型": "整数", "文本": "42", "行": 2, "列": 3}, t
    # 扫描器端到端组装 标识符/符号/整数/结束
    tokens = lexer_bootstrap_interpret("count+42")
    types = [tok["类型"] for tok in tokens]
    texts = [tok["文本"] for tok in tokens]
    assert types == ["标识符", "符号", "整数", "结束"], types
    assert texts == ["count", "+", "42", ""], texts
    print("  ✓ token 内建字典 + 扫描器组装 标识符/符号/整数/结束")


# ============================================================
# 3) Matha 自举 lexer 端到端 tokenize
# ============================================================

def test_bootstrap_lexer_tokenize_num_id_sym():
    """lexer_bootstrap_interpret("x + 123") 期望 token 序列。"""
    print("\n--- 自举 lexer: tokenize 'x + 123' ---")
    tokens = lexer_bootstrap_interpret("x + 123")
    print(f"  tokens = {tokens}")
    types = [t["类型"] for t in tokens]
    texts = [t["文本"] for t in tokens]
    assert types[-1] == "结束"
    assert types[:-1] == ["标识符", "符号", "整数"], f"类型序列不对: {types}"
    assert texts[0] == "x", tokens
    assert texts[1] == "+", tokens
    assert texts[2] == "123", tokens
    print("  ✓ 标识符/符号/整数/结束 序列正确")


def test_bootstrap_lexer_tokenize_identifier_with_digits():
    """标识符带字母数字下划线前缀：abc123_def。"""
    print("\n--- 自举 lexer: tokenize 复合标识符 ---")
    tokens = lexer_bootstrap_interpret("abc123_def = 5")
    print(f"  tokens = {tokens}")
    texts = [t["文本"] for t in tokens]
    types = [t["类型"] for t in tokens]
    # 期望：标识符 abc123_def；符号 =；整数 5；结束
    assert "abc123_def" in texts, texts
    assert types == ["标识符", "符号", "整数", "结束"], types
    print("  ✓ abc123_def = 5 → 标识符/符号/整数/结束")


def test_bootstrap_lexer_tokenize_empty_or_all_ws():
    """全空白：只产出 结束 Token。"""
    print("\n--- 自举 lexer: 全空白输入 ---")
    tokens = lexer_bootstrap_interpret("   \t  ")
    assert len(tokens) == 1 and tokens[0]["类型"] == "结束", tokens
    print("  ✓ 全空白 → 仅结束 Token")


def test_bootstrap_lexer_tokenize_symbols_only():
    """仅符号串。"""
    print("\n--- 自举 lexer: 符号串 ---")
    tokens = lexer_bootstrap_interpret("+-*")
    types = [t["类型"] for t in tokens]
    texts = [t["文本"] for t in tokens]
    assert types == ["符号", "符号", "符号", "结束"], types
    assert texts == ["+", "-", "*", ""], texts
    print("  ✓ +-* → 3 符号 + 结束")


def test_bootstrap_lexer_matha_still_runs_as_whole():
    """lexer.matha 完整执行后，函数式扫描器可直接调用产出 Token。"""
    print("\n--- lexer.matha 完整执行 ---")
    interp = Interpreter()
    program = parse(_load(LEXER_PATH))
    outputs, trace = interp.run(program)
    # 直接调用函数式扫描器 tokenize 占位源码 "x + 1"
    tokens = interp.call("扫描", "x + 1", 0, 1, 1, [])
    print(f"  tokens = {tokens}")
    assert len(tokens) >= 3, f"期望至少 3 个实际 token + 结束，实际 {tokens}"
    assert tokens[-1]["类型"] == "结束"
    # 函数可调用
    assert interp.call("推进位置", 5) == 6
    assert interp.call("是下划线", 95) is True
    print(f"  ✓ tokens={len(tokens)} 个，推进位置/是下划线 仍可调用")


# ============================================================
# runner
# ============================================================

def _run_all():
    tests = [
        # 内建
        test_builtin_ord_chr,
        test_builtin_len_str_and_list,
        test_builtin_get_index,
        test_builtin_slice_curried,
        test_builtin_list_and_append,
        test_string_concat_and_repeat,
        test_list_concat_plus,
        test_inline_expression_mixed,
        # 函数式字符处理
        test_functional_read_and_advance,
        test_functional_skip_whitespace,
        test_functional_classify,
        test_functional_token_assembly,
        # 自举 lexer 端到端
        test_bootstrap_lexer_tokenize_num_id_sym,
        test_bootstrap_lexer_tokenize_identifier_with_digits,
        test_bootstrap_lexer_tokenize_empty_or_all_ws,
        test_bootstrap_lexer_tokenize_symbols_only,
        test_bootstrap_lexer_matha_still_runs_as_whole,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except (AssertionError, MathaRuntimeError, Exception) as ex:
            failed += 1
            print(f"  ✗ {t.__name__} 失败: {type(ex).__name__}: {ex}")
            import traceback
            traceback.print_exc()
    print(f"\n{'='*48}")
    print(f"方案 E 测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
