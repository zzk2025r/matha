import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'
p = Parser(code)

import src.parser as parser_mod

orig_postfix = parser_mod.Parser._parse_postfix

def traced_postfix(self):
    print(f"  _parse_postfix ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_postfix(self)
    print(f"  _parse_postfix RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_postfix = traced_postfix

orig_primary = parser_mod.Parser._parse_primary

def traced_primary(self):
    print(f"  _parse_primary ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_primary(self)
    print(f"  _parse_primary RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_primary = traced_primary

try:
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
