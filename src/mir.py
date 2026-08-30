# -*- coding: utf-8 -*-
"""
Matha 专属 IR (MIR - Matha Intermediate Representation)

MIR 设计原则：
  1. 数学领域优化：直接表达数学运算语义
  2. 静态单赋值形式 (SSA)：便于优化
  3. 类型精确：double/int/bool 明确区分
  4. 可生成 C/Python 代码：双目标后端
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


# ============================================================
# MIR 类型系统
# ============================================================

class MIRType(Enum):
    """MIR 类型。"""
    VOID = "void"
    BOOL = "i1"
    INT = "i64"
    FLOAT = "double"
    PTR = "ptr"
    FUNC = "func"
    ARRAY = "array"


# ============================================================
# MIR 指令集
# ============================================================

class MIRInstrType(Enum):
    """MIR 指令类型。"""
    # 算术运算
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    POW = auto()
    FADD = auto()
    FSUB = auto()
    FMUL = auto()
    FDIV = auto()
    FPOW = auto()
    MOD = auto()
    NEG = auto()

    # 比较运算
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()

    # 逻辑运算
    AND = auto()
    OR = auto()
    NOT = auto()

    # 函数调用
    CALL = auto()
    CIMPORT = auto()  # 从 C 库导入函数

    # 内存操作
    LOAD = auto()
    STORE = auto()
    ALLOC = auto()

    # 控制流
    BRANCH = auto()
    COND_BRANCH = auto()
    LABEL = auto()
    RETURN = auto()

    # 数学常量
    PI = auto()
    E = auto()
    SQRT2 = auto()
    LN2 = auto()
    LN10 = auto()
    LOG2E = auto()
    LOG10E = auto()
    SQRT1_2 = auto()
    TAU = auto()

    # 数学函数
    SIN = auto()
    COS = auto()
    TAN = auto()
    ASIN = auto()
    ACOS = auto()
    ATAN = auto()
    ATAN2 = auto()
    SINH = auto()
    COSH = auto()
    TANH = auto()
    SQRT = auto()
    CBRT = auto()
    EXP = auto()
    EXP2 = auto()
    EXPM1 = auto()
    LOG = auto()
    LOG10 = auto()
    LOG2 = auto()
    LOG1P = auto()
    FABS = auto()
    CEIL = auto()
    FLOOR = auto()
    ROUND = auto()
    TRUNC = auto()
    SIGN = auto()
    HYPOT = auto()
    DEG2RAD = auto()
    RAD2DEG = auto()


# ============================================================
# MIR 指令类
# ============================================================

@dataclass
class MIRInstr:
    """MIR 指令基类。"""
    result: str = ""
    instr_type: MIRInstrType = MIRInstrType.ADD
    operands: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    value: float = None  # 常量折叠后的值

    def __str__(self) -> str:
        return self.format()

    def format(self) -> str:
        raise NotImplementedError


@dataclass
class MIRArithInstr(MIRInstr):
    """算术运算指令。"""
    op: str = ""

    def format(self) -> str:
        if self.op == "**":
            return f"{self.result} = pow({', '.join(self.operands)})"
        return f"{self.result} = {self.operands[0]} {self.op} {self.operands[1]}"


@dataclass
class MIRUnaryInstr(MIRInstr):
    """一元运算指令。"""
    op: str = ""

    def format(self) -> str:
        return f"{self.result} = {self.op}{self.operands[0]}"


@dataclass
class MIRCallInstr(MIRInstr):
    """函数调用指令。"""
    func_name: str = ""
    c_func: str = ""
    lib: str = ""

    def format(self) -> str:
        args = ", ".join(self.operands) if self.operands else ""
        return f"{self.result} = {self.c_func or self.func_name}({args})"


@dataclass
class MIRCImportInstr(MIRInstr):
    """从 C 库导入函数。"""
    c_func: str = ""
    lib: str = "math"

    def format(self) -> str:
        return f"; #include <{self.lib}.h>"

    def get_c_signature(self) -> str:
        args = ", ".join(f"double {a}" for a in self.operands)
        return f"double {self.c_func}({args})"


@dataclass
class MIRCompareInstr(MIRInstr):
    """比较运算指令。"""
    op: str = ""

    def format(self) -> str:
        return f"{self.result} = ({self.operands[0]} {self.op} {self.operands[1]})"


@dataclass
class MIRLogicalInstr(MIRInstr):
    """逻辑运算指令。"""
    op: str = ""

    def format(self) -> str:
        if self.op == "not":
            return f"{self.result} = (!{self.operands[0]})"
        return f"{self.result} = ({self.operands[0]} {self.op} {self.operands[1]})"


@dataclass
class MIRBranchInstr(MIRInstr):
    """分支指令。"""
    label: str = ""

    def format(self) -> str:
        return f"br label %{self.label}"


@dataclass
class MIRCondBranchInstr(MIRInstr):
    """条件分支指令。"""
    cond: str = ""
    true_label: str = ""
    false_label: str = ""

    def format(self) -> str:
        return f"br i1 {self.cond}, label %{self.true_label}, label %{self.false_label}"


@dataclass
class MIRLabelInstr(MIRInstr):
    """标签指令。"""
    label: str = ""

    def format(self) -> str:
        return f"{self.label}:"


@dataclass
class MIRReturnInstr(MIRInstr):
    """返回指令。"""
    value: str = ""

    def format(self) -> str:
        if self.value:
            return f"ret double {self.value}"
        return "ret void"


@dataclass
class MIRStoreInstr(MIRInstr):
    """存储指令。"""
    target: str = ""

    def format(self) -> str:
        return f"store {self.operands[0]}, {self.target}"


@dataclass
class MIRLoadInstr(MIRInstr):
    """加载指令。"""
    source: str = ""

    def format(self) -> str:
        return f"{self.result} = load {self.source}"


@dataclass
class MIRConstInstr(MIRInstr):
    """常量指令。"""
    value: float = 0.0

    def format(self) -> str:
        return f"{self.result} = const double {self.value}"


# ============================================================
# MIR 程序结构
# ============================================================

@dataclass
class MIRFunction:
    """MIR 函数。"""
    name: str
    params: list = field(default_factory=list)
    param_types: list = field(default_factory=list)
    return_type: str = "double"
    instructions: list = field(default_factory=list)
    labels: dict = field(default_factory=dict)
    c_imports: list = field(default_factory=list)


@dataclass
class MIRProgram:
    """MIR 程序。"""
    functions: dict = field(default_factory=dict)
    globals: dict = field(default_factory=dict)
    constants: dict = field(default_factory=dict)
    temp_counter: int = 0


# ============================================================
# MIR 生成器：AST → MIR
# ============================================================

class MIRGenerator:
    """将 Matha AST 转换为 MIR。"""

    # 数学函数映射 (函数名 → (C库, C函数名))
    MATH_FUNCS = {
        "sin": ("math", "sin"),
        "cos": ("math", "cos"),
        "tan": ("math", "tan"),
        "asin": ("math", "asin"),
        "acos": ("math", "acos"),
        "atan": ("math", "atan"),
        "atan2": ("math", "atan2"),
        "sinh": ("math", "sinh"),
        "cosh": ("math", "cosh"),
        "tanh": ("math", "tanh"),
        "sqrt": ("math", "sqrt"),
        "cbrt": ("math", "cbrt"),
        "exp": ("math", "exp"),
        "exp2": ("math", "exp2"),
        "expm1": ("math", "expm1"),
        "log": ("math", "log"),
        "log10": ("math", "log10"),
        "log2": ("math", "log2"),
        "log1p": ("math", "log1p"),
        "fabs": ("math", "fabs"),
        "floor": ("math", "floor"),
        "ceil": ("math", "ceil"),
        "round": ("math", "round"),
        "trunc": ("math", "trunc"),
        "signbit": ("math", "signbit"),
        "hypot": ("math", "hypot"),
        "pow": ("math", "pow"),
        "fmod": ("math", "fmod"),
    }

    # 数学常量
    MATH_CONSTS = {
        "pi": 3.141592653589793,
        "tau": 6.283185307179586,
        "e": 2.718281828459045,
        "sqrt2": 1.4142135623730951,
        "sqrt3": 1.7320508075688772,
        "ln2": 0.6931471805599453,
        "ln10": 2.302585092994046,
        "log2e": 1.4426950408889634,
        "log10e": 0.4342944819032518,
        "sqrt1_2": 0.7071067811865476,
    }

    def __init__(self) -> None:
        self._program = MIRProgram()
        self._scopes: list = [{}]
        self._temp_counter = 0

    def _new_temp(self) -> str:
        self._temp_counter += 1
        return f"t{self._temp_counter}"

    def _ensure_scope(self) -> dict:
        if not self._scopes:
            self._scopes = [{}]
        return self._scopes[-1]

    def generate(self, ast: Any) -> MIRProgram:
        """生成 MIR 程序。"""
        main_func = MIRFunction(name="main", params=[], param_types=[], return_type="double")
        self._program.functions["main"] = main_func
        self._compile_program(ast)
        self._add_required_imports()
        return self._program

    def _compile_program(self, program: Any) -> None:
        if program is None:
            return
        for decl in getattr(program, "decls", []):
            self._compile_decl(decl)

    def _compile_decl(self, decl: Any) -> None:
        kind = type(decl).__name__
        if kind == "FuncDef":
            self._compile_func_def(decl)
        elif kind == "Binding":
            self._compile_binding(decl)
        elif kind == "Output":
            if hasattr(decl, "expr") and decl.expr:
                result = self._compile_expr(decl.expr)
                # 支持自定义输出目标，默认为 printf
                output_target = getattr(decl, "target", "printf")
                self._program.functions["main"].instructions.append(
                    MIRCallInstr(result, MIRInstrType.CALL, [result], {"c_func": output_target})
                )
        elif kind == "LetBinding":
            if hasattr(decl, "value"):
                result = self._compile_expr(decl.value)
                if hasattr(decl, "name"):
                    self._ensure_scope()[decl.name] = result

    def _compile_func_def(self, func_def: Any) -> None:
        name = getattr(func_def, "name", "unknown")
        params = [p.name if hasattr(p, "name") else str(p) for p in getattr(func_def, "params", [])]
        return_type = getattr(func_def, "return_type", "double")

        func = MIRFunction(name=name, params=params, param_types=["double"] * len(params), return_type=return_type)
        scope = {param: param for param in params}
        self._scopes.append(scope)

        body = getattr(func_def, "body", None)
        if body:
            result = self._compile_expr(body)
            func.instructions.append(MIRReturnInstr(result, MIRInstrType.RETURN, [result]))

        self._scopes.pop()
        self._program.functions[name] = func

    def _compile_binding(self, binding: Any) -> None:
        name = getattr(binding, "name", "")
        value = getattr(binding, "value", None)
        if value:
            result = self._compile_expr(value)
            self._ensure_scope()[name] = result
            main = self._program.functions["main"]
            main.instructions.append(MIRStoreInstr("", MIRInstrType.STORE, [result], {"target": name}))

    # 类型分派表（避免字符串比较）- 实例变量，避免跨实例污染
    _COMPILE_EXPR_DISPATCH: dict = None

    def _compile_expr(self, expr: Any) -> str:
        if expr is None:
            return "0.0"
        expr_type = type(expr)
        if self._COMPILE_EXPR_DISPATCH is None:
            self._COMPILE_EXPR_DISPATCH = {}
        handler = self._COMPILE_EXPR_DISPATCH.get(expr_type)
        if handler is None:
            kind = expr_type.__name__
            if kind == "Literal":
                handler = self._compile_literal
            elif kind in ("FloatLit", "IntegerLit", "StringLit", "BoolLit"):
                handler = self._compile_literal
            elif kind == "Variable":
                handler = self._compile_variable
            elif kind == "BinaryOp":
                handler = self._compile_binary
            elif kind == "UnaryOp":
                handler = self._compile_unary
            elif kind == "FuncApp":
                handler = self._compile_func_app
            elif kind == "Lambda":
                handler = self._compile_lambda
            elif kind == "IfExpr":
                handler = self._compile_if
            elif kind == "ListLiteral":
                handler = self._compile_list
            elif kind == "DictLiteral":
                handler = self._compile_dict
            elif kind == "PathExpr":
                handler = self._compile_path
            elif kind == "TupleExpr":
                handler = self._compile_tuple
            elif kind == "IndexExpr":
                handler = self._compile_index
            elif kind == "SliceExpr":
                handler = self._compile_slice
            elif kind == "SetConstruct":
                handler = self._compile_set
            else:
                raise ValueError(f"未知的AST节点类型: {kind}")
            self._COMPILE_EXPR_DISPATCH[expr_type] = handler
        return handler(expr)

    def _compile_literal(self, lit: Any) -> str:
        result = self._new_temp()
        value = getattr(lit, "value", 0.0)
        # 创建常量指令，设置 value 属性
        instr = MIRConstInstr(result, MIRInstrType.ADD, [])
        instr.value = value
        self._program.functions["main"].instructions.append(instr)
        return result

    def _compile_variable(self, var: Any) -> str:
        name = getattr(var, "name", "")
        scope = self._scopes[-1] if self._scopes else {}
        return scope.get(name, name)

    def _compile_binary(self, op_expr: Any) -> str:
        left = self._compile_expr(getattr(op_expr, "left", None))
        right = self._compile_expr(getattr(op_expr, "right", None))
        op = getattr(op_expr, "op", "")
        result = self._new_temp()
        main = self._program.functions["main"]

        if op in ("+", "-", "*", "/", "//", "%", "**"):
            instr = MIRArithInstr(result, MIRInstrType.ADD, [left, right])
            instr.op = op
            main.instructions.append(instr)
        elif op in ("<", ">", "<=", ">=", "==", "!="):
            instr = MIRCompareInstr(result, MIRInstrType.EQ, [left, right])
            instr.op = op
            main.instructions.append(instr)
        elif op in ("and", "or"):
            instr = MIRLogicalInstr(result, MIRInstrType.AND, [left, right])
            instr.op = op
            main.instructions.append(instr)
        elif op == "→":
            instr = MIRCallInstr(result, MIRInstrType.CALL, [left, right])
            instr.func_name = "apply"
            main.instructions.append(instr)
        else:
            return left
        return result

    def _compile_unary(self, op_expr: Any) -> str:
        operand = self._compile_expr(getattr(op_expr, "operand", None))
        op = getattr(op_expr, "op", "")
        result = self._new_temp()
        main = self._program.functions["main"]

        if op == "-":
            main.instructions.append(MIRArithInstr(result, MIRInstrType.FSUB, ["0.0", operand], {"op": "-"}))
        elif op in ("++", "INCR"):
            main.instructions.append(MIRArithInstr(result, MIRInstrType.FADD, [operand, "1.0"], {"op": "+"}))
        elif op in ("--", "DECR"):
            main.instructions.append(MIRArithInstr(result, MIRInstrType.FSUB, [operand, "1.0"], {"op": "-"}))
        elif op == "^":
            main.instructions.append(MIRCallInstr(result, MIRInstrType.CALL, [operand], {"c_func": "sqrt", "lib": "math"}))
        else:
            return operand
        return result

    def _compile_func_app(self, func_app: Any) -> str:
        func = getattr(func_app, "func", None)
        arg = getattr(func_app, "arg", None)

        if isinstance(func, str):
            func_name = func
        elif hasattr(func, "name"):
            func_name = func.name
        else:
            func_name = "unknown"

        arg_val = self._compile_expr(arg) if arg else "0.0"
        result = self._new_temp()

        if func_name in self.MATH_FUNCS:
            lib, c_func = self.MATH_FUNCS[func_name]
            instr = MIRCallInstr(result, MIRInstrType.CALL, [arg_val])
            instr.func_name = func_name
            instr.c_func = c_func
            instr.lib = lib
            self._program.functions["main"].instructions.append(instr)
        elif func_name in self._program.functions:
            instr = MIRCallInstr(result, MIRInstrType.CALL, [arg_val])
            instr.func_name = func_name
            self._program.functions["main"].instructions.append(instr)
        else:
            instr = MIRCallInstr(result, MIRInstrType.CALL, [arg_val])
            instr.func_name = func_name
            self._program.functions["main"].instructions.append(instr)
        return result

    def _compile_lambda(self, lam: Any) -> str:
        return self._new_temp()

    def _compile_if(self, if_expr: Any) -> str:
        cond = self._compile_expr(getattr(if_expr, "cond", None))
        then_val = self._compile_expr(getattr(if_expr, "then", None))
        else_val = self._compile_expr(getattr(if_expr, "else_", None)) if getattr(if_expr, "else_", None) else "0.0"
        result = self._new_temp()
        main = self._program.functions["main"]

        true_label = f"if_then_{len(main.instructions)}"
        false_label = f"if_else_{len(main.instructions)}"
        end_label = f"if_end_{len(main.instructions)}"

        main.instructions.append(MIRCondBranchInstr("", MIRInstrType.COND_BRANCH, [cond], {"true_label": true_label, "false_label": false_label}))
        main.instructions.append(MIRLabelInstr(true_label, MIRInstrType.LABEL, [true_label]))
        main.instructions.append(MIRArithInstr(result, MIRInstrType.FADD, [then_val], {"op": "="}))
        main.instructions.append(MIRBranchInstr("", MIRInstrType.BRANCH, [true_label], {"label": end_label}))
        main.instructions.append(MIRLabelInstr(false_label, MIRInstrType.LABEL, [false_label]))
        main.instructions.append(MIRArithInstr(result, MIRInstrType.FADD, [else_val], {"op": "="}))
        main.instructions.append(MIRBranchInstr("", MIRInstrType.BRANCH, [false_label], {"label": end_label}))
        main.instructions.append(MIRLabelInstr(end_label, MIRInstrType.LABEL, [end_label]))
        return result

    def _compile_list(self, lst: Any) -> str:
        result = self._new_temp()
        items = [self._compile_expr(i) for i in getattr(lst, "items", [])]
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, items, {"func_name": "make_list", "c_func": "make_list"})
        )
        return result

    def _compile_dict(self, dct: Any) -> str:
        result = self._new_temp()
        keys = [self._compile_expr(k) for k in getattr(dct, "keys", [])]
        values = [self._compile_expr(v) for v in getattr(dct, "values", [])]
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, keys + values, {"func_name": "make_dict", "c_func": "make_dict"})
        )
        return result

    def _compile_path(self, path: Any) -> str:
        left = self._compile_expr(getattr(path, "left", None))
        right = getattr(path, "right", "")
        result = self._new_temp()
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, [left], {"func_name": f"get_{right}", "c_func": f"get_{right}"})
        )
        return result

    def _compile_tuple(self, tpl: Any) -> str:
        """编译元组表达式。"""
        elements = [self._compile_expr(e) for e in getattr(tpl, "elements", [])]
        result = self._new_temp()
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, elements, {"func_name": "make_tuple", "c_func": "make_tuple"})
        )
        return result

    def _compile_index(self, idx: Any) -> str:
        """编译索引表达式。"""
        container = self._compile_expr(getattr(idx, "container", None))
        index = self._compile_expr(getattr(idx, "index", None))
        result = self._new_temp()
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, [container, index], {"func_name": "index", "c_func": "index"})
        )
        return result

    def _compile_slice(self, slc: Any) -> str:
        """编译切片表达式。"""
        container = self._compile_expr(getattr(slc, "container", None))
        start = self._compile_expr(getattr(slc, "start", None)) if getattr(slc, "start", None) else "0.0"
        end = self._compile_expr(getattr(slc, "end", None)) if getattr(slc, "end", None) else "0.0"
        result = self._new_temp()
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, [container, start, end], {"func_name": "slice", "c_func": "slice"})
        )
        return result

    def _compile_set(self, set_node: Any) -> str:
        """编译集合构造表达式。"""
        result = self._new_temp()
        literals = [self._compile_expr(l) for l in getattr(set_node, "literals", [])]
        self._program.functions["main"].instructions.append(
            MIRCallInstr(result, MIRInstrType.CALL, literals, {"func_name": "make_set", "c_func": "make_set"})
        )
        return result

    def _add_required_imports(self) -> None:
        main = self._program.functions["main"]
        for instr in main.instructions:
            if isinstance(instr, MIRCallInstr) and instr.lib:
                import_instr = MIRCImportInstr(instr.c_func, MIRInstrType.CIMPORT, [], {"lib": instr.lib, "c_func": instr.c_func})
                if import_instr not in main.c_imports:
                    main.c_imports.append(import_instr)

    def to_dict(self) -> dict:
        return {
            "functions": {
                name: {
                    "name": f.name,
                    "params": f.params,
                    "return_type": f.return_type,
                    "instructions": [str(i) for i in f.instructions],
                    "c_imports": [i.get_c_signature() for i in f.c_imports],
                }
                for name, f in self._program.functions.items()
            },
            "globals": self._program.globals,
        }


# ============================================================
# 公共 API
# ============================================================

def generate_mir(ast: Any) -> MIRProgram:
    """生成 MIR 程序。"""
    generator = MIRGenerator()
    return generator.generate(ast)


def mir_to_dict(mir: MIRProgram) -> dict:
    """将 MIR 转换为字典。"""
    result = {}
    for name, func in mir.functions.items():
        result[name] = {
            "params": func.params,
            "return_type": func.return_type,
            "instructions": [str(i) for i in func.instructions],
            "c_imports": [i.get_c_signature() for i in func.c_imports],
        }
    return result


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "MIRType", "MIRInstrType",
    "MIRInstr", "MIRArithInstr", "MIRUnaryInstr", "MIRCallInstr",
    "MIRCImportInstr", "MIRCompareInstr", "MIRLogicalInstr",
    "MIRBranchInstr", "MIRCondBranchInstr", "MIRLabelInstr",
    "MIRReturnInstr", "MIRStoreInstr", "MIRLoadInstr", "MIRConstInstr",
    "MIRFunction", "MIRProgram",
    "MIRGenerator",
    "generate_mir",
    "mir_to_dict",
]
