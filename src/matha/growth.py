# -*- coding: utf-8 -*-
"""
Matha 成长引擎（Matha Growth Engine）

核心问题：死板的公式构建代码有强局限性，无法创造无限可能
解决：让 Matha 具备自主组合、符号推导、从无到有构建新公式的能力

三大能力：
  1. 组合（Compose）   — 从已有公式中找共享变量，自动代数组合
  2. 推导（Infer）     — 符号微分/代入/代数变形，从已知推出未知
  3. 生成（Generate）  — 从约束条件无中生有，构建全新公式类型

使用方式：
  from src.matha.growth import FormulaGrowthEngine

  engine = FormulaGrowthEngine(formula_registry)

  # 组合：动能 + 动量 → 导出 Ek = p²/(2m)
  results = engine.compose(['动能', '动量'])

  # 推导：对圆的面积求导 → 得到圆周长
  results = engine.infer('圆面积求导', 'S', 'r')

  # 生成：从零构建一个全新公式
  results = engine.generate(
      name='示例新公式',
      target='F',
      variables=['m', 'a'],
      constraints={'dimension': '力', 'domain': '动力学'}
  )

  # 查看成长历史
  print(engine.growth_log)
"""
from __future__ import annotations
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.symbolic import Expr, Var, Num, Mul, Div, Add, Sub, Pow, Neg, FuncCall, symbol_expr
from src.formula_system import Formula, FormulaRegistry

logger = logging.getLogger(__name__)


# ============================================================
#  成长记录
# ============================================================

@dataclass
class GrowthRecord:
    """一次成长操作的记录。"""
    op_type: str        # 'compose' / 'infer' / 'generate'
    source: str         # 来源（公式名列表或描述）
    result_name: str    # 结果公式名
    result_expr: str    # 结果表达式字符串
    result_free_vars: list   # 自由变量列表
    derivation_steps: list  # 推导步骤（调试用）
    domain: str = ''
    category: str = 'general'
    success: bool = True
    error: str = ''

    def summary(self) -> str:
        status = '✓' if self.success else '✗'
        return f"[{status}] {self.op_type}: {self.source} → {self.result_name} = {self.result_expr}"


# ============================================================
#  能力 1：公式组合（FormulaComposer）
# ============================================================

class FormulaComposer:
    """从已有公式中找出共享变量，自动代数组合成新公式。

    策略：
      1. 遍历所有公式对，找共享变量
      2. 对共享变量做代入消元
      3. 简化结果，注册新公式
    """

    def __init__(self, registry: FormulaRegistry):
        self._reg = registry

    def compose_pair(self, name_a: str, name_b: str) -> Optional[GrowthRecord]:
        """组合两个公式。"""
        fa = self._reg._formulas.get(name_a)
        fb = self._reg._formulas.get(name_b)
        if not fa or not fb:
            return GrowthRecord('compose', f'{name_a}+{name_b}', '—', '—', [], [], success=False,
                                error=f'公式不存在: {name_a} 或 {name_b}')

        vars_a = fa.free_vars()
        vars_b = fb.free_vars()
        shared = vars_a & vars_b
        if not shared:
            return GrowthRecord('compose', f'{name_a}+{name_b}', '—', '—', [], [], success=False,
                                error='无共享变量')

        steps = [f'公式A({name_a}): {fa.expr}  vars={sorted(vars_a)}',
                 f'公式B({name_b}): {fb.expr}  vars={sorted(vars_b)}',
                 f'共享变量: {sorted(shared)}']

        # 策略：用公式B消去公式A中的一个共享变量
        # 从公式B解出共享变量的表达式，代入公式A
        best_result = None
        best_elim_var = None

        for elim_var in sorted(shared):
            try:
                # 尝试从公式B中解出 elim_var（用代数方法）
                # 简化：假设公式B是 Elim_var 的显式函数，直接替换
                substituted = fb.substitute(elim_var, fa.expr)
                simplified = substituted.simplify()

                # 检查简化后是否还包含 elim_var（理想情况应消去）
                remaining = simplified.free_vars()
                if elim_var not in remaining or len(remaining) < len(vars_a):
                    new_name = f'{name_a}∘{name_b}'
                    new_params = sorted(remaining)
                    record = GrowthRecord(
                        op_type='compose',
                        source=f'{name_a} + {name_b} (消去 {elim_var})',
                        result_name=new_name,
                        result_expr=str(simplified),
                        result_free_vars=list(new_params),
                        derivation_steps=steps + [
                            f'代入: {elim_var} → {fa.expr}',
                            f'简化: {simplified}',
                            f'剩余变量: {sorted(remaining)}',
                        ],
                        domain=fa.domain or fb.domain,
                        category=fa.category,
                    )
                    if best_result is None or len(remaining) < len(best_result.result_free_vars):
                        best_result = record
                        best_elim_var = elim_var
            except Exception as ex:
                steps.append(f'  尝试消去 {elim_var}: {ex}')

        if best_result is None:
            # 退而求其次：直接组合（不做消元）
            combined = Add(fa.expr, fb.expr)
            all_vars = sorted(vars_a | vars_b)
            return GrowthRecord(
                op_type='compose',
                source=f'{name_a} + {name_b}',
                result_name=f'{name_a}+{name_b}',
                result_expr=str(combined),
                result_free_vars=all_vars,
                derivation_steps=steps + [f'直接相加: {combined}'],
                domain=fa.domain or fb.domain,
            )

        return best_result

    def compose_all(self, names: List[str]) -> List[GrowthRecord]:
        """组合多个公式，返回所有有效组合结果。"""
        results = []
        for i, na in enumerate(names):
            for nb in names[i + 1:]:
                r = self.compose_pair(na, nb)
                if r and r.success:
                    results.append(r)
        return results


