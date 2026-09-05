import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''let s2 = get(src)(pos + 1) in
let c1 = get(src)(pos) in'''

import src.parser as parser_mod

orig_parse_rel_expr = parser_mod.Parser._parse_rel_expr

def traced_parse_rel_expr(self):
    from src import ast_nodes as ast
    print(f"  [rel] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    left = self._parse_add_expr()
    print(f"  [rel] after add_expr: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")

    # Check operators...
    if self._check(TokenType.OP_LT, TokenType.OP_GT, TokenType.OP_LE, TokenType.OP_GE):
        op = self._advance().value
        right = self._parse_add_expr()
        return ast.BinaryOp(op=op, left=left, right=right)
    if self._check(TokenType.OP_STRICT_EQ):
        self._advance()
        right = self._parse_add_expr()
        return ast.BinaryOp(op="===", left=left, right=right)
    if self._check(TokenType.OP_STRICT_NEQ):
        self._advance()
        right = self._parse_add_expr()
        return ast.BinaryOp(op="!==", left=left, right=right)
    if self._check(TokenType.OP_ASSIGN, TokenType.OP_NEQ):
        op = self._advance().value
        if op == "=" and self._check(TokenType.OP_ASSIGN):
            self._advance()
            op = "=="
        if self._in_lambda_rel:
            right = self._parse_add_expr()
        else:
            right = self._parse_expr()
        return ast.BinaryOp(op=op, left=left, right=right)
    if self._check(TokenType.OP_ARROW_FW):
        self._advance()
        right = self._parse_add_expr()
        return ast.BinaryOp(op="→", left=left, right=right)
    if self._check(TokenType.KW_IS):
        self._advance()
        right = self._parse_add_expr()
        return ast.IsExpr(left=left, right=right)

    # Python in 成员判断
    if self._check(TokenType.KW_IN):
        saved = self.pos
        self._advance()
        self._skip_newlines()
        _after_in = self._current().type
        print(f"  [rel] after in: pos={self.pos}, tok={_after_in.name}={self._current().value!r}")
        _is_stmt_keyword = _after_in in (
            TokenType.KW_LET, TokenType.KW_FUNC, TokenType.KW_BREAK,
            TokenType.KW_CONTINUE, TokenType.KW_RETURN, TokenType.KW_IF,
            TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_MATCH,
            TokenType.KW_SWITCH, TokenType.KW_TRY, TokenType.KW_CATCH,
        )
        is_sep = self._is_stmt_separator()
        print(f"  [rel] is_sep={is_sep}, is_stmt_keyword={_is_stmt_keyword}")
        if is_sep or _is_stmt_keyword:
            self.pos = saved
            print(f"  [rel] backtracked to pos={self.pos}")
        else:
            right = self._parse_add_expr()
            print(f"  [rel] parsed as binary op, right at pos={self.pos}")
            return ast.BinaryOp(op=" in ", left=left, right=right)

    # 属于判断 ∈
    if self._check(TokenType.SYMBOL) and self._current().value == "∈":
        self._advance()
        right = self._parse_add_expr()
        return ast.Belongs(left=left, right=right)

    print(f"  [rel] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return left

parser_mod.Parser._parse_rel_expr = traced_parse_rel_expr

try:
    p = Parser(code)
    ast = p.parse()
    print(f"\nParse OK, {len(ast.decls)} decls")
except Exception as e:
    print(f"Parse ERROR: {e}")
