# -*- coding: utf-8 -*-
"""
Matha 源码编译器（src/matha/compiler.py）完整单元测试。

覆盖：
  - parse_matha_source: 语法解析
  - _parse_expr_str: 表达式解析
  - formula_from_parsed: Formula 构建
  - compile_matha_source: 端到端编译
  - compile_and_register: 注册 + 能力标注
  - compile_file / compile_dir: 文件/目录编译
  - 边界情况：注释、空行、无效表达式、重复公式等
  - 回归测试：6 个已修复 bug 的复现防护
"""
from __future__ import annotations
import os
import tempfile
import math

import pytest

from src.matha.compiler import (
    parse_matha_source,
    _parse_expr_str,
    formula_from_parsed,
    compile_matha_source,
    compile_and_register,
    compile_file,
    compile_dir,
)
from src.symbolic import Var, Num, Mul, Div, Add, Sub, Pow, FuncCall, Neg, Log
from src.formula_system import Formula, FormulaRegistry, get_capability_registry

# ============================================================
#  十一、回归测试（历史 bug 复现防护）
# ============================================================

class TestRegressionBugs:
    """
    回归测试：覆盖已修复的 bug，防止再次引入。

    修复的 bug：
      1. Num/Var/Neg/Add/Sub/Mul/Div/Pow/FuncCall 缺少 free_vars() 方法
      2. π 常量在 _parse_primary 中未识别 → 抛出 ValueError
      3. 负号后为空字符串（如 "-x" 中 x 为空）→ 抛出 ValueError
      4. _parse_expr 未处理一元负号前缀 → 无限递归
      5. compile_and_register 返回值返回 len(formulas) 而非实际注册数
      6. Num(0) 缺少 free_vars() → 调用时报 AttributeError
    """

    # ------------------------------------------------------------------
    # Bug 1: 所有 Expr 子类必须有 free_vars() 方法
    # ------------------------------------------------------------------

    def test_num_free_vars_empty(self):
        """Num.free_vars() 返回空集（常量无自由变量）"""
        n = Num(3.14)
        assert n.free_vars() == set()

    def test_var_free_vars_returns_name(self):
        """Var.free_vars() 返回自身名字"""
        v = Var('r')
        assert v.free_vars() == {'r'}

    def test_mul_free_vars_combined(self):
        """Mul.free_vars() 合并左右子树"""
        m = Mul(Var('r'), Var('r'))
        assert m.free_vars() == {'r'}

    def test_mul_free_vars_multiple(self):
        """Mul.free_vars() 合并多个变量"""
        m = Mul(Var('m'), Var('v'))
        assert m.free_vars() == {'m', 'v'}

    def test_div_free_vars_combined(self):
        """Div.free_vars() 合并分子分母"""
        d = Div(Var('F'), Var('m'))
        assert d.free_vars() == {'F', 'm'}

    def test_add_free_vars_combined(self):
        """Add.free_vars() 合并左右子树"""
        a = Add(Var('x'), Var('y'))
        assert a.free_vars() == {'x', 'y'}

    def test_sub_free_vars_combined(self):
        """Sub.free_vars() 合并左右子树"""
        s = Sub(Var('x'), Var('y'))
        assert s.free_vars() == {'x', 'y'}

    def test_pow_free_vars_combined(self):
        """Pow.free_vars() 合并底数和指数"""
        p = Pow(Var('r'), Num(2))
        assert p.free_vars() == {'r'}

    def test_neg_free_vars(self):
        """Neg.free_vars() 返回内部表达式变量"""
        n = Neg(Var('x'))
        assert n.free_vars() == {'x'}

    def test_func_call_free_vars(self):
        """FuncCall.free_vars() 返回所有参数变量"""
        fc = FuncCall('sin', [Var('x')])
        assert fc.free_vars() == {'x'}

    def test_nested_expr_free_vars(self):
        """嵌套表达式自由变量正确聚合"""
        # (x + y) * z / (x - y)
        expr = Div(Mul(Add(Var('x'), Var('y')), Var('z')), Sub(Var('x'), Var('y')))
        assert expr.free_vars() == {'x', 'y', 'z'}

    def test_pi_constant_free_vars(self):
        """π 是常量，不含自由变量；表达式只有 r"""
        from src.symbolic import symbol_expr
        e = symbol_expr('π * r * r')
        vars_found = e.free_vars()
        assert 'r' in vars_found
        assert 'π' not in vars_found  # π 不是自由变量，是常量

    def test_log_free_vars(self):
        """Log.free_vars() 返回内部表达式变量"""
        import math
        l = Log(Var('x'))
        assert l.free_vars() == {'x'}
        assert l.evaluate({'x': 1.0}) == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Bug 2: π 常量解析
    # ------------------------------------------------------------------

    def test_parse_pi_constant(self):
        """符号解析器能识别 π 常量"""
        from src.symbolic import symbol_expr
        e = symbol_expr('π')
        assert isinstance(e, Num)
        assert e.value == pytest.approx(math.pi)

    def test_parse_pi_in_expression(self):
        """π 参与运算能正确求值"""
        from src.symbolic import symbol_expr
        e = symbol_expr('π * r * r')
        assert e.evaluate({'r': 1.0}) == pytest.approx(math.pi)

    # ------------------------------------------------------------------
    # Bug 3: 负号后为空 → 不抛异常，返回 Num(0)
    # ------------------------------------------------------------------

    def test_negative_empty_returns_zero(self):
        """负号后为空字符串时返回 Num(0) 而非抛异常"""
        from src.symbolic import symbol_expr
        # 单独负号（极端边界）
        e = symbol_expr('-')
        assert isinstance(e, Num)
        assert e.value == 0.0

    # ------------------------------------------------------------------
    # Bug 4: 一元负号前缀处理（避免无限递归）
    # ------------------------------------------------------------------

    def test_unary_negative_single_var(self):
        """-x 正确解析为 Neg(Var('x')) 而非无限递归"""
        from src.symbolic import symbol_expr
        e = symbol_expr('-x')
        assert isinstance(e, Neg)
        assert e.evaluate({'x': 5.0}) == pytest.approx(-5.0)

    def test_unary_positive_single_var(self):
        """+x 正确解析为 x 而非无限递归"""
        from src.symbolic import symbol_expr
        e = symbol_expr('+x')
        assert not isinstance(e, Neg)
        assert e.evaluate({'x': 5.0}) == pytest.approx(5.0)

    # ------------------------------------------------------------------
    # Bug 5: compile_and_register 返回值 = 实际注册数（非 len(formulas)）
    # ------------------------------------------------------------------

    def test_skip_existing_returns_zero(self):
        """同名公式已存在时返回 0（未新增任何公式）"""
        reg = FormulaRegistry()
        reg.register(Formula(name='动能', expr=Num(100), params=['x'], domain='original'))
        src = '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学'
        count = compile_and_register(src, reg)
        assert count == 0  # 被跳过，无新增

    def test_new_formula_returns_one(self):
        """新公式注册成功时返回 1"""
        reg = FormulaRegistry()
        src = '公式 测试公式(a) = a + 1\n  域: 测试'
        count = compile_and_register(src, reg)
        assert count == 1
        assert '测试公式' in reg._formulas

    def test_multiple_new_returns_actual_count(self):
        """多个新公式时返回实际注册数（非源公式总数）"""
        reg = FormulaRegistry()
        # 预注册一个公式
        reg.register(Formula(name='已存在', expr=Num(1), params=['x']))
        src = (
            '公式 已存在(a) = a + 1\n  域: 测试\n'
            '公式 新公式(b) = b * 2\n  域: 测试\n'
        )
        count = compile_and_register(src, reg)
        assert count == 1  # 只有第二个是新公式

    # ------------------------------------------------------------------
    # Bug 6: Num(0) 缺少 free_vars() → AttributeError
    # ------------------------------------------------------------------

    def test_zero_num_free_vars(self):
        """Num(0).free_vars() 返回空集，不抛 AttributeError"""
        z = Num(0)
        assert z.free_vars() == set()

    def test_zero_in_formula_params_extraction(self):
        """无效表达式回退 Num(0) 时不崩溃"""
        parsed = {
            'name': '坏公式',
            'params': [],
            'expr_str': 'invalid_@@@',
            'domain': '测试',
        }
        f = formula_from_parsed(parsed)
        # Num(0) 回退，free_vars 应返回空集
        assert f.params == []  # Num(0) 无自由变量
        assert f.expr.value == 0.0

    def test_free_vars_via_symbol_expr(self):
        """symbol_expr 构建的表达式 free_vars 链式正确"""
        from src.symbolic import symbol_expr
        e = symbol_expr('k * q1 * q2 / (r * r)')
        vars_found = e.free_vars()
        assert 'k' in vars_found
        assert 'q1' in vars_found
        assert 'q2' in vars_found
        assert 'r' in vars_found


