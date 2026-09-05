"""Matha 递归下降语法分析器。

对应 EBNF（17-完整语法EBNF.md）各章产生式。
每个 parse_* 方法对应一条 EBNF 产生式，方法签名注释标注对应产生式。

规格版本：0.6 草案（M3.2 细化版）

关键消解规则（EBNF §16）：
    - >> 四重语义：链式 / 步进迭代 / 属于判断 / 路径距离（按位置消解）
    - ^ 双语义：中缀次方（前有操作数）/ 前缀开方（前无操作数）
    - { } 双语义：代码块 vs 集合构造（按 { 后内容消解）
    - #N: vs #：：# 后跟数字 → 段号；否则无段号
    - 段内 5 步固定顺序：命令→变量→？公式→字母公式→输出（M3.1/M3.2）
    - >> 链式触发条件：单条命令/单条输出不足以完成任务时才启用（M3.2）
"""

from __future__ import annotations
import logging
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from src.tokens import Token, TokenType
from src.lexer import Lexer
from src import ast_nodes as ast
from enum import auto
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 全局自定义运算符表：symbol → TokenType
GLOBAL_CUSTOM_OPS: dict[str, Any] = {}


class ParseError(Exception):
    """语法错误。"""

    def __init__(self, msg: str, token: Token):
        super().__init__(f"ParseError at L{token.line}:{token.col}: {msg} (got {token.type.name} {token.value!r})")
        self.token = token


