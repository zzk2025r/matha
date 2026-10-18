# -*- coding: utf-8 -*-
"""可扩展 AST 节点注册表（``src/ast_ext.py``）测试。

覆盖：
  1. ``define_node`` — 动态 dataclass 节点 + 注入 ``src.ast_nodes`` 命名空间
     （幂等、字段冲突、非法名、非法字段）
  2. ``register_eval`` / ``register_exec`` — 解释器端规则分派
  3. ``register_compile_expr`` / ``register_compile_stmt`` — MBC 端规则分派
  4. 四端一致 — 同一插件节点在解释器、字节码 VM 与原生后端上结果相同
  5. 兜底而非覆盖 — 未注册节点两端报错与既有行为一致；
     给内置节点注册规则不改变其既有分派
"""
import dataclasses as dc
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'D:\trae')

import pytest

from src import ast_ext
from src import ast_nodes as ast
from src.interp import Interpreter, MathaRuntimeError
from src.mbc import compile_program, opcodes, run_module
from src.mbc.native import emit_exe

# ---- 插件示例：Threshold 表达式节点 ----

def _threshold_eval(ip, node):
    return 1 if ip.eval_expr(node.value) >= ip.eval_expr(node.limit) else 0


def _threshold_lower(node):
    """把插件节点降级为核心 AST（MBC 端只产码，不再解释）。"""
    return ast.IfExpr(
        cond=ast.BinaryOp(op=">=", left=node.value, right=node.limit),
        then=ast.IntegerLit(value=1),
        else_=ast.IntegerLit(value=0),
    )


def _threshold_compile(cp, node, scope, code):
    cp.emit_expr(_threshold_lower(node), scope, code)


@pytest.fixture
def threshold():
    """注册 Threshold 插件节点（解释器 + MBC 两端）并返回其类。"""
    cls = ast_ext.define_node("Threshold", ("value", "limit"))
    ast_ext.register_eval(cls, _threshold_eval)
    ast_ext.register_compile_expr(cls, _threshold_compile)
    return cls


# ---- 插件示例：Announce 语句节点 ----

def _announce_exec(ip, node):
    ip.outputs.append(ip.eval_expr(node.text))


def _announce_compile(cp, node, scope, code):
    cp.emit_expr(node.text, scope, code)
    code.append((opcodes.OUTPUT,))


@pytest.fixture
def announce():
    """注册 Announce 插件语句节点（解释器 + MBC 两端）并返回其类。"""
    cls = ast_ext.define_node("Announce", ("text",))
    ast_ext.register_exec(cls, _announce_exec)
    ast_ext.register_compile_stmt(cls, _announce_compile)
    return cls


@pytest.fixture(autouse=True)
def _isolate_registry():
    """注册表隔离：测试前后清空，避免插件节点/规则泄漏到其它测试。"""
    ast_ext.clear()
    try:
        yield
    finally:
        ast_ext.clear()


def _program(*decls):
    return ast.Program(decls=list(decls))


def _output(expr):
    return ast.Output(expr=expr)


# ---- 1. define_node ----

def test_define_node_injects_ast_namespace():
    cls = ast_ext.define_node("Threshold", ("value", "limit"))
    # 注入 src.ast_nodes → 成为 AST 一等公民
    assert ast.Threshold is cls
    # 是真 dataclass，字段可按名/位构造
    node = cls(value=ast.IntegerLit(value=3), limit=ast.IntegerLit(value=5))
    assert isinstance(node, cls)
    assert isinstance(node, dc.dataclass(cls))
    assert node.value.value == 3
    assert node.limit.value == 5
    # 注册表记录
    assert ast_ext.NODES["Threshold"].fields == ("value", "limit")


def test_define_node_idempotent_same_fields():
    first = ast_ext.define_node("Threshold", ("value", "limit"))
    again = ast_ext.define_node("Threshold", ("value", "limit"))
    assert again is first


def test_define_node_conflicting_fields_rejected():
    ast_ext.define_node("Threshold", ("value", "limit"))
    with pytest.raises(ValueError, match="字段不同"):
        ast_ext.define_node("Threshold", ("value",))


def test_define_node_rejects_invalid_name():
    with pytest.raises(ValueError, match="合法标识符"):
        ast_ext.define_node("1bad", ())
    with pytest.raises(ValueError, match="合法标识符"):
        ast_ext.define_node("_private", ())


