# -*- coding: utf-8 -*-
"""解释器 / VM 后端一致性与包导入性能回归测试。

覆盖两类修复：

1. ``src/__init__.py`` 由 eager-import hub 改为惰性导出。此前它在 import 时
   就把 ``src.mcp_server``（连带 MCP SDK / pydantic / uvicorn / asyncio）等
   全部拖进来，使 ``import src.interp`` 从 ~2.1s 涨到 ~9.8s——包初始化是任何
   ``import src.*`` 的必经之路，于是解释器、编译器与全部测试被一起拖慢。
2. VM 修复后解释器未同步的能力：``输出``/``print``、``安全索引``、
   ``安全取属性``、``构造集合``、``_empty_dict``、``sqrt`` 前缀、``typeof``
   类型名表、``len(dict)``、集合字面量的去重保序列表语义。
"""
import os
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import interpret
from src.mbc import compile_source, run_module


def _interp(src: str) -> list[str]:
    return [str(v) for v in interpret(src)[0]]


def _vm(src: str) -> list[str]:
    return [str(v) for v in run_module(compile_source(src))]


def _both(src: str):
    """两个后端都必须成功，且输出一致。"""
    iv = _interp(src)
    vv = _vm(src)
    assert iv == vv, f"解释器 {iv} != VM {vv}"
    return iv


# ---------- 解释器 / VM 一致性 ----------

PARITY_CASES = {
    # 集合：去重 + 保序 + 普通 list 承载
    "set_dedup": '输出(构造集合("enumeration", 0, [1, 2, 2, 3]))',
    "set_order": '输出(构造集合("enumeration", 0, [3, 1, 3, 2]))',
    "set_empty": '输出(构造集合("enumeration", 0, []))',
    "set_literal_len": "let s = {1, 2, 2}\n输出(len(s))",
    "set_literal_index": "let s = {5, 7}\n输出(s[0])",
    "set_literal_safe": "let s = {5, 7}\n输出(安全索引(s, 1))",
    "set_membership": "let s = {1, 2, 2}\n输出(2 in s)",
    # sqrt 前缀：完全平方回退整数
    "sqrt_9": "let a = ^9\n输出(a)",
    "sqrt_16": "let a = ^16\n输出(a)",
    "sqrt_2": "let a = ^2\n输出(a)",
    "sqrt_float": "let a = ^2.25\n输出(a)",
    # 安全访问
    "safe_index_hit": 'let d = {"a": 1}\n输出(安全索引(d, "a"))',
    "safe_index_miss": 'let d = {"a": 1}\n输出(安全索引(d, "z"))',
    "safe_index_null": '输出(安全索引(null, "z"))',
    "safe_attr_hit": 'let d = {"a": 7}\n输出(安全取属性(d, "a"))',
    "safe_attr_miss": 'let d = {"a": 7}\n输出(安全取属性(d, "z"))',
    "safe_attr_null": '输出(安全取属性(null, "z"))',
    # 空字典常量
    "empty_dict_len": "输出(len(_empty_dict))",
    "empty_dict_typeof": "输出(typeof(_empty_dict))",
    # 输出内建（可链式）
    "output": "输出(1)",
    "print": "print(1)",
    "output_chain": "输出(输出(1) + 输出(2))",
    # typeof 关键字：中文类型名表（与 VM / 原生 _TYPEOF_ZH 一致）
    "typeof_int": "输出(typeof(1))",
    "typeof_float": "输出(typeof(1.5))",
    "typeof_str": '输出(typeof("a"))',
    "typeof_list": "输出(typeof([1]))",
    "typeof_dict": '输出(typeof({"a": 1}))',
    "typeof_bool": "输出(typeof(true))",
    "typeof_null": "输出(typeof(null))",
    # 去重（解释器与 VM 双向补齐）
    "dedup": "输出(去重([1, 2, 2, 3]))",
    # 位移 / is
    "shift_left": "let a = 1 << 3\n输出(a)",
    "shift_right": "let a = 16 >> 2\n输出(a)",
    "is_op": "let a = 1\n输出(a is 1)",
    # 文本编码（VM 修复曾移除外层 str() 包装）
    "encode_binary_int": "输出(encode_binary(65))",
    "encode_ternary_int": "输出(encode_ternary(5))",
}


@pytest.mark.parametrize("name", sorted(PARITY_CASES))
def test_interp_vm_parity(name):
    src = PARITY_CASES[name]
    assert _interp(src) == _vm(src), f"{name}: 解释器与 VM 结果不一致"


def test_set_literal_is_ordered_list_not_python_set():
    """集合字面量须为去重保序的 list——此前返回 Python set，导致无序且
    len()/索引/去重() 等内建全部失效。"""
    out = _interp("let s = {3, 1, 3, 2}\n输出(s)")
    assert out == ["[3, 1, 2]"]


