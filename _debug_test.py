import sys
sys.path.insert(0, 'd:/trae')
from src.parser import Parser
from src.ast_nodes import *
from src.interp import Interpreter

# Check what the parser produces for ["Some", 42]
s = 'x = ["Some", 42]'
print("=== Test: list with string and int ===")
parser = Parser(s)
ast = parser.parse()
print(f"AST: {type(ast.decls[0]).__name__}")
if isinstance(ast.decls[0], Binding):
    print(f"  value: {type(ast.decls[0].value).__name__}")
    if isinstance(ast.decls[0].value, ListLiteral):
        print(f"  elements: {[type(e).__name__ for e in ast.decls[0].value.elements]}")
        for i, e in enumerate(ast.decls[0].value.elements):
            print(f"    elem[{i}]: {type(e).__name__} = {e}")

interp = Interpreter()
val = interp._eval(ast.decls[0].value)
print(f"Evaluated: {val} (type: {type(val).__name__})")

# Test match
print("\n=== Test: match ===")
s2 = '''#：{
  opt = ["Some", 42]
  v = match opt {
    | Some(x) => x
    | _ => 0
  }
  #：[v]
}'''
parser2 = Parser(s2)
ast2 = parser2.parse()
interp2 = Interpreter(debug=True)
outputs, trace = interp2.run(ast2)
print(f"Outputs: {outputs}")
