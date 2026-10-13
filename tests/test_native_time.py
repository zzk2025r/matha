"""原生后端日期时间测试。

覆盖 闰年判断/月份天数/时区偏移/时区转换/日期差/星期几/日期加减 的原生语义，
以及与解释器/VM 的 parity（含 1970 前日期、世纪闰年、随机日期与未知时区）。

另覆盖非纯时钟采集族（获取时间戳/获取日期/当前日期/当前时间/获取日期时间/
获取UTC时间/格式化时间）：确定性部分做三端 parity，取当前时刻者做格式/时钟
一致性断言（其值本身非确定）。
"""
import datetime
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret
from src.mbc import compile_source, run_module
from src.mbc.native import compile_to_exe


def _run(src):
    exe = os.path.join(tempfile.gettempdir(), "pr_native_time.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    lines = r.stdout.decode("utf-8", "replace").strip().splitlines()
    return r.returncode & 0xFFFFFFFF, "\n".join(lines)


def _host(src):
    iout = "\n".join(str(v) for v in interpret(src)[0])
    vout = "\n".join(str(v) for v in run_module(compile_source(src)))
    return iout, vout


CASES = [
    ('闰年判断(1900)', "False"),
    ('闰年判断(2000)', "True"),
    ('闰年判断(2024)', "True"),
    ('闰年判断(2023)', "False"),
    ('闰年判断(1)', "False"),
    ('闰年判断(400)', "True"),
    ('月份天数(2024)(2)', "29"),
    ('月份天数(2023)(2)', "28"),
    ('月份天数(1900)(2)', "28"),
    ('月份天数(2000)(2)', "29"),
    ('月份天数(2024)(4)', "30"),
    ('月份天数(2024)(12)', "31"),
    ('时区偏移("UTC")', "0"),
    ('时区偏移("Asia/Shanghai")', "8"),
    ('时区偏移("CST")', "8"),
    ('时区偏移("America/New_York")', "-5"),
    ('时区偏移("America/Los_Angeles")', "-8"),
    ('时区偏移("Asia/Tokyo")', "9"),
    ('时区偏移("Europe/Berlin")', "1"),
    ('时区偏移("未知")', "0"),
    ('时区转换(0)("UTC")("Asia/Shanghai")', "28800"),
    ('时区转换(0)("Asia/Shanghai")("UTC")', "-28800"),
    ('时区转换(1000)("UTC")("UTC")', "1000"),
    ('日期差("2024-01-01")("2024-03-01")', "60"),
    ('日期差("2024-03-01")("2024-01-01")', "-60"),
    ('日期差("1970-01-01")("1970-01-01")', "0"),
    ('日期差("2024-02-28")("2024-03-01")', "2"),
    ('星期几("2024-01-01")', "星期一"),
    ('星期几("2024-01-07")', "星期日"),
    ('星期几("1970-01-01")', "星期四"),
    ('星期几("1969-12-31")', "星期三"),
    ('日期加减(1)("2024-02-28")', "2024-02-29"),
    ('日期加减(-1)("2024-03-01")', "2024-02-29"),
    ('日期加减(60)("2024-01-01")', "2024-03-01"),
    ('日期加减(1)("2023-12-31")', "2024-01-01"),
    ('日期加减(-1)("1970-01-01")', "1969-12-31"),
    ('日期加减(0)("2000-02-29")', "2000-02-29"),
    ('日期加减(400)("2000-01-01")', "2001-02-04"),
]


@pytest.mark.parametrize("expr,expected", CASES)
def test_pure_cases(expr, expected):
    rc, out = _run(f"输出({expr})")
    assert rc == 0 and out == expected


PARITY_EXPRS = [expr for expr, _ in CASES] + [
    '时区偏移("GMT")', '时区偏移("EST")', '时区偏移("PST")',
    '时区偏移("JST")', '时区偏移("CET")',
    '时区转换(3600)("UTC")("Asia/Tokyo")',
    '日期差("1900-01-01")("2000-01-01")',
    '日期差("1999-12-31")("2000-01-01")',
    '星期几("2000-02-29")', '星期几("1900-02-28")',
    '日期加减(-36525)("2024-01-01")',
    '日期加减(36525)("1970-01-01")',
    '日期加减(30)("1800-06-15")',
]


def test_parity_with_host():
    src = "\n".join(f"输出({e})" for e in PARITY_EXPRS)
    iout, vout = _host(src)
    assert iout == vout
    rc, nout = _run(src)
    assert rc == 0 and nout == iout


# ---- 非纯时钟采集族 ----

# 确定性：给定时间戳与格式串，三端应完全一致（均用本机本地时区）。
FMT_CASES = [
    (0, "%Y-%m-%d %H:%M:%S"),
    (1, "%Y-%m-%d %H:%M:%S"),
    (1000000, "%Y-%m-%d %H:%M:%S"),
    (1234567890, "%Y-%m-%d %H:%M:%S"),
    (262144, "%Y-%m-%d %H:%M:%S"),      # 触发 localtime 影子空间路径
    (1000000000, "%Y/%m/%d"),
    (2147483647, "%Y-%m-%d %H:%M:%S"),
    (1000000000, "今天是 %Y 年 %m 月 %d 日"),
]


@pytest.mark.parametrize("ts,fmt", FMT_CASES)
def test_format_time_parity(ts, fmt):
    expr = f'格式化时间({ts})("{fmt}")'
    iout = "\n".join(str(v) for v in interpret(f"输出({expr})")[0])
    rc, nout = _run(f"输出({expr})")
    assert rc == 0 and nout == iout


def test_now_timestamp_close_to_clock():
    before = time.time()
    rc, out = _run("输出(获取时间戳())")
    after = time.time()
    assert rc == 0
    assert before - 2 <= float(out) <= after + 2


NOW_FORMATS = {
    "获取日期": r"\d{4}-\d{2}-\d{2}",
    "当前日期": r"\d{4}-\d{2}-\d{2}",
    "当前时间": r"\d{2}:\d{2}:\d{2}",
    "获取日期时间": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}",
    "获取UTC时间": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z",
}