def test_define_node_rejects_invalid_field():
    with pytest.raises(TypeError, match="字段应为"):
        ast_ext.define_node("Bad", (123,))


def test_define_node_supports_defaults_and_factory():
    cls = ast_ext.define_node(
        "Sample", ("name", ("count", 0), ("items", dc.field(default_factory=list))))
    node = cls(name="x")
    assert node.count == 0
    assert node.items == []
    node.items.append(1)
    # default_factory → 默认值互不共享
    assert cls(name="y").items == []


def test_describe_reports_bound_rules(threshold, announce):
    rows = {r["name"]: r for r in ast_ext.describe()}
    assert rows["Threshold"] == {
        "name": "Threshold", "fields": ["value", "limit"],
        "eval": True, "exec": False,
        "compile_expr": True, "compile_stmt": False}
    assert rows["Announce"]["exec"] is True
    assert rows["Announce"]["compile_stmt"] is True
    assert rows["Announce"]["eval"] is False


def test_clear_removes_node_and_rules(threshold):
    assert ast_ext.get_eval(threshold) is not None
    ast_ext.clear()
    assert not hasattr(ast, "Threshold")
    assert ast_ext.NODES == {}
    assert ast_ext.get_eval(threshold) is None


# ---- 2. register_* 入参校验 ----

def test_register_requires_callable(threshold):
    with pytest.raises(TypeError, match="可调用"):
        ast_ext.register_eval(threshold, "not-callable")


def test_register_accepts_node_name(threshold):
    ast_ext.register_eval("Threshold", _threshold_eval)
    assert ast_ext.get_eval(threshold) is _threshold_eval


def test_register_unknown_name_raises():
    with pytest.raises(KeyError, match="未定义"):
        ast_ext.register_eval("Nope", _threshold_eval)


# ---- 3. 解释器端规则 ----

def test_eval_rule_drives_interpreter(threshold):
    prog = _program(_output(threshold(
        value=ast.IntegerLit(value=4), limit=ast.IntegerLit(value=4))))
    outs, _trace = Interpreter().run(prog)
    assert outs == [1]


def test_eval_rule_can_be_called_via_public_entrypoint(threshold):
    ip = Interpreter()
    node = threshold(value=ast.IntegerLit(value=4), limit=ast.IntegerLit(value=9))
    assert ip.eval_expr(node) == 0


def test_exec_rule_drives_interpreter_statement(announce):
    prog = _program(announce(text=ast.StringLit(value="hello")))
    outs, _trace = Interpreter().run(prog)
    assert outs == ["hello"]


def test_exec_stmt_public_entrypoint_appends(announce):
    ip = Interpreter()
    ip.exec_stmt(announce(text=ast.StringLit(value="hi")))
    assert ip.outputs == ["hi"]


# ---- 4. MBC 端规则 ----

def test_compile_expr_rule_drives_mbc(threshold):
    prog = _program(_output(threshold(
        value=ast.IntegerLit(value=7), limit=ast.IntegerLit(value=2))))
    assert run_module(compile_program(prog)) == [1]


def test_compile_stmt_rule_drives_mbc(announce):
    prog = _program(announce(text=ast.StringLit(value="bytecode")))
    assert run_module(compile_program(prog)) == ["bytecode"]


# ---- 5. 四端一致（解释器 ↔ 字节码 VM） ----

@pytest.mark.parametrize("value,limit,expected", [
    (3, 5, 0),
    (5, 5, 1),
    (9, 2, 1),
    (0, 1, 0),
])
def test_interp_and_mbc_agree_on_expression(threshold, value, limit, expected):
    node = threshold(value=ast.IntegerLit(value=value),
                     limit=ast.IntegerLit(value=limit))
    prog = _program(_output(node))
    interp_out, _ = Interpreter().run(prog)
    mbc_out = run_module(compile_program(prog))
    assert interp_out == [expected]
    assert mbc_out == [expected]


def test_interp_and_mbc_agree_on_nested_node(threshold):
    inner = threshold(value=ast.IntegerLit(value=9),
                      limit=ast.IntegerLit(value=4))
    outer = threshold(value=inner, limit=ast.IntegerLit(value=0))
    prog = _program(_output(outer))
    assert Interpreter().run(prog)[0] == [1]
    assert run_module(compile_program(prog)) == [1]


