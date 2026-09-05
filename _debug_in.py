import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Test 1: simple list literal in expression context
code1 = 'v = 2 in [1, 2, 3]'
try:
    p1 = Parser(code1)
    ast1 = p1.parse()
    print("test1 Parse OK")
except Exception as e:
    print(f"test1 Parse ERROR: {e}")
    print(f"  pos={p1.pos}, tok={p1._current().type.name}={p1._current().value!r}")

# Test 2: Belongs with list
code2 = 'v = 2 ∈ [1, 2, 3]'
try:
    p2 = Parser(code2)
    ast2 = p2.parse()
    print("test2 Parse OK")
except Exception as e:
    print(f"test2 Parse ERROR: {e}")
    print(f"  pos={p2.pos}, tok={p2._current().type.name}={p2._current().value!r}")

# Test 3: token list for [1, 2, 3]
print("\nTokens for [1, 2, 3]:")
code3 = 'x = [1, 2, 3]'
p3 = Parser(code3)
for i, t in enumerate(p3.tokens):
    print(f"  {i}: {t.type.name:20} = {t.value!r}")

# Test 4: tokens for 2 in [1, 2, 3]
print("\nTokens for '2 in [1, 2, 3]':")
code4 = '2 in [1, 2, 3]'
p4 = Parser(code4)
for i, t in enumerate(p4.tokens):
    print(f"  {i}: {t.type.name:20} = {t.value!r}")
