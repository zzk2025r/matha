"""Matha 正则表达式库（可移植回溯引擎 + 解释器/VM 注册）。

设计目标：**单一语义源**。解释器与 M3V VM 直接复用本模块的纯 Python 引擎；
原生后端（src/mbc/native.py）将复用同一套「模式 → 节点」编译结果与同一匹配
算法（后续发射为 x86-64），从而保证三端行为一致。

支持的 PCRE 风格语法：
  - 字面量、转义（\\n \\r \\t \\f \\v \\a \\e \\0 \\xHH \\uHHHH \\UXXXXXXXX）
  - `.`（默认不匹配换行；(?s) 打开 DOTALL）
  - 字符类 [...]（范围 a-z、取反 ^、内嵌 \\d\\w\\s 及其取反、转义；`]` 作首字符即字面量）
  - 简写类 \\d \\D \\w \\W \\s \\S
  - 锚点 ^ $ \\A \\Z \\z \\b \\B
  - 量词 * + ? {m} {m,} {m,n}，贪婪 / 惰性(后缀 ?) / 占有(后缀 +)
  - 分组：捕获 (...) / 非捕获 (?:...) / 命名 (?P<名>...) (?<名>...) (?'名'...)
  - 反向引用 \\1..\\99、\\k<名>、\\g<名>、(?P=名)
  - 环绕断言（lookaround）：(?=…) (?!…) (?<=…) (?<!…)
  - 内联标志 (?i) (?m) (?s) (?x) 及作用域标志 (?i:…)（i 忽略大小写 / m 多行 /
    s 点匹配换行 / x 忽略空白与 # 注释）

对外 Matha 内建（命名沿用现有中文风格，柯里化）：
  匹配(re)(s)        布尔：是否在 s 中搜到 re
  全匹配(re)(s)      布尔：re 是否完整覆盖 s
  查找正则(re)(s)    列表 [整体, 组1, ...]（未参与为 null），无匹配为 null
  查找全部(re)(s)    列表，每项同上
  命名组(re)(s)      字典 {组名: 文本}（未参与为 null），无匹配为 null
  替换正则(re)(新)(s) 文本（新可含 \\1..\\9 \\0 \\g<名> 或 $1）
  分割正则(re)(s)    列表
"""
from __future__ import annotations

import functools

# ---------------- 标志 ----------------
_I = 1   # ignorecase
_M = 2   # multiline
_S = 4   # dotall
_X = 8   # verbose

_FLAG_CHARS = {"i": _I, "m": _M, "s": _S, "x": _X}


class RegexError(Exception):
    """正则编译/匹配错误。"""


# ---------------- 字符判定 ----------------
def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


def _is_boundary(s: str, pos: int) -> bool:
    left = pos > 0 and _is_word(s[pos - 1])
    right = pos < len(s) and _is_word(s[pos])
    return left != right


_SHORTHAND = {"d": "d", "D": "d", "w": "w", "W": "w", "s": "s", "S": "s"}
_SHORTHAND_NEG = {"d": False, "D": True, "w": False, "W": True, "s": False, "S": True}


def _sh_matches(kind: str, neg: bool, c: str) -> bool:
    if kind == "d":
        ok = c.isdigit()
    elif kind == "w":
        ok = _is_word(c)
    else:
        ok = c.isspace()
    return (not ok) if neg else ok


def _set_matches(negated: bool, items: list, c: str, flags: int) -> bool:
    def one(ch: str) -> bool:
        o = ord(ch)
        for it in items:
            if len(it) == 3 and it[0] == "sh":
                if _sh_matches(it[1], it[2], ch):
                    return True
            elif it[0] <= o <= it[1]:
                return True
        return False

    ok = one(c)
    if not ok and (flags & _I):
        alt = c.swapcase()
        if alt != c:
            ok = one(alt)
    return (not ok) if negated else ok


