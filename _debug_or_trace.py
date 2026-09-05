import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in'''

import src.parser as parser_mod

# Patch _parse_or_expr to trace
orig_parse_or_expr = parser_mod.Parser._parse_or_expr

def traced_parse_or_expr(self):
    print(f"    TRACE _parse_or_expr ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_parse_or_expr(self)
    print(f"    TRACE _parse_or_expr RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_or_expr = traced_parse_or_expr

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
