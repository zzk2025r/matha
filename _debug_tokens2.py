import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser

code = '''      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in'''

p = Parser(code)
for i, t in enumerate(p.tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")
