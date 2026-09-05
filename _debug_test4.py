from src.parser import parse
from src.ast_nodes import FuncApp

# Test: Parse with parentheses
src1 = "v = 加(10, 20)"
prog1 = parse(src1)
print('Test 1 (with parens) AST:')
for decl in prog1.decls:
    print(f'  {type(decl).__name__}: {decl}')
    if hasattr(decl, 'value'):
        print(f'    value: {type(decl.value).__name__}: {decl.value}')

# Test: Parse without parentheses
src2 = "v = 加 10 20"
prog2 = parse(src2)
print('\nTest 2 (no parens) AST:')
for decl in prog2.decls:
    print(f'  {type(decl).__name__}: {decl}')
    if hasattr(decl, 'value'):
        print(f'    value: {type(decl.value).__name__}: {decl.value}')

# Test: Parse bare function call
src3 = "加 10 20"
prog3 = parse(src3)
print('\nTest 3 (bare call no parens) AST:')
for decl in prog3.decls:
    print(f'  {type(decl).__name__}: {decl}')
    if hasattr(decl, 'func'):
        print(f'    func: {type(decl.func).__name__}: {decl.func}')
        print(f'    arg: {type(decl.arg).__name__}: {decl.arg}')
