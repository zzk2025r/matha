# -*- coding: utf-8 -*-
"""阶段 46c 判定面换形锁：裁判不是 Python 的判据。

**为什么要换形**：脱 Python 之后，「与宿主对拍」这条 oracle 会整面消失——
Track B 的 `equal` 是 boot↔host 差分（裁判 = 宿主 Python），golden 的 vm↔interp
两边也都是 Python。若退役前不把判据换成不依赖 Python 的形态，退役那一刻就
没有正确性判据了，剩下的只有「没崩」——正是阶段 41 清过的那一类假成功温床。

**本档的裁判形态**（Python 只做构建种子，不做判定；口径承继阶段 44 拍板
「允许 Python 仅作种子，最终判定用无 Python 的 Matha 原生映像自证」）：

- 46c2-1 **构建确定性**：同一份源编译两次 → PE 逐字节相同。地址序参与摆放、
  表遍历序进产物、时间戳入头，任何一条都会在这里露馅（45d-0 的旧序比较就是
  按 `.data` 地址序判的，产物层同族缺陷同形）。
- 46c2-2 **运行确定性**：同一个映像连跑三次 → rc 与 stdout 逐字相同。
- 46c2-3 **分区等价**：多模块链接的映像 vs 文本拼接的映像 → 映像逐字节相同 +
  读数逐字相同。当前二者逐字节相同这一事实本身登记为「链接面就是拼接」
  （45b1 的编译面等价在产物层的投影）；将来链接面若长出独立逻辑，这条会变。
- 46c2-4/5 **手算字面读数**：Matha 写的词法器/语法器跑在真 PE64 里，输出逐行
  写死在本档字面量里（每条读数的依据指到 `matha/lexer.matha` /
  `matha/parser.matha` 的源行），只与原生映像比对——**不调** hi/vm 任何一面。
  这是 Python 退役后仍然活着的判据。
- 46c2-6 **承重反控**：把字面量置换/改一个字，必须与映像读数不同判——
  证明锁的是逐字逐序，不是「有输出就行」。
- 46c2-7 **零 Python 裁判边界**：本档源码里不许出现宿主面对拍调用/领域插件 import。
- 46c2-8 **差分面 dev-only 口径**：`scripts/selfhost_matrix.AUTHORITY` 明写
  dev-only 差分参照，且产品面 `src/**` 零 import 该脚本（判定工具不许反向变成产品依赖）。
- 46c2-9/10/11 **差分面功率台账**：Track B 快照的 `both_ok_equal` 按有无读数
  分层（obs / silent）、逐条带 `n_outs`，四份文档的口径行与实测值锚定，
  资源库语料的证据贡献如实记账（阶段 46c 时点：52 条全为 silent）。
- 46c2-12/13/14 **编译面 A/B 双跑**（形态 ① 的真身）：`matha/compiler_matha.matha`
  连同词法/标准库/语法四片链进原生映像后，**编译器在映像里跑起来了**——两个
  独立构建的映像（四片链接 vs 四片拼接）各在自己的进程里编译同一批源，产出的
  字节码读数逐字相同；同一映像内重复编译同判；读数另与本档手算字面量对拍
  （依据到编译器源行），并用三刀反控证明字面量承重。

**边界（本档自证的到哪一步为止）**：任务 #249 的 ① 原形是「原生映像 A 编译出的
产物 == 原生映像 B」。今天交付的是**编译面**的 A/B 双跑（四片链）；把 boot 的
**解释器面**（`interp_matha` / `loader`）也链进映像，实测在第一条驱动语句前就
以 `不可调用的值` 退出（rc=0x1），即 46a（24 个 latent 宿主注入名归零）+ 46b
的边界；那之后 ① 才扩到「映像自己编译 + 自己运行」的全链双跑。登记见
KNOWN_ISSUES 阶段 46c。
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

# 只允许「构建面」import：发射器 + 编译面。宿主解释器/VM 一面都不进。
from src.mbc import native                                   # noqa: E402
from src.mbc.compiler import compile_sources                 # noqa: E402

_HERE = Path(__file__).resolve()
_MAIN_SRC = _HERE.read_text(encoding="utf-8")
_LEXER_TXT = (_ROOT / "matha" / "lexer.matha").read_text(encoding="utf-8")
_STDLIB_TXT = (_ROOT / "matha" / "stdlib.matha").read_text(encoding="utf-8")
_PARSER_TXT = (_ROOT / "matha" / "parser.matha").read_text(encoding="utf-8")

_EXES: dict[str, str] = {}


def _lit(items: list[str]) -> str:
    return "[" + ", ".join(f'"{s}"' for s in items) + "]"


def _exe(tag: str, sources: list[str]) -> str:
    """一次构建、多锁复用；固定名带 46c 前缀，不与 p45/p46 的映像争用。"""
    if tag not in _EXES:
        p = os.path.join(tempfile.gettempdir(), f"p46c_{tag}.exe")
        Path(p).write_bytes(native.emit_exe(compile_sources(sources)))
        _EXES[tag] = p
    return _EXES[tag]


def _run(path: str) -> tuple[int, list[str], str]:
    r = subprocess.run([path], capture_output=True, timeout=300)
    return (r.returncode & 0xFFFFFFFF,
            [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l != ""],
            r.stderr.decode("utf-8", "replace"))


def _bytes(tag: str, sources: list[str]) -> bytes:
    """绕开缓存，真·独立编译一次（确定性判据要的是两次独立发射）。"""
    return native.emit_exe(compile_sources(sources))


# ==================================================== 46c2-1/2/3 原生自证三形

_SMALL = "输出(1 + 2)\n"
_CHAIN_LEX = [_LEXER_TXT]
_CHAIN_AST = [_LEXER_TXT, _STDLIB_TXT, _PARSER_TXT]


@pytest.mark.parametrize("tag,sources", [
    ("small", [_SMALL]),
    ("lex", _CHAIN_LEX),
    ("parser_chain", _CHAIN_AST),
], ids=["单语句", "词法器片", "词法+标准+语法片"])
def test_46c21_native_build_is_byte_deterministic(tag, sources):
    """同一份源独立编译两次 → PE 逐字节相同（原生自证的第一形）。

    构建期裁判只有发射器自己的可重复性，不涉及任何执行面对拍。
    """
    a = _bytes(f"{tag}_a", sources)
    b = _bytes(f"{tag}_b", sources)
    assert a == b, f"{tag} 两次编译产物不同（{len(a)} vs {len(b)} 字节）——产物里混入了序/时间戳/地址"
    assert a[:2] == b"MZ", f"{tag} 产物不是 PE"


def test_46c22_same_image_runs_verbatim_identically():
    """同一个映像连跑三次 → rc 0 且 stdout 逐字相同（原生自证的第二形）。

    只比一次的话，「每次不同但这次恰好等于字面量」这种形态接不住；三次是
    把 ASLR / 未初始化槽 / 表遍历序这类运行期不定性逼出来。
    """
    exe = _exe("lex_drv", _CHAIN_LEX + [_LEX_DRV])
    runs = [_run(exe) for _ in range(3)]
    for rc, _out, err in runs:
        assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:160]}"
    assert all(o == runs[0][1] for _r, o, _e in runs), "同一映像三跑读数不同"
    assert all(e == "" for _r, _o, e in runs), "同一映像三跑 stderr 不同"


def test_46c23_link_partition_equals_concatenation_image():
    """多模块链接 vs 文本拼接：映像逐字节相同、读数逐字相同。

    「相同」是当下的真实现状（45b 的链接面即按源序拼接后一次发射），不是缺陷——
    但这条锁的价值在于它是**产物层**的等值：将来链接面若长出独立的符号解析/
    数据段布局，本锁会红，届时按新口径改写而不是删掉。
    """
    linked = _bytes("linked", _CHAIN_AST + [_LEX_DRV])
    merged = _bytes("merged", ["\n".join(_CHAIN_AST + [_LEX_DRV])])
    assert linked == merged, "链接面与拼接面产物已分叉——本锁口径需随实现改写并登记"
    p1 = _exe("linked_drv", _CHAIN_AST + [_LEX_DRV])
    p2 = _exe("merged_drv", ["\n".join(_CHAIN_AST + [_LEX_DRV])])
    r1, r2 = _run(p1), _run(p2)
    assert r1[0] == r2[0] == 0, f"rc 不同：{hex(r1[0])} vs {hex(r2[0])}"
    assert r1[1] == r2[1], "链接面与拼接面读数不同判"


# ================================================== 46c2-4 词法器手算字面读数

# 6 条输入，逐行依据写进注释：类型名取自 `matha/lexer.matha` 的
# 类型枚举（14-15 行 整数/浮点/字符串/布尔/标识符/关键字/符号/换行/结束）、
# 单符映射表（103-157 行）、多符表（70-84 行）、关键字表（160-191 行）与
# 扫描主循环的行列推进（415-459 行，入口 扫描(src)(0)(1)(1)([])，EOF 产
# 做Token(结束, "", line, col)）。
_LEX_IN = ["1",                                # 整数 + 结束（pos0→col1，EOF col2）
           "x + 2",                           # 标识符/加/整数
           "a >= b",                          # 大于等于走 检测多符（70 行）
           "真 假",                            # 布尔走 关键字类型（187/194 行）
           "1.5",                             # 浮点（444 行数字分支）
           "func f(x: Int) -> Int = (x) => x"]
# 注意 `Int` 是 关键字 而非 标识符——关键字表 188 行逐字列了
# (tok = "Int")，故类型位给 关键字。这一条是手算过程里唯一被源文件推翻的
# 直觉（「类型名该是标识符」），正说明字面裁判得对着 Matha 源推，不能对着
# 记忆里别的语言推。
LEX_WANT = [
    "[1] n=2",
    "整数|1|1|1", "结束||1|2",
    "[x + 2] n=4",
    "标识符|x|1|1", "加|+|1|3", "整数|2|1|5", "结束||1|6",
    "[a >= b] n=4",
    "标识符|a|1|1", "大于等于|>=|1|3", "标识符|b|1|6", "结束||1|7",
    "[真 假] n=3",
    "布尔|真|1|1", "布尔|假|1|3", "结束||1|4",
    "[1.5] n=2",
    "浮点|1.5|1|1", "结束||1|4",
    "[func f(x: Int) -> Int = (x) => x] n=16",
    "关键字|func|1|1", "标识符|f|1|6", "左括号|(|1|7", "标识符|x|1|8",
    "冒号|:|1|9", "关键字|Int|1|11", "右括号|)|1|14", "箭头|->|1|16",
    "关键字|Int|1|19", "等于|=|1|23", "左括号|(|1|25", "标识符|x|1|26",
    "右括号|)|1|27", "胖箭头|=>|1|29", "标识符|x|1|32", "结束||1|33",
]

_LEX_DRV = ("let 输入们 = " + _lit(_LEX_IN) + "\n"
            "for s in 输入们 {\n"
            "  let 记 = 词法器.扫描(s)(0)(1)(1)([])\n"
            '  输出("[" + s + "] n=" + str(len(记)))\n'
            "  for t in 记 {\n"
            '    输出(str(t.类型) + "|" + str(t.文本) + "|" + str(t.行) + "|" + str(t.列))\n'
            "  }\n}\n")


def test_46c24_matha_lexer_in_a_native_exe_matches_hand_literals():
    """词法器（Matha 写的）跑在真 PE64 里，37 行 token 流逐字等于本档手写字面量。

    裁判只有这份字面量——不调 hi/vm/链面任何一面。Python 退役后这条照样成立，
    因为被判定的是映像的 stdout 与一段写死在仓库里的文本。
    """
    rc, out, err = _run(_exe("lex_drv", _CHAIN_LEX + [_LEX_DRV]))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:160]}"
    first = next((i for i in range(max(len(out), len(LEX_WANT)))
                  if out[i:i + 1] != LEX_WANT[i:i + 1]), None)
    assert out == LEX_WANT, f"第 {first} 行起与手写字面量不同判：got={out[first:first+3]} want={LEX_WANT[first:first+3]}"


# ================================================== 46c2-5 语法器手算字面读数

# 三条输入 → 程序/声明 类型与名。类型名逐字取自 `matha/parser.matha` 的构造子：
# 做Program 的 "程序"（21 行）、做FuncDef 的 "函数定义"（23 行）、
# 做Binding 的 "绑定"（27 行）、做FuncApp 的 "函数应用"（144 行）。
# 首行 '1' 不是本驱动的读数，而是 `matha/parser.matha` 末尾
# `#：{ [1] }` 自测块在映像里被执行时产的一行（与阶段 45 45d-4 锁的
# 「1 回声 + 9 头 + 9 声明 = 19 行」同一来源）。
_AST_IN = ["x = 1", "func 加一(a: Int) -> Int = (a) => a + 1", "输出(1 + 2)"]
AST_WANT = [
    "1",
    "[x = 1] 程序/1", "绑定/x/None",
    "[func 加一(a: Int) -> Int = (a) => a + 1] 程序/1", "函数定义/加一/None",
    "[输出(1 + 2)] 程序/1", "函数应用/None/None",
]
_AST_DRV = ("let 输入们 = " + _lit(_AST_IN) + "\n"
            "for s in 输入们 {\n"
            "  let ast = 语法器.parse(词法器.扫描(s)(0)(1)(1)([]))\n"
            '  输出("[" + s + "] " + str(ast.类型) + "/" + str(len(ast.声明)))\n'
            "  for d in ast.声明 {\n"
            '    输出(str(d.类型) + "/" + str(d.名) + "/" + str(d.运算符))\n'
            "  }\n}\n")


def test_46c25_matha_parser_in_a_native_exe_matches_hand_literals():
    """三文件链进的映像产 AST 流，7 行逐字等于手写字面量（含 '1' 回声行）。

    `d.运算符` 对绑定/函数定义/函数应用节点都是缺键 → 渲染 None，这三行
    同时是「缺键读取给 None」这条语言口径在原生面的读数证据。
    """
    rc, out, err = _run(_exe("ast_drv", _CHAIN_AST + [_AST_DRV]))
    assert rc == 0, f"映像非零退出 rc={hex(rc)} stderr={err[:160]}"
    assert out == AST_WANT, f"AST 流与手写字面量不同判：{out}"


# ==================================================== 46c2-6 字面量是承重的

def test_46c26_hand_literals_are_load_bearing():
    """反控：置换顺序 / 改一个类型名，都必须与映像读数不同判。

    没有这条，把 LEX_WANT 换成任意一份「看起来像」的表都能靠「只比集合不比序」
    蒙过去——逐字逐序才有判定力。
    """
    rc, out, _err = _run(_exe("lex_drv", _CHAIN_LEX + [_LEX_DRV]))
    assert rc == 0
    assert out == LEX_WANT
    shuffled = LEX_WANT[1:] + LEX_WANT[:1]          # 头行挪到末尾
    assert shuffled != out, "顺序没被锁住：置换整张表仍与读数相同"
    mutated = list(LEX_WANT)
    mutated[mutated.index("关键字|Int|1|11")] = "标识符|Int|1|11"
    assert mutated != out, "类型名没被锁住：改成 标识符 仍与读数相同"
    mutated2 = list(LEX_WANT)
    mutated2[mutated2.index("大于等于|>=|1|3")] = "大于|>=|1|3"
    assert mutated2 != out, "多符归一没被锁住：退化成 大于 仍与读数相同"


def test_46c27_literals_agree_with_the_matha_source_not_with_memory():
    """字面量的依据可追：每条断言的类型名都能在 `matha/lexer.matha` 里逐字找到。

    手算读数最怕「写的是当年宿主给的东西」。这里把 6 个类型名反查回 Matha 源
    （关键字表/多符表/单符表/类型枚举），源一改而字面量未同步 → 红。
    """
    for tok_type in ("整数", "标识符", "加", "大于等于", "布尔", "浮点",
                     "关键字", "冒号", "左括号", "右括号", "箭头", "等于",
                     "胖箭头", "结束"):
        assert re.search(rf"\b{tok_type}\b", _LEXER_TXT), \
            f"类型名 {tok_type} 在 matha/lexer.matha 里已找不到——字面量依据失效"
    for node_type in ("程序", "函数定义", "绑定", "函数应用"):
        assert f'"{node_type}"' in _PARSER_TXT, \
            f"AST 类型名 {node_type} 在 matha/parser.matha 里已找不到"


# ================================================= 46c2-12/13/14 编译面 A/B 双跑

_COMPILER_TXT = (_ROOT / "matha" / "compiler_matha.matha").read_text(encoding="utf-8")
# 编译面四片：词法 → 标准库 → 语法 → 编译（`matha/compiler_matha.matha` 顶部
# `use 词法器 / 语法器 / 标准库`，缺任一片在链接期即拒）。解释器面
# （interp_matha / loader）仍进不了映像——见本档末尾的边界段。
_BC_SRC = [_LEXER_TXT, _STDLIB_TXT, _PARSER_TXT, _COMPILER_TXT]

# 驱动在**映像内**调用 Matha 自己写的编译器（`编译器.编译`），将字节码模块的
# 常量池 / 主码 / 函数表逐条渲染出来。Python 在这里只做两件事：把这四片源
# 交给发射器、跑产物——不参与任何判定。
_BC_DRV = r'''
let 输入们 = ["输出(7)", "let x = 2 * 3\n输出(x)", "输出(\"hi\")",
              "func 加一(a: Int) -> Int = (a) => a + 1\n输出(加一(41))"]
for s in 输入们 {
  let m = 编译器.编译(s)
  输出("SRC|" + s)
  输出("nconst|" + str(len(m.常量)))
  for c in m.常量 { 输出("C|" + str(c)) }
  输出("nmain|" + str(len(m.主码)))
  for ins in m.主码 { 输出("M|" + str(ins)) }
  输出("nfunc|" + str(len(m.函数)))
  for f in m.函数 { 输出("F|" + str(f)) }
  输出("mod|" + str(m.模块名))
}
let m1 = 编译器.编译("输出(7)")
let m2 = 编译器.编译("输出(7)")
输出("repeat常量|" + str(m1.常量) + "|" + str(m2.常量))
输出("repeat主码|" + str(m1.主码) + "|" + str(m2.主码))
输出("repeat函数|" + str(m1.函数) + "|" + str(m2.函数))
'''

# 任务 #249 形态 ①「原生映像 A 编译出的产物 == 原生映像 B」+ 形态 ② 手算对拍
# 的同一条读数。逐行依据（`matha/compiler_matha.matha` 的行号）：
#   · 常量登记**不去重**：`_加常量`(134 行) 直接 append，故同一个名字出现几位
#     就占几个常量位（B 组的 "x" 两位、D 组的 名字/运算符 各一位）。
#   · OP 编码取自编译器自己的常量表：PUSH_CONST 1(28 行 0x01)、LOAD_LOCAL 16
#     (32 行 0x10)、LOAD_GLOBAL 23(39 行 0x17)、STORE_GLOBAL 24(40 行 0x18)、
#     CALL 33(42 行 0x21)、RET 34(43 行 0x22)、BINOP 64(47 行 0x40)、
#     POP 89(56 行 0x59)、HALT 255(71 行 0xFF)。
#   · FuncApp 发射序 = callee 先、参数后、再 CALL 带元数；嵌套应用自内向外收口。
#   · 顶层表达式语句尾随 POP，程序末 HALT。
#   · `2 * 3` 走 `_折叠二元`(1449 行) → 常量池里是 6，主码里没有 BINOP 项；
#     `a + 1` 的操作数不可折叠 → 函数码里保留 [64, 1]，其 1 指向 "+" 的常量位。
# 首行 "1" 是 `matha/parser.matha` 末尾自测块在装载时产的回声（与 46c2-5 同源）。
# 注：F| 一行的引号/键序形如 `{'参数': ...}` 由原生 `str` 内建的渲染族决定
# （src/mbc/native.py），不是 Matha 源里的定义——渲染族改版时该行随之改，
# 而 A/B 双跑（46c35）与反控（46c37）不受影响。
BC_WANT = [
    "1",
    # A: 输出(7)
    "SRC|输出(7)", "nconst|2", "C|输出", "C|7", "nmain|5",
    "M|[23, 0]", "M|[1, 1]", "M|[33, 1]", "M|[89]", "M|[255]", "nfunc|0", "mod|主程序",
    # B: let x = 2 * 3 / 输出(x)
    "SRC|let x = 2 * 3", "输出(x)", "nconst|4", "C|6", "C|x", "C|输出", "C|x", "nmain|7",
    "M|[1, 0]", "M|[24, 1]", "M|[23, 2]", "M|[23, 3]", "M|[33, 1]", "M|[89]", "M|[255]",
    "nfunc|0", "mod|主程序",
    # C: 输出("hi")
    'SRC|输出("hi")', "nconst|2", "C|输出", "C|hi", "nmain|5",
    "M|[23, 0]", "M|[1, 1]", "M|[33, 1]", "M|[89]", "M|[255]", "nfunc|0", "mod|主程序",
    # D: func 加一 / 输出(加一(41))
    "SRC|func 加一(a: Int) -> Int = (a) => a + 1", "输出(加一(41))",
    "nconst|5", "C|1", "C|+", "C|输出", "C|加一", "C|41", "nmain|7",
    "M|[23, 2]", "M|[23, 3]", "M|[1, 4]", "M|[33, 1]", "M|[33, 1]", "M|[89]", "M|[255]",
    "nfunc|1",
    "F|['加一', {'参数': ['a'], '元数': 1, '局部数': 1, '码': [[16, 0], [1, 0], [64, 1], [34]]}]",
    "mod|主程序",
    # 同一映像内两次独立编译同判（编译器无可变状态泄漏）
    "repeat常量|['输出', 7]|['输出', 7]",
    "repeat主码|[[23, 0], [1, 1], [33, 1], [89], [255]]|[[23, 0], [1, 1], [33, 1], [89], [255]]",
    "repeat函数|[]|[]",
]


def _bc_out(exe: str) -> list[str]:
    rc, out, err = _run(exe)
    assert rc == 0, f"编译面映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    return out


def test_46c36_two_independently_built_images_compile_identically():
    """形态 ① 的真身：A（四片链接）与 B（同四片拼接）各为独立构建的原生映像，
    在**各自进程内**由 Matha 编译器编译同一批源，两串字节码读数逐字相同。

    裁判不是 Python，也不是「同一文件跑两遍」——是两个分别构建的映像互相为照。
    Python 只把源交给发射器（阶段 44 拍板的「仅作种子」）。
    """
    a = _exe("bc_linked", _BC_SRC + [_BC_DRV])
    b = _exe("bc_merged", ["\n".join(_BC_SRC + [_BC_DRV])])
    assert Path(a).read_bytes() == Path(b).read_bytes(), \
        "编译面链接产物与拼接产物已分叉（本锁口径需随实现改写并登记）"
    oa, ob = _bc_out(a), _bc_out(b)
    assert oa == ob, f"A/B 双映像编译读数不同判：{next((i for i in range(max(len(oa), len(ob))) if oa[i:i+1] != ob[i:i+1]), None)}"
    assert oa == BC_WANT, "A/B 相同但与手算字面量不同判——见 46c37 的逐行依据"
    for line in [l for l in oa if l.startswith("repeat")]:
        _tag, x, y = line.split("|", 2)
        assert x == y, f"同一映像内重复编译不同判：{line}"


def test_46c37_native_compiled_bytecode_matches_hand_literals():
    """Matha 编译器在真 PE64 里产的字节码逐行等于本档手写字面量（形态 ②）。

    这条是 Python 退役后仍然活着的**编译面**判据：被判定的是映像 stdout 与
    一段写死在仓库里的文本，依据指到 `matha/compiler_matha.matha` 的源行。
    """
    out = _bc_out(_exe("bc_linked", _BC_SRC + [_BC_DRV]))
    first = next((i for i in range(max(len(out), len(BC_WANT)))
                  if out[i:i + 1] != BC_WANT[i:i + 1]), None)
    assert out == BC_WANT, \
        f"第 {first} 行起与手算字节码不同判：got={out[first:first + 4]} want={BC_WANT[first:first + 4]}"


def test_46c38_bytecode_literals_are_load_bearing():
    """反控：改一个操作码数 / 把折叠改回两条压栈 / 调常量池顺序，都必须不同判。

    字节码读数若只比「指令条数」，这三刀都砍不下去——逐字逐序才有力气。
    """
    out = _bc_out(_exe("bc_linked", _BC_SRC + [_BC_DRV]))
    assert out == BC_WANT
    m1 = list(BC_WANT)
    m1[m1.index("M|[23, 0]")] = "M|[24, 0]"        # LOAD_GLOBAL → STORE_GLOBAL
    assert m1 != out, "操作码编号没被锁住"
    m2 = list(BC_WANT)
    m2[m2.index("C|6")] = "C|2"                    # 折叠结果退回左操作数
    assert m2 != out, "常量折叠结果没被锁住"
    m3 = list(BC_WANT)
    i = m3.index("C|x")
    m3[i], m3[i + 1] = m3[i + 1], m3[i]            # 常量池顺序置换
    assert m3 != out, "常量池顺序没被锁住"
    assert len([l for l in out if l.startswith("M|")]) == \
        sum(int(l.split("|")[1]) for l in out if l.startswith("nmain|")), \
        "nmain 计数与 M| 行数不闭合"


# ==================================================== 46c2-8 零 Python 裁判

# 逐条拆成两段再拼接：needle 整词写进本文件时，去引号扫描会在**声明处**命中自己
# （第一跑就是恒红在这里）。拼接后本文件文本不含任何 needle 的连续形，
# 命中只可能是真调用。
_FORBIDDEN = ("interp" + "ent(", "run_module" + "(", "exec" + "_api",
              "from src" + ".interp", "from src import" + " interp",
              "make" + "_vm", "build" + "_boot_vm",
              "src" + ".domains", "src" + ".plugins")


def test_46c28_this_ledger_never_asks_python_to_judge():
    """本档源码级边界：宿主面/领域插件一面都不许进裁判。

    锁的是「文本里出现什么」而不是「跑出来什么」——因为一旦允许 host 读数等于
    映像读数这种形，Python 就又变成裁判了，而这正是 46c 要拆掉的东西。
    """
    scanned = _MAIN_SRC.replace('"', "")
    for forbidden in _FORBIDDEN:
        assert forbidden not in scanned, \
            f"46c 自证档里出现了宿主裁判/插件引用 {forbidden!r}"
    assert "from src.mbc import native" in _MAIN_SRC
    assert "from src.mbc.compiler import compile_sources" in _MAIN_SRC


def test_46c29_differential_face_is_declared_dev_only():
    """Track B 的差分面自陈口径：AUTHORITY = dev-only-differential。

    改这个常量 = 声明「差分面升级为正确性权威」，那需要新的判据形态，不该悄悄发生。
    """
    from scripts import selfhost_matrix as sm
    assert sm.AUTHORITY == "dev-only-differential", sm.AUTHORITY
    doc = (_ROOT / "scripts" / "selfhost_matrix.py").read_text(encoding="utf-8")
    assert "dev-only" in doc and "46c" in doc, "脚本 docstring 的 46c 口径段被删了"


def test_46c30_product_code_does_not_import_the_dev_only_faces():
    """dev-only 判定工具不许反向变成产品依赖（否则退役时拆不掉）。"""
    needle = re.compile(r"(from|import)\s+scripts[.\s]", re.M)
    offenders = []
    for p in (_ROOT / "src").rglob("*.py"):
        if needle.search(p.read_text(encoding="utf-8", errors="replace")):
            offenders.append(p.relative_to(_ROOT).as_posix())
    assert not offenders, f"产品面 import 了判定工具：{offenders}"


# ==================================================== 46c2-9/10/11 功率台账

def _snap():
    return _ROOT / "docs" / "selfhost_matrix.json"


def test_46c31_snapshot_splits_equality_by_power():
    """快照的 both_ok_equal 必须逐条带 n_outs，且 summary.power 分层与条目一致。"""
    from scripts import selfhost_matrix as sm
    snap = sm.load_snapshot()
    s = snap["summary"]
    assert "power" in s, f"快照缺 power 节（需 python scripts/selfhost_matrix.py --write）：{sorted(s)}"
    rows = [e for e in snap["files"] if sm._classify(e) == "both_ok_equal"]
    assert all("n_outs" in e for e in rows), \
        [e["path"] for e in rows if "n_outs" not in e][:5]
    obs = [e for e in rows if e["n_outs"]]
    silent = [e for e in rows if not e["n_outs"]]
    assert len(obs) == s["power"]["both_ok_equal_obs"], "obs 读数与条目不一致"
    assert len(silent) == s["power"]["both_ok_equal_silent"], "silent 读数与条目不一致"
    assert len(obs) + len(silent) == s["both_ok_equal"]
    ok, msg = sm.structure_check()
    assert ok, f"结构锁不闭合：{msg}"
    assert OBS_PATHS == sorted(e["path"] for e in obs), "有读数的语料清单漂移（见 46c2-10 台账）"
    assert sum(e["n_outs"] for e in obs) == OBS_LINES, "比对行数漂移"


#: 46c2-10 台账：差分面真正比过内容的语料（阶段 46c 时点实测）。这是**漂移台账**
#: 而不是正确性判据——它只回答「哪天这条面少比了哪几个文件」。
OBS_PATHS = [
    "examples/ai/ai_framework.matha", "examples/ai/data_pipeline.matha",
    "examples/ai/genetic_algo.matha", "examples/ai/neural_network.matha",
    "examples/basic_examples.matha", "golden_tests/cases/01_arithmetic_and_relations.matha",
    "golden_tests/cases/02_function_definition.matha", "golden_tests/cases/03_curried_closure.matha",
    "golden_tests/cases/04_block_tail_value.matha", "golden_tests/cases/05_block_tail_if.matha",
    "golden_tests/cases/06_block_multi_statement.matha", "golden_tests/cases/07_loops.matha",
    "golden_tests/cases/08_loops_break_continue.matha", "golden_tests/cases/09_try_catch_raise.matha",
    "golden_tests/cases/10_try_catch_runtime_error.matha", "golden_tests/cases/11_try_throw.matha",
    "golden_tests/cases/15_type_annotations_typeof.matha", "golden_tests/cases/16_recursion.matha",
    "golden_tests/cases/17_try_block_binding.matha", "golden_tests/cases/18_domain_lazy_load.matha",
    "golden_tests/cases/19_corpus_recursion.matha", "golden_tests/cases/20_corpus_sum.matha",
    "golden_tests/cases/21_corpus_dot.matha", "golden_tests/cases/22_corpus_cond_chain.matha",
    "golden_tests/cases/23_corpus_tuple_index.matha", "golden_tests/cases/30_corpus_nested_rec_nocap.matha",
    "golden_tests/cases/32_ternary_eq_precedence.matha", "golden_tests/cases/33_sci_notation.matha",
    "golden_tests/cases/34_return_list_literal.matha", "golden_tests/cases/35_list_comp.matha",
    "golden_tests/cases/36_basics_map_filter_reduce.matha", "golden_tests/cases/37_basics_sorted.matha",
    "golden_tests/cases/38_basics_join_split.matha", "golden_tests/cases/39_basics_gcd.matha",
    "matha/bootstrap_full_test.matha", "matha/bootstrap_matha.matha",
    "matha/bootstrap_test.matha", "matha/bootstrap_test_v2.matha",
    "matha/examples/01_arithmetic.matha", "matha/examples/02_functions.matha",
    "matha/examples/03_set_iter.matha", "matha/examples/04_pipeline.matha",
    "matha/examples/05_sensor_read.matha", "matha/examples/06_main.matha",
    "matha/examples/06_sub.matha", "matha/examples/07_auto_debug.matha",
    "matha/examples/07_debug_sub.matha", "matha/examples/08_auto_optimize.matha",
    "matha/examples/08_optimize_sub.matha", "matha/examples/09_grow_sub.matha",
    "matha/examples/09_self_grow.matha", "matha/examples/10_library_read.matha",
    "matha/examples/10_library_sub.matha", "matha/examples/10_web_app.matha",
    "matha/examples/11_desktop.matha", "matha/examples/11_grow_sub.matha",
    "matha/examples/11_library_grow.matha", "matha/examples/12_backend.matha",
    "matha/examples/12_library_discipline.matha", "matha/examples/12_mech_sub.matha",
    "matha/examples/99_multiParam_boundary.matha", "matha/interp.matha",
    "matha/runtime/test_compile.matha", "matha/runtime/test_math.matha",
    "matha/shaft_sub.matha", "matha/store_engine.matha",
    "matha/template_new.matha", "matha/template_old.matha",
    "tests/test_plugin_load.matha", "tests/test_plugin_ode.matha",
    "tests/test_plugin_series.matha",
]
OBS_LINES = 270


def test_46c32_resource_corpus_has_no_differential_evidence():
    """资源库语料在差分面上的证据贡献如实记账：52 条全是空对空。

    旧口径「52 个资源语料全 both_ok_equal」被读作收益证据，实际那 52 条
    一条内容都没比过（语料只定义函数、顶层不产输出）。资源库真正的证据在
    `tests/test_resource_algorithm_true_phase41.py` 的手算锁里——本条把这件事
    变成机器判定，谁把「全 both_ok_equal」再当收益引用，这里就露形。
    """
    from scripts import selfhost_matrix as sm
    snap = sm.load_snapshot()
    res = [e for e in snap["files"] if e["path"].startswith("matha/resource/")]
    assert len(res) == 52, f"资源语料数变了：{len(res)}"
    eq = [e for e in res if sm._classify(e) == "both_ok_equal"]
    assert len(eq) == 52, [e["path"] for e in res if sm._classify(e) != "both_ok_equal"]
    assert all(not e.get("n_outs") for e in eq), \
        [(e["path"], e.get("n_outs")) for e in eq if e.get("n_outs")][:5]


#: 46c2-11 文档口径锚点：四份文档里写的名数/行数必须等于当场实测。
_DOC_ANCHOR_FIELDS = ("README.md", "docs/ARCHITECTURE.md", "docs/CHANGELOG.md",
                      "docs/KNOWN_ISSUES.md")


def test_46c33_docs_anchor_the_power_reading_to_measured_values():
    """防「文档与判定面脱钩」：口径行由实测值拼出，改数不改文即红。

    承继 46j 的做法（阶段 46-1 把 25 写成现行值正是缺这类锁）。
    """
    from scripts import selfhost_matrix as sm
    s = sm.load_snapshot()["summary"]
    p = s["power"]
    anchor = (f"双面一致 {s['both_ok_equal']} = 有读数 {p['both_ok_equal_obs']} "
              f"+ 空对空 {p['both_ok_equal_silent']}")
    bad = [rel for rel in _DOC_ANCHOR_FIELDS
           if anchor not in (_ROOT / rel).read_text(encoding="utf-8")]
    assert not bad, f"以下文档缺 46c 功率口径行 {anchor!r}：{bad}"


def test_46c34_evidence_file_is_registered_and_not_self_referential():
    """快照在位 + 本档锁的判据不依赖快照之外的隐藏产物。"""
    assert _snap().exists(), "缺 docs/selfhost_matrix.json"
    assert (_ROOT / "tests" / "test_judgment_face_phase46c.py").exists()
    assert not list(_ROOT.glob("scripts/scratch/p46c/*.json")), \
        "46c 的判据不许寄生在 scratch 产物里"
