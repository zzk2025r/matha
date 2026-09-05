import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType
from src import ast_nodes as ast

code = 'v = 2 in [1, 2, 3]'

# Test: does `in` followed by `[` get parsed as index?
# Expected: BinaryOp(in, left=2, right=[1,2,3])
# Actual: Error because [1,2,3] is treated as index

# Let's manually trace what happens
# The issue: in _parse_postfix, after parsing `in` as Variable,
# the loop sees `[` and tries to parse it as index access

# Fix: need to check if previous expr is Variable('in') and next token is `[`
# If so, don't treat as index, let it fall through to _parse_rel_expr

print("Testing current behavior...")
try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"Parse OK: {ast_tree}")
except Exception as e:
    print(f"Parse ERROR: {e}")

# What we want: 2 in [1, 2, 3] should be BinaryOp(op=" in ", left=2, right=[1,2,3])
# Current: it parses `in` as Variable, then `[1, 2, 3]` as index, which fails