@pytest.mark.parametrize("name,pat", list(NOW_FORMATS.items()))
def test_now_format(name, pat):
    rc, out = _run(f"输出({name}())")
    assert rc == 0 and re.fullmatch(pat, out)


def test_now_date_matches_local_clock():
    rc, out = _run("输出(获取日期())")
    assert rc == 0
    y, m, d = map(int, re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", out).groups())
    assert abs((datetime.date(y, m, d) - datetime.date.today()).days) <= 1


PARSE_CASES = [
    ('"2001-09-09 09:46:40"', '"%Y-%m-%d %H:%M:%S"', "1000000000.0"),
    ('"2024-01-01 12:00:00"', '"%Y-%m-%d %H:%M:%S"', "1704081600.0"),
    ('"2024-02-29 23:59:59"', '"%Y-%m-%d %H:%M:%S"', "1709222399.0"),
    ('"1999-12-31 12:00:00"', '"%Y-%m-%d %H:%M:%S"', "946612800.0"),
    ('"2024/07/04 06:30:00"', '"%Y/%m/%d %H:%M:%S"', "1720045800.0"),
    ('"2024-01-02"', '"%Y-%m-%d"', "1704124800.0"),
    ('"23-05-06"', '"%y-%m-%d"', "1683302400.0"),
    ('"2024-01-01 00:00:00.5"', '"%Y-%m-%d %H:%M:%S.%f"', "1704038400.5"),
    ('"2024.01.02"', '"%Y.%m.%d"', "1704124800.0"),
    ('"2024-1-2"', '"%Y-%m-%d"', "1704124800.0"),
    ('"bad input"', '"%Y-%m-%d %H:%M:%S"', "0.0"),
    ('"2024-13-01"', '"%Y-%m-%d"', "0.0"),
    ('"2024-02-30"', '"%Y-%m-%d %H:%M:%S"', "0.0"),
    ('"2024-01-01 12:00:00 extra"', '"%Y-%m-%d %H:%M:%S"', "0.0"),
    ('"2024-01-01x"', '"%Y-%m-%d"', "0.0"),
    ('"2024-01-01 12:00:00"', '"%Y-%m-%d%"', "0.0"),
]


@pytest.mark.parametrize("text,fmt,expected", PARSE_CASES)
def test_parse_time_cases(text, fmt, expected):
    expr = f"解析时间({text})({fmt})"
    rc, out = _run(f"输出({expr})")
    assert rc == 0 and out == expected


def test_parse_time_parity_with_host():
    src = "\n".join(f"输出(解析时间({t})({f}))" for t, f, _ in PARSE_CASES)
    iout, vout = _host(src)
    assert iout == vout
    rc, nout = _run(src)
    assert rc == 0 and nout == iout


def test_host_zero_arg_builtins():
    """零参内建经 `_ignore_unit` 包装后，解释器/VM 均应正常求值。"""
    for name in ["获取时间戳", "获取日期", "当前日期", "当前时间",
                 "获取日期时间", "获取UTC时间"]:
        iout = interpret(f"输出({name}())")[0]
        vout = run_module(compile_source(f"输出({name}())"))
        assert len(iout) == 1 and len(vout) == 1
