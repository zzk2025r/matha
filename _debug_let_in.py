import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType
from src import ast_nodes as ast

code = 'let x = 1 in 2'

import src.parser as parser_mod

orig_parse_let = parser_mod.Parser._parse_let

def traced_parse_let(self):
    print(f"_parse_let ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    # Manually trace
    self._expect(TokenType.IDENTIFIER, "let")
    is_rec = False
    name = self._expect(TokenType.IDENTIFIER, "绑定名").value
    print(f"  after name: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    self._expect(TokenType.OP_ASSIGN, "=")
    print(f"  after =: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    value = self._parse_expr()
    print(f"  after value: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, value={type(value).__name__}")
    body = None
    if self._check(TokenType.KW_IN):
        print(f"  found in at pos={self.pos}")
        saved = self.pos
        self._advance()
        self._skip_newlines()
        _after_in = self._current()
        print(f"  after in: pos={self.pos}, tok={_after_in.type.name}={_after_in.value!r}")
        _is_sep = self._is_stmt_separator()
        print(f"  _is_stmt_separator={_is_sep}")
        _is_stmt_keyword = _after_in.type in (
            TokenType.KW_FUNC, TokenType.KW_BREAK,
            TokenType.KW_CONTINUE, TokenType.KW_RETURN, TokenType.KW_IF,
            TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_MATCH,
            TokenType.KW_SWITCH, TokenType.KW_TRY, TokenType.KW_CATCH,
        ) or (_after_in.type == TokenType.IDENTIFIER and _after_in.value in ("let", "rec"))
        print(f"  _is_stmt_keyword={_is_stmt_keyword}")
        _is_line_end = _after_in.type in (TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF)
        print(f"  _is_line_end={_is_line_end}")
        if _is_sep or _is_stmt_keyword or _is_line_end:
            print(f"  -> treating as let keyword, backtracking to pos={saved}")
            self.pos = saved
        else:
            print(f"  -> treating as binary operator, parsing body")
            body = self._parse_expr()
            print(f"  after body: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    print(f"_parse_let RETURN: pos={self.pos}, body={type(body).__name__ if body else None}")
    return ast.LetBinding(name=name, value=value, is_recursive=is_rec, params=[], body=body)

parser_mod.Parser._parse_let = traced_parse_let

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
