# -*- coding: utf-8 -*-
"""
Matha 多范式引擎 v1.3.0
========================
融合函数式/命令式/逻辑式/符号式编程范式的统一执行引擎。

功能：
  • Functional  — 纯函数式计算（lambda/柯里化/高阶函数）
  • Imperative  — 命令式状态机（变量/循环/分支）
  • Symbolic    — 符号代数（表达式/微积分/简化）
  • Logic       — 逻辑推理（规则/约束/推导）
  • Paradigm    — 范式切换器（根据任务自动选择）
"""
from __future__ import annotations
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List, Tuple
from enum import Enum

# 确保 src/ 目录在路径中（直接运行模块时）
if __name__ == "__main__" and "src" not in sys.path:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

logger = logging.getLogger("matha.paradigm")

# ═══════════════════════════════════════════════════════════════════════════════
#  范式枚举
# ═══════════════════════════════════════════════════════════════════════════════

class Paradigm(str, Enum):
    FUNCTIONAL = "functional"
    IMPERATIVE = "imperative"
    SYMBOLIC   = "symbolic"
    LOGIC      = "logic"
    DATAFLOW   = "dataflow"
    OBJECT     = "object"


@dataclass
class ParadigmContext:
    """范式执行上下文。"""
    paradigm: Paradigm
    state: Dict[str, Any] = field(default_factory=dict)
    bindings: Dict[str, Any] = field(default_factory=dict)
    return_value: Any = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  函数式引擎
# ═══════════════════════════════════════════════════════════════════════════════

class FunctionalEngine:
    """纯函数式计算引擎：lambda、柯里化、高阶函数、不可变状态。"""

    def __init__(self):
        self._env: Dict[str, Any] = {}
        logger.info("  [函数式] 引擎初始化")

    def eval(self, expr: Any, env: Dict = None) -> Any:
        """求值表达式。"""
        if env is None:
            env = dict(self._env)
        if isinstance(expr, (int, float, bool, type(None))):
            return expr
        if isinstance(expr, str):
            return env.get(expr, expr)
        if isinstance(expr, list) and len(expr) == 1:
            # 单元素列表：直接求值
            return self.eval(expr[0], env)
        if isinstance(expr, list) and len(expr) >= 2:
            op = expr[0]
            args = expr[1:]
            if op == 'lambda':
                return ("lambda", args[0] if args else None,
                        args[1] if len(args) > 1 else None, env)
            if op == 'let':
                for binding in args:
                    if isinstance(binding, list) and len(binding) == 2:
                        env[binding[0]] = self.eval(binding[1], env)
                return self.eval(args[-1] if args else None, env) if args else None
            if op == 'if':
                cond = self.eval(args[0], env)
                return self.eval(args[1], env) if cond else (self.eval(args[2], env) if len(args) > 2 else None)
            # 先求值所有参数
            func_args = [self.eval(a, env) for a in args]
            # 内置算术运算符
            if op == '*':
                r = 1
                for a in func_args: r *= a
                return r
            if op == '+':
                return sum(func_args)
            if op == '-':
                return func_args[0] - sum(func_args[1:]) if len(func_args) > 1 else -func_args[0]
            if op == '/':
                return func_args[0] / func_args[1] if len(func_args) > 1 else 0
            if op == '//':
                return func_args[0] // func_args[1] if len(func_args) > 1 else 0
            if op == '%':
                return func_args[0] % func_args[1] if len(func_args) > 1 else 0
            if op == '**':
                return func_args[0] ** func_args[1] if len(func_args) > 1 else 0
            if op == '==':
                return func_args[0] == func_args[1] if len(func_args) > 1 else False
            if op == '!=':
                return func_args[0] != func_args[1] if len(func_args) > 1 else False
            if op == '<':
                return func_args[0] < func_args[1] if len(func_args) > 1 else False
            if op == '>':
                return func_args[0] > func_args[1] if len(func_args) > 1 else False
            if op == 'and':
                return func_args[0] and func_args[1] if len(func_args) > 1 else func_args[0]
            if op == 'or':
                return func_args[0] or func_args[1] if len(func_args) > 1 else func_args[0]
            # 函数应用
            func = self.eval(op, env)
            if isinstance(func, tuple) and func[0] == 'lambda':
                params = func[1] or []
                body = func[2]
                new_env = dict(env)
                for p, v in zip(params, func_args):
                    new_env[p] = v
                return self.eval(body, new_env)
            if callable(func):
                return func(*func_args)
            # FFI 函数查找（如 sin, cos, sqrt 等）
            try:
                from src.ffi import get_ffi
                ffi = get_ffi()
                if ffi.is_registered(op):
                    return ffi.call(op, *func_args)
            except Exception:
                pass
            raise ValueError(f"不可调用: {op}")
        if isinstance(expr, str) and expr in env:
            return env[expr]
        return expr

    def curry(self, func: Callable, n: int) -> Callable:
        """柯里化：将多参函数转为嵌套单参函数。"""
        def _curried(*args):
            if len(args) >= n:
                return func(*args[:n])
            return lambda *more: _curried(*args, *more)
        return _curried

    def compose(self, *funcs: Callable) -> Callable:
        """函数组合：(f ∘ g ∘ h)(x) = f(g(h(x)))"""
        def _composed(x):
            result = x
            for f in reversed(funcs):
                result = f(result)
            return result
        return _composed

    def fold(self, func: Callable, init: Any, lst: list) -> Any:
        """归约：foldl(func, init, [a,b,c]) = func(func(func(init, a), b), c)"""
        acc = init
        for item in lst:
            acc = func(acc, item)
        return acc

    def map(self, func: Callable, lst: list) -> list:
        """映射：map(func, [a,b,c]) = [func(a), func(b), func(c)]"""
        return [func(x) for x in lst]

    def filter(self, func: Callable, lst: list) -> list:
        """过滤：filter(func, [a,b,c]) = [x for x in lst if func(x)]"""
        return [x for x in lst if func(x)]


