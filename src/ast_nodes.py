"""Matha 抽象语法树节点定义。

对应 EBNF 各章产生式，每个 AST 节点用 dataclass 表示。
节点命名与 EBNF 非终结符对应（驼峰命名）。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
# 顶层结构（EBNF §1）
# ============================================================

@dataclass
class Program:
    """<program> = { <top_level> }"""
    decls: list[Any] = field(default_factory=list)


# ============================================================
# 词法层 AST（EBNF §2）—— 命令 / 标注 / 设定 / 循环后缀
# ============================================================

@dataclass
class Annotation:
    """<annotation> = "*/" , <annot_text> , [ "*" , <expr> ] , "/*" """
    text: str
    formula: Optional[Any] = None  # <expr>，可选


@dataclass
class CommandLiteral:
    """<command_literal> = 《文字》 | 【文字】（两种写法等价，M3.1）"""
    text: str
    form: str = "bracket"  # "bracket"（【】）或 "cn"（《》）


@dataclass
class SetUpItem:
    """<set_up_item> = ( <variable> | <path_expr> ) , [ <annotation> ] , [ "=" , <expr> ]"""
    target: Any               # Variable | PathExpr
    annotation: Optional[Annotation] = None
    value: Optional[Any] = None   # <expr>


@dataclass
class SetUp:
    """<set_up> = @(...) | @:xxx，yyy（双形式）"""
    items: list[SetUpItem] = field(default_factory=list)
    form: str = "prefix"  # "paren"（@(...)|分格）或 "prefix"（@:xxx，分格）


@dataclass
class LoopFraction:
    """<loop_fraction> = (x/y) 或 （x/y），半/全角等价"""
    current: int   # x = 当前执行次数
    maximum: int   # y = 最大允许次数


@dataclass
class SegLoopSuffix:
    """<seg_loop_suffix> = … , [ <seg_id> ] , <loop_fraction>（单省略号，段级）"""
    seg_id: Optional[int] = None
    fraction: Optional[LoopFraction] = None


@dataclass
class GlobalLoopSuffix:
    """<global_loop_suffix> = …… , <loop_fraction>（双省略号，全局）"""
    fraction: Optional[LoopFraction] = None


@dataclass
class OutputTrail:
    """<output_trail> = <output>
                     , [ <seg_loop_suffix>
                       , [ <subfile_ref> ]            (* 段循环后：子文件引用，下位文件补充/扩充，| 分隔多个 *)
                       , [ <global_code_id> ]
                       , [ <global_loop_suffix>
                         , [ <file_ref> ]             (* 全局循环后：文件路径，当前文件被分割成多文件 *)
                         ]
                       ]"""
    output: Any                          # Output
    seg_loop: Optional[SegLoopSuffix] = None
    subfiles: Optional[list[str]] = None  # 段循环后的子文件引用（下位文件，补充/扩充），| 分隔
    global_code_id: Optional[str] = None
    global_loop: Optional[GlobalLoopSuffix] = None
    file_ref: Optional[str] = None       # 全局循环后的文件路径（当前文件被分割成多文件）


@dataclass
class FileMarker:
    """<file_marker> = #：【文件】 或 #：【路径】"""
    path_content: str
    is_end_marker: bool = False  # True = #：【文件】（结束标记）


@dataclass
class GlobalIdStmt:
    """<global_id_stmt> = <global_code_id>（跨文件绑定，独立一行或 #： 前缀）
    is_placeholder=True 表示 ？ 模板占位符。"""
    code_id: str
    is_placeholder: bool = False


# ============================================================
# 数学核心（EBNF §4）
# ============================================================

@dataclass
class MechUnit:
    """<mech_unit> = ( <generate> | <generate_seg> ) , ( <code_block> | <mech_stmt> | <mech_body> )"""
    generate: Any       # Generate（无段号）或 GenerateSeg（带段号）
    body: Any           # CodeBlock | MechStmt | list[MechStmt]


@dataclass
class Generate:
    """<generate> = #："""
    seg_id: Optional[int] = None  # None = 无段号；int = 段号


