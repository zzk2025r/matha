# -*- coding: utf-8 -*-
"""
Matha 三进制编译器 v2 — 支持函数定义与递归
==========================================
架构：.matha → Lexer → AST → 两阶段字节码生成 → M3V字节码
  Phase 1: 收集所有函数定义，编译为独立字节码
  Phase 2: 编译主程序（调用函数通过 CALL + 函数名）
  M3V VM 在加载时注册所有函数，调用时查找执行
"""

import sys
import os

from base3_matha import Base3, Base2, Base10, char_to_trinary
from lexer_matha import MathaLexer, Token


# ============================================================
# AST 节点
# ============================================================

class ASTNode:
    def __init__(self, node_type, trinary=None):
        self.type = node_type
        self.trinary = trinary
class NumLiteral(ASTNode):
    def __init__(self, value, is_int=False, trinary=None):
        super().__init__('NumLiteral', trinary)
        self.value = value
        self.is_int = is_int

class StrLiteral(ASTNode):
    def __init__(self, value, trinary=None):
        super().__init__('StrLiteral', trinary)
        self.value = value

class VarRef(ASTNode):
    def __init__(self, name, trinary=None):
        super().__init__('VarRef', trinary)
        self.name = name

class BinOp(ASTNode):
    def __init__(self, op, left, right, trinary=None):
        super().__init__('BinOp', trinary)
        self.op = op
        self.left = left
        self.right = right

class UnaryOp(ASTNode):
    def __init__(self, op, operand, trinary=None):
        super().__init__('UnaryOp', trinary)
        self.op = op
        self.operand = operand

class FuncCall(ASTNode):
    def __init__(self, func, args, trinary=None):
        super().__init__('FuncCall', trinary)
        self.func = func
        self.args = args

class FuncDef(ASTNode):
    def __init__(self, name, params, param_types, ret_type, body, trinary=None):
        super().__init__('FuncDef', trinary)
        self.name = name
        self.params = params
        self.param_types = param_types
        self.ret_type = ret_type
        self.body = body

class LetBinding(ASTNode):
    def __init__(self, name, value, trinary=None):
        super().__init__('LetBinding', trinary)
        self.name = name
        self.value = value

class IfExpr(ASTNode):
    def __init__(self, cond, then_branch, else_branch, trinary=None):
        super().__init__('IfExpr', trinary)
        self.cond = cond
        self.then_branch = then_branch
        self.else_branch = else_branch

class LambdaExpr(ASTNode):
    def __init__(self, params, body, trinary=None):
        super().__init__('LambdaExpr', trinary)
        self.params = params
        self.body = body

class Program(ASTNode):
    def __init__(self, declarations, trinary=None):
        super().__init__('Program', trinary)
        self.declarations = declarations

class ModuleBlock(ASTNode):
    def __init__(self, name, declarations, trinary=None):
        super().__init__('ModuleBlock', trinary)
        self.name = name
        self.declarations = declarations

class PrintStmt(ASTNode):
    """[expr] 语句：求值并打印"""
    def __init__(self, expr, trinary=None):
        super().__init__('PrintStmt', trinary)
        self.expr = expr


# ============================================================
# M3V 操作码
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
    FUNC_REG  = 0x90   # 注册函数定义 (name)
    FUNC_CALL = 0x91   # 调用注册函数 (nargs)
    LIST_NEW  = 0x92; LIST_PUSH = 0x93; LIST_GET = 0x94
    PRINT = 0xA0; INPUT = 0xA1; ERROR = 0xA2; HALT = 0xFF


# ============================================================
# M3V 字节码容器
# ============================================================

