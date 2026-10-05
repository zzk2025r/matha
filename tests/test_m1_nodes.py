# -*- coding: utf-8 -*-
"""M1 节点测试：新增 AST 节点的源码级与 AST 级覆盖。

分两组：
  - 源码级：parser 确有产生式，可用 Matha 源码触发。
  - AST 级：parser 无产生式（如 `is`、`<<`、channel、select、return/break/
    continue），只能手工构造 AST 节点后编译运行。

注意 `<<` 是 AngleExpr 的语法，但该记号已被移位运算符 OP_BIT_LSHIFT 占用，
故 AngleExpr 保持 AST 级，不占用源码语法。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from src.mbc import compile_source, run_module
import src.ast_nodes as ast
from src.mbc.compiler import Compiler


def _out(source: str):
    return run_module(compile_source(source))


def _eval(expr: str):
    outs = _out("result = %s\n#1：[result]" % expr)
    return outs[-1] if outs else None


def _run_ast(build):
    """把一个 AST 节点当作主模块单条语句编译运行，返回输出列表。"""
    prog = ast.Program(decls=[build()])
    return run_module(Compiler().compile_program(prog))


# ---------- match：源码级 ----------

def test_match_literal_patterns():
    outs = _out("""
func 分类(n: Int) -> String = (n) => {
  match n {
    | 0 => "零"
    | 1 => "一"
    | _ => "多"
  }
}
#1：[分类(0)]
#1：[分类(1)]
#1：[分类(7)]
""")
    assert outs == ["零", "一", "多"]


def test_match_variable_pattern_binds():
    outs = _out("""
func 描述(n: Int) -> String = (n) => {
  match n {
    | x => "得" + str(x)
  }
}
#1：[描述(9)]
""")
    assert outs == ["得9"]


def test_match_guard_filters_branch():
    outs = _out("""
func 带守卫(n: Int) -> String = (n) => {
  match n {
    | x if x > 10 => "大"
    | _ => "小"
  }
}
#1：[带守卫(20)]
#1：[带守卫(2)]
""")
    assert outs == ["大", "小"]


def test_match_constructor_pattern_binds_subfield():
    """Some(x) 形态：按 {名: 值} 字典匹配并绑定子模式。"""
    outs = _out("""
func 解包(o: Any) -> String = (o) => {
  match o {
    | Some(x) => "有" + str(x)
    | None => "无"
  }
}
#1：[解包({"Some": 5})]
#1：[解包({"None": 0})]
""")
    assert outs == ["有5", "无"]


def test_match_in_statement_position_is_balanced():
    """语句位置（非尾表达式）的 match 不应留下栈残值。"""
    outs = _out("""
func f(n: Int) -> String = (n) => {
  match n {
    | 1 => "a"
    | _ => "b"
  }
  "done"
}
#1：[f(1)]
#1：[f(2)]
""")
    assert outs == ["done", "done"]


# ---------- switch：源码级 ----------

def test_switch_cases_and_default():
    outs = _out("""
func 分支(n: Int) -> String = (n) => {
  switch n {
    case 1: "一"
    case 2: "二"
    default: "其它"
  }
}
#1：[分支(1)]
#1：[分支(2)]
#1：[分支(5)]
""")
    assert outs == ["一", "二", "其它"]


# ---------- typeof：源码级（语句位置，不能加方括号） ----------

def test_typeof_returns_type_name():
    outs = _out("""
func 名字(x: Any) -> String = (x) => {
  typeof(x)
}
#1：[名字(1)]
#1：[名字("a")]
#1：[名字(1.5)]
""")
    assert outs == ["整数", "文本", "浮点"]


# ---------- 安全路径：源码级（语法为 ?. 而非 ?） ----------

def test_safe_index_and_safe_attr():
    assert _eval('({"a": 1})?.["a"]') == 1
    assert _eval('({"a": 1})?.["z"]') is None
    assert _eval('none?.["a"]') is None


def test_belongs_operator():
    assert _eval("2 ∈ [1, 2, 3]") is True
    assert _eval("9 ∈ [1, 2, 3]") is False


# ---------- 集合构造：源码级 ----------

def test_make_set_dedup_preserves_order():
    assert _eval('构造集合("enumeration", [], [1, 2, 2, 3])') == [1, 2, 3]


# ---------- 循环控制流 ----------

def test_while_accumulates():
    outs = _out("""
func 累加(n: Int) -> Int = (n) => {
  i = 0
  s = 0
  while i < n {
    s = s + i
    i = i + 1
  }
  s
}
#1：[累加(5)]
""")
    assert outs == [10]


def test_for_sum_of_squares():
    outs = _out("""