@dataclass
class GenStmt:
    """<gen_stmt> / <gen_stmt_seg> = #(N)：( <command_literal> | <expr> | <output_trail> )"""
    generate: Generate
    content: Any  # CommandLiteral | Expr | OutputTrail


@dataclass
class Binding:
    """<binding> = ( <variable> | <path_expr> ) , [ <annotation> ] , "=" , <expr>"""
    target: Any
    annotation: Optional[Annotation] = None
    value: Any = None  # <expr>


@dataclass
class PathExpr:
    """<path_expr> = <variable> >> <variable>（路径/距离）"""
    left: Any
    right: Any


@dataclass
class SetConstruct:
    """<set_construct> = { <var_list> | <cond_list> } 或 { <literal_list> }"""
    form: str  # "comprehension"（理解形式）或 "enumeration"（枚举形式）
    variables: Optional[list[Any]] = None   # var_list
    conditions: Optional[list[Any]] = None   # cond_list
    literals: Optional[list[Any]] = None     # literal_list


@dataclass
class DictLiteral:
    """<dict_literal> = { <key> : <value> , { , <key> : <value> } }"""
    keys: list[Any]
    values: list[Any]


@dataclass
class Iteration:
    """<iteration> = (？<variable> | <variable>) >> <expr> <block>"""
    var: Any
    placeholder: bool = False  # True = ？x 形式
    iterable: Any = None       # <expr>
    block: Any = None          # <block>


@dataclass
class TupleExpr:
    """<tuple_expr> = ( <expr> , { , <expr> } )"""
    elements: list[Any]


@dataclass
class ListLiteral:
    """<list_literal> = [ <expr> , { , <expr> } ]"""
    elements: list[Any]


@dataclass
class IndexExpr:
    """<index_expr> = <expr> [ <expr> ]（列表/字符串索引）"""
    container: Any
    index: Any


@dataclass
class SliceExpr:
    """<slice_expr> = <expr> [ <start> : <end> ]（列表/字符串切片）"""
    container: Any
    start: Any = None
    end: Any = None


@dataclass
class ChainStmt:
    """<chain_stmt> = <mech_stmt> , { >> , <mech_stmt> }（通用链式，M3.1）
    M3.2 触发条件：单条命令/单条输出不足以完成任务时才启用。"""
    stmts: list[Any] = field(default_factory=list)


# ============================================================
# 表达式（EBNF §6）
# ============================================================

@dataclass
class IntegerLit:
    value: int
    unit: str = ""


@dataclass
class FloatLit:
    value: float
    unit: str = ""


@dataclass
class StringLit:
    value: str


@dataclass
class BoolLit:
    value: bool


@dataclass
class Variable:
    name: str
    is_placeholder: bool = False  # True = ？占位符


@dataclass
class BinaryOp:
    """二元运算：<expr> <op> <expr>"""
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    """一元运算：- <expr> 或 ^ <expr>（前缀开方）"""
    op: str
    operand: Any


@dataclass
class AngleExpr:
    """<angle_expr> = << <expr>"""
    expr: Any


@dataclass
class Belongs:
    """<belongs> = <expr> >> <expr>（属于判断）"""
    left: Any
    right: Any


@dataclass
class Output:
    """<output> = [ , [ <expr> ] , ]"""
    expr: Optional[Any] = None
    target: str = "printf"  # 输出目标: printf / print / log 等


@dataclass
class ReadBlock:
    """<read_block> = 【 <read_content> 】 或 〔 ... 〕"""
    content: Any  # CommandLiteral | Annotation | str（资源路径）


@dataclass
class NLBlock:
    """<nl_block> = 【*/标注/*】<natural_lang>（自然语言意图块）

    标注确定意图类别，natural_lang 为意图描述正文（纯文本，不做变量检查）。
    """
    annotation: Any  # Annotation
    natural_lang: str = ""


@dataclass
class Lambda:
    """<lambda> = ( <params> ) => <expr>"""
    params: list[Any] = field(default_factory=list)
    body: Any = None


@dataclass
class CodeBlock:
    """<code_block> = { <newline> , { <mech_stmt> , <newline> } , }"""
    stmts: list[Any] = field(default_factory=list)


