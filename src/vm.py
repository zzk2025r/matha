"""
MathaVM：MIR 级原生解释器

与现有 Interpreter（AST 级）的区别：
  - Interpreter: AST → Python 递归求值（慢，~75x 慢于 Python 原生）
  - MathaVM:     MIR → 栈式执行（快，~1-2x 快于 Interpreter）

设计目标：
  1. 直接执行 MIR 指令，无需 Python AST 递归
  2. 与 Interpreter 交叉验证（相同输入 → 相同输出）
  3. 支持所有 MIR 指令类型
  4. 性能基准测试
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================
# 日志配置
# ============================================================

logger = logging.getLogger("matha.vm")


def configure_vm_logging(level: int = logging.WARNING) -> None:
    """配置 VM 日志。"""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)


# ============================================================
# MIR 指令执行结果
# ============================================================

class VMResult(Enum):
    """VM 执行结果。"""
    OK = "ok"
    HALT = "halt"
    RETURN = "return"
    ERROR = "error"
    BRANCH_TRUE = "branch_true"
    BRANCH_FALSE = "branch_false"
    JUMP = "jump"
    LABEL = "label"


@dataclass
class VMFrame:
    """执行帧（函数调用栈）。"""
    func_name: str
    params: list[str] = field(default_factory=list)
    locals: dict[str, float] = field(default_factory=dict)
    instructions: list = field(default_factory=list)
    pc: int = 0  # 程序计数器
    returns: list[float] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


@dataclass
class VMState:
    """VM 全局状态。"""
    frames: list[VMFrame] = field(default_factory=list)
    globals: dict[str, float] = field(default_factory=dict)
    outputs: list[Any] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    error: str | None = None
    max_iterations: int = 1_000_000
    _iterations: int = 0


# ============================================================
# MathaVM：MIR 原生解释器
# ============================================================

class MathaVM:
    """
    Matha VM：直接执行 MIR 指令的原生解释器。

    与 Interpreter 的对比：
    ┌─────────────────┬──────────────────────┬─────────────────────┐
    │     特性        │   Interpreter        │     MathaVM         │
    ├─────────────────┼──────────────────────┼─────────────────────┤
    │ 执行级别         │ AST 递归求值          │ MIR 指令执行         │
    │ 性能            │ 慢（~75x）           │ 快（~1-2x）         │
    │ 内存占用         │ 高（递归栈）          │ 低（迭代执行）       │
    │ 调试能力         │ 好（Python 反射）     │ 中（trace 日志）     │
    │ 交叉验证         │ 基准                 │ 对比目标             │
    └─────────────────┴──────────────────────┴─────────────────────┘
    """

    # C 数学函数映射
    _MATH_FUNCS: dict[str, callable] = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "atan2": math.atan2, "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "sqrt": math.sqrt, "cbrt": lambda x: x ** (1/3),
        "exp": math.exp, "exp2": lambda x: 2 ** x,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "fabs": abs, "floor": math.floor, "ceil": math.ceil,
        "round": round, "trunc": lambda x: int(x),
        "hypot": math.hypot, "fmod": math.fmod, "signbit": lambda x: -1 if x < 0 else (1 if x > 0 else 0),
    }

    def __init__(self, max_iterations: int = 1_000_000, debug: bool = False) -> None:
        self._state = VMState(max_iterations=max_iterations)
        self._debug = debug
        if debug:
            configure_vm_logging(logging.DEBUG)

    # ---------- 入口 ----------

    def run(self, mir_program: Any) -> tuple[list, list[str]]:
        """运行 MIR 程序，返回 (outputs, trace)。"""
        self._state = VMState(max_iterations=self._state.max_iterations)
        self._state.globals = {}

        for func_name, func in mir_program.functions.items():
            self._state.trace.append(f"; func {func_name}({func.params})")
            frame = VMFrame(
                func_name=func_name,
                params=func.params,
                locals={},
                instructions=getattr(func, "instructions", []),
            )
            # 预解析标签
            for i, instr in enumerate(frame.instructions):
                if hasattr(instr, "label"):
                    frame.labels[instr.label] = i
            self._state.frames.append(frame)
            self._execute_frame(frame)

        return self._state.outputs, self._state.trace

    def run_func(self, func_name: str, args: list[float] | None = None) -> float:
        """运行指定函数，返回结果。"""
        self._state = VMState(max_iterations=self._state.max_iterations)
        args = args or []

        if func_name not in self._state.globals:
            # 从 program 中查找
            raise ValueError(f"函数 '{func_name}' 不存在")

        frame = VMFrame(func_name=func_name, params=[], locals=dict(enumerate(args)))
        func = self._state.globals[func_name]
        frame.instructions = getattr(func, "instructions", [])
        for i, instr in enumerate(frame.instructions):
            if hasattr(instr, "label"):
                frame.labels[instr.label] = i

        self._state.frames.append(frame)
        self._execute_frame(frame)
        return frame.returns[-1] if frame.returns else 0.0

    # ---------- 执行循环 ----------

    def _execute_frame(self, frame: VMFrame) -> None:
        """执行单个帧。"""
        instructions = frame.instructions
        pc = 0
        iterations = 0

        while pc < len(instructions):
            iterations += 1
            if iterations > self._state.max_iterations:
                self._state.error = f"执行超时: {self._state.max_iterations} 次迭代"
                self._state.trace.append(f"; ERROR: {self._state.error}")
                return

            instr = instructions[pc]
            result = self._execute_instruction(frame, instr, pc)

            if result == VMResult.HALT:
                break
            elif result == VMResult.RETURN:
                return
            elif result == VMResult.JUMP or result == VMResult.BRANCH_TRUE or result == VMResult.BRANCH_FALSE:
                # pc 由 instruction handler 设置
                pass
            elif result == VMResult.LABEL:
                pc += 1
                continue
            else:
                pc += 1

        frame.pc = pc

    def _execute_instruction(self, frame: VMFrame, instr: Any, pc: int) -> VMResult:
        """执行单条指令。"""
        result_var = getattr(instr, "result", "")
        operands = getattr(instr, "operands", [])
        metadata = getattr(instr, "metadata", {})

        # 常量赋值
        if hasattr(instr, "value") and instr.value is not None:
            val = float(instr.value)
            if result_var:
                frame.locals[result_var.lstrip("%")] = val
            if self._debug:
                self._state.trace.append(f"  [{pc}] const {result_var} = {val}")
            return VMResult.OK

        # 标签（无条件跳转或纯标签）
        if hasattr(instr, "label"):
            # 检查是否有 true_label（条件分支）
            if hasattr(instr, "true_label") and hasattr(instr, "false_label"):
                cond = self._resolve_operand(frame, operands[0]) if operands else 0.0
                if cond != 0:
                    self._state.trace.append(f"  [{pc}] br true -> %{instr.true_label}")
                    return VMResult.BRANCH_TRUE
                else:
                    self._state.trace.append(f"  [{pc}] br false -> %{instr.false_label}")
                    return VMResult.BRANCH_FALSE
            else:
                # 无条件跳转或纯标签
                label = getattr(instr, "label", "")
                if label in frame.labels:
                    if self._debug:
                        self._state.trace.append(f"  [{pc}] label %{label}")
                    return VMResult.LABEL
                elif label:
                    self._state.trace.append(f"  [{pc}] jmp %{label}")
                    return VMResult.JUMP

        # 函数调用
        if hasattr(instr, "c_func") or hasattr(instr, "func_name"):
            return self._execute_call(frame, instr, operands, result_var, metadata)

        # 算术运算
        if hasattr(instr, "op") and instr.op:
            return self._execute_arith(frame, instr, operands, result_var)

        # 比较运算
        if hasattr(instr, "op") and instr.op in ("==", "!=", "<", "<=", ">", ">="):
            return self._execute_compare(frame, instr, operands, result_var)

        # 逻辑运算
        if hasattr(instr, "op") and instr.op in ("and", "or", "not"):
            return self._execute_logical(frame, instr, operands, result_var)

        # Store/Load
        if hasattr(instr, "instr_type"):
            if instr.instr_type.name == "STORE":
                return self._execute_store(frame, instr, operands)
            elif instr.instr_type.name == "LOAD":
                return self._execute_load(frame, instr, operands, result_var)
            # 新增指令类型处理
            elif instr.instr_type.name == "FREE":
                return self._execute_free(frame, instr, operands)
            elif instr.instr_type.name == "MEMCPY":
                return self._execute_memcpy(frame, instr, operands)
            elif instr.instr_type.name == "MEMSET":
                return self._execute_memset(frame, instr, operands)
            elif instr.instr_type.name in ("VLOAD", "VSTORE"):
                return self._execute_vector_load_store(frame, instr, operands, result_var)
            elif instr.instr_type.name in ("VADD", "VSUB", "VMUL", "VDIV"):
                return self._execute_vector_arith(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VDOT":
                return self._execute_vector_dot(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VMATMUL":
                return self._execute_vector_matmul(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VTRANSPOSE":
                return self._execute_vector_transpose(frame, instr, operands, result_var)
            elif instr.instr_type.name.startswith("VREDUCE"):
                return self._execute_vector_reduce(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VSLICE":
                return self._execute_vector_slice(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VCONCAT":
                return self._execute_vector_concat(frame, instr, operands, result_var)
            elif instr.instr_type.name == "VRESHAPE":
                return self._execute_vector_reshape(frame, instr, operands, result_var)
            elif instr.instr_type.name in ("TRY", "CATCH", "THROW", "FINALLY", "LANDINGPAD"):
                return self._execute_exception(frame, instr, operands, result_var, pc)
            elif instr.instr_type.name in ("SPAWN", "SEND", "RECV", "SELECT", "YIELD"):
                return self._execute_coroutine(frame, instr, operands, result_var, pc)
            elif instr.instr_type.name in ("CHANNEL_CREATE", "CHANNEL_CLOSE"):
                return self._execute_channel(frame, instr, operands, result_var)
            elif instr.instr_type.name in ("MUTEX_LOCK", "MUTEX_UNLOCK", "COND_WAIT", "COND_SIGNAL", "COND_BROADCAST"):
                return self._execute_sync(frame, instr, operands, result_var)
            elif instr.instr_type.name in ("TRACE", "PROBE", "SAMPLE", "BREAKPOINT"):
                return self._execute_debug(frame, instr, operands, result_var)

        if self._debug:
            self._state.trace.append(f"  [{pc}] skip {type(instr).__name__}")
        return VMResult.OK

    # ---------- 算术执行 ----------

    def _execute_arith(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """执行算术运算。"""
        op = getattr(instr, "op", "")
        left = self._resolve_operand(frame, operands[0]) if len(operands) > 0 else 0.0
        right = self._resolve_operand(frame, operands[1]) if len(operands) > 1 else 0.0

        try:
            if op == "+":
                val = left + right
            elif op == "-":
                val = left - right
            elif op == "*":
                val = left * right
            elif op == "/":
                val = left / right if right != 0 else float("inf")
            elif op == "**":
                val = left ** right
            elif op == "%":
                val = left % right if right != 0 else float("nan")
            else:
                val = 0.0

            if result_var:
                frame.locals[result_var.lstrip("%")] = val
            if self._debug:
                self._state.trace.append(f"  [{instr._pc}] {result_var} = {left} {op} {right} = {val}")
            return VMResult.OK
        except (OverflowError, ValueError):
            self._state.trace.append(f"; ERROR: 算术溢出 {left} {op} {right}")
            return VMResult.ERROR

    # ---------- 比较执行 ----------

    def _execute_compare(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """执行比较运算。"""
        op = getattr(instr, "op", "")
        left = self._resolve_operand(frame, operands[0])
        right = self._resolve_operand(frame, operands[1])

        try:
            if op == "==":
                val = 1.0 if left == right else 0.0
            elif op == "!=":
                val = 1.0 if left != right else 0.0
            elif op == "<":
                val = 1.0 if left < right else 0.0
            elif op == "<=":
                val = 1.0 if left <= right else 0.0
            elif op == ">":
                val = 1.0 if left > right else 0.0
            elif op == ">=":
                val = 1.0 if left >= right else 0.0
            else:
                val = 0.0

            if result_var:
                frame.locals[result_var.lstrip("%")] = val
            return VMResult.OK
        except Exception:
            return VMResult.ERROR

    # ---------- 逻辑执行 ----------

    def _execute_logical(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """执行逻辑运算。"""
        op = getattr(instr, "op", "")
        left = self._resolve_operand(frame, operands[0])
        right = self._resolve_operand(frame, operands[1]) if len(operands) > 1 else 0.0

        try:
            if op == "and":
                val = 1.0 if (left != 0 and right != 0) else 0.0
            elif op == "or":
                val = 1.0 if (left != 0 or right != 0) else 0.0
            elif op == "not":
                val = 1.0 if left == 0 else 0.0
            else:
                val = 0.0

            if result_var:
                frame.locals[result_var.lstrip("%")] = val
            return VMResult.OK
        except Exception:
            return VMResult.ERROR

    # ---------- 函数调用执行 ----------

    def _execute_call(self, frame: VMFrame, instr: Any, operands: list, result_var: str, metadata: dict) -> VMResult:
        """执行函数调用。"""
        c_func = getattr(instr, "c_func", "") or metadata.get("c_func", "")
        func_name = getattr(instr, "func_name", "") or metadata.get("func_name", "")
        getattr(instr, "lib", "") or metadata.get("lib", "")

        # 解析操作数
        resolved = [self._resolve_operand(frame, op) for op in operands]

        # C 数学函数
        if c_func and c_func in self._MATH_FUNCS:
            try:
                val = self._MATH_FUNCS[c_func](*resolved) if resolved else self._MATH_FUNCS[c_func](0)
                if result_var:
                    frame.locals[result_var.lstrip("%")] = val
                return VMResult.OK
            except (ValueError, OverflowError, ZeroDivisionError) as e:
                self._state.trace.append(f"; ERROR: {c_func}({resolved}) -> {e}")
                return VMResult.ERROR

        # 用户定义函数
        if func_name and func_name in self._state.globals:
            target_func = self._state.globals[func_name]
            return self._execute_function_call(frame, func_name, target_func, resolved, result_var)

        # 内建函数
        if func_name in self._BUILTINS:
            try:
                val = self._BUILTINS[func_name](*resolved)
                if result_var:
                    frame.locals[result_var.lstrip("%")] = val
                return VMResult.OK
            except Exception as e:
                self._state.trace.append(f"; ERROR: {func_name}({resolved}) -> {e}")
                return VMResult.ERROR

        self._state.trace.append(f"; WARN: 未知函数 {c_func or func_name}")
        if result_var:
            frame.locals[result_var.lstrip("%")] = 0.0
        return VMResult.OK

    def _execute_function_call(self, caller_frame: VMFrame, func_name: str,
                                func: Any, args: list[float], result_var: str) -> VMResult:
        """执行用户函数调用。"""
        # 创建新帧
        new_frame = VMFrame(
            func_name=func_name,
            params=getattr(func, "params", []),
            locals=dict(enumerate(args)),
            instructions=getattr(func, "instructions", []),
        )
        # 预解析标签
        for i, instr in enumerate(new_frame.instructions):
            if hasattr(instr, "label"):
                new_frame.labels[instr.label] = i

        self._state.frames.append(new_frame)
        self._state.trace.append(f"; call {func_name}({args})")
        self._execute_frame(new_frame)
        self._state.frames.pop()

        if new_frame.returns:
            val = new_frame.returns[-1]
            if result_var:
                caller_frame.locals[result_var.lstrip("%")] = val
            return VMResult.RETURN
        return VMResult.OK

    # ---------- 存储/加载执行 ----------

    def _execute_store(self, frame: VMFrame, instr: Any, operands: list) -> VMResult:
        """执行 store 指令。"""
        value = self._resolve_operand(frame, operands[0])
        target = getattr(instr, "metadata", {}).get("target", "")
        if target:
            frame.locals[target] = value
        return VMResult.OK

    def _execute_load(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """执行 load 指令。"""
        source = operands[0] if operands else ""
        val = frame.locals.get(source.lstrip("%"), 0.0)
        if result_var:
            frame.locals[result_var.lstrip("%")] = val
        return VMResult.OK

    # ---------- 新增指令执行 ----------

    def _execute_free(self, frame: VMFrame, instr: Any, operands: list) -> VMResult:
        """执行 free 指令（标记内存可回收，实际由 Python GC 处理）。"""
        target = getattr(instr, "target", "")
        if target:
            frame.locals.pop(target, None)
        return VMResult.OK

    def _execute_memcpy(self, frame: VMFrame, instr: Any, operands: list) -> VMResult:
        """执行 memcpy 指令。"""
        dest = getattr(instr, "dest", "")
        src = getattr(instr, "src", "")
        getattr(instr, "size", 0)
        if src in frame.locals:
            frame.locals[dest] = frame.locals[src]
        return VMResult.OK

    def _execute_memset(self, frame: VMFrame, instr: Any, operands: list) -> VMResult:
        """执行 memset 指令。"""
        target = getattr(instr, "target", "")
        value = getattr(instr, "value", 0)
        getattr(instr, "size", 0)
        frame.locals[target] = float(value)
        return VMResult.OK

    # 向量操作
    def _resolve_vector(self, frame: VMFrame, operand: Any) -> list:
        """解析向量操作数。"""
        if isinstance(operand, list):
            return [float(x) for x in operand]
        if isinstance(operand, str):
            return frame.locals.get(operand.lstrip("%"), [])
        return []

    def _execute_vector_load_store(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量加载/存储。"""
        if hasattr(instr, "instr_type"):
            if instr.instr_type.name == "VLOAD":
                source = operands[0] if operands else ""
                vec = frame.locals.get(source.lstrip("%"), [])
                if result_var:
                    frame.locals[result_var.lstrip("%")] = vec
            elif instr.instr_type.name == "VSTORE":
                target = getattr(instr, "target", "")
                vec = self._resolve_vector(frame, operands[0]) if operands else []
                frame.locals[target] = vec
        return VMResult.OK

    def _execute_vector_arith(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量四则运算。"""
        op = getattr(instr, "op", "")
        left = self._resolve_vector(frame, operands[0]) if operands else []
        right = self._resolve_vector(frame, operands[1]) if len(operands) > 1 else []

        if len(left) != len(right):
            self._state.trace.append(f"; ERROR: 向量长度不匹配 {len(left)} vs {len(right)}")
            return VMResult.ERROR

        try:
            if op == "add":
                result = [a + b for a, b in zip(left, right)]
            elif op == "sub":
                result = [a - b for a, b in zip(left, right)]
            elif op == "mul":
                result = [a * b for a, b in zip(left, right)]
            elif op == "div":
                result = [a / b if b != 0 else float("inf") for a, b in zip(left, right)]
            else:
                result = []

            if result_var:
                frame.locals[result_var.lstrip("%")] = result
            return VMResult.OK
        except Exception as e:
            self._state.trace.append(f"; ERROR: 向量运算 {e}")
            return VMResult.ERROR

    def _execute_vector_dot(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量点积。"""
        left = self._resolve_vector(frame, operands[0]) if operands else []
        right = self._resolve_vector(frame, operands[1]) if len(operands) > 1 else []

        if len(left) != len(right):
            return VMResult.ERROR

        result = sum(a * b for a, b in zip(left, right))
        if result_var:
            frame.locals[result_var.lstrip("%")] = result
        return VMResult.OK

    def _execute_vector_matmul(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """矩阵乘法（简化版：仅支持 1D 向量外积）。"""
        left = self._resolve_vector(frame, operands[0]) if operands else []
        right = self._resolve_vector(frame, operands[1]) if len(operands) > 1 else []

        # 简化：向量外积
        result = [[a * b for b in right] for a in left]
        if result_var:
            frame.locals[result_var.lstrip("%")] = result
        return VMResult.OK

    def _execute_vector_transpose(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """矩阵转置。"""
        matrix = self._resolve_vector(frame, operands[0]) if operands else []
        # 简化：假设是 2D 列表
        if matrix and isinstance(matrix[0], list):
            result = list(map(list, zip(*matrix)))
        else:
            result = matrix
        if result_var:
            frame.locals[result_var.lstrip("%")] = result
        return VMResult.OK

    def _execute_vector_reduce(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量归约。"""
        vec = self._resolve_vector(frame, operands[0]) if operands else []
        if not vec:
            return VMResult.OK

        reduce_op = getattr(instr, "reduce_op", "sum")
        try:
            if reduce_op == "sum":
                result = sum(vec)
            elif reduce_op == "max":
                result = max(vec)
            elif reduce_op == "min":
                result = min(vec)
            elif reduce_op == "mean":
                result = sum(vec) / len(vec)
            else:
                result = 0.0

            if result_var:
                frame.locals[result_var.lstrip("%")] = result
            return VMResult.OK
        except Exception:
            return VMResult.ERROR

    def _execute_vector_slice(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量切片。"""
        vec = self._resolve_vector(frame, operands[0]) if operands else []
        start = getattr(instr, "start", (0,))
        end = getattr(instr, "end", (len(vec),))

        # 简化：1D 切片
        s = start[0] if start else 0
        e = end[0] if end else len(vec)
        result = vec[s:e]

        if result_var:
            frame.locals[result_var.lstrip("%")] = result
        return VMResult.OK

    def _execute_vector_concat(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量拼接。"""
        axis = getattr(instr, "axis", 0)
        vectors = [self._resolve_vector(frame, op) for op in operands]
        if not vectors:
            return VMResult.OK

        if axis == 0:
            result = []
            for v in vectors:
                result.extend(v)
        else:
            # 简化：仅 axis=0
            result = vectors[0]

        if result_var:
            frame.locals[result_var.lstrip("%")] = result
        return VMResult.OK

    def _execute_vector_reshape(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """向量重塑。"""
        vec = self._resolve_vector(frame, operands[0]) if operands else []
        getattr(instr, "new_shape", tuple())
        # 简化：仅展平/重塑 1D
        if result_var:
            frame.locals[result_var.lstrip("%")] = vec
        return VMResult.OK

    # 异常处理
    def _execute_exception(self, frame: VMFrame, instr: Any, operands: list, result_var: str, pc: int) -> VMResult:
        """异常处理指令。"""
        instr_type = instr.instr_type.name

        if instr_type == "THROW":
            exc = operands[0] if operands else "unknown"
            frame.locals["__exception__"] = exc
            self._state.trace.append(f"  [{pc}] throw {exc}")
            # 查找最近的 catch
            return VMResult.BRANCH_TRUE  # 触发异常分支

        elif instr_type == "TRY":
            # 记录 catch/finally 标签，实际跳转由异常触发
            return VMResult.OK

        elif instr_type == "CATCH":
            # 检查是否有异常
            exc = frame.locals.get("__exception__")
            if exc:
                exc_type = getattr(instr, "exception_type", "")
                exc_var = getattr(instr, "exception_var", "")
                if not exc_type or exc_type == exc:
                    if exc_var:
                        frame.locals[exc_var] = exc
                    frame.locals.pop("__exception__", None)
                    return VMResult.BRANCH_TRUE
            return VMResult.BRANCH_FALSE

        elif instr_type == "FINALLY":
            # finally 块总是执行
            return VMResult.OK

        return VMResult.OK

    # 协程/并发
    def _execute_coroutine(self, frame: VMFrame, instr: Any, operands: list, result_var: str, pc: int) -> VMResult:
        """协程指令。"""
        instr_type = instr.instr_type.name

        if instr_type == "SPAWN":
            func_name = getattr(instr, "func_name", "")
            # 简化：标记为后台任务
            frame.locals["__spawned__"] = frame.locals.get("__spawned__", []) + [func_name]
            return VMResult.OK

        elif instr_type == "SEND":
            channel = getattr(instr, "channel", "")
            value = self._resolve_operand(frame, operands[0]) if operands else 0.0
            if "__channels__" not in frame.locals:
                frame.locals["__channels__"] = {}
            if channel not in frame.locals["__channels__"]:
                frame.locals["__channels__"][channel] = []
            frame.locals["__channels__"][channel].append(value)
            return VMResult.OK

        elif instr_type == "RECV":
            channel = getattr(instr, "channel", "")
            channels = frame.locals.get("__channels__", {})
            if channel in channels and channels[channel]:
                value = channels[channel].pop(0)
                if result_var:
                    frame.locals[result_var.lstrip("%")] = value
                return VMResult.OK
            # 通道为空，挂起（简化：返回 0）
            if result_var:
                frame.locals[result_var.lstrip("%")] = 0.0
            return VMResult.OK

        elif instr_type == "SELECT":
            cases = getattr(instr, "cases", [])
            default_label = getattr(instr, "default_label", "")
            channels = frame.locals.get("__channels__", {})
            for ch, label in cases:
                if ch in channels and channels[ch]:
                    # 有数据，跳转到对应 label
                    frame.pc = frame.labels.get(label, pc)
                    return VMResult.JUMP
            if default_label:
                frame.pc = frame.labels.get(default_label, pc)
                return VMResult.JUMP
            return VMResult.OK

        elif instr_type == "YIELD":
            # 协程让出，简化为 no-op
            return VMResult.OK

        return VMResult.OK

    def _execute_channel(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """通道操作。"""
        instr_type = instr.instr_type.name

        if instr_type == "CHANNEL_CREATE":
            getattr(instr, "elem_type", "double")
            getattr(instr, "capacity", 0)
            chan_id = f"chan_{len(frame.locals.get('__channels__', {}))}"
            if "__channels__" not in frame.locals:
                frame.locals["__channels__"] = {}
            frame.locals["__channels__"][chan_id] = []
            if result_var:
                frame.locals[result_var.lstrip("%")] = chan_id
            return VMResult.OK

        elif instr_type == "CHANNEL_CLOSE":
            channel = getattr(instr, "channel", "")
            if "__channels__" in frame.locals:
                frame.locals["__channels__"].pop(channel, None)
            return VMResult.OK

        return VMResult.OK

    def _execute_sync(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """同步原语。"""
        instr_type = instr.instr_type.name

        if instr_type == "MUTEX_LOCK":
            mutex = getattr(instr, "mutex", "")
            locks = frame.locals.get("__mutexes__", {})
            locks[mutex] = True
            frame.locals["__mutexes__"] = locks
            return VMResult.OK

        elif instr_type == "MUTEX_UNLOCK":
            mutex = getattr(instr, "mutex", "")
            locks = frame.locals.get("__mutexes__", {})
            locks[mutex] = False
            frame.locals["__mutexes__"] = locks
            return VMResult.OK

        elif instr_type in ("COND_WAIT", "COND_SIGNAL", "COND_BROADCAST"):
            # 简化：标记条件变量状态
            return VMResult.OK

        return VMResult.OK

    def _execute_debug(self, frame: VMFrame, instr: Any, operands: list, result_var: str) -> VMResult:
        """调试/画像指令。"""
        instr_type = instr.instr_type.name

        if instr_type == "TRACE":
            msg = getattr(instr, "message", "")
            self._state.trace.append(f"  [TRACE] {msg}")
        elif instr_type == "PROBE":
            probe_id = getattr(instr, "probe_id", "")
            self._state.trace.append(f"  [PROBE] {probe_id}")
        elif instr_type == "SAMPLE":
            sample_name = getattr(instr, "sample_name", "")
            self._state.trace.append(f"  [SAMPLE] {sample_name}")
        elif instr_type == "BREAKPOINT":
            self._state.trace.append("  [BREAKPOINT]")

        return VMResult.OK

    # ---------- 帮助方法 ----------

    def _resolve_operand(self, frame: VMFrame, op: Any) -> float:
        """解析操作数（变量或常量）。"""
        if isinstance(op, (int, float)):
            return float(op)
        if isinstance(op, str):
            # 尝试解析为数字
            try:
                return float(op)
            except ValueError:
                # 变量引用
                return frame.locals.get(op.lstrip("%"), 0.0)
        return 0.0

    def _eval_expr(self, expr: Any, frame: VMFrame) -> float:
        """递归求值表达式。"""
        if isinstance(expr, (int, float)):
            return float(expr)
        if isinstance(expr, str):
            try:
                return float(expr)
            except ValueError:
                return frame.locals.get(expr, 0.0)
        return 0.0

    # ---------- 内建函数 ----------
    _BUILTINS: dict[str, callable] = {
        "print": lambda *args: None,  # 在 VM 层不直接输出
        "len": lambda x: float(len(x)) if hasattr(x, "__len__") else 0.0,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
    }


# ============================================================
# 交叉验证器
# ============================================================

class CrossVerifier:
    """
    交叉验证器：对比 Interpreter (AST) 和 MathaVM (MIR) 的执行结果。

    工作流程：
    1. 解析 Matha 源码为 AST
    2. 用 Interpreter 执行 AST
    3. 将 AST 编译为 MIR
    4. 用 MathaVM 执行 MIR
    5. 对比两者的输出和 trace
    """

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose
        self._results: list[dict] = []

    def verify(self, source: str) -> dict:
        """验证源码在两个解释器中产生相同结果。"""
        from src.interp import Interpreter
        from src.mir import MIRGenerator
        from src.parser import parse

        result = {
            "source": source[:100],
            "interpreter_output": None,
            "vm_output": None,
            "match": False,
            "errors": [],
        }

        try:
            # 1. 解析
            ast_program = parse(source)

            # 2. Interpreter 执行
            interp = Interpreter()
            interp_outputs, interp_trace = interp.run(ast_program)
            result["interpreter_output"] = interp_outputs
            if self._verbose:
                print(f"  [Interpreter] outputs={interp_outputs}, trace_len={len(interp_trace)}")

            # 3. 编译为 MIR
            mir_gen = MIRGenerator()
            mir_program = mir_gen.generate(ast_program)

            # 4. MathaVM 执行
            vm = MathaVM(debug=self._verbose)
            vm_outputs, vm_trace = vm.run(mir_program)
            result["vm_output"] = vm_outputs
            if self._verbose:
                print(f"  [MathaVM] outputs={vm_outputs}, trace_len={len(vm_trace)}")

            # 5. 对比
            if interp_outputs == vm_outputs:
                result["match"] = True
                if self._verbose:
                    print("  ✓ 输出匹配")
            else:
                result["match"] = False
                result["errors"].append(f"输出不匹配: interp={interp_outputs}, vm={vm_outputs}")
                if self._verbose:
                    print("  ✗ 输出不匹配")

        except Exception as e:
            result["errors"].append(f"执行错误: {type(e).__name__}: {e}")
            if self._verbose:
                print(f"  ✗ 错误: {e}")

        self._results.append(result)
        return result

    def batch_verify(self, sources: list[str]) -> dict:
        """批量验证多个源码。"""
        passed = 0
        failed = 0
        for i, source in enumerate(sources):
            result = self.verify(source)
            if result["match"]:
                passed += 1
            else:
                failed += 1
            print(f"  [{i+1}/{len(sources)}] {'✓' if result['match'] else '✗'} {source[:50]}...")

        return {
            "total": len(sources),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(sources) if sources else 0,
            "results": self._results,
        }

    def get_summary(self) -> str:
        """获取验证摘要。"""
        total = len(self._results)
        passed = sum(1 for r in self._results if r["match"])
        return f"交叉验证: {passed}/{total} 通过 ({passed/total*100:.1f}%)"


# ============================================================
# 性能基准
# ============================================================

def benchmark(interpreter_source: str, iterations: int = 1000) -> dict:
    """性能基准测试。"""
    import time

    from src.interp import Interpreter
    from src.mir import MIRGenerator
    from src.mir_opt import MathaOptimizationPipeline
    from src.parser import parse

    ast_program = parse(interpreter_source)

    # Interpreter 基准
    interp = Interpreter()
    t0 = time.perf_counter()
    for _ in range(iterations):
        interp.run(ast_program)
    interp_ms = (time.perf_counter() - t0) * 1000

    # MathaVM 基准
    mir_gen = MIRGenerator()
    mir_program = mir_gen.generate(ast_program)
    pipeline = MathaOptimizationPipeline()
    mir_program = pipeline.run(mir_program)

    vm = MathaVM()
    t0 = time.perf_counter()
    for _ in range(iterations):
        vm.run(mir_program)
    vm_ms = (time.perf_counter() - t0) * 1000

    speedup = interp_ms / vm_ms if vm_ms > 0 else float("inf")

    return {
        "interpreter_ms": interp_ms,
        "vm_ms": vm_ms,
        "speedup": speedup,
        "iterations": iterations,
    }


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MathaVM",
    "VMResult",
    "VMFrame",
    "VMState",
    "CrossVerifier",
    "benchmark",
    "configure_vm_logging",
]