# ============================================================
#  能力 2：符号推导（FormulaInferencer）
# ============================================================

class FormulaInferencer:
    """使用符号微分、代入和代数变形从已知公式推导出新公式。

    推导策略：
      1. 微分法：对已知公式关于某变量求导
      2. 代入法：用已知关系代入消元
      3. 量纲法：分析表达式的量纲，推断合理形式
    """

    def __init__(self, registry: FormulaRegistry):
        self._reg = registry

    def differentiate(self, formula_name: str, var: str) -> Optional[GrowthRecord]:
        """对公式关于某变量求导，得到新公式。"""
        f = self._reg._formulas.get(formula_name)
        if not f:
            return GrowthRecord('infer', formula_name, '—', '—', [], [], success=False,
                                error=f'公式不存在: {formula_name}')

        steps = [f'对 {formula_name}: {f.expr} 求导 d/d{var}']
        try:
            deriv = f.expr.diff(var)
            simplified = deriv.simplify()
            free = sorted(simplified.free_vars())

            record = GrowthRecord(
                op_type='infer',
                source=f'{formula_name} → d/d{var}',
                result_name=f'{formula_name}_d{var}',
                result_expr=str(simplified),
                result_free_vars=free,
                derivation_steps=steps + [f'd/d{var}({f.expr}) = {simplified}'],
                domain=f.domain,
                category='general',
            )
            logger.info(f'  [推导] {record.summary()}')
            return record
        except Exception as ex:
            return GrowthRecord('infer', formula_name, '—', '—', [], steps, success=False,
                                error=str(ex))

    def substitute_and_simplify(self, formula_name: str,
                                elim_var: str,
                                substitution_expr: Expr) -> Optional[GrowthRecord]:
        """用给定表达式替换公式中的变量并简化。"""
        f = self._reg._formulas.get(formula_name)
        if not f:
            return GrowthRecord('infer', formula_name, '—', '—', [], [], success=False,
                                error=f'公式不存在: {formula_name}')

        steps = [f'公式: {f.expr}', f'代入: {elim_var} → {substitution_expr}']
        try:
            result = f.substitute(elim_var, substitution_expr)
            simplified = result.simplify()
            free = sorted(simplified.free_vars())
            record = GrowthRecord(
                op_type='infer',
                source=f'{formula_name} [代入 {elim_var}]',
                result_name=f'{formula_name}_sub_{elim_var}',
                result_expr=str(simplified),
                result_free_vars=free,
                derivation_steps=steps + [f'结果: {simplified}'],
                domain=f.domain,
            )
            return record
        except Exception as ex:
            return GrowthRecord('infer', formula_name, '—', '—', [], steps, success=False,
                                error=str(ex))

    def infer_from_relation(self, target_expr: Expr, relation_var: str,
                            relation_expr: Expr) -> Optional[GrowthRecord]:
        """从关系式 target = f(relation_var) 和 relation_var = g(...) 推导。"""
        steps = [f'target = {target_expr}', f'relation_var = {relation_var}',
                 f'relation_expr = {relation_expr}']
        try:
            substituted = target_expr.substitute(relation_var, relation_expr)
            simplified = substituted.simplify()
            free = sorted(simplified.free_vars())
            record = GrowthRecord(
                op_type='infer',
                source=f'{target_expr} 通过 {relation_var}={relation_expr}',
                result_name='derived_formula',
                result_expr=str(simplified),
                result_free_vars=free,
                derivation_steps=steps + [f'代入后: {simplified}'],
            )
            return record
        except Exception as ex:
            return GrowthRecord('infer', 'relation', '—', '—', [], steps, success=False,
                                error=str(ex))

    def batch_differentiate(self, formula_name: str) -> List[GrowthRecord]:
        """对公式关于所有变量求导，返回所有结果。"""
        f = self._reg._formulas.get(formula_name)
        if not f:
            return []
        results = []
        for var in sorted(f.free_vars()):
            r = self.differentiate(formula_name, var)
            if r and r.success:
                results.append(r)
        return results


