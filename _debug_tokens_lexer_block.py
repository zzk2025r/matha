import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")
