# -*- coding: utf-8 -*-
"""
Matha 源码编译器（Matha Source Compiler）

核心问题：程序员/黑客直接写公式代码，但不标注定义 → 系统认知错乱
解决：提供 Matha 原生源码格式，每行公式自动标注能力元数据

Matha 源码语法：
    公式 公式名(参数列表) = 表达式
      域: 领域名
      分类: area/volume/perimeter/general
      单位: 物理单位
      说明: 中文描述

示例：
    公式 牛顿第二定律(F, m, a) = F = m * a
      域: 动力学
      分类: 力
      说明: 牛顿第二定律 F = ma

编译流程：
    1. parse_matha_source(src) → list[Formula]
    2. compile_to_registry(formulas, reg) → None
    3. compile_and_register(src, reg) → int  (已注册公式数)
"""
from __future__ import annotations
import re
from typing import Optional

from src.symbolic import Expr, Var, Num, Mul, Div, Add, Sub, Pow, Neg, FuncCall, symbol_expr
from src.formula_system import Formula, FormulaRegistry, get_capability_registry


# ============================================================
#  公式源码行解析
# ============================================================

# 公式声明：公式 名字(参数) = 表达式
FORMULA_RE = re.compile(
    r'^\s*公式\s+'
    r'(?P<name>\S+)\s*'
    r'\((?P<params>[^)]*)\)\s*=\s*(?P<expr>.+?)\s*$',
    re.DOTALL
)

# 元数据标签：键: 值
META_RE = re.compile(r'^\s*(?P<key>域|分类|单位|说明|别名)\s*:\s*(?P<value>.+?)\s*$')

# 公式块分隔：连续公式声明之间用空行或下一公式分隔
# 状态机：FORMULA_DECL → META_LINES → FORMULA_DECL


def parse_matha_source(src: str) -> list[dict]:
    """解析 Matha 源码，返回公式列表。

    每行公式包含：
        name:        公式名
        params:      参数名列表
        expr_str:    表达式字符串（右侧）
        domain:      领域（最后一个设置的值）
        category:    分类
        unit:        单位
        description: 说明
    """
    formulas = []
    lines = src.split('\n')
    i = 0
    current_meta = {}

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 跳过空行和注释
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # 公式声明
        m = FORMULA_RE.match(line)
        if m:
            # 先保存上一个公式（如果有）
            if current_meta:
                formulas.append(current_meta)
            name = m.group('name')
            params_str = m.group('params')
            expr_str = m.group('expr').strip()
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            current_meta = {
                'name': name,
                'params': params,
                'expr_str': expr_str,
                'domain': '',
                'category': 'general',
                'unit': '',
                'description': '',
            }
            i += 1
            continue

        # 元数据行
        mm = META_RE.match(line)
        if mm and current_meta is not None:
            key = mm.group('key')
            value = mm.group('value').strip()
            if key == '域':
                current_meta['domain'] = value
            elif key == '分类':
                current_meta['category'] = value
            elif key == '单位':
                current_meta['unit'] = value
            elif key == '说明':
                current_meta['description'] = value
            elif key == '别名':
                current_meta['alias'] = value
            i += 1
            continue

        i += 1

    # 保存最后一个公式
    if current_meta:
        formulas.append(current_meta)

    return formulas


def _parse_expr_str(expr_str: str) -> Expr:
    """将公式右侧表达式字符串解析为 Expr。

    支持格式：
      - "m * a"                     → 直接解析
      - "F = m * a"                 → 取右侧
      - "p = (a+b+c)/2; S = sqrt(...)"  → 取最后一段
    """
    # 统一常量名：pi → π（与现有公式库保持一致）
    expr_str = expr_str.replace('pi', 'π')
    # 取分号分隔的最后一段
    if ';' in expr_str:
        expr_str = expr_str.split(';')[-1].strip()
    # 处理 "name = expr" 格式，取右侧
    if '=' in expr_str:
        expr_str = expr_str.split('=', 1)[1].strip()
    return symbol_expr(expr_str)


def formula_from_parsed(parsed: dict) -> Formula:
    """从解析结果构建 Formula 对象。"""
    name = parsed['name']
    params = parsed['params']
    domain = parsed.get('domain', '')
    category = parsed.get('category', 'general')
    description = parsed.get('description', '')
    expr_str = parsed['expr_str']
    unit = parsed.get('unit', '')

    try:
        expr = _parse_expr_str(expr_str)
    except Exception:
        expr = Num(0)

    # 从表达式自动提取参数
    if not params:
        params = list(sorted(expr.free_vars()))

    notes = description
    if unit:
        notes = f"{notes}  [{unit}]" if notes else unit

    return Formula(
        name=name,
        expr=expr,
        params=params,
        category=category,
        notes=notes,
        expr_text=f"{name}({', '.join(params)}) = {expr_str}",
        domain=domain,
    )


def compile_matha_source(src: str) -> list[Formula]:
    """编译 Matha 源码，返回 Formula 列表。"""
    parsed = parse_matha_source(src)
    return [formula_from_parsed(p) for p in parsed]


def compile_and_register(src: str, registry: FormulaRegistry) -> int:
    """编译 Matha 源码并注册到公式库，返回注册数量。
    跳过已存在的公式（避免覆盖参数名不一致的同名公式）。"""
    formulas = compile_matha_source(src)
    count = 0
    for formula in formulas:
        if formula.name in registry._formulas:
            continue  # 跳过已存在的公式
        registry.register(formula)
        count += 1
    # 同步能力标注
    try:
        from src.formula_system import get_capability_registry
        cap_reg = get_capability_registry()
        for formula in formulas:
            if formula.domain:
                # 创建一个虚拟 Capability（从 Formula 提取）
                from src.formula_system import Capability
                cap = Capability(
                    name=formula.name,
                    domain=formula.domain,
                    capability=formula.name,
                    params=formula.params,
                    expr=formula.expr,
                    description=formula.notes,
                )
                cap_reg.register(cap)
    except Exception:
        pass
    return count


def compile_file(path: str, registry: FormulaRegistry) -> int:
    """编译 Matha 源文件。"""
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    return compile_and_register(src, registry)


def compile_dir(dir_path: str, registry: FormulaRegistry) -> int:
    """编译目录下所有 .matha 文件。"""
    import os
    total = 0
    for fname in sorted(os.listdir(dir_path)):
        if fname.endswith('.matha'):
            fpath = os.path.join(dir_path, fname)
            total += compile_file(fpath, registry)
    return total
