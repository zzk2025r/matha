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

orig_let = parser_mod.Parser._parse_let

call_count = [0]
def traced_let(self, is_rec=False):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[LET{cid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_let(self, is_rec)
    print(f"[LET{cid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    if isinstance(result, ast.LetBinding):
        print(f"    name={result.name}, value={type(result.value).__name__}, body={type(result.body).__name__ if result.body else None}")
    return result

parser_mod.Parser._parse_let = traced_let

orig_parse_expr = parser_mod.Parser._parse_expr

expr_count = [0]
def traced_expr(self, *args, **kwargs):
    expr_count[0] += 1
    eid = expr_count[0]
    print(f"  [EXPR{eid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_parse_expr(self, *args, **kwargs)
    print(f"  [EXPR{eid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_expr

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
