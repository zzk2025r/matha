# -*- coding: utf-8 -*-
"""阶段 40 语言收敛锁（真缺陷批——三引号双端词法器 + differ 3 语料级收口）。

方向 A 拍板：Track B 判定面残留两类——① 三引号字符串双端词法器均不支持
（39-① 同形失败边界）② both_ok_differ 3 语料（31-⑨ 登记不修）。本片落地面：

40a 三引号字符串双端词法器真化（39-① 退役）：
  宿主 ``src/lexer.py`` 新增 ``_string_triple``（定界符为双引号或单引号三连），
  链面 ``matha/lexer.matha`` 镜像 是三连 / 扫描三引号续。语义对齐 CPython：
  定界符内换行原样保留为值的一部分、转义序列照常解码（三引号不改转义规则）、
  六引号为空串、闭定界符后尾随定界符残留判未闭合。字符串字面量 token 的
  （值, 行, 列）双端逐字同判，后续 token 位置随之同步。
  附带同批真修：未闭合字符串链面诚实报错（此前静默成 token → boot_ok_host_err
  假象），文案「字符串未闭合」双端一致；载体类名分歧（host LexerError 带位置
  前缀 vs 链面 MathaRuntimeError）登记不修。

40b differ 3 语料级收口（31-⑨ 退役）：
  ① 值语义对象：``Dataset.__repr__/__eq__``、``_OptResult/_GrowResult.__eq__``
     ——默认 ``object`` 地址表示使同一程序在双执行面/两次运行间不可比（Track B
     both_ok_differ 根因）。可变值对象定义 ``__eq__`` 后即不可哈希（Python 契约）。
  ② 可复现训练：``src/ai_framework.seed_random`` + 神经网络插件 随机种子 内建
     ——权重初始化走全局 ``random``，无播种插口时 loss/history 逐次抖动。
     ``examples/ai/neural_network.matha`` 首行显式播种后双面同判。

登记不修（KNOWN_ISSUES 阶段 40，四条）：① ``matha/interp.matha`` 四文件链镜
  像缺 机械单元/生成语句 执行臂（29c 只落 interp_matha），同 AST 形态链面
  「未知表达式类型: 机械单元」vs interp_matha 真跑；② NEWLINE token 位置/值
  约定分歧（宿主推进后记录 vs 链面推进前）——既有边界，非本片引入；③ 未闭
  合串载体类名分歧（见 40a 段）；④ bootstrap_test 裸解释器面自举链嵌套装载
  深栈需递归预算高于 ``Interpreter.run`` 自适应抬升值——限幅伪影非语义分歧，
  phase19/phase21 两处边界锁按 Track B worker 口径抬 20000 后真化跑通
  [54, 3, 57]（官方门面 exec_api 面无需抬即同判）。
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src import interp as host_interp
from src import matha_bootstrap
from src.kernel import exec_api
from src.kernel.errors import MathaRuntimeError
from src.lexer import Lexer, LexerError

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_INTERP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
                 "matha/interp.matha"]
_M3V_FILES = _INTERP_FILES + ["matha/compiler_matha.matha", "matha/vm.matha"]
_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _compile_chain(files):
    comp = Compiler()
    decls = []
    for rel in files:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    return vm


@pytest.fixture(scope="module")
def bootvm():
    """interp_matha 五文件链（Track B boot 面同源）——词法器镜像宿主面。"""
    vm = _compile_chain(_BOOT_FILES)
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


@pytest.fixture(scope="module")
def interpvm():
    """interp.matha 四文件链面——镜像臂缺口登记锁宿主面。"""
    return _compile_chain(_INTERP_FILES)


@pytest.fixture(scope="module")
def m3v():
    """M3V 运行面（六文件链）：自举编译器 编译 + vm.matha 运行M3V。"""
    return _compile_chain(_M3V_FILES)


def _boot_run(vm, src):
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env = vm.call("注册内建", vm.call("空环境"))
    for nm, ns in vm._chain_nss.items():
        env = vm.call("绑定环境", env, nm, ns)
    vm.call("执行语句", prog, env)
    return list(vm.call("输出快照"))


def _host_tokens(src):
    return [(t.type.name, t.value, t.line, t.col)
            for t in Lexer(src).tokenize()]


def _boot_tokens(vm, src):
    return [(t["类型"], t["文本"], t["行"], t["列"])
            for t in vm.call("扫描", src, 0, 1, 1, [])]


def _hi_run(src):
    try:
        return host_interp.interpret(src)[0], None
    except Exception as e:  # noqa: BLE001
        return None, e


def _err_str(exc):
    return f"{type(exc).__name__}: {exc}"


# ============================================================
# 40a-1 三引号 token 级双端对拍（值/行/列）
# ============================================================

_TRIPLE_FORMS = [
    ('let s = """a\nb""" in 输出(s)\n', [("a\nb", 1, 9)]),
    ("let s = '''x\ny''' in 输出(s)\n", [("x\ny", 1, 9)]),
    ('let s = """""" in 输出(s)\n', [("", 1, 9)]),
    ('let s = """""""" in 输出(s)\n', [("", 1, 9), ("", 1, 15)]),
    ('let s = """a\\"b""" in 输出(s)\n', [('a"b', 1, 9)]),
    ('let s = """a\\\\b""" in 输出(s)\n', [("a\\b", 1, 9)]),
    ('let s = """\n""" in 输出(s)\n', [("\n", 1, 9)]),
]


