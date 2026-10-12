"""Matha IO系统模块：文件读写、标准IO、流操作、管道。

覆盖：
  1) 文件读/写/追加
  2) 标准输入/输出/错误
  3) 内存流/StringIO
  4) 管道通信
  5) 文件属性查询
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from datetime import datetime
from typing import Any

# ============================================================
# 文件操作
# ============================================================

def file_read(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容为字符串。"""
    with open(path, encoding=encoding) as f:
        return f.read()


def file_read_bytes(path: str) -> bytes:
    """读取文件为字节。"""
    with open(path, "rb") as f:
        return f.read()


def file_write(path: str, content: str, encoding: str = "utf-8") -> int:
    """写入字符串到文件，返回字节数。"""
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
    return len(content.encode(encoding))


def file_append(path: str, content: str) -> int:
    """追加内容到文件。"""
    with open(path, "a") as f:
        f.write(content)
    return len(content)


def file_exists(path: str) -> bool:
    """检查文件是否存在。"""
    return os.path.exists(path)


def file_size(path: str) -> int:
    """获取文件大小（字节）。"""
    return os.path.getsize(path)


def file_delete(path: str) -> bool:
    """删除文件。"""
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def file_list(dir_path: str = ".") -> list[str]:
    """列出目录内容。"""
    try:
        return os.listdir(dir_path)
    except OSError:
        return []


def file_mkdir(path: str) -> bool:
    """创建目录。"""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def file_get_content(path: str) -> dict:
    """获取文件信息字典。"""
    if not os.path.exists(path):
        return {"exists": False}
    stat = os.stat(path)
    return {
        "exists": True,
        "path": path,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "is_file": os.path.isfile(path),
        "is_dir": os.path.isdir(path),
    }


# ============================================================
# 标准IO
# ============================================================

_stdout_buffer: list[str] = []
_stderr_buffer: list[str] = []
_stdin_buffer: list[str] = []


def stdout_write(text: str) -> int:
    """写入标准输出。"""
    sys.stdout.write(text)
    sys.stdout.flush()
    _stdout_buffer.append(text)
    return len(text)


def stderr_write(text: str) -> int:
    """写入标准错误。"""
    sys.stderr.write(text)
    sys.stderr.flush()
    _stderr_buffer.append(text)
    return len(text)


def stdin_read(prompt: str = "") -> str:
    """从标准输入读取。"""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline().rstrip("\n")
    _stdin_buffer.append(line)
    return line


def stdout_get_buffer() -> str:
    """获取输出缓冲区内容。"""
    return "".join(_stdout_buffer)


def stderr_get_buffer() -> str:
    """获取错误缓冲区内容。"""
    return "".join(_stderr_buffer)


# ============================================================
# 内存流
# ============================================================

_memory_streams: dict[str, io.StringIO] = {}


def mem_stream_open(name: str = "default") -> io.StringIO:
    """打开内存流。"""
    if name not in _memory_streams:
        _memory_streams[name] = io.StringIO()
    return _memory_streams[name]


def mem_stream_write(name: str, text: str) -> int:
    """写入内存流。"""
    stream = mem_stream_open(name)
    stream.write(text)
    return len(text)


def mem_stream_read(name: str = "default") -> str:
    """读取内存流内容。"""
    stream = _memory_streams.get(name)
    if stream:
        return stream.getvalue()
    return ""


def mem_stream_reset(name: str = "default") -> None:
    """重置内存流。"""
    if name in _memory_streams:
        _memory_streams[name] = io.StringIO()


# ============================================================
# 数据序列化
# ============================================================

def json_encode(data: Any) -> str:
    """序列化为JSON字符串。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def json_decode(text: str) -> Any:
    """解析JSON字符串。"""
    return json.loads(text)


def base64_encode(data: str) -> str:
    """Base64编码。"""
    return base64.b64encode(data.encode()).decode()


def base64_decode(text: str) -> str:
    """Base64解码。"""
    return base64.b64decode(text.encode()).decode()


# ============================================================
# 注册
# ============================================================

def _register_io(builtins: dict) -> None:
    builtins["文件读取"] = file_read
    builtins["文件写入"] = file_write
    builtins["文件追加"] = file_append
    builtins["文件存在"] = file_exists
    builtins["文件大小"] = file_size
    builtins["文件删除"] = file_delete
    builtins["文件列表"] = file_list
    builtins["创建目录"] = file_mkdir
    builtins["文件信息"] = file_get_content
    builtins["标准输出"] = stdout_write
    builtins["标准错误"] = stderr_write
    builtins["标准输入"] = stdin_read
    builtins["输出缓冲区"] = stdout_get_buffer
    builtins["JSON编码"] = json_encode
    builtins["JSON解码"] = json_decode
    builtins["Base64编码"] = base64_encode
    builtins["Base64解码"] = base64_decode
    builtins["内存流打开"] = mem_stream_open
    builtins["内存流写入"] = mem_stream_write
    builtins["内存流读取"] = mem_stream_read
    builtins["内存流重置"] = mem_stream_reset


def _io_symtab_names() -> list[str]:
    return [
        "文件读取", "文件写入", "文件追加", "文件存在", "文件大小",
        "文件删除", "文件列表", "创建目录", "文件信息",
        "标准输出", "标准错误", "标准输入", "输出缓冲区",
        "JSON编码", "JSON解码", "Base64编码", "Base64解码",
        "内存流打开", "内存流写入", "内存流读取", "内存流重置",
    ]


__all__ = [
    "file_read", "file_write", "file_append", "file_exists", "file_size",
    "file_delete", "file_list", "file_mkdir", "file_get_content",
    "stdout_write", "stderr_write", "stdin_read",
    "json_encode", "json_decode", "base64_encode", "base64_decode",
    "mem_stream_open", "mem_stream_write", "mem_stream_read",
    "_register_io", "_io_symtab_names",
]
