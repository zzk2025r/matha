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

orig_primary = parser_mod.Parser._parse_primary

def traced_primary(self):
    tok = self._current()
    print(f"  _parse_primary ENTER: pos={self.pos}, tok={tok.type.name}={tok.value!r}")
    result = orig_primary(self)
    print(f"  _parse_primary RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_primary = traced_primary

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
