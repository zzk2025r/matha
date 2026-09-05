import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Debug: tokens around line 67 in lexer.matha
with open(r"D:\trae\matha\lexer.matha", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find line 67
print(f"Line 67: {lines[66]!r}")
print(f"Line 66: {lines[65]!r}")
print(f"Line 68: {lines[67]!r}")

# Parse just the relevant part
code = '''func 检测多符(src: String, pos: Int) -> (类型, String) =
    (src, pos) =>
      (pos + 1 < len(src)) ?
        let s2 = get(src)(pos + 1) in
        let c1 = get(src)(pos) in'''

p = Parser(code)
for i, t in enumerate(p.tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")