class M3VBytecode:
    def __init__(self):
        self.instructions = []
        self.constants = []
        self.functions = {}   # name → list of instructions
        self.globals = {}

    def emit(self, opcode, *operands):
        pos = len(self.instructions)
        self.instructions.append((opcode, operands))
        return pos

    def emit_trinary_const(self, value):
        idx = len(self.constants)
        if isinstance(value, Base3):
            self.constants.append(('trinary', value.digits[:]))
        elif isinstance(value, str):
            self.constants.append(('string', value))
        elif isinstance(value, (int, float)):
            self.constants.append(('number', value))
        return idx

    @staticmethod
    def _instr_byte_len(op, operands):
        """计算单条指令的字节长度"""
        n = 1  # opcode
        if isinstance(operands, int):
            n += 4
        else:
            for operand in operands:
                if isinstance(operand, int):
                    n += 4
                elif isinstance(operand, str):
                    n += len(operand.encode('utf-8')) + 3  # 2-byte length prefix + null terminator
        return n

    def register_function(self, name, params, body_instructions):
        """注册函数字节码"""
        body_len = sum(M3VBytecode._instr_byte_len(op, ops) for op, ops in body_instructions)
        self.functions[name] = (params, body_instructions, body_len)

    def to_bytes(self) -> bytes:
        buf = bytearray()
        buf.extend(b'M3V')
        buf.append(1)  # version

        # 函数定义（先写函数，再写常量，再写主指令）
        buf.extend(len(self.functions).to_bytes(4, 'big'))
        for name, (params, body, body_len) in self.functions.items():
            encoded_name = name.encode('utf-8')
            buf.extend(len(encoded_name).to_bytes(2, 'big'))
            buf.extend(encoded_name)
            buf.append(0)  # null terminator
            buf.extend(len(params).to_bytes(4, 'big'))
            for p in params:
                enc_p = p.encode('utf-8')
                buf.extend(len(enc_p).to_bytes(2, 'big'))
                buf.extend(enc_p)
                buf.append(0)  # null terminator
            buf.extend(body_len.to_bytes(4, 'big'))
            for op, operands in body:
                buf.append(op)
                # operands may be a tuple or a single int
                if isinstance(operands, int):
                    buf.extend(operands.to_bytes(4, 'big', signed=True))
                else:
                    for operand in operands:
                        if isinstance(operand, int):
                            buf.extend(operand.to_bytes(4, 'big', signed=True))
                        elif isinstance(operand, str):
                            op_encoded = operand.encode('utf-8') + b'\x00'
                            buf.extend(len(op_encoded).to_bytes(2, 'big'))
                            buf.extend(op_encoded)

        # 常量池
        buf.extend(len(self.constants).to_bytes(4, 'big'))
        for ctype, cval in self.constants:
            if ctype == 'trinary':
                buf.append(0x03)
                buf.extend(bytes(cval))
            elif ctype == 'string':
                encoded = cval.encode('utf-8')
                buf.append(0x02)
                buf.extend(len(encoded).to_bytes(2, 'big'))
                buf.extend(encoded)
            elif ctype == 'number':
                buf.append(0x01)
                buf.extend(int(cval).to_bytes(4, 'big', signed=True))

        # 主指令
        buf.extend(len(self.instructions).to_bytes(4, 'big'))
        for op, operands in self.instructions:
            buf.append(op)
            if isinstance(operands, int):
                buf.extend(operands.to_bytes(4, 'big', signed=True))
            else:
                for operand in operands:
                    if isinstance(operand, int):
                        buf.extend(operand.to_bytes(4, 'big', signed=True))
                    elif isinstance(operand, str):
                        encoded = operand.encode('utf-8') + b'\x00'
                        buf.extend(len(encoded).to_bytes(2, 'big'))
                        buf.extend(encoded)

        return bytes(buf)


# ============================================================
# 三进制编译器
# ============================================================

