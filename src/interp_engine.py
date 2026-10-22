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

from typing import Any, Callable, Optional

from src import ast_nodes as ast
from src.interp_stack import (
    Machine, Frame, CallbackFrame, Dispatcher,
    ReturnSignal, ThrowSignal, BREAK, CONTINUE,
)


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
                machine.return_value_now(self.interp._apply_binary_values(op, lv, rv))
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
        saved_matha_env = getattr(interp, "_matha_env", None)
        if isinstance(captured, list):
            local = dict(captured)
            cur_matha_env = captured
        else:
            local = dict(captured)
            cur_matha_env = getattr(interp, "_matha_env", None)
            if cur_matha_env is None:
                cur_matha_env = list(local.items())
            if "env" in local and not isinstance(local["env"], list):
                local["env"] = list(local["env"].items()) if isinstance(local["env"], dict) else local["env"]

        # ---- 偏应用：参数不足 → 返回闭包 ----
        if len(args) < len(params):
            for p, a in zip(params, args):
                local[interp._param_name(p)] = a
            remaining = params[len(args):]
            new_pairs = [(interp._param_name(p), a) for p, a in zip(params, args)]
            if isinstance(captured, list):
                captured.extend(new_pairs)
                cur_matha_env = captured
            elif isinstance(cur_matha_env, list):
                cur_matha_env = list(cur_matha_env) + new_pairs
            else:
                cur_matha_env = list(cur_matha_env.items()) + new_pairs
            if len(remaining) > 1:
                b = body
                while isinstance(b, ast.Lambda):
                    b = b.body
            else:
                b = body
            machine.return_value_now(("__closure__", remaining, b, cur_matha_env))
            return

        # ---- 完整应用 ----
        for p, a in zip(params, args):
            local[interp._param_name(p)] = a
        if isinstance(cur_matha_env, list):
            cur_matha_env = list(cur_matha_env) + [
                (interp._param_name(p), a) for p, a in zip(params, args)]
        extra = args[len(params):]

        frame = _LambdaFrame(machine, self, body, local, cur_matha_env,
                             saved_matha_env, extra)
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


class _LambdaFrame(Frame):
    """lambda 调用帧：恢复环境、处理 return 信号、应用多余参数。"""

    __slots__ = ("engine", "body", "saved_env", "saved_matha_env", "extra",
                 "pending_exc", "_saved_depth", "skip_extras")

    def __init__(self, machine, engine, body, local_env, matha_env,
                 saved_matha_env, extra):
        super().__init__(machine)
        self.engine = engine
        self.body = body
        self.pending_exc = None
        self.skip_extras = False
        interp = engine.interp
        self.saved_env = interp.env
        self.saved_matha_env = saved_matha_env
        self.extra = extra
        interp.env = local_env
        interp._matha_env = matha_env
        self._saved_depth = interp._depth
        if interp.debug:
            interp._depth += 1

    def _restore(self):
        interp = self.engine.interp
        interp.env = self.saved_env
        interp._matha_env = self.saved_matha_env
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


__all__ = ["StackEngine", "EngineMachine"]
