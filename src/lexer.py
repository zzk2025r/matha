"""Matha 词法分析器。

对应 EBNF §2 词法层 + §16 解析器验证中的词法规则。

关键消解规则（§16）：
    - 最长匹配：……  > …；>> > >；<< > <；<= > <；>= > >
    - #N: vs #：：# 后跟数字 → 段号；# 后直接跟全角： → 无段号
    - 分数括号半/全角归一：（x/y）→ (x/y) 内部表示
    - 整数/浮点 + CJK 单位：紧邻 CJK 字符合并为带单位字面量
    - 标注 */文字/* 或 */文字*公式/*：*/ 起始，/* 结束
"""

from src.tokens import Token, TokenType, KEYWORDS, MULTI_CHAR_OPS


# ── 单字符 Token 映射表（模块级常量，避免每次调用重建 dict）────────────────
_SINGLE_CHAR_MAP: dict[str, TokenType] = {
    # ---------- 基础运算符 ----------
    "+": TokenType.OP_PLUS,
    "-": TokenType.OP_MINUS,
    "*": TokenType.OP_STAR,
    "/": TokenType.OP_SLASH,
    "%": TokenType.OP_MOD,
    "^": TokenType.OP_POWER,
    "=": TokenType.OP_ASSIGN,
    "<": TokenType.OP_LT,
    ">": TokenType.OP_GT,
    "?": TokenType.OP_QUESTION,
    ":": TokenType.OP_COLON,
    "|": TokenType.OP_PIPE,
    "!": TokenType.OP_NEQ,
    # ---------- 括号（半角 + 全角） ----------
    "(": TokenType.PUNCT_LPAREN,
    ")": TokenType.PUNCT_RPAREN,
    "（": TokenType.PUNCT_LPAREN,
    "）": TokenType.PUNCT_RPAREN,
    "[": TokenType.PUNCT_LBRACKET,
    "]": TokenType.PUNCT_RBRACKET,
    "{": TokenType.PUNCT_LBRACE,
    "}": TokenType.PUNCT_RBRACE,
    # ---------- 分隔符（半角 + 全角） ----------
    ",": TokenType.PUNCT_COMMA,
    "，": TokenType.MATHA_COMMA,
    ".": TokenType.PUNCT_DOT,
    "_": TokenType.PUNCT_UNDERSCORE,
    # ---------- Matha 专属符号 ----------
    "？": TokenType.MATHA_PLACEHOLDER,
    "【": TokenType.MATHA_READ_OPEN,
    "】": TokenType.MATHA_READ_CLOSE,
    "〔": TokenType.MATHA_READ_OPEN2,
    "〕": TokenType.MATHA_READ_CLOSE2,
    "《": TokenType.MATHA_CMD_OPEN,
    "》": TokenType.MATHA_CMD_CLOSE,
    "#": TokenType.MATHA_HASH,
    "：": TokenType.MATHA_COLON_FW,
    "@": TokenType.MATHA_AT,
    "、": TokenType.MATHA_COMMA,
    # ---------- CJK 标点 (U+3000-303F) ----------
    "。": TokenType.PUNCT_DOT,
    "；": TokenType.MATHA_COLON_FW,
    "！": TokenType.OP_QUESTION,
    "「": TokenType.MATHA_READ_OPEN,
    "」": TokenType.MATHA_READ_CLOSE,
    "『": TokenType.MATHA_READ_OPEN2,
    "』": TokenType.MATHA_READ_CLOSE2,
    "〈": TokenType.MATHA_READ_OPEN,
    "〉": TokenType.MATHA_READ_CLOSE,
    "〖": TokenType.MATHA_READ_OPEN2,
    "〗": TokenType.MATHA_READ_CLOSE2,
    "〘": TokenType.MATHA_READ_OPEN,
    "〙": TokenType.MATHA_READ_CLOSE,
    "〚": TokenType.MATHA_READ_OPEN2,
    "〛": TokenType.MATHA_READ_CLOSE2,
    "〝": TokenType.MATHA_READ_OPEN,
    "〞": TokenType.MATHA_READ_CLOSE,
    # ---------- 全角 Latin (U+FF00-FFEF) ----------
    "＆": TokenType.OP_PIPE,
    "＄": TokenType.OP_SET_PROD,
    "％": TokenType.OP_MOD,
    "＊": TokenType.OP_STAR,
    "＋": TokenType.OP_PLUS,
    "－": TokenType.OP_MINUS,
    "．": TokenType.PUNCT_DOT,
    "／": TokenType.OP_SLASH,
    "：": TokenType.OP_COLON,
    "；": TokenType.MATHA_COLON_FW,
    "＜": TokenType.OP_LT,
    "＞": TokenType.OP_GT,
    "？": TokenType.MATHA_PLACEHOLDER,
    "＝": TokenType.OP_ASSIGN,
    "＠": TokenType.MATHA_AT,
    "［": TokenType.PUNCT_LBRACKET,
    "＼": TokenType.OP_SET_DIFF,
    "］": TokenType.PUNCT_RBRACKET,
    "＾": TokenType.OP_POWER,
    "｀": TokenType.PUNCT_UNDERSCORE,
    "｛": TokenType.PUNCT_LBRACE,
    "｜": TokenType.OP_PIPE,
    "｝": TokenType.PUNCT_RBRACE,
    "～": TokenType.OP_SET_COMP,
    "〜": TokenType.OP_SET_COMP,
    # ---------- 通用标点 (U+2000-206F) ----------
    "—": TokenType.OP_MINUS,
    "–": TokenType.OP_MINUS,
    "′": TokenType.MATHA_ELLIPSIS,
    "″": TokenType.MATHA_DOUBLE_ELLIPSIS,
    "†": TokenType.SYMBOL,
    "‡": TokenType.SYMBOL,
    "•": TokenType.SYMBOL,
    "…": TokenType.MATHA_ELLIPSIS,
    "‟": TokenType.SYMBOL,
    "‛": TokenType.SYMBOL,
    # ---------- 数学运算符 (U+2200-22FF) ----------
    "≤": TokenType.OP_LE,
    "≥": TokenType.OP_GE,
    "≠": TokenType.OP_NEQ,
    "≈": TokenType.SYMBOL,
    "→": TokenType.OP_ARROW_FW,
    "≡": TokenType.SYMBOL,
    "∈": TokenType.SYMBOL,
    "∉": TokenType.SYMBOL,
    "∅": TokenType.SYMBOL,
    "∝": TokenType.SYMBOL,
    "∠": TokenType.SYMBOL,
    "∧": TokenType.OP_PIPE,
    "∨": TokenType.OP_PIPE,
    "∩": TokenType.OP_SET_INTER,
    "∪": TokenType.OP_SET_UNION,
    "∫": TokenType.SYMBOL,
    "∬": TokenType.SYMBOL,
    "∀": TokenType.SYMBOL,
    "∃": TokenType.SYMBOL,
    "¬": TokenType.OP_SET_COMP,
    "⊕": TokenType.SYMBOL,
    "⊗": TokenType.SYMBOL,
    "⊥": TokenType.SYMBOL,
    "∥": TokenType.SYMBOL,
    "∞": TokenType.SYMBOL,
    # ---------- Box Drawing (U+2500-257F) ----------
    "┌": TokenType.SYMBOL,
    "┐": TokenType.SYMBOL,
    "└": TokenType.SYMBOL,
    "┘": TokenType.SYMBOL,
    "─": TokenType.SYMBOL,
    "│": TokenType.SYMBOL,
    "├": TokenType.SYMBOL,
    "┤": TokenType.SYMBOL,
    "┬": TokenType.SYMBOL,
    "┴": TokenType.SYMBOL,
    "┼": TokenType.SYMBOL,
    # ---------- 其他常用符号 ----------
    "°": TokenType.SYMBOL,
    "℃": TokenType.SYMBOL,
    "℉": TokenType.SYMBOL,
    "§": TokenType.SYMBOL,
    "¶": TokenType.SYMBOL,
    "″″": TokenType.SYMBOL,
    "℅": TokenType.SYMBOL,
    "№": TokenType.SYMBOL,
    # ---------- 集合运算符 ----------
    "×": TokenType.OP_SET_PROD,
    "⊆": TokenType.OP_SET_SUBSET,
    "~": TokenType.OP_SET_COMP,
}
# 集合运算符子集（与原 set_ops 保持一致）
_SINGLE_SET_OPS: dict[str, TokenType] = {
    "∪": TokenType.OP_SET_UNION,
    "∩": TokenType.OP_SET_INTER,
    "×": TokenType.OP_SET_PROD,
    "⊆": TokenType.OP_SET_SUBSET,
    "~": TokenType.OP_SET_COMP,
}

