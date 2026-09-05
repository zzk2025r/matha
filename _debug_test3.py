from src.parser import parse
from src.ast_nodes import FuncApp

# Test 1: Simple function application
src1 = "v = 加 10 20"
prog1 = parse(src1)
print('Test 1 AST:')
for decl in prog1.decls:
    print(f'  {type(decl).__name__}: {decl}')
    if hasattr(decl, 'value'):
        print(f'    value: {type(decl.value).__name__}: {decl.value}')
        if hasattr(decl.value, 'func'):
            print(f'    func: {type(decl.value.func).__name__}: {decl.value.func}')
            print(f'    arg: {type(decl.value.arg).__name__}: {decl.value.arg}')

# Test 2: Check the 资源_加载 call
src2 = '资源_加载("core/arithmetic")(0)'
prog2 = parse(src2)
print('\nTest 2 AST:')
for decl in prog2.decls:
    print(f'  {type(decl).__name__}: {decl}')
