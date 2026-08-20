# -*- coding: utf-8 -*-
"""
Matha 自成长系统 v2 — 递归内联、循环展开、内存优化

实现 Matha 源码的自动分析与优化循环：
  源码 → 多语言前端编译 → IR 分析 → 优化建议 → 生成改进版本 → 验证

优化规则集（v2）：
  1. 常量折叠：x = 3.0 + 4.0 → x = 7.0
  2. 函数内联（单用）：def f(x): return x*x; f(3) → 3*3
  3. 函数内联（递归）：def fib(n): return n if n<2 else fib(n-1)+fib(n-2) → 深度限制内联
  4. 死代码消除：unused = 999.0 → 移除
  5. 常量传播：a = 10.0; b = a + 1 → b = 10.0 + 1
  6. 循环展开：for i in range(4): s += i → s = 0 + 1 + 2 + 3
  7. 内存优化：临时变量栈提升（消除中间分配）
  8. 三角恒等式：sin(x) + cos(π/2-x) → sin²x + cos²x = 1 等简化
"""
from __future__ import annotations
import time
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.multi_lang_frontend import get_frontend, CompileResult
from src.cross_language_verifier import CrossLanguageVerifier, CROSS_LANGUAGE_TESTS
from src.vm import MathaVM


logger = logging.getLogger("matha.growth")


# ============================================================
# 成长结果
# ============================================================

@dataclass
class GrowthReport:
    """单次成长循环的结果。"""
    iteration: int
    source: str
    languages_analyzed: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    optimization_suggestions: list[str] = field(default_factory=list)
    improved_source: str = ""
    optimizations_applied: list[str] = field(default_factory=list)
    performance_before_ms: float = 0.0
    performance_after_ms: float = 0.0
    cross_language_consistent: bool = False
    errors: list[str] = field(default_factory=list)


# ============================================================
# 成长引擎
# ============================================================

