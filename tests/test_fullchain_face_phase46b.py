# -*- coding: utf-8 -*-
"""阶段 46b-3 全链同像锁：**一个**原生映像里跑完「读盘 → Matha 编译器 → Matha VM」。

**这一档量的是什么**：任务 #247/#248 的「全链阻塞项」原状是——原生映像里跑不了
`输出(a is b)` 这类源，因为发射器不认 BINOP `is`（`NativeNotSupported: 原生后端暂不
支持二元运算 'is'`，构建期 fail-closed）。`src/mbc/native.py` 补上 `is` 发射后，
五片配方（`matha/lexer.matha` + `matha/stdlib.matha` + `matha/parser.matha` +
`matha/compiler_matha.matha` + `matha/vm.matha`）第一次能在**同一个无导入表 PE64**
里完成整条自举链：

    标准库.read_file(path)        ← 映像自己 open 盘（src/mbc/native.py 的 FS 载体）
      → 编译器.编译(src)          ← Matha 自己写的编译面（matha/compiler_matha.matha:17）
        → 字节码虚拟机.运行M3V(m)  ← Matha 自己写的 VM（matha/vm.matha:18）

Python 在本档只做两件事：把这五片源交给发射器、跑产物。它不参与任何判定——判定
由手算字面量承担（口径承继阶段 44 拍板「允许 Python 仅作种子，最终判定用无 Python
的 Matha 原生映像自证」+ 阶段 46c「跑起来了不等于正确」）。

**锁清单**：

- 46b3-1 十份真语料的逐份全链读数（8 条手算 + 1 条规模 + 1 条诚实拒绝）
- 46b3-2 A/B 双构建：PE 逐字节相同 + 读数逐字相同
- 46b3-3 同像三跑：同一映像连跑三次逐字相同
- 46b3-4 手算表改一个字必须与映像读数不同判
- 46b3-5 **盘上内容承重**：同一个映像读一份被改过一个字的语料副本，读数必须随盘变
- 46b3-6/7 **编译片 / VM 片承重**：配方里抽掉 `compiler_matha` / `vm.matha`，对应
  模块名在映像内必须变成 `未定义变量 '编译器'` / `未定义变量 '字节码虚拟机'`
- 46b3-8/9 `is` 的**两条路**：①驱动源经 Python MBC 编译 → 原生 `is` 发射；②语料在
  映像内经 `编译器.编译` → `字节码虚拟机.运行M3V` → `matha/vm.matha` 的 应用运算 分发。
  两条路都要给出「身份 vs 相等」的可判读数（`a is b` 假而 `a = b` 真）
- 46b3-10 **`is` 优先级的双面分歧取证**（46b3 新发现，登记不修）：宿主把 `is` 放在
  关系层（`src/parser.py:1876-1884`，松于 `+`），boot 镜像把它放在移位层
  （`matha/parser.matha:626-628`，紧于 `+`）→ `1 + 1 is 2` 在两条路上不同判。
  本条锁的是**现状**与源行依据，反转条件写在该条 docstring
- 46b3-11 同像内两次独立编译同判（编译面无可变状态泄漏）
- 46b3-12 `read_file` 缺路径的静默 null 现状锁（原生 FS 载体的假成功，登记不修）
- 46b3-13 **共像符号串扰取证**：boot 六片 + `vm.matha` 时，解释面读数被
  `matha/vm.matha` 的同名内部函数 `应用运算` 覆盖成 `未知运算符: =`（现状锁）
- 46b3-14 零 Python 裁判边界：本档只 import 构建面
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

# 只允许构建面：发射器 + 编译面。宿主解释器 / Python VM / boot 链会话一面都不进。
from src.mbc import native                                    # noqa: E402
from src.mbc.compiler import compile_sources                  # noqa: E402

#: 五片配方：刻意**不带**解释面（`matha/interp_matha.matha` / `matha/loader.matha`）。
#: 理由见 46b3-13——`interp_matha` 与 `vm.matha` 各自定义同名内部函数 `应用运算`，
#: 扁平链接产物层后者覆盖前者，把解释面读数打成 `未知运算符: =`。全链自证只需
#: 词法/标准库/语法/编译/VM 五片，解释面的收口另立任务（链接面模块符号作用域）。
_FIVE = ("matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
         "matha/compiler_matha.matha", "matha/vm.matha")
_SRC = {f: (_ROOT / f).read_text(encoding="utf-8") for f in _FIVE}

#: boot 六片（46b3-13 的共像串扰取证用）
_BOOT_FILES = ("matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha",
               "matha/interp_matha.matha", "matha/loader.matha")

_EXES: dict[str, str] = {}


def _exe(tag: str, sources: list[str]) -> str:
    """一次构建、多锁复用；固定名带 46b3 前缀，不与 p45/p46b/p46c 的映像争用。"""
    if tag not in _EXES:
        p = os.path.join(tempfile.gettempdir(), f"p46b3_{tag}.exe")
        Path(p).write_bytes(native.emit_exe(compile_sources(sources)))
        _EXES[tag] = p
    return _EXES[tag]


def _main_sources() -> list[str]:
    return [_SRC[f] for f in _FIVE] + [MAIN_DRV]


def _run(path: str) -> tuple[int, dict[str, str], str]:
    """跑映像，返回 (退出码, `KEY -> 余下文本`, stderr)。

    自举链源末尾的自测块会在映像装载时产若干回声行（如 `matha/parser.matha` 的
    "1"），它们不带 `|`，天然落在 key 表外——所以这里按「首段是 KEY」收表，而不是
    按固定头行数切片（五片配方与 boot 六片配方的回声行数不同，切片会错身）。
    """
    r = subprocess.run([path], capture_output=True, timeout=1800)
    rows: dict[str, str] = {}
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        if "|" in ln:
            k, _, v = ln.partition("|")
            if re.fullmatch(r"[A-Za-z0-9_]+", k):
                rows[k] = v
    return r.returncode & 0xFFFFFFFF, rows, r.stderr.decode("utf-8", "replace")


# ================================================== 语料清单（10 份 + 1 份改字副本）

#: 逐份手算依据见 `_FULL_ROWS` 的注释。
_FILES = [
    "matha/examples/01_arithmetic.matha",
    "matha/examples/02_functions.matha",
    "matha/examples/03_set_iter.matha",
    "matha/examples/04_pipeline.matha",
    "matha/examples/05_sensor_read.matha",
    "matha/examples/06_main.matha",
    "matha/examples/06_sub.matha",
    "golden_tests/cases/01_arithmetic_and_relations.matha",
    "matha/lexer.matha",
    "matha/bootstrap_test_v2.matha",
]

#: 46b3-5 的反控副本：`matha/examples/01_arithmetic.matha` 只把 `a=2` 改成 `a=3`。
#: 手算：a + b * c = 3 + 3*4 = **15**；a ^ 10 = 3^10 = **59049**；^9 = **3**；^16 = **4**。
_MUT_PATH = Path(tempfile.gettempdir()) / "p46b3_mut_arith.matha"
_MUT_SRC = (_ROOT / "matha/examples/01_arithmetic.matha").read_text(
    encoding="utf-8").replace("a=2，b=3，c=4", "a=3，b=3，c=4")
_MUT_PATH.write_text(_MUT_SRC, encoding="utf-8")
assert "a=3，b=3，c=4" in _MUT_PATH.read_text(encoding="utf-8"), "改字副本没改到盘上"

# 移位层语料（46b3-10）：链面读数 = 映像内编译 + 映像内 VM；原生面读数 = 驱动源被
# Python MBC 编译后由映像直接执行。两路必须分开标出，否则会误读成「同一张表」。
_PREC = [
    "1 + 1 is 2",
    "(1 + 1) is 2",
    "1 + (1 is 2)",
    "2 is 2",
    "1 is 2",
    "2 + 3 is 5",
    "3 is 3 + 0",
    "1 < 2 is 真",
]


def _drv_paths(items: list[str]) -> str:
    """把语料清单写成映像内可用的绝对路径串（临时副本已带盘符，不再前缀仓库根）。"""
    root = _ROOT.as_posix()
    return ", ".join(f'"{p if ":" in p else root + "/" + p}"' for p in items)


# ================================================== 主驱动（五片共像，一次跑全）

# 逐份：读盘 → 编译 → 打印模块规模 → 运行 → 打印 VM 的输出表。
# 规模行 `BCM|n常量|n主码|n函数` 取自编译面自己的模块 dict（`常量/主码/函数`），
# 运行读数取自 `字节码虚拟机.运行M3V` 的 `输出指针[1]`（matha/vm.matha:1167 起）。
_LOOP = '''
files = [{paths}]
i = 0
while (i < len(files)) {
  rd = 调用捕获(() => 标准库.read_file(files[i]))([])
  输出("F" + str(i) + "RD|" + rd[0])
  cm = 调用捕获(() => 编译器.编译(rd[1]))([])
  输出("F" + str(i) + "BC|" + cm[0])
  if (cm[0] = "__正常__") {
    n = 调用捕获(() => str(len(cm[1].常量)) + "|" + str(len(cm[1].主码)) + "|" + str(len(cm[1].函数)))([])
    输出("F" + str(i) + "BCM|" + n[1])
    rr = 调用捕获(() => 字节码虚拟机.运行M3V(cm[1]))([])
    输出("F" + str(i) + "RUN|" + rr[0])
    输出("F" + str(i) + "OUT|" + str(rr[1]))
  } else {
    输出("F" + str(i) + "BCE|" + str(cm[1]))
  }
  i = i + 1
}
'''

# `is` 的两条路（46b3-8 / 46b3-9）。ID 段的字符串就是驱动源里的字面量，Python
# 不参与判定；a/b 是两个**内容相同但不同对象**的列表，正是身份 vs 相等的分界。
_ID = '''
let a = [1, 2]
let b = [1, 2]
输出("ID1|" + str(a is a))
输出("ID2|" + str(a is b))
输出("ID3|" + str(a = b))
输出("ID4|" + str(null is null))
输出("ID5|" + str(1 is 1))
输出("ID6|" + str("ab" is "ab"))
输出("ID7|" + str(1.5 is 1.5))
let f = (x) => x + 1
输出("ID8|" + str(f is f))
'''

# 路 ②：语料进**字符串** → 映像内 `编译器.编译` → 映像内 `字节码虚拟机.运行M3V`。
# 这条路上 `is` 要过三层：Matha 词法/语法（`是中缀is`）→ Matha 编译面发射 BINOP
# "is" → vm.matha 的 应用运算 `op = "is"` 臂 → 原生 `is`。
_CHAIN = r'''
q = chr(34)
cs = "let a = [1, 2]" + chr(10)
cs = cs + "let b = [1, 2]" + chr(10)
cs = cs + "输出(a is a)" + chr(10)
cs = cs + "输出(a is b)" + chr(10)
cs = cs + "输出(a = b)" + chr(10)
cs = cs + "输出(1 is 1)" + chr(10)
cs = cs + "输出(1 + 1 is 2)" + chr(10)
cs = cs + "输出(" + q + "ab" + q + " is " + q + "ab" + q + ")" + chr(10)
cb = 调用捕获(() => 编译器.编译(cs))([])
输出("CBC|" + cb[0])
cr = 调用捕获(() => 字节码虚拟机.运行M3V(cb[1]))([])
输出("CRUN|" + cr[0])
输出("COUT|" + str(cr[1]))
'''

# 46b3-11：同一映像内两次独立编译同一份源，模块 dict 渲染必须逐字相同。
_TWICE = '''
ta = 调用捕获(() => 编译器.编译("输出(7)"))([])
tb = 调用捕获(() => 编译器.编译("输出(7)"))([])
输出("SAMEBC|" + str(str(ta[1]) = str(tb[1])))
'''

# 46b3-10 的移位层表：每行一个 case。P{i}D 只给前三个（模块 dict 渲染较长，足以
# 钉住解析形状），P{i}V 是链面读数，N{i}V 是原生直接路读数。
_PREC_LINES = []
for _i, _c in enumerate(_PREC):
    _src = f'ss = "输出({_c})"'
    _PREC_LINES.append(_src)
    _PREC_LINES.append('pc = 调用捕获(() => 编译器.编译(ss))([])')
    if _i < 3:
        _PREC_LINES.append(f'输出("P{_i}D|" + str(pc[1]))')
    _PREC_LINES.append(f'输出("P{_i}T|" + pc[0])')
    _PREC_LINES.append('pv = 调用捕获(() => 字节码虚拟机.运行M3V(pc[1]))([])')
    _PREC_LINES.append(f'输出("P{_i}V|" + pv[0] + "|" + str(pv[1]))')
    _PREC_LINES.append(f'输出("N{_i}V|" + str(调用捕获(() => {_c})([])[1]))')

# 46b3-12：原生 FS 载体对**不存在**路径的现行读数（`src/mbc/native.py:7674` 起
# `_emit_builtin_read_file` 失败 → `rf_fail` 返 `null_obj`，而宿主
# `src/interp.py:631 builtin_read_file` 抛 `读文件失败: {{e}}`）。
_MISS = '''
ms = 调用捕获(() => 标准库.read_file("{missing}"))([])
输出("MISS|" + ms[0] + "|" + str(ms[1]))
'''

_ROOT_POSIX = _ROOT.as_posix()


def _small_drv() -> str:
    return _SMALL_DRV.replace("{arith}", f"{_ROOT_POSIX}/matha/examples/01_arithmetic.matha")


MAIN_DRV = (_LOOP.replace("{paths}", _drv_paths(_FILES + [str(_MUT_PATH).replace("\\", "/")]))
            + _ID + _CHAIN + _TWICE + "\n".join(_PREC_LINES) + "\n" + _MISS)


# ================================================== 手算读数表

#: `十份真语料 + 一份改字副本` 的全链读数。每行 = (RD, BC, BCM, RUN, OUT)。
#: 逐条依据：
#:  F0  `matha/examples/01_arithmetic.matha`：a=2,b=3,c=4 → `a + b * c`=**14**、
#:      `a ^ 10`=**1024**、`^9`=**3**、`^16`=**4**（VM 面走 `matha/vm.matha` 的
#:      应用一元 sqrt → 完全平方回退整数；解释面给 3.0/4.0，即 41-② 已登记口径，
#:      本档不引解释面）。四条 `#：[...]` 语句 → 输出表四项。
#:  F1  `02_functions.matha`：三条 `#：[...]` 在 `？#：{}` 标签块形态下产的是
#:      **块名串** `['incx', 'doublex', 'hx']`——读数正确但对手算无判别力（同 46b
#:      的「退化」标注），本档如实登记为退化，不当作证据。nfunc=5 是判别位。
#:  F2  `03_set_iter.matha`：sum = 1+2+…+10 = **55**。
#:  F3  `04_pipeline.matha`：records = **0**。
#:  F4  `05_sensor_read.matha`：temp = **25.6**。
#:  F5  `06_main.matha`：area = x*y = 5*3 = **15**、端口 = **8080**、area = **15**。
#:  F6  `06_sub.matha`：total = area * 单价 = 15*10 = **150**。
#:  F7  `golden_tests/cases/01_arithmetic_and_relations.matha`：2 + 3 * 4 = **14**、
#:      `10 >= 5` = **True**、`"func" = "func"` = **True**。
#:  F8  `matha/lexer.matha`：**编译面自己编译自己的词法器**（1600 行真源）→
#:      规模读数 1590 常量 / 344 主码 / 49 函数、运行无输出。非手算，作规模锁。
#:  F9  `matha/bootstrap_test_v2.matha`：编译正常、VM 运行如实报
#:      `未定义变量 '加载模块'`——该名的宿主臂不在五片配方里，**不许**给假读数。
#:  F10 改字副本（46b3-5 反控）：15 / 59049 / 3 / 4。
_FULL_ROWS = {
    "F0": ("__正常__", "__正常__", "16|21|0", "__正常__", "[14, 1024, 3, 4]"),
    "F1": ("__正常__", "__正常__", "16|21|5", "__正常__", "['incx', 'doublex', 'hx']"),
    "F2": ("__正常__", "__正常__", "67|69|0", "__正常__", "[55]"),
    "F3": ("__正常__", "__正常__", "9|11|0", "__正常__", "[0]"),
    "F4": ("__正常__", "__正常__", "5|7|0", "__正常__", "[25.6]"),
    "F5": ("__正常__", "__正常__", "15|19|0", "__正常__", "[15, 8080, 15]"),
    "F6": ("__正常__", "__正常__", "11|13|0", "__正常__", "[150]"),
    "F7": ("__正常__", "__正常__", "9|13|0", "__正常__", "[14, True, True]"),
    "F8": ("__正常__", "__正常__", "1590|344|49", "__正常__", "[]"),
    "F9": ("__正常__", "__正常__", "129|175|5", "__异常__", "未定义变量 '加载模块'"),
    "F10": ("__正常__", "__正常__", "16|21|0", "__正常__", "[15, 59049, 3, 4]"),
}

#: `is` 身份矩阵（路 ①：驱动源 → Python MBC 编译 → 原生发射）。依据见
#: `src/mbc/native.py` 的 `elif sym == "is"` 分支注释：原生值模型里可判定的身份 =
#: tagged raw 逐位相同。ID6/ID7 与 Python `is` 的口径分歧（intern / 常量复用）是
#: **刻意不追随**的：宿主那侧的 "ab" is "ab" 为真来自实现细节而非语言定义。
_ID_WANT = {
    "ID1": "True",     # a is a        同一对象
    "ID2": "False",    # a is b        两个不同列表对象（内容相同）
    "ID3": "True",     # a = b         相等 → 与 ID2 构成本档的身份 vs 相等分界
    "ID4": "True",     # null is null  同一 tagged 原元
    "ID5": "True",     # 1 is 1        tagged 小整数 raw 即值
    "ID6": "False",    # "ab" is "ab"  每次 LOAD_CONST 重物化（不追随 interning）
    "ID7": "False",    # 1.5 is 1.5    浮点每次新装箱
    "ID8": "True",     # f is f        闭包值同一对象
}

#: 路 ② 的六条 `输出` 读数（同 F 段的语料表；最后一项 None 属 46b3-10 的优先级形态）。
_CHAIN_IS_WANT = "[True, False, True, True, None, False]"

#: 46b3-10 移位层表：`链面读数 / 原生面读数`（`P{i}V` / `N{i}V` 实测）。
_PREC_WANT = [
    ("[None]", "True"),          # 1 + 1 is 2   链面 = 1 + (1 is 2) → None；原生 = (1+1) is 2
    ("[True]", "True"),          # (1 + 1) is 2 显式括号后两路一致
    ("[None]", "None"),          # 1 + (1 is 2) 显式括号后两路一致
    ("[True]", "True"),          # 2 is 2
    ("[False]", "False"),        # 1 is 2
    ("[None]", "True"),          # 2 + 3 is 5   同形态 1
    ("[None]", "True"),          # 3 is 3 + 0   同形态 1 的镜像（右侧 3 + 0）
    ("[False]", "不可调用的值"),  # 1 < 2 is 真  两路皆非「正常布尔」，形态存疑，只锁实测
]


# ============================================================ 46b3-1 全链读数

def test_46b3_01_full_chain_readings_inside_one_native_image():
    """五片共像：逐份读盘 → 编译 → VM 运行，11 行读数与手算表逐字相同。

    这是 #248「boot 全链进原生映像运行」的正面判据：不是「跑起来了」，而是每份
    语料的输出表都能由源文件手算出来（依据见 `_FULL_ROWS` 注释），且规模位
    （n常量/n主码/n函数）与非正常路径（F9 的诚实拒绝）一并锁住。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:300]}"
    for key, want in _FULL_ROWS.items():
        got = tuple(rows.get(f"{key}{fld}", f"<缺行 {key}{fld}>")
                    for fld in ("RD", "BC", "BCM", "RUN", "OUT"))
        assert got == want, f"{key} 全链读数不符\n实测 {got}\n手算 {want}"


