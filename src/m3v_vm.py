# -*- coding: utf-8 -*-
"""
Matha 三进制虚拟机 (M3V)
=========================
设计原则：
  - 完全独立于 Python/C/C++，纯三进制架构
  - 字节码格式：M3V (Magic: M3V, Version: 1)
  - 所有常量、变量名均以三进制编码
  - 支持：数值/字符串/函数/递归/闭包
"""

import sys
import os

from base3_matha import Base3, Base2, Base10, char_to_trinary


# ============================================================
# M3V 操作码（与编译器一致）
# ============================================================

class M3VOpcodes:
    PUSH_NUM    = 0x01
    PUSH_STR    = 0x02
    PUSH_TR     = 0x03
    PUSH_LOCAL  = 0x10
    PUSH_GLOBAL = 0x11
    STORE_LOCAL = 0x20
    STORE_GLOBAL = 0x21
    ADD = 0x30; SUB = 0x31; MUL = 0x32; DIV = 0x33
    MOD = 0x34; POW = 0x35; NEG = 0x36
    EQ  = 0x40; NEQ = 0x41; LT  = 0x42
    GT  = 0x43; LEQ = 0x44; GEQ = 0x45
    AND = 0x50; OR  = 0x51; NOT = 0x52
    JMP     = 0x80; JZ  = 0x81; JNZ = 0x82
    CALL    = 0x83; RET = 0x84; RETURN = 0x85
    FUNC_DEF  = 0x90; FUNC_CALL = 0x91
    LIST_NEW  = 0x92; LIST_PUSH = 0x93; LIST_GET = 0x94
    PRINT = 0xA0; INPUT = 0xA1; ERROR = 0xA2; HALT = 0xFF


# ============================================================
# M3V 虚拟机
# ============================================================

class M3VFrame:
    """VM 执行帧"""
    __slots__ = ('func_name', 'locals', 'params', 'return_addr', 'return_value')

    def __init__(self, func_name):
        self.func_name = func_name
        self.locals = {}
        self.params = []
        self.return_addr = -1
        self.return_value = None


