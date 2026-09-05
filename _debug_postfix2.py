import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'

import src.parser as parser_mod

# Patch _parse_postfix more carefully
call_count = [0]
orig_postfix = parser_mod.Parser._parse_postfix

def traced_postfix(self):
    call_count[0] += 1
    cid = call_count[0]
    print(f"[{cid}] _parse_postfix ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_postfix(self)
    print(f"[{cid}] _parse_postfix RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_postfix = traced_postfix

# Also patch _parse_primary
prim_count = [0]
orig_primary = parser_mod.Parser._parse_primary

def traced_primary(self):
    prim_count[0] += 1
    cid = prim_count[0]
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