# ============================================================ 46b3-2 A/B 双构建

def test_46b3_02_two_independent_builds_are_byte_identical():
    """同一配方两次独立发射 → PE 逐字节相同，且两份产物的全链读数逐字相同。

    确定性判据必须绕开 `_EXES` 缓存：这里真发两次 `compile_sources` + `emit_exe`。
    """
    a = native.emit_exe(compile_sources(_main_sources()))
    b = native.emit_exe(compile_sources(_main_sources()))
    assert a == b, f"两次发射的 PE 不同：{len(a)} vs {len(b)} 字节"
    pa = Path(tempfile.gettempdir()) / "p46b3_ab_a.exe"
    pb = Path(tempfile.gettempdir()) / "p46b3_ab_b.exe"
    pa.write_bytes(a)
    pb.write_bytes(b)
    _, ra, _ = _run(str(pa))
    _, rb, _ = _run(str(pb))
    assert ra == rb, f"逐字节相同的产物读数不同：{set(ra.items()) ^ set(rb.items())}"
    assert ra["F0OUT"] == _FULL_ROWS["F0"][4]


# ============================================================ 46b3-3 同像三跑

def test_46b3_03_same_image_three_runs_agree():
    """同一映像连跑三次，读数表逐字相同（原生载体无跨进程状态泄漏）。"""
    exe = _exe("main", _main_sources())
    first = _run(exe)
    for i in (2, 3):
        rc, rows, err = _run(exe)
        assert rc == 0, f"第 {i} 跑非零退出 rc={hex(rc)} stderr={err[:200]}"
        assert rows == first[1], f"第 {i} 跑读数与首跑不同"


