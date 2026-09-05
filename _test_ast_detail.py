import sys
sys.path.insert(0, '.')
import importlib
import src.parser; importlib.reload(src.parser)
import src.interp; importlib.reload(src.interp)
from src.parser import Parser
from src import ast_nodes as ast

src = open('matha/knowledge/math/calculus.matha', encoding='utf-8').read()
p = Parser(src)
ast_tree = p.parse()

def show_tree(node, indent=0):
    prefix = '  ' * indent
    t = type(node).__name__
    info = ''
    if hasattr(node, 'name'):
        info += f' name={node.name}'
    if hasattr(node, 'params'):
        info += f' params={[p.name for p in node.params]}'
    if hasattr(node, 'else_body'):
        info += f' else_body={type(node.else_body).__name__ if node.else_body else None}'
    print(f'{prefix}{t}{info}')
    for attr in ['body', 'value', 'expr', 'cond', 'then', 'else_', 'left', 'right']:
        child = getattr(node, attr, None)
        if child is not None:
            print(f'{prefix}  [{attr}]')
            if isinstance(child, list):
                for item in child:
                    show_tree(item, indent+2)
            else:
                show_tree(child, indent+2)
    if hasattr(node, 'decls'):
        print(f'{prefix}  [decls]')
        for d in node.decls:
            show_tree(d, indent+2)
    if hasattr(node, 'stmts'):
        print(f'{prefix}  [stmts]')
        for s in node.stmts:
            show_tree(s, indent+2)

print('=== Full AST ===')
for d in ast_tree.decls:
    show_tree(d)
