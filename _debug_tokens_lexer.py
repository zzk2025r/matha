import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

# Debug: tokenize the lexer.matha self-test section
code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

from src.parser import Parser
from src.tokens import TokenType
p = Parser(code)
for i, t in enumerate(p.tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")
