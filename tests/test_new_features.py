# -*- coding: utf-8 -*-
"""Matha 新功能集成测试：位运算、集合运算、严格比较、空值合并、可选链、Struct 字段访问。"""
import sys
sys.path.insert(0, r'D:\trae')

from src.interp import interpret


def get_out(src: str):
    """执行 Matha 源码，返回最后一次输出。"""
    out, _ = interpret(src)
    return out[-1] if out else None


# ─── 位运算 ─────────────────────────────────────────────────────────────────

def test_bit_and():
    assert get_out('12 & 10') == 8
    print('  ✓ 位与: 12 & 10 = 8')

def test_bit_or():
    assert get_out('12 | 10') == 14
    print('  ✓ 位或: 12 | 10 = 14')

def test_bit_xor():
    # 异或的专用符号是 ⊕（EBNF §16）。中缀 ^ 是**次方**（EBNF 2.1
    # <power> = "^"、docs/06「^（中缀）| 次方（右结合）」），不是异或。
    assert get_out('12 ⊕ 10') == 6
    print('  ✓ 位异或: 12 ⊕ 10 = 6')


def test_caret_is_power():
    # 中缀 ^ = 次方，右结合、优先级高于 *（与 ** 同语义）。
    assert get_out('2 ^ 3') == 8
    assert get_out('2 ^ 3 ^ 2') == 512          # 右结合：2^(3^2)
    assert get_out('2 ^ 3 * 2') == 16           # ^ 比 * 紧：8*2
    assert get_out('2 ^ -1') == 0.5
    print('  ✓ 次方(^): 2^3^2 = 512，2^3*2 = 16')


def test_caret_prefix_is_sqrt():
    # 前缀位置 ^ 仍为开方（EBNF §16 双语义消解）。
    assert get_out('^9') == 3
    assert get_out('^16') == 4
    print('  ✓ 前缀开方(^): ^9 = 3')


def test_bit_lshift():
    assert get_out('1 << 3') == 8
    print('  ✓ 左移: 1 << 3 = 8')

def test_bit_rshift():
    assert get_out('16 >> 2') == 4
    print('  ✓ 右移: 16 >> 2 = 4')

def test_bit_not():
    assert get_out('~5') == -6
    assert get_out('~0') == -1
    print('  ✓ 位取反: ~5 = -6')

def test_bit_xor_unicode():
    # ⊕ 有独立 token（TokenType.OP_XOR），与中缀次方 ^ 区分。
    assert get_out('12 ⊕ 10') == 6
    assert get_out('0 ⊕ 0') == 0
    print('  ✓ 位异或(Unicode): 12 ⊕ 10 = 6')


# ─── 角度前缀 <<（docs/06 级 6）─────────────────────────────────────────────

def test_angle_prefix():
    # <<n 把度数归一化为弧度，故可��接喂给只吃弧度的 sin/cos。
    import math
    assert get_out('<<0') == 0.0
    assert get_out('<<90') == math.pi / 2
    assert get_out('<<180') == math.pi
    assert get_out('<<-90') == -math.pi / 2
    print('  ✓ 角度(<<): <<90 = pi/2，<<180 = pi')


def test_angle_with_trig():
    import math
    # 顶层裸函数调用不会被回显（只有字面量/二元式会），故这里显式 输出。
    assert get_out('输出(sin(<<30))') == math.sin(math.radians(30))
    assert get_out('输出(cos(<<90))') == math.cos(math.radians(90))
    print('  ✓ 角度喂三角: sin(<<30) = 0.5')


def test_angle_float_and_var():
    import math
    assert get_out('<<30.0') == math.radians(30.0)
    assert get_out('let a = 45\n<<a') == math.radians(45)
    print('  ✓ 角度接受浮点与变量')


def test_angle_precedence():
    # 级 6 高于算术：<<a * 2 == <<(a*2)，而非 (<<a) * 2。
    import math
    assert get_out('<<90 + 1') == math.radians(90) + 1
    assert get_out('let a = 30\n<<a * 2') == math.radians(60)
    print('  ✓ 角度优先级: <<只吃紧操作数')


