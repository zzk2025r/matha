"""显式栈求值引擎（Strangler Fig：表达式层先行）。

本模块承接 ``interp.py`` 的**表达式求值**语义，把 ``Interpreter._eval`` 的
Python 递归下降改写为「显式帧栈 + trampoline」。它是「整数 → 表达式 →
语句 → 函数调用」逐模块绞杀的第二块：先让表达式求值脱离宿主递归，其余
节点（语句/函数调用）暂由解释器的既有递归实现兜底。

分层设计
--------
- ``Interpreter._eval(node)`` 为**唯一**公开求值入口。
- 引擎开启时（``MATHA_FEATURE_STACK_ENGINE``），``_eval`` 转调
  ``StackEngine.eval_value(node)``；引擎内部经 ``machine`` 迭代推进，
  宿主栈深度 O(1)（与表达式嵌套深度无关）。
- 引擎对尚未迁移的节点（如 FuncApp、MatchStmt、推导式）回退到
  ``interp._eval``——注意该回退仍是宿主递归，随绞杀推进逐步消除。

语义一致性保证
--------------
- 运算符复用 ``Interpreter._apply_binary_values``（与递归路径同一实现）。
- 变量查找复用 ``Interpreter._eval_variable``。
- 各内建/闭包调用复用 ``Interpreter._apply`` / ``_call_lambda``。
"""
from __future__ import annotations

import weakref
from typing import Any, Callable, Optional

from src import ast_nodes as ast
from src.interp_stack import (
    Machine, Frame, CallbackFrame, Dispatcher,
    ReturnSignal, ThrowSignal, BREAK, CONTINUE,
)


_MISSING = object()  # 哨兵：标记 env 中「该键原本不存在」
_ABSENT = object()   # 哨兵：标记 Scope 解析缓存中「父链已确认无此键」


