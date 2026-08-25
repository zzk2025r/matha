import sys
sys.path.insert(0, r'D:\trae')
from src.parser import Parser
from src import ast_nodes as ast

# 详细追踪 a >> b = 5 的解析过程
source = 'a >> b = 5'
p = Parser(source)

print(f'Source: {source!r}')
print(f'Tokens: {[(i, t.type.name, t.value) for i, t in enumerate(p.tokens)]}')
print()

# 手动追踪
print('=== 手动追踪 _parse_expr_or_binding ===')
expr = p._parse_expr()
print(f'_parse_expr() 返回: {type(expr).__name__}')
if hasattr(expr, 'left'):
    print(f'  left: {type(expr.left).__name__}')
    if hasattr(expr.left, 'left'):
        print(f'    left.left: {type(expr.left.left).__name__}')
        print(f'    left.right: {type(expr.left.right).__name__}')
if hasattr(expr, 'right'):
    print(f'  right: {type(expr.right).__name__}')

# 现在测试 _is_path_context
print()
print('=== _is_path_context 调试 ===')
p2 = Parser('a >> b = 5')
# 走到 >> 位置
p2._parse_primary()  # 解析 a
print(f'After _parse_primary, pos={p2.pos}, current={p2._current().value}')
print(f'_peek(1)={p2._peek(1).type.name}={p2._peek(1).value}')
print(f'_peek(2)={p2._peek(2).type.name}={p2._peek(2).value}')
print(f'_is_path_context()={p2._is_path_context()}')