@dataclass
class FuncApp:
    """函数应用（后缀）：<primary> <primary>"""
    func: Any
    arg: Any


# ============================================================
# 语句与控制流（EBNF §7）
# ============================================================

@dataclass
class IfExpr:
    """<if_expr> = <expr> ? <expr> : <expr>（三元）"""
    cond: Any
    then: Any
    else_: Any


@dataclass
class LetBinding:
    """let 局部绑定节点。"""
    name: str
    value: Any
    is_recursive: bool = False
    params: list[Any] = field(default_factory=list)
    body: Any = None


@dataclass
class LetTupleBinding:
    """let (a, b, ...) = expr in body — 元组解构绑定。"""
    names: list[str]
    value: Any
    body: Any = None


@dataclass
class IfStmt:
    """<if_stmt> = <expr> <block> [ 否则 ... ]（草案）"""
    cond: Any
    then_block: Any
    else_block: Optional[Any] = None


@dataclass
class WhileStmt:
    """<while_stmt> = while <expr> { <block> }"""
    cond: Any
    block: Any = None


@dataclass
class ForStmt:
    """<for_stmt> = for <var> in <expr> { <block> }"""
    var: str
    iterable: Any
    block: Any = None


@dataclass
class LoopStep:
    """<loop_step> = (？<var> | <var>) >> <expr> <block>（步进循环）"""
    var: Any
    placeholder: bool = False
    iterable: Any = None
    block: Any = None


@dataclass
class LoopWhile:
    """<loop_while> = <expr> ? <block>（条件循环，草案）"""
    cond: Any
    block: Any = None


@dataclass
class MatchStmt:
    """<match_stmt> = match <expr> { | <pattern> => <expr> }"""
    scrutinee: Any
    branches: list[tuple[Any, Any]] = field(default_factory=list)


# ============================================================
# 类型系统（EBNF §5）
# ============================================================

@dataclass
class BasicType:
    name: str  # Int / Float / Bool / String / Unit / Angle


@dataclass
class SetType:
    elem_type: Any


@dataclass
class FuncType:
    param_type: Any
    return_type: Any


@dataclass
class TupleType:
    types: list[Any] = field(default_factory=list)


@dataclass
class AnnotatedType:
    base_type: Any
    annotation: Annotation


# ============================================================
# 函数 / 类型定义 / 模块 / 并发（EBNF §8-11）
# ============================================================

@dataclass
class FuncDef:
    """<func_def> = <identifier> [ <annotation> ] : <func_type> = <lambda>"""
    name: str
    annotation: Optional[Annotation] = None
    func_type: Any = None
    body: Any = None  # Lambda
    else_body: Any = None  # 后续语句（如 let rec f = lambda; f(args) 中的 f(args)）


@dataclass
class StructDef:
    name: str
    type_params: list[str] = field(default_factory=list)
    annotation: Optional[Annotation] = None
    fields: list[Any] = field(default_factory=list)


@dataclass
class EnumDef:
    name: str
    type_params: list[str] = field(default_factory=list)
    annotation: Optional[Annotation] = None
    ctors: list[Any] = field(default_factory=list)


@dataclass
class AliasDef:
    name: str
    type_params: list[str] = field(default_factory=list)
    target_type: Any = None


@dataclass
class ModuleDecl:
    name: str
    annotation: Optional[Annotation] = None
    decls: list[Any] = field(default_factory=list)


@dataclass
class ImportDecl:
    module_name: str
    import_list: Optional[list[str]] = None
    alias: Optional[str] = None


@dataclass
class GoStmt:
    expr: Any


@dataclass
class ChanExpr:
    elem_type: Any
    buffer_size: Optional[int] = None


@dataclass
class SendExpr:
    channel: Any
    value: Any


@dataclass
class SelectStmt:
    branches: list[Any] = field(default_factory=list)


@dataclass
class DefineOp:
    """<define_op> = @define_op: <symbol> = <precedence> | <assoc>

    用户自定义运算符定义节点。
    """
    symbol: str
    precedence: int
    assoc: str  # "left" | "right"
    token_type: Any = None  # 运行时动态创建的 TokenType
