import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3] ; #：[v]'
p = Parser(code)
print("Tokens:")
for i, t in enumerate(p.tokens):
    print(f"  {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")

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
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
