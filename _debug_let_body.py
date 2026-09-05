import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse

# Test: let with [1] as body
code = '''let toks = 扫描("x + 1") in
[1]'''

try:
    p = parse(code)
    print(f"Parse OK, {len(p.decls)} decls")
    for i, d in enumerate(p.decls):
        print(f"  [{i}] {type(d).__name__}")
        if hasattr(d, 'name'):
            print(f"      name={d.name}")
        if hasattr(d, 'value'):
            print(f"      value={type(d.value).__name__}")
        if hasattr(d, 'body'):
            print(f"      body={type(d.body).__name__ if d.body else None}")
except Exception as e:
    print(f"Parse ERROR: {e}")
