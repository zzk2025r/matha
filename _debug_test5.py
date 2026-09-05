from src.parser import parse
from src.ast_nodes import FuncApp, Binding

# Test with parentheses
src1 = "v = 加(10, 20)"
prog1 = parse(src1)
print('Test 1 (with parens):')
for decl in prog1.decls:
    print(f'  {type(decl).__name__}: {decl}')

# Test without parentheses
src2 = "v = 加 10 20"
prog2 = parse(src2)
print('\nTest 2 (no parens):')
for decl in prog2.decls:
    print(f'  {type(decl).__name__}: {decl}')
    if hasattr(decl, 'value'):
        print(f'    value: {type(decl.value).__name__}')
        if isinstance(decl.value, FuncApp):
            print(f'    func: {type(decl.value.func).__name__}: {decl.value.func}')
            print(f'    arg: {type(decl.value.arg).__name__}: {decl.value.arg}')

# Test bare function call
src3 = "加 10 20"
prog3 = parse(src3)
print('\nTest 3 (bare call):')
for decl in prog3.decls:
    print(f'  {type(decl).__name__}: {decl}')
