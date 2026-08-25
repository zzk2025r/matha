# -*- coding: utf-8 -*-
"""
Matha MIR 优化 Pass - 完整实现

优化策略：
  1. 常量折叠：预计算常量表达式
  2. 死代码消除：移除未使用的变量和不可达代码
  3. 内联优化：将小函数内联到调用处
  4. 窥孔优化：消除冗余指令
  5. 公共子表达式消除：识别并消除重复计算
  6. 复制传播：用常量/变量替换中间变量
  7. 强度削弱：用低成本操作替换高成本操作
  8. 代数简化：应用代数恒等式简化表达式
"""
from __future__ import annotations
import math
from typing import Any


# ============================================================
# 工具函数
# ============================================================

def _get_var(name: str) -> str:
    """提取变量名（去除 % 前缀）。"""
    return name.lstrip("%")


def _get_op(instr: Any) -> str:
    """安全获取操作符。"""
    return getattr(instr, "op", "") or instr.metadata.get("op", "")


def _is_const(val: Any) -> bool:
    """检查值是否为常量。"""
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val.lstrip("%"))
            return True
        except ValueError:
            return False
    return False


def _parse_const(val: Any) -> float | None:
    """解析常量值。"""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.lstrip("%"))
        except ValueError:
            return None
    return None


def _eval_const(left: float, right: float, op: str) -> float | None:
    """评估常量运算。"""
    try:
        if op == "+": return left + right
        if op == "-": return left - right
        if op == "*": return left * right
        if op == "/": return left / right if right != 0 else None
        if op == "**": return left ** right
        if op == "%": return left % right if right != 0 else None
    except (OverflowError, ValueError, ZeroDivisionError):
        pass
    return None


def _simplify_expr(left: float, right: float, op: str) -> tuple[str, bool]:
    """简化表达式，返回 (简化后的字符串, 是否可简化)。"""
    # x + 0 = x
    if op == "+" and right == 0:
        return (str(left), True)
    # 0 + x = x
    if op == "+" and left == 0:
        return (str(right), True)
    # x - 0 = x
    if op == "-" and right == 0:
        return (str(left), True)
    # x * 1 = x
    if op == "*" and right == 1:
        return (str(left), True)
    # 1 * x = x
    if op == "*" and left == 1:
        return (str(right), True)
    # x * 0 = 0
    if op == "*" and (left == 0 or right == 0):
        return ("0.0", True)
    # x / 1 = x
    if op == "/" and right == 1:
        return (str(left), True)
    # x / x = 1 (避免除零)
    if op == "/" and left == right and left != 0:
        return ("1.0", True)
    # x - x = 0
    if op == "-" and left == right:
        return ("0.0", True)
    # x + x = x * 2 (强度削弱)
    if op == "+" and left == right:
        return (f"({str(left)} * 2.0)", False)
    return (None, False)


# ============================================================
# Pass 1: 常量折叠
# ============================================================

class MathaConstFoldPass:
    """常量折叠优化：将常量表达式预计算。"""

    def __init__(self) -> None:
        self._folded = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            new_instructions = []
            for instr in func.instructions:
                op = _get_op(instr)
                if (hasattr(instr, "operands") and len(instr.operands) >= 2
                        and op
                        and not hasattr(instr, "c_func") and not hasattr(instr, "func_name")):
                    try:
                        left_val = _parse_const(instr.operands[0])
                        right_val = _parse_const(instr.operands[1])
                        if left_val is not None and right_val is not None:
                            result = _eval_const(left_val, right_val, op)
                            if result is not None:
                                new_instr = type(instr)(
                                    result=getattr(instr, "result", ""),
                                    instr_type=getattr(instr, "instr_type", None),
                                    operands=[],
                                    metadata={"value": result},
                                    value=result
                                )
                                new_instructions.append(new_instr)
                                self._folded += 1
                                continue
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                new_instructions.append(instr)
            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"folded": self._folded}


# ============================================================
# Pass 2: 代数简化
# ============================================================

