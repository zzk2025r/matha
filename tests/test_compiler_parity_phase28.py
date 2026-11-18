# -*- coding: utf-8 -*-
"""阶段 28c 字节码全语料对拍锁 —— Matha 自举编译器（compiler_matha.matha 编译入
host MBC、跑在 host VM，即 stage3）对全部 matha/**/*.matha 语料的编译产物，
与宿主编译器 stage2（src/mbc/compiler.py）的 _canon 逐位对拍。

判据（阶段 28 拍板①全语料三重公式判据的第二重）：
  Matha parser AST ≡ 宿主 AST（28b 已锁 test_parser_parity_phase28.py）
  → Matha compiler 字节码 ≡ 宿主 _canon（本文件，全语料 182 文件逐位）

VM 执行面维持阶段 27 stage-4 闭环锁（VM² ~10.5 min/文件，不随本锁扩面）。

28c 修复的五类根因（每类一个最小源回归锁，语料面由参数化全语料锁覆盖）：
  R1 module X { func X } 同名冲突不发射命名空间绑定（宿主 _compile_top_decl
     `decl.name not in member_names` 门，阶段 24a 资源形态）；
  R2 函数体内语句位 let rec：盒协议（先声明盒槽 MAKE_BOX → 值 → STORE_BOX，
     lambda 体内自引用 LOAD_OUTER_BOX 沿父链解析）——此前值先编译、名后声明，
     自引用漏 LOAD_GLOBAL + 名泄漏常量池；
  R3 return 语句（28b 词法器补关键字后 parser 产出 返回语句 节点）——
     有值求值+RET / 无值 PUSH_NULL+RET；
  R4 `#N：…` 后跟 { } 代码块合并形态 body 为裸 list [生成语句, 程序]——
     逐条编译（宿主 _compile_stmt isinstance(node, list) 同构，阶段 19b）；
  R5 lambda 体内 if 的下一行 else 不挂链——双端解析器一致产出
     [if(else=None), 裸 变量"else", 裸 程序] 兄弟（28b 语料 advanced_math
     形态），编译面三承接位对齐宿主（表达式位块留值 / 语句位块不留值 /
     块尾补 PUSH_NULL）。

登记不修（本锁边界）：`#：？公式` 槽位形态的 FORMULA_SCHEMA(0x62) 发射为
宿主编译器专有——全语料 182 文件经宿主 parser 扫描 0 个 GenStmt 含槽（2026-11-18
实测），Matha 侧不建公式库镜像；语料出现该形态前本边界不阻塞三重判据。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src import ast_nodes as ast

_ROOT = Path(__file__).resolve().parent.parent
_COMP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha"]


def _strip_bom(src):
    return src.lstrip("﻿") if src and src[0] == "﻿" else src


def _boot_module():
    comp = Compiler()
    decls = []
    for rel in _COMP_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp.mod


def dict_to_module(d):
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def _canon(mod):
    """MModule 或自举 dict 归一为可逐位比较结构（与 test_mbc_bootstrap 同规）。"""
    if isinstance(mod, MModule):
        functions = dict(mod.functions.items())
        module = mod.module_name
        constants = list(mod.constants)
        main = [tuple(i) for i in mod.main_code]
        fns = {n: (f.arity, f.nlocals, list(f.params),
                   [tuple(i) for i in f.code])
               for n, f in functions.items()}
    else:
        module = mod.get("模块名", "主程序")
        constants = list(mod["常量"])
        main = [tuple(i) for i in mod["主码"]]
        fns = {e[0]: (e[1]["元数"], e[1]["局部数"], list(e[1]["参数"]),
                      [tuple(i) for i in e[1]["码"]])
               for e in mod["函数"]}
    return {"module": module, "constants": constants, "main": main, "fns": fns}


def _host_compile(source):
    return Compiler().compile_program(py_parse(source))


@pytest.fixture(scope="module")
def cvm():
    vm = VM(_boot_module())
    vm.run()
    return vm


def _assert_stage3_eq_stage2(cvm, source):
    stage3 = _canon(dict_to_module(cvm.call("编译", _strip_bom(source))))
    stage2 = _canon(_host_compile(_strip_bom(source)))
    assert stage3 == stage2


# ============================================================
# 全语料参数化对拍（182 文件，逐文件独立归因）
# ============================================================

def _corpus():
    return sorted(str(p.relative_to(_ROOT)).replace("\\", "/")
                  for p in _ROOT.glob("matha/**/*.matha"))


@pytest.mark.parametrize("rel", _corpus(), ids=lambda r: r)
def test_corpus_bytecode_parity(cvm, rel):
    src = (_ROOT / rel).read_text(encoding="utf-8")
    _assert_stage3_eq_stage2(cvm, src)


# ============================================================
# 根因回归锁（最小源，快速归因）
# ============================================================

def test_r1_module_name_conflict_no_namespace(cvm):
    """R1：module X { func X } 同名冲突不发射命名空间绑定。"""
    _assert_stage3_eq_stage2(
        cvm,
        "module 圆柱体积 {\n"
        "func 圆柱体积(r: Float, h: Float) -> Float = (r, h) => 3.14159 * r * r * h\n"
        "}\n")


def test_r2_statement_let_rec_box_protocol(cvm):
    """R2：函数体内语句位 let rec 盒协议（自引用经盒沿父链解析）。"""
    _assert_stage3_eq_stage2(
        cvm,
        "func 线性搜索(arr: List, target: Int) -> Int = (arr, target) => {\n"
        "  let rec search(i: Int) -> Int = (i) =>\n"
        "    i >= len(arr) ? -1 : arr[i] == target ? i : search(i + 1)\n"
        "  search(0)\n"
        "}\n"
        "#：[线性搜索([1, 2, 3], 2)]\n")


def test_r3_return_statement(cvm):
    """R3：return 语句——有值求值+RET / 无值 PUSH_NULL+RET。"""
    _assert_stage3_eq_stage2(
        cvm,
        "func 找(arr: List, t: Int) -> Int = (arr, t) => {\n"
        "  for x in arr {\n"
        "    if x == t { return x }\n"
        "  }\n"
        "  -1\n"
        "}\n"
        "#：[找([1, 2], 2)]\n")


def test_r4_gen_with_code_block_list_body(cvm):
    """R4：`#1：【标题】` + { } 代码块合并形态，body 裸 list 逐条编译。"""
    _assert_stage3_eq_stage2(
        cvm,
        "#1：【算术测试】\n"
        "{\n"
        "  a = 1 + 2 * 3\n"
        "  [a]\n"
        "}\n")


def test_r5_next_line_else_detached_chain(cvm):
    """R5：if 的 else 在下一行不挂链（lambda 体内多行 if/else）——双端解析器
    一致产出 [if(else=None), 裸 变量"else", 裸 程序] 兄弟；编译面三承接位：
    _发射表达式 程序→块(留值)（宿主 _emit_expr CodeBlock 分支）、
    _编译声明 程序→块(不留值)（宿主 _compile_stmt CodeBlock 分支）、
    块尾 程序→语句+PUSH_NULL（宿主 _STMT_NODES 含 CodeBlock 非 _VALUE_STMTS）。"""
    _assert_stage3_eq_stage2(
        cvm,
        "module T {\n"
        "  func f(node: Int, 邻接表: List, visited: List) -> List =\n"
        "    (node, 邻接表, visited) => {\n"
        "    let rec filter(i: Int, result: List) -> List =\n"
        "      (i, result) => {\n"
        "        if i >= len(邻接表[node]) { result } else {\n"
        "          if 节点已访问(邻接表[node][i], visited) { result }\n"
        "          else { filter(i + 1, result + [邻接表[node][i]]) }\n"
        "        }\n"
        "      }\n"
        "    filter(0, [])\n"
        "    }\n"
        "}\n")

