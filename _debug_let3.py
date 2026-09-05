import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in
        let c2 = get(src)(pos + 1) in'''

import src.parser as parser_mod

orig_parse_let = parser_mod.Parser._parse_let

def traced_parse_let(self):
    from src import ast_nodes as ast
    print(f"TRACE _parse_let ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    self._expect(TokenType.IDENTIFIER, "let")
    is_rec = False
    name = self._expect(TokenType.IDENTIFIER, "绑定名").value
    self._expect(TokenType.OP_ASSIGN, "=")
    print(f"TRACE _parse_let after '=': pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    value = self._parse_expr()
    print(f"TRACE _parse_let after value: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    body = None
    if self._check(TokenType.KW_IN):
        self._advance()
        print(f"TRACE _parse_let after 'in': pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
        body = self._parse_expr()
        print(f"TRACE _parse_let after body: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = ast.LetBinding(name=name, value=value, is_recursive=is_rec, params=[], body=body)
    print(f"TRACE _parse_let RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_let = traced_parse_let

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
