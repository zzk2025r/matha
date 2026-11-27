"""阶段 45 锁档：原生映像承载 Matha 工具链首片。

拍板口径（阶段 45）：首批切片 = 原生映像承载 Matha 工具链首片；范围边界 =
只做最小可编译片段（不扩 OS 载体）+ 补多模块链接（一次编入多个 .matha）+
一并处理原生栈上限 + 附带收口文档漂移与勘误；验证深度 = 全量门禁 + 真原生
exe e2e。

45a arity 上限真化：`MAX_NATIVE_ARITY` 8 → 15。15 不是选定的经验值，而是
调用点/序言的 disp8 编码可达上界（`-8*(argc+1)` ≥ -128 ⇒ argc ≤ 15；
arity=16 可定义但同一次调用最多递 15 个实参，永不完整应用，故定义位与
调用位取同一常量）。`apply_rt` 按 rdx 动态 `rep movsq`，本身无 arity 假设。
boot 链中唯一的越界真形是 `扫描三引号续`(9)（全链另含 `_推导绑定`(9)），
旧上限使整个词法器在原生面直接编译失败——这是「原生面承载 Matha 工具链」
的编译期唯一硬阻塞。

覆盖：
- 45a-1 上限常量与两处拒绝位的文案同源锁（改数不改文案 → 红）。
- 45a-2 9..15 参函数原生面**真跑**且与 hi/vm 三面同判（含 15 的 disp8 边界）。
- 45a-3 16 参显式拒绝（不静默错编）。
- 45a-4 boot 链越界函数名集锁（漂移即显形）。
- 45a-5 词法器片在原生面从「编译失败」转「编译成功」（本阶段首个真收益）。
- 45b-1 链接语义（编译面）：N 源并一个模块、源序即顶层执行序、空源不特殊拒绝。
- 45b-2 跨文件 `use` 在原生 exe 里**真跑**三面同判，且单文件不链则运行期诚实
  失败——证明收益来自链接而非偶然的全局注入；单源路径逐字节零扰动。
- 45b-3/4 门面 `compile_modules` / `build_exe(list)` 与产品 CLI `原生构建`
  多源位：一份产物、默认输出取首源、次源不可读不留半成品。
- 45b-5 文案与 argparse 接线锁（usage 行声称多源即一次链接，须与行为同源）。
- 45c-1 静态栈模型锁：全操作码净增量表无遗漏、峰值/汇合/夹住/不收敛四条判据、
  容量与留白常量的算术自洽、操作数栈落 .bss（不花文件字节）、守卫标签真在
  .text 里、`_start` 真填 `stack_floor`、PE 头 StackReserve 与常量同源。
- 45c-2 真 exe 行为锁：薄帧 2 万层给正确读数（旧形是静默改写内存后退出码 0）、
  越界给可捕获的诚实异常而非 rc 0 / 0xC00000FD、胖帧由调用栈守卫接住、
  `调用捕获` 接住后进程继续正常执行；全 .matha 语料与 boot 链在链接期零拒绝。
- 45d-0 原生序比较真化：字符串/列表/元组/布尔的 `< <= > >=` 三面逐字同判。旧形在
  任一侧为指针时按 `.data` 地址序给判——`输出("b" > "a")` 直接反号，故这条正形锁
  本身就是反地址序探测器；混合类型/字典/null 三面各自诚实拒绝，原生文案取自发射器
  错误表（与宿主 `'<' not supported between…` 文案分歧登记不修）。
- 45d-0b 符号扩展位形锁：`val_cmp` 的 -1 必须走 REX.W 形（`48 C7 C0 FF FF FF FF`），
  32 位零扩展形会把 -1 变成 +4294967295，而调用点按 `cmp rax,0` 定序即全反；
  尾位置一元负返回值锁（`func f(x) -> Int = -x` 旧形把 `is_bigint` 的 0/1 判定值
  当结果返回，只有返回位露馅）。
- 45d-1 帧内解构 rbp 回归：8 形态三面同判、解构后续开局部槽仍指真帧、解构失败在
  帧内可捕获、未捕获时保住先前输出并给同一句消息体。
- 45d-2 编码位防再犯：`mov_rr(dst, src)` 的 5 对寄存器编码表锁 + 手拼
  `mov rbp,r8` 模式在发射器源码里绝迹 + 解构头真值来源是 `mov_rr`。
- 45d-3 Matha 写的词法器片编进真 PE64：14 条输入的 token 流（类型|文本|行|列）与
  宿主两面逐字同判，并有可达性正向锁——读数里确有只经帧内解构产得的记号。
- 45d-4 Matha 写的语法器片（词法+标准库+语法三文件链接）：9 条可解析输入的 AST 流
  三面逐字同判；5 条不可解析输入在 `调用捕获` 下三面同给同一句消息体（不是崩溃）；
  未捕获时 exe 非零退出、stderr 给同一消息体。
- 45d-5 反向控：承载工具链的映像与阶段 44 的小产物同规格——无导入表、三节、
  PE32+，产物字节里无 python/Cpython/site-packages 标记。
- 45d-6 诚实边界：「能编」≠「已脱宿主」——boot 全链 22 个宿主注入名的 latent 名集
  与重复次数锁（阶段 45 时点 25，其中 `acc` 经 46 摸底取证为**语料级自由名缺陷**而非
  宿主注入名，同批真修后名集 25→24，见 `test_native_selfhost_phase46.py`；阶段 46a-3
  给 `未定义错误`/`MathaRuntimeError` 落原生载体后再 24→22）、词法器单片
  latent 归零、latent 名在运行期如实点名失败；另锁
  `src/mbc/native.py`「当前无此类可达名字」断言已过时（`长度` 直调 / 函数体内均为
  latent，`use` 形态还把 `加载模块` 自身带成 latent——45b 多源链接的存在理由）；另锁
  原生面未定义名的 stderr **带名同判**（`未定义变量 'X'`，与 hi/vm/链面逐字一致——
  阶段 46a-3 前原生只报无名的「未定义变量」，载体缺口无法定位）。异常**类名**载体
  仍缺（原生无异常类型），该形状差承继 41-③ 登记。
- 45e 文档口径收口：链面固定注册面 60 名（interp_matha）与宿主对位镜像 44 名（interp）
  双计数锁、`module 解释器` 两套源 + 三套解析序的落点锁、5 处消费者只用交集名（分歧
  目前潜伏）、struct 工厂缺口的登记锁与 KNOWN_ISSUES 行号勘误锁。第四个计数：宿主
  `Interpreter` **实例内建表** 3025 名（阶段 41 时点 3020 + 阶段 44 映像族拒绝内建 5），
  与模块级基表 `src.interp.BUILTINS` 82 名不是一张表——锁法不是写死数字，而是「文档
  口径段所写 == 当场实测」，内建表一动该锁即红，逼读数同步（时点值被读作现行值，正是
  本轮要治的漂移）。
"""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src import ast_nodes as ast  # noqa: E402
from src.interp import MathaUndefinedNameError, interpret  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.mbc import compile_source, run_module  # noqa: E402
from src.mbc import native  # noqa: E402
from src.mbc.compiler import Compiler, compile_sources  # noqa: E402
from src.mbc import opcodes as OP  # noqa: E402
from src.mbc.native import (MAX_NATIVE_ARITY, NativeNotSupported,  # noqa: E402
                           compile_sources_to_exe, compile_to_exe)
from src.mbc.vm import VM  # noqa: E402
from src.parser import parse as py_parse  # noqa: E402

NATIVE_SRC = (_ROOT / "src" / "mbc" / "native.py").read_text(encoding="utf-8")
MAIN_SRC = (_ROOT / "src" / "matha_main.py").read_text(encoding="utf-8")


