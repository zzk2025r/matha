"""？公式模式库：按「格式」统一同形公式。

语义依据（用户确认）
------------------
* `#：？公式` **登记为模式**，进公式库。它**不可执行**——`？` 表示「此处为一个
  变量」的槽，槽本身没有可求值的值（`docs/02` L144 原写作「运行：执行公式」，
  与槽语义冲突，已按模式库更正）。
* 裸 `？` 是**匿名槽**：每次出现**彼此独立**。
* `？name` 是**具名槽**：跨出现**强制一致**（Prolog 变量 / Python `{name}` 的
  `{name}`）。这正是 `？name` 存在的意义——它给形状加上等式约束，
  `？a + ？a = ？b` 能接受 `面积 + 面积 = 周长` 而拒绝 `x + y = z`。
* 统一的依据是**格式（形状）**：运算符与结合结构属于形状，槽名不属于。故
  `单价 + 运费 = 总价` 与 `？+？=？` 同形而统一，`单价 * 数量 = 总价` 不同形。

由此得到两个方向的效果：

* **多公式一用途意图**：任意多个具体公式合一到同一模式（形状相同即同一条公式）。
* **一公式多用途意图**：同一模式换基础定义（换绑定）即换用途——
  `？+？=？` 绑成 `收入+支出=结余` / `长+宽=周长` / `速度+时间=距离` 都是同一条
  公式的不同实例。

槽的标识
--------
匿名槽没有节点级身份（`ast_nodes.Variable` 只有 `name` 与 `is_placeholder`，
每个 `？` 都是同一个 `Variable('？', True)`）。这里用**左到右遍历次序**充当
匿名槽的序号（1、2、3……）：遍历顺序确定、与具体式遍历顺序一致，故模式与
具体式两侧的槽天然对齐，且序号可序列化、可用于实例化，无需改 AST。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from . import ast_nodes as ast

__all__ = [
    "ANON", "Slot", "Bindings", "Match",
    "shape", "collect_slots", "has_slot", "unify", "instantiate", "render",
    "FormulaSchema", "FormulaLibrary",
]

ANON = "？"           # 匿名槽在 ast.Variable.name 里的哨兵值


# ── 遍历工具 ────────────────────────────────────────────────────────────────

def _children(expr: Any) -> list:
    """按**左到右**顺序取出子表达式——匿名槽序号依赖这个顺序。

    字段名对照 `ast_nodes`：`ListLiteral`/`TupleExpr` 用 `elements`，
    `IndexExpr` 用 `container`，`Belongs`/`PathExpr`/`SafePathExpr` 用
    `left`/`right`，`AngleExpr` 用 `expr`。
    """
    if isinstance(expr, ast.BinaryOp):
        return [expr.left, expr.right]
    if isinstance(expr, ast.UnaryOp):
        return [expr.operand]
    if isinstance(expr, ast.AngleExpr):
        return [expr.expr]
    if isinstance(expr, (ast.Belongs, ast.PathExpr, ast.SafePathExpr)):
        return [expr.left, expr.right]
    if isinstance(expr, (ast.ListLiteral, ast.TupleExpr)):
        return list(expr.elements)
    if isinstance(expr, ast.IndexExpr):
        return [expr.container, expr.index]
    if isinstance(expr, ast.FuncApp):
        return [expr.func, expr.arg]
    if isinstance(expr, ast.IfExpr):
        return [expr.cond, expr.then, expr.else_]
    return []


# ── 形状归一化 ──────────────────────────────────────────────────────────────

def shape(expr: Any) -> str:
    """把表达式归一化为**格式**串：槽位→`_` / `:<name>`，其余保留字面形状。"""
    return _shape(expr, [0])


def _shape(e: Any, counter: list) -> str:
    # 二元 / 一元必须**先于**通用 _children 处理，否则会渲染成 `BinaryOp(...)`
    # 而丢掉运算符——而运算符正是「格式」的组成部分。
    if isinstance(e, ast.BinaryOp):
        return "(%s %s %s)" % (_shape(e.left, counter), e.op, _shape(e.right, counter))
    if isinstance(e, ast.UnaryOp):
        return "(%s %s)" % (e.op, _shape(e.operand, counter))
    if isinstance(e, ast.Variable):
        if not e.is_placeholder:
            return e.name
        if e.name == ANON:
            counter[0] += 1
            return "_%d" % counter[0]
        return ":" + e.name
    if isinstance(e, ast.IntegerLit):
        return "i" + str(e.value)
    if isinstance(e, ast.FloatLit):
        return "f" + repr(e.value)
    if isinstance(e, ast.StringLit):
        return "s" + repr(e.value)
    if isinstance(e, ast.BoolLit):
        return "b" + repr(e.value)
    if isinstance(e, ast.AngleExpr):
        return "angle(%s)" % _shape(e.expr, counter)
    if isinstance(e, ast.Belongs):
        return "in(%s,%s)" % (_shape(e.left, counter), _shape(e.right, counter))
    if isinstance(e, (ast.ListLiteral, ast.TupleExpr)):
        return "%s[%s]" % (type(e).__name__,
                           ",".join(_shape(x, counter) for x in e.elements))
    if isinstance(e, ast.IndexExpr):
        return "idx(%s,%s)" % (_shape(e.container, counter),
                                _shape(e.index, counter))
    kids = _children(e)
    if kids:
        return "%s(%s)" % (type(e).__name__,
                           ",".join(_shape(k, counter) for k in kids))
    return type(e).__name__


# ── 槽位收集 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Slot:
    """一个 `？` 槽。

    `ordinal` 只对匿名槽有意义（1 起，按左到右出现次序）；具名槽 ordinal 为 0，
    靠 `name` 跨出现共享。
    """
    ordinal: int
    name: str = ""            # 空 = 匿名

    @property
    def key(self) -> str:
        return "?" + str(self.ordinal) if not self.name else ":" + self.name

    @property
    def display(self) -> str:
        return "？" if not self.name else "？" + self.name


def collect_slots(expr: Any) -> list:
    """按左到右次序收集全部槽位。"""
    out: list = []
    _collect(expr, [0], out)
    return out


def _collect(e: Any, counter: list, out: list) -> None:
    if isinstance(e, ast.Variable):
        if e.is_placeholder:
            if e.name == ANON:
                counter[0] += 1
                out.append(Slot(counter[0]))
            else:
                out.append(Slot(0, e.name))
        return
    if isinstance(e, ast.Belongs):
        _collect(e.left, counter, out)
        _collect(e.right, counter, out)
        return
    for k in _children(e):
        _collect(k, counter, out)


def has_slot(expr: Any) -> bool:
    """表达式是否含 `？` 槽——含槽即是模式，不该被求值。"""
    if isinstance(expr, ast.Variable):
        return bool(expr.is_placeholder)
    if isinstance(expr, ast.Belongs):
        return has_slot(expr.left) or has_slot(expr.right)
    return any(has_slot(k) for k in _children(expr))


# ── 合一 ────────────────────────────────────────────────────────────────────

Bindings = dict          # slot.key -> 具体子式（AST 节点）
Match = "Match"


def unify(schema_expr: Any, concrete_expr: Any,
           bindings: Bindings | None = None) -> Bindings | None:
    """把具体公式合一到模式上；成功返回绑定，失败返回 ``None``。

    约束只有一条：**格式相同**（形状一致，运算符与结合结构必须吻合），
    外加**具名槽跨出现一致**。槽可绑定到任意具体子式（含字面量与嵌套式）。

    绑定以 ``Slot.key`` 为键，匿名槽 ``"?1"``、具名槽 ``":name"``，两者同表。
    """
    if bindings is None:
        bindings = {}
    return _unify(schema_expr, concrete_expr, [0], bindings)


def _unify(s: Any, c: Any, counter: list, b: dict) -> Bindings | None:
    if isinstance(s, ast.Variable):
        if not s.is_placeholder:
            # 模式里的普通名字：具体式必须同名同物。
            if not (isinstance(c, ast.Variable) and c.name == s.name):
                return None
            return b
        if s.name == ANON:                       # 匿名槽：每次出现独立
            if isinstance(c, ast.Variable) and c.is_placeholder:
                return None                       # 槽不与槽合一
            counter[0] += 1
            b[Slot(counter[0]).key] = c
            return b
        k = Slot(0, s.name).key                  # 具名槽一致性约束
        prev = b.get(k)
        if prev is not None:
            return b if render(prev) == render(c) else None
        b[k] = c
        return b
    if isinstance(s, ast.BinaryOp):
        if not isinstance(c, ast.BinaryOp) or c.op != s.op:
            return None
        left = _unify(s.left, c.left, counter, b)
        if left is None:
            return None
        return _unify(s.right, c.right, counter, b)
    if isinstance(s, ast.UnaryOp):
        if not isinstance(c, ast.UnaryOp) or c.op != s.op:
            return None
        return _unify(s.operand, c.operand, counter, b)
    if isinstance(s, ast.AngleExpr):
        if not isinstance(c, ast.AngleExpr):
            return None
        return _unify(s.expr, c.expr, counter, b)
    if isinstance(s, ast.Belongs):
        if not isinstance(c, ast.Belongs):
            return None
        left = _unify(s.left, c.left, counter, b)
        if left is None:
            return None
        return _unify(s.right, c.right, counter, b)
    if isinstance(s, (ast.ListLiteral, ast.TupleExpr)):
        if type(s) is not type(c) or len(s.elements) != len(c.elements):
            return None
        for x, y in zip(s.elements, c.elements):
            if _unify(x, y, counter, b) is None:
                return None
        return b
    if isinstance(s, ast.IndexExpr):
        if not isinstance(c, ast.IndexExpr):
            return None
        left = _unify(s.container, c.container, counter, b)
        if left is None:
            return None
        return _unify(s.index, c.index, counter, b)
    if isinstance(s, ast.FuncApp):
        if not isinstance(c, ast.FuncApp):
            return None
        # 被调者必须同形（同一个函数名占同一个槽），实参参与合一。
        left = _unify(s.func, c.func, counter, b)
        if left is None:
            return None
        return _unify(s.arg, c.arg, counter, b)
    if isinstance(s, (ast.IntegerLit, ast.FloatLit, ast.StringLit, ast.BoolLit)):
        if type(s) is not type(c) or s.value != c.value:
            return None
        return b
    return None


# ── 渲染 / 实例化 ───────────────────────────────────────────────────────────

def render(expr: Any) -> str:
    """把子式渲染回 Matha 源码文本（用于日志与具名槽一致性比较）。"""
    if isinstance(expr, ast.Variable):
        # 槽要带 `？` 前缀显示，否则模式 `？a+？a=？b` 会被打印成 `a+a=b`，
        # 与具体公式混淆。
        if expr.is_placeholder:
            return ANON if expr.name == ANON else ANON + expr.name
        return expr.name
    if isinstance(expr, ast.IntegerLit):
        return str(expr.value)
    if isinstance(expr, ast.FloatLit):
        return str(expr.value)
    if isinstance(expr, ast.StringLit):
        return '"%s"' % expr.value
    if isinstance(expr, ast.BoolLit):
        return "真" if expr.value else "假"
    if isinstance(expr, ast.BinaryOp):
        return "%s %s %s" % (render(expr.left), expr.op, render(expr.right))
    if isinstance(expr, ast.UnaryOp):
        return "%s%s" % (expr.op, render(expr.operand))
    if isinstance(expr, ast.AngleExpr):
        return "<<%s>>" % render(expr.expr)
    if isinstance(expr, ast.Belongs):
        return "%s >> %s" % (render(expr.left), render(expr.right))
    if isinstance(expr, (ast.ListLiteral, ast.TupleExpr)):
        items = ", ".join(render(x) for x in expr.elements)
        return "[%s]" % items if isinstance(expr, ast.ListLiteral) else "(%s)" % items
    if isinstance(expr, ast.IndexExpr):
        return "%s[%s]" % (render(expr.container), render(expr.index))
    return shape(expr)


def instantiate(schema_expr: Any, bindings: Bindings) -> Any:
    """把模式按绑定实例化成具体公式——「换基础定义即换用途」的那一步。"""
    return _inst(schema_expr, [0], bindings)


def _inst(s: Any, counter: list, b: Bindings) -> Any:
    if isinstance(s, ast.Variable):
        if not s.is_placeholder:
            return s
        if s.name == ANON:
            counter[0] += 1
            val = b.get(Slot(counter[0]).key)
            return val if val is not None else s
        return b.get(Slot(0, s.name).key, s)
    if isinstance(s, ast.BinaryOp):
        return ast.BinaryOp(s.op, _inst(s.left, counter, b), _inst(s.right, counter, b))
    if isinstance(s, ast.UnaryOp):
        return ast.UnaryOp(s.op, _inst(s.operand, counter, b))
    if isinstance(s, ast.AngleExpr):
        return ast.AngleExpr(_inst(s.expr, counter, b))
    if isinstance(s, ast.Belongs):
        return ast.Belongs(_inst(s.left, counter, b), _inst(s.right, counter, b))
    if isinstance(s, (ast.ListLiteral, ast.TupleExpr)):
        return type(s)([_inst(x, counter, b) for x in s.elements])
    if isinstance(s, ast.IndexExpr):
        return ast.IndexExpr(_inst(s.container, counter, b),
                             _inst(s.index, counter, b))
    if isinstance(s, ast.FuncApp):
        return ast.FuncApp(_inst(s.func, counter, b), _inst(s.arg, counter, b))
    return s


# ── 公式库 ──────────────────────────────────────────────────────────────────

@dataclass
class FormulaSchema:
    """一条已登记的 `？` 公式模式。

    `expr` 只在解释器侧（AST 级）有值；VM/AOT 经 `register_meta` 只存静态元数据。
    """
    expr: Any
    seg_id: int | None = None
    shape: str = ""
    slots: list = field(default_factory=list)
    text_: str = ""

    @property
    def text(self) -> str:
        return self.text_ if self.expr is None else render(self.expr)

    @property
    def display(self) -> str:
        prefix = "#%d：" % self.seg_id if self.seg_id is not None else "#："
        return prefix + self.text


@dataclass
class Unification:
    """一次成功的一一。"""
    schema: FormulaSchema
    bindings: Bindings

    @property
    def concrete(self) -> str:
        return render(instantiate(self.schema.expr, self.bindings))

    def describe(self) -> str:
        named = {k[1:]: v for k, v in self.bindings.items() if k.startswith(":")}
        anon = {k: v for k, v in self.bindings.items() if k.startswith("?")}
        parts = ["#%s→%s" % (n, render(v)) for n, v in sorted(anon.items())]
        parts += ["？%s→%s" % (n, render(v)) for n, v in named.items()]
        return "同一公式 %s ⇠ 绑定{%s}" % (self.schema.display, " ".join(parts))


class FormulaLibrary:
    """`#：？公式` 登记的公式模式库。

    登记同形公式时会**归并**：形状相同即视为同一条公式（这正是「根据格式统一
    相同格式的公式」），不重复堆积；`一公式多用途` 由 `instantiate` 换绑定实现。
    """

    def __init__(self) -> None:
        self._schemas: list[FormulaSchema] = []

    # -- 登记 ---------------------------------------------------------------
    def register(self, expr: Any, seg_id: int | None = None) -> FormulaSchema:
        """登记一条 `？` 模式；同形已存在则复用原条目（格式即身份）。"""
        sh = shape(expr)
        for s in self._schemas:
            if s.shape == sh:
                return s
        s = FormulaSchema(expr=expr, seg_id=seg_id, shape=sh,
                          slots=collect_slots(expr))
        self._schemas.append(s)
        return s

    def register_meta(self, seg_id: int | None, text: str, shp: str,
                      slots: tuple) -> FormulaSchema:
        """只登记**静态元数据**的入口，供 VM/AOT 使用。

        编译器把模式整体常量化成 `(seg_id, 文本, 形状, 槽位表)`，后端无需重建
        AST 即可登记；形状即身份，故同形仍归并为一条。
        """
        for s in self._schemas:
            if s.shape == shp:
                return s
        s = FormulaSchema(expr=None, seg_id=seg_id, shape=shp, text_=text,
                          slots=[Slot(o, n) for o, n, _ in slots])
        self._schemas.append(s)
        return s

    # -- 查询 ---------------------------------------------------------------
    def match(self, expr: Any) -> list:
        """把具体公式与库中所有模式合一，返回全部成功者（多公式一用途）。"""
        out = []
        for s in self._schemas:
            b = unify(s.expr, expr)
            if b is not None:
                out.append(Unification(s, b))
        return out

    def get(self, seg_id: int | None) -> FormulaSchema | None:
        for s in self._schemas:
            if s.seg_id == seg_id:
                return s
        return None

    @property
    def schemas(self) -> list:
        return list(self._schemas)

    def __len__(self) -> int:
        return len(self._schemas)

    def __iter__(self) -> Iterator[FormulaSchema]:
        return iter(self._schemas)

    def __repr__(self) -> str:
        return "FormulaLibrary(%d 条模式: %s)" % (
            len(self._schemas), [s.display for s in self._schemas])
