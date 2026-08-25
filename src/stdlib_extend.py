# -*- coding: utf-8 -*-
"""Matha 标准库补全：re/hashlib/sqlite3/pathlib/asyncio/csv/logging等。"""

from __future__ import annotations
import collections
import csv
import hashlib
import io
import json
import logging
import os
import pathlib
import re
import sqlite3
import sys
import time
from typing import Any, Optional


def _register_standard_library(builtins: dict) -> None:
    """将标准库函数注册为 Matha 内建。"""

    # ---- 正则表达式 ----
    builtins["正则匹配"] = lambda pattern, text: bool(re.search(pattern, text))
    builtins["正则替换"] = lambda pattern, repl, text: re.sub(pattern, repl, text)
    builtins["正则分割"] = lambda pattern, text: re.split(pattern, text)
    builtins["正则查找所有"] = lambda pattern, text: re.findall(pattern, text)
    builtins["正则匹配对象"] = lambda pattern, text: re.match(pattern, text)

    # ---- 哈希/加密 ----
    builtins["SHA256"] = lambda data: hashlib.sha256(str(data).encode()).hexdigest()
    builtins["MD5"] = lambda data: hashlib.md5(str(data).encode()).hexdigest()
    builtins["SHA1"] = lambda data: hashlib.sha1(str(data).encode()).hexdigest()
    builtins["哈希比较"] = lambda h1, h2: h1 == h2

    # ---- 数据库 ----
    def _sqlite_execute(db_path: str, sql: str) -> list:
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute(sql)
            result = cur.fetchall()
            conn.close()
            return result
        except Exception as e:
            return [f"error: {e}"]

    builtins["SQLite执行"] = _sqlite_execute
    builtins["SQLite查询"] = _sqlite_execute

    # ---- 路径操作 ----
    builtins["路径存在"] = lambda p: os.path.exists(str(p))
    builtins["路径是文件"] = lambda p: os.path.isfile(str(p))
    builtins["路径是目录"] = lambda p: os.path.isdir(str(p))
    builtins["路径目录"] = lambda p: os.path.dirname(str(p))
    builtins["路径文件名"] = lambda p: os.path.basename(str(p))
    builtins["路径展开"] = lambda p: os.path.abspath(str(p))
    builtins["路径合并"] = lambda *parts: os.path.join(*parts)
    builtins["路径扩展"] = lambda p: os.path.expanduser(str(p))

    # ---- CSV ----
    def _csv_read(path: str, delimiter: str = ",") -> list:
        try:
            with open(str(path), "r", encoding="utf-8", newline="") as f:
                return list(csv.reader(f, delimiter=delimiter))
        except Exception as e:
            return [[f"error: {e}"]]

    def _csv_write(path: str, data: list, delimiter: str = ",") -> bool:
        try:
            with open(str(path), "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerows(data)
            return True
        except Exception:
            return False

    builtins["CSV读取"] = _csv_read
    builtins["CSV写入"] = _csv_write

    # ---- 日志 ----
    def _log_message(level: str, msg: str) -> None:
        lvl = getattr(logging, level.upper(), logging.INFO)
        logging.log(lvl, msg)

    builtins["日志信息"] = lambda msg: _log_message("info", msg)
    builtins["日志警告"] = lambda msg: _log_message("warning", msg)
    builtins["日志错误"] = lambda msg: _log_message("error", msg)
    builtins["日志调试"] = lambda msg: _log_message("debug", msg)

    # ---- 时间/日期 ----
    builtins["当前时间戳"] = time.time
    builtins["格式化时间"] = lambda fmt: time.strftime(fmt)
    builtins["延迟"] = lambda secs: time.sleep(float(secs))

    # ---- 系统信息 ----
    builtins["工作目录"] = os.getcwd
    builtins["列表目录"] = os.listdir
    builtins["环境查询"] = lambda k, default="": os.environ.get(k, default)

    # ---- 序列化 ----
    builtins["JSON序列化"] = lambda obj: json.dumps(obj, ensure_ascii=False)
    builtins["JSON反序列化"] = lambda text: json.loads(text)
    builtins["pickle序列化"] = lambda obj: __import__("pickle").dumps(obj)
    builtins["pickle反序列化"] = lambda data: __import__("pickle").loads(data)

    # ---- 数学扩展 ----
    import math
    builtins["阶乘"] = math.factorial
    builtins["组合数C"] = lambda n, k: math.comb(n, k) if hasattr(math, 'comb') else __import__('math').factorial(n)//(__import__('math').factorial(k)*__import__('math').factorial(n-k))
    builtins["排列数P"] = lambda n, k: math.perm(n, k) if hasattr(math, 'perm') else __import__('math').factorial(n)//__import__('math').factorial(n-k)
    builtins["弧度转角度"] = math.degrees
    builtins["角度转弧度"] = math.radians

    # ---- 数据科学（numpy/scipy）----
    try:
        import numpy as np
        builtins["numpy数组"] = lambda *args: np.array(args)
        builtins["numpy求和"] = lambda arr: float(np.sum(arr)) if hasattr(arr, '__len__') else arr
        builtins["numpy均值"] = lambda arr: float(np.mean(arr)) if hasattr(arr, '__len__') else arr
        builtins["numpy标准差"] = lambda arr: float(np.std(arr)) if hasattr(arr, '__len__') else arr
        builtins["numpy矩阵乘"] = lambda a, b: (np.array(a) @ np.array(b)).tolist()
        builtins["numpy转置"] = lambda m: (np.array(m).T).tolist()
        builtins["numpy逆"] = lambda m: (np.linalg.inv(np.array(m))).tolist()
    except ImportError:
        pass

    # ---- asyncio ----
    try:
        import asyncio
        builtins["asyncio事件循环"] = asyncio.get_event_loop
        builtins["asyncio运行"] = lambda coro: asyncio.get_event_loop().run_until_complete(coro)
    except Exception:
        pass

    # ---- 文件监听（inotify/pyinotify 简化）----
    builtins["文件修改时间"] = lambda p: os.path.getmtime(str(p))
    builtins["文件创建时间"] = lambda p: os.path.getctime(str(p))
    builtins["文件访问时间"] = lambda p: os.path.getatime(str(p))


def register_all(builtins: dict) -> None:
    _register_standard_library(builtins)


__all__ = ["register_all"]
