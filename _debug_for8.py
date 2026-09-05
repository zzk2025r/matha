import sys
sys.path.insert(0, r"D:\trae")
from src.parser import Parser
from src.tokens import TokenType

code = '''#：{
  result = 0
  items = [(1, "a"), (2, "b"), (3, "c")]
  for (a, b) in items {
    result = result + a
  }
  #：[result]
}'''

# Monkey-patch with detailed tracing
import src.parser as parser_mod
original_parse_for = parser_mod.Parser._parse_for

def traced_parse_for(self):
    print(f"TRACE _parse_for ENTER: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}, in_cf={self._in_control_flow}")
    self._expect(TokenType.KW_FOR, "for")
    saved = self.pos
    print(f"TRACE after 'for': pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")

    if self._check(TokenType.PUNCT_LPAREN):
        print("TRACE: entering tuple destructuring branch")
        params = []
        self._advance()  # consume (
        print(f"TRACE after consuming (: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
        while not self._check(TokenType.PUNCT_RPAREN, TokenType.EOF):
            self._skip_newlines()
            if self._check(TokenType.PUNCT_RPAREN):
                break
            if params:
                self._expect(TokenType.PUNCT_COMMA, ",")
            p = self._current()
            print(f"TRACE loop: pos={self.pos}, tok={p.type.name}={p.value!r}")
            if p.type == TokenType.PUNCT_RPAREN:
                break
            if p.type in (TokenType.IDENTIFIER, TokenType.MATHA_PLACEHOLDER):
                self._advance()
                params.append(p.value)
                print(f"TRACE consumed {p.value}, params={params}")
            else:
                break
        self._skip_newlines()
        print(f"TRACE after collecting params: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
        print(f"TRACE _check RPAREN: {self._check(TokenType.PUNCT_RPAREN)}")
        # Check manually
        self._skip_newlines()
        print(f"TRACE after _skip_newlines in check: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
        print(f"TRACE _check KW_IN: {self._check(TokenType.KW_IN)}")
        if self._check(TokenType.PUNCT_RPAREN) and self._check_after_skip(TokenType.KW_IN):
            self._advance()  # consume )
            print(f"TRACE after consuming ): pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
            self._expect(TokenType.KW_IN, "in")
            print(f"TRACE after consuming in: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
            saved_cf = self._in_control_flow
            self._in_control_flow = True
            try:
                iterable = self._parse_expr()
            finally:
                self._in_control_flow = saved_cf
            print(f"TRACE after parsing iterable: pos={self.pos}, tok={self._current().type.name}={self._current().value!r}")
            self._expect(TokenType.PUNCT_LBRACE, "{")
            block = self._parse_block_body()
            self._expect(TokenType.PUNCT_RBRACE, "}")
            print(f"TRACE: parsed for (a,b) in items {{...}}")
            from src import ast_nodes as ast
            return ast.ForStmt(var=params, iterable=iterable, block=block)
        else:
            print("TRACE: NOT for (a,b) in form, falling back")
            self.pos = saved
    else:
        print("TRACE: NOT tuple destructuring, plain for")
        self.pos = saved

    var = self._expect(TokenType.IDENTIFIER, "迭代变量").value
    self._expect(TokenType.KW_IN, "in")
    saved_cf = self._in_control_flow
    self._in_control_flow = True
    try:
        iterable = self._parse_expr()
    finally:
        self._in_control_flow = saved_cf
    self._expect(TokenType.PUNCT_LBRACE, "{")
    block = self._parse_block_body()
    self._expect(TokenType.PUNCT_RBRACE, "}")
    from src import ast_nodes as ast
    return ast.ForStmt(var=[var], iterable=iterable, block=block)

parser_mod.Parser._parse_for = traced_parse_for

try:
    p = Parser(code)
    ast = p.parse()
    print("Parse OK")
except Exception as e:
    print(f"Parse ERROR: {e}")
    print(f"Current token at error: pos={p.pos}, tok={p._current().type.name}={p._current().value!r}")
