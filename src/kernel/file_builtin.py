"""Matha 内核文件 I/O 原语。

文件读写是「需要 OS 访问、纯 Matha 无法实现」的最小内核能力之一，因此与
时间一样留在核心主线可达的零依赖范围内（VM 与原生后端都直接映射到它）：

    宿主侧   src.kernel.file_builtin      —— 本模块
    VM 侧    src.mbc.vm._default_builtins —— 注册同一批实现
    原生侧   src.mbc.native               —— _emit_builtin_read_file / write / append

三个符号名（`_read_file` / `_write_file` / `_append_file`）与原生后端逐一对齐，
不得改名：改名会让 VM↔native 对拍失效。
"""
from __future__ import annotations


def read_file(path) -> str:
    """read_file(path) → 文件内容字符串。"""
    try:
        with open(str(path), encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise RuntimeError(f"read_file 失败: {e}")


def write_file(path, content) -> None:
    """write_file(path, content) → 无返回值，覆盖写入。"""
    try:
        with open(str(path), "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"write_file 失败: {e}")
    return None


def append_file(path, content) -> None:
    """append_file(path, content) → 无返回值，追加写入。"""
    try:
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"append_file 失败: {e}")
    return None


def _curry2(fn):
    """两参函数柯里化：f(a)(b) 或 f(a, b) 均可用。

    与 src.mbc.vm._curry2 逐字一致 —— 三端（宿主/VM/原生）柯里化布局必须相同。
    """
    return lambda a: (lambda b: fn(a, b))


def _register_file(builtins: dict) -> None:
    """把文件原语注册进内建表（键名与 VM / 原生后端一致）。"""
    builtins.setdefault("_read_file", read_file)
    builtins.setdefault("_write_file", _curry2(write_file))
    builtins.setdefault("_append_file", _curry2(append_file))


__all__ = [
    "read_file", "write_file", "append_file",
    "_register_file",
]