def test_angle_nested_with_unary():
    # 各级一元前缀可叠加：-<<90 == -(<<90)。
    import math
    assert get_out('-<<90') == -math.pi / 2
    assert get_out('<<-90') == -math.pi / 2
    print('  ✓ 角度与一元运算叠加')


def test_angle_binary_shift_unaffected():
    # 中缀 << 仍是位移，不能被角度前缀吃掉。
    assert get_out('5 << 2') == 20
    assert get_out('5 >> 1') == 2
    assert get_out('let a = 5\na << 2') == 20
    print('  ✓ 中缀位移不受影响: 5 << 2 = 20')


def test_angle_rejects_non_numeric():
    # bool/字符串/列表对角度无意义，三端都必须抛错而不是静默给值。
    for src in ('<<True', '<<"90"', '<<[1,2]'):
        try:
            get_out(src)
        except Exception:
            continue
        raise AssertionError('<< 对非数值应报错：%r' % src)
    print('  ✓ 角度拒绝非数值')

# ─── 集合运算 ────────────────────────────────────────────────────────────────

def test_set_union():
    assert get_out('#1：[1,2,3] ∪ [3,4,5]') == [1, 2, 3, 4, 5]
    print('  ✓ 集合并: [1,2,3] ∪ [3,4,5]')

def test_set_inter():
    assert get_out('#1：[1,2,3] ∩ [2,3,4]') == [2, 3]
    print('  ✓ 集合交: [1,2,3] ∩ [2,3,4]')

def test_set_diff():
    assert get_out('#1：[1,2,3] ⊖ [2,3,4]') == [1]
    print('  ✓ 集合差: [1,2,3] ⊖ [2,3,4]')

def test_set_subset():
    assert get_out('#1：[1,2] ⊆ [1,2,3]') is True
    assert get_out('#1：[1,2,4] ⊆ [1,2,3]') is False
    print('  ✓ 子集: [1,2] ⊆ [1,2,3] = True')

def test_set_prod():
    result = get_out('#1：[1,2] × ["a","b"]')
    assert sorted(result) == [(1, 'a'), (1, 'b'), (2, 'a'), (2, 'b')]
    print('  ✓ 笛卡尔积: [1,2] × [a,b]')

def test_set_op_single_element_operand():
    # 回归：集合运算符右值为单元素列表 [x] 时，曾被 _parse_primary 误判为
    # 输出语句 Output(x)（因 OP_SET_* 未列入「运算符右值」token 集合），
    # 导致 [1,2] ∪ [5] 变成 BinaryOp(∪, [1,2], Output(5))，四端结果错乱。
    assert get_out('#1：[[1,2] ∪ [5]]') == [1, 2, 5]
    assert get_out('#1：[[1,2,3] ∩ [3]]') == [3]
    assert get_out('#1：[[1,2,3] ⊖ [3]]') == [1, 2]
    assert get_out('#1：[[3,1] ∪ [2]]') == [3, 1, 2]
    assert get_out('#1：[[5] ∪ [1,2]]') == [5, 1, 2]
    print('  ✓ 集合运算符右值单元素列表（解析器回归）')

# ─── 严格比较 ───────────────────────────────────────────────────────────────

def test_strict_eq():
    assert get_out('1 === 1') is True
    assert get_out('1 === "1"') is False
    assert get_out('null === null') is True
    print('  ✓ 严格相等: 1 === 1, 1 === "1", null === null')

def test_strict_neq():
    assert get_out('1 !== "1"') is True
    assert get_out('1 !== 1') is False
    print('  ✓ 严格不等: 1 !== "1" = True')

# ─── 空值合并 ───────────────────────────────────────────────────────────────

def test_null_coal_basic():
    out, _ = interpret('let x = null; #1：[x ?? 42]')
    assert out[-1] == 42, out
    print('  ✓ 空值合并: null ?? 42 = 42')