# ═══════════════════════════════════════════════════════════════════════════════
#  命令式引擎
# ═══════════════════════════════════════════════════════════════════════════════

class ImperativeEngine:
    """命令式状态机：变量赋值、循环、分支、副作用。"""

    def __init__(self):
        self._state: Dict[str, Any] = {}
        logger.info("  [命令式] 引擎初始化")

    def set(self, name: str, value: Any):
        """设置变量。"""
        self._state[name] = value
        logger.debug(f"  [命令式] {name} = {value}")

    def get(self, name: str) -> Any:
        """获取变量。"""
        return self._state.get(name)

    def eval_stmt(self, stmt: dict) -> Any:
        """执行单条语句。"""
        kind = stmt.get("kind")
        if kind == "assign":
            self.set(stmt["var"], self._eval_expr(stmt["value"]))
            return None
        elif kind == "expr":
            return self._eval_expr(stmt["expr"])
        elif kind == "seq":
            result = None
            for s in stmt.get("statements", []):
                result = self.eval_stmt(s)
            return result
        elif kind == "if":
            cond = self._eval_expr(stmt["condition"])
            if cond:
                return self.eval_stmt(stmt["then"])
            elif "else" in stmt:
                return self.eval_stmt(stmt["else"])
            return None
        elif kind == "while":
            result = None
            for _ in range(10000):
                cond = self._eval_expr(stmt["condition"])
                if not cond:
                    break
                result = self.eval_stmt(stmt["body"])
            return result
        elif kind == "for":
            var = stmt["var"]
            iterable = self._eval_expr(stmt["iterable"])
            result = None
            for item in iterable:
                self.set(var, item)
                result = self.eval_stmt(stmt["body"])
            return result
        return None

    def _eval_expr(self, expr: Any) -> Any:
        """表达式求值。"""
        if isinstance(expr, (int, float, str, bool, type(None))):
            return expr
        if isinstance(expr, list):
            op = expr[0]
            args = [self._eval_expr(a) for a in expr[1:]]
            if op == "+": return sum(args)
            if op == "-": return args[0] - sum(args[1:]) if len(args) > 1 else -args[0]
            if op == "*":
                r = 1
                for a in args: r *= a
                return r
            if op == "/": return args[0] / args[1] if len(args) > 1 else 0
            if op == "==": return args[0] == args[1]
            if op == "!=": return args[0] != args[1]
            if op == "<": return args[0] < args[1]
            if op == ">": return args[0] > args[1]
            if op == "and": return args[0] and args[1]
            if op == "or": return args[0] or args[1]
            if op == "not": return not args[0]
            if op == "list":
                # 将 range/set/单个可迭代对象转为列表
                if len(args) == 1 and isinstance(args[0], (range, set)):
                    return list(args[0])
                return args if args else []
            if op == "len": return len(args[0]) if args else 0
            if op == "get":
                if len(args) >= 1 and isinstance(args[0], str) and args[0] in self._state:
                    return self._state[args[0]]
                return None
            if op == "append":
                lst = args[0] if args else []
                lst = list(lst) if isinstance(lst, list) else lst
                if len(args) > 1: lst.append(args[1])
                return lst
        if isinstance(expr, str) and expr in self._state:
            return self._state[expr]
        return expr

    def get_state(self) -> Dict[str, Any]:
        """获取当前状态。"""
        return dict(self._state)


