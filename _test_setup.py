import sys
sys.path.insert(0, '.')
import importlib
import src.parser; importlib.reload(src.parser)
import src.interp; importlib.reload(src.interp)
from src.parser import Parser
from src.interp import interpret

src = '@：【计价参数】，单价=10，数量=3'
p = Parser(src)
ast_tree = p.parse()

print('Decls:')
for d in ast_tree.decls:
    print(f'  {type(d).__name__}', end='')
    if hasattr(d, 'items'):
        print(f' items={len(d.items)}', end='')
        for j, it in enumerate(d.items):
            val_name = type(it.value).__name__ if it.value else 'None'
            print(f' @{j}={it.target}={val_name}', end='')
    print()
