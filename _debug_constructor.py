import sys
sys.path.insert(0, r"D:\trae")
from src.interp import interpret

s = 'opt = ["Some", 42]\nv = match opt {\n  | Some(x) => x\n  | _ => 0\n}\n#：[v]'
out, _ = interpret(s)
print('out:', out)
