import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

code = '''#：{
  result = 0
  items = [(1, "a"), (2, "b"), (3, "c")]
  for (a, b) in items {
    result = result + a
  }
  #：[result]
}'''

try:
    ast = parse(code)
    print("Parse OK")
    print("Decls:", [type(d).__name__ for d in ast.decls])
    for d in ast.decls:
        if hasattr(d, 'content'):
            print("  content:", type(d.content).__name__)
            if hasattr(d.content, 'stmts'):
                for s in d.content.stmts:
                    print("    stmt:", type(s).__name__, getattr(s, 'var', ''))
except Exception as e:
    print(f"Parse ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
