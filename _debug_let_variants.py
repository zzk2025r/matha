import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

# Test various let + output combinations
tests = [
    'let x = 1 in [2]',
    'let x = 1 in\n[2]',
    'let x = 1 in 2',
    'let x = f() in\n[1]',
]

for code in tests:
    print(f"\nCode: {code!r}")
    try:
        ast = parse(code)
        print(f"  OK: {len(ast.decls)} decls")
        for d in ast.decls:
            print(f"    {type(d).__name__}: name={getattr(d, 'name', None)}, value={type(getattr(d, 'value', None)).__name__}, body={type(getattr(d, 'body', None)).__name__ if getattr(d, 'body', None) else None}")
    except Exception as e:
        print(f"  ERROR: {e}")
