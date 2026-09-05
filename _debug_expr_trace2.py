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

call_count = [0]
def traced_expr(self, *args, **kwargs):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[E{cid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_parse_expr(self, *args, **kwargs)
    print(f"[E{cid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_expr

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
    for d in ast_tree.decls:
        if hasattr(d, 'body') and hasattr(d.body, 'stmts'):
            for j, s in enumerate(d.body.stmts):
                print(f"  stmt[{j}]: {type(s).__name__}")
                if hasattr(s, 'name'):
                    print(f"    name={s.name}")
                if hasattr(s, 'value'):
                    print(f"    value={type(s.value).__name__}")
                if hasattr(s, 'body'):
                    print(f"    body={type(s.body).__name__ if s.body else None}")
except Exception as e:
    print(f"\nParse ERROR: {e}")
