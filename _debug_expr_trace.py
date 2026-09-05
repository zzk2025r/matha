import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'

import src.parser as parser_mod

# Patch _parse_expr to trace
call_depth = [0]
orig_expr = parser_mod.Parser._parse_expr

def traced_expr(self, *args, **kwargs):
    call_depth[0] += 1
    d = call_depth[0]
    indent = "  " * d
    print(f"{indent}_parse_expr ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_expr(self, *args, **kwargs)
    print(f"{indent}_parse_expr RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    call_depth[0] -= 1
    return result

parser_mod.Parser._parse_expr = traced_expr

# Patch _parse_rel_expr
orig_rel = parser_mod.Parser._parse_rel_expr

def traced_rel(self):
    print(f"  _parse_rel_expr ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_rel(self)
    print(f"  _parse_rel_expr RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_rel_expr = traced_rel

try:
    p = Parser(code)
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