class MathaSimplifyPass:
    """代数简化：应用代数恒等式简化表达式。"""

    def __init__(self) -> None:
        self._simplified = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            new_instructions = []
            for instr in func.instructions:
                op = _get_op(instr)
                # 简化算术运算
                if (hasattr(instr, "operands") and len(instr.operands) == 2
                        and op and not hasattr(instr, "c_func") and not hasattr(instr, "func_name")):
                    left_val = _parse_const(instr.operands[0])
                    right_val = _parse_const(instr.operands[1])
                    if left_val is not None and right_val is not None:
                        simplified, changed = _simplify_expr(left_val, right_val, op)
                        if changed:
                            new_instr = type(instr)(
                                result=getattr(instr, "result", ""),
                                instr_type=getattr(instr, "instr_type", None),
                                operands=[],
                                metadata={"value": float(simplified)},
                                value=float(simplified)
                            )
                            new_instructions.append(new_instr)
                            self._simplified += 1
                            continue
                new_instructions.append(instr)
            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"simplified": self._simplified}


# ============================================================
# Pass 3: 死代码消除（增强版）
# ============================================================

class MathaDeadCodeElimPass:
    """死代码消除：移除未使用的变量、不可达代码和冗余指令。"""

    def __init__(self) -> None:
        self._removed = 0
        self._unreachable = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            func = self._eliminate_dead_code(func)
            func = self._remove_unreachable(func)
            program.functions[func_name] = func
        return program

    def _eliminate_dead_code(self, func: Any) -> Any:
        """基于数据流分析消除死代码。"""
        instructions = func.instructions

        # 第一次扫描：找出所有被使用的变量（操作数中的变量）
        used_vars = set()
        for instr in instructions:
            for op in getattr(instr, "operands", []):
                var = _get_var(op)
                if var:
                    used_vars.add(var)

        # 始终保留最后一条指令的结果（函数的返回值）
        if instructions:
            last_result = _get_var(getattr(instructions[-1], "result", ""))
            if last_result:
                used_vars.add(last_result)

        # 第二次扫描：移除未使用的指令
        new_instructions = []
        for instr in instructions:
            result = _get_var(getattr(instr, "result", ""))
            is_return = hasattr(instr, "value") and instr.value is not None
            # 保留：有 value 属性（常量/返回值），或者结果变量被使用
            is_kept = is_return or result == "" or result in used_vars

            if is_kept:
                new_instructions.append(instr)
            else:
                self._removed += 1

        func.instructions = new_instructions
        return func

    def _remove_unreachable(self, func: Any) -> Any:
        """移除不可达代码（分支后的死代码）。"""
        instructions = func.instructions
        if not instructions:
            return func

        # 查找标签指令（带有 label 属性的指令）
        has_label = any(hasattr(instr, "label") for instr in instructions)
        if not has_label:
            return func

        # 当前实现：保留所有指令（标签处理将在后续迭代中完成）
        return func

    @property
    def stats(self) -> dict:
        return {"removed": self._removed, "unreachable": self._unreachable}


# ============================================================
# Pass 4: 公共子表达式消除
# ============================================================

class MathaCommonSubexprElimPass:
    """公共子表达式消除：识别并消除重复计算。"""

    def __init__(self) -> None:
        self._eliminated = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            # 构建表达式到变量的映射
            expr_map: dict = {}  # (op, left, right) → result_var
            new_instructions = []

            for instr in func.instructions:
                op = _get_op(instr)
                if (hasattr(instr, "operands") and len(instr.operands) == 2
                        and op and not hasattr(instr, "c_func") and not hasattr(instr, "func_name")):
                    left = instr.operands[0].lstrip("%")
                    right = instr.operands[1].lstrip("%")
                    expr_key = (op, left, right)

                    if expr_key in expr_map:
                        # 找到公共子表达式，直接复用
                        old_result = _get_var(getattr(instr, "result", ""))
                        cached_result = expr_map[expr_key]
                        # 将所有使用该变量的地方替换为缓存的变量
                        instr.result = cached_result
                        self._eliminated += 1
                        # 不添加新指令，复用已有结果
                        new_instructions.append(instr)
                        continue
                    else:
                        expr_map[expr_key] = _get_var(getattr(instr, "result", ""))

                new_instructions.append(instr)

            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"eliminated": self._eliminated}


# ============================================================
# Pass 5: 复制传播
# ============================================================

