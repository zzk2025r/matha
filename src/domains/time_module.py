"""Matha 时间模块：时间/日期操作、计时器、时区、调度。

覆盖：
  1) 时间获取与格式化
  2) 日期计算
  3) 计时器（高精度）
  4) 时区转换
  5) 定时任务调度
  6) 时间戳操作
"""
from __future__ import annotations

import calendar
import datetime
import time

# ============================================================
# 时间获取与格式化
# ============================================================

def now() -> float:
    """当前时间戳（秒）。"""
    return time.time()


def today() -> str:
    """当前日期（YYYY-MM-DD）。"""
    return datetime.date.today().isoformat()


def now_datetime() -> str:
    """当前日期时间（ISO格式）。"""
    return datetime.datetime.now().isoformat()


def now_utc() -> str:
    """当前UTC时间。"""
    return datetime.datetime.utcnow().isoformat() + "Z"


def format_time(timestamp: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间戳。"""
    return datetime.datetime.fromtimestamp(timestamp).strftime(fmt)


def parse_time(text: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> float:
    """解析时间字符串为时间戳。"""
    try:
        dt = datetime.datetime.strptime(text, fmt)
        return dt.timestamp()
    except ValueError:
        return 0.0


def time_str() -> str:
    """当前时间字符串。"""
    return datetime.datetime.now().strftime("%H:%M:%S")


def date_str() -> str:
    """当前日期字符串。"""
    return datetime.date.today().strftime("%Y-%m-%d")


# ============================================================
# 日期计算
# ============================================================

def date_add(days: int, base: str | None = None) -> str:
    """日期加减天数。"""
    d = datetime.date.today() if base is None else datetime.date.fromisoformat(base)
    return (d + datetime.timedelta(days=days)).isoformat()


def date_diff(date1: str, date2: str) -> int:
    """计算两个日期之间的天数差。"""
    d1 = datetime.date.fromisoformat(date1)
    d2 = datetime.date.fromisoformat(date2)
    return (d2 - d1).days


def day_of_week(date_str_val: str) -> str:
    """获取星期几（中文）。"""
    days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    d = datetime.date.fromisoformat(date_str_val)
    return days[d.weekday()]


def is_leap_year(year: int) -> bool:
    """判断闰年。"""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """获取月份天数。"""
    return calendar.monthrange(year, month)[1]


# ============================================================
# 计时器
# ============================================================

class Timer:
    """高精度计时器（宿主 Python 直接使用；Matha 侧见 make_timer）。"""

    def __init__(self):
        self._start: float = 0.0
        self._elapsed: float = 0.0
        self._running: bool = False

    def start(self) -> None:
        """开始计时。"""
        self._start = time.perf_counter()
        self._running = True

    def stop(self) -> float:
        """停止计时并返回秒数。"""
        if self._running:
            self._elapsed += time.perf_counter() - self._start
            self._running = False
        return self._elapsed

    def reset(self) -> None:
        """重置计时器。"""
        self._start = 0.0
        self._elapsed = 0.0
        self._running = False

    def elapsed(self) -> float:
        """获取已过时间（秒）。"""
        if self._running:
            return self._elapsed + (time.perf_counter() - self._start)
        return self._elapsed


def make_timer() -> dict:
    """创建计时器对象（极简对象/方法模型的宿主表示）。

    对象 = 字典：键为方法名，值为共享同一份可变状态的闭包。方法以「忽略一个
    占位实参」的单参形式暴露，以对齐 Matha 的 `f()` → 对占位整数 0 的应用
    （parser.py 空括号 → FuncApp(f, IntegerLit(0))），故 `t.start()` 合法。
    原生后端以「字典 + 闭包记录（env 指向状态盒）」实现同一布局，三端一致。
    """
    state = [0.0, 0.0, False]  # [start, elapsed, running]

    def _start(_unit=None) -> None:
        state[0] = time.perf_counter()
        state[2] = True

    def _stop(_unit=None) -> float:
        if state[2]:
            state[1] += time.perf_counter() - state[0]
            state[2] = False
        return state[1]

    def _reset(_unit=None) -> None:
        state[0] = 0.0
        state[1] = 0.0
        state[2] = False

    def _elapsed(_unit=None) -> float:
        if state[2]:
            return state[1] + (time.perf_counter() - state[0])
        return state[1]

    return {
        "start": _start,
        "stop": _stop,
        "reset": _reset,
        "elapsed": _elapsed,
    }


# ============================================================
# 时区转换
# ============================================================

def timezone_offset(timezone_str: str = "UTC") -> float:
    """获取时区偏移（小时）。"""
    offsets = {
        "UTC": 0, "GMT": 0,
        "CST": 8, "Asia/Shanghai": 8,
        "EST": -5, "America/New_York": -5,
        "PST": -8, "America/Los_Angeles": -8,
        "JST": 9, "Asia/Tokyo": 9,
        "CET": 1, "Europe/Berlin": 1,
    }
    return offsets.get(timezone_str, 0)


def convert_timezone(timestamp: float, from_tz: str = "UTC", to_tz: str = "UTC") -> float:
    """时区转换。"""
    offset_diff = timezone_offset(to_tz) - timezone_offset(from_tz)
    return timestamp + offset_diff * 3600


# ============================================================
# 定时调度
# ============================================================

_scheduled_tasks: list[dict] = []


def schedule_task(interval_seconds: float, task_name: str, callback) -> int:
    """注册定时任务。"""
    task = {
        "interval": interval_seconds,
        "name": task_name,
        "callback": callback,
        "next_run": time.time() + interval_seconds,
        "id": len(_scheduled_tasks),
    }
    _scheduled_tasks.append(task)
    return task["id"]


def run_pending_tasks() -> list[str]:
    """执行到期的定时任务。"""
    current = time.time()
    executed = []
    for task in _scheduled_tasks:
        if current >= task["next_run"]:
            try:
                task["callback"]()
                executed.append(task["name"])
            except Exception:
                pass
            task["next_run"] = current + task["interval"]
    return executed


def get_pending_tasks() -> list[dict]:
    """获取待执行的任务列表。"""
    return [t for t in _scheduled_tasks if time.time() < t["next_run"]]


# ============================================================
# 注册
# ============================================================

def _curry2(func):
    def w1(a):
        return lambda b: func(a, b)
    return w1


def _curry3(func):
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1


def _ignore_unit(func):
    """把零参函数包装为「忽略一个占位实参」的单参函数。

    Matha 的 `f()` 会被解析为对占位整数 0 的应用（parser.py 空括号 →
    FuncApp(func, IntegerLit(0))），故零参内建必须以单参形式暴露，否则
    `获取日期()` 会以 0 作为实参调用而抛 TypeError。
    """
    def w(_unit=None):
        return func()
    return w


def _register_time(builtins: dict) -> None:
    builtins["获取时间戳"] = _ignore_unit(now)
    builtins["获取日期"] = _ignore_unit(today)
    builtins["获取日期时间"] = _ignore_unit(now_datetime)
    builtins["获取UTC时间"] = _ignore_unit(now_utc)
    builtins["格式化时间"] = _curry2(format_time)
    builtins["解析时间"] = _curry2(parse_time)
    builtins["当前时间"] = _ignore_unit(time_str)
    builtins["当前日期"] = _ignore_unit(date_str)
    builtins["日期加减"] = _curry2(date_add)
    builtins["日期差"] = _curry2(date_diff)
    builtins["星期几"] = day_of_week
    builtins["闰年判断"] = is_leap_year
    builtins["月份天数"] = _curry2(days_in_month)
    builtins["创建计时器"] = _ignore_unit(make_timer)
    builtins["时区偏移"] = timezone_offset
    builtins["时区转换"] = _curry3(convert_timezone)
    builtins["注册任务"] = _curry3(schedule_task)
    builtins["执行待办"] = _ignore_unit(run_pending_tasks)
    builtins["待办列表"] = _ignore_unit(get_pending_tasks)


def _time_symtab_names() -> list[str]:
    return [
        "获取时间戳", "获取日期", "获取日期时间", "获取UTC时间",
        "格式化时间", "解析时间", "当前时间", "当前日期",
        "日期加减", "日期差", "星期几", "闰年判断",
        "月份天数", "创建计时器", "时区偏移", "时区转换",
        "注册任务", "执行待办", "待办列表",
    ]


__all__ = [
    "now", "today", "now_datetime", "now_utc",
    "format_time", "parse_time", "time_str", "date_str",
    "date_add", "date_diff", "day_of_week",
    "is_leap_year", "days_in_month", "Timer", "make_timer",
    "timezone_offset", "convert_timezone",
    "schedule_task", "run_pending_tasks", "get_pending_tasks",
    "_register_time", "_time_symtab_names",
]
