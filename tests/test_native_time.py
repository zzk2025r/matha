"""原生后端日期时间（纯函数）测试。

覆盖 闰年判断/月份天数/时区偏移/时区转换/日期差/星期几/日期加减 的原生语义，
以及与解释器/VM 的 parity（含 1970 前日期、世纪闰年、随机日期与未知时区）。
"""
import os
import subprocess
import sys
import tempfile
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
