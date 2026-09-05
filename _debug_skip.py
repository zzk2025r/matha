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

p = Parser(code)
tokens = p.tokens

# Test _check_after_skip behavior
for start_pos in [35, 36, 37]:
    p2 = Parser(code)
    for _ in range(start_pos):
        p2._advance()
    print(f"\nStart pos={start_pos}: tok={p2._current().type.name}={p2._current().value!r}")
    p2._skip_newlines()
    print(f"After _skip_newlines: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
    result = p2._check_after_skip(TokenType.KW_IN)
    print(f"_check_after_skip KW_IN: {result}")
    print(f"After _check_after_skip: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