# ═══════════════════════════════════════════════════════════════════════════════
#  逻辑式引擎
# ═══════════════════════════════════════════════════════════════════════════════

class LogicEngine:
    """逻辑推理引擎：规则匹配、约束求解、推导。"""

    def __init__(self):
        self._rules: List[dict] = []
        self._facts: Dict[str, Any] = {}
        logger.info("  [逻辑式] 引擎初始化")

    def add_rule(self, name: str, body: Callable, conclusion: Callable):
        """添加推理规则。"""
        self._rules.append({"name": name, "body": body, "conclusion": conclusion})
        logger.info(f"  [逻辑式] 添加规则: {name}")

    def add_fact(self, name: str, value: Any):
        """添加事实。"""
        self._facts[name] = value

    def query(self, goal: str) -> Optional[Any]:
        """查询目标，返回推导结果。"""
        for rule in self._rules:
            try:
                if rule["body"](self._facts):
                    result = rule["conclusion"](self._facts)
                    logger.info(f"  [逻辑式] 规则 {rule['name']} 匹配: {goal} → {result}")
                    return result
            except Exception:
                continue
        return self._facts.get(goal)

    def unify(self, pattern: dict, facts: dict) -> Optional[dict]:
        """合一：将模式与事实匹配。"""
        bindings = {}
        for key, val in pattern.items():
            if isinstance(val, str) and val.startswith("?"):
                bindings[val] = facts.get(key)
            elif facts.get(key) == val:
                pass
            else:
                return None
        return bindings


# ═══════════════════════════════════════════════════════════════════════════════
#  数据流引擎
# ═══════════════════════════════════════════════════════════════════════════════

class DataflowEngine:
    """数据流引擎：节点式计算图。"""

    def __init__(self):
        self._nodes: Dict[str, Callable] = {}
        self._edges: Dict[str, List[str]] = {}
        self._outputs: Dict[str, Any] = {}
        logger.info("  [数据流] 引擎初始化")

    def add_node(self, name: str, func: Callable):
        """添加计算节点。"""
        self._nodes[name] = func
        logger.info(f"  [数据流] 添加节点: {name}")

    def add_edge(self, from_node: str, to_node: str):
        """添加数据流边。"""
        self._edges.setdefault(from_node, []).append(to_node)

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """运行数据流图。"""
        # 构建反向依赖图：to_node → [from_node, ...]
        reverse_edges: Dict[str, List[str]] = {}
        for frm, to in self._edges.items():
            for t in to:
                reverse_edges.setdefault(t, []).append(frm)

        logger.info(f"  [数据流] 启动运行，输入: {inputs}")
        logger.info(f"  [数据流] 正向边: {dict(self._edges)}, 反向依赖: {dict(reverse_edges)}")

        results = dict(inputs)
        visited = set()
        queue = list(inputs.keys())
        step = 0
        while queue:
            node = queue.pop(0)
            if node in visited:
                logger.debug(f"  [数据流] 跳过已访问节点: {node}")
                continue
            visited.add(node)
            step += 1
            logger.info(f"  [数据流] 处理节点 [{step}]: {node}, results={results}, deps={reverse_edges.get(node, [])}")
            if node in self._nodes:
                deps = reverse_edges.get(node, [])
                if deps:
                    args = [results.get(d) for d in deps]
                    logger.info(f"  [数据流] 节点 {node} 调用: func(args={args})")
                    results[node] = self._nodes[node](*args)
                else:
                    # 输入节点：直接用输入值调用
                    val = results.get(node)
                    logger.info(f"  [数据流] 节点 {node} 直接输入: val={val}")
                    results[node] = self._nodes[node](val) if val is not None else None
                logger.info(f"  [数据流] 节点 {node} 结果: {results[node]}")
            for dep in self._edges.get(node, []):
                if dep not in visited:
                    queue.append(dep)
        self._outputs = results
        logger.info(f"  [数据流] 完成，输出: {results}")
        return results