class MathaCompiler:
    def __init__(self):
        self.bytecode = M3VBytecode()

    def compile(self, source: str) -> bytes:
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        ast = self.parse(tokens)
        self._compile_program(ast)
        return self.bytecode.to_bytes()

    def parse(self, tokens: list) -> Program:
        self._tokens = tokens
        self._pos = 0
        return self._parse_program()

    def _peek(self):
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _peek_after(self, offset=1):
        pos = self._pos + offset
        if pos < len(self._tokens):
            return self._tokens[pos]
        return None

    def _is_lambda(self) -> bool:
        """检查当前位置是否是 lambda 表达式 (params) => body"""
        pos = self._pos
        # 跳过参数（ID 和逗号），停在 ')' 前不消耗
        while pos < len(self._tokens):
            tok = self._tokens[pos]
            if tok.type == 'PUNCT' and tok.value == ')':
                break  # 停在 ')' 位置，不推进
            if tok.type == 'ID':
                pos += 1
            elif tok.type == 'COMMA':
                pos += 1
            else:
                return False
        else:
            return False
        # 检查 ')' 后是否有 '=>'
        if pos + 1 >= len(self._tokens):
            return False
        return self._tokens[pos + 1].type == 'LAMBDA'

    def _consume(self):
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type_):
        tok = self._peek()
        if tok is None or tok.type != type_:
            raise SyntaxError(f"期望 {type_}, 得到 {tok.type if tok else 'EOF'}")
        return self._consume()

    def _expect_kw(self, value):
        """期望一个值为 value 的关键词 token（ID 或 _KW）"""
        tok = self._peek()
        if tok is None:
            raise SyntaxError(f"期望 {value!r}, 得到 EOF")
        if tok.value == value or tok.type == f'{value}_KW':
            return self._consume()
        raise SyntaxError(f"期望 {value!r}, 得到 {tok.value!r}")

    def _parse_program(self) -> Program:
        decls = []
        while self._peek() is not None:
            decls.append(self._parse_declaration())
        return Program(decls)

    def _parse_declaration(self):
        tok = self._peek()
        if tok is None:
            return None
        if tok.type == 'func_KW':
            return self._parse_func_def()
        elif tok.type == 'let_KW':
            return self._parse_let()
        elif tok.type == 'module_KW':
            return self._parse_module_block()
        elif tok.type == 'PUNCT' and tok.value == '[':
            return self._parse_print_stmt()
        elif tok.type == 'PUNCT' and tok.value == '{':
            # Skip nested block (e.g. #100：{...})
            self._skip_block()
            return None
        else:
            expr = self._parse_or()
            self._consume_semicolon()
            return expr

    def _skip_block(self):
        """跳过匹配的 { ... } 块"""
        self._expect('PUNCT')  # consume {
        depth = 1
        while self._peek() and depth > 0:
            tok = self._peek()
            if tok.value == '{':
                depth += 1
                self._consume()
            elif tok.value == '}':
                depth -= 1
                if depth > 0:
                    self._consume()
            else:
                # Skip any non-brace token
                self._consume()

    def _parse_func_def(self) -> FuncDef:
        self._consume()  # func
        name_tok = self._expect('ID')
        name = name_tok.value
        tr = name_tok.trinary
        self._expect('PUNCT')  # (
        params = []
        param_types = {}
        while self._peek() and self._peek().type != 'PUNCT' and self._peek().value != ')':
            p = self._consume().value
            params.append(p)
            if self._peek() and self._peek().type == 'PUNCT' and self._peek().value == ':':
                self._consume()
                t = self._consume().value
                param_types[p] = t
            if self._peek() and self._peek().type == 'COMMA':
                self._consume()
        self._expect('PUNCT')  # )
        self._expect('ARROW')
        ret_type = self._consume().value
        # = is optional when lambda body follows directly
        if self._peek() and self._peek().type == 'OP' and self._peek().value == '=':
            self._consume()
        body = self._parse_or()
        return FuncDef(name, params, param_types, ret_type, body, tr)

    def _parse_let(self):
        self._consume()  # let
        name_tok = self._expect('ID')
        name = name_tok.value
        self._expect('OP')  # =
        value = self._parse_or()
        return LetBinding(name, value, name_tok.trinary)

    def _parse_or(self):
        left = self._parse_and()
        while self._peek() and self._peek().type == 'ID' and self._peek().value == 'or':
            self._consume()
            right = self._parse_and()
            left = BinOp('or', left, right)
        return left

    def _parse_and(self):
        left = self._parse_comparison()
        while self._peek() and self._peek().type == 'ID' and self._peek().value == 'and':
            self._consume()
            right = self._parse_comparison()
            left = BinOp('and', left, right)
        return left

    def _parse_comparison(self):
        left = self._parse_additive()
        cmp_ops = {'==', '!=', '<', '>', '<=', '>='}
        while self._peek() and self._peek().type in ('OP', 'CMP') and self._peek().value in cmp_ops:
            op = self._consume().value
            right = self._parse_additive()
            left = BinOp(op, left, right)
        return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while self._peek() and self._peek().type == 'OP' and self._peek().value in ('+', '-'):
            op = self._consume().value
            right = self._parse_multiplicative()
            left = BinOp(op, left, right)
        return left

    def _parse_multiplicative(self):
        left = self._parse_unary()
        while self._peek() and self._peek().type == 'OP' and self._peek().value in ('*', '/', '%'):
            op = self._consume().value
            right = self._parse_unary()
            left = BinOp(op, left, right)
        return left

    def _parse_unary(self):
        if self._peek() and self._peek().type == 'OP' and self._peek().value in ('-', 'not'):
            op = self._consume().value
            operand = self._parse_unary()
            return UnaryOp(op, operand)
        return self._parse_primary()

    def _parse_primary(self):
        tok = self._peek()
        if tok is None:
            raise SyntaxError("意外的表达式结束")

        if tok.type == 'NUM':
            self._consume()
            is_int = '.' not in tok.value and 'e' not in tok.value.lower()
            return NumLiteral(float(tok.value) if '.' in tok.value else int(tok.value), is_int)

        elif tok.type == 'STRING':
            self._consume()
            return StrLiteral(tok.value)

        elif tok.type == 'ID':
            name = self._consume().value
            tr = tok.trinary
            if self._peek() and self._peek().type == 'PUNCT' and self._peek().value == '(':
                return self._parse_func_call(name, tr)
            elif self._peek() and self._peek().type == 'LAMBDA':
                return self._parse_lambda(name, tr)
            elif name == 'let' and self._peek() and self._peek().type == 'ID':
                return self._parse_let_expr()
            elif name == 'if':
                return self._parse_if_expr()
            else:
                return VarRef(name, tr)

        elif tok.type == 'if_KW':
            return self._parse_if_expr()

        elif tok.type == 'PUNCT' and tok.value == '(':
            self._consume()
            # 检查是否为 lambda：(params) => body
            if self._is_lambda():
                params = []
                while self._peek() and self._peek().type == 'ID':
                    params.append(self._consume().value)
                    if self._peek() and self._peek().type == 'COMMA':
                        self._consume()
                self._expect('PUNCT')  # consume ')'
                self._consume()  # consume '=>'
                return LambdaExpr(params, self._parse_or(), tok.trinary)
            # 普通括号表达式
            expr = self._parse_or()
            self._expect('PUNCT')
            return expr

        elif tok.type in ('真', '假') or (tok.type == 'ID' and tok.value in ('真', '假')):
            self._consume()
            val = 1.0 if tok.value == '真' else 0.0
            return NumLiteral(val)

        else:
            self._consume()
            raise SyntaxError(f"意外的 token: {tok.value!r}")

    def _parse_func_call(self, name, tr) -> FuncCall:
        self._expect('PUNCT')  # (
        args = []
        while self._peek() and self._peek().type != 'PUNCT':
            args.append(self._parse_or())
            if self._peek() and self._peek().type == 'COMMA':
                self._consume()
        self._expect('PUNCT')  # )
        return FuncCall(name, args, tr)

    def _parse_lambda(self, param_hint, tr) -> LambdaExpr:
        self._consume()  # =>
        params = [param_hint] if param_hint else []
        body = self._parse_or()
        return LambdaExpr(params, body, tr)

    def _parse_let_expr(self):
        self._consume()  # let
        name_tok = self._expect('ID')
        self._expect('OP')  # =
        value = self._parse_or()
        self._expect_kw('in')
        body = self._parse_or()
        return LetBinding(body, value)  # simplified

    def _parse_if_expr(self) -> IfExpr:
        self._consume()  # if
        cond = self._parse_or()
        self._expect_kw('then')
        then_branch = self._parse_or()
        else_branch = NumLiteral(0.0)
        if self._peek() and (self._peek().value == 'else' or self._peek().type == 'else_KW'):
            self._consume()
            else_branch = self._parse_or()
        return IfExpr(cond, then_branch, else_branch)

    def _consume_semicolon(self):
        if self._peek() and self._peek().type == 'SEMI':
            self._consume()

    def _parse_module_block(self) -> ModuleBlock:
        self._consume()  # module
        name_tok = self._expect('ID')
        name = name_tok.value
        self._expect('PUNCT')  # {
        decls = []
        depth = 1  # we already consumed the opening {
        while self._peek() and depth > 0:
            tok = self._peek()
            if tok.value == '{':
                depth += 1
                self._consume()
            elif tok.value == '}':
                depth -= 1
                self._consume()
                if depth == 0:
                    break
            else:
                decls.append(self._parse_declaration())
        return ModuleBlock(name, decls)

    def _parse_print_stmt(self) -> PrintStmt:
        self._consume()  # [
        expr = self._parse_or()
        self._expect('PUNCT')  # ]
        return PrintStmt(expr)

    # ---- 两阶段编译 ----

    def _compile_program(self, prog: Program):
        """Phase 1: 编译函数定义, Phase 2: 编译主程序"""
        # 展平所有声明（包括 module 块内的）
        all_decls = []
        for d in prog.declarations:
            if isinstance(d, ModuleBlock):
                all_decls.extend(d.declarations)
            else:
                all_decls.append(d)

        # Phase 1: 收集并编译函数
        func_defs = [d for d in all_decls if isinstance(d, FuncDef)]
        main_body = [d for d in all_decls if not isinstance(d, FuncDef)]

        for func in func_defs:
            func_instrs = self._compile_func_body(func)
            self.bytecode.register_function(func.name, func.params, func_instrs)

        # Phase 2: 编译主程序
        for decl in main_body:
            self._emit_stmt(decl)

    def _compile_func_body(self, func: FuncDef) -> list:
        """编译函数体为指令列表（独立编译单元）"""
        # 临时保存并恢复 bytecode
        old_bc = self.bytecode
        func_bc = M3VBytecode()
        func_bc.constants = old_bc.constants  # 共享常量池，确保索引一致
        self.bytecode = func_bc
        # 参数名注册到全局（供 PUSH_GLOBAL 读取参数值），初始为 0.0
        for param in func.params:
            func_bc.globals[param] = 0.0
        # 函数体可能是 LambdaExpr，提取其 body 编译
        body_expr = func.body.body if isinstance(func.body, LambdaExpr) else func.body
        self._emit_expr(body_expr)
        # 返回指令
        func_bc.emit(M3VOpcodes.RETURN, 0)
        result = func_bc.instructions
        self.bytecode = old_bc
        return result

    def _emit_stmt(self, stmt):
        if isinstance(stmt, FuncDef):
            pass  # 已在 Phase 1 处理
        elif isinstance(stmt, LetBinding):
            self._emit_expr(stmt.value)
            self.bytecode.emit(M3VOpcodes.STORE_GLOBAL, stmt.name)
        elif isinstance(stmt, PrintStmt):
            self._emit_expr(stmt.expr)
            self.bytecode.emit(M3VOpcodes.PRINT)
        else:
            self._emit_expr(stmt)
            self.bytecode.emit(M3VOpcodes.PRINT)

    def _emit_expr(self, expr):
        if isinstance(expr, NumLiteral):
            idx = self.bytecode.emit_trinary_const(expr.value)
            self.bytecode.emit(M3VOpcodes.PUSH_NUM, idx)

        elif isinstance(expr, StrLiteral):
            idx = self.bytecode.emit_trinary_const(expr.value)
            self.bytecode.emit(M3VOpcodes.PUSH_STR, idx)

        elif isinstance(expr, VarRef):
            self.bytecode.emit(M3VOpcodes.PUSH_GLOBAL, expr.name)

        elif isinstance(expr, BinOp):
            self._emit_expr(expr.left)
            self._emit_expr(expr.right)
            op_map = {
                '+': M3VOpcodes.ADD, '-': M3VOpcodes.SUB,
                '*': M3VOpcodes.MUL, '/': M3VOpcodes.DIV,
                '%': M3VOpcodes.MOD, '^': M3VOpcodes.POW,
                '==': M3VOpcodes.EQ, '!=': M3VOpcodes.NEQ,
                '<': M3VOpcodes.LT, '>': M3VOpcodes.GT,
                '<=': M3VOpcodes.LEQ, '>=': M3VOpcodes.GEQ,
                'and': M3VOpcodes.AND, 'or': M3VOpcodes.OR,
            }
            op = op_map.get(expr.op, M3VOpcodes.ADD)
            self.bytecode.emit(op)

        elif isinstance(expr, UnaryOp):
            self._emit_expr(expr.operand)
            if expr.op == '-':
                self.bytecode.emit(M3VOpcodes.NEG)
            elif expr.op == 'not':
                self.bytecode.emit(M3VOpcodes.NOT)

        elif isinstance(expr, FuncCall):
            self.bytecode.emit(M3VOpcodes.PUSH_GLOBAL, expr.func)
            for arg in reversed(expr.args):
                self._emit_expr(arg)
            self.bytecode.emit(M3VOpcodes.FUNC_CALL, len(expr.args))

        elif isinstance(expr, IfExpr):
            self._emit_expr(expr.cond)
            else_pos = self.bytecode.emit(M3VOpcodes.JZ, 0)
            self._emit_expr(expr.then_branch)
            jump_pos = self.bytecode.emit(M3VOpcodes.JMP, 0)
            else_target = len(self.bytecode.instructions)
            self.bytecode.instructions[else_pos] = (M3VOpcodes.JZ, else_target)
            self._emit_expr(expr.else_branch)
            jump_target = len(self.bytecode.instructions)
            self.bytecode.instructions[jump_pos] = (M3VOpcodes.JMP, jump_target)

        elif isinstance(expr, LambdaExpr):
            self.bytecode.emit(M3VOpcodes.PUSH_NUM, 0)  # 占位

        else:
            raise SyntaxError(f"不支持的 AST 节点: {expr.type}")


# ============================================================
# 主入口
# ============================================================

def compile_matha(source: str) -> bytes:
    compiler = MathaCompiler()
    return compiler.compile(source)


if __name__ == '__main__':
    print("=== Matha 三进制编译器 v2 测试 ===")

    source = """
    func 加(a: Float, b: Float) -> Float = (a, b) => a + b
    func 阶乘(n: Int) -> Int = (n) => if n <= 1 then 1 else n * 阶乘(n - 1)
    加(3.0, 4.0)
    """
    bc = compile_matha(source)
    print(f"编译成功! 字节码长度: {len(bc)} 字节")
    print(f"魔数: {bc[:3]}")
    print(f"常量池大小: {int.from_bytes(bc[4:8], 'big')}")

    # 显示函数定义
    print(f"函数列表: {list(bc[8:12])}")

    print("\n=== 编译器 v2 运行正常 ===")
