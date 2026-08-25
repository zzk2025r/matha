"""外部语言互操作子系统测试：外部求值 / 双实现对比 / 对比升级。

覆盖四个层次：
  1) ForeignRunner：Python 内嵌求值（表达式/语句/输入注入/函数调用/多参数/
     未定义函数/返回结构/空输出/0 参数/返回 list/不支持语言）
  2) DualComparator：双实现对比（一致/差异/部分一致/异常处理/结果字典/类型容忍/
     空测试/None 对比/多参数/外部语法错）
  3) compare_upgrade：对比驱动的自我升级（成功/失败回滚/源码错/语法错/覆写/零测试/
     额外校验通过/拒绝/异常/输出摘要/对比异常回滚/覆写不一致保留旧版/连续/恢复性）
  4) Matha 侧内建：外部求值/对比实现/对比升级/对比升级失败抛错/空列表/沙箱隔离/
     外部求值返回 list/外部求值语句/对比升级覆写/对比升级零测试

运行：python -m tests.test_foreign
"""

from src.parser import parse
from src.interp import Interpreter, interpret, MathaRuntimeError
from src.foreign import (
    ForeignRunner, DualComparator, CompareResult, compare_upgrade,
)


def _interp_with(src: str) -> Interpreter:
    """解析并运行源码，返回已装载的解释器。"""
    i = Interpreter()
    i.run(parse(src))
    return i


# ============================================================
# 1) ForeignRunner：外部语言求值
# ============================================================

def test_foreign_eval_python_expression():
    """Python 表达式求值。"""
    print("\n--- 外部求值: Python 表达式 ---")
    r = ForeignRunner()
    assert r.eval("Python", "1 + 2 * 3") == 7
    assert r.eval("Python", "len([1, 2, 3])") == 3
    assert r.eval("Python", "'ab' + 'cd'") == "abcd"
    print("  ✓ 1+2*3=7; len([1,2,3])=3; 'ab'+'cd'='abcd'")


def test_foreign_eval_python_statement():
    """Python 语句执行（无返回值）。"""
    print("\n--- 外部求值: Python 语句 ---")
    r = ForeignRunner()
    result = r.eval("Python", "x = 42")
    assert result is None  # exec 无返回值
    print("  ✓ 语句执行返回 None")


def test_foreign_eval_python_with_inputs():
    """Python 求值带输入变量注入。"""
    print("\n--- 外部求值: 输入注入 ---")
    r = ForeignRunner()
    result = r.eval("Python", "a + b", inputs={"a": 10, "b": 20})
    assert result == 30, result
    print("  ✓ a+b=30 (a=10, b=20 注入)")


def test_foreign_call_python_function():
    """Python 函数调用：定义函数 + 传参调用。"""
    print("\n--- 外部调用: Python 函数 ---")
    r = ForeignRunner()
    code = "def 平方(x): return x * x"
    assert r.call("Python", code, "平方", [5]) == 25
    assert r.call("Python", code, "平方", [-3]) == 9
    print("  ✓ 平方(5)=25; 平方(-3)=9")


def test_foreign_call_python_multi_arg():
    """Python 多参数函数调用。"""
    print("\n--- 外部调用: 多参数 ---")
    r = ForeignRunner()
    code = "def 加(a, b, c): return a + b + c"
    assert r.call("Python", code, "加", [1, 2, 3]) == 6
    print("  ✓ 加(1,2,3)=6")


def test_foreign_call_python_function_not_defined():
    """Python 调用未定义函数 → 抛 MathaRuntimeError。"""
    print("\n--- 外部调用: 未定义函数 ---")
    r = ForeignRunner()
    try:
        r.call("Python", "x = 1", "不存在", [])
        raised = False
    except MathaRuntimeError as ex:
        raised = True
        assert "不存在" in str(ex)
    assert raised
    print("  ✓ 未定义函数抛 MathaRuntimeError")


def test_foreign_eval_returns_list_and_dict():
    """Python 求值返回 list/dict 结构。"""
    print("\n--- 外部求值: list/dict 返回 ---")
    r = ForeignRunner()
    assert r.eval("Python", "[1, 2, 3]") == [1, 2, 3]
    assert r.eval("Python", "{'a': 1, 'b': 2}") == {"a": 1, "b": 2}
    print("  ✓ [1,2,3] 和 {'a':1,'b':2} 正确返回")