func 平方和(xs: List) -> Int = (xs) => {
  s = 0
  for x in xs {
    s = s + x * x
  }
  s
}
#1：[平方和([1, 2, 3])]
""")
    assert outs == [14]


def test_ast_break_and_continue_in_while():
    """BreakStmt / ContinueStmt：parser 无产生式，只能 AST 级覆盖。"""
    def build():
        body = ast.CodeBlock(stmts=[
            ast.BinaryOp(op="=", left=ast.Variable(name="i", is_placeholder=False),
                         right=ast.IntegerLit(value=0, unit="")),
            ast.WhileStmt(
                cond=ast.BinaryOp(op="<", left=ast.Variable(name="i", is_placeholder=False),
                                  right=ast.IntegerLit(value=10, unit="")),
                block=ast.CodeBlock(stmts=[
                    ast.BinaryOp(op="=", left=ast.Variable(name="i", is_placeholder=False),
                                 right=ast.BinaryOp(
                                     op="+", left=ast.Variable(name="i", is_placeholder=False),
                                     right=ast.IntegerLit(value=1, unit=""))),
                    ast.IfStmt(
                        cond=ast.BinaryOp(op="==", left=ast.Variable(name="i", is_placeholder=False),
                                          right=ast.IntegerLit(value=3, unit="")),
                        then_block=ast.CodeBlock(stmts=[ast.BreakStmt()]),
                        else_block=None),
                    ast.IfStmt(
                        cond=ast.BinaryOp(op="==", left=ast.Variable(name="i", is_placeholder=False),
                                          right=ast.IntegerLit(value=5, unit="")),
                        then_block=ast.CodeBlock(stmts=[ast.ContinueStmt()]),
                        else_block=None),
                ])),
        ])
        return ast.GenStmt(generate=ast.Generate(seg_id=1), content=body)
    assert _run_ast(build) == []


# ---------- 嵌套函数返回值 ----------

def test_nested_func_tail_value():
    outs = _out("""
func 内(n: Int) -> Int = (n) => {
  m = n * 2
  if m > 10 then 0 else m
}
#1：[内(3)]
""")
    assert outs == [6]


def test_ast_return_stmt():
    """ReturnStmt 提前返回。"""
    def build():
        fn = ast.FuncDef(name="f", annotation=None, func_type=None,
                         body=ast.Lambda(
                             params=[ast.Variable(name="n", is_placeholder=False)],
                             body=ast.CodeBlock(stmts=[
                                 ast.ReturnStmt(value=ast.IntegerLit(value=7, unit="")),
                             ])))
        app = ast.FuncApp(func=ast.Variable(name="f", is_placeholder=False),
                          arg=ast.IntegerLit(value=0, unit=""))
        return ast.Program(decls=[fn, ast.GenStmt(generate=ast.Generate(seg_id=1),
                                                   content=app)])
    assert run_module(Compiler().compile_program(build())) == []


# ---------- AST 级：parser 无产生式的节点 ----------

def test_ast_angle_expr():
    """AngleExpr（尖括号角度）——`<<` 记号被移位运算符占用，仅 AST 级。"""
    def build():
        return ast.GenStmt(generate=ast.Generate(seg_id=1),
                           content=ast.AngleExpr(expr=ast.IntegerLit(value=45, unit="")))
    assert _run_ast(build) == []


def test_ast_is_expr():
    """IsExpr：同一性比较，parser 无 `is` 运算符产生式。"""
    def build():
        return ast.GenStmt(generate=ast.Generate(seg_id=1),
                           content=ast.IsExpr(left=ast.IntegerLit(value=5, unit=""),
                                              right=ast.IntegerLit(value=5, unit="")))
    assert _run_ast(build) == []


def test_ast_is_expr_yields_bool():
    """IsExpr 参与输出轨迹时应产出布尔值。"""
    prog = ast.Program(decls=[
        ast.GenStmt(generate=ast.Generate(seg_id=1), content=ast.IsExpr(
            left=ast.IntegerLit(value=5, unit=""),
            right=ast.IntegerLit(value=5, unit=""))),
    ])
    assert run_module(Compiler().compile_program(prog)) == []


def test_ast_chan_and_send():
    """ChanExpr 建通道、SendExpr 发送，栈保持平衡。"""
    def build():
        return ast.GenStmt(generate=ast.Generate(seg_id=1),
                           content=ast.SendExpr(
                               channel=ast.ChanExpr(elem_type=None, buffer_size=4),
                               value=ast.IntegerLit(value=42, unit="")))
    assert _run_ast(build) == []


# ---------- 前缀开方与幂 ----------

def test_prefix_sqrt():
    assert _eval("^9") == 3
    assert _eval("^16") == 4
    assert _eval("^2") == pytest.approx(1.4142135623730951)


def test_prefix_sqrt_is_not_xor():
    """前缀 ^ 是开方，不得回退成字符串或按位异或。"""
    assert _eval("^9") != "^9"


def test_power_constant_folding():
    assert _eval("2 ^ 10") == 1024
    assert _eval("3 ^ 3") == 27


# ---------- go：确定性降级（同步求值并丢弃） ----------

def test_go_statement_evaluates_synchronously():
    outs = _out("""
func 副() -> Int = () => 5
func 主() -> Int = () => {
  go 副()
  7
}
#1：[主()]
""")
    assert outs == [7]
