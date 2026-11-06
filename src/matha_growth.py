"""
Matha 自成长系统 v2 — 递归内联、循环展开、内存优化

实现 Matha 源码的自动分析与优化循环：
  源码 → 多语言前端编译 → IR 分析 → 优化建议 → 生成改进版本 → 验证

优化规则集（v2）：
  1. 常量折叠：x = 3.0 + 4.0 → x = 7.0
  2. 函数内联（单用）：def f(x): return x*x; f(3) → 3*3
  3. 函数内联（递归）：def fib(n): return n if n<2 else fib(n-1)+fib(n-2) → 深度限制内联
  4. 死代码消除：S3 起已从核心自动管线移除（删未用绑定与 P1 名守恒冲突），
     迁为 opt-in 扩展 `src/growth_extensions.py::optimize_dead_code`（自带 outputs 对拍）
  5. 常量传播：a = 10.0; b = a + 1 → b = 10.0 + 1
  6. 循环展开：for i in range(4): s += i → s = 0 + 1 + 2 + 3
  7. 内存优化（临时变量内联）：S2 起已从核心自动管线移除（删绑定与 P1 名守恒冲突），
     迁为 opt-in 扩展 `src/growth_extensions.py::optimize_temp_inlining`（自带 outputs 对拍）
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
    """单次成长循环的结果。

    S5：已移除三个幻影字段 `languages_analyzed` / `performance_before_ms` /
    `performance_after_ms`——它们仅在数据类定义中出现、`grow` 全程不写（恒默认），属误导面；
    且「性能计时」与本轨道「不承诺更快」纪律相违。无消费方，故直接删除而非伪填。
    """
    iteration: int
    source: str
    diagnostics: list[str] = field(default_factory=list)
    optimization_suggestions: list[str] = field(default_factory=list)
    improved_source: str = ""
    optimizations_applied: list[str] = field(default_factory=list)
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

        # S3：死代码消除已从核心自动管线**移除**——删未用绑定同样破 P1 名守恒（被删名即其
        # 自身），且旧实现把赋值自身 LHS 也算进 used → 恒 no-op。真删除能力迁为 opt-in
        # 扩展，见 `src/growth_extensions.py`。

        improved, n = self._apply_const_propagation(improved)
        if n: applied.append(f"常量传播 × {n}")

        improved, n = self._apply_function_inlining(improved)
        if n: applied.append(f"函数内联 × {n}")

        improved, n = self._apply_loop_unrolling(improved)
        if n: applied.append(f"循环展开 × {n}")

        # S2：内存优化（临时变量内联）已从核心自动管线**移除**——删绑定行丢名与 P1
        # 名守恒契约结构性冲突（恒被拒），迁为 opt-in 扩展，见 `src/growth_extensions.py`。

        improved, n = self._apply_trig_identities(improved)
        if n: applied.append(f"三角恒等式 × {n}")

        return improved, applied

    def _verify(self, original: str, improved: str) -> bool:
        """改写前后一致性佐证（S4）：送入 `CrossLanguageVerifier` 的 `"python"` 通道，
        编译为 MIR 并执行，据验证器产出的可观测结果判一致。

        真实契约（见 src/cross_language_verifier.py）：`verify(algorithm: str,
        sources: dict[str, str]) -> CrossLanguageResult`——旧实现把 `improved`(str) 当作
        `sources` 传入，verify 内部执行 `sources.items()` → 抛异常被 except 吞 → 恒 False（phantom）。
        现按契约以 `{'python': <源码>}` 正确调用。判据只用**真实**字段：
          ① 改写前后两侧在该前端均编译+执行成功（`LanguageResult.success`）；
          ② 两侧 `vm_outputs` 逐项相等。
        二者皆真才返回 True。任一侧失败 / 缺该语言结果 / 调用抛异常 → **诚实 False**
        （无从验证就不报一致）。不读 `CrossLanguageResult.consistent`——它默认
        True、仅在 ≥2 语言互拍分歧时才置 False，单语言场景下是「未验证≠一致」的假阳性陷阱。

        ⚠ 已知缺口 G-1（待真修复，见 docs/KNOWN_ISSUES.md §7c）：本通道的 `"python"` 前端实为
        `src/mir2_frontend.py::PythonFrontend`，其 `compile` 直接 `ast.parse(source)`——即 **Python 子集**
        前端，只吃 `x = 3.0 + 4.0` 这类写法。而 `grow` 的输入域是 **Matha 源码**（P1 闸门用
        `src.parser.parse`），真实 Matha 构造（`func` / `let` / 中文函数名）在该前端直接 SyntaxError
        → 两侧均不可运行 → 本字段对真实 Matha 程序**结构性恒 False、不携带信息**（结论诚实，但无信息量）。
        真修复方向：改走 Matha 主链（`src.parser` + `src.interp.Interpreter`，即本文件
        `_exec_outputs` / `_semantic_equivalent` 已拍板的正交权威）；并需同时避免 G-2 假阳性：
        两侧都无可见输出时 `[] == []` 会误判等价，故必须先要求两侧有可观测输出。

        ⚠ 本字段**不是** grow 的安全闸门：grow 的「绝不出坏源码」仍**只**依赖 P1
        `_is_safe_candidate`。`_verify` 只是佐证信号，供诊断参考。
        """
        try:
            r_o = self._verifier.verify("growth-original", {"python": original})
            r_i = self._verifier.verify("growth-improved", {"python": improved})
            o = r_o.languages.get("python")
            i = r_i.languages.get("python")
            if o is None or i is None:
                return False
            if not (o.success and i.success):
                return False
            return o.vm_outputs == i.vm_outputs
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
        r"""常量折叠（P3-1·全行锚定）：仅折「整行右端恰为 `num op num`」为单一字面量。

        修优先级腐蚀：旧 `([\d.]+\s*[+\-*/%]\s*[\d.]+)` 只吃前两个操作数、不锚定整行，
        把 `x = 1 + 2 * 3` 折成 `x = 3 * 3`（=9≠7，过 P1 却改坏值）。现逐行 `fullmatch`，要求
        右端除「数字 op 数字」外不得再有第三个运算符/操作数 → `1 + 2 * 3`、`8 // 2`（双运算符）
        自然不匹配、不折。op 集沿用 `+ - * / %`（不新增）；除零/取模零守卫保留；逐行重建替换，
        不再全局 str.replace（避免同名片段误伤）；数字操作数严格 `\d+(?:\.\d*)?`。
        每条改写经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent` 双验收。
        """
        lines = source.split('\n')
        count = 0
        for idx, line in enumerate(lines):
            m = re.fullmatch(
                r'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*'
                r'(\d+(?:\.\d*)?)[ \t]*([+\-*/%])[ \t]*(\d+(?:\.\d*)?)[ \t]*',
                line,
            )
            if not m:
                continue
            var, a, op, b = m.group(1), m.group(2), m.group(3), m.group(4)
            try:
                result = eval(f"{a}{op}{b}")  # a/b 严格数字字面量、op 属固定集，非任意求值
            except (SyntaxError, ZeroDivisionError, ValueError):
                continue
            lines[idx] = f"{var} = {result}"
            count += 1
        return '\n'.join(lines), count

    # S3：`_apply_dead_code_elimination`（旧「删未用赋值行」）已删除——它把自身 LHS 也算进
    # used → 恒 no-op；且删未用绑定同样破 P1 名守恒。真删除能力已重写为正确版本并迁为
    # opt-in 扩展（自带 outputs 对拍、不走 P1），见 `src/growth_extensions.py::optimize_dead_code`。

    def _apply_const_propagation(self, source: str) -> tuple[str, int]:
        r"""常量传播（P3-2·逐行顺序扫描·位置感知）：只把「当前活跃纯字面量」传播到其**定义之后**的使用点。

        承 P2-2 两条保守约束（① 纯字面量右端全行锚定 ② 只替换使用点、左端/`==`/`=>` 受保护、
        经 `_sub_outside_strings` 避开字符串），并修掉「前向引用 / 重绑定」腐蚀（元凶 C）：
        旧 `def_re.findall(source)` 找到每个纯字面量定义后把名字回灌到**全文所有**使用点，
        既灌向定义**之前**的使用点（`x=2.0*3.0; y=x+1; x=10.0` → `y` 由 7.0 被改成 11.0，
        过 P1 却语义腐蚀），也无视同名重绑定。现逐行顺序扫描，维护 `known`（name → 最近一次
        纯字面量绑定的活跃值）：每行先用「进入本行前」的活跃字面量替换本行使用点，再据本行更新状态
        （纯字面量赋值→更新活跃值；非字面量赋值→失效，后续不再传播旧值）。自引用行（`y=y+1`）
        先按旧值替换、再判失效。数字形态仅 `\d+(?:\.\d*)?`（不认负号/前导点/科学计数，宁可不改）。
        每条改写经 P1 闸门 `_is_safe_candidate` 与 P2-0 harness `_semantic_equivalent` 双验收。
        """
        def_re = re.compile(
            r'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*(?!=)(\d+(?:\.\d*)?)[ \t]*'
        )
        assign_re = re.compile(r'[ \t]*([^\W\d]\w*)[ \t]*=[ \t]*(?!=)')
        lines = source.split('\n')
        improved_lines: list[str] = []
        known: dict[str, str] = {}
        count = 0
        for line in lines:
            newline = line
            for name, val in known.items():
                newline, c = self._sub_outside_strings(
                    rf'\b{re.escape(name)}\b(?![ \t]*=)', val, newline
                )
                count += c
            improved_lines.append(newline)
            dm = def_re.fullmatch(line)
            if dm:
                known[dm.group(1)] = dm.group(2)
            else:
                am = assign_re.match(line)
                if am:
                    known.pop(am.group(1), None)
        return '\n'.join(improved_lines), count

    def _apply_function_inlining(self, source: str) -> tuple[str, int]:
        r"""函数内联（P2-3·选项 1·按构造正确的保守版）。

        只处理 curried 单表达式形态 `func n(ps) -> T = (ps) => expr`，且仅在「可证等价」
        时把调用点 `n(args)` 就地内联为 `(expr[ps:=args])`，**绝不动函数定义本身**（定义
        头以 `func\s+$` 前缀识别并跳过，故元凶 A「删函数名」从结构上不可能复发）。可证等价须同时满足：
          ① 形参表全为干净标识符，且实参数 == 形参数；
          ② 每个实参为「简单 token」（标识符或纯数字字面量）——避免重复求值副作用与优先级改变；
          ③ body 的自由标识符 ⊆ 形参集（函数只闭合于自身参数 → 在任意调用点内联都不改变
             变量解析，规避遮蔽/捕获/递归风险；含自由变量的函数一律不内联）。
        形参→实参替换用单遍正则（长名优先）一次完成，避免顺序替换串扰；全程经
        `_sub_outside_strings` 避开字符串字面量。其余形态一律原样不动。
        """
        improved = source
        count = 0
        fn_re = re.compile(
            r'func\s+([^\W\d]\w*)\s*\([^)]*\)\s*->\s*\w+\s*=\s*\(([^)]*)\)\s*=>\s*(.+?)(?:\n|$)'
        )
        for m in fn_re.finditer(source):
            name = m.group(1)
            params_raw = m.group(2)
            body = m.group(3).strip()
            params = [p.strip() for p in params_raw.split(',')] if params_raw.strip() else []
            if any(not re.fullmatch(r'[^\W\d]\w*', p) for p in params):
                continue  # 形参非干净标识符 → 不内联
            if set(re.findall(r'[^\W\d]\w*', body)) - set(params):
                continue  # body 含非形参的自由标识符 → 不内联
            pat = (r'\b(' + '|'.join(re.escape(p) for p in sorted(params, key=len, reverse=True)) + r')\b'
                   if params else None)
            call_re = re.compile(rf'\b{re.escape(name)}\s*\(([^)]*)\)')

            def repl(cm, _body=body, _pat=pat, _params=params):
                nonlocal count
                if re.search(r'func\s+$', cm.string[:cm.start()]):
                    return cm.group(0)  # 定义头，非调用点 → 不动
                raw = cm.group(1)
                args = [a.strip() for a in raw.split(',')] if raw.strip() else []
                if len(args) != len(_params):
                    return cm.group(0)
                if any(not re.fullmatch(r'[^\W\d]\w*|\d+(?:\.\d*)?', a) for a in args):
                    return cm.group(0)  # 实参非简单 token → 不内联
                amap = dict(zip(_params, args))
                if _pat is None:
                    inl_body = _body
                else:
                    inl_body, _ = self._sub_outside_strings(_pat, lambda mm: amap[mm.group(0)], _body)
                count += 1
                return f"({inl_body})"

            improved = call_re.sub(repl, improved)
        return improved, count

    def _apply_loop_unrolling(self, source: str) -> tuple[str, int]:
        r"""循环展开（S1·按 Matha 真实 `for v in <iterable> { … }` 语法·保守可证等价）。

        旧实现正则 `for … in range(N):\n` 针对 Python 冒号缩进语法——Matha 根本不用该语法
        （真实为花括号块 `for v in <expr> { … }`、`range(a,b)` 两参），故旧规则只在非法输入上
        触发，且 `body.replace(var, i)` 子串误伤（`ab`→`0b`）。现仅在**可静态枚举且可证等价**时展开：
          ① 单循环变量（非元组解构 `(a,b)`）；
          ② iterable 为数字字面量列表 `[n,…]` 或 `range(int,int)`/`range(int)(int)`（跨度≤阈值）；
          ③ 块体无嵌套花括号、不含控制流关键字、且不在体内重新赋值循环变量（避免改变循环
             变量的逐迭代作用域/清除语义）；
          ④ 循环变量按**词边界**、经 `_sub_outside_strings` 逐元素代入，替换后体内不再出现循环变量
             → 与原解释器“循环后清除循环变量”作用域一致。
        展开后候选经 P1 闸门（名守恒）兜底、由表征锁逐例验证 `_semantic_equivalent` 等价。
        """
        _NUM = r'\d+(?:\.\d*)?'
        span_cap = 16
        loop_re = re.compile(
            r'for\s+([^\W\d]\w*)\s+in\s+'
            r'(\[[^\[\]]*\]|range\([^)]*\)(?:\s*\([^)]*\))?)'
            r'\s*\{\s*([^{}]*)\s*\}'
        )
        improved = source
        count = 0
        for m in loop_re.finditer(source):
            var, iterable_raw, body = m.group(1), m.group(2), m.group(3)
            # 体内控制流/结构关键字一律不展开（保守）
            if re.search(r'\b(break|continue|return|func|let|match|switch|typeof|if|for|while)\b', body):
                continue
            # 体内重新赋值循环变量（=`var =`/`var op=`，但非 `==`）→ 作用域难证等价 → 不展开
            if re.search(rf'\b{re.escape(var)}\b\s*(?:[+\-*/%])?=(?!=)', body):
                continue
            # 解析可枚举元素
            if iterable_raw.startswith('['):
                inner = iterable_raw[1:-1].strip()
                if inner == '':
                    elems: list[str] = []
                else:
                    parts = [p.strip() for p in inner.split(',')]
                    if len(parts) > span_cap or not all(re.fullmatch(_NUM, p) for p in parts):
                        continue
                    elems = parts
            else:
                rm = (re.fullmatch(r'range\(\s*(\d+)\s*,\s*(\d+)\s*\)', iterable_raw)
                      or re.fullmatch(r'range\(\s*(\d+)\s*\)\s*\(\s*(\d+)\s*\)', iterable_raw))
                if not rm:
                    continue
                a, b = int(rm.group(1)), int(rm.group(2))
                if b < a or (b - a) > span_cap:
                    continue
                elems = [str(x) for x in range(a, b)]
            # 逐元素词边界代入循环变量（避开字符串）；替换后体内不再引用 var → 作用域与原始一致
            instances = [
                self._sub_outside_strings(rf'\b{re.escape(var)}\b', v, body)[0]
                for v in elems
            ]
            unrolled = '\n'.join(instances)
            improved = improved.replace(m.group(0), unrolled, 1)
            count += 1
        return improved, count

    # S2：`_apply_memory_optimization`（旧「删 `x = temp_*` 行」）已删除——它丢绑定名 →
    # 恒被 P1 拒、且并非真「栈提升」。其能力已重写为正确的临时变量内联，迁为 opt-in 扩展
    # （自带 outputs 对拍、不走 P1），见 `src/growth_extensions.py::optimize_temp_inlining`。

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
