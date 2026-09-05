import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType
from src import ast_nodes as ast

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

import src.parser as parser_mod

orig_parse_expr = parser_mod.Parser._parse_expr
orig_parse_let = parser_mod.Parser._parse_let

call_count = [0]
def traced_expr(self, *args, **kwargs):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[E{cid}] _parse_expr ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_parse_expr(self, *args, **kwargs)
    print(f"[E{cid}] _parse_expr RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_expr

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
    print(f"Current: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
