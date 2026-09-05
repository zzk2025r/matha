import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Just test parsing the problematic code directly
code = '''let s2 = get(src)(pos + 1) in
let c1 = get(src)(pos) in'''

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
    for d in ast.decls:
        print(f"  Decl: {type(d).__name__}")
        if hasattr(d, 'name'):
            print(f"    name={d.name}")
        if hasattr(d, 'value'):
            print(f"    value={type(d.value).__name__}")
        if hasattr(d, 'body'):
            print(f"    body={type(d.body).__name__ if d.body else 'None'}")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
    for i in range(max(0, p.pos-3), min(len(p.tokens), p.pos+5)):
        print(f"  Token {i}: {p.tokens[i].type.name} = {p.tokens[i].value!r}")