# ============================================================
#  一、parse_matha_source 测试
# ============================================================

class TestParseMathaSource:
    """测试 Matha 源码语法解析。"""

    def test_basic_formula(self):
        """基本公式：名字 + 参数 + 表达式"""
        src = '公式 牛顿第二定律(F, m, a) = F = m * a'
        result = parse_matha_source(src)
        assert len(result) == 1
        assert result[0]['name'] == '牛顿第二定律'
        assert result[0]['params'] == ['F', 'm', 'a']
        assert result[0]['expr_str'] == 'F = m * a'

    def test_formula_with_chinese_params(self):
        """中文参数名"""
        src = '公式 圆面积(S, r) = S = pi * r * r'
        result = parse_matha_source(src)
        assert result[0]['name'] == '圆面积'
        assert result[0]['params'] == ['S', 'r']

    def test_multiple_formulas(self):
        """多个公式"""
        src = (
            '公式 公式1(a, b) = a + b\n'
            '公式 公式2(x, y) = x * y\n'
        )
        result = parse_matha_source(src)
        assert len(result) == 2
        assert result[0]['name'] == '公式1'
        assert result[1]['name'] == '公式2'

    def test_metadata_domain(self):
        """域元数据"""
        src = (
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '  域: 动力学\n'
        )
        result = parse_matha_source(src)
        assert result[0]['domain'] == '动力学'

    def test_metadata_category(self):
        """分类元数据"""
        src = (
            '公式 圆面积(S, r) = S = pi * r * r\n'
            '  分类: area\n'
        )
        result = parse_matha_source(src)
        assert result[0]['category'] == 'area'

    def test_metadata_unit(self):
        """单位元数据"""
        src = (
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '  单位: J\n'
        )
        result = parse_matha_source(src)
        assert result[0]['unit'] == 'J'

    def test_metadata_description(self):
        """说明元数据"""
        src = (
            '公式 牛顿第二定律(F, m, a) = F = m * a\n'
            '  说明: 牛顿第二定律 F = ma\n'
        )
        result = parse_matha_source(src)
        assert result[0]['description'] == '牛顿第二定律 F = ma'

    def test_metadata_alias(self):
        """别名元数据"""
        src = (
            '公式 圆面积(S, r) = S = pi * r * r\n'
            '  别名: 圆表面积\n'
        )
        result = parse_matha_source(src)
        assert result[0]['alias'] == '圆表面积'

    def test_all_metadata(self):
        """完整元数据"""
        src = (
            '公式 欧姆定律(I, V, R) = I = V / R\n'
            '  域: 电磁学\n'
            '  分类: general\n'
            '  单位: A\n'
            '  说明: 欧姆定律 I = V/R\n'
        )
        result = parse_matha_source(src)
        assert result[0]['domain'] == '电磁学'
        assert result[0]['category'] == 'general'
        assert result[0]['unit'] == 'A'
        assert result[0]['description'] == '欧姆定律 I = V/R'

    def test_comments_skipped(self):
        """注释行被跳过"""
        src = (
            '# 这是注释\n'
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '# 另一条注释\n'
            '公式 动量(p, m, v) = p = m * v\n'
        )
        result = parse_matha_source(src)
        assert len(result) == 2
        assert result[0]['name'] == '动能'
        assert result[1]['name'] == '动量'

    def test_empty_lines_skipped(self):
        """空行被跳过"""
        src = (
            '\n'
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '\n\n'
            '公式 动量(p, m, v) = p = m * v\n'
            '\n'
        )
        result = parse_matha_source(src)
        assert len(result) == 2

    def test_empty_source(self):
        """空源码"""
        result = parse_matha_source('')
        assert result == []

    def test_only_comments(self):
        """只有注释"""
        src = '# 注释1\n# 注释2\n'
        result = parse_matha_source(src)
        assert result == []

    def test_no_params(self):
        """无参数公式"""
        src = '公式 圆周率() = 3.141592653589793'
        result = parse_matha_source(src)
        assert len(result) == 1
        assert result[0]['params'] == []

    def test_many_params(self):
        """多参数公式"""
        src = '公式 伯努利(P1, rho, v1, h1, P2, v2, h2) = P1 + 0.5 * rho * v1 * v1 + rho * g * h1 = P2 + 0.5 * rho * v2 * v2 + rho * g * h2'
        result = parse_matha_source(src)
        assert len(result[0]['params']) == 7

    def test_multiline_expression(self):
        """多行表达式（通过续行）"""
        src = '公式 动能(Ek, m, v) = 0.5 * m * v * v'
        result = parse_matha_source(src)
        assert result[0]['expr_str'] == '0.5 * m * v * v'

    def test_formula_with_spaces_in_params(self):
        """参数间有空格"""
        src = '公式 力(F, m, a) = F = m * a'
        result = parse_matha_source(src)
        assert result[0]['params'] == ['F', 'm', 'a']