def _cli(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """走产品入口 `matha …`（stderr 并入 stdout，与阶段 44 锁档同口径）。"""
    return subprocess.run([sys.executable, "-m", "src.matha_main", *args],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          cwd=str(_ROOT), timeout=timeout)


def _exe(tag: str, src: str) -> str:
    """每个用例独立 exe 名——Windows 下固定名会被上一进程的映像锁住。"""
    p = os.path.join(tempfile.gettempdir(), f"p45_{tag}.exe")
    Path(p).write_bytes(compile_to_exe(src))
    return p


def _exe_srcs(tag: str, sources: list[str]) -> str:
    p = os.path.join(tempfile.gettempdir(), f"p45_{tag}.exe")
    Path(p).write_bytes(compile_sources_to_exe(sources))
    return p


def _run(path: str) -> tuple[int, list[str], str]:
    r = subprocess.run([path], capture_output=True, timeout=120)
    return (r.returncode & 0xFFFFFFFF,
            r.stdout.decode("utf-8", "replace").splitlines(),
            r.stderr.decode("utf-8", "replace"))


def _aot(tag: str, src: str) -> tuple[int, list[str], str]:
    return _run(_exe(tag, src))


def _aot_srcs(tag: str, sources: list[str]) -> tuple[int, list[str], str]:
    return _run(_exe_srcs(tag, sources))


def _hi(src: str) -> list[str]:
    outs, _trace = interpret(src)      # interpret 返回 (outputs, trace)
    return [str(o) for o in outs]


def _vm(src: str) -> list[str]:
    return [str(v) for v in run_module(compile_source(src))]


def _arity_src(n: int) -> str:
    """n 参函数，形参权重互异且非单调——顺序错位立刻显形。

    权重按 10**(i%4) 循环，故 n>4 时高位由进位区分，三面读数必为同一整数。
    """
    sig = ", ".join(f"a{i}: Int" for i in range(n))
    ps = ", ".join(f"a{i}" for i in range(n))
    body = " + ".join(f"a{i} * {10 ** (i % 4)}" for i in range(n))
    args = ", ".join(str(i + 1) for i in range(n))
    return f"func f({sig}) -> Int = ({ps}) => {body}\n输出(f({args}))\n"


# ---------------------------------------------------------- 45a-1 同源锁

def test_45a1_cap_is_the_disp8_encoding_ceiling():
    """上限取 15 的理由锁进断言，而非只写进注释。

    调用点函数槽读取用 disp8：`-8*(argc+1)` 必须 ≥ -128 ⇒ argc ≤ 15；
    再大一位（argc=16 → -136）就溢出 disp8，发射器会静默截成错误偏移。
    """
    assert MAX_NATIVE_ARITY == 15
    assert -8 * (MAX_NATIVE_ARITY + 1) == -128, \
        "上限不再是 disp8 可达边界，常量与编码约束已脱钩"
    assert -8 * (MAX_NATIVE_ARITY + 2) < -128, \
        "越界样本不再是必然溢出 disp8 的第一位"


def test_45a1_refusal_texts_are_derived_from_the_constant():
    """两处拒绝位（调用点 / 定义点）的文案必须引用常量而非写死数字。

    写死数字会让「上限 8」与「上限 15」的文案各自漂移，用户按文案试过
    一次仍失败——那是假拒绝。
    """
    call_guard = 'f"原生后端实参数上限 {MAX_NATIVE_ARITY}：收到 {argc}"'
    def_guard = 'f"原生后端函数参数上限 {MAX_NATIVE_ARITY}：{name} 有 {fn.arity} 个参数"'
    assert call_guard in NATIVE_SRC, "调用点拒绝文案不再与上限常量同源"
    assert def_guard in NATIVE_SRC, "定义点拒绝文案不再与上限常量同源"
    assert "实参数上限 8" not in NATIVE_SRC, \
        "native.py 的结构性限制段仍写死旧上限 8"


def test_45a1_prologue_and_call_emit_paths_share_the_cap():
    """定义位与调用位用同一个常量：只抬一侧会造成可定义却不可调用的死函数。"""
    assert NATIVE_SRC.count("MAX_NATIVE_ARITY") >= 5, \
        "生效位数量少于预期（常量定义 + 两处拒绝判断 + 两处比较），改动未贯穿"
    assert "if argc > MAX_NATIVE_ARITY" in NATIVE_SRC
    assert "if fn.arity > MAX_NATIVE_ARITY" in NATIVE_SRC


# ------------------------------------------------- 45a-2 越界 arity 真跑

@pytest.mark.parametrize("n", [9, 10, 11, 12, 13, 14, 15])
def test_45a2_over_old_cap_functions_run_natively(n):
    """旧上限（8）之下的越界形状必须在原生面真跑出正确读数。

    三面同判：hi 解释器 / MBC vm / 原生 PE64。只锁「编译通过」不算数——
    序言搬移与调用点偏移任一错位都会给出错值而非报错，那比崩溃更坏。
    """
    src = _arity_src(n)
    rc, out, err = _aot(f"ar{n}", src)
    assert rc == 0, f"{n} 参原生映像退出码 {rc}，stderr={err[:200]}"
    assert out == _hi(src), f"{n} 参：原生 {out} ≠ hi {_hi(src)}"
    assert out == _vm(src), f"{n} 参：原生 {out} ≠ vm {_vm(src)}"


def test_45a2_boundary_of_the_cap_and_one_below():
    """边界成对锁：上限本身可跑，上限-1 也可跑（防「+1 偏移」型 off-by-one）。"""
    for n in (MAX_NATIVE_ARITY - 1, MAX_NATIVE_ARITY):
        src = _arity_src(n)
        rc, out, err = _aot(f"bound{n}", src)
        assert rc == 0, f"{n} 参未跑通：rc={rc} stderr={err[:200]}"
        assert out == _vm(src) == _hi(src)


def test_45a2_order_sensitive_at_max_arity():
    """15 参时形参顺序仍须严格：换实参序则换读数。

    序言按 `[r12-8*(arity-i)]` 搬移，索引反了不会被上面的同判用例抓到
    （回文权重会自欺），故这里显式打乱一次。
    """
    n = MAX_NATIVE_ARITY
    sig = ", ".join(f"a{i}: Int" for i in range(n))
    ps = ", ".join(f"a{i}" for i in range(n))
    args = ", ".join(str(i + 1) for i in range(n))
    rev = ", ".join(str(i + 1) for i in reversed(range(n)))
    src = (f"func f({sig}) -> Int = ({ps}) => a0 * 10 + a14\n"
           f"输出(f({args}))\n输出(f({rev}))\n")
    rc, out, err = _aot("order15", src)
    assert rc == 0, f"rc={rc} stderr={err[:200]}"
    assert out == ["25", "151"], f"形参顺序错位：{out}"
    assert out == _vm(src) == _hi(src)


def test_45a2_max_arity_recursion():
    """15 参函数自递归：每层递归都要重发 disp8 偏移与序言搬移。

    手算：acc(3,0,1×7,0×6) → 累加 7 → acc(2,7,0…) → acc(1,7,0…) →
    acc(0,7,0…) → 返回 a1 = 7。
    """
    n = MAX_NATIVE_ARITY
    sig = ", ".join(f"a{i}: Int" for i in range(n))
    ps = ", ".join(f"a{i}" for i in range(n))
    sum_tail = " + ".join(f"a{i}" for i in range(2, n))
    zeros = ", ".join("0" for _ in range(2, n))
    src = (f"func acc({sig}) -> Int = ({ps}) =>"
           f" if a0 <= 0 then a1 else acc(a0 - 1, a1 + {sum_tail}, {zeros})\n"
           f"输出(acc(3, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0))\n")
    rc, out, err = _aot("rec15", src)
    assert rc == 0, f"rc={rc} stderr={err[:200]}"
    assert out == ["7"], f"15 参递归读数错：{out}"
    assert out == _vm(src) == _hi(src)


def test_45a2_max_arity_closure_capture():
    """15 参闭包 + 外层捕获：env 槽与形参搬移不得互踩。

    手算：1 + 15 + 3 = 19。
    """
    n = MAX_NATIVE_ARITY
    ps = ", ".join(f"a{i}" for i in range(n))
    args = ", ".join(str(i + 1) for i in range(n))
    src = (f"let base = 3 in\n"
           f"let f = ({ps}) => a0 + a14 + base in\n"
           f"输出(f({args}))\n")
    rc, out, err = _aot("cap15", src)
    assert rc == 0, f"rc={rc} stderr={err[:200]}"
    assert out == ["19"], f"15 参闭包捕获读数错：{out}"
    assert out == _vm(src) == _hi(src)


# ------------------------------------------------------- 45a-3 拒绝位

def test_45a3_beyond_encoding_ceiling_is_refused_not_miscompiled():
    """16 参必须显式拒绝。

    放行会让调用点 disp8 = -136 被 `& 0xFF` 截成 0x78（+120），读错槽且
    不报任何错——静默错编比拒绝危险得多，故这条锁的是「拒绝存在」本身。
    """
    n = MAX_NATIVE_ARITY + 1
    with pytest.raises(NativeNotSupported) as ei:
        compile_to_exe(_arity_src(n))
    assert str(MAX_NATIVE_ARITY) in str(ei.value)
    assert str(n) in str(ei.value)


def test_45a3_refusal_is_a_clean_exception_not_a_crash():
    """拒绝发生在发射期且只抛 NativeNotSupported——不得留下半成品 exe。"""
    bad = _arity_src(MAX_NATIVE_ARITY + 1)
    try:
        compile_to_exe(bad)
    except NativeNotSupported:
        pass
    rc, out, err = _aot("ar_ok_after_bad", _arity_src(4))
    assert rc == 0 and out == _vm(_arity_src(4)), f"拒绝后原生面已污染：{out} {err[:200]}"


# ----------------------------------------------- 45a-4/5 boot 链真实形状

def _boot_decls(rels):
    decls: list = []
    for rel in rels:
        decls.extend(py_parse((_ROOT / rel).read_text(encoding="utf-8")).decls)
    return ast.Program(decls=decls)


def _compile(rels):
    comp = Compiler()
    comp.compile_program(_boot_decls(rels))
    return comp


def test_45a4_boot_chain_over_limit_set_is_exactly_two_nine_arg():
    """全 boot 链越界名集锁：当前只有 2 个 9 参函数，无 ≥10 参。

    登记具体名字而非只锁数量——新增越界函数（尤其 ≥16 参，原生面不可达）
    必须显形，否则「上限已抬」会悄悄再次失真。
    """
    from src.matha_chain import BOOT_FILES
    comp = _compile(list(BOOT_FILES))
    over = {n: f.arity for n, f in comp.mod.functions.items()
            if f.arity > 8}
    assert over == {"_推导绑定": 9, "扫描三引号续": 9}, f"越界名集漂移：{over}"
    assert max(f.arity for f in comp.mod.functions.values()) == 9, \
        "boot 链出现新的最大 arity，上限抬升的收益需重新核实"


def test_45a5_lexer_fragment_compiles_natively():
    """词法器单片在原生面从「编译失败」转「编译成功」——本阶段的直接收益。

    旧上限下此片报「原生后端函数参数上限 8：扫描三引号续 有 9 个参数」，
    即 Matha 自己的词法器根本无法进原生映像。
    """
    comp = _compile(["matha/lexer.matha"])
    exe = native.emit_exe(comp.mod)
    assert exe[:2] == b"MZ" and len(exe) > 100_000, \
        f"词法器片未产出真 PE64：{len(exe)} 字节"


def test_45a5_full_boot_chain_compiles_natively():
    """六文件全链（含装载器/解释器镜像）现已整体通过原生编译。

    这条锁的是「编译期不再有阻塞」；运行期载体缺口（22 个无原生载体的宿主
    注入名）另在 45d 的边界锁里如实登记，不在这里冒充已脱宿主。
    """
    from src.matha_chain import BOOT_FILES
    comp = _compile(list(BOOT_FILES))
    exe = native.emit_exe(comp.mod)
    assert exe[:2] == b"MZ"
    assert len(exe) > 2_000_000, f"全链 PE64 体积异常：{len(exe)}"


# ============================================== 45b-1 链接语义（编译面）

# 跨文件 use 的最小链接样本：甲只定义符号，乙只消费符号并产顶层输出。
_LINK_A = ("module 甲 {\n"
           "  func 加(a: Int, b: Int) -> Int = (a, b) => a * 100 + b\n}\n")
_LINK_B = ("module 乙 {\n  use 甲 { 加 }\n}\n输出(加(3, 4))\n")


def test_45b1_linkage_is_one_module_equivalent_to_text_concat():
    """N 源并入**一个**模块，与「文本串接后一次编译」逐指令同判。

    这条等价性是链接形正确的证据：没有为多源引入第二套发射路径，也没有
    悄悄重排声明。前提是每个源以换行收尾——否则会拼成同一 token 流。
    """
    f1, f2 = "输出(1)\n输出(2)\n", "输出(3)\n"
    merged = compile_sources([f1, f2])
    concat = compile_source(f1 + f2)
    assert list(merged.main_code) == list(concat.main_code), \
        "多源并入的顶层代码序与文本串接不同——链接引入了未声明的重排"
    assert merged.module_name == concat.module_name
    assert merged.functions.keys() == concat.functions.keys()


def test_45b1_source_order_is_execution_order():
    """源序即顶层执行序（与 boot 链装配同口径），换序即换读数。"""
    f1, f2 = "输出(1)\n输出(2)\n", "输出(3)\n"
    assert [str(v) for v in run_module(compile_sources([f1, f2]))] == ["1", "2", "3"]
    assert [str(v) for v in run_module(compile_sources([f2, f1]))] == ["3", "1", "2"]


def test_45b1_empty_and_blank_sources_are_not_special_rejections():
    """空列表/空串不特殊拒绝，也不多出代码——按无声明程序编译（只留 HALT）。"""
    halt = list(compile_sources([]).main_code)
    assert halt == list(compile_sources(["", ""]).main_code), \
        "空源与空列表的产物不同——逐源循环里掺了补偿逻辑"
    rc, out, err = _aot_srcs("empty", [])
    assert (rc, out) == (0, []), f"空程序应静默正常退出：rc={rc} out={out} err={err[:200]}"
    rc, out, _ = _aot_srcs("bom", ["\ufeff输出(7)\n"])
    assert (rc, out) == (0, ["7"]), "逐源 BOM 未被容忍（与 compile_source 口径脱钩）"


# ========================================= 45b-2 跨文件 use 原生真跑

def test_45b2_cross_file_use_runs_natively_and_matches_three_faces():
    """跨文件 use 的调用必须在原生 exe 里真跑出正确读数，且三面同判。

    只锁「编译通过」不够——`use` 在编译面被忽略（符号本就落全局），若全局
    解析只覆盖首源，调用点会编成指向空槽而运行时才崩。
    """
    rc, out, err = _aot_srcs("link", [_LINK_A, _LINK_B])
    assert rc == 0, f"链接映像退出码 {rc}，stderr={err[:200]}"
    assert out == ["304"], f"跨文件调用读数错：{out}"
    assert out == [str(x) for x in interpret(_LINK_A + _LINK_B)[0]], "hi 面不同判"
    assert out == [str(v) for v in run_module(compile_sources([_LINK_A, _LINK_B]))], \
        "vm 面不同判"


def test_45b2_linkage_not_success_is_what_makes_it_run():
    """反证：单独编乙必须运行期诚实失败——收益来自链接，不是偶然的全局注入。

    若 b-only 也能跑出 304，说明「多模块链接」其实一直在把别源符号偷偷带进
    去，那条「链接」锁就是自证的假象。
    """
    rc, out, err = _aot("link_b_only", _LINK_B)
    assert rc != 0, f"未链接却跑通了（链接面在说谎）：out={out}"
    assert out == [], f"失败前不应有部分读数：{out}"
    assert "未定义变量" in err, f"失败文案未如实指名缺符号：{err[:200]}"


def test_45b2_symbol_resolution_is_order_independent():
    """符号解析与源序无关，顶层执行序才与源序有关。

    乙写在甲之前仍应得 304：链接单元是一个模块 + 一份顶层代码序，全局名解析
    一遍完成，不存在「前向引用要先声明」。
    """
    rc, out, err = _aot_srcs("link_rev", [_LINK_B, _LINK_A])
    assert rc == 0, f"反序链接退出码 {rc}，stderr={err[:200]}"
    assert out == ["304"], f"反序链接读数错：{out}"


@pytest.mark.parametrize("shape", ["plain", "module_use", "max_arity"])
def test_45b2_single_source_path_is_byte_unchanged(shape):
    """零扰动主锁：单源经多源入口与经旧入口逐字节同判。

    `compile_sources_to_exe([s]) == compile_to_exe(s)` 若破了，说明 45b 改的
    不是「多了个入口」而是重写了单源路径——那会牵动全部既有原生锁档。
    """
    src = (_LINK_A if shape == "module_use" else
           _LINK_B if shape == "plain" else
           _arity_src(MAX_NATIVE_ARITY))
    single = compile_to_exe(src)
    linked = compile_sources_to_exe([src])
    assert single == linked, f"{shape}：单源走多源入口后产物字节变了"


# ================================================= 45b-3 统一执行门面

def test_45b3_facade_exposes_compile_modules_on_the_same_pipeline():
    """门面 `compile_modules` 与 `compile_module` 同管线（插件接线 + 编译后钩子）。

    只查 `__all__` 与签名不够——真正的口径是「列表入参走 compile_sources，
    字符串入参走 compile_source」，两条都要在门面里汇合，否则 CLI 与库面分裂。
    """
    assert "compile_modules" in exec_api.__all__, "门面未导出多源入口"
    assert "compile_sources_to_exe" in dir(native), "原生侧未导出多源发射入口"
    f1, f2 = "输出(1)\n", "输出(2)\n"
    assert (list(exec_api.compile_modules([f1, f2]).main_code)
            == list(exec_api.compile_module(f1 + f2).main_code))


def test_45b3_build_exe_accepts_str_and_list_without_diverging():
    """`build_exe`  widened：给字符串走原路，给列表走链接，二者各与库面同判。

    这是 `src/mbc/cli.py` 的 `native` 子命令仍能工作的依据（它传字符串）。
    """
    tmp = Path(tempfile.gettempdir())
    s = "输出(1 + 2)\n"
    a = exec_api.build_exe(s, tmp / "p45_facade_str.exe")
    b = exec_api.build_exe([s], tmp / "p45_facade_list.exe")
    assert a.read_bytes() == b.read_bytes() == compile_to_exe(s)
    c = exec_api.build_exe([_LINK_A, _LINK_B], tmp / "p45_facade_two.exe")
    assert c.read_bytes() == compile_sources_to_exe([_LINK_A, _LINK_B])
    rc, out, err = _run(str(c))
    assert (rc, out) == (0, ["304"]), f"门面产物跑不通：rc={rc} out={out} {err[:200]}"


def test_45b3_native_main_takes_multiple_sources(tmp_path):
    """`python -m src.mbc.native` 入口同样多源，且只写一份产物。"""
    a = tmp_path / "m_a.matha"
    b = tmp_path / "m_b.matha"
    a.write_text(_LINK_A, encoding="utf-8")
    b.write_text(_LINK_B, encoding="utf-8")
    out = tmp_path / "two.exe"
    rc = native.main([str(a), str(b), "-o", str(out)])
    assert rc == 0
    assert out.is_file() and out.read_bytes()[:2] == b"MZ"
    assert not (tmp_path / "m_b.exe").exists(), "多源只应产出一份 exe"


# ==================================================== 45b-4 产品 CLI

def test_45b4_cli_native_build_links_multiple_sources_into_one_exe(tmp_path):
    """产品入口 `matha 原生构建 a.matha b.matha -o out.exe` 端到端。"""
    a = tmp_path / "cli_a.matha"
    b = tmp_path / "cli_b.matha"
    a.write_text(_LINK_A, encoding="utf-8")
    b.write_text(_LINK_B, encoding="utf-8")
    exe = tmp_path / "cli.exe"
    r = _cli("原生构建", str(a), str(b), "-o", str(exe))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, txt
    assert "原生构建成功" in txt and "无导入表" in txt, txt
    assert f"{a} + {b}" in txt, f"成功行未列出全部源：{txt}"
    assert exe.read_bytes() == compile_sources_to_exe([_LINK_A, _LINK_B]), \
        "CLI 与库面产物不同判（多源路径有额外不确定性）"
    rc, out, err = _run(str(exe))
    assert (rc, out) == (0, ["304"]), f"CLI 产物跑不通：rc={rc} out={out} {err[:200]}"
    assert not (tmp_path / "cli_b.exe").exists(), "次源不得各自产出 exe"


def test_45b4_cli_default_output_comes_from_first_source(tmp_path):
    """不给 -o 时取**首源**名换 .exe（多源下若无此口径则产物落点不可预期）。"""
    a = tmp_path / "dflt_a.matha"
    b = tmp_path / "dflt_b.matha"
    a.write_text(_LINK_A, encoding="utf-8")
    b.write_text(_LINK_B, encoding="utf-8")
    r = _cli("原生构建", str(a), str(b))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, txt
    assert a.with_suffix(".exe").is_file(), f"默认落点不是首源：{txt}"
    assert not b.with_suffix(".exe").exists()


def test_45b4_cli_second_source_unreadable_leaves_no_artifact(tmp_path):
    """次源不可读 → rc 2 且不留任何产物：读取全部源先于发射。

    若边读边编，首源已成功构建、次源才失败——用户拿到一份缺模块的 exe，
    那是假成功的新形态。
    """
    a = tmp_path / "ok_a.matha"
    a.write_text(_LINK_A, encoding="utf-8")
    exe = tmp_path / "should_not_exist.exe"
    r = _cli("原生构建", str(a), str(tmp_path / "nope.matha"), "-o", str(exe))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 2, txt
    assert "原生构建失败" in txt and "源不可读" in txt, txt
    assert not exe.exists() and not a.with_suffix(".exe").exists(), \
        "源读取失败却留下了产物"


def test_45b4_single_source_cli_line_is_unchanged(tmp_path):
    """单源 CLI 文案零扰动：一源时不出现 ' + ' 连接符。"""
    a = tmp_path / "solo.matha"
    a.write_text("输出(6 * 7)\n", encoding="utf-8")
    exe = tmp_path / "solo.exe"
    r = _cli("原生构建", str(a), "-o", str(exe))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, txt
    assert f"原生构建成功: {a} → {exe}" in txt, txt
    assert " + " not in txt, f"单源文案掺了多源连接符：{txt}"
    assert exe.read_bytes() == compile_to_exe("输出(6 * 7)\n")


# ==================================================== 45b-5 接线文案

def test_45b5_usage_and_argparse_advertise_multi_source():
    """声称与行为同源：usage 行与 argparse 都写「多源即一次链接」。

    只改实现不改文案，用户仍按「一个文件一条命令」去拼两次构建，就会得到
    两份互不相见的产物——那正是本切片要消灭的形状。
    """
    assert 'p_nat.add_argument("source", nargs="+"' in MAIN_SRC, \
        "原生构建 的源参数未放开到多源"
    assert "file [file...]" in MAIN_SRC and "多源即一次链接" in MAIN_SRC, \
        "usage 行未声称多源链接"
    seg = MAIN_SRC[MAIN_SRC.index("def _cmd_native_build("):
                   MAIN_SRC.index("def _cmd_native_build(") + 4000]
    assert "build_exe(texts, out)" in seg, "命令位未把源列表交给门面"
    nat_seg = NATIVE_SRC[NATIVE_SRC.index("def main(argv"):]
    assert 'parser.add_argument("source", nargs="+"' in nat_seg, \
        "src.mbc.native 的 CLI 未放开到多源"


# =========================================== 45c-1 静态栈模型（编译面，无 exe）

def _pe_u64(exe: bytes, off: int) -> int:
    return int.from_bytes(exe[off:off + 8], "little")


def test_45c1_effect_table_covers_every_opcode():
    """净增量表必须逐条覆盖 opcodes.py 的全部操作码——漏一条即按「+1 且继续」处理。

    fail-closed 的默认分支对**已知**指令悄悄生效，就是模型与实际 VM 行为脱钩：
    一条只弹不压的指令被当成压，守卫定得过高（浪费深度）；反过来一条只压不弹的
    指令被当成中性，守卫定得过低——深度够却误报溢出。故这里锁「表与操作码集
    合同名」，新增操作码未入表即红。
    """
    import inspect
    import re as _re
    from src.mbc import opcodes
    body = inspect.getsource(native._stack_effect)
    named = set(_re.findall(r"OP\.([A-Z_]+)", body))
    defined = {k for k, v in vars(opcodes).items()
               if k.isupper() and isinstance(v, int)}
    assert defined - named == set(), f"操作码未入净增量表：{sorted(defined - named)}"
    assert named - defined == set(), f"净增量表引用了不存在的操作码：{sorted(named - defined)}"
    assert len(defined) == 36, "操作码集规模变了，递归深度推导需重算"


def test_45c1_peak_of_hand_written_sequences():
    """几条手算序列的峰值逐一对齐「压/弹」直觉，防表内符号写反。

    手算：
    - `[PUSH PUSH BINOP RET]`：压 2 → 弹 2 压 1 → 弹 1 ⇒ 峰 2。
    - `CALL 3`：压函数 + 3 实参 = 4，净 −3 ⇒ 峰 4。
    - `BUILD_DICT 2`：交替压 4 → 弹 4 压 1 ⇒ 峰 4。
    - `STORE_SUBSCRIPT`：压 3 → 弹 3 ⇒ 峰 3。
    - 入参 arity=2 时帧基之上先有 2 槽 ⇒ 峰至少 2。
    """
    P, RET = (OP.PUSH_CONST, 0), (OP.RET,)
    assert native._operand_peak("a", [P, P, (OP.BINOP, 0), RET], 0) == 2
    assert native._operand_peak("b", [(OP.MAKE_CLOSURE, 0), P, P, P,
                                      (OP.CALL, 3), RET], 0) == 4
    assert native._operand_peak("c", [P, P, P, P, (OP.BUILD_DICT, 2), RET], 0) == 4
    assert native._operand_peak("d", [P, P, P, (OP.STORE_SUBSCRIPT,), RET], 0) == 3
    assert native._operand_peak("e", [RET], 2) == 2, "形参槽不计入本帧峰值"
    assert native._operand_peak("f", [], 0) == 0, "空体峰值即帧基"


def test_45c1_branch_join_takes_the_max():
    """分派两路各压各的：峰值取所有可达路径的最大高度，且 JMP 不得连带落点。

    手算（指令下标见代码）：0 压 1 → 1 处 JZ（弹条件）→ 路 A 在 2..4 再压 3 后
    JMP 到 7；路 B 在 6 只压 1 后落到 7。正确峰值 = 3。若把 JMP 也按「目标 +
    顺序后继」处理，7 之前会再走一遍 6，峰值变 4——多算的那一路正是「跳转图
    画错」最常见的形状。
    """
    P = (OP.PUSH_CONST, 0)
    code = [P, (OP.JZ, 6), P, P, P, (OP.JMP, 7), P, (OP.RET,)]
    assert native._operand_peak("j", code, 0) == 3


def test_45c1_effect_table_matches_the_call_convention():
    """净增量表逐条对齐发射器的实际 r12 位移（写反一位守卫就定错）。

    对照 `_emit_call`（弹 argc + 弹函数、压返回值、净 −argc）、`_emit_epilogue`
    （RET 弹返回值、值仍留在栈上给调用点，故 −1 且终止）、`_emit_apply_rt` 无 arity
    假设。JMP 是纯控制流（0），JZ/JNZ 弹条件（−1）。
    """
    assert native._stack_effect((OP.CALL, 3)) == (-3, False)
    assert native._stack_effect((OP.RET,)) == (-1, True)
    assert native._stack_effect((OP.HALT,)) == (0, True)
    assert native._stack_effect((OP.RAISE,)) == (-1, True)
    assert native._stack_effect((OP.RAISE_MATCH,)) == (-1, True)
    assert native._stack_effect((OP.JMP, 5)) == (0, False)
    assert native._stack_effect((OP.JZ, 5)) == (-1, False)
    assert native._stack_effect((OP.BUILD_DICT, 2)) == (-3, False)
    assert native._stack_effect((OP.BUILD_LIST, 4)) == (-3, False)
    assert native._stack_effect((OP.BUILD_TUPLE, 4)) == (-3, False)
    assert native._stack_effect((OP.UNPACK_SEQ, 3)) == (2, False)
    assert native._stack_effect((OP.STORE_SUBSCRIPT,)) == (-3, False)
    assert native._stack_effect((OP.BUILD_SLICE,)) == (-2, False)
    assert native._stack_effect((OP.DUP,)) == (1, False)
    assert native._stack_effect((OP.GET_ATTR, 0)) == (0, False)


def test_45c1_unbalanced_pop_clamps_and_leak_refuses():
    """两条夹住方向：弹到帧基以下按 0 计（只抬峰值不压低），只压不弹的环必须拒绝。

    环不收敛 = 静态峰值无界。放行即产出一枚「跑到一定深度静默改写 .data 相邻
    全局、退出码还是 0」的 exe，比拒绝坏得多。
    """
    assert native._operand_peak("p", [(OP.POP,), (OP.POP,), (OP.POP,), (OP.RET,)], 0) == 0
    with pytest.raises(NativeNotSupported, match="跳转图松弛不收敛"):
        native._operand_peak("leak", [(OP.PUSH_CONST, 0), (OP.JMP, 0)], 0)


def test_45c1_capacity_refusals_name_the_frame_that_does_not_fit(monkeypatch):
    """装不下的两种形状各自拒绝并指名是谁装不下：函数帧 / 模块顶层。

    真语料要造一个 13 万槽的帧得写几 MB 源，这里把容量临时压到 40 槽走同一条
    判断（`_operand_peak` 读模块全局，口径不变）——锁的是「拒绝存在且指名」，
    不是某个具体数字。顶层样本用 10 层嵌套调用（峰值 12）而非列表字面量：后者
    被常量折叠成一次压栈，测不到峰值。
    """
    monkeypatch.setattr(native, "VSTACK_SLOTS", 40)
    with pytest.raises(NativeNotSupported, match="函数 big 静态峰值已达"):
        compile_to_exe("func big(a: Int) -> Int = (a) => [a, a, a, a, a, a, a, a, a][0]\n"
                       "输出(big(1))\n")
    nested = ("func id(x: Int) -> Int = (x) => x\n"
              "输出(" + "id(" * 10 + "1" + ")" * 10 + ")\n")
    with pytest.raises(NativeNotSupported, match="模块顶层 静态峰值已达"):
        compile_to_exe(nested)


def test_45c1_stack_constants_are_internally_consistent():
    """常量算术自洽 + 旧口径文字退役。

    1MB 操作数栈 / 8MB 调用栈 / 32 槽运行期余量的比值就是「递归深度上限」的
    推导依据；`CPU_STACK_SLACK` 必须为正，否则守卫触发时 raise_rt 自己先炸栈。
    """
    assert native.VSTACK_SIZE == 0x100000
    assert native.VSTACK_SLOTS * 8 == native.VSTACK_SIZE
    assert native.CPU_STACK_RESERVE == 0x800000
    assert 0 < native.CPU_STACK_SLACK < native.CPU_STACK_RESERVE
    assert native.VSTACK_GUARD_SLOTS == 32
    assert native.VSTACK_SLOTS > 4096, "容量小于 4096 槽时链面 20000 层预算不成立"
    assert "操作数栈固定 64KB（无溢出检查）" not in NATIVE_SRC, \
        "结构性限制段仍声称无溢出检查"
    assert "VSTACK_SIZE = 0x10000\n" not in NATIVE_SRC


def test_45c1_operand_stack_lives_in_bss_and_costs_no_file_bytes():
    """操作数栈落 .bss：虚拟容量 = VSTACK_SIZE，而 exe 文件比它小一个量级。

    旧形在 .data 里写 64KB 真零字节——放大容量等于放大产物。这里锁两头的证据：
    `vstack`/`vstack_end` 两个标签相差正好 VSTACK_SIZE（容量真被登记），且真 exe
    的字节数远小于 VSTACK_SIZE（说明它没有物化成文件数据）。
    """
    mod = compile_source("输出(1)\n")
    labels = native.label_rvas(mod)
    assert labels["vstack_end"] - labels["vstack"] == native.VSTACK_SIZE
    _t, _b, bss_vsize, _d, _dv = native._build_payload(mod)
    assert bss_vsize >= native.VSTACK_SIZE
    assert len(compile_to_exe("输出(1)\n")) < native.VSTACK_SIZE
    assert 'ed.emit(b"\\x00" * VSTACK_SIZE)' not in NATIVE_SRC, \
        "操作数栈仍被物化进 .data（放大容量即放大产物）"
    assert "eb.emit_virtual(VSTACK_SIZE)" in NATIVE_SRC


def test_45c1_guard_code_and_floor_are_real_artifacts():
    """守卫标签真落在 .text，`_start` 真写 stack_floor，PE 头 StackReserve 与常量同源。

    只在源码里「写了守卫」不算收口：标签没进 .text 或 `_start` 少填一行，运行期
    就是「比一个从未赋值的 0」——所有帧都会被判越界，或全都不判。
    """
    mod = compile_source("func f(a: Int) -> Int = (a) => a\n输出(f(1))\n")
    labels = native.label_rvas(mod)
    for k in ("gs_vstack", "gs_cpu", "err_vstack", "err_cpu_stack", "stack_floor"):
        assert k in labels, f"守卫缺标签 {k}（发射路径未贯穿）"
    text = native._build_payload(mod)[0]
    for k in ("gs_vstack", "gs_cpu"):
        assert native.TEXT_RVA <= labels[k] < native.TEXT_RVA + len(text), \
            f"{k} 不在 .text 内，序言跳转目标错位"
    start = NATIVE_SRC[NATIVE_SRC.index('ec.store_rip_from("stack_top", 4)'):]
    assert 'ec.store_rip_from("stack_floor", 0)' in start[:800], \
        "_start 未在置栈顶后写 stack_floor"
    assert 'load_rip_to(0, "stack_top")' in start[:800]
    exe = native.emit_exe(mod)
    lfanew = int.from_bytes(exe[0x3C:0x40], "little")
    assert _pe_u64(exe, lfanew + 0x18 + 72) == native.CPU_STACK_RESERVE, \
        "PE OptionalHeader.SizeOfStackReserve 与守卫用的预留量不同源"


# ================================================ 45c-2 真 exe 行为（原生映像）

_DOWN = ("func down(n: Int) -> Int = (n) =>\n"
         "  (n <= 0) ? 0 : (1 + down(n - 1))\n")
# 60 个局部 → 每帧 ≈512B 调用栈，比操作数栈先耗尽（守卫接住的是第二根）
_FAT = ("func fat(n: Int) -> Int = (n) =>\n"
        + "".join(f"  let v{i} = n + {i} in\n" for i in range(60))
        + "  (n <= 0) ? 0 : (1 + fat(n - 1))\n")


def test_45c2_thin_frame_recursion_returns_the_real_value():
    """2 万层非尾递归在原生面给正确读数——旧形是 4100 层起静默改写内存仍 rc 0。

    读数本身是解析可得的（`down(n)` 恒等于 n），故这里以「闭式解 + MBC vm 面」
    双判；hi 解释器在 2 万层是 Python 递归栈的事（阶段 40 登记不修④同族），
    用 200 层的同形程序做 hi/vm 同判，不拿面间缺陷冒充原生缺陷。
    """
    src = _DOWN + "输出(down(20000))\n"
    rc, out, err = _aot("c2_down20k", src)
    assert rc == 0, f"rc={rc} stderr={err[:200]}"
    assert out == ["20000"], f"2 万层读数错：{out}"
    assert out == _vm(src), f"vm 面不同判：{_vm(src)}"
    small = _DOWN + "输出(down(200))\n"
    assert _hi(small) == _vm(small) == ["200"]
    rc2, out2, _ = _aot("c2_down200", small)
    assert (rc2, out2) == (0, ["200"])


def test_45c2_operand_overflow_is_an_honest_catchable_failure():
    """越界必须是「非零退出 + 指名原生栈溢出」，不得是 rc 0 的垃圾读数。

    9 万层 ≈ 操作数栈（131072 槽 / 每层 2 槽）之外。旧行为：越过 vstack 末端后
    写进 .data 相邻全局，输出被截断成 `4103\\x03\\x00` 之类且退出码 0——下游按
    成功处理。现在 rc=1 + 明确文案，且同一条异常可被 `调用捕获` 接住。
    """
    rc, out, err = _aot("c2_down90k", _DOWN + "输出(down(90000))\n")
    assert rc != 0, f"越界仍被判成功（静默改写内存）：out={out}"
    assert out == [], f"越界前不得留下半截读数：{out}"
    assert "原生栈溢出" in err and "操作数栈耗尽" in err, err[:200]
    assert "0xc00000fd" not in err.lower(), f"炸成真异常码：{err[:200]}"


def test_45c2_fat_frames_hit_the_cpu_stack_guard():
    """胖帧：1.5 万层跑通、3 万层由**调用栈**守卫接住。

    两根守卫的分工证据——薄帧越界报「操作数栈耗尽」，胖帧（每帧 512B）越界报
    「调用栈耗尽」；后者旧形是 0xC00000FD 且缓冲输出全丢（连已算出的行都看不到）。
    """
    rc, out, err = _aot("c2_fat15k", _FAT + "输出(fat(15000))\n")
    assert rc == 0, f"1.5 万层胖帧应跑通：rc={rc} stderr={err[:200]}"
    assert out == ["15000"], f"胖帧读数错：{out}"
    rc2, out2, err2 = _aot("c2_fat30k", _FAT + "输出(fat(30000))\n")
    assert rc2 != 0, f"3 万层胖帧越界却判成功：out={out2}"
    assert "原生栈溢出" in err2 and "调用栈耗尽" in err2, err2[:200]


def test_45c2_guard_raise_is_catchable_and_the_process_survives():
    """`调用捕获` 接住栈溢出后进程继续正常执行——守卫是可恢复异常而非终局崩溃。

    手算：`down(400000)` 越界 → `__异常__` + 溢出文案；随后 `down(20000)` 仍得
    20000（r12/rsp/rbp 由处理器记录还原），`调用捕获(down)([10])` 正常路径得 10。
    """
    src = (_DOWN + "let r = 调用捕获(down)([400000])\n"
           "输出(get(r)(0))\n输出(get(r)(1))\n输出(down(20000))\n"
           "输出(get(调用捕获(down)([10]))(1))\n")
    rc, out, err = _aot("c2_catch", src)
    assert rc == 0, f"rc={rc} stderr={err[:200]}"
    assert out[0] == "__异常__" and "原生栈溢出" in out[1], out
    assert out[2] == "20000", f"接住溢出后正常调用坏了：{out}"
    assert out[3] == "10", f"溢出后正常捕获路径读数错：{out}"


def test_45c1_full_corpus_links_without_refusal():
    """全 .matha 语料过一遍链接期栈预算：零拒绝 + 峰值余量两个量级。

    静态守卫给每帧加了一道「装得下才让编」的门槛——这正是本切片唯一可能把别的
    原生用例挡掉的环节。语料只有 189 个文件、纯分析只要几秒，所以整仓扫而不是
    抽样：漏一个文件就是漏一条「以前能编现在拒绝」的回归。
    """
    files = sorted(p for root in ("matha", "examples", "tests/fixtures")
                   for p in (_ROOT / root).rglob("*.matha"))
    assert len(files) >= 185, f"语料文件数骤减，扫描面不足以作证：{len(files)}"
    worst = 0
    for p in files:
        mod = compile_source(p.read_text(encoding="utf-8"))
        peaks = native._stack_budget(mod)          # 拒绝即红（NativeNotSupported 不被吞）
        worst = max(worst, max(peaks.values(), default=0),
                    native._operand_peak("模块顶层", mod.main_code, 0))
    assert worst < native.VSTACK_SLOTS // 32, \
        f"最胖帧峰值 {worst} 槽已逼近容量 {native.VSTACK_SLOTS}，深度预算需重算"


def test_45c2_boot_corpus_links_without_refusal():
    """全 boot 链 + 词法/语法片在链接期零拒绝，且最胖单帧远小于容量。

    静态守卫的前提是「每帧装得下」。这条锁的是收益不被本切片自己吃掉：若某个
    工具链函数的单帧峰值涨到与容量同量级，原生面会在链接期就拒绝整条链——
    那比运行期溢出更早地堵死 45d。
    """
    from src.matha_chain import BOOT_FILES
    comp = _compile(list(BOOT_FILES))
    peaks = native._stack_budget(comp.mod)
    assert len(peaks) > 200, "boot 链函数数异常，链接期分析未覆盖全链"
    assert max(peaks.values()) < 4096, \
        f"最胖单帧峰值 {max(peaks.values())} 槽，递归深度预算需重算"
    lex = native._stack_budget(_compile(["matha/lexer.matha"]).mod)
    assert max(lex.values()) < 4096


# ============================================================ 45d 工具链承载

_LEXER_TXT = (_ROOT / "matha" / "lexer.matha").read_text(encoding="utf-8")
_STDLIB_TXT = (_ROOT / "matha" / "stdlib.matha").read_text(encoding="utf-8")
_PARSER_TXT = (_ROOT / "matha" / "parser.matha").read_text(encoding="utf-8")

_EXE_CACHE: dict[str, str] = {}


def _chain_exe(tag: str, sources: list[str]) -> str:
    """工具链映像一次构建、多锁复用（1.7 MB 映像逐锁重编不值这些秒数）。"""
    if tag not in _EXE_CACHE:
        p = os.path.join(tempfile.gettempdir(), f"p45_{tag}.exe")
        Path(p).write_bytes(native.emit_exe(compile_sources(sources)))
        _EXE_CACHE[tag] = p
    return _EXE_CACHE[tag]


def _chain_out(tag: str, sources: list[str]) -> list[str]:
    rc, out, err = _run(_chain_exe(tag, sources))
    assert rc == 0, f"原生映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    return [l for l in out if l != ""]


# ------------------------------------------ 45d-0 原生序比较：内容而非地址序

# 45a/45b 之后，原生面跑 Matha 工具链的第一个非载体阻塞不是指令集而是**语义**：
# BINOP 的 `< <= > >=` 曾在任一侧为指针时直接 `cmp` 地址。`.data` 里字面量按源序
# 摆放，于是 `输出("b" > "a")` 给出假——凡依赖字符串序的 Matha 代码（stdlib 的
# int/float 进制前缀判定、词法分支）在原生面都会静默走错路，而不是报错。
# 现改走运行期助手 `val_cmp`：裸整数按值、布尔按真值（且只与整数/布尔比序）、
# 字符串按 UTF-8 字节（`repe cmpsb` 后比首个不等字节，等则比长度）、列表/元组逐
# 元素递归后比长度；其余类型组合与混合两侧一律 `raise_rt` 诚实拒绝。
_ORDER_CASES = [
    ('"a" < "b"', "True"),
    ('"b" > "a"', "True"),
    ('"abc" >= "ab"', "True"),
    ('"ab" <= "ab"', "True"),
    ('"" < "a"', "True"),
    ('"中" < "文"', "True"),
    ('"z" < "aa"', "False"),
    ("[1, 2] < [1, 3]", "True"),
    ("[1, 2] < [1, 2, 3]", "True"),
    ("[2] > [1, 9]", "True"),
    ("[1, 2] <= [1, 2]", "True"),
    ('("a", 1) < ("b", 1)', "True"),
    ("(1, 2) < (1, 2, 0)", "True"),
    ("假 < 真", "True"),
    ("真 > 假", "True"),
    ("真 >= 真", "True"),
    ("假 < 1", "True"),
    ("1 > 假", "True"),
    ("-5 < 3", "True"),
    ("-5 > -3", "False"),
    ("2.5 > 2", "True"),
    ("-2.5 < -2.0", "True"),
    ("99999999999999999999999 < 100000000000000000000000", "True"),
    ("100000000000000000000000 > 99999999999999999999999", "True"),
]
_ORDER_SRC = "".join(f"输出({e})\n" for e, _ in _ORDER_CASES)


def test_45d0_ordering_matches_the_three_faces_line_for_line():
    """24 条序比较读数在 hi / vm / 原生 exe 三面逐字同判。

    一条汇编错的判定会把整列挪位，所以逐行比对而不是集合比对。
    """
    want = [w for _, w in _ORDER_CASES]
    assert _hi(_ORDER_SRC) == want, f"宿主解释器面漂移：{_hi(_ORDER_SRC)}"
    assert _vm(_ORDER_SRC) == want, f"宿主 VM 面漂移：{_vm(_ORDER_SRC)}"
    rc, out, err = _aot("ord_all", _ORDER_SRC)
    assert rc == 0, f"原生映像非零退出 rc={hex(rc)} stderr={err[:200]}"
    assert out == want, f"原生面序比较漂移：{out}"


def test_45d0_string_verdict_is_not_the_data_address_order():
    """反地址序探测器：字面量在 .data 里的摆放次序与字典序**相反**。

    旧发射器比的是地址，故这五条里至少 `("b","a")` 一族必然给反。把它单独立一
    条，是为了让回归的失败信息直接指向根因，而不是淹没在 24 行逐字比对里。
    """
    src = ('输出("b" > "a")\n输出("z" > "a")\n输出("zy" > "ab")\n'
           '输出("b" < "a")\n输出("ab" > "abc")\n')
    want = ["True", "True", "True", "False", "False"]
    assert _vm(src) == _hi(src) == want, "宿主两面已漂移"
    rc, out, err = _aot("ord_addr", src)
    assert rc == 0, f"rc={hex(rc)} {err[:200]}"
    assert out == want, f"原生面又按地址序给判了：{out}"


def test_45d0_negative_result_keeps_its_sign_width():
    """`val_cmp` 的 -1 必须走 REX.W 立即数形（符号扩展）。

    `mov eax,-1` 是零扩展 → +4294967295，而调用点按 `cmp rax,0` 定序，判定全反；
    行为面由 `-5 < 3` 与 `"a" < "b"` 接住，这里锁的是编码本身。
    """
    assert 'em.emit(b"\\x48\\xC7\\xC0\\xFF\\xFF\\xFF\\xFF")' in NATIVE_SRC, \
        "val_cmp 的 -1 不再是 REX.W 符号扩展形"
    assert 'em.emit(b"\\xB8\\xFF\\xFF\\xFF\\xFF")' not in NATIVE_SRC, \
        "又出现了把 -1 零扩展成 +4294967295 的 32 位形"


def test_45d0_ordering_branches_route_through_the_runtime_helper():
    """结构锁：BINOP 序分支在任一侧为堆指针时改调 `val_cmp`，且助手真在 .text 里。

    只看行为不足以挡住「序分支退回裸 cmp 而恰好读数对」——把接线本身钉住。
    """
    assert 'em.call_rel32("val_cmp")' in NATIVE_SRC
    assert 'em.label_here("val_cmp")' in NATIVE_SRC
    site = NATIVE_SRC.split('lobj = f"bo_or_obj_', 1)
    assert len(site) == 2, "BINOP 的指针分流分支锚点丢了（接线位置需重指）"
    body = site[1].split("elif sym ==", 1)[0]
    assert 'em.call_rel32("val_cmp")' in body, "序分支已不再走助手"
    assert 'em.emit(b"\\x31\\xC9")' in body, "调用点不再把助手结论与 0 比序"


# 混合类型 / 不同族容器 / null 的序比较：宿主两面各自抛错（文案是 Python 的
# `'<' not supported between instances of …`），原生面抛自己的文案。三面都拒绝
# 即诚实，文案分歧登记不修（40-③/41-③ 同族）。
_MIXED_ORDER = [
    ('1 < "a"', "'int' and 'str'"),
    ('"a" > 1', "'str' and 'int'"),
    ('[1] < "a"', "'list' and 'str'"),
    ("null < 1", "'NoneType' and 'int'"),
    ('真 < "a"', "'bool' and 'str'"),
    ('("a", 1) < [1, "a"]', "'tuple' and 'list'"),
]


def test_45d0_mixed_type_ordering_is_rejected_by_every_face():
    """越界类型组合不静默给判：宿主两面抛错、原生面非零退出 + 先前输出保住。

    `("a", 1) < [1, "a"]` 走的是「两侧同为容器但标签不同族」的拒绝位，
    `null < 1` 走的是「裸整数 vs 非布尔对象」那条独立拒绝臂——两臂都锁到。
    """
    for i, (expr, host_hint) in enumerate(_MIXED_ORDER):
        src = f'输出("before")\n输出({expr})\n'
        for face, fn in (("hi", _hi), ("vm", _vm)):
            with pytest.raises(Exception) as ei:
                fn(src)
            assert host_hint in str(ei.value), f"{face} 面 {expr}：{ei.value}"
        rc, out, err = _aot(f"ord_mix{i}", src)
        assert rc != 0, f"原生面对 {expr} 竟给了读数：{out}"
        assert out == ["before"], f"{expr} 崩溃前输出没保住：{out}"
        assert err.strip() == "序比较不适用于该类型组合", err[:200]


def test_45d0_chained_comparison_short_circuits_before_the_bad_arm():
    """`a > b < c` 脱糖成 `and`：短路让坏臂根本不求值，三面同给 False 而不是报错。

    这条锁的是拒绝的**边界**——`val_cmp` 抛的是它那一臂，不吞掉既有的短路语义。若
    发射器把 `and` 改成两侧都求值，这里会立刻变成非零退出。
    """
    src = '输出(1 > 真 < "a")\n输出(1 < 真 < "a")\n'
    assert _hi(src) == _vm(src) == ["False", "False"], "宿主两面已漂移"
    rc, out, err = _aot("ord_chain", src)
    assert rc == 0, f"短路被拒绝吞掉了：rc={hex(rc)} {err[:200]}"
    assert out == ["False", "False"], out


def test_45d0_rejection_wording_shares_one_source_with_the_emitter():
    """原生拒绝文案与发射器错误表同源（改表不改行为即红）。"""
    assert '("err_cmp_type", "序比较不适用于该类型组合")' in NATIVE_SRC
    body = NATIVE_SRC.split('em.label_here("vc_raise")', 1)[1]
    assert 'em.lea_rip(0, "err_cmp_type")' in body[:200], "拒绝位不再引用该标签"


# ------------------------------------------ 45d-0b 尾位置一元负的返回寄存器

# `func f(x) -> Int = (x) => -x` 的字节码尾是 `UNARYOP; RET`，而 `OP.RET` 只发序言
# 尾，返回值取 rax。neg 的整数臂原先只 `neg qword [r12-8]`（栈槽是对的），rax 里
# 留着 `is_bigint` 的 0/1 判定值 → 返回位露馅：`输出(-x)` 对、`f(-x)` 给 0。
_TAIL_NEG = [
    ("int", 'func f(x: Int) -> Int = (x) => -x\n输出(f(5))\n输出(f(-5))\n',
     ["-5", "5"]),
    ("float", 'func f(x: Float) -> Float = (x) => -x\n输出(f(2.5))\n', ["-2.5"]),
    ("bigint", 'func f(x: Int) -> Int = (x) => -x\n'
     '输出(f(99999999999999999999999))\n', ["-99999999999999999999999"]),
    ("twice", 'func f(x: Int) -> Int = (x) => -(-x)\n输出(f(7))\n', ["7"]),
    ("in_order", 'func f(x: Int) -> Int = (x) => -x\n输出(f(-5) < 3)\n', ["False"]),
]


@pytest.mark.parametrize("tag,src,want", _TAIL_NEG, ids=[c[0] for c in _TAIL_NEG])
def test_45d0b_tail_position_unary_neg_returns_a_value(tag, src, want):
    """尾位置一元负的三面同判——只有返回位露馅的缺陷才会在这里显形。"""
    assert _hi(src) == _vm(src) == want, f"{tag} 宿主两面漂移"
    rc, out, err = _aot(f"neg_{tag}", src)
    assert rc == 0, f"{tag} rc={hex(rc)} {err[:200]}"
    assert out == want, f"{tag} 原生面返回位读数：{out}"


def test_45d0b_neg_int_arm_reads_the_slot_back_into_rax():
    """结构锁：整数取反后必须回读栈顶，否则 RET 拿到的是判定值。"""
    tail = NATIVE_SRC.split("neg qword [r12-8]", 1)[1][:400]
    assert "em.read_top_to(0)" in tail, f"整数取反臂没把结果送回 rax：{tail[:120]}"


# -------------------------------- 45d-0c 收益判据：stdlib 数值解析进原生映像

# stdlib 的 `int` 逐位判数字靠 `c >= "0" and c <= "9"`，`float` 判指数符号/小数位
# 同族——这些全是 45d-0 之前「按地址序必错」的形状（stdlib 的 int 不认 0x/0b 前缀，
# 进制解析属词法器职责，故这里不放进制样本）。这条锁的是「修完原语就能用」，
# 而不是只修原语。
_STD_DRV = ('输出(int("-42"))\n'
            '输出(int("309"))\n'
            '输出(int(strip(" 7 ")))\n'
            '输出(float("1.5e3"))\n'
            '输出(float("-0.25"))\n'
            '输出(int("-42") < int("-7"))\n')


def test_45d0c_stdlib_number_parsing_runs_inside_a_native_exe():
    """标准库片单独链进原生映像后，int/float 的读数与宿主 VM 面逐字同判。"""
    srcs = [_STDLIB_TXT, _STD_DRV]
    nat = _chain_out("45d_std", srcs)
    want = ["-42", "309", "7", "1500.0", "-0.25", "True"]
    assert nat == want, f"原生面 stdlib 读数：{nat}"
    assert _vm(_merged(*srcs)) == want, "宿主 VM 面已漂移"


# ---------------------------------------------------- 45d-1 帧内解构 rbp 回归

# 「函数帧里解构」是原生发射器唯一会写 rbp 相对槽的路径之一：`_emit_unpack_seq`
# 曾把 `mov rax,r13` 编成 `4C 89 C5`——那是 `mov rbp,r8`（89 /r 的 dst 在 rm 域、
# src 在 reg 域，REX 位序是 W|R|X|B），帧指针当场被毁，紧随的第一条 STORE_LOCAL
# 通过垃圾 rbp 写内存 → 0xc0000005。顶层解构走 STORE_GLOBAL 不碰 rbp，所以只有
# 帧内解构（正是词法器 `let (t, txt) = 检测多符(src, pos) in …` 的形状）会崩。
_UNPACK_CASES = [
    ("tuple_in_frame",
     'func f() -> Int = () => let (t, x) = (7, "y") in t\n输出(f())\n', "7"),
    ("list_in_frame",
     "func f() -> Int = () => let (a, b) = [1, 2] in a + b\n输出(f())\n", "3"),
    ("three_names_in_frame",
     'func f() -> Int = () => let (a, b, c) = (1, 2, 3) in a * 100 + b * 10 + c\n'
     '输出(f())\n', "123"),
    ("call_tuple_in_frame",
     'func g(s: String, i: Int) -> (Int, String) = (s, i) => (9, "tail")\n'
     'func f() -> Int = () => let (t, txt) = g("abc", 0) in t + 1\n输出(f())\n', "10"),
    ("unpack_with_param",
     'func f(n: Int) -> Int = (n) => let (a, b) = (n, n + 1) in a * b\n输出(f(3))\n',
     "12"),
    ("unpack_in_loop_body",
     'func f() -> Int = () => {\n  let s = 0\n  for (a, b) in [[1, 2], [3, 4]] {\n'
     '    s = s + a * b\n  }\n  s\n}\n输出(f())\n', "14"),
    ("tuple_top_level", 'let (a, b) = (3, 4)\n输出(a + b)\n', "7"),
    ("list_top_level", "let (a, b) = [5, 6]\n输出(a * b)\n", "30"),
]


@pytest.mark.parametrize("tag,src,want", _UNPACK_CASES,
                         ids=[c[0] for c in _UNPACK_CASES])
def test_45d1_unpack_matches_three_faces(tag, src, want):
    """帧内/顶层解构三面（hi / vm / 原生 exe）逐字同判，读数即手算值。"""
    assert _hi(src) == _vm(src) == [want], f"{tag} 宿主两面已漂移"
    rc, out, err = _aot(f"unpk_{tag}", src)
    assert rc == 0, f"{tag} 原生面 rc={hex(rc)} stderr={err[:200]}"
    assert out == [want], f"{tag} 原生面读数：{out}"


def test_45d1_locals_allocated_after_unpack_keep_the_frame_pointer():
    """解构之后再开局部槽仍指得到真帧（rbp 未被覆写的直接判据）。

    单看解构结果可能只经过 `LOAD_LOCAL` 前几个槽；这里在解构后续开 c/d/e 三个
    槽并回读，任何一次 rbp 漂移都会把读数换成垃圾或直接崩。
    """
    src = ('func f(p: Int) -> Int = (p) => {\n'
           '  let (a, b) = (p, p + 1)\n'
           '  let c = a * 10\n'
           '  let d = b * 100\n'
           '  let e = c + d\n'
           '  e + 1\n}\n输出(f(2))\n')
    assert _vm(src) == _hi(src) == ["321"]
    rc, out, err = _aot("unpk_more_locals", src)
    assert (rc, out) == (0, ["321"]), f"{out} {err[:200]}"


def test_45d1_unpack_failure_is_catchable_and_the_frame_survives():
    """解构失败在帧内是**可捕获**的诚实读数，不是进程死亡。

    `调用捕获(f)([])` 是柯里化两位（`(fn)(args)`）——只给一位得到的是偏函数，
    那是调用方的 arity 误用而非载体缺陷，故这里按正形调用。三面逐字同判。
    """
    src = ('func f1() -> Int = () => let (a, b) = [1, 2, 3] in a\n'
           'func f2() -> Int = () => let (a, b) = 7 in a\n'
           'func ok() -> Int = () => let (a, b) = [1, 2] in a + b\n'
           '输出(调用捕获(f1)([]))\n输出(调用捕获(f2)([]))\n'
           '输出(调用捕获(ok)([]))\n输出("活著")\n')
    want = ["['__异常__', '解构失败：期望 2 个元素，实际 list']",
            "['__异常__', '解构失败：期望 2 个元素，实际 int']",
            "['__正常__', 3]", "活著"]
    assert _vm(src) == want, f"vm 面读数漂移：{_vm(src)}"
    assert _hi(src) == want, f"hi 面读数漂移：{_hi(src)}"
    rc, out, err = _aot("unpk_catch", src)
    assert rc == 0, f"接住异常后进程仍死了：rc={hex(rc)} {err[:200]}"
    assert out == want, f"原生面捕获读数：{out}"


def test_45d1_uncatchable_unpack_keeps_prior_output_and_names_the_shape():
    """未接住时诚实终止：先前输出保得住、stderr 给的是同一句消息体。

    异常**载体类名**分歧（宿主 `MathaRuntimeError:` 前缀 vs 原生裸消息）承继
    40-③/41-③ 同族登记，本锁只锁消息体逐字一致——那才是判定面关心的内容。
    """
    src = ('输出("before")\n'
           'func f1() -> Int = () => let (a, b) = [1, 2, 3] in a\n'
           '输出(f1())\n输出("after")\n')
    rc, out, err = _aot("unpk_die", src)
    assert rc != 0, f"解构失败竟成功了：{out}"
    assert out == ["before"], f"崩溃前的输出没保住：{out}"
    assert err.strip() == "解构失败：期望 2 个元素，实际 list", err[:200]


# ------------------------------------------------------ 45d-2 编码位防再犯

def test_45d2_mov_rr_places_destination_in_the_rm_field():
    """`mov_rr(dst, src)` 的位序锁：89 /r 的 dst 在 rm、src 在 reg，REX=W|R|X|B。

    本次缺陷就是 13(r13) 与 0(rax) 写反后手拼出的 `4C 89 C5`。把 rbp(5) 与
    r13(13) 这几对最容易混的编码钉成表，改位序或改 REX 计算都会立刻显形。
    """
    class _E:
        def __init__(self):
            self.buf = bytearray()

        def emit(self, b):
            self.buf += b

    def enc(dst, src):
        e = _E()
        native._Emitter.mov_rr(e, dst, src)
        return bytes(e.buf)

    assert enc(0, 13) == b"\x4C\x89\xE8", "mov rax,r13"
    assert enc(13, 0) == b"\x49\x89\xC5", "mov r13,rax"
    assert enc(5, 0) == b"\x48\x89\xC5", "mov rbp,rax"
    assert enc(0, 5) == b"\x48\x89\xE8", "mov rax,rbp"
    assert enc(0, 8) == b"\x4C\x89\xC0", "mov rax,r8"


def test_45d2_unpack_head_does_not_target_the_frame_pointer():
    """解构头不再有任何写 rbp 的编码，且真值来源是 `mov_rr` 而非手拼字节。

    锁两层：源码里 `4C 89 C5` 这个模式（mov rbp,r8）整体绝迹；`_emit_unpack_seq`
    函数体内出现 `em.mov_rr(0, 13)`。手拼一次就有一次写反的机会。
    """
    assert 'b"\\x4C\\x89\\xC5"' not in NATIVE_SRC, \
        "原生发射器又出现了 mov rbp,r8 的手拼编码"
    body = native._emit_unpack_seq.__doc__ or ""
    src = NATIVE_SRC.split("def _emit_unpack_seq(", 1)[1].split("\ndef ", 1)[0]
    assert "em.mov_rr(0, 13)" in src, f"解构头的 r13 取回不再是 mov_rr 真形：{src[:120]}"
    assert "em.emit(b\"\\x4C\\x89" not in src
    assert body  # 文档串在（口径注的载体）


# ------------------------------------------ 45d-3/4 Matha 工具链片的原生承载

# 不含内嵌换行的输入：换行 token 的「文本」就是 \n，按行切分会把一行劈成两行，
# 那是取证口径的假差异而不是执行面的差异。
_LEX_INPUTS = ["42 + 1", "x", "+ - * /", "( ) [ ] { }", "func if while",
               "=> -> != <= >= << >>", "真 假 true false", "1 << 3",
               "0b1010 0t11 0xFF", "a?.b", "你好 x", "a…b", "1.5e3",
               "func 加一(x: Int) -> Int = (x) => x + 1"]

# 语法器对这 9 条给出可逐字比对的 AST。另 5 条落「期望表达式/期望 (」——那是
# 语料本身的形状，不是执行面分歧，故进 45d-4b 的诚实失败锁而非同判锁。
_AST_INPUTS = ["42 + 1", "x", "真 假 true false", "1 << 3",
               "0b1010 0t11 0xFF", "a?.b", "你好 x", "1.5e3",
               "func 加一(x: Int) -> Int = (x) => x + 1"]
_REJECT_INPUTS = ["+ - * /", "( ) [ ] { }", "func if while",
                  "=> -> != <= >= << >>", "a…b"]


def _lit_list(items: list[str]) -> str:
    return "[" + ", ".join(f'"{s}"' for s in items) + "]"


_LEX_DRV = (
    f"let 输入们 = {_lit_list(_LEX_INPUTS)}\n"
    "for s in 输入们 {\n"
    "  let 记 = 词法器.扫描(s)(0)(1)(1)([])\n"
    '  输出("[" + s + "] n=" + str(len(记)))\n'
    "  for t in 记 {\n"
    '    输出(str(t.类型) + "|" + str(t.文本) + "|" + str(t.行) + "|" + str(t.列))\n'
    "  }\n}\n")

_AST_DRV = (
    f"let 输入们 = {_lit_list(_AST_INPUTS)}\n"
    "for s in 输入们 {\n"
    "  let ast = 语法器.parse(词法器.扫描(s)(0)(1)(1)([]))\n"
    '  输出("[" + s + "] " + str(ast.类型) + "/" + str(len(ast.声明)))\n'
    "  for d in ast.声明 {\n"
    '    输出(str(d.类型) + "/" + str(d.名) + "/" + str(d.运算符))\n'
    "  }\n}\n")

# 逐条包在 调用捕获 里：不可解析输入必须作为**可捕获的诚实异常**回来（三面同一句
# 消息体），而不是让映像崩掉——崩了就分不清「语法器拒绝」与「原生面缺陷」。
_REJ_DRV = (
    f"let 输入们 = {_lit_list(_REJECT_INPUTS)}\n"
    "for s in 输入们 {\n"
    "  let r = 调用捕获(() => 语法器.parse(词法器.扫描(s)(0)(1)(1)([])))([])\n"
    '  输出("[" + s + "] " + str(r))\n}\n')

# 语法器片的链接集（词法器 + 标准库 + 语法器）——45b 的多模块链接在此只被用来
# 一次装三个 .matha，产物仍是一份 exe。
_PARSER_CHAIN = [_LEXER_TXT, _STDLIB_TXT, _PARSER_TXT]


def _merged(*parts: str) -> str:
    return "\n".join(parts)


def _chain三面(tag: str, sources: list[str], merged_src: str) -> list[str]:
    nat = _chain_out(tag, sources)
    assert _vm(merged_src) == nat, (
        f"{tag} 宿主 VM 面与原生映像不同判：vm={_vm(merged_src)[:4]} nat={nat[:4]}")
    assert _hi(merged_src) == nat, (
        f"{tag} 宿主解释器面与原生映像不同判：hi={_hi(merged_src)[:4]} nat={nat[:4]}")
    return nat


def test_45d3_matha_lexer_runs_inside_a_native_exe_and_matches_the_host():
    """Matha 写的词法器编进真 PE64 后，token 流与宿主两面逐字同判。

    这是 45a 抬上限 + 45b 链接 + 45c 栈守卫 + 45d 帧内解构四片收益的合取判据：
    被执行的「词法器」是 Matha 源本身（471 行、47 个函数、含 9 参柯里化入口），
    运行期没有 Python 词法器参与——宿主两面只是判据，不是产物的一部分。
    """
    nat = _chain三面("45d_lex", [_LEXER_TXT, _LEX_DRV], _merged(_LEXER_TXT, _LEX_DRV))
    assert len(nat) == 88, f"token 流行数变了（14 头行 + 74 记号行）：{len(nat)}"
    assert nat[0] == "[42 + 1] n=4", nat[:3]


def test_45d3_lexer_exe_actually_walks_the_in_frame_unpack_paths():
    """正向锁的「可达性」半边：token 流里确有只经帧内解构才产得出来的记号。

    没有这条，`test_45d3` 即便被改成一个从不解构的驱动也照样绿——收益就假了。
    双字符运算符（`>=`/`=>`/`<<`/`>>`/`?.`）全部出自 `检测多符` 的
    `let (t, txt) = …` 帧内解构；三引号/进制前缀同理。
    """
    nat = _chain_out("45d_lex", [_LEXER_TXT, _LEX_DRV])
    got = {l.split("|")[0] for l in nat if "|" in l}
    for must in ("大于等于", "胖箭头", "左移", "右移", "可选链", "箭头", "整数"):
        assert must in got, f"帧内解构路径没被走到，缺记号 {must}：{sorted(got)}"


def test_45d4_matha_parser_runs_inside_a_native_exe_and_matches_the_host():
    """三文件链接（词法器 + 标准库 + 语法器）→ 原生面产 AST 流，三面逐字同判。

    语法器片自带 `#：{…}` 早停块，故整体驱动另起；这条锁证明多模块链接不是
    「能编」而是「编完还能跑对」。
    """
    nat = _chain三面("45d_ast", _PARSER_CHAIN + [_AST_DRV],
                     _merged(*_PARSER_CHAIN, _AST_DRV))
    assert any(l.startswith("[42 + 1] 程序/1") for l in nat), nat[:4]
    assert "二元运算/None/+" in nat, nat[:6]
    assert "函数定义/加一/None" in nat, nat[-6:]
    assert len(nat) == 19, f"9 条可解析输入应产 1 回声 + 9 头 + 9 声明：{len(nat)}"


def test_45d4b_unparseable_input_is_a_catchable_honest_error_not_a_crash():
    """5 条不可解析输入在 `调用捕获` 下三面同给消息体，映像不崩。

    这是「诚实边界」的正形一半：拒绝得越早越像缺陷被接住，而不是被执行体吞掉。
    读数逐字锁死（含 `a…b` 的「未知」token 类型名——词法器对非 ASCII 标点给的
    就是这个词），改文案或改成崩溃都会立刻红。
    """
    want = ["1",
            "[+ - * /] ['__异常__', '期望表达式，实际 +']",
            "[( ) [ ] { }] ['__异常__', '期望表达式，实际 ]']",
            "[func if while] ['__异常__', '期望 (']",
            "[=> -> != <= >= << >>] ['__异常__', '期望表达式，实际 =>']",
            "[a…b] ['__异常__', '期望表达式，实际 未知']"]
    srcs = _PARSER_CHAIN + [_REJ_DRV]
    merged = _merged(*srcs)
    assert _vm(merged) == want, f"vm 面读数漂移：{_vm(merged)}"
    assert _hi(merged) == want, f"hi 面读数漂移：{_hi(merged)}"
    rc, out, err = _run(_chain_exe("45d_ast_rej", srcs))
    assert rc == 0, f"接住语法错误后进程仍死了：rc={hex(rc)} {err[:200]}"
    assert [l for l in out if l != ""] == want, out


def test_45d4_native_parse_failure_reports_the_same_message_body():
    """未接住的语法错误在原生面如实终止：先前输出保住、stderr 是宿主同一句消息体。

    消息体逐字取自 45d-4b 已锁定的宿主读数。原生面无异常类名前缀（同族登记），
    故这里锁的是判定面关心的内容而不是载体外壳。
    """
    drv = ('输出("before")\n'
           'let ast = 语法器.parse(词法器.扫描("+ - * /")(0)(1)(1)([]))\n'
           '输出(ast.类型)\n')
    exe = _chain_exe("45d_ast_die", _PARSER_CHAIN + [drv])
    rc, out, err = _run(exe)
    assert rc != 0, f"不可解析的输入在原生面静默通过：{out}"
    assert out[:2] == ["1", "before"], f"崩溃前的输出没保住：{out}"
    assert err.strip() == "期望表达式，实际 +", err[:200]


# ------------------------------------------------ 45d-5 反向控：仍是纯原生映像

def _pe_facts(blob: bytes) -> dict:
    off = struct.unpack_from("<I", blob, 0x3C)[0]
    nsec = struct.unpack_from("<H", blob, off + 6)[0]
    optsize = struct.unpack_from("<H", blob, off + 20)[0]
    opt = off + 24
    magic = struct.unpack_from("<H", blob, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    imp_rva, imp_size = struct.unpack_from("<II", blob, dd)
    sec = opt + optsize
    return {"sig": blob[off:off + 4] == b"PE\x00\x00",
            "machine": struct.unpack_from("<H", blob, off + 4)[0],
            "opt_magic": magic,
            "sections": [blob[sec + i * 40:sec + i * 40 + 8].rstrip(b"\0").decode()
                         for i in range(nsec)],
            "import_rva": imp_rva, "import_size": imp_size}


@pytest.mark.parametrize("tag,sources", [
    ("45d_lex", [_LEXER_TXT, _LEX_DRV]),
    ("45d_ast", _PARSER_CHAIN + [_AST_DRV]),
], ids=["词法器片", "词法+标准+语法片"])
def test_45d5_toolchain_image_is_still_an_importless_pe64(tag, sources):
    """承载工具链的映像与阶段 44 的小产物同规格：无导入表、三节、纯 PE32+。

    体积上去（0.33 MB → 1.72 MB）不代表偷偷换了装配路径——这条锁断的是那一点。
    """
    blob = Path(_chain_exe(tag, sources)).read_bytes()
    pe = _pe_facts(blob)
    assert pe["sig"] and pe["machine"] == 0x8664 and pe["opt_magic"] == 0x20B, pe
    assert pe["import_rva"] == 0 and pe["import_size"] == 0, \
        f"工具链映像出现导入表（运行期应由 PEB 走表解析 kernel32）：{pe}"
    assert pe["sections"] == [".text", ".bss", ".data"], pe


def test_45d5_toolchain_image_carries_no_python_marker():
    """产物字节里无 python/Cpython 标记——工具链入象后这条仍然成立。"""
    blob = Path(_chain_exe("45d_ast", _PARSER_CHAIN + [_AST_DRV])
                ).read_bytes().lower()
    for marker in (b"python", b"cpython", b"python3", b"site-packages"):
        assert marker not in blob, f"工具链映像里出现宿主标记 {marker!r}"


# ---------------------------------------------- 45d-6 诚实边界：能编 ≠ 已脱宿主

def _latent_reads(mod) -> dict[str, int]:
    """按 native.py LOAD_GLOBAL 的分派序挑出「无定义也无载体」的名字。

    这些名字链接期不报错，运行期才落到 `err_undefined` + `raise_rt`——它们就是
    「原生编译成功」与「运行期零 Python」之间的距离。分派序逐条对齐
    `_declared_globals` / `NATIVE_BUILTINS` / 静态常量 / `_UNRESOLVED_GLOBALS`。
    """
    consts = mod.constants
    user = set(mod.functions)
    carrier = set(native.NATIVE_BUILTINS)
    declared = native._declared_globals(mod)
    fn_names = user | (carrier - user)
    hits: dict[str, int] = {}
    for code in [mod.main_code] + [f.code for f in mod.functions.values()]:
        for ins in code:
            if len(ins) < 2 or ins[0] != OP.LOAD_GLOBAL:
                continue
            name = consts[ins[1]]
            if not isinstance(name, str):
                continue
            if (name == "print" and name not in user and name not in declared
                    and "输出" in fn_names):
                name = "输出"
            if name in fn_names and not (name in declared and name in carrier):
                continue
            if name in declared or name in ("真", "假", "null", "None"):
                continue
            if name in native._UNRESOLVED_GLOBALS:
                continue
            hits[name] = hits.get(name, 0) + 1
    return hits


# boot 全链 22 个宿主注入名：OS 载体（执行命令/输入行/列目录…）、链面工具
# （解析_JSON/执行Matha…）。
# 阶段 45 时点此表含 `acc`（25 名）——46 摸底判定它是 matha/stdlib.matha 的
# 自由名缺陷而非宿主注入缺口，同批真修后从本表移出（`test_native_selfhost_phase46.py`）。
# 阶段 46a-3 再把异常名族 `未定义错误`/`MathaRuntimeError` 落进原生载体（三者共用
# 消息体发射器），本表随之 24→22。
_BOOT_LATENT = {
    "_to_tuple", "升级包", "当前目录", "执行Matha",
    "执行命令", "执行命令输入", "检查包更新", "改名", "列目录", "删除路径",
    "换目录", "管道结束", "管道输入", "建目录",
    "装载包根们", "装载根", "装载根们", "复制文件", "调试Matha", "路径存在",
    "输入行", "解析_JSON",
}
# 重复读取次数 >1 的名字（其余各 1 次）——锁这份小表，使「同名多点」的载体缺口
# 规模也能显形，而不只是名集。
_BOOT_LATENT_REPEAT = {"_to_tuple": 3, "当前目录": 3,
                       "列目录": 2, "路径存在": 2}


def test_45d6_boot_chain_compiles_but_still_needs_host_injected_names():
    """链接期零拒绝的 boot 全链，运行期仍有 22 个名字没有原生载体——名集锁。

    45a5 的「全链编译成功」只到链接为止；不登记这一层，那条评论就会被读成
    「Matha 工具链已可脱离 Python 运行」。新增/消除 latent 名都会撞这条。
    """
    from src.matha_chain import BOOT_FILES
    mod = _compile(list(BOOT_FILES)).mod
    latent = _latent_reads(mod)
    assert set(latent) == _BOOT_LATENT, (
        f"latent 名集漂移：新增 {sorted(set(latent) - _BOOT_LATENT)}，"
        f"消失 {sorted(_BOOT_LATENT - set(latent))}")
    assert len(latent) == 22, f"latent 名数：{len(latent)}"
    assert {k: v for k, v in latent.items() if v > 1} == _BOOT_LATENT_REPEAT


def test_45d6_lexer_fragment_alone_has_no_latent_name():
    """词法器单片 latent 归零——45d 的正向锁不是靠链上别处的载体蒙过去的。"""
    assert _latent_reads(_compile(["matha/lexer.matha"]).mod) == {}


def test_45d6_latent_name_fails_honestly_at_runtime_not_silently():
    """一个 latent 名的真形：先前输出保住、退出码非零、stderr 点名「未定义变量」。

    取 `_BOOT_LATENT` 里的真名（装载根）而不是生造名——生造名测的是拼写错误，
    这里测的是载体缺口。
    """
    src = '输出("before")\nlet x = 装载根\n输出(x)\n'
    rc, out, err = _aot("latent_honest", src)
    assert rc != 0, f"无载体的宿主名竟然跑通了：{out}"
    assert out == ["before"], out
    assert "未定义变量" in err, err[:200]


def test_45d6_native_docstring_claim_of_no_reachable_name_is_stale():
    """`src/mbc/native.py` 说「当前无此类可达名字，仅保留防御分支」——本批取证为过时。

    该类 = 「VM 能解析、原生未实现」的全局。实测 `长度`（VM/宿主有、原生只带 `len`）
    在链接期**不报错**、只在运行期落 `err_undefined`，即防御分支确是可达的；`use`
    形态更把 `加载模块` 本身也带成 latent 名——这正是 45b 多源链接存在的理由（链接
    期把跨文件符号编进同一映像，而不是留一个运行期才炸的名字）。
    本锁同时锁住那句过时断言仍在源码里：改写它的人必须重新取证，而不是顺手删掉。
    """
    from src.mbc.compiler import compile_source  # noqa: PLC0415

    assert "长度" not in native.NATIVE_BUILTINS and "len" in native.NATIVE_BUILTINS
    direct = _latent_reads(compile_source('输出(长度([1,2]))\n'))
    inside = _latent_reads(compile_source('func f(x) -> Int = 长度(x)\n输出(f([1,2]))\n'))
    assert list(direct) == ["长度"] and list(inside) == ["长度"]

    use_form = _latent_reads(compile_source('use 标准库 { 长度 }\n输出(长度([1,2]))\n'))
    assert "加载模块" in use_form, f"use 形态不再降级为 加载模块，本条登记需重新取证：{use_form}"

    doc = (_ROOT / "src" / "mbc" / "native.py").read_text(encoding="utf-8")
    assert "当前无此类可达名字，仅保留防御分支" in doc


def test_45d6_latent_stderr_names_the_missing_carrier():
    """原生面未定义名 stderr **带名同判**：`未定义变量 'X'` 与 hi/vm/链面逐字一致。

    阶段 46a-3 前原生发射器只有无参条目 `("err_undefined", "未定义变量")`，报错丢名字
    ——载体缺口因此无法定位（只知「有个未定义变量」，不知哪个）。现在 LOAD_GLOBAL 的
    未定义位走 `err_undef_pre` + `sob:{名}` + `str_concat` + `dk_q` 拼出带名句，
    与三面同源（消息体即 `MathaUndefinedNameError.__str__` 的返回值）。
    异常**类名**载体仍缺（原生无异常类型），该差登记承继 41-③ 同族，不在本锁掩盖。
    """
    assert '("err_undefined", "未定义变量")' not in NATIVE_SRC, \
        "无名的 err_undefined 条目已退役——复原它等于让原生面重新丢失缺名信息"
    assert '("err_undef_pre", "未定义变量 \'")' in NATIVE_SRC
    rc, out, err = _aot("latent_shape", "let x = 装载根\n")
    assert rc != 0, f"无载体名竟跑通：{out}"
    assert err.strip() == "未定义变量 '装载根'", err[:200]


def test_45d6_undefined_name_message_matches_host_faces():
    """同一句缺名读数在 hi / vm / 原生三面逐字相同。

    三面各自独立求值同一条源 `let x = 装载根`，读数必须字字相同（裁判面不吃 Python：
    原生是独立映像，hi/vm 只是对位判据）。任一面改文案都会撞这里。链面的同句读数由
    `test_native_process_phase44.py::test_44c_boot_face_reports_undefined_name` 锁住。
    """
    src = "let x = 装载根\n"
    msgs = []
    for face in ("hi", "vm"):
        try:
            if face == "hi":
                interpret(src)
            else:
                VM(compile_sources([src])).run()
            raise AssertionError(f"{face} 面未定义名竟跑通")
        except MathaUndefinedNameError as e:
            msgs.append((face, str(e)))
    assert msgs == [("hi", "未定义变量 '装载根'"),
                    ("vm", "未定义变量 '装载根'")], msgs
    rc, _out, err = _aot("latent_four", src)
    assert rc != 0
    assert err.strip() == "未定义变量 '装载根'", (err[:200], msgs)


# ==================== 45e 文档口径收口锁 ====================
# 本片不改代码，只把阶段 45 写进 KNOWN_ISSUES / ARCHITECTURE / README 的**读数**
# 变成机器判定：链面固定注册面 60 名、宿主对位镜像 44 名（不等集）、`module 解释器`
# 两套源三套解析序、消费者只触交集名、struct 工厂缺口、以及两处行号/文件勘误。

_BIND_RE = re.compile(r'绑定环境\(\s*env\w*\s*,\s*"([^"]+)"')
_DECL_RE = re.compile(r"^  (?:func|let)\s+([^\s(=]+)", re.M)
_USE_RE = re.compile(r"use\s+解释器(?:\s*\{([^}]*)\})?")
_QUAL_RE = re.compile(r"解释器\.([^\s()\[\]{},.，。）（]+)")

_BOOT_INTERP = _ROOT / "matha" / "interp_matha.matha"
_HOST_INTERP = _ROOT / "matha" / "interp.matha"
_KI_TXT = (_ROOT / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
_ARCH_TXT = (_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
_README_TXT = (_ROOT / "README.md").read_text(encoding="utf-8")

#: boot 固定面独有名（宿主对位镜像的 注册内建 不绑，靠 28d 插口运行期补）
_BOOT_ONLY_FACE = {"输出", "print", "int", "float", "str", "log", "pow", "range",
                   "factorial", "assert", "strip", "to_lower", "to_upper",
                   "replace", "split", "parse_JSON", "__公式库__"}
#: 镜像固定面独有名
_MIRROR_ONLY_FACE = {"原地设置"}


def _face(path: Path) -> list[str]:
    """`func 注册内建` 体内逐条 `绑定环境(envN, "名", …)` 的静态名序（含重复）。"""
    txt = path.read_text(encoding="utf-8")
    i = txt.index("func 注册内建")
    j = txt.index("\n\n", txt.index("env5", i))
    return _BIND_RE.findall(txt[i:j])


def _module_names(path: Path) -> set[str]:
    """`module 解释器` 之后的模块级 `func`/`let` 声明名集。"""
    txt = path.read_text(encoding="utf-8")
    return set(_DECL_RE.findall(txt[txt.index("module 解释器"):]))


def test_45e_chain_registration_face_is_the_documented_60():
    """boot 链固定注册面 = 60 名唯一，且三份文档都写的是这个现值。"""
    names = _face(_BOOT_INTERP)
    assert len(names) == 60, f"链面固定注册面现值 {len(names)} 名，文档口径漂移"
    assert len(set(names)) == 60, "注册面出现重名绑定（计数会把缺口藏起来）"
    assert set(names) & _BOOT_ONLY_FACE == _BOOT_ONLY_FACE, "boot 独有名集漂移"
    for carrier in ("执行命令", "检查包更新", "错误", "当前目录", "执行Matha", "调试Matha"):
        assert carrier in names, f"载体/raise 名脱离固定面：{carrier}"
    assert "逐条 **60 名**" in _ARCH_TXT, "ARCHITECTURE 第五节的现值口径已过期"
    assert "现行固定面 60 名" in _README_TXT, "README 阶段 41 段仍把 47 读作现值"
    assert "**60 名**" in _KI_TXT


def test_45e_host_mirror_face_is_a_different_set_not_the_same_60():
    """「双镜像」≠「固定面等集」：镜像静态 44 名，尾走 28d 插口补名。"""
    boot, mirror = set(_face(_BOOT_INTERP)), set(_face(_HOST_INTERP))
    assert len(mirror) == 44 and len(set(mirror)) == 44, f"镜像固定面 {len(mirror)} 名"
    assert boot - mirror == _BOOT_ONLY_FACE, f"boot 独有名集漂移：{sorted(boot - mirror)}"
    assert mirror - boot == _MIRROR_ONLY_FACE
    assert len(boot & mirror) == 43
    txt = _HOST_INTERP.read_text(encoding="utf-8")
    assert "并插口(env42, 解释器插口[0])" in txt, "镜像固定面尾部的插口缝被摘掉"
    assert "解释器插口 = [[]]" in txt, "插口起始空表约定变了（静态名数口径要随之改）"
    assert "静态只绑 44 名" in _ARCH_TXT and "交集 43 名" in _ARCH_TXT


@pytest.mark.parametrize("rel,line,needle", [
    ("src/matha_chain.py", 37, '"matha/interp_matha.matha"'),
    ("src/interp.py", 946, '"解释器": "interp.matha"'),
    # 46c 在 484 之上补了功率分层（+15 行），落点随行号漂移改指 499——
    # 该锁的本意就是「漂移即红」，不放宽成全文搜索。
    ("scripts/selfhost_matrix.py", 499, '"解释器": "interp.matha"'),
    ("matha/loader.matha", 23, '["解释器", "interp.matha"]'),
    ("src/os_runtime.py", 58, "_BOOT_CHAIN_FILES = ["),
    ("src/os_runtime.py", 60, '"matha/vm.matha"]'),
    # 46a-2 把 `func 注册内建` 上方的顶层入口/载体臂注扩写（+6/+5 行），两个落点随行号
    # 漂移改指 1438 / 1517；同理 46a-1 的 标准库.len 归一使臂表整体下移 6 行。
    ("matha/interp_matha.matha", 1438, "func 注册内建"),
    ("matha/interp_matha.matha", 1517, "env57"),
    ("matha/interp.matha", 17, "use 词法器 { Token"),
    ("matha/lexer.matha", 29, "struct Token {"),
])
def test_45e_documented_line_anchors_still_point_at_their_target(rel, line, needle):
    """登记条目/架构段引用的落点行必须逐条命中——行号漂移就是本轮勘误一的复发。"""
    got = (_ROOT / rel).read_text(encoding="utf-8").splitlines()[line - 1]
    assert needle in got, f"{rel}:{line} 现为 {got.strip()[:60]!r}，不再是 {needle!r}"


def test_45e_interpreter_module_resolves_to_two_sources_across_three_orders():
    """`module 解释器` 同名两套源；三套解析序各自指向不同文件。"""
    from src.interp import _CN2FILE
    from src.matha_chain import BOOT_FILES
    from src.os_runtime import _BOOT_CHAIN_FILES
    assert _CN2FILE["解释器"] == "interp.matha"
    assert "matha/interp_matha.matha" in BOOT_FILES
    assert "matha/interp.matha" not in BOOT_FILES
    assert "matha/interp.matha" in _BOOT_CHAIN_FILES
    assert "matha/interp_matha.matha" not in _BOOT_CHAIN_FILES
    assert '"解释器": "interp.matha"' in (_ROOT / "scripts" / "selfhost_matrix.py").read_text(encoding="utf-8")
    assert '["解释器", "interp.matha"]' in (_ROOT / "matha" / "loader.matha").read_text(encoding="utf-8")


def test_45e_the_two_interpreter_sources_are_not_name_equal():
    """模块名集 106 / 141、交集 53——同名 `module 解释器` 实为两套声明。

    boot 侧 139 → 141 是阶段 46b 入口绑名批（代码注 46b-2）新增的
    `绑模块名`/`绑名对` 两个 helper（`matha/interp_matha.matha:1529` 一带），
    二者均为 boot 独有名，故交集仍 53——「两套源不等集」这一判据不受影响。
    """
    mirror, boot = _module_names(_HOST_INTERP), _module_names(_BOOT_INTERP)
    assert len(mirror) == 106 and len(boot) == 141, f"{len(mirror)} / {len(boot)}"
    assert len(mirror & boot) == 53, f"交集 {len(mirror & boot)} 名，两套源已变形"
    assert "func_len" in mirror and "func_len" not in boot
    assert "应用内建" in boot and "应用内建" not in mirror


def test_45e_host_face_resolution_actually_reads_the_mirror_not_the_boot_engine():
    """宿主面 `use 解释器 {…}` 的实测读数——解析序不是纸面推断。"""
    assert _hi('use 解释器 { func_len }\n输出(1)\n') == ["1"]
    try:
        _hi('use 解释器 { 应用内建 }\n输出(1)\n')
    except Exception as exc:                        # noqa: BLE001
        assert "模块 '解释器' 中未找到 '应用内建'" in str(exc), str(exc)[:120]
    else:
        pytest.fail("interp_matha 独有名在宿主面竟可装载——解析序已改，文档要同步")


def test_45e_interpreter_consumers_only_touch_the_shared_names():
    """分歧目前潜伏：5 处 `use 解释器` + 全部限定引用都只落在交集 53 名内。"""
    mirror, boot = _module_names(_HOST_INTERP), _module_names(_BOOT_INTERP)
    inter = mirror & boot
    use_sites, refs = [], set()
    for p in sorted((_ROOT / "matha").glob("*.matha")):
        txt = p.read_text(encoding="utf-8")
        for m in _USE_RE.finditer(txt):
            use_sites.append(p.name)
            if m.group(1):
                refs |= {x.strip() for x in re.split(r"[|,]", m.group(1)) if x.strip()}
        refs |= set(_QUAL_RE.findall(txt))
    assert sorted(set(use_sites)) == ["bootstrap_full_test.matha", "bootstrap_matha.matha",
                                      "bootstrap_test.matha", "nl_engine.matha",
                                      "nl_engine_en.matha"], use_sites
    assert refs <= inter, f"消费者触到非交集名：{sorted(refs - inter)}"


def test_45e_consumer_corpora_are_double_face_equal_in_the_snapshot():
    """裸 `use 解释器`（整模块导入）的名称面无法静态锁——Track B 快照是它的实证锁。"""
    snap = json.loads((_ROOT / "docs" / "selfhost_matrix.json").read_text(encoding="utf-8"))
    by_path = {e["path"]: e for e in snap["files"]}
    for name in ("bootstrap_matha.matha", "bootstrap_test.matha", "bootstrap_full_test.matha",
                 "nl_engine.matha", "nl_engine_en.matha", "loader.matha"):
        e = by_path[f"matha/{name}"]
        assert e["boot"] == "ok" and e["host"] == "ok" and e["equal"] is True, \
            f"{name} 双面不再同判：{e}"


def test_45e_struct_factory_gap_between_gate_and_product_is_registered():
    """判定面补 struct 工厂、产品链没补——`装载("解释器")` 在产品链必失败（登记不修二）。"""
    assert "struct Token {" in (_ROOT / "matha" / "lexer.matha").read_text(encoding="utf-8")
    assert "Token" in (_ROOT / "matha" / "interp.matha").read_text(encoding="utf-8")
    assert "_augment_chain_ns" in (_ROOT / "scripts" / "selfhost_matrix.py").read_text(encoding="utf-8")
    chain = (_ROOT / "src" / "matha_chain.py").read_text(encoding="utf-8")
    assert "_augment_chain_ns" not in chain and "struct" not in chain
    assert "模块 '词法器' 中未找到 'Token'" in _KI_TXT, "登记不修二的读数被删了"


def test_45e_documented_line_reference_erratum_is_applied():
    """勘误一（interp_matha 臂表行号 773-774 → 783-784）+ 勘误二（已删文件的行号引用）。

    行号随 46a 的两批改动继续漂移：46a-1 的 `标准库.len` 归一在臂表上方净增 6 行，
    故 777-778 → 783-784。本锁把「文档行锚 == 代码现场」钉死，漂移即红。
    """
    lines = _BOOT_INTERP.read_text(encoding="utf-8").splitlines()
    assert 'name = "执行Matha"' in lines[782] and 'name = "调试Matha"' in lines[783]
    assert "matha/interp_matha.matha:783-784 直接委托宿主内建" in _KI_TXT
    assert _KI_TXT.count("interp_matha.matha:773-774") == 1, "勘误一的旧行号仍在别处流传"
    assert not (_ROOT / "src" / "plugins" / "ffi_sdk.py").exists()
    assert "src/plugins/ffi_sdk.py" in _KI_TXT, "历史条目引用被抹掉而非标注"
    assert "阶段 45 勘误" in _KI_TXT and "阶段 22b 孤儿清算删除" in _KI_TXT


def _flat(txt: str) -> str:
    """文档口径段是折行 + Markdown 强调/代码块写的——去 `*` 与反引号、压空白，
    令断言只锁语义串本身，不锁排版。"""
    return " ".join(txt.replace("*", "").replace("`", "").split())


def test_45e_host_builtin_face_count_in_docs_is_the_live_value():
    """45e 第四个数：宿主内建表阶段 41 时点 3020 → 阶段 44 映像族显式拒绝 +5 = 3025。

    这里故意不把 3025 写死在断言里，而是锁「文档口径段所写 == 当场实测」：内建表增减
    时该锁变红，逼读数同步——「时点值被读作现行值」正是本轮口径收口要治的漂移。
    另锁 +5 的来源可追溯到代码，以及 `src.interp.BUILTINS`（模块级基表）不是那张 3025
    的表——文档曾把后者写成「Interpreter BUILTINS」，两类一名之差即口径漂移。
    """
    from src.interp import BUILTINS as _MODULE_TABLE  # noqa: PLC0415
    from src.interp import Interpreter, PROCESS_IMAGE_BUILTINS  # noqa: PLC0415

    live = len(Interpreter().builtins)
    img = set(PROCESS_IMAGE_BUILTINS)
    assert live - len(img) == 3020, "映像族之外的表也在动，3020 这个时点值需要重新取证"
    assert img <= set(Interpreter().builtins), "映像族五名不再进宿主表"

    arch, ki = _flat(_ARCH_TXT), _flat(_KI_TXT)
    for doc, name in ((arch, "ARCHITECTURE"), (ki, "KNOWN_ISSUES")):
        assert f"实例内建表 {live} 名" in doc, f"{name} 的宿主内建表读数不是现值 {live}"
        assert "阶段 41 时点 3020 → 阶段 44 映像族" in doc
    assert len(_MODULE_TABLE) != live, "模块级基表与实例内建表被当成同一张"
    assert "另一张表只有 82 名" in ki, f"模块级 BUILTINS（实测 {len(_MODULE_TABLE)}）与实例表混读"
    assert len(_MODULE_TABLE) == 82
    assert "NATIVE_BUILTINS 134 名" in arch or "NATIVE_BUILTINS 面独立（现测 134 名）" in ki
    assert len(native.NATIVE_BUILTINS) == 134


def test_45e_new_documented_code_anchor_points_at_its_target():
    """本轮口径段新引入的行锚 `src/interp.py:614` 必须真指到 PROCESS_IMAGE_BUILTINS。"""
    lines = (_ROOT / "src" / "interp.py").read_text(encoding="utf-8").splitlines()
    assert lines[613].startswith("PROCESS_IMAGE_BUILTINS = (")
    assert "src/interp.py:614 PROCESS_IMAGE_BUILTINS" in _flat(_ARCH_TXT)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))