def test_foreign_eval_empty_output():
    """Python 求值无输出语句 → 返回 None。"""
    print("\n--- 外部求值: 空输出 ---")
    r = ForeignRunner()
    assert r.eval("Python", "pass") is None
    assert r.eval("Python", "x = 1") is None  # exec 返回 None
    print("  ✓ pass / x=1 返回 None")


def test_foreign_call_zero_arg_function():
    """Python 0 参数函数调用。"""
    print("\n--- 外部调用: 0 参数函数 ---")
    r = ForeignRunner()
    code = "def pi(): return 314"
    assert r.call("Python", code, "pi", []) == 314
    print("  ✓ pi() = 314")


def test_foreign_call_returns_list():
    """Python 函数返回 list 结构。"""
    print("\n--- 外部调用: 返回 list ---")
    r = ForeignRunner()
    code = "def f(n): return [i * i for i in range(n)]"
    assert r.call("Python", code, "f", [3]) == [0, 1, 4]
    assert r.call("Python", code, "f", [0]) == []
    print("  ✓ f(3)=[0,1,4]; f(0)=[]")


def test_foreign_eval_unsupported_language():
    """不支持的语言名 → 抛 MathaRuntimeError。"""
    print("\n--- 外部求值: 不支持语言 ---")
    r = ForeignRunner()
    try:
        r.eval("cobol", "1")
        raised = False
    except MathaRuntimeError as ex:
        raised = True
        assert "不支持" in str(ex)
    assert raised
    print("  ✓ cobol 抛 MathaRuntimeError")


def test_foreign_call_unsupported_language():
    """call 不支持语言 → 抛 MathaRuntimeError。"""
    print("\n--- 外部调用: 不支持语言 ---")
    r = ForeignRunner()
    try:
        r.call("pascal", "x", "f", [])
        raised = False
    except MathaRuntimeError:
        raised = True
    assert raised
    print("  ✓ pascal call 抛 MathaRuntimeError")


# ============================================================
# 2) DualComparator：双实现对比
# ============================================================

def test_compare_all_match():
    """Matha 与外部实现完全一致 → 通过。"""
    print("\n--- 对比: 全一致 ---")
    i = _interp_with('func 平方(x: Int) -> Int = (x) => x * x')
    cmp = DualComparator(i, "平方", "Python", "def 平方(x): return x * x")
    result = cmp.compare([[2], [3], [5], [-1]])
    assert result.通过 is True
    assert result.总数 == 4
    assert result.一致数 == 4
    assert result.差异 == []
    print(f"  ✓ 4/4 一致；通过={result.通过}")


def test_compare_has_diffs():
    """Matha 与外部实现不一致 → 差异详情。"""
    print("\n--- 对比: 有差异 ---")
    i = _interp_with('func 加一(x: Int) -> Int = (x) => x + 1')
    cmp = DualComparator(i, "加一", "Python", "def 加一(x): return x + 2")
    result = cmp.compare([[1], [2]])
    assert result.通过 is False
    assert result.总数 == 2
    assert result.一致数 == 0
    assert len(result.差异) == 2
    assert result.差异[0]["输入"] == [1]
    assert result.差异[0]["Matha结果"] == 2
    assert result.差异[0]["外部结果"] == 3
    print(f"  ✓ 0/2 一致；差异含输入/Matha结果/外部结果")


def test_compare_partial_match():
    """部分一致：部分输入匹配，部分不匹配。"""
    print("\n--- 对比: 部分一致 ---")
    # Matha 实现：x>2 时正确（x*x），x<=2 时错误（x+1）
    i = _interp_with('func f(x: Int) -> Int = (x) => (x > 2) ? x * x : x + 1')
    cmp = DualComparator(i, "f", "Python", "def f(x): return x * x")
    result = cmp.compare([[2], [3]])
    assert result.通过 is False
    assert result.一致数 == 1  # 3*3=9 一致
    assert len(result.差异) == 1  # 2: Matha=3, 外部=4
    print(f"  ✓ 1/2 一致；差异 1 项")


def test_compare_matha_exception():
    """Matha 函数抛异常 → 差异中记录异常。"""
    print("\n--- 对比: Matha 异常 ---")
    i = _interp_with('func 倒数(x: Int) -> Int = (x) => 1 / x')
    cmp = DualComparator(i, "倒数", "Python", "def 倒数(x): return 1 / x")
    result = cmp.compare([[0]])
    assert result.通过 is False
    assert "Matha异常" in str(result.差异[0]["Matha结果"])
    print(f"  ✓ Matha 异常被捕获记录")


