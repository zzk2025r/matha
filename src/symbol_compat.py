"""Matha 多语言符号兼容性配置。

支持跨语言符号混合使用：
  - Matha 优先使用自身符号（+ - * / and or if while func 等）
  - 可通过配置启用其他语言的符号（C/Python/JS 风格）
  - 用户可自由混合使用不同语言的符号

用法：
    from src.symbol_compat import set_symbol_mode, get_symbol_mode
    set_symbol_mode("python")      # 启用 Python 风格符号
    set_symbol_mode("c")           # 启用 C 风格符号
    set_symbol_mode("js")          # 启用 JavaScript 风格符号
    set_symbol_mode("mixed")       # 启用所有语言符号（推荐）
    set_symbol_mode("native")      # 仅 Matha 原生符号
"""

from enum import Enum, auto


class SymbolMode(str, Enum):
    """符号兼容模式。"""
    NATIVE = "native"     # 仅 Matha 原生符号
    MIXED = "mixed"       # 混合所有语言符号（推荐）
    PYTHON = "python"     # Python 风格
    C = "c"               # C/C++/Java 风格
    JS = "js"             # JavaScript 风格


# ── 全局配置 ─────────────────────────────────────────────────────────────────

_current_mode: SymbolMode = SymbolMode.NATIVE


def set_symbol_mode(mode: str | SymbolMode) -> SymbolMode:
    """设置符号兼容模式。"""
    global _current_mode
    if isinstance(mode, str):
        mode = SymbolMode(mode.lower())
    _current_mode = mode
    return mode


def get_symbol_mode() -> SymbolMode:
    """获取当前符号兼容模式。"""
    return _current_mode


def is_enabled(symbol: str) -> bool:
    """检查指定符号在当前模式下是否可用。

    Matha 原生符号在所有模式下均可用。
    跨语言符号仅在对应模式下启用。
    """
    if _current_mode == SymbolMode.NATIVE:
        return _is_native_symbol(symbol)
    if _current_mode == SymbolMode.MIXED:
        return True
    if _current_mode == SymbolMode.PYTHON:
        return _is_python_symbol(symbol)
    if _current_mode == SymbolMode.C:
        return _is_c_symbol(symbol)
    if _current_mode == SymbolMode.JS:
        return _is_js_symbol(symbol)
    return _is_native_symbol(symbol)


# ── 各模式符号定义 ────────────────────────────────────────────────────────────

# Matha 原生符号（所有模式）
_NATIVE_SYMBOLS: set[str] = {
    "+", "-", "*", "/", "%", "^", "=", "<", ">",
    "<=", ">=", "!=", "?", ":", "|", "!",
    "->", "=>", "<<", ">>", "++", "--",
    "(", ")", "[", "]", "{", "}", ",", ".",
    "&&", "||", "**", "//", "==", "!=",
    # Matha 专属 Unicode
    "？", "【", "】", "〔", "〕", "《", "》",
    "#", "：", "@", "…", "……", "、",
    # 全角变体
    "（", "）", "［", "］", "｛", "｝",
    "＋", "－", "＊", "／", "％", "＾", "＝",
    "＜", "＞", "≤", "≥", "≠", "≈", "→", "∧", "∨",
}

# C/C++/Java 风格符号
_C_SYMBOLS: set[str] = {
    "&&", "||", "!", "~", "&", "|", "^",
    "<<", ">>", ">>=", "<<=",
    "++", "--",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "==", "!=", ">=", "<=",
    "->", "=>",
    "...",
    "sizeof", "struct", "enum", "union",
    "break", "continue", "return",
    "switch", "case", "default",
    "goto",
    "typedef", "const", "volatile",
    "auto", "register", "static",
    "extern", "inline",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
}

# Python 风格符号
_PYTHON_SYMBOLS: set[str] = {
    "**", "//",
    "==", "!=", "<>",
    "is", "is not",
    "in", "not in",
    "and", "or", "not",
    "lambda", "yield", "from",
    "import", "as", "with", "try", "except", "finally",
    "raise", "pass", "global", "nonlocal",
    "if", "elif", "else",
    "for", "while", "break", "continue", "return",
    "def", "class",
    "True", "False", "None",
    "@", "...",
    "<<", ">>", "&", "|", "^", "~",
    "+=", "-=", "*=", "/=", "%=", "**=", "//=",
    "and", "or", "not",
    "is", "in",
    # 运算符别名
    "isinstance", "type", "len", "range",
}

# JavaScript 风格符号
_JS_SYMBOLS: set[str] = {
    "=== ", "!== ",
    "??", "?.",
    "&&", "||", "!", "~", "&", "|", "^",
    "<<", ">>",
    "++", "--",
    "+=", "-=", "*=", "/=", "%=", "**=",
    "...",
    "typeof", "instanceof",
    "new", "delete", "void",
    "try", "catch", "finally", "throw",
    "switch", "case", "default",
    "let", "const", "var",
    "function", "async", "await",
    "class", "extends", "super", "this",
    "export", "import", "from",
    "if", "else", "for", "while", "do",
    "break", "continue", "return",
    "true", "false", "null", "undefined",
    "NaN", "Infinity",
    "=>",
}


def _is_native_symbol(sym: str) -> bool:
    return sym in _NATIVE_SYMBOLS


def _is_python_symbol(sym: str) -> bool:
    if sym in _NATIVE_SYMBOLS:
        return True
    return sym in _PYTHON_SYMBOLS


def _is_c_symbol(sym: str) -> bool:
    if sym in _NATIVE_SYMBOLS:
        return True
    return sym in _C_SYMBOLS


def _is_js_symbol(sym: str) -> bool:
    if sym in _NATIVE_SYMBOLS:
        return True
    return sym in _JS_SYMBOLS
