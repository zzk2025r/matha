# -*- coding: utf-8 -*-
"""
Matha 三进制词法器
==================
设计原则：
  - 字母/汉字 → 三进制编码
  - 零 Python 标准库依赖（仅用 re）
  - 支持：标识符（含中文）、数字、运算符、字符串、注释
"""

import sys
import os
import re

from base3_matha import Base3, Base2, Base10, register_chinese_chars, char_to_trinary


# ============================================================
# Token 类型
# ============================================================

class Token:
    __slots__ = ('type', 'value', 'trinary', 'line', 'col')

    def __init__(self, type_, value, trinary=None, line=0, col=0):
        self.type = type_
        self.value = value
        self.trinary = trinary  # 三进制编码
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, tr={self.trinary})"

    def __eq__(self, other):
        return self.type == other.type and self.value == other.value


# ============================================================
# 词法器
# ============================================================

class MathaLexer:
    """Matha 词法器 — 字母/汉字 → 三进制编码"""

    TOKEN_PATTERN = re.compile(r'''
        (?P<COMMENT>\(\*(.*?)\*\))                         |  # (* ... *) 注释
        (?P<LINE_COMMENT>\#[^\n]*)                            |  # # 行注释（至行尾，不含换行）
        (?P<STRING>"[^"\\]*(?:\\.[^"\\]*)*")               |  # 字符串
        (?P<FLOAT>-?\d+\.\d+[eE][+-]?\d+)                  |  # 浮点科学计数
        (?P<FLOAT2>-?\d+\.\d+)                               |  # 浮点数
        (?P<INT>-?\d+)                                      |  # 整数
        (?P<ID>[a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*) |  # 标识符（含中文）
        (?P<ARROW>\->)                                      |  # 箭头（类型标注）
        (?P<LAMBDA>=\>)                                    |  # lambda 箭头
        (?P<CMP><=|>=|==|!=)                               |  # 比较运算符
        (?P<OP>[+\-*/%=<>!&|^~])                           |  # 运算符
        (?P<QUESTION>\?)                                   |  # 条件三元
        (?P<COMMA>,)                                       |  # 逗号（必须在 PUNCT 之前）
        (?P<PUNCT>[();:{}\[\]：()])                          |  # 标点（含 [] 和全角冒号）
        (?P<SEMI>;)                                        |  # 分号
        (?P<WHITESPACE>\s+)                                 |  # 空白
    ''', re.VERBOSE | re.DOTALL)

    KEYWORDS = {
        'func', 'let', 'in', 'if', 'then', 'else', 'module',
        'rec', 'and', 'Bool', 'Int', 'Float', 'String', 'List',
        '真', '假', '错误', '返回', 'use', 'import', 'type',
        'match', 'case', 'while', 'for', 'break', 'continue',
        'try', 'catch', 'raise', 'class', 'struct', 'enum',
        'return', 'void', 'public', 'private', 'static', 'const',
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 0
        # 注册常用汉字
        self._register_common_chinese()

    def _register_common_chinese(self):
        """注册常用汉字到三进制表"""
        # 数学相关
        math_chars = '加减乘除等于不等大于小于正负零一二三四五六七八九十百千万亿'
        math_chars += '平方立方根号指数对数三角正弦余弦正切'
        math_chars += '函数变量常量参数返回类型模块编译'
        math_chars += '字母数字字符串列表字典集合'
        for ch in math_chars:
            char_to_trinary(ch)  # 触发注册

    def __iter__(self):
        while self.pos < len(self.source):
            m = self.TOKEN_PATTERN.match(self.source, self.pos)
            if not m:
                ch = self.source[self.pos]
                raise SyntaxError(f"无法识别的字符: {ch!r} at line {self.line} col {self.col}")
            self.pos = m.end()

            name = m.lastgroup
            value = m.group()

            if name == 'WHITESPACE':
                self.line += value.count('\n')
                continue
            if name == 'COMMENT':
                continue
            if name == 'LINE_COMMENT':
                # 如果注释行尾包含 {，需要继续消费直到匹配的 }
                # 注意：只消费到第一个匹配的 }，不跨 module 块
                if value.rstrip().endswith('{'):
                    depth = 1
                    while self.pos < len(self.source) and depth > 0:
                        ch = self.source[self.pos]
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                self.pos += 1
                                break
                        elif ch == '\n':
                            self.line += 1
                        self.pos += 1
                continue
            if name == 'OP':
                yield Token('OP', value, char_to_trinary(value[0]) if len(value) == 1 else None, self.line, self.col)
            elif name == 'CMP':
                yield Token('CMP', value, char_to_trinary(value[0]) if len(value) == 1 else None, self.line, self.col)
            elif name == 'ID' and value in self.KEYWORDS:
                yield Token(f"{value}_KW", value, char_to_trinary(value), self.line, self.col)
            elif name == 'ID':
                tr = char_to_trinary(value[0]) if len(value) == 1 else None
                yield Token('ID', value, tr, self.line, self.col)
            elif name in ('INT', 'FLOAT', 'FLOAT2'):
                yield Token('NUM', value, None, self.line, self.col)
            elif name == 'STRING':
                yield Token('STRING', value[1:-1], None, self.line, self.col)
            elif name in ('ARROW', 'LAMBDA', 'QUESTION', 'SEMI', 'COMMA', 'PUNCT'):
                yield Token(name, value, char_to_trinary(value[0]) if len(value) == 1 else None, self.line, self.col)
            else:
                yield Token(name, value, None, self.line, self.col)

            # 更新行列
            self.col = m.start() % 80 + 1

    def tokenize(self) -> list:
        """返回 token 列表"""
        return list(self)

    def to_trinary_bytes(self) -> bytes:
        """将所有 token 转为三进制字节流"""
        tokens = self.tokenize()
        buf = bytearray()
        for tok in tokens:
            if tok.trinary is not None:
                for d in tok.trinary.digits:
                    buf.append(d)
            else:
                # 数字/字符串直接编码
                buf.append(ord(tok.value[0]) % 3)
        return bytes(buf)


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    print("=== Matha 词法器测试 ===")

    source = """
    (* 测试注释 *)
    func 加(a: Float, b: Float) -> Float = (a, b) => a + b
    let x = 加(3.0, 4.0)
    if x > 6.0 then 真 else 假
    """

    lexer = MathaLexer(source)
    tokens = lexer.tokenize()
    for tok in tokens:
        print(f"  {tok.type:12s} {tok.value!r:20s} tr={tok.trinary}")

    print("\n=== 词法器运行正常 ===")
