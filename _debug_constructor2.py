import sys
sys.path.insert(0, r"D:\trae")
from src.interp import interpret
from src.parser import parse
import logging
logging.basicConfig(level=logging.DEBUG)

s = 'opt = ["Some", 42]\nv = match opt {\n  | Some(x) => x\n  | _ => 0\n}\n#：[v]'
ast = parse(s)
print("AST decls:", [type(d).__name__ for d in ast.decls])
out, _ = interpret(s, debug=True)
print('out:', out)
