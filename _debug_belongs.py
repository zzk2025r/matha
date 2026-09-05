import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Check how ∈ is tokenized
code = '2 ∈ [1, 2, 3]'
p = Parser(code)
for i, t in enumerate(p.tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r}")