# ============================================================ 46b3-4 手算表承重

def test_46b3_04_hand_table_is_load_bearing():
    """反控：手算表里改一个字，必须与映像读数不同判。

    没有这条，46b3-1 可能锁的是一个「怎么改都过」的空洞断言。
    """
    exe = _exe("main", _main_sources())
    _, rows, _ = _run(exe)
    tampered = dict(_FULL_ROWS)
    tampered["F2"] = ("__正常__", "__正常__", "67|69|0", "__正常__", "[54]")
    assert rows["F2OUT"] == _FULL_ROWS["F2"][4], "映像读数本身就与手算表不符"
    assert rows["F2OUT"] != tampered["F2"][4], "改字后仍同判——手算表不承重"
    tampered2 = dict(_FULL_ROWS)
    tampered2["F7"] = ("__正常__", "__正常__", "9|13|0", "__异常__", "[14, True, True]")
    assert rows["F7RUN"] != tampered2["F7"][3], "RUN 位改字后仍同判"


# ============================================================ 46b3-5 盘上内容承重

def test_46b3_05_readings_follow_disk_content_not_python():
    """反控：同一个映像读「改过一个字」的语料副本，读数必须随盘变。

    F0 与 F10 是**同一个映像内的两次读盘**：F10 的副本只把 `a=2` 改成 `a=3`，
    于是 `a + b * c` 从 14 → **15**、`a ^ 10` 从 1024 → **59049**。若读数其实来自
    Python 侧硬塞（假自证），这一条就会与 F0 相同。同时锁 nfunc 位不变（0），
    证明改动只落在常量上而非结构上。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["F0OUT"] != rows["F10OUT"], "改字副本与原件同判——读数没走盘"
    assert rows["F10OUT"] == _FULL_ROWS["F10"][4], rows["F10OUT"]
    assert rows["F10BCM"] == rows["F0BCM"]


# ==================================================== 46b3-6/7 配方片承重

_SMALL_DRV = '''
rd = 调用捕获(() => 标准库.read_file("{arith}"))([])
输出("RD|" + rd[0])
cm = 调用捕获(() => 编译器.编译(rd[1]))([])
输出("BC|" + cm[0])
if (cm[0] = "__正常__") {
  rr = 调用捕获(() => 字节码虚拟机.运行M3V(cm[1]))([])
  输出("RUN|" + rr[0])
  输出("OUT|" + str(rr[1]))
} else {
  输出("BCE|" + str(cm[1]))
}
'''


def test_46b3_06_compiler_piece_is_load_bearing():
    """反控：配方抽掉 `matha/compiler_matha.matha` → `编译器` 在映像内不存在。

    `module 编译器 {`（matha/compiler_matha.matha:17）是这个名字的唯一来源。抽片后
    驱动里的 `编译器.编译` 必须如实报 `未定义变量 '编译器'`（原生 NI-001 带名抛错），
    而不是悄悄编出一个模块来。读盘位仍正常，证明失败点恰在编译片。
    """
    src = [_SRC[f] for f in _FIVE if f != "matha/compiler_matha.matha"] + [_small_drv()]
    rc, rows, err = _run(_exe("nocc", src))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["RD"] == "__正常__", rows["RD"]
    assert rows["BC"] == "__异常__", f"抽掉编译片仍编译成功——片不承重：{rows}"
    assert rows["BCE"] == "未定义变量 '编译器'", rows["BCE"]


def test_46b3_07_vm_piece_is_load_bearing():
    """反控：配方抽掉 `matha/vm.matha` → 编译照常，`运行M3V` 无处可寻。

    `module 字节码虚拟机 {`（matha/vm.matha:18）是 VM 面的唯一来源。抽片后编译面仍
    正常（`编译器` 不反向依赖 VM），RUN 位必须落到 `__异常__|未定义变量 '字节码虚拟机'`
    ——这同时证明 46b3-1 的运行读数是 Matha 自己写的 VM 跑出来的，不是原生执行体
    代劳（代劳的话抽片后照样出数）。
    """
    src = [_SRC[f] for f in _FIVE if f != "matha/vm.matha"] + [_small_drv()]
    rc, rows, err = _run(_exe("novm", src))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["BC"] == "__正常__", (
        f"缺 VM 片时编译面自身就崩了，说明 编译器 反向依赖 vm.matha：{rows}")
    assert rows["RUN"] == "__异常__", rows["RUN"]
    assert rows["OUT"] == "未定义变量 '字节码虚拟机'", rows["OUT"]


# ============================================================ 46b3-8/9 is 两条路

def test_46b3_08_native_face_is_identity_matrix():
    """路 ①：`is` 在原生发射面上的身份读数（八格，逐格依据见 `_ID_WANT`）。

    关键是 ID2/ID3 这一对：`a is b` **假** 而 `a = b` **真**——只有当 `is` 真的走
    「同一对象」而不是退化成相等比较时才可能成立。ID1/ID8 是同对象的正例，
    ID4/ID5 是 tagged 原元/小整数，ID6/ID7 锁住「不追随 Python interning」的口径。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    bad = {k: (rows.get(k), w) for k, w in _ID_WANT.items() if rows.get(k) != w}
    assert not bad, f"原生 `is` 身份矩阵不符（实测, 手算）：{bad}"