def test_null_coal_value():
    out, _ = interpret('let x = 7; #1：[x ?? 42]')
    assert out[-1] == 7
    print('  ✓ 空值合并: 7 ?? 42 = 7')

# ─── 可选链 ────────────────────────────────────────────────────────────────

def test_optional_chain_attr():
    src = '''
struct Point{x: Int, y: Int}
let p = Point(3, 4)
#1：[p.x]
'''
    assert get_out(src) == 3
    print('  ✓ 可选链属性: Point(3,4).x = 3')

def test_optional_chain_attr_missing():
    src = '''
struct Empty{}
let e = Empty()
#1：[e.missing ?? "none"]
'''
    assert get_out(src) == "none"
    print('  ✓ 可选链缺失属性: e.missing ?? "none"')

def test_safe_path_expr_none():
    src = '''
let p = null
#1：[p?.field]
'''
    assert get_out(src) is None
    print('  ✓ SafePathExpr None: null?.field = None')

def test_safe_path_expr_attr():
    src = '''
struct Person{name: Str}
let p = Person("Alice")
#1：[p?.name]
'''
    assert get_out(src) == "Alice"
    print('  ✓ SafePathExpr 属性: Person("Alice")?.name = Alice')

# ─── Struct 字段访问 ────────────────────────────────────────────────────────

def test_struct_field_access():
    src = '''
struct Point{x: Int, y: Int}
let p = Point(1, 2)
#1：[p.x + p.y]
'''
    assert get_out(src) == 3
    print('  ✓ Struct 字段访问: Point(1,2).x + Point(1,2).y = 3')

def test_struct_dict_access():
    src = '''
struct Person{name: Str, age: Int}
let p = Person("Bob", 30)
#1：[p["name"] + " is " + p["age"]]
'''
    assert get_out(src) == "Bob is 30"
    print('  ✓ Struct 下标访问: Person("Bob",30)["name"]')

# ─── 前缀自增 / 自减 ─────────────────────────────────────────────────────────

def test_prefix_incr_decr():
    # 语义是**非原地**的 v±1（不改绑定），故 ++x 不改变 x 本身。
    assert get_out('++2.5') == 3.5
    assert get_out('--2.5') == 1.5
    assert get_out('++3') == 4
    assert get_out('--3') == 2
    assert get_out('let x = 5\n++x') == 6
    assert get_out('let x = 5\n--x') == 4
    print('  ✓ 前缀自增自减: ++2.5 = 3.5，--3 = 2')


def test_prefix_incr_decr_float_result():
    assert get_out('--(2 + 0.5)') == 1.5
    assert get_out('let a = 2.5\n--a') == 1.5
    assert get_out('输出(--(90 / 1))') == 89.0
    print('  ✓ 自增自减作用于运行期浮点')


def test_prefix_incr_decr_rejects_non_numeric():
    for src in ('++"a"', '--[1,2]'):
        try:
            get_out('输出(%s)' % src)
        except Exception:
            continue
        raise AssertionError('%% 应报错：%r' % src)
    print('  ✓ 自增自减拒绝非数值')


# ─── `？` 占位符与具名变量的等价性 ────────────────────────────────────────────

def test_placeholder_equals_named_variable():
    # docs/00 L135、docs/02「占位符」条：`？` 可被任意字母替代，
    # `？sum` 等价于具名变量 `sum`。
    assert get_out('？sum = 0\n输出(sum)') == 0
    assert get_out('？sum = 0\n输出(？sum)') == 0
    assert get_out('sum = 5\n输出(？sum)') == 5
    print('  ✓ ？sum ≡ sum')


def test_placeholder_in_expression():
    assert get_out('？a = 1\n？b = 2\n输出(？a + ？b)') == 3
    assert get_out('？a = 1\n输出(？a * 3)') == 3
    print('  ✓ ？a 在表达式中可用')


# ─── `？` 公式模式库：按格式统一同形公式 ──────────────────────────────────────

def get_trace(src):
    """执行并返回 trace（公式模式的登记/合一记在 trace 里）。"""
    out, trace = interpret(src)
    return out, trace


