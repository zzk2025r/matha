import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Trace lexer.matha ternary parsing
code = '''(pos + 1 < len(src)) ?
  let s2 = get(src)(pos + 1) in
  let c1 = get(src)(pos) in
  (c1 = ">" and c2 = "=") ? (不等于, "!=") :
  (c1 = ">" and c2 = ">") ? (大于等于, ">>") :
  "default"'''

import src.parser as parser_mod

orig_expr = parser_mod.Parser._parse_expr
orig_rel = parser_mod.Parser._parse_rel_expr

call_count = [0]
def traced_expr(self, *args, **kwargs):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[E{cid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_expr(self, *args, **kwargs)
    print(f"[E{cid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_expr

try:
    p = Parser(code)
    ast = p.parse()
    print(f"\nParse OK: {len(ast.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
    print(f"Current: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