def test_46b3_09_chain_face_is_identity_matrix():
    """路 ②：同一条 `is` 语料在**映像内**被 Matha 编译器编译、被 Matha VM 执行。

    `COUT` 的六项 = `a is a` / `a is b` / `a = b` / `1 is 1` / `1 + 1 is 2` /
    `"ab" is "ab"`。前三项与路 ① 逐字同判（身份真、异对象假、相等真）；第四项
    同判；第五项是 46b3-10 的优先级形态（链面 None vs 原生 True）；第六项同为
    False（两侧都重物化，不 intern）。这条读数经过 `matha/vm.matha:136` 的
    `op = "is" ? (l is r)` 臂，故它锁的是「Matha 编译器 + Matha VM + 原生 is」三层。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["CBC"] == "__正常__", rows["CBC"]
    assert rows["CRUN"] == "__正常__", rows["CRUN"]
    assert rows["COUT"] == _CHAIN_IS_WANT, f"{rows['COUT']} != {_CHAIN_IS_WANT}"


# ==================================================== 46b3-10 优先级双面分歧

def test_46b3_10_is_precedence_divergence_is_registered_current_state():
    """现状锁：`is` 的优先级在两条路上**不同判**，本档锁住这个事实与源行依据。

    **取证依据**（不是推测，是盘上源 + 映像读数）：
      · 宿主 `src/parser.py:1876-1884`：`is` 在 `_parse_rel_expr` 的**末尾**处理，
        左操作数来自 `_parse_set_expr`（→ `_parse_add_expr`），右操作数也走
        `_parse_set_expr` → `is` **松于** `+`，故 `1 + 1 is 2` = `(1+1) is 2` = True。
      · boot 镜像 `matha/parser.matha:626-628`：`是中缀is` 分支在 `解析移位_续` 里，
        而 解析移位 的左操作数来自 `解析乘除` → `is` **紧于** `+`，故
        `1 + 1 is 2` = `1 + (1 is 2)` → `1 is 2` 假 → `1 + 假` 无可加语义 → None。
        该片 `matha/parser.matha:600-602` 的注释自称「对齐宿主 `_parse_set_expr` 内的
        IsExpr 分支」——宿主其实没有这个分支，注释所指在 `_parse_rel_expr`。
      · 锁住的字节码（`P0D` vs `P2D`）证明这不是渲染差异：`1 + 1 is 2` 与
        `1 + (1 is 2)` 在映像内编出**逐字相同**的模块 dict（同为
        BINOP "is" 在前、BINOP "+" 在后），而 `(1 + 1) is 2` 编出不同形状。

    **反转条件**：`matha/parser.matha` 的 `是中缀is` 分支从移位层移到关系层（宿主
    对齐）后，`P0V`/`P5V`/`P6V` 必须变成与 `N0V`/`N5V`/`N6V` 同判，本条随之改锁。
    在此之前**不许**把这条分歧写成「已对齐」，也不许靠改语料规避它。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    for i, (chain, nat) in enumerate(_PREC_WANT):
        tag = rows.get(f"P{i}T")
        assert tag == "__正常__", f"case {i} 编译面就失败：{rows}"
        got_chain = rows.get(f"P{i}V", "<缺行>")
        got_nat = rows.get(f"N{i}V", "<缺行>")
        assert got_chain.endswith("|" + chain), f"P{i}V 链面读数 {got_chain} != {chain}"
        assert got_nat == nat, f"N{i}V 原生面读数 {got_nat} != {nat}"
    # 形态判据：链面前两 case 同形（无括号 = 显式右括号），第三 case 才不同形
    assert rows["P0D"] == rows["P2D"], "解析形状锁失效：同形判据不成立"
    assert rows["P0D"] != rows["P1D"], "解析形状锁失效：显式括号未改变形状"


