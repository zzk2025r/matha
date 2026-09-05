import sys
sys.path.insert(0, '.')
import importlib
import src.parser; importlib.reload(src.parser)
import src.interp; importlib.reload(src.interp)
from src.parser import Parser
from src.interp import interpret

src = open('matha/examples/06_sub.matha', encoding='utf-8').read()
p = Parser(src)
ast_tree = p.parse()

def show_stmt(s, indent=0):
    prefix = '  ' * indent
    t = type(s).__name__
    info = ''
    if isinstance(s, Parser.__class__ and hasattr(s, 'body')):  # WRONG
        pass
    if hasattr(s, 'body'):
        b = s.body
        if isinstance(b, list):
            info += f' body=list[{len(b)}]'
            for i, item in enumerate(b):
                print(f'{prefix}  [{i}] {type(item).__name__}', end='')
                if hasattr(item, 'items'):
                    for j, it in enumerate(item.items):
                        val_name = type(it.value).__name__ if it.value else 'None'
                        print(f' @{j}={it.target}={val_name}', end='')
                print()
                show_stmt(item, indent+2)
            return
        elif hasattr(b, 'stmts'):
            info += f' body=CodeBlock[{len(b.stmts)}]'
        else:
            info += f' body={type(b).__name__}'
    if hasattr(s, 'items'):
        info += f' items={len(s.items)}'
        for j, it in enumerate(s.items):
            val_name = type(it.value).__name__ if it.value else 'None'
            info += f' @{j}={it.target}={val_name}'
    print(f'{prefix}{t}{info}')

print(f'Top-level decls: {len(ast_tree.decls)}')
for i, d in enumerate(ast_tree.decls):
    print(f'  [{i}] {type(d).__name__}')
    if hasattr(d, 'body'):
        b = d.body
        if isinstance(b, list):
            print(f'    body=list[{len(b)}]')
            for j, item in enumerate(b):
                print(f'      [{j}] {type(item).__name__}', end='')
                if hasattr(item, 'items'):
                    for k, it in enumerate(item.items):
                        val_name = type(it.value).__name__ if it.value else 'None'
                        print(f' @{k}={it.target}={val_name}', end='')
                print()
                if hasattr(item, 'body'):
                    show_stmt(item, 2)
        elif hasattr(b, 'stmts'):
            print(f'    body=CodeBlock[{len(b.stmts)}]')
            for j, item in enumerate(b.stmts):
                print(f'      [{j}] {type(item).__name__}', end='')
                if hasattr(item, 'items'):
                    for k, it in enumerate(item.items):
                        val_name = type(it.value).__name__ if it.value else 'None'
                        print(f' @{k}={it.target}={val_name}', end='')
                print()
        else:
            print(f'    body={type(b).__name__}')

print()
try:
    out, trace = interpret(src)
    print('PASS:', out, trace)
except Exception as e:
    print(f'FAIL: {e}')
    import traceback
    traceback.print_exc()
