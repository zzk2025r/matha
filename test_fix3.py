import sys
sys.path.insert(0, r'd:\trae')
from src.parser import parse
with open(r'd:\trae\matha\resource\logic\discrete_math.matha', 'r', encoding='utf-8') as f:
    source = f.read()
program = parse(source)
print('OK:', len(program.decls))
