p = r'D:\trae\src\parser.py'
s = open(p, encoding='utf-8').read()
old = '''    def _parse_list_literal(self) -> Any:
        """<list_literal> = [ <expr> , { , <expr> } ] | [ <expr> for ... ]"""
        self._expect(TokenType.PUNCT_LBRACKET, "列表左括号 [")
        # 检测列表推导：[expr for target in iter if ...]
        saved = self.pos
        try:
            first = self._parse_expr()
            if self._check(TokenType.KW_FOR):
                self._advance()
                target = self._parse_expr()
                if self._check(TokenType.KW_IN):
                    self._advance()
                it = self._parse_expr()
                ifs = []
                while self._check(TokenType.KW_IF):
                    self._advance()
                    ifs.append(self._parse_expr())
                self._skip_newlines()
                self._expect(TokenType.PUNCT_RBRACKET, "列表右括号 ]")
                return ast.ListComp(expr=first, target=target, iter=it, ifs=ifs)
            self.pos = saved
        except Exception:
            self.pos = saved'''
new = '''    def _parse_list_literal(self) -> Any:
        """<list_literal> = [ <expr> , { , <expr> } ] | [ <expr> for ... ]"""
        self._expect(TokenType.PUNCT_LBRACKET, "列表左括号 [")
        # 检测列表推导：[expr for target in iter if ...]
        saved = self.pos
        try:
            first = self._parse_expr()
            if self._check(TokenType.KW_FOR):
                self._advance()
                target = self._parse_expr()
                if self._check(TokenType.KW_IN):
                    self._advance()
                it = self._parse_expr()
                ifs = []
                while self._check(TokenType.KW_IF):
                    self._advance()
                    ifs.append(self._parse_expr())
                self._skip_newlines()
                self._expect(TokenType.PUNCT_RBRACKET, "列表右括号 ]")
                return ast.ListComp(expr=first, target=target, iter=it, ifs=ifs)
            self.pos = saved
        except Exception:
            self.pos = saved'''
# same logic but need to be careful - in our flow pos is after [ now; but if called from certain contexts, different
# actually easier: also try from before [
if old in s:
    print('found')
else:
    print('no')
