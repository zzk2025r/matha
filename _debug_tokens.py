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
for i, t in enumerate(tokens):
    if 30 <= i <= 40:
        print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")

# Now test _check_after_skip manually
print("\n--- Manual test ---")
p2 = Parser(code)
# Skip to token 36 (the RPAREN after b)
for _ in range(36):
    p2._advance()
print(f"At pos 36: {p2._current().type.name} = {p2._current().value!r}")
print(f"_check RPAREN: {p2._check(TokenType.PUNCT_RPAREN)}")
print(f"_check_after_skip KW_IN: {p2._check_after_skip(TokenType.KW_IN)}")
print(f"After _check_after_skip, pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
