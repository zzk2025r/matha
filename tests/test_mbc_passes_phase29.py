# -*- coding: utf-8 -*-
"""阶段 29e 三锁：编译器框架接入 MBC 主线（PassManager 字节码遍，双保险 opt-in 默认关）。

A. 接入面锁：内核 exec_api 编译后钩子槽（set/get_compile_hook）——内核不 import
   src.compiler（dep_audit 棘轮遗留面，方向反转：适配器 import 即反向注册）；
   默认态（子进程无适配器）无钩子且行为不变。
B. 字节码遍实效锁：MBC_PASSES 开启后编译产物过 字节码常量折叠/死代码消除——
   折叠面主码无「双常量+纯算术 BINOP」模式；除零诚实保留运行期报错；合成
   指令流单测覆盖定点折叠链 + 跳入模式中段保守跳过 + 死代码删除与跳转重映射。
C. 语义保持锁：开关 on/off 双态对拍——输出与报错逐位一致（含函数/循环/
   块体/除零/未定义名）。默认关：开关未开时钩子已注册但产物原样。
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import features  # noqa: E402
from src.compiler import mbc_adapter  # noqa: E402  # import 即反向注册钩子
from src.kernel import exec_api  # noqa: E402
from src.mbc import opcodes as OP  # noqa: E402


@pytest.fixture(autouse=True)
def _mbc_passes_flag_off():
    features.clear_feature("MBC_PASSES")
    yield
    features.clear_feature("MBC_PASSES")


def _has_foldable_binop_pattern(code: list, pool: list) -> bool:
    """主码中是否存在「双常量 + 纯数值 BINOP」未折叠模式（诊断用）。"""
    for i in range(len(code) - 2):
        if (code[i][0] == OP.PUSH_CONST and code[i + 1][0] == OP.PUSH_CONST
                and code[i + 2][0] == OP.BINOP):
            ia, ib, iop = code[i][1], code[i + 1][1], code[i + 2][1]
            if not (isinstance(ia, int) and isinstance(ib, int) and isinstance(iop, int)
                    and 0 <= ia < len(pool) and 0 <= ib < len(pool) and 0 <= iop < len(pool)):
                continue
            op = pool[iop]
            if op in ("+", "-", "*") and isinstance(pool[ia], (int, float)) \
                    and isinstance(pool[ib], (int, float)):
                return True
    return False


# ============================================================
# A. 接入面锁
# ============================================================

def test_kernel_default_no_hook_subprocess():
    """无适配器的干净进程：无钩子 + 行为不变（内核默认关）。"""
    code = (
        "import sys\n"
        "from src.kernel import exec_api\n"
        "assert exec_api.get_compile_hook() is None\n"
        "outs, err = exec_api.run_checked('输出(1 + 2)')\n"
        "assert err is None and outs == [3], (outs, err)\n"
        "assert exec_api.get_compile_hook() is None\n"
        "assert 'src.compiler' not in sys.modules, '内核不得拉入框架'\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_adapter_import_registers_hook():
    """适配器 import 即反向注册（本测试模块 import 已接线）。"""
    assert exec_api.get_compile_hook() is mbc_adapter._apply_passes


def test_uninstall_clears_hook_and_reinstalls():
    try:
        mbc_adapter.uninstall()
        assert exec_api.get_compile_hook() is None
    finally:
        mbc_adapter.install()
    assert exec_api.get_compile_hook() is mbc_adapter._apply_passes


def test_default_flag_passthrough():
    """开关默认关：钩子在但产物原样（零行为差）。"""
    assert features.mbc_passes() is False
    mod = exec_api.compile_module("输出(1 + 2)")
    before = [tuple(i) for i in mod.main_code]
    out = mbc_adapter._apply_passes(mod)
    assert out is mod
    assert [tuple(i) for i in mod.main_code] == before


# ============================================================
# B. 字节码遍实效锁
# ============================================================

def test_fold_flag_on_removes_binop_pattern():
    features.set_feature("MBC_PASSES", True)
    try:
        mod = exec_api.compile_module("输出(1 + 2)\n输出((3 + 4) * 5)")
        assert not _has_foldable_binop_pattern(mod.main_code, mod.constants), \
            [tuple(i) for i in mod.main_code]
    finally:
        features.clear_feature("MBC_PASSES")
    mod_off = exec_api.compile_module("输出(1 + 2)\n输出((3 + 4) * 5)")
    assert _has_foldable_binop_pattern(mod_off.main_code, mod_off.constants)


def test_fold_flag_on_runtime_effect():
    features.set_feature("MBC_PASSES", True)
    try:
        outs, err = exec_api.run_checked("输出(1 + 2)\n输出((3 + 4) * 5)")
        assert err is None and outs == [3, 35], (outs, err)
    finally:
        features.clear_feature("MBC_PASSES")


def test_div_zero_honestly_not_folded():
    features.set_feature("MBC_PASSES", True)
    try:
        outs, err = exec_api.run_checked("输出(1 / 0)")
        assert err is not None and "除零" in str(err), (outs, err)
    finally:
        features.clear_feature("MBC_PASSES")


def test_fold_unit_and_pool_intern():
    from src.mbc.vm import _BINOPS, _UNARYOPS
    pool = [1, 2, "+"]
    code = [(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1), (OP.BINOP, 2), (OP.OUTPUT,)]
    new_code, n = mbc_adapter._fold_code_list(code, pool, _BINOPS, _UNARYOPS)
    assert n == 1 and new_code == [(OP.PUSH_CONST, 3), (OP.OUTPUT,)]
    assert pool[3] == 3


def test_fold_chain_to_fixpoint():
    from src.mbc.vm import _BINOPS, _UNARYOPS
    pool = [1, 2, 3, "+"]
    code = [(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1), (OP.BINOP, 3),
            (OP.PUSH_CONST, 2), (OP.BINOP, 3), (OP.OUTPUT,)]
    new_code, n = mbc_adapter._fold_code_list(code, pool, _BINOPS, _UNARYOPS)
    assert n == 2
    assert new_code[0][0] == OP.PUSH_CONST and pool[new_code[0][1]] == 6
    assert new_code[1:] == [(OP.OUTPUT,)]


def test_fold_skips_jump_into_pattern_middle():
    from src.mbc.vm import _BINOPS, _UNARYOPS
    pool = [1, 2, "+"]
    code = [(OP.JZ, 2),
            (OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1), (OP.BINOP, 2),
            (OP.OUTPUT,)]
    new_code, n = mbc_adapter._fold_code_list(code, pool, _BINOPS, _UNARYOPS)
    assert n == 0 and new_code == code


def test_div_zero_not_folded_unit():
    from src.mbc.vm import _BINOPS, _UNARYOPS
    pool = [1, 0, "/"]
    code = [(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1), (OP.BINOP, 2), (OP.OUTPUT,)]
    new_code, n = mbc_adapter._fold_code_list(code, pool, _BINOPS, _UNARYOPS)
    assert n == 0 and new_code == code


def test_dead_code_unit_delete_and_remap():
    """JMP 越过的 OUTPUT 不可达删除，跳转目标 3→2 重映射。"""
    code = [(OP.PUSH_CONST, 0), (OP.JMP, 3), (OP.OUTPUT,), (OP.RET,)]
    new_code, removed = mbc_adapter._dead_code_list(code)
    assert removed == 1
    assert new_code == [(OP.PUSH_CONST, 0), (OP.JMP, 2), (OP.RET,)]


def test_dead_code_unit_unreachable_tail():
    code = [(OP.PUSH_CONST, 0), (OP.OUTPUT,), (OP.RET,),
            (OP.PUSH_CONST, 1), (OP.OUTPUT,)]
    new_code, removed = mbc_adapter._dead_code_list(code)
    assert removed == 2
    assert new_code == [(OP.PUSH_CONST, 0), (OP.OUTPUT,), (OP.RET,)]


def test_pass_manager_pipeline_effect():
    """合成模块经两遍管道：折叠+死代码，持有者代码表真替换。"""
    from src.mbc.compiler import MModule
    mod = MModule(constants=[7, 99, "*"], main_code=[
        (OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1), (OP.BINOP, 2), (OP.OUTPUT,),  # 7*99
        (OP.RET,),
        (OP.PUSH_CONST, 1), (OP.OUTPUT,),   # 不可达尾
    ])
    out = mbc_adapter._MANAGER.run(mod)
    assert out is mod
    code = mod.main_code
    assert code[0][0] == OP.PUSH_CONST and mod.constants[code[0][1]] == 693
    assert code[1:] == [(OP.OUTPUT,), (OP.RET,)]
    stats = mbc_adapter._MANAGER.get_stats()
    assert stats["字节码常量折叠"]["折叠次数"] >= 1
    assert stats["字节码死代码消除"]["删除指令数"] >= 2


# ============================================================
# C. 语义保持锁（开关 on/off 双态对拍）
# ============================================================

_EQUIV_CASES = [
    "输出(1 + 2)",
    "输出((3 + 4) * 5)",
    "输出(10 % 3)",
    "输出(2 ** 10)",
    '输出("a" + "b")',
    "输出([1, 2, 3])",
    "输出(真 and 假)",
    "输出(真 or 5)",
    "输出(-5)",
    "输出(typeof(42))",
    "func f(n: Int) -> Int = (n) => n * 2\n输出(f(21))",
    "func f() -> Int = { r = 1 > 0 ? 10 : 20\n  [r] }\n输出(f())",
    "i = 0\nacc = 0\nwhile i < 3 {\n  acc = acc + (i > 1 ? 10 : 1)\n  i = i + 1\n}\n输出(acc)",
    "输出(1 / 0)",
    "输出(不存在的名字)",
]


def _run_pair(src: str):
    outs_off, err_off = exec_api.run_checked(src)
    features.set_feature("MBC_PASSES", True)
    try:
        outs_on, err_on = exec_api.run_checked(src)
    finally:
        features.clear_feature("MBC_PASSES")
    return (outs_off, err_off), (outs_on, err_on)


@pytest.mark.parametrize("src", _EQUIV_CASES)
def test_flag_on_off_equivalence(src):
    (o0, e0), (o1, e1) = _run_pair(src)
    assert o0 == o1, (src, o0, o1)
    assert (e0 is None) == (e1 is None) and (
        e0 is None or (type(e0).__name__ + str(e0)) == (type(e1).__name__ + str(e1))), \
        (src, e0, e1)


def test_flag_on_full_outputs_stable():
    """折叠/死代码不改变输出序列（含中途报错前的已产生输出）。"""
    src = '输出("a")\n输出(1 + 2)\n输出(1 / 0)\n输出("c")'
    (o0, e0), (o1, e1) = _run_pair(src)
    assert o0 == o1 and e0 is not None and e1 is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