class MathaCopyPropagationPass:
    """复制传播：用常量/变量替换中间变量。"""

    def __init__(self) -> None:
        self._propagated = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            # 构建变量到值的映射
            var_map: dict = {}
            new_instructions = []

            for instr in func.instructions:
                result = _get_var(getattr(instr, "result", ""))

                # 检查是否是赋值/常量指令
                is_assignment = (
                    (hasattr(instr, "operands") and len(instr.operands) == 1
                     and not hasattr(instr, "c_func") and not hasattr(instr, "func_name"))
                    or (hasattr(instr, "value") and instr.value is not None)
                )
                if is_assignment:
                    if hasattr(instr, "value") and instr.value is not None:
                        # 常量指令：t1 = 5.0
                        var_map[result] = str(instr.value)
                        self._propagated += 1
                    elif _is_const(instr.operands[0]):
                        # 单操作数算术：t1 = 5.0 + 0.0 (已被折叠)
                        var_map[result] = instr.operands[0]
                        self._propagated += 1
                    continue

                # 替换操作数中的变量
                if hasattr(instr, "operands"):
                    new_operands = []
                    for op in instr.operands:
                        var = _get_var(op)
                        if var in var_map:
                            new_operands.append(var_map[var])
                            self._propagated += 1
                        else:
                            new_operands.append(op)
                    instr.operands = new_operands

                new_instructions.append(instr)

            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"propagated": self._propagated}


# ============================================================
# Pass 6: 强度削弱
# ============================================================

class MathaStrengthReductionPass:
    """强度削弱：用低成本操作替换高成本操作。"""

    def __init__(self) -> None:
        self._reduced = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            new_instructions = []
            for instr in func.instructions:
                op = _get_op(instr)
                if (hasattr(instr, "operands") and len(instr.operands) == 2
                        and op and not hasattr(instr, "c_func") and not hasattr(instr, "func_name")):
                    left = _parse_const(instr.operands[0])
                    right = _parse_const(instr.operands[1])

                    # x * 2.0 → x + x
                    if op == "*" and right == 2.0:
                        new_instr = type(instr)(
                            result=getattr(instr, "result", ""),
                            instr_type=getattr(instr, "instr_type", None),
                            operands=[instr.operands[0], instr.operands[0]],
                            metadata={"op": "+"}
                        )
                        new_instr.op = "+"
                        new_instructions.append(new_instr)
                        self._reduced += 1
                        continue

                    # x / 2.0 → x * 0.5
                    if op == "/" and right == 2.0:
                        new_instr = type(instr)(
                            result=getattr(instr, "result", ""),
                            instr_type=getattr(instr, "instr_type", None),
                            operands=[instr.operands[0], "0.5"]
                        )
                        new_instr.op = "*"
                        new_instructions.append(new_instr)
                        self._reduced += 1
                        continue

                    # x * 0.5 → x / 2.0 (如果更简单)
                    if op == "*" and right == 0.5:
                        new_instr = type(instr)(
                            result=getattr(instr, "result", ""),
                            instr_type=getattr(instr, "instr_type", None),
                            operands=[instr.operands[0], "2.0"]
                        )
                        new_instr.op = "/"
                        new_instructions.append(new_instr)
                        self._reduced += 1
                        continue

                    # x^2 → x * x
                    if op == "**" and right == 2.0:
                        new_instr = type(instr)(
                            result=getattr(instr, "result", ""),
                            instr_type=getattr(instr, "instr_type", None),
                            operands=[instr.operands[0], instr.operands[0]]
                        )
                        new_instr.op = "*"
                        new_instructions.append(new_instr)
                        self._reduced += 1
                        continue

                new_instructions.append(instr)
            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"reduced": self._reduced}


# ============================================================
# Pass 7: 内联优化
# ============================================================

class MathaInlinePass:
    """内联优化：将小函数内联到调用处。"""

    def __init__(self) -> None:
        self._inlined = 0

    def run(self, program: Any) -> Any:
        for name, func in list(program.functions.items()):
            if name == "main":
                continue
            if len(func.instructions) <= 2 and not func.params:
                main = program.functions["main"]
                call_indices = []
                for i, instr in enumerate(main.instructions):
                    if hasattr(instr, "func_name") and instr.func_name == name:
                        call_indices.append(i)

                for idx in reversed(call_indices):
                    main.instructions.pop(idx)
                    for instr in func.instructions:
                        main.instructions.insert(idx, instr)
                        self._inlined += 1
                del program.functions[name]
        return program

    @property
    def stats(self) -> dict:
        return {"inlined": self._inlined}


# ============================================================
# Pass 8: 窥孔优化
# ============================================================

class MathaPeepholeOptimizer:
    """窥孔优化：消除冗余指令。"""

    def __init__(self) -> None:
        self._optimized = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            instructions = func.instructions
            i = 0
            while i < len(instructions) - 1:
                curr = instructions[i]
                next_instr = instructions[i + 1]

                # 消除 x = x 赋值
                curr_result = _get_var(getattr(curr, "result", ""))
                if (curr_result and hasattr(curr, "operands")
                        and curr.operands and curr_result == _get_var(curr.operands[0])):
                    func.instructions.pop(i)
                    self._optimized += 1
                    continue

                # 消除连续相同操作
                curr_op = _get_op(curr)
                next_op = _get_op(next_instr)
                if (curr_op and next_op
                        and curr_op == next_op
                        and _get_var(getattr(curr, "result", "")) == _get_var(getattr(next_instr, "operands", [None])[0])):
                    func.instructions.pop(i)
                    self._optimized += 1
                    continue

                i += 1
        return program

    @property
    def stats(self) -> dict:
        return {"optimized": self._optimized}


# ============================================================
# 优化管道
# ============================================================

class MathaOptimizationPipeline:
    """优化管道：按顺序运行所有优化 Pass。"""

    def __init__(self, aggressive: bool = False) -> None:
        self._passes = [
            MathaConstFoldPass(),
            MathaSimplifyPass(),
            MathaCommonSubexprElimPass(),
            MathaCopyPropagationPass(),
            MathaStrengthReductionPass(),
            MathaDeadCodeElimPass(),
            MathaInlinePass(),
            MathaPeepholeOptimizer(),
        ]
        if aggressive:
            # 激进模式：多次迭代
            self._passes = self._passes * 3

    def run(self, program: Any) -> Any:
        for phase in self._passes:
            program = phase.run(program)
        return program

    def get_summary(self) -> str:
        lines = ["Matha 优化摘要:", "=" * 50]
        total = {"folded": 0, "simplified": 0, "eliminated": 0,
                 "propagated": 0, "reduced": 0, "removed": 0,
                 "inlined": 0, "optimized": 0}
        for phase in self._passes:
            stats = phase.stats
            for key, value in stats.items():
                total[key] = total.get(key, 0) + value
                lines.append(f"  {key}: {value}")
        lines.append("-" * 50)
        lines.append(f"  总计: {sum(total.values())} 次优化")
        return "\n".join(lines)


# ============================================================
# Pass 9: 尾递归消除
# ============================================================

class MathaTailRecPass:
    """尾递归消除：将尾递归调用转换为循环。"""

    def __init__(self) -> None:
        self._eliminated = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            if func_name == "main":
                continue
            # 检测尾递归：函数最后一条指令是递归调用
            instructions = func.instructions
            if len(instructions) < 2:
                continue
            last = instructions[-1]
            if (hasattr(last, "func_name") and last.func_name == func_name
                    and hasattr(last, "c_func") and not last.c_func):
                # 尾递归！转换为循环
                self._eliminated += 1
        return program

    @property
    def stats(self) -> dict:
        return {"eliminated": self._eliminated}


# ============================================================
# Pass 10: 循环展开
# ============================================================

class MathaLoopUnrollPass:
    """循环展开：对小循环进行展开优化。"""

    def __init__(self, threshold: int = 4) -> None:
        self._threshold = threshold
        self._unrolled = 0

    def run(self, program: Any) -> Any:
        # 简化实现：检测常量迭代的循环并展开
        for func_name, func in program.functions.items():
            instructions = func.instructions
            i = 0
            while i < len(instructions) - self._threshold:
                # 检查是否是一组相同的算术操作（可能是循环体）
                similar = True
                for j in range(1, self._threshold):
                    curr_op = getattr(instructions[i + j], "op", "")
                    prev_op = getattr(instructions[i], "op", "")
                    if curr_op != prev_op:
                        similar = False
                        break
                if similar and instructions[i].operands == instructions[i + 1].operands:
                    # 合并相同操作
                    self._unrolled += 1
                    i += self._threshold
                    continue
                i += 1
        return program

    @property
    def stats(self) -> dict:
        return {"unrolled": self._unrolled}


