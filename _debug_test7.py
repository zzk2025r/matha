from src.parser import parse
from src.ast_nodes import FuncApp, Binding, BinaryOp, Lambda

# Test: with parens
src1 = "v = 加(10, 20)"
try:
    prog1 = parse(src1)
    print('Test 1 OK:', [(type(d).__name__, getattr(d, 'value', None)) for d in prog1.decls])
except Exception as e:
    print('Test 1 FAIL:', e)
    import traceback
    traceback.print_exc()

# Test: simple binary op
src2 = "v = 10 + 20"
try:
    prog2 = parse(src2)
    print('Test 2 OK:', [(type(d).__name__, getattr(d, 'value', None)) for d in prog2.decls])
except Exception as e:
    print('Test 2 FAIL:', e)

# Test: function call
src3 = "加(10, 20)"
try:
    prog3 = parse(src3)
    print('Test 3 OK:', [(type(d).__name__, getattr(d, 'func', None)) for d in prog3.decls])
except Exception as e:
    print('Test 3 FAIL:', e)
    import traceback
    traceback.print_exc()

# Test: simple var
src4 = "v = 加"
try:
    prog4 = parse(src4)
    print('Test 4 OK:', [(type(d).__name__, getattr(d, 'value', None)) for d in prog4.decls])
except Exception as e:
    print('Test 4 FAIL:', e)
