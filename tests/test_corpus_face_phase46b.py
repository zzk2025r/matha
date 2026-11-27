# -*- coding: utf-8 -*-
"""阶段 46b 语料判定面锁：boot 全链在原生映像里跑真语料，第三端落地。

**这一端是什么**：判定面原有两端——`hi`（`src/interp.py` 树遍历器）与
`vm`（`src/mbc/vm.py` 字节码机），两端都是 Python 执行体，裁判也是 Python。
本档加入第三端：**同一批 boot 链源（六片）链进一个无导入表的 PE64 映像，映像
用 Matha 自己写的解释器（`matha/interp_matha.matha` 的 `interpret` 入口）从盘读
语料、自己解析、自己执行**，Python 全程只做两件事：把源交给发射器、跑产物。

**本档的判据形态**（口径承继阶段 44 拍板「允许 Python 仅作种子，最终判定用无
Python 的 Matha 原生映像自证」+ 阶段 46c「跑起来了不等于正确」）：

- 46b-1 **全链 10 份语料逐份读数**：每份的手算依据写进 `_EXPECT` 注释，逐字对
  拍原生映像；7 条有判别力 + 3 条如实标 `退化`（读数正确但无判别力，见下）。
- 46b-2 **A/B 双构建**：两次独立发射 → PE 逐字节相同 + 读数逐字相同。
- 46b-3 **同像三跑**：同一映像连跑三次读数逐字相同。
- 46b-4 **承重反控**：手算表里改一个字必须与映像读数不同判。
- 46b-5 **入口绑名的正负两面**：`use 运行时引擎` + `运行时引擎.PI` 在映像内产
  手算读数；缺模块仍如实报 `未找到模块 'X'`（不许因为预绑而变成假成功）。
- 46b-6 **镜像不同动的取证**：`matha/interp.matha` 入口刻意不绑模块名——绑了
  反而把 `标准库.len(...)` 从正确读数打成 `不可调用的值: None`（本档锁住这个
  结论的源行依据，谁再"顺手对齐"就红）。
- 46b-7 **零 Python 裁判边界**：本档只 import 构建面（发射器 + 编译面），不 import
  `src.interp` / `src.mbc.vm` / `src.matha_chain`。
- 46b-8/9 **CRLF 的原生载体自证 + 反控**：换行折叠这条判据在 hi/vm 两面**根本不存在**
  ——Python `Path.read_text` 的 universal-newlines 让 \\r 永远进不了宿主/VM 语料，
  故「三面同判」在换行面上是一句空话。本档把 LF 与 CRLF 两份源在**同一个映像内**
  用 `chr(13)`/`chr(10)` 现拼后各自跑解释器，读数必须逐字相同（46b10）；再把
  `matha/lexer.matha` 的 CR 守卫置恒假重链一次，CRLF 必须与 LF 分叉而 LF 不受波及
  （46b11）——证明上一条锁的是 CR 通道本身，不是「有输出就行」。

**为什么不与 hi/vm 对拍**：那是 Python 当裁判的老形态，退役后整面消失。本档的
读数全部由 Matha 源文件手算得出，Python 退役后这条判据仍然活着。
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

# 只允许构建面：发射器 + 编译面。宿主解释器 / VM / boot 链会话一面都不进。
from src.mbc import native                                    # noqa: E402
from src.mbc.compiler import compile_sources                  # noqa: E402

_BOOT_FILES = ("matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha",
               "matha/interp_matha.matha", "matha/loader.matha")
_BOOT = [(_ROOT / f).read_text(encoding="utf-8") for f in _BOOT_FILES]
# 46b-11 的反控要逐字替换词法器源里的一处守卫，故单独持有一份，且必须与
# _BOOT[0] 同源同字（否则「替换 1 处」落在链外，反控变成假反控）。
_LEXER_TXT = _BOOT[0]

_EXES: dict[str, str] = {}


def _exe(tag: str, sources: list[str]) -> str:
    """一次构建、多锁复用；固定名带 46b 前缀，不与 p45/p46c 的映像争用。"""
    if tag not in _EXES:
        p = os.path.join(tempfile.gettempdir(), f"p46b_{tag}.exe")
        Path(p).write_bytes(native.emit_exe(compile_sources(sources)))
        _EXES[tag] = p
    return _EXES[tag]


def _run(path: str) -> tuple[int, list[str], str]:
    r = subprocess.run([path], capture_output=True, timeout=900)
    return (r.returncode & 0xFFFFFFFF,
            [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l != ""],
            r.stderr.decode("utf-8", "replace"))


def _bytes(sources: list[str]) -> bytes:
    """绕开缓存，真·独立编译一次（确定性判据要的是两次独立发射）。"""
    return native.emit_exe(compile_sources(sources))


#: boot 链顶层自测块在映像里执行时产的头 6 行数字（`1,8,14,200,10,6`）——
#: 与阶段 45 45d-4 锁同源，驱动读数一律跳过。
_BOOT_HEADER = 6


# ================================================== 46b-1 十份语料的手算读数表

_DRV_TMPL = '''files = [{paths}]
tags = [{tags}]
i = 0
while (i < len(files)) {{
  rd = 调用捕获(() => 标准库.read_file(files[i]))([])
  r = 调用捕获(() => interpret(rd[1]))([])
  输出("FILE")
  输出(tags[i])
  输出(r[0])
  输出(type_of(r[1]))
  输出(len(r[1]))
  输出(r[1])
  i = i + 1
}}
'''

#: (相对路径, 状态, 读数类型, 读数长度, 逐字读数, 分类)
#:
#: 手算依据（逐条）：
#:  1. `matha/examples/01_arithmetic.matha`：@ 行绑 a=2,b=3,c=4 → `a + b * c`
#:     = 2 + 3*4 = **14**；`a ^ 10` = 2^10 = **1024**；`^9`/`^16` 是一元开方
#:     （`matha/lexer.matha` 多符表 / 语法器一元 开方 臂）= 3 / 4，链面牛顿迭代
#:     恒浮点故写作 **3.0 / 4.0**（KNOWN_ISSUES 41-② 登记的渲染分歧，非缺陷）。
#:  2. `matha/examples/02_functions.matha`：x=5，`inc x`/`double x`/`h x` 的
#:     意图读数是 6/10/11，但 0x62 公式模式把空格应用式折成单个标识符，
#:     `[inc x]` 退化为对名字 "incx" 的取值——三面（hi/vm/原生）逐字同判为
#:     名字串，故本条记 **退化**（读数正确反映当前语言行为，但无判别力，
#:     不得当作「算对了」的证据）。
#:  3. `matha/examples/03_set_iter.matha`：手抄 1..10 逐次累加 = 55（等差和
#:     10*11/2 = **55**）。
#:  4. `matha/examples/04_pipeline.matha`：`records = 0` 后原样输出 → **[0]**，
#:     全程无计算，记 **退化**（正确但零判别力）。
#:  5. `matha/examples/05_sensor_read.matha`：`temp = 25.6` 原样输出 → **[25.6]**。
#:  6. `matha/examples/06_main.matha`：端口=8080、x=5、y=3 → `area = x * y` =
#:     **15**，读数序 [area, 端口, area] = **[15, 8080, 15]**（末行 `#：[area]…
#:     （0/？）【06_sub.matha】` 是注记文本，不产第二条读数）。
#:  7. `matha/examples/06_sub.matha`：area=15、单价=10 → total = **150**。
#:  8. `matha/lexer.matha`：整份是 `module 词法器 { … }`，模块体只声明函数、
#:     顶层不产输出 → **[]**（长度 0 是这份语料的真读数，不是失败）。
#:  9. `matha/bootstrap_test_v2.matha`：七组测试 + 汇总，逐条手算——
#:     算术 5 条 = 1+2*3=**7**、10-3=**7**、12/4=**3.0**（`/` 恒浮除）、
#:     2^10=**1024**、17%5=**2**；三角 3 条 = sin(3.14159)=**2.65358979335273e-06**
#:     （一阶：π-3.14159 = 2.65358979335273e-06，sin'(π)=1）、cos(0.0)=**1.0**、
#:     sin(3.14159)+cos(1.57)= 2.65358979335273e-06 + 7.963267107332633e-04
#:     = **0.0007989803005266161**（cos(1.57) 一阶 π/2-1.57=7.9632679e-04，
#:     二阶修正后取此值）；函数 2 条 = **6**/**14**；递归 阶乘(6)=**720**；
#:     斐波那契(10)=**55**；柯里化 加(10)(20)=**30**；条件 **True**/**False**。
#:     首段 15 条 + 汇总段 14 条 = **29** 条，汇总段无 sin+cos 合式故少一项。
#:     本条是 46b-5 入口绑名的正面载体（旧读数：异常「未找到模块 '运行时引擎'」）。
#: 10. `golden_tests/cases/01_arithmetic_and_relations.matha`：2+3*4=**14**、
#:     10>=5=**True**、"func"="func"=**True**。
_EXPECT = [
    ("matha/examples/01_arithmetic.matha", "__正常__", "List", 4,
     "[14, 1024, 3.0, 4.0]", "判别"),
    ("matha/examples/02_functions.matha", "__正常__", "List", 3,
     "['incx', 'doublex', 'hx']", "退化"),
    ("matha/examples/03_set_iter.matha", "__正常__", "List", 1, "[55]", "判别"),
    ("matha/examples/04_pipeline.matha", "__正常__", "List", 1, "[0]", "退化"),
    ("matha/examples/05_sensor_read.matha", "__正常__", "List", 1, "[25.6]", "判别"),
    ("matha/examples/06_main.matha", "__正常__", "List", 3, "[15, 8080, 15]", "判别"),
    ("matha/examples/06_sub.matha", "__正常__", "List", 1, "[150]", "判别"),
    ("matha/lexer.matha", "__正常__", "List", 0, "[]", "退化"),
    ("matha/bootstrap_test_v2.matha", "__正常__", "List", 29,
     "[7, 7, 3.0, 1024, 2, 2.65358979335273e-06, 1.0, "
     "0.0007989803005266161, 6, 14, 720, 55, 30, True, False, "
     "7, 7, 3.0, 1024, 2, 2.65358979335273e-06, 1.0, "
     "6, 14, 720, 55, 30, True, False]", "判别"),
    ("golden_tests/cases/01_arithmetic_and_relations.matha", "__正常__", "List", 3,
     "[14, True, True]", "判别"),
]


def _corpus_drv() -> str:
    paths = ", ".join(f'"{(_ROOT / rel).as_posix()}"' for rel, *_ in _EXPECT)
    tags = ", ".join(f'"{rel}"' for rel, *_ in _EXPECT)
    return _DRV_TMPL.format(paths=paths, tags=tags)


def _parse_runs(lines: list[str]) -> list[tuple[str, str, str, int, str]]:
    """FILE 分段 → (标签, 状态, 类型, 长度, 读数)；不足五段的尾块如实报错。"""
    out = []
    i = 0
    while i < len(lines):
        assert lines[i] == "FILE", f"第 {i} 行不是 FILE 分段头：{lines[i]!r}"
        assert i + 5 < len(lines), f"分段残缺：{lines[i:]}"
        out.append((lines[i + 1], lines[i + 2], lines[i + 3],
                    int(lines[i + 4]), lines[i + 5]))
        i += 6
    return out


@pytest.fixture(scope="module")
def corpus_run() -> list[tuple[str, str, str, int, str]]:
    exe = _exe("corpus", _BOOT + [_corpus_drv()])
    rc, out, err = _run(exe)
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    return _parse_runs(out[_BOOT_HEADER:])


def test_46b1_native_image_runs_all_ten_boot_chain_corpus_files(corpus_run):
    """十份语料在原生映像内全部 `__正常__`，读数与手算字面逐字同判。

    这是 #248 的主判据：boot 全链（词法→标准库→语法→运行时→解释器→装载器）
    链进同一个 PE64，映像用自己的解释器读盘、解析、执行，Python 不参与判定。
    """
    assert len(corpus_run) == len(_EXPECT) == 10
    got = [(rel, tag, ty, n, text) for rel, tag, ty, n, text in corpus_run]
    want = [(rel, tag, ty, n, text) for rel, tag, ty, n, text, _kind in _EXPECT]
    bad = [(w, g) for w, g in zip(want, got) if w != g]
    assert not bad, [(f"期望 {w}", f"实得 {g}") for w, g in bad]


def test_46b1b_classification_is_seven_discriminating_three_degenerate(corpus_run):
    """读数分类如实记账：7 条有判别力、3 条退化，退化条不得当收益引用。

    承继 46c32 的做法——「跑通且读数一致」和「读数有判别力」是两件事。
    02/04/lexer 三条的退化根因逐条写在 `_EXPECT` 注释里。
    """
    kinds = [k for *_rest, k in _EXPECT]
    assert kinds.count("判别") == 7, kinds
    assert kinds.count("退化") == 3, kinds
    deg = {rel for rel, *_rest, k in [(e[0], e[5]) for e in _EXPECT] if k == "退化"}
    assert deg == {"matha/examples/02_functions.matha",
                   "matha/examples/04_pipeline.matha",
                   "matha/lexer.matha"}, deg


def test_46b1c_bootstrap_v2_reading_matches_every_hand_value(corpus_run):
    """bootstrap_test_v2 的 29 项逐个点名（合并成一条断言会让错位看不出来）。"""
    row = [r for r in corpus_run if r[0] == "matha/bootstrap_test_v2.matha"]
    assert len(row) == 1, row
    text = row[0][4]
    for lit in ("7", "3.0", "1024", "2", "2.65358979335273e-06", "1.0",
                "0.0007989803005266161", "6", "14", "720", "55", "30",
                "True", "False"):
        assert lit in text, f"29 项读数里缺手算项 {lit!r}：{text}"
    assert text.count(",") == 28, f"应为 29 项（28 个逗号）：{text}"


# ============================================ 46b-2/3 确定性与 46b-4 承重反控


def test_46b2_two_independent_builds_are_byte_identical_and_agree():
    """两次独立发射 → PE 逐字节相同，且两个映像的读数逐字相同。

    boot 全链（六片）比 46c 的四片大一个量级，这条锁的是「解释器面进映像后
    确定性仍然成立」——地址序参与摆放或表遍历序进产物都会在这里露馅。
    """
    srcs = _BOOT + [_corpus_drv()]
    a = _bytes(srcs)
    b = _bytes(srcs)
    assert a == b, f"两次编译产物不同（{len(a)} vs {len(b)} 字节）"
    assert a[:2] == b"MZ"
    pa = os.path.join(tempfile.gettempdir(), "p46b_ab_a.exe")
    pb = os.path.join(tempfile.gettempdir(), "p46b_ab_b.exe")
    Path(pa).write_bytes(a)
    Path(pb).write_bytes(b)
    ra, rb = _run(pa), _run(pb)
    assert ra[0] == rb[0] == 0, f"rc 不同：{hex(ra[0])} vs {hex(rb[0])}"
    assert ra[1] == rb[1], "两个独立构建的映像读数不同判"


def test_46b3_same_image_three_runs_are_verbatim_identical(corpus_run):
    exe = _exe("corpus", _BOOT + [_corpus_drv()])
    runs = [_run(exe) for _ in range(3)]
    assert all(rc == 0 for rc, _o, _e in runs)
    assert all(o == runs[0][1] for _r, o, _e in runs), "同一映像三跑读数不同"
    assert _parse_runs(runs[0][1][_BOOT_HEADER:]) == \
        _parse_runs(runs[1][1][_BOOT_HEADER:])


def test_46b4_hand_literals_are_load_bearing(corpus_run):
    """反控三刀：改一个数字、换一项顺序、把退化条写成「意图值」都必须不同判。

    证明锁的是逐字逐序，不是「有输出就行」。三刀都只改本档的字面量，不动源。
    """
    rows = {(rel): text for rel, _t, _ty, _n, text in corpus_run}
    v2 = rows["matha/bootstrap_test_v2.matha"]
    assert v2.replace("720", "721") != v2, "字面量可替换性自检"
    assert v2.replace("720", "721") != rows["matha/bootstrap_test_v2.matha"]
    head = rows["matha/examples/01_arithmetic.matha"]
    assert head.replace("[14,", "[15,") != head
    # 顺序承重：把 06_main 的三项换个序
    main = rows["matha/examples/06_main.matha"]
    assert main == "[15, 8080, 15]" and main != "[15, 15, 8080]"
    # 退化条反控：02_functions 的意图值（6/10/11）不是现行语言读数
    funcs = rows["matha/examples/02_functions.matha"]
    assert funcs != "[6, 10, 11]", "02_functions 的意图读数若成立，本条口径需改写"


# ====================================== 46b-5 入口绑链模块名（46b-2 修复的正面）

_ENTRY_DRV = '''cases = [{srcs}]
tags = {tags}
i = 0
while (i < len(cases)) {{
  r = 调用捕获(() => interpret(cases[i]))([])
  输出("CASE")
  输出(tags[i])
  输出(r[0])
  输出(r[1])
  i = i + 1
}}
'''

#: (标签, 内层源, 期望状态, 期望读数)——手算依据逐条写在注释里。
_ENTRY_CASES = [
    # 正面 1：入口 env 预绑 运行时引擎 → `use 运行时引擎` 命中，`运行时引擎.PI`
    # 取 `matha/runtime/matha_runtime.matha:18` 的字面量 3.141592653589793。
    ("模块use点取", "use 运行时引擎\\np = 运行时引擎.PI\\n[p]\\n",
     "__正常__", "[3.141592653589793]"),
    # 正面 2：裸算术（不依赖模块）仍同判——预绑没有改变既有读数。
    ("裸算术", "a = 1 + 2 * 3\\n[a]\\n", "__正常__", "[7]"),
    # 正面 3：标准库模块名同样可达（dict 点取 + 函数应用）。
    ("标准库点取", "use 标准库\\nb = 标准库.len([1, 2, 3, 4])\\n[b]\\n",
     "__正常__", "[4]"),
    # 负面：未预绑的模块名仍如实报错——预绑不是「什么都算命中」的假成功。
    ("缺模块", "use 不存在的模块\\nq = 1\\n[q]\\n",
     "__异常__", "未找到模块 '不存在的模块'"),
]


def _entry_drv() -> str:
    srcs = ", ".join(f'"{s}"' for _t, s, _e, _x in _ENTRY_CASES)
    tags = "[" + ", ".join(f'"{t}"' for t, _s, _e, _x in _ENTRY_CASES) + "]"
    return _ENTRY_DRV.format(srcs=srcs, tags=tags)


def test_46b5_entry_env_binds_chain_modules_with_honest_missing_module():
    """入口绑名批的正负两面：链模块可达 + 缺模块仍诚实拒绝。

    旧写 `注册内建(空环境())` 起 env 不含任何模块名，`use 运行时引擎` 在
    `导入绑定`（`matha/interp_matha.matha:1291`）处直接落「未找到模块」——
    bootstrap_test_v2 因此在原生映像里是全链唯一跑不通的一份（46b 摸底读数）。
    """
    rc, out, err = _run(_exe("entry", _BOOT + [_entry_drv()]))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    lines = out[_BOOT_HEADER:]
    got = {}
    for i, ln in enumerate(lines):
        if ln == "CASE":
            got[lines[i + 1]] = (lines[i + 2], lines[i + 3])
    assert set(got) == {t for t, *_x in _ENTRY_CASES}, got
    bad = []
    for tag, _src, want_tag, want_text in _ENTRY_CASES:
        if got[tag] != (want_tag, want_text):
            bad.append((tag, f"期望 {(want_tag, want_text)}", f"实得 {got[tag]}"))
    assert not bad, bad


# ============================ 46b-6/7 镜像取证 + 零 Python 裁判边界 + 结构锁

_CRLF_DRV = '''lf = "a = 1 + 2 * 3" + chr(10) + "b = a * 2" + chr(10) + "[a, b]" + chr(10)
crlf = "a = 1 + 2 * 3" + chr(13) + chr(10) + "b = a * 2" + chr(13) + chr(10) + "[a, b]" + chr(13) + chr(10)
r1 = 调用捕获(() => interpret(lf))([])
r2 = 调用捕获(() => interpret(crlf))([])
输出("LF")
输出(r1[0])
输出(r1[1])
输出("CRLF")
输出(r2[0])
输出(r2[1])
输出("SAME")
cmp = 调用捕获(() => r1[1] = r2[1])([])
输出(cmp[0])
输出(cmp[1])
'''

#: 反控用的词法器改写：`扫描主体` 的 CR 守卫改成恒假，分支结构一字不动。
#: 复原这条 = 阶段 46a-1 之前的链面（\r 落单字符分支降级成 符号 → 被当变量引用）。
_CR_NEUTERED = "(是回车码(ord(get(src)(pos))) ?"


def _crlf_rows(lines: list[str]) -> dict[str, str]:
    keys = ("LF", "CRLF", "SAME")
    assert [l for l in lines if l in keys] == list(keys), lines
    out = {}
    for i, ln in enumerate(lines):
        if ln in keys:
            out[ln] = (lines[i + 1], lines[i + 2])
    return out


def test_46b10_crlf_and_lf_agree_inside_the_image():
    """CRLF 折叠在原生载体三面同判（46a-1 的判据）。

    为什么只在原生面显形：宿主/VM 面经 Python `read_text` 的 universal-newlines
    永远收不到 \\r，链面此前只认码 10，\\r 落到单字符分支降级成 符号、被解析为
    变量引用而报「未定义变量 '<CR>'」。本条把 LF 与 CRLF 两份源在**同一个映像
    内**用 `chr(13)`/`chr(10)` 现拼，读数必须逐字相同——
    手算：a = 1 + 2*3 = **7**，b = a*2 = **14**，一条表达式语句 `[a, b]` → 解释器
    的输出表是 **`[[7, 14]]`**（外层是「输出行表」，内层才是列表字面量）。
    """
    rc, out, err = _run(_exe("crlf", _BOOT + [_CRLF_DRV]))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    rows = _crlf_rows(out[_BOOT_HEADER:])
    assert rows["LF"] == ("__正常__", "[[7, 14]]"), rows["LF"]
    assert rows["CRLF"] == ("__正常__", "[[7, 14]]"), rows["CRLF"]
    assert rows["SAME"] == ("__正常__", "True"), rows["SAME"]


def test_46b11_crlf_lock_is_load_bearing():
    """反控：把词法器的 CR 守卫改恒假后，同一份 CRLF 源必须与 LF 不同判。

    没有这条，上一条可能锁的是一个「怎么改都过」的空洞断言。改写点在
    `matha/lexer.matha:447`（`扫描主体` 的 CR 分支），置恒假后 \\r 落回单字符
    分支降级成 符号 → 解析为变量引用 → CRLF 侧 `__异常__`，而 LF 侧不受波及
    （证明改的确实是 CR 通道，不是整条流水线）。
    """
    assert _CR_NEUTERED in _LEXER_TXT, "词法器 CR 守卫位变了，反控改写点需同步取证"
    neutered = [_LEXER_TXT.replace(_CR_NEUTERED, "(假 ?", 1)] + _BOOT[1:]
    rc, out, err = _run(_exe("crlf_mut", neutered + [_CRLF_DRV]))
    assert rc == 0, f"反控映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    rows = _crlf_rows(out[_BOOT_HEADER:])
    assert rows["LF"] == ("__正常__", "[[7, 14]]"), f"LF 侧被改写波及：{rows['LF']}"
    assert rows["SAME"] != ("__正常__", "True"), \
        f"剥离 CR 分支后 CRLF 仍与 LF 同判——上一条锁是空洞的：{rows}"


_INTERP_MATHA_TXT = (_ROOT / "matha" / "interp_matha.matha").read_text(encoding="utf-8")
_INTERP_MIRROR_TXT = (_ROOT / "matha" / "interp.matha").read_text(encoding="utf-8")


def test_46b6_both_chain_entries_bind_module_names():
    """结构锁：`interpret` 与 `run` 两个入口都走 `绑模块名`，谁漏一个都红。

    只有 `interpret` 改 while `run` 忘改，是这类批最容易留下的半截实现。
    """
    assert "func 绑模块名(env: List) -> List" in _INTERP_MATHA_TXT
    assert _INTERP_MATHA_TXT.count("绑模块名(注册内建(空环境()))") == 2, \
        "入口 interpret/run 必须双双绑名"
    assert "func 绑名对(env: List, 对们: List) -> List" in _INTERP_MATHA_TXT
    for mod in ("词法器", "标准库", "语法器", "运行时引擎"):
        assert f'["{mod}", {mod}]' in _INTERP_MATHA_TXT, mod


def test_46b7_mirror_deliberately_does_not_bind_and_says_why():
    """镜像不同动的取证必须在源里写明（`matha/interp.matha` 入口注）。

    依据（实测）：镜像的 `对象取字段` 只认 struct 实例/enum 命名空间，字典一律
    返 null，`标准库.len(...)` 全靠 `求值属性` 的「变量未绑定 → 平铺回退」臂；
    预绑后点取改走字典臂落 null，宿主面读数由 `[3]` 退化为
    「不可调用的值: None」。本条同时锁住镜像入口仍是 `注册内建(空环境())`。
    """
    assert "46b-2 不同动（取证不修）" in _INTERP_MIRROR_TXT
    assert "不可调用的值: None" in _INTERP_MIRROR_TXT
    assert "let env = 注册内建(空环境())" in _INTERP_MIRROR_TXT
    assert "绑模块名" not in _INTERP_MIRROR_TXT, "镜像侧若真长出 导入/字典回退臂，再连同本注一起改写"


def test_46b8_this_file_has_no_python_referee():
    """零 Python 裁判边界：本档不 import 宿主面/VM 面/boot 会话。

    与 46c2-7 同族。构建面（发射器 + 编译面）是允许的 Python 种子。
    """
    txt = Path(__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^from (\S+) import|^import (\S+)", txt, re.M)
    flat = {a or b for a, b in imports}
    assert "src.interp" not in flat and "src.mbc.vm" not in flat, flat
    assert "src.matha_chain" not in flat, flat
    assert {"src.mbc", "src.mbc.compiler"} <= flat, flat


def test_46b9_boot_six_slices_stay_the_documented_set():
    """boot 六片清单与 `src/matha_chain.BOOT_FILES` 同源（静态文本对拍，不 import）。

    链面语料进映像的前提是这六片全链进产物；BOOT_FILES 若增删，本档的
    `_BOOT_FILES` 必须同步——否则「全链」二字就是空话。
    """
    txt = (_ROOT / "src" / "matha_chain.py").read_text(encoding="utf-8")
    block = txt.split("BOOT_FILES", 1)[1].split(")", 1)[0]
    listed = re.findall(r'"([^"]+\.matha)"', block)
    assert listed == list(_BOOT_FILES), listed
