# -*- coding: utf-8 -*-
"""标准库 collections_core（map/filter/reduce/sorted/join/split/gcd）行为锁。

P1 内建函数库补齐的**语义对拍**层（黄金 36-39 锁三端逐字节，本文件锁值语义）：
外部真相直接取 Python `sorted/map/filter`、`math.gcd`、`str.split/str.join`，
以 VM 输出逐值断言；vm ↔ interp 平价逐值复核（解释器为第二预言机）。

边界口径（与库文件头注释同一份契约）：
  · sorted 为稳定插入排序，等值类内部保持原序；
  · split 对齐 Python `str.split(sep)`：连续分隔符产生空段、
    `"".split(sep)==[""]`、无分隔符得整串单段；空分隔符抛错；
  · gcd 转调内核柯里化内建 最大公约数（含 0/负数/互质）。

另锁「纯脚本跑库零 `src.domains.*` import」：库走 VM 常驻、gcd 是内核
内建（register_kernel_builtins / native 砖块 17），不得把领域插件带进进程
——断言需干净解释器，起子进程（同 test_plugin_contract 口径）。
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import features  # noqa: E402
from src.kernel import exec_api  # noqa: E402

LIB = (ROOT / "matha" / "library" / "collections_core.matha").read_text(encoding="utf-8")


def _vm(src: str) -> list:
    features.set_feature("SCOPED_BLOCKS", True)
    outs, err = exec_api.run_checked(LIB + "\n" + src, mode="vm")
    features.clear_feature()
    if err is not None:
        raise err
    return list(outs)


def _interp(src: str) -> list:
    from src.interp import Interpreter
    from src.parser import parse
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse(LIB + "\n" + src))
    return list(ip.outputs)


def _both(src: str) -> list:
    """vm 值等于断言值，且 vm ↔ interp 逐值平价。返回 vm 输出便于链式断言。"""
    expected = _interp(src)
    got = _vm(src)
    assert got == expected, f"vm ↔ interp 分歧: {got!r} != {expected!r}"
    return got


# ============================================================
# 一、map / filter / reduce ↔ Python 真相
# ============================================================

MAPFILTER_SRC = """
inc = (x) => x + 1
ev = (x) => x % 2 == 0
add = (a, b) => a + b
mul = (a, b) => a * b
[map(inc, [1, 2, 3, 4])]
[map(inc, [])]
[map((x) => x * x, [1, 2, 3])]
[filter(ev, [1, 2, 3, 4, 5])]
[filter(ev, [])]
[filter((x) => x > 99, [1, 2, 3])]
[reduce(add, [1, 2, 3, 4], 0)]
[reduce(add, [], 7)]
[reduce(mul, [1, 2, 3, 4], 1)]
[reduce(add, map((x) => x * x, [1, 2, 3]), 0)]
"""

# 右侧 = Python 真相（lambda/map/filter/functools.reduce 手算入账）
MAPFILTER_TRUTH = [
    [2, 3, 4, 5],          # map(inc, [1..4])
    [],                    # 空迭代
    [1, 4, 9],             # map(平方)
    [2, 4],                # filter(偶)
    [],                    # filter 空
    [],                    # filter 全滤除
    10,                    # reduce(+)
    7,                     # reduce 空表取初值
    24,                    # reduce(×)
    14,                    # reduce ∘ map：1+4+9
]


def test_map_filter_reduce_matches_python():
    assert _vm(MAPFILTER_SRC) == MAPFILTER_TRUTH


def test_map_filter_reduce_vm_interp_parity():
    _both(MAPFILTER_SRC)


# ============================================================
# 二、sorted ↔ Python sorted（含稳定性）
# ============================================================

def _sorted_case(xs, key=None):
    src = "\n".join([
        "lt = (a, b) => a < b",
        "gt = (a, b) => a > b",
        "mod3 = (a, b) => (a % 3) < (b % 3)",
        f"[sorted({xs}, lt)]",
        f"[sorted({xs}, gt)]",
        f"[sorted({xs}, mod3)]",
    ])
    got = _both(src)
    assert got[0] == sorted(eval(xs)), f"升序偏离 Python: {xs}"
    assert got[1] == sorted(eval(xs), reverse=True), f"降序偏离 Python: {xs}"
    # 稳定器：mod3 类内保持原序 ↔ Python 稳定排序 key=x%3
    assert got[2] == sorted(eval(xs), key=lambda x: x % 3), f"稳定性偏离 Python: {xs}"


@pytest.mark.parametrize("xs", [
    "[5, 3, 1, 4, 2]",
    "[]",
    "[7]",
    "[1, 2, 3]",          # 已排序
    "[3, 2, 1]",          # 逆序
    "[2, 2, 1]",          # 等值
    "[1, 4, 2, 5, 3]",    # mod3 等值类交叉：稳定序可观察
    "[3, 1, 3, 1, 2]",
])
def test_sorted_matches_python_with_stability(xs):
    _sorted_case(xs)


# ============================================================
# 三、join ↔ Python str.join（Matha str 化口径：int 直走 str()，bool 为 True/False）
# ============================================================

def test_join_matches_python():
    src = """
