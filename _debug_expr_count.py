import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType
from src import ast_nodes as ast

code = 'let x = 1 in 2'

import src.parser as parser_mod

orig_expr = parser_mod.Parser._parse_expr
expr_count = [0]

def traced_expr(self, *args, **kwargs):
    expr_count[0] += 1
    eid = expr_count[0]
    print(f"[E{eid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_expr(self, *args, **kwargs)
    print(f"[E{eid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_expr

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
    for d in ast_tree.decls:
        print(f"  {type(d).__name__}: name={getattr(d, 'name', None)}, body={type(d.body).__name__ if hasattr(d, 'body') and d.body else None}")
except Exception as e:
    print(f"\nParse ERROR: {e}")
