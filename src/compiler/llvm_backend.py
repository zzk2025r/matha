# -*- coding: utf-8 -*-
"""Matha LLVM 后端：Matha AST → LLVM IR → 原生机器码。

架构：
  1. Matha AST → Matha IR (中间表示)
  2. Matha IR → LLVM IR (文本格式)
  3. LLVM IR → 本机机器码 (通过 llc/clang subprocess)
  4. 原生机器码 → 可调用函数 (通过 ctypes)

性能目标：
  - 算术表达式：接近 Python 原生速度
  - 递归函数：通过 LLVM 尾递归消除 + 循环转换
  - 数值循环：向量化 (SIMD)

依赖：
  - 可选：llvmlite (Python LLVM bindings)
  - 必需：llc 或 clang (LLVM 工具链)
"""

from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


# ============================================================
# LLVM 类型系统
# ============================================================

class LLVMType(Enum):
    VOID = "void"
    I1 = "i1"
    I8 = "i8"
    I16 = "i16"
    I32 = "i32"
    I64 = "i64"
    FLOAT = "float"
    DOUBLE = "double"
    PTR = "ptr"
    ARRAY = "array"
    FUNC = "function"


@dataclass
class LLVMValue:
    """LLVM 值表示。"""
    name: str
    lltype: str
    immediate: bool = False

    def __str__(self) -> str:
        if self.immediate:
            return self.name
        return f"%{self.name}"

    def __repr__(self) -> str:
        return f"LLVMValue({self.name}, {self.lltype})"


# ============================================================
# Matha IR (中间表示)
# ============================================================

class MathaIRNode:
    """Matha 中间表示节点基类。"""
    pass


@dataclass
class IRConstant(MathaIRNode):
    value: Any
    lltype: str = "double"


@dataclass
class IRVariable(MathaIRNode):
    name: str
    lltype: str = "double"


@dataclass
class IRArithOp(MathaIRNode):
    op: str  # add, sub, mul, div, fadd, fsub, fmul, fdiv
    left: MathaIRNode
    right: MathaIRNode
    result_type: str = "double"


@dataclass
class IRCompareOp(MathaIRNode):
    op: str  # eq, ne, lt, gt, le, ge
    left: MathaIRNode
    right: MathaIRNode


@dataclass
class IRLogicalOp(MathaIRNode):
    op: str  # and, or, not
    operands: list[MathaIRNode]


@dataclass
class IRFunctionCall(MathaIRNode):
    func_name: str
    args: list[MathaIRNode]
    result_type: str = "double"


@dataclass
class IRVariableAccess(MathaIRNode):
    name: str
    lltype: str = "double"


@dataclass
class IRAssignment(MathaIRNode):
    target: str
    value: MathaIRNode
    lltype: str = "double"


@dataclass
class IRIfExpr(MathaIRNode):
    cond: MathaIRNode
    then_branch: MathaIRNode
    else_branch: MathaIRNode
    result_type: str = "double"


@dataclass
class IRLoop(MathaIRNode):
    init: MathaIRNode
    cond: MathaIRNode
    step: MathaIRNode
    body: MathaIRNode
    result_type: str = "void"


@dataclass
class IRFunctionDef(MathaIRNode):
    name: str
    params: list[str]
    param_types: list[str]
    return_type: str
    body: MathaIRNode


# ============================================================
# Matha AST → IR 转换器
# ============================================================

