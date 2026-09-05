import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in
        let c2 = get(src)(pos + 1) in'''

p = Parser(code)
tokens = p.tokens

# Simulate _parse_rel_expr at pos 25
print(f"Token 25: {tokens[25].type.name} = {tokens[25].value!r}")
print(f"Token 26: {tokens[26].type.name} = {tokens[26].value!r}")
print(f"Token 27: {tokens[27].type.name} = {tokens[27].value!r}")

# Test _is_stmt_separator at pos 25
p2 = Parser(code)
for _ in range(25):
    p2._advance()
print(f"\nAt pos 25: {p2._current().type.name} = {p2._current().value!r}")
print(f"_is_stmt_separator at pos 25: {p2._is_stmt_separator()}")

# Simulate the fix
saved = p2.pos
p2._advance()  # consume 'in'
print(f"After consuming 'in': pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
p2._skip_newlines()
print(f"After _skip_newlines: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
print(f"_is_stmt_separator after in: {p2._is_stmt_separator()}")
