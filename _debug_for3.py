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

p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name} = {t.value!r} at L{t.line}:{t.col}")

print("\n--- Tracing _parse_for ---")
from src.tokens import TokenType
# Find 'for'
for i, t in enumerate(tokens):
    if t.value == 'for':
        print(f"Found 'for' at token {i}")
        # Simulate what _parse_for does
        print(f"Current token after 'for': {tokens[i+1].type.name} = {tokens[i+1].value!r}")
        # Check if it's LPAREN
        print(f"Is LPAREN? {tokens[i+1].type == TokenType.PUNCT_LPAREN}")
        break