class MathaToIRConverter:
    """将 Matha AST 转换为 Matha IR。"""

    def __init__(self) -> None:
        self._var_count = 0

    def _fresh_var(self, lltype: str = "double") -> str:
        self._var_count += 1
        return f"var_{self._var_count}"

    def convert(self, ast_node: Any) -> MathaIRNode:
        """将 AST 节点转换为 IR。"""
        if ast_node is None:
            return IRConstant(0.0, "double")

        kind = type(ast_node).__name__

        if kind == "IntegerLit":
            return IRConstant(float(ast_node.value), "double")
        if kind == "FloatLit":
            return IRConstant(float(ast_node.value), "double")
        if kind == "StringLit":
            return IRConstant(ast_node.value, "ptr")
        if kind == "BoolLit":
            return IRConstant(1.0 if ast_node.value else 0.0, "i1")

        elif kind == "Variable":
            return IRVariableAccess(ast_node.name, "double")

        elif kind == "BinaryOp":
            return self._convert_binary(ast_node)

        elif kind == "UnaryOp":
            return self._convert_unary(ast_node)

        elif kind == "FuncApp":
            return self._convert_func_app(ast_node)

        elif kind == "Lambda":
            return self._convert_lambda(ast_node)

        elif kind == "IfExpr":
            return self._convert_if_expr(ast_node)

        elif kind == "ListLiteral":
            items = [self.convert(i) for i in getattr(ast_node, "items", [])]
            return IRConstant(items, "ptr")

        elif kind == "DictLiteral":
            return IRConstant({}, "ptr")

        elif kind == "IndexExpr":
            container = self.convert(ast_node.container)
            index = self.convert(ast_node.index)
            return IRArithOp("getelementptr", container, index, "ptr")

        elif kind == "PathExpr":
            left = self.convert(ast_node.left)
            right = ast_node.right if hasattr(ast_node, "right") else ""
            return IRVariableAccess(f"{left}.{right}", "double")

        elif kind == "LetBinding":
            val = self.convert(ast_node.value)
            if ast_node.body:
                body = self.convert(ast_node.body)
                return IRAssignment(ast_node.name, val, "double")
            return IRAssignment(ast_node.name, val, "double")

        # 兼容 fake node (测试用)
        if hasattr(ast_node, 'kind'):
            if ast_node.kind == "IntegerLit":
                return IRConstant(float(ast_node.value), "double")
            if ast_node.kind == "FloatLit":
                return IRConstant(float(ast_node.value), "double")
            if ast_node.kind == "Variable":
                return IRVariableAccess(ast_node.name, "double")
            if ast_node.kind == "BinaryOp":
                return self._convert_binary(ast_node)
            if ast_node.kind == "FuncApp":
                return self._convert_func_app(ast_node)

        return IRConstant(0.0, "double")

    def _convert_binary(self, node: Any) -> MathaIRNode:
        left = self.convert(node.left)
        right = self.convert(node.right)
        op = getattr(node, "op", "")

        # 数值运算
        if op in ("+", "-", "*", "/", "//", "%"):
            llvm_op = {"+": "fadd", "-": "fsub", "*": "fmul",
                       "/": "fdiv", "//": "fdiv", "%": "fmod"}.get(op, op)
            return IRArithOp(llvm_op, left, right, "double")

        if op == "**":
            return IRArithOp("call @pow", left, right, "double")

        # 比较运算
        if op in ("<", ">", "<=", ">=", "==", "!="):
            llvm_op = {"<": "fcmp olt", ">": "fcmp ogta", "<=": "fcmp ole",
                       ">=": "fcmp oge", "==": "fcmp one", "!=": "fcmp one"}.get(op, op)
            return IRCompareOp(llvm_op, left, right)

        # 逻辑运算
        if op in ("and", "or"):
            return IRLogicalOp(op, [left, right])

        if op == "→":
            # 函数应用
            return IRFunctionCall(left.name if hasattr(left, "name") else "func",
                                 [right], "double")

        if op == "++":
            return IRArithOp("fadd", left, IRConstant(1.0, "double"), "double")

        if op == "--":
            return IRArithOp("fsub", left, IRConstant(1.0, "double"), "double")

        return IRConstant(0.0, "double")

    def _convert_unary(self, node: Any) -> MathaIRNode:
        operand = self.convert(node.operand)
        op = getattr(node, "op", "")

        if op == "-":
            return IRArithOp("fsub", IRConstant(0.0, "double"), operand, "double")
        if op == "^":
            return IRArithOp("call @sqrt", operand, IRConstant(0.0, "double"), "double")
        if op == "++":
            return IRArithOp("fadd", operand, IRConstant(1.0, "double"), "double")
        if op == "--":
            return IRArithOp("fsub", operand, IRConstant(1.0, "double"), "double")

        return operand

    def _convert_func_app(self, node: Any) -> MathaIRNode:
        func = self.convert(node.func)
        arg = self.convert(node.arg)
        func_name = func.name if hasattr(func, "name") else "unknown"
        return IRFunctionCall(func_name, [arg], "double")

    def _convert_lambda(self, node: Any) -> MathaIRNode:
        params = [p.name if hasattr(p, "name") else str(p)
                  for p in getattr(node, "params", [])]
        body = self.convert(node.body)
        return IRFunctionDef(f"lambda_{id(node)}", params, ["double"] * len(params),
                             "double", body)

    def _convert_if_expr(self, node: Any) -> MathaIRNode:
        cond = self.convert(node.cond)
        then_branch = self.convert(node.then)
        else_branch = self.convert(node.else_) if hasattr(node, "else_") and node.else_ \
            else IRConstant(0.0, "double")
        return IRIfExpr(cond, then_branch, else_branch, "double")

    def convert_program(self, program: Any) -> list[MathaIRNode]:
        """转换整个程序。"""
        nodes = []
        for decl in getattr(program, "decls", []):
            kind = type(decl).__name__
            if kind == "Binding":
                nodes.append(IRAssignment(
                    getattr(decl.target, "name", "result"),
                    self.convert(decl.value),
                    "double"
                ))
            elif kind == "FuncDef":
                params = [p.name if hasattr(p, "name") else str(p)
                          for p in getattr(decl, "params", [])]
                nodes.append(IRFunctionDef(
                    decl.name, params, ["double"] * len(params),
                    "double", self.convert(decl.body)
                ))
            elif kind in ("Output", "MechUnit"):
                if hasattr(decl, "expr") and decl.expr:
                    nodes.append(self.convert(decl.expr))
        return nodes


