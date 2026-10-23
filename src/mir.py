"""
Matha 专属 IR (MIR - Matha Intermediate Representation)

MIR 设计原则：
  1. 数学领域优化：直接表达数学运算语义
  2. 静态单赋值形式 (SSA)：便于优化
  3. 类型精确：double/int/bool 明确区分
  4. 可生成 C/Python 代码：双目标后端
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

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
    FREE = auto()
    MEMCPY = auto()
    MEMSET = auto()

    # 向量/矩阵运算
    VLOAD = auto()
    VSTORE = auto()
    VADD = auto()
    VSUB = auto()
    VMUL = auto()
    VDIV = auto()
    VDOT = auto()
    VMATMUL = auto()
    VTRANSPOSE = auto()
    VREDUCE_SUM = auto()
    VREDUCE_MAX = auto()
    VREDUCE_MIN = auto()
    VREDUCE_MEAN = auto()
    VSLICE = auto()
    VCONCAT = auto()
    VRESHAPE = auto()

    # 控制流
    BRANCH = auto()
    COND_BRANCH = auto()
    LABEL = auto()
    RETURN = auto()

    # 异常处理
    TRY = auto()
    CATCH = auto()
    THROW = auto()
    FINALLY = auto()
    LANDINGPAD = auto()

    # 协程/并发
    SPAWN = auto()
    SEND = auto()
    RECV = auto()
    SELECT = auto()
    YIELD = auto()
    CHANNEL_CREATE = auto()
    CHANNEL_CLOSE = auto()
    MUTEX_LOCK = auto()
    MUTEX_UNLOCK = auto()
    COND_WAIT = auto()
    COND_SIGNAL = auto()
    COND_BROADCAST = auto()

    # 调试/画像
    TRACE = auto()
    PROBE = auto()
    SAMPLE = auto()
    BREAKPOINT = auto()

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
        op = self.instr_type.name
        operands = ", ".join(str(o) for o in self.operands)
        folded = f"  # folded={self.value}" if self.value is not None else ""
        head = f"{self.result} = " if self.result else ""
        return f"{head}{op}({operands}){folded}"


@dataclass
class MIRArithInstr(MIRInstr):
    """算术运算指令。"""
    op: str = ""

    def format(self) -> str:
        if self.op == "**":
            return f"{self.result} = pow({', '.join(self.operands)})"
        if self.op == "=" and len(self.operands) == 1:
            return f"{self.result} = {self.operands[0]}"
        if len(self.operands) < 2:
            return f"{self.result} = {self.op}({', '.join(self.operands)})"
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
        if len(self.operands) < 2:
            return f"{self.result} = {self.op}({', '.join(self.operands)})"
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
# 扩展指令类 (Layer 1.2)
# ============================================================

@dataclass
class MIRFreeInstr(MIRInstr):
    """内存释放指令。"""
    target: str = ""

    def format(self) -> str:
        return f"free {self.target}"


@dataclass
class MIRMemcpyInstr(MIRInstr):
    """内存复制指令。"""
    dest: str = ""
    src: str = ""
    size: int = 0

    def format(self) -> str:
        return f"memcpy {self.dest}, {self.src}, {self.size}"


@dataclass
class MIRMemsetInstr(MIRInstr):
    """内存设置指令。"""
    target: str = ""
    value: int = 0
    size: int = 0

    def format(self) -> str:
        return f"memset {self.target}, {self.value}, {self.size}"


# 向量/矩阵指令

@dataclass
class MIRVectorInstr(MIRInstr):
    """向量运算基类。"""
    vec_type: str = "float64"  # float32/float64/int32/int64
    shape: tuple = field(default_factory=tuple)

    def format(self) -> str:
        op = self.instr_type.name
        operands = ", ".join(str(o) for o in self.operands)
        head = f"{self.result} = " if self.result else ""
        vec = f"<{self.vec_type}x{''.join(str(s) for s in self.shape)}>"
        return f"{head}{op} {vec}({operands})"


@dataclass
class MIRVLoadInstr(MIRVectorInstr):
    """向量加载指令。"""
    source: str = ""

    def format(self) -> str:
        return f"{self.result} = vload {self.source} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVStoreInstr(MIRVectorInstr):
    """向量存储指令。"""
    target: str = ""

    def format(self) -> str:
        return f"vstore {self.operands[0]}, {self.target} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVArithInstr(MIRVectorInstr):
    """向量算术运算。"""
    op: str = ""

    def format(self) -> str:
        op = self.op or (self.metadata.get('op', '') if self.metadata else '')
        return f"{self.result} = v{op} {self.operands[0]}, {self.operands[1]} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVDotInstr(MIRVectorInstr):
    """向量点积。"""

    def format(self) -> str:
        return f"{self.result} = vdot {self.operands[0]}, {self.operands[1]} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVMatMulInstr(MIRVectorInstr):
    """矩阵乘法。"""

    def format(self) -> str:
        return f"{self.result} = vmatmul {self.operands[0]}, {self.operands[1]} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVTransposeInstr(MIRVectorInstr):
    """矩阵转置。"""

    def format(self) -> str:
        return f"{self.result} = vtranspose {self.operands[0]} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVReduceInstr(MIRVectorInstr):
    """向量归约。"""
    reduce_op: str = ""  # sum/max/min/mean

    def format(self) -> str:
        op = self.reduce_op
        if not op and hasattr(self, 'instr_type'):
            # 从指令类型推断
            t = self.instr_type.name
            if t.startswith("VREDUCE_"):
                op = t[8:].lower()
        return f"{self.result} = vreduce.{op} {self.operands[0]} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVSliceInstr(MIRVectorInstr):
    """向量切片。"""
    start: tuple = field(default_factory=tuple)
    end: tuple = field(default_factory=tuple)

    def format(self) -> str:
        return f"{self.result} = vslice {self.operands[0]}, {self.start}, {self.end} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVConcatInstr(MIRVectorInstr):
    """向量拼接。"""
    axis: int = 0

    def format(self) -> str:
        return f"{self.result} = vconcat {', '.join(self.operands)}, axis={self.axis} : {self.vec_type}[{','.join(map(str,self.shape))}]"


@dataclass
class MIRVReshapeInstr(MIRVectorInstr):
    """向量重塑。"""
    new_shape: tuple = field(default_factory=tuple)

    def format(self) -> str:
        return f"{self.result} = vreshape {self.operands[0]}, {self.new_shape} : {self.vec_type}[{','.join(map(str,self.shape))}]"


# 异常处理指令

@dataclass
class MIRTryInstr(MIRInstr):
    """try 块开始。"""
    catch_label: str = ""
    finally_label: str = ""

    def format(self) -> str:
        return f"try label %{self.catch_label}, finally label %{self.finally_label}"


@dataclass
class MIRCatchInstr(MIRInstr):
    """catch 块。"""
    exception_type: str = ""
    exception_var: str = ""

    def format(self) -> str:
        return f"catch {self.exception_type} as {self.exception_var}"


@dataclass
class MIRThrowInstr(MIRInstr):
    """抛出异常。"""
    exception: str = ""

    def format(self) -> str:
        return f"throw {self.exception}"


@dataclass
class MIRFinallyInstr(MIRInstr):
    """finally 块。"""

    def format(self) -> str:
        return "finally"


@dataclass
class MIRLandingPadInstr(MIRInstr):
    """异常着陆点（用于栈展开）。"""
    personality: str = ""

    def format(self) -> str:
        return f"landingpad {self.personality}"


# 协程/并发指令

@dataclass
class MIRSpawnInstr(MIRInstr):
    """生成协程。"""
    func_name: str = ""

    def format(self) -> str:
        args = ", ".join(self.operands) if self.operands else ""
        return f"{self.result} = spawn {self.func_name}({args})"


@dataclass
class MIRSendInstr(MIRInstr):
    """通道发送。"""
    channel: str = ""

    def format(self) -> str:
        return f"send {self.channel}, {self.operands[0]}"


@dataclass
class MIRRecvInstr(MIRInstr):
    """通道接收。"""
    channel: str = ""

    def format(self) -> str:
        return f"{self.result} = recv {self.channel}"


@dataclass
class MIRSelectInstr(MIRInstr):
    """多路选择。"""
    cases: list = field(default_factory=list)  # [(channel, label), ...]
    default_label: str = ""

    def format(self) -> str:
        case_strs = [f"case {c} => label %{l}" for c, l in self.cases]
        if self.default_label:
            case_strs.append(f"default => label %{self.default_label}")
        return f"select {{\n  {chr(10).join('  ' + s for s in case_strs)}\n}}"


@dataclass
class MIRYieldInstr(MIRInstr):
    """协程让出。"""

    def format(self) -> str:
        return "yield"


@dataclass
class MIRChannelCreateInstr(MIRInstr):
    """创建通道。"""
    elem_type: str = "double"
    capacity: int = 0  # 0 = 无缓冲

    def format(self) -> str:
        return f"{self.result} = make_chan {self.elem_type}, {self.capacity}"


@dataclass
class MIRChannelCloseInstr(MIRInstr):
    """关闭通道。"""
    channel: str = ""

    def format(self) -> str:
        return f"close {self.channel}"


# 同步原语

@dataclass
class MIRMutexLockInstr(MIRInstr):
    """互斥锁加锁。"""
    mutex: str = ""

    def format(self) -> str:
        return f"lock {self.mutex}"


@dataclass
class MIRMutexUnlockInstr(MIRInstr):
    """互斥锁解锁。"""
    mutex: str = ""

    def format(self) -> str:
        return f"unlock {self.mutex}"


@dataclass
class MIRCondWaitInstr(MIRInstr):
    """条件变量等待。"""
    cond: str = ""
    mutex: str = ""

    def format(self) -> str:
        return f"cond_wait {self.cond}, {self.mutex}"


@dataclass
class MIRCondSignalInstr(MIRInstr):
    """条件变量通知单个。"""
    cond: str = ""

    def format(self) -> str:
        return f"cond_signal {self.cond}"


@dataclass
class MIRCondBroadcastInstr(MIRInstr):
    """条件变量广播。"""
    cond: str = ""

    def format(self) -> str:
        return f"cond_broadcast {self.cond}"


# 调试/画像指令

@dataclass
class MIRTraceInstr(MIRInstr):
    """执行跟踪。"""
    message: str = ""

    def format(self) -> str:
        return f'trace "{self.message}"'


@dataclass
class MIRProbeInstr(MIRInstr):
    """探针点（用于性能分析）。"""
    probe_id: str = ""

    def format(self) -> str:
        return f"probe {self.probe_id}"


@dataclass
class MIRSampleInstr(MIRInstr):
    """采样点。"""
    sample_name: str = ""

    def format(self) -> str:
        return f"sample {self.sample_name}"


@dataclass
class MIRBreakpointInstr(MIRInstr):
    """断点。"""

    def format(self) -> str:
        return "breakpoint"


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
        self._current_func: MIRFunction | None = None

    def _new_temp(self) -> str:
        self._temp_counter += 1
        return f"t{self._temp_counter}"

    def _ensure_scope(self) -> dict:
        if not self._scopes:
            self._scopes = [{}]
        return self._scopes[-1]

    def _current(self) -> MIRFunction:
        if self._current_func is None:
            self._current_func = self._program.functions["main"]
        return self._current_func

    def _emit(self, instr: MIRInstr) -> MIRInstr:
        """将指令写入当前函数，而不是固定写入 main。"""
        self._current().instructions.append(instr)
        return instr

    def generate(self, ast: Any) -> MIRProgram:
        """生成 MIR 程序。"""
        self._program = MIRProgram()
        self._scopes = [{}]
        self._temp_counter = 0
        main_func = MIRFunction(name="main", params=[], param_types=[], return_type="double")
        self._program.functions["main"] = main_func
        self._current_func = main_func
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
                self._emit(MIRCallInstr(
                    result=result,
                    instr_type=MIRInstrType.CALL,
                    operands=[result],
                    func_name=output_target,
                    c_func=output_target,
                ))
        elif kind == "LetBinding":
            if hasattr(decl, "value"):
                result = self._compile_expr(decl.value)
                if hasattr(decl, "name"):
                    self._ensure_scope()[decl.name] = result
        elif kind == "FuncApp":
            self._compile_expr(decl)
        elif kind == "MechUnit":
            self._compile_mech_unit(decl)

    def _emit_output(self, value: str) -> None:
        self._emit(MIRCallInstr(
            result="",
            instr_type=MIRInstrType.CALL,
            operands=[value],
            func_name="printf",
            c_func="printf",
        ))

    def _compile_mech_unit(self, mech_unit: Any) -> None:
        """按 Matha 块尾值语义输出代码块最后一个表达式。"""
        body = getattr(mech_unit, "body", None)
        statements = list(getattr(body, "stmts", []) or [])
        last_value = ""
        for statement in statements:
            kind = type(statement).__name__
            if kind == "LetBinding":
                name = getattr(statement, "name", "")
                value = getattr(statement, "value", None)
                if name and value is not None:
                    self._ensure_scope()[name] = self._compile_expr(value)
                continue
            last_value = self._compile_expr(statement)
        if last_value:
            self._emit_output(last_value)

    def _compile_func_def(self, func_def: Any) -> None:
        name = getattr(func_def, "name", "unknown")
        body = getattr(func_def, "body", None)

        param_nodes = getattr(body, "params", None)
        if param_nodes is None:
            param_nodes = getattr(func_def, "params", [])
        params = [p.name if hasattr(p, "name") else str(p) for p in param_nodes]

        # 遗留 MIR/C 后端把数值统一表示为 double；在 MIR 侧保持同一假设，
        # 避免 MIR 声明与 C 生成器签名不一致。
        param_types = ["double"] * len(params)
        return_type = "double"

        func = MIRFunction(name=name, params=params, param_types=param_types, return_type=return_type)
        previous = self._current_func
        self._current_func = func
        self._scopes.append({param: param for param in params})

        try:
            if body is not None:
                result = self._compile_expr(body)
                self._emit(MIRReturnInstr(
                    result=result,
                    instr_type=MIRInstrType.RETURN,
                    operands=[result],
                    value=result,
                ))
        finally:
            self._scopes.pop()
            self._current_func = previous

        self._program.functions[name] = func

    def _compile_binding(self, binding: Any) -> None:
        name = getattr(binding, "name", "")
        value = getattr(binding, "value", None)
        if value:
            result = self._compile_expr(value)
            self._ensure_scope()[name] = result
            self._emit(MIRStoreInstr(
                result="",
                instr_type=MIRInstrType.STORE,
                operands=[result],
                target=name,
            ))

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
            if kind == "Literal" or kind in ("FloatLit", "IntegerLit", "StringLit", "BoolLit"):
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
        self._emit(MIRConstInstr(
            result=result,
            instr_type=MIRInstrType.ADD,
            operands=[],
            value=value,
        ))
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

        if op in ("+", "-", "*", "/", "//", "%", "**"):
            self._emit(MIRArithInstr(
                result=result,
                instr_type=MIRInstrType.ADD,
                operands=[left, right],
                op=op,
            ))
        elif op in ("<", ">", "<=", ">=", "==", "!="):
            self._emit(MIRCompareInstr(
                result=result,
                instr_type=MIRInstrType.EQ,
                operands=[left, right],
                op=op,
            ))
        elif op in ("and", "or"):
            self._emit(MIRLogicalInstr(
                result=result,
                instr_type=MIRInstrType.AND,
                operands=[left, right],
                op=op,
            ))
        elif op == "→":
            self._emit(MIRCallInstr(
                result=result,
                instr_type=MIRInstrType.CALL,
                operands=[left, right],
                func_name="apply",
                c_func="apply",
            ))
        else:
            return left
        return result

    def _compile_unary(self, op_expr: Any) -> str:
        operand = self._compile_expr(getattr(op_expr, "operand", None))
        op = getattr(op_expr, "op", "")
        result = self._new_temp()

        if op == "-":
            self._emit(MIRArithInstr(
                result=result,
                instr_type=MIRInstrType.FSUB,
                operands=["0.0", operand],
                op="-",
            ))
        elif op in ("++", "INCR"):
            self._emit(MIRArithInstr(
                result=result,
                instr_type=MIRInstrType.FADD,
                operands=[operand, "1.0"],
                op="+",
            ))
        elif op in ("--", "DECR"):
            self._emit(MIRArithInstr(
                result=result,
                instr_type=MIRInstrType.FSUB,
                operands=[operand, "1.0"],
                op="-",
            ))
        elif op == "^":
            self._emit(MIRCallInstr(
                result=result,
                instr_type=MIRInstrType.CALL,
                operands=[operand],
                func_name="sqrt",
                c_func="sqrt",
                lib="math",
            ))
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

        if func_name in ("输出", "print"):
            self._emit_output(arg_val)
            return ""

        result = self._new_temp()

        if func_name in self.MATH_FUNCS:
            lib, c_func = self.MATH_FUNCS[func_name]
        else:
            lib, c_func = "", ""

        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=[arg_val],
            func_name=func_name,
            c_func=c_func,
            lib=lib,
        ))
        return result

    def _compile_lambda(self, lam: Any) -> str:
        """在当前函数内展开 lambda 体；遗留 MIR 后端没有闭包表示。"""
        params = getattr(lam, "params", [])
        scope = {
            (p.name if hasattr(p, "name") else str(p)):
            (p.name if hasattr(p, "name") else str(p))
            for p in params
        }
        self._scopes.append(scope)
        try:
            return self._compile_expr(getattr(lam, "body", None))
        finally:
            self._scopes.pop()

    def _compile_if(self, if_expr: Any) -> str:
        cond = self._compile_expr(getattr(if_expr, "cond", None))
        then_val = self._compile_expr(getattr(if_expr, "then", None))
        else_val = self._compile_expr(getattr(if_expr, "else_", None)) if getattr(if_expr, "else_", None) else "0.0"
        result = self._new_temp()

        instr_index = len(self._current().instructions)
        true_label = f"if_then_{instr_index}"
        false_label = f"if_else_{instr_index}"
        end_label = f"if_end_{instr_index}"

        self._emit(MIRCondBranchInstr(
            result="",
            instr_type=MIRInstrType.COND_BRANCH,
            operands=[cond],
            cond=cond,
            true_label=true_label,
            false_label=false_label,
        ))
        self._emit(MIRLabelInstr(
            result="",
            instr_type=MIRInstrType.LABEL,
            operands=[],
            label=true_label,
        ))
        self._emit(MIRArithInstr(
            result=result,
            instr_type=MIRInstrType.FADD,
            operands=[then_val],
            op="=",
        ))
        self._emit(MIRBranchInstr(
            result="",
            instr_type=MIRInstrType.BRANCH,
            operands=[],
            label=end_label,
        ))
        self._emit(MIRLabelInstr(
            result="",
            instr_type=MIRInstrType.LABEL,
            operands=[],
            label=false_label,
        ))
        self._emit(MIRArithInstr(
            result=result,
            instr_type=MIRInstrType.FADD,
            operands=[else_val],
            op="=",
        ))
        self._emit(MIRBranchInstr(
            result="",
            instr_type=MIRInstrType.BRANCH,
            operands=[],
            label=end_label,
        ))
        self._emit(MIRLabelInstr(
            result="",
            instr_type=MIRInstrType.LABEL,
            operands=[],
            label=end_label,
        ))
        return result

    def _compile_list(self, lst: Any) -> str:
        result = self._new_temp()
        items = [self._compile_expr(i) for i in getattr(lst, "items", [])]
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=items,
            func_name="make_list",
            c_func="make_list",
        ))
        return result

    def _compile_dict(self, dct: Any) -> str:
        result = self._new_temp()
        keys = [self._compile_expr(k) for k in getattr(dct, "keys", [])]
        values = [self._compile_expr(v) for v in getattr(dct, "values", [])]
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=keys + values,
            func_name="make_dict",
            c_func="make_dict",
        ))
        return result

    def _compile_path(self, path: Any) -> str:
        left = self._compile_expr(getattr(path, "left", None))
        right = getattr(path, "right", "")
        result = self._new_temp()
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=[left],
            func_name=f"get_{right}",
            c_func=f"get_{right}",
        ))
        return result

    def _compile_tuple(self, tpl: Any) -> str:
        """编译元组表达式。"""
        elements = [self._compile_expr(e) for e in getattr(tpl, "elements", [])]
        result = self._new_temp()
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=elements,
            func_name="make_tuple",
            c_func="make_tuple",
        ))
        return result

    def _compile_index(self, idx: Any) -> str:
        """编译索引表达式。"""
        container = self._compile_expr(getattr(idx, "container", None))
        index = self._compile_expr(getattr(idx, "index", None))
        result = self._new_temp()
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=[container, index],
            func_name="index",
            c_func="index",
        ))
        return result

    def _compile_slice(self, slc: Any) -> str:
        """编译切片表达式。"""
        container = self._compile_expr(getattr(slc, "container", None))
        start = self._compile_expr(getattr(slc, "start", None)) if getattr(slc, "start", None) else "0.0"
        end = self._compile_expr(getattr(slc, "end", None)) if getattr(slc, "end", None) else "0.0"
        result = self._new_temp()
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=[container, start, end],
            func_name="slice",
            c_func="slice",
        ))
        return result

    def _compile_set(self, set_node: Any) -> str:
        """编译集合构造表达式。"""
        if getattr(set_node, "form", None) == "comprehension":
            raise ValueError(
                "遗留 MIR/C 代码生成路径不支持集合理解 {输出 | 生成 | 条件}（该路径无循环构造）；"
                "宿主解释器与 PE64 原生后端（src/mbc/native.py）均已支持。"
                "如确需走本路径，请改用集合枚举 {1,2,3}")
        result = self._new_temp()
        literals = [self._compile_expr(l) for l in getattr(set_node, "literals", [])]
        self._emit(MIRCallInstr(
            result=result,
            instr_type=MIRInstrType.CALL,
            operands=literals,
            func_name="make_set",
            c_func="make_set",
        ))
        return result

    def _add_required_imports(self) -> None:
        for func in self._program.functions.values():
            for instr in func.instructions:
                if isinstance(instr, MIRCallInstr) and instr.lib:
                    import_instr = MIRCImportInstr(
                        result=instr.c_func,
                        instr_type=MIRInstrType.CIMPORT,
                        operands=[],
                        c_func=instr.c_func,
                        lib=instr.lib,
                    )
                    if import_instr not in func.c_imports:
                        func.c_imports.append(import_instr)

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
