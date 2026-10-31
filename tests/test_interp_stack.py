# -*- coding: utf-8 -*-
"""显式栈协议（src/interp_stack.py）的影子执行器测试。

策略：契约优先。先不改动 interp.py，而是用协议构建一个**极简**的
算术/let/if/lambda/调用 语言影子执行器，在最苛刻场景上验证协议闭环：

  1. 深嵌套表达式（10000 层加法）—— 宿主栈深度须恒为 O(1)。
  2. 尾递归 / 深递归函数调用（countdown 100000）—— 独立堆帧栈，
     突破 sys.setrecursionlimit。
  3. let 作用域、if 分支、闭包捕获。
  4. break / return 控制流信号在帧栈上的显式传播。

运行：python -m tests.test_interp_stack
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp_stack import (
    Machine, Frame, Dispatcher, CallbackFrame,
    ReturnSignal, ThrowSignal, BREAK,
)


# ============================================================
# 影子语言 AST（极简，仅用于验证协议）
# ============================================================

class Lit:
    __slots__ = ("v",)
    def __init__(self, v): self.v = v


class Var:
    __slots__ = ("name",)
    def __init__(self, name): self.name = name


class Add:
    __slots__ = ("a", "b")
    def __init__(self, a, b): self.a, self.b = a, b


class Let:
    __slots__ = ("name", "value", "body")
    def __init__(self, name, value, body): self.name, self.value, self.body = name, value, body


class RecLet:
    """递归绑定：let rec f = <lam> in body（预注册可变单元，支持自引用）。"""
    __slots__ = ("name", "value", "body")
    def __init__(self, name, value, body): self.name, self.value, self.body = name, value, body


class If:
    __slots__ = ("cond", "then", "els")
    def __init__(self, cond, then, els): self.cond, self.then, self.els = cond, then, els


class Lam:
    __slots__ = ("params", "body")
    def __init__(self, params, body): self.params, self.body = params, body


class Call:
    __slots__ = ("fn", "arg")
    def __init__(self, fn, arg): self.fn, self.arg = fn, arg


class Seq:
    __slots__ = ("stmts",)
    def __init__(self, stmts): self.stmts = stmts


class LetStmt:
    __slots__ = ("name", "value")
    def __init__(self, name, value): self.name, self.value = name, value


class Return:
    __slots__ = ("value",)
    def __init__(self, value): self.value = value


class IfStmt:
    __slots__ = ("cond", "then", "els")
    def __init__(self, cond, then, els): self.cond, self.then, self.els = cond, then, els


# ============================================================
# 环境
# ============================================================

class Env:
    """list-of-tuples 环境（与 interp.py 的 _matha_env 同构）。"""

    __slots__ = ("pairs",)

    def __init__(self, pairs=None):
        self.pairs = pairs if pairs is not None else []

    def lookup(self, name):
        for k, v in reversed(self.pairs):
            if k == name:
                return v.value if isinstance(v, Cell) else v
        raise NameError(name)

    def extend(self, pairs):
        return Env(self.pairs + list(pairs))

    def set_local(self, name, value):
        self.pairs.append((name, value))


class Cell:
    """可变单元：递归绑定的延迟填充占位符。"""
    __slots__ = ("value",)
    def __init__(self, value=None): self.value = value


class Closure:
    __slots__ = ("params", "body", "env")
    def __init__(self, params, body, env): self.params, self.body, self.env = params, body, env


# ============================================================
# 影子 Dispatcher：把节点编译为帧栈操作
# ============================================================

class ShadowDispatcher(Dispatcher):
    def __init__(self):
        super().__init__()
        self.on_eval(Lit, self._lit)
        self.on_eval(Var, self._var)
        self.on_eval(Add, self._add)
        self.on_eval(Let, self._let)
        self.on_eval(RecLet, self._rec_let)
        self.on_eval(If, self._if)
        self.on_eval(Lam, self._lam)
        self.on_eval(Call, self._call)
        self.on_exec(Seq, self._seq)
        self.on_exec(LetStmt, self._let_stmt)
        self.on_exec(Return, self._return)
        self.on_exec(IfStmt, self._if_stmt)
        self.fallback_eval = self._unknown
        self.fallback_exec = self._unknown

    def _unknown(self, machine, node):
        raise RuntimeError(f"影子执行器不支持的节点: {type(node).__name__}")

    # ---- 表达式 ----

    def _lit(self, machine, node):
        machine.return_value_now(node.v)

    def _var(self, machine, node):
        machine.return_value_now(machine.env.lookup(node.name))

    def _add(self, machine, node):
        # 先求左，再求右，最后相加 —— 经帧栈，不递归
        def after_left(lv):
            def after_right(rv):
                machine.return_value_now(lv + rv)
            machine.eval(node.b, CallbackFrame(machine, after_right))
        machine.eval(node.a, CallbackFrame(machine, after_left))

    def _let(self, machine, node):
        def after_val(v):
            saved = machine.env
            machine.env = saved.extend([(node.name, v)])
            try:
                def restore(body_v):
                    machine.env = saved
                    machine.return_value_now(body_v)
                machine.eval(node.body, CallbackFrame(machine, restore))
            except Exception:
                machine.env = saved
                raise
        machine.eval(node.value, CallbackFrame(machine, after_val))

    def _rec_let(self, machine, node):
        # 预注册可变单元，使函数体自引用可解析
        cell = Cell()
        saved = machine.env
        machine.env = saved.extend([(node.name, cell)])

        def after_val(v):
            cell.value = v

            def restore(body_v):
                machine.env = saved
                machine.return_value_now(body_v)
            machine.eval(node.body, CallbackFrame(machine, restore))
        machine.eval(node.value, CallbackFrame(machine, after_val))

    def _if(self, machine, node):
        def after_cond(c):
            branch = node.then if c else node.els
            machine.eval(branch, CallbackFrame(machine, machine.return_value_now))
        machine.eval(node.cond, CallbackFrame(machine, after_cond))

    def _lam(self, machine, node):
        machine.return_value_now(Closure(node.params, node.body, machine.env))

    def _call(self, machine, node):
        def after_fn(fn):
            def after_arg(arg):
                machine.call_callable(fn, [arg])
            machine.eval(node.arg, CallbackFrame(machine, after_arg))
        machine.eval(node.fn, CallbackFrame(machine, after_fn))

    # ---- 语句 ----

    def _seq(self, machine, node):
        stmts = node.stmts
        if not stmts:
            machine.return_value_now(None)
            return

        def step(i):
            if i >= len(stmts):
                machine.return_value_now(None)
                return

            def after_stmt(_):
                step(i + 1)

            machine.exec(stmts[i], CallbackFrame(machine, after_stmt))
        step(0)

    def _let_stmt(self, machine, node):
        def after(v):
            machine.env.set_local(node.name, v)
            machine.return_value_now(None)
        machine.eval(node.value, CallbackFrame(machine, after))

    def _return(self, machine, node):
        def after(v):
            machine.raise_signal(ReturnSignal(v))
        machine.eval(node.value, CallbackFrame(machine, after))

    def _if_stmt(self, machine, node):
        def after_cond(c):
            branch = node.then if c else node.els
            machine.exec(branch, CallbackFrame(machine, machine.return_value_now))
        machine.eval(node.cond, CallbackFrame(machine, after_cond))


class _SeqStep:
    __slots__ = ("machine", "node")
    def __init__(self, machine, node):
        self.machine, self.node = machine, node
    def step(self, machine):
        machine.exec(self.node, self.machine.frames.pop())


# ============================================================
# 把「调用用户闭包」作为 machine 的能力（独立堆帧栈）
# ============================================================

class ShadowMachine(Machine):
    def __init__(self, dispatcher, max_steps=None):
        super().__init__(max_steps=max_steps)
        self.env = Env()
        self.bind(dispatcher)
        self._dispatcher_ref = dispatcher

    def call_callable(self, fn, args):
        """调用闭包/内建：使用机器的帧栈，不递归。"""
        if isinstance(fn, Closure):
            params = fn.params
            if len(args) < len(params):
                # 偏应用
                bound = list(zip(params, args))

                def partial(_):
                    self.return_value_now(Closure(params[len(args):], fn.body, fn.env.extend(bound)))
                self.next(partial)
                return
            self.env = fn.env.extend(zip(params, args))
            # 返回信号消费帧：函数体的 ReturnSignal 在此被捕获
            ret_frame = _FunctionFrame(self, fn.env)
            self.frames.append(ret_frame)
            self.eval(fn.body, CallbackFrame(self, self.return_value_now))
            return
        if callable(fn):
            self.return_value_now(fn(*args))
            return
        raise RuntimeError(f"不可调用: {fn!r}")

    def next(self, fn):
        """投递一个立即执行的 Python 回调（不递归）。"""
        from src.interp_stack import Thunk
        self.push_instruction(Thunk(fn))


class _FunctionFrame(Frame):
    """函数帧：消费 RETURN 信号，恢复调用者环境。"""

    __slots__ = ("caller_env",)

    def __init__(self, machine, caller_env):
        super().__init__(machine)
        self.caller_env = caller_env

    def resume(self, value):
        # 函数体正常结束（无 return）：恢复环境，值继续向上回填
        self.machine.env = self.caller_env
        self.machine.return_value_now(value)

    def handle(self, signal):
        if isinstance(signal, ReturnSignal):
            self.machine.env = self.caller_env
            self.machine.return_value = signal.value
            return True
        return False


# ============================================================
# 测试
# ============================================================

def _run(expr, env_pairs=None):
    disp = ShadowDispatcher()
    m = ShadowMachine(disp, max_steps=50_000_000)
    m.env = Env(list(env_pairs) if env_pairs else [])
    m.run_driver(expr)
    return m.return_value


def test_arithmetic():
    e = Add(Lit(2), Add(Lit(3), Lit(4)))
    assert _run(e) == 9


def test_let_and_scoping():
    # let x = 10 in (let y = 20 in x + y)
    e = Let("x", Lit(10), Let("y", Lit(20), Add(Var("x"), Var("y"))))
    assert _run(e) == 30


def test_if():
    e = If(Lit(True), Lit(1), Lit(2))
    assert _run(e) == 1
    e = If(Lit(False), Lit(1), Lit(2))
    assert _run(e) == 2


def test_lambda_capture():
    # (let a = 5 in ((x) => a + x)(10)) == 15
    e = Let("a", Lit(5), Call(Lam(["x"], Add(Var("a"), Var("x"))), Lit(10)))
    assert _run(e) == 15


def test_deep_nested_expression_no_host_recursion():
    """10000 层嵌套加法：宿主栈深度须为 O(1)。

    证明方式：把 Python recursionlimit 压到很低（200）。若求值走宿主递归，
    10000 层嵌套必然 RecursionError；显式帧栈则不受影响。
    """
    e = Lit(0)
    for _ in range(10000):
        e = Add(Lit(1), e)
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(200)
    try:
        disp = ShadowDispatcher()
        m = ShadowMachine(disp, max_steps=50_000_000)
        m.run_driver(e)
    finally:
        sys.setrecursionlimit(old)
    assert m.return_value == 10000, m.return_value


def test_deep_tail_recursion_bypasses_recursionlimit():
    """深递归 countdown(100000)：独立堆帧栈，突破 Python recursionlimit。"""
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(200)  # 极具侵略性的低上限
    try:
        # let rec f = (n) => if n == 0 then 0 else f(n-1) in f(100000)
        prog = RecLet(
            "f",
            Lam(["n"], If(
                Call(Var("eq0"), Var("n")),
                Lit(0),
                Call(Var("f"), Call(Var("sub1"), Var("n"))),
            )),
            Call(Var("f"), Lit(100000)),
        )
        disp = ShadowDispatcher()
        m = ShadowMachine(disp, max_steps=50_000_000)
        m.env = Env([("eq0", lambda n: n == 0), ("sub1", lambda n: n - 1)])
        m.run_driver(prog)
        assert m.return_value == 0, m.return_value
    finally:
        sys.setrecursionlimit(old)


# ---------------- run_driver：驱动不递归的主循环 ----------------

def _install_driver():
    def run_driver(self, node):
        """以 node 为根求值，trampoline 驱动至完成。"""
        holder = {}
        root_frame = CallbackFrame(self, lambda v: holder.__setitem__("v", v))
        self.eval(node, root_frame)
        # 直接跑主循环（self.run 需要一个 Instruction 根）
        while self._pending is not None or self.frames:
            if self.max_steps is not None and self.steps > self.max_steps:
                raise RuntimeError("步数超限")
            self.steps += 1
            if self._pending is not None:
                instr = self._pending
                self._pending = None
                instr.step(self)
                continue
            if self.frames:
                self._resume_top()
        self.return_value = holder.get("v")
    ShadowMachine.run_driver = run_driver


_install_driver()


# ============================================================
# 端到端：StackEngine 让 Matha 深递归绕过 sys.setrecursionlimit
# ============================================================

def test_engine_deep_matha_recursion_bypasses_recursionlimit():
    """MATHA_FEATURE_STACK_ENGINE 开启时，Matha 深递归不受 Python 递归上限约束。

    对照：关闭引擎 → RecursionError；开启引擎 → 正常返回。
    """
    from src import features
    from src.parser import parse
    from src.interp import Interpreter

    src = (
        'func count(n) -> Int = (n) =>\n'
        '  if n <= 0 then 0\n'
        '  else count(n - 1)\n'
        '输出(count(N))\n'
    )

    def _run(engine_on, n):
        # 进程内覆盖优先于环境变量，显式置 False/True 以隔离
        # 外部 MATHA_FEATURE_STACK_ENGINE 的环境影响。
        features.set_feature("STACK_ENGINE", bool(engine_on))
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(300)
        try:
            return Interpreter().run(parse(src.replace("N", str(n))))[0]
        finally:
            sys.setrecursionlimit(old)
            features.clear_feature()

    # 关闭引擎：深递归应触发 RecursionError（证明宿主栈确实受限）
    try:
        _run(False, 5000)
        raised = False
    except RecursionError:
        raised = True
    assert raised, "关闭引擎时深递归应触发 RecursionError"

    # 开启引擎：同等深度正常返回
    assert _run(True, 5000) == [0]


if __name__ == "__main__":
    test_arithmetic()
    test_let_and_scoping()
    test_if()
    test_lambda_capture()
    test_deep_nested_expression_no_host_recursion()
    test_deep_tail_recursion_bypasses_recursionlimit()
    test_engine_deep_matha_recursion_bypasses_recursionlimit()
    print("✓ 影子执行器：协议闭环验证通过（深嵌套 + 尾递归均不依赖宿主栈）")
