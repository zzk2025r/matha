import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'

import src.parser as parser_mod

orig_primary = parser_mod.Parser._parse_primary

call_count = [0]
def traced_primary(self):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[P{cid}] _parse_primary ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_primary(self)
    print(f"[P{cid}] _parse_primary RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_primary = traced_primary

try:
    p = Parser(code)
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