# ═══════════════════════════════════════════════════════════════════════════════
#  统一多范式引擎
# ═══════════════════════════════════════════════════════════════════════════════

class MultiParadigmEngine:
    """
    多范式融合引擎 — 根据任务自动选择并切换执行范式。

    策略：
      1. 数值计算 → 函数式（纯函数，无副作用）
      2. 状态管理 → 命令式（变量/循环/分支）
      3. 符号推导 → 符号式（代数/微积分/简化）
      4. 逻辑推理 → 逻辑式（规则/约束/推导）
      5. 管道处理 → 数据流式（节点/边/拓扑）
      6. 混合任务 → 自动组合各范式结果
    """

    def __init__(self):
        self.functional = FunctionalEngine()
        self.imperative = ImperativeEngine()
        self.logic = LogicEngine()
        self.dataflow = DataflowEngine()
        self._paradigm_stack: List[Paradigm] = []
        logger.info("  [多范式] 引擎初始化完成")

    def compute(self, task: dict) -> dict:
        """
        智能任务分发：根据任务类型自动选择范式。
        """
        task_type = task.get("type", "mixed")
        logger.info(f"  [多范式] === 任务开始 === type={task_type}")
        logger.info(f"  [多范式] 完整任务: {task}")

        if task_type == "functional":
            return self._run_functional(task)
        elif task_type == "imperative":
            return self._run_imperative(task)
        elif task_type == "symbolic":
            return self._run_symbolic(task)
        elif task_type == "logic":
            return self._run_logic(task)
        elif task_type == "dataflow":
            return self._run_dataflow(task)
        elif task_type == "mixed":
            return self._run_mixed(task)
        else:
            logger.warning(f"  [多范式] 未知任务类型: {task_type}")
            return {"error": f"未知任务类型: {task_type}"}

    def _run_functional(self, task: dict) -> dict:
        """函数式执行。"""
        expr = task.get("expr")
        env = task.get("params", {})
        result = self.functional.eval(expr, env)
        logger.info(f"  [函数式] 结果: {result}")
        return {"paradigm": "functional", "result": result}

    def _run_imperative(self, task: dict) -> dict:
        """命令式执行。"""
        stmts = task.get("statements", [])
        for stmt in stmts:
            self.imperative.eval_stmt(stmt)
        state = self.imperative.get_state()
        logger.info(f"  [命令式] 状态: {state}")
        return {"paradigm": "imperative", "state": state}

    def _run_symbolic(self, task: dict) -> dict:
        """符号式执行。"""
        try:
            from src.symbolic import symbol_expr, diff_expr, simplify_expr, eval_expr
        except ImportError:
            from .symbolic import symbol_expr, diff_expr, simplify_expr, eval_expr
        expr_str = task.get("expr", "")
        bindings = task.get("params", {})

        expr = symbol_expr(expr_str)
        simplified = simplify_expr(expr)
        derivative = diff_expr(expr, list(bindings.keys())[0] if bindings else 'x')

        try:
            value = eval_expr(expr, **bindings)
        except Exception:
            value = None

        result = {
            "expression": expr_str,
            "simplified": str(simplified),
            "derivative": str(derivative),
            "value": value,
        }
        logger.info(f"  [符号式] {expr_str} → {result}")
        return {"paradigm": "symbolic", "result": result}

    def _run_logic(self, task: dict) -> dict:
        """逻辑式执行。"""
        for rule in task.get("rules", []):
            self.logic.add_rule(rule["name"], rule["body"], rule["conclusion"])
        for fact_name, fact_val in task.get("facts", {}).items():
            self.logic.add_fact(fact_name, fact_val)

        results = {}
        for goal in task.get("goals", []):
            results[goal] = self.logic.query(goal)
        logger.info(f"  [逻辑式] 查询结果: {results}")
        return {"paradigm": "logic", "results": results}

    def _run_dataflow(self, task: dict) -> dict:
        """数据流执行。"""
        for name, func in task.get("nodes", {}).items():
            self.dataflow.add_node(name, func)
        for from_n, to_n in task.get("edges", []):
            self.dataflow.add_edge(from_n, to_n)

        inputs = task.get("inputs", {})
        results = self.dataflow.run(inputs)
        logger.info(f"  [数据流] 输入: {inputs}, 输出: {results}")
        return {"paradigm": "dataflow", "outputs": results}

    def _run_mixed(self, task: dict) -> dict:
        """混合执行：组合多种范式。"""
        results = {}
        # 1. 先函数式计算基础值
        if "expr" in task:
            expr_result = self._run_functional(task)
            results["functional"] = expr_result

        # 2. 再符号式推导
        if "symbolic_expr" in task:
            sym_task = {**task, "expr": task["symbolic_expr"]}
            sym_result = self._run_symbolic(sym_task)
            results["symbolic"] = sym_result

        # 3. 命令式状态管理
        if "statements" in task:
            imp_result = self._run_imperative(task)
            results["imperative"] = imp_result

        # 4. 逻辑推理
        if "goals" in task:
            log_result = self._run_logic(task)
            results["logic"] = log_result

        logger.info(f"  [混合] 结果: {list(results.keys())}")
        return {"paradigm": "mixed", "results": results}

    def switch_paradigm(self, paradigm: Paradigm):
        """切换到指定范式。"""
        self._paradigm_stack.append(paradigm)
        logger.info(f"  [多范式] 切换到范式: {paradigm.value}")

    def get_paradigm_history(self) -> List[str]:
        """获取范式切换历史。"""
        return [p.value for p in self._paradigm_stack]


