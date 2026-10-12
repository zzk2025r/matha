"""Matha 通用工具：字符串、正则、日期、并发、IO。"""
from __future__ import annotations

import base64
import datetime
import hashlib
import math
import os
import queue
import random
import shutil
import string
import tempfile
import threading
import time
import uuid
import zlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class StringUtils:
    """字符串工具。"""

    @staticmethod
    def reverse(s: str) -> str:
        return s[::-1]

    @staticmethod
    def capitalize(s: str) -> str:
        return s.capitalize()

    @staticmethod
    def lower(s: str) -> str:
        return s.lower()

    @staticmethod
    def upper(s: str) -> str:
        return s.upper()

    @staticmethod
    def strip(s: str) -> str:
        return s.strip()

    @staticmethod
    def lstrip(s: str) -> str:
        return s.lstrip()

    @staticmethod
    def rstrip(s: str) -> str:
        return s.rstrip()

    @staticmethod
    def split(s: str, sep: str = " ") -> list[str]:
        return s.split(sep)

    @staticmethod
    def join(parts: list[str], sep: str = " ") -> str:
        return sep.join(parts)

    @staticmethod
    def replace(s: str, old: str, new: str) -> str:
        return s.replace(old, new)

    @staticmethod
    def contains(s: str, sub: str) -> bool:
        return sub in s

    @staticmethod
    def startswith(s: str, prefix: str) -> bool:
        return s.startswith(prefix)

    @staticmethod
    def endswith(s: str, suffix: str) -> bool:
        return s.endswith(suffix)

    @staticmethod
    def slice(s: str, start: int, end: int = None) -> str:
        return s[start:end]

    @staticmethod
    def trim(s: str) -> str:
        return s.strip()

    @staticmethod
    def format(template: str, **kwargs) -> str:
        return template.format(**kwargs)

    @staticmethod
    def pad(s: str, width: int,
               fillchar: str = " ") -> str:
        return s.ljust(width, fillchar)

    @staticmethod
    def center(s: str, width: int,
                  fillchar: str = " ") -> str:
        return s.center(width, fillchar)

    @staticmethod
    def count(s: str, sub: str) -> int:
        return s.count(sub)

    @staticmethod
    def index(s: str, sub: str) -> int:
        return s.index(sub)

    @staticmethod
    def is_alpha(s: str) -> bool:
        return s.isalpha()

    @staticmethod
    def is_digit(s: str) -> bool:
        return s.isdigit()

    @staticmethod
    def is_alnum(s: str) -> bool:
        return s.isalnum()

    @staticmethod
    def is_empty(s: str) -> bool:
        return len(s) == 0

    @staticmethod
    def to_chinese_chars(s: str) -> str:
        return s

    @staticmethod
    def random_string(length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def to_base64(s: str) -> str:
        return base64.b64encode(s.encode()).decode()

    @staticmethod
    def from_base64(s: str) -> str:
        return base64.b64decode(s).decode()


class MathUtils:
    """数学工具。"""

    @staticmethod
    def factorial(n: int) -> int:
        if n <= 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

    @staticmethod
    def fibonacci(n: int) -> int:
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @staticmethod
    def gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a

    @staticmethod
    def lcm(a: int, b: int) -> int:
        return abs(a * b) // MathUtils.gcd(a, b)

    @staticmethod
    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        for i in range(2, int(math.sqrt(n)) + 1):
            if n % i == 0:
                return False
        return True

    @staticmethod
    def power(base: float, exp: float) -> float:
        return math.pow(base, exp)

    @staticmethod
    def sqrt(x: float) -> float:
        return math.sqrt(x)

    @staticmethod
    def log(x: float, base: float = math.e) -> float:
        return math.log(x, base)

    @staticmethod
    def sin(x: float) -> float:
        return math.sin(x)

    @staticmethod
    def cos(x: float) -> float:
        return math.cos(x)

    @staticmethod
    def tan(x: float) -> float:
        return math.tan(x)

    @staticmethod
    def pi() -> float:
        return math.pi

    @staticmethod
    def e() -> float:
        return math.e

    @staticmethod
    def random_int(min_val: int = 0,
                      max_val: int = 100) -> int:
        return random.randint(min_val, max_val)

    @staticmethod
    def random_float(min_val: float = 0.0,
                        max_val: float = 1.0) -> float:
        return random.uniform(min_val, max_val)

    @staticmethod
    def clamp(value: float,
                 min_val: float, max_val: float) -> float:
        return max(min_val, min(value, max_val))

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    @staticmethod
    def clamp_angle(angle: float) -> float:
        return angle % 360


class DateTime:
    """日期时间工具。"""

    @staticmethod
    def now() -> datetime.datetime:
        return datetime.datetime.now()

    @staticmethod
    def today() -> datetime.date:
        return datetime.date.today()

    @staticmethod
    def from_timestamp(ts: float) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(ts)

    @staticmethod
    def format(dt: datetime.datetime,
                  fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        return dt.strftime(fmt)

    @staticmethod
    def parse(s: str,
                 fmt: str = "%Y-%m-%d %H:%M:%S"
                 ) -> datetime.datetime:
        return datetime.datetime.strptime(s, fmt)

    @staticmethod
    def add_days(dt: datetime.date,
                    days: int) -> datetime.date:
        return dt + datetime.timedelta(days=days)

    @staticmethod
    def add_hours(dt: datetime.datetime,
                     hours: int) -> datetime.datetime:
        return dt + datetime.timedelta(hours=hours)

    @staticmethod
    def diff(dt1: datetime.datetime,
                dt2: datetime.datetime) -> float:
        return (dt2 - dt1).total_seconds()

    @staticmethod
    def timestamp() -> float:
        return time.time()


class FileUtils:
    """文件工具。"""

    @staticmethod
    def read(path: str) -> str:
        with open(path) as f:
            return f.read()

    @staticmethod
    def write(path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

    @staticmethod
    def append(path: str, content: str) -> None:
        with open(path, "a") as f:
            f.write(content)

    @staticmethod
    def exists(path: str) -> bool:
        return os.path.exists(path)

    @staticmethod
    def remove(path: str) -> bool:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @staticmethod
    def mkdir(path: str) -> bool:
        os.makedirs(path, exist_ok=True)
        return True

    @staticmethod
    def listdir(path: str = ".") -> list[str]:
        return os.listdir(path)

    @staticmethod
    def glob(pattern: str) -> list[str]:
        import glob as g
        return g.glob(pattern)

    @staticmethod
    def copy(src: str, dst: str) -> bool:
        shutil.copy2(src, dst)
        return True

    @staticmethod
    def move(src: str, dst: str) -> bool:
        shutil.move(src, dst)
        return True

    @staticmethod
    def get_size(path: str) -> int:
        return os.path.getsize(path)

    @staticmethod
    def get_extension(path: str) -> str:
        return os.path.splitext(path)[1]

    @staticmethod
    def basename(path: str) -> str:
        return os.path.basename(path)

    @staticmethod
    def dirname(path: str) -> str:
        return os.path.dirname(path)

    @staticmethod
    def join_paths(*paths: str) -> str:
        return os.path.join(*paths)

    @staticmethod
    def create_temp_file() -> str:
        return tempfile.mktemp()

    @staticmethod
    def create_temp_dir() -> str:
        return tempfile.mkdtemp()


class ConcurrentUtils:
    """并发工具。"""

    @staticmethod
    def async_run(coro: Callable) -> Any:
        return coro()

    @staticmethod
    def thread_pool(func: Callable,
                       items: list,
                       workers: int = 4) -> list:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(func, item)
                       for item in items]
            for future in futures:
                results.append(future.result())
        return results

    @staticmethod
    def parallel_map(func: Callable,
                        items: list,
                        workers: int = 4) -> list:
        return ConcurrentUtils.thread_pool(func, items, workers)

    @staticmethod
    def async_gather(*coros: Callable) -> list:
        return [coro() for coro in coros]

    @staticmethod
    def async_sleep(duration: float) -> None:
        time.sleep(duration)

    @staticmethod
    def mutex() -> threading.Lock:
        return threading.Lock()

    @staticmethod
    def semaphore(max_count: int = 1) -> threading.Semaphore:
        return threading.Semaphore(max_count)

    @staticmethod
    def future(func: Callable, *args,
                  **kwargs) -> threading.Thread:
        t = threading.Thread(target=func, args=args,
                             kwargs=kwargs)
        t.start()
        return t

    @staticmethod
    def queue() -> queue.Queue:
        return queue.Queue()


class UUID:
    """UUID 工具。"""

    @staticmethod
    def uuid4() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def uuid1() -> str:
        return str(uuid.uuid1())

    @staticmethod
    def uuid5(namespace: str, name: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


class HashUtils:
    """哈希工具。"""

    @staticmethod
    def md5(data: str) -> str:
        return hashlib.md5(data.encode()).hexdigest()

    @staticmethod
    def sha1(data: str) -> str:
        return hashlib.sha1(data.encode()).hexdigest()

    @staticmethod
    def sha256(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def sha512(data: str) -> str:
        return hashlib.sha512(data.encode()).hexdigest()

    @staticmethod
    def blake2b(data: str,
                   size: int = 64) -> str:
        return hashlib.blake2b(data.encode(),
                               digest_size=size).hexdigest()

    @staticmethod
    def blake2s(data: str,
                   size: int = 32) -> str:
        return hashlib.blake2s(data.encode(),
                               digest_size=size).hexdigest()

    @staticmethod
    def crc32(data: str) -> int:
        return zlib.crc32(data.encode())

    @staticmethod
    def hash_file(path: str) -> str:
        return HashUtils.sha256(FileUtils.read(path))


def create_string_utils() -> StringUtils:
    return StringUtils()


def create_math_utils() -> MathUtils:
    return MathUtils()


def create_date_time() -> DateTime:
    return DateTime()


def create_file_utils() -> FileUtils:
    return FileUtils()


def create_concurrent_utils() -> ConcurrentUtils:
    return ConcurrentUtils()


def create_uuid() -> UUID:
    return UUID()


def create_hash_utils() -> HashUtils:
    return HashUtils()


# ============================================================
# 内置注册
# ============================================================

def _register_general(builtins: dict) -> None:
    builtins["创建字符串工具"] = create_string_utils
    builtins["创建数学工具"] = create_math_utils
    builtins["创建日期时间"] = create_date_time
    builtins["创建文件工具"] = create_file_utils
    builtins["创建并发工具"] = create_concurrent_utils
    builtins["创建UUID"] = create_uuid
    builtins["创建哈希工具"] = create_hash_utils


def _general_names() -> list[str]:
    return ["创建字符串工具", "创建数学工具",
            "创建日期时间", "创建文件工具",
            "创建并发工具", "创建UUID",
            "创建哈希工具"]


__all__ = [
    "StringUtils", "MathUtils", "DateTime",
    "FileUtils", "ConcurrentUtils", "UUID",
    "HashUtils",
    "create_string_utils", "create_math_utils",
    "create_date_time", "create_file_utils",
    "create_concurrent_utils", "create_uuid",
    "create_hash_utils",
    "_register_general", "_general_names",
]
