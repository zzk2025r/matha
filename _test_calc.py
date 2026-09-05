import sys
sys.path.insert(0, '.')
import importlib
import src.parser; importlib.reload(src.parser)
import src.interp; importlib.reload(src.interp)
from src.parser import Parser
from src.interp import interpret

src = open('matha/knowledge/math/calculus.matha', encoding='utf-8').read()
p = Parser(src)
ast_tree = p.parse()

print('Module decls:')
for d in ast_tree.decls:
    print(f'  {type(d).__name__} name={getattr(d, "name", "")}')
    if hasattr(d, 'decls'):
        for sub in d.decls:
            print(f'    {type(sub).__name__} name={getattr(sub, "name", "")} else_body={getattr(sub, "else_body", None)}')

print()
try:
    out, trace = interpret(src)
    print('Output:', out)
except Exception as e:
    print(f'FAIL: {e}')
    import traceback
    traceback.print_exc()
