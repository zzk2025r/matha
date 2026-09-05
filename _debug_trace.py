import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Trace parsing of '2 in [1, 2, 3]'
code = 'v = 2 in [1, 2, 3]'
p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r}")

# Now manually trace what _parse_expr does
print("\n--- Manual trace ---")
p2 = Parser(code)
# Simulate: v = 2 in [1, 2, 3]
# First, parse 'v' as variable
p2._expect(TokenType.IDENTIFIER, "变量名")
print(f"After 'v': pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
# Then parse '='
p2._expect(TokenType.OP_ASSIGN, "=")
print(f"After '=': pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
# Now parse expr starting from '2'
print(f"Parsing expr from pos={p2.pos}")
expr = p2._parse_expr()
print(f"Expr parsed: {type(expr).__name__}")
print(f"After expr: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
# What's left?
for i in range(p2.pos, min(p2.pos+5, len(tokens))):
    print(f"  Remaining {i}: {tokens[i].type.name} = {tokens[i].value!r}")