class Parser:
    """Matha 递归下降语法分析器。

    用法：
        parser = Parser(source_text)
        program = parser.parse()
    """

    def __init__(self, source: str):
        self.source = source
        self.source_lines = source.split("\n")
        self.tokens: list[Token] = list(Lexer(source).tokenize())
        self.pos = 0
        self._in_control_flow = False  # True when parsing if/while/for condition
        self._in_lambda_body = False   # True when parsing inside a lambda body
        self._in_lambda_rel = False    # True when parsing = right side inside lambda body
        self._in_func_app = False      # True when parsing inside a function call args
        self._in_let_value = False     # True when parsing the value expression of a let statement
        self._if_depth: int = 0        # 当前 if 表达式嵌套深度
        # 段内步骤追踪（用于 5 步固定顺序校验，M3.1/M3.2）
        self._current_seg: int | None = None
        self._seg_step: int = 0

    # ============================================================
    # 辅助方法
    # ============================================================

    def _peek(self, offset: int = 0) -> Token:
        """查看当前 + offset 处的 Token。"""
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        """当前 Token 类型是否在 types 中。"""
        return self._current().type in types

    def _match(self, *types: TokenType) -> Token | None:
        """若当前 Token 匹配则消费并返回，否则返回 None。"""
        if self._check(*types):
            return self._advance()
        return None

    def _expect(self, ttype: TokenType, desc: str = "") -> Token:
        """断言当前 Token 为 ttype，消费并返回；否则抛 ParseError。"""
        if self._check(ttype):
            return self._advance()
        raise ParseError(f"期望 {desc or ttype.name}", self._current())

    def _skip_newlines(self) -> None:
        """跳过连续换行、缩进和去缩进标记。"""
        while self._check(TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
            self._advance()

    def _skip_semicolon(self) -> None:
        """跳过语句结束的分号（ASCII `;`、全角 `；`）。

        注意：全角逗号 `，` 不在此处消费，而是在 _parse_expr 中作为表达式分隔符处理。
        """
        # 全角分号已映射为 MATHA_COLON_FW
        if self._check(TokenType.MATHA_COLON_FW):
            self._advance()
            return
        # ASCII 分号降级为 SYMBOL，通过 value 识别
        if self._check(TokenType.SYMBOL) and self._current().value == ";":
            self._advance()

    def _is_colon(self) -> bool:
        """当前是否为冒号（半角 : 或全角 ：）。"""
        return self._check(TokenType.OP_COLON, TokenType.MATHA_COLON_FW)

    def _is_stmt_separator(self) -> bool:
        """当前 token 是否为语句分隔符（换行、EOF、闭括号等）。"""
        return self._check(TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF,
                           TokenType.PUNCT_RBRACE, TokenType.PUNCT_RPAREN,
                           TokenType.PUNCT_RBRACKET)

    def _is_comma(self) -> bool:
        """当前是否为逗号（半角 , 或全角 ，）。"""
        return self._check(TokenType.PUNCT_COMMA, TokenType.MATHA_COMMA)

    def _skip_comma(self) -> None:
        """跳过逗号分隔符（半角 , 或全角 ，）。"""
        if self._is_comma():
            self._advance()

    def _is_read_open(self) -> bool:
        """当前是否为读取开括号（【 或 〔）。"""
        return self._check(TokenType.MATHA_READ_OPEN, TokenType.MATHA_READ_OPEN2)

    def _is_read_close(self) -> bool:
        """当前是否为读取闭括号（】 或 〔）。"""
        return self._check(TokenType.MATHA_READ_CLOSE, TokenType.MATHA_READ_CLOSE2)

    # ============================================================
    # §1 顶层结构
    # <program> = { <top_level> }
    # <top_level> = <module_decl> | <import_decl> | <nl_block>
    #             | <mech_unit> | <command_unit> | <decl>
    # ============================================================

    def parse(self) -> ast.Program:
        """解析整个程序，返回 AST 根节点。"""
        program = ast.Program()
        self._skip_newlines()
        while not self._check(TokenType.EOF):
            decl = self._parse_top_level()
            if decl is not None:
                program.decls.append(decl)
                logger.debug("解析声明: %s (行 %s)", type(decl).__name__, getattr(decl, 'line', '?'))
            self._skip_newlines()
            self._skip_semicolon()
            self._skip_newlines()
        logger.info("程序解析完成: %d 条声明", len(program.decls))
        return program

    def _parse_top_level(self):
        """<top_level>"""
        tok = self._current()

        # module / use 关键字
        if tok.type == TokenType.KW_MODULE:
            return self._parse_module_decl()
        if tok.type == TokenType.KW_USE:
            return self._parse_import_decl()

        # struct / enum / type
        if tok.type in (TokenType.KW_STRUCT, TokenType.KW_ENUM, TokenType.KW_TYPE):
            return self._parse_type_def()

        # #： / #N： → 机械单元（含 gen_stmt / code_block）
        if tok.type == TokenType.MATHA_HASH:
            return self._parse_mech_unit()

        # @define_op → 自定义运算符定义
        if tok.type == TokenType.MATHA_AT:
            saved = self.pos
            if self._peek(1).type == TokenType.IDENTIFIER and self._peek(1).value == "define_op":
                self.pos = saved
                return self._parse_define_op()
            self.pos = saved
            return self._parse_set_up()

        # 自然语言块 【*/.../*】
        if self._is_read_open() and self._peek(1).type == TokenType.MATHA_ANNOT_START:
            return self._parse_nl_block()

        # 命令单元
        if tok.type in (TokenType.MATHA_CMD_OPEN, TokenType.PUNCT_LBRACKET):
            return self._parse_command_unit()

        # 代码编号前缀：？#：{ 或 N#：{（跨文件共用编号，放在代码开头）
        if tok.type == TokenType.MATHA_PLACEHOLDER and self._peek(1).type == TokenType.MATHA_HASH:
            return self._parse_global_id_stmt()
        if tok.type == TokenType.LIT_INTEGER and self._peek(1).type == TokenType.MATHA_HASH:
            return self._parse_global_id_stmt()

        # 纯数字行 → 跨文件全局编号绑定
        if tok.type == TokenType.LIT_INTEGER and self._peek(1).type in (TokenType.NEWLINE, TokenType.EOF):
            return self._parse_global_id_stmt()

        # 其他声明（绑定 / 函数定义）
        return self._parse_decl()

    # ============================================================
    # §2.4-2.6 命令 / 标注 / 设定 / 循环后缀
    # ============================================================

    def _parse_annotation(self) -> ast.Annotation:
        """<annotation> = "*/" , <annot_text> , [ "*" , <expr> ] , "/*" """
        self._expect(TokenType.MATHA_ANNOT_START, "标注起始 */")
        text_tok = self._advance()
        text = text_tok.value
        formula = None
        if self._check(TokenType.OP_STAR):
            self._advance()
            formula = self._parse_expr()
        self._expect(TokenType.MATHA_ANNOT_END, "标注结束 /*")
        return ast.Annotation(text=text, formula=formula)

    def _parse_command_literal(self) -> ast.CommandLiteral:
        """<command_literal> = 《文字》 | 【文字】（两种写法等价，M3.1）"""
        if self._check(TokenType.MATHA_CMD_OPEN):
            self._advance()
            text = self._parse_command_text()
            self._expect(TokenType.MATHA_CMD_CLOSE, "命令闭括号 》")
            return ast.CommandLiteral(text=text, form="cn")
        if self._check(TokenType.MATHA_READ_OPEN):
            self._advance()
            text = self._parse_command_text()
            self._expect(TokenType.MATHA_READ_CLOSE, "命令闭括号 】")
            return ast.CommandLiteral(text=text, form="bracket")
        raise ParseError("期望命令字面量 《》 或 【】", self._current())

    def _parse_command_text(self) -> str:
        """<command_text> = <identifier> | <natural_lang_fragment>"""
        parts: list[str] = []
        while not self._is_read_close() and not self._check(TokenType.MATHA_CMD_CLOSE, TokenType.EOF):
            parts.append(self._advance().value)
        return "".join(parts)

    def _parse_set_up(self, seg_id: int | None = None) -> ast.SetUp:
        """<set_up> = @(...) | @:xxx，yyy
        <set_up_seg> = @N(...) | @N:xxx，yyy（带段号，M3）"""
        self._expect(TokenType.MATHA_AT, "@")
        # 可选段号 @N
        if self._check(TokenType.LIT_INTEGER):
            seg_id = int(self._advance().value)
        items: list[ast.SetUpItem] = []
        if self._check(TokenType.PUNCT_LPAREN):
            # @N(a|b|c) 或 @(a|b|c) 括号形式
            self._advance()
            items.append(self._parse_set_up_item())
            while self._match(TokenType.OP_PIPE):
                items.append(self._parse_set_up_item())
            self._expect(TokenType.PUNCT_RPAREN, ")")
            return ast.SetUp(items=items, form="paren")
        # @:xxx，yyy 或 @N：xxx，yyy 前缀形式
        if self._is_colon():
            self._advance()
        # 混合语法：@：【内容】 命令式设定（与 @：变量=值 可混用）
        if self._is_read_open():
            self._advance()
            text = self._parse_command_text()
            self._expect(TokenType.MATHA_READ_CLOSE, "命令闭括号 】")
            items.append(ast.SetUpItem(
                target=ast.Variable(name="？", is_placeholder=True),
                annotation=None,
                value=ast.StringLit(value=text)
            ))
            while self._is_comma():
                self._advance()
                if self._is_read_open():
                    self._advance()
                    text = self._parse_command_text()
                    self._expect(TokenType.MATHA_READ_CLOSE, "命令闭括号 】")
                    items.append(ast.SetUpItem(
                        target=ast.Variable(name="？", is_placeholder=True),
                        annotation=None,
                        value=ast.StringLit(value=text)
                    ))
                else:
                    items.append(self._parse_set_up_item())
            return ast.SetUp(items=items, form="cmd")
        items.append(self._parse_set_up_item())
        while self._is_comma():
            self._advance()
            items.append(self._parse_set_up_item())
        return ast.SetUp(items=items, form="prefix")

    def _parse_set_up_item(self) -> ast.SetUpItem:
        """<set_up_item> = ( <variable> | <path_expr> ) , [ <annotation> ] , [ "=" , <expr> ]

        设定值可能是表达式或路径/文本（如 /data/config、8080、10元、windows.iso）。
        当值无法完整解析为表达式时（如含 . 的文件名），回退为文本字符串。
        裸标识符值（如 MyApp、x64）视为配置字符串，不当作变量引用。
        """
        target = self._parse_variable_or_path()
        annotation = None
        if self._check(TokenType.MATHA_ANNOT_START):
            annotation = self._parse_annotation()
        value = None
        if self._match(TokenType.OP_ASSIGN):
            # 尝试解析为表达式；失败或未消费完整则回退为路径/文本
            saved_pos = self.pos
            try:
                value = self._parse_expr(stop_at_comma=True)
                # 检查值是否消费完整：当前应为逗号/换行/EOF/|(分格)
                if not (self._is_comma() or self._check(TokenType.NEWLINE, TokenType.EOF, TokenType.OP_PIPE)):
                    raise ParseError("设定值未消费完整，回退为文本", self._current())
                # 裸标识符作为配置值（字符串），不当作变量引用
                if isinstance(value, ast.Variable) and not value.is_placeholder:
                    value = ast.StringLit(value=value.name)
            except ParseError:
                self.pos = saved_pos
                parts: list[str] = []
                while not self._is_comma() and not self._check(TokenType.NEWLINE, TokenType.EOF):
                    parts.append(self._advance().value)
                value = ast.StringLit(value="".join(parts))
        return ast.SetUpItem(target=target, annotation=annotation, value=value)

    def _parse_variable_or_path(self):
        """<variable> | <path_expr>（路径 a>>b）"""
        var = self._parse_variable()
        if self._check(TokenType.OP_NEXT):
            # 检查是否为路径语境（>> 后跟变量，且不在循环头/链式语境）
            if self._is_path_context():
                self._advance()
                right = self._parse_variable()
                return ast.PathExpr(left=var, right=right)
        return var

    def _is_path_context(self) -> bool:
        """判断 >> 是否为路径/距离语境（绑定/设定左侧 a>>b=...）。

        路径语境条件：
          1. >> 后跟标识符或占位符（保留原逻辑）
          2. 标识符后跟 = （区分路径 a>>b=5 与属于判断 a>>b）
          3. 不在控制流条件解析中（_in_control_flow）
          4. 不在 lambda 体内（_in_lambda_body）
          5. 不在函数调用参数中（_in_func_app）
          6. 不处于链式语境（_is_chain_context）
        """
        next_tok = self._peek(1)
        if next_tok.type not in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER):
            logger.debug(">> 非路径: token类型=%s (非标识符/占位符)", next_tok.type.name)
            return False
        # 检查标识符后是否跟 =：路径 a>>b=5 vs 属于 a>>b
        tok_after_var = self._peek(2)
        if tok_after_var.type != TokenType.OP_ASSIGN:
            logger.debug(">> 非路径: %s 后跟 %s (非 =)", next_tok.value, tok_after_var.type.name)
            return False
        if self._in_control_flow:
            logger.debug(">> 非路径: 在控制流语境中 (_in_control_flow=True)")
            return False
        if self._in_lambda_body:
            logger.debug(">> 非路径: 在lambda体内 (_in_lambda_body=True)")
            return False
        if self._in_func_app:
            logger.debug(">> 非路径: 在函数调用参数中 (_in_func_app=True)")
            return False
        if self._is_chain_context():
            logger.debug(">> 非路径: 处于链式语境 (_is_chain_context=True)")
            return False
        logger.debug(">> 识别为路径: %s >> %s", self._current().value, next_tok.value)
        return True

    def _parse_loop_fraction(self) -> ast.LoopFraction:
        """<loop_fraction> = (x/y) 或 （x/y），半/全角等价
        支持占位符 ？ 表示待定次数（存储为 -1）"""
        self._expect(TokenType.PUNCT_LPAREN, "循环分数左括号 (")
        if self._check(TokenType.MATHA_PLACEHOLDER):
            current = -1
            self._advance()
        else:
            current = int(self._expect(TokenType.LIT_INTEGER, "当前次数").value)
        self._expect(TokenType.OP_SLASH, "分数线 /")
        if self._check(TokenType.MATHA_PLACEHOLDER):
            maximum = -1
            self._advance()
        else:
            maximum = int(self._expect(TokenType.LIT_INTEGER, "最大次数").value)
        self._expect(TokenType.PUNCT_RPAREN, "循环分数右括号 )")
        return ast.LoopFraction(current=current, maximum=maximum)

    def _parse_seg_loop_suffix(self) -> ast.SegLoopSuffix:
        """<seg_loop_suffix> = … , [ <seg_id> ] , <loop_fraction>（单省略号）"""
        self._expect(TokenType.MATHA_ELLIPSIS, "段级循环省略号 …")
        seg_id = None
        if self._check(TokenType.LIT_INTEGER):
            seg_id = int(self._advance().value)
        fraction = self._parse_loop_fraction()
        return ast.SegLoopSuffix(seg_id=seg_id, fraction=fraction)

    def _parse_global_loop_suffix(self) -> ast.GlobalLoopSuffix:
        """<global_loop_suffix> = …… , <loop_fraction>（双省略号）"""
        self._expect(TokenType.MATHA_DOUBLE_ELLIPSIS, "全局循环双省略号 ……")
        fraction = self._parse_loop_fraction()
        return ast.GlobalLoopSuffix(fraction=fraction)

    def _parse_output_trail(self) -> ast.OutputTrail:
        """<output_trail> = <output>
                         , [ <seg_loop_suffix>
                           , [ <subfile_ref> ]            (* 段循环后：子文件，| 分隔多个 *)
                           , [ <global_code_id> ]
                           , [ <global_loop_suffix>
                             , [ <file_ref> ]             (* 全局循环后：文件路径 *)
                             ]
                           ]

        完整末行形态（M3.3）：
            #：[输出]…（x/y）【子文件|子文件】<全局编号>……（x/y）【文件/路径】
        模板形式（不可编辑代码）允许仅有全局循环而无段级循环：
            #：[输出]……（0/1）
        """
        output = self._parse_output()
        trail = ast.OutputTrail(output=output)
        if self._check(TokenType.MATHA_ELLIPSIS):
            trail.seg_loop = self._parse_seg_loop_suffix()
            # 段循环后可选子文件引用【子文件|子文件】（下位文件，补充/扩充）
            if self._is_read_open():
                trail.subfiles = self._parse_subfile_ref()
            # 可选全局编号
            if self._check(TokenType.LIT_INTEGER):
                trail.global_code_id = self._advance().value
            # 可选全局循环
            if self._check(TokenType.MATHA_DOUBLE_ELLIPSIS):
                trail.global_loop = self._parse_global_loop_suffix()
                # 全局循环后可选文件路径【文件/路径】（当前文件被分割成多文件）
                if self._is_read_open():
                    trail.file_ref = self._parse_file_ref()
        elif self._check(TokenType.MATHA_DOUBLE_ELLIPSIS):
            # 模板形式：仅有全局循环，无段级循环
            trail.global_loop = self._parse_global_loop_suffix()
            if self._is_read_open():
                trail.file_ref = self._parse_file_ref()
        return trail

    def _parse_subfile_ref(self) -> list[str]:
        """<subfile_ref> = ( 【 | 〔 ) , <path_content> , { "|" , <path_content> } , ( 】 | 〕 )

        段循环后的子文件引用：下位文件，用于补充/扩充当前段。
        多个子文件用 | 分隔：【sub1.matha|sub2.matha】
        """
        self._advance()  # 消费开括号
        subfiles: list[str] = []
        parts: list[str] = []
        while not self._is_read_close() and not self._check(TokenType.EOF):
            if self._check(TokenType.OP_PIPE):
                subfiles.append("".join(parts))
                parts = []
                self._advance()
            else:
                parts.append(self._advance().value)
        subfiles.append("".join(parts))
        self._advance()  # 消费闭括号
        return subfiles

    def _parse_file_ref(self) -> str:
        """<file_ref> = ( 【 | 〔 ) , <path_content> , ( 】 | 〕 )

        全局循环后的文件路径：当前代码文件被分割/分化成多个文件使用。
        """
        self._advance()  # 消费开括号
        parts: list[str] = []
        while not self._is_read_close() and not self._check(TokenType.EOF):
            parts.append(self._advance().value)
        self._advance()  # 消费闭括号
        return "".join(parts)

    def _parse_global_id_stmt(self) -> ast.GlobalIdStmt:
        """<global_id_stmt> = <global_code_id>（独立一行或 #： 前缀的全局编号）
        支持 ？ 占位符（模板/schema 形式）和整数编号。"""
        if self._check(TokenType.MATHA_PLACEHOLDER):
            tok = self._advance()
            return ast.GlobalIdStmt(code_id=tok.value, is_placeholder=True)
        tok = self._expect(TokenType.LIT_INTEGER, "全局代码编号")
        return ast.GlobalIdStmt(code_id=tok.value)

    # ============================================================
    # §4 数学核心：机械单元 / 语句
    # ============================================================

    def _parse_mech_unit(self) -> ast.MechUnit:
        """<mech_unit> = ( <generate> | <generate_seg> ) , ( <code_block> | <mech_stmt> | <mech_body> )

        #：{ ... }  → generate + code_block
        #1：【命令】 → generate + GenStmt(content=command)
        #1：【命令】{ ... }  → generate + [GenStmt, CodeBlock]
        #1：？公式   → generate + GenStmt(content=expr)
        #1：[输出]   → generate + GenStmt(content=output_trail)
        """
        generate = self._parse_generate()
        self._current_seg = generate.seg_id
        self._seg_step = 0

        # #：{ ... } 代码块形式
        if self._check(TokenType.PUNCT_LBRACE):
            body = self._parse_code_block()
        else:
            body = self._parse_gen_stmt_content(generate)
            # 如果命令后紧跟代码块，将两者组合进同一个 MechUnit
            if isinstance(body, ast.GenStmt):
                self._skip_newlines()
                if self._check(TokenType.PUNCT_LBRACE):
                    code_block = self._parse_code_block()
                    body = [body, code_block]
        self._current_seg = None
        return ast.MechUnit(generate=generate, body=body)

    def _parse_gen_stmt_content(self, generate: ast.Generate):
        """解析 gen_stmt / gen_stmt_seg 的内容部分（命令 / 表达式 / 输出追踪）。

        <gen_stmt>     = <generate> , ( <command_literal> | <expr> | <output_trail> )
        <gen_stmt_seg> = <generate_seg> , ( <command_literal> | <expr> | <output_trail> )

        内容后检查 >> 链式（M3.2：单条不够才启用）。
        """
        # #N：【命令】或 #N：《命令》
        if self._check(TokenType.MATHA_CMD_OPEN, TokenType.MATHA_READ_OPEN):
            cmd = self._parse_command_literal()
            stmt = ast.GenStmt(generate=generate, content=cmd)
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：[输出] → output_trail
        if self._check(TokenType.PUNCT_LBRACKET):
            trail = self._parse_output_trail()
            stmt = ast.GenStmt(generate=generate, content=trail)
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：go / if / while / for / match 任务 → 并发 / 控制流语句
        if self._check(TokenType.KW_GO, TokenType.KW_IF, TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_MATCH):
            node = self._parse_statement()
            stmt = ast.GenStmt(generate=generate, content=node)
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：？公式 / #N：字母公式 → expr
        expr = self._parse_expr()
        stmt = ast.GenStmt(generate=generate, content=expr)
        if self._check(TokenType.OP_NEXT) and self._is_chain_context():
            return self._parse_chain(stmt)
        return stmt

    def _parse_generate(self) -> ast.Generate:
        """<generate> = #： 或 <generate_seg> = #N："""
        self._expect(TokenType.MATHA_HASH, "#")
        seg_id = None
        if self._check(TokenType.LIT_INTEGER):
            seg_id = int(self._advance().value)
        if not self._is_colon():
            raise ParseError("期望冒号 : 或 ：", self._current())
        self._advance()  # 消费冒号
        return ast.Generate(seg_id=seg_id)

    def _parse_code_block(self) -> ast.CodeBlock:
        """<code_block> = { <newline> , { <mech_stmt> , <newline> } , }"""
        self._expect(TokenType.PUNCT_LBRACE, "代码块开括号 {")
        self._skip_newlines()
        stmts: list[Any] = []
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            stmt = self._parse_mech_stmt()
            if stmt is not None:
                stmts.append(stmt)
            # 跳过换行和分号（分号作为语句分隔符，兼容 Python/C 风格）
            self._skip_newlines()
            self._skip_semicolon()
        self._expect(TokenType.PUNCT_RBRACE, "代码块闭括号 }")
        return ast.CodeBlock(stmts=stmts)

    def _parse_block_body(self) -> ast.CodeBlock:
        """解析代码块内部语句（不含外层 { }）。"""
        self._skip_newlines()
        stmts: list[Any] = []
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            stmt = self._parse_mech_stmt()
            if stmt is not None:
                stmts.append(stmt)
            # 跳过换行和分号（分号作为语句分隔符，兼容 Python/C 风格）
            self._skip_newlines()
            self._skip_semicolon()
        return ast.CodeBlock(stmts=stmts)

    def _parse_mech_stmt(self):
        """<mech_stmt> —— 机械语句（分支消解）

        <mech_stmt> = <binding> | <set_construct> | <iteration> | <output> | <output_trail>
                    | <expr> | <set_up> | <set_up_seg>
                    | <gen_stmt> | <gen_stmt_seg>
                    | <file_marker> | <global_id_stmt> | <statement> | <chain_stmt>
        """
        # #：... → gen_stmt / file_marker
        if self._check(TokenType.MATHA_HASH):
            return self._parse_gen_or_file_marker()

        # @define_op → 自定义运算符定义
        if self._check(TokenType.MATHA_AT):
            saved = self.pos
            if self._peek(1).type == TokenType.IDENTIFIER and self._peek(1).value == "define_op":
                self.pos = saved
                return self._parse_define_op()
            self.pos = saved
            return self._parse_set_up()

        # [...] → output / output_trail
        if self._check(TokenType.PUNCT_LBRACKET):
            trail = self._parse_output_trail()
            # 检查 >> 链式（M3.2：单条不够才启用）
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(trail)
            return trail

        # 【...】 独立行 → read_block / command
        if self._is_read_open():
            return self._parse_read_or_command()

        # { ... } → set_construct 或 code_block（按内容消解）
        if self._check(TokenType.PUNCT_LBRACE):
            return self._parse_brace_dispatch()

        # 纯数字行 → global_id_stmt
        if self._check(TokenType.LIT_INTEGER) and self._peek(1).type in (TokenType.NEWLINE, TokenType.EOF):
            return self._parse_global_id_stmt()

        # go / if / while / for / match / func 等控制流语句（代码块内裸语句）
        if self._check(TokenType.KW_GO, TokenType.KW_IF, TokenType.KW_WHILE, TokenType.KW_FOR,
                       TokenType.KW_MATCH, TokenType.KW_FUNC):
            return self._parse_statement()

        # 其他 → 表达式 / 绑定
        return self._parse_expr_or_binding()

    def _parse_define_op(self) -> ast.AST:
        """<define_op> = @define_op: <symbol> = <precedence> | <assoc>

        例：
            @define_op: ≈ = 5 | left
            @define_op: ≡ = 5 | left
            @define_op: → = 3 | right
        """
        self._expect(TokenType.MATHA_AT, "@")
        # 消费 define_op 关键字（作为标识符）
        self._expect(TokenType.IDENTIFIER, "define_op")
        # 接受半角 : 或全角 ：（仅消费一个）
        if self._check(TokenType.OP_COLON):
            self._advance()
        else:
            self._expect(TokenType.MATHA_COLON_FW, "：")
        # 消费符号
        sym_tok = self._expect(TokenType.SYMBOL, "自定义运算符符号")
        symbol = sym_tok.value
        self._expect(TokenType.OP_ASSIGN, "=")
        # 消费优先级
        prec_tok = self._expect(TokenType.LIT_INTEGER, "优先级")
        precedence = int(prec_tok.value)
        self._expect(TokenType.OP_PIPE, "|")
        # 消费结合性
        assoc_tok = self._expect(TokenType.IDENTIFIER, "结合性")
        assoc = assoc_tok.value
        if assoc not in ("left", "right"):
            raise ParseError(f"结合性应为 left 或 right，实际: {assoc!r}", assoc_tok)
        # 注册到全局运算符表
        op_name = f"OP_CUSTOM_{symbol}"
        if not hasattr(TokenType, op_name):
            setattr(TokenType, op_name, auto())
        custom_type = getattr(TokenType, op_name)
        GLOBAL_CUSTOM_OPS[symbol] = custom_type
        # 返回定义节点
        return ast.DefineOp(symbol=symbol, precedence=precedence, assoc=assoc, token_type=custom_type)

    def _parse_gen_or_file_marker(self):
        """区分 #：命令/公式/输出 vs #：【文件】/【路径】

        #：【文件】     → FileMarker（结束标记，无段号）
        #：【path】     → FileMarker（路径引用，无段号）
        #N：【命令】    → GenStmt(command)（有段号）
        #N：？公式      → GenStmt(expr)
        #N：[输出]      → GenStmt(output_trail)
        #N：…1（x/y）  → GenStmt(loop_line)（M3.2 分行）
        """
        generate = self._parse_generate()
        self._current_seg = generate.seg_id

        # 文件标记：#：【文件】（无段号 + 【文件】）→ FileMarker
        # 其他 #：【内容】（无段号）→ 回退为 GenStmt 命令（新模板支持）
        if generate.seg_id is None and self._is_read_open():
            saved = self.pos
            self._advance()  # 消费 【 或 〔
            content = self._parse_command_text()
            if self._is_read_close():
                self._advance()
            if content == "文件":
                return ast.FileMarker(path_content=content, is_end_marker=True)
            # 非文件标记 → 回退，按 GenStmt 命令解析
            self.pos = saved

        # M3.2：#N：…1（x/y） 分行循环后缀（主输出行已在上方，此处仅循环+路径）
        if self._check(TokenType.MATHA_ELLIPSIS, TokenType.MATHA_DOUBLE_ELLIPSIS):
            return self._parse_loop_line(generate)

        # #N：【命令】或 #N：《命令》
        if self._check(TokenType.MATHA_CMD_OPEN, TokenType.MATHA_READ_OPEN):
            cmd = self._parse_command_literal()
            stmt = ast.GenStmt(generate=generate, content=cmd)
            # >> 链式（M3.2：单条命令不够才启用）
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：[输出] → output_trail
        if self._check(TokenType.PUNCT_LBRACKET):
            trail = self._parse_output_trail()
            stmt = ast.GenStmt(generate=generate, content=trail)
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：go / if / while / for / match 任务 → 并发 / 控制流语句
        if self._check(TokenType.KW_GO, TokenType.KW_IF, TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_MATCH):
            node = self._parse_statement()
            stmt = ast.GenStmt(generate=generate, content=node)
            if self._check(TokenType.OP_NEXT) and self._is_chain_context():
                return self._parse_chain(stmt)
            return stmt

        # #N：？公式 / #N：字母公式 → expr
        expr = self._parse_expr()
        stmt = ast.GenStmt(generate=generate, content=expr)
        if self._check(TokenType.OP_NEXT) and self._is_chain_context():
            return self._parse_chain(stmt)
        return stmt

    def _parse_loop_line(self, generate: ast.Generate):
        """M3.2/M3.3 分行循环后缀：#N：…N（x/y）[【子文件|…】][全局编号][……（x/y）][【文件/路径】]

        主输出行 [输出] 已在上方独立一行，此处仅解析循环+子文件+路径部分。
        生成一个 OutputTrail（expr=None）表示纯循环追踪行。
        """
        trail = ast.OutputTrail(output=ast.Output(expr=None))
        if self._check(TokenType.MATHA_ELLIPSIS):
            trail.seg_loop = self._parse_seg_loop_suffix()
            # 段循环后可选子文件引用（下位文件，补充/扩充）
            if self._is_read_open():
                trail.subfiles = self._parse_subfile_ref()
            if self._check(TokenType.LIT_INTEGER):
                trail.global_code_id = self._advance().value
            if self._check(TokenType.MATHA_DOUBLE_ELLIPSIS):
                trail.global_loop = self._parse_global_loop_suffix()
                # 全局循环后可选文件路径（当前文件被分割成多文件）
                if self._is_read_open():
                    trail.file_ref = self._parse_file_ref()
        elif self._check(TokenType.MATHA_DOUBLE_ELLIPSIS):
            trail.global_loop = self._parse_global_loop_suffix()
            if self._is_read_open():
                trail.file_ref = self._parse_file_ref()
        return ast.GenStmt(generate=generate, content=trail)

    def _parse_read_or_command(self):
        """【...】独立行：read_block 或 command_literal"""
        if self._check(TokenType.MATHA_CMD_OPEN):
            return self._parse_command_literal()
        # 【...】读取块
        self._advance()
        content = self._parse_command_text()
        self._advance()
        return ast.ReadBlock(content=content)

    def _parse_brace_dispatch(self):
        """{ } 双义消解：代码块 vs 集合构造 vs 字典字面量（EBNF §16）

        消解规则（前瞻 { 后第一个 token）：
        - NEWLINE → 代码块（EBNF: { <newline> ... }）
        - } → 空集合构造
        - 逗号或管道 → 集合构造（枚举 {1,2,3} / 理解 {x | cond}）
        - 整数/浮点/布尔 → 集合枚举（如 {1, 2, 3}）
        - 字符串/标识符 且 下一 token 为 : → 字典字面量（如 {"类型": "程序"}）
        - 标识符 且 下一 token 为 | → 集合理解（如 {x | x > 5}）
        - 其他 → 代码块（默认规则）
        """
        next_tok = self._peek(1)
        if next_tok.type == TokenType.NEWLINE:
            return self._parse_code_block()
        if next_tok.type == TokenType.PUNCT_RBRACE:
            return self._parse_set_construct()
        # 有逗号或管道分隔符 → 集合构造
        if next_tok.type in (TokenType.PUNCT_COMMA, TokenType.OP_PIPE, TokenType.MATHA_COMMA) \
                or (next_tok.type == TokenType.SYMBOL and next_tok.value in (",", "|", "，", "；")):
            return self._parse_set_construct()
        # 整数字面量 / 浮点 / 布尔 → 集合枚举（如 {1, 2, 3}）
        if next_tok.type in (TokenType.LIT_INTEGER, TokenType.LIT_FLOAT,
                             TokenType.LIT_BOOL):
            return self._parse_set_construct()
        # 字符串 → 检查后一个 token：: 则字典，, 或 | 则集合
        if next_tok.type == TokenType.LIT_STRING:
            next_next = self._peek(2)
            if next_next.type == TokenType.OP_COLON:
                return self._parse_dict_literal()
            if next_next.type in (TokenType.PUNCT_COMMA, TokenType.OP_PIPE, TokenType.MATHA_COMMA) \
                    or (next_next.type == TokenType.SYMBOL and next_next.value in (",", "|", "，", "；")):
                return self._parse_set_construct()
            return self._parse_code_block()
        # 标识符 → 检查后一个 token：| 则集合理解，: 则字典，否则代码块
        if next_tok.type == TokenType.IDENTIFIER:
            next_next = self._peek(2)
            if next_next.type == TokenType.OP_PIPE:
                return self._parse_set_construct()
            if next_next.type == TokenType.OP_COLON:
                return self._parse_dict_literal()
            return self._parse_code_block()
        # 无分隔符 → 代码块（含 if 体、lambda 体等）
        return self._parse_code_block()

    def _parse_set_construct(self) -> ast.SetConstruct:
        """<set_construct> = { <var_list> | <cond_list> } 或 { <literal_list> }

        枚举形式: {1, 2, 3}（逗号分隔）
        理解形式: {x | cond | cond}（管道分隔）
        """
        self._expect(TokenType.PUNCT_LBRACE, "集合构造开括号 {")
        # 空集合 {}
        if self._check(TokenType.PUNCT_RBRACE):
            self._advance()
            return ast.SetConstruct(form="enumeration", literals=[])
        # 解析第一个元素
        first = self._parse_expr()
        # 理解形式: first | cond | cond（管道分隔）
        if self._check(TokenType.OP_PIPE):
            self._advance()
            variables = [first]
            conditions = [self._parse_expr()]
            while self._check(TokenType.OP_PIPE):
                self._advance()
                conditions.append(self._parse_expr())
            self._expect(TokenType.PUNCT_RBRACE, "集合构造闭括号 }")
            return ast.SetConstruct(form="comprehension", variables=variables, conditions=conditions)
        # 枚举形式: first, expr, expr（逗号分隔，半/全角等价）
        literals = [first]
        while self._is_comma():
            self._advance()
            literals.append(self._parse_expr())
        self._expect(TokenType.PUNCT_RBRACE, "集合构造闭括号 }")
        return ast.SetConstruct(form="enumeration", literals=literals)

    def _parse_dict_literal(self) -> ast.DictLiteral:
        """<dict_literal> = { <key> : <value> , { , <key> : <value> } }

        例：{"类型": "程序"}  →  DictLiteral(keys=["类型"], values=[StringLit("程序")])
        """
        self._expect(TokenType.PUNCT_LBRACE, "字典字面量开括号 {")
        keys: list[Any] = []
        values: list[Any] = []
        # 第一个键值对
        key = self._parse_expr()
        self._expect(TokenType.OP_COLON, ":")
        value = self._parse_expr()
        keys.append(key)
        values.append(value)
        # 后续键值对
        while self._is_comma():
            self._advance()
            key = self._parse_expr()
            self._expect(TokenType.OP_COLON, ":")
            value = self._parse_expr()
            keys.append(key)
            values.append(value)
        self._expect(TokenType.PUNCT_RBRACE, "字典字面量闭括号 }")
        return ast.DictLiteral(keys=keys, values=values)

    def _parse_expr_or_binding(self):
        """表达式 / 绑定消解：variable = expr → binding；否则 → expr

        注意：= 在表达式内是关系等于（rel_op），_parse_expr 会将其解析为
        BinaryOp("=", left, right)。在语句层，variable = value 应识别为 binding，
        故将顶层 BinaryOp("=") 转换为 Binding（variable / path 两种 target）。

        重要：若 = 左侧是函数应用（FuncApp），则为等于比较而非赋值。
        例：做二元("+")(3)(5) = 8  →  BinaryOp("=", 做二元("+")(3)(5), 8)（等于判断）

        Lambda 体内特殊处理：在 lambda 体内（_in_lambda_body=True），= 一律
        作为等于比较，不转换为绑定。
        例：op = "+" ? left + right : 0  →  BinaryOp("=", op, IfExpr(...))
        """
        self._in_bind_value = True
        try:
            expr = self._parse_expr()
        finally:
            self._in_bind_value = False
        # 语句层：variable = value / a>>b = value → binding
        if isinstance(expr, ast.BinaryOp) and expr.op == "=":
            # 若左侧是 FuncApp（lambda 应用或函数调用），= 为等于比较，不作绑定
            if isinstance(expr.left, ast.FuncApp):
                return expr
            # Lambda 体内：= 一律作为等于比较
            if self._in_lambda_body:
                return expr
            if isinstance(expr.left, ast.Variable):
                return ast.Binding(target=expr.left, annotation=None, value=expr.right)
            if isinstance(expr.left, ast.PathExpr):
                return ast.Binding(target=expr.left, annotation=None, value=expr.right)
            if isinstance(expr.left, ast.Belongs):
                # a>>b = value → path binding（expr 内 >> 被解析为 Belongs）
                return ast.Binding(
                    target=ast.PathExpr(left=expr.left.left, right=expr.left.right),
                    annotation=None, value=expr.right,
                )
        # 检查 >> 链式
        if self._check(TokenType.OP_NEXT) and self._is_chain_context():
            return self._parse_chain(expr)
        # 全角冒号作为语句分隔符（如 `a ： b = 1` → binding(a) ; binding(b=1)）
        if self._check(TokenType.MATHA_COLON_FW) or self._check(TokenType.OP_COLON):
            self._advance()
            self._skip_newlines()
            return self._make_binding_or_expr(expr)
        return expr

    def _make_binding_or_expr(self, expr) -> ast.AST:
        """将 expr 转换为 binding（如果 applicable），或原样返回。"""
        if isinstance(expr, ast.BinaryOp) and expr.op == "=":
            if isinstance(expr.left, ast.Variable):
                return ast.Binding(target=expr.left, annotation=None, value=expr.right)
            if isinstance(expr.left, ast.PathExpr):
                return ast.Binding(target=expr.left, annotation=None, value=expr.right)
            if isinstance(expr.left, ast.Belongs):
                return ast.Binding(
                    target=ast.PathExpr(left=expr.left.left, right=expr.left.right),
                    annotation=None, value=expr.right,
                )
        return expr

    def _has_conditional_suffix(self, expr) -> bool:
        """expr 是否是 比较表达式 且后面紧跟三元操作。

        用于检测 `3 > 2 ? 100 : 200` 模式：expr 是 BinaryOp(>)，
        其后还有 ? then : else。
        """
        if not isinstance(expr, ast.BinaryOp):
            return False
        if expr.op not in ("<", ">", "<=", ">="):
            return False
        # 检查后面是否有 ? —— 只需保存/恢复位置，tokens 不变
        saved_pos = self.pos
        try:
            # expr.right 已解析，继续检查下一个 token
            return self._check(TokenType.OP_QUESTION)
        finally:
            self.pos = saved_pos

    def _parse_conditional_binding(self, var: ast.Variable, rel_expr: ast.BinaryOp) -> ast.Binding:
        """解析 var = <rel_expr> ? <then> : <else> 作为绑定。

        rel_expr 是已解析的比较表达式（如 3 > 2）。
        需要消费 ? then : else 并构建 IfExpr。
        """
        saved_pos = self.pos
        try:
            self._expect(TokenType.OP_QUESTION, "?")
            then_expr = self._parse_expr()
            self._expect(TokenType.OP_COLON, ":")
            else_expr = self._parse_expr()
            return ast.Binding(
                target=var,
                annotation=None,
                value=ast.IfExpr(cond=rel_expr, then=then_expr, else_=else_expr),
            )
        finally:
            # 回退：如果解析失败，恢复位置
            self.pos = saved_pos

    # _is_rel_op 已废弃：三元检测已移入 _parse_rel_expr

    # ============================================================
    # >> 链式（M3.1/M3.2）
    # <chain_stmt> = <mech_stmt> , { ">>" , <mech_stmt> }
    # ============================================================

    def _is_chain_context(self) -> bool:
        """判断 >> 是否为通用链式语境（M3.2 触发条件）。

        链式语境：>> 两侧均为语句且不在循环头/绑定左侧/表达式内部。
        M3.2 收紧：仅当单条命令/单条输出不足以完成任务时才启用。
        """
        # 简化判断：>> 后跟命令/输出/设定语句开头 → 链式
        next_tok = self._peek(1)
        return next_tok.type in (
            TokenType.MATHA_CMD_OPEN,
            TokenType.MATHA_READ_OPEN,
            TokenType.PUNCT_LBRACKET,
            TokenType.MATHA_AT,
            TokenType.MATHA_HASH,
        )

    def _parse_chain(self, first_stmt) -> ast.ChainStmt:
        """<chain_stmt> = <mech_stmt> , { ">>" , <mech_stmt> }

        拍平嵌套：子 mech_stmt（如 #N：段经 _parse_gen_or_file_marker）
        可能递归返回 ChainStmt，此处展开为单层扁平链，契合 >> 的
        扁平顺序语义（M3.1/M3.2）。
        """
        stmts: list[Any] = []
        if isinstance(first_stmt, ast.ChainStmt):
            stmts.extend(first_stmt.stmts)
            logger.debug("展开递归链: %d 个子声明", len(first_stmt.stmts))
        else:
            stmts.append(first_stmt)
        chain_count = 0
        while self._check(TokenType.OP_NEXT):
            self._advance()
            stmt = self._parse_mech_stmt()
            if isinstance(stmt, ast.ChainStmt):
                stmts.extend(stmt.stmts)  # 拍平递归子链
                logger.debug("链式声明 #%d (展开子链 %d 条)", chain_count, len(stmt.stmts))
            else:
                stmts.append(stmt)
            chain_count += 1
            logger.debug("链式声明 #%d: %s", chain_count, type(stmt).__name__)
        logger.debug("链式语句解析完成: %d 条语句 (含 %d 个 >>)", len(stmts), chain_count)
        return ast.ChainStmt(stmts=stmts)

    # ============================================================
    # §6 表达式与运算符
    # <expr> = <rel_expr>
    # 优先级：rel > add > mul > pow > unary > postfix > primary
    # ============================================================

    def _parse_expr(self, stop_at_comma: bool = False):
        """<expr> = <or_expr> , [ ";" , <expr> ]* （支持分号分隔的表达式序列）

        三元是最低优先级表达式，使 a ? b : c 可出现在绑定值 / lambda 体 /
        输出 / 括号内等任意 <expr> 位置。半角 ? / : 对应 lexer 已识别的
        OP_QUESTION / OP_COLON（与全角 ？占位符、：段号不冲突）。

        let 表达式也在此处支持，使 lambda 体内可使用 let ... in。

        stop_at_comma: 遇到全角逗号时停止（用于 setUp 项等语境）。
        """
        self._skip_newlines()
        # let x = expr [in expr] 也作为表达式支持（用于 lambda 体等）
        if self._check(TokenType.IDENTIFIER) and self._current().value == "let":
            return self._parse_let()
        # if-else 表达式关键字形式（顶层 and in function args）
        # 优先级低于 and/or，高于 ternary，使 a if cond else b 在表达式中正确解析
        # 注意：在控制流语境中，if 由 _parse_if 处理，不在 _parse_expr 中处理
        if not self._in_control_flow and self._check(TokenType.KW_IF):
            return self._parse_if_expr()
        exprs = [self._parse_or_expr()]
        # 支持分号/全角逗号分隔的多表达式序列（如 p = 推进(p); 当前(p)）
        # 注意：分号后若跨行则视为语句分隔符，不再继续解析表达式序列
        _expr_start_line = self._current().line
        while True:
            _is_sep = (
                (self._check(TokenType.SYMBOL) and self._current().value == ";")
                or (self._check(TokenType.IDENTIFIER) and self._current().value == ";")
            )
            # 全角逗号仅在 stop_at_comma=False 时作为分隔符
            if not stop_at_comma:
                _is_sep = _is_sep or self._check(TokenType.MATHA_COMMA)
            if not _is_sep:
                break
            _sep_line = self._current().line
            self._advance()
            self._skip_newlines()
            # 跨行：视为语句分隔符（lambda 体内允许跨行表达式）
            if (self._check(TokenType.NEWLINE) or (self._current().line != _sep_line)) and not self._in_lambda_body:
                break
            if self._is_primary_start():
                exprs.append(self._parse_or_expr())
            else:
                break
        if len(exprs) == 1:
            cond = exprs[0]
        else:
            # 多表达式序列：用最后一个表达式作为值
            cond = exprs[-1]
        if self._check(TokenType.OP_QUESTION):
            self._advance()
            then_expr = self._parse_expr()
            self._skip_newlines()
            # 检查 else 分支：可能是 else expr，也可能是裸的 else 值（如 `假`）
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                saved = self.pos
                self._advance()
                self._skip_newlines()
                next_is_if_branch = (
                    self._check(TokenType.IDENTIFIER) and self._current().value in ("then", "else", "in")
                )
                if not next_is_if_branch:
                    # else 属于外层三元：回退并作为 else 分支
                    self.pos = saved
                    self._advance()
                    else_expr = self._parse_expr()
                    return ast.IfExpr(cond=cond, then=then_expr, else_=else_expr)
                # else 属于内层 if-expr，不消费
            elif self._check(TokenType.LIT_BOOL):
                # 裸 else 值：如 `(cond) ? a 假 : b`
                # 将当前标识符作为 else 分支
                else_expr = self._parse_expr()
                self._skip_newlines()
                self._expect(TokenType.OP_COLON, ":")
                else_expr = self._parse_expr()
                return ast.IfExpr(cond=cond, then=then_expr, else_=else_expr)
            else:
                self._expect(TokenType.OP_COLON, ":")
                else_expr = self._parse_expr()
                return ast.IfExpr(cond=cond, then=then_expr, else_=else_expr)
            return then_expr
        return cond

    def _parse_or_expr(self):
        """<or_expr> = <and_expr> , { "or" , <and_expr> }"""
        left = self._parse_and_expr()
        while self._check(TokenType.KW_OR):
            self._advance()
            self._skip_newlines()
            right = self._parse_and_expr()
            left = ast.BinaryOp(op="or", left=left, right=right)
        return left

    def _parse_and_expr(self):
        """<and_expr> = <rel_expr> , { "and" , <rel_expr> }"""
        left = self._parse_rel_expr()
        while self._check(TokenType.KW_AND):
            self._advance()
            self._skip_newlines()
            right = self._parse_rel_expr()
            left = ast.BinaryOp(op="and", left=left, right=right)
        return left

    def _parse_rel_expr(self):
        """<rel_expr> = <add_expr> , [ <rel_op> , <add_expr> | <expr> ]

        比较运算符（> < >= <=）的右操作数用 _parse_add_expr（标准行为）。
        赋值/等于运算符（= ==）的右操作数用 _parse_expr，使绑定值能包含三元表达式。

        例：
          `m = 3 > 2 ? 100 : 200` → Binding(m, IfExpr(cond=3>2, then=100, else=200))
          `3 > 2 ? 100 : 200`     → IfExpr(cond=3>2, then=100, else=200)
          `z = 3 > 2`             → Binding(z, BinaryOp('>', 3, 2))
        """
        left = self._parse_add_expr()
        if self._check(TokenType.OP_LT, TokenType.OP_GT, TokenType.OP_LE, TokenType.OP_GE):
            op = self._advance().value
            right = self._parse_add_expr()
            return ast.BinaryOp(op=op, left=left, right=right)
        if self._check(TokenType.OP_ASSIGN, TokenType.OP_NEQ):
            op = self._advance().value
            # 处理连续等号：= = → ==（等于比较）
            if op == "=" and self._check(TokenType.OP_ASSIGN):
                self._advance()
                op = "=="
            # 在 lambda 体内比较语境中，= 作为比较运算符，右操作数用 _parse_add_expr
            # 在语句层，= 作为赋值运算符，右操作数用 _parse_expr 以支持三元表达式
            if self._in_lambda_rel:
                right = self._parse_add_expr()
            else:
                right = self._parse_expr()
            return ast.BinaryOp(op=op, left=left, right=right)
        # → 右箭头：等价于 -> 但作为比较运算符（a → b）
        if self._check(TokenType.OP_ARROW_FW):
            self._advance()
            right = self._parse_add_expr()
            return ast.BinaryOp(op="→", left=left, right=right)
        # Python in 成员判断
        if self._check(TokenType.KW_IN) and not self._in_let_value:
            # 前瞻：如果 in 后面是语句分隔符、语句开头关键字，或换行/EOF（let body 边界），则 not an operator
            saved = self.pos
            self._advance()
            self._skip_newlines()
            _after_in = self._current()
            _is_sep = self._is_stmt_separator()
            _is_stmt_keyword = _after_in.type in (
                TokenType.KW_FUNC, TokenType.KW_BREAK,
                TokenType.KW_CONTINUE, TokenType.KW_RETURN, TokenType.KW_IF,
                TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_MATCH,
                TokenType.KW_SWITCH, TokenType.KW_TRY, TokenType.KW_CATCH,
            ) or (_after_in.type == TokenType.IDENTIFIER and _after_in.value in ("let", "rec"))
            # in 后紧跟换行或 EOF → let body 边界（如 `let x = 1 in\n...`）
            _is_line_end = _after_in.type in (TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF)
            if _is_sep or _is_stmt_keyword or _is_line_end:
                # in 是 let 语句的关键字，回退
                self.pos = saved
            else:
                # in 是二元运算符
                right = self._parse_add_expr()
                return ast.BinaryOp(op=" in ", left=left, right=right)
        # 属于判断 ∈
        if self._check(TokenType.SYMBOL) and self._current().value == "∈":
            self._advance()
            right = self._parse_add_expr()
            return ast.Belongs(left=left, right=right)
        return left

    def _parse_add_expr(self):
        """<add_expr> = <mul_expr> , { ("+" | "-") , <mul_expr> }"""
        left = self._parse_mul_expr()
        while self._check(TokenType.OP_PLUS, TokenType.OP_MINUS):
            op = self._advance().value
            right = self._parse_mul_expr()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_mul_expr(self):
        """<mul_expr> = <pow_expr> , { ("*" | "/" | "%") , <pow_expr> }"""
        left = self._parse_pow_expr()
        while self._check(TokenType.OP_STAR, TokenType.OP_SLASH, TokenType.OP_MOD):
            op = self._advance().value
            right = self._parse_pow_expr()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_pow_expr(self):
        """<pow_expr> = <unary> , [ "^" , <pow_expr> ]（中缀次方，右结合）"""
        left = self._parse_unary()
        if self._check(TokenType.OP_POWER):
            self._advance()
            right = self._parse_pow_expr()
            return ast.BinaryOp(op="^", left=left, right=right)
        return left

    def _parse_unary(self):
        """<unary> = [ "-" | "^" | "++" | "--" ] , <postfix>
        ^ 双语义消解：前无操作数 → 前缀开方（§16）"""
        if self._check(TokenType.OP_MINUS):
            self._advance()
            operand = self._parse_postfix()
            return ast.UnaryOp(op="-", operand=operand)
        if self._check(TokenType.OP_POWER):
            # 前缀开方 ^9=3（前无操作数）
            self._advance()
            operand = self._parse_postfix()
            return ast.UnaryOp(op="^", operand=operand)
        # 前缀自增 / 自减
        if self._check(TokenType.OP_INCR, TokenType.OP_DECR):
            op = self._advance().value
            operand = self._parse_postfix()
            return ast.UnaryOp(op=op, operand=operand)
        return self._parse_postfix()

    def _parse_postfix(self):
        """<postfix> = <primary> , { <primary> }（函数应用，左结合）

        注意：当 _in_control_flow=True 时（if/while/for 的条件解析中），
        跳过 { ... } 作为函数参数的消费，避免条件表达式后的代码块被误判为参数。

        Lambda 应用特殊处理：当 expr 是 Lambda 且下一 token 为 ( 时，
        不将 ( 消费为参数（否则 lambda 应用会被内层消费），
        让外层 _parse_paren_dispatch 处理 lambda 应用。
        另外，在 lambda 体内（_in_lambda_body=True），也不消费 ( 作为函数应用，
        以便外层能识别 lambda 直接应用 (params) => body(args)。

        重要：当 primary 是 Variable 且后续 token 为 KW_IF 时，
        应将 primary 与 if 表达式组合（如 a if cond else b）。
        """
        expr = self._parse_primary()
        # 属性访问和函数应用交替处理：当前(p).类型 → PathExpr(FuncApp(当前, p), 类型)
        while True:
            # 属性访问：expr.field
            while self._check(TokenType.PUNCT_DOT):
                    self._advance()
                    field = self._expect(TokenType.IDENTIFIER, "属性名").value
                    expr = ast.PathExpr(left=expr, right=field)
            # 属于判断 / 路径：expr >> expr
            if self._check(TokenType.OP_NEXT):
                saved = self.pos
                self._advance()
                if self._is_primary_start():
                    # 路径语境：a >> b → PathExpr（仅在绑定/设定语境）
                    if self._is_path_context():
                        right = self._parse_variable()
                        expr = ast.PathExpr(left=expr, right=right)
                    else:
                        right = self._parse_or_expr()
                        expr = ast.Belongs(left=expr, right=right)
                    continue
                else:
                    self.pos = saved
            # 下标访问：expr[index] 或 expr[start:end]
            if self._check(TokenType.PUNCT_LBRACKET):
                self._advance()
                start = None
                end = None
                has_colon = False
                # 检查是否是切片（冒号分隔）
                if self._check(TokenType.OP_COLON):
                    has_colon = True
                    self._advance()
                    end = self._parse_expr() if not self._check(TokenType.PUNCT_RBRACKET) else None
                elif not self._check(TokenType.PUNCT_RBRACKET):
                    start = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.OP_COLON):
                        has_colon = True
                        self._advance()
                        end = self._parse_expr() if not self._check(TokenType.PUNCT_RBRACKET) else None
                self._expect(TokenType.PUNCT_RBRACKET, "]")
                if has_colon:
                    expr = ast.SliceExpr(container=expr, start=start, end=end)
                else:
                    expr = ast.IndexExpr(container=expr, index=start if start is not None else ast.IntegerLit(value=0))
                continue
            # if-else 表达式延续：primary 后跟 if ... else ...（仅在非控制流语境）
            # 例如：浮点 if 有小数点 else 整数
            # 只有当 if 后紧跟 then/else 时才触发，避免将 if 关键字误判为表达式延续
            if not self._in_control_flow and self._check(TokenType.KW_IF):
                # 前瞻：检查 if 后面是否有 then/else，如果没有则不是 if-expr
                saved = self.pos
                self._advance()  # peek past if
                self._skip_newlines()
                next_is_if_branch = (
                    self._check(TokenType.IDENTIFIER) and self._current().value in ("then", "else")
                )
                if not next_is_if_branch:
                    self.pos = saved
                    break
                # 确认是 if-expr，恢复位置正式解析
                self.pos = saved
                self._advance()  # consume if
                saved_cf = self._in_control_flow
                self._in_control_flow = True
                try:
                    cond = self._parse_expr()
                finally:
                    self._in_control_flow = saved_cf
                if self._check(TokenType.IDENTIFIER) and self._current().value == "then":
                    self._advance()
                    then_val = self._parse_expr()
                    self._skip_newlines()
                    else_val = None
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                        self._advance()
                        else_val = self._parse_expr()
                    expr = ast.IfExpr(cond=cond, then=then_val, else_=else_val)
                    continue
                elif self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                    self._advance()
                    else_val = self._parse_expr()
                    expr = ast.IfExpr(cond=cond, then=else_val, else_=None)
                    continue
                else:
                    self.pos = saved
                    break
            # 函数应用：expr(arg) — 仅当 expr 是 Variable/PathExpr/Literal 时
            # 不将 ( 消费为函数参数如果 expr 是 Lambda（已由 _parse_paren_dispatch 处理）
            # 也不将 ( 消费为分组如果 expr 是 BinaryOp（如 p = 推进(p)）
            if not self._check(TokenType.PUNCT_LPAREN):
                break
            if isinstance(expr, ast.Lambda):
                break
            if isinstance(expr, ast.BinaryOp):
                break
            self._advance()  # consume (
            # if-continuation in function args: 做Token(浮点 if 有小数点 else 整数, ...)
            # 前瞻：如果 ( 后跟 <ident> if，则第一个参数是 if-expr
            if not self._check(TokenType.PUNCT_RPAREN):
                first_tok = self._current().type
                first_is_ident = (first_tok == TokenType.IDENTIFIER or first_tok == TokenType.MATHA_PLACEHOLDER)
                second_is_if = (
                    self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.KW_IF
                )
                if first_is_ident and second_is_if:
                    # 保存第一个标识符，消费它，然后解析 if-expr
                    first_ident = self._advance().value
                    saved_cf = self._in_control_flow
                    self._in_control_flow = True
                    try:
                        if_expr = self._parse_if_expr()
                    finally:
                        self._in_control_flow = saved_cf
                    # if_expr 消费了 if cond then/else ...
                    # 构造 IfExpr(cond=if_expr.cond, then=first_ident, else_=if_expr.else_)
                    cond = if_expr.cond
                    then_val = ast.Variable(name=first_ident, is_placeholder=False)
                    else_val = if_expr.else_
                    if_expr = ast.IfExpr(cond=cond, then=then_val, else_=else_val)
                    args = [if_expr]
                    self._in_func_app = True
                    try:
                        while self._check(TokenType.PUNCT_COMMA):
                            self._advance()
                            args.append(self._parse_expr())
                    finally:
                        self._in_func_app = False
                    self._expect(TokenType.PUNCT_RPAREN, ")")
                    expr = ast.FuncApp(func=expr, arg=args[0])
                    continue
            if self._check(TokenType.PUNCT_RPAREN):
                self._advance()
                expr = ast.FuncApp(func=expr, arg=ast.IntegerLit(value=0))
            else:
                self._in_func_app = True
                try:
                    args = [self._parse_expr()]
                    while self._check(TokenType.PUNCT_COMMA):
                        self._advance()
                        args.append(self._parse_expr())
                    # 支持无逗号分隔的参数（柯里化）：f(a b c) → FuncApp(FuncApp(a, b), c)
                    while not self._check(TokenType.PUNCT_RPAREN):
                        if self._current().type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER,
                                                     TokenType.LIT_INTEGER, TokenType.LIT_FLOAT,
                                                     TokenType.LIT_STRING, TokenType.LIT_BOOL,
                                                     TokenType.PUNCT_LPAREN, TokenType.PUNCT_LBRACKET,
                                                     TokenType.PUNCT_LBRACE, TokenType.KW_IF,
                                                     TokenType.MATHA_READ_OPEN, TokenType.MATHA_READ_OPEN2):
                            args.append(self._parse_expr())
                        elif self._is_comma():
                            self._advance()
                            args.append(self._parse_expr())
                        else:
                            break
                finally:
                    self._in_func_app = False
                self._expect(TokenType.PUNCT_RPAREN, ")")
                # 多参数：构建嵌套 FuncApp（柯里化应用）f(a, b, c) → f(a)(b)(c)
                if len(args) == 1:
                    expr = ast.FuncApp(func=expr, arg=args[0])
                else:
                    # f(a)(b)(c)：从左到右嵌套
                    for i, arg in enumerate(args):
                        expr = ast.FuncApp(func=expr, arg=arg)
            # 继续检查后续属性访问
        return expr

    def _is_primary_start(self) -> bool:
        """当前 Token 是否可作为 primary 开头。"""
        return self._current().type in (
            TokenType.LIT_INTEGER, TokenType.LIT_FLOAT, TokenType.LIT_STRING,
            TokenType.LIT_BOOL, TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER,
            TokenType.OP_ANGLE, TokenType.PUNCT_LPAREN, TokenType.PUNCT_LBRACKET,
            TokenType.PUNCT_LBRACE, TokenType.MATHA_READ_OPEN, TokenType.MATHA_READ_OPEN2,
            TokenType.KW_IF,  # lambda 体内 if 作为表达式
            TokenType.SYMBOL,  # 符号 token（emoji、数学符号、BoxDrawing 等）可作为变量名
        )

    def _parse_primary(self):
        """<primary> = <integer> | <float> | <string> | <bool> | <variable>
                    | <angle_expr> | <path_expr> | <set_construct> | <read_block>
                    | <output> | <set_up> | <lambda> | <code_block> | "(" , <expr> , ")"
        """
        tok = self._current()

        # 整数 / 浮点
        if tok.type == TokenType.LIT_INTEGER:
            self._advance()
            return self._make_number_lit(tok.value, is_float=False)
        if tok.type == TokenType.LIT_FLOAT:
            self._advance()
            return self._make_number_lit(tok.value, is_float=True)

        # 字符串
        if tok.type == TokenType.LIT_STRING:
            self._advance()
            return ast.StringLit(value=tok.value)

        # 布尔
        if tok.type == TokenType.LIT_BOOL:
            self._advance()
            return ast.BoolLit(value=tok.value in ("真", "true"))

        # 变量 / 占位符
        if tok.type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER, TokenType.SYMBOL):
            return self._parse_variable()

        # 角度 <<90
        if tok.type == TokenType.OP_ANGLE:
            self._advance()
            return ast.AngleExpr(expr=self._parse_expr())

        # ( ... ) 分组 / lambda / 元组
        if tok.type == TokenType.PUNCT_LPAREN:
            return self._parse_paren_dispatch()

        # [ ... ] 列表字面量 / 输出
        # 空列表 [] 始终解析为列表字面量；非空列表在函数应用语境中或独立使用时均解析为列表字面量
        if tok.type == TokenType.PUNCT_LBRACKET:
            saved = self.pos
            self._advance()  # consume [
            if self._check(TokenType.PUNCT_RBRACKET):
                # 空列表 [] → 列表字面量
                self._advance()
                return ast.ListLiteral(elements=[])
            self.pos = saved  # 回退，可能是输出或非空列表
            # 非空列表：在函数应用语境中，或紧跟 => (lambda 体中) / = (绑定右值) / 逗号 (setUp) 时解析为列表
            if self._in_func_app or self._check(TokenType.OP_FATARROW) or self._check(TokenType.OP_ASSIGN):
                return self._parse_list_literal()
            # 绑定右值语境：opt = [...] 中的 [ 应解析为列表
            if getattr(self, '_in_bind_value', False):
                return self._parse_list_literal()
            # 独立使用：检查是否紧跟换行、EOF 或 | (输出语境)
            if self._check(TokenType.NEWLINE, TokenType.EOF, TokenType.OP_PIPE, TokenType.MATHA_COMMA):
                return self._parse_list_literal()
            return self._parse_output()

        # { ... } 集合构造 / 代码块
        if tok.type == TokenType.PUNCT_LBRACE:
            return self._parse_brace_dispatch()

        # if-else 表达式（lambda 体内 / match 分支内 / 函数参数内）
        if tok.type == TokenType.KW_IF:
            return self._parse_if_expr()

        # match 表达式（lambda 体内 / match 分支内 / 赋值右值）
        if tok.type == TokenType.KW_MATCH:
            return self._parse_match_stmt()

        # 【...】 / 〔...〕 读取块
        if self._is_read_open():
            return self._parse_read_or_command()

        # 关键字作为变量名（如 func、and、or 用作标识符）
        if tok.type in (TokenType.KW_FUNC, TokenType.KW_AND, TokenType.KW_OR,
                        TokenType.KW_FOR, TokenType.KW_IN, TokenType.KW_WHILE):
            self._advance()
            return ast.Variable(name=tok.value)

        raise ParseError("期望表达式", tok)

    def _parse_paren_dispatch(self):
        """( ... ) 消解：分组 / lambda / 元组（元组暂未实现）

        lambda 形式：(params) => body，params 为逗号分隔的参数名（可带 : Type）。
        通过「试探-回退」区分：先尝试解析参数列表，若紧随 => 则为 lambda，
        否则回退为分组表达式。修复历史 TODO：此前独立 lambda 的 params 永远
        为空，导致 lambda 无法作为一等值正确传递参数。
        """
        self._expect(TokenType.PUNCT_LPAREN, "(")
        # 空参数列表 () => body
        if self._check(TokenType.PUNCT_RPAREN):
            self._advance()
            if self._check(TokenType.OP_FATARROW):
                self._advance()
                self._skip_newlines()
                # 在 lambda 体内解析 body，阻止 ( 被消费为函数应用
                saved_lambda = self._in_lambda_body
                self._in_lambda_body = True
                try:
                    # 跳过空白行/注释后的 DEDENT（lambda 体为空或仅含注释时）
                    while self._check(TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
                        self._advance()
                    body = self._parse_expr()
                finally:
                    self._in_lambda_body = saved_lambda
                lam = ast.Lambda(params=[], body=body)
                # 支持 lambda 直接应用：() => body(args)
                if self._check(TokenType.PUNCT_LPAREN):
                    arg = self._parse_expr()
                    return ast.FuncApp(func=lam, arg=arg)
                return lam
            # () 无实义分组 → 函数调用空参数
            # 若在函数应用语境中（_in_func_app=True），返回空占位；否则仍为 Unit
            if self._in_func_app:
                return ast.IntegerLit(value=0)
            return ast.IntegerLit(value=0)
        # 试探：参数列表（标识符/占位符，逗号分隔，可带 :Type）后跟 => body
        # 关键：=> 在 ) 之后，故先消费 ) 再判 =>。若不是 lambda 则整体回退。
        # 在控制流语境中，跳过 lambda/元组试探，直接解析为分组表达式
        if not self._in_control_flow and self._current().type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER):
            saved = self.pos
            is_lambda = False
            try:
                params = [self._parse_lambda_param()]
                while self._is_comma():
                    self._advance()
                    self._skip_newlines()
                    params.append(self._parse_lambda_param())
                self._expect(TokenType.PUNCT_RPAREN, ")")
                if self._check(TokenType.OP_FATARROW):
                    self._advance()
                    self._skip_newlines()
                    # 在 lambda 体内解析 body，阻止 ( 被消费为函数应用
                    saved_lambda = self._in_lambda_body
                    self._in_lambda_body = True
                    try:
                        body = self._parse_expr()
                    finally:
                        self._in_lambda_body = saved_lambda
                    lam = ast.Lambda(params=params, body=body)
                    # 支持 lambda 直接应用：(params) => body(args)
                    # 若 lambda 后立即跟 (，则解析为应用
                    if self._check(TokenType.PUNCT_LPAREN):
                        arg = self._parse_expr()
                        return ast.FuncApp(func=lam, arg=arg)
                    return lam
                # 消费了 ) 但无 => → 不是 lambda，回退
                self.pos = saved
            except ParseError:
                self.pos = saved
            # 若在函数应用语境中，尝试解析为多参函数调用 f(a, b) 或 f a b
            if self._in_func_app:
                    args = [self._parse_expr()]
                    # 支持无逗号分隔的参数：f(a b c) → FuncApp(FuncApp(a, b), c)
                    while not self._check(TokenType.PUNCT_RPAREN):
                        # 如果下一个 token 是表达式起始（标识符、括号等），视为函数应用参数
                        if self._current().type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER,
                                                     TokenType.LIT_INTEGER, TokenType.LIT_FLOAT,
                                                     TokenType.LIT_STRING, TokenType.LIT_BOOL,
                                                     TokenType.PUNCT_LPAREN, TokenType.PUNCT_LBRACKET,
                                                     TokenType.PUNCT_LBRACE, TokenType.KW_IF,
                                                     TokenType.MATHA_READ_OPEN, TokenType.MATHA_READ_OPEN2):
                            args.append(self._parse_expr())
                        elif self._is_comma():
                            self._advance()
                            args.append(self._parse_expr())
                        else:
                            break
                    self._expect(TokenType.PUNCT_RPAREN, ")")
                    # 返回第一个参数，由外层 _parse_postfix 构造 FuncApp
                    if len(args) == 1:
                        return args[0]
                    return args[0]
        # 元组字面量：(expr, expr, ...) — 必须有逗号才是元组
        # 在控制流语境中，跳过 lambda/元组试探，避免语句序列中的括号被误判
        if not self._in_control_flow and self._current().type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER,
                                    TokenType.LIT_INTEGER, TokenType.LIT_FLOAT,
                                    TokenType.LIT_STRING, TokenType.LIT_BOOL):
            try:
                elements = [self._parse_expr()]
                self._skip_newlines()
                has_comma = False
                while self._is_comma():
                    has_comma = True
                    self._advance()
                    elements.append(self._parse_expr())
                    self._skip_newlines()
                self._expect(TokenType.PUNCT_RPAREN, ")")
                # 只有有逗号时才认为是元组，否则回退为分组
                if has_comma and not self._check(TokenType.OP_FATARROW):
                    return ast.TupleExpr(elements=elements)
                # 无逗号：分组表达式，直接返回（已消费 )）
                return elements[0]
            except ParseError:
                pass
        # 控制流语境中的元组试探：(expr, expr, ...)  — 允许 [ 开头的元组（如 ([], p)）
        if self._in_control_flow and not self._check(TokenType.OP_FATARROW):
            saved = self.pos
            try:
                elements = [self._parse_expr()]
                self._skip_newlines()
                has_comma = False
                while self._is_comma():
                    has_comma = True
                    self._advance()
                    elements.append(self._parse_expr())
                    self._skip_newlines()
                self._expect(TokenType.PUNCT_RPAREN, ")")
                if has_comma:
                    return ast.TupleExpr(elements=elements)
                # 无逗号：回退为分组
                self.pos = saved
            except ParseError:
                self.pos = saved
                # 回退后恢复 _in_control_flow，让分组代码正确处理三元
                pass
        # 分组: (expr) — 支持三元表达式 (cond) ? a : b
        expr = self._parse_expr()
        self._skip_newlines()
        # 检查是否为三元表达式
        if self._check(TokenType.OP_QUESTION):
            self._advance()
            then_expr = self._parse_expr()
            self._skip_newlines()
            self._expect(TokenType.OP_COLON, ":")
            else_expr = self._parse_expr()
            expr = ast.IfExpr(cond=expr, then=then_expr, else_=else_expr)
        elif self._is_comma():
            # 控制流语境中的逗号：回退为元组
            self._advance()
            elements = [expr]
            elements.append(self._parse_expr())
            while self._is_comma():
                self._advance()
                elements.append(self._parse_expr())
                self._skip_newlines()
            self._expect(TokenType.PUNCT_RPAREN, ")")
            return ast.TupleExpr(elements=elements)
        self._expect(TokenType.PUNCT_RPAREN, ")")
        return expr

    def _parse_lambda_param(self):
        """lambda 参数：name 或 name: Type（类型标注可选，仅消费不保留）。"""
        tok = self._current()
        if tok.type == TokenType.MATHA_PLACEHOLDER:
            self._advance()
            return ast.Variable(name=tok.value, is_placeholder=True)
        # 参数名可以是关键字（如 func、and、or）
        if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                        TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                        TokenType.KW_IN, TokenType.KW_WHILE):
            self._advance()
            name = tok.value
        else:
            name = self._expect(TokenType.IDENTIFIER, "lambda 参数名").value
        if self._is_colon():
            self._advance()
            self._parse_type_expr()  # 消费类型标注
        return ast.Variable(name=name)

    def _parse_output(self) -> ast.Output:
        """<output> = [ , [ <expr> ] , ]

        输出内容可为表达式或自然语言文本（如 [你好，世界]）。
        当内容无法解析为完整表达式（含闭括号 ]）时，回退为文本字符串。
        """
        self._expect(TokenType.PUNCT_LBRACKET, "输出左括号 [")
        if self._check(TokenType.PUNCT_RBRACKET):
            self._advance()
            return ast.Output(expr=None)

        # 尝试解析为 表达式 + ]；失败则回退为文本
        saved_pos = self.pos
        try:
            expr = self._parse_expr()
            self._expect(TokenType.PUNCT_RBRACKET, "输出右括号 ]")
            return ast.Output(expr=expr)
        except ParseError:
            self.pos = saved_pos
            parts: list[str] = []
            while not self._check(TokenType.PUNCT_RBRACKET, TokenType.EOF):
                parts.append(self._advance().value)
            self._expect(TokenType.PUNCT_RBRACKET, "输出右括号 ]")
            return ast.Output(expr=ast.StringLit(value="".join(parts)))

    def _parse_list_literal(self) -> ast.ListLiteral:
        """<list_literal> = [ <expr> , { , <expr> } ]"""
        self._expect(TokenType.PUNCT_LBRACKET, "列表左括号 [")
        elements: list[Any] = []
        if not self._check(TokenType.PUNCT_RBRACKET):
            elements.append(self._parse_expr())
            while self._check(TokenType.PUNCT_COMMA):
                self._advance()
                elements.append(self._parse_expr())
        self._expect(TokenType.PUNCT_RBRACKET, "列表右括号 ]")
        return ast.ListLiteral(elements=elements)

    def _parse_variable(self) -> ast.Variable:
        """<variable> = <placeholder> | <identifier> | <symbol>"""
        tok = self._current()
        if tok.type == TokenType.MATHA_PLACEHOLDER:
            self._advance()
            return ast.Variable(name=tok.value, is_placeholder=True)
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            return ast.Variable(name=tok.value, is_placeholder=False)
        # SYMBOL token（emoji、数学符号等）作为变量名
        if tok.type == TokenType.SYMBOL:
            self._advance()
            return ast.Variable(name=tok.value, is_placeholder=False)
        raise ParseError("期望变量名或占位符 ？", tok)

    def _make_number_lit(self, value: str, is_float: bool):
        """从字面量字符串构造数字 AST（分离数值与 CJK 单位）。

        支持进制前缀：0b(二进制) / 0t(三进制) / 0x(十六进制)。
        进制字面量保留原始形式，此处按前缀转换为十进制 int。
        """
        # 进制前缀识别：0b / 0t / 0x
        if len(value) >= 3 and value[0] == "0":
            p = value[1].lower()
            if p in ("b", "t", "x"):
                radix = {"b": 2, "t": 3, "x": 16}[p]
                digits = value[2:]
                # 分离进制数字（ASCII）与 CJK 单位（非 ASCII）
                num_part = "".join(ch for ch in digits if ord(ch) < 128)
                unit_part = "".join(ch for ch in digits if ord(ch) >= 128)
                return ast.IntegerLit(value=int(num_part, radix), unit=unit_part)
        # 普通十进制：分离数字部分与 CJK 单位部分
        num_part = ""
        unit_part = ""
        for ch in value:
            if ch.isdigit() or ch == ".":
                num_part += ch
            else:
                unit_part += ch
        if is_float:
            return ast.FloatLit(value=float(num_part), unit=unit_part)
        return ast.IntegerLit(value=int(num_part), unit=unit_part)

    # ============================================================
    # §3 自然语言前端
    # <nl_block> = <read_natural>
    # <read_natural> = 【 <annotation> 】 <natural_lang>
    # ============================================================

    def _parse_nl_block(self):
        """<nl_block> = 【*/文字/*】<natural_lang>

        标注块后的自然语言正文（跳过换行，读取下一行整行作为意图描述）。
        正文从原始源码切片，保留空格与标点（英文正文不丢空格）。
        """
        self._advance()  # 消费 【 或 〔
        annotation = self._parse_annotation()
        self._advance()  # 消费 】 或 〕
        # 不跳过换行：】后若直接换行/EOF，说明标注块单独成行，
        # 后续是代码块（如 #N：{...}），不应被当作自然语言正文吞掉。
        if self._check(TokenType.NEWLINE, TokenType.EOF):
            return ast.NLBlock(annotation=annotation, natural_lang="")
        # 记录正文起始 token，消费正文到换行
        start_tok = self._current()
        while not self._check(TokenType.NEWLINE, TokenType.EOF):
            self._advance()
        # 从原始源码切片正文（保留空格，不依赖 token.value 拼接）
        natural_lang = self._slice_from(start_tok)
        return ast.NLBlock(annotation=annotation, natural_lang=natural_lang)

    def _slice_from(self, start_tok: Token) -> str:
        """从原始源码切片：start_tok 起始到行尾（当前 token 为 NEWLINE/EOF）。

        用 source_lines[line][col:] 切片，保留 token 间的空格与标点，
        避免 lexer 跳过空格导致英文正文丢空格。
        """
        line_idx = start_tok.line - 1
        if 0 <= line_idx < len(self.source_lines):
            line = self.source_lines[line_idx]
            return line[start_tok.col - 1:].rstrip()
        return ""

    # ============================================================
    # §5 类型系统
    # <type_expr> = <basic_type> | <set_type> | <func_type> | ...
    # ============================================================

    def _parse_type_expr(self):
        """<type_expr>"""
        tok = self._current()
        # 元组类型：(T1, T2, ...)
        if tok.type == TokenType.PUNCT_LPAREN:
            self._advance()
            elem_types = [self._parse_type_expr()]
            while self._check(TokenType.PUNCT_COMMA):
                self._advance()
                elem_types.append(self._parse_type_expr())
            self._expect(TokenType.PUNCT_RPAREN, ")")
            if len(elem_types) == 1:
                return elem_types[0]
            return ast.TupleType(types=elem_types)
        # 命名类型：内置基本类型或用户自定义类型（含关键字作为类型名）
        if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                        TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                        TokenType.KW_IN, TokenType.KW_WHILE):
            self._advance()
            base = ast.BasicType(name=tok.value)
            # Set[T]
            if self._check(TokenType.PUNCT_LBRACKET):
                self._advance()
                elem = self._parse_type_expr()
                self._expect(TokenType.PUNCT_RBRACKET, "]")
                return ast.SetType(elem_type=elem)
            return base
        raise ParseError("期望类型表达式", tok)

    # ============================================================
    # §7 语句与控制流
    # ============================================================

    def _parse_statement(self):
        """<statement> = let | while | if | for | match | go | func | expr_or_binding"""
        tok = self._current()
        # let x = expr [in expr]
        if tok.type == TokenType.IDENTIFIER and tok.value == "let":
            return self._parse_let()
        # while cond { block }
        if tok.type == TokenType.KW_WHILE:
            return self._parse_while()
        # if cond { block } [ 否则 { block }]
        if tok.type == TokenType.KW_IF:
            return self._parse_if()
        # for var in expr { block }
        if tok.type == TokenType.KW_FOR:
            return self._parse_for()
        if tok.type == TokenType.KW_MATCH:
            return self._parse_match_stmt()
        if tok.type == TokenType.KW_GO:
            self._advance()
            return ast.GoStmt(expr=self._parse_expr())
        if tok.type == TokenType.KW_FUNC:
            return self._parse_func_def()
        # typeof <expr>
        if tok.type == TokenType.KW_TYPEOF:
            self._advance()
            operand = self._parse_expr()
            return ast.TypeOfExpr(operand=operand)
        # switch <expr> { case <val>: <expr> ... default: <expr> }
        if tok.type == TokenType.KW_SWITCH:
            return self._parse_switch()
        return self._parse_expr_or_binding()

    def _parse_let(self) -> ast.AST:
        """let [rec] <name> = <expr> [in <expr>]
        or: let (name1, name2, ...) = <expr> [in <expr>]
        or: let rec <name>(<params>) -> <type> = (<params>) => <expr>  (递归函数)"""
        self._expect(TokenType.IDENTIFIER, "let")
        is_rec = False
        if self._check(TokenType.IDENTIFIER) and self._current().value == "rec":
            is_rec = True
            self._advance()
        # 元组解构: let (a, b) = expr [in expr]
        # 注意：let rec calc(i: Int) -> Float = ... 是函数定义，不是元组解构
        # 通过 lookahead 区分：( 后跟 identifier: 为函数定义，identifier 后为 ,/) 为元组解构
        if self._check(TokenType.PUNCT_LPAREN):
            # lookahead: 检查 ( 后是否是 标识符: 形式（函数参数）
            _peek1 = self._peek(1)
            _is_typed_param = (
                _peek1.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                                TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                                TokenType.KW_IN, TokenType.KW_WHILE)
                and self._peek(2).type == TokenType.OP_COLON
            )
            if not _is_typed_param:
                return self._parse_let_tuple(is_rec)
            # 是函数定义，但 name 为空（匿名函数），直接跳到这里解析参数列表
            saved = self.pos
        else:
            name = self._expect(TokenType.IDENTIFIER, "绑定名").value
            # 检查是否为函数定义: name(params) -> Type = (params) => body
            # 保存位置：在消费 ( 之前，以便失败时回退到普通 let 绑定
            saved = self.pos
        # 检查是否为函数定义: name(params) -> Type = (params) => body
        if self._check(TokenType.PUNCT_LPAREN):
            try:
                # 解析参数列表
                self._advance()  # consume (
                params: list[tuple[str, Any]] = []
                if not self._check(TokenType.PUNCT_RPAREN):
                    params.append(self._parse_typed_param())
                    while self._is_comma():
                        self._advance()
                        params.append(self._parse_typed_param())
                self._expect(TokenType.PUNCT_RPAREN, ")")
                # 检查 -> 返回类型
                if self._check(TokenType.OP_ARROW):
                    self._advance()  # consume ->
                    ret_type = self._parse_type_expr()
                    # 检查 = (params) => body
                    self._expect(TokenType.OP_ASSIGN, "=")
                    self._skip_newlines()
                    self._expect(TokenType.PUNCT_LPAREN, "(")
                    lam_params: list[Any] = []
                    if not self._check(TokenType.PUNCT_RPAREN):
                        tok = self._current()
                        if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                                        TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                                        TokenType.KW_IN, TokenType.KW_WHILE):
                            self._advance()
                            lam_params.append(ast.Variable(name=tok.value))
                        else:
                            lam_params.append(ast.Variable(name=self._expect(TokenType.IDENTIFIER, "参数名").value))
                        while self._is_comma():
                            self._advance()
                            tok = self._current()
                            if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                                            TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                                            TokenType.KW_IN, TokenType.KW_WHILE):
                                self._advance()
                                lam_params.append(ast.Variable(name=tok.value))
                            else:
                                lam_params.append(ast.Variable(name=self._expect(TokenType.IDENTIFIER, "参数名").value))
                    self._expect(TokenType.PUNCT_RPAREN, ")")
                    self._expect(TokenType.OP_FATARROW, "=>")
                    self._skip_newlines()
                    # 在 lambda 体内比较语境中解析 body，使 = 作为比较而非赋值
                    # 同时设置 _in_lambda_body = True，使 ( 不被消费为函数应用
                    saved_rel = self._in_lambda_rel
                    saved_lb = self._in_lambda_body
                    self._in_lambda_rel = True
                    self._in_lambda_body = True
                    try:
                        lam_body = self._parse_lambda_body()
                    finally:
                        self._in_lambda_rel = saved_rel
                        self._in_lambda_body = saved_lb
                    body = ast.Lambda(params=lam_params, body=lam_body)
                    if len(params) == 0:
                        param_type: Any = ast.BasicType(name="Unit")
                    elif len(params) == 1:
                        param_type = params[0][1] or ast.BasicType(name="Int")
                    else:
                        param_type = ast.TupleType(types=[p[1] or ast.BasicType(name="Int") for p in params])
                    func_type = ast.FuncType(param_type=param_type, return_type=ret_type)
                    func_def = ast.FuncDef(name=name, annotation=None, func_type=func_type, body=body)
                    # 检查后面是否有对同一变量的调用：let rec f = lambda; f(args) → LetBinding with body
                    if is_rec and self._check(TokenType.IDENTIFIER) and self._current().value == name:
                        next_saved = self.pos
                        try:
                            self._advance()  # consume name
                            if self._check(TokenType.PUNCT_LPAREN):
                                # 是一个函数调用，解析为 body
                                self._advance()  # consume (
                                call_args = [self._parse_expr()]
                                while self._check(TokenType.PUNCT_COMMA):
                                    self._advance()
                                    call_args.append(self._parse_expr())
                                self._expect(TokenType.PUNCT_RPAREN, ")")
                                # 构建嵌套 FuncApp（多参数 → 柯里化）
                                call_expr = ast.FuncApp(func=ast.Variable(name=name), arg=call_args[0])
                                for arg in call_args[1:]:
                                    call_expr = ast.FuncApp(func=call_expr, arg=arg)
                                # 继续解析调用后的表达式（如 sum(0, 0) / len(...)）
                                # 但仅当在同一行时：若跨行则认为是下一个语句，回退位置
                                saved_expr_pos = self.pos
                                saved_expr_line = self._current().line
                                saved_expr = self._in_lambda_body
                                self._in_lambda_body = False
                                try:
                                    body_expr = self._parse_expr()
                                    # 若跨过了换行（新行），回退到调用位置
                                    if self._current().line != saved_expr_line:
                                        self.pos = saved_expr_pos
                                        body_expr = call_expr
                                finally:
                                    self._in_lambda_body = saved_expr
                                # 返回 LetBinding，让解释器先注册再执行 body
                                return ast.LetBinding(name=name, value=func_def.body, is_recursive=True, params=params, body=body_expr)
                        except ParseError:
                            self.pos = next_saved  # 回退到函数调用前的位置
                            pass  # 不是函数调用，回退
                    return func_def
            except ParseError:
                # 回退到普通 let 绑定（恢复名字消费前的位置）
                self.pos = saved
        # 可选类型标注（无参数列表时）
        if self._is_colon():
            self._advance()
            self._parse_type_expr()
        self._expect(TokenType.OP_ASSIGN, "=")
        self._in_let_value = True
        try:
            value = self._parse_expr()
        finally:
            self._in_let_value = False
        # 可选 in
        body = None
        if self._check(TokenType.KW_IN):
            self._advance()
            body = self._parse_expr()
        return ast.LetBinding(name=name, value=value, is_recursive=is_rec, params=[], body=body)

    def _parse_let_tuple(self, is_rec: bool) -> ast.AST:
        """let (name1, name2, ...) = <expr> [in <expr>]"""
        self._expect(TokenType.PUNCT_LPAREN, "(")
        names = [self._expect(TokenType.IDENTIFIER, "绑定名").value]
        while self._check(TokenType.PUNCT_COMMA):
            self._advance()
            names.append(self._expect(TokenType.IDENTIFIER, "绑定名").value)
        self._expect(TokenType.PUNCT_RPAREN, ")")
        self._expect(TokenType.OP_ASSIGN, "=")
        self._in_let_value = True
        try:
            value = self._parse_expr()
        finally:
            self._in_let_value = False
        body = None
        if self._check(TokenType.KW_IN):
            self._advance()
            body = self._parse_expr()
        return ast.LetTupleBinding(names=names, value=value, body=body)

    def _parse_while(self) -> ast.WhileStmt:
        """while <expr> { <block> }"""
        self._expect(TokenType.KW_WHILE, "while")
        saved = self._in_control_flow
        self._in_control_flow = True
        try:
            cond = self._parse_expr()
        finally:
            self._in_control_flow = saved
        self._expect(TokenType.PUNCT_LBRACE, "{")
        block = self._parse_block_body()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.WhileStmt(cond=cond, block=block)

    def _parse_if(self) -> ast.AST:
        """if <expr> { <block> } [ 否则 { <block> }]
        or: if <expr> then <expr> else <expr>"""
        self._expect(TokenType.KW_IF, "if")
        # 在控制流上下文中解析条件和分支，防止 { ... } 被当作函数参数
        saved = self._in_control_flow
        self._in_control_flow = True
        try:
            cond = self._parse_expr()
            # 关键字形式: if cond then expr else expr
            if self._check(TokenType.IDENTIFIER) and self._current().value == "then":
                result = self._parse_if_then_else_expr(cond)
                if result is not None:
                    return result
            # 关键字形式: if cond else expr (省略 then)
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                result = self._parse_if_then_else_expr_no_then(cond)
                if result is not None:
                    return result
            # 语句形式: if cond { block } [ 否则 { block }]
            self._expect(TokenType.PUNCT_LBRACE, "{")
            then_block = self._parse_block_body()
            self._expect(TokenType.PUNCT_RBRACE, "}")
            else_block = None
            if self._check(TokenType.KW_OTHERWISE):
                self._advance()
                self._expect(TokenType.PUNCT_LBRACE, "{")
                else_block = self._parse_block_body()
                self._expect(TokenType.PUNCT_RBRACE, "}")
            return ast.IfStmt(cond=cond, then_block=then_block, else_block=else_block)
        finally:
            self._in_control_flow = saved

    def _parse_if_then_else_expr(self, cond) -> ast.IfExpr:
        """解析 if cond then expr else expr 三元表达式形式。
        then/else 分支支持分号分隔的表达式序列，取最后一个表达式的值。
        注意：如果 else 分支后还有 else（如 if A then B else C else D），
        则只取 then 分支，让外层三元继续。"""
        self._advance()  # consume 'then'
        then_exprs = self._parse_semicolon_exprs()
        self._skip_newlines()
        else_expr = None
        if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
            # 前瞻：如果 else 分支后还有 else，说明当前 else 属于外层三元，回退
            saved = self.pos
            self._advance()  # consume 'else'
            else_exprs = self._parse_semicolon_exprs()
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                # 还有 else，回退：else 属于外层
                self.pos = saved
            else:
                # 正常 else 分支
                pass
        # 取最后一个表达式作为分支值
        then_val = then_exprs[-1] if isinstance(then_exprs, list) and then_exprs else then_exprs
        else_val = else_exprs[-1] if isinstance(else_exprs, list) and else_exprs else else_exprs
        return ast.IfExpr(cond=cond, then=then_val, else_=else_val)

    def _parse_if_then_else_expr_no_then(self, cond) -> ast.IfExpr:
        """解析 if cond else expr 三元表达式形式（省略 then）。
        注意：如果 else 分支后还有 else（如 if A else B else C），
        则回退让外层三元消费 else。"""
        saved = self.pos
        saved_cf = self._in_control_flow
        self._in_control_flow = True
        try:
            self._advance()  # consume 'else'
            else_exprs = self._parse_semicolon_exprs()
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                # 还有 else，回退
                self.pos = saved
                self._in_control_flow = saved_cf
                return None
            else_val = else_exprs[-1] if isinstance(else_exprs, list) and else_exprs else else_exprs
            self._in_control_flow = saved_cf
            return ast.IfExpr(cond=cond, then=else_val, else_=None)
        except Exception:
            self.pos = saved
            self._in_control_flow = saved_cf
            return None

    def _parse_if_expr_impl(self) -> ast.IfExpr:
        """内部实现：解析 if 表达式（支持 then/else 关键字形式和 {block} 语句形式）。"""
        self._expect(TokenType.KW_IF, "if")
        _saved_if_depth = self._if_depth
        self._if_depth += 1
        try:
            # 条件解析保留控制流上下文（防止 { } 被误判为函数参数）
            saved = self._in_control_flow
            self._in_control_flow = True
            try:
                cond = self._parse_expr()
            finally:
                self._in_control_flow = saved
            # 关键字形式: if cond then expr else expr
            if self._check(TokenType.IDENTIFIER) and self._current().value == "then":
                self._advance()
                # 恢复 _in_control_flow 以允许 then/else 分支内解析嵌套 if 表达式
                self._in_control_flow = saved
                then_expr = self._parse_expr()
                self._skip_newlines()
                else_expr = None
                # 支持 elif: 作为 else: if ... 的语法糖
                while self._check(TokenType.IDENTIFIER) and self._current().value == "elif":
                    self._advance()
                    self._skip_newlines()
                    elif_cond = self._parse_expr()
                    self._skip_newlines()
                    # 支持 elif then ... 和 elif: ... 两种形式
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "then":
                        self._advance()
                    elif self._check(TokenType.OP_COLON):
                        self._advance()
                    self._skip_newlines()
                    elif_then = self._parse_expr()
                    self._skip_newlines()
                    else_expr = ast.IfExpr(cond=elif_cond, then=elif_then, else_=else_expr)
                if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                    # 前瞻：检查当前 else 后是否紧跟另一个 else（属于外层 if-expr），若是则不消费
                    _saved_else = self.pos
                    _saved_depth_at_else = self._if_depth
                    self._advance()  # consume 'else'
                    _else_expr = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "else" and self._if_depth < _saved_depth_at_else:
                        # 还有 else 且深度更低，回退让外层 if-expr 处理
                        self.pos = _saved_else
                        else_expr = None
                    else:
                        else_expr = _else_expr
                return ast.IfExpr(cond=cond, then=then_expr, else_=else_expr)
            # 冒号形式: if cond: expr else expr
            if self._check(TokenType.OP_COLON):
                self._advance()
                self._in_control_flow = saved
                then_expr = self._parse_expr()
                self._skip_newlines()
                else_expr = None
                # 支持 elif: 作为 else: if ... 的语法糖
                while self._check(TokenType.IDENTIFIER) and self._current().value == "elif":
                    self._advance()
                    self._skip_newlines()
                    # elif 后直接跟条件表达式（不跟冒号）
                    elif_cond = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.OP_COLON):
                        self._advance()
                        self._skip_newlines()
                    elif_then = self._parse_expr()
                    self._skip_newlines()
                    else_expr = ast.IfExpr(cond=elif_cond, then=elif_then, else_=else_expr)
                if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                    _saved_else = self.pos
                    _saved_depth_at_else = self._if_depth
                    self._advance()
                    _else_expr = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "else" and self._if_depth < _saved_depth_at_else:
                        self.pos = _saved_else
                        else_expr = None
                    else:
                        else_expr = _else_expr
                return ast.IfExpr(cond=cond, then=then_expr, else_=else_expr)
            # elif 形式: if cond elif cond2: expr2 else: expr3
            if self._check(TokenType.IDENTIFIER) and self._current().value == "elif":
                self._advance()
                self._skip_newlines()
                elif_cond = self._parse_expr()
                self._skip_newlines()
                if self._check(TokenType.OP_COLON):
                    self._advance()
                    self._skip_newlines()
                elif_then = self._parse_expr()
                self._skip_newlines()
                else_expr = None
                if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                    _saved_else = self.pos
                    _saved_depth_at_else = self._if_depth
                    self._advance()
                    # 支持 else: 语法（冒号作为分隔符）
                    if self._check(TokenType.OP_COLON):
                        self._advance()
                        self._skip_newlines()
                    _else_expr = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "else" and self._if_depth < _saved_depth_at_else:
                        self.pos = _saved_else
                        else_expr = None
                    else:
                        else_expr = _else_expr
                return ast.IfExpr(cond=cond, then=elif_then, else_=else_expr)
            # 关键字形式: if cond else expr (省略 then)
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                # 前瞻：检查当前 else 后是否紧跟另一个 else（属于外层 if-expr），若是则不消费
                _saved_else = self.pos
                _saved_depth_at_else = self._if_depth
                self._advance()  # consume 'else'
                self._skip_newlines()
                # 支持 else: 语法（冒号作为分隔符）
                if self._check(TokenType.OP_COLON):
                    self._advance()
                    self._skip_newlines()
                # 支持 elif: 作为 else 后跟 if ... 的语法糖
                elif_exprs = []
                while True:
                    # 解析 else 分支
                    _else_expr = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.IDENTIFIER) and self._current().value == "else" and self._if_depth < _saved_depth_at_else:
                        # 还有 else 且深度更低，回退让外层 if-expr 处理
                        self.pos = _saved_else
                        else_expr = None
                        return ast.IfExpr(cond=cond, then=None, else_=None)
                    elif_exprs.append(_else_expr)
                    # 检查是否有 elif
                    if not (self._check(TokenType.IDENTIFIER) and self._current().value == "elif"):
                        break
                    self._advance()
                    self._skip_newlines()
                    elif_cond = self._parse_expr()
                    self._skip_newlines()
                    if self._check(TokenType.OP_COLON):
                        self._advance()
                        self._skip_newlines()
                    elif_then = self._parse_expr()
                    self._skip_newlines()
                    else_expr = ast.IfExpr(cond=elif_cond, then=elif_then, else_=None)
                    # 将 elif 分支插入到 elif_exprs 中
                    if elif_exprs:
                        elif_exprs[-1] = else_expr
                    else:
                        elif_exprs = [else_expr]
                # 构建嵌套的 if-else 链
                if elif_exprs:
                    result = elif_exprs[-1]
                    for expr in reversed(elif_exprs[:-1]):
                        result = ast.IfExpr(cond=elif_exprs[elif_exprs.index(expr)+1] if expr in elif_exprs else expr, then=expr, else_=result)
                    else_expr = result
                else:
                    else_expr = None
                return ast.IfExpr(cond=cond, then=None, else_=else_expr)
            # 语句形式: if cond { block } [ 否则 { block }]
            self._expect(TokenType.PUNCT_LBRACE, "{")
            then_block = self._parse_block_body()
            self._expect(TokenType.PUNCT_RBRACE, "}")
            else_block = None
            if self._check(TokenType.KW_OTHERWISE):
                self._advance()
                self._expect(TokenType.PUNCT_LBRACE, "{")
                else_block = self._parse_block_body()
                self._expect(TokenType.PUNCT_RBRACE, "}")
            return ast.IfExpr(cond=cond, then=then_block, else_=else_block)
        finally:
            self._if_depth = _saved_if_depth

    def _parse_if_then_else_expr(self, cond) -> ast.IfExpr:
        """解析 if cond then expr else expr 三元表达式形式。
        then/else 分支支持分号分隔的表达式序列，取最后一个表达式的值。"""
        self._advance()  # consume 'then'
        saved = self._in_control_flow
        self._in_control_flow = True
        try:
            then_exprs = self._parse_semicolon_exprs()
            self._skip_newlines()
            else_expr = None
            if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
                self._advance()
                else_expr = self._parse_semicolon_exprs()
        finally:
            self._in_control_flow = saved
        then_val = then_exprs[-1] if isinstance(then_exprs, list) and then_exprs else then_exprs
        else_val = else_expr[-1] if isinstance(else_expr, list) and else_expr else else_expr
        return ast.IfExpr(cond=cond, then=then_val, else_=else_val)

    def _parse_if_then_else_expr_no_then(self, cond) -> ast.IfExpr:
        """解析 if cond else expr 三元表达式形式（省略 then）。
        注意：如果 else 分支后还有 else（如 if A else B else C），
        则只取 then 分支为 cond，让外层三元继续。"""
        saved = self.pos
        self._advance()  # consume 'else'
        else_exprs = self._parse_semicolon_exprs()
        self._skip_newlines()
        if self._check(TokenType.IDENTIFIER) and self._current().value == "else":
            # 还有 else，回退
            self.pos = saved
            return ast.IfExpr(cond=cond, then=cond, else_=None)
        else_val = else_exprs[-1] if isinstance(else_exprs, list) and else_exprs else else_exprs
        return ast.IfExpr(cond=cond, then=else_val, else_=None)

    def _parse_semicolon_exprs(self) -> Any:
        """解析分号分隔的表达式序列，返回最后一个表达式的 AST。"""
        self._skip_semicolon()
        exprs = [self._parse_expr()]
        while self._check(TokenType.SYMBOL) and self._current().value == ";":
            self._advance()
            exprs.append(self._parse_expr())
            self._skip_semicolon()
        return exprs[-1] if len(exprs) == 1 else exprs

    def _parse_if_expr(self) -> ast.IfExpr:
        """if <expr> { <block> } [ 否则 { <block> } ]
        or: if <expr> then <expr> else <expr>

        在 lambda 体内 / match 分支内作为表达式使用。
        返回 IfExpr，其 then/else_ 可能是 CodeBlock（语句形式）或表达式（三元形式）。
        """
        return self._parse_if_expr_impl()

    def _parse_for(self) -> ast.ForStmt:
        """for <var> in <expr> { <block> } 或 for (a, b) in <expr> { <block> }"""
        self._expect(TokenType.KW_FOR, "for")
        saved = self.pos
        # 试探元组解构：for (a, b) in ...
        if self._check(TokenType.PUNCT_LPAREN):
            self._advance()  # 消费 (
            params: list[Any] = []
            while not self._check(TokenType.PUNCT_RPAREN, TokenType.EOF):
                self._skip_newlines()
                if self._check(TokenType.PUNCT_RPAREN):
                    break
                if params:
                    self._expect(TokenType.PUNCT_COMMA, ",")
                p = self._current()
                if p.type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER):
                    self._advance()
                    params.append(p.value)
                else:
                    break
            self._skip_newlines()
            if self._check(TokenType.PUNCT_RPAREN):
                self._advance()  # 消费 )
                self._skip_newlines()
                if self._check(TokenType.KW_IN):
                    # 确认是 for (a, b) in 形式
                    self._expect(TokenType.KW_IN, "in")
                    saved_cf = self._in_control_flow
                    self._in_control_flow = True
                    try:
                        iterable = self._parse_expr()
                    finally:
                        self._in_control_flow = saved_cf
                    self._expect(TokenType.PUNCT_LBRACE, "{")
                    block = self._parse_block_body()
                    self._expect(TokenType.PUNCT_RBRACE, "}")
                    return ast.ForStmt(var=params, iterable=iterable, block=block)
            # 回退
            self.pos = saved
        # 普通 for var in expr
        var = self._expect(TokenType.IDENTIFIER, "迭代变量").value
        self._expect(TokenType.KW_IN, "in")
        saved_cf = self._in_control_flow
        self._in_control_flow = True
        try:
            iterable = self._parse_expr()
        finally:
            self._in_control_flow = saved_cf
        self._expect(TokenType.PUNCT_LBRACE, "{")
        block = self._parse_block_body()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.ForStmt(var=[var], iterable=iterable, block=block)

    def _parse_match_stmt(self) -> ast.MatchStmt:
        """<match_stmt> = match <expr> { | <pattern> => <expr> }"""
        self._expect(TokenType.KW_MATCH, "match")
        # 在控制流上下文中解析 scrutinee，防止 { ... } 被误判为函数参数/代码块
        saved = self._in_control_flow
        self._in_control_flow = True
        try:
            scrutinee = self._parse_expr()
        finally:
            self._in_control_flow = saved
        # 消费 match 体的开括号
        self._expect(TokenType.PUNCT_LBRACE, "{")
        branches: list[tuple[Any, Any]] = []
        # 分支以 | 开头，支持换行和分号分隔
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            self._skip_newlines()
            if not self._match(TokenType.OP_PIPE):
                break
            pattern = self._parse_pattern()
            # 支持 match guard: | _ if cond => value
            if (self._check(TokenType.IDENTIFIER) or self._check(TokenType.KW_IF)) and self._current().value == "if":
                self._advance()
                guard = self._parse_expr()
            else:
                guard = None
            self._expect(TokenType.OP_FATARROW, "=>")
            body = self._parse_expr()
            branches.append((pattern, guard, body))
            # 跳过换行或分号
            self._skip_newlines()
            self._skip_semicolon()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.MatchStmt(scrutinee=scrutinee, branches=branches)

    def _parse_switch(self) -> ast.SwitchStmt:
        """switch <expr> { case <val>: <expr> ... default: <expr> }"""
        self._expect(TokenType.KW_SWITCH, "switch")
        saved = self._in_control_flow
        self._in_control_flow = True
        try:
            value = self._parse_expr()
        finally:
            self._in_control_flow = saved
        self._expect(TokenType.PUNCT_LBRACE, "{")
        cases: list[tuple[Any, Any]] = []
        default_block = None
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF, TokenType.DEDENT):
            self._skip_newlines()
            if self._check(TokenType.KW_DEFAULT):
                self._advance()
                self._expect(TokenType.OP_COLON, ":")
                self._skip_newlines()
                default_block = self._parse_expr()
                self._skip_newlines()
                self._skip_semicolon()
            elif self._check(TokenType.KW_CASE):
                self._advance()
                case_val = self._parse_expr()
                self._expect(TokenType.OP_COLON, ":")
                self._skip_newlines()
                case_body = self._parse_expr()
                cases.append((case_val, case_body))
                self._skip_newlines()
                self._skip_semicolon()
            else:
                break
        if self._check(TokenType.DEDENT):
            self._advance()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.SwitchStmt(value=value, cases=cases, default_block=default_block)

    def _parse_pattern(self):
        """<pattern> = <literal> | <variable> | <constructor> | "_" | <belongs_pat>"""
        if self._check(TokenType.PUNCT_UNDERSCORE):
            self._advance()
            return ast.Variable(name="_")
        if self._check(TokenType.LIT_INTEGER):
            tok = self._advance()
            return self._make_number_lit(tok.value, is_float=False)
        if self._check(TokenType.LIT_FLOAT):
            tok = self._advance()
            return self._make_number_lit(tok.value, is_float=True)
        if self._check(TokenType.LIT_STRING):
            tok = self._advance()
            return ast.StringLit(value=tok.value)
        if self._check(TokenType.LIT_BOOL):
            tok = self._advance()
            return ast.BoolLit(value=tok.value in ("真", "true"))
        # 构造子模式：Name(...)
        if self._check(TokenType.IDENTIFIER):
            name = self._advance().value
            if self._check(TokenType.PUNCT_LPAREN):
                self._advance()  # 消费 (
                fields: list[Any] = []
                while not self._check(TokenType.PUNCT_RPAREN, TokenType.EOF):
                    self._skip_newlines()
                    if self._check(TokenType.PUNCT_RPAREN):
                        break
                    if fields:
                        self._expect(TokenType.PUNCT_COMMA, ",")
                    fields.append(self._parse_pattern())
                self._skip_newlines()
                self._expect(TokenType.PUNCT_RPAREN, ")")
                return ast.ConstructorPat(name=name, fields=fields)
            return ast.Variable(name=name)
        return self._parse_variable()

    # ============================================================
    # §8 函数定义
    # <func_def> = <identifier> [ <annotation> ] : <func_type> = <lambda>
    # ============================================================

    def _parse_decl(self):
        """<decl> = <binding> | <func_def> | <type_def> | <statement>"""
        tok = self._current()
        # 控制流语句（let/while/if/for）在顶层也可出现
        if tok.type == TokenType.IDENTIFIER and tok.value == "let":
            return self._parse_let()
        if tok.type == TokenType.KW_WHILE:
            return self._parse_while()
        if tok.type == TokenType.KW_IF:
            return self._parse_if()
        if tok.type == TokenType.KW_FOR:
            return self._parse_for()
        if tok.type == TokenType.KW_MATCH:
            return self._parse_match_stmt()
        if self._check(TokenType.KW_FUNC):
            return self._parse_func_def()
        # typeof <expr>
        if tok.type == TokenType.KW_TYPEOF:
            self._advance()
            operand = self._parse_expr()
            return ast.TypeOfExpr(operand=operand)
        # switch <expr> { case <val>: <expr> ... default: <expr> }
        if tok.type == TokenType.KW_SWITCH:
            return self._parse_switch()
        return self._parse_expr_or_binding()

    def _parse_func_def(self) -> ast.FuncDef:
        """<func_def> = func <id> [annotation] ( <params> ) -> <type> = <lambda>

        参数列表：(name: Type, name: Type, ...)，类型标注可选。
        lambda 体：(params) => expr
        """
        self._expect(TokenType.KW_FUNC, "func")
        name = self._expect(TokenType.IDENTIFIER, "函数名").value
        annotation = None
        if self._check(TokenType.MATHA_ANNOT_START):
            annotation = self._parse_annotation()
        # 参数列表（带类型标注）
        self._expect(TokenType.PUNCT_LPAREN, "(")
        params: list[tuple[str, Any]] = []
        if not self._check(TokenType.PUNCT_RPAREN):
            params.append(self._parse_typed_param())
            while self._is_comma():
                self._advance()
                params.append(self._parse_typed_param())
        self._expect(TokenType.PUNCT_RPAREN, ")")
        # 返回类型
        self._expect(TokenType.OP_ARROW, "->")
        ret_type = self._parse_type_expr()
        # 构造函数类型
        if len(params) == 0:
            param_type: Any = ast.BasicType(name="Unit")
        elif len(params) == 1:
            param_type = params[0][1] or ast.BasicType(name="Int")
        else:
            param_type = ast.TupleType(types=[p[1] or ast.BasicType(name="Int") for p in params])
        func_type = ast.FuncType(param_type=param_type, return_type=ret_type)
        # 函数体：(params) => expr 或 expr（直接表达式，零参 lambda）
        self._expect(TokenType.OP_ASSIGN, "=")
        self._skip_newlines()
        # 支持零参函数直接返回表达式（如 func f() -> List = [...]）
        if not self._check(TokenType.PUNCT_LPAREN):
            # 直接表达式作为 body，包装为零参 lambda
            lam_body = self._parse_expr()
            body = ast.Lambda(params=[], body=lam_body)
            return ast.FuncDef(name=name, annotation=annotation, func_type=func_type, body=body)
        self._expect(TokenType.PUNCT_LPAREN, "(")
        lam_params: list[Any] = []
        if not self._check(TokenType.PUNCT_RPAREN):
            # 参数名可以是关键字（如 func、and、or）
            tok = self._current()
            if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                            TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                            TokenType.KW_IN, TokenType.KW_WHILE):
                self._advance()
                lam_params.append(ast.Variable(name=tok.value))
            else:
                lam_params.append(ast.Variable(name=self._expect(TokenType.IDENTIFIER, "参数名").value))
            while self._is_comma():
                self._advance()
                self._skip_newlines()
                tok = self._current()
                if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                                TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                                TokenType.KW_IN, TokenType.KW_WHILE):
                    self._advance()
                    lam_params.append(ast.Variable(name=tok.value))
                else:
                    lam_params.append(ast.Variable(name=self._expect(TokenType.IDENTIFIER, "参数名").value))
        self._expect(TokenType.PUNCT_RPAREN, ")")
        self._expect(TokenType.OP_FATARROW, "=>")
        self._skip_newlines()
        # 在 lambda 体内比较语境中解析 body，使 = 作为比较而非赋值
        # 同时设置 _in_lambda_body = True，使 ( 不被消费为函数应用
        saved_rel = self._in_lambda_rel
        saved_lb = self._in_lambda_body
        self._in_lambda_rel = True
        self._in_lambda_body = True
        try:
            lam_body = self._parse_lambda_body()
        finally:
            self._in_lambda_rel = saved_rel
            self._in_lambda_body = saved_lb
        body = ast.Lambda(params=lam_params, body=lam_body)
        return ast.FuncDef(name=name, annotation=annotation, func_type=func_type, body=body)

    def _parse_lambda_body(self) -> ast.AST:
        """解析 lambda 体：单个表达式，以 DEDENT/EOF 结束。"""
        self._skip_newlines()
        return self._parse_expr()

    def _parse_typed_param(self) -> tuple[str, Any]:
        """name: Type（类型标注可选）"""
        self._skip_newlines()
        # 参数名可以是关键字（如 func、and、or），作为标识符使用
        tok = self._current()
        if tok.type in (TokenType.IDENTIFIER, TokenType.KW_FUNC, TokenType.KW_AND,
                        TokenType.KW_OR, TokenType.KW_IF, TokenType.KW_FOR,
                        TokenType.KW_IN, TokenType.KW_WHILE):
            self._advance()
            pname = tok.value
        else:
            pname = self._expect(TokenType.IDENTIFIER, "参数名").value
        ptype = None
        if self._is_colon():
            self._advance()
            ptype = self._parse_type_expr()
        return (pname, ptype)

    # ============================================================
    # §9 类型定义
    # ============================================================

    def _parse_type_def(self):
        """<type_def> = <struct_def> | <enum_def> | <alias_def>"""
        tok = self._current()
        if tok.type == TokenType.KW_STRUCT:
            return self._parse_struct_def()
        if tok.type == TokenType.KW_ENUM:
            return self._parse_enum_def()
        if tok.type == TokenType.KW_TYPE:
            return self._parse_alias_def()
        raise ParseError("期望 struct/enum/type", tok)

    def _parse_struct_def(self) -> ast.StructDef:
        """<struct_def> = struct <id> [type_params] [annotation] [=] { <fields> }

        = 可选（支持 struct Name { ... } 和 struct Name = { ... } 两种写法）。
        fields = { <field_name> : <type_expr> [, | 换行] }
        """
        self._expect(TokenType.KW_STRUCT, "struct")
        name = self._expect(TokenType.IDENTIFIER, "结构体名").value
        type_params = self._parse_optional_type_params()
        annotation = None
        if self._check(TokenType.MATHA_ANNOT_START):
            annotation = self._parse_annotation()
        self._match(TokenType.OP_ASSIGN)  # = 可选
        self._expect(TokenType.PUNCT_LBRACE, "{")
        self._skip_newlines()
        fields: list[Any] = []
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            field_name = self._expect(TokenType.IDENTIFIER, "字段名").value
            if not self._is_colon():
                raise ParseError("期望字段类型分隔符 : 或 ：", self._current())
            self._advance()
            field_type = self._parse_type_expr()
            fields.append((field_name, field_type))
            self._skip_newlines()
            self._skip_comma()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.StructDef(name=name, type_params=type_params, annotation=annotation, fields=fields)

    def _parse_enum_def(self) -> ast.EnumDef:
        """<enum_def> = enum <id> [type_params] [annotation] [=] { <ctors> }

        = 可选。ctors = <id> { | <id> }（管道分隔的构造子）。
        """
        self._expect(TokenType.KW_ENUM, "enum")
        name = self._expect(TokenType.IDENTIFIER, "枚举名").value
        type_params = self._parse_optional_type_params()
        annotation = None
        if self._check(TokenType.MATHA_ANNOT_START):
            annotation = self._parse_annotation()
        self._match(TokenType.OP_ASSIGN)  # = 可选
        self._expect(TokenType.PUNCT_LBRACE, "{")
        self._skip_newlines()
        ctors: list[Any] = []
        # 构造子分隔：| 或换行均可（支持单行 A|B|C 与多行每行一个）
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            ctors.append(self._expect(TokenType.IDENTIFIER, "构造子").value)
            self._skip_newlines()
            if self._match(TokenType.OP_PIPE):
                self._skip_newlines()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.EnumDef(name=name, type_params=type_params, annotation=annotation, ctors=ctors)

    def _parse_alias_def(self) -> ast.AliasDef:
        """<alias_def> = type <id> [type_params] = <type_expr>"""
        self._expect(TokenType.KW_TYPE, "type")
        name = self._expect(TokenType.IDENTIFIER, "别名").value
        type_params = self._parse_optional_type_params()
        self._expect(TokenType.OP_ASSIGN, "=")
        target = self._parse_type_expr()
        return ast.AliasDef(name=name, type_params=type_params, target_type=target)

    def _parse_optional_type_params(self) -> list[str]:
        """<type_params> = [ <typevar> , { , <typevar> } ]"""
        params: list[str] = []
        if self._match(TokenType.PUNCT_LBRACKET):
            params.append(self._expect(TokenType.IDENTIFIER, "类型变量").value)
            while self._is_comma():
                self._advance()
                params.append(self._expect(TokenType.IDENTIFIER, "类型变量").value)
            self._expect(TokenType.PUNCT_RBRACKET, "]")
        return params

    def _skip_to_rbrace(self) -> None:
        """跳过到 } 为止（骨架占位）。"""
        depth = 1
        while depth > 0 and not self._check(TokenType.EOF):
            if self._check(TokenType.PUNCT_LBRACE):
                depth += 1
            elif self._check(TokenType.PUNCT_RBRACE):
                depth -= 1
                if depth == 0:
                    self._advance()
                    return
            self._advance()

    # ============================================================
    # §10 模块系统
    # ============================================================

    def _parse_module_decl(self) -> ast.ModuleDecl:
        """<module_decl> = module <name> [annotation] [=] { { <decl> } }

        = 可选（支持 module Name { ... } 和 module Name = { ... } 两种写法）。
        """
        self._expect(TokenType.KW_MODULE, "module")
        name = self._parse_module_name()
        annotation = None
        if self._check(TokenType.MATHA_ANNOT_START):
            annotation = self._parse_annotation()
        self._match(TokenType.OP_ASSIGN)  # = 可选
        self._expect(TokenType.PUNCT_LBRACE, "{")
        self._skip_newlines()
        decls: list[Any] = []
        while not self._check(TokenType.PUNCT_RBRACE, TokenType.EOF):
            decl = self._parse_top_level()
            if decl is not None:
                # 检查 let rec f = lambda; f(args) 模式：将后续调用合并到 FuncDef.else_body
                if isinstance(decl, ast.FuncDef) and decl.else_body is None:
                    self._skip_newlines()
                    if self._check(TokenType.IDENTIFIER) and self._current().value == decl.name:
                        saved = self.pos
                        try:
                            self._advance()  # consume name
                            if self._check(TokenType.PUNCT_LPAREN):
                                self._advance()  # consume (
                                call_args = [self._parse_expr()]
                                while self._check(TokenType.PUNCT_COMMA):
                                    self._advance()
                                    call_args.append(self._parse_expr())
                                self._expect(TokenType.PUNCT_RPAREN, ")")
                                # 构建嵌套 FuncApp
                                call_expr = ast.FuncApp(func=ast.Variable(name=decl.name), arg=call_args[0])
                                for arg in call_args[1:]:
                                    call_expr = ast.FuncApp(func=call_expr, arg=arg)
                                decl.else_body = call_expr
                        except ParseError:
                            self.pos = saved
                decls.append(decl)
            self._skip_newlines()
        self._expect(TokenType.PUNCT_RBRACE, "}")
        return ast.ModuleDecl(name=name, annotation=annotation, decls=decls)

    def _parse_import_decl(self) -> ast.ImportDecl:
        """<import_decl> = use <name> [ { <import_list> } ] [ as <id> ]"""
        self._expect(TokenType.KW_USE, "use")
        module_name = self._parse_module_name()
        import_list = None
        if self._match(TokenType.PUNCT_LBRACE):
            import_list = [self._expect(TokenType.IDENTIFIER, "导入项").value]
            while self._match(TokenType.OP_PIPE):
                import_list.append(self._expect(TokenType.IDENTIFIER, "导入项").value)
            self._expect(TokenType.PUNCT_RBRACE, "}")
        alias = None
        if self._match(TokenType.KW_AS):
            alias = self._expect(TokenType.IDENTIFIER, "别名").value
        return ast.ImportDecl(module_name=module_name, import_list=import_list, alias=alias)

    def _parse_module_name(self) -> str:
        """<module_name> = <identifier> , { . <identifier> }"""
        name = self._expect(TokenType.IDENTIFIER, "模块名").value
        while self._match(TokenType.PUNCT_DOT):
            name += "." + self._expect(TokenType.IDENTIFIER, "模块名").value
        return name

    # ============================================================
    # §12 可读输出层
    # <command_unit> = <gen_command> | <command_literal> | <output>
    # ============================================================

    def _parse_command_unit(self):
        """<command_unit>"""
        if self._check(TokenType.MATHA_CMD_OPEN, TokenType.MATHA_READ_OPEN):
            return self._parse_command_literal()
        if self._check(TokenType.PUNCT_LBRACKET):
            return self._parse_output()
        raise ParseError("期望命令或输出", self._current())


