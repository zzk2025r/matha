"""Test multi-line function parameter lists."""
import sys
sys.path.insert(0, 'src')
from src.parser import parse

# Test 1: multi-line func def with typed params
code1 = """func add(a: Int,
         b: Int) -> Int = (a,
         b) => a + b"""

# Test 2: multi-line let rec func def
code2 = """let rec multiply(x: Int,
                  y: Int) -> Int = (x,
                  y) => x * y"""

# Test 3: multi-line lambda
code3 = """(a,
 b) => a + b"""

# Test 4: multi-line lambda with types
code4 = """(a: Int,
 b: Int) => a + b"""

tests = [
    ("func def multi-line params", code1),
    ("let rec multi-line params", code2),
    ("lambda multi-line params", code3),
    ("lambda multi-line with types", code4),
]

passed = 0
failed = 0
for name, code in tests:
    try:
        result = parse(code)
        print(f"  PASS: {name}")
        print(f"        {code[:60].replace(chr(10), ' ')}...")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"        Error: {e}")
        print(f"        Code: {repr(code)}")
        failed += 1

print(f"\nResults: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
