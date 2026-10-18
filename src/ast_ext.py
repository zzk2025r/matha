"""可扩展 AST 节点注册表（Matha 核心自定义扩展接口 · 一处定义、两端求值）。

插件用本模块**声明新的 AST 节点类型**并**绑定求值规则**，解释器与 MBC 字节码
编译器各自在兜底前查表分派，因此同一节点两端语义一致（四端一致的扩展层体现）::

    Threshold = ast_ext.define_node("Threshold", ("value", "limit"))
    ast_ext.register_eval(Threshold, lambda ip, n:
                          1 if ip.eval_expr(n.value) >= ip.eval_expr(n.limit) else 0)
    ast_ext.register_compile_expr(Threshold, lambda cp, n, scope, code:
                                  cp.emit_expr(_lower(n), scope, code))

    Interpreter().run(prog)                 # → 按 register_eval      求值
    run_module(compile_program(prog))       # → 按 register_compile_* 求值

四张规则表（按节点**类对象**分派）：

===========================  ==========================  =====================
``register_eval``            解释器 · 表达式             ``fn(interp, node)`` → 值
``register_exec``            解释器 · 语句               ``fn(interp, node)`` → None
``register_compile_expr``    MBC · 表达式                ``fn(cp, node, scope, code)`` 栈上留值
``register_compile_stmt``    MBC · 语句                  ``fn(cp, node, scope, code)`` 不产值
===========================  ==========================  =====================

钩子位置 —— 本模块只做注册与查询，不改变内置节点语义：

- ``src/interp.py::_eval``        兜底 ``暂不支持求值`` 之前查 ``register_eval``
- ``src/interp.py::_exec_stmt``   兜底转发 ``_eval``      之前查 ``register_exec``
- ``src/interp.py::_exec_decl``   顶层声明兜底之前        查 ``register_exec``
- ``src/mbc/compiler.py::_emit_expr``    兜底 ``暂不支持的节点`` 之前查 ``register_compile_expr``
- ``src/mbc/compiler.py::_compile_stmt`` 兜底裸表达式（值后丢弃）之前查 ``register_compile_stmt``
- ``src/parser.py::_parse_postfix`` 收尾处查 ``rewrite_call`` —— **解析期**把
  ``name(a, b)`` 改写为插件节点（见 :func:`register_syntax`），使 Matha 源码可达

**规则是兜底，不是覆盖**：内置节点已有实现的分支先于钩子命中，因此给
``ast.BinaryOp`` 之类注册规则不会改变其既有行为——扩展只能**新增**节点。

节点一经 ``define_node`` 会同时注入 ``src.ast_nodes`` 命名空间，成为 AST 一等公民。
测试请用 ``clear()`` 还原现场。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from src import ast_nodes

#: 节点类注入的目标模块
AST_MODULE = ast_nodes


@dataclass(frozen=True)
class NodeSpec:
    """一条已定义的扩展节点。"""
    name: str
    cls: type
    fields: tuple[str, ...]


#: name → NodeSpec
NODES: dict[str, NodeSpec] = {}

#: 源码语法名 → (节点类, 字段名元组)
SYNTAX: dict[str, tuple[type, tuple[str, ...]]] = {}

#: 节点类 → 规则（四张表）
_EVAL: dict[type, Any] = {}
_EXEC: dict[type, Any] = {}
_COMPILE_EXPR: dict[type, Any] = {}
_COMPILE_STMT: dict[type, Any] = {}

_RULE_TABLES = (_EVAL, _EXEC, _COMPILE_EXPR, _COMPILE_STMT)

#: 改写应用链时用到的核心类型（避免反复属性访问）
_FUNCAPP = ast_nodes.FuncApp
_VARIABLE = ast_nodes.Variable


def _field_name(spec) -> str:
    """字段声明允许 ``"名"`` 或 ``("名", 默认值)``。"""
    if isinstance(spec, str):
        return spec
    if isinstance(spec, tuple) and spec and isinstance(spec[0], str):
        return spec[0]
    raise TypeError(f"字段应为 '名' 或 ('名', 默认值)，实际: {spec!r}")


def _resolve(node) -> type:
    """规则入参：节点类，或已定义节点的名字。"""
    if isinstance(node, str):
        spec = NODES.get(node)
        if spec is None:
            raise KeyError(f"节点 {node} 未定义（先调用 define_node）")
        return spec.cls
    if not isinstance(node, type):
        raise TypeError(f"应传入节点类或节点名，实际: {node!r}")
    return node


def define_node(name: str, fields=(), *, doc: str | None = None) -> type:
    """声明一个新的 dataclass AST 节点类型，并注入 ``src.ast_nodes``。

    ``fields`` 为字段声明序列，元素取 ``"名"``（无默认值）或 ``("名", 默认值)``；
    默认值可传 ``dataclasses.field(default_factory=...)`` 以得到可变默认。
    已用同名同字段定义过时返回既有类（幂等），字段不同则报错。
    """
    if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
        raise ValueError(f"节点名必须是合法标识符，实际: {name!r}")
    existing = NODES.get(name)
    if existing is not None:
        want = tuple(_field_name(f) for f in fields) if fields else existing.fields
        if want == existing.fields:
            return existing.cls
        raise ValueError(
            f"节点 {name} 已定义且字段不同: {existing.fields} → {want}")
    ann: dict[str, Any] = {}
    ns: dict[str, Any] = {}
    for f in fields:
        fname = _field_name(f)
        ann[fname] = Any
        if not isinstance(f, str):
            ns[fname] = f[1]
    ns["__annotations__"] = ann
    ns["__module__"] = AST_MODULE.__name__
    if doc:
        ns["__doc__"] = doc
    cls = dataclasses.dataclass(type(name, (), ns))
    NODES[name] = NodeSpec(name=name, cls=cls, fields=tuple(ann))
    setattr(AST_MODULE, name, cls)
    return cls


def register_eval(node, fn):
    """注册解释器表达式规则 ``fn(interp, node) -> value``。"""
    return _register(_EVAL, node, fn, "register_eval")


def register_exec(node, fn):
    """注册解释器语句规则 ``fn(interp, node) -> None``。"""
    return _register(_EXEC, node, fn, "register_exec")


def register_compile_expr(node, fn):
    """注册 MBC 表达式规则 ``fn(compiler, node, scope, code)``，须在栈上留值。"""
    return _register(_COMPILE_EXPR, node, fn, "register_compile_expr")


def register_compile_stmt(node, fn):
    """注册 MBC 语句规则 ``fn(compiler, node, scope, code)``，不产栈值。"""
    return _register(_COMPILE_STMT, node, fn, "register_compile_stmt")


def _register(table: dict, node, fn, where: str):
    if not callable(fn):
        raise TypeError(f"{where} 的规则必须可调用，实际: {fn!r}")
    table[_resolve(node)] = fn
    return fn


def register_syntax(name: str, node, fields=None) -> type:
    """注册**解析期**源码语法：Matha 源码里的 ``name(a, b, …)`` 直接构造成该节点。

    解析器在 ``_parse_postfix`` 收尾处调用 :func:`rewrite_call`，因此改写发生在
    **进入 AST 之前**——节点随后按既有钩子被 解释器 / MBC / 原生 三端分派。

    - ``name``：源码里书写的标识符（可与节点类名不同，例如 ``阈值``）。
    - ``node``：节点类或 :func:`define_node` 登记过的名字。
    - ``fields``：实参对应的字段名；缺省取节点自带字段。
      节点未经 :func:`define_node` 定义时必须显式给出。

    须在**解析之前**注册（插件模块 import 期）；参数个数不符在解析期报错。

    注意：输出括号 ``[ … ]`` 语境本身会把**解析失败**回退成字符串文本
    （``#：[Hello world]`` 的既有设计），插件的参数个数错误落在该语境同样会被
    回退为字符串；需要硬错误请用绑定 / 裸表达式语境。
    """
    if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
        raise ValueError(f"语法名必须是合法标识符，实际: {name!r}")
    cls = _resolve(node)
    if fields is None:
        fields = _fields_of(cls)
        if fields is None:
            raise ValueError(
                f"节点 {cls.__name__} 未经 define_node 定义，需显式传 fields")
    SYNTAX[name] = (cls, tuple(_field_name(f) for f in fields))
    return cls


def _fields_of(cls) -> tuple[str, ...] | None:
    for spec in NODES.values():
        if spec.cls is cls:
            return spec.fields
    return None


def build_from_call(name: str, args):
    """``name(args…)`` → 插件节点；未注册名返回 ``None``。个数不符报 ``ValueError``。"""
    hit = SYNTAX.get(name)
    if hit is None:
        return None
    cls, fs = hit
    if len(args) != len(fs):
        raise ValueError(f"语法 {name} 期望 {len(fs)} 个参数，实际 {len(args)}")
    return cls(**dict(zip(fs, args, strict=True)))


def rewrite_call(expr):
    """解析期改写：以已注册语法名为头的**应用链** → 插件节点；否则原样返回。

    只在 ``expr`` 确为 ``FuncApp`` 链时改写 —— 单独出现的同名变量保持原样。
    ``SYNTAX`` 为空（默认）时立即返回，对既有解析零影响。
    """
    if not SYNTAX or not isinstance(expr, _FUNCAPP):
        return expr
    head = expr
    while isinstance(head, _FUNCAPP):
        head = head.func
    if not (isinstance(head, _VARIABLE) and head.name in SYNTAX):
        return expr
    args = []
    node = expr
    while isinstance(node, _FUNCAPP):
        args.append(node.arg)
        node = node.func
    args.reverse()
    return build_from_call(head.name, args)


def get_eval(node: type):
    """表达式规则（入参为**节点类**）；无则 ``None``。"""
    return _EVAL.get(node)


def get_exec(node: type):
    return _EXEC.get(node)


def get_compile_expr(node: type):
    return _COMPILE_EXPR.get(node)


def get_compile_stmt(node: type):
    return _COMPILE_STMT.get(node)


def describe() -> list[dict]:
    """列出已定义节点及其规则 / 源码语法绑定情况（供 ``matha features`` 等展示）。"""
    return [{
        "name": spec.name,
        "fields": list(spec.fields),
        "syntax": [n for n, (cls, _fs) in SYNTAX.items() if cls is spec.cls],
        "eval": spec.cls in _EVAL,
        "exec": spec.cls in _EXEC,
        "compile_expr": spec.cls in _COMPILE_EXPR,
        "compile_stmt": spec.cls in _COMPILE_STMT,
    } for spec in NODES.values()]


def clear() -> None:
    """清空全部注册（移除注入的节点类与源码语法），主要用于测试隔离。"""
    for spec in NODES.values():
        if getattr(AST_MODULE, spec.name, None) is spec.cls:
            delattr(AST_MODULE, spec.name)
    NODES.clear()
    SYNTAX.clear()
    for table in _RULE_TABLES:
        table.clear()