def test_question_formula_registered_not_evaluated():
    """`#：？公式` 登记为模式而非求值：槽没有可求值的值。"""
    out, trace = get_trace('#1：？+？=？')
    assert out == []
    assert trace == ['#1：？ + ？ = ？']
    print('  ✓ `？+？=？` 登记为模式，不求值')


def test_question_formula_shape_unifies_many():
    """多公式一用途：格式相同的具体公式都合一到同一模式。"""
    _, trace = get_trace('#1：？+？=？\n#2：单价 + 运费 = 总价\n#3：a + b = c')
    assert trace[0] == '#1：？ + ？ = ？'
    assert trace[1:] == ['单价 + 运费 = 总价', 'a + b = c']
    print('  ✓ 同形公式统一：`单价+运费=总价` 与 `a+b=c`')


def test_question_formula_operator_is_part_of_shape():
    """格式（形状）含运算符，故 `？+？=？` 不吃 `？*？=？`。

    非同形公式在解释器里会落到 `_eval`（求值未定义名会报错），故此项在
    库层面断言，不走 interpret。
    """
    from src.parser import parse
    from src import formula_schema as fs

    def expr(src):
        return parse(src).decls[0].body.content

    lib = fs.FormulaLibrary()
    lib.register(expr('#1：？+？=？'), 1)
    assert lib.match(expr('#2：单价 * 数量 = 总价')) == []
    assert len(lib.match(expr('#3：单价 + 运费 = 总价'))) == 1
    print('  ✓ 运算符属于格式：`*` 不与 `+` 同形')


def test_question_formula_named_slot_consistency():
    """具名槽跨出现强制一致——这正是 `？name` 的作用。"""
    _, trace = get_trace('#1：？a + ？a = ？b\n#2：面积 + 面积 = 周长')
    assert trace == ['#1：？a + ？a = ？b', '面积 + 面积 = 周长']

    from src.parser import parse
    from src import formula_schema as fs

    def expr(src):
        return parse(src).decls[0].body.content

    lib = fs.FormulaLibrary()
    lib.register(expr('#1：？a + ？a = ？b'), 1)
    # x + y = z 无法满足 ?a 同时等于 x 与 y，故不合一
    assert lib.match(expr('#2：x + y = z')) == []
    assert len(lib.match(expr('#3：面积 + 面积 = 周长'))) == 1
    print('  ✓ 具名槽一致性：`面积+面积=周长` 合，`x+y=z` 不合')


def test_question_formula_same_shape_merged():
    """格式即身份：同形模式归并为一条，不重复堆积。"""
    from src.parser import parse
    from src import formula_schema as fs

    def expr(src):
        return parse(src).decls[0].body.content

    lib = fs.FormulaLibrary()
    lib.register(expr('#1：？+？=？'), 1)
    again = lib.register(expr('#2：？+？=？'), 2)
    assert len(lib) == 1 and again.seg_id == 1
    # 但两段各自的声明形式都应留在 trace 里（记自己的段号）
    _, trace = get_trace('#1：？+？=？\n#2：？+？=？')
    assert trace == ['#1：？ + ？ = ？', '#2：？ + ？ = ？']
    print('  ✓ 同形模式归并为一条')


def test_question_formula_anonymous_slots_independent():
    """裸 `？` 是匿名槽，每次出现彼此独立。"""
    from src.parser import parse
    from src import formula_schema as fs
    e = parse('#1：？ = 0').decls[0].body.content
    b = fs.unify(e, parse('#1：sum = 0').decls[0].body.content)
    assert b is not None and list(b) == ['?1']
    print('  ✓ 裸 `？` 绑定到任意字母名')


