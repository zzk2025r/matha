import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '2 in [1, 2, 3]'
p = Parser(code)
print("Tokens:")
for i, t in enumerate(p.tokens):
    print(f"  {i}: {t.type.name:20} = {t.value!r}")

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
    print(f"\nParse OK: {type(ast.decls[0]).__name__}")
except Exception as e:
    print(f"\nParse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
    for i in range(max(0, p.pos-3), min(len(p.tokens), p.pos+5)):
        print(f"  Token {i}: {p.tokens[i].type.name} = {p.tokens[i].value!r}")