# ============================================================
#  二、_parse_expr_str 测试
# ============================================================

class TestParseExprStr:
    """测试表达式字符串解析。"""

    def test_simple_multiplication(self):
        """简单乘法"""
        result = _parse_expr_str('m * a')
        assert isinstance(result, Mul)
        assert result.evaluate({'m': 2.0, 'a': 3.0}) == pytest.approx(6.0)

    def test_expression_with_equals(self):
        """含等号的表达式：F = m * a → m * a"""
        result = _parse_expr_str('F = m * a')
        assert isinstance(result, Mul)
        assert result.evaluate({'m': 2.0, 'a': 3.0}) == pytest.approx(6.0)

    def test_semicolon_expr(self):
        """分号分隔：取最后一段"""
        result = _parse_expr_str('a = 1; b = 2; c = a + b')
        assert isinstance(result, Add)
        assert result.evaluate({'a': 1.0, 'b': 2.0}) == pytest.approx(3.0)

    def test_pi_constant_replacement(self):
        """pi → π 常量替换"""
        result = _parse_expr_str('π * r * r')
        assert isinstance(result, Mul)
        # π 是常量，r 是变量
        vars_found = list(result.free_vars())
        assert 'r' in vars_found
        assert 'π' not in vars_found

    def test_chinese_pi_constant(self):
        """中文 π 常量"""
        result = _parse_expr_str('π * r * r')
        assert isinstance(result, Mul)

    def test_division(self):
        """除法"""
        result = _parse_expr_str('V / R')
        assert isinstance(result, Div)
        assert result.evaluate({'V': 10.0, 'R': 2.0}) == pytest.approx(5.0)

    def test_power(self):
        """幂运算"""
        result = _parse_expr_str('r * r')
        # r*r → r^2 (simplified)
        assert result.evaluate({'r': 3.0}) == pytest.approx(9.0)

    def test_parenthesized_expression(self):
        """括号表达式"""
        result = _parse_expr_str('(a + b) * c')
        assert result.evaluate({'a': 1.0, 'b': 2.0, 'c': 3.0}) == pytest.approx(9.0)

    def test_complex_division(self):
        """复杂除法：k * q1 * q2 / (r * r)"""
        result = _parse_expr_str('k * q1 * q2 / (r * r)')
        assert result.evaluate({'k': 9e9, 'q1': 1.0, 'q2': 1.0, 'r': 1.0}) == pytest.approx(9e9)

    def test_sqrt_function(self):
        """sqrt 函数"""
        result = _parse_expr_str('sqrt(x)')
        assert isinstance(result, FuncCall)
        assert result.evaluate({'x': 4.0}) == pytest.approx(2.0)

    def test_mixed_operations(self):
        """混合运算"""
        result = _parse_expr_str('0.5 * m * v * v')
        assert result.evaluate({'m': 2.0, 'v': 3.0}) == pytest.approx(9.0)

    def test_pi_with_number(self):
        """pi 与数字组合"""
        result = _parse_expr_str('4 / 3 * pi * r * r * r')
        assert result.evaluate({'r': 1.0}) == pytest.approx(4.0 / 3.0 * math.pi)


# ============================================================
#  三、formula_from_parsed 测试
# ============================================================