# ---------------- 解析 ----------------
class _Parser:
    def __init__(self, pattern: str, flags: int):
        self.p = pattern
        self.n = len(pattern)
        self.i = 0
        self.flags = flags
        self.ngroups = 0
        self.names: dict[str, int] = {}

    # ---- 基础 ----
    def _peek(self) -> str:
        return self.p[self.i] if self.i < self.n else ""

    def _expect(self, c: str):
        if self.i < self.n and self.p[self.i] == c:
            self.i += 1
            return
        raise RegexError(f"正则：位置 {self.i} 期望 {c!r}，实际 {self._peek()!r}")

    def _read_int(self):
        s = self.i
        while self.i < self.n and self.p[self.i].isdigit():
            self.i += 1
        return int(self.p[s:self.i]) if self.i > s else None

    def _read_name(self, close: str) -> str:
        s = self.i
        while self.i < self.n and self.p[self.i] != close:
            self.i += 1
        if self.i >= self.n:
            raise RegexError(f"正则：组名缺少结束符 {close!r}")
        name = self.p[s:self.i]
        self.i += 1
        if not name:
            raise RegexError("正则：组名不能为空")
        return name

    def _skip_ws(self):
        if not (self.flags & _X):
            return
        while self.i < self.n:
            c = self.p[self.i]
            if c in " \t\r\n\f\v":
                self.i += 1
            elif c == "#":
                while self.i < self.n and self.p[self.i] != "\n":
                    self.i += 1
            else:
                break

    # ---- 入口 ----
    def parse(self):
        node = self._parse_alt()
        self._skip_ws()
        if self.i < self.n:
            raise RegexError(f"正则：位置 {self.i} 处存在无法解析的 {self._peek()!r}")
        self._validate(node)
        return node

    def _parse_alt(self):
        branches = [self._parse_seq()]
        while self._peek() == "|":
            self.i += 1
            branches.append(self._parse_seq())
        if len(branches) == 1:
            return branches[0]
        return ("alt", branches)

    def _parse_seq(self):
        nodes = []
        while True:
            self._skip_ws()
            c = self._peek()
            if c == "" or c == "|" or c == ")":
                break
            nodes.append(self._parse_quant())
        if len(nodes) == 1:
            return nodes[0]
        return ("seq", nodes)

    def _parse_quant(self):
        atom = self._parse_atom()
        self._skip_ws()
        c = self._peek()
        mn = mx = 0
        if c == "*":
            self.i += 1
            mn, mx = 0, -1
        elif c == "+":
            self.i += 1
            mn, mx = 1, -1
        elif c == "?":
            self.i += 1
            mn, mx = 0, 1
        elif c == "{":
            save = self.i
            self.i += 1
            lo = self._read_int()
            if lo is None:
                self.i = save
            else:
                if self._peek() == ",":
                    self.i += 1
                    hi = self._read_int()
                    if hi is None:
                        hi = -1
                else:
                    hi = lo
                if self.i < self.n and self.p[self.i] == "}":
                    self.i += 1
                    if hi != -1 and hi < lo:
                        raise RegexError(f"正则：量词 {{{lo},{hi}}} 上限小于下限")
                    mn, mx = lo, hi
                else:
                    self.i = save
            c = self._peek()
            if self.i == save:
                return atom
        else:
            return atom
        mode = 0
        if self._peek() == "?":
            self.i += 1
            mode = 1
        elif self._peek() == "+":
            self.i += 1
            mode = 2
        return ("rep", atom, mn, mx, mode)

    # ---- 原子 ----
    def _parse_atom(self):
        atom = self._parse_atom_raw()
        if self.flags:
            return ("flags", self.flags, atom)
        return atom

    def _parse_atom_raw(self):
        c = self._peek()
        if c == "(":
            return self._parse_group()
        if c == "[":
            return self._parse_class()
        if c == ".":
            self.i += 1
            return ("any",)
        if c == "^":
            self.i += 1
            return ("anchor", "bol")
        if c == "$":
            self.i += 1
            return ("anchor", "eol")
        if c == "\\":
            return self._parse_escape(False)
        if c in "*+?":
            raise RegexError(f"正则：位置 {self.i} 的量词 {c!r} 没有可作用的目标")
        self.i += 1
        return ("lit", c)

    def _parse_group(self):
        self.i += 1  # '('
        if self._peek() == "?":
            self.i += 1
            c = self._peek()
            if c == ":":
                self.i += 1
                node = self._parse_alt()
                self._expect(")")
                return node
            if c == "P":
                self.i += 1
                if self._peek() == "<":
                    self.i += 1
                    return self._named_group(self._read_name(">"))
                if self._peek() == "=":
                    self.i += 1
                    return ("bref", None, self._read_name(")"))
                raise RegexError("正则：(?P…) 语法错误")
            if c in "=!":
                self.i += 1
                node = self._parse_alt()
                self._expect(")")
                return ("look", c, False, node)
            if c == "<":
                self.i += 1
                c2 = self._peek()
                if c2 in "=!":
                    self.i += 1
                    node = self._parse_alt()
                    self._expect(")")
                    return ("look", c2, True, node)
                return self._named_group(self._read_name(">"))
            if c == "'":
                self.i += 1
                return self._named_group(self._read_name("'"))
            # 内联标志
            fl_add = 0
            fl_rem = 0
            neg = False
            while self._peek() in _FLAG_CHARS or self._peek() == "-":
                ch = self.p[self.i]
                self.i += 1
                if ch == "-":
                    neg = True
                    continue
                if neg:
                    fl_rem |= _FLAG_CHARS[ch]
                else:
                    fl_add |= _FLAG_CHARS[ch]
            if self.i < self.n and self.p[self.i] == ")":
                self.i += 1
                self.flags = (self.flags | fl_add) & ~fl_rem
                return ("seq", [])
            if self._peek() == ":":
                self.i += 1
                old = self.flags
                self.flags = (old | fl_add) & ~fl_rem
                node = self._parse_alt()
                self.flags = old
                self._expect(")")
                return node
            raise RegexError("正则：(?…) 组语法错误")
        self.ngroups += 1
        idx = self.ngroups
        node = self._parse_alt()
        self._expect(")")
        return ("group", idx, node)

    def _named_group(self, name):
        if name in self.names:
            raise RegexError(f"正则：重复的组名 {name!r}")
        self.ngroups += 1
        self.names[name] = self.ngroups
        node = self._parse_alt()
        self._expect(")")
        return ("group", self.ngroups, node)

    # ---- 转义 ----
    def _parse_escape(self, in_class):
        self.i += 1  # '\'
        if self.i >= self.n:
            raise RegexError("正则：结尾处的反斜杠")
        c = self.p[self.i]
        if c in _SHORTHAND:
            self.i += 1
            if in_class:
                return ("sh", _SHORTHAND[c], _SHORTHAND_NEG[c])
            return ("set", _SHORTHAND_NEG[c], [("sh", _SHORTHAND[c], False)])
        if not in_class:
            if c in ("b", "B"):
                self.i += 1
                return ("anchor", "wb" if c == "b" else "nwb")
            if c == "A":
                self.i += 1
                return ("anchor", "bos")
            if c in ("Z", "z"):
                self.i += 1
                return ("anchor", "eos")
            if c in "123456789":
                return ("bref", self._read_int(), None)
            if c in ("k", "g"):
                self.i += 1
                if self._peek() in "<{'":
                    op = self.p[self.i]
                    self.i += 1
                    close = {"<": ">", "{": "}", "'": "'"}[op]
                    nm = self._read_name(close)
                    if c == "g" and op == "{" and nm.isdigit():
                        return ("bref", int(nm), None)
                    return ("bref", None, nm)
                raise RegexError(f"正则：\\{c} 后应为 <名> 或 '名'")
        self.i += 1
        simple = {"n": "\n", "r": "\r", "t": "\t", "f": "\f", "v": "\v",
                  "a": "\a", "e": "\x1b", "0": "\0"}
        if in_class and c == "b":
            return ("lit", "\x08")
        if c in simple:
            return ("lit", simple[c])
        if c == "x":
            return ("lit", self._read_hex(2))
        if c == "u":
            return ("lit", self._read_hex(4))
        if c == "U":
            return ("lit", self._read_hex(8))
        return ("lit", c)

    def _read_hex(self, k):
        s = self.i
        cnt = 0
        while cnt < k and self.i < self.n and self.p[self.i] in "0123456789abcdefABCDEF":
            self.i += 1
            cnt += 1
        if cnt == 0:
            raise RegexError("正则：\\x/\\u/\\U 期望十六进制数字")
        return chr(int(self.p[s:self.i], 16))

    # ---- 字符类 ----
    def _class_atom(self):
        c = self.p[self.i]
        if c == "\\":
            r = self._parse_escape(True)
            if r[0] == "sh":
                return r
            return r[1]
        self.i += 1
        return c

    def _parse_class(self):
        self.i += 1  # '['
        negated = False
        if self._peek() == "^":
            negated = True
            self.i += 1
        items = []
        if self._peek() == "]":
            items.append((ord("]"), ord("]")))
            self.i += 1
        while True:
            if self.i >= self.n:
                raise RegexError("正则：字符类缺少 ']'")
            if self.p[self.i] == "]":
                self.i += 1
                break
            a = self._class_atom()
            if isinstance(a, tuple):
                items.append(a)
                continue
            if self._peek() == "-" and self.i + 1 < self.n and self.p[self.i + 1] != "]":
                self.i += 1
                b = self._class_atom()
                if isinstance(b, tuple):
                    raise RegexError("正则：字符类范围端点不能是字符类")
                if ord(a) > ord(b):
                    raise RegexError("正则：字符类范围下限大于上限")
                items.append((ord(a), ord(b)))
            else:
                items.append((ord(a), ord(a)))
        return ("set", negated, items)

    # ---- 校验反向引用 ----
    def _validate(self, node):
        if not isinstance(node, tuple):
            return
        tag = node[0]
        if tag == "bref":
            num, name = node[1], node[2]
            if name is not None:
                if name not in self.names:
                    raise RegexError(f"正则：引用了未知组名 {name!r}")
            elif num is None or num > self.ngroups:
                raise RegexError(f"正则：引用了不存在的组 \\{num}")
            return
        for sub in node[1:]:
            if isinstance(sub, tuple):
                self._validate(sub)
            elif isinstance(sub, list):
                for x in sub:
                    if isinstance(x, tuple):
                        self._validate(x)