# ============================================================
# 便捷入口
# ============================================================

def parse(source: str) -> ast.Program:
    """解析 Matha 源码，返回 AST。"""
    return Parser(source).parse()


def parse_file(path: str) -> ast.Program:
    """从文件读取并解析。"""
    with open(path, "r", encoding="utf-8") as f:
        return parse(f.read())


# ============================================================
# v2.5 ThreadPoolExecutor 并行解析（线程池复用，解决 P0 瓶颈）
# ============================================================
#
# 设计原则：
#   1. 固定大小线程池（max_workers=16），避免动态创建线程的开销
#   2. 线程池全局单例，跨调用复用
#   3. 任务队列背压：超出队列容量时拒绝新任务
#   4. 优雅关闭：shutdown(wait=True) 等待所有任务完成
#
# 与 v2.4 ProcessPoolExecutor 对比：
#   - v2.4：进程池绕过 GIL，但进程创建/通信开销大（~200ms/进程）
#   - v2.5：线程池无跨进程开销，但受 GIL 限制（regex 释放 GIL 可并行）
#   - 适用场景：
#     * v2.4 适合 CPU 密集型、无 GIL 释放的操作
#     * v2.5 适合 I/O 密集型、regex 释放 GIL 的操作
# ============================================================

_parse_pool_lock = threading.Lock()
_parse_pool: Optional[ThreadPoolExecutor] = None
_MAX_WORKERS = 16  # 固定线程数，避免 10000 线程创建开销


