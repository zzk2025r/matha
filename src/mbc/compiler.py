# -*- coding: utf-8 -*-
"""M3V 字节码编译器：Matha AST → MModule（函数表 + 常量池 + 顶层码）。

作用域在编译期解析为 (depth, slot)：
  - depth 0 = 当前帧槽位；depth d = 闭包定义帧链第 d 层
  - let rec 自引用用 Box（槽位存放可变盒子，闭包经帧链共享）
  - Lambda 编译为独立函数，MAKE_CLOSURE 在运行时捕获定义帧
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src import ast_nodes as ast
from src.mbc import opcodes as OP


@dataclass
class MFunction:
    name: str
    arity: int
    nlocals: int
    code: list = field(default_factory=list)
    params: list = field(default_factory=list)


@dataclass
class MModule:
    functions: dict = field(default_factory=dict)   # name -> MFunction
    main_code: list = field(default_factory=list)   # 模块顶层初始化码
    constants: list = field(default_factory=list)
    module_name: str = "主程序"


class _Scope:
    """词法作用域：name -> (slot, boxed)。

    is_main=True 表示模块主码作用域：main_frame 无局部槽数组，
    所有绑定/临时槽一律落全局（STORE_GLOBAL/LOAD_GLOBAL）。"""
    __slots__ = ("parent", "names", "nslots", "is_main")

    def __init__(self, parent: "_Scope | None", is_main: bool = False):
        self.parent = parent
        self.names: dict[str, tuple[int, bool]] = {}
        self.nslots = 0
        self.is_main = is_main

    def declare(self, name: str, boxed: bool = False) -> int:
        slot = self.nslots
        self.nslots += 1
        self.names[name] = (slot, boxed)
        return slot

    def resolve(self, name: str, depth: int = 0):
        """返回 (kind, depth, slot, boxed)；kind ∈ {'local','outer','global'}。

        main 作用域没有局部槽数组，其声明一律落全局，故直接报 global。
        """
        if name in self.names:
            if self.is_main:
                return ("global", 0, name, False)
            slot, boxed = self.names[name]
            return ("local" if depth == 0 else "outer", depth, slot, boxed)
        if self.parent is not None:
            return self.parent.resolve(name, depth + 1)
        return ("global", 0, name, False)


# 二元运算符 → VM 运算表索引（与 vm._BINOPS 键一致）
_BIN_OPS = {
    "+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "^": "**", "**": "**",
    "//": "//", "=": "==", "==": "==", "!=": "!=", "<>": "!=",
    "<": "<", ">": ">", "<=": "<=", ">=": ">=",
    "and": "and", "or": "or", "in": "in",
    # 位移：解释器后端早已支持（tests/test_new_features.py 断言 1 << 3 == 8、
    # 16 >> 2 == 4），MBC 后端此前缺表项 → 「不支持的二元运算符 '<<'」。
    "<<": "<<", ">>": ">>",
}
_UNARY_OPS = {"-": "neg", "not": "not", "非": "not",
              "sqrt": "sqrt", "^": "sqrt", "√": "sqrt"}

_NO_FOLD = object()


def _lit_num(node):
    """字面量数值（整数/浮点），非字面量返回 None。"""
    if isinstance(node, ast.IntegerLit):
        return node.value
    if isinstance(node, ast.FloatLit):
        return node.value
    return None


def _fold_unary(op: str, operand):
    """常量折叠一元运算：字面量上直接求值（VM 与原生后端共用）。"""
    v = _lit_num(operand)
    if v is None:
        return _NO_FOLD
    try:
        if op == "neg":
            return -v
        if op == "not":
            return not v
        if op == "sqrt":
            if v < 0:
                return _NO_FOLD
            r = v ** 0.5
            return int(r) if isinstance(v, int) and r == int(r) else r
    except (ArithmeticError, ValueError, TypeError):
        return _NO_FOLD
    return _NO_FOLD


def _fold_bin(op: str, left, right):
    """常量折叠二元运算：两侧均为字面量时直接求值。"""
    a = _lit_num(left)
    b = _lit_num(right)
    if a is None or b is None:
        return _NO_FOLD
    try:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "**":
            if b < 0 and isinstance(a, int):
                return _NO_FOLD
            r = a ** b
            return r
    except (ArithmeticError, ValueError, TypeError):
        return _NO_FOLD
    return _NO_FOLD


def _scan_fn_arities(program) -> dict[str, int]:
    """预扫描所有顶层 FuncDef 的 name -> arity（与声明顺序无关）。

    parser 把 f(a1, …, aN) 建成左嵌套 FuncApp（f(a1)(a2)…）。若逐层发射
    CALL 1，完全应用的调用会在运行期退化为 Partial 柯里化。预先知道 arity
    后即可把完全应用的调用融成单条 CALL N，VM 与原生后端语义一致。
    """
    out: dict[str, int] = {}

    def visit(node) -> None:
        if isinstance(node, ast.FuncDef):
            lam = getattr(node, "body", None)
            params = getattr(lam, "params", None)
            if params is not None:
                out[node.name] = len(params)
        for inner in getattr(node, "decls", None) or []:
            visit(inner)

    for decl in getattr(program, "decls", None) or []:
        visit(decl)
    return out


def _flatten_call(node):
    """把左嵌套 FuncApp 链 f(a1)(a2)…(aN) 摊平为 (f, [a1, …, aN])。

    实参自身若也是左嵌套 FuncApp 链则同样摊平（f(g(1,2),3) 中 g 也变成
    单条 2 参调用），保证每个实参独立压栈。
    """
    args = []
    cur = node
    while isinstance(cur, ast.FuncApp):
        args.append(cur.arg)
        cur = cur.func
    args.reverse()
    return cur, args


class Compiler:
    def __init__(self):
        self.mod = MModule()
        self._lam_seq = 0
        # break/continue 补丁栈：每层循环 {'brk': [...], 'cont': [...]}
        self._loops: list[dict] = []
        # 顶层 FuncDef 的 name -> arity 预扫描结果（与声明顺序无关），
        # 供多参调用融合成单条 CALL N 使用
        self._fn_arities: dict[str, int] = {}

    # ---- 常量池 ----
    def const(self, value) -> int:
        self.mod.constants.append(value)
        return len(self.mod.constants) - 1

    def sconst(self, s: str) -> int:
        return self.const(s)

    # ---- 入口 ----
    def compile_program(self, program: ast.Program) -> MModule:
        self._fn_arities = _scan_fn_arities(program)
        for decl in program.decls:
            self._compile_top_decl(decl, self.mod.main_code)
        self.mod.main_code.append((OP.HALT,))
        return self.mod

    def _compile_top_decl(self, decl, code: list) -> None:
        if isinstance(decl, ast.ModuleDecl):
            self.mod.module_name = decl.name
            # 先全部注册函数名（支持函数间互引）
            for inner in decl.decls:
                if isinstance(inner, ast.FuncDef):
                    self._compile_func(inner)
            # 再编译顶层非函数声明（let 常量 / 输出）
            for inner in decl.decls:
                if isinstance(inner, ast.FuncDef):
                    continue
                self._compile_top_decl(inner, code)
        elif isinstance(decl, ast.FuncDef):
            self._compile_func(decl)
        elif isinstance(decl, ast.Binding):
            # 顶层绑定：name = expr
            # 用 main 作用域求值：其内出现的 let/临时槽都落全局（main 无局部槽数组）
            self._emit_expr(decl.value, _Scope(None, is_main=True), code)
            tgt = decl.target
            name = tgt.name if isinstance(tgt, ast.Variable) else str(tgt)
            code.append((OP.STORE_GLOBAL, self.sconst(name)))
        elif isinstance(decl, ast.LetBinding):
            # 顶层 let：求值后存入全局
            top_scope = _Scope(None, is_main=True)
            if getattr(decl, "params", None):
                lam = ast.Lambda(params=self._param_vars(decl.params), body=decl.value)
                self._emit_expr(lam, top_scope, code)
            else:
                self._emit_expr(decl.value, top_scope, code)
            code.append((OP.STORE_GLOBAL, self.sconst(decl.name)))
            # `let x = v in body` 的 body 必须照常编译。此前这里直接丢弃，
            # 顶层 let...in 的后续表达式被静默跳过（自举定点中 lexer.matha 的
            # `#：{...}` 自测块因此少编译尾部表达式，常量池比自举产物少一项）。
            if getattr(decl, "body", None) is not None:
                self._emit_expr(decl.body, top_scope, code)
                code.append((OP.POP,))
        elif isinstance(decl, ast.LetTupleBinding):
            top_scope = _Scope(None, is_main=True)
            self._emit_expr(decl.value, top_scope, code)
            code.append((OP.UNPACK_SEQ, len(decl.names)))
            for nm in reversed(decl.names):
                code.append((OP.STORE_GLOBAL, self.sconst(nm)))
            # `let (a, b) = v in body` 的 body 必须照常编译。与上方
            # LetBinding 分支同理：此前顶层解构绑定的 body 被静默丢弃，
            # 导致 `let (a, b) = [1, 2] in 输出(a + b)` 无任何输出。
            if getattr(decl, "body", None) is not None:
                self._emit_expr(decl.body, top_scope, code)
                code.append((OP.POP,))
        elif isinstance(decl, ast.EnumDef):
            # 枚举成员注册为全局字符串常量（struct 实例用 dict 表示，比较即字符串比较）
            member_names = []
            for ctor in decl.ctors:
                nm = ctor.name if isinstance(ctor, ast.Variable) else str(ctor)
                member_names.append(nm)
                code.append((OP.PUSH_CONST, self.const(nm)))
                code.append((OP.STORE_GLOBAL, self.sconst(nm)))
            # 枚举名本身注册为 {成员: 成员} dict，支持 类型.整数 形式访问
            for nm in member_names:
                code.append((OP.PUSH_CONST, self.const(nm)))  # key
                code.append((OP.PUSH_CONST, self.const(nm)))  # value
            code.append((OP.BUILD_DICT, len(member_names)))
            code.append((OP.STORE_GLOBAL, self.sconst(decl.name)))
        elif isinstance(decl, ast.StructDef):
            pass  # 运行时结构体即 dict，构造子（如 做Token）直接产出 dict
        elif isinstance(decl, ast.Output):
            if decl.expr is not None:
                self._emit_expr(decl.expr, _Scope(None), code)
                code.append((OP.OUTPUT,))
        elif isinstance(decl, ast.OutputTrail):
            if getattr(decl, "output", None) is not None:
                self._compile_stmt(decl.output, code)
        elif isinstance(decl, ast.MechUnit):
            # #1：[expr] 输出单元 → GenStmt → OutputTrail/Output
            self._compile_stmt(decl.body, code)
        elif isinstance(decl, (ast.IfStmt, ast.IfElseStmt, ast.WhileStmt, ast.ForStmt,
                               ast.TryStmt, ast.ThrowStmt, ast.CodeBlock)):
            # 顶层控制流语句（绑定写全局，语句值丢弃）
            self._compile_stmt(decl, code)
        else:
            # 顶层裸表达式语句（如 输出(1+2) 解析为 FuncApp）：
            # 交给 _compile_stmt 处理，避免被静默丢弃。
            # 不受支持的节点会在 _emit_expr 抛出明确错误而非无声消失。
            self._compile_stmt(decl, code)

    def _compile_stmt(self, node, code: list, scope: "_Scope | None" = None) -> None:
        """编译语句链（MechUnit/GenStmt/OutputTrail/Output/CodeBlock/控制流）。

        scope=None 表示模块顶层（绑定写全局）；否则绑定声明为当前帧局部槽位。
        所有语句编译后栈平衡（不留值）。"""
        if node is None:
            return
        if scope is None:
            scope = _Scope(None, is_main=True)
        top_level = scope.is_main
        if isinstance(node, ast.MechUnit):
            self._compile_stmt(node.body, code, scope)
        elif isinstance(node, ast.GenStmt):
            self._compile_stmt(node.content, code, scope)
        elif isinstance(node, ast.OutputTrail):
            self._compile_stmt(node.output, code, scope)
        elif isinstance(node, ast.Output):
            if node.expr is not None:
                self._emit_expr(node.expr, scope, code)
                code.append((OP.OUTPUT,))
        elif isinstance(node, ast.CodeBlock):
            self._emit_block(node, scope, code, leave_last=False)
        elif isinstance(node, (ast.Binding, ast.LetBinding, ast.LetTupleBinding)):
            self._emit_binding_stmt(node, scope, code, top_level)
        elif isinstance(node, (ast.IfStmt, ast.IfElseStmt)):
            self._emit_if_stmt(node, scope, code)
        elif isinstance(node, ast.WhileStmt):
            self._emit_while_stmt(node, scope, code)
        elif isinstance(node, ast.ForStmt):
            self._emit_for_stmt(node, scope, code)
        elif isinstance(node, ast.TryStmt):
            # try 表达式语义留值于栈；语句位置丢弃
            self._emit_try_stmt(node, scope, code)
            code.append((OP.POP,))
        elif isinstance(node, (ast.ThrowStmt, ast.RaiseExpr)):
            self._emit_expr(node.value, scope, code)
            code.append((OP.RAISE,))
        elif isinstance(node, ast.FuncDef):
            self._compile_func(node)
        elif isinstance(node, ast.ReturnStmt):
            if node.value is not None:
                self._emit_expr(node.value, scope, code)
            else:
                code.append((OP.PUSH_NULL,))
            code.append((OP.RET,))
        elif isinstance(node, ast.BreakStmt):
            if not self._loops:
                raise RuntimeError("字节码编译：break 出现在循环之外")
            jmp = len(code)
            code.append((OP.JMP, 0))
            self._loops[-1]["brk"].append(jmp)
        elif isinstance(node, ast.ContinueStmt):
            if not self._loops:
                raise RuntimeError("字节码编译：continue 出现在循环之外")
            jmp = len(code)
            code.append((OP.JMP, 0))
            self._loops[-1]["cont"].append(jmp)
        elif isinstance(node, ast.MatchStmt):
            self._emit_match(node, scope, code)
        elif isinstance(node, ast.SwitchStmt):
            self._emit_switch(node, scope, code)
        elif isinstance(node, ast.LoopWhile):
            self._emit_while_stmt(ast.WhileStmt(cond=node.cond,
                                                block=node.block),
                                  scope, code)
        elif isinstance(node, ast.LoopStep):
            self._emit_loop_step(node, scope, code)
        elif isinstance(node, ast.Iteration):
            self._emit_iteration(node, scope, code)
        elif isinstance(node, ast.ChainStmt):
            for st in node.stmts:
                self._compile_stmt(st, code, scope)
        elif isinstance(node, ast.SetUp):
            self._emit_setup(node, scope, code)
        elif isinstance(node, ast.ReadBlock):
            self._emit_read_block(node, scope, code)
        elif isinstance(node, ast.GoStmt):
            # go f(x)：VM 无抢占式调度，降级为「立即求值并丢弃返回值」
            self._emit_expr(node.expr, scope, code)
            code.append((OP.POP,))
        elif isinstance(node, ast.SelectStmt):
            self._emit_select(node, scope, code)
        elif isinstance(node, ast.ImportDecl):
            self._emit_import(node, code)
        elif node.__class__ in self._NOOP_STMTS or \
                isinstance(node, self._NOOP_STMTS):
            return  # 标注/命令文字/文件标记/类型：编译期无操作
        else:
            # 裸表达式语句：求值后丢弃
            self._emit_expr(node, scope, code)
            code.append((OP.POP,))

    # ---- 块与语句 ----

    # 词法/标注层节点：编译期无代码（标注、命令文字/读取块、文件标记、段号、类型）
    # ReadBlock：顶层声明里 【...】（无 */ 标注时）与函数体内的 【...】
    # 都由 _parse_read_or_command 产出。此前不在本表，会掉到 _compile_stmt
    # 兜底的 _emit_expr，报「暂不支持的节点 ReadBlock」。它与 NLBlock 同为
    # 说明性文本，编译期不应产码。
    _NOOP_STMTS = (
        ast.GlobalIdStmt, ast.FileMarker, ast.Annotation,
        ast.CommandLiteral, ast.NLBlock, ast.ReadBlock, ast.Generate,
        ast.DefineOp, ast.AliasDef, ast.GlobalLoopSuffix,
        ast.SegLoopSuffix, ast.LoopFraction, ast.SetUpItem,
        ast.BasicType, ast.SetType, ast.FuncType, ast.TupleType,
        ast.AnnotatedType,
    )

    _STMT_NODES = (ast.MechUnit, ast.GenStmt, ast.OutputTrail, ast.Output,
                   ast.CodeBlock, ast.Binding, ast.LetBinding, ast.LetTupleBinding,
                   ast.IfStmt, ast.IfElseStmt, ast.WhileStmt, ast.ForStmt, ast.TryStmt,
                   ast.ThrowStmt, ast.RaiseExpr, ast.FuncDef,
                   # —— M1 补齐 ——
                   ast.ReturnStmt, ast.BreakStmt, ast.ContinueStmt,
                   ast.MatchStmt, ast.SwitchStmt, ast.LoopWhile, ast.LoopStep,
                   ast.Iteration, ast.ChainStmt, ast.SetUp, ast.GoStmt,
                   ast.SelectStmt, ast.ReadBlock, ast.StructDef,
                   ast.EnumDef, ast.AliasDef, ast.ImportDecl, ast.ModuleDecl,
                   ) + _NOOP_STMTS
    # 作为块尾时能产出值的语句
    _VALUE_STMTS = (ast.TryStmt, ast.IfStmt, ast.IfElseStmt,
                    ast.MatchStmt, ast.SwitchStmt)

    def _emit_block(self, block: ast.CodeBlock, scope: _Scope, code: list,
                    leave_last: bool) -> None:
        """编译语句块。leave_last=True 时最后一条表达式语句的值留在栈上
        （函数体/tail 表达式语义）；否则块编译后栈平衡。

        宽容消解：语句位置的 `var = expr`（parser 在 lambda 体内产出
        BinaryOp("=") 比较）按槽位赋值编译（首次出现即声明局部槽）。
        表达式内部的 =（如三元条件）仍是相等比较。"""
        stmts = block.stmts
        n = len(stmts)
        for i, s in enumerate(stmts):
            last = (i == n - 1)
            is_stmt = isinstance(s, self._STMT_NODES)
            is_assign = (not is_stmt and isinstance(s, ast.BinaryOp)
                         and s.op == "=" and isinstance(s.left, ast.Variable))
            if is_assign and not (last and leave_last):
                self._emit_expr(s.right, scope, code)
                if scope.is_main:
                    code.append((OP.STORE_GLOBAL, self.sconst(s.left.name)))
                else:
                    slot = self._declare_slot(scope, s.left.name)
                    code.append((OP.STORE_LOCAL, slot))
            elif last and leave_last and isinstance(s, self._VALUE_STMTS):
                # try / if / match / switch 作为块尾表达式：分支值即块值
                self._emit_if_try_value(s, scope, code)
            elif last and leave_last and not is_stmt:
                self._emit_expr(s, scope, code)
            elif is_stmt:
                self._compile_stmt(s, code, scope)
            else:
                self._emit_expr(s, scope, code)
                code.append((OP.POP,))
        if leave_last and (n == 0 or
                           (isinstance(stmts[-1], self._STMT_NODES)
                            and not isinstance(stmts[-1], self._VALUE_STMTS))):
            code.append((OP.PUSH_NULL,))

    def _emit_if_try_value(self, node, scope: _Scope, code: list) -> None:
        """块尾位置的 if/try/match/switch 值表达式发射。"""
        if isinstance(node, ast.TryStmt):
            self._emit_try_stmt(node, scope, code)
        elif isinstance(node, ast.MatchStmt):
            self._emit_match(node, scope, code, leave_value=True)
        elif isinstance(node, ast.SwitchStmt):
            self._emit_switch(node, scope, code, leave_value=True)
        else:
            self._emit_if_stmt(node, scope, code, leave_value=True)

    def _emit_binding_stmt(self, node, scope: _Scope, code: list, top_level: bool) -> None:
        """绑定语句：顶层写全局；块/函数内声明当前帧槽位。栈平衡。"""
        if top_level:
            self._compile_top_decl(node, code)
            return
        if isinstance(node, ast.Binding):
            self._emit_expr(node.value, scope, code)
            tgt = node.target
            name = tgt.name if isinstance(tgt, ast.Variable) else str(tgt)
            slot = self._declare_slot(scope, name)
            code.append((OP.STORE_LOCAL, slot))
        elif isinstance(node, ast.LetTupleBinding):
            self._emit_expr(node.value, scope, code)
            if scope.is_main:
                for nm in node.names:
                    scope.declare(nm, boxed=False)
                code.append((OP.UNPACK_SEQ, len(node.names)))
                for nm in reversed(node.names):
                    code.append((OP.STORE_GLOBAL, self.sconst(nm)))
            else:
                slots = [scope.declare(nm) for nm in node.names]
                code.append((OP.UNPACK_SEQ, len(slots)))
                for slot in reversed(slots):
                    code.append((OP.STORE_LOCAL, slot))
        else:
            # 无 body 的 let 语句：_emit_let 会留值（PUSH_NULL 或 body 值），丢弃
            self._emit_let(node, scope, code)
            code.append((OP.POP,))

    def _declare_slot(self, scope: _Scope, name: str) -> int:
        """块内绑定：已在当前帧声明则复用槽位（循环/分支重复赋值），否则新声明。"""
        kind, depth, slot, boxed = scope.resolve(name)
        if kind == "global":
            return scope.declare(name)
        return slot

    def _alloc_temp(self, scope: _Scope, hint: str):
        """分配临时存储：main 作用域用唯一名全局槽，否则用帧局部槽。
        返回 ('g', name) 或 ('l', slot)。"""
        if scope.is_main:
            scope.nslots += 1
            return ("g", f"__{hint}_{self._lam_seq}_{scope.nslots}")
        return ("l", scope.declare(hint))

    def _store_name(self, code: list, scope: _Scope, name: str) -> None:
        """把栈顶值写回具名变量（global / local / boxed local 皆可）。"""
        kind, _depth, slot, boxed = scope.resolve(name)
        if kind == "global":
            code.append((OP.STORE_GLOBAL, self.sconst(name)))
        elif kind == "local":
            code.append((OP.STORE_BOX if boxed else OP.STORE_LOCAL, slot))
        else:
            # 外层帧无 STORE_OUTER；外层槽仅在 boxed（let rec）时可写
            code.append((OP.STORE_BOX, slot))

    def _load_temp(self, code: list, t) -> None:
        if t[0] == "g":
            code.append((OP.LOAD_GLOBAL, self.sconst(t[1])))
        else:
            code.append((OP.LOAD_LOCAL, t[1]))

    def _store_temp(self, code: list, t) -> None:
        if t[0] == "g":
            code.append((OP.STORE_GLOBAL, self.sconst(t[1])))
        else:
            code.append((OP.STORE_LOCAL, t[1]))

    def _emit_if_stmt(self, stmt, scope: _Scope, code: list,
                      leave_value: bool = False) -> None:
        """if { } / if/elif/else 链：块在当前帧编译（绑定经同一帧槽位，块后可见）。

        leave_value=True 时作为块尾表达式编译：各分支块留尾值，无 else 时
        落空路径压 null；整体留一个值于栈上。"""
        if isinstance(stmt, ast.IfStmt):
            conditions = [stmt.cond]
            blocks = [stmt.then_block]
            else_block = stmt.else_block
        else:
            conditions = stmt.conditions
            blocks = stmt.blocks
            else_block = stmt.else_block
        end_jumps = []
        for cond, blk in zip(conditions, blocks):
            self._emit_expr(cond, scope, code)
            jz = len(code)
            code.append((OP.JZ, 0))
            if leave_value:
                self._emit_block(blk, scope, code, leave_last=True)
            else:
                self._emit_block(blk, scope, code, leave_last=False)
            jmp = len(code)
            code.append((OP.JMP, 0))
            end_jumps.append(jmp)
            code[jz] = (OP.JZ, len(code))
        if else_block is not None:
            self._emit_block(else_block, scope, code, leave_last=leave_value)
        elif leave_value:
            code.append((OP.PUSH_NULL,))
        if not leave_value:
            for j in end_jumps:
                code[j] = (OP.JMP, len(code))
        else:
            for j in end_jumps:
                code[j] = (OP.JMP, len(code))

    def _emit_while_stmt(self, stmt: ast.WhileStmt, scope: _Scope, code: list) -> None:
        """while cond { body }：JZ 退出 + 回跳。break 跳到循环尾，continue 跳到条件。"""
        self._loops.append({"brk": [], "cont": []})
        top = len(code)
        self._emit_expr(stmt.cond, scope, code)
        jz = len(code)
        code.append((OP.JZ, 0))
        self._emit_block(stmt.block, scope, code, leave_last=False)
        code.append((OP.JMP, top))
        code[jz] = (OP.JZ, len(code))
        frame = self._loops.pop()
        for j in frame["brk"]:
            code[j] = (OP.JMP, len(code))
        for j in frame["cont"]:
            code[j] = (OP.JMP, top)

    def _emit_for_stmt(self, stmt: ast.ForStmt, scope: _Scope, code: list) -> None:
        """for var(s) in iterable { body }：迭代槽 + 索引槽，len/get 内建驱动。
        var 为名字列表（parser 统一产 list）；多变量走 UNPACK_SEQ 解构。"""
        names = stmt.var
        if isinstance(names, str):
            names = [names]
        elif isinstance(names, ast.Variable):
            names = [names.name]
        self._emit_expr(stmt.iterable, scope, code)
        xs_t = self._alloc_temp(scope, "for_xs")
        i_t = self._alloc_temp(scope, "for_i")
        if scope.is_main:
            var_ts = [("g", nm) for nm in names]
        else:
            var_ts = [("l", self._declare_slot(scope, nm)) for nm in names]
        self._store_temp(code, xs_t)
        code.append((OP.PUSH_CONST, self.const(0)))
        self._store_temp(code, i_t)
        self._loops.append({"brk": [], "cont": []})
        top = len(code)
        # i < len(xs)（CALL 栈布局：fn 在下、arg 在上）
        self._load_temp(code, i_t)
        code.append((OP.LOAD_GLOBAL, self.sconst("len")))
        self._load_temp(code, xs_t)
        code.append((OP.CALL, 1))
        code.append((OP.BINOP, self.const("<")))
        jz = len(code)
        code.append((OP.JZ, 0))
        # elem = get(xs)(i)，多变量则 UNPACK_SEQ 解构
        code.append((OP.LOAD_GLOBAL, self.sconst("get")))
        self._load_temp(code, xs_t)
        code.append((OP.CALL, 1))
        self._load_temp(code, i_t)
        code.append((OP.CALL, 1))
        if len(var_ts) == 1:
            self._store_temp(code, var_ts[0])
        else:
            code.append((OP.UNPACK_SEQ, len(var_ts)))
            for t in reversed(var_ts):
                self._store_temp(code, t)
        self._emit_block(stmt.block, scope, code, leave_last=False)
        # i += 1
        inc_pos = len(code)  # continue 跳此处（跳回 top 会死循环）
        self._load_temp(code, i_t)
        code.append((OP.PUSH_CONST, self.const(1)))
        code.append((OP.BINOP, self.const("+")))
        self._store_temp(code, i_t)
        code.append((OP.JMP, top))
        code[jz] = (OP.JZ, len(code))
        frame = self._loops.pop()
        for j in frame["brk"]:
            code[j] = (OP.JMP, len(code))
        for j in frame["cont"]:
            code[j] = (OP.JMP, inc_pos)

    def _emit_try_stmt(self, stmt: ast.TryStmt, scope: _Scope, code: list) -> None:
        """try/catch/finally：三块各编译为 thunk，VM「调用捕获」返回 tagged 结果：
        正常 ["__正常__", 值]；异常 ["__异常__", 消息]。

        块内绑定为块作用域（thunk 私有帧）；try/catch 作为值表达式时其值为
        正常体或捕获体的尾值，finally 的返回值丢弃。语句位置则整体 POP。"""
        try_name = self._compile_thunk(stmt.try_block, scope)
        # guarded = 调用捕获(try_thunk)；result = guarded([])
        code.append((OP.LOAD_GLOBAL, self.sconst("调用捕获")))
        code.append((OP.MAKE_CLOSURE, try_name))
        code.append((OP.CALL, 1))
        code.append((OP.BUILD_LIST, 0))
        code.append((OP.CALL, 1))
        result_t = self._alloc_temp(scope, "try_result")
        self._store_temp(code, result_t)
        # result[0] == "__正常__"
        self._load_temp(code, result_t)
        code.append((OP.PUSH_CONST, self.const(0)))
        code.append((OP.INDEX_GET,))
        code.append((OP.PUSH_CONST, self.const("__正常__")))
        code.append((OP.BINOP, self.const("==")))
        jz = len(code)
        code.append((OP.JZ, 0))
        # 正常：result[1]
        self._load_temp(code, result_t)
        code.append((OP.PUSH_CONST, self.const(1)))
        code.append((OP.INDEX_GET,))
        jmp = len(code)
        code.append((OP.JMP, 0))
        # 异常：catch_thunk(result[1])；无 catch 则重新抛出消息
        code[jz] = (OP.JZ, len(code))
        if stmt.catch_block is not None:
            catch_params = [stmt.catch_var] if stmt.catch_var else []
            catch_name = self._compile_thunk(stmt.catch_block, scope, catch_params)
            code.append((OP.MAKE_CLOSURE, catch_name))
            self._load_temp(code, result_t)
            code.append((OP.PUSH_CONST, self.const(1)))
            code.append((OP.INDEX_GET,))
            code.append((OP.CALL, 1 if catch_params else 0))
        else:
            self._load_temp(code, result_t)
            code.append((OP.PUSH_CONST, self.const(1)))
            code.append((OP.INDEX_GET,))
            code.append((OP.RAISE,))
        code[jmp] = (OP.JMP, len(code))
        # finally：零参 thunk，返回值丢弃
        if stmt.finally_block is not None:
            fin_name = self._compile_thunk(stmt.finally_block, scope)
            code.append((OP.MAKE_CLOSURE, fin_name))
            code.append((OP.BUILD_LIST, 0))
            code.append((OP.CALL, 1))
            code.append((OP.POP,))

    def _param_vars(self, params) -> list:
        """let f(params)=body 的 params: [(Variable, type), ...] → [Variable]。"""
        out = []
        for p in params:
            pv = p[0] if isinstance(p, tuple) else p
            if not isinstance(pv, ast.Variable):
                pv = ast.Variable(name=str(pv))
            out.append(pv)
        return out

    def _compile_func(self, fdef: ast.FuncDef) -> MFunction:
        lam = fdef.body
        scope = _Scope(None)
        for p in lam.params:
            scope.declare(p.name if isinstance(p, ast.Variable) else str(p))
        code: list = []
        self._emit_body(lam.body, scope, code)
        code.append((OP.RET,))
        fn = MFunction(name=fdef.name, arity=len(lam.params),
                       nlocals=scope.nslots, code=code,
                       params=[p.name if isinstance(p, ast.Variable) else str(p)
                               for p in lam.params])
        self.mod.functions[fdef.name] = fn
        return fn

    def _compile_lambda(self, lam: ast.Lambda, scope: _Scope) -> str:
        """编译匿名 lambda，返回函数表中的内部名。"""
        self._lam_seq += 1
        name = f"__lam_{self._lam_seq}"
        inner = _Scope(scope)
        for p in lam.params:
            inner.declare(p.name if isinstance(p, ast.Variable) else str(p))
        code: list = []
        self._emit_body(lam.body, inner, code)
        code.append((OP.RET,))
        fn = MFunction(name=name, arity=len(lam.params),
                       nlocals=inner.nslots, code=code,
                       params=[p.name if isinstance(p, ast.Variable) else str(p)
                               for p in lam.params])
        self.mod.functions[name] = fn
        return name

    def _compile_thunk(self, body, scope: _Scope, param_names: list | None = None) -> str:
        """编译 try/catch/finally 块为独立零参（或带参）函数，返回函数名。

        块内绑定为块作用域（thunk 私有帧）；对外层变量只读（经闭包帧链
        LOAD_OUTER）。catch thunk 单参 e 接收异常消息字符串。"""
        self._lam_seq += 1
        name = f"__lam_{self._lam_seq}"
        inner = _Scope(scope)
        for p in (param_names or []):
            inner.declare(p)
        code: list = []
        self._emit_body(body, inner, code)
        code.append((OP.RET,))
        fn = MFunction(name=name, arity=len(param_names or []),
                       nlocals=inner.nslots, code=code, params=list(param_names or []))
        self.mod.functions[name] = fn
        return name

    # ---- M1 新增发射器 ----

    def _emit_set_construct_args(self, node: ast.SetConstruct,
                                 scope: _Scope, code: list) -> None:
        """集合构造：压入 (form, variables, conditions+literals) 三参数。"""
        code.append((OP.PUSH_CONST, self.const(node.form or "set")))
        names = [v.name if isinstance(v, ast.Variable) else str(v)
                 for v in (node.variables or [])]
        for nm in names:
            code.append((OP.PUSH_CONST, self.const(nm)))
        code.append((OP.BUILD_LIST, len(names)))
        tail = list(node.conditions or []) + list(node.literals or [])
        for e in tail:
            self._emit_expr(e, scope, code)
        code.append((OP.BUILD_LIST, len(tail)))

    def _emit_match(self, node: ast.MatchStmt, scope: _Scope,
                    code: list, leave_value: bool = False) -> None:
        """match <expr> { | <pattern> [if guard] => <body> }

        降级为 if/elif 链：每个分支把被匹配值存入临时槽，按模式测试。
        模式：字面量 / 变量绑定 / ConstructorPat / _ 通配。"""
        scrut_t = self._alloc_temp(scope, "match_s")
        self._emit_expr(node.scrutinee, scope, code)
        self._store_temp(code, scrut_t)
        end_jumps: list[int] = []
        for pat, guard, body in node.branches:
            fails: list[int] = []
            # 模式测试失败时跳到下一分支；绑定型模式顺带把值存入槽位
            self._emit_pattern_test(pat, scrut_t, scope, code, fails)
            if guard is not None:
                self._emit_expr(guard, scope, code)
                jz = len(code); code.append((OP.JZ, 0))
                fails.append(jz)
            self._emit_body(body, scope, code)
            if not leave_value:
                code.append((OP.POP,))
            jmp = len(code); code.append((OP.JMP, 0))
            end_jumps.append(jmp)
            # 仅改跳转目标，必须保留 JZ 的条件语义
            for j in fails:
                code[j] = (code[j][0], len(code))
        if leave_value:
            code.append((OP.PUSH_NULL,))
        for j in end_jumps:
            code[j] = (OP.JMP, len(code))

    def _emit_pattern_test(self, pat, scrut_t, scope: _Scope,
                           code: list, fails: list[int]) -> None:
        """模式测试：从临时槽载入被匹配值后测试，失败则跳到 fails 各补丁点。

        全程只用临时槽传递值，保证成功/失败路径栈都平衡。
        模式：字面量 / 变量绑定 / ConstructorPat / `_` 通配。
        """
        self._load_temp(code, scrut_t)
        self._emit_pattern_on_value(pat, scope, code, fails)

    def _emit_pattern_on_value(self, pat, scope: _Scope,
                               code: list, fails: list[int]) -> None:
        """栈顶为待测值：就地测试并消费之，失败跳到 fails。"""
        val_t = self._alloc_temp(scope, "pat_v")
        self._store_temp(code, val_t)
        if isinstance(pat, ast.ConstructorPat):
            # 容器 → 取 pat.name 字段得到载荷：
            #   单字段时载荷即该字段值；多字段时载荷为列表/元组，按位取。
            # 先做字段存在性判定，缺失时跳到下一分支（不得抛 KeyError）。
            # BINOP "in" 的左操作数是元素，故先压键名再压容器。
            code.append((OP.PUSH_CONST, self.const(pat.name)))
            self._load_temp(code, val_t)
            code.append((OP.BINOP, self.const("in")))
            jz = len(code); code.append((OP.JZ, 0))
            fails.append(jz)
            self._load_temp(code, val_t)
            code.append((OP.PUSH_CONST, self.const(pat.name)))
            code.append((OP.INDEX_GET,))
            if len(pat.fields) == 1:
                self._emit_pattern_on_value(pat.fields[0], scope, code, fails)
                return
            box_t = self._alloc_temp(scope, "pat_box")
            self._store_temp(code, box_t)
            for k, sub in enumerate(pat.fields):
                self._load_temp(code, box_t)
                code.append((OP.PUSH_CONST, self.const(k)))
                code.append((OP.INDEX_GET,))
                self._emit_pattern_on_value(sub, scope, code, fails)
            return
        if isinstance(pat, ast.Variable):
            if pat.is_placeholder or pat.name == "_":
                return  # 通配：恒真，不绑定
            # 变量模式恒真：绑定被匹配值
            self._load_temp(code, val_t)
            self._emit_pattern_bind(pat.name, scope, code)
            return
        # 字面量模式
        self._load_temp(code, val_t)
        self._emit_expr(pat, scope, code)
        code.append((OP.BINOP, self.const("==")))
        jz = len(code); code.append((OP.JZ, 0))
        fails.append(jz)

    def _emit_pattern_bind(self, name: str, scope: _Scope,
                           code: list) -> None:
        """把当前栈顶值绑定到模式变量名。"""
        if scope.is_main:
            code.append((OP.STORE_GLOBAL, self.sconst(name)))
        else:
            code.append((OP.STORE_LOCAL, self._declare_slot(scope, name)))

    def _emit_switch(self, node: ast.SwitchStmt, scope: _Scope,
                     code: list, leave_value: bool = False) -> None:
        """switch v { case c: block ... default: block } → == 比较的 if/elif 链。"""
        val_t = self._alloc_temp(scope, "switch_v")
        self._emit_expr(node.value, scope, code)
        self._store_temp(code, val_t)
        end_jumps: list[int] = []
        for case_val, blk in node.cases:
            self._load_temp(code, val_t)
            self._emit_expr(case_val, scope, code)
            code.append((OP.BINOP, self.const("==")))
            jz = len(code); code.append((OP.JZ, 0))
            self._emit_body(blk, scope, code)
            if not leave_value:
                code.append((OP.POP,))
            jmp = len(code); code.append((OP.JMP, 0))
            end_jumps.append(jmp)
            code[jz] = (OP.JZ, len(code))
        if node.default_block is not None:
            self._emit_body(node.default_block, scope, code)
            if not leave_value:
                code.append((OP.POP,))
        elif leave_value:
            code.append((OP.PUSH_NULL,))
        for j in end_jumps:
            code[j] = (OP.JMP, len(code))

    def _emit_loop_step(self, node: ast.LoopStep, scope: _Scope,
                        code: list) -> None:
        """x >> expr { block }：对 expr 施加步进变换后循环。"""
        names = node.var
        if isinstance(names, str):
            names = [names]
        elif isinstance(names, ast.Variable):
            names = [names.name if not names.is_placeholder else None]
        elif isinstance(names, list):
            names = [n.name if isinstance(n, ast.Variable) and
                     not n.is_placeholder else None for n in names]
        var_ts = []
        for nm in names:
            if nm is None:
                var_ts.append(None)
            elif scope.is_main:
                var_ts.append(("g", nm))
            else:
                var_ts.append(("l", self._declare_slot(scope, nm)))
        real = [t for t in var_ts if t is not None]
        if not real or node.iterable is None:
            return
        # for v in iterable { body }
        fake = ast.ForStmt(var=[v[1] for v in real], iterable=node.iterable,
                           block=node.block)
        self._emit_for_stmt(fake, scope, code)

    def _emit_iteration(self, node: ast.Iteration, scope: _Scope,
                        code: list) -> None:
        """?x / x >> expr { block }：迭代赋值语义，同 LoopStep。"""
        self._emit_loop_step(ast.LoopStep(var=node.var, placeholder=node.placeholder,
                                          iterable=node.iterable,
                                          block=node.block), scope, code)

    def _emit_setup(self, node: ast.SetUp, scope: _Scope,
                    code: list) -> None:
        """@：a=2，b=3 —— 设定项按绑定编译；?占位目标与无值项跳过。"""
        for item in node.items:
            if item.value is None:
                continue
            tgt = item.target
            if isinstance(tgt, ast.Variable) and tgt.is_placeholder:
                continue  # ？占位符不落地
            if not isinstance(tgt, ast.Variable):
                continue
            if scope.is_main:
                self._emit_expr(item.value, scope, code)
                code.append((OP.STORE_GLOBAL, self.sconst(tgt.name)))
            else:
                self._emit_expr(item.value, scope, code)
                code.append((OP.STORE_LOCAL,
                             self._declare_slot(scope, tgt.name)))

    def _emit_read_block(self, node: ast.ReadBlock, scope: _Scope,
                         code: list) -> None:
        """【…】：内容为表达式则求值丢弃；为标注/命令文字则编译期无操作。"""
        content = node.content
        if content is None:
            return
        if isinstance(content, str):
            return  # 标注文字 或 命令名
        if isinstance(content, (ast.CommandLiteral, ast.Annotation,
                                 ast.NLBlock)):
            return
        if hasattr(content, "__dataclass_fields__"):
            self._emit_expr(content, scope, code)
            code.append((OP.POP,))
            return

    def _emit_select(self, node: ast.SelectStmt, scope: _Scope,
                     code: list) -> None:
        """select { case <-ch => body ... }

        VM 无抢占调度，降级为「按分支顺序取第一个就绪的通道」：
        通道就绪（缓冲非空）则取其首元素并执行该分支。"""
        for br in node.branches:
            chan = body = None
            if isinstance(br, ast.TupleExpr) and len(br.elements) == 2:
                chan, body = br.elements
            elif isinstance(br, (tuple, list)) and len(br) == 2:
                chan, body = br
            else:
                continue
            ch_t = self._alloc_temp(scope, "sel_ch")
            self._emit_expr(chan, scope, code)
            self._store_temp(code, ch_t)
            # 就绪判定：len(ch["缓冲"]) > 0
            self._load_temp(code, ch_t)
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            code.append((OP.INDEX_GET,))
            code.append((OP.LOAD_GLOBAL, self.sconst("len")))
            self._load_temp(code, ch_t)
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            code.append((OP.INDEX_GET,))
            code.append((OP.CALL, 1))
            code.append((OP.BINOP, self.const(">")))
            jz = len(code); code.append((OP.JZ, 0))
            # 弹出首元素交给分支体
            self._load_temp(code, ch_t)
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            code.append((OP.INDEX_GET,))
            code.append((OP.PUSH_CONST, self.const(0)))
            code.append((OP.INDEX_GET,))
            self._emit_body(body, scope, code)
            code.append((OP.POP,))
            jmp = len(code); code.append((OP.JMP, 0))
            code[jz] = (OP.JZ, len(code))
            code[jmp] = (OP.JMP, len(code))

    def _emit_import(self, node: ast.ImportDecl, code: list) -> None:
        """use/import：M3V 单模块运行时无跨模块加载，记为全局标记供宿主检查。"""
        if node.module_name:
            code.append((OP.PUSH_CONST,
                         self.const(f"<import {node.module_name}>")))
            code.append((OP.STORE_GLOBAL,
                         self.sconst(f"__import_{node.module_name}")))

    def _emit_param_vars_unused(self, params):
        return self._param_vars(params)

    def _emit_body(self, body, scope: _Scope, code: list) -> None:
        """函数/lambda/thunk 体：CodeBlock 走语句编译（留尾值），否则表达式。

        文档类节点（【...】 读取块 ReadBlock / 自然语言块 NLBlock）作函数体时
        不是 CodeBlock，但它们编译期无码：此时按「尾值为 None」发射 PUSH_NULL，
        与 _emit_block 的 leave_last 收尾（末句是语句则补 PUSH_NULL）一致。
        """
        if isinstance(body, ast.CodeBlock):
            self._emit_block(body, scope, code, leave_last=True)
        elif isinstance(body, self._NOOP_STMTS):
            code.append((OP.PUSH_NULL,))
        else:
            self._emit_expr(body, scope, code)

    # ---- 表达式发射 ----
    def _emit_expr(self, node, scope: _Scope, code: list) -> None:
        if node is None:
            code.append((OP.PUSH_NULL,))
            return

        if isinstance(node, ast.CodeBlock):
            # 表达式位置的代码块：语句序列，值为尾表达式
            self._emit_block(node, scope, code, leave_last=True)

        elif isinstance(node, ast.IntegerLit):
            code.append((OP.PUSH_CONST, self.const(int(node.value))))
        elif isinstance(node, ast.FloatLit):
            code.append((OP.PUSH_CONST, self.const(float(node.value))))
        elif isinstance(node, ast.StringLit):
            code.append((OP.PUSH_CONST, self.const(node.value)))
        elif isinstance(node, ast.BoolLit):
            code.append((OP.PUSH_TRUE if node.value else OP.PUSH_FALSE,))
        elif isinstance(node, ast.Variable):
            self._emit_load(node.name, scope, code)

        elif isinstance(node, ast.Lambda):
            name = self._compile_lambda(node, scope)
            code.append((OP.MAKE_CLOSURE, name))

        elif isinstance(node, ast.FuncApp):
            callee, args = _flatten_call(node)
            # 完全应用到已知 arity 的顶层函数：融成单条 CALL N。
            # arity 0 的无参函数亦走此路径（args 为空 -> CALL 0）。
            if (isinstance(callee, ast.Variable)
                    and not callee.is_placeholder
                    and self._fn_arities.get(callee.name) == len(args)):
                self._emit_load(callee.name, scope, code)
                for a in args:
                    self._emit_expr(a, scope, code)
                code.append((OP.CALL, len(args)))
                return
            # 其余情形（Python 内建、lambda、偏应用、实参数量未定）保持
            # 逐次 CALL 1，由 VM 依 Closure/Partial 语义柯里化。
            self._emit_expr(node.func, scope, code)
            self._emit_expr(node.arg, scope, code)
            code.append((OP.CALL, 1))

        elif isinstance(node, ast.BinaryOp):
            # and / or 为短路特殊形式（与宿主解释器语义一致）：
            #   a and b：a 假则结果为 a（不求值 b），否则结果为 b
            #   a or  b：a 真则结果为 a（不求值 b），否则结果为 b
            if node.op == "and":
                self._emit_expr(node.left, scope, code)
                code.append((OP.DUP,))
                jz = len(code); code.append((OP.JZ, 0))
                code.append((OP.POP,))
                self._emit_expr(node.right, scope, code)
                code[jz] = (OP.JZ, len(code))
                return
            if node.op == "or":
                self._emit_expr(node.left, scope, code)
                code.append((OP.DUP,))
                jnz = len(code); code.append((OP.JNZ, 0))
                code.append((OP.POP,))
                self._emit_expr(node.right, scope, code)
                code[jnz] = (OP.JNZ, len(code))
                return
            op = _BIN_OPS.get(node.op)
            if op is None:
                raise RuntimeError(f"字节码编译：不支持的二元运算符 {node.op!r}")
            folded = _fold_bin(op, node.left, node.right)
            if folded is not _NO_FOLD:
                code.append((OP.PUSH_CONST, self.const(folded)))
                return
            self._emit_expr(node.left, scope, code)
            self._emit_expr(node.right, scope, code)
            code.append((OP.BINOP, self.const(op)))

        elif isinstance(node, ast.UnaryOp):
            if node.op == "null":
                # bare null 字面量（parser 偶尔产出 UnaryOp('null')）
                code.append((OP.PUSH_NULL,))
                return
            op = _UNARY_OPS.get(node.op)
            if op is None:
                raise RuntimeError(f"字节码编译：不支持的一元运算符 {node.op!r}")
            folded = _fold_unary(op, node.operand)
            if folded is not _NO_FOLD:
                code.append((OP.PUSH_CONST, self.const(folded)))
                return
            self._emit_expr(node.operand, scope, code)
            code.append((OP.UNARYOP, self.const(op)))

        elif isinstance(node, ast.IfExpr):
            self._emit_expr(node.cond, scope, code)
            jz = len(code); code.append((OP.JZ, 0))
            self._emit_expr(node.then, scope, code)
            jmp = len(code); code.append((OP.JMP, 0))
            code[jz] = (OP.JZ, len(code))
            self._emit_expr(node.else_, scope, code)
            code[jmp] = (OP.JMP, len(code))

        elif isinstance(node, ast.LetBinding):
            self._emit_let(node, scope, code)

        elif isinstance(node, ast.ListLiteral):
            for el in node.elements:
                self._emit_expr(el, scope, code)
            code.append((OP.BUILD_LIST, len(node.elements)))

        elif isinstance(node, ast.TupleExpr):
            for el in node.elements:
                self._emit_expr(el, scope, code)
            code.append((OP.BUILD_LIST, len(node.elements)))  # 元组按列表处理

        elif isinstance(node, ast.DictLiteral):
            n = 0
            for k, v in zip(node.keys, node.values):
                key = k.name if isinstance(k, ast.Variable) else self._literal_key(k)
                code.append((OP.PUSH_CONST, self.const(key)))
                self._emit_expr(v, scope, code)
                n += 1
            code.append((OP.BUILD_DICT, n))

        elif isinstance(node, ast.IsExpr):
            # a is b：同一性（不可变标量退化为相等）
            self._emit_expr(node.left, scope, code)
            self._emit_expr(node.right, scope, code)
            code.append((OP.BINOP, self.const("is")))

        elif isinstance(node, ast.TypeOfExpr):
            # typeof x → 调用内建 typeof
            code.append((OP.LOAD_GLOBAL, self.sconst("typeof")))
            self._emit_expr(node.operand, scope, code)
            code.append((OP.CALL, 1))

        elif isinstance(node, ast.Belongs):
            # a ∈ b：成员判定
            self._emit_expr(node.left, scope, code)
            self._emit_expr(node.right, scope, code)
            code.append((OP.BINOP, self.const("in")))

        elif isinstance(node, ast.AngleExpr):
            # ⟨expr⟩：单值包装，直接取内层值
            self._emit_expr(node.expr, scope, code)

        elif isinstance(node, ast.SafePathExpr):
            # a?.b / a?.[i]：a 为空则整体为空（不抛错）
            # 属性形式的 node.right 是裸 str（属性名，非表达式），
            # 故须以常量压栈，不能走 _emit_expr（它只收 AST 节点）。
            code.append((OP.LOAD_GLOBAL,
                         self.sconst("安全索引" if node.is_index else "安全取属性")))
            self._emit_expr(node.left, scope, code)
            if node.is_index:
                self._emit_expr(node.right, scope, code)
            else:
                code.append((OP.PUSH_CONST, self.const(node.right)))
            code.append((OP.CALL, 2))

        elif isinstance(node, ast.ChanExpr):
            # chan T：降级为 {"缓冲": [], "容量": n, "关闭": False}
            # BUILD_DICT 栈布局为 k1 v1 k2 v2 ...，故每个键紧跟其值
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            code.append((OP.BUILD_LIST, 0))
            code.append((OP.PUSH_CONST, self.const("容量")))
            code.append((OP.PUSH_CONST, self.const(node.buffer_size or 0)))
            code.append((OP.PUSH_CONST, self.const("关闭")))
            code.append((OP.PUSH_CONST, self.const(False)))
            code.append((OP.BUILD_DICT, 3))

        elif isinstance(node, ast.SendExpr):
            # ch <- v：把 v 追加到 ch["缓冲"]，求值为 true。
            # append 内建返回**新列表**（list(xs) + [x]），不是原地修改，
            # 故须用 _dict_put 把新列表写回 ch，再压 true。
            ch_t = self._alloc_temp(scope, "send_ch")
            buf_t = self._alloc_temp(scope, "send_buf")
            self._emit_expr(node.channel, scope, code)
            self._store_temp(code, ch_t)
            # buf = append(ch["缓冲"], v)
            code.append((OP.LOAD_GLOBAL, self.sconst("append")))
            self._load_temp(code, ch_t)
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            code.append((OP.INDEX_GET,))
            self._emit_expr(node.value, scope, code)
            code.append((OP.CALL, 2))
            self._store_temp(code, buf_t)
            # ch = _dict_put(ch, "缓冲", buf)
            code.append((OP.LOAD_GLOBAL, self.sconst("_dict_put")))
            self._load_temp(code, ch_t)
            code.append((OP.PUSH_CONST, self.const("缓冲")))
            self._load_temp(code, buf_t)
            code.append((OP.CALL, 3))
            # 写回通道变量（须是具名变量才能回写；否则退化为求值丢弃）
            chan = node.channel
            if isinstance(chan, ast.Variable) and not chan.is_placeholder:
                self._store_name(code, scope, chan.name)
            else:
                code.append((OP.POP,))
            code.append((OP.PUSH_TRUE,))

        elif isinstance(node, ast.SetConstruct):
            code.append((OP.LOAD_GLOBAL, self.sconst("构造集合")))
            self._emit_set_construct_args(node, scope, code)
            code.append((OP.CALL, 3))

        elif isinstance(node, ast.IndexExpr):
            self._emit_expr(node.container, scope, code)
            self._emit_expr(node.index, scope, code)
            code.append((OP.INDEX_GET,))

        elif isinstance(node, ast.SliceExpr):
            self._emit_expr(node.container, scope, code)
            if node.start is not None:
                self._emit_expr(node.start, scope, code)
            else:
                code.append((OP.PUSH_NULL,))
            if node.end is not None:
                self._emit_expr(node.end, scope, code)
            else:
                code.append((OP.PUSH_NULL,))
            code.append((OP.BUILD_SLICE,))

        elif isinstance(node, ast.PathExpr):
            self._emit_expr(node.left, scope, code)
            field = node.right
            fname = field.name if isinstance(field, ast.Variable) else str(field)
            code.append((OP.GET_ATTR, self.sconst(fname)))

        elif isinstance(node, ast.RaiseExpr):
            self._emit_expr(node.value, scope, code)
            code.append((OP.RAISE,))

        elif isinstance(node, ast.LetTupleBinding):
            # let (a, b, ...) = <seq> in <body>
            self._emit_expr(node.value, scope, code)
            if scope.is_main:
                # main 无局部槽数组：声明仅为让后续读取解析为同名全局，
                # 与 _emit_let 的 main 分支同理（否则 STORE_LOCAL 越界
                # 访问 locals[slot]，嵌套 let (a,b) 在 main 下抛 IndexError）。
                names = []
                for nm in node.names:
                    scope.declare(nm, boxed=False)
                    names.append(nm)
                code.append((OP.UNPACK_SEQ, len(names)))
                for nm in reversed(names):
                    code.append((OP.STORE_GLOBAL, self.sconst(nm)))
            else:
                slots = [scope.declare(nm) for nm in node.names]
                code.append((OP.UNPACK_SEQ, len(slots)))
                for slot in reversed(slots):
                    code.append((OP.STORE_LOCAL, slot))
            if node.body is not None:
                self._emit_expr(node.body, scope, code)
            else:
                code.append((OP.PUSH_NULL,))

        elif isinstance(node, ast.Output):
            # 表达式位置的输出 #[expr]：求值、输出，值仍留在栈上
            if node.expr is not None:
                self._emit_expr(node.expr, scope, code)
                code.append((OP.DUP,))
                code.append((OP.OUTPUT,))
            else:
                code.append((OP.PUSH_NULL,))

        elif isinstance(node, ast.OutputTrail):
            if getattr(node, "output", None) is not None:
                self._emit_expr(node.output, scope, code)
            else:
                code.append((OP.PUSH_NULL,))

        else:
            raise RuntimeError(f"字节码编译：暂不支持的节点 {type(node).__name__}")

    def _literal_key(self, node) -> str:
        if isinstance(node, ast.StringLit):
            return node.value
        if isinstance(node, ast.IntegerLit):
            return str(node.value)
        return str(node)

    def _emit_load(self, name: str, scope: _Scope, code: list) -> None:
        kind, depth, slot, boxed = scope.resolve(name)
        if kind == "global":
            code.append((OP.LOAD_GLOBAL, self.sconst(name)))
        elif kind == "local":
            code.append((OP.LOAD_BOX if boxed else OP.LOAD_LOCAL, slot))
        else:
            code.append((OP.LOAD_OUTER_BOX if boxed else OP.LOAD_OUTER, depth, slot))

    def _emit_let(self, node: ast.LetBinding, scope: _Scope, code: list) -> None:
        boxed = bool(node.is_recursive)
        # 函数式 let f(params) = body：parser 可能存为 params+裸体，
        # 也可能直接产出 FuncDef 节点，统一归约为 Lambda
        value = node.value
        if isinstance(value, ast.FuncDef):
            value = value.body
        if getattr(node, "params", None):
            value = ast.Lambda(params=self._param_vars(node.params), body=node.value)
        if boxed:
            # let rec：先声明 Box 槽位，RHS 中自引用经 Box 读取（帧链共享）
            if scope.is_main:
                # main 无局部槽数组：rec 绑定退化为同名全局，
                # 否则 MAKE_BOX/STORE_BOX 会越界访问 locals[slot]
                # （互递归 let rec 曾在此抛 IndexError）。
                # 同级多个 let rec 依声明顺序依次定义，body 通过
                # LOAD_GLOBAL 读取已定义者。
                self._emit_expr(value, scope, code)
                scope.declare(node.name, boxed=False)
                code.append((OP.STORE_GLOBAL, self.sconst(node.name)))
            else:
                slot = scope.declare(node.name, boxed=True)
                code.append((OP.MAKE_BOX, slot))
                self._emit_expr(value, scope, code)
                code.append((OP.STORE_BOX, slot))
        else:
            # 非 rec：先在「新名字尚未声明」的作用域中求值 RHS，
            # 使 `let x = x + 1` 正确读取外层 x（避免读到未初始化槽位），
            # 然后再声明槽位供 body 使用
            self._emit_expr(value, scope, code)
            if scope.is_main:
                # main 无局部槽数组：声明仅为让后续读取解析为同名全局
                scope.declare(node.name, boxed=False)
                code.append((OP.STORE_GLOBAL, self.sconst(node.name)))
            else:
                slot = scope.declare(node.name, boxed=False)
                code.append((OP.STORE_LOCAL, slot))
        if node.body is not None:
            self._emit_expr(node.body, scope, code)
        else:
            code.append((OP.PUSH_NULL,))


def compile_program(program: ast.Program) -> MModule:
    return Compiler().compile_program(program)


def compile_source(source: str) -> MModule:
    from src.parser import parse
    if source and source[0] == "\ufeff":  # 容忍 UTF-8 BOM
        source = source.lstrip("\ufeff")
    return compile_program(parse(source))
