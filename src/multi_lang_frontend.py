# -*- coding: utf-8 -*-
"""
多语言前端统一接口

为 Rust/Go/JavaScript/C 提供统一的源码解析 → Matha MIR 转换接口。

架构：
  ┌────────────────────────────────────────────────────────────────┐
  │                    MultiLanguageFrontend                      │
  │                                                                │
  │  register("rust", RustFrontend())                             │
  │  register("go",    GoFrontend())                              │
  │  register("js",    JSFrontend())                              │
  │  register("c",     CFrontend())                               │
  │  register("python",PythonFrontend())  # 已有                   │
  │                                                                │
  │  compile(source, language) → MIRProgram                        │
  │  infer_types(source, language) → dict                          │
  │  analyze_effects(source, language) → dict                      │
  └────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
import re
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# 尝试加载 tree-sitter 后端（无外部依赖的回退方案）
try:
    from src.tree_sitter_backends import (
        RustParser as _TS_Rust,
        GoParser as _TS_Go,
        JSParser as _TS_JS,
        CParser as _TS_C,
        get_parser as _ts_get_parser,
        _TS_AVAILABLE,
    )
    _USE_TS = True
except ImportError:
    _USE_TS = False

from src.mir import MIRProgram, MIRFunction, MIRInstrType, MIRConstInstr, MIRArithInstr
from src.mir import MIRCallInstr, MIRCompareInstr, MIRLogicalInstr, MIRLabelInstr
from src.mir import MIRCondBranchInstr, MIRReturnInstr, MIRInstr
from src.typesystem_v2_fixed import Type, T_INT, T_FLOAT, T_BOOL, T_STRING, T_ANY, ConstraintSolver


# ============================================================
# 统一 IR 节点（语言无关）
# ============================================================

class IRKind(Enum):
    """语言无关 IR 节点种类。"""
    # 值
    CONST = "const"
    VAR = "var"
    BINOP = "binop"
    UNARY = "unary"
    CALL = "call"
    COMPARE = "compare"
    LOGICAL = "logical"
    # 控制流
    LABEL = "label"
    JUMP = "jump"
    BRANCH = "branch"
    RETURN = "return"
    # 复合
    BLOCK = "block"
    FUNC = "func"
    LOOP = "loop"


@dataclass
class IRNode:
    """语言无关 IR 节点。"""
    kind: IRKind
    value: Any = None
    op: Optional[str] = None
    operands: list = field(default_factory=list)
    result: str = ""
    typ: Type = T_ANY
    children: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def with_type(self, typ: Type) -> "IRNode":
        """返回类型注解后的新节点。"""
        node = IRNode(self.kind, self.value, self.op, self.operands.copy(),
                      self.result, typ, self.children.copy(), self.metadata.copy())
        return node

    def __repr__(self) -> str:
        return f"IR({self.kind.name}, op={self.op}, typ={self.typ})"


# ============================================================
# 编译结果
# ============================================================

@dataclass
class CompileResult:
    """前端编译结果。"""
    language: str
    source: str
    ir_nodes: list[IRNode] = field(default_factory=list)
    functions: dict[str, list[IRNode]] = field(default_factory=dict)
    types: dict[str, Type] = field(default_factory=dict)
    effects: dict[str, str] = field(default_factory=dict)
    globals: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_mir(self) -> MIRProgram:
        """转换为 Matha MIR。"""
        program = MIRProgram()
        for name, body in self.functions.items():
            func = MIRFunction(name=name, params=[], return_type="double")
            for node in body:
                func.instructions.extend(_ir_to_mir(node))
            program.functions[name] = func
        return program


def _ir_to_mir(node: IRNode) -> list[MIRInstr]:
    """将 IR 节点转换为 MIR 指令。"""
    from src.mir import MIRConstInstr, MIRArithInstr, MIRCallInstr, MIRCompareInstr
    from src.mir import MIRLogicalInstr, MIRUnaryInstr, MIRReturnInstr

    if node.kind == IRKind.CONST:
        return [MIRConstInstr(node.result, MIRInstrType.ADD, [], {"value": float(node.value)})]

    if node.kind == IRKind.BINOP:
        ops = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "**": "POW", "%": "MOD"}
        instr_type = MIRInstrType.ADD
        for k, v in ops.items():
            if node.op == k:
                instr_type = getattr(MIRInstrType, v)
                break
        return [MIRArithInstr(node.result, instr_type, [str(op) for op in node.operands],
                            {"op": node.op})]

    if node.kind == IRKind.UNARY:
        return [MIRUnaryInstr(node.result, MIRInstrType.ADD,
                            [str(node.operands[0])], {"op": node.op})]

    if node.kind == IRKind.CALL:
        return [MIRCallInstr(node.result, MIRInstrType.CALL,
                            [str(op) for op in node.operands],
                            {"func_name": node.value, "c_func": node.value})]

    if node.kind == IRKind.COMPARE:
        return [MIRCompareInstr(node.result, MIRInstrType.ADD,
                               [str(op) for op in node.operands], {"op": node.op})]

    if node.kind == IRKind.LOGICAL:
        return [MIRLogicalInstr(node.result, MIRInstrType.ADD,
                               [str(op) for op in node.operands], {"op": node.op})]

    return []


# ============================================================
# Rust 前端
# ============================================================

class RustFrontend:
    """Rust → Matha IR 前端（基于正则解析，无需 rustc crate）。"""

    LANGUAGE = "rust"
    # Rust 类型映射
    TYPE_MAP = {
        "i32": T_INT, "i64": T_INT, "isize": T_INT,
        "u32": T_INT, "u64": T_INT, "usize": T_INT,
        "f32": T_FLOAT, "f64": T_FLOAT,
        "bool": T_BOOL, "String": T_STRING, "&str": T_STRING,
    }

    # Rust 标准库函数映射
    STD_MATH = {
        "sin": "sin", "cos": "cos", "tan": "tan",
        "sqrt": "sqrt", "exp": "exp", "log": "log",
        "log10": "log10", "abs": "fabs", "floor": "floor", "ceil": "ceil",
    }

    def compile(self, source: str) -> CompileResult:
        """编译 Rust 源码。"""
        result = CompileResult(language=self.LANGUAGE, source=source)

        # 提取函数定义
        func_pattern = re.compile(
            r'fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^{]+?))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.DOTALL
        )

        for match in func_pattern.finditer(source):
            name = match.group(1)
            params_str = match.group(2).strip()
            ret_type_str = (match.group(3) or "f64").strip()
            body = match.group(4)

            params, param_types = self._parse_params(params_str)
            return_type = self._resolve_type(ret_type_str)

            ir_body = self._parse_body(body, param_types)
            result.functions[name] = ir_body
            result.types[name] = return_type
            result.effects[name] = "Pure" if not self._has_io(body) else "IO"

        # 提取顶层表达式
        for line in source.split('\n'):
            line = line.strip().rstrip(';').strip()
            if not line or line.startswith('//') or line.startswith('fn ') or line.startswith('use '):
                continue
            if '=' in line and not line.startswith('#'):
                ir_nodes = self._parse_expr(line, {})
                if ir_nodes:
                    result.ir_nodes.extend(ir_nodes)

        return result

    def _parse_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        """解析参数列表。"""
        params = []
        types = {}
        if not params_str:
            return params, types
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            parts = param.split(':')
            if len(parts) == 2:
                name = parts[0].strip().lstrip('&').strip()
                typ = self._resolve_type(parts[1].strip())
                types[name] = typ
            else:
                name = param.strip().lstrip('&').strip()
                types[name] = T_INT
            params.append(name)
        return params, types

    def _resolve_type(self, type_str: str) -> Type:
        """解析 Rust 类型。"""
        type_str = type_str.strip()
        if type_str in self.TYPE_MAP:
            return self.TYPE_MAP[type_str]
        if type_str.startswith('Vec<'):
            return T_ANY  # 动态类型
        if type_str == 'Option<':
            return T_ANY
        if type_str in ('i32', 'i64', 'isize', 'u32', 'u64', 'usize', 'i8', 'i16'):
            return T_INT
        if type_str in ('f32', 'f64'):
            return T_FLOAT
        if type_str == 'bool':
            return T_BOOL
        if type_str in ('String', '&str', '&String'):
            return T_STRING
        return T_ANY

    def _parse_body(self, body: str, param_types: dict[str, Type]) -> list[IRNode]:
        """解析函数体。"""
        nodes: list[IRNode] = []
        var_counter = 0

        # 提取变量声明: let x: Type = expr;
        let_pattern = re.compile(r'let\s+(\w+)(?::\s*([^{]+?))?\s*=\s*([^;]+);')
        for match in let_pattern.finditer(body):
            var_name = match.group(1)
            var_type_str = (match.group(2) or "").strip()
            expr_str = match.group(3).strip()

            typ = self._resolve_type(var_type_str) if var_type_str else param_types.get(var_name, T_ANY)
            expr_nodes = self._parse_expr(expr_str, param_types)
            if expr_nodes:
                result_var = f"t{var_counter}"
                var_counter += 1
                nodes.append(IRNode(IRKind.CONST, value=0.0, result=result_var, typ=typ))
                nodes.extend(expr_nodes)
                nodes.append(IRNode(IRKind.VAR, value=var_name, result=result_var, typ=typ))
                param_types[var_name] = typ

        # 提取 return
        return_pattern = re.compile(r'return\s+([^;]+);')
        for match in return_pattern.finditer(body):
            expr_str = match.group(1).strip()
            expr_nodes = self._parse_expr(expr_str, param_types)
            nodes.extend(expr_nodes)
            if expr_nodes:
                nodes.append(IRNode(IRKind.RETURN, operands=[expr_nodes[-1].result]))

        # 提取 if/else
        if_pattern = re.compile(r'if\s*\(([^)]+)\)\s*\{([^}]*)\}(?:\s*else\s*\{([^}]*)\})?')
        for match in if_pattern.finditer(body):
            cond_str = match.group(1)
            then_body = match.group(2)
            else_body = match.group(3) or ""

            cond_nodes = self._parse_expr(cond_str, param_types)
            then_nodes = self._parse_body(then_body, param_types) if then_body.strip() else []
            else_nodes = self._parse_body(else_body, param_types) if else_body.strip() else []

            nodes.append(IRNode(IRKind.BRANCH, operands=[cond_nodes[-1].result if cond_nodes else "0"],
                              children=[then_nodes, else_nodes]))

        # 提取 for 循环
        for_pattern = re.compile(r'for\s+(\w+)\s+in\s+([^{\n]+)\s*\{([^}]*)\}')
        for match in for_pattern.finditer(body):
            loop_var = match.group(1)
            iterable = match.group(2).strip()
            loop_body = match.group(3)

            param_types[loop_var] = T_INT
            loop_nodes = self._parse_body(loop_body, param_types)
            nodes.append(IRNode(IRKind.LOOP, value=iterable, children=[loop_nodes]))

        # 提取独立表达式（包括隐式 return）
        expr_lines = re.findall(r'^\s*([a-zA-Z_]\w*\s*[+\-*/%^<>=!&|]+[^;]*);?', body, re.MULTILINE)
        for expr_str in expr_lines:
            expr_str = expr_str.strip()
            if not expr_str or expr_str.startswith('let ') or expr_str.startswith('return '):
                continue
            expr_nodes = self._parse_expr(expr_str, param_types)
            nodes.extend(expr_nodes)
            # 最后一个表达式作为隐式 return
            if expr_nodes and not any(n.kind == IRKind.RETURN for n in nodes):
                nodes.append(IRNode(IRKind.RETURN, operands=[expr_nodes[-1].result]))

        return nodes

    def _parse_expr(self, expr_str: str, param_types: dict[str, Type]) -> list[IRNode]:
        """解析表达式。"""
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()

        # 函数调用
        call_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)

            if func_name in ('if', 'for', 'while', 'let', 'return'):
                continue

            # 数学函数映射
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"

            # 解析参数
            arg_nodes = []
            if args_str.strip():
                for arg in args_str.split(','):
                    arg_nodes.extend(self._parse_atom(arg.strip(), param_types))

            nodes.append(IRNode(IRKind.CALL, value=math_func, operands=arg_nodes,
                              result=result_var, typ=T_FLOAT if func_name in self.STD_MATH else T_ANY))
            return nodes

        # 二元运算
        for op in ['**', '//', '%', '+=', '-=', '*=', '/=', '==', '!=', '<=', '>=', '&&', '||', '<<', '>>']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_atom(parts[0].strip(), param_types)
                    right = self._parse_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op, operands=[left[-1].result if left else "0",
                                                                       right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 一元运算
        for op in ['-', '+', '!']:
            if expr_str.startswith(op):
                operand = self._parse_atom(expr_str[1:].strip(), param_types)
                result_var = f"t{len(nodes)}"
                nodes.extend(operand)
                nodes.append(IRNode(IRKind.UNARY, op=op, operands=[operand[-1].result if operand else "0"],
                                  result=result_var))
                return nodes

        # 常量
        for atom in self._tokenize_expr(expr_str):
            nodes.extend(self._parse_atom(atom, param_types))
        return nodes

    def _parse_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        """解析原子表达式。"""
        atom = atom.strip()
        if not atom:
            return []

        # 数字常量
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result=f"t{hash(atom) & 0xFFFF}", typ=T_FLOAT)]
        except ValueError:
            pass

        # 布尔常量
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]

        # 变量引用
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_ANY)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]

        return []

    def _tokenize_expr(self, expr: str) -> list[str]:
        """表达式分词。"""
        return re.findall(r'[a-zA-Z_]\w*|[\d.]+|[-+*/%^=!<>]', expr)

    def _has_io(self, body: str) -> bool:
        """检测是否有 IO 操作。"""
        io_keywords = ['println!', 'print!', 'eprintln!', 'panic!', 'read!']
        return any(kw in body for kw in io_keywords)

    def infer_types(self, source: str) -> dict[str, Type]:
        """类型推断。"""
        result = self.compile(source)
        types = result.types.copy()
        # 从参数推断
        func_pattern = re.compile(r'fn\s+(\w+)\s*\(([^)]*)\)')
        for match in func_pattern.finditer(source):
            params_str = match.group(2)
            for param in params_str.split(','):
                param = param.strip()
                if ':' in param:
                    name, typ_str = param.split(':', 1)
                    types[name.strip()] = self._resolve_type(typ_str.strip())
        return types

    def analyze_effects(self, source: str) -> dict[str, str]:
        """效应分析。"""
        result = self.compile(source)
        return result.effects


# ============================================================
# Go 前端
# ============================================================

class GoFrontend:
    """Go → Matha IR 前端。"""

    LANGUAGE = "go"
    TYPE_MAP = {
        "int": T_INT, "int32": T_INT, "int64": T_INT, "uint": T_INT, "uint64": T_INT,
        "float32": T_FLOAT, "float64": T_FLOAT,
        "bool": T_BOOL, "string": T_STRING,
        "rune": T_INT,
    }
    STD_MATH = {"sin": "sin", "cos": "cos", "tan": "tan", "sqrt": "sqrt",
                "exp": "exp", "log": "log", "log10": "log10", "abs": "fabs"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)

        # 函数定义
        func_pattern = re.compile(
            r'func\s+(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|([^{]+))?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.DOTALL
        )
        for match in func_pattern.finditer(source):
            name = match.group(1)
            params_str = match.group(2).strip()
            ret_types = (match.group(3) or match.group(4) or "float64").strip()
            body = match.group(5)

            params, param_types = self._parse_params(params_str)
            return_type = self._resolve_type(ret_types)

            ir_body = self._parse_body(body, param_types)
            result.functions[name] = ir_body
            result.types[name] = return_type
            result.effects[name] = "Pure" if not self._has_io(body) else "IO"

        # 回退：检测 Python 风格 def 函数并生成等效 IR
        if not result.functions:
            py_func_pattern = re.compile(
                r'def\s+(\w+)\s*\(([^)]*)\)\s*:\s*return\s+(.+)',
                re.DOTALL
            )
            for match in py_func_pattern.finditer(source):
                name = match.group(1)
                params_str = match.group(2).strip()
                ret_expr = match.group(3).strip()
                params, param_types = self._parse_py_params(params_str)
                ir_body = self._parse_py_return(ret_expr, param_types)
                result.functions[name] = ir_body
                result.types[name] = T_FLOAT
                for p in params:
                    result.types[p] = T_FLOAT
                result.effects[name] = "Pure"

            # 顶层表达式
            for line in source.split('\n'):
                line = line.strip().rstrip('#').strip()
                if not line or line.startswith('def ') or line.startswith('#'):
                    continue
                if '=' in line and '=>' not in line:
                    expr_nodes = self._parse_py_expr(line)
                    if expr_nodes:
                        result.ir_nodes.extend(expr_nodes)

        return result

    def _parse_py_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        """解析 Python 风格参数。"""
        params, types = [], {}
        if not params_str:
            return params, types
        for param in params_str.split(','):
            param = param.strip()
            if param and param != 'self':
                params.append(param)
                types[param] = T_FLOAT
        return params, types

    def _parse_py_return(self, ret_expr: str, param_types: dict[str, Type]) -> list[IRNode]:
        """从 Python return 表达式生成 IR 节点。"""
        nodes: list[IRNode] = []
        expr_nodes = self._parse_py_expr(ret_expr, param_types)
        nodes.extend(expr_nodes)
        if expr_nodes:
            nodes.append(IRNode(IRKind.RETURN, operands=[expr_nodes[-1].result]))
        return nodes

    def _parse_py_expr(self, expr_str: str, param_types: Optional[dict[str, Type]] = None) -> list[IRNode]:
        """解析 Python 风格表达式生成 IR。"""
        if param_types is None:
            param_types = {}
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()
        if not expr_str:
            return nodes

        # 函数调用
        call_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)
            if func_name in ('if', 'for', 'while', 'return', 'def'):
                continue
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"
            arg_nodes = [self._parse_py_atom(a.strip(), param_types) for a in args_str.split(',') if a.strip()]
            arg_flat = [n for ans in arg_nodes for n in ans]
            nodes.append(IRNode(IRKind.CALL, value=math_func,
                              operands=[n.result for n in arg_flat],
                              result=result_var, typ=T_FLOAT))
            nodes.extend(arg_flat)
            return nodes

        # 二元运算
        for op in ['**', '%', '==', '!=', '<=', '>=', '&&', '||']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_py_atom(parts[0].strip(), param_types)
                    right = self._parse_py_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op,
                                      operands=[left[-1].result if left else "0",
                                               right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 一元运算
        for op in ['-', '+', '!']:
            if expr_str.startswith(op):
                operand = self._parse_py_atom(expr_str[1:].strip(), param_types)
                result_var = f"t{len(nodes)}"
                nodes.extend(operand)
                nodes.append(IRNode(IRKind.UNARY, op=op,
                                  operands=[operand[-1].result if operand else "0"],
                                  result=result_var))
                return nodes

        # 原子
        for atom in re.findall(r'[a-zA-Z_]\w*|[\d.]+', expr_str):
            nodes.extend(self._parse_py_atom(atom, param_types))
        return nodes

    def _parse_py_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        atom = atom.strip()
        if not atom:
            return []
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result="t0", typ=T_FLOAT)]
        except ValueError:
            pass
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_FLOAT)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]
        return []

    def _parse_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        params, types = [], {}
        if not params_str:
            return params, types
        # Go: "a int, b float64" 或 "a, b int"
        grouped: dict[str, list[str]] = {}
        for part in params_str.split(','):
            part = part.strip()
            if not part:
                continue
            words = part.split()
            if len(words) >= 2:
                for w in words[:-1]:
                    if w and not w.startswith('*') and not w.startswith('&'):
                        grouped.setdefault(words[-1], []).append(w)
            elif len(words) == 1 and words[0] not in ('int', 'float64', 'string', 'bool'):
                grouped["int"].append(words[0])
        for typ_str, names in grouped.items():
            typ = self._resolve_type(typ_str)
            for name in names:
                params.append(name)
                types[name] = typ
        return params, types

    def _resolve_type(self, type_str: str) -> Type:
        type_str = type_str.strip().lstrip('*').lstrip('&').strip()
        if type_str in self.TYPE_MAP:
            return self.TYPE_MAP[type_str]
        if type_str.startswith('[]'):
            return T_ANY
        return T_ANY

    def _parse_body(self, body: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        var_counter = 0

        # var 声明
        var_pattern = re.compile(r'var\s+(\w+)\s*(:\s*([a-zA-Z<>[\]| ]+))?\s*=\s*([^;]+);?')
        for match in var_pattern.finditer(body):
            var_name = match.group(1)
            typ_str = (match.group(3) or "").strip()
            expr_str = match.group(4).strip()
            typ = self._resolve_type(typ_str) if typ_str else param_types.get(var_name, T_ANY)
            expr_nodes = self._parse_expr(expr_str, param_types)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=result_var, typ=typ))
            nodes.extend(expr_nodes)
            param_types[var_name] = typ

        # 赋值
        assign_pattern = re.compile(r'(\w+)\s*=\s*([^;{}]+);?')
        for match in assign_pattern.finditer(body):
            var_name = match.group(1)
            expr_str = match.group(2).strip()
            if var_name in ('if', 'for', 'range', 'var', 'func', 'return'):
                continue
            expr_nodes = self._parse_expr(expr_str, param_types)
            typ = param_types.get(var_name, T_ANY)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=var_name, typ=typ))
            nodes.extend(expr_nodes)

        # return
        for match in re.finditer(r'return\s+([^;]+);', body):
            expr_str = match.group(1).strip()
            expr_nodes = self._parse_expr(expr_str, param_types)
            nodes.extend(expr_nodes)

        # if
        for match in re.finditer(r'if\s*\(([^)]+)\)\s*\{([^}]*)\}', body):
            cond = self._parse_expr(match.group(1), param_types)
            then_body = self._parse_body(match.group(2), param_types)
            nodes.append(IRNode(IRKind.BRANCH, operands=[cond[-1].result if cond else "0"],
                              children=[then_body]))

        return nodes

    def _parse_expr(self, expr_str: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()
        if not expr_str:
            return nodes

        # 函数调用
        call_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)
            if func_name in ('if', 'for', 'range', 'var', 'func', 'return', 'make', 'len', 'cap', 'append'):
                continue
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"
            arg_nodes = [self._parse_atom(a.strip(), param_types) for a in args_str.split(',') if a.strip()]
            arg_flat = [n for ans in arg_nodes for n in ans]
            nodes.append(IRNode(IRKind.CALL, value=math_func, operands=[n.result for n in arg_flat],
                              result=result_var, typ=T_FLOAT))
            nodes.extend(arg_flat)
            return nodes

        # 运算符
        for op in ['**', '//', '%', '+=', '-=', '==', '!=', '<=', '>=', '&&', '||']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_atom(parts[0].strip(), param_types)
                    right = self._parse_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op,
                                      operands=[left[-1].result if left else "0",
                                               right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 原子
        for atom in self._tokenize_expr(expr_str):
            nodes.extend(self._parse_atom(atom, param_types))
        return nodes

    def _parse_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        atom = atom.strip()
        if not atom:
            return []
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result="t0", typ=T_FLOAT)]
        except ValueError:
            pass
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_ANY)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]
        return []

    def _tokenize_expr(self, expr: str) -> list[str]:
        return re.findall(r'[a-zA-Z_]\w*|[\d.]+|[-+*/%^=!<>]', expr)

    def _has_io(self, body: str) -> bool:
        return any(kw in body for kw in ['fmt.Println', 'fmt.Print', 'fmt.Sprintf', 'panic', 'log.'])

    def infer_types(self, source: str) -> dict[str, Type]:
        result = self.compile(source)
        types = result.types.copy()
        var_pattern = re.compile(r'var\s+(\w+)\s*:\s*([a-zA-Z<>[\]| ]+)')
        for match in var_pattern.finditer(source):
            types[match.group(1)] = self._resolve_type(match.group(2).strip())
        return types

    def analyze_effects(self, source: str) -> dict[str, str]:
        result = self.compile(source)
        return result.effects


# ============================================================
# JavaScript 前端
# ============================================================

class JSFrontend:
    """JavaScript → Matha IR 前端。"""

    LANGUAGE = "javascript"
    TYPE_MAP = {
        "number": T_FLOAT, "float": T_FLOAT, "double": T_FLOAT,
        "int": T_INT, "integer": T_INT,
        "bool": T_BOOL, "boolean": T_BOOL,
        "string": T_STRING,
        "void": T_ANY, "any": T_ANY,
    }
    STD_MATH = {"Math.sin": "sin", "Math.cos": "cos", "Math.tan": "tan",
                "Math.sqrt": "sqrt", "Math.exp": "exp", "Math.log": "log",
                "Math.log10": "log10", "Math.abs": "fabs",
                "Math.floor": "floor", "Math.ceil": "ceil",
                "Math.pow": "pow", "Math.round": "round",
                "sin": "sin", "cos": "cos", "sqrt": "sqrt", "exp": "exp", "log": "log"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)

        # 函数定义: function name(params) { body } 或 const name = (params) => body
        func_patterns = [
            re.compile(r'function\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL),
            re.compile(r'const\s+(\w+)\s*=\s*\(([^)]*)\)\s*=>\s*([^;{]+)', re.DOTALL),
            re.compile(r'const\s+(\w+)\s*=\s*function\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', re.DOTALL),
        ]
        for pattern in func_patterns:
            for match in pattern.finditer(source):
                name = match.group(1)
                params_str = (match.group(2) or "").strip()
                body = match.group(3) or ""

                params, param_types = self._parse_params(params_str)
                ir_body = self._parse_body(body, param_types)
                result.functions[name] = ir_body
                result.types[name] = T_FLOAT

        # 顶层表达式
        for line in source.split('\n'):
            line = line.strip().rstrip(';').strip()
            if not line or line.startswith('//') or line.startswith('/*') or line.startswith('const '):
                continue
            if '=' in line and not line.startswith('if') and not line.startswith('for'):
                expr_nodes = self._parse_expr(line, {})
                if expr_nodes:
                    result.ir_nodes.extend(expr_nodes)

        return result

    def _parse_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        params, types = [], {}
        if not params_str:
            return params, types
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            parts = param.split(':')
            name = parts[0].strip()
            typ = self._resolve_type(parts[1].strip()) if len(parts) > 1 else T_FLOAT
            params.append(name)
            types[name] = typ
        return params, types

    def _resolve_type(self, type_str: str) -> Type:
        type_str = type_str.strip().lower()
        if type_str in self.TYPE_MAP:
            return self.TYPE_MAP[type_str]
        return T_ANY

    def _parse_body(self, body: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        var_counter = 0

        # const/let 声明
        decl_pattern = re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*([^;]+);')
        for match in decl_pattern.finditer(body):
            var_name = match.group(1)
            expr_str = match.group(2).strip()
            typ = param_types.get(var_name, T_FLOAT)
            expr_nodes = self._parse_expr(expr_str, param_types)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=result_var, typ=typ))
            nodes.extend(expr_nodes)
            param_types[var_name] = typ

        # 赋值
        assign_pattern = re.compile(r'(\w+)\s*=\s*([^;{}]+);')
        for match in assign_pattern.finditer(body):
            var_name = match.group(1)
            expr_str = match.group(2).strip()
            if var_name in ('if', 'for', 'while', 'const', 'let', 'var', 'return'):
                continue
            expr_nodes = self._parse_expr(expr_str, param_types)
            typ = param_types.get(var_name, T_FLOAT)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=var_name, typ=typ))
            nodes.extend(expr_nodes)

        # return
        for match in re.finditer(r'return\s+([^;]+);', body):
            expr_nodes = self._parse_expr(match.group(1).strip(), param_types)
            nodes.extend(expr_nodes)

        # if
        for match in re.finditer(r'if\s*\(([^)]+)\)\s*\{([^}]*)\}', body):
            cond = self._parse_expr(match.group(1), param_types)
            then_body = self._parse_body(match.group(2), param_types)
            nodes.append(IRNode(IRKind.BRANCH, operands=[cond[-1].result if cond else "0"],
                              children=[then_body]))

        # for
        for match in re.finditer(r'for\s*\(\s*([^;]*);[^;]*;[^)]*\)\s*\{([^}]*)\}', body):
            init = match.group(1)
            loop_body = match.group(2)
            if init:
                init_nodes = self._parse_expr(init.strip(), param_types)
                nodes.extend(init_nodes)
            loop_nodes = self._parse_body(loop_body, param_types)
            nodes.append(IRNode(IRKind.LOOP, children=[loop_nodes]))

        return nodes

    def _parse_expr(self, expr_str: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()
        if not expr_str:
            return nodes

        # 函数调用
        call_pattern = re.compile(r'(\w+(?:\.\w+)?)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)
            if func_name in ('if', 'for', 'while', 'console', 'document'):
                continue
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"
            arg_nodes = [self._parse_atom(a.strip(), param_types) for a in args_str.split(',') if a.strip()]
            arg_flat = [n for ans in arg_nodes for n in ans]
            nodes.append(IRNode(IRKind.CALL, value=math_func,
                              operands=[n.result for n in arg_flat],
                              result=result_var, typ=T_FLOAT))
            nodes.extend(arg_flat)
            return nodes

        # 运算符
        for op in ['**', '//', '%', '==', '!=', '<=', '>=', '&&', '||']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_atom(parts[0].strip(), param_types)
                    right = self._parse_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op,
                                      operands=[left[-1].result if left else "0",
                                               right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 一元运算
        for op in ['-', '+', '!']:
            if expr_str.startswith(op):
                operand = self._parse_atom(expr_str[1:].strip(), param_types)
                result_var = f"t{len(nodes)}"
                nodes.extend(operand)
                nodes.append(IRNode(IRKind.UNARY, op=op,
                                  operands=[operand[-1].result if operand else "0"],
                                  result=result_var))
                return nodes

        # 三元表达式
        if '?' in expr_str and ':' in expr_str:
            parts = expr_str.split('?', 1)
            if ':' in parts[1]:
                cond_parts = parts[1].split(':', 1)
                cond = self._parse_atom(parts[0].strip(), param_types)
                then_expr = self._parse_expr(cond_parts[0].strip(), param_types)
                else_expr = self._parse_expr(cond_parts[1].strip(), param_types)
                nodes.extend(cond + then_expr + else_expr)
                return nodes

        # 原子
        for atom in self._tokenize_expr(expr_str):
            nodes.extend(self._parse_atom(atom, param_types))
        return nodes

    def _parse_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        atom = atom.strip()
        if not atom:
            return []
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result="t0", typ=T_FLOAT)]
        except ValueError:
            pass
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_FLOAT)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]
        return []

    def _tokenize_expr(self, expr: str) -> list[str]:
        return re.findall(r'[a-zA-Z_]\w*|[\d.]+|[-+*/%^=!<>]', expr)

    def infer_types(self, source: str) -> dict[str, Type]:
        result = self.compile(source)
        return result.types

    def analyze_effects(self, source: str) -> dict[str, str]:
        effects = {}
        for name in self.compile(source).functions:
            effects[name] = "IO" if "console." in source else "Pure"
        return effects


# ============================================================
# C 前端
# ================================================= ============================================================

class CFrontend:
    """C → Matha IR 前端。"""

    LANGUAGE = "c"
    TYPE_MAP = {
        "int": T_INT, "long": T_INT, "long long": T_INT,
        "float": T_FLOAT, "double": T_FLOAT,
        "char": T_INT, "short": T_INT,
        "unsigned int": T_INT, "unsigned long": T_INT,
    }
    STD_MATH = {"sin": "sin", "cos": "cos", "tan": "tan", "sqrt": "sqrt",
                "exp": "exp", "log": "log", "fabs": "fabs",
                "floor": "floor", "ceil": "ceil", "pow": "pow"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)

        # 函数定义: return_type name(params) { body }
        func_pattern = re.compile(
            r'([a-zA-Z_]\w*)\s+(\w+)\s*\(([^)]*)\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.DOTALL
        )
        for match in func_pattern.finditer(source):
            ret_type = match.group(1).strip()
            name = match.group(2).strip()
            params_str = match.group(3).strip()
            body = match.group(4)

            params, param_types = self._parse_params(params_str)
            return_type = self._resolve_type(ret_type)

            ir_body = self._parse_body(body, param_types)
            result.functions[name] = ir_body
            result.types[name] = return_type
            result.effects[name] = "Pure" if not self._has_io(body) else "IO"

        # 回退：检测 Python 风格 def 函数并生成等效 IR
        if not result.functions:
            py_func_pattern = re.compile(
                r'def\s+(\w+)\s*\(([^)]*)\)\s*:\s*return\s+(.+)',
                re.DOTALL
            )
            for match in py_func_pattern.finditer(source):
                name = match.group(1)
                params_str = match.group(2).strip()
                ret_expr = match.group(3).strip()
                params, param_types = self._parse_py_params(params_str)
                ir_body = self._parse_py_return(ret_expr, param_types)
                result.functions[name] = ir_body
                result.types[name] = T_FLOAT
                for p in params:
                    result.types[p] = T_FLOAT
                result.effects[name] = "Pure"

            # 顶层表达式
            for line in source.split('\n'):
                line = line.strip().rstrip('#').strip()
                if not line or line.startswith('def ') or line.startswith('#'):
                    continue
                if '=' in line and '=>' not in line:
                    expr_nodes = self._parse_py_expr(line)
                    if expr_nodes:
                        result.ir_nodes.extend(expr_nodes)

        return result

    def _parse_py_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        """解析 Python 风格参数。"""
        params, types = [], {}
        if not params_str:
            return params, types
        for param in params_str.split(','):
            param = param.strip()
            if param and param != 'self':
                params.append(param)
                types[param] = T_FLOAT
        return params, types

    def _parse_py_return(self, ret_expr: str, param_types: dict[str, Type]) -> list[IRNode]:
        """从 Python return 表达式生成 IR 节点。"""
        nodes: list[IRNode] = []
        expr_nodes = self._parse_py_expr(ret_expr, param_types)
        nodes.extend(expr_nodes)
        if expr_nodes:
            nodes.append(IRNode(IRKind.RETURN, operands=[expr_nodes[-1].result]))
        return nodes

    def _parse_py_expr(self, expr_str: str, param_types: Optional[dict[str, Type]] = None) -> list[IRNode]:
        """解析 Python 风格表达式生成 IR。"""
        if param_types is None:
            param_types = {}
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()
        if not expr_str:
            return nodes

        # 函数调用
        call_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)
            if func_name in ('if', 'for', 'while', 'return', 'def'):
                continue
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"
            arg_nodes = [self._parse_py_atom(a.strip(), param_types) for a in args_str.split(',') if a.strip()]
            arg_flat = [n for ans in arg_nodes for n in ans]
            nodes.append(IRNode(IRKind.CALL, value=math_func,
                              operands=[n.result for n in arg_flat],
                              result=result_var, typ=T_FLOAT))
            nodes.extend(arg_flat)
            return nodes

        # 二元运算
        for op in ['**', '%', '==', '!=', '<=', '>=', '&&', '||']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_py_atom(parts[0].strip(), param_types)
                    right = self._parse_py_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op,
                                      operands=[left[-1].result if left else "0",
                                               right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 一元运算
        for op in ['-', '+', '!']:
            if expr_str.startswith(op):
                operand = self._parse_py_atom(expr_str[1:].strip(), param_types)
                result_var = f"t{len(nodes)}"
                nodes.extend(operand)
                nodes.append(IRNode(IRKind.UNARY, op=op,
                                  operands=[operand[-1].result if operand else "0"],
                                  result=result_var))
                return nodes

        # 原子
        for atom in re.findall(r'[a-zA-Z_]\w*|[\d.]+', expr_str):
            nodes.extend(self._parse_py_atom(atom, param_types))
        return nodes

    def _parse_py_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        atom = atom.strip()
        if not atom:
            return []
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result="t0", typ=T_FLOAT)]
        except ValueError:
            pass
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_FLOAT)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]
        return []

    def _parse_params(self, params_str: str) -> tuple[list[str], dict[str, Type]]:
        params, types = [], {}
        if not params_str or params_str == 'void':
            return params, types
        # C: "int a, float b, double c"
        # 按逗号分割，每个参数可能有多词类型
        parts = []
        current = ""
        depth = 0
        for ch in params_str:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                parts.append(current.strip())
                current = ""
                continue
            current += ch
        if current.strip():
            parts.append(current.strip())

        for part in parts:
            words = part.split()
            if not words:
                continue
            # 最后一个是参数名，前面是类型
            name = words[-1].lstrip('*').lstrip('&').strip()
            type_words = ' '.join(words[:-1]) if len(words) > 1 else "int"
            typ = self._resolve_type(type_words)
            params.append(name)
            types[name] = typ
        return params, types

    def _resolve_type(self, type_str: str) -> Type:
        type_str = type_str.strip().lstrip('*').lstrip('&').strip()
        if type_str in self.TYPE_MAP:
            return self.TYPE_MAP[type_str]
        if type_str.startswith('unsigned'):
            return T_INT
        return T_INT

    def _parse_body(self, body: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        var_counter = 0

        # 变量声明 + 初始化: type name = expr;
        decl_pattern = re.compile(r'(?:int|float|double|long|unsigned|char)\s+(\w+)\s*=\s*([^;]+);')
        for match in decl_pattern.finditer(body):
            var_name = match.group(1)
            expr_str = match.group(2).strip()
            typ = T_FLOAT if any(kw in match.group(0) for kw in ('float', 'double')) else T_INT
            expr_nodes = self._parse_expr(expr_str, param_types)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=result_var, typ=typ))
            nodes.extend(expr_nodes)
            param_types[var_name] = typ

        # 赋值: name = expr;
        assign_pattern = re.compile(r'(\w+)\s*=\s*([^;{}]+);')
        for match in assign_pattern.finditer(body):
            var_name = match.group(1)
            expr_str = match.group(2).strip()
            if var_name in ('if', 'for', 'while', 'return'):
                continue
            expr_nodes = self._parse_expr(expr_str, param_types)
            typ = param_types.get(var_name, T_FLOAT)
            result_var = f"t{var_counter}"
            var_counter += 1
            nodes.append(IRNode(IRKind.VAR, value=var_name, result=var_name, typ=typ))
            nodes.extend(expr_nodes)

        # return
        for match in re.finditer(r'return\s+([^;]+);', body):
            expr_nodes = self._parse_expr(match.group(1).strip(), param_types)
            nodes.extend(expr_nodes)

        # if
        for match in re.finditer(r'if\s*\(([^)]+)\)\s*\{([^}]*)\}', body):
            cond = self._parse_expr(match.group(1), param_types)
            then_body = self._parse_body(match.group(2), param_types)
            nodes.append(IRNode(IRKind.BRANCH, operands=[cond[-1].result if cond else "0"],
                              children=[then_body]))

        return nodes

    def _parse_expr(self, expr_str: str, param_types: dict[str, Type]) -> list[IRNode]:
        nodes: list[IRNode] = []
        expr_str = expr_str.strip()
        if not expr_str:
            return nodes

        # 函数调用
        call_pattern = re.compile(r'(\w+)\s*\(([^)]*)\)')
        for match in call_pattern.finditer(expr_str):
            func_name = match.group(1)
            args_str = match.group(2)
            if func_name in ('if', 'for', 'while', 'return'):
                continue
            math_func = self.STD_MATH.get(func_name, func_name)
            result_var = f"t{len(nodes)}"
            arg_nodes = [self._parse_atom(a.strip(), param_types) for a in args_str.split(',') if a.strip()]
            arg_flat = [n for ans in arg_nodes for n in ans]
            nodes.append(IRNode(IRKind.CALL, value=math_func,
                              operands=[n.result for n in arg_flat],
                              result=result_var, typ=T_FLOAT))
            nodes.extend(arg_flat)
            return nodes

        # 运算符
        for op in ['**', '%', '==', '!=', '<=', '>=', '&&', '||']:
            if op in expr_str:
                parts = expr_str.split(op, 1)
                if len(parts) == 2:
                    left = self._parse_atom(parts[0].strip(), param_types)
                    right = self._parse_atom(parts[1].strip(), param_types)
                    result_var = f"t{len(nodes)}"
                    nodes.extend(left + right)
                    nodes.append(IRNode(IRKind.BINOP, op=op,
                                      operands=[left[-1].result if left else "0",
                                               right[-1].result if right else "0"],
                                      result=result_var))
                    return nodes

        # 一元运算
        for op in ['-', '+', '!']:
            if expr_str.startswith(op):
                operand = self._parse_atom(expr_str[1:].strip(), param_types)
                result_var = f"t{len(nodes)}"
                nodes.extend(operand)
                nodes.append(IRNode(IRKind.UNARY, op=op,
                                  operands=[operand[-1].result if operand else "0"],
                                  result=result_var))
                return nodes

        # 原子
        for atom in self._tokenize_expr(expr_str):
            nodes.extend(self._parse_atom(atom, param_types))
        return nodes

    def _parse_atom(self, atom: str, param_types: dict[str, Type]) -> list[IRNode]:
        atom = atom.strip()
        if not atom:
            return []
        try:
            val = float(atom)
            return [IRNode(IRKind.CONST, value=val, result="t0", typ=T_FLOAT)]
        except ValueError:
            pass
        if atom == 'true':
            return [IRNode(IRKind.CONST, value=1.0, result="t0", typ=T_BOOL)]
        if atom == 'false':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_BOOL)]
        if atom == 'NULL' or atom == 'null':
            return [IRNode(IRKind.CONST, value=0.0, result="t0", typ=T_INT)]
        if re.match(r'^[a-zA-Z_]\w*$', atom):
            typ = param_types.get(atom, T_INT)
            return [IRNode(IRKind.VAR, value=atom, result=atom, typ=typ)]
        return []

    def _tokenize_expr(self, expr: str) -> list[str]:
        return re.findall(r'[a-zA-Z_]\w*|[\d.]+|[-+*/%^=!<>]', expr)

    def _has_io(self, body: str) -> bool:
        return any(kw in body for kw in ('printf', 'scanf', 'fprintf', 'fscanf'))

    def infer_types(self, source: str) -> dict[str, Type]:
        result = self.compile(source)
        types = result.types.copy()
        # 从参数声明推断
        param_pattern = re.compile(r'(int|float|double|long|unsigned|char)\s+(\w+)')
        for match in param_pattern.finditer(source):
            types[match.group(2)] = self._resolve_type(match.group(1))
        return types

    def analyze_effects(self, source: str) -> dict[str, str]:
        result = self.compile(source)
        return result.effects


# ============================================================
# 统一多语言前端
# ============================================================

class MultiLanguageFrontend:
    """多语言前端统一入口。"""

    def __init__(self):
        self._frontends: dict[str, Any] = {}

    def register(self, language: str, frontend: Any) -> None:
        """注册语言前端。"""
        self._frontends[language.lower()] = frontend

    def compile(self, source: str, language: str = "python") -> CompileResult:
        """编译源码为 IR。"""
        frontend = self._frontends.get(language.lower())
        if frontend is None:
            raise ValueError(f"不支持的语言前端: {language}。"
                           f"支持: {list(self._frontends.keys())}")
        return frontend.compile(source)

    def infer_types(self, source: str, language: str = "python") -> dict[str, Type]:
        """类型推断。"""
        frontend = self._frontends.get(language.lower())
        if frontend is None:
            raise ValueError(f"不支持的语言: {language}")
        return frontend.infer_types(source)

    def analyze_effects(self, source: str, language: str = "python") -> dict[str, str]:
        """效应分析。"""
        frontend = self._frontends.get(language.lower())
        if frontend is None:
            raise ValueError(f"不支持的语言: {language}")
        return frontend.analyze_effects(source)

    def supported_languages(self) -> list[str]:
        """返回支持的语言列表。"""
        return list(self._frontends.keys())

    def to_mir(self, result: CompileResult) -> MIRProgram:
        """将编译结果转换为 MIR。"""
        return result.to_mir()


# ============================================================
# 初始化注册
# ============================================================

# ── tree-sitter 适配器（替代 Regex 前端）─────────────────────────

class _TS_RustAdapter:
    """Rust tree-sitter 适配器。"""
    LANGUAGE = "rust"
    STD_MATH = {"sin": "sin", "cos": "cos", "tan": "tan", "sqrt": "sqrt",
                "exp": "exp", "log": "log", "log10": "log10", "abs": "fabs",
                "floor": "floor", "ceil": "ceil"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)
        try:
            parser = _TS_Rust()
            tree = parser.parse(source)
            for fn in tree.children:
                if fn.type in ("rust_function",):
                    name = fn.value
                    result.functions[name] = []
                    result.types[name] = T_FLOAT
                    result.effects[name] = "Pure"
        except Exception as e:
            result.errors.append(f"Rust compile error: {e}")
        return result

    def infer_types(self, source: str) -> dict[str, Type]:
        result = self.compile(source)
        return result.types

    def analyze_effects(self, source: str) -> dict[str, str]:
        result = self.compile(source)
        return result.effects


class _TS_GoAdapter:
    """Go tree-sitter 适配器。"""
    LANGUAGE = "go"
    STD_MATH = {"sin": "sin", "cos": "cos", "tan": "tan", "sqrt": "sqrt",
                "exp": "exp", "log": "log", "log10": "log10", "abs": "fabs"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)
        try:
            parser = _TS_Go()
            tree = parser.parse(source)
            for fn in tree.children:
                if fn.type in ("go_function",):
                    name = fn.value
                    result.functions[name] = []
                    result.types[name] = T_FLOAT
                    result.effects[name] = "Pure"
        except Exception as e:
            result.errors.append(f"Go compile error: {e}")
        return result

    def infer_types(self, source: str) -> dict[str, Type]:
        return self.compile(source).types

    def analyze_effects(self, source: str) -> dict[str, str]:
        return self.compile(source).effects


class _TS_JSAdapter:
    """JS tree-sitter 适配器。"""
    LANGUAGE = "javascript"

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)
        try:
            parser = _TS_JS()
            tree = parser.parse(source)
            for child in tree.children:
                if child.type == "js_function":
                    name = child.value
                    result.functions[name] = []
                    result.types[name] = T_FLOAT
                elif child.type == "js_stmt":
                    result.ir_nodes.extend([child])
        except Exception as e:
            result.errors.append(f"JS compile error: {e}")
        return result

    def infer_types(self, source: str) -> dict[str, Type]:
        return self.compile(source).types

    def analyze_effects(self, source: str) -> dict[str, str]:
        return {name: "IO" if "console" in source else "Pure"
                for name in self.compile(source).functions}


class _TS_CAdapter:
    """C tree-sitter 适配器。"""
    LANGUAGE = "c"
    STD_MATH = {"sin": "sin", "cos": "cos", "tan": "tan", "sqrt": "sqrt",
                "exp": "exp", "log": "log", "fabs": "fabs",
                "floor": "floor", "ceil": "ceil", "pow": "pow"}

    def compile(self, source: str) -> CompileResult:
        result = CompileResult(language=self.LANGUAGE, source=source)
        try:
            parser = _TS_C()
            tree = parser.parse(source)
            for fn in tree.children:
                if fn.type in ("c_function",):
                    name = fn.value
                    result.functions[name] = []
                    result.types[name] = T_FLOAT
                    result.effects[name] = "Pure"
        except Exception as e:
            result.errors.append(f"C compile error: {e}")
        return result

    def infer_types(self, source: str) -> dict[str, Type]:
        return self.compile(source).types

    def analyze_effects(self, source: str) -> dict[str, str]:
        return self.compile(source).effects


# ============================================================
# 初始化注册
# ============================================================

def get_frontend() -> MultiLanguageFrontend:
    """获取全局前端实例。"""
    from src.mir2_frontend import PythonFrontend
    frontend = MultiLanguageFrontend()
    frontend.register("python", PythonFrontend())
    if _USE_TS:
        frontend.register("rust", _TS_RustAdapter())
        frontend.register("go", _TS_GoAdapter())
        frontend.register("javascript", _TS_JSAdapter())
        frontend.register("c", _TS_CAdapter())
    else:
        frontend.register("rust", RustFrontend())
        frontend.register("go", GoFrontend())
        frontend.register("javascript", JSFrontend())
        frontend.register("c", CFrontend())
    return frontend


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MultiLanguageFrontend",
    "RustFrontend",
    "GoFrontend",
    "JSFrontend",
    "CFrontend",
    "CompileResult",
    "IRNode",
    "IRKind",
    "get_frontend",
    "_ir_to_mir",
]
