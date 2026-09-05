import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'

import src.parser as parser_mod

# Trace _parse_postfix with full call stack
orig_postfix = parser_mod.Parser._parse_postfix

def traced_postfix(self):
    import traceback
    print(f"  _parse_postfix ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    for line in traceback.format_stack()[-6:-1]:
        print(f"    {line.strip()}")
    result = orig_postfix(self)
    print(f"  _parse_postfix RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_postfix = traced_postfix

try:
    p = Parser(code)
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
