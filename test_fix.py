import sys
sys.path.insert(0, r'd:\trae')
from src.parser import parse

# Test 1: Parse discrete_math.matha
print("=== Test 1: discrete_math.matha ===")
with open(r'd:\trae\matha\resource\logic\discrete_math.matha', 'r', encoding='utf-8') as f:
    source = f.read()
program = parse(source)
print(f'Parse OK: {len(program.decls)} declarations')
for decl in program.decls:
    name = getattr(decl, 'name', '?')
    print(f'  - {type(decl).__name__}: {name}')
    if hasattr(decl, 'body') and decl.body:
        body = decl.body.body
        print(f'    body: {type(body).__name__}')
        if hasattr(body, 'elements'):
            print(f'    elements: {len(body.elements)}')
            for i, e in enumerate(body.elements):
                print(f'      [{i}] {type(e).__name__}', end='')
                if hasattr(e, 'elements'):
                    print(f' (tuple with {len(e.elements)} items)')
                else:
                    print()

# Test 2: Simple list with tuples
print("\n=== Test 2: Simple list with tuples ===")
source2 = '''
module Test {
  func 真值表_与() -> List =
    [(真, 真, 真), (真, 假, 假), (假, 真, 假), (假, 假, 假)]
}
'''
program2 = parse(source2)
print('Parse OK')
for decl in program2.decls:
    if hasattr(decl, 'body') and decl.body:
        body = decl.body.body
        print(f'  Lambda body: {type(body).__name__}')
        if hasattr(body, 'elements'):
            print(f'  List: {len(body.elements)} elements')
            for i, e in enumerate(body.elements):
                print(f'    [{i}] {type(e).__name__}', end='')
                if hasattr(e, 'elements'):
                    print(f' (tuple {len(e.elements)} items)')
                else:
                    print()

# Test 3: Output with 全角 comma should still work
print("\n=== Test 3: Output with 全角 comma ===")
source3 = '#：[你好，世界]'
program3 = parse(source3)
print(f'Parse OK: {len(program3.decls)} declarations')
for decl in program3.decls:
    print(f'  {type(decl).__name__}')

# Test 4: Empty list
print("\n=== Test 4: Empty list ===")
source4 = '''
module Test {
  func empty() -> List = []
}
'''
program4 = parse(source4)
print('Parse OK')

# Test 5: Simple list (no tuples)
print("\n=== Test 5: Simple list ===")
source5 = '''
module Test {
  func nums() -> List = [1, 2, 3]
}
'''
program5 = parse(source5)
print('Parse OK')
for decl in program5.decls:
    if hasattr(decl, 'body') and decl.body:
        body = decl.body.body
        print(f'  body: {type(body).__name__}')
        if hasattr(body, 'elements'):
            print(f'  list: {len(body.elements)} elements')

print("\nAll tests passed!")
