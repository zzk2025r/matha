"""向后兼容垫片：时间实现已下沉为内核模块 src.kernel.time_builtin。

阶段 1 起，时间是语言内建符号的实现（VM / 原生后端均依赖），不再属于领域层。
为避免一次性改动全部引用点（src.domains.registry、src.semantic、
tests/test_native_time.py、test_full.py 等），本模块保留原路径并原样转发。

新代码请直接 import src.kernel.time_builtin；本垫片仅服务于历史引用，
后续阶段收敛完成后可移除。
"""
from __future__ import annotations

from src.kernel.time_builtin import (  # noqa: F401
    Timer,
    convert_timezone,
    date_add,
    date_diff,
    date_str,
    day_of_week,
    days_in_month,
    format_time,
    get_pending_tasks,
    is_leap_year,
    make_timer,
    now,
    now_datetime,
    now_utc,
    parse_time,
    run_pending_tasks,
    schedule_task,
    time_str,
    timezone_offset,
    today,
    _ignore_unit,
    _register_time,
    _time_symtab_names,
)

#: 定时任务表是共享可变状态，必须由内核模块独占；此处以属性转发保持同一对象。
from src.kernel.time_builtin import _scheduled_tasks  # noqa: F401

__all__ = [
    "now", "today", "now_datetime", "now_utc",
    "format_time", "parse_time", "time_str", "date_str",
    "date_add", "date_diff", "day_of_week",
    "is_leap_year", "days_in_month", "Timer", "make_timer",
    "timezone_offset", "convert_timezone",
    "schedule_task", "run_pending_tasks", "get_pending_tasks",
    "_register_time", "_time_symtab_names",
]
