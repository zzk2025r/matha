"""Matha 全符号资源库宿主接入（Phase ③）。

单一数据来源：``matha/stdlib_symbols.matha``（Matha 源文件）。
本模块编译并运行该文件，读取其全局 ``符号表``（list[dict]），
再以 Python API 提供与 Matha 侧查询函数等价的访问。

设计要点：
  - 数据只在该 .matha 文件里维护一处，宿主通过「编译 + 运行」取得同一份数据；
  - 本模块只做读取与查询，**不改变词法器行为**，也不注册任何运算符；
  - 结果缓存于进程内，可用 :func:`clear_cache` 强制重载。

条目字段：``符号 / 码位 / 中文名 / 英文名 / 别名 / 类别 / 标签 / 语义 / 优先级 / 结合性``。
类别（主类别，共 7 类）：中文标点 / 全角 / ASCII / 运算符 / 数学 / 希腊 / 学科。
``按类别`` 同时匹配 ``类别`` 与 ``标签``（如 π 主类=数学、标签含 希腊）。
"""

from __future__ import annotations

import os

from src.mbc import compile_source
from src.mbc.vm import VM

#: 符号资源库源文件路径
SYMBOLS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "matha", "stdlib_symbols.matha",
)

#: 主类别（与 stdlib_symbols.matha 的 类别列表() 保持一致）
CATEGORIES = ["中文标点", "全角", "ASCII", "运算符", "数学", "希腊", "学科"]

_cache: list | None = None


def clear_cache() -> None:
    """清除已加载的符号表缓存（下次查询时重新编译运行）。"""
    global _cache
    _cache = None


def _load() -> list:
    """编译并运行符号资源库，返回全局 ``符号表``（list[dict]）。"""
    global _cache
    if _cache is None:
        with open(SYMBOLS_FILE, encoding="utf-8") as f:
            src = f.read()
        vm = VM(compile_source(src))
        vm.run()
        _cache = list(vm.globals.get("符号表", []))
    return _cache


def all_symbols() -> list:
    """返回全部符号条目（浅拷贝列表；条目为 dict，请勿原地修改）。"""
    return list(_load())


def count() -> int:
    """符号总数。"""
    return len(_load())


def categories() -> list:
    """返回全部主类别名（固定 7 类，顺序稳定）。"""
    return list(CATEGORIES)


def by_category(category: str) -> list:
    """按主类别或标签匹配，返回条目列表（保序）。"""
    return [
        e for e in _load()
        if e.get("类别") == category or category in e.get("标签", [])
    ]


def by_symbol(symbol: str) -> dict | None:
    """按符号字面量精确查找，返回首个条目或 None。"""
    for e in _load():
        if e.get("符号") == symbol:
            return e
    return None


def by_codepoint(codepoint: int) -> dict | None:
    """按码位查找（多字符符号取其任一字符即可命中），返回首个条目或 None。"""
    for e in _load():
        if codepoint in e.get("码位", []):
            return e
    return None


def by_name(name: str) -> dict | None:
    """按名查找：匹配 中文名 / 英文名 / 别名 / 符号本身，返回首个条目或 None。"""
    for e in _load():
        if (e.get("中文名") == name or e.get("英文名") == name
                or e.get("符号") == name or name in e.get("别名", [])):
            return e
    return None


def semantics(symbol: str) -> str:
    """取符号语义描述；未登记返回空串。"""
    e = by_symbol(symbol)
    return e.get("语义", "") if e else ""


def operator_declaration(symbol: str) -> str:
    """生成 ``@define_op`` 声明文本；非运算符（优先级≤0）或未登记返回空串。"""
    e = by_symbol(symbol)
    if not e or e.get("优先级", 0) <= 0:
        return ""
    return f"@define_op: {symbol} = {e['优先级']} | {e['结合性']}"


def definable_operators() -> list:
    """返回所有可经 ``@define_op`` 表达的运算符符号（优先级 > 0，保序）。"""
    return [e["符号"] for e in _load() if e.get("优先级", 0) > 0]
