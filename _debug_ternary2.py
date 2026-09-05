import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Test 1: ternary with let
code1 = '''(1 < 2) ?
  let a = 1 in
  let b = 2 in
  a + b'''

print("=== Test 1: ternary with let ===")
try:
    ast = Parser(code1).parse()
    print(f"Parse OK: {len(ast.decls)} decls")
except Exception as e:
    print(f"Parse ERROR: {e}")

# Test 2: simple in operator
code2 = '''2 in [1, 2, 3]'''
print("\n=== Test 2: simple in operator ===")
try:
    ast = Parser(code2).parse()
    print(f"Parse OK: {len(ast.decls)} decls")
    for d in ast.decls:
        print(f"  {type(d).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")

# Test 3: let with in body
code3 = '''let x = 1 in
2'''
print("\n=== Test 3: let with in body ===")
try:
    ast = Parser(code3).parse()
    print(f"Parse OK: {len(ast.decls)} decls")
    for d in ast.decls:
        print(f"  {type(d).__name__}")
        if hasattr(d, 'body'):
            print(f"    body={type(d.body).__name__ if d.body else None}")
except Exception as e:
    print(f"Parse ERROR: {e}")