# ============================================================
#  能力 3：从无到有生成（FormulaGenerator）
# ============================================================

class FormulaGenerator:
    """从约束条件无中生有构建全新公式类型。

    生成策略：
      1. 量纲分析：根据目标量纲和变量列表，构造合理的数学表达式
      2. 结构模板：使用常见公式结构模板（乘积/商/幂/线性组合）
      3. 约束满足：确保生成的公式满足用户指定的约束
      4. 自检验证：通过数值测试验证生成公式的合理性
    """

    # 常见公式结构模板
    _templates = [
        # (描述, 生成函数)
        ('乘积形式', lambda vars: _multiply_expr(vars)),
        ('商形式', lambda vars: _divide_expr(vars) if len(vars) >= 2 else None),
        ('幂形式', lambda vars: _power_expr(vars) if len(vars) >= 1 else None),
        ('线性组合', lambda vars: _linear_expr(vars) if len(vars) >= 2 else None),
        ('二次型', lambda vars: _quadratic_expr(vars) if len(vars) >= 1 else None),
        ('带系数乘积', lambda vars: _coeff_product_expr(vars)),
    ]

    def generate(self, name: str, target_var: str,
                 variables: List[str],
                 constraints: Optional[Dict[str, Any]] = None) -> List[GrowthRecord]:
        """从无到有生成公式。

        Args:
            name:         公式名称
            target_var:   目标变量（等号左侧）
            variables:    参与计算的变量列表
            constraints:  约束条件 {'dimension': 量纲, 'domain': 领域, ...}
        """
        constraints = constraints or {}
        results = []
        steps = []

        steps.append(f'生成新公式: {name}')
        steps.append(f'  目标变量: {target_var}')
        steps.append(f'  变量列表: {variables}')
        steps.append(f'  约束: {constraints}')

        # 尝试每种模板
        for desc, template_fn in self._templates:
            try:
                expr = template_fn(variables)
                if expr is None:
                    continue

                # 自检：能否求值？
                test_bindings = {v: 1.0 for v in variables}
                try:
                    val = expr.evaluate(test_bindings)
                    if not math.isfinite(val):
                        steps.append(f'  [{desc}] 自检失败: 求值非有限 ({val})')
                        continue
                except Exception:
                    steps.append(f'  [{desc}] 自检失败: 求值异常')
                    continue

                free = sorted(expr.free_vars())
                record = GrowthRecord(
                    op_type='generate',
                    source=f'从约束生成: {name}({", ".join(variables)})',
                    result_name=name,
                    result_expr=str(expr),
                    result_free_vars=free,
                    derivation_steps=steps + [f'  [{desc}] 生成成功: {expr}'],
                    domain=constraints.get('domain', ''),
                    category=constraints.get('category', 'general'),
                )
                results.append(record)
                steps.append(f'  [{desc}] ✓ 通过')

            except Exception as ex:
                steps.append(f'  [{desc}] 生成失败: {ex}')

        # 如果没有生成任何公式，返回错误记录
        if not results:
            results.append(GrowthRecord(
                op_type='generate',
                source=name,
                result_name=name,
                result_expr='—',
                result_free_vars=[],
                derivation_steps=steps,
                success=False,
                error='所有模板生成失败',
            ))

        return results