[join("-", [1, 2, 3])]
[join("", [4, 5])]
[join(",", [])]
[join("+", ["x", "y", "z"])]
[join("::", ["a", "b"])]
"""
    got = _both(src)
    assert got == ["1-2-3", "45", "", "x+y+z", "a::b"]


# ============================================================
# 四、split ↔ Python str.split(sep)
# ============================================================

@pytest.mark.parametrize("s,sep", [
    ("a,b,c", ","),
    ("a,,b", ","),        # 连续分隔符 → 空段
    ("abc", ","),         # 无分隔符 → 整串单段
    ("", ","),            # 空串 → [""]
    ("a,", ","),          # 尾部分隔符 → 尾空段
    (",,", ","),         # 全空段
    ("a::b::c", "::"),    # 多字符分隔符整段匹配
    ("a:x:b", ":"),
])
def test_split_matches_python(s, sep):
    got = _both(f'[split("{s}", "{sep}")]')
    assert got == [s.split(sep)]


def test_split_empty_sep_raises_on_both_backends():
    """空分隔符报错口径：双端消息主体一致「不支持: 空分隔符」。"""
    src = LIB + '\n[split("abc", "")]'
    features.set_feature("SCOPED_BLOCKS", True)
    _, vm_err = exec_api.run_checked(src, mode="vm")
    features.clear_feature()
    assert vm_err is not None and "不支持: 空分隔符" in str(vm_err)

    from src.interp import Interpreter
    from src.parser import parse
    ip = Interpreter(debug=False)
    with pytest.raises(Exception) as ei, contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse(src))
    assert "不支持: 空分隔符" in str(ei.value)


# ============================================================
# 五、gcd ↔ math.gcd
# ============================================================

@pytest.mark.parametrize("a,b", [
    (12, 18), (0, 5), (5, 0), (0, 0), (-6, 9), (7, 13), (270, 192), (1, 1),
])
def test_gcd_matches_python(a, b):
    got = _both(f"[gcd({a}, {b})]")
    assert got == [math.gcd(a, b)]


# ============================================================
# 六、纯净门禁：跑库（含 gcd）零 src.domains.* import
# ============================================================

_PURITY_SNIPPET = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "from src import features\n"
    "from src.kernel import exec_api\n"
    f"lib = Path({str(ROOT / 'matha' / 'library' / 'collections_core.matha')!r}).read_text(encoding='utf-8')\n"
    "features.set_feature('SCOPED_BLOCKS', True)\n"
    "outs, err = exec_api.run_checked(lib + '\\n[gcd(12, 18)]\\n[map((x) => x + 1, [1, 2])]', mode='vm')\n"
    "assert err is None, err\n"
    "leaked = sorted(m for m in sys.modules if m.startswith('src.domains'))\n"
    "print(json.dumps({'out': [str(x) for x in outs], 'leak': leaked}))\n"
)


def test_library_run_imports_no_domain_modules():
    """gcd 是内核内建（register_kernel_builtins/native 砖块 17），库全走 VM
    常驻符号 —— 纯脚本执行不得把任何领域插件带进进程。"""
    proc = subprocess.run(
        [sys.executable, "-c", _PURITY_SNIPPET],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["leak"] == [], f"库执行泄漏领域 import: {payload['leak']}"
    assert payload["out"] == ["6", "[2, 3]"]
