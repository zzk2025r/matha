import sys
sys.path.insert(0, r'D:\trae')
from src.parser import Parser
from src import ast_nodes as ast

# 测试 a >> b = 5
source = 'a >> b = 5'
p = Parser(source)

# 手动追踪
print(f'Source: {source!r}')
print()

# Step 1: _parse_expr()
expr = p._parse_expr()
print(f'_parse_expr() 返回: {type(expr).__name__}')
if hasattr(expr, 'op'):
    print(f'  op={expr.op!r}')
if hasattr(expr, 'left'):
    print(f'  left={type(expr.left).__name__}')
    if hasattr(expr.left, 'left'):
        print(f'    left.left={type(expr.left.left).__name__}')
        print(f'    left.right={type(expr.left.right).__name__}')
if hasattr(expr, 'right'):
    print(f'  right={type(expr.right).__name__}')
print()

# Step 2: _make_binding_or_expr
if isinstance(expr, ast.BinaryOp) and expr.op == '=':
    print(f'expr 是 BinaryOp("=")')
    print(f'  expr.left 类型: {type(expr.left).__name__}')
    if isinstance(expr.left, ast.Belongs):
        print(f'  expr.left 是 Belongs → 应转换为 PathExpr')
    elif isinstance(expr.left, ast.Variable):
        print(f'  expr.left 是 Variable')
    elif isinstance(expr.left, ast.PathExpr):
        print(f'  expr.left 是 PathExpr')
    else:
        print(f'  expr.left 是其他: {type(expr.left).__name__}')

# Step 3: 完整解析
p2 = Parser(source)
result = p2.parse()
print(f'\n完整解析结果:')
for d in result.decls:
    print(f'  {type(d).__name__}')
    if hasattr(d, 'target'):
        print(f'    target: {type(d.target).__name__}')
