import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

import src.parser as parser_mod

orig_code_block = parser_mod.Parser._parse_code_block

def traced_code_block(self):
    print(f"_parse_code_block ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_code_block(self)
    print(f"_parse_code_block RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    return result

parser_mod.Parser._parse_code_block = traced_code_block

orig_mech_stmt = parser_mod.Parser._parse_mech_stmt

def traced_mech_stmt(self):
    print(f"_parse_mech_stmt ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
    result = orig_mech_stmt(self)
    print(f"_parse_mech_stmt RETURN: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, result={type(result).__name__}")
    return result

parser_mod.Parser._parse_mech_stmt = traced_mech_stmt

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
