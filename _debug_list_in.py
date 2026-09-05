import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Test: parse [1, 2, 3] as expression
code = '[1, 2, 3]'
p = Parser(code)
print(f"Tokens: {[(t.type.name, t.value) for t in p.tokens]}")
try:
    ast = p.parse()
    print(f"Parse OK: {type(ast.decls[0]).__name__}")
    for d in ast.decls:
        print(f"  {type(d).__name__}")
        if hasattr(d, 'expr'):
            print(f"    expr={type(d.expr).__name__}")
        if hasattr(d, 'value'):
            print(f"    value={type(d.value).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")

# Test: parse 2 in [1, 2, 3]
print("\n--- Test 2 in [1, 2, 3] ---")
code2 = '2 in [1, 2, 3]'
p2 = Parser(code2)
print(f"Tokens: {[(t.type.name, t.value) for t in p2.tokens]}")
try:
    ast2 = p2.parse()
    print(f"Parse OK: {type(ast2.decls[0]).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token: pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")