# ============================================================
# Matha IR → LLVM IR 生成器
# ============================================================

class LLVMIRGenerator:
    """将 Matha IR 转换为 LLVM IR 文本。"""

    def __init__(self, module_name: str = "matha_module") -> None:
        self._module_name = module_name
        self._funcs: dict[str, str] = {}
        self._globals: list[str] = []
        self._llvm_vars: dict[str, str] = {}
        self._var_counter = 0

    def _fresh_var(self) -> str:
        self._var_counter += 1
        return f"%v{self._var_counter}"

    def _llvm_type(self, matha_type: str) -> str:
        type_map = {
            "double": "double",
            "i1": "i1",
            "i32": "i32",
            "i64": "i64",
            "ptr": "ptr",
            "string": "ptr",
        }
        return type_map.get(matha_type, "double")

    def generate(self, ir_nodes: list[MathaIRNode]) -> str:
        """生成完整的 LLVM IR 模块。"""
        lines = [
            "; Matha LLVM IR 生成自 Matha AST",
            f"; 模块: {self._module_name}",
            ";",
            'target triple = "x86_64-pc-windows-msvc"',
            '',
            '; 数学函数声明',
            'declare double @sqrt(double)',
            'declare double @pow(double, double)',
            'declare double @sin(double)',
            'declare double @cos(double)',
            'declare double @tan(double)',
            'declare double @log(double)',
            'declare double @exp(double)',
            'declare double @fabs(double)',
            '',
            '; 主函数',
            'define double @main() {',
            '  entry:',
        ]

        # 生成每个 IR 节点
        for node in ir_nodes:
            ir_ll = self._emit_node(node)
            if ir_ll:
                lines.extend(ir_ll)

        lines.extend([
            '  ret double 0.0',
            '}',
        ])

        return "\n".join(lines)

    def _emit_node(self, node: MathaIRNode) -> list[str]:
        """生成单个 IR 节点的 LLVM IR。"""
        if isinstance(node, IRConstant):
            return self._emit_constant(node)
        elif isinstance(node, IRVariableAccess):
            return self._emit_variable(node)
        elif isinstance(node, IRArithOp):
            return self._emit_arith(node)
        elif isinstance(node, IRCompareOp):
            return self._emit_compare(node)
        elif isinstance(node, IRLogicalOp):
            return self._emit_logical(node)
        elif isinstance(node, IRFunctionCall):
            return self._emit_func_call(node)
        elif isinstance(node, IRAssignment):
            return self._emit_assignment(node)
        elif isinstance(node, IRIfExpr):
            return self._emit_if(node)
        elif isinstance(node, IRLoop):
            return self._emit_loop(node)
        elif isinstance(node, IRFunctionDef):
            return self._emit_function_def(node)
        return []

    def _emit_constant(self, node: IRConstant) -> list[str]:
        val = node.value
        lltype = self._llvm_type(node.lltype)
        var = self._fresh_var()
        if isinstance(val, bool):
            return [f"  {var} = call {lltype} @const_bool({int(val)})"]
        return [f"  {var} = const {lltype} {val}"]

    def _emit_variable(self, node: IRVariableAccess) -> list[str]:
        var = self._fresh_var()
        if node.name in self._llvm_vars:
            return [f"  {var} = load {self._llvm_type(node.lltype)}, {self._llvm_type(node.lltype)}* {self._llvm_vars[node.name]}"]
        return [f"  {var} = const {self._llvm_type(node.lltype)} 0.0"]

    def _emit_arith(self, node: IRArithOp) -> list[str]:
        left_ll = self._emit_node(node.left)
        right_ll = self._emit_node(node.right)
        result_var = self._fresh_var()
        result_type = self._llvm_type(node.result_type)

        # 生成左右操作数
        lines = list(left_ll) + list(right_ll) if left_ll and right_ll else []

        if node.op in ("fadd", "fsub", "fmul", "fdiv", "fmod"):
            lines.append(f"  {result_var} = {node.op} {result_type} {left_ll[-1].split('=')[1].strip() if left_ll else '0.0'}, {right_ll[-1].split('=')[1].strip() if right_ll else '0.0'}")
        elif node.op == "call @pow":
            lines.append(f"  {result_var} = call {result_type} @pow({result_type} {left_ll[-1].split('=')[1].strip() if left_ll else '0.0'}, {result_type} {right_ll[-1].split('=')[1].strip() if right_ll else '0.0'})")
        elif node.op == "call @sqrt":
            lines.append(f"  {result_var} = call {result_type} @sqrt({result_type} {left_ll[-1].split('=')[1].strip() if left_ll else '0.0'})")
        elif node.op in ("getelementptr",):
            lines.append(f"  {result_var} = getelementptr {result_type}*, {result_type}** {left_ll[-1].split('=')[1].strip() if left_ll else 'null'}, i64 0, i64 {right_ll[-1].split('=')[1].strip() if right_ll else '0'}")
        else:
            lines.append(f"  {result_var} = const {result_type} 0.0")

        return lines

    def _emit_compare(self, node: IRCompareOp) -> list[str]:
        left_ll = self._emit_node(node.left)
        right_ll = self._emit_node(node.right)
        result_var = self._fresh_var()
        lines = list(left_ll) + list(right_ll) if left_ll and right_ll else []

        # 简化：直接使用 fcmp
        left_val = left_ll[-1].split('=')[1].strip() if left_ll else '0.0'
        right_val = right_ll[-1].split('=')[1].strip() if right_ll else '0.0'
        lines.append(f"  {result_var} = fcmp o{node.op[4:]} double {left_val}, {right_val}" if node.op.startswith("fcmp") else
                     f"  {result_var} = icmp {node.op} double {left_val}, {right_val}")
        return lines

    def _emit_logical(self, node: IRLogicalOp) -> list[str]:
        if node.op == "not":
            operand_ll = self._emit_node(node.operands[0])
            result_var = self._fresh_var()
            operand_val = operand_ll[-1].split('=')[1].strip() if operand_ll else '0'
            return [f"  {result_var} = xor i1 {operand_val}, true"]
        # and/or 简化处理
        return [f"  %logic_tmp = const i1 0"]

    def _emit_func_call(self, node: IRFunctionCall) -> list[str]:
        result_var = self._fresh_var()
        args_str = ", ".join(
            self._emit_node(arg)[-1].split('=')[1].strip() if self._emit_node(arg) else '0.0'
            for arg in node.args
        )
        return [f"  {result_var} = call double @{node.func_name}({args_str})"]

    def _emit_assignment(self, node: IRAssignment) -> list[str]:
        val_ll = self._emit_node(node.value)
        result_var = self._fresh_var()
        lltype = self._llvm_type(node.lltype)

        lines = list(val_ll) if val_ll else []

        # 获取值
        if lines:
            val_str = lines[-1].split('=')[1].strip()
        else:
            val_str = '0.0'

        # 存储到变量
        var_name = f"@{node.target}"
        lines.append(f"  store {lltype} {val_str}, {lltype}* {var_name}")
        lines.append(f"  {result_var} = load {lltype}, {lltype}* {var_name}")

        # 记录变量
        self._llvm_vars[node.target] = var_name

        return lines

    def _emit_if(self, node: IRIfExpr) -> list[str]:
        cond_ll = self._emit_node(node.cond)
        then_ll = self._emit_node(node.then_branch)
        else_ll = self._emit_node(node.else_branch)

        lines = list(cond_ll) if cond_ll else []
        lines.extend(list(then_ll) if then_ll else [])
        lines.extend(list(else_ll) if else_ll else [])

        # 条件分支
        cond_var = cond_ll[-1].split('=')[1].strip() if cond_ll else 'false'
        then_var = then_ll[-1].split('=')[1].strip() if then_ll else '0.0'
        else_var = else_ll[-1].split('=')[1].strip() if else_ll else '0.0'

        result_var = self._fresh_var()
        lines.append(f"  br i1 {cond_var}, label %if.then, label %if.else")
        lines.append(f"if.then:")
        lines.append(f"  br label %if.end")
        lines.append(f"if.else:")
        lines.append(f"  br label %if.end")
        lines.append(f"if.end:")
        lines.append(f"  {result_var} = phi double [{then_var}, %if.then], [{else_var}, %if.else]")

        return lines

    def _emit_loop(self, node: IRLoop) -> list[str]:
        # 简化：展开为 while 循环
        init_ll = self._emit_node(node.init)
        cond_ll = self._emit_node(node.cond)
        step_ll = self._emit_node(node.step)
        body_ll = self._emit_node(node.body)

        lines = list(init_ll) if init_ll else []
        lines.extend(list(cond_ll) if cond_ll else [])

        cond_var = cond_ll[-1].split('=')[1].strip() if cond_ll else 'true'
        lines.append(f"  br label %loop.cond")
        lines.append(f"loop.cond:")
        lines.append(f"  %loop_cond = icmp eq i1 {cond_var}, true")
        lines.append(f"  br i1 %loop_cond, label %loop.body, label %loop.end")
        lines.append(f"loop.body:")
        lines.extend(list(step_ll) if step_ll else [])
        lines.extend(list(body_ll) if body_ll else [])
        lines.append(f"  br label %loop.cond")
        lines.append(f"loop.end:")

        return lines

    def _emit_function_def(self, node: IRFunctionDef) -> list[str]:
        params_str = ", ".join(f"double %{p}" for p in node.params)
        body_ir = self._emit_node(node.body)
        body_lines = "\n".join(body_ir) if body_ir else "  ret double 0.0"

        return [
            f'define double @{node.name}({params_str}) {{',
            body_lines,
            '  ret double 0.0',
            '}',
        ]