# 进制合法字符映射（模块级常量，避免每次创建 dict）
_RADIX_VALID: dict[str, str] = {
    "b": "01",
    "t": "012",
    "x": "0123456789abcdefABCDEF",
}

# 转义字符映射（模块级常量，避免每次字符串解析时创建 dict）
_ESCAPE_MAP: dict[str, str] = {
    "n": "\n",
    "t": "\t",
    '"': '"',
    "\\": "\\",
}


# CJK 表意文字 Unicode 区间（简化版，覆盖常见汉字）
# 注意：不包含 0x3000-0x303F（CJK 符号和标点），因为该区间含 Matha 专属符号
# 【】(U+3010/3011)、〔〕(U+3014/3015)、《》(U+300A/300B) 等，由词法层单独处理。
CJK_RANGES: list[tuple[int, int]] = [
    (0x4E00, 0x9FFF),    # CJK 统一表意文字
    (0x3400, 0x4DBF),    # CJK 扩展 A
]


def is_cjk(ch: str) -> bool:
    """判断字符是否为 CJK 表意文字（可用作标识符 / 单位）。"""
    cp = ord(ch)
    for lo, hi in CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


# 希腊字母 Unicode 区间（U+0370–U+03FF）
GREEK_LETTERS: set[str] = set()
for _cp in range(0x0370, 0x0400):
    _ch = chr(_cp)
    if _ch.isalpha():
        GREEK_LETTERS.add(_ch)


