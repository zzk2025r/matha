import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser

code = '''let s2 = get(src)(pos + 1) in
let c1 = get(src)(pos) in'''

p = Parser(code)
print(f"Total tokens: {len(p.tokens)}")
for i, t in enumerate(p.tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r}")

# Now manually trace the parsing
print("\n--- Manual trace ---")
# After parsing first let, we should be at token 11 (in)
# Then _parse_expr is called again at token 11
# My fix should check: after in, is next token a stmt keyword?
# Token 12 is NEWLINE, which is a stmt separator -> should backtrack
# But then _parse_expr at token 11 returns BinaryOp? No, it should return left

# Actually the issue is: _parse_let calls _parse_expr for body
# Let's trace what happens
import src.parser as parser_mod
orig_parse_expr = parser_mod.Parser._parse_expr

call_count = [0]
def traced_parse_expr(self, *args, **kwargs):
    call_count[0] += 1
    cid = call_count[0]
    print(f"  [{cid}] _parse_expr ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_parse_expr(self, *args, **kwargs)
    print(f"  [{cid}] _parse_expr RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_expr = traced_parse_expr

try:
    ast = p.parse()
    print(f"\nParse OK, {len(ast.decls)} decls")
    for i, d in enumerate(ast.decls):
        print(f"  decl[{i}]: {type(d).__name__}")
except Exception as e:
    print(f"Parse ERROR: {e}")
