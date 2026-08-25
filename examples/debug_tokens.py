import sys
sys.path.insert(0, r'D:\trae')
from src.parser import Parser
from src import ast_nodes as ast

# 测试 a >> b = 5
source = 'a >> b = 5'
p = Parser(source)
print(f'Source: {source!r}')
print(f'Tokens: {[t.value for t in p.tokens]}')
print()

# 逐步追踪
for i, tok in enumerate(p.tokens):
    print(f'  [{i}] {tok.type.name:20s} {tok.value!r}')
