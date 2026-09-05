import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType
from src import ast_nodes as ast

code = '''#：{
  let toks = 扫描("x + 1") in
  [1]
}'''

import src.parser as parser_mod

orig_check = parser_mod.Parser._check

call_count = [0]
def traced_check(self, *types):
    call_count[0] += 1
    cid = call_count[0]
    tok = self._current()
    result = orig_check(self, *types)
    if tok.type == TokenType.KW_IN and result:
        print(f"  [_check IN] pos={self.pos}, tok={tok.value!r}, result={result}")
        # Show what's after
        saved = self.pos
        self._advance()
        self._skip_newlines()
        after = self._current()
        print(f"    after in: pos={self.pos}, tok={after.type.name}={after.value!r}")
        self.pos = saved
    return result

parser_mod.Parser._check = traced_check

try:
    p = Parser(code)
    ast_tree = p.parse()
    print(f"\nParse OK: {len(ast_tree.decls)} decls")
except Exception as e:
    print(f"\nParse ERROR: {e}")
