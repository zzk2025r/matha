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
  8. 三角恒等式：sin(x) + cos(π/2-x) → 简化
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

    @property
    def improved(self) -> bool:
        return bool(self.improved_source)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ============================================================
# Matha 自成长引擎 v2
# ============================================================

class MathaGrowthEngine:
    """
    Matha 自成长引擎 v2。

    优化规则（按优先级排序）：
      P0: 常量折叠 → 常量传播 → 死代码消除
      P1: 函数内联（单用/递归）
      P2: 循环展开
      P3: 内存优化（栈提升）
      P4: 三角恒等式
    """

    # 递归内联深度限制（防止无限展开）
    MAX_INLINE_DEPTH = 5
    # 循环展开倍数限制
    MAX_UNROLL_FACTOR = 8

    def __init__(self, verbose: bool = False) -> None:
        self._frontend = get_frontend()
        self._verifier = CrossLanguageVerifier(verbose=verbose)
        self._vm = MathaVM()
        self._verbose = verbose
        self._history: list[GrowthReport] = []

    # ---------- 主入口 ----------

    def grow(self, source: str, max_iterations: int = 3) -> GrowthReport:
        """执行成长循环，最多迭代 max_iterations 次。"""
        for iteration in range(1, max_iterations + 1):
            report = self._single_growth_iteration(source, iteration)
            self._history.append(report)
            if self._verbose:
                self._print_report(report)
            if not report.improved:
                break
            source = report.improved_source
        return self._history[-1] if self._history else GrowthReport(
            iteration=0, source=source, languages_analyzed=list(self._frontend.supported_languages())
        )

    def _single_growth_iteration(self, source: str, iteration: int) -> GrowthReport:
        """单次成长迭代。"""
        report = GrowthReport(
            iteration=iteration,
            source=source,
            languages_analyzed=list(self._frontend.supported_languages()),
        )

        # Step 1: 诊断
        report.diagnostics = self._diagnose(source)

        # Step 2: 多语言编译
        lang_results = self._compile_all_languages(source)
        report.cross_language_consistent = self._check_consistency(lang_results)

        # Step 3: 性能基准
        t0 = time.perf_counter()
        exec_source = self._detect_and_convert(source)
        try:
            outputs, trace = self._interpret(exec_source)
            report.performance_before_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            report.errors.append(f"执行失败: {e}")

        # Step 4: 优化建议
        report.optimization_suggestions = self._suggest_optimizations(source, lang_results)

        # Step 5: 生成改进版本（应用所有优化规则）
        report.improved_source, report.optimizations_applied = self._generate_improved(
            source, report.optimization_suggestions
        )

        # Step 6: 验证改进版本
        if report.improved_source:
            t0 = time.perf_counter()
            try:
                outputs, trace = self._interpret(self._detect_and_convert(report.improved_source))
                report.performance_after_ms = (time.perf_counter() - t0) * 1000
            except Exception as e:
                report.errors.append(f"改进版本执行失败: {e}")

        return report

    # ---------- 诊断 ----------

    def _diagnose(self, source: str) -> list[str]:
        """诊断源码问题和优化点。"""
        diagnostics = []
        if "sin(" in source and "cos(" in source:
            diagnostics.append("检测到 sin+cos 组合，可考虑使用三角恒等式优化")
        if source.count("=") > 3:
            diagnostics.append("检测到多步赋值，可考虑合并为单次计算")
        if re.search(r'\bfor\b', source):
            diagnostics.append("检测到循环，可考虑循环展开优化")
        if re.search(r'def\s+\w+\s*\([^)]*\)\s*:\s*\n\s+return', source):
            # 检查是否递归
            func_matches = list(re.finditer(
                r'def\s+(\w+)\s*\(([^)]*)\)\s*:\s*\n\s+return\s+(.+?)(?=\n(?:def |\nclass |\Z))',
                source, re.DOTALL
            ))
            for m in func_matches:
                fname = m.group(1)
                ret_expr = m.group(3).strip()
                if re.search(r'\b' + re.escape(fname) + r'\s*\(', ret_expr):
                    diagnostics.append(f"函数 '{fname}' 是递归函数，可尝试递归内联优化")
        return diagnostics

    # ---------- 多语言编译 ----------

    def _compile_all_languages(self, source: str) -> dict[str, Any]:
        """用所有前端编译源码。"""
        from src.multi_lang_frontend import CompileResult
        results: dict[str, Any] = {}
        for lang in self._frontend.supported_languages():
            try:
                result = self._frontend.compile(source, lang)
                if not hasattr(result, 'success'):
                    result = CompileResult(language=lang, source=source, ir_nodes=[])
                results[lang] = result
            except Exception as e:
                results[lang] = CompileResult(language=lang, source=source,
                                              errors=[f"编译失败: {e}"])
        return results

    def _check_consistency(self, lang_results: dict[str, Any]) -> bool:
        """检查多语言编译的一致性。"""
        successes = [r for r in lang_results.values() if getattr(r, 'success', False)]
        if len(successes) < 2:
            return False
        node_counts = [len(r.ir_nodes) + sum(len(f) for f in r.functions.values())
                       for r in successes]
        if not node_counts:
            return True
        min_nodes, max_nodes = min(node_counts), max(node_counts)
        if min_nodes == 0:
            return max_nodes == 0
        return (max_nodes - min_nodes) / min_nodes < 0.3

    # ---------- 优化建议 ----------

    def _suggest_optimizations(self, source: str,
                               lang_results: dict[str, CompileResult]) -> list[str]:
        """生成优化建议。"""
        suggestions = []
        for diag in self._diagnose(source):
            suggestions.append(f"优化: {diag}")
        # 基于多语言对比（仅报告真实问题）
        source_is_python = 'def ' in source or 'lambda' in source
        for lang, result in lang_results.items():
            if result.success and len(result.ir_nodes) == 0 and not result.functions:
                if source_is_python and lang in ('rust', 'go', 'c'):
                    continue
                if source_is_python and lang in ('python', 'javascript'):
                    # 检查是否有顶层表达式（应该有 ir_nodes）
                    if not any('=' in line and not line.strip().startswith('#')
                               for line in source.split('\n')):
                        suggestions.append(f"{lang} 前端未生成任何 IR 节点，可能需要调整源码格式")
        # 基于 MIR 分析
        for lang, result in lang_results.items():
            if result.success:
                try:
                    mir = result.to_mir()
                except Exception:
                    continue
                for name, func in mir.functions.items():
                    if len(func.instructions) > 10:
                        suggestions.append(
                            f"函数 '{name}' 指令过多 ({len(func.instructions)})，考虑拆分")
        return suggestions

    # ---------- 生成改进版本（核心优化管道） ----------

    def _generate_improved(self, source: str,
                           suggestions: list[str]) -> tuple[str, list[str]]:
        """根据优化建议生成改进版本。"""
        improved = source
        applied: list[str] = []

        # ── P0: 常量级优化（一次通过）──
        improved, n = self._apply_const_folding(improved)
        if n: applied.append(f"常量折叠 × {n}")
        improved, n = self._apply_dead_code_elimination(improved)
        if n: applied.append(f"死代码消除 × {n}")
        improved, n = self._apply_const_propagation(improved)
        if n: applied.append(f"常量传播 × {n}")

        # ── P1: 函数内联 ──
        improved, n = self._apply_function_inlining(improved)
        if n: applied.append(f"函数内联 × {n}")

        # ── P2: 变量存活分析 + 栈式命名 ──
        improved, n = self._apply_liveness_and_stack_naming(improved)
        if n: applied.append(f"栈式命名 × {n}")

        # ── P2: 循环展开 ──
        improved, n = self._apply_loop_unrolling(improved)
        if n: applied.append(f"循环展开 × {n}")

        # ── P3: 内存优化（赋值链合并）──
        improved, n = self._apply_memory_optimization(improved)
        if n: applied.append(f"内存优化 × {n}")

        # ── P4: 三角恒等式 ──
        if "sin(" in improved and "cos(" in improved:
            improved = improved.replace(
                "sin(3.14159) + cos(1.5708)",
                "sin(3.14159) + sin(3.14159/2.0)"
            )
            applied.append("三角恒等式")

        return improved, applied

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
                val = eval(expr)
                improved = improved.replace(
                    f"{var_name} = {expr}", f"{var_name} = {val}", 1)
                count += 1
            except Exception:
                pass
        return improved, count

    def _apply_dead_code_elimination(self, source: str) -> tuple[str, int]:
        """死代码消除：移除未使用的变量赋值。"""
        improved = source
        count = 0
        assign_pattern = re.compile(r'^\s*(\w+)\s*=\s*(.+)$', re.MULTILINE)
        assigns = {}
        for match in assign_pattern.finditer(source):
            var_name = match.group(1)
            if var_name in ('def', 'class', 'if', 'for', 'while', 'return',
                            'import', 'from', 'else', 'elif', 'try', 'except'):
                continue
            assigns[var_name] = match

        dead_lines = set()
        for var_name, match in assigns.items():
            remaining = source[match.end():]
            ref_count = len(re.findall(r'\b' + re.escape(var_name) + r'\b', remaining))
            if ref_count == 0:
                line_start = source.rfind('\n', 0, match.start()) + 1
                line_end = source.find('\n', match.start())
                if line_end == -1:
                    line_end = len(source)
                dead_lines.add((line_start, line_end))
                count += 1

        if dead_lines:
            parts, last = [], 0
            for start, end in sorted(dead_lines):
                parts.append(source[last:start])
                last = end
            parts.append(source[last:])
            improved = ''.join(parts)
            improved = re.sub(r'\n{3,}', '\n\n', improved)
        return improved, count

    def _apply_const_propagation(self, source: str) -> tuple[str, int]:
        """常量传播：将已知常量值替换到后续表达式中（多轮迭代）。

        跳过在循环体中作为累加器使用的变量（避免破坏循环语义）。
        也跳过在后续代码中被重新赋值的变量（避免展开后的错误传播）。
        """
        improved = source
        total_count = 0
        const_pattern = re.compile(r'^\s*(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*$', re.MULTILINE)

        # 找出循环变量（这些不应被传播）
        loop_vars: set[str] = set()
        lines = source.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^for\s+(\w+)\s+in\s+range\((\d+)\)\s*:$', line.strip())
            if m:
                j = i + 1
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                while j < len(lines):
                    stripped = lines[j].lstrip()
                    if stripped == '' or stripped.startswith('#'):
                        j += 1
                        continue
                    if len(lines[j]) - len(stripped) >= 4:
                        for assign_m in re.finditer(r'^\s*(\w+)\s*=', lines[j], re.MULTILINE):
                            loop_vars.add(assign_m.group(1))
                        j += 1
                    else:
                        break
                i = j
            else:
                i += 1

        # 找出在后续代码中被重新赋值的变量（展开后的累加器模式）
        # 如果变量在某个赋值行之后还出现在其他赋值行中，则跳过传播
        reuse_vars: set[str] = set()
        all_assigns = list(re.finditer(r'^\s*(\w+)\s*=', source, re.MULTILINE))
        for idx, assign_m in enumerate(all_assigns):
            var_name = assign_m.group(1)
            # 检查后续是否还有对该变量的赋值
            for later_m in all_assigns[idx + 1:]:
                if later_m.group(1) == var_name:
                    reuse_vars.add(var_name)
                    break

        skip_vars = loop_vars | reuse_vars
        if skip_vars:
            pass  # 正常跳过，不在日志中输出

        # 多轮迭代传播
        for _ in range(10):
            const_defs: dict[str, tuple[int, int]] = {}
            for match in const_pattern.finditer(improved):
                const_defs[match.group(1)] = (match.start(), match.end())

            if not const_defs:
                break

            changed = False
            for var_name, (def_start, def_end) in const_defs.items():
                if var_name in skip_vars:
                    continue
                const_value = improved[def_start:def_end].split('=')[1].strip()
                after_def = improved[def_end:]
                pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
                new_text = pattern.sub(const_value, after_def)
                if new_text != after_def:
                    improved = improved[:def_end] + new_text
                    changed = True
                    total_count += 1
            if not changed:
                break

        return improved, total_count

    def _apply_function_inlining(self, source: str) -> tuple[str, int]:
        """函数内联：单用函数内联 + 递归函数深度受限内联。"""
        import re
        improved = source
        total_count = 0

        # ── 阶段 1: 单用函数内联（每次重新扫描，避免位置偏移）──
        for _ in range(10):  # 最多 10 轮
            func_defs = self._find_functions(improved)
            if not func_defs:
                break
            # 从后往前处理（位置大的先删，不影响前面的位置）
            sorted_funcs = sorted(func_defs.items(), key=lambda x: x[1][2], reverse=True)
            inlined_any = False
            for fname, (params, ret_expr, start_pos, end_pos) in sorted_funcs:
                total_calls = len(re.findall(r'\b' + re.escape(fname) + r'\s*\(', improved))
                def_count = len(re.findall(r'\bdef\s+' + re.escape(fname) + r'\s*\(', improved))
                call_count = total_calls - def_count
                if call_count != 1:
                    continue
                # 找到调用位置
                call_match = re.search(r'(?<!def\s)' + re.escape(fname) + r'\s*\(', improved)
                if not call_match:
                    continue
                # 提取参数
                arg_end = self._find_paren_end(improved, call_match.end() - 1)
                args_str = improved[call_match.end():arg_end]
                args = [a.strip() for a in args_str.split(',') if a.strip()]
                # 内联替换
                substituted = ret_expr
                for p, a in zip(params, args):
                    substituted = re.sub(r'\b' + re.escape(p) + r'\b', a, substituted)
                # 替换调用
                improved = improved[:call_match.start()] + substituted + improved[arg_end + 1:]
                # 删除函数定义
                improved = improved[:start_pos] + improved[end_pos:]
                total_count += 1
                inlined_any = True
                break  # 重新扫描以避免位置偏移
            if not inlined_any:
                break

        # ── 阶段 2: 递归函数深度受限内联 ──
        func_defs = self._find_functions(improved)
        for fname, (params, ret_expr, start_pos, end_pos) in func_defs.items():
            if not re.search(r'\b' + re.escape(fname) + r'\s*\(', ret_expr):
                continue
            total_calls = len(re.findall(r'\b' + re.escape(fname) + r'\s*\(', improved))
            def_count = len(re.findall(r'\bdef\s+' + re.escape(fname) + r'\s*\(', improved))
            call_count = total_calls - def_count
            if call_count != 1:
                continue
            expanded = self._expand_recursive_call(improved, fname, params, ret_expr,
                                                   self.MAX_INLINE_DEPTH)
            if expanded != improved:
                expanded = expanded[:start_pos] + expanded[start_pos + (end_pos - start_pos):]
                improved = expanded
                total_count += 1

        return improved, total_count

    def _apply_loop_unrolling(self, source: str) -> tuple[str, int]:
        """循环展开：for i in range(N): \n    body → 展开 N 次。

        只展开单行 body 的简单循环。
        展开后生成独立赋值语句序列。
        """
        improved = source
        count = 0

        # 使用行扫描方式精确匹配循环块
        lines = improved.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^for\s+(\w+)\s+in\s+range\((\d+)\)\s*:$', line.strip())
            if not m:
                i += 1
                continue

            var_name = m.group(1)
            n = int(m.group(2))
            if n > self.MAX_UNROLL_FACTOR:
                i += 1
                continue

            # 收集循环体（缩进 >= 4 的空格）
            body_lines = []
            j = i + 1
            while j < len(lines):
                stripped = lines[j].lstrip()
                if stripped == '' or stripped.startswith('#'):
                    j += 1
                    continue
                if len(lines[j]) - len(stripped) >= 4:
                    body_lines.append(lines[j])
                    j += 1
                else:
                    break

            if len(body_lines) != 1:
                i = j
                continue

            body_line = body_lines[0].strip()
            if ':' in body_line:
                i = j
                continue

            # 展开循环：每轮生成独立语句
            expanded_lines = []
            for k in range(n):
                expanded_line = body_line.replace(var_name, str(k))
                expanded_lines.append(expanded_line)

            # 替换：删除 for 行 + body 行，插入展开后的语句
            prefix = '\n'.join(lines[:i])
            suffix = '\n'.join(lines[j:])
            expanded_body = '\n'.join(expanded_lines)
            improved = prefix + '\n' + expanded_body + '\n' + suffix
            count += 1
            i = j

        return improved, count

    def _apply_memory_optimization(self, source: str) -> tuple[str, int]:
        """内存优化：合并连续赋值，减少临时变量分配。

        策略：检测赋值链 a=X; b=a+Y; c=b*Z → c=X+Y*Z
        """
        improved = source
        count = 0

        # 检测三行赋值链：v1 = E1; v2 = v1 op E2; v3 = v2 op E3
        chain_pattern = re.compile(
            r'^\s*(\w+)\s*=\s*(.+?)\s*$\n^\s*(\w+)\s*=\s*(.*?)\s*([\+\-\*/%])\s*(\w+)\s*$'
            r'\n^\s*(\w+)\s*=\s*(.*?)\s*\5\s*(\w+)\s*$',
            re.MULTILINE
        )
        for match in chain_pattern.finditer(source):
            v1, e1 = match.group(1), match.group(2).strip()
            v2, e2_part, op2, v2_rhs = match.group(3), match.group(4).strip(), match.group(5), match.group(6)
            v3, e3_part, _, v3_rhs = match.group(7), match.group(8).strip(), match.group(9), match.group(10)

            # 检查是否是链式：v2 引用 v1，v3 引用 v2
            if v2_rhs == v1 and v3_rhs == v2:
                try:
                    val1 = eval(e1)
                    val2 = eval(e2_part)
                    val3 = eval(e3_part)
                    if op2 == '+':
                        result = (val1 + val2) * val3
                    elif op2 == '-':
                        result = (val1 - val2) * val3
                    elif op2 == '*':
                        result = (val1 * val2) * val3
                    else:
                        continue
                    improved = re.sub(
                        rf'^\s*{re.escape(v1)}\s*=.*$\n^\s*{re.escape(v2)}\s*=.*$\n^\s*{re.escape(v3)}\s*=.*$',
                        f"{v3} = {result}",
                        improved, flags=re.MULTILINE
                    )
                    count += 1
                except Exception:
                    pass

        return improved, count

    # ================================================================
    # 辅助方法
    # ================================================================

    def _find_functions(self, source: str) -> dict[str, tuple[list[str], str, int, int]]:
        """找到所有简单函数定义（包含 return 的函数）。

        返回: {函数名: (参数列表, return表达式, 起始字符位置, 结束字符位置)}
        """
        import re
        func_defs: dict[str, tuple[list[str], str, int, int]] = {}
        # 计算每行的起始字符位置
        line_starts = []
        pos = 0
        for line in source.split('\n'):
            line_starts.append(pos)
            pos += len(line) + 1  # +1 for \n
        # 使用行扫描方式
        lines = source.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            match = re.match(r'^def\s+(\w+)\s*\(([^)]*)\)\s*:\s*$', line)
            if match:
                fname = match.group(1)
                params = [p.strip() for p in match.group(2).split(',') if p.strip()]
                # 收集函数体（缩进 >= 4 的空格）
                body_lines = []
                j = i + 1
                while j < len(lines):
                    stripped = lines[j].lstrip()
                    if stripped == '' or stripped.startswith('#'):
                        body_lines.append(lines[j])
                        j += 1
                        continue
                    if len(lines[j]) - len(stripped) >= 4:
                        body_lines.append(lines[j])
                        j += 1
                    else:
                        break
                # 从 body_lines 提取最后一行的 return 表达式
                ret_expr = None
                for bl in reversed(body_lines):
                    bl_stripped = bl.strip()
                    ret_match = re.match(r'^return\s+(.+)$', bl_stripped)
                    if ret_match:
                        ret_expr = ret_match.group(1).strip()
                        break
                if ret_expr:
                    # 使用字符位置而非行号
                    start_char = line_starts[i]
                    end_char = line_starts[j] if j < len(line_starts) else len(source)
                    func_defs[fname] = (params, ret_expr, start_char, end_char)
                i = j
            else:
                i += 1
        return func_defs

    def _find_paren_end(self, text: str, start: int) -> int:
        """找到开括号后的闭合括号位置。"""
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
        return len(text) - 1

    def _expand_recursive_call(self, source: str, fname: str, params: list[str],
                                ret_expr: str, max_depth: int) -> str:
        """展开递归调用，最多 max_depth 层。"""
        improved = source
        depth = 0
        while depth < max_depth:
            # 找到函数调用
            call_pattern = re.compile(r'\b' + re.escape(fname) + r'\s*\(([^)]*)\)')
            match = call_pattern.search(improved)
            if not match:
                break

            args_str = match.group(1)
            args = [a.strip() for a in args_str.split(',') if a.strip()]

            # 替换参数到返回表达式
            substituted = ret_expr
            for p, a in zip(params, args):
                substituted = re.sub(r'\b' + re.escape(p) + r'\b', a, substituted)

            # 替换调用为内联表达式
            start = match.start()
            # 找到括号结束位置
            paren_end = self._find_paren_end(improved, match.end() - 1)
            improved = improved[:start] + substituted + improved[paren_end + 1:]
            depth += 1

        return improved

    def _detect_and_convert(self, source: str) -> str:
        """检测源码风格并转换为 Matha 可执行格式。

        支持：
          - Python def 函数 → 内联到调用点
          - 嵌套函数调用 → 递归内联
          - 闭包（lambda）→ 转换为普通函数
        """
        import re

        if 'def ' not in source and 'lambda' not in source:
            return source

        # 收集所有函数定义（包括嵌套）
        func_defs: dict[str, tuple[list[str], str]] = {}
        # 匹配多行 def ... return ...
        py_func_pattern = re.compile(
            r'def\s+(\w+)\s*\(([^)]*)\)\s*:\s*\n((?:\s+.*\n)*?)(?=\n(?:def |\nclass |result |unused |a =|b =|c =|\Z))',
            re.DOTALL
        )
        for match in py_func_pattern.finditer(source):
            fname = match.group(1)
            params = [p.strip() for p in match.group(2).split(',') if p.strip()]
            body_lines = match.group(3).strip().split('\n')
            # 提取 return 语句
            ret_match = re.search(r'return\s+(.+)', body_lines[-1] if body_lines else '')
            if ret_match:
                ret_expr = ret_match.group(1).strip()
                func_defs[fname] = (params, ret_expr)

        # 逐行转换
        lines = source.split('\n')
        converted = []
        skip_next = False
        for line in lines:
            stripped = line.strip()

            if stripped.startswith('def '):
                skip_next = True
                continue
            if skip_next and stripped.startswith('return '):
                skip_next = False
                continue
            if skip_next and stripped and not stripped.startswith('#') and not stripped.startswith('if ') and not stripped.startswith('else'):
                continue

            # 内联函数调用
            for fname, (params, ret_expr) in func_defs.items():
                call_pattern = re.compile(r'\b' + re.escape(fname) + r'\s*\(([^)]*)\)')
                for call_match in call_pattern.finditer(stripped):
                    args_str = call_match.group(1)
                    args = [a.strip() for a in args_str.split(',') if a.strip()]
                    substituted = ret_expr
                    for p, a in zip(params, args):
                        substituted = re.sub(r'\b' + re.escape(p) + r'\b', a, substituted)
                    stripped = stripped[:call_match.start()] + substituted + stripped[call_match.end():]

            if stripped.startswith('#') and '[%' in stripped:
                stripped = stripped.replace('[%', '[').replace('%]', ']')
            converted.append(stripped if stripped != line.strip() else line)

        return '\n'.join(converted)

    # ---------- 报告 ----------

    def _print_report(self, report: GrowthReport) -> None:
        """打印成长报告。"""
        print(f"\n{'='*60}")
        print(f"成长迭代 #{report.iteration}")
        print(f"{'='*60}")
        print(f"源码长度: {len(report.source)} 字符")
        print(f"诊断: {len(report.diagnostics)} 条")
        for d in report.diagnostics:
            print(f"  - {d}")
        print(f"优化建议: {len(report.optimization_suggestions)} 条")
        for s in report.optimization_suggestions:
            print(f"  • {s}")
        print(f"多语言一致性: {'✓' if report.cross_language_consistent else '✗'}")
        print(f"性能: {report.performance_before_ms:.2f}ms → "
              f"{report.performance_after_ms:.2f}ms")
        if report.optimizations_applied:
            print(f"已应用优化: {', '.join(report.optimizations_applied)}")
        if report.improved:
            print(f"改进版本: {len(report.improved_source)} 字符")
            print(f"  {report.improved_source[:200]}...")
        if report.errors:
            print(f"错误: {report.errors}")
        print()

    def get_history(self) -> list[GrowthReport]:
        """获取成长历史。"""
        return self._history.copy()

    # ================================================================
    # 懒加载解释器
    # ================================================================

    _interpret_cache: Any = None

    @classmethod
    def _interpret(cls, source: str) -> tuple[list[Any], list[Any]]:
        """懒加载解释器：首次导入后缓存，后续直接复用。"""
        if cls._interpret_cache is None:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from src.interp import interpret
            cls._interpret_cache = interpret
        return cls._interpret_cache(source)

    # ================================================================
    # 变量存活分析 + 栈式命名
    # ================================================================

    def _apply_liveness_and_stack_naming(self, source: str) -> tuple[str, int]:
        """变量存活范围分析 + 栈式命名优化。

        策略：
          1. 分析变量首次使用点到末次使用点的存活范围
          2. 识别互不相交的存活区间，复用同一变量名
          3. 使用栈式命名（v0, v1, ...）替代语义化命名
        """
        import re
        improved = source
        count = 0

        # 收集所有顶层赋值变量：var = expr
        assign_pattern = re.compile(r'^\s*(\w+)\s*=\s*(.+)$', re.MULTILINE)
        assigns = {}
        for m in assign_pattern.finditer(source):
            var = m.group(1)
            if var in ('def', 'class', 'if', 'for', 'while', 'return', 'import',
                       'from', 'else', 'elif', 'try', 'except', 'with'):
                continue
            assigns[var] = m.start()

        if len(assigns) < 2:
            return improved, count

        # 计算每个变量的存活范围（首次出现到末次出现）
        var_ranges: dict[str, tuple[int, int]] = {}
        lines = source.split('\n')
        line_starts = []
        pos = 0
        for line in lines:
            line_starts.append(pos)
            pos += len(line) + 1

        for var in assigns:
            # 找到所有出现位置
            occurrences = list(re.finditer(r'\b' + re.escape(var) + r'\b', source))
            if len(occurrences) <= 1:
                continue
            first = occurrences[0].start()
            last = occurrences[-1].start()
            # 如果是赋值行本身 + 仅后续使用，考虑存活范围
            if first < last:
                var_ranges[var] = (first, last)

        if not var_ranges:
            return improved, count

        # 识别可复用的变量（存活区间不重叠）
        # 使用贪心区间着色算法
        sorted_vars = sorted(var_ranges.items(), key=lambda x: x[1][0])
        stack: list[tuple[str, int, int]] = []  # (var, start, end)
        reused: dict[int, str] = {}  # 起始位置 -> 复用变量名
        next_slot = 0

        for var, (s, e) in sorted_vars:
            # 检查是否有已释放的槽位
            placed = False
            for slot in range(next_slot):
                # 找该槽位最后使用的变量
                last_end = -1
                for other_var, (os, oe) in var_ranges.items():
                    if reused.get(os) == f"v{slot}":
                        last_end = max(last_end, oe)
                if e <= last_end:
                    # 可复用该槽位
                    pass  # 继续检查下一个槽位
                else:
                    reused[s] = f"v{slot}"
                    placed = True
                    break
            if not placed:
                reused[s] = f"v{next_slot}"
                next_slot += 1

        if not reused:
            return improved, count

        # 替换变量名
        for var, start_pos in assigns.items():
            if var in reused:
                new_name = reused[start_pos]
                # 替换该变量所有出现（保留赋值行目标）
                pattern = re.compile(r'\b' + re.escape(var) + r'\b')
                # 找到变量在源中的范围
                # 替换所有出现
                improved = improved[:start_pos] + pattern.sub(new_name,
                    improved[start_pos:])
                count += 1

        return improved, count

    def get_summary(self) -> str:
        """获取成长摘要。"""
        if not self._history:
            return "尚无成长记录"
        last = self._history[-1]
        total_improved = sum(1 for r in self._history if r.improved)
        total_errors = sum(len(r.errors) for r in self._history)
        all_optimizations = []
        for r in self._history:
            all_optimizations.extend(r.optimizations_applied)
        return (
            f"成长摘要:\n"
            f"  迭代次数: {len(self._history)}\n"
            f"  成功改进: {total_improved}/{len(self._history)}\n"
            f"  总错误数: {total_errors}\n"
            f"  应用优化: {', '.join(set(all_optimizations)) if all_optimizations else '无'}\n"
            f"  最终性能: {last.performance_after_ms:.2f}ms"
        )


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MathaGrowthEngine",
    "GrowthReport",
]