def is_greek_letter(ch: str) -> bool:
    """判断字符是否为希腊字母（可用作标识符）。"""
    return ch in GREEK_LETTERS


def is_ascii_letter(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def is_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


# ── Unicode 标识符支持 ────────────────────────────────────────────────────────
# 使用 Python 内置 Unicode 类别检测，覆盖所有语言的字母（日文、阿拉伯、希腊等）。
# 判断依据：
#   - 标识符首字符：ch.isalpha() → 覆盖所有 Letter 类别（Ll, Lu, Lm, Lo, Lt, Lc）
#   - 标识符续字符：ch.isalnum() or ch == "_" → 字母 + 数字 + 下划线
# 无法作为标识符的字符：emoji (So)、数学符号 (Sm)、BoxDrawing (So) 等，
#   会被 isalpha()/isalnum() 正确拒绝，降级为 SYMBOL token（不崩溃）。

def is_unicode_letter(ch: str) -> bool:
    """判断字符是否为 Unicode 字母（覆盖所有语言：ASCII、CJK、日文、阿拉伯、希腊等）。

    使用 str.isalpha() 判定，等价于 Unicode 类别 L*（Letter）。
    覆盖范围：
      - ASCII a-z / A-Z (Ll, Lu)
      - CJK 汉字（Lo）
      - 日文假名/片假名（Lo）
      - 希腊字母（Ll, Lu）
      - 阿拉伯字母（Lo）
      - 韩文（Lo）
      - 其他书写系统的字母
    不覆盖（正确拒绝）：
      - emoji（So 类别）
      - 数学符号（Sm 类别，如 ∑ ∞ ≈）
      - BoxDrawing（So 类别，如 ┌ ┐ └ ┘）
      - 其他符号
    """
    return ch.isalpha()


def is_unicode_id_continue(ch: str) -> bool:
    """判断字符是否可作为标识符续字符（字母/数字/下划线）。"""
    return ch.isalnum() or ch == "_"


def _starts_multi_char_op(source: str, pos: int) -> bool:
    """检查 pos 位置是否是多字符运算符的起始。"""
    for text, _ in MULTI_CHAR_OPS:
        if source[pos:pos + len(text)] == text:
            return True
    return False


class LexerError(Exception):
    """词法错误。"""

    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"LexerError at L{line}:{col}: {msg}")
        self.line = line
        self.col = col