# ============================================================ 46b3-11 编译同判

def test_46b3_11_two_compilations_in_same_image_agree():
    """同一映像内两次独立 `编译器.编译("输出(7)")` → 模块 dict 渲染逐字相同。

    编译面（`matha/compiler_matha.matha`）若有任何跨调用的可变状态泄漏（常量池
    复用、全局计数器），第二次编译的 dict 就会漂移。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["SAMEBC"] == "True", rows["SAMEBC"]


# ==================================================== 46b3-12 FS 假成功现状锁

def test_46b3_12_missing_file_is_currently_silent_inside_the_image():
    """现状锁：五片共像里 `标准库.read_file` 读**不存在**的路径给 `__正常__|None`。

    这是原生 FS 载体的**假成功**，不是正确行为：宿主 `src/interp.py:631
    builtin_read_file` 抛 `读文件失败: {e}`，而原生 `_emit_builtin_read_file`
    （`src/mbc/native.py:7674` 一带）失败走 `rf_fail` → `null_obj`，文档口径也写着
    「失败 → null」。本档刻意把它锁成**现状**而不是当成通过证据——
    全链读数（46b3-1）里没有任何一份语料依赖这个 null 形。

    **反转条件**：原生 `read_file`/`write_file`/`append_file` 改诚实抛错后，本条必须
    翻成 `MISS|__异常__|读文件失败: ...` 同文案锁；在那之前，任何新增的全链判据都
    **不许**把 `__正常__|None` 当作「读到了内容」。
    """
    rc, rows, err = _run(_exe("main", _main_sources()))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert rows["MISS"] == "__正常__|None", (
        f"缺路径读数已变：{rows['MISS']}——若已改成诚实抛错，请把本条翻成同文案锁")


# ==================================================== 46b3-13 共像符号串扰取证

_CLOBBER_DRV = '''
files = ["{golden01}"]
i = 0
while (i < len(files)) {
  rd = 标准库.read_file(files[i])
  ip = 调用捕获(() => interpret(rd))([])
  输出("ITP|" + ip[0] + "|" + str(ip[1]))
  i = i + 1
}
输出("OPNAME|" + str(type_of(应用运算)))
'''


def _clobber_drv() -> str:
    return _CLOBBER_DRV.replace(
        "{golden01}", f"{_ROOT_POSIX}/golden_tests/cases/01_arithmetic_and_relations.matha")


def test_46b3_13_flat_link_face_clobbers_same_named_module_funcs():
    """现状锁：boot 六片 + `vm.matha` 共像时，解释面读数被同名内部函数覆盖。

    `matha/interp_matha.matha:508` 与 `matha/vm.matha:119` **都**定义了内部函数
    `应用运算`。MBC 编译单元把各模块的 `func` 提升进同一张全局函数表（boot 六片里
    `应用运算` 就是这张表的一个名，`OPNAME` 行给出它的类型），故链接面上后一片的定义
    覆盖前一片——而 vm 面的 `应用运算` **没有** `op = "="` 臂（`interp_matha.matha:526`
    有），于是解释面跑 `golden_tests/cases/01_arithmetic_and_relations.matha` 的
    `#1：["func" = "func"]` 时落进 `错误("未知运算符: =")`：

      · boot 六片单独成像     → `__正常__|[14, True, True]`
      · boot 六片 + vm.matha  → `__异常__|未知运算符: =`

    同一破坏在 **Python VM 面**（`src/mbc/vm.py` 跑同一份链接产物）同样复现，故它
    属于「链接面就是拼接」（46c2-3 已登记口径）的产物层缺陷，**不是**原生专属。
    正因如此，46b3 的全链配方刻意用五片（不含解释面）。

    **反转条件**：链接面按模块收口符号作用域（另立任务）后，`boot6 + vm.matha` 的
    解释面读数必须回到 `__正常__|[14, True, True]`，本条随之翻成正面锁。
    """
    boot = [(_ROOT / f).read_text(encoding="utf-8") for f in _BOOT_FILES]
    _, base, _ = _run(_exe("cl_boot6", boot + [_clobber_drv()]))
    assert base["ITP"] == "__正常__|[14, True, True]", (
        f"boot 六片基线读数已变（{base['ITP']}）——先确认解释面是否被修，"
        f"再决定本条往哪边翻")
    assert base["OPNAME"] == "Function", base["OPNAME"]

    with_vm = boot + [_SRC["matha/vm.matha"]] + [_clobber_drv()]
    _, clob, _ = _run(_exe("cl_boot6vm", with_vm))
    assert clob["ITP"] == "__异常__|未知运算符: =", (
        f"共像串扰已消失或换了形态：{clob['ITP']}——若链接面已按模块收口，"
        f"请把本条改成正面锁「+vm.matha 后仍为 [14, True, True]」")
    assert clob["OPNAME"] == "Function", clob["OPNAME"]


# ==================================================== 46b3-14 零 Python 裁判边界

def test_46b3_14_no_python_execution_face_is_imported():
    """本档只许 import 构建面：发射器 + 编译面。

    宿主解释器 / Python VM / boot 链会话一旦进档，判定就又回到「Python 当裁判」，
    与阶段 44/46c 的换形口径相背。这里直接扫源码，防止「顺手 import 一下排障」。
    """
    txt = Path(__file__).read_text(encoding="utf-8")
    for banned in ("src.interp", "src.mbc.vm", "src.matha_chain", "src.interp_engine"):
        assert not re.search(rf"^\s*(from|import)\s+{re.escape(banned)}", txt,
                             re.MULTILINE), f"本档 import 了执行/裁判面：{banned}"


def test_46b3_15_is_carrier_is_a_real_native_emission_not_a_fallback():
    """载体结构锁：原生后端必须有 `is` 的真发射分支，且不再有「不支持 'is'」的拒绝文案。

    读数以 46b3-8/9 为准，本条锁的是**实现位置**：`src/mbc/native.py` 的
    `elif sym == "is"` 分支里必须真的发 `cmp rax,rcx` + `sete`，而不是把 `is`
    偷偷接到 `=`（相等）上——那样 ID2 会变 True，46b3-8 立刻红。
    """
    txt = (_ROOT / "src" / "mbc" / "native.py").read_text(encoding="utf-8")
    assert re.search(r'elif sym == "is":', txt), "原生后端缺 `is` 发射分支"
    seg = txt.split('elif sym == "is":', 1)[1][:1200]
    assert "\\x48\\x39\\xC8" in seg, "`is` 分支未发 cmp rax,rcx"
    assert "\\x0F\\x94\\xC0" in seg, "`is` 分支未发 sete al"
    assert "不支持二元运算 'is'" not in txt, "`is` 的拒绝文案仍在"