# ============================================================
# LLVM 编译器 (llc/clang)
# ============================================================

class LLVMCompiler:
    """将 LLVM IR 编译为原生机器码。"""

    def __init__(self, toolchain: str = "clang") -> None:
        self._toolchain = toolchain
        self._cache: dict[str, Callable] = {}

    def compile(self, llvm_ir: str, func_name: str = "main") -> Optional[Callable]:
        """编译 LLVM IR 为原生函数。"""
        # 检查缓存
        cache_key = hashlib.sha256(llvm_ir.encode()).hexdigest()[:16]
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # 写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ll', delete=False) as f:
                f.write(llvm_ir)
                ll_file = f.name

            # 编译为对象文件
            obj_file = ll_file + '.o'
            exe_file = ll_file + '.exe'

            # 使用 llc 编译
            result = subprocess.run(
                ['llc', '-O2', ll_file, '-o', obj_file],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                # 回退到 clang
                result = subprocess.run(
                    ['clang', '-O2', '-c', ll_file, '-o', obj_file],
                    capture_output=True, text=True, timeout=30
                )

            if result.returncode != 0:
                os.unlink(ll_file)
                return None

            # 链接为可执行文件
            result = subprocess.run(
                ['clang', obj_file, '-o', exe_file],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                os.unlink(ll_file)
                os.unlink(obj_file)
                return None

            # 加载共享库
            import ctypes
            lib = ctypes.CDLL(exe_file if os.path.exists(exe_file) else obj_file)
            func = getattr(lib, func_name, None)
            if func:
                self._cache[cache_key] = func
                # 清理临时文件
                for f in [ll_file, obj_file, exe_file]:
                    if os.path.exists(f):
                        os.unlink(f)
                return func

            os.unlink(ll_file)
            os.unlink(obj_file)
            return None

        except FileNotFoundError:
            # llc/clang 不可用，返回 None
            return None
        except Exception as e:
            return None

    def get_cached(self, cache_key: str) -> Optional[Callable]:
        return self._cache.get(cache_key)

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()


# ============================================================
# 热点追踪 JIT 编译器
# ============================================================

class LLVMHotJIT:
    """热点追踪 + LLVM JIT 编译。"""

    def __init__(self, threshold: int = 5) -> None:
        self._tracker = {}
        self._threshold = threshold
        self._compiler = LLVMCompiler()
        self._compiled: dict[str, Callable] = {}

    def record(self, name: str) -> None:
        self._tracker[name] = self._tracker.get(name, 0) + 1

    def should_compile(self, name: str) -> bool:
        return self._tracker.get(name, 0) >= self._threshold

    def compile_and_cache(self, name: str, llvm_ir: str) -> Optional[Callable]:
        if name in self._compiled:
            return self._compiled[name]
        func = self._compiler.compile(llvm_ir, name)
        if func:
            self._compiled[name] = func
        return func

    def get_compiled(self, name: str) -> Optional[Callable]:
        return self._compiled.get(name)

    @property
    def stats(self) -> dict:
        return {
            "tracked": len(self._tracker),
            "compiled": len(self._compiled),
            "compiler_cache": self._compiler.cache_size,
        }


# ============================================================
# 公共 API
# ============================================================

def matha_to_llvm_ir(ast_node: Any, module_name: str = "matha_module") -> str:
    """将 Matha AST 转换为 LLVM IR 文本。"""
    converter = MathaToIRConverter()
    ir_nodes = [converter.convert(ast_node)]
    generator = LLVMIRGenerator(module_name)
    return generator.generate(ir_nodes)


def compile_llvm_ir(llvm_ir: str, func_name: str = "main") -> Optional[Callable]:
    """编译 LLVM IR 为原生函数。"""
    compiler = LLVMCompiler()
    return compiler.compile(llvm_ir, func_name)


def create_hot_jit(threshold: int = 5) -> LLVMHotJIT:
    """创建热点追踪 JIT 编译器。"""
    return LLVMHotJIT(threshold)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "LLVMType", "LLVMValue",
    "MathaIRNode", "IRConstant", "IRVariable", "IRArithOp",
    "IRCompareOp", "IRLogicalOp", "IRFunctionCall",
    "IRVariableAccess", "IRAssignment", "IRIfExpr", "IRLoop", "IRFunctionDef",
    "MathaToIRConverter",
    "LLVMIRGenerator",
    "LLVMCompiler",
    "LLVMHotJIT",
    "matha_to_llvm_ir",
    "compile_llvm_ir",
    "create_hot_jit",
]