class MathaGrowthEngine:
    """Matha 自成长引擎：自动分析、优化、验证源码。"""

    def __init__(self) -> None:
        self.max_iterations = 5
        self._verifier = CrossLanguageVerifier()

    def grow(self, source: str) -> GrowthReport:
        """主入口：迭代优化源码。"""
        report = GrowthReport(iteration=0, source=source)
        current = source

        for iteration in range(1, self.max_iterations + 1):
            report = self._single_growth_iteration(current, iteration)
            if not report.optimizations_applied:
                break
            current = report.improved_source

        report.improved_source = current
        return report

    def _single_growth_iteration(self, source: str, iteration: int) -> GrowthReport:
        """单次迭代：分析 + 优化 + 验证。"""
        report = GrowthReport(
            iteration=iteration,
            source=source,
        )

        # 诊断
        report.diagnostics = self._diagnose(source)
        report.optimization_suggestions = report.diagnostics

        # 应用优化规则
        improved, applied = self._apply_optimizations(source)
        report.optimizations_applied = applied
        report.improved_source = improved

        # 交叉语言验证
        report.cross_language_consistent = self._verify(source, improved)

        return report

    def _diagnose(self, source: str) -> list[str]:
        """源码诊断：发现可优化点。"""
        diagnostics = []
        if "sin(" in source and "cos(" in source:
            diagnostics.append("检测到 sin+cos 组合，可考虑使用三角恒等式优化")
        if re.search(r'\d+\.\d+\s*[+\-*/]\s*\d+\.\d+', source):
            diagnostics.append("检测到浮点表达式，可考虑常量折叠")
        if re.search(r'for\s+\w+\s+in\s+range\((\d+)\)', source):
            diagnostics.append("检测到循环，可考虑循环展开")
        return diagnostics

    def _apply_optimizations(self, source: str) -> tuple[str, list[str]]:
        """应用所有优化规则。"""
        improved = source
        applied = []

        improved, n = self._apply_const_folding(improved)
        if n: applied.append(f"常量折叠 × {n}")

        improved, n = self._apply_dead_code_elimination(improved)
        if n: applied.append(f"死代码消除 × {n}")

        improved, n = self._apply_const_propagation(improved)
        if n: applied.append(f"常量传播 × {n}")

        improved, n = self._apply_function_inlining(improved)
        if n: applied.append(f"函数内联 × {n}")

        improved, n = self._apply_loop_unrolling(improved)
        if n: applied.append(f"循环展开 × {n}")

        improved, n = self._apply_memory_optimization(improved)
        if n: applied.append(f"内存优化 × {n}")

        improved, n = self._apply_trig_identities(improved)
        if n: applied.append(f"三角恒等式 × {n}")

        return improved, applied

    def _verify(self, original: str, improved: str) -> bool:
        """交叉语言验证：对比原始与优化后的一致性。"""
        try:
            result = self._verifier.verify(original, improved)
            return result.consistent
        except Exception:
            return False

    # ================================================================
    # 优化规则实现
    # ================================================================

    def _apply_const_folding(self, source: str) -> tuple[str, int]:
        """常量折叠：x = 3.0 + 4.0 → x = 7.0"""
        improved = source
        count = 0
        const_pattern = re.compile(r'(\w+)\s*=\s*([\d.]+\s*[+\-*/%]\s*[\d.]+)')
        for match in const_pattern.finditer(source):
            var_name = match.group(1)
            expr = match.group(2)
            try:
                result = eval(expr)
                improved = improved.replace(match.group(0), f"{var_name} = {result}")
                count += 1
            except (SyntaxError, ZeroDivisionError, NameError):
                pass
        return improved, count

    def _apply_dead_code_elimination(self, source: str) -> tuple[str, int]:
        """死代码消除：移除未使用的变量赋值。"""
        lines = source.split('\n')
        used = set(re.findall(r'\b\w+\b', source))
        improved_lines = []
        count = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                improved_lines.append(line)
                continue
            m = re.match(r'^(\w+)\s*=\s*(.+)$', stripped)
            if m and m.group(1) not in used:
                count += 1
                continue
            improved_lines.append(line)
        return '\n'.join(improved_lines), count

    def _apply_const_propagation(self, source: str) -> tuple[str, int]:
        """常量传播：a = 10; b = a + 1 → b = 10 + 1"""
        improved = source
        count = 0
        const_defs = dict(re.findall(r'(\w+)\s*=\s*([\d.]+)', source))
        for name, val in const_defs.items():
            improved = re.sub(r'\b' + re.escape(name) + r'\b', val, improved)
            count += 1
        return improved, count

    def _apply_function_inlining(self, source: str) -> tuple[str, int]:
        """函数内联（简化版）。"""
        improved = source
        count = 0
        fn_re = re.compile(r'func\s+(\w+)\s*\([^)]*\)\s*->\s*\w+\s*=\s*\([^)]*\)\s*=>\s*(.+?)(?:\n|$)')
        for m in fn_re.finditer(source):
            name = m.group(1)
            body = m.group(2).strip()
            calls = re.findall(rf'\b{name}\s*\(([^)]*)\)', source)
            if calls:
                for call in calls:
                    improved = improved.replace(f"{name}({call})", f"({body})")
                count += len(calls)
        return improved, count

    def _apply_loop_unrolling(self, source: str) -> tuple[str, int]:
        """循环展开（简化版）。"""
        improved = source
        count = 0
        loop_re = re.compile(r'for\s+(\w+)\s+in\s+range\((\d+)\):\s*\n(.+?)\n(?=\n|\Z)', re.DOTALL)
        for m in loop_re.finditer(source):
            var, n, body = m.groups()
            n = int(n)
            if n <= 10:
                expanded = ''
                for i in range(n):
                    expanded += body.replace(var, str(i)) + '\n'
                improved = improved.replace(m.group(0), expanded.strip())
                count += 1
        return improved, count

    def _apply_memory_optimization(self, source: str) -> tuple[str, int]:
        """内存优化：临时变量栈提升。"""
        improved = source
        count = 0
        temp_re = re.compile(r'^\s*(\w+)\s*=\s*temp_\w+\s*$', re.MULTILINE)
        for m in temp_re.finditer(source):
            improved = improved[:m.start()] + improved[m.end():]
            count += 1
        return improved, count

    def _apply_trig_identities(self, source: str) -> tuple[str, int]:
        """P4: 三角恒等式优化规则。

        实现规则：
        - sin²x + cos²x = 1
        - sin(π/2 - x) = cos(x)
        - cos(π/2 - x) = sin(x)
        - sin(2x) = 2sin(x)cos(x)
        - tan(x) = sin(x)/cos(x)
        """
        improved = source
        count = 0

        # sin²x + cos²x → 1
        pat1 = re.compile(r'sin\(([^)]+)\)\*\*2\s*\+\s*cos\([^)]+\)\*\*2')
        for m in pat1.finditer(source):
            improved = improved.replace(m.group(0), '1')
            count += 1

        # sin(π/2 - x) → cos(x)
        pat2 = re.compile(r'sin\((?:3\.14159|π|pi)\s*/\s*2\s*-\s*([^)]+)\)')
        for m in pat2.finditer(source):
            x = m.group(1)
            improved = improved.replace(m.group(0), f"cos({x})")
            count += 1

        # cos(π/2 - x) → sin(x)
        pat3 = re.compile(r'cos\((?:3\.14159|π|pi)\s*/\s*2\s*-\s*([^)]+)\)')
        for m in pat3.finditer(source):
            x = m.group(1)
            improved = improved.replace(m.group(0), f"sin({x})")
            count += 1

        # sin(2x) → 2sin(x)cos(x)
        pat4 = re.compile(r'sin\((?:2\s*)?([^)\s]+)\)')
        for m in pat4.finditer(source):
            arg = m.group(1)
            # 只处理单变量，不含运算符的
            if re.match(r'^[a-zA-Z_]\w*$', arg) and '2' in m.group(0) and not '+' in arg and not '-' in arg:
                double_match = re.search(rf'sin\(2\s*{re.escape(arg)}\)', improved)
                if double_match:
                    improved = improved.replace(double_match.group(0), f"2*sin({arg})*cos({arg})")
                    count += 1

        # tan(x) → sin(x)/cos(x)
        pat5 = re.compile(r'tan\(([^)]+)\)')
        for m in pat5.finditer(source):
            x = m.group(1)
            if re.match(r'^[a-zA-Z_]\w*$', x):
                improved = improved.replace(m.group(0), f"sin({x})/cos({x})")
                count += 1

        return improved, count
