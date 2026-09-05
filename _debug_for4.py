import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser

code = '''#：{
  result = 0
  items = [(1, "a"), (2, "b"), (3, "c")]
  for (a, b) in items {
    result = result + a
  }
  #：[result]
}'''

# Add some debug to _parse_for
import src.parser as parser_mod
original_parse_for = parser_mod.Parser._parse_for

def debug_parse_for(self):
    from src.tokens import TokenType
    print(f"DEBUG _parse_for: current token = {self._current().type.name} = {self._current().value!r}")
    print(f"DEBUG _parse_for: pos = {self.pos}")
    result = original_parse_for(self)
    print(f"DEBUG _parse_for: returned {type(result).__name__}")
    return result

parser_mod.Parser._parse_for = debug_parse_for

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
