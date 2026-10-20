# -*- coding: utf-8 -*-
p = r'D:\trae\src\parser.py'
s = open(p, encoding='utf-8').read()

old = '''    def _parse_list_literal(self) -> Any:
        """<list_literal> = [ <expr> , { , <expr> } ]

        集合运算符链（`[a,b] ∪ [c,d]` 等）不再在此处自持尾链——统一由上层
        `_parse_set_expr` 处理（左结合）。此前此处另有 `right=_parse_expr()` 的
        尾链，与 `_parse_set_expr` 重复：当左操作数是列表字面量时它抢先行动，
        且因 `_parse_expr` 会再次进入 `_parse_set_expr`/本函数而呈**右结合**，
        与左操作数非列表时（走 `_parse_set_expr`，左结合）不一致，并导致
        `[1,2] ⊖ [3] ⊖ [1]` 的 stage2 ≠ stage3。移除后唯一链点即 `_parse_set_expr`。
        """
        self._expect(TokenType.PUNCT_LBRACKET, "列表左括号 [")
        elements: list[Any] = []
        if not self._check(TokenType.PUNCT_RBRACKET):
            elements.append(self._parse_expr())
            while self._check(TokenType.PUNCT_COMMA):
                self._advance()
                self._skip_newlines()
                if self._check(TokenType.PUNCT_RBRACKET):
                    break  # 允许尾随逗号
                elements.append(self._parse_expr())
        self._skip_newlines()
        self._expect(TokenType.PUNCT_RBRACKET, "列表右括号 ]")
        return ast.ListLiteral(elements=elements)'''

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
            self.pos = saved

        elements: list[Any] = []
        if not self._check(TokenType.PUNCT_RBRACKET):
            elements.append(self._parse_expr())
            while self._check(TokenType.PUNCT_COMMA):
                self._advance()
                self._skip_newlines()
                if self._check(TokenType.PUNCT_RBRACKET):
                    break  # 允许尾随逗号
                elements.append(self._parse_expr())
        self._skip_newlines()
        self._expect(TokenType.PUNCT_RBRACKET, "列表右括号 ]")
        return ast.ListLiteral(elements=elements)'''

if old not in s:
    print('not found')
else:
    open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    print('ok')
