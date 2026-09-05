import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

# Test the ternary with let
code = '''(1 < 2) ?
  let a = 1 in
  let b = 2 in
  a + b'''

try:
    ast = parse(code)
    print(f"Parse OK: {len(ast.decls)} decls")
    for i, d in enumerate(ast.decls):
        print(f"  [{i}] {type(d).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")
