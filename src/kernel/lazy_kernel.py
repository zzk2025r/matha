# -*- coding: utf-8 -*-
"""内核内建惰性物化层（阶段 23a）。

terminal_builtin（≈69ms 冷导入，shutil/fnmatch/re 链）、time_builtin
（≈35ms，calendar/locale 链）与 json_builtin（≈38ms，json 链）在旧形态下
被两侧注册点急切装入——任何一次求值都付出全量代价，而多数程序根本不用
终端 I/O、时间或 JSON。

本模块提供 ``LazyKernelFn``：注册点仍在内建表中放置**同名条目**（``in``/
``len``/``keys``/``defer_to_plugins`` 等清单类语义零变化），但值是首调才
import 所属内核模块并物化真实现的 callable。物化结果按 loader 缓存——
同一内核节只 import 一次、只构建一次。

形状纪律：宿主侧柯里化（``_curry_module`` lambda 链）与 VM 侧柯里化
（``_Curried`` 类）实现不同，各面经 ``make_*_builtins(curry2)`` 注入自己的
柯里化函数，物化值与旧急切值逐字节同形状；``callable(v)`` 判定为 True，
type_of/str/输出 渲染走既有 callable 分支（"Function"/"<function>"），四端
渲染语义不变。
"""
from __future__ import annotations

#: 终端 I/O 内建（src/kernel/terminal_builtin.py 注册面；两侧同名注册）
TERMINAL_BUILTIN_NAMES = (
    "输入行", "管道输入", "管道结束", "列目录", "建目录", "删除路径",
    "复制文件", "改名", "当前目录", "换目录", "路径存在", "执行Matha",
)

#: 时间内建（src/kernel/time_builtin.py 注册面）
TIME_BUILTIN_NAMES = (
    "获取时间戳", "获取日期", "获取日期时间", "获取UTC时间",
    "格式化时间", "解析时间", "当前时间", "当前日期",
    "日期加减", "日期差", "星期几", "闰年判断",
    "月份天数", "创建计时器", "时区偏移", "时区转换",
    "注册任务", "执行待办", "待办列表",
)

#: JSON 内建（src/kernel/json_builtin.py 注册面）
JSON_BUILTIN_NAMES = ("解析_JSON",)

LAZY_KERNEL_NAMES = frozenset(
    TERMINAL_BUILTIN_NAMES + TIME_BUILTIN_NAMES + JSON_BUILTIN_NAMES)


class _SectionCache:
    """同一 loader 的物化缓存：一个内核节只 import 一次、只构建一次。"""

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = None


class LazyKernelFn:
    """首调物化的内核内建占位。"""

    __slots__ = ("_load", "_key", "_impl")

    def __init__(self, load, key: str) -> None:
        self._load = load
        self._key = key
        self._impl = None

    def __call__(self, *args, **kwargs):
        impl = self._impl
        if impl is None:
            impl = self._impl = self._load()[self._key]
        return impl(*args, **kwargs)


def lazy_section(loader, names) -> dict:
    """为一节内核符号生成同名惰性占位表；loader() 返回 {名: 真实现}。"""
    cache = _SectionCache()

    def load():
        if cache.value is None:
            cache.value = loader()
        return cache.value

    return {name: LazyKernelFn(load, name) for name in names}
