import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

s = 'opt = ["Some", 42]'
ast = parse(s)
print("Decls:")
for d in ast.decls:
    print(f"  {type(d).__name__}: {d}")
    if hasattr(d, 'value'):
        print(f"    value type: {type(d.value).__name__}")
        if hasattr(d.value, 'elements'):
            print(f"    elements: {d.value.elements}")