def test_question_formula_one_schema_many_uses():
    """一公式多用途：同一模式换基础定义即换用途。"""
    from src.parser import parse
    from src import formula_schema as fs

    def named(src):
        return parse(src).decls[0].body.content

    schema = fs.FormulaLibrary().register(named('#1：？+？=？'), 1)
    for trio, want in ((('收入', '支出', '结余'), '收入 + 支出 = 结余'),
                       (('长', '宽', '周长'), '长 + 宽 = 周长'),
                       (('速度', '时间', '距离'), '速度 + 时间 = 距离')):
        b = {'?1': named('#：%s' % trio[0]), '?2': named('#：%s' % trio[1]),
             '?3': named('#：%s' % trio[2])}
        assert fs.render(fs.instantiate(schema.expr, b)) == want
    print('  ✓ 一公式多用途：同一 `？+？=？` 三种绑定三种用途')


def test_question_formula_traversal_covers_all_expr_forms():
    """槽收集须覆盖全部表达式形态——函数调用、索引、一元、属于。

    早期实现漏了 FuncApp，`sin(？)` 收集不到槽（形状退化成 `FuncApp`）；
    `ListLiteral`/`TupleExpr`/`IndexExpr` 的字段名一度写成 `items`/`obj`
    （实为 `elements`/`container`），导致这些节点被静默跳过。
    """
    from src.parser import parse
    from src import formula_schema as fs

    def expr(src):
        return parse(src).decls[0].body.content

    cases = {
        '#：sin(？)': 1, '#：len(？)': 1, '#：？[？]': 2,
        '#：-？': 1, '#：？ >> ？': 2,
    }
    for src, n in cases.items():
        assert len(fs.collect_slots(expr(src))) == n, src
    print('  ✓ 槽收集覆盖函数调用/索引/一元/属于')


def test_question_formula_unify_function_and_index():
    from src.parser import parse
    from src import formula_schema as fs

    def expr(src):
        return parse(src).decls[0].body.content

    lib = fs.FormulaLibrary()
    sin = lib.register(expr('#1：sin(？)'), 1)
    assert lib.match(expr('#2：sin(0.5)'))
    assert not lib.match(expr('#3：cos(0.5)'))     # 函数名不同 → 不同格式
    lib2 = fs.FormulaLibrary()
    idx = lib2.register(expr('#1：？[？]'), 1)
    m = lib2.match(expr('#2：d[3]'))
    assert m and fs.render(fs.instantiate(idx.expr, m[0].bindings)) == 'd[3]'
    print('  ✓ 函数调用与索引参与合一')


# ─── 组合测试 ───────────────────────────────────────────────────────────────

def test_bit_in_expr_context():
    assert get_out('let x = 1; #1：[x * 2 & 3]') == 2
    print('  ✓ 位与优先级: 1*2 & 3 = 2')

def test_set_union_in_expr():
    assert get_out('let s = [1,2]; #1：[s ∪ [3,4]]') == [1, 2, 3, 4]
    print('  ✓ 集合并在变量表达式中')


# ─── Phase ②：符号常量 π τ φ ∞ ∅ ────────────────────────────────────────────

def test_symbol_constants():
    import math
    assert get_out('#1：[π]') == math.pi
    assert get_out('#1：[τ]') == math.tau
    assert get_out('#1：[φ]') == (1 + 5 ** 0.5) / 2
    assert get_out('#1：[∞]') == math.inf
    assert get_out('#1：[π, ∛8]') == [math.pi, 2]
    print('  ✓ 符号常量: π τ φ ∞')

def test_empty_set_literal():
    assert get_out('#1：[∅]') == []
    assert get_out('#1：[len(∅)]') == 0
    print('  ✓ 空集字面量: ∅ = []')


# ─── Phase ②：前缀 √ ∛ ──────────────────────────────────────────────────────

def test_sqrt_symbol_prefix():
    assert get_out('#1：[√9]') == 3
    assert get_out('#1：[√16]') == 4
    assert get_out('#1：[√2]') == 2 ** 0.5
    assert get_out('#1：[√9 + 1]') == 4
    print('  ✓ 符号开方: √9 = 3')

def test_cbrt_symbol_prefix():
    assert get_out('#1：[∛27]') == 3
    assert get_out('#1：[∛8]') == 2
    assert get_out('#1：[∛64]') == 4
    assert get_out('#1：[∛-8]') == -2
    assert get_out('#1：[∛2]') == 2 ** (1 / 3)
    print('  ✓ 符号立方根: ∛27 = 3')