# ---------------- 匹配 ----------------
class Match:
    """一次匹配结果。caps[i] = (start, end) 或 None；caps[0] 为整体。"""

    __slots__ = ("s", "caps", "pat")

    def __init__(self, s, caps, pat):
        self.s = s
        self.caps = caps
        self.pat = pat

    @property
    def start(self):
        return self.caps[0][0]

    @property
    def end(self):
        return self.caps[0][1]

    def group(self, i=0):
        seg = self.caps[i]
        return None if seg is None else self.s[seg[0]:seg[1]]

    def groups(self):
        return [self.group(i) for i in range(1, self.pat.ngroups + 1)]


class Pattern:
    def __init__(self, nodes, ngroups, names, flags):
        self.top = nodes
        self.ngroups = ngroups
        self.names = names
        self.flags = flags

    # ---- 单点尝试 ----
    def _try(self, pos, require_end):
        self._end = -1
        self._caps = [None] * (self.ngroups + 1)

        def k(e):
            if require_end is not None and e != require_end:
                return False
            self._end = e
            return True

        if self._node(self.top, pos, k):
            return self._end
        return None

    def _node(self, nd, pos, k):
        tag = nd[0]
        if tag == "lit":
            c = nd[1]
            if pos < len(self._s) and (
                self._s[pos] == c or ((self._f & _I) and self._s[pos] == c.swapcase())
            ):
                return k(pos + 1)
            return False
        if tag == "any":
            if pos < len(self._s) and ((self._f & _S) or self._s[pos] != "\n"):
                return k(pos + 1)
            return False
        if tag == "set":
            if pos < len(self._s) and _set_matches(nd[1], nd[2], self._s[pos], self._f):
                return k(pos + 1)
            return False
        if tag == "seq":
            return self._seq(nd[1], 0, pos, k)
        if tag == "alt":
            for branch in nd[1]:
                snap = list(self._caps)
                if self._node(branch, pos, k):
                    return True
                self._caps = snap
            return False
        if tag == "flags":
            old = self._f
            self._f = nd[1]
            try:
                return self._node(nd[2], pos, k)
            finally:
                self._f = old
        if tag == "group":
            idx, node = nd[1], nd[2]
            if idx == 0:
                return self._node(node, pos, k)

            def cont(e):
                old = self._caps[idx]
                self._caps[idx] = (pos, e)
                if k(e):
                    return True
                self._caps[idx] = old
                return False

            return self._node(node, pos, cont)
        if tag == "rep":
            return self._repeat(nd[1], nd[2], nd[3], nd[4], pos, k)
        if tag == "anchor":
            return k(pos) if self._anchor(nd[1], pos) else False
        if tag == "bref":
            return self._bref(nd[1], nd[2], pos, k)
        if tag == "look":
            return self._look(nd[1], nd[2], nd[3], pos, k)
        raise RegexError(f"正则：未知节点 {tag!r}")

    def _seq(self, nodes, i, pos, k):
        if i >= len(nodes):
            return k(pos)
        return self._node(nodes[i], pos, lambda e: self._seq(nodes, i + 1, e, k))

    def _repeat(self, node, mn, mx, mode, pos, k):
        if mode == 2:  # 占有：贪婪消费且不回溯
            cnt = 0
            p = pos
            while mx < 0 or cnt < mx:
                box = {}
                if not self._node(node, p, lambda e, box=box: box.__setitem__("e", e) or True):
                    break
                e = box["e"]
                if e == p:
                    break
                p = e
                cnt += 1
            return k(p) if cnt >= mn else False

        def rec(cnt, p):
            if mode == 0:  # 贪婪：先多
                if mx < 0 or cnt < mx:
                    def more(e):
                        if e == p:
                            return k(e) if cnt + 1 >= mn else False
                        return rec(cnt + 1, e)
                    if self._node(node, p, more):
                        return True
                return k(p) if cnt >= mn else False
            # 惰性：先少
            if cnt >= mn and k(p):
                return True
            if mx < 0 or cnt < mx:
                def more(e):
                    return False if e == p else rec(cnt + 1, e)
                if self._node(node, p, more):
                    return True
            return False

        return rec(0, pos)

    def _anchor(self, kind, pos):
        s, n = self._s, len(self._s)
        if kind == "bol":
            return pos == 0 or ((self._f & _M) and s[pos - 1] == "\n")
        if kind == "eol":
            if (self._f & _M) and pos < n and s[pos] == "\n":
                return True
            return pos == n
        if kind == "bos":
            return pos == 0
        if kind == "eos":
            return pos == n
        if kind == "wb":
            return _is_boundary(s, pos)
        if kind == "nwb":
            return not _is_boundary(s, pos)
        return False

    def _bref(self, num, name, pos, k):
        gi = self.pat_index(name) if name is not None else num
        seg = self._caps[gi] if 0 <= gi < len(self._caps) else None
        if seg is None:
            return False
        text = self._s[seg[0]:seg[1]]
        end = pos + len(text)
        if end > len(self._s):
            return False
        chunk = self._s[pos:end]
        if chunk == text or ((self._f & _I) and chunk.lower() == text.lower()):
            return k(end)
        return False

    def pat_index(self, name):
        return self.names[name]

    def _look(self, sign, behind, node, pos, k):
        snap = list(self._caps)
        if not behind:
            ok = self._node(node, pos, lambda e: True)
            if sign == "=":
                return k(pos) if ok else False
            self._caps = snap
            return False if ok else k(pos)
        # 后顾：尝试所有起点 st，使 node 恰好在此结束
        for st in range(pos, -1, -1):
            if self._node(node, st, lambda e: e == pos):
                if sign == "=":
                    return k(pos)
                self._caps = snap
                return False
        self._caps = snap
        return k(pos) if sign == "!" else False

    # ---- 对外接口 ----
    def _run(self, s, pos, require_end):
        self._s = s
        self._f = self.flags
        end = self._try(pos, require_end)
        if end is None:
            return None
        self._caps[0] = (pos, end)
        return Match(s, list(self._caps), self)

    def match(self, s, pos=0):
        return self._run(s, pos, None)

    def fullmatch(self, s, pos=0):
        return self._run(s, pos, len(s))

    def search(self, s, pos=0):
        for i in range(pos, len(s) + 1):
            m = self._run(s, i, None)
            if m is not None:
                return m
        return None

    def finditer(self, s, pos=0):
        i = pos
        n = len(s)
        while i <= n:
            m = self._run(s, i, None)
            if m is None:
                i += 1
                continue
            yield m
            i = m.end + 1 if m.end == i else m.end

    def sub(self, repl, s, count=0):
        out = []
        last = 0
        for done, m in enumerate(self.finditer(s)):
            if count and done >= count:
                break
            out.append(s[last:m.start])
            out.append(_expand_repl(repl, s, m.caps, self.names))
            last = m.end
        out.append(s[last:])
        return "".join(out)

    def split(self, s, maxsplit=0):
        parts = []
        last = 0
        for done, m in enumerate(self.finditer(s)):
            if maxsplit and done >= maxsplit:
                break
            parts.append(s[last:m.start])
            for gi in range(1, self.ngroups + 1):
                parts.append(m.group(gi))
            last = m.end
        parts.append(s[last:])
        return parts


