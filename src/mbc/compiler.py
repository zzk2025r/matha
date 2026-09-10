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
    """词法作用域：name -> (slot, boxed)。"""
    __slots__ = ("parent", "names", "nslots")

    def __init__(self, parent: "_Scope | None"):
        self.parent = parent
        self.names: dict[str, tuple[int, bool]] = {}
        self.nslots = 0

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
        # 其余声明类型（struct/enum/语句等）本轮暂不编译到字节码

    def _compile_stmt(self, node, code: list) -> None:
        """编译语句链（MechUnit/GenStmt/OutputTrail/Output/CodeBlock）。"""
        if node is None:
            return
        if isinstance(node, ast.MechUnit):
            self._compile_stmt(node.body, code)
        elif isinstance(node, ast.GenStmt):
            self._compile_stmt(node.content, code)
        elif isinstance(node, ast.OutputTrail):
            self._compile_stmt(node.output, code)
        elif isinstance(node, ast.Output):
            if node.expr is not None:
                self._emit_expr(node.expr, _Scope(None), code)
                code.append((OP.OUTPUT,))
        elif isinstance(node, ast.CodeBlock):
            for s in node.stmts:
                self._compile_stmt(s, code)
        elif isinstance(node, (ast.Binding, ast.LetBinding)):
            self._compile_top_decl(node, code)

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
        self._emit_expr(lam.body, scope, code)
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
        self._emit_expr(lam.body, inner, code)
        code.append((OP.RET,))
        fn = MFunction(name=name, arity=len(lam.params),
                       nlocals=inner.nslots, code=code,
                       params=[p.name if isinstance(p, ast.Variable) else str(p)
                               for p in lam.params])
        self.mod.functions[name] = fn
        return name

    # ---- 表达式发射 ----
    def _emit_expr(self, node, scope: _Scope, code: list) -> None:
        if node is None:
            code.append((OP.PUSH_NULL,))
            return

        if isinstance(node, ast.IntegerLit):
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
        slot = scope.declare(node.name, boxed=boxed)
        if boxed:
            code.append((OP.MAKE_BOX, slot))
        # 函数式 let f(params) = body：parser 可能存为 params+裸体，
        # 也可能直接产出 FuncDef 节点，统一归约为 Lambda
        value = node.value
        if isinstance(value, ast.FuncDef):
            value = value.body
        if getattr(node, "params", None):
            value = ast.Lambda(params=self._param_vars(node.params), body=node.value)
        self._emit_expr(value, scope, code)
        if boxed:
            code.append((OP.STORE_BOX, slot))
        else:
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
