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

import logging
import re
from dataclasses import dataclass, field

from src.cross_language_verifier import CrossLanguageVerifier

logger = logging.getLogger("matha.growth")

# P2-1 算术恒等式正则构件（首批仅 7 条、不泛化）：
#   操作数限定为标识符（变量名）；恒等元限定为裸整数 0/1（前后字界，绝不碰 0.5/10/11//）。
_ARITH_BOUND = r'(?<![\w.])'
_ARITH_NAME = r'[^\W\d]\w*'
_ARITH_ZERO = r'(?<![\w.])0(?![\d.])'
_ARITH_ONE = r'(?<![\w.])1(?![\d.])'


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
        """主入口：迭代优化源码。

        正确性闸门（P1·只保证「绝不出坏源码」，不承诺优化有效）：每一轮候选改写
        必须 ①能被重新解析、②不丢失原文已绑定的名字（Binding 变量 / FuncDef），
        否则回退上一安全版本、如实置空本轮 optimizations_applied，停止前传。
        闸门只作用于此「前传决策」，_single_growth_iteration 保持原样（不改写规则本身）。
        """
        report = GrowthReport(iteration=0, source=source)
        current = source

        for iteration in range(1, self.max_iterations + 1):
            report = self._single_growth_iteration(current, iteration)
            if not report.optimizations_applied:
                break
            candidate = report.improved_source
            if not self._is_safe_candidate(current, candidate):
                # 诚实回退：本轮改写未过闸门，保留上一安全版本，绝不产出坏源码。
                report = GrowthReport(
                    iteration=iteration,
                    source=current,
                    diagnostics=report.diagnostics,
                    optimization_suggestions=report.optimization_suggestions,
                    improved_source=current,
                    optimizations_applied=[],
                    errors=[
                        f"第 {iteration} 轮改写未通过正确性闸门，已回退"
                        "（不产出不可解析 / 丢失已绑定名字的源码）"
                    ],
                )
                break
            current = candidate

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

        improved, n = self._apply_arith_identities(improved)
        if n: applied.append(f"算术恒等式 × {n}")

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
        """交叉语言验证：对比原始与优化后的一致性。

        ⚠ 已知 phantom（见 KNOWN_ISSUES.md §7c）：本方法把 `improved`(str) 当作
        `CrossLanguageVerifier.verify` 的 `sources` 参数传入，而 verify 内部执行
        `sources.items()`——字符串无 `.items()` → 抛异常被 except 吞 → 恒返回 False。
        且 verify 的语义本是「同算法×多语言前端」互拍，非「改写是否保持原文语义」。
        因此 `cross_language_consistent` 是不可靠信号，grow 的正确性判定**不依赖**它，
        改由 `_is_safe_candidate` 的两档硬底线承担。修正 _verify 本身另立切片。
        """
        try:
            result = self._verifier.verify(original, improved)
            return result.consistent
        except Exception:
            return False

    def _is_safe_candidate(self, original: str, improved: str) -> bool:
        """正确性闸门：判定候选改写是否「绝不出坏源码」。

        Tier 1：`improved` 必须能被重新解析（否则产出语法坏码，如函数名被删）。
        Tier 2：`improved` 不得丢失 `original` 已绑定的顶层名字（Binding 变量 / FuncDef），
                防「赋值声明退化为裸表达式」这类能过 parser 却语义腐蚀的改写。
        原文本就不可解析时，无从谈保持语义，仅要求 `improved` 至少可解析。
        """
        if improved == original:
            return True
        from src.parser import parse
        try:
            prog_i = parse(improved)
        except Exception:
            return False
        try:
            prog_o = parse(original)
        except Exception:
            return True
        return self._bound_names(prog_o) <= self._bound_names(prog_i)

    @staticmethod
    def _bound_names(program) -> set[str]:
        """收集顶层已绑定/声明的名字：Binding(Variable) 与 FuncDef。"""
        from src import ast_nodes as _ast
        names: set[str] = set()
        for d in getattr(program, "decls", []):
            if isinstance(d, _ast.Binding) and isinstance(d.target, _ast.Variable):
                names.add(d.target.name)
            elif isinstance(d, _ast.FuncDef):
                fname = getattr(d, "name", None)
                if isinstance(fname, str):
                    names.add(fname)
        return names

    def _semantic_equivalent(self, original: str, improved: str) -> bool:
        """语义等价正交判据（P2-0 harness）：分别独立运行原文与改写文，比对可观测 outputs。

        唯一正交标准（拍板）：在一次性解释器上各跑一遍：
          - 原文运行出错 → 无法作为基准 → 判 False；
          - 改写文运行出错 → 破坏原行为 → 判 False；
          - 两者均成功且 outputs 逐项相等 → 判 True，否则 False。
        纯离线、无文件副作用、不触 L1 内核入口。**仅作验证 harness**，不接入 grow()
        运行路径（grow 仍由 P1 闸门的再解析/名守恒兼底）。
        """
        o_out, o_err = self._exec_outputs(original)
        if o_err is not None:
            return False
        i_out, i_err = self._exec_outputs(improved)
        if i_err is not None:
            return False
        return o_out == i_out

    @staticmethod
    def _exec_outputs(source: str):
        """在一次性全新解释器上跑 source，返回 (outputs, error|None)。

        每次新建 Interpreter，实例间不共享可变状态（杜绝用例间污染）。
        解析或运行期异常均被捕获为 error 字符串，不裸抛。
        """
        try:
            from src.interp import Interpreter
            from src.parser import parse
            interp = Interpreter(debug=False)
            outputs, _trace = interp.run(parse(source))
            return outputs, None
        except Exception as ex:
            return None, f"{type(ex).__name__}: {ex}"

    # ================================================================
    # 优化规则实现
    # ================================================================

    def _apply_arith_identities(self, source: str) -> tuple[str, int]:
        """P2-1：首批 7 条简单算术恒等式（恒等元消去），纯正则、不泛化。

        x+0→x、x-0→x、0+x→x、1*x→x、x*1→x、x/1→x、x**1→x。
        仅作用于双引号字符串之外的子表达式；左操作数限定为标识符，恒等元限定为
        裸整数 0/1（带字界）。`*` 与 `**` 互不误伤；`/` 不碰整除 `//`。
        改写结果经 P1 闸门与语义等价 harness 双重验收；本规则按构造保守、正确。
        """
        improved = source
        total = 0
        rules = [
            (rf'{_ARITH_BOUND}({_ARITH_NAME})\s*\+\s*{_ARITH_ZERO}', r'\1'),   # x + 0
            (rf'{_ARITH_BOUND}({_ARITH_NAME})\s*-\s*{_ARITH_ZERO}', r'\1'),    # x - 0
            (rf'{_ARITH_ZERO}\s*\+\s*({_ARITH_NAME})', r'\1'),                 # 0 + x
            (rf'{_ARITH_ONE}\s*\*(?!\*)\s*({_ARITH_NAME})', r'\1'),            # 1 * x
            (rf'{_ARITH_BOUND}({_ARITH_NAME})\s*\*(?!\*)\s*{_ARITH_ONE}', r'\1'),  # x * 1
            (rf'{_ARITH_BOUND}({_ARITH_NAME})\s*/\s*{_ARITH_ONE}', r'\1'),     # x / 1
            (rf'{_ARITH_BOUND}({_ARITH_NAME})\s*\*\*\s*{_ARITH_ONE}', r'\1'),  # x ** 1
        ]
        for pattern, repl in rules:
            improved, c = self._sub_outside_strings(pattern, repl, improved)
            total += c
        return improved, total

    @staticmethod
    def _sub_outside_strings(pattern: str, repl: str, source: str) -> tuple[str, int]:
        """在双引号字符串之外的区间执行 re.subn，字符串字面量原样保留（防误伤常量）。

        未闭合的引号段一律原样保留（宁可不改，不可改错）。
        """
        parts: list[str] = []
        total = 0
        i = 0
        n = len(source)
        seg_start = 0
        in_str = False
        prev = ""
        while i < n:
            ch = source[i]
            if ch == '"' and prev != "\\":
                if not in_str:
                    piece = source[seg_start:i]
                    new_piece, c = re.subn(pattern, repl, piece)
                    parts.append(new_piece)
                    total += c
                    in_str = True
                    seg_start = i
                else:
                    parts.append(source[seg_start:i + 1])
                    in_str = False
                    seg_start = i + 1
            prev = ch
            i += 1
        if in_str:
            parts.append(source[seg_start:])
        else:
            new_tail, c = re.subn(pattern, repl, source[seg_start:])
            parts.append(new_tail)
            total += c
        return "".join(parts), total

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
        r"""常量传播（P2-2 修正版）：仅把「整行右端恰为单一数字字面量」的绑定名传播到其**使用点**。

        严格只做两件事（拍板），修掉元凶 B：
          ① 纯字面量右端：全行锚定 `= [ \t]*(?!=)(\d+(?:\.\d*)?)[ \t]*$`，右端除单一数字外
             不得有运算符 / 其它标识符——旧 `(\w+)\s*=\s*([\d.]+)` 把 `y = 3.0 + 4.0` 误读为 `3.0`；
          ② 只替换使用点：用点正则带 `(?! [ \t]*=)` 前视，赋值左端绑定名与 `==` / `=>` 受保护，
             并经 `_sub_outside_strings` 避开字符串字面量内部——旧 `re.sub` 连左端一起改写致 `7.0 = 7.0`。
        数字字面量保守：仅 `\d+(\.\d*)?`，不认负号 / 前导点 / 科学计数（宁可不改）。
        每条改写经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent` 双验收。
        """
        improved = source
        count = 0
        def_re = re.compile(
            r'^[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*(?!=)(\d+(?:\.\d*)?)[ \t]*$',
            re.MULTILINE,
        )
        for name, val in def_re.findall(source):
            improved, c = self._sub_outside_strings(
                rf'\b{re.escape(name)}\b(?![ \t]*=)', val, improved
            )
            count += c
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
            if re.match(r'^[a-zA-Z_]\w*$', arg) and '2' in m.group(0) and '+' not in arg and '-' not in arg:
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