def _expand_repl(repl, s, caps, names):
    out = []
    i = 0
    n = len(repl)

    def group_text(gi):
        if 0 <= gi < len(caps) and caps[gi] is not None:
            return s[caps[gi][0]:caps[gi][1]]
        return ""

    while i < n:
        c = repl[i]
        if c == "\\" and i + 1 < n:
            nx = repl[i + 1]
            if nx.isdigit():
                j = i + 1
                num = ""
                while j < n and repl[j].isdigit() and len(num) < 2:
                    num += repl[j]
                    j += 1
                out.append(group_text(int(num)))
                i = j
                continue
            if nx in ("g", "k") and i + 2 < n and repl[i + 2] in "<{'":
                op = repl[i + 2]
                close = {"<": ">", "{": "}", "'": "'"}[op]
                j = i + 3
                name = ""
                while j < n and repl[j] != close:
                    name += repl[j]
                    j += 1
                if j < n:
                    j += 1
                if name.isdigit():
                    out.append(group_text(int(name)))
                elif name in names:
                    out.append(group_text(names[name]))
                i = j
                continue
            simple = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\"}
            out.append(simple.get(nx, nx))
            i += 2
            continue
        if c == "$" and i + 1 < n and repl[i + 1].isdigit():
            j = i + 1
            num = ""
            while j < n and repl[j].isdigit() and len(num) < 2:
                num += repl[j]
                j += 1
            out.append(group_text(int(num)))
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


