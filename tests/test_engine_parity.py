# -*- coding: utf-8 -*-
"""新旧引擎差分测试：递归解释器 vs 显式栈引擎（StackEngine）。

对同一批 Matha 源码，分别
  - OLD：默认递归路径（features STACK_ENGINE 关闭）
  - NEW：显式栈引擎（features STACK_ENGINE 开启）
运行，要求 ``(outputs, trace)`` 完全一致；若两者都抛错，则要求异常类型与
消息一致（错误路径也是契约的一部分）。

这是「增量绞杀」的安全网：任何一次迁移都必须让本测试保持全绿。

运行：python -m tests.test_engine_parity
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features
from src.parser import parse
from src.interp import Interpreter


def _run(src: str, engine: bool):
    """运行源码，返回 (outputs, trace) 或 ("ERR", 类型名, 消息)。"""
    features.clear_feature()
    if engine:
        features.set_feature("STACK_ENGINE", True)
    try:
        out, trace = Interpreter().run(parse(src))
        return (list(out), list(trace))
    except Exception as e:  # noqa: BLE001
        return ("ERR", type(e).__name__, str(e))
    finally:
        features.clear_feature()


# ============================================================
# 差分语料：覆盖各表达式/语句/调用/控制流形态
# ============================================================

CORPUS = {
    # ---- 字面量与算术 ----
    "int": "#1：[42]",
    "float": "#1：[3.14]",
    "string": '#1：["hi"]',
    "bool": "#1：[真]",
    "arith": "#1：[2 + 3 * 4 - 1]",
    "div": "#1：[10 / 4]",
    "floordiv": "#1：[10 // 3]",
    "mod": "#1：[10 % 3]",
    "pow_caret": "输出(2 ^ 10)",
    "pow_star": "输出(2 ** 8)",
    "unary_minus": "输出(-(3 + 4))",
    "sqrt_prefix": "输出(^16)",
    "sqrt_float": "输出(^2.25)",
    "cbrt_prefix": "输出(∛27)",
    "angle_prefix": "输出(<<90)",
    "bit_not": "输出(~5)",
    "incr": "输出(++5)",

    # ---- 比较与逻辑 ----
    "eq": "输出(3 == 3)",
    "neq": "输出(3 != 4)",
    "lt_gt": "输出((2 < 3) && (5 > 4))",
    "and_or": "输出(真 && 假 || 真)",
    "strict_eq": "输出(1 === 1)",
    "strict_neq": "输出(1 !== 2)",
    "null_coalesce": "输出(null ?? 7)",
    "is_op": "输出(1 is 1)",

    # ---- 位运算 ----
    "bit_and": "输出(6 & 3)",
    "bit_or": "输出(6 | 3)",
    "bit_xor": "输出(6 ⊕ 3)",
    "shl": "输出(1 << 4)",
    "shr": "输出(-8 >> 1)",

    # ---- 变量与绑定 ----
    "bind_simple": "let x = 5\n输出(x + 1)",
    "bind_chain": "let a = 1\nlet b = a + 1\nlet c = b + 1\n输出(c)",
    "top_binding": "y = 100\n输出(y)",

    # ---- 集合 / 列表 / 字典 ----
    "set_dedup": '输出(构造集合("enumeration", 0, [1, 2, 2, 3]))',
    "set_order": '输出(构造集合("enumeration", 0, [3, 1, 3, 2]))',
    "set_empty": '输出(构造集合("enumeration", 0, []))',
    "set_literal_len": "let s = {1, 2, 2}\n输出(len(s))",
    "set_membership": "let s = {1, 2, 2}\n输出(2 in s)",
    "set_union": "输出({1, 2} ∪ {2, 3})",
    "set_inter": "输出({1, 2, 3} ∩ {2, 3, 4})",
    "set_diff": "输出({1, 2, 3} ⊖ {2})",
    "list_index": "输出([1, 2, 3][1])",
    "list_len": "输出(len([1, 2, 3, 4]))",
    "len_str": '输出(len("hello"))',
    "dict_access": "let d = {a: 1, b: 2}\n输出(d[a])",

    # ---- 集合理解 ----
    "set_comp": "let s = {x * 2 | x >> {1, 2, 3}}\n输出(len(s))",
    "set_comp_filter": "let s = {x | x >> {1, 2, 3, 4} | x > 2}\n输出(len(s))",

    # ---- 函数 ----
    "func_single": "func inc(c) = (c) => c + 1\n输出(inc(5))",
    "func_curried": "func add(a) = (a) => (b) => a + b\n输出(add(3)(4))",
    "func_closure": "func mk(n) = (n) => (x) => n + x\nlet f = mk(10)\n输出(f(5))",
    "func_recursive": (
        "func fact(n) -> Int = (n) =>\n"
        "  if n <= 1 then 1 else n * fact(n - 1)\n"
        "输出(fact(6))"
    ),
    "func_rec_multi": (
        "func fib(n) -> Int = (n) =>\n"
        "  if n < 2 then n else fib(n - 1) + fib(n - 2)\n"
        "输出(fib(10))"
    ),
    "lambda_let": "let f = (x) => x * x\n输出(f(9))",
    "higher_order": "输出((x) => x + 1)(41)",

    # ---- 控制流 ----
    "if_expr": "输出(if 真 then 1 else 2)",
    "ternary": "输出(真 ? 10 : 20)",
    "if_stmt": "if 3 > 2 { 输出(1) } else { 输出(2) }",
    "if_elseif": "if 假 { 输出(1) } else if 真 { 输出(2) } else { 输出(3) }",
    "while_sum": (
        "let i = 0\nlet s = 0\n"
        "while i < 5 { s = s + i i = i + 1 }\n"
        "输出(s)"
    ),
    "for_sum": "let s = 0\nfor x in [1, 2, 3, 4] { s = s + x }\n输出(s)",
    "break": (
        "let i = 0\nlet s = 0\n"
        "while 真 { if i >= 3 { break } s = s + i i = i + 1 }\n"
        "输出(s)"
    ),
    "continue": (
        "let s = 0\n"
        "for x in [1, 2, 3, 4, 5] { if x == 3 { continue } s = s + x }\n"
        "输出(s)"
    ),
    "match": 'match 3 {\n| 1 => 输出("a")\n| 3 => 输出("b")\n| _ => 输出("c")\n}',
    "match_default": 'match 9 {\n| 1 => 输出("a")\n| _ => 输出("c")\n}',

    # ---- 内建 ----
    "ord_chr": "输出(chr(ord(\"A\")))",
    "append": "输出(append([1, 2])(3))",
    "get": "输出(get([10, 20, 30])(2))",
    "slice_builtin": '输出(slice([1,2,3,4])(1)(3))',
    "range": "输出(len(range(0, 5)))",
    "map": "输出(映射([1, 2, 3])((x) => x * 2))",
    "filter": "输出(过滤([1, 2, 3, 4])((x) => x > 2))",
    "typeof": "输出(typeof(42))",
    "str_func": "输出(str(123))",

    # ---- 错误路径（须两端一致抛错）----
    "err_undef_var": "输出(不存在的变量)",
    "err_div_zero": "输出(1 / 0)",
    "err_bad_index": "输出([1, 2][9])",
    "err_type": '输出(1 - "a")',

    # ---- 多语句 / 嵌套 ----
    "nested_block": "let r = if 真 { 1 + 2 } else { 3 + 4 }\n输出(r)",
    "nested_func": (
        "func outer(a) = (a) =>\n"
        "  let inner = (b) => b * 2\n"
        "  inner(a) + 1\n"
        "输出(outer(5))"
    ),
}


def test_all_corpus_parity():
    mismatches = []
    for name, src in CORPUS.items():
        old = _run(src, engine=False)
        new = _run(src, engine=True)
        if _norm(old) != _norm(new):
            mismatches.append((name, src, old, new))
    if mismatches:
        lines = [f"差分不一致 {len(mismatches)} 例:"]
        for name, src, old, new in mismatches:
            lines.append(f"\n[{name}] {src!r}")
            lines.append(f"  OLD: {old}")
            lines.append(f"  NEW: {new}")
        raise AssertionError("\n".join(lines))


def _norm(result):
    # 输出/路径值统一为字符串比较，规避 int/float 等 repr 差异噪音
    if isinstance(result, tuple) and len(result) == 3 and result[0] == "ERR":
        return ("ERR", result[1], result[2])
    out, trace = result
    return ([str(v) for v in out], [str(t) for t in trace])


if __name__ == "__main__":
    test_all_corpus_parity()
    print(f"✓ 新旧引擎差分一致：{len(CORPUS)} 例全部匹配")
