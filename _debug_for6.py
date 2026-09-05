import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''#：{
  result = 0
  items = [(1, "a"), (2, "b"), (3, "c")]
  for (a, b) in items {
    result = result + a
  }
  #：[result]
}'''

# Monkey-patch with detailed tracing
import src.parser as parser_mod
original_parse_for = parser_mod.Parser._parse_for

def traced_parse_for(self):
    print(f"TRACE _parse_for ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, in_cf={self._in_control_flow}")
    self._expect(TokenType.KW_FOR, "for")
    saved = self.pos
    print(f"TRACE after 'for': pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    print(f"TRACE _check LPAREN: {self._check(TokenType.PUNCT_LPAREN)}")
    if self._check(TokenType.PUNCT_LPAREN):
        print("TRACE: entering tuple destructuring branch")
    else:
        print("TRACE: NOT entering tuple branch, falling through")
    result = original_parse_for(self)
    print(f"TRACE _parse_for RETURN: {type(result).__name__}")
    return result

parser_mod.Parser._parse_for = traced_parse_for

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token at error: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
