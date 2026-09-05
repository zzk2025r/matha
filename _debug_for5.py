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

# Manually trace _parse_for
# Simulate being at token 31 (for)
p.pos = 31
print(f"Token 31: {tokens[31].type.name} = {tokens[31].value!r}")

# Now step through _parse_for logic
print(f"Current before _expect: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
p._expect(TokenType.KW_FOR, "for")
saved = p.pos
print(f"After consuming 'for': pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
print(f"Is LPAREN check: {p._check(TokenType.PUNCT_LPAREN)}")

# Now try the full parse
print("\n--- Full parse ---")
p2 = Parser(code)
try:
    ast = p2.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token at error: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
