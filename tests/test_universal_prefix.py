# -*- coding: utf-8 -*-
"""#：全能前缀 — 词法/语法/运行时统一测试。

设计要点（docs/02-词法结构.md §前缀）：
  - 裸 `#` 是符号，不再是行注释；`(* *)` 是唯一注释形式。
  - `#：` 是「全能前缀」：可充当一切前缀（外来语言路由 / Matha 公式 / 代码前缀），
    无需互译，把多语言变成单一通用语言。
  - `#N：` 是历史兼容简写（保留解析），官方新形式一律 `#：`。
  - Matha 关键字（func/let 等）优先于外来签名：`#：func ...` 定义 Matha 函数，
    而不是误判为 go/rust 兜底转译。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.lexer import Lexer
from src.parser import parse, _detect_foreign_lang, _strip_hash_colon
from src.interp import interpret, Interpreter


def get_out(src: str):
    """执行 Matha 源码，返回最后一次输出。"""
    out, _ = interpret(src)
    return out[-1] if out else None


def get_trace(src: str):
    _, trace = interpret(src)
    return trace


# ─── 词法：裸 # 是符号，不是注释 ─────────────────────────────────────────────

def test_bare_hash_is_symbol_not_comment():
    toks = [t.type.name for t in Lexer('x = 1  # 注释\n# import sys').tokenize()]
    assert toks.count('MATHA_HASH') == 2
    assert 'MATHA_HASH' in toks
    print('  ✓ 裸 # → MATHA_HASH 符号（不再吞噬为行注释）')


def test_only_comment_form_is_matha_annotation():
    # (* *) 仍是唯一注释形式；注释内容不产出 token。
    toks = Lexer('(* 独立注释 *) 1').tokenize()
    assert any(t.type.name == 'LIT_INTEGER' for t in toks)
    print('  ✓ (* *) 为唯一注释形式')


# ─── 语法：#：外来语言路由（保原文空格） ─────────────────────────────────────

def test_hash_colon_parses_foreign_decl():
    prog = parse('#：import os')
    d = prog.decls[0]
    body = d.body if hasattr(d, 'body') else d
    assert type(body).__name__ == 'ForeignDecl'
    assert body.prefix == '#：'
    assert body.lang == 'python'
    assert body.text == 'import os'
    print('  ✓ #：import os → ForeignDecl(#：, python, "import os") 原文空格保留')


def test_hash_colon_python_import_executes():
    trace = get_trace('#：import math')
    assert trace and '#[python]' in trace[0]
    print('  ✓ #：import math 经 ForeignRunner 执行')


def test_hash_colon_python_chinese_name_executes():
    trace = get_trace('#：def 双倍(x): return x * 2')
    assert trace and '#[python]' in trace[0]
    print('  ✓ #：def 中文名(...) 正确路由为 python（而非 ruby）')


def test_bare_hash_inert():
    i = Interpreter()
    i.run(parse('# import math'))
    assert i.trace == ['# importmath']
    print('  ✓ 裸 # ... 惰性（符号语义，不执行）')


def test_bare_hash_zero_external_side_effect():
    # 裸 # 行绝不进入外来路由：不能有任何 #[lang] 痕迹。
    i = Interpreter()
    i.run(parse('# import numpy as np\n# def foo(): pass'))
    assert not any(t.startswith('#[') for t in i.trace)
    print('  ✓ 裸 # 行零外部副作用')


# ─── 语法：#：作为 Matha 公式/代码前缀 ──────────────────────────────────────

def test_hash_colon_expression_block():
    assert get_out('#：{ [1 + 1] }') == 2
    print('  ✓ #：{ [expr] } 公式仍正常')


def test_hash_colon_legacy_seg_block():
    assert get_out('#1：{ [2 + 3] }') == 5
    print('  ✓ #N：历史简写（#1：{ ... }）仍兼容')


def test_hash_colon_control_flow():
    src = '#：{\n if (1 < 2) {\n  输出({ name = "甲乙"\n [name] })\n }\n}'
    assert get_out(src) == '甲乙'
    print('  ✓ #：{ ... } 内 if 控制流正常')


def test_code_prefix_per_line_binding():
    src = '#：{\n  name = "语言桥"\n  rootUri = "d:/trae"\n  [rootUri]\n}'
    i = Interpreter()
    i.run(parse(src))
    assert i.outputs == ['d:/trae']
    print('  ✓ 代码前缀 name/rootUri 逐行绑定（rootUri 为路径）')


# ─── 语法：Matha 关键字优先于外来签名 ───────────────────────────────────────

def test_hash_colon_func_is_matha_not_go():
    # go/rust 签名有 func/fn；但 func 是 Matha 关键字，须先按 Matha 解析。
    src = '#：func add(a, b) -> Int = a + b\n#：{ [add(2, 3)] }'
    assert get_out(src) == 5
    assert not get_trace('#：func add(a, b) -> Int = a + b')
    print('  ✓ #：func ... 定义 Matha 函数（不被 go 签名误吞）')


def test_hash_colon_func_chinese_apply():
    src = '#：func 双倍(x) -> Int = x * 2\n#：{ [双倍(21)] }'
    assert get_out(src) == 42
    print('  ✓ #：func 中文名可用、可调用（Matha 语义）')


# ─── 外来语言签名检测 ────────────────────────────────────────────────────────

def test_foreign_lang_signatures():
    assert _detect_foreign_lang('import numpy as np') == 'python'
    assert _detect_foreign_lang('from os import path') == 'python'
    assert _detect_foreign_lang('def 求和(a, b):') == 'python'
    assert _detect_foreign_lang('class 计算器(object):') == 'python'
    assert _detect_foreign_lang('fn main() {') == 'rust'
    assert _detect_foreign_lang('func main() {') == 'go'       # 兜底；Matha 侧先分流
    assert _detect_foreign_lang('const x = 1;') == 'js'
    assert _detect_foreign_lang('console.log("hi")') == 'js'
    assert _detect_foreign_lang('def add') == 'ruby'
    assert _detect_foreign_lang('puts hello') == 'ruby'
    assert _detect_foreign_lang('#include <stdio.h>') == 'c'
    print('  ✓ 外来语言行级签名（python/rust/go/js/ruby/c）')


def test_seg_prefix_never_routed_foreign():
    # #N：#… 保留段号，不是外来路由入口。
    assert _strip_hash_colon('#1：import math') == '1：import math'
    assert _detect_foreign_lang('1：import math') == ''
    print('  ✓ #N：不加冒号剥离 → 不误路由为外来代码')


# ─── 运行时：路由可关闭，失败不致命 ─────────────────────────────────────────

def test_foreign_routing_can_be_disabled():
    i = Interpreter(foreign_routing=False)
    i.run(parse('#：import math'))
    assert i.trace == ['# import math']
    print('  ✓ foreign_routing=False 时 #：惰性防呆')


def test_foreign_failure_non_fatal():
    # 外来执行失败 → 记入 trace，Matha 程序继续运行（不抛错）。
    trace = get_trace('#：import no_such_module_xyz_943')
    assert trace and trace[0].startswith('#[python]') and '执行失败' in trace[0]
    print('  ✓ 外来执行失败不致命（记入 trace）')


def test_mbc_bytecode_bare_hash_noop():
    # 编译期消费者（mbc 字节码）把 ForeignDecl 视为编译期无操作：
    # 词法时代 # 注释被吞掉 = 不产码，行为保持一致。
    from src.mbc.compiler import compile_source
    mod = compile_source('# 注释行\n1 + 1')
    assert mod.main_code
    print('  ✓ mbc 字节码编译：裸 # 行为编译期无操作（不抛"暂不支持的节点"）')


# ─── 主入口 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== Matha #：全能前缀测试 ===')
    tests = [
        test_bare_hash_is_symbol_not_comment,
        test_only_comment_form_is_matha_annotation,
        test_hash_colon_parses_foreign_decl,
        test_hash_colon_python_import_executes,
        test_hash_colon_python_chinese_name_executes,
        test_bare_hash_inert,
        test_bare_hash_zero_external_side_effect,
        test_hash_colon_expression_block,
        test_hash_colon_legacy_seg_block,
        test_hash_colon_control_flow,
        test_code_prefix_per_line_binding,
        test_hash_colon_func_is_matha_not_go,
        test_hash_colon_func_chinese_apply,
        test_foreign_lang_signatures,
        test_seg_prefix_never_routed_foreign,
        test_foreign_routing_can_be_disabled,
        test_foreign_failure_non_fatal,
        test_mbc_bytecode_bare_hash_noop,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'  ✗ {t.__name__}: {e}')
            failed += 1
    print(f'\n结果: {passed} 通过, {failed} 失败')
    if failed:
        sys.exit(1)