@pytest.mark.parametrize("src,expect", _TRIPLE_FORMS,
                         ids=[f"f{i}" for i in range(len(_TRIPLE_FORMS))])
def test_40a1_triple_quote_string_token_parity(bootvm, src, expect):
    """三引号字面量 token：宿主 LIT_STRING 与链面 字符串 的（值, 行, 列）逐字同判。"""
    h = [(v, ln, c) for (k, v, ln, c) in _host_tokens(src) if k == "LIT_STRING"]
    b = [(v, ln, c) for (k, v, ln, c) in _boot_tokens(bootvm, src) if k == "字符串"]
    assert h == b == list(expect), (h, b, expect)


@pytest.mark.parametrize("src", ["let s = '' in 输出(s)\n",
                                 'let s = "" in 输出(s)\n',
                                 'let s = "a\\tb" in 输出(s)\n',
                                 "let s = 'it''s' in 输出(s)\n"],
                         ids=["empty-sq", "empty-dq", "esc-tab", "sq-quote-pair"])
def test_40a1_single_line_string_regression(bootvm, src):
    """回归：单定界符串族不因三连分支改变（值/行/列双端同判）。"""
    h = [(v, ln, c) for (k, v, ln, c) in _host_tokens(src) if k == "LIT_STRING"]
    b = [(v, ln, c) for (k, v, ln, c) in _boot_tokens(bootvm, src) if k == "字符串"]
    assert h == b, (h, b)


def test_40a1_full_stream_parity_except_newline_position(bootvm):
    """整条 token 流（值/行/列）双端同判，NEWLINE 除外（位置约定既有分歧，
    另由 test_40c_newline_token_position_registration 登记）。"""
    src = 'let s = """li1\nli2"""\n输出(s)\n'
    h = [(k, v, ln, c) for (k, v, ln, c) in _host_tokens(src) if k != "NEWLINE"]
    b = [(k, v, ln, c) for (k, v, ln, c) in _boot_tokens(bootvm, src) if k != "换行"]
    assert [x[1:] for x in h] == [x[1:] for x in b], (h, b)
    assert len(h) == len(b)


# ============================================================
# 40a-2 多行串值面四面 + M3V 编译态往返
# ============================================================

_ML_SRC = 'let s = """li1\nli2\\ttab""" in 输出(s)\n'


def test_40a2_multiline_value_four_faces(bootvm):
    """vm/hi/mb/bootvm 四面：三引号值含换行与转义，逐字同判。"""
    expect = ["li1\nli2\ttab"]
    vo, verr = exec_api.run_checked(_ML_SRC)
    hi, hi_err = _hi_run(_ML_SRC)
    mb = matha_bootstrap.interpret(_ML_SRC, strict=True)[0]
    assert verr is None and hi_err is None, (verr, hi_err)
    assert vo == hi == list(mb) == _boot_run(bootvm, _ML_SRC) == expect, (
        vo, hi, mb, _boot_run(bootvm, _ML_SRC))


def test_40a2_m3v_triple_quote_roundtrip(m3v):
    """M3V 编译态往返：三引号常量入常量池 → 运行M3V 取值/长度同判。"""
    assert list(m3v.call("运行M3V", m3v.call(
        "编译", _ML_SRC))) == ["li1\nli2\ttab"]
    assert list(m3v.call("运行M3V", m3v.call(
        "编译", 'let s = """""" in 输出(s)\n'))) == [""]
    assert list(m3v.call("运行M3V", m3v.call(
        "编译", 'let s = """a\\tb""" in 输出(len(s))\n'))) == [3]
    assert list(m3v.call("运行M3V", m3v.call(
        "编译", "let s = '''x\ny''' in 输出(len(s))\n"))) == [3]


