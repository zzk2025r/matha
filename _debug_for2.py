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
# Manually trace _parse_for
from src.tokens import TokenType
tokens = p.tokens
for i, t in enumerate(tokens):
    if t.value == 'for':
        print(f"Token {i}: {t.type.name} = {t.value!r} at L{t.line}:{t.col}")
        if i+1 < len(tokens):
            print(f"  Next: {tokens[i+1].type.name} = {tokens[i+1].value!r} at L{tokens[i+1].line}:{tokens[i+1].col}")
        if i+2 < len(tokens):
            print(f"  Next+1: {tokens[i+2].type.name} = {tokens[i+2].value!r} at L{tokens[i+2].line}:{tokens[i+2].col}")

# Now try to parse
try:
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    # Find where we are
    print(f"Current token at error: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