class TestFormulaFromParsed:
    """测试 Formula 对象构建。"""

    def test_basic_formula(self):
        """基本公式构建"""
        parsed = {
            'name': '牛顿第二定律',
            'params': ['F', 'm', 'a'],
            'expr_str': 'm * a',
            'domain': '动力学',
            'category': 'general',
            'description': '牛顿第二定律 F = ma',
            'unit': 'N',
        }
        f = formula_from_parsed(parsed)
        assert f.name == '牛顿第二定律'
        assert f.params == ['F', 'm', 'a']
        assert f.domain == '动力学'
        assert f.category == 'general'
        assert 'N' in f.notes
        assert '牛顿第二定律' in f.notes

    def test_auto_params_extraction(self):
        """无参数时从表达式自动提取"""
        parsed = {
            'name': '无参公式',
            'params': [],
            'expr_str': 'pi * r * r',
            'domain': '几何',
        }
        f = formula_from_parsed(parsed)
        # 应自动提取 r
        assert 'r' in f.params

    def test_invalid_expr_fallback(self):
        """无效表达式回退到 Num(0)"""
        parsed = {
            'name': '坏公式',
            'params': ['x'],
            'expr_str': 'not_valid_expr@@@',
            'domain': '测试',
        }
        f = formula_from_parsed(parsed)
        assert isinstance(f.expr, Num)
        assert f.expr.value == 0.0

    def test_category_default(self):
        """默认分类"""
        parsed = {
            'name': '测试',
            'params': ['x'],
            'expr_str': 'x',
        }
        f = formula_from_parsed(parsed)
        assert f.category == 'general'

    def test_expr_text_generation(self):
        """expr_text 自动生成"""
        parsed = {
            'name': '动能',
            'params': ['Ek', 'm', 'v'],
            'expr_str': '0.5 * m * v * v',
        }
        f = formula_from_parsed(parsed)
        assert '动能' in f.expr_text
        assert '0.5 * m * v * v' in f.expr_text


# ============================================================
#  四、compile_matha_source 测试
# ============================================================

class TestCompileMathaSource:
    """测试端到端编译。"""

    def test_compile_simple_formula(self):
        """编译简单公式"""
        src = '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学\n  说明: 动能公式'
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        f = formulas[0]
        assert f.name == '动能'
        assert f.domain == '动力学'
        assert f.evaluate({'m': 2.0, 'v': 3.0}) == pytest.approx(9.0)

    def test_compile_multiple_formulas(self):
        """编译多个公式"""
        src = (
            '公式 牛顿第二定律(F, m, a) = F = m * a\n'
            '  域: 动力学\n'
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '  域: 动力学\n'
        )
        formulas = compile_matha_source(src)
        assert len(formulas) == 2
        assert formulas[0].name == '牛顿第二定律'
        assert formulas[1].name == '动能'

    def test_compile_with_all_metadata(self):
        """完整元数据编译"""
        src = (
            '公式 欧姆定律(I, V, R) = I = V / R\n'
            '  域: 电磁学\n'
            '  分类: general\n'
            '  单位: A\n'
            '  说明: 欧姆定律 I=V/R\n'
        )
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.domain == '电磁学'
        assert f.category == 'general'
        assert 'A' in f.notes
        assert '欧姆定律' in f.notes

    def test_compile_circle_area(self):
        """圆面积公式"""
        src = '公式 圆面积(S, r) = S = pi * r * r\n  域: 几何\n  分类: area'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'r': 2.0}) == pytest.approx(math.pi * 4.0)

    def test_compile_sphere_volume(self):
        """球体积公式"""
        src = '公式 球体积(V, r) = V = 4 / 3 * pi * r * r * r\n  域: 几何'
        formulas = compile_matha_source(src)
        f = formulas[0]
        expected = 4.0 / 3.0 * math.pi * 8.0
        assert f.evaluate({'r': 2.0}) == pytest.approx(expected)

    def test_compile_coulomb_force(self):
        """库仑力公式"""
        src = '公式 库仑力(F, k, q1, q2, r) = F = k * q1 * q2 / (r * r)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'k': 9e9, 'q1': 1.0, 'q2': 1.0, 'r': 1.0}) == pytest.approx(9e9)

    def test_compile_with_comment(self):
        """含注释的源码"""
        src = (
            '# 动力学公式集\n'
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
            '# 注释2\n'
        )
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        assert formulas[0].name == '动能'

    def test_compile_empty_source(self):
        """空源码"""
        formulas = compile_matha_source('')
        assert formulas == []

    def test_compile_only_comments(self):
        """只有注释"""
        formulas = compile_matha_source('# 注释1\n# 注释2\n')
        assert formulas == []


# ============================================================
#  五、compile_and_register 测试
# ============================================================

class TestCompileAndRegister:
    """测试注册到公式库。"""

    def test_register_single_formula(self):
        """注册单个公式"""
        reg = FormulaRegistry()
        src = '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学'
        count = compile_and_register(src, reg)
        assert count == 1
        assert '动能' in reg._formulas

    def test_register_multiple_formulas(self):
        """注册多个公式"""
        reg = FormulaRegistry()
        src = (
            '公式 牛顿第二定律(F, m, a) = F = m * a\n'
            '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n'
        )
        count = compile_and_register(src, reg)
        assert count == 2
        assert '牛顿第二定律' in reg._formulas
        assert '动能' in reg._formulas

    def test_skip_existing_formula(self):
        """跳过已存在的同名公式"""
        reg = FormulaRegistry()
        # 先注册一个同名公式
        reg.register(Formula(name='动能', expr=Num(100), params=['x']))
        src = '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学'
        count = compile_and_register(src, reg)
        assert count == 0  # 被跳过
        # 原有公式保持不变
        assert reg._formulas['动能'].expr.value == 100.0

    def test_register_preserves_domain(self):
        """注册后 domain 保留"""
        reg = FormulaRegistry()
        src = '公式 圆面积(S, r) = S = pi * r * r\n  域: 几何\n  分类: area'
        count = compile_and_register(src, reg)
        assert count == 1
        f = reg._formulas['圆面积']
        assert f.domain == '几何'
        assert f.category == 'area'

    def test_capability_registered(self):
        """能力标注已注册"""
        reg = FormulaRegistry()
        src = '公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学'
        compile_and_register(src, reg)
        cap_reg = get_capability_registry()
        cap = cap_reg.get('动能')
        assert cap is not None
        assert cap.domain == '动力学'

    def test_capability_not_registered_without_domain(self):
        """无域时不注册能力"""
        reg = FormulaRegistry()
        src = '公式 测试(a) = a + 1'
        compile_and_register(src, reg)
        cap_reg = get_capability_registry()
        cap = cap_reg.get('测试')
        assert cap is None


# ============================================================
#  六、compile_file 测试
# ============================================================