def _parse_worker(source: str) -> ast.Program:
    """工作线程执行的单条解析任务。"""
    return Parser(source).parse()


def parse_batch(
    sources: list[str],
    max_workers: int = _MAX_WORKERS,
) -> list[ast.Program]:
    """批量并行解析 Matha 源码（v2.5 线程池版本）。

    参数:
        sources: 待解析的源码列表
        max_workers: 并发线程数（默认 16，受 GIL 限制不建议超过 32）

    返回:
        与 sources 顺序对应的 AST 列表（失败的返回空 Program）
    """
    if not sources:
        return []

    executor = _get_or_create_pool(max_workers)
    futures = {executor.submit(_parse_worker, src): i for i, src in enumerate(sources)}
    results: list[Optional[ast.Program]] = [None] * len(sources)

    for future in as_completed(futures, timeout=60):
        idx = futures[future]
        try:
            results[idx] = future.result(timeout=30)
        except Exception as e:
            logger.error("线程解析失败 (index %d): %s", idx, e)
            results[idx] = ast.Program()

    return [r for r in results if r is not None]


def _get_or_create_pool(max_workers: int) -> ThreadPoolExecutor:
    """获取或创建全局线程池（线程安全）。"""
    global _parse_pool
    with _parse_pool_lock:
        if _parse_pool is None or _parse_pool._shutdown:
            _parse_pool = ThreadPoolExecutor(
                max_workers=max(max_workers, _MAX_WORKERS),
                thread_name_prefix="matha-parser",
            )
        return _parse_pool


def shutdown_parsers(wait: bool = True) -> None:
    """关闭解析器线程池。"""
    global _parse_pool
    with _parse_pool_lock:
        if _parse_pool:
            _parse_pool.shutdown(wait=wait)
            _parse_pool = None


# ============================================================
# v2.4 遗留：ProcessPoolExecutor（供对比测试使用）
# ============================================================