def test_interp_and_mbc_agree_on_statement(announce):
    prog = _program(announce(text=ast.StringLit(value="both ends")))
    assert Interpreter().run(prog)[0] == ["both ends"]
    assert run_module(compile_program(prog)) == ["both ends"]


# ---- 6. 原生后端（消费同一 MModule 字节码） ----

def _run_native(mod) -> str:
    """把 MModule 编译为 exe 并运行，返回 stdout 文本。"""
    exe = os.path.join(tempfile.gettempdir(), "test_ast_ext_native.exe")
    Path(exe).write_bytes(emit_exe(mod))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert r.returncode & 0xFFFFFFFF == 0, r.stderr.decode("utf-8", "replace")
    return r.stdout.decode("utf-8", "replace").strip()


@pytest.mark.parametrize("value,limit,expected", [
    (3, 5, 0),
    (9, 2, 1),
])
def test_native_agrees_with_interp_and_vm(threshold, value, limit, expected):
    """插件节点降级为核心字节码 → 原生后端无需感知插件即可编译执行。"""
    node = threshold(value=ast.IntegerLit(value=value),
                     limit=ast.IntegerLit(value=limit))
    prog = _program(_output(node))
    assert Interpreter().run(prog)[0] == [expected]
    assert run_module(compile_program(prog)) == [expected]
    assert _run_native(compile_program(prog)) == str(expected)


def test_native_agrees_on_statement(announce):
    prog = _program(announce(text=ast.IntegerLit(value=7)))
    assert Interpreter().run(prog)[0] == [7]
    assert run_module(compile_program(prog)) == [7]
    assert _run_native(compile_program(prog)) == "7"


# ---- 7. 兜底而非覆盖 ----

def test_unknown_node_still_reports_same_errors():
    ghost_cls = ast_ext.define_node("Ghost", ("payload",))
    node = ghost_cls(payload=ast.IntegerLit(value=1))

    with pytest.raises(MathaRuntimeError, match="暂不支持求值: Ghost"):
        Interpreter().eval_expr(node)
    with pytest.raises(RuntimeError, match="暂不支持的节点 Ghost"):
        compile_program(_program(_output(node)))


def test_unknown_top_level_statement_keeps_existing_behaviour():
    """无 exec 规则的顶层语句节点 → 两端维持各自的既有兜底行为。

    解释器 ``_exec_decl`` 对未知声明既然是「跳过」，MBC ``_compile_stmt`` 既然是
    「转表达式 → 暂不支持的节点」，扩展接口不应偷偷改变它们。
    """
    ghost_cls = ast_ext.define_node("Ghost", ("payload",))
    node = ghost_cls(payload=ast.IntegerLit(value=1))

    outs, _trace = Interpreter().run(_program(node))
    assert outs == []
    with pytest.raises(RuntimeError, match="暂不支持的节点 Ghost"):
        compile_program(_program(node))


def test_builtin_dispatch_is_not_overridden_by_registering():
    """内置节点已有实现先于钩子命中 → 注册规则不会改变既有行为。"""
    def _boom(ip, node):
        raise AssertionError("内置分派不应被插件规则覆盖")

    ast_ext.register_eval(ast.IntegerLit, _boom)
    ast_ext.register_compile_expr(ast.IntegerLit, _boom)
    # 表达式位置仍按内置 IntegerLit 求值 / 编译
    assert Interpreter().eval_expr(ast.IntegerLit(value=42)) == 42
    prog = _program(_output(ast.IntegerLit(value=42)))
    assert Interpreter().run(prog)[0] == [42]
    assert run_module(compile_program(prog)) == [42]


def test_default_registry_is_empty_and_interpreter_untouched():
    """默认（未注册）路径与既有行为一致。"""
    assert ast_ext.NODES == {}
    assert ast_ext.describe() == []
    prog = _program(_output(ast.BinaryOp(
        op="+", left=ast.IntegerLit(value=1), right=ast.IntegerLit(value=2))))
    assert Interpreter().run(prog)[0] == [3]
    assert run_module(compile_program(prog)) == [3]