# ═══════════════════════════════════════════════════════════════════════════════
#  单例
# ═══════════════════════════════════════════════════════════════════════════════

_engine_instance: Optional[MultiParadigmEngine] = None


def get_paradigm_engine() -> MultiParadigmEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MultiParadigmEngine()
    return _engine_instance


def paradigm_compute(task: dict) -> dict:
    """便捷入口。"""
    return get_paradigm_engine().compute(task)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha 多范式引擎 v1.3.0")
    print("=" * 60)

    engine = MultiParadigmEngine()

    # 函数式
    print("\n[函数式]")
    r = engine.compute({"type": "functional", "expr": ['let', ['x', 5], ['let', ['y', 3], ['+', ['x'], ['*', ['y'], ['y']]]]]})
    print(f"  x=5, y=3, x+y² = {r['result']}")

    # 符号式
    print("\n[符号式]")
    r = engine.compute({"type": "symbolic", "expr": "x^2 + 3*x - 5", "params": {"x": 2}})
    print(f"  x²+3x-5 (x=2): {r['result']}")
    print(f"  简化: {r['result']['simplified']}")
    print(f"  导数: {r['result']['derivative']}")

    # 命令式
    print("\n[命令式]")
    r = engine.compute({
        "type": "imperative",
        "statements": [
            {"kind": "assign", "var": "n", "value": 10},
            {"kind": "assign", "var": "sum", "value": 0},
            {"kind": "for", "var": "i", "iterable": ["list", 1, 2, 3, 4, 5],
             "body": {"kind": "seq", "statements": [
                 {"kind": "assign", "var": "sum", "value": ["+", ["get", "sum"], ["get", "i"]]}
             ]}},
            {"kind": "expr", "expr": ["get", "sum"]},
        ]
    })
    print(f"  1+2+3+4+5 = {r['state']['sum']}")

    # 数据流
    print("\n[dataflow]")
    r = engine.compute({
        "type": "dataflow",
        "nodes": {
            "double": lambda x: x * 2,
            "add_one": lambda x: x + 1,
            "final": lambda a, b: a + b,
        },
        "edges": [["double", "final"], ["add_one", "final"]],
        "inputs": {"double": 5, "add_one": 10},
    })
    print(f"  double(5)+add_one(10) = {r['outputs']['final']}")

    print("\n完成。")