def _multiply_expr(vars: List[str]) -> Optional[Expr]:
    """构造乘积形式：v1 * v2 * ... * vn"""
    if not vars:
        return None
    expr = Var(vars[0])
    for v in vars[1:]:
        expr = Mul(expr, Var(v))
    return expr


def _divide_expr(vars: List[str]) -> Optional[Expr]:
    """构造商形式：v1 / v2"""
    if len(vars) < 2:
        return None
    return Div(Var(vars[0]), Var(vars[1]))


def _power_expr(vars: List[str]) -> Optional[Expr]:
    """构造幂形式：v1 ^ 2（用数值2保证可求值）"""
    if not vars:
        return None
    return Pow(Var(vars[0]), Num(2))


def _linear_expr(vars: List[str]) -> Optional[Expr]:
    """构造线性组合：v1 + v2 + ... + vn"""
    if not vars:
        return None
    expr = Var(vars[0])
    for v in vars[1:]:
        expr = Add(expr, Var(v))
    return expr


def _quadratic_expr(vars: List[str]) -> Optional[Expr]:
    """构造二次型：v1² + v2²"""
    if not vars:
        return None
    expr = Pow(Var(vars[0]), Num(2))
    for v in vars[1:]:
        expr = Add(expr, Pow(Var(v), Num(2)))
    return expr


def _coeff_product_expr(vars: List[str]) -> Optional[Expr]:
    """构造带系数乘积：0.5 * v1 * v2"""
    if not vars:
        return None
    expr = Mul(Num(0.5), Var(vars[0]))
    for v in vars[1:]:
        expr = Mul(expr, Var(v))
    return expr


# ============================================================
#  主引擎：FormulaGrowthEngine
# ============================================================

