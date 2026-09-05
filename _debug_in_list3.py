import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = 'v = 2 in [1, 2, 3]'
p = Parser(code)
print("Tokens:")
for i, t in enumerate(p.tokens):
    print(f"  {i}: {t.type.name:20} = {t.value!r}")

# Add more detailed tracing
import src.parser as parser_mod

orig_list_literal = parser_mod.Parser._parse_list_literal

def traced_list_literal(self):
    print(f"  _parse_list_literal ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_list_literal(self)
    print(f"  _parse_list_literal RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_list_literal = traced_list_literal

orig_output = parser_mod.Parser._parse_output

def traced_output(self):
    print(f"  _parse_output ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_output(self)
    print(f"  _parse_output RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_output = traced_output

try:
    ast = p.parse()
    print(f"\nParse OK")
except Exception as e:
    print(f"\nParse ERROR: {e}")
