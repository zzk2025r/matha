import sys; sys.path.insert(0, r'D:\trae')
from src.parser import Parser
from src import ast_nodes as ast

# 测试 a >> b = 5
p = Parser('a >> b = 5')
ast_result = p.parse()
print('声明类型:', [type(d).__name__ for d in ast_result.decls])
for d in ast_result.decls:
    tname = type(d).__name__
    print(f'  {tname}')
    if hasattr(d, 'target'):
        print(f'    target: {type(d.target).__name__}')
        if hasattr(d.target, 'left'):
            print(f'      left={type(d.target.left).__name__}, right={type(d.target.right).__name__}')
    if hasattr(d, 'expr'):
        print(f'    expr: {type(d.expr).__name__}')
        if hasattr(d.expr, 'left'):
            print(f'      left={type(d.expr.left).__name__}, right={type(d.expr.right).__name__}')