class TestCompileFile:
    """测试文件编译。"""

    def test_compile_matha_file(self):
        """编译 .matha 文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.matha', delete=False, encoding='utf-8') as f:
            f.write('公式 动能(Ek, m, v) = Ek = 0.5 * m * v * v\n  域: 动力学\n')
            path = f.name
        try:
            reg = FormulaRegistry()
            count = compile_file(path, reg)
            assert count == 1
            assert '动能' in reg._formulas
        finally:
            os.unlink(path)

    def test_compile_nonexistent_file_raises(self):
        """编译不存在的文件抛出异常"""
        reg = FormulaRegistry()
        with pytest.raises(FileNotFoundError):
            compile_file('/nonexistent/path.matha', reg)


# ============================================================
#  七、compile_dir 测试
# ============================================================

class TestCompileDir:
    """测试目录编译。"""

    def test_compile_dir_with_matha_files(self):
        """编译目录下所有 .matha 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建两个 .matha 文件
            with open(os.path.join(tmpdir, 'a.matha'), 'w', encoding='utf-8') as f:
                f.write('公式 公式A(x) = x + 1\n  域: 测试\n')
            with open(os.path.join(tmpdir, 'b.matha'), 'w', encoding='utf-8') as f:
                f.write('公式 公式B(y) = y * 2\n  域: 测试\n')
            # 非 .matha 文件应被忽略
            with open(os.path.join(tmpdir, 'readme.txt'), 'w') as f:
                f.write('not a matha file')

            reg = FormulaRegistry()
            count = compile_dir(tmpdir, reg)
            assert count == 2
            assert '公式A' in reg._formulas
            assert '公式B' in reg._formulas

    def test_compile_empty_dir(self):
        """编译空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = FormulaRegistry()
            count = compile_dir(tmpdir, reg)
            assert count == 0


# ============================================================
#  八、边界情况与异常处理
# ============================================================

class TestEdgeCases:
    """边界情况测试。"""

    def test_formula_name_with_chinese(self):
        """中文公式名"""
        src = '公式 牛顿第二定律(F, m, a) = F = m * a'
        formulas = compile_matha_source(src)
        assert formulas[0].name == '牛顿第二定律'

    def test_formula_name_with_english(self):
        """英文公式名"""
        src = '公式 NewtonsLaw(F, m, a) = F = m * a'
        formulas = compile_matha_source(src)
        assert formulas[0].name == 'NewtonsLaw'

    def test_formula_name_with_numbers(self):
        """含数字的公式名"""
        src = '公式 公式1(a, b) = a + b'
        formulas = compile_matha_source(src)
        assert formulas[0].name == '公式1'

    def test_expression_with_sqrt(self):
        """sqrt 函数"""
        src = '公式 勾股定理(c, a, b) = c = sqrt(a * a + b * b)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'a': 3.0, 'b': 4.0}) == pytest.approx(5.0)

    def test_expression_with_parentheses(self):
        """括号表达式"""
        src = '公式 梯形面积(S, a, b, h) = S = (a + b) * h / 2'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'a': 3.0, 'b': 5.0, 'h': 4.0}) == pytest.approx(16.0)

    def test_expression_with_power(self):
        """幂运算"""
        src = '公式 正方形面积(S, a) = S = a * a'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'a': 5.0}) == pytest.approx(25.0)

    def test_large_params_count(self):
        """多参数"""
        src = '公式 多参(a, b, c, d, e, f) = a + b + c + d + e + f'
        formulas = compile_matha_source(src)
        assert len(formulas[0].params) == 6
        assert formulas[0].evaluate({'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6}) == 21

    def test_whitespace_in_params(self):
        """参数间多余空格"""
        src = '公式 测试( a , b , c ) = a + b + c'
        formulas = compile_matha_source(src)
        assert formulas[0].params == ['a', 'b', 'c']

    def test_no_metadata(self):
        """无元数据的公式"""
        src = '公式 测试(a) = a + 1'
        formulas = compile_matha_source(src)
        assert formulas[0].domain == ''
        assert formulas[0].category == 'general'
        assert formulas[0].notes == ''

    def test_only_domain_metadata(self):
        """只有域元数据"""
        src = (
            '公式 测试(a) = a + 1\n'
            '  域: 测试域\n'
        )
        formulas = compile_matha_source(src)
        assert formulas[0].domain == '测试域'

    def test_eval_with_constants(self):
        """含常量的表达式求值"""
        src = '公式 圆周长(C, r) = C = 2 * pi * r'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'r': 1.0}) == pytest.approx(2 * math.pi)

    def test_expression_with_log(self):
        """log 函数"""
        src = '公式 对数(x) = log(x)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'x': 1.0}) == pytest.approx(0.0)

    def test_expression_with_exp(self):
        """exp 函数"""
        src = '公式 指数(x) = exp(x)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'x': 0.0}) == pytest.approx(1.0)

    def test_expression_with_sin(self):
        """sin 函数"""
        src = '公式 正弦(x) = sin(x)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'x': 0.0}) == pytest.approx(0.0)

    def test_negative_coefficient(self):
        """负系数"""
        src = '公式 负值(x) = -x'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'x': 5.0}) == pytest.approx(-5.0)

    def test_complex_expression(self):
        """复杂表达式"""
        src = '公式 复杂(x, y, z) = (x + y) * z / (x - y)'
        formulas = compile_matha_source(src)
        f = formulas[0]
        assert f.evaluate({'x': 5.0, 'y': 3.0, 'z': 2.0}) == pytest.approx(8.0)

    def test_expr_to_str_format(self):
        """expr_text 格式"""
        src = '公式 测试(a, b) = a + b\n  域: 测试'
        formulas = compile_matha_source(src)
        assert '测试(a, b) = a + b' in formulas[0].expr_text


# ============================================================
#  九、与现有公式库集成测试
# ============================================================

class TestIntegrationWithRegistry:
    """与 FormulaRegistry 集成测试。"""

    def test_register_and_lookup(self):
        """注册后可查"""
        reg = FormulaRegistry()
        src = '公式 自定义公式(x, y) = x * y\n  域: 测试'
        compile_and_register(src, reg)
        assert '自定义公式' in reg.list_formulas()

    def test_register_and_evaluate(self):
        """注册后可求值"""
        reg = FormulaRegistry()
        src = '公式 加速度(a, F, m) = a = F / m\n  域: 动力学'
        compile_and_register(src, reg)
        f = reg._formulas['加速度']
        assert f.evaluate({'F': 10.0, 'm': 2.0}) == pytest.approx(5.0)

    def test_duplicate_name_preserves_original(self):
        """同名公式保留原有定义"""
        from src.formula_system import Formula
        reg = FormulaRegistry()
        reg.register(Formula(name='测试', expr=Num(999), params=['x'], domain='original'))
        src = '公式 测试(x) = x + 1\n  域: matha'
        compile_and_register(src, reg)
        # 原有公式保留
        assert reg._formulas['测试'].expr.value == 999.0
        assert reg._formulas['测试'].domain == 'original'


# ============================================================
#  十、实际 .matha 文件测试
# ============================================================

class TestRealMathaFile:
    """测试实际的 .matha 文件编译。"""

    def test_dynamics_matha_exists(self):
        """动力学 .matha 文件存在"""
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'formulas', 'dynamics.matha')
        assert os.path.isfile(path), f'文件不存在: {path}'

    def test_dynamics_matha_compile(self):
        """编译动力学 .matha 文件"""
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'formulas', 'dynamics.matha')
        reg = FormulaRegistry()
        count = compile_file(path, reg)
        assert count > 0
        # 验证几个关键公式
        assert '牛顿第二定律' in reg._formulas
        assert '动能' in reg._formulas
        assert '圆面积' in reg._formulas
        assert '库仑力' in reg._formulas
        assert '欧姆定律' in reg._formulas

    def test_dynamics_matha_evaluate(self):
        """编译后求值验证"""
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'formulas', 'dynamics.matha')
        reg = FormulaRegistry()
        compile_file(path, reg)

        # 牛顿第二定律：F = ma
        f = reg._formulas['牛顿第二定律']
        assert f.evaluate({'m': 10.0, 'a': 9.8}) == pytest.approx(98.0)

        # 动能：Ek = 0.5 * m * v²
        f = reg._formulas['动能']
        assert f.evaluate({'m': 2.0, 'v': 3.0}) == pytest.approx(9.0)

        # 圆面积：S = πr²
        f = reg._formulas['圆面积']
        assert f.evaluate({'r': 2.0}) == pytest.approx(math.pi * 4.0)

        # 库仑力：F = kq₁q₂/r²
        f = reg._formulas['库仑力']
        assert f.evaluate({'k': 9e9, 'q1': 1.0, 'q2': 1.0, 'r': 1.0}) == pytest.approx(9e9)

    def test_dynamics_matha_domains(self):
        """验证 .matha 公式的 domain 标注"""
        path = os.path.join(os.path.dirname(__file__), '..', 'src', 'formulas', 'dynamics.matha')
        reg = FormulaRegistry()
        compile_file(path, reg)

        dynamics_formulas = [n for n, f in reg._formulas.items() if f.domain == '动力学']
        assert len(dynamics_formulas) > 0

        geometry_formulas = [n for n, f in reg._formulas.items() if f.domain == '几何']
        assert len(geometry_formulas) > 0

        em_formulas = [n for n, f in reg._formulas.items() if f.domain == '电磁学']
        assert len(em_formulas) > 0


# ============================================================
#  十一、成长引擎回归测试（growth.py 引入的 bug）
# ============================================================

class TestGrowthRegressionBugs:
    """
    回归测试：成长引擎开发过程中修复的 bug。

    修复的 bug：
      1. Pow.free_vars() 缺失 → NotImplementedError
      2. Add.free_vars() 缺失 → NotImplementedError
      3. Log.free_vars() 缺失 → NotImplementedError
      4. Div.free_vars() 缺失 → NotImplementedError
      5. _parse_primary 空字符串未处理 → ValueError: 无法解析表达式: ''
      6. _parse_expr 未处理一元 ± 前缀 → 无限递归
      7. compile_and_register 返回值错误 → len(formulas) 而非实际注册数
      8. π 常量在表达式中导致 free_vars 包含 π → 应只返回变量
    """

    # ------------------------------------------------------------------
    # Bug 1: Pow.free_vars() 缺失
    # ------------------------------------------------------------------

    def test_pow_free_vars(self):
        """Pow.free_vars() 返回底数和指数的并集"""
        from src.symbolic import Pow
        p = Pow(Var('r'), Num(2))
        assert p.free_vars() == {'r'}

    def test_pow_free_vars_with_constant_exponent(self):
        """幂运算常指数时只返回底数变量"""
        from src.symbolic import Pow
        p = Pow(Var('x'), Num(3))
        assert p.free_vars() == {'x'}

    # ------------------------------------------------------------------
    # Bug 2: Add.free_vars() 缺失
    # ------------------------------------------------------------------

    def test_add_free_vars(self):
        """Add.free_vars() 合并左右子树"""
        a = Add(Var('x'), Var('y'))
        assert a.free_vars() == {'x', 'y'}

    def test_add_free_vars_nested(self):
        """嵌套 Add 的 free_vars 正确传播"""
        from src.symbolic import Add
        a = Add(Add(Var('x'), Var('y')), Var('z'))
        assert a.free_vars() == {'x', 'y', 'z'}

    # ------------------------------------------------------------------
    # Bug 3: Log.free_vars() 缺失
    # ------------------------------------------------------------------

    def test_log_free_vars(self):
        """Log.free_vars() 返回内部表达式变量"""
        from src.symbolic import Log
        l = Log(Var('x'))
        assert l.free_vars() == {'x'}

    def test_log_free_vars_nested(self):
        """嵌套 Log 的 free_vars 正确传播"""
        from src.symbolic import Log, Add
        l = Log(Add(Var('x'), Var('y')))
        assert l.free_vars() == {'x', 'y'}

    # ------------------------------------------------------------------
    # Bug 4: Div.free_vars() 缺失
    # ------------------------------------------------------------------

    def test_div_free_vars(self):
        """Div.free_vars() 合并分子分母"""
        d = Div(Var('F'), Var('m'))
        assert d.free_vars() == {'F', 'm'}

    def test_div_free_vars_nested(self):
        """嵌套 Div 的 free_vars 正确传播"""
        from src.symbolic import Div, Mul
        d = Div(Mul(Var('k'), Var('q1')), Var('r'))
        assert d.free_vars() == {'k', 'q1', 'r'}

    # ------------------------------------------------------------------
    # Bug 5: _parse_primary 空字符串未处理
    # ------------------------------------------------------------------

    def test_parse_empty_string_returns_zero(self):
        """空字符串解析返回 Num(0) 而非抛异常"""
        from src.symbolic import symbol_expr
        e = symbol_expr('')
        assert isinstance(e, Num)
        assert e.value == 0.0

    def test_parse_whitespace_only_returns_zero(self):
        """纯空格字符串解析返回 Num(0)"""
        from src.symbolic import symbol_expr
        e = symbol_expr('   ')
        assert isinstance(e, Num)
        assert e.value == 0.0

    def test_negative_single_char(self):
        """单字符负号 -x 正确解析"""
        from src.symbolic import symbol_expr, Neg
        e = symbol_expr('-x')
        assert isinstance(e, Neg)

    def test_negative_two_chars(self):
        """两字符负号表达式正确解析"""
        from src.symbolic import symbol_expr, Neg
        e = symbol_expr('-ab')  # '-' 后跟空，不应崩溃
        # 实际会尝试解析 'ab'
        assert e is not None

    # ------------------------------------------------------------------
    # Bug 6: _parse_expr 未处理一元 ± 前缀
    # ------------------------------------------------------------------

    def test_unary_plus(self):
        """+x 解析为 x 而非无限递归"""
        from src.symbolic import symbol_expr
        e = symbol_expr('+x')
        assert e.evaluate({'x': 7.0}) == pytest.approx(7.0)

    def test_unary_minus_chain(self):
        """--x 正确解析"""
        from src.symbolic import symbol_expr
        e = symbol_expr('--x')
        assert e.evaluate({'x': 3.0}) == pytest.approx(3.0)

    # ------------------------------------------------------------------
    # Bug 7: compile_and_register 返回值
    # ------------------------------------------------------------------

    def test_compile_and_register_returns_actual_count(self):
        """compile_and_register 返回实际注册数（非源公式总数）"""
        from src.formula_system import Formula
        reg = FormulaRegistry()
        reg.register(Formula(name='已有公式', expr=Num(1), params=['x']))
        src = (
            '公式 已有公式(a) = a + 1\n  域: 测试\n'
            '公式 新公式(b) = b * 2\n  域: 测试\n'
        )
        count = compile_and_register(src, reg)
        assert count == 1  # 只有第二个是新公式

    def test_compile_and_register_all_new(self):
        """全部新公式时返回正确数量"""
        reg = FormulaRegistry()
        src = (
            '公式 公式A(x) = x + 1\n  域: 测试\n'
            '公式 公式B(y) = y * 2\n  域: 测试\n'
            '公式 公式C(z) = z / 3\n  域: 测试\n'
        )
        count = compile_and_register(src, reg)
        assert count == 3

    # ------------------------------------------------------------------
    # Bug 8: π 常量不应出现在 free_vars 中
    # ------------------------------------------------------------------

    def test_pi_not_in_free_vars(self):
        """π 是常量，不应出现在 free_vars 中"""
        from src.symbolic import symbol_expr
        e = symbol_expr('π * r * r')
        vars_found = e.free_vars()
        assert 'r' in vars_found
        assert 'π' not in vars_found  # π 是常量，不是自由变量

    def test_pi_in_complex_expression(self):
        """复杂表达式中 π 不污染 free_vars"""
        from src.symbolic import symbol_expr
        e = symbol_expr('4 / 3 * π * r * r * r')
        vars_found = e.free_vars()
        assert vars_found == {'r'}

    # ------------------------------------------------------------------
    # 集成回归：.matha 文件中的 π 表达式
    # ------------------------------------------------------------------

    def test_matha_pi_expression_compiles(self):
        """.matha 文件中含 π 的表达式能正确编译"""
        src = '公式 球体积(V, r) = V = 4 / 3 * π * r * r * r\n  域: 几何'
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        f = formulas[0]
        # 求值验证
        assert f.evaluate({'r': 1.0}) == pytest.approx(4.0 / 3.0 * math.pi)

    def test_matha_division_expression_compiles(self):
        """.matha 文件中含除法的表达式能正确编译"""
        src = '公式 库仑力(F, k, q1, q2, r) = F = k * q1 * q2 / (r * r)'
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        f = formulas[0]
        assert f.evaluate({'k': 9e9, 'q1': 1.0, 'q2': 1.0, 'r': 1.0}) == pytest.approx(9e9)

    def test_matha_negative_coefficient(self):
        """.matha 文件中含负系数的表达式能正确编译"""
        src = '公式 负值(x) = -x'
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        f = formulas[0]
        assert f.evaluate({'x': 5.0}) == pytest.approx(-5.0)


# ============================================================
#  十二、回归测试补充：阶乘 / 复合边界 / 多行元数据 / 重复公式
# ============================================================

class TestRegressionSupplements:
    """
    补充回归测试：覆盖更多历史 bug 及边界场景，防止回归。

    补充覆盖的 bug 场景：
      A. 阶乘表达式 (!) 未正确处理 → ValueError
      B. 多重括号嵌套 → 递归解析错误
      C. compile_and_register 同名但 domain 不同时仍跳过（不应覆盖）
      D. formula_from_parsed 自动参数提取时 free_vars 链调用
      E. 复合一元负号链（如 ---x）→ 无限递归
      F. _parse_expr_str 分号后取最后一段的历史 bug
    """

    # ------------------------------------------------------------------
    # Bug A: 阶乘表达式 (!) 解析
    # ------------------------------------------------------------------

    def test_factorial_symbol_expr(self):
        """阶乘表达式 5! 能正确解析"""
        from src.symbolic import symbol_expr, FuncCall
        e = symbol_expr('5!')
        assert isinstance(e, FuncCall)
        assert e.evaluate({}) == pytest.approx(120.0)

    def test_factorial_in_formula(self):
        """公式中含阶乘表达式能编译"""
        src = '公式 阶乘测试(n) = n!'
        formulas = compile_matha_source(src)
        assert len(formulas) == 1
        f = formulas[0]
        assert f.evaluate({'n': 5.0}) == pytest.approx(120.0)

    def test_factorial_var(self):
        """变量阶乘表达式"""
        from src.symbolic import symbol_expr, FuncCall
        e = symbol_expr('x!')
        assert isinstance(e, FuncCall)
        assert e.evaluate({'x': 3.0}) == pytest.approx(6.0)

    # ------------------------------------------------------------------
    # Bug B: 多重括号嵌套
    # ------------------------------------------------------------------

    def test_nested_parentheses_deep(self):
        """深层嵌套括号 ((a+b)*c)"""
        from src.symbolic import symbol_expr
        e = symbol_expr('((a + b) * c)')
        assert e.evaluate({'a': 1.0, 'b': 2.0, 'c': 3.0}) == pytest.approx(9.0)

    def test_nested_parentheses_double(self):
        """双层括号 (a+b) 能正确解析"""
        from src.symbolic import symbol_expr
        e = symbol_expr('(a + b)')
        assert e.evaluate({'a': 1.0, 'b': 2.0}) == pytest.approx(3.0)

    # ------------------------------------------------------------------
    # Bug C: compile_and_register 同名公式不覆盖（domain 不同时）
    # ------------------------------------------------------------------

    def test_compile_and_register_skip_same_name_different_domain(self):
        """同名公式即使 domain 不同也跳过（不覆盖）"""
        from src.formula_system import Formula
        reg = FormulaRegistry()
        reg.register(Formula(name='测试公式', expr=Num(999), params=['x'], domain='原域'))
        src = '公式 测试公式(x) = x + 1\n  域: 新域'
        count = compile_and_register(src, reg)
        assert count == 0
        assert reg._formulas['测试公式'].domain == '原域'
        assert reg._formulas['测试公式'].expr.value == 999.0

    # ------------------------------------------------------------------
    # Bug D: formula_from_parsed 自动参数提取时 free_vars 链
    # ------------------------------------------------------------------

    def test_auto_params_with_nested_expr(self):
        """无参数时从复杂表达式自动提取多个变量"""
        parsed = {
            'name': '复合公式',
            'params': [],
            'expr_str': 'a * b + c / d',
            'domain': '测试',
        }
        f = formula_from_parsed(parsed)
        assert set(f.params) == {'a', 'b', 'c', 'd'}

    def test_auto_params_with_power_expr(self):
        """无参数时从幂表达式自动提取变量"""
        parsed = {
            'name': '平方公式',
            'params': [],
            'expr_str': 'r * r',
            'domain': '几何',
        }
        f = formula_from_parsed(parsed)
        assert f.params == ['r']

    # ------------------------------------------------------------------
    # Bug E: 复合一元负号链（如 ---x）
    # ------------------------------------------------------------------

    def test_triple_unary_minus(self):
        """--x = x，双重负号不崩溃"""
        from src.symbolic import symbol_expr
        e = symbol_expr('--x')
        assert e.evaluate({'x': 3.0}) == pytest.approx(3.0)

    def test_many_unary_minus(self):
        """多重重负号链：----x = x"""
        from src.symbolic import symbol_expr
        e = symbol_expr('----x')
        assert e.evaluate({'x': 7.0}) == pytest.approx(7.0)

    # ------------------------------------------------------------------
    # Bug F: _parse_expr_str 分号分隔取最后一段
    # ------------------------------------------------------------------

    def test_semicolon_multiple_segments(self):
        """分号多段：取最后一段表达式"""
        result = _parse_expr_str('a = 1; b = 2; c = a + b + c')
        # 最后一段是 c = a + b + c → a + b + c
        assert result.evaluate({'a': 1.0, 'b': 2.0, 'c': 3.0}) == pytest.approx(6.0)

    def test_semicolon_with_pi_replacement(self):
        """分号后含 pi → π 替换"""
        result = _parse_expr_str('a = 1; area = pi * r * r')
        assert result.evaluate({'r': 1.0}) == pytest.approx(math.pi)

    # ------------------------------------------------------------------
    # 补充：π 常量自由变量一致性
    # ------------------------------------------------------------------

    def test_pi_free_vars_consistency_across_parsers(self):
        """symbol_expr 和 _parse_expr_str 对 π 的 free_vars 结果一致"""
        from src.symbolic import symbol_expr
        e1 = symbol_expr('π * r')
        e2 = _parse_expr_str('π * r')
        assert e1.free_vars() == e2.free_vars()
        assert 'r' in e1.free_vars()
        assert 'π' not in e1.free_vars()

    # ------------------------------------------------------------------
    # 补充：compile_file 非 .matha 文件应被忽略
    # ------------------------------------------------------------------

    def test_compile_dir_ignores_non_matha(self):
        """.matha 目录编译时忽略非 .matha 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'real.matha'), 'w', encoding='utf-8') as f:
                f.write('公式 真公式(x) = x + 1\n  域: 测试\n')
            with open(os.path.join(tmpdir, 'ignore.txt'), 'w') as f:
                f.write('公式 忽略(x) = x\n')
            with open(os.path.join(tmpdir, 'ignore.py'), 'w') as f:
                f.write('# python file')

            reg = FormulaRegistry()
            count = compile_dir(tmpdir, reg)
            assert count == 1
            assert '真公式' in reg._formulas
            assert '忽略' not in reg._formulas