def test_compare_foreign_exception():
    """外部函数抛异常 → 差异中记录异常。"""
    print("\n--- 对比: 外部异常 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    cmp = DualComparator(i, "f", "Python", "def f(x): return x / 0")
    result = cmp.compare([[1]])
    assert result.通过 is False
    assert "外部异常" in str(result.差异[0]["外部结果"])
    print(f"  ✓ 外部异常被捕获记录")


def test_compare_result_as_dict():
    """CompareResult.as_dict() 返回普通 dict。"""
    print("\n--- 对比: 结果字典 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    cmp = DualComparator(i, "f", "Python", "def f(x): return x")
    result = cmp.compare([[1], [2]])
    d = result.as_dict()
    assert d == {"通过": True, "总数": 2, "一致数": 2, "差异数": 0}, d
    print(f"  ✓ as_dict 含 通过/总数/一致数/差异数")


def test_compare_values_equal_type_tolerance():
    """值对比容忍类型差异：int/float 互通，bool 严格。"""
    print("\n--- 对比: 类型容忍 ---")
    from src.foreign import _values_equal
    assert _values_equal(1, 1.0) is True      # int/float 互通
    assert _values_equal(True, 1) is False     # bool 严格区分
    assert _values_equal([1, 2], [1, 2]) is True
    assert _values_equal([1, 2], (1, 2)) is True  # list/tuple 互通
    assert _values_equal("a", "a") is True
    assert _values_equal({"a": 1}, {"a": 1}) is True
    print("  ✓ int/float 互通; bool 严格; list/tuple/dict 递归")


def test_compare_empty_test_cases():
    """零测试输入 → 空对比通过（无差异）。"""
    print("\n--- 对比: 零测试用例 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    cmp = DualComparator(i, "f", "Python", "def f(x): return x")
    result = cmp.compare([])
    assert result.通过 is True
    assert result.总数 == 0
    assert result.一致数 == 0
    assert result.差异 == []
    print("  ✓ 0/0 一致；通过")


def test_compare_none_vs_value():
    """Matha 返回 0 vs Python 返回 None → 不一致（类型差异）。"""
    print("\n--- 对比: None vs 值 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => 0')
    cmp = DualComparator(i, "f", "Python", "def f(x): return None")
    result = cmp.compare([[1]])
    assert result.通过 is False
    assert result.一致数 == 0
    assert len(result.差异) == 1
    print("  ✓ Matha(0) vs Python(None) → 不一致")


def test_compare_multi_arg_functions():
    """多参数函数对比：Matha 柯里化 vs Python 多参。"""
    print("\n--- 对比: 多参数函数 ---")
    # Matha 多参定义（逗号），柯里化应用
    i = _interp_with('func 加(a: Int, b: Int) -> Int = (a) => (b) => a + b')
    cmp = DualComparator(i, "加", "Python", "def 加(a, b): return a + b")
    result = cmp.compare([[1, 2], [3, 4], [10, -5]])
    assert result.通过 is True, result.差异
    assert result.总数 == 3
    assert result.一致数 == 3
    print("  ✓ 多参 加(1,2)/加(3,4)/加(10,-5) 全一致")


def test_compare_foreign_syntax_error():
    """外部代码语法错 → call 抛异常，记入差异。"""
    print("\n--- 对比: 外部语法错 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    cmp = DualComparator(i, "f", "Python", "def f(x) return x")  # 缺冒号
    result = cmp.compare([[1]])
    assert result.通过 is False
    assert "外部异常" in str(result.差异[0]["外部结果"])
    print("  ✓ 外部语法错记入差异")


def test_compare_returns_bool():
    """对比返回 bool 的函数。"""
    print("\n--- 对比: 返回 bool ---")
    i = _interp_with('func 是正(x: Int) -> Int = (x) => (x > 0) ? 1 : 0')
    # Matha 无 bool 字面量，用 1/0 对比 Python True/False → bool 严格 → 不一致
    cmp = DualComparator(i, "是正", "Python", "def 是正(x): return x > 0")
    result = cmp.compare([[1], [-1]])
    assert result.通过 is False  # 1 vs True, 0 vs False → bool 严格
    assert result.一致数 == 0
    print("  ✓ Matha(1/0) vs Python(True/False) → bool 严格不一致")


def test_compare_returns_list():
    """对比返回 list 的函数。"""
    print("\n--- 对比: 返回 list ---")
    i = _interp_with('func 双倍(表: List) -> List = (表) => 表')
    # Matha 实现直接返回输入（占位），与 Python 双倍对比
    cmp = DualComparator(i, "双倍", "Python", "def 双倍(表): return [x*2 for x in 表]")
    result = cmp.compare([[[1, 2, 3]]])
    assert result.通过 is False  # [1,2,3] vs [2,4,6]
    print("  ✓ list 返回值对比：[1,2,3] vs [2,4,6] → 不一致")


# ============================================================
# 3) compare_upgrade：对比驱动的自我升级
# ============================================================

def test_compare_upgrade_success():
    """对比升级成功：Matha 实现与外部一致 → 提交。"""
    print("\n--- 对比升级: 成功 ---")
    i = _interp_with('')
    matha_src = 'func 平方(x: Int) -> Int = (x) => x * x'
    py_code = "def 平方(x): return x * x"
    r = compare_upgrade(i, matha_src, "平方", "Python", py_code, [[2], [3], [5]])
    assert r.成功 is True, r.错误
    assert "平方" in r.变更["新函数"]
    assert i.call("平方", 4) == 16
    print("  ✓ 对比通过 → 提交；本体 平方(4)=16")


def test_compare_upgrade_mismatch_rolls_back():
    """对比升级不一致 → 回滚，本体不污染。"""
    print("\n--- 对比升级: 不一致回滚 ---")
    i = _interp_with('')
    # Matha 实现错误（x+1 而非 x*x）
    matha_src = 'func 平方(x: Int) -> Int = (x) => x + 1'
    py_code = "def 平方(x): return x * x"
    r = compare_upgrade(i, matha_src, "平方", "Python", py_code, [[2], [3]])
    assert r.成功 is False
    assert "对比不一致" in (r.错误 or ""), r.错误
    assert "平方" not in i.funcs  # 本体未污染
    print(f"  ✓ 对比不一致 → 回滚；本体无 平方")


def test_compare_upgrade_source_error_rolls_back():
    """对比升级源码错 → 回滚。"""
    print("\n--- 对比升级: 源码错回滚 ---")
    i = _interp_with('')
    matha_src = '#1：[未定义量]'  # 运行时错
    py_code = "def f(x): return x"
    r = compare_upgrade(i, matha_src, "f", "Python", py_code, [[1]])
    assert r.成功 is False
    assert "加载失败" in (r.错误 or ""), r.错误
    print(f"  ✓ 源码错 → 回滚；错误含 '加载失败'")


def test_compare_upgrade_parse_error_rolls_back():
    """对比升级 Matha 源码语法错 → 回滚。"""
    print("\n--- 对比升级: 语法错回滚 ---")
    i = _interp_with('')
    matha_src = 'func 错(x: Int -> Int = (x) => x'  # 缺括号
    py_code = "def 错(x): return x"
    r = compare_upgrade(i, matha_src, "错", "Python", py_code, [[1]])
    assert r.成功 is False
    assert "加载失败" in (r.错误 or "")
    assert "错" not in i.funcs
    print(f"  ✓ 语法错 → 回滚")


def test_compare_upgrade_redefine_function():
    """对比升级覆写已有函数（Matha 新版与外部一致）。"""
    print("\n--- 对比升级: 覆写已有函数 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x + 1')
    # 覆写为 x*2，与外部一致
    matha_src = 'func f(x: Int) -> Int = (x) => x * 2'
    py_code = "def f(x): return x * 2"
    r = compare_upgrade(i, matha_src, "f", "Python", py_code, [[1], [2]])
    assert r.成功 is True, r.错误
    assert "f" in r.变更["改函数"]
    assert i.call("f", 3) == 6  # 新版
    print(f"  ✓ 覆写 f 归类改函数；本体 f(3)=6")


def test_compare_upgrade_empty_test_cases():
    """对比升级零测试用例 → 空对比通过（无差异）。"""
    print("\n--- 对比升级: 零测试用例 ---")
    i = _interp_with('')
    matha_src = 'func f(x: Int) -> Int = (x) => x'
    py_code = "def f(x): return x"
    r = compare_upgrade(i, matha_src, "f", "Python", py_code, [])
    assert r.成功 is True, r.错误  # 无测试 → 无差异 → 通过
    assert "f" in r.变更["新函数"]
    print(f"  ✓ 零测试用例 → 空对比通过")


def test_compare_upgrade_extra_verify_pass():
    """对比通过 + 额外校验通过 → 提交。"""
    print("\n--- 对比升级: 额外校验通过 ---")
    i = _interp_with('')
    matha_src = 'func 双倍(x: Int) -> Int = (x) => x * 2'
    py_code = "def 双倍(x): return x * 2"
    r = compare_upgrade(
        i, matha_src, "双倍", "Python", py_code, [[5]],
        extra_verify=lambda sb: sb.call("双倍", 10) == 20,
    )
    assert r.成功 is True, r.错误
    print(f"  ✓ 对比通过 + 额外校验通过 → 提交")


def test_compare_upgrade_extra_verify_rejects():
    """对比通过但额外校验拒绝 → 回滚。"""
    print("\n--- 对比升级: 额外校验拒绝 ---")
    i = _interp_with('')
    matha_src = 'func f(x: Int) -> Int = (x) => x'
    py_code = "def f(x): return x"
    r = compare_upgrade(
        i, matha_src, "f", "Python", py_code, [[1]],
        extra_verify=lambda sb: False,  # 故意拒绝
    )
    assert r.成功 is False
    assert "额外校验" in (r.错误 or "")
    assert "f" not in i.funcs
    print(f"  ✓ 额外校验拒绝 → 回滚")


def test_compare_upgrade_output_contains_summary():
    """对比升级成功的输出含对比摘要。"""
    print("\n--- 对比升级: 输出含摘要 ---")
    i = _interp_with('')
    matha_src = 'func f(x: Int) -> Int = (x) => x'
    py_code = "def f(x): return x"
    r = compare_upgrade(i, matha_src, "f", "Python", py_code, [[1], [2]])
    assert r.成功 is True
    # 输出末尾应含对比摘要 dict
    summary = r.输出[-1]
    assert isinstance(summary, dict)
    assert summary["通过"] is True
    assert summary["总数"] == 2
    assert summary["一致数"] == 2
    print(f"  ✓ 输出末尾含摘要: {summary}")


def test_compare_upgrade_compare_exception_rolls_back():
    """对比时外部代码坏（语法错）→ 记入差异，对比不一致 → 回滚。"""
    print("\n--- 对比升级: 外部代码错回滚 ---")
    i = _interp_with('')
    # 外部代码语法错 → DualComparator 记入差异（外部异常）→ 对比不一致 → 回滚
    matha_src = 'func f(x: Int) -> Int = (x) => x'
    bad_py = "def f(x) return x"  # 语法错
    r = compare_upgrade(i, matha_src, "f", "Python", bad_py, [[1]])
    assert r.成功 is False
    assert "对比不一致" in (r.错误 or ""), r.错误
    assert "外部异常" in (r.错误 or ""), r.错误  # 差异详情含外部异常
    assert "f" not in i.funcs
    print(f"  ✓ 外部代码错 → 对比不一致回滚；本体未污染")


def test_compare_upgrade_extra_verify_exception_rolls_back():
    """额外校验抛异常 → 回滚。"""
    print("\n--- 对比升级: 校验异常回滚 ---")
    i = _interp_with('')

    def bad_verify(sb):
        raise ValueError("校验器坏")

    r = compare_upgrade(i, 'func f(x: Int) -> Int = (x) => x', "f",
                        "Python", "def f(x): return x", [[1]],
                        extra_verify=bad_verify)
    assert r.成功 is False
    assert "额外校验异常" in (r.错误 or ""), r.错误
    assert "f" not in i.funcs
    print(f"  ✓ 校验异常 → 回滚；错误含 '额外校验异常'")


def test_compare_upgrade_redefine_mismatch_keeps_old():
    """覆写但对比不一致 → 旧版保留。"""
    print("\n--- 对比升级: 覆写不一致保留旧版 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x + 1')
    assert i.call("f", 1) == 2
    # 新版 x+100 与外部 x+1 不一致 → 回滚
    r = compare_upgrade(i, 'func f(x: Int) -> Int = (x) => x + 100',
                        "f", "Python", "def f(x): return x + 1", [[1]])
    assert r.成功 is False
    assert "f" not in r.变更.get("改函数", [])  # 未改
    assert i.call("f", 1) == 2  # 旧版保留
    print(f"  ✓ 覆写不一致 → 旧版 f(1)=2 保留")


def test_compare_upgrade_consecutive():
    """连续对比升级：每次在前次基础上叠加。"""
    print("\n--- 对比升级: 连续多次 ---")
    i = _interp_with('')
    r1 = compare_upgrade(i, 'func a(x: Int) -> Int = (x) => x',
                         "a", "Python", "def a(x): return x", [[1]])
    r2 = compare_upgrade(i, 'func b(x: Int) -> Int = (x) => x',
                         "b", "Python", "def b(x): return x", [[1]])
    assert r1.成功 and r2.成功
    assert i.call("a", 5) == 5
    assert i.call("b", 7) == 7
    print("  ✓ 连续升级 a/b 全部可用")


def test_compare_upgrade_failure_then_recovery():
    """对比升级失败后可再次升级成功（可恢复性）。"""
    print("\n--- 对比升级: 失败后恢复 ---")
    i = _interp_with('')
    rf = compare_upgrade(i, 'func f(x: Int) -> Int = (x) => x + 1',
                         "f", "Python", "def f(x): return x", [[1]])
    assert rf.成功 is False
    # 本体未被污染，可继续升级
    rs = compare_upgrade(i, 'func g(x: Int) -> Int = (x) => x',
                         "g", "Python", "def g(x): return x", [[1]])
    assert rs.成功 is True, rs.错误
    assert i.call("g", 5) == 5
    print("  ✓ 失败后可恢复；g(5)=5")


def test_compare_upgrade_batch_functions():
    """对比升级批量定义多个函数 → 全部提交。"""
    print("\n--- 对比升级: 批量函数 ---")
    i = _interp_with('')
    matha_src = (
        'func 加(x: Int) -> Int = (x) => x + 1\n'
        'func 减(x: Int) -> Int = (x) => x - 1'
    )
    py_code = (
        "def 加(x): return x + 1\n"
        "def 减(x): return x - 1"
    )
    r = compare_upgrade(i, matha_src, "加", "Python", py_code,
                        [[1], [5], [10]])
    assert r.成功 is True, r.错误
    assert set(r.变更["新函数"]) == {"加", "减"}, r.变更
    assert i.call("加", 1) == 2
    assert i.call("减", 5) == 4
    print("  ✓ 批量 加/减 全部提交")


def test_compare_upgrade_probe_reflects_change():
    """对比升级后探针状态反映新函数。"""
    print("\n--- 对比升级: 探针反映变更 ---")
    i = _interp_with('func 原(x: Int) -> Int = (x) => x')
    before = i.probe().state()
    assert "新" not in before["函数"]
    compare_upgrade(i, 'func 新(x: Int) -> Int = (x) => x + 1',
                    "新", "Python", "def 新(x): return x + 1", [[1]])
    after = i.probe().state()
    assert "新" in after["函数"], after
    assert "原" in after["函数"]
    assert len(after["函数"]) == len(before["函数"]) + 1
    print("  ✓ 升级前 无'新'；升级后 '新'出现，函数数 +1")


# ============================================================
# 4) Matha 侧内建
# ============================================================

def test_matha_builtin_foreign_eval():
    """Matha 外部求值("Python")("代码") 柯里化调用。"""
    print("\n--- Matha 内建: 外部求值 ---")
    src = '#：{ [外部求值("Python")("1 + 2 * 3")] }'
    out, _ = interpret(src)
    assert out == [7], out
    print(f"  ✓ 外部求值('Python')('1+2*3') = 7")


def test_matha_builtin_foreign_eval_string():
    """Matha 外部求值 Python 字符串操作。"""
    print("\n--- Matha 内建: 外部求值字符串 ---")
    src = '#：{ [外部求值("Python")("len(\\"hello\\")")] }'
    out, _ = interpret(src)
    assert out == [5], out
    print(f"  ✓ 外部求值 len('hello') = 5")


def test_matha_builtin_compare_impl():
    """Matha 对比实现 柯里化四参 → bool。"""
    print("\n--- Matha 内建: 对比实现 ---")
    src = '''
func 平方(x: Int) -> Int = (x) => x * x
#：{
  用例 = append(append(空列表)(list(2)))(list(3))
  [对比实现("平方")("Python")("def 平方(x): return x * x")(用例)]
}
'''
    out, _ = interpret(src)
    assert out == [True], out
    print(f"  ✓ 对比实现 平方 vs Python → True")


def test_matha_builtin_compare_impl_mismatch():
    """Matha 对比实现 不一致 → False。"""
    print("\n--- Matha 内建: 对比实现不一致 ---")
    src = '''
func 加一(x: Int) -> Int = (x) => x + 1
#：{
  用例 = append(空列表)(list(1))
  [对比实现("加一")("Python")("def 加一(x): return x + 2")(用例)]
}
'''
    out, _ = interpret(src)
    assert out == [False], out
    print(f"  ✓ 对比实现 加一(x+1) vs Python(x+2) → False")


def test_matha_builtin_compare_upgrade():
    """Matha 对比升级 柯里化五参 → 函数名列表 + 本体可用。"""
    print("\n--- Matha 内建: 对比升级 ---")
    src = '''
#：{
  用例 = append(append(空列表)(list(2)))(list(3))
  名表 = 对比升级("func 立方(x: Int) -> Int = (x) => x * x * x")("立方")("Python")("def 立方(x): return x * x * x")(用例)
  [名表]
  [立方(2)]
  [立方(3)]
}
'''
    out, _ = interpret(src)
    assert out[0] == ["立方"], out
    assert out[1] == 8, out
    assert out[2] == 27, out
    print(f"  ✓ 对比升级 立方 → 名表=['立方']; 立方(2)=8; 立方(3)=27")


def test_matha_builtin_compare_upgrade_failure_raises():
    """Matha 对比升级 不一致 → 抛 MathaRuntimeError。"""
    print("\n--- Matha 内建: 对比升级失败抛错 ---")
    src = '''
#：{
  用例 = append(空列表)(list(2))
  对比升级("func 平方(x: Int) -> Int = (x) => x + 1")("平方")("Python")("def 平方(x): return x * x")(用例)
}
'''
    try:
        interpret(src)
        raised = False
    except MathaRuntimeError as ex:
        raised = True
        assert "对比升级失败" in str(ex), str(ex)
    assert raised
    print(f"  ✓ 对比升级不一致 → 抛 MathaRuntimeError")


def test_matha_empty_list_builtin():
    """Matha 空列表 内建 + append 构造列表。"""
    print("\n--- Matha 内建: 空列表 ---")
    src = '''
#：{
  表 = append(append(空列表)(1))(2)
  [len(表)]
  [get(表)(0)]
  [get(表)(1)]
}
'''
    out, _ = interpret(src)
    assert out == [2, 1, 2], out
    print(f"  ✓ 空列表 + append → [1,2]; len=2; get(0)=1 get(1)=2")


def test_matha_foreign_eval_in_sandbox():
    """沙箱内调用 外部求值 不影响本体（层间隔离）。"""
    print("\n--- Matha 内建: 沙箱内外部求值 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    src = '#：{ [外部求值("Python")("6 * 7")] }'
    outs, _, err = sb.run(src)
    assert err is None, err
    assert outs == [42], outs
    # 本体不受影响
    assert i.call("基础", 5) == 5
    sb.rollback()
    print(f"  ✓ 沙箱内 外部求值=42；本体未受影响")


def test_matha_foreign_eval_returns_list():
    """Matha 外部求值 Python 返回 list。"""
    print("\n--- Matha 内建: 外部求值返回 list ---")
    src = '#：{ [外部求值("Python")("[1, 2, 3]")] }'
    out, _ = interpret(src)
    assert out == [[1, 2, 3]], out
    print(f"  ✓ 外部求值 返回 [1,2,3]")


def test_matha_foreign_eval_statement_returns_none():
    """Matha 外部求值 Python 语句 → None。"""
    print("\n--- Matha 内建: 外部求值语句 ---")
    src = '#：{ [外部求值("Python")("x = 42")] }'
    out, _ = interpret(src)
    assert out == [None], out
    print(f"  ✓ 外部求值 语句 → None")


def test_matha_compare_upgrade_redefine():
    """Matha 对比升级覆写已有函数。"""
    print("\n--- Matha 内建: 对比升级覆写 ---")
    src = '''
func f(x: Int) -> Int = (x) => x + 1
#：{
  用例 = append(空列表)(list(1))
  名表 = 对比升级("func f(x: Int) -> Int = (x) => x * 2")("f")("Python")("def f(x): return x * 2")(用例)
  [名表]
  [f(3)]
}
'''
    out, _ = interpret(src)
    assert out[0] == ["f"], out
    assert out[1] == 6, out  # 新版 x*2
    print(f"  ✓ 对比升级覆写 f；本体 f(3)=6")


def test_matha_compare_upgrade_zero_cases():
    """Matha 对比升级零测试用例 → 空对比通过。"""
    print("\n--- Matha 内建: 对比升级零测试 ---")
    src = '''
#：{
  名表 = 对比升级("func f(x: Int) -> Int = (x) => x")("f")("Python")("def f(x): return x")(空列表)
  [名表]
  [f(5)]
}
'''
    out, _ = interpret(src)
    assert out[0] == ["f"], out
    assert out[1] == 5, out
    print(f"  ✓ 零测试用例 → 空对比通过；f(5)=5")


def test_interp_foreign_eval_method():
    """Interpreter.foreign_eval() 方法直接调用。"""
    print("\n--- Interpreter 方法: foreign_eval ---")
    i = _interp_with('')
    assert i.foreign_eval("Python", "3 * 4") == 12
    assert i.foreign_eval("Python", "'ab' + 'cd'") == "abcd"
    print(f"  ✓ foreign_eval('3*4')=12; ('ab'+'cd')='abcd'")


def test_matha_compare_impl_in_sandbox():
    """沙箱内对比实现 不影响本体。"""
    print("\n--- Matha 内建: 沙箱内对比实现 ---")
    i = _interp_with('func 平方(x: Int) -> Int = (x) => x * x')
    sb = i.sandbox()
    src = '''
#：{
  用例 = append(空列表)(list(2))
  [对比实现("平方")("Python")("def 平方(x): return x * x")(用例)]
}
'''
    outs, _, err = sb.run(src)
    assert err is None, err
    assert outs == [True], outs
    # 本体不受影响
    assert i.call("平方", 3) == 9
    sb.rollback()
    print(f"  ✓ 沙箱内 对比实现=True；本体未受影响")


# ============================================================
# runner
# ============================================================

def _run_all():
    tests = [
        # ForeignRunner
        test_foreign_eval_python_expression,
        test_foreign_eval_python_statement,
        test_foreign_eval_python_with_inputs,
        test_foreign_call_python_function,
        test_foreign_call_python_multi_arg,
        test_foreign_call_python_function_not_defined,
        test_foreign_eval_returns_list_and_dict,
        test_foreign_eval_empty_output,
        test_foreign_call_zero_arg_function,
        test_foreign_call_returns_list,
        test_foreign_eval_unsupported_language,
        test_foreign_call_unsupported_language,
        # DualComparator
        test_compare_all_match,
        test_compare_has_diffs,
        test_compare_partial_match,
        test_compare_matha_exception,
        test_compare_foreign_exception,
        test_compare_result_as_dict,
        test_compare_values_equal_type_tolerance,
        test_compare_empty_test_cases,
        test_compare_none_vs_value,
        test_compare_multi_arg_functions,
        test_compare_foreign_syntax_error,
        test_compare_returns_bool,
        test_compare_returns_list,
        # compare_upgrade
        test_compare_upgrade_success,
        test_compare_upgrade_mismatch_rolls_back,
        test_compare_upgrade_source_error_rolls_back,
        test_compare_upgrade_parse_error_rolls_back,
        test_compare_upgrade_redefine_function,
        test_compare_upgrade_empty_test_cases,
        test_compare_upgrade_extra_verify_pass,
        test_compare_upgrade_extra_verify_rejects,
        test_compare_upgrade_output_contains_summary,
        test_compare_upgrade_compare_exception_rolls_back,
        test_compare_upgrade_extra_verify_exception_rolls_back,
        test_compare_upgrade_redefine_mismatch_keeps_old,
        test_compare_upgrade_consecutive,
        test_compare_upgrade_failure_then_recovery,
        test_compare_upgrade_batch_functions,
        test_compare_upgrade_probe_reflects_change,
        # Matha 内建
        test_matha_builtin_foreign_eval,
        test_matha_builtin_foreign_eval_string,
        test_matha_builtin_compare_impl,
        test_matha_builtin_compare_impl_mismatch,
        test_matha_builtin_compare_upgrade,
        test_matha_builtin_compare_upgrade_failure_raises,
        test_matha_empty_list_builtin,
        test_matha_foreign_eval_in_sandbox,
        test_matha_foreign_eval_returns_list,
        test_matha_foreign_eval_statement_returns_none,
        test_matha_compare_upgrade_redefine,
        test_matha_compare_upgrade_zero_cases,
        test_interp_foreign_eval_method,
        test_matha_compare_impl_in_sandbox,
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
    print(f"\n{'='*52}")
    print(f"外部语言互操作测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