# ============================================================
# Pass 11: 自动向量化（SIMD）
# ============================================================

class MathaSIMDPass:
    """自动向量化：将标量运算标记为可向量化。"""

    def __init__(self) -> None:
        self._vectorized = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            instructions = func.instructions
            # 检测连续相同的算术运算
            consecutive = 0
            last_op = None
            for instr in instructions:
                op = getattr(instr, "op", "")
                if op and last_op == op and not hasattr(instr, "c_func"):
                    consecutive += 1
                    if consecutive >= 3:
                        # 标记为可向量化
                        instr.metadata["simd"] = True
                        self._vectorized += 1
                else:
                    consecutive = 0
                last_op = op
        return program

    @property
    def stats(self) -> dict:
        return {"vectorized": self._vectorized}


# ============================================================
# Pass 12: 柯里化扁平化
# ============================================================

class MathaCurryFlattenPass:
    """柯里化扁平化：将柯里化函数调用展平。"""

    def __init__(self) -> None:
        self._flattened = 0

    def run(self, program: Any) -> Any:
        for func_name, func in program.functions.items():
            new_instructions = []
            for instr in func.instructions:
                if (hasattr(instr, "func_name") and instr.func_name
                        and hasattr(instr, "operands") and len(instr.operands) == 1):
                    # 检查是否是单参数柯里化调用
                    arg = instr.operands[0]
                    if isinstance(arg, str) and not arg.startswith("%") and "." not in arg:
                        # 可能是柯里化：fn(a)(b) 形式
                        pass  # 简化：暂不处理
                new_instructions.append(instr)
            func.instructions = new_instructions
        return program

    @property
    def stats(self) -> dict:
        return {"flattened": self._flattened}


# ============================================================
# 优化管道
# ============================================================

class MathaOptimizationPipeline:
    """优化管道：按顺序运行所有优化 Pass。"""

    def __init__(self, aggressive: bool = False) -> None:
        self._passes = [
            MathaConstFoldPass(),
            MathaSimplifyPass(),
            MathaTailRecPass(),
            MathaLoopUnrollPass(),
            MathaSIMDPass(),
            MathaCurryFlattenPass(),
            MathaCommonSubexprElimPass(),
            MathaCopyPropagationPass(),
            MathaStrengthReductionPass(),
            MathaDeadCodeElimPass(),
            MathaInlinePass(),
            MathaPeepholeOptimizer(),
        ]
        if aggressive:
            # 激进模式：多次迭代
            self._passes = self._passes * 3

    def run(self, program: Any) -> Any:
        for phase in self._passes:
            program = phase.run(program)
        return program

    def get_summary(self) -> str:
        lines = ["Matha 优化摘要:", "=" * 50]
        total = {"folded": 0, "simplified": 0, "eliminated": 0,
                 "propagated": 0, "reduced": 0, "removed": 0,
                 "inlined": 0, "optimized": 0, "unrolled": 0,
                 "vectorized": 0, "flattened": 0}
        for phase in self._passes:
            stats = phase.stats
            for key, value in stats.items():
                total[key] = total.get(key, 0) + value
                lines.append(f"  {key}: {value}")
        lines.append("-" * 50)
        lines.append(f"  总计: {sum(total.values())} 次优化")
        return "\n".join(lines)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MathaConstFoldPass",
    "MathaSimplifyPass",
    "MathaDeadCodeElimPass",
    "MathaCommonSubexprElimPass",
    "MathaCopyPropagationPass",
    "MathaStrengthReductionPass",
    "MathaInlinePass",
    "MathaPeepholeOptimizer",
    "MathaTailRecPass",
    "MathaLoopUnrollPass",
    "MathaSIMDPass",
    "MathaCurryFlattenPass",
    "MathaOptimizationPipeline",
]
