import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

# Parse just the problematic section of parser.matha
code = '''    let (cond, p2) = 解析比较(p) in
    if 匹配(p2, 类型.问号) then
      let p3 = 推进(p2) in
      let (then_expr, p4) = 解析三元(p3) in
      let p5 = 期望(p4, 类型.冒号) in
      let (else_expr, p6) = 解析三元(p5) in
      (做If(cond, then_expr, else_expr), p6)
    else (cond, p2)'''

p = Parser(code)
tokens = p.tokens
for i, t in enumerate(tokens):
    print(f"Token {i}: {t.type.name:20} = {t.value!r} at L{t.line}:{t.col}")
