import sys
sys.path.insert(0, r"D:\trae")
from src.parser import parse
from src import ast as ast_mod

s = 'opt = ["Some", 42]\nv = match opt {\n  | Some(x) => x\n  | _ => 0\n}\n#：[v]'
prog = parse(s)
print("Top-level decls:")
for d in prog.decls:
    print(f"  {type(d).__name__}")
    if hasattr(d, 'value') and d.value:
        print(f"    value: {type(d.value).__name__}")
        if hasattr(d.value, 'scrutinee'):
            print(f"    scrutinee: {d.value.scrutinee}")
        if hasattr(d.value, 'branches'):
            for i, (pat, guard, body) in enumerate(d.value.branches):
                print(f"    branch {i}: pattern={type(pat).__name__}", end="")
                if isinstance(pat, ast_mod.ConstructorPat):
                    print(f" name={pat.name} fields={[type(f).__name__ for f in pat.fields]}")
                elif isinstance(pat, ast_mod.Variable):
                    print(f" name={pat.name}")
                else:
                    print()
                print(f"      body={type(body).__name__}")
