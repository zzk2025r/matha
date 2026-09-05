import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

code = '''func 解析三元(p: 解析器) -> (Dict, 解析器) = (p) =>
  let (cond, p2) = 解析比较(p) in
  if 匹配(p2, 类型.问号) then
    let p3 = 推进(p2) in
    let (then_expr, p4) = 解析三元(p3) in
    let p5 = 期望(p4, 类型.冒号) in
    let (else_expr, p6) = 解析三元(p5) in
    (做If(cond, then_expr, else_expr), p6)
  else (cond, p2)'''

ast = parse(code)
print(f"Parsed as {len(ast.decls)} decls")
for i, d in enumerate(ast.decls):
    print(f"  [{i}] {type(d).__name__}")
    if hasattr(d, 'name'):
        print(f"    name={d.name}")
    if hasattr(d, 'body'):
        body = d.body
        if hasattr(body, 'stmts'):
            for j, s in enumerate(body.stmts):
                print(f"    stmt[{j}]: {type(s).__name__}")