# ============================================================
# 40a-3 未闭合字符串：链面诚实报错 + 文案双端一致（载体类名登记）
# ============================================================

_UNCLOSED = [
    ('let s = "abc in 输出(s)\n', "dq"),
    ("let s = 'abc in 输出(s)\n", "sq"),
    ('let s = """abc in 输出(s)\n', "tq"),
    ('let s = """a"""" in 输出(s)\n', "tq-trailing"),
]


@pytest.mark.parametrize("src", [s for s, _ in _UNCLOSED],
                         ids=[i for _, i in _UNCLOSED])
def test_40a3_unterminated_string_honest_both_faces(bootvm, src):
    """未闭合串双面均诚实报错，文案「字符串未闭合」一致；载体类名分歧
    （host LexerError 带 L:col 前缀 vs 链面 MathaRuntimeError）登记不修。"""
    with pytest.raises(LexerError) as h_exc:
        list(Lexer(src).tokenize())
    h_msg = _err_str(h_exc.value)
    assert "字符串未闭合" in h_msg and h_msg.startswith("LexerError"), h_msg
    assert "at L" in h_msg, h_msg
    with pytest.raises(MathaRuntimeError) as b_exc:
        bootvm.call("扫描", src, 0, 1, 1, [])
    assert str(b_exc.value) == "字符串未闭合", _err_str(b_exc.value)


def test_40a3_unterminated_string_m3v_face(m3v):
    """M3V 面同判：编译期即报 字符串未闭合（不静默成 token）。"""
    for src, _ in _UNCLOSED:
        with pytest.raises(MathaRuntimeError, match="字符串未闭合"):
            m3v.call("编译", src)


# ============================================================
# 40b-1 播种插口：可复现 + 类型守卫
# ============================================================

def test_40b1_seed_random_reproducible_and_guard():
    """seed_random 同种子同权重、异种子异权重；非整数（含 bool）诚实拒绝。"""
    from src.ai_framework import _rand_matrix, seed_random
    assert seed_random(7) == 7
    first = _rand_matrix(2, 2, 1.0)
    seed_random(7)
    assert _rand_matrix(2, 2, 1.0) == first
    seed_random(8)
    assert _rand_matrix(2, 2, 1.0) != first
    for bad in (True, False, 1.5, "7", None):
        with pytest.raises(ValueError, match="seed 须为整数"):
            seed_random(bad)


# ============================================================
# 40b-2 随机种子 内建注册面 + 双面可达
# ============================================================

def test_40b2_seed_builtin_registered():
    """单插件一名：注册钩子 / 符号表 / 域模板 / 清单四处齐备（声明↔实现一致）。"""
    import json

    from src.domains.neural_network import _nn_symtab_names, _register_nn
    builtins = {}
    _register_nn(builtins)
    assert "随机种子" in builtins, sorted(builtins)
    assert "随机种子" in _nn_symtab_names()
    from src.domains.registry import DomainRegistry
    assert "随机种子" in DomainRegistry._DOMAIN_TEMPLATES[
        "NeuralNetwork"]["functions"]
    manifest = json.loads((_ROOT / "src/domains/manifest.json").read_text(
        encoding="utf-8"))
    nn = [p for p in manifest["plugins"] if p.get("module")
          == "src.domains.neural_network"]
    assert len(nn) == 1, nn
    assert "随机种子" in nn[0]["symbols"], nn[0]["symbols"]


def test_40b2_seed_builtin_two_faces():
    """域加载后 vm/hi 双面可直调 随机种子，回显种子值。"""
    src = '@：【加载领域】，神经网络\n输出(随机种子(2026))\n'
    hi, hi_err = _hi_run(src)
    assert hi_err is None and hi == [2026], (hi, _err_str(hi_err) if hi_err else None)
    vo, verr = exec_api.run_checked(src)
    assert verr is None and vo == [2026], (vo, verr)


# ============================================================
# 40b-3 值语义对象（__eq__ / __repr__）
# ============================================================

