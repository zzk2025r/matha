import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''let toks = 扫描("x + 1") in
[1]'''

p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")

# Test: what does _parse_expr do with [1] after in?
print("\n--- Testing [1] as expr ---")
p2 = Parser("[1]")
try:
    ast = p2.parse()
    print(f"Parse OK: {type(ast.decls[0]).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")