@functools.lru_cache(maxsize=512)
def _compile(pattern: str, flags: int = 0) -> Pattern:
    p = _Parser(pattern, flags)
    nodes = p.parse()
    return Pattern(nodes, p.ngroups, dict(p.names), flags | 0)


def compile_regex(pattern, flags: int = 0) -> Pattern:
    if not isinstance(pattern, str):
        pattern = str(pattern)
    return _compile(pattern, flags)


# ---------------- Matha 内建（柯里化） ----------------
def _to_match_list(m: Match):
    if m is None:
        return None
    return [m.group(0)] + [m.group(i) for i in range(1, m.pat.ngroups + 1)]


def _bmatch(re, s):
    return compile_to_pattern(re).search(_as_text(s)) is not None


def compile_to_pattern(re) -> Pattern:
    return compile_regex(_as_text(re))


def _as_text(x) -> str:
    return x if isinstance(x, str) else str(x)


def _b_fullmatch(re, s):
    return compile_to_pattern(re).fullmatch(_as_text(s)) is not None


def _b_find(re, s):
    return _to_match_list(compile_to_pattern(re).search(_as_text(s)))


def _b_findall(re, s):
    return [_to_match_list(m) for m in compile_to_pattern(re).finditer(_as_text(s))]


def _b_named(re, s):
    m = compile_to_pattern(re).search(_as_text(s))
    if m is None:
        return None
    text = _as_text(s)
    out = {}
    for name, gi in m.pat.names.items():
        seg = m.caps[gi]
        out[name] = None if seg is None else text[seg[0]:seg[1]]
    return out


def _b_sub(re, repl, s):
    return compile_to_pattern(re).sub(_as_text(repl), _as_text(s))


def _b_split(re, s):
    return compile_to_pattern(re).split(_as_text(s))


def _curry2(func):
    def w1(a):
        return lambda b: func(a, b)
    return w1


def _curry3(func):
    def w1(a):
        def w2(b):
            return lambda c: func(a, b, c)
        return w2
    return w1


def _register_regex_builtins(builtins: dict) -> None:
    """把正则内建注册进解释器/VM 的 builtins 字典（柯里化，符合单参应用约定）。"""
    builtins["匹配"] = _curry2(_bmatch)
    builtins["全匹配"] = _curry2(_b_fullmatch)
    builtins["查找正则"] = _curry2(_b_find)
    builtins["查找全部"] = _curry2(_b_findall)
    builtins["命名组"] = _curry2(_b_named)
    builtins["替换正则"] = _curry3(_b_sub)
    builtins["分割正则"] = _curry2(_b_split)
