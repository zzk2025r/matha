import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

# Test: parse '2 in [1, 2, 3]' alone
code = '2 in [1, 2, 3]'
ast = parse(code)
print(f"Parsed as {len(ast.decls)} decls:")
for i, d in enumerate(ast.decls):
    print(f"  [{i}] {type(d).__name__}")
    if hasattr(d, 'target'):
        print(f"      target={d.target}")
    if hasattr(d, 'value'):
        print(f"      value={type(d.value).__name__}")
    if hasattr(d, 'name'):
        print(f"      name={d.name}")
    if hasattr(d, 'expr'):
        print(f"      expr={type(d.expr).__name__}")

# Also test: parse 'v = 2 in [1, 2, 3]'
print("\n--- v = 2 in [1, 2, 3] ---")
code2 = 'v = 2 in [1, 2, 3]'
ast2 = parse(code2)
print(f"Parsed as {len(ast2.decls)} decls:")
for i, d in enumerate(ast2.decls):
    print(f"  [{i}] {type(d).__name__}")
    if hasattr(d, 'target'):
        print(f"      target={d.target.name if hasattr(d.target, 'name') else d.target}")
    if hasattr(d, 'value'):
        print(f"      value={type(d.value).__name__}")
        if hasattr(d.value, 'op'):
            print(f"        op={d.value.op}")
            print(f"        left={type(d.value.left).__name__}")
            print(f"        right={type(d.value.right).__name__}")
    if hasattr(d, 'name'):
        print(f"      name={d.name}")
    if hasattr(d, 'expr'):
        print(f"      expr={type(d.expr).__name__}")
