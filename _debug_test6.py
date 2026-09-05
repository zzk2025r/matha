from src.parser import parse
from src.ast_nodes import FuncApp, Binding

# Test 1: with parens
try:
    src1 = "v = 加(10, 20)"
    prog1 = parse(src1)
    print('Test 1 OK:', [(type(d).__name__, getattr(d, 'value', None)) for d in prog1.decls])
except Exception as e:
    print('Test 1 FAIL:', e)

# Test 2: no parens
try:
    src2 = "v = 加 10 20"
    prog2 = parse(src2)
    print('Test 2 OK:', [(type(d).__name__, getattr(d, 'value', None)) for d in prog2.decls])
except Exception as e:
    print('Test 2 FAIL:', e)

# Test 3: bare call
try:
    src3 = "加 10 20"
    prog3 = parse(src3)
    print('Test 3 OK:', [(type(d).__name__, getattr(d, 'func', None)) for d in prog3.decls])
except Exception as e:
    print('Test 3 FAIL:', e)
