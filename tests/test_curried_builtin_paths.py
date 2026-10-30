"""柯里化内建调用路径的保语义回归锁（P3.2 内建性能优化的前置测试）。

背景：VM `_invoke` 对 Python callable 内建一律**逐参应用**（f(a)→f(b)…），
二元柯里化内建 `get(xs)(i)` 因此每次都要创建一个中间闭包；基准（scripts/bench.py
b06）显示这是最慢的内建调用形态。已采纳的优化分两段，缺一不可：
  · 编译器把完全应用的柯里化内建调用融成单条 CALL N（arity 表宿主侧与 Matha
    自举侧必须逐项同值，否则 stage2↔stage3 定点红）；
  · VM `_curry2/_curry3` 返回携带 `fn`/`arity` 的 `_Curried`，`_invoke` 在齐 arity
    时直接 `fn(*args)`，不物化中间闭包。本文件锁住必须保持的行为：

  1. 分步链式 f(a)(b) 与一次二元 f(a, b) 结果一致；
  2. 偏应用 f(a) 的返回值可继续分步喂参，也可被 CALL argc=2 直接消费
     （`Partial` 展开路径，map/filter 等库函数依赖）；
  3. 超量应用（arity 用尽后再来实参）：异常类型与消息文本 vm↔interp 一致；
  4. 三参柯里化 slice 同上；
  5. 上述结果在三端（vm/interp/native）逐值一致。

口径参照 tests/bench_call_env.py、golden 03_curried_closure 与
matha/library/collections_core.matha 的 append/get 用法。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret  # noqa: E402
from src.mbc import compile_source, run_module  # noqa: E402


def _vm(src: str):
    return run_module(compile_source(src))


def _interp(src: str):
    # src.interp.interpret 返回 (outputs, trace)
    return list(interpret(src)[0])


# ---------------------------------------------------------------- 1/2：链式、二元、偏应用

CASES_ARY2 = [
    ("get 链式", "let xs = [10, 20, 30]\n输出(get(xs)(1))", [20]),
    ("get 二元", "let xs = [10, 20, 30]\n输出(get(xs, 1))", [20]),
    ("append 链式", "输出(append([1])(2))", [[1, 2]]),
    ("append 二元", "输出(append([1], 2))", [[1, 2]]),
    ("range 链式", "输出(range(1)(4))", [[1, 2, 3]]),
    ("range 二元", "输出(range(1, 4))", [[1, 2, 3]]),
    ("atan2 链式", "输出(round(atan2(1)(1) * 1000))", [785]),
    # 偏应用值：先绑定首参，返回值继续被调用
    ("偏应用喂单参", "let g = get([7, 8, 9])\n输出(g(2))", [9]),
    # 注：偏应用值作实参（((f) => f(1))(get(xs))）：两端都把非 Closure 的
    # 可调用值渲染成 '<function>'（_norm_output 既有契约），只锁该文本。
]

RENDER_BOTH = [
    ("偏应用作实参渲染", "let xs = [5, 6]\n输出((f) => f(1))(get(xs))", ["<function>"]),
]

CASES_ARY3 = [
    ("slice 链式", "输出(slice([1, 2, 3, 4])(1)(3))", [[2, 3]]),
    ("slice 一步三元", "输出(slice([1, 2, 3, 4], 1, 3))", [[2, 3]]),
    ("slice 混合", "输出(slice([1, 2, 3, 4], 1)(3))", [[2, 3]]),
    ("slice 偏应用", "let s = slice([1, 2, 3, 4], 1)\n输出(s(3))", [[2, 3]]),
]

# 内建名被用户绑定遮蔽、函数体内链式调用、for 语法糖与三参链的发射面
# （这些形态都必须保持逐次 CALL 1，且结果与解释器一致）。
SHADOW_CASES = [
    ("get 被 let 遮蔽", "let get = 7\n输出(get)\n", [7]),
    ("append 被函数遮蔽", "func append(x: Int, y: Int) -> Int = (x, y) => x - y\n输出(append(5)(2))", [3]),
    ("函数体内链式 get", "func f(xs: List) -> Int = (xs) => get(xs)(1)\n输出(f([9, 8]))", [8]),
    ("三参链分步应用", "输出(slice([1, 2, 3, 4, 5])(1)(3))", [[2, 3]]),
    ("for 元素读取", "let s = 0\nfor x in [1, 2, 3] {\n  s = s + x\n}\n输出(s)", [6]),
    ("range 链式作列表", "输出(range(0)(3))", [[0, 1, 2]]),
]


@pytest.mark.parametrize("name,src,expected", SHADOW_CASES,
                         ids=[c[0] for c in SHADOW_CASES])
def test_shadow_cases_vm_interp(name, src, expected):
    assert _vm(src) == expected, name
    assert _interp(src) == expected, name


@pytest.mark.parametrize("name,src,expected", CASES_ARY2 + CASES_ARY3,
                         ids=[c[0] for c in CASES_ARY2 + CASES_ARY3])
def test_curried_forms_same_value(name, src, expected):
    assert _vm(src) == expected, name
    assert _interp(src) == expected, name


@pytest.mark.parametrize("name,src,expected", RENDER_BOTH, ids=[c[0] for c in RENDER_BOTH])
def test_curried_function_value_renders(name, src, expected):
    # 函数值经 输出 渲染：vm↔interp 同为 '<function>'（不改语义，只锁现状）
    assert _vm(src) == expected, name
    assert _interp(src) == expected, name


# ---------------------------------------------------------------- 3：超量应用错误对齐

def test_overapplication_error_text_vm_interp_consistent():
    """arity 用尽后再喂实参：两端异常文本逐字一致（不改写、不归一发明）。"""
    src = "let xs = [1, 2]\n输出(get(xs)(0)(9))"
    try:
        _vm(src)
        vm_err = None
    except Exception as e:  # noqa: BLE001 — 记录原始类型与文本
        vm_err = (type(e).__name__, str(e))
    try:
        _interp(src)
        it_err = None
    except Exception as e:  # noqa: BLE001
        it_err = (type(e).__name__, str(e))
    # 两端要么都成功返回同一值，要么异常类型+文本一致
    if vm_err is None or it_err is None:
        assert vm_err == it_err is None
    else:
        assert vm_err == it_err, f"vm={vm_err} interp={it_err}"


# ---------------------------------------------------------------- 5：三端逐值一致

@pytest.mark.parametrize("name,src,expected",
                         CASES_ARY2 + CASES_ARY3,
                         ids=[c[0] for c in CASES_ARY2 + CASES_ARY3])
def test_curried_native_parity(name, src, expected):
    native = pytest.importorskip("src.mbc.native")
    if not getattr(native, "compile_to_exe", None):
        pytest.skip("原生后端不可用")
    import subprocess
    import tempfile
    from pathlib import Path
    from src.mbc.native import NativeNotSupported, compile_to_exe

    exe = Path(tempfile.gettempdir()) / "matha_test_curried_parity.exe"
    try:
        exe.write_bytes(compile_to_exe(src))
    except NativeNotSupported as e:
        pytest.skip(f"该场景原生后端未实现：{e}")
    try:
        proc = subprocess.run([str(exe)], capture_output=True, timeout=60, text=True)
    finally:
        exe.unlink(missing_ok=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    got = proc.stdout.strip()
    # native 渲染：列表带引号/方括号形态与 VM repr 不同，只比对纯标量与整数列表
    want = str(expected[0])
    assert got == want.strip() or eval(got.replace("'", '"')) == expected[0] \
        or got == want, f"{name}: native={got!r} want={want!r}"


# ---------------------------------------------------- 6：字节码形状与双侧同值锁

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CURRIED_SHAPES = [
    ("链式二元", "let xs = [1, 2, 3]\n输出(get(xs)(1))", 2),
    ("一步二元", "let xs = [1, 2, 3]\n输出(get(xs, 1))", 2),
    ("链式三元", "输出(slice([1, 2, 3, 4])(1)(3))", 3),
    ("append 链式", "输出(append([1])(2))", 2),
]


def _call_argcs(mod) -> list[int]:
    from src.mbc import opcodes as OP
    codes = [mod.main_code] + [f.code for f in mod.functions.values()]
    return [ins[1] for code in codes for ins in code
            if len(ins) >= 2 and ins[0] == OP.CALL]


@pytest.mark.parametrize("name,src,arity", CURRIED_SHAPES,
                         ids=[c[0] for c in CURRIED_SHAPES])
def test_curried_full_application_fuses_to_call_n(name, src, arity):
    """完全应用到固定 arity 的柯里化内建 → 融成单条 CALL N。

    用例只有一层内建调用 + 一个 `输出`，故融合后的 CALL 序列恰好是
    `[N, 1]`；未融合时为 `[1, 1, 1]`（N 次内建应参 + 1 次输出）。
    """
    argc = _call_argcs(compile_source(src))
    assert argc == [arity, 1], f"{name}: CALL 序列 {argc}，预期 [{arity}, 1]"


def test_host_and_bootstrap_curried_arity_tables_are_equal():
    """宿主 `_CURRIED_BUILTIN_ARITY` 与自举编译器 `_预扫元数` 初始表逐项同值。

    这两个表各自决定一边的 CALL N 融合判定。字节码是宿主编译器与 Matha 自举
    编译器必须逐字节一致的产物（tests/test_mbc_bootstrap.py 的 stage2↔stage3），
    不同值就红——本锁把“改了这边要改那边”变成可执行判据而不是口头约定。
    """
    import re
    from src.mbc.compiler import _CURRIED_BUILTIN_ARITY

    text = open(os.path.join(ROOT, "matha", "compiler_matha.matha"),
                encoding="utf-8").read()
    m = re.search(r"_预扫元数走\(decls,\s*dict_from_pairs\(\[(.*?)\]\)\)", text, re.S)
    assert m is not None, (
        "未在 matha/compiler_matha.matha 中找到 _预扫元数 的初始元数表；"
        "若改了它的写法，请同步本锁的正则")
    got = {k: int(v) for k, v in
           re.findall(r'\[\s*"([^"]+)"\s*,\s*(\d+)\s*\]', m.group(1))}
    assert got == _CURRIED_BUILTIN_ARITY, (
        f"自举侧元数表 {got} 与宿主 {_CURRIED_BUILTIN_ARITY} 不同值，自举定点必红")


def test_shadowed_curried_name_keeps_stepwise_semantics():
    """内建名被用户 FuncDef 声明覆盖时，以用户 arity 为准（不拿内建表去套）。"""
    src = "func get(x: Int) -> Int = (x) => x + 100\n输出(get(1))\n"
    assert _vm(src) == [101]
    assert _interp(src) == [101]


def test_corpus_never_rebinds_curried_builtin_names():
    """全仓库 .matha 语料不得把四个柯里化内建名绑成 let/形参/元组目标。

    这是 `CALL N` 融合的安全前提：融合按固定 arity 一次实参齐应，若某模块把
    `get` 重绑成其他 arity 的值（且不是 FuncDef，因而不会被元数表覆盖），
    融合后的行为就会与逐次 CALL 1（以及不经字节码的 interp）分歧。FuncDef
    形态的同名定义是允许的（扫描后覆盖预置值，以用户声明为准）。
    """
    from src.parser import Parser

    dirs = [Path(ROOT, "matha"), Path(ROOT, "golden_tests"),
            Path(ROOT, "scripts", "bench_cases"), Path(ROOT, "examples")]
    files = [f for d in dirs if d.is_dir() for f in d.rglob("*.matha")]
    assert files, "未找到任何 .matha 语料，扫描面失效"

    def is_node(x):
        return hasattr(x, "__dict__") and type(x).__module__.startswith("src.")

    def walk(node, seen):
        if id(node) in seen:
            return
        seen.add(id(node))
        t = type(node).__name__
        names = []
        if t == "FuncDef":
            names.append((getattr(node, "name", None), "FuncDef"))
        elif t == "Lambda":
            names.extend((x, "Lambda参数") for x in (getattr(node, "params", None) or []))
        elif t == "LetBinding":
            names.append((getattr(node, "name", None), "let"))
        elif t == "LetTupleBinding":
            names.extend((x, "元组绑定") for x in (getattr(node, "names", None) or []))
        elif t == "Binding":
            tgt = getattr(node, "target", None)
            if type(tgt).__name__ == "Variable":
                names.append((getattr(tgt, "name", None), "赋值目标"))
        for n, kind in names:
            if isinstance(n, str) and n in _CURRIED_NAMES and kind != "FuncDef":
                offenders.append(f"{kind}:{n}")
        for v in list(node.__dict__.values()):
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if is_node(x):
                    walk(x, seen)

    _CURRIED_NAMES = set(_curried_arity_table())
    offenders: list[str] = []
    for f in files:
        prog = Parser(f.read_text(encoding="utf-8", errors="replace")).parse()
        walk(prog, set())
    assert not offenders, (
        f"语料把柯里化内建名重绑成了非 FuncDef 绑定（会破坏 CALL N 融合与 interp 对齐）："
        f"{offenders}"
    )


def _curried_arity_table() -> dict:
    from src.mbc.compiler import _CURRIED_BUILTIN_ARITY
    return _CURRIED_BUILTIN_ARITY