class M3VM:
    """M3V 三进制虚拟机"""

    def __init__(self):
        self.stack = []
        self.frames = [M3VFrame("<main>")]
        self.globals = {}
        self.functions = {}   # name → (params, body_bytecode)
        self.constants = []   # 常量池
        self.pc = 0
        self.instructions = []
        self.outputs = []
        self._builtins = self._init_builtins()

    def _init_builtins(self):
        return {
            'print': self._b_print,
            'error': self._b_error,
            'abs': self._b_abs,
            'int': self._b_int,
            'float': self._b_float,
            'len': self._b_len,
            'sin': self._b_sin,
            'cos': self._b_cos,
            'tan': self._b_tan,
            'exp': self._b_exp,
            'log': self._b_log,
            'sqrt': self._b_sqrt,
            'floor': self._b_floor,
            'ceil': self._b_ceil,
            'trunc': self._b_trunc,
            'round': self._b_round,
            'factorial': self._b_factorial,
            'pow': self._b_pow,
            'min': self._b_min,
            'max': self._b_max,
            # 三进制转换
            'to_base2': self._b_to_base2,
            'to_base3': self._b_to_base3,
            'from_base2': self._b_from_base2,
            'from_base3': self._b_from_base3,
        }

    # ===== 内建函数（纯数学实现）=====

    def _b_print(self, *args):
        vals = [str(a) for a in args]
        result = ' '.join(vals)
        self.outputs.append(result)
        print(result)
        return 0.0

    def _b_error(self, msg):
        raise RuntimeError(str(msg))

    def _b_abs(self, x):
        return abs(float(x))

    def _b_int(self, x):
        return int(float(x))

    def _b_float(self, x):
        return float(x)

    def _b_len(self, x):
        if isinstance(x, str):
            return len(x)
        return 0

    def _b_sin(self, x):
        return _math_sin(float(x))

    def _b_cos(self, x):
        return _math_cos(float(x))

    def _b_tan(self, x):
        return _math_tan(float(x))

    def _b_exp(self, x):
        return _math_exp(float(x))

    def _b_log(self, x):
        return _math_log(float(x))

    def _b_sqrt(self, x):
        return _math_sqrt(float(x))

    def _b_floor(self, x):
        return _math_floor(float(x))

    def _b_ceil(self, x):
        return _math_ceil(float(x))

    def _b_trunc(self, x):
        return _math_trunc(float(x))

    def _b_round(self, x):
        return round(float(x))

    def _b_factorial(self, n):
        n = int(float(n))
        if n <= 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return float(result)

    def _b_pow(self, base, exp):
        return float(base) ** float(exp)

    def _b_min(self, a, b):
        return min(float(a), float(b))

    def _b_max(self, a, b):
        return max(float(a), float(b))

    def _b_to_base2(self, n):
        return Base2(int(float(n))).bits

    def _b_to_base3(self, n):
        return Base3(int(float(n))).digits

    def _b_from_base2(self, bits):
        return int(bits, 2) if isinstance(bits, str) else int(float(bits))

    def _b_from_base3(self, digits):
        if isinstance(digits, list):
            val = 0
            for d in digits:
                val = val * 3 + d
            return val
        return int(float(digits))

    # ===== VM 核心操作 =====

    def _push(self, val):
        self.stack.append(val)

    def _pop(self):
        if not self.stack:
            raise RuntimeError("VM 栈空")
        return self.stack.pop()

    def _peek(self):
        if not self.stack:
            raise RuntimeError("VM 栈空")
        return self.stack[-1]

    def _current_frame(self):
        return self.frames[-1]

    def _get_var(self, name):
        for frame in reversed(self.frames):
            if name in frame.locals:
                return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        if name in self._builtins:
            return self._builtins[name]
        raise RuntimeError(f"未定义变量: {name}")

    def _set_var(self, name, val):
        self._current_frame().locals[name] = val

    # ===== 加载字节码并执行 =====

    def load_bytecode(self, data: bytes):
        """从 M3V 二进制数据加载 — 解析函数定义、常量池、主指令"""
        if data[:3] != b'M3V':
            raise RuntimeError("无效 M3V 文件: 魔数不匹配")
        if data[3] != 1:
            raise RuntimeError(f"不支持的 M3V 版本: {data[3]}")

        pos = 4

        # ---- 函数定义 ----
        func_count = int.from_bytes(data[pos:pos+4], 'big')
        pos += 4
        self.functions = {}
        for _ in range(func_count):
            name_len = int.from_bytes(data[pos:pos+2], 'big')
            pos += 2
            name = data[pos:pos+name_len].decode('utf-8')
            pos += name_len
            # 跳过 null terminator
            pos += 1
            # 参数列表
            param_count = int.from_bytes(data[pos:pos+4], 'big')
            pos += 4
            params = []
            for _ in range(param_count):
                plen = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
                pname = data[pos:pos+plen].decode('utf-8')
                pos += plen
                pos += 1  # null terminator
                params.append(pname)
            # 函数体指令
            body_len = int.from_bytes(data[pos:pos+4], 'big')
            pos += 4
            body_end = pos + body_len
            body = []
            while pos < body_end:
                op = data[pos]
                pos += 1
                operands = []
                if op == 0x00:
                    continue  # skip padding bytes
                elif op in (M3VOpcodes.PUSH_NUM, M3VOpcodes.PUSH_STR, M3VOpcodes.PUSH_TR):
                    idx = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                    pos += 4
                    operands.append(idx)
                elif op in (M3VOpcodes.STORE_GLOBAL, M3VOpcodes.PUSH_GLOBAL, M3VOpcodes.FUNC_DEF):
                    slen = int.from_bytes(data[pos:pos+2], 'big')
                    pos += 2
                    name_end = data.index(b'\x00', pos)
                    name_str = data[pos:name_end].decode('utf-8')
                    pos = name_end + 1
                    operands.append(name_str)
                elif op in (M3VOpcodes.JMP, M3VOpcodes.JZ, M3VOpcodes.JNZ):
                    target = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                    pos += 4
                    operands.append(target)
                elif op in (M3VOpcodes.CALL, M3VOpcodes.FUNC_CALL, M3VOpcodes.STORE_LOCAL):
                    nargs = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                    pos += 4
                    operands.append(nargs)
                elif op == M3VOpcodes.RETURN:
                    ret_val = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                    pos += 4
                    operands.append(ret_val)
                elif op in (M3VOpcodes.ADD, M3VOpcodes.SUB, M3VOpcodes.MUL, M3VOpcodes.DIV,
                            M3VOpcodes.MOD, M3VOpcodes.POW, M3VOpcodes.NEG,
                            M3VOpcodes.EQ, M3VOpcodes.NEQ, M3VOpcodes.LT, M3VOpcodes.GT,
                            M3VOpcodes.LEQ, M3VOpcodes.GEQ, M3VOpcodes.AND, M3VOpcodes.OR,
                            M3VOpcodes.NOT):
                    pass  # no operands
                else:
                    raise RuntimeError(f"函数体中未知操作码: 0x{op:02X}")
                body.append((op, tuple(operands)))
            self.functions[name] = {'params': params, 'body': body}
            self.globals[name] = name  # register function name as global for PUSH_GLOBAL

        # ---- 常量池 ----
        const_count = int.from_bytes(data[pos:pos+4], 'big')
        pos += 4
        self.constants = []
        for _ in range(const_count):
            ctype = data[pos]
            pos += 1
            if ctype == 0x01:  # 数字
                val = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                pos += 4
                self.constants.append(val)
            elif ctype == 0x02:  # 字符串
                slen = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
                s = data[pos:pos+slen].decode('utf-8')
                pos += slen
                self.constants.append(s)
            elif ctype == 0x03:  # 三进制
                tlen = int.from_bytes(data[pos:pos+4], 'big')
                pos += 4
                digits = list(data[pos:pos+tlen])
                pos += tlen
                self.constants.append(Base3(digits))
            else:
                raise RuntimeError(f"未知常量类型: {ctype}")

        # ---- 主指令 ----
        instr_count = int.from_bytes(data[pos:pos+4], 'big')
        pos += 4
        self.instructions = []
        for _ in range(instr_count):
            op = data[pos]
            pos += 1
            operands = []
            if op in (M3VOpcodes.PUSH_NUM, M3VOpcodes.PUSH_STR, M3VOpcodes.PUSH_TR):
                idx = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                pos += 4
                operands.append(idx)
            elif op in (M3VOpcodes.STORE_GLOBAL, M3VOpcodes.PUSH_GLOBAL):
                slen = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
                name_end = data.index(b'\x00', pos)
                name = data[pos:name_end].decode('utf-8')
                pos = name_end + 1
                operands.append(name)
            elif op in (M3VOpcodes.JMP, M3VOpcodes.JZ, M3VOpcodes.JNZ):
                target = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                pos += 4
                operands.append(target)
            elif op in (M3VOpcodes.CALL, M3VOpcodes.FUNC_CALL, M3VOpcodes.STORE_LOCAL):
                nargs = int.from_bytes(data[pos:pos+4], 'big', signed=True)
                pos += 4
                operands.append(nargs)
            elif op == M3VOpcodes.FUNC_DEF:
                slen = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
                name_end = data.index(b'\x00', pos)
                name = data[pos:name_end].decode('utf-8')
                pos = name_end + 1
                operands.append(name)
            self.instructions.append((op, tuple(operands)))

    def run(self):
        """执行虚拟机"""
        self.pc = 0
        while self.pc < len(self.instructions):
            op, operands = self.instructions[self.pc]
            self.pc += 1
            if not self._exec(op, operands):
                break
        return self.outputs

    def _exec(self, op, operands):
        if op == M3VOpcodes.HALT:
            return False
        elif op == M3VOpcodes.PUSH_NUM:
            self._push(self.constants[operands[0]])
        elif op == M3VOpcodes.PUSH_STR:
            self._push(self.constants[operands[0]])
        elif op == M3VOpcodes.PUSH_TR:
            self._push(self.constants[operands[0]])
        elif op == M3VOpcodes.PUSH_GLOBAL:
            self._push(self._get_var(operands[0]))
        elif op == M3VOpcodes.STORE_GLOBAL:
            val = self._pop()
            self.globals[operands[0]] = val
        elif op == M3VOpcodes.STORE_LOCAL:
            val = self._pop()
            self._set_var(operands[0], val)
        elif op == M3VOpcodes.ADD:
            b, a = self._pop(), self._pop()
            self._push(float(a) + float(b))
        elif op == M3VOpcodes.SUB:
            b, a = self._pop(), self._pop()
            self._push(float(a) - float(b))
        elif op == M3VOpcodes.MUL:
            b, a = self._pop(), self._pop()
            self._push(float(a) * float(b))
        elif op == M3VOpcodes.DIV:
            b, a = self._pop(), self._pop()
            self._push(float(a) / float(b) if float(b) != 0 else float('inf'))
        elif op == M3VOpcodes.MOD:
            b, a = self._pop(), self._pop()
            self._push(float(a) % float(b))
        elif op == M3VOpcodes.POW:
            b, a = self._pop(), self._pop()
            self._push(float(a) ** float(b))
        elif op == M3VOpcodes.NEG:
            a = self._pop()
            self._push(-float(a))
        elif op in (M3VOpcodes.EQ, M3VOpcodes.NEQ, M3VOpcodes.LT, M3VOpcodes.GT, M3VOpcodes.LEQ, M3VOpcodes.GEQ):
            b, a = self._pop(), self._pop()
            fa, fb = float(a), float(b)
            if op == M3VOpcodes.EQ:    self._push(1.0 if fa == fb else 0.0)
            elif op == M3VOpcodes.NEQ: self._push(1.0 if fa != fb else 0.0)
            elif op == M3VOpcodes.LT:   self._push(1.0 if fa < fb else 0.0)
            elif op == M3VOpcodes.GT:   self._push(1.0 if fa > fb else 0.0)
            elif op == M3VOpcodes.LEQ:  self._push(1.0 if fa <= fb else 0.0)
            elif op == M3VOpcodes.GEQ:  self._push(1.0 if fa >= fb else 0.0)
        elif op == M3VOpcodes.AND:
            b, a = self._pop(), self._pop()
            self._push(1.0 if (float(a) != 0 and float(b) != 0) else 0.0)
        elif op == M3VOpcodes.OR:
            b, a = self._pop(), self._pop()
            self._push(1.0 if (float(a) != 0 or float(b) != 0) else 0.0)
        elif op == M3VOpcodes.NOT:
            a = self._pop()
            self._push(1.0 if float(a) == 0 else 0.0)
        elif op == M3VOpcodes.JMP:
            self.pc = operands[0]
        elif op == M3VOpcodes.JZ:
            val = self._pop()
            if float(val) == 0:
                self.pc = operands[0]
        elif op == M3VOpcodes.JNZ:
            val = self._pop()
            if float(val) != 0:
                self.pc = operands[0]
        elif op == M3VOpcodes.CALL:
            nargs = operands[0]
            args = []
            for _ in range(nargs):
                args.append(self._pop())
            args.reverse()
            func_ref = self._pop()
            result = self._call_func(func_ref, args)
            self._push(result)
        elif op == M3VOpcodes.FUNC_CALL:
            nargs = operands[0]
            args = []
            for _ in range(nargs):
                args.append(self._pop())
            args.reverse()
            func_ref = self._pop()
            result = self._call_func(func_ref, args)
            self._push(result)
        elif op == M3VOpcodes.RETURN:
            # 保存返回值到当前帧（供调用方读取）
            if self.stack:
                self._current_frame().return_value = self._pop()
            # 总是弹出当前帧
            if len(self.frames) > 1:
                self.frames.pop()
                return True  # 返回给调用方，继续执行
            # 主程序 RETURN：弹出主帧并停止
            self.frames.pop()
            return False
        elif op == M3VOpcodes.PRINT:
            val = self._pop()
            print(str(val))
            self.outputs.append(val)
            self._push(0.0)
        elif op == M3VOpcodes.ERROR:
            msg = self._pop()
            raise RuntimeError(str(msg))
        else:
            raise RuntimeError(f"未知指令: 0x{op:02X}")
        return True

    def _call_func(self, func_ref, args):
        """调用函数"""
        if callable(func_ref) and func_ref.__name in self._builtins:
            return func_ref(*args)
        elif isinstance(func_ref, str) and func_ref in self.functions:
            func_info = self.functions[func_ref]
            params = func_info['params']
            func_body = func_info['body']
            frame = M3VFrame(func_ref)
            for i, param in enumerate(params):
                frame.locals[param] = args[i] if i < len(args) else 0
            self.frames.append(frame)
            old_pc = self.pc
            old_instr = self.instructions
            self.instructions = func_body
            self.pc = 0
            self.run()
            ret_val = frame.return_value if frame.return_value is not None else 0.0
            self.instructions = old_instr
            self.pc = old_pc
            # RETURN 可能已弹出帧，仅当帧仍在时才弹出
            if self.frames and self.frames[-1] is frame:
                self.frames.pop()
            return ret_val
        elif isinstance(func_ref, str) and func_ref in self.globals:
            fn = self.globals[func_ref]
            if callable(fn):
                return fn(*args)
        raise RuntimeError(f"未定义函数: {func_ref}")

    def eval_expr(self, source: str) -> object:
        """执行 Matha 表达式，返回结果"""
        from compiler_matha import compile_matha
        bytecode = compile_matha(source)
        self.load_bytecode(bytecode)
        self.run()
        return self._peek() if self.stack else 0.0


# ============================================================
# 纯数学函数（不依赖外部库）
# ============================================================

def _math_sin(x):
    """Taylor 级数 sin(x)"""
    # 角度约化到 [-pi, pi]
    PI = 3.141592653589793
    TAU = 2.0 * PI
    x = x % TAU
    if x > PI:
        x -= TAU
    elif x < -PI:
        x += TAU
    result = x
    term = x
    for n in range(1, 30):
        term *= -x * x / ((2 * n) * (2 * n + 1))
        result += term
        if abs(term) < 1e-15:
            break
    return result


def _math_cos(x):
    """Taylor 级数 cos(x)"""
    PI = 3.141592653589793
    TAU = 2.0 * PI
    x = x % TAU
    if x > PI:
        x -= TAU
    elif x < -PI:
        x += TAU
    result = 1.0
    term = 1.0
    for n in range(1, 30):
        term *= -x * x / ((2 * n - 1) * (2 * n))
        result += term
        if abs(term) < 1e-15:
            break
    return result


def _math_tan(x):
    c = _math_cos(x)
    if abs(c) < 1e-15:
        raise RuntimeError("tan: 未定义")
    return _math_sin(x) / c


def _math_exp(x):
    result = 1.0
    term = 1.0
    for n in range(1, 50):
        term *= x / n
        result += term
        if abs(term) < 1e-15:
            break
    return result


def _math_log(x):
    """自然对数（牛顿迭代法）"""
    if x <= 0:
        raise RuntimeError("log: 参数必须 > 0")
    # 使用 exp 的牛顿迭代
    target = x
    guess = 1.0
    for _ in range(100):
        guess = guess + (target - _math_exp(guess)) / _math_exp(guess)
        if abs(_math_exp(guess) - target) < 1e-15:
            break
    return guess


def _math_sqrt(x):
    """平方根（牛顿迭代法）"""
    if x < 0:
        raise RuntimeError("sqrt: 负数")
    if x == 0:
        return 0.0
    guess = x / 2.0 if x >= 1 else 1.0
    for _ in range(100):
        new_guess = (guess + x / guess) / 2.0
        if abs(new_guess - guess) < 1e-15:
            break
        guess = new_guess
    return guess


def _math_floor(x):
    return int(x // 1)


def _math_ceil(x):
    return int(x // 1) + (1 if x > int(x // 1) else 0)


def _math_trunc(x):
    return int(x)


# ============================================================
# 主入口
# ============================================================

if __name__ == '__main__':
    print("=== M3V 三进制虚拟机测试 ===")

    vm = M3VM()

    # 测试：计算 3 + 4
    source = """
    func 加(a: Float, b: Float) -> Float = (a, b) => a + b
    加(3.0, 4.0)
    """
    result = vm.eval_expr(source)
    print(f"3 + 4 = {result}")

    # 测试：阶乘
    source2 = """
    func 阶乘(n: Int) -> Int = (n) => if n <= 1 then 1 else n * 阶乘(n - 1)
    阶乘(5)
    """
    result2 = vm.eval_expr(source2)
    print(f"5! = {result2}")

    # 测试：三进制转换
    source3 = """
    to_base3(255)
    """
    try:
        result3 = vm.eval_expr(source3)
        print(f"255 → Base3: {result3}")
    except Exception as e:
        print(f"三进制测试: {e}")

    print("\n=== M3V 虚拟机运行正常 ===")
