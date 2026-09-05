import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Debug: trace parsing with more detail
code = '''      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in'''

p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")

# Now trace the specific issue
print("\n--- Tracing after 'get(src)(pos + 1)' ---")
# After parsing get(src)(pos+1), we should be at token 25 (in)
# Let's manually check
p2 = Parser(code)
# Skip to after get(src)(pos+1) - that's token 25
for _ in range(25):
    p2._advance()
print(f"At pos 25: {p2._current().type.name} = {p2._current().value!r}")
print(f"Next (pos 26): {p2.tokens[26].type.name} = {p2.tokens[26].value!r}")

# Check _is_stmt_separator
print(f"_is_stmt_separator at pos 25: {p2._is_stmt_separator()}")
# But we need to check AFTER consuming 'in'
p2._advance()  # consume 'in'
print(f"After consuming 'in', pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
print(f"_is_stmt_separator after 'in': {p2._is_stmt_separator()}")
