import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse
from src import ast_nodes as ast

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

ast_tree = parse(code)
print(f"Parsed as {len(ast_tree.decls)} decls:")
for i, d in enumerate(ast_tree.decls):
    print(f"  [{i}] {type(d).__name__}")
    if hasattr(d, 'body'):
        body = d.body
        print(f"    body: {type(body).__name__}")
        if hasattr(body, 'stmts'):
            for j, s in enumerate(body.stmts):
                print(f"      [{j}] {type(s).__name__}")
                if hasattr(s, 'name'):
                    print(f"          name={s.name}")
                if hasattr(s, 'value'):
                    print(f"          value={type(s.value).__name__}")
                    if hasattr(s.value, 'op'):
                        print(f"            op={s.value.op}")
                        print(f"            left={type(s.value.left).__name__}")
                        print(f"            right={type(s.value.right).__name__}")
                if hasattr(s, 'body'):
                    print(f"          body={type(s.body).__name__ if s.body else None}")
                if hasattr(s, 'expr'):
                    print(f"          expr={type(s.expr).__name__}")