# ─── Phase ②：中缀 ÷ ────────────────────────────────────────────────────────

def test_divide_symbol():
    assert get_out('#1：[6 ÷ 2]') == 3.0
    assert get_out('#1：[2 ÷ 4]') == 0.5
    assert get_out('#1：[12 ÷ 2 ÷ 3]') == 2.0
    print('  ✓ 除号 ÷: 6 ÷ 2 = 3.0')


# ─── Phase ②：单位后缀 ° ℃ ℉（纯字符串标签，只取值） ────────────────────────

def test_unit_suffix_symbols():
    assert get_out('#1：[90°]') == 90
    assert get_out('#1：[30℃]') == 30
    assert get_out('#1：[98℉]') == 98
    assert get_out('#1：[90° + 10]') == 100
    assert get_out('#1：[100米]') == 100
    print('  ✓ 单位后缀: 90° 30℃ 98℉')


# ─── Phase ②：聚合前缀 ∑ ∏（列表求和/求积，非列表报错） ─────────────────────

def test_aggregate_prefix_symbols():
    assert get_out('#1：[∑[1,2,3,4]]') == 10
    assert get_out('#1：[∑[]]') == 0
    assert get_out('#1：[∏[1,2,3,4]]') == 24
    assert get_out('#1：[∏[]]') == 1
    assert get_out('#1：[∑[7,]]') == 7
    assert get_out('#1：[∏[7,]]') == 7
    assert get_out('#1：[∑[1, 2.5, 3]]') == 6.5
    assert get_out('#1：[∏[1.5, 2]]') == 3.0
    assert get_out('#1：[∑[1,2,3] + 10]') == 16
    assert get_out('#1：[∑[√9, √16]]') == 7
    assert get_out('#1：[∑[∏[1,2], ∏[3,4]]]') == 14
    print('  ✓ 聚合前缀: ∑[1,2,3,4] = 10, ∏[1,2,3,4] = 24')


# ─── 主入口 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== Matha 新功能集成测试 ===')
    tests = [
        test_bit_and, test_bit_or, test_bit_xor,
        test_bit_lshift, test_bit_rshift, test_bit_not, test_bit_xor_unicode,
        test_angle_prefix, test_angle_with_trig, test_angle_float_and_var,
        test_angle_precedence, test_angle_nested_with_unary,
        test_angle_binary_shift_unaffected, test_angle_rejects_non_numeric,
        test_prefix_incr_decr, test_prefix_incr_decr_float_result,
        test_prefix_incr_decr_rejects_non_numeric,
        test_placeholder_equals_named_variable, test_placeholder_in_expression,
        test_question_formula_registered_not_evaluated,
        test_question_formula_shape_unifies_many,
        test_question_formula_operator_is_part_of_shape,
        test_question_formula_named_slot_consistency,
        test_question_formula_same_shape_merged,
        test_question_formula_anonymous_slots_independent,
        test_question_formula_one_schema_many_uses,
        test_question_formula_traversal_covers_all_expr_forms,
        test_question_formula_unify_function_and_index,
        test_set_union, test_set_inter, test_set_diff,
        test_set_subset, test_set_prod,
        test_strict_eq, test_strict_neq,
        test_null_coal_basic, test_null_coal_value,
        test_optional_chain_attr, test_optional_chain_attr_missing,
        test_safe_path_expr_none, test_safe_path_expr_attr,
        test_struct_field_access, test_struct_dict_access,
        test_bit_in_expr_context, test_set_union_in_expr,
        test_symbol_constants, test_empty_set_literal,
        test_sqrt_symbol_prefix, test_cbrt_symbol_prefix,
        test_divide_symbol, test_unit_suffix_symbols,
        test_aggregate_prefix_symbols,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'  ✗ {t.__name__}: {e}')
            failed += 1
    print(f'\n结果: {passed} 通过, {failed} 失败')
    if failed:
        sys.exit(1)