class Lexer:
    """Matha 词法分析器。

    用法：
        lex = Lexer(source_text)
        tokens = list(lex.tokenize())
    """

    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.n = len(source)

    # ---------- 工具方法 ----------

    def _peek(self, offset: int = 0) -> str:
        """查看 offset 处字符，不前进。越界返回空串。"""
        idx = self.pos + offset
        return self.src[idx] if idx < self.n else ""

    def _advance(self) -> str:
        """消费当前字符并前进。"""
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _match(self, text: str) -> bool:
        """若当前位置匹配 text 则消费并返回 True。"""
        if self.src[self.pos:self.pos + len(text)] == text:
            for _ in text:
                self._advance()
            return True
        return False

    def _skip_whitespace_inline(self) -> None:
        """跳过行内空白（空格/制表符），不跳换行。"""
        while self.pos < self.n and self.src[self.pos] in (" ", "\t"):
            self._advance()

    # ---------- 主入口 ----------

    def tokenize(self):
        """生成 Token 流（含 NEWLINE / EOF）。

        缩进块（INDENT/DEDENT）暂未实现，预留接口。
        """
        # 预处理：跳过注释 (* ... *)
        while self.pos < self.n:
            ch = self.src[self.pos]

            # 跳过行内空白
            if ch in (" ", "\t"):
                self._advance()
                continue

            # 跳过注释 (* ... *)  —— EBNF 风格注释
            if ch == "(" and self._peek(1) == "*":
                self._skip_comment()
                continue

            # 跳过 # 行注释（# 后跟非数字非冒号字符时视为注释）
            if ch == "#":
                peek = self._peek(1)
                if peek and peek not in ("：", ":", "") and not (peek and peek.isdigit()):
                    while self.pos < self.n and self.src[self.pos] != "\n":
                        self._advance()
                    continue

            # 换行
            if ch == "\n":
                yield Token(TokenType.NEWLINE, "\\n", self.line, self.col)
                self._advance()
                continue

            # 回车（\r\n 或单独 \r）
            if ch == "\r":
                self._advance()
                if self.pos < self.n and self.src[self.pos] == "\n":
                    pass  # \r 已消费，下面 \n 会单独产出 NEWLINE
                else:
                    yield Token(TokenType.NEWLINE, "\\n", self.line, self.col)
                continue

            # 多字符运算符（最长匹配）
            matched = False
            for text, ttype in MULTI_CHAR_OPS:
                if self._match(text):
                    yield Token(ttype, text, self.line, self.col)
                    matched = True
                    break
            if matched:
                continue

            # 处理双字符操作符：**（幂运算）
            if ch == "*" and self._peek(1) == "*":
                self._advance()
                self._advance()
                yield Token(TokenType.OP_POWER, "**", self.line, self.col)
                continue

            # 单字符符号
            tok = self._single_char(ch)
            if tok is not None:
                self._advance()  # 消费当前字符
                yield tok
                continue

            # 数字字面量
            if is_digit(ch):
                yield self._number()
                continue

            # 字符串字面量
            if ch == '"':
                yield self._string()
                continue

            # 标识符 / 关键字 / CJK / 顿号（、在【】内作为文本分隔符）
            if is_unicode_letter(ch) or ch == "_" or ch == "、" or ch == "—":
                yield self._identifier()
                continue
            # 未映射到任何 token 的字符（emoji、数学符号等）也作为标识符
            # 已映射的字符（包括映射为 SYMBOL 的）通过后续逻辑处理
            # 但排除常见 ASCII 标点（如 ; ），避免误识别为标识符
            if ch not in _SINGLE_CHAR_MAP and ch not in _SINGLE_SET_OPS \
                    and ch not in ";,()[]{}`~'":
                yield self._identifier()
                continue

            # 未识别字符降级为 SYMBOL token（不崩溃）
            # 这使 Matha 能使用任意 Unicode 标点，用户可通过 @define_op 自定义语义
            yield Token(TokenType.SYMBOL, ch, self.line, self.col)
            self._advance()
            continue

        yield Token(TokenType.EOF, "", self.line, self.col)

    # ---------- 各类 Token 解析 ----------

    def _skip_comment(self) -> None:
        """跳过 (* ... *) 注释。"""
        start_line, start_col = self.line, self.col
        self._advance()  # (
        self._advance()  # *
        depth = 1
        while self.pos < self.n and depth > 0:
            if self.src[self.pos] == "(" and self._peek(1) == "*":
                depth += 1
                self._advance()
                self._advance()
            elif self.src[self.pos] == "*" and self._peek(1) == ")":
                depth -= 1
                self._advance()
                self._advance()
            else:
                self._advance()
        if depth > 0:
            raise LexerError("注释未闭合 (* ... *)", start_line, start_col)

    def _single_char(self, ch: str) -> Token | None:
        """处理单字符 Token。"""
        ttype = _SINGLE_CHAR_MAP.get(ch) or _SINGLE_SET_OPS.get(ch)
        if ttype is None:
            return None
        return Token(ttype, ch, self.line, self.col)

    def _number(self) -> Token:
        """解析数字字面量（整数/浮点），可带 CJK 单位。

        对应 EBNF：
            <integer> = <digit> , { <digit> } , [ <unit> ]
            <float>   = <integer> , "." , { <digit> } , [ <unit> ]

        支持进制前缀（M3.4）：
            0b1010  → 二进制（值=10）
            0t210   → 三进制（值=21）
            0xFF    → 十六进制（值=255）
        """
        start_line, start_col = self.line, self.col
        # 进制前缀：0b(二进制) / 0t(三进制) / 0x(十六进制)
        if self.src[self.pos] == "0" and self.pos + 1 < self.n:
            p = self.src[self.pos + 1].lower()
            if p in ("b", "t", "x"):
                return self._radix_literal(p, start_line, start_col)
        num_parts = []
        while self.pos < self.n and is_digit(self.src[self.pos]):
            num_parts.append(self._advance())
        num_str = "".join(num_parts)

        is_float = False
        if self.pos < self.n and self.src[self.pos] == ".":
            # 确认不是范围/成员访问（后跟数字才是浮点）
            if self.pos + 1 < self.n and is_digit(self.src[self.pos + 1]):
                is_float = True
                num_parts.append(self._advance())  # .
                while self.pos < self.n and is_digit(self.src[self.pos]):
                    num_parts.append(self._advance())
                num_str = "".join(num_parts)
        # 科学计数法：XeY 或 Xe+Y 或 Xe-Y（必须用 if 而非 elif，因为小数后也可能有 e）
        if self.pos < self.n and self.src[self.pos].lower() == "e":
            peek = self._peek(1)
            if peek and (peek.isdigit() or peek in ("+", "-")):
                is_float = True
                num_parts.append(self._advance())  # e
                if self.pos < self.n and self.src[self.pos] in ("+", "-"):
                    num_parts.append(self._advance())
                while self.pos < self.n and is_digit(self.src[self.pos]):
                    num_parts.append(self._advance())
                num_str = "".join(num_parts)

        # 可选 CJK 单位（紧邻的 CJK 字符序列）
        unit_parts = []
        while self.pos < self.n and is_cjk(self.src[self.pos]):
            # 注意：全角冒号/中文逗号不属于单位，需排除
            ch = self.src[self.pos]
            if ch in ("：", "，"):
                break
            unit_parts.append(self._advance())
        unit = "".join(unit_parts)

        value = num_str + unit
        ttype = TokenType.LIT_FLOAT if is_float else TokenType.LIT_INTEGER
        return Token(ttype, value, start_line, start_col)

    def _radix_literal(self, prefix: str, start_line: int, start_col: int) -> Token:
        """解析进制字面量：0b(二进制) / 0t(三进制) / 0x(十六进制)。

        保留原始形式（如 0b1010），值由 parser 按前缀转换为 int。
        """
        self._advance()  # 消费 0
        self._advance()  # 消费 b/t/x
        valid = {"b": "01", "t": "012", "x": "0123456789abcdefABCDEF"}[prefix]
        digits = ""
        while self.pos < self.n and self.src[self.pos].lower() in valid:
            digits += self._advance()
        value = f"0{prefix}{digits}"
        return Token(TokenType.LIT_INTEGER, value, start_line, start_col)

    def _string(self) -> Token:
        """解析字符串字面量 "..."（转义规则草案）。"""
        start_line, start_col = self.line, self.col
        self._advance()  # 消费开引号
        result = ""
        while self.pos < self.n and self.src[self.pos] != '"':
            ch = self.src[self.pos]
            if ch == "\\":
                self._advance()
                if self.pos < self.n:
                    esc = self._advance()
                    result += _ESCAPE_MAP.get(esc, esc)
            else:
                result += self._advance()
        if self.pos >= self.n:
            raise LexerError("字符串未闭合", start_line, start_col)
        self._advance()  # 消费闭引号
        return Token(TokenType.LIT_STRING, result, start_line, start_col)

    def _identifier(self) -> Token:
        """解析标识符 / 关键字。

        对应 EBNF：
            <identifier> = <letter> , { <letter> | <digit> | "_" }
            <letter>     = <unicode_letter>

        连续的 Unicode 字母/数字/下划线/ CJK 字符会作为一个整体标识符。
        遇到多字符运算符时停止，不崩溃，降级为 SYMBOL。
        """
        start_line, start_col = self.line, self.col
        parts = []
        while self.pos < self.n:
            ch = self.src[self.pos]
            if is_unicode_id_continue(ch):
                parts.append(self._advance())
            elif is_unicode_letter(ch):
                parts.append(self._advance())
            elif ch in ("、", "—"):
                # 顿号/长破折号：仅作为首字符，不纳入标识符
                break
            elif ch in _SINGLE_CHAR_MAP or ch in _SINGLE_SET_OPS:
                # 遇到已映射单字符（如 +、=、→ 等），停止标识符
                break
            elif _starts_multi_char_op(self.src, self.pos):
                # 遇到多字符运算符起始（如 ->、=>、++ 等），停止
                break
            elif ch in (" ", "\t", "\n", "\r"):
                # 空白字符不纳入标识符
                break
            else:
                # 未映射字符（emoji 等）继续纳入标识符
                parts.append(self._advance())
        result = "".join(parts)
        # 查关键字表
        ttype = KEYWORDS.get(result, TokenType.IDENTIFIER)
        return Token(ttype, result, start_line, start_col)
