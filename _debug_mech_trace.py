import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

import src.parser as parser_mod

orig_mech_stmt = parser_mod.Parser._parse_mech_stmt

call_count = [0]
def traced_mech_stmt(self):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[MS{cid}] ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_mech_stmt(self)
    print(f"[MS{cid}] RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__ if result else None}")
    return result

parser_mod.Parser._parse_mech_stmt = traced_mech_stmt

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
