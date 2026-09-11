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
        """返回 (kind, depth, slot, boxed)；kind ∈ {'local','outer','global'}。"""
        if name in self.names:
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
}
_UNARY_OPS = {"-": "neg", "not": "not", "非": "not"}


class Compiler:
    def __init__(self):
        self.mod = MModule()
        self._lam_seq = 0

    # ---- 常量池 ----
    def const(self, value) -> int:
        self.mod.constants.append(value)
        return len(self.mod.constants) - 1

    def sconst(self, s: str) -> int:
        return self.const(s)

    # ---- 入口 ----
    def compile_program(self, program: ast.Program) -> MModule:
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
            self._emit_expr(decl.value, _Scope(None), code)
            tgt = decl.target
            name = tgt.name if isinstance(tgt, ast.Variable) else str(tgt)
            code.append((OP.STORE_GLOBAL, self.sconst(name)))
        elif isinstance(decl, ast.LetBinding):
            # 顶层 let：求值后存入全局
            if getattr(decl, "params", None):
                lam = ast.Lambda(params=self._param_vars(decl.params), body=decl.value)
                self._emit_expr(lam, _Scope(None), code)
            else:
                self._emit_expr(decl.value, _Scope(None), code)
            code.append((OP.STORE_GLOBAL, self.sconst(decl.name)))
        elif isinstance(decl, ast.LetTupleBinding):
            self._emit_expr(decl.value, _Scope(None), code)
            code.append((OP.UNPACK_SEQ, len(decl.names)))
            for nm in reversed(decl.names):
                code.append((OP.STORE_GLOBAL, self.sconst(nm)))
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
        # 其余声明类型（struct/enum 等）在字节码层无表示

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
        else:
            # 裸表达式语句：求值后丢弃
            self._emit_expr(node, scope, code)
            code.append((OP.POP,))

    # ---- 块与语句 ----

    _STMT_NODES = (ast.MechUnit, ast.GenStmt, ast.OutputTrail, ast.Output,
                   ast.CodeBlock, ast.Binding, ast.LetBinding, ast.LetTupleBinding,
                   ast.IfStmt, ast.IfElseStmt, ast.WhileStmt, ast.ForStmt, ast.TryStmt,
                   ast.ThrowStmt, ast.RaiseExpr, ast.FuncDef)
    # 作为块尾时能产出值的语句
    _VALUE_STMTS = (ast.TryStmt, ast.IfStmt, ast.IfElseStmt)

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
            elif last and leave_last and isinstance(s, (ast.TryStmt, ast.IfStmt, ast.IfElseStmt)):
                # try / if 作为块尾表达式：分支值即块值
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
        """块尾位置的 if/try 值表达式发射。"""
        if isinstance(node, ast.TryStmt):
            self._emit_try_stmt(node, scope, code)
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
        """while cond { body }：JZ 退出 + 回跳。"""
        top = len(code)
        self._emit_expr(stmt.cond, scope, code)
        jz = len(code)
        code.append((OP.JZ, 0))
        self._emit_block(stmt.block, scope, code, leave_last=False)
        code.append((OP.JMP, top))
        code[jz] = (OP.JZ, len(code))

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
        self._load_temp(code, i_t)
        code.append((OP.PUSH_CONST, self.const(1)))
        code.append((OP.BINOP, self.const("+")))
        self._store_temp(code, i_t)
        code.append((OP.JMP, top))
        code[jz] = (OP.JZ, len(code))

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

    def _emit_body(self, body, scope: _Scope, code: list) -> None:
        """函数/lambda/thunk 体：CodeBlock 走语句编译（留尾值），否则表达式。"""
        if isinstance(body, ast.CodeBlock):
            self._emit_block(body, scope, code, leave_last=True)
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
            slot = scope.declare(node.name, boxed=True)
            code.append((OP.MAKE_BOX, slot))
            self._emit_expr(value, scope, code)
            code.append((OP.STORE_BOX, slot))
        else:
            # 非 rec：先在「新名字尚未声明」的作用域中求值 RHS，
            # 使 `let x = x + 1` 正确读取外层 x（避免读到未初始化槽位），
            # 然后再声明槽位供 body 使用
            self._emit_expr(value, scope, code)
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