class VersionedDict(dict):
    """带版本号的 dict：任何内容变更都会递增 ``_ver``。

    作为 ``Scope`` 的根容器（全局环境）时，``Scope`` 可比对 ``_ver`` 判断
    「全局环境是否在本作用域存活期间被改过」，从而及时失效解析缓存
    （尤其是负缓存——某键原本不存在、后来被定义）。
    """

    __slots__ = ("_ver",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ver = 0

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._ver += 1

    def __delitem__(self, key):
        super().__delitem__(key)
        self._ver += 1

    def pop(self, *args):
        result = super().pop(*args)
        self._ver += 1
        return result

    def popitem(self):
        result = super().popitem()
        self._ver += 1
        return result

    def clear(self):
        super().clear()
        self._ver += 1

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._ver += 1

    def setdefault(self, key, default=None):
        result = super().setdefault(key, default)
        self._ver += 1
        return result


class Scope:
    """叠加式作用域：本地写层 + 只读父层链。

    用于在**不拷贝**父环境的前提下为新函数体提供隔离的局部命名空间：

    - 读取：先查本地层，再沿父链回溯（``__getitem__``/``get``/``__contains__``）。
    - 写入：只落本地层（``__setitem__``），父层不受影响 → 退帧即丢弃。
    - ``items``/``keys``/``values``/``__iter__``/``__len__`` 合并父链（本地覆盖父层），
      使其可当作普通 dict 使用（兼容 ``dict(self.env.items())`` 等既有写法）。

    开销：建帧 O(arity)（仅写入参数），读取 O(层深)；不做任何父环境拷贝，
    因此深递归不再有 O(n²) 拷贝。
    """

    __slots__ = ("_local", "_parent", "_cache", "_ver", "_pver",
                 "_root", "_root_ver", "_root_ok", "_children", "__weakref__")

    def __init__(self, parent=None, local=None):
        self._parent = parent
        self._local = local if local is not None else {}
        # 解析缓存：name → 值 或 _ABSENT。链压缩（path compression）——
        # 首次查找后把「本地层已解析」的结果缓存，深层帧可 O(1) 命中父层缓存，
        # 避免每次变量 miss 都遍历整条父链（递归时链深=调用深度 → O(n²)）。
        self._cache: dict = {}
        # 版本号：本层每次变更 +1；子层通过比对父版本发现「祖先已变更」→
        # 自身缓存可能过期（尤其是负缓存 _ABSENT），据此精准失效。
        self._ver = 0
        self._pver = parent._ver if isinstance(parent, Scope) else 0
        # 链根容器（通常是全局环境 dict）与它的版本：全局环境被改写时，
        # 链上任意深度都能立即察觉（否则深层帧会读到过期的负缓存）。
        if isinstance(parent, Scope):
            self._root = parent._root
            self._root_ok = parent._root_ok
        else:
            self._root = parent
            self._root_ok = isinstance(parent, VersionedDict)
        self._root_ver = self._root._ver if self._root_ok else None
        # 子层订阅（弱引用，避免父子互相持有造成内存滞留）
        self._children: list = []
        if isinstance(parent, Scope):
            parent._subscribe(self)

    def _subscribe(self, child):
        """登记子层，便于本层变更时向下传播失效信号。"""
        kids = self._children
        if len(kids) > 8:
            kids[:] = [ref for ref in kids if ref() is not None]
        kids.append(weakref.ref(child))

    def _propagate(self):
        """把变更信号迭代式传播给所有后代层（迭代实现，避免深链宿主递归）。"""
        stack = list(self._children)
        while stack:
            ref = stack.pop()
            child = ref()
            if child is None:
                continue
            child._ver += 1
            child._cache.clear()
            stack.extend(child._children)

    def _resolve(self, key):
        """返回 ``(found, value)``：本地层 → 缓存 → 父层（缓存/字典）。

        缓存只在「链根容器可版本化」时启用：普通 dict 根无法感知外部改写，
        缓存会读到过期值（尤其负缓存）。此时退化为逐层回溯，但普通 dict 根
        只出现在用户自建/快照场景，引擎热路径的根都是 :class:`VersionedDict`。
        """
        local = self._local
        if key in local:
            return True, local[key]
        stale = False
        parent = self._parent
        if isinstance(parent, Scope) and parent._ver != self._pver:
            # 直接父层已变更 → 本层缓存（含负缓存）可能过期
            stale = True
            self._pver = parent._ver
        if self._root_ok:
            root_ver = self._root._ver
            if root_ver != self._root_ver:
                # 链根（全局环境）已变更 → 任意深度都可能读到过期值
                stale = True
                self._root_ver = root_ver
        if stale:
            self._cache.clear()
        cacheable = self._root_ok
        cache = self._cache
        hit = cache.get(key, _MISSING)
        if hit is not _MISSING:
            return (False, None) if hit is _ABSENT else (True, hit)
        if parent is None:
            if cacheable:
                cache[key] = _ABSENT
            return False, None
        if isinstance(parent, Scope):
            found, value = parent._resolve(key)
            if cacheable:
                cache[key] = value if found else _ABSENT
            return found, value
        if key in parent:
            value = parent[key]
            if cacheable:
                cache[key] = value
            return True, value
        if cacheable:
            cache[key] = _ABSENT
        return False, None

    def __getitem__(self, key):
        found, value = self._resolve(key)
        if found:
            return value
        raise KeyError(key)

    def _invalidate(self, key):
        """精确失效：把自身及祖先链上关于 ``key`` 的缓存条目移除。

        只影响该 key（而非整表清空），避免高频赋值把已建立的解析缓存整体作废。
        """
        node = self
        while isinstance(node, Scope):
            node._cache.pop(key, None)
            node = node._parent

    def __setitem__(self, key, value):
        self._local[key] = value
        # 仅本层写入 → 只失效本层该 key 的缓存（父层内容未变，其缓存仍有效）
        self._cache.pop(key, None)
        self._ver += 1
        self._propagate()

    def __delitem__(self, key):
        if key in self._local:
            del self._local[key]
            self._cache.pop(key, None)
            self._ver += 1
            self._propagate()
            return
        parent = self._parent
        if isinstance(parent, Scope):
            del parent[key]
            self._invalidate(key)
            return
        if parent is not None and key in parent:
            del parent[key]
            self._invalidate(key)
            return
        raise KeyError(key)

    def __contains__(self, key):
        return self._resolve(key)[0]

    def get(self, key, default=None):
        found, value = self._resolve(key)
        return value if found else default

    def __iter__(self):
        seen = set()
        scope = self
        while scope is not None:
            if isinstance(scope, Scope):
                keys = scope._local.keys()
                parent = scope._parent
            else:
                keys = scope.keys()
                parent = None
            for k in keys:
                if k not in seen:
                    seen.add(k)
                    yield k
            scope = parent

    def __len__(self):
        return sum(1 for _ in self)

    def keys(self):
        return list(self)

    def items(self):
        for k in self:
            yield k, self[k]

    def values(self):
        for k in self:
            yield self[k]

    def copy(self):
        return dict(self.items())

    def pop(self, key, default=_MISSING):
        if key in self._local:
            value = self._local.pop(key)
            self._cache.pop(key, None)
            self._ver += 1
            self._propagate()
            return value
        scope = self._parent
        while scope is not None:
            if isinstance(scope, Scope):
                if key in scope._local:
                    value = scope._local.pop(key)
                    scope._cache.pop(key, None)
                    scope._ver += 1
                    scope._propagate()
                    # 父层被删 → 本层及中间祖先缓存的 key 同样失效
                    self._invalidate(key)
                    return value
                scope = scope._parent
            else:
                if key in scope:
                    value = scope.pop(key)
                    self._invalidate(key)
                    return value
                if default is _MISSING:
                    raise KeyError(key)
                return default
        if default is _MISSING:
            raise KeyError(key)
        return default

    def setdefault(self, key, default=None):
        found, value = self._resolve(key)
        if found:
            return value
        self._local[key] = default
        self._cache.pop(key, None)
        self._ver += 1
        self._propagate()
        return default

    def update(self, other=(), **kwargs):
        if hasattr(other, "items"):
            other = other.items()
        for k, v in other:
            self._local[k] = v
            self._cache.pop(k, None)
        for k, v in kwargs.items():
            self._local[k] = v
            self._cache.pop(k, None)
        self._ver += 1
        self._propagate()

    def __repr__(self):
        return f"Scope({dict(self.items())!r})"


class _ValueHolder:
    __slots__ = ("value",)
    def __init__(self):
        self.value = None


class EngineMachine(Machine):
    """承载解释器引用的执行机。"""

    def __init__(self, engine: "StackEngine", max_steps=None):
        super().__init__(max_steps=max_steps)
        self.engine = engine
        self.interp = engine.interp
        self.bind(engine.dispatcher)


class StackEngine:
    """表达式求值的显式栈实现。"""

    def __init__(self, interp):
        self.interp = interp
        self.dispatcher = Dispatcher()
        self._register()
        self.machine = EngineMachine(self)

    # ---------- 入口 ----------

    def eval_value(self, node) -> Any:
        """求值单个表达式节点并返回结果（trampoline 驱动，无宿主递归）。"""
        holder = _ValueHolder()
        m = self.machine
        # 复位状态（引擎可被复用于多次顶层求值）
        m.frames.clear()
        m._pending = None
        m.return_value = None
        m._current_signal = None
        m.eval(node, CallbackFrame(m, lambda v: setattr(holder, "value", v)))
        self._drive(m)
        return holder.value

    def exec_value(self, node) -> None:
        """执行单个语句节点（trampoline 驱动）。"""
        m = self.machine
        m.frames.clear()
        m._pending = None
        m.return_value = None
        m._current_signal = None
        m.exec(node, CallbackFrame(m, lambda v: None))
        self._drive(m)

    def _drive(self, m: Machine) -> None:
        while m._pending is not None or m.frames:
            if m.max_steps is not None and m.steps > m.max_steps:
                raise RuntimeError("StackEngine 步数超限（疑似死循环）")
            m.steps += 1
            if m._pending is not None:
                instr = m._pending
                m._pending = None
                instr.step(m)
                continue
            if m.frames:
                m._resume_top()

    # ---------- 分派注册 ----------

    def _register(self) -> None:
        d = self.dispatcher
        # 字面量
        d.on_eval(ast.IntegerLit, self._lit)
        d.on_eval(ast.FloatLit, self._lit)
        d.on_eval(ast.StringLit, self._lit)
        d.on_eval(ast.BoolLit, self._lit)
        # 变量
        d.on_eval(ast.Variable, self._variable)
        # 二元 / 一元
        d.on_eval(ast.BinaryOp, self._binary)
        d.on_eval(ast.UnaryOp, self._unary)
        # 条件
        d.on_eval(ast.IfExpr, self._if_expr)
        d.on_eval(ast.IfStmt, self._if_stmt_expr)
        # 数据结构
        d.on_eval(ast.ListLiteral, self._list_literal)
        d.on_eval(ast.TupleExpr, self._tuple_expr)
        d.on_eval(ast.DictLiteral, self._dict_literal)
        # 访问
        d.on_eval(ast.IndexExpr, self._index)
        d.on_eval(ast.SliceExpr, self._slice)
        d.on_eval(ast.PathExpr, self._path)
        d.on_eval(ast.SafePathExpr, self._safe_path)
        # 类型/成员
        d.on_eval(ast.TypeOfExpr, self._typeof)
        d.on_eval(ast.IsExpr, self._is)
        d.on_eval(ast.Belongs, self._belongs)
        # 函数应用 / lambda
        d.on_eval(ast.FuncApp, self._func_app)
        d.on_eval(ast.Lambda, self._lambda)
        # 未迁移节点 → 回退解释器（暂仍递归）
        d.fallback_eval = self._fallback_eval
        d.fallback_exec = self._fallback_exec

    # ---------- 兜底 ----------

    def _fallback_eval(self, machine, node):
        machine.return_value_now(self.interp._eval(node))

    def _fallback_exec(self, machine, node):
        self.interp._exec_stmt(node)
        machine.return_value_now(None)

    # ---------- 字面量 / 变量 ----------

    def _lit(self, machine, node):
        machine.return_value_now(node.value)

    def _variable(self, machine, node):
        machine.return_value_now(self.interp._eval_variable(node))

    # ---------- 二元 / 一元 ----------

    _SHORT_CIRCUIT = {
        "&&": lambda a, b: a and b,
        "and": lambda a, b: a and b,
        "||": lambda a, b: a or b,
        "or": lambda a, b: a or b,
    }

    def _binary(self, machine, node):
        from src import custom_ops
        op = node.op
        # 用户自定义运算符：回退解释器（其副作用/分派复杂）
        if custom_ops.is_custom_op(op):
            machine.return_value_now(self.interp._eval_custom_op(node))
            return
        # 短路：先求左，再决定是否求右
        if op in ("&&", "and"):
            def after_l(lv):
                if not lv:
                    machine.return_value_now(lv)
                else:
                    machine.eval(node.right, CallbackFrame(machine, lambda rv: machine.return_value_now(lv and rv)))
            machine.eval(node.left, CallbackFrame(machine, after_l))
            return
        if op in ("||", "or"):
            def after_l(lv):
                if lv:
                    machine.return_value_now(lv)
                else:
                    machine.eval(node.right, CallbackFrame(machine, lambda rv: machine.return_value_now(lv or rv)))
            machine.eval(node.left, CallbackFrame(machine, after_l))
            return

        def after_l(lv):
            def after_r(rv):
                machine.return_value_now(
                    self.interp._apply_binary_values(op, lv, rv, site=node))
            machine.eval(node.right, CallbackFrame(machine, after_r))
        machine.eval(node.left, CallbackFrame(machine, after_l))

    def _unary(self, machine, node):
        op = node.op
        if op == "null":
            machine.return_value_now(None)
            return

        def after_v(v):
            machine.return_value_now(self._apply_unary(op, v))
        machine.eval(node.operand, CallbackFrame(machine, after_v))

    def _apply_unary(self, op, v):
        import math
        from src.interp import MathaRuntimeError, builtin_列表求和, builtin_列表求积
        if op == "-":
            return -v
        if op == "^" or op == "sqrt":
            r = v ** 0.5
            if isinstance(v, int) and not isinstance(v, bool) and r == int(r):
                r = int(r)
            return r
        if op == "cbrt":
            r = -((-v) ** (1 / 3)) if v < 0 else v ** (1 / 3)
            if isinstance(v, int) and not isinstance(v, bool):
                ri = round(r)
                if ri * ri * ri == v:
                    r = ri
            return r
        if op == "sum":
            return builtin_列表求和(v)
        if op == "prod":
            return builtin_列表求积(v)
        if op == "++":
            if isinstance(v, (int, float)):
                return v + 1
            raise MathaRuntimeError(f"++ 仅适用于数值，实际 {type(v).__name__}")
        if op == "--":
            if isinstance(v, (int, float)):
                return v - 1
            raise MathaRuntimeError(f"-- 仅适用于数值，实际 {type(v).__name__}")
        if op == "!":
            return not v
        if op == "not":
            return not v
        if op == "angle":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise MathaRuntimeError(f"<< 角度仅适用于数值，实际 {type(v).__name__}")
            return math.radians(v)
        if op == "~":
            if isinstance(v, int):
                return ~int(v)
            raise MathaRuntimeError(f"~ 仅适用于整数，实际 {type(v).__name__}")
        raise MathaRuntimeError(f"未知一元运算符 '{op}'")

    # ---------- 条件 ----------

    def _if_expr(self, machine, node):
        def after_cond(c):
            branch = node.then if c else node.else_
            # 分支若是代码块，回退解释器块尾值逻辑；否则引擎求值
            if isinstance(branch, ast.CodeBlock):
                machine.return_value_now(self.interp._eval_block_value(branch))
            else:
                machine.eval(branch, CallbackFrame(machine, machine.return_value_now))
        machine.eval(node.cond, CallbackFrame(machine, after_cond))

    def _if_stmt_expr(self, machine, node):
        def after_cond(c):
            branch = node.then_block if c else node.else_block
            machine.return_value_now(self.interp._eval_block_value(branch))
        machine.eval(node.cond, CallbackFrame(machine, after_cond))

    # ---------- 数据结构 ----------

    def _list_literal(self, machine, node):
        self._eval_seq(machine, node.elements, lambda vs: list(vs))

    def _tuple_expr(self, machine, node):
        self._eval_seq(machine, node.elements, lambda vs: tuple(vs))

    def _eval_seq(self, machine, items, build):
        """依次求值 ``items``，完成后用 ``build(values)`` 构造结果。"""
        if not items:
            machine.return_value_now(build([]))
            return
        acc: list = []

        def step(i):
            if i >= len(items):
                machine.return_value_now(build(acc))
                return

            def after(v):
                acc.append(v)
                step(i + 1)
            machine.eval(items[i], CallbackFrame(machine, after))
        step(0)

    def _dict_literal(self, machine, node):
        keys, values = node.keys, node.values
        if not keys:
            machine.return_value_now({})
            return
        acc: dict = {}

        def step(i):
            if i >= len(keys):
                machine.return_value_now(acc)
                return
            k = keys[i]

            def after_v(v):
                acc[k if isinstance(k, ast.Variable) else kk[0]] = v
                step(i + 1)

            if isinstance(k, ast.Variable):
                kk = [None]

                def after_vv(v, _k=k.name):
                    acc[_k] = v
                    step(i + 1)
                machine.eval(values[i], CallbackFrame(machine, after_vv))
            else:
                kk = [None]

                def after_k(kv):
                    def after_val(v):
                        acc[kv] = v
                        step(i + 1)
                    machine.eval(values[i], CallbackFrame(machine, after_val))
                machine.eval(k, CallbackFrame(machine, after_k))
        step(0)

    # ---------- 访问 ----------

    def _index(self, machine, node):
        def after_c(container):
            def after_i(index):
                machine.return_value_now(self._do_index(container, index))
            machine.eval(node.index, CallbackFrame(machine, after_i))
        machine.eval(node.container, CallbackFrame(machine, after_c))

    def _do_index(self, container, index):
        from src.interp import MathaRuntimeError, _StructInstance
        if isinstance(container, (list, tuple, str)) and isinstance(index, int):
            return container[index]
        if isinstance(container, _StructInstance) and isinstance(index, str):
            return container[index]
        if isinstance(container, dict):
            try:
                return container.get(index)
            except TypeError:
                raise MathaRuntimeError(f"索引操作不支持: dict[{index}]（不可哈希的键）")
        raise MathaRuntimeError(f"索引操作不支持: {type(container).__name__}[{index}]")

    def _slice(self, machine, node):
        def after_c(container):
            state = {"start": None, "end": None}

            def do_end():
                from src.interp import MathaRuntimeError
                if isinstance(container, (list, tuple, str)):
                    machine.return_value_now(container[state["start"]:state["end"]])
                else:
                    raise MathaRuntimeError(
                        f"切片操作不支持: {type(container).__name__}[{state['start']}:{state['end']}]")

            def after_start(s):
                state["start"] = s
                if node.end is None:
                    do_end()
                else:
                    machine.eval(node.end, CallbackFrame(machine, after_end))

            def after_end(e):
                state["end"] = e
                do_end()

            if node.start is None:
                do_end()
            else:
                machine.eval(node.start, CallbackFrame(machine, after_start))
        machine.eval(node.container, CallbackFrame(machine, after_c))

    def _path(self, machine, node):
        def after_l(left_val):
            field_name = node.right
            if isinstance(left_val, tuple) and isinstance(field_name, int):
                from src.interp import MathaRuntimeError
                if 0 <= field_name < len(left_val):
                    machine.return_value_now(left_val[field_name])
                else:
                    raise MathaRuntimeError(f"元组索引越界: {field_name}")
                return
            if isinstance(left_val, dict) and isinstance(field_name, str):
                v = left_val.get(field_name)
                if v is not None:
                    machine.return_value_now(v)
                    return
                if field_name in self.interp.builtins:
                    machine.return_value_now(self.interp.builtins[field_name])
                    return
                machine.return_value_now(None)
                return
            from src.interp import MathaRuntimeError, _StructInstance
            try:
                machine.return_value_now(getattr(left_val, field_name))
            except AttributeError:
                if isinstance(left_val, _StructInstance):
                    machine.return_value_now(None)
                    return
                raise MathaRuntimeError(
                    f"属性访问失败: {type(left_val).__name__}.{field_name}")
        machine.eval(node.left, CallbackFrame(machine, after_l))

    def _safe_path(self, machine, node):
        def after_l(left_val):
            from src.interp import MathaRuntimeError
            if left_val is None:
                machine.return_value_now(None)
                return
            if node.is_index:
                def after_i(idx):
                    if isinstance(left_val, (list, tuple, str)) and isinstance(idx, int):
                        machine.return_value_now(left_val[idx])
                    else:
                        raise MathaRuntimeError(
                            f"?. 下标访问失败: {type(left_val).__name__}[{idx}]")
                machine.eval(node.right, CallbackFrame(machine, after_i))
            else:
                try:
                    machine.return_value_now(getattr(left_val, node.right))
                except AttributeError:
                    machine.return_value_now(None)
        machine.eval(node.left, CallbackFrame(machine, after_l))

    # ---------- 类型 / 成员 ----------

    def _typeof(self, machine, node):
        from src.interp import builtin_typeof
        machine.eval(node.operand, CallbackFrame(
            machine, lambda v: machine.return_value_now(builtin_typeof(v))))

    def _is(self, machine, node):
        def after_l(lv):
            machine.eval(node.right, CallbackFrame(
                machine, lambda rv: machine.return_value_now(lv is rv)))
        machine.eval(node.left, CallbackFrame(machine, after_l))

    def _belongs(self, machine, node):
        from src.interp import MathaRuntimeError
        def after_l(lv):
            def after_r(rv):
                if isinstance(rv, (list, tuple, str, dict, set)):
                    machine.return_value_now(lv in rv)
                else:
                    raise MathaRuntimeError(
                        f"∈ 右侧需为序列/集合/字典，实际 {type(rv).__name__}")
            machine.eval(node.right, CallbackFrame(machine, after_r))
        machine.eval(node.left, CallbackFrame(machine, after_l))

    # ---------- 函数应用 / lambda（Layer 2：堆帧栈） ----------

    def _lambda(self, machine, node):
        interp = self.interp
        matha_env = getattr(interp, "_matha_env", None)
        if matha_env is None:
            matha_env = list(interp.env.items())
        machine.return_value_now(("__closure__", node, matha_env))

    def _func_app(self, machine, node):
        interp = self.interp
        # 自动定义功能（与 _eval_func_app 对齐）
        fnode = node.func
        if (isinstance(fnode, ast.Variable) and "." not in fnode.name
                and not fnode.name.startswith("_") and interp._heal_enabled()
                and interp._is_undefined(fnode.name)):
            interp._auto_define_function(fnode.name)

        def after_fn(fn):
            def after_arg(arg):
                self.apply_callable(machine, fn, [arg])
            machine.eval(node.arg, CallbackFrame(machine, after_arg))
        machine.eval(node.func, CallbackFrame(machine, after_fn))

    def apply_callable(self, machine, func, args: list) -> None:
        """在机器帧栈上应用可调用值（`_apply` 的迭代版，支持完整参数列表）。

        分派顺序严格对齐 ``Interpreter._apply``（interp.py:3201）：
        ① Python callable ② ``_RecPlaceholder`` ③ ``ast.FuncDef``
        ④ ``("__closure__", …)`` 闭包元组。**callable 必须最先判定**——
        柯里化 partial（``_curry_module`` 返回的 lambda）是纯 Python
        callable，若让闭包元组分支先行，会把 partial 误当闭包解构，导致
        把 ``(dependent, args)`` 元组塞进真正的函数槽（→ 'tuple' object
        is not callable）。
        """
        interp = self.interp
        from src.interp import _RecPlaceholder, MathaRuntimeError
        # ① Python 内建 / 柯里化 partial / 任意纯 callable：按旧引擎
        #    _apply 语义逐参位置调用，绝不打包成元组。
        if callable(func):
            result = func
            for a in args:
                result = result(a)
            machine.return_value_now(result)
            return
        # ② 递归占位符：转发参数（与 _apply 一致）
        if isinstance(func, _RecPlaceholder):
            result = func
            for a in args:
                result = interp._apply(result, a)
            machine.return_value_now(result)
            return
        # ③ FuncDef：函数体 params/body 落在机器帧栈上（不递归）
        if isinstance(func, ast.FuncDef):
            self.call_lambda(machine, func.body.params, func.body.body,
                             self.interp.env, args)
            return
        # ④ Matha 闭包元组：4 元组 (params, body, env) 或 3 元组 (lam, env)
        if isinstance(func, tuple) and func and func[0] == "__closure__":
            if len(func) == 4:
                params, body, captured = func[1], func[2], func[3]
            else:
                _, lam_node, captured = func
                params, body = lam_node.params, lam_node.body
            self.call_lambda(machine, params, body, captured, args)
            return
        raise MathaRuntimeError(f"不可调用的值: {func!r}")

    def call_lambda(self, machine, params, body, captured, args: list) -> None:
        """在机器帧栈上调用 lambda 体（`_call_lambda` 的迭代版）。

        只负责「进入函数」：压入一个 ``_LambdaFrame`` 处理环境恢复 + 尾部
        多余参数；函数体经 ``machine.eval`` 求值（表达式体）或回退解释器
        （块体，尚未迁移）——两者都不构成宿主递归调用链。
        """
        interp = self.interp

        # ---- 偏应用：参数不足 → 返回闭包 ----
        if len(args) < len(params):
            snap = self._env_snapshot(interp, captured)
            for p, a in zip(params, args):
                snap[interp._param_name(p)] = a
            remaining = params[len(args):]
            if len(remaining) > 1:
                b = body
                while isinstance(b, ast.Lambda):
                    b = b.body
            else:
                b = body
            machine.return_value_now(("__closure__", remaining, b, snap))
            return

        # ---- 完整应用：引用传递 + 作用域快照（无 dict/list 拷贝）----
        frame = _LambdaFrame(machine, self, body, params, args, captured)
        # 函数体的结果直接回填到 _LambdaFrame.resume。
        # 语句块体（CodeBlock）暂由解释器递归实现兜底，需把其 _ReturnException
        # 转换为显式 ReturnSignal，交由 _LambdaFrame 消费（避免宿主异常外泄）。
        if isinstance(body, ast.CodeBlock):
            def run_body(_machine=None):
                from src.interp import _ReturnException
                try:
                    machine.return_value_now(interp._eval(body))
                except _ReturnException as e:
                    frame.skip_extras = True
                    machine.return_value_now(e.value)
                except Exception as e:  # noqa: BLE001
                    frame.pending_exc = e
                    machine.return_value_now(None)
            machine.frames.append(frame)
            machine.call(run_body)
        else:
            machine.eval(body, frame)

    # ---------- 环境：引用传递 + 作用域快照（Shadow / undo-log） ----------

    @staticmethod
    def _env_snapshot(interp, captured):
        """按值构造一个 env 字典（仅偏应用/闭包捕获路径使用，非热路径）。

        ``captured`` 可能是 dict（引擎闭包捕获）或 list-of-tuples（Matha env）。
        """
        if isinstance(captured, dict):
            snap = dict(captured)
        elif isinstance(captured, list):
            snap = {}
            for k, v in captured:
                snap[k] = v
        else:
            snap = dict(getattr(interp, "env", {}) or {})
        return snap

    @staticmethod
    def _scope_parent(captured):
        """把 ``captured``（dict / list-of-tuples / Scope / None）归一化为父层映射。

        - list-of-tuples（Matha 自举闭包）→ :class:`VersionedDict`（一次性，O(len)）。
        - dict → 带版本号的副本（快照语义与经典 ``dict(captured)`` 一致，
          同时让 Scope 的链根可版本化 → 缓存能正确感知改写）。
        - Scope → 直接引用（O(1)，热路径）。
        - None → None（无父层，仅内建/函数表可见）。
        """
        if isinstance(captured, list):
            # 直接以 C 层 dict 构造器复制（避免逐项走 Python 层 __setitem__）
            return VersionedDict(captured)
        if isinstance(captured, dict) and not isinstance(captured, VersionedDict):
            snap = VersionedDict(captured)
            return snap
        return captured


class _LambdaFrame(Frame):
    """lambda 调用帧：叠加式作用域（``Scope``）——隔离写、O(1) 建帧。

    进入时把 ``interp.env`` 替换为 ``Scope(parent=captured, local=params)``：
    函数体的局部赋值写入本地层（不泄漏给调用者）；读取沿父链回溯到闭包捕获
    环境。退出时把 ``interp.env`` 还原为进入前的值——无任何父环境拷贝。
    """

    __slots__ = ("engine", "body", "saved_matha_env", "extra",
                 "pending_exc", "_saved_depth", "skip_extras",
                 "params", "args", "_saved_env", "_matha_len")

    def __init__(self, machine, engine, body, params, args, captured=None):
        super().__init__(machine)
        self.engine = engine
        self.body = body
        self.pending_exc = None
        self.skip_extras = False
        interp = engine.interp
        self.params = params
        self.args = args
        self.extra = args[len(params):]
        # 叠加式作用域：父层 = 闭包捕获环境（引用传递），本地层 = 参数绑定。
        parent = engine._scope_parent(captured)
        local = {}
        for p, a in zip(params, args):
            local[interp._param_name(p)] = a
        self._saved_env = interp.env
        interp.env = Scope(parent=parent, local=local)
        # matha_env（list）：引用传递，原地追加参数对，退出时截断
        self._matha_len = None
        me = getattr(interp, "_matha_env", None)
        if isinstance(me, list):
            self._matha_len = len(me)
            me.extend((interp._param_name(p), a) for p, a in zip(params, args))
        self._saved_depth = interp._depth
        if interp.debug:
            interp._depth += 1

    def _restore(self):
        interp = self.engine.interp
        interp.env = self._saved_env
        if self._matha_len is not None:
            me = getattr(interp, "_matha_env", None)
            if isinstance(me, list) and len(me) >= self._matha_len:
                del me[self._matha_len:]
        interp._depth = self._saved_depth

    def resume(self, value):
        if self.pending_exc is not None:
            self._restore()
            raise self.pending_exc
        self._restore()
        # 多余参数：仅当结果是可调用闭包时继续应用
        if self.extra and not self.skip_extras:
            for i, a in enumerate(self.extra):
                is_closure = callable(value) or (
                    isinstance(value, tuple) and value and value[0] == "__closure__")
                if is_closure:
                    if i == len(self.extra) - 1:
                        # 最后一个多余参数：在机器帧栈上应用（不递归）
                        self.engine.apply_callable(self.machine, value, [a])
                        return
                    # 多个多余参数：偶发路径，回退解释器递归实现
                    value = self.engine.interp._apply(value, a)
                    continue
                break
        self.machine.return_value_now(value)

    def handle(self, signal):
        if isinstance(signal, ReturnSignal):
            self._restore()
            self.machine.return_value_now(signal.value)
            return True
        return False


__all__ = ["StackEngine", "EngineMachine", "Scope", "VersionedDict"]
