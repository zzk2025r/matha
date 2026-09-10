# -*- coding: utf-8 -*-
"""
Matha 原生虚拟机 (MathaVM)
==========================
设计原则：
  - 零 Python/C/C++ 依赖：所有类型基于二进制/三进制/十进制原生构建
  - 字符编码：汉字/字母 → 三进制（Base-3）映射 → 二进制存储
  - 数字：Int（二进制/十进制），Float（十进制），Bool（二进制）
  - 字节码：纯 Matha 自描述格式，不依赖任何外部运行时

架构：
  .matha 源码 → compiler_matha 编译器 → M3V 字节码 → M3V 虚拟机 → 结果
"""

# ============================================================
# 底层数制：二进制 / 三进制 / 十进制
# ============================================================

class Base2:
    """二进制值（Base-2）— 所有数据的最终物理表示"""
    __slots__ = ('bits',)

    def __init__(self, value=0):
        if isinstance(value, str):
            # 字符串直接是二进制位
            self.bits = value
        elif isinstance(value, Base3):
            # 三进制转二进制
            self.bits = self._from_trinary(value.digits)
        elif isinstance(value, int):
            self.bits = bin(value)[2:]
        else:
            self.bits = bin(int(value))[2:]

    def _from_trinary(self, digits):
        """三进制 → 二进制"""
        value = 0
        for d in digits:
            value = value * 3 + d
        return bin(value)[2:]

    def __int__(self):
        return int(self.bits, 2) if self.bits else 0

    def __repr__(self):
        return f"Base2(0b{self.bits})"

    def __eq__(self, other):
        if isinstance(other, Base3):
            return self == Base2(other)
        return int(self) == int(other)

    def __add__(self, other):
        return Base2(int(self) + int(other))

    def __sub__(self, other):
        return Base2(int(self) - int(other))

    def __mul__(self, other):
        return Base2(int(self) * int(other))

    def __truediv__(self, other):
        return Base2(int(self) // int(other))

    def __and__(self, other):
        return Base2(int(self) & int(other))

    def __or__(self, other):
        return Base2(int(self) | int(other))

    def __xor__(self, other):
        return Base2(int(self) ^ int(other))

    def __lshift__(self, other):
        return Base2(int(self) << int(other))

    def __rshift__(self, other):
        return Base2(int(self) >> int(other))

    def __lt__(self, other):
        return int(self) < int(other)

    def __le__(self, other):
        return int(self) <= int(other)

    def __gt__(self, other):
        return int(self) > int(other)

    def __ge__(self, other):
        return int(self) >= int(other)

    def __neg__(self):
        return Base2(-int(self))

    def __abs__(self):
        return Base2(abs(int(self)))


class Base3:
    """三进制值（Base-3）— 字符/汉字编码的中间表示"""
    __slots__ = ('digits',)

    # 基础字符集 → 三进制编码
    # 字母: a-z(0-25), A-Z(26-51), 数字: 0-9(52-61)
    # 中文基本字符: 一级汉字常用(62+)
    _char_to_trinary = {}
    _trinary_to_char = {}

    def __init__(self, value=0):
        if isinstance(value, str) and len(value) == 1:
            # 字符 → 三进制
            if value not in self._char_to_trinary:
                # 自动生成三进制编码
                code = len(self._char_to_trinary)
                self._char_to_trinary[value] = code
                self._trinary_to_char[code] = value
            self.digits = self._to_trinary(self._char_to_trinary[value])
        elif isinstance(value, Base2):
            self.digits = self._from_binary(value.bits)
        elif isinstance(value, int):
            self.digits = self._to_trinary(value)
        elif isinstance(value, list):
            self.digits = value
        else:
            self.digits = self._to_trinary(int(value))

    def _to_trinary(self, n):
        """整数 → 三进制数字列表"""
        if n == 0:
            return [0]
        digits = []
        neg = n < 0
        n = abs(n)
        while n > 0:
            digits.append(n % 3)
            n //= 3
        if neg:
            # 三进制负数用补码表示
            pass
        return digits[::-1]

    def _from_trinary(self, digits):
        """三进制数字列表 → 整数"""
        value = 0
        for d in digits:
            value = value * 3 + d
        return value

    def _from_binary(self, bits):
        """二进制字符串 → 三进制"""
        return self._to_trinary(int(bits, 2))

    def __int__(self):
        return self._from_trinary(self.digits) if self.digits else 0

    def to_base2(self):
        """三进制 → 二进制"""
        return Base2(self._from_trinary(self.digits))

    def to_char(self):
        """三进制编码 → 字符（仅当是单字符编码时）"""
        val = self._from_trinary(self.digits) if self.digits else 0
        return self._trinary_to_char.get(val, f'\\u{val:04X}')

    def __repr__(self):
        return f"Base3({self.digits})"

    def __eq__(self, other):
        if isinstance(other, Base2):
            return self == Base3(other)
        if isinstance(other, int):
            return self._from_trinary(self.digits) == other
        return self.digits == other.digits

    def __add__(self, other):
        return Base3(self._from_trinary(self.digits) + (other if isinstance(other, int) else other._from_trinary(other.digits)))

    def __mul__(self, other):
        return Base3(self._from_trinary(self.digits) * (other if isinstance(other, int) else other._from_trinary(other.digits)))

    def __lt__(self, other):
        v = self._from_trinary(self.digits)
        o = other if isinstance(other, int) else other._from_trinary(other.digits)
        return v < o


class Base10:
    """十进制值（Base-10）— 人类可读的数值表示"""
    __slots__ = ('value',)

    def __init__(self, value=0.0):
        if isinstance(value, str):
            self.value = float(value)
        elif isinstance(value, Base2):
            self.value = float(int(value))
        elif isinstance(value, Base3):
            self.value = float(value._from_trinary(value.digits))
        else:
            self.value = float(value)

    def __float__(self):
        return self.value

    def __int__(self):
        return int(self.value)

    def __repr__(self):
        return f"Base10({self.value})"

    def __eq__(self, other):
        if isinstance(other, (Base2, Base3)):
            return self.value == float(other)
        return self.value == float(other)

    def __add__(self, other):
        return Base10(self.value + float(other))

    def __sub__(self, other):
        return Base10(self.value - float(other))

    def __mul__(self, other):
        return Base10(self.value * float(other))

    def __truediv__(self, other):
        return Base10(self.value / float(other))

    def __lt__(self, other):
        return self.value < float(other)

    def __le__(self, other):
        return self.value <= float(other)

    def __gt__(self, other):
        return self.value > float(other)

    def __ge__(self, other):
        return self.value >= float(other)

    def __neg__(self):
        return Base10(-self.value)

    def __abs__(self):
        return Base10(abs(self.value))

    def floor(self):
        return Base10(int(self.value // 1))

    def ceil(self):
        return Base10(int(self.value // 1) + (1 if self.value > int(self.value) else 0))

    def trunc(self):
        return Base10(int(self.value))

    def round(self):
        return Base10(round(self.value))


# ============================================================
# MathaVM 指令集
# ============================================================

class MathaOpcode:
    """MathaVM 指令码"""
    # 常量与加载
    PUSH_INT   = 0x01   # 推送整型常量
    PUSH_FLOAT = 0x02   # 推送浮点常量
    PUSH_STR   = 0x03   # 推送字符串常量
    PUSH_BASE2 = 0x04   # 推送二进制常量
    PUSH_BASE3 = 0x05   # 推送三进制常量
    PUSH_LOCAL = 0x10   # 推送局部变量
    PUSH_GLOBAL = 0x11  # 推送全局变量

    # 存储
    STORE_LOCAL = 0x20  # 存储到局部变量
    STORE_GLOBAL = 0x21 # 存储到全局变量
    STORE_PARAM = 0x22  # 存储到参数

    # 算术运算（栈操作）
    ADD    = 0x30  # a + b
    SUB    = 0x31  # a - b
    MUL    = 0x32  # a * b
    DIV    = 0x33  # a / b
    MOD    = 0x34  # a % b
    POW    = 0x35  # a ** b
    NEG    = 0x36  # -a

    # 比较运算
    EQ     = 0x40  # a == b
    NEQ    = 0x41  # a != b
    LT     = 0x42  # a < b
    GT     = 0x43  # a > b
    LEQ    = 0x44  # a <= b
    GEQ    = 0x45  # a >= b

    # 逻辑运算
    AND    = 0x50  # a and b
    OR     = 0x51  # a or b
    NOT    = 0x52  # not a

    # 类型转换
    TO_INT     = 0x60  # float → int
    TO_FLOAT   = 0x61  # any → float
    TO_BOOL    = 0x62  # any → bool
    FROM_BASE2 = 0x63  # Base2 → 其他
    FROM_BASE3 = 0x64  # Base3 → 其他
    TO_BASE2   = 0x65  # 其他 → Base2
    TO_BASE3   = 0x66  # 其他 → Base3

    # 数学函数
    SIN     = 0x70
    COS     = 0x71
    TAN     = 0x72
    ASIN    = 0x73
    ACOS    = 0x74
    ATAN    = 0x75
    EXP     = 0x76
    LOG     = 0x77
    SQRT    = 0x78
    ABS     = 0x79
    FLOOR   = 0x7A
    CEIL    = 0x7B
    TRUNC   = 0x7C
    ROUND   = 0x7D
    FACTORIAL = 0x7E
    LEN     = 0x7F

    # 控制流
    JMP      = 0x80  # 无条件跳转
    JZ       = 0x81  # 零值跳转
    JNZ      = 0x82  # 非零跳转
    CALL     = 0x83  # 调用函数
    RET      = 0x84  # 返回
    RETURN   = 0x85  # 返回值

    # 列表操作
    LIST_NEW   = 0x90  # 创建空列表
    LIST_PUSH  = 0x91  # 列表追加
    LIST_GET   = 0x92  # 列表索引取值
    LIST_SET   = 0x93  # 列表索引赋值
    LIST_LEN   = 0x94  # 列表长度

    # 系统操作
    PRINT    = 0xA0  # 打印输出
    INPUT    = 0xA1  # 输入
    ERROR    = 0xA2  # 抛出错误
    HALT     = 0xFF  # 停止

    @staticmethod
    def name(op):
        for k, v in MathaOpcode.__dict__.items():
            if v == op and not k.startswith('_'):
                return k
        return f"0x{op:02X}"


# ============================================================
# MathaVM 字节码格式
# ============================================================

class MathaBytecode:
    """MathaVM 字节码容器"""

    def __init__(self):
        self.instructions = []  # list of (opcode, operands)
        self.constants = []     # 常量池
        self.functions = {}     # 函数名 → 字节码偏移
        self.globals = {}       # 全局变量
        self.source_map = {}    # 字节码偏移 → 源代码位置

    def emit(self, opcode, *operands):
        """发射一条指令"""
        pos = len(self.instructions)
        self.instructions.append((opcode, operands))
        return pos

    def emit_jump(self, opcode, target_label):
        """发射跳转指令（目标在链接阶段解析）"""
        pos = self.emit(opcode, target_label)
        return pos

    def add_constant(self, value):
        """添加常量到常量池"""
        idx = len(self.constants)
        self.constants.append(value)
        return idx

    def function_start(self, name):
        """标记函数开始"""
        self.functions[name] = len(self.instructions)

    def function_end(self, name):
        """标记函数结束"""
        pass  # 简化实现

    def to_bytes(self):
        """序列化为字节"""
        buf = bytearray()
        # 魔数
        buf.extend(b'MATH')
        # 版本
        buf.append(1)
        # 常量池大小
        buf.extend(len(self.constants).to_bytes(4, 'big'))
        # 常量池
        for c in self.constants:
            buf.extend(self._encode_constant(c))
        # 指令数量
        buf.extend(len(self.instructions).to_bytes(4, 'big'))
        # 指令
        for op, operands in self.instructions:
            buf.append(op)
            buf.extend(self._encode_operands(operands))
        return bytes(buf)

    def _encode_constant(self, value):
        """编码常量"""
        if isinstance(value, int):
            return b'\x01' + value.to_bytes(8, 'big', signed=True)
        elif isinstance(value, float):
            return b'\x02' + int(value * 2**53).to_bytes(8, 'big')
        elif isinstance(value, str):
            encoded = value.encode('utf-8')
            return b'\x03' + len(encoded).to_bytes(2, 'big') + encoded
        elif isinstance(value, Base2):
            return b'\x04' + value.bits.encode('ascii')
        elif isinstance(value, Base3):
            return b'\x05' + bytes(value.digits)
        else:
            return b'\x00'

    def _encode_operands(self, operands):
        """编码指令操作数"""
        buf = bytearray()
        for op in operands:
            if isinstance(op, int):
                buf.extend(op.to_bytes(4, 'big', signed=True))
            elif isinstance(op, str):
                # 标签引用
                buf.extend(b'\xff')
                buf.extend(op.encode('utf-8') + b'\x00')
            elif isinstance(op, Base2):
                buf.extend(b'\x04' + op.bits.encode('ascii'))
            elif isinstance(op, Base3):
                buf.extend(b'\x05' + bytes(op.digits))
        return bytes(buf)


# ============================================================
# MathaVM 解释器
# ============================================================

class MathaVM:
    """Matha 虚拟机 — 纯 Matha 实现，零外部依赖"""

    def __init__(self, bytecode=None):
        self.bc = bytecode or MathaBytecode()
        self.stack = []
        self.locals = {}
        self.globals = {}
        self.functions = {}
        self.pc = 0  # 程序计数器
        self.running = False
        self._builtin_funcs = self._init_builtins()

    def _init_builtins(self):
        """初始化内建函数（纯数学实现，无外部库依赖）"""
        return {
            'print': self._builtin_print,
            'error': self._builtin_error,
            'abs': self._builtin_abs,
            'int': self._builtin_int,
            'float': self._builtin_float,
            'len': self._builtin_len,
            'sin': self._builtin_sin,
            'cos': self._builtin_cos,
            'tan': self._builtin_tan,
            'asin': self._builtin_asin,
            'acos': self._builtin_acos,
            'atan': self._builtin_atan,
            'exp': self._builtin_exp,
            'log': self._builtin_log,
            'sqrt': self._builtin_sqrt,
            'floor': self._builtin_floor,
            'ceil': self._builtin_ceil,
            'trunc': self._builtin_trunc,
            'round': self._builtin_round,
            'factorial': self._builtin_factorial,
            'pow': self._builtin_pow,
            'min': self._builtin_min,
            'max': self._builtin_max,
            # Matha 原生数制转换
            'to_base2': self._builtin_to_base2,
            'to_base3': self._builtin_to_base3,
            'from_base2': self._builtin_from_base2,
            'from_base3': self._builtin_from_base3,
        }

    # ===== 内建函数实现（纯数学，无 import）=====

    def _builtin_print(self, *args):
        vals = [self._resolve(v) for v in args]
        print(' '.join(str(v) for v in vals))
        return None

    def _builtin_error(self, msg):
        raise RuntimeError(str(self._resolve(msg)))

    def _builtin_abs(self, x):
        return abs(self._to_float(x))

    def _builtin_int(self, x):
        return int(self._to_float(x))

    def _builtin_float(self, x):
        return float(self._resolve(x))

    def _builtin_len(self, x):
        return len(self._resolve(x))

    def _builtin_sin(self, x):
        return self._taylor_sin(self._to_float(x))

    def _builtin_cos(self, x):
        return self._taylor_cos(self._to_float(x))

    def _builtin_tan(self, x):
        return self._builtin_sin(x) / self._builtin_cos(x)

    def _builtin_asin(self, x):
        return self._taylor_asin(self._to_float(x))

    def _builtin_acos(self, x):
        return self._PI / 2.0 - self._builtin_asin(x)

    def _builtin_atan(self, x):
        return self._taylor_atan(self._to_float(x))

    def _builtin_exp(self, x):
        return self._taylor_exp(self._to_float(x))

    def _builtin_log(self, x):
        return self._taylor_log(self._to_float(x))

    def _builtin_sqrt(self, x):
        return self._newton_sqrt(self._to_float(x))

    def _builtin_floor(self, x):
        return float(int(self._to_float(x)))

    def _builtin_ceil(self, x):
        f = self._to_float(x)
        i = int(f)
        return float(i + (1 if f > i else 0))

    def _builtin_trunc(self, x):
        return float(int(self._to_float(x)))

    def _builtin_round(self, x):
        return float(round(self._to_float(x)))

    def _builtin_factorial(self, n):
        n = int(self._to_float(n))
        if n < 0:
            raise ValueError("阶乘定义域为非负整数")
        result = 1
        for i in range(2, n + 1):
            result *= i
        return float(result)

    def _builtin_pow(self, base, exp):
        return self._to_float(base) ** self._to_float(exp)

    def _builtin_min(self, *args):
        vals = [self._to_float(a) for a in args]
        return min(vals)

    def _builtin_max(self, *args):
        vals = [self._to_float(a) for a in args]
        return max(vals)

    def _builtin_to_base2(self, n):
        return Base2(int(self._to_float(n)))

    def _builtin_to_base3(self, n):
        return Base3(int(self._to_float(n)))

    def _builtin_from_base2(self, b):
        return int(self._resolve(b))

    def _builtin_from_base3(self, b):
        return int(self._resolve(b))

    # ===== 纯数学实现（Taylor 级数，无 import math）=====

    _PI = 3.14159265358979323846
    _E = 2.71828182845904523536

    def _taylor_sin(self, x):
        """sin(x) via Taylor series"""
        x = self._reduce_angle(x)
        result = 0.0
        term = x
        for n in range(30):
            result += term
            term *= -x * x / ((2 * n + 2) * (2 * n + 3))
        return result

    def _taylor_cos(self, x):
        """cos(x) via Taylor series"""
        x = self._reduce_angle(x)
        result = 0.0
        term = 1.0
        for n in range(30):
            result += term
            term *= -x * x / ((2 * n + 1) * (2 * n + 2))
        return result

    def _taylor_exp(self, x):
        """exp(x) via Taylor series with argument reduction"""
        # 参数约化: e^x = (e^(x/2^k))^(2^k)
        k = 0
        while abs(x) > 1.0:
            x /= 2.0
            k += 1
        # Taylor 级数
        result = 1.0
        term = 1.0
        for n in range(1, 50):
            term *= x / n
            result += term
        # 平方 k 次
        for _ in range(k):
            result = result * result
        return result

    def _taylor_log(self, x):
        """log(x) via Taylor series with argument reduction"""
        if x <= 0:
            raise ValueError("log: 定义域为正数")
        # 参数约化: log(x) = log(x/2^k) + k*ln(2)
        k = 0
        while x > 2.0:
            x /= 2.0
            k += 1
        while x < 0.5:
            x *= 2.0
            k -= 1
        # Taylor: log(1+u) = u - u^2/2 + u^3/3 - ...
        u = x - 1.0
        result = 0.0
        term = u
        for n in range(1, 100):
            result += term / n
            term *= -u
        return result + k * self._LN2

    _LN2 = 0.6931471805599453

    def _taylor_asin(self, x):
        """asin(x) via Taylor series"""
        if abs(x) > 1.0:
            raise ValueError("asin: 定义域为 [-1, 1]")
        result = x
        term = x
        for n in range(1, 80):
            ratio = ((2 * n - 1) ** 2) / (2 * n * (2 * n + 1))
            term *= x * x * ratio
            result += term
            if abs(term) < 1e-16:
                break
        return result

    def _taylor_atan(self, x):
        """atan(x) with argument reduction"""
        negative = x < 0
        x = abs(x)
        # 参数约化: atan(x) = 2*atan(x/(1+sqrt(1+x^2)))
        k = 0
        while x > 0.4:
            x = x / (1.0 + self._newton_sqrt(1.0 + x * x))
            k += 1
        # Taylor: atan(x) = x - x^3/3 + x^5/5 - ...
        result = 0.0
        term = x
        for n in range(80):
            result += term * (1.0 if n % 2 == 0 else -1.0) / (2 * n + 1)
            term *= -x * x
            if abs(term) < 1e-15:
                break
        # 应用约化: atan(x) = 2^k * atan(reduced_x)
        result *= (2 ** k)
        if negative:
            result = -result
        return result

    def _newton_sqrt(self, x):
        """sqrt(x) via Newton-Raphson"""
        if x < 0:
            raise ValueError("sqrt: 定义域为非负数")
        if x == 0:
            return 0.0
        guess = x if x >= 1.0 else 1.0
        for _ in range(50):
            new_guess = 0.5 * (guess + x / guess)
            if abs(new_guess - guess) < 1e-15:
                break
            guess = new_guess
        return guess

    def _reduce_angle(self, x):
        """角度约化到 [-pi, pi]"""
        two_pi = 2.0 * self._PI
        x = x % two_pi
        if x > self._PI:
            x -= two_pi
        elif x < -self._PI:
            x += two_pi
        return x

    # ===== 辅助方法 =====

    def _resolve(self, val):
        """解析值（可能是栈引用或直接值）"""
        if isinstance(val, str) and val.startswith('$'):
            idx = int(val[1:])
            return self.stack[idx] if idx < len(self.stack) else None
        return val

    def _to_float(self, x):
        """统一转为浮点数"""
        if isinstance(x, Base2):
            return float(int(x))
        elif isinstance(x, Base3):
            return float(x._from_trinary(x.digits))
        elif isinstance(x, Base10):
            return x.value
        elif isinstance(x, (int, float)):
            return float(x)
        else:
            return float(x)

    # ===== 执行引擎 =====

    def run(self, bytecode=None):
        """执行字节码"""
        if bytecode:
            self.bc = bytecode
        self.stack = []
        self.locals = {}
        self.globals = {}
        self.pc = 0
        self.running = True

        while self.running and self.pc < len(self.bc.instructions):
            op, operands = self.bc.instructions[self.pc]
            self.pc += 1
            self._dispatch(op, operands)

        return self.stack[-1] if self.stack else None

    def _dispatch(self, op, operands):
        """分发指令"""
        handlers = {
            # 加载
            MathaOpcode.PUSH_INT:   lambda: self._push_int(operands),
            MathaOpcode.PUSH_FLOAT: lambda: self._push_float(operands),
            MathaOpcode.PUSH_STR:   lambda: self._push_str(operands),
            MathaOpcode.PUSH_BASE2: lambda: self._push_base2(operands),
            MathaOpcode.PUSH_BASE3: lambda: self._push_base3(operands),
            MathaOpcode.PUSH_LOCAL: lambda: self._push_local(operands),
            MathaOpcode.PUSH_GLOBAL: lambda: self._push_global(operands),
            # 存储
            MathaOpcode.STORE_LOCAL:  lambda: self._store_local(operands),
            MathaOpcode.STORE_GLOBAL: lambda: self._store_global(operands),
            # 算术
            MathaOpcode.ADD:   lambda: self._arith(MathaOpcode.ADD, lambda a,b: a+b),
            MathaOpcode.SUB:   lambda: self._arith(MathaOpcode.SUB, lambda a,b: a-b),
            MathaOpcode.MUL:   lambda: self._arith(MathaOpcode.MUL, lambda a,b: a*b),
            MathaOpcode.DIV:   lambda: self._arith(MathaOpcode.DIV, lambda a,b: a/b),
            MathaOpcode.MOD:   lambda: self._arith(MathaOpcode.MOD, lambda a,b: a%b),
            MathaOpcode.POW:   lambda: self._arith(MathaOpcode.POW, lambda a,b: a**b),
            MathaOpcode.NEG:   lambda: self._unary(lambda a: -a),
            # 比较
            MathaOpcode.EQ:    lambda: self._compare(lambda a,b: a==b),
            MathaOpcode.NEQ:   lambda: self._compare(lambda a,b: a!=b),
            MathaOpcode.LT:    lambda: self._compare(lambda a,b: a<b),
            MathaOpcode.GT:    lambda: self._compare(lambda a,b: a>b),
            MathaOpcode.LEQ:   lambda: self._compare(lambda a,b: a<=b),
            MathaOpcode.GEQ:   lambda: self._compare(lambda a,b: a>=b),
            # 逻辑
            MathaOpcode.AND:   lambda: self._logical(lambda a,b: a and b),
            MathaOpcode.OR:    lambda: self._logical(lambda a,b: a or b),
            MathaOpcode.NOT:   lambda: self._unary(lambda a: not a),
            # 类型转换
            MathaOpcode.TO_INT:     lambda: self._unary(lambda a: int(self._to_float(a))),
            MathaOpcode.TO_FLOAT:   lambda: self._unary(lambda a: self._to_float(a)),
            MathaOpcode.TO_BOOL:    lambda: self._unary(lambda a: bool(self._resolve(a))),
            MathaOpcode.FROM_BASE2: lambda: self._unary(self._builtin_from_base2),
            MathaOpcode.FROM_BASE3: lambda: self._unary(self._builtin_from_base3),
            # 数学函数
            MathaOpcode.SIN:      lambda: self._unary(self._builtin_sin),
            MathaOpcode.COS:      lambda: self._unary(self._builtin_cos),
            MathaOpcode.TAN:      lambda: self._unary(self._builtin_tan),
            MathaOpcode.ASIN:     lambda: self._unary(self._builtin_asin),
            MathaOpcode.ACOS:     lambda: self._unary(self._builtin_acos),
            MathaOpcode.ATAN:     lambda: self._unary(self._builtin_atan),
            MathaOpcode.EXP:      lambda: self._unary(self._builtin_exp),
            MathaOpcode.LOG:      lambda: self._unary(self._builtin_log),
            MathaOpcode.SQRT:     lambda: self._unary(self._builtin_sqrt),
            MathaOpcode.ABS:      lambda: self._unary(self._builtin_abs),
            MathaOpcode.FLOOR:    lambda: self._unary(self._builtin_floor),
            MathaOpcode.CEIL:     lambda: self._unary(self._builtin_ceil),
            MathaOpcode.TRUNC:    lambda: self._unary(self._builtin_trunc),
            MathaOpcode.ROUND:    lambda: self._unary(self._builtin_round),
            MathaOpcode.FACTORIAL: lambda: self._unary(self._builtin_factorial),
            MathaOpcode.LEN:      lambda: self._unary(self._builtin_len),
            # 列表
            MathaOpcode.LIST_NEW:  lambda: self.stack.append([]),
            MathaOpcode.LIST_PUSH: lambda: self._list_push(),
            MathaOpcode.LIST_GET:  lambda: self._list_get(),
            MathaOpcode.LIST_LEN:  lambda: self._unary(self._builtin_len),
            # 控制流
            MathaOpcode.JMP:  lambda: self._jmp(operands),
            MathaOpcode.JZ:   lambda: self._jz(operands),
            MathaOpcode.JNZ:  lambda: self._jnz(operands),
            MathaOpcode.CALL: lambda: self._call(operands),
            MathaOpcode.RET:  lambda: self._ret(),
            MathaOpcode.RETURN: lambda: self._return(operands),
            # 系统
            MathaOpcode.PRINT: lambda: self._print(operands),
            MathaOpcode.ERROR: lambda: self._error(operands),
            MathaOpcode.HALT:  lambda: self._halt(),
        }

        handler = handlers.get(op)
        if handler:
            handler()
        else:
            raise RuntimeError(f"未知指令: 0x{op:02X}")

    # ===== 指令实现 =====

    def _push_int(self, operands):
        idx = operands[0]
        self.stack.append(self.bc.constants[idx])

    def _push_float(self, operands):
        idx = operands[0]
        self.stack.append(self.bc.constants[idx])

    def _push_str(self, operands):
        idx = operands[0]
        self.stack.append(self.bc.constants[idx])

    def _push_base2(self, operands):
        idx = operands[0]
        self.stack.append(self.bc.constants[idx])

    def _push_base3(self, operands):
        idx = operands[0]
        self.stack.append(self.bc.constants[idx])

    def _push_local(self, operands):
        name = operands[0]
        self.stack.append(self.locals.get(name, 0))

    def _push_global(self, operands):
        name = operands[0]
        self.stack.append(self.globals.get(name, 0))

    def _store_local(self, operands):
        name = operands[0]
        self.locals[name] = self.stack.pop()

    def _store_global(self, operands):
        name = operands[0]
        self.globals[name] = self.stack.pop()

    def _arith(self, op, fn):
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.append(fn(self._to_float(a), self._to_float(b)))

    def _unary(self, fn):
        a = self.stack.pop()
        self.stack.append(fn(a))

    def _compare(self, fn):
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.append(1 if fn(self._to_float(a), self._to_float(b)) else 0)

    def _logical(self, fn):
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.append(1 if fn(self._resolve(a), self._resolve(b)) else 0)

    def _list_push(self):
        val = self.stack.pop()
        lst = self.stack.pop()
        lst.append(val)
        self.stack.append(lst)

    def _list_get(self):
        idx = int(self.stack.pop())
        lst = self.stack.pop()
        self.stack.append(lst[idx])

    def _jmp(self, operands):
        label = operands[0]
        target = self.bc.functions.get(label, self.pc)
        self.pc = target

    def _jz(self, operands):
        label = operands[0]
        val = self.stack.pop()
        if not val:
            self.pc = self.bc.functions.get(label, self.pc)

    def _jnz(self, operands):
        label = operands[0]
        val = self.stack.pop()
        if val:
            self.pc = self.bc.functions.get(label, self.pc)

    def _call(self, operands):
        func_name = operands[0]
        arg_count = operands[1] if len(operands) > 1 else 0
        # 保存当前上下文
        saved_pc = self.pc
        saved_stack = self.stack[:]
        saved_locals = self.locals.copy()

        # 获取函数字节码并执行
        func_bc = self.bc.functions.get(f'_{func_name}_code')
        if func_bc:
            old_bc = self.bc
            self.bc = func_bc
            self.pc = 0
            self.run()
            result = self.stack[-1] if self.stack else None
            self.bc = old_bc
        else:
            # 内建函数
            builtin = self._builtin_funcs.get(func_name)
            if builtin:
                args = self.stack[-arg_count:] if arg_count else []
                result = builtin(*args)
            else:
                raise RuntimeError(f"函数未找到: {func_name}")

        # 恢复上下文（结果留在栈上）
        self.stack = saved_stack + ([result] if result is not None else [])
        self.locals = saved_locals
        self.pc = saved_pc

    def _ret(self):
        self.running = False

    def _return(self, operands):
        result = self.stack[-1] if self.stack else None
        self._ret()

    def _print(self, operands):
        idx = operands[0]
        val = self.bc.constants[idx]
        print(self._resolve(val))

    def _error(self, operands):
        idx = operands[0]
        msg = self.bc.constants[idx]
        raise RuntimeError(str(msg))

    def _halt(self):
        self.running = False


# ============================================================
# 入口
# ============================================================

def main():
    """测试 MathaVM"""
    vm = MathaVM()

    # 测试: 2 + 3 = 5
    bc = MathaBytecode()
    c0 = bc.add_constant(2)
    c1 = bc.add_constant(3)
    bc.emit(MathaOpcode.PUSH_INT, c0)
    bc.emit(MathaOpcode.PUSH_INT, c1)
    bc.emit(MathaOpcode.ADD)
    bc.emit(MathaOpcode.PRINT, 0)  # 打印栈顶（常量0是格式占位）
    bc.emit(MathaOpcode.HALT)

    result = vm.run(bc)
    print(f"2 + 3 = {result}")

    # 测试 sin(π/2) = 1
    bc2 = MathaBytecode()
    pi_half = bc2.add_constant(vm._PI / 2.0)
    bc2.emit(MathaOpcode.PUSH_FLOAT, pi_half)
    bc2.emit(MathaOpcode.SIN)
    bc2.emit(MathaOpcode.PRINT, 0)
    bc2.emit(MathaOpcode.HALT)

    result2 = vm.run(bc2)
    print(f"sin(π/2) = {result2}")

    # 测试 factorial(5) = 120
    bc3 = MathaBytecode()
    bc3.emit(MathaOpcode.PUSH_INT, bc3.add_constant(5))
    bc3.emit(MathaOpcode.FACTORIAL)
    bc3.emit(MathaOpcode.PRINT, 0)
    bc3.emit(MathaOpcode.HALT)

    result3 = vm.run(bc3)
    print(f"5! = {result3}")


if __name__ == '__main__':
    main()