def test_40b3_dataset_value_semantics():
    """Dataset 同内容判等、异名不等、跨类型 NotImplemented；repr 无内存地址；
    可变值对象不可哈希（定义 __eq__ 后 Python 契约）。"""
    from src.domains.data_science import Dataset

    def make(name, rows):
        ds = Dataset(name, 2, 2)
        ds._data = [list(r) for r in rows]
        return ds

    a, b = make("d", [[1.0, 2.0], [3.0, 4.0]]), make("d", [[1.0, 2.0], [3.0, 4.0]])
    assert a == b and not (a != b)
    assert a != make("e", [[1.0, 2.0], [3.0, 4.0]])
    assert a != make("d", [[1.0, 2.0], [3.0, 5.0]])
    assert a.__eq__(object()) is NotImplemented
    text = repr(a)
    assert text == ("Dataset(name='d', features=2, samples=2, rows=2, labels=0)"), text
    assert "0x" not in text, text
    with pytest.raises(TypeError):
        hash(a)


def test_40b3_opt_grow_result_value_semantics():
    """_OptResult/_GrowResult 值语义判等 + repr 可读；_GrowResult 带 错误 形参
    （learn_from_file 失败路径此前无该形参 → TypeError 潜隐缺陷）。"""
    from src.autonomous import _GrowResult, _OptResult

    assert _OptResult(True, {"新函数": ["f"]}) == _OptResult(True, {"新函数": ["f"]})
    assert _OptResult(True, {}) != _OptResult(False, {})
    assert repr(_OptResult(False, {})) == "_OptResult(成功=False, 变更={})"
    assert _GrowResult(True, ["a"], "n") == _GrowResult(True, ["a"], "n")
    assert _GrowResult(True, ["a"], "n") != _GrowResult(True, ["a"], "n", "boom")
    assert _GrowResult(False, [], "p", "无法读取文件").错误 == "无法读取文件"
    assert repr(_GrowResult(False, [], "p", "无法读取文件")) == (
        "_GrowResult(成功=False, 新能力=[], 名称='p', 错误='无法读取文件')")
    for obj in (_OptResult(True, {}), _GrowResult(True, [])):
        with pytest.raises(TypeError):
            hash(obj)


def test_40b4_dataset_print_value_semantic_two_faces():
    """输出通道渲染值语义：vm/hi 双面同判且不含内存地址。"""
    src = '@：【加载领域】，数据科学\nds = 创建数据集("d", 2, 3)\n输出(ds)\n'
    hi, hi_err = _hi_run(src)
    assert hi_err is None and len(hi) == 1, _err_str(hi_err) if hi_err else hi
    text = str(hi[0])
    assert text == "Dataset(name='d', features=2, samples=3, rows=0, labels=0)", text
    vo, verr = exec_api.run_checked(src)
    assert verr is None and str(vo[0]) == text, (vo, verr)
    assert "0x" not in text


# ============================================================
# 40c 登记不修（防漂移锁）
# ============================================================

def test_40c_interp_matha_mech_unit_mirror_registration(bootvm, interpvm):
    """登记：机械单元/生成语句 执行臂只在 interp_matha 落地——同 AST 形态
    interp_matha 真跑得 2，interp.matha 四文件链面「未知表达式类型: 机械单元」。"""
    src = "#：[1 + 1]\n"

    def exec_stmt(vm):
        toks = vm.call("扫描", src, 0, 1, 1, [])
        prog = vm.call("parse", toks)
        env = vm.call("注册内建", vm.call("空环境"))
        return vm.call("执行语句", prog, env)

    value, _env = exec_stmt(bootvm)
    assert value == 2, value
    with pytest.raises(MathaRuntimeError, match="未知表达式类型: 机械单元"):
        exec_stmt(interpvm)


def test_40c_newline_token_position_registration(bootvm):
    """登记：NEWLINE token 约定分歧——宿主推进到下一行后记录 (行+1, 1) 且值为
    两字符转义文本，链面推进前记录本行末列且值为真换行；其余 token 位置同判
    （40a-1 流级锁），既有边界非本片引入。"""
    src = 'let s = "a"\n输出(s)\n'
    h_nl = [t for t in _host_tokens(src) if t[0] == "NEWLINE"]
    b_nl = [t for t in _boot_tokens(bootvm, src) if t[0] == "换行"]
    assert h_nl == [("NEWLINE", "\\n", 2, 1), ("NEWLINE", "\\n", 3, 1)], h_nl
    assert b_nl == [("换行", "\n", 1, 12), ("换行", "\n", 2, 6)], b_nl
