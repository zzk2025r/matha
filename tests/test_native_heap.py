# -*- coding: utf-8 -*-
"""原生后端堆对象（字符串/列表）端到端测试：编译 → 运行 exe → 校验 stdout。

复核对象头 [type][len][payload] 与 bump 分配、指针区间判定、打印分派。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.mbc import compile_source, run_module
from src.mbc.native import compile_to_exe


def _aot(src: str) -> list[str]:
    exe = os.path.join(tempfile.gettempdir(), "test_native_heap.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert r.returncode == 0, f"AOT 退出码 {r.returncode}"
    return r.stdout.decode("utf-8", "replace").splitlines()


def _vm(src: str) -> list[str]:
    return [str(v) for v in run_module(compile_source(src))]


# ---------- 字符串 ----------

def test_string_literal():
    assert _aot('#1：["hello"]') == ["hello"]


def test_string_unicode():
    assert _aot('#1：["你好"]') == ["你好"]


def test_string_concat():
    assert _aot('#1：["a" + "b" + "c"]') == ["abc"]


def test_string_eq_true():
    assert _aot('#1：["a" == "a"]') == ["True"]


def test_string_eq_false():
    assert _aot('#1：["a" == "b"]') == ["False"]


def test_string_ne():
    assert _aot('#1：["x" != "y"]') == ["True"]


def test_string_global():
    assert _aot('x = "hi"\n#1：[x]\n#2：[x + "!"]') == ["hi", "hi!"]


def test_string_index():
    assert _aot('#1：["abc"[1]]') == ["b"]


def test_len_string():
    assert _aot('#1：[len("")]\n#2：[len("abc")]') == ["0", "3"]


# ---------- 列表 ----------

def test_list_literal():
    assert _aot('#1：[1, 2, 3]') == ["[1, 2, 3]"]


def test_list_empty():
    assert _aot('#1：[[]]') == ["[]"]


def test_list_of_strings():
    assert _aot('#1：["a", "b", "c"]') == ["['a', 'b', 'c']"]


def test_list_len():
    assert _aot('#1：[len([10, 20, 30, 40])]') == ["4"]


def test_list_index():
    assert _aot('l = [7, 8, 9]\n#1：[l[0]]\n#2：[l[2]]') == ["7", "9"]


def test_list_nested():
    assert _aot("#1：[[1], 2]") == ["[[1], 2]"]
    assert _aot("#1：[[1, 2], [3]]") == ["[[1, 2], [3]]"]
    assert _aot("#1：[[[1]], [[2]]]") == ["[[[1]], [[2]]]"]


# ---------- 序列重复（seq_repeat 倍增）----------

@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 16, 17, 33, 64, 65])
def test_string_repeat(n):
    """字符串 × 整数：奇偶路径都必须正确（曾因 test r14,1 编码成 r12 而全错）。"""
    assert _aot('#1：["ab" * %d]' % n) == ["ab" * n]


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5, 7, 8, 16])
def test_list_repeat(n):
    assert _aot('#1：[[1, 2] * %d]' % n) == [str([1, 2] * n)]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
def test_int_times_sequence_swaps_operands(n):
    """整数 × 序列：曾解引用整数当指针读类型标签，直接 0xC0000005。"""
    assert _aot('#1：[3 * "xy"]') == ["xy" * 3]
    assert _aot('#1：[3 * [1, 2]]') == [str([1, 2] * 3)]
    assert _aot('#1：[%d * "z"]' % n) == ["z" * n]


def test_sequence_repeat_edges():
    assert _aot('#1：["" * 3]\n#2：[len("" * 5)]\n#3：[[] * 3]\n#4：[len([] * 5)]') == \
        ["", "0", "[]", "0"]
    assert _aot('#1：["ab" * -2]\n#2：[len("ab" * -2)]') == ["", "0"]
    assert _aot('#1：[len("x" * 100000)]') == ["100000"]
    assert _aot('let s = "ab"\n#1：[s * 3]\n#2：[("ab" * 2) * 2]') == ["ababab", "abababab"]


def test_sequence_repeat_unsupported_returns_none():
    """非序列组合（字典、序列 × 序列）原生降级为 None，与既有约定一致。"""
    assert _aot('#1：[{"a": 1} * 2]') == ["None"]
    assert _aot('#1：["ab" * "cd"]') == ["None"]


# ---------- 字典 ----------

def test_dict_literal():
    assert _aot('#1：[{"k": 1}]') == ["{'k': 1}"]


def test_dict_multi_pair_reversed_order():
    assert _aot('#1：[{"a": 1, "b": 2, "c": 3}]') == ["{'c': 3, 'b': 2, 'a': 1}"]


def test_dict_global():
    assert _aot('d = {"a": 1, "b": 2}\n#1：[d]') == ["{'b': 2, 'a': 1}"]


def test_dict_len():
    assert _aot('d = {"a": 1, "b": 2}\n#1：[len(d)]') == ["2"]


def test_dict_index():
    assert _aot('d = {"a": 1, "b": 2}\n#1：[d["a"]]') == ["1"]


def test_dict_attr():
    assert _aot('d = {"a": 1, "b": 2}\n#1：[d.b]') == ["2"]


def test_dict_nested():
    assert _aot('#1：[{"a": {"b": 3}}]') == ["{'a': {'b': 3}}"]


def test_dict_missing_index_returns_none():
    """缺失键索引：原生防御性返回 None（VM 抛 KeyError——显式偏差）。"""
    assert _aot('d = {"a": 1}\n#1：[d["zz"]]') == ["None"]


def test_non_dict_attr_returns_none():
    """非字典属性访问不崩，返回 None（VM 抛 TypeError——显式偏差）。"""
    assert _aot('#1：[3.z]') == ["None"]


def test_natural_language_output():
    """全角逗号分隔的自然语言输出回退为文本（不当作表达式序列）。"""
    assert _aot("#1：[你好，世界]") == ["你好，世界"]


# ---------- 砖块 19：嵌套文本 repr（与 Python repr 对齐）----------

def test_repr_string_in_list_and_dict():
    assert _aot('#1：["a", "b"]') == ["['a', 'b']"]
    assert _aot('#1：[{"k": "v"}]') == ["{'k': 'v'}"]
    assert _aot('#1：[["x", "y"], {"k": "z"}]') == ["[['x', 'y'], {'k': 'z'}]"]


def test_repr_quote_selection():
    # 串内含 ' 且不含 " → 用双引号
    assert _aot('#1：[["it\'s"]]') == ["[\"it's\"]"]
    # 串内含 " 不含 ' → 用单引号
    assert _aot('#1：[[ "say \\"hi\\"" ]]') == ['[\'say "hi"\']']
    # 两种引号都有 → 用单引号并转义内部 '
    assert _aot('#1：[[ "both \' and \\"" ]]') == ["['both \\' and \"']"]


def test_repr_escapes_control_and_backslash():
    assert _aot('#1：[[ "nl\\nhere" ]]') == ["['nl\\nhere']"]
    assert _aot('#1：[[ "tab\\there" ]]') == ["['tab\\there']"]
    assert _aot('#1：[[ "back\\\\slash" ]]') == ["['back\\\\slash']"]


def test_repr_hex_escapes_from_bytes(tmp_path):
    f = tmp_path / "ctrl.bin"
    f.write_bytes(bytes([0x01, 0x1F, 0x7F, 0x0A, 0x09, 0x41]))
    p = str(f).replace("\\", "/")
    assert _aot(f'let s = _read_file("{p}")\n输出([s])\n') == [r"['\x01\x1f\x7f\n\tA']"]


# ---------- 砖块 19：str(容器) 两遍渲染 ----------

def test_str_of_list():
    assert _aot('let a = [1, "x", 2.5, 真]\n输出(str(a))\n') == ["[1, 'x', 2.5, True]"]


def test_str_of_dict():
    assert _aot('let d = {"a": 1, "b": 2}\n输出(str(d))\n') == ["{'b': 2, 'a': 1}"]


def test_str_of_empty_dict():
    assert _aot('let d = _empty_dict\n输出(str(d))\n') == ["{}"]


def test_str_of_nested():
    assert _aot('let a = [["x", "y"], {"k": "z"}]\n输出(str(a))\n') == ["[['x', 'y'], {'k': 'z'}]"]


def test_str_of_list_with_escapes():
    assert _aot('let a = ["nl\\nhere", 1]\n输出(str(a))\n') == ["['nl\\nhere', 1]"]


def test_str_returns_str_type():
    assert _aot('let a = [1]\nlet s = str(a)\n输出(len(s))\n输出(s)\n') == ["3", "[1]"]


# ---------- 砖块 19：list(文本) 按 Unicode 码点切分 ----------

def test_list_from_text_ascii():
    assert _aot('输出(list("abc"))\n') == ["['a', 'b', 'c']"]


def test_list_from_text_codepoints():
    assert _aot('输出(list("你好"))\n') == ["['你', '好']"]
    assert _aot('输出(list("a😀b"))\n') == ["['a', '😀', 'b']"]
    assert _aot('输出(list("aé中"))\n输出(len(list("aé中")))\n') == ["['a', 'é', '中']", "3"]


def test_list_from_empty_text():
    assert _aot('输出(list(""))\n') == ["[]"]


# ---------- 砖块 19：{} 集合构造（构造集合 → list_dedup） ----------

def test_empty_set_literal():
    """{} 是空集合（返回空列表），不是空字典。"""
    assert _aot('输出({})\n') == ["[]"]
    assert _aot('输出(len({}))\n') == ["0"]


def test_set_literal_dedups_preserving_order():
    assert _aot('输出({1, 2, 2, 3, 1})\n') == ["[1, 2, 3]"]
    assert _aot('输出({"a", "b", "a"})\n') == ["['a', 'b']"]
    assert _aot('输出({1.5, 2.5, 1.5})\n') == ["[1.5, 2.5]"]
    assert _aot('输出({真, 假})\n') == ["[True, False]"]
    assert _aot('输出({7})\n') == ["[7]"]


def test_empty_dict_still_works():
    """_empty_dict 路径未被 {} 修复波及。"""
    assert _aot('let d = _empty_dict\n输出(d)\n输出(len(d))\n') == ["{}", "0"]


def test_make_set_curried():
    """构造集合 是 arity-3 内建，支持柯里化偏应用。"""
    assert _aot(
        'let f = 构造集合("enumeration")\n'
        '输出(f([])([1, 1, 2]))\n'
    ) == ["[1, 2]"]


def test_make_set_degrades_on_non_list():
    """elements 非列表时退化为空列表。

    刻意与 VM 有别：VM 侧 `for e in (elements or [])` 会抛 TypeError，而原生运行时
    没有语言级异常机制（仅 OOM abort），内建一律降级处理（同 len/append）。
    编译器永远传列表，故此路径只对直接调用构造集合 的程序可见。
    """
    assert _aot('输出(构造集合("enumeration")([])(5))\n') == ["[]"]


# ---------- 与 VM 奇偶 ----------

_PARITY = {
    "str_concat": '#1：["foo" + "bar"]',
    "seq_repeat_str": '输出("ab" * 3)\n输出(len("ab" * 3))\n输出("ab" * 0)',
    "seq_repeat_list": '输出([1, 2] * 3)\n输出(len([1, 2] * 5))',
    "seq_repeat_swap": '输出(3 * "xy")\n输出(2 * [7])',
    "seq_repeat_edges": '输出("" * 3)\n输出([] * 3)\n输出("ab" * -1)\n输出(len("z" * 500))',
    "seq_repeat_nested": '输出(("ab" * 2) * 3)\n输出(len([0] * 1000))',
    "str_eq": '#1：["abc" == "abc"]\n#2：["abc" == "abd"]',
    "list_literal": "#1：[1, 2, 3]",
    "list_index": "l = [5, 6, 7]\n#1：[l[1]]",
    "dict_literal": '#1：[{"k": 1}]',
    "dict_multi": '#1：[{"a": 1, "b": 2}]',
    "dict_three": '#1：[{"a": 1, "b": 2, "c": 3}]',
    "dict_global": 'd = {"a": 1, "b": 2}\n#1：[d]',
    "dict_len": 'd = {"a": 1, "b": 2}\n#1：[len(d)]',
    "dict_index": 'd = {"a": 1, "b": 2}\n#1：[d["a"]]',
    "dict_attr": 'd = {"a": 1, "b": 2}\n#1：[d.b]',
    "dict_missing_attr": 'd = {"a": 1}\n#1：[d.zz]',
    "dict_nested": '#1：[{"a": {"b": 3}}]',
    "nested_str_list": '#1：["a", "b", "c"]',
    "nested_str_dict": '#1：[{"k": "v", "n": 1}]',
    "nested_mixed": '#1：[["x"], {"k": "v"}]',
    "repr_quote_single": '#1：[["it\'s"]]',
    "repr_escape_nl": '#1：[["nl\\nhere"]]',
    "str_of_list": 'let a = [1, "x", 2.5, 真]\n输出(str(a))\n',
    "str_of_dict": 'let d = {"a": 1, "b": 2}\n输出(str(d))\n',
    "str_of_empty_dict": 'let d = _empty_dict\n输出(str(d))\n',
    "str_of_nested": 'let a = [["x", "y"], {"k": "z"}]\n输出(str(a))\n',
    "list_from_text_ascii": '输出(list("abc"))\n',
    "list_from_text_cjk": '输出(list("你好"))\n',
    "list_from_text_emoji": '输出(list("a😀b"))\n',
    "set_empty_literal": '输出({})\n输出(len({}))\n',
    "set_enum_ints": '输出({1, 2, 3})\n',
    "set_enum_dedup": '输出({1, 2, 2, 3, 1})\n',
    "set_enum_strs": '输出({"a", "b", "a"})\n',
    "set_enum_floats": '输出({1.5, 2.5, 1.5})\n',
    "set_single": '输出({7})\n',
    "set_membership": 'let s = {1, 2, 3}\n输出(2 in s)\n输出(9 in s)\n',
    "set_for_iter": 'for x in {1, 2, 3} {\n  输出(x)\n}\n',
    "set_ops": '输出(集合并({1,2},{2,3}))\n输出(集合交({1,2},{2,3}))\n',
    "set_vs_dict_literal": '输出({"k": 1})\n输出({1, 2})\n',
    "make_set_curried": 'let f = 构造集合("enumeration")\n输出(f([])([1, 1, 2]))\n',
    "len_mixed": '#1：[len("hello")]\n#2：[len([1, 2])]',
    "global_str": 'x = "hi"\n#1：[x + " " + x]',
    "bool_true": "#1：真\n#2：假",
    "bool_cmp": "#1：[3 == 3]\n#2：[3 == 4]",
    "bool_not": "#1：[not 假]\n#2：[not 真]",
    "null_print": "#1：[null]",
    "print_builtin": '输出(3)\n输出(真)\n输出("s")\n输出(null)',
    "print_returns_arg": "y = 输出(7)\n#1：[y]",
    "if_else": 'x = [1, 2, 3]\n#1：if len(x) == 3 then\n  输出("三")\nelse\n  输出("非三")',
    "truthy_empty_list": "#1：[not []]",
}


@pytest.mark.parametrize("case", sorted(_PARITY))
def test_vm_aot_parity_heap(case):
    src = _PARITY[case]
    assert _aot(src) == _vm(src), f"{case} 的 VM/AOT 输出不一致"


# ---------- 砖块 18：堆 GC（保守式 mark-sweep）----------

def test_gc_string_churn():
    """40 万次非恒定分配（约 12MB > 8MB 堆）触发多轮 GC 后仍正确。"""
    assert _aot(
        'let s = ""\n'
        'for i in range(0, 400000) {\n  s = "n" + str(i)\n}\n'
        '输出(s)\n输出(len(s))\n'
    ) == ["n399999", "7"]


def test_gc_retains_global_list():
    """GC 期间全局单元引用的列表必须存活（cell 槽为 GC 根）。"""
    assert _aot(
        'let a = "alpha"\nlet b = "bravo"\nlet c = "charlie"\n'
        'let d = [a, b, c]\n'
        'let s = ""\n'
        'for i in range(0, 400000) {\n  s = "n" + str(i)\n}\n'
        '输出(d)\n输出(s)\n'
    ) == ["['alpha', 'bravo', 'charlie']", "n399999"]


def test_gc_retains_dict_across_collection():
    assert _aot(
        'let d = {"a": 1, "b": 2}\n'
        'let s = ""\n'
        'for i in range(0, 400000) {\n  s = "n" + str(i)\n}\n'
        '输出(d["a"])\n输出(d)\n'
    ) == ["1", "{'b': 2, 'a': 1}"]


def test_gc_retains_closure_capture():
    """闭包捕获的环境/装箱值经 GC 后仍可调用。"""
    assert _aot(
        'let make = (n) => (x) => n + x\n'
        'let fs = [make(1), make(2), make(3)]\n'
        'let s = ""\n'
        'for i in range(0, 400000) {\n  s = "n" + str(i)\n}\n'
        '输出(fs[0](10))\n输出(fs[1](10))\n输出(fs[2](10))\n'
    ) == ["11", "12", "13"]


def test_gc_retains_large_object_during_churn():
    """大对象（约 400KB 列表）在多次 GC 间存活，且回收块被复用以避免越界。"""
    assert _aot(
        'let big = range(0, 50000)\n'
        'let s = ""\n'
        'for i in range(0, 400000) {\n  s = "n" + str(i)\n}\n'
        '输出(len(big))\n输出(big[49999])\n输出(s)\n'
    ) == ["50000", "49999", "n399999"]


def _blob(tmp_path, n=200000):
    f = tmp_path / "blob.txt"
    f.write_text("a" * n, encoding="utf-8")
    return str(f).replace("\\", "/")


def test_gc_coalesces_adjacent_free_blocks(tmp_path):
    """回收一大片地址连续的小对象后应合并为单块，供更大的对象复用。

    空闲对象们合计约 6.4MB（1.6MB 列表 + 200000×24B 字符串）。请求 3.2MB 的
    range 列表大于任何单个回收对象（最大 1.6MB），只有把连续空闲块合并后才能
    在堆内复用；否则 bump 越过 8MB 上限、破坏 GC 位图，随后 churn 触发的 GC 即
    崩溃（此用例覆盖该回归）。"""
    p = _blob(tmp_path)
    assert _aot(
        f'let s = _read_file("{p}")\n'
        'let xs = list(s)\n'
        'xs = 0\n'
        'let big = range(0, 400000)\n'
        'let t = ""\n'
        'for i in range(0, 300000) {\n  t = "n" + str(i)\n}\n'
        '输出(len(big))\n输出(big[399999])\n输出(len(t))\n'
    ) == ["400000", "399999", "7"]


def test_gc_splits_reused_free_block(tmp_path):
    """合并后的空闲大块应被切分复用给后续整批小对象。

    若分配块不切分，第一个小对象独占整块，其余 20 万个小对象需 bump 并越过堆上限。"""
    p = _blob(tmp_path)
    assert _aot(
        f'let s = _read_file("{p}")\n'
        'let xs = list(s)\n'
        'xs = 0\n'
        'let ys = list(s)\n'
        '输出(len(ys))\n输出(ys[199999])\n'
    ) == ["200000", "a"]


def test_gc_merges_reclaimed_run_with_adjacent_free_block():
    """回收的死亡 run 必须与既有相邻空闲块按地址合并，否则无法复用。

    两个相邻大列表（各约 3.2MB）先后死亡：A 释放后经一次 GC 成为空闲块，并被
    存活分配切出后半；C 释放后的死亡 run 紧邻该空闲块。请求约 4MB（500000 元素）
    大于任一单独空闲块、也大于 bump 余量，只有把 C 的 run 与既有相邻空闲块按地址
    合并后才能满足（用受控补丁禁用合并则此用例确定性 OOM 退出）。"""
    assert _aot(
        'let a = range(0, 400000)\n'
        'let c = range(0, 400000)\n'
        'a = 0\n'
        'let trig = range(0, 300000)\n'
        'c = 0\n'
        'let big = range(0, 500000)\n'
        '输出(len(trig))\n输出(len(big))\n'
    ) == ["300000", "500000"]


def _aot_run(src: str):
    exe = os.path.join(tempfile.gettempdir(), "test_native_heap_oom.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    return subprocess.run([exe], capture_output=True, timeout=30)


def test_gc_oom_aborts_deterministically():
    """存活集超过 8MB 堆时必须确定性终止（stderr 诊断 + 非零退出码），
    而非越过 heap_limit 覆写 GC 位图造成静默损坏/后续崩溃。"""
    r = _aot_run("let big = range(0, 2000000)\n输出(len(big))\n")
    assert r.returncode != 0
    assert r.stdout == b""
    assert "内存不足".encode("utf-8") in r.stderr