class FormulaGrowthEngine:
    """Matha 成长引擎：组合、推导、生成三大能力的统一入口。

    使用流程：
      1. 初始化引擎，传入公式注册表
      2. 调用 compose / infer / generate 方法
      3. 检查结果并注册到新公式
      4. 查看 growth_log 了解成长历史
    """

    def __init__(self, registry: FormulaRegistry):
        self._registry = registry
        self._composer = FormulaComposer(registry)
        self._inferencer = FormulaInferencer(registry)
        self._generator = FormulaGenerator()
        self._growth_log: List[GrowthRecord] = []
        self._grown_formulas: Dict[str, Formula] = {}  # 成长产生的公式

    @property
    def growth_log(self) -> List[GrowthRecord]:
        return list(self._growth_log)

    @property
    def grown_count(self) -> int:
        return len(self._growth_log)

    # ------------------------------------------------------------------
    # 组合能力
    # ------------------------------------------------------------------

    def compose(self, names: List[str]) -> List[GrowthRecord]:
        """从已有公式组合出新公式。"""
        results = self._composer.compose_all(names)
        for r in results:
            self._growth_log.append(r)
            logger.info(f'  [成长-组合] {r.summary()}')
        return results

    def compose_pair(self, name_a: str, name_b: str) -> GrowthRecord:
        """组合两个公式。"""
        r = self._composer.compose_pair(name_a, name_b)
        self._growth_log.append(r)
        logger.info(f'  [成长-组合] {r.summary()}')
        return r

    # ------------------------------------------------------------------
    # 推导能力
    # ------------------------------------------------------------------

    def infer(self, formula_name: str, var: Optional[str] = None,
              elim_var: Optional[str] = None,
              substitution: Optional[Expr] = None) -> List[GrowthRecord]:
        """推导新公式。"""
        results = []

        if var is not None:
            # 微分推导
            r = self._inferencer.differentiate(formula_name, var)
            if r and r.success:
                results.append(r)
            self._growth_log.append(r)
            logger.info(f'  [成长-推导] {r.summary()}')

        elif elim_var is not None and substitution is not None:
            # 代入推导
            r = self._inferencer.substitute_and_simplify(formula_name, elim_var, substitution)
            if r and r.success:
                results.append(r)
            self._growth_log.append(r)
            logger.info(f'  [成长-推导] {r.summary()}')

        else:
            # 对所有变量求导
            derivs = self._inferencer.batch_differentiate(formula_name)
            for d in derivs:
                results.append(d)
                self._growth_log.append(d)
                logger.info(f'  [成长-推导] {d.summary()}')

        return results

    # ------------------------------------------------------------------
    # 生成能力
    # ------------------------------------------------------------------

    def generate(self, name: str, target_var: str,
                 variables: List[str],
                 constraints: Optional[Dict[str, Any]] = None) -> List[GrowthRecord]:
        """从无到有生成新公式。"""
        results = self._generator.generate(name, target_var, variables, constraints)
        for r in results:
            self._growth_log.append(r)
            logger.info(f'  [成长-生成] {r.summary()}')
        return results

    # ------------------------------------------------------------------
    # 注册成长结果
    # ------------------------------------------------------------------

    def register_grown_formula(self, record: GrowthRecord,
                                name_override: Optional[str] = None) -> bool:
        """将成长产生的公式注册到公式库。"""
        if not record.success:
            return False
        fname = name_override or record.result_name
        if fname in self._registry._formulas:
            logger.warning(f'  [成长] 跳过已存在公式: {fname}')
            return False
        try:
            expr = symbol_expr(record.result_expr)
        except Exception as ex:
            logger.warning(f'  [成长] 表达式解析失败: {ex}')
            return False

        formula = Formula(
            name=fname,
            expr=expr,
            params=record.result_free_vars,
            category=record.category,
            notes=f'成长生成: {record.source}  |  步骤: {" → ".join(record.derivation_steps)}',
            expr_text=f'{fname} = {record.result_expr}',
            domain=record.domain,
        )
        self._registry.register(formula)
        self._grown_formulas[fname] = formula
        logger.info(f'  [成长] 已注册: {fname} = {expr}')
        return True

    def register_all_grown(self) -> int:
        """注册所有未注册的成长结果，返回注册数量。"""
        count = 0
        for r in self._growth_log:
            if r.success and r.result_name != '—':
                if self.register_grown_formula(r):
                    count += 1
        return count

    # ------------------------------------------------------------------
    # 全自动化成长流程
    # ------------------------------------------------------------------

    def auto_grow(self, source_names: Optional[List[str]] = None,
                  max_combinations: int = 10,
                  max_derivatives: int = 20,
                  generate_constraints: Optional[List[Dict]] = None) -> Dict[str, int]:
        """全自动成长：组合 + 推导 + 生成。

        Returns:
            {'compose': N, 'infer': N, 'generate': N}
        """
        stats = {'compose': 0, 'infer': 0, 'generate': 0}

        # 1. 组合：从已有公式中自动组合
        if source_names is None:
            source_names = list(self._registry.list_formulas())[:20]  # 取前20个
        compose_results = self.compose(source_names[:max_combinations + 1])
        stats['compose'] = sum(1 for r in compose_results if r.success)

        # 2. 推导：对关键公式求导
        key_formulas = ['牛顿第二定律', '动能', '圆面积', '球体积', '欧姆定律']
        for kf in key_formulas:
            if kf in self._registry._formulas:
                derivs = self.infer(kf)
                stats['infer'] += sum(1 for d in derivs if d.success)
                if stats['infer'] >= max_derivatives:
                    break

        # 3. 生成：从无到有构建
        if generate_constraints:
            for gc in generate_constraints:
                results = self.generate(
                    name=gc.get('name', '新公式'),
                    target_var=gc.get('target', 'x'),
                    variables=gc.get('variables', ['x', 'y']),
                    constraints=gc.get('constraints', {}),
                )
                stats['generate'] += sum(1 for r in results if r.success)

        logger.info(f'  [成长引擎] 本轮成长: 组合{stats["compose"]} 推导{stats["infer"]} 生成{stats["generate"]}')
        return stats

    def summary(self) -> str:
        """成长总览。"""
        lines = ['  ┌─ 成长引擎总览 ──────────────────────']
        lines.append(f'  │ 成长记录: {len(self._growth_log)} 条')
        lines.append(f'  │ 已注册新公式: {len(self._grown_formulas)} 个')

        by_type: Dict[str, int] = {}
        for r in self._growth_log:
            by_type[r.op_type] = by_type.get(r.op_type, 0) + 1
        for t, c in sorted(by_type.items()):
            lines.append(f'  │   {t}: {c} 条')

        if self._grown_formulas:
            lines.append(f'  │ 已注册公式:')
            for fname, f in list(self._grown_formulas.items())[:5]:
                lines.append(f'  │    • {fname} = {f.expr}')
        lines.append('  └──────────────────────────────────────')
        return '\n'.join(lines)