def test_empty_braces_is_empty_set():
    """{} 是空集合，不是空字典。"""
    assert _interp("let s = {}\n输出(len(s))") == ["0"]
    assert _interp("let s = {}\n输出(typeof(s))") == ["列表"]


def test_len_accepts_dict():
    """len() 须接受 dict——VM 直接用 Python len，解释器此前只收 str/list/tuple。"""
    assert _interp('输出(len({"a": 1, "b": 2}))') == ["2"]


def test_output_builtin_records_and_returns_value():
    outs, _ = interpret("let x = 输出(42)\n输出(x)")
    assert [str(o) for o in outs] == ["42", "42"]


def test_interp_has_vm_parity_builtins():
    import src.interp as I

    interp = I.Interpreter()
    for name in ("输出", "print", "安全索引", "安全取属性", "构造集合", "_empty_dict"):
        assert name in interp.builtins, f"解释器缺少内建 {name}"
    assert interp.builtins["_empty_dict"] == {}
    # 输出内建必须绑定到实例自己的输出流
    assert interp.builtins["输出"](7) == 7
    assert interp.outputs == [7]


# ---------- 根包惰性导出 ----------

def test_lazy_export_resolves_to_correct_module():
    import src
    import src.interp
    import src.virtual_code

    # interpret 曾被 `from src.virtual_code import ... interpret ...` 意外遮蔽
    assert src.interpret is src.interp.interpret
    assert src.interpret is not src.virtual_code.interpret
    assert src.Interpreter is src.interp.Interpreter


def test_lazy_export_module_attribute_shadowing():
    """importlib 会把子模块写进父包 __dict__；惰性解析须主动覆写，
    否则 src.matha_main 会变成子模块而非导出的 main 函数。"""
    import src
    import src.matha_main  # 触发 importlib 写入父包属性

    exported = src.matha_main          # 导出名 → 应为 main 函数
    assert callable(exported), "src.matha_main 应为 matha_main 的 main 函数"
    assert exported is sys.modules["src.matha_main"].main

    # 该「导出名遮蔽同名子模块」的行为与改动前的 eager 版本一致：
    # `import src.matha_main as c` 走 getattr，得到的同样是 main 函数。
    import src.matha_main as _alias
    assert _alias is exported


def test_lazy_export_all_entries_resolvable_or_unbound():
    """__all__ 中每个名字要么能解析，要么属于历史上从未绑定的 _UNBOUND。"""
    import src

    for name in src.__all__:
        try:
            getattr(src, name)
        except AttributeError:
            assert name in src._UNBOUND, f"{name} 既不可解析也未登记为未绑定"


def test_lazy_export_unknown_name_raises_attributeerror():
    import src

    with pytest.raises(AttributeError):
        src.definitely_not_exported_xyz


def test_dir_includes_lazy_exports():
    import src

    names = dir(src)
    assert "interpret" in names and "Interpreter" in names


def test_from_src_import_ast_nodes_still_works():
    """仓库内广泛使用 `from src import ast_nodes as ast`。"""
    from src import ast_nodes as ast

    assert ast.IntegerLit is not None


# ---------- 导入性能 ----------

@pytest.mark.slow
def test_import_src_does_not_pull_mcp_server():
    """导入 src（或 src.interp）时不得连带加载 MCP SDK。

    这是 4.6 慢启动回归的守卫：eager hub 会在包初始化时 import
    src.mcp_server，单此一项 ~5.7s。
    """
    code = (
        "import sys, src.interp;"
        "heavy=[m for m in sys.modules if m.split('.')[0] in "
        "('mcp','uvicorn','starlette','pydantic_settings')];"
        "print(','.join(sorted(heavy)))"
    )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       cwd=root, timeout=120)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    loaded = r.stdout.decode("utf-8", "replace").strip()
    assert loaded == "", f"import src.interp 拖入了重依赖: {loaded}"


@pytest.mark.slow
def test_import_src_interp_under_time_budget():
    """`import src.interp` 须在 4s 内完成（eager 时期约 9.8s，修复后约 1.8s）。

    用全新进程测量，取三次最好成绩以避开磁盘/杀毒软件抖动。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    best = None
    for _ in range(3):
        t0 = time.perf_counter()
        r = subprocess.run([sys.executable, "-c", "import src.interp"],
                           capture_output=True, cwd=root, timeout=180)
        dt = time.perf_counter() - t0
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        best = dt if best is None else min(best, dt)
    assert best < 4.0, f"import src.interp 耗时 {best:.2f}s，超过 4s 预算"
