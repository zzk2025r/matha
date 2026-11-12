"""M3V 字节码二进制工件（.mbc）读写。

文件布局：
  magic "MBC1" | 块1 常量池 | 块2 函数表 | 块3 顶层码 | 块4 模块名
  每个块：4 字节小端长度 + marshal 负载。
.mbc 是自包含二进制：运行时无需 .matha 源码，仅需 VM runner。
"""
from __future__ import annotations

import io
import marshal
import struct

from src.mbc.compiler import MFunction, MModule

MAGIC = b"MBC1"


def _write_block(f, obj) -> None:
    payload = marshal.dumps(obj)
    f.write(struct.pack("<I", len(payload)))
    f.write(payload)


def _read_block(f):
    header = f.read(4)
    if len(header) < 4:
        raise EOFError("字节码块长度缺失")
    (length,) = struct.unpack("<I", header)
    return marshal.loads(f.read(length))


def _funcs_dict(mod: MModule) -> dict:
    return {
        name: {"arity": fn.arity, "nlocals": fn.nlocals,
               "params": fn.params, "code": fn.code}
        for name, fn in mod.functions.items()
    }


def serialize_mbc(mod: MModule) -> bytes:
    """MModule → MBC1 内存字节串（与 write_mbc 的文件布局完全一致）。"""
    buf = io.BytesIO()
    buf.write(MAGIC)
    _write_block(buf, mod.constants)
    _write_block(buf, _funcs_dict(mod))
    _write_block(buf, mod.main_code)
    _write_block(buf, mod.module_name)
    return buf.getvalue()


def deserialize_mbc(data: bytes) -> MModule:
    """MBC1 内存字节串 → MModule（与 read_mbc 的文件解析完全一致）。"""
    stream = io.BytesIO(data)
    magic = stream.read(4)
    if magic != MAGIC:
        raise ValueError(f"非法 .mbc 数据（magic={magic!r}）")
    return _load_blocks(stream)


def _load_blocks(stream) -> MModule:
    constants = _read_block(stream)
    funcs_raw = _read_block(stream)
    main_code = _read_block(stream)
    module_name = _read_block(stream)
    mod = MModule(module_name=module_name)
    mod.constants = constants
    mod.main_code = main_code
    for name, d in funcs_raw.items():
        mod.functions[name] = MFunction(
            name=name, arity=d["arity"], nlocals=d["nlocals"],
            code=d["code"], params=d["params"])
    return mod


def write_mbc(mod: MModule, path: str) -> None:
    with open(path, "wb") as f:
        f.write(serialize_mbc(mod))


def read_mbc(path: str) -> MModule:
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC:
            raise ValueError(f"非法 .mbc 文件（magic={magic!r}）")
        return _load_blocks(f)
