"""Token 类型定义。

对应 EBNF §2 词法层（02-词法结构.md）。
所有 Matha Unicode 符号（？【】〔〕《》#：………，等）均按字面终结符处理。
"""

from enum import Enum, auto


class TokenType(Enum):
    """Matha Token 类型。

    命名约定：
        - OP_*   运算符
        - PUNCT_* 标点/括号
        - KW_*   保留关键字
        - LIT_*  字面量
        - MATHA_* Matha 专属 Unicode 符号
    """

    # ---------- 运算符（EBNF §2.1） ----------
    OP_PLUS = auto()       # +
    OP_MINUS = auto()      # -
    OP_STAR = auto()       # *
    OP_SLASH = auto()      # /
    OP_POWER = auto()      # ^  （双语义：中缀次方 / 前缀开方，语法层按位置消解）
    OP_ASSIGN = auto()     # =
    OP_LT = auto()         # <
    OP_GT = auto()         # >
    OP_LE = auto()         # <=
    OP_NEQ = auto()        # !=  不等于
    OP_GE = auto()         # >=
    OP_MOD = auto()        # %   取模
    OP_ANGLE = auto()      # <<  角度运算
    OP_NEXT = auto()       # >>  四重语义：步进/属于/路径距离/通用链式

    # 函数 / 控制
    OP_ARROW = auto()      # ->  函数类型
    OP_ARROW_FW = auto()   # →  右箭头（Unicode 等价于 ->）
    OP_FATARROW = auto()   # =>  lambda 体 / 匹配结果
    OP_SEND = auto()       # <-  channel 发送/接收
    OP_QUESTION = auto()   # ?   三元条件 / 错误传播（草案）
    OP_COLON = auto()      # :   半角冒号
    OP_PIPE = auto()       # |   分格
    OP_INCR = auto()       # ++  前缀自增
    OP_DECR = auto()       # --  前缀自减

    # 集合运算（草案 Unicode）
    OP_SET_UNION = auto()      # ∪
    OP_SET_INTER = auto()      # ∩
    OP_SET_DIFF = auto()       # \
    OP_SET_COMP = auto()       # ~
    OP_SET_PROD = auto()       # ×
    OP_SET_SUBSET = auto()     # ⊆

    # ---------- 标点 / 括号 ----------
    PUNCT_LPAREN = auto()   # (
    PUNCT_RPAREN = auto()   # )
    PUNCT_LBRACKET = auto() # [
    PUNCT_RBRACKET = auto() # ]
    PUNCT_LBRACE = auto()   # {
    PUNCT_RBRACE = auto()   # }
    PUNCT_COMMA = auto()    # ,  英文逗号
    PUNCT_DOT = auto()      # .
    PUNCT_UNDERSCORE = auto()  # _
    SYMBOL = auto()            # 用户自定义或通用符号（降级 token）
    UNKNOWN = auto()           # 完全无法识别的字符（调试用）

    # ---------- Matha 专属符号（Unicode） ----------
    MATHA_PLACEHOLDER = auto()   # ？  公式通用占位符
    MATHA_READ_OPEN = auto()     # 【  读取（方头括号开）
    MATHA_READ_CLOSE = auto()    # 】  读取（方头括号闭）
    MATHA_READ_OPEN2 = auto()    # 〔  读取（六角括号开，与【等价）
    MATHA_READ_CLOSE2 = auto()   # 〕  读取（六角括号闭，与】等价）
    MATHA_CMD_OPEN = auto()      # 《  命令字面量开
    MATHA_CMD_CLOSE = auto()     # 》  命令字面量闭
    MATHA_HASH = auto()          # #  生成/运行前缀
    MATHA_COLON_FW = auto()      # ：  全角冒号（与 : 等价）
    MATHA_AT = auto()            # @  设定前缀
    MATHA_ELLIPSIS = auto()      # …  单省略号（段级循环，U+2026）
    MATHA_DOUBLE_ELLIPSIS = auto()  # …… 双省略号（全局循环）
    MATHA_COMMA = auto()         # ，  中文逗号（与 , 等价分格）
    MATHA_ANNOT_START = auto()   # */  标注起始
    MATHA_ANNOT_END = auto()     # /*  标注结束

    # ---------- 字面量 ----------
    LIT_INTEGER = auto()    # 整数（可带单位：100米）
    LIT_FLOAT = auto()      # 浮点数（可带单位：262.5米）
    LIT_STRING = auto()     # 字符串
    LIT_BOOL = auto()       # 真/假/true/false

    # ---------- 标识符 / 关键字 ----------
    IDENTIFIER = auto()     # 标识符（ASCII + CJK）

    KW_STRUCT = auto()
    KW_ENUM = auto()
    KW_TYPE = auto()
    KW_MATCH = auto()
    KW_MODULE = auto()
    KW_USE = auto()
    KW_AS = auto()
    KW_GO = auto()
    KW_FUNC = auto()
    KW_CHAN = auto()
    KW_SELECT = auto()
    KW_OTHERWISE = auto()   # 否则
    KW_WHILE = auto()       # while
    KW_IF = auto()          # if
    KW_FOR = auto()         # for
    KW_IN = auto()          # in
    KW_AND = auto()         # and
    KW_OR = auto()          # or

    # ---------- 特殊 ----------
    NEWLINE = auto()        # 换行
    INDENT = auto()         # 缩进增加
    DEDENT = auto()         # 缩进减少
    EOF = auto()            # 文件结束


class Token:
    """词法 Token。"""

    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type: TokenType, value: str, line: int, col: int):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"

    def __eq__(self, other) -> bool:
        if isinstance(other, TokenType):
            return self.type == other
        if isinstance(other, Token):
            return self.type == other.type
        return False


# ---------- 关键字表（EBNF §14） ----------
KEYWORDS: dict[str, TokenType] = {
    "struct": TokenType.KW_STRUCT,
    "enum": TokenType.KW_ENUM,
    "type": TokenType.KW_TYPE,
    "match": TokenType.KW_MATCH,
    "module": TokenType.KW_MODULE,
    "use": TokenType.KW_USE,
    "as": TokenType.KW_AS,
    "go": TokenType.KW_GO,
    "func": TokenType.KW_FUNC,
    "chan": TokenType.KW_CHAN,
    "select": TokenType.KW_SELECT,
    "否则": TokenType.KW_OTHERWISE,
    "if": TokenType.KW_IF,
    "while": TokenType.KW_WHILE,
    "for": TokenType.KW_FOR,
    "in": TokenType.KW_IN,
    "and": TokenType.KW_AND,
    "or": TokenType.KW_OR,
    "真": TokenType.LIT_BOOL,
    "假": TokenType.LIT_BOOL,
    "true": TokenType.LIT_BOOL,
    "false": TokenType.LIT_BOOL,
}


# ---------- 多字符运算符（最长匹配优先） ----------
# 按长度降序排列，保证最长匹配
MULTI_CHAR_OPS: list[tuple[str, TokenType]] = [
    ("……", TokenType.MATHA_DOUBLE_ELLIPSIS),  # 双省略号优先于单省略号
    ("<<", TokenType.OP_ANGLE),
    (">>", TokenType.OP_NEXT),
    ("<=", TokenType.OP_LE),
    (">=", TokenType.OP_GE),
    ("!=", TokenType.OP_NEQ),
    ("->", TokenType.OP_ARROW),
    ("=>", TokenType.OP_FATARROW),
    ("<-", TokenType.OP_SEND),
    ("*/", TokenType.MATHA_ANNOT_START),
    ("/*", TokenType.MATHA_ANNOT_END),
    ("…", TokenType.MATHA_ELLIPSIS),
    ("++", TokenType.OP_INCR),
    ("--", TokenType.OP_DECR),
]
