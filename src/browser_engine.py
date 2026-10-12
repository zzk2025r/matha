"""Matha 浏览器内核：HTML 解析、CSS 布局、JavaScript 引擎、排版。"""
from __future__ import annotations

import base64
import html
import json
import math
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================
# 1. DOM 树
# ============================================================

class NodeType(Enum):
    ELEMENT = 1
    TEXT = 3
    COMMENT = 8
    DOCUMENT = 9
    DOCTYPE = 10


VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img",
                 "input", "link", "meta", "param", "source",
                 "track", "wbr"}

DEFAULT_STYLE: dict[str, str] = {
    "display": "inline",
    "color": "#000000",
    "background-color": "rgba(0,0,0,0)",
    "font-size": "16px",
    "font-weight": "400",
    "font-family": "serif",
    "margin-top": "0px",
    "margin-right": "0px",
    "margin-bottom": "0px",
    "margin-left": "0px",
    "padding-top": "0px",
    "padding-right": "0px",
    "padding-bottom": "0px",
    "padding-left": "0px",
    "border-width": "0px",
    "width": "auto",
    "height": "auto",
    "text-align": "left",
    "line-height": "normal",
    "overflow": "visible",
}


@dataclass
class CSSStyle:
    """CSS 样式盒模型。"""
    props: dict[str, str] = field(default_factory=dict)

    def get(self, name: str, default: str = "") -> str:
        return self.props.get(name, DEFAULT_STYLE.get(name, default))

    def set(self, name: str, value: str) -> None:
        self.props[name] = value

    def px(self, name: str, default: float = 0.0) -> float:
        return parse_px(self.get(name, ""), default)

    def computed(self) -> dict[str, str]:
        result = dict(DEFAULT_STYLE)
        result.update(self.props)
        return result

    def copy(self) -> CSSStyle:
        return CSSStyle(dict(self.props))

    def cascade(self, other: CSSStyle) -> CSSStyle:
        merged = self.copy()
        merged.props.update(other.props)
        return merged


def parse_px(value: str, default: float = 0.0) -> float:
    if not value:
        return default
    v = value.strip().lower()
    units = {"px": 1.0, "pt": 4.0 / 3.0, "pc": 16.0,
             "in": 96.0, "cm": 37.795, "mm": 3.7795,
             "q": 0.9449, "em": 16.0, "rem": 16.0, "": 1.0}
    for u, scale in units.items():
        if v.endswith(u):
            try:
                return float(v[:len(v) - len(u)] or 0) * scale
            except ValueError:
                return default
    if v.endswith("%"):
        try:
            return float(v[:-1])
        except ValueError:
            return default
    return default


class Node:
    """DOM 节点。"""

    def __init__(self, node_type: NodeType,
                 tag: str = "", text: str = ""):
        self.node_type = node_type
        self.tag = tag
        self.text = text
        self.children: list[Node] = []
        self.parent: Node | None = None
        self.attributes: dict[str, str] = {}
        self.style = CSSStyle()
        self.computed_style: dict[str, str] = {}
        self._id = str(id(self))

    def append(self, child: Node) -> Node:
        child.parent = self
        self.children.append(child)
        return child

    def remove(self, child: Node) -> bool:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False

    def get_attribute(self, name: str,
                      default: str = "") -> str:
        return self.attributes.get(name, default)

    def set_attribute(self, name: str, value: str) -> None:
        self.attributes[name] = value

    @property
    def class_list(self) -> list[str]:
        return self.get_attribute("class", "").split()

    @property
    def id(self) -> str:
        return self.get_attribute("id")

    @property
    def inner_text(self) -> str:
        if self.node_type == NodeType.TEXT:
            return self.text
        return "".join(c.inner_text for c in self.children)

    def walk(self) -> list[Node]:
        out = [self]
        for c in self.children:
            out.extend(c.walk())
        return out

    def find_all(self, tag: str) -> list[Node]:
        return [n for n in self.walk()
                if n.node_type == NodeType.ELEMENT
                and n.tag == tag]

    def find_by_id(self, node_id: str) -> Node | None:
        for n in self.walk():
            if n.id == node_id:
                return n
        return None

    def query_selector(self, selector: str) -> Node | None:
        for n in self.walk():
            if matches_selector(n, selector):
                return n
        return None

    def query_selector_all(self, selector: str) -> list[Node]:
        return [n for n in self.walk()
                if matches_selector(n, selector)]

    def __repr__(self) -> str:
        if self.node_type == NodeType.TEXT:
            return f"Text({self.text[:20]!r})"
        return f"<{self.tag}{' ' + str(self.attributes) if self.attributes else ''}>"


def matches_selector(node: Node, selector: str) -> bool:
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        if node.node_type != NodeType.ELEMENT:
            continue
        if part.startswith("#"):
            if node.id == part[1:]:
                return True
        elif part.startswith("."):
            if part[1:] in node.class_list:
                return True
        elif part == "*" or node.tag == part.lower():
            return True
    return False


# ============================================================
# 2. HTML 解析器
# ============================================================

class HTMLTokenizer:
    """HTML 分词器。"""

    TAG_RE = re.compile(
        r"<!--(.*?)-->|<!DOCTYPE[^>]*>|"
        r"</\s*([a-zA-Z][\w:-]*)\s*>|"
        r"<\s*([a-zA-Z][\w:-]*)((?:\s+[\w:-]+"
        r"(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*)\s*"
        r"(/?)>|([^<]+)", re.S)
    ATTR_RE = re.compile(
        r"([\w:-]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+)))?")
    RAW_TEXT = {"script", "style", "textarea", "title"}

    # 遇到起始标签时自动闭合的标签
    AUTO_CLOSE = {
        "li": {"li"},
        "dt": {"dt", "dd"}, "dd": {"dt", "dd"},
        "p": {"p"},
        "td": {"td", "th"}, "th": {"td", "th"},
        "tr": {"tr", "td", "th"},
        "tbody": {"thead", "tbody", "tr", "td", "th"},
        "thead": {"thead", "tbody"},
        "option": {"option"},
        "h1": {"p"}, "h2": {"p"}, "h3": {"p"},
        "h4": {"p"}, "h5": {"p"}, "h6": {"p"},
        "div": {"p"},
    }

    def tokenize(self, source: str) -> list[tuple[str, Any]]:
        tokens: list[tuple[str, Any]] = []
        pos = 0
        while pos < len(source):
            m = self.TAG_RE.search(source, pos)
            if not m:
                break
            if m.start() > pos:
                tokens.append(("text", source[pos:m.start()]))
            if m.group(1) is not None:
                tokens.append(("comment", m.group(1)))
            elif m.group(2):
                tokens.append(("close", m.group(2).lower()))
            elif m.group(3):
                attrs = {}
                for am in self.ATTR_RE.finditer(
                        m.group(4) or ""):
                    val = (am.group(2) or am.group(3)
                           or am.group(4) or "")
                    attrs[am.group(1).lower()] = html.unescape(val)
                tokens.append(("open", (m.group(3).lower(),
                                        attrs, m.group(5) == "/")))
            elif m.group(6) is not None:
                tokens.append(("text", m.group(6)))
            pos = m.end()
        return tokens

    def parse(self, source: str) -> Node:
        doc = Node(NodeType.DOCUMENT, "#document")
        stack: list[Node] = [doc]
        tokens = self.tokenize(source)
        i = 0
        while i < len(tokens):
            kind, value = tokens[i]
            top = stack[-1]
            if kind == "text":
                if value.strip():
                    top.append(Node(NodeType.TEXT, text=value))
            elif kind == "comment":
                top.append(Node(NodeType.COMMENT, text=value))
            elif kind == "open":
                tag, attrs, self_closing = value
                closable = self.AUTO_CLOSE.get(tag, set())
                while len(stack) > 1 and stack[-1].tag in closable:
                    stack.pop()
                top = stack[-1]
                el = Node(NodeType.ELEMENT, tag=tag)
                el.attributes.update(attrs)
                top.append(el)
                if self_closing or tag in VOID_ELEMENTS:
                    pass
                elif tag in self.RAW_TEXT:
                    j = i + 1
                    raw = []
                    while j < len(tokens) and \
                            tokens[j][0] != "close":
                        raw.append(tokens[j][1])
                        j += 1
                    el.children.append(Node(
                        NodeType.TEXT,
                        text="".join(raw) if raw else ""))
                    i = j
                else:
                    stack.append(el)
            elif kind == "close":
                tag = value
                for k in range(len(stack) - 1, 0, -1):
                    if stack[k].tag == tag:
                        del stack[k:]
                        break
            i += 1
        return doc


# ============================================================
# 3. CSS 解析与层叠
# ============================================================

class CSSParser:
    """CSS 解析器。"""

    COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

    def strip_comments(self, css: str) -> str:
        return self.COMMENT_RE.sub("", css)

    def parse(self, css: str) -> list[tuple[str, CSSStyle, int]]:
        rules: list[tuple[str, CSSStyle, int]] = []
        css = self.strip_comments(css)
        i = 0
        while i < len(css):
            while i < len(css) and css[i].isspace():
                i += 1
            if i >= len(css):
                break
            start = i
            depth = 0
            while i < len(css):
                if css[i] == "{":
                    depth += 1
                    if depth == 1:
                        break
                elif css[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            selector = css[start:i].strip()
            i += 1
            body_start = i
            while i < len(css) and css[i] != "}":
                i += 1
            body = css[body_start:i]
            i += 1
            style = self.parse_declarations(body)
            specificity = self.specificity(selector)
            rules.append((selector, style, specificity))
        return rules

    def parse_declarations(self, body: str) -> CSSStyle:
        style = CSSStyle()
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            name, _, value = decl.partition(":")
            name = name.strip().lower()
            value = value.strip()
            if self.important(name, body):
                value = value.replace("!important", "").strip()
            style.set(name, value)
        return style

    def important(self, name: str, body: str) -> bool:
        return f"{name}" in body and "!important" in body

    def specificity(self, selector: str) -> int:
        ids = selector.count("#")
        classes = selector.count(".") + selector.count("[")
        tags = len(re.findall(r"(?:^|[\s>])[a-zA-Z][\w]*", selector))
        return ids * 100 + classes * 10 + tags

    def parse_inline(self, style_str: str) -> CSSStyle:
        return self.parse_declarations(style_str)


class StyleEngine:
    """样式层叠引擎。"""

    def __init__(self):
        self.rules: list[tuple[str, CSSStyle, int]] = []
        self.origin = 0

    def add_stylesheet(self, css: str,
                       origin: int = 0) -> int:
        rules = CSSParser().parse(css)
        rules = [(s, st, sp + origin) for s, st, sp in rules]
        self.rules.extend(rules)
        return len(rules)

    def resolve(self, node: Node,
                inherited: dict[str, str] | None = None
                ) -> dict[str, str]:
        computed = dict(DEFAULT_STYLE)
        computed["display"] = UA_DISPLAY.get(node.tag, "inline")
        if node.tag in ("html", "body"):
            computed["display"] = "block"
        if node.tag in ("strong", "b"):
            computed["font-weight"] = "bold"
        if node.tag in ("em", "i"):
            computed["font-style"] = "italic"
        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            computed["font-weight"] = "bold"
        if inherited:
            computed.update(inherited)
        matched = [(sp, st) for sel, st, sp in self.rules
                   if matches_selector(node, sel)]
        matched.sort(key=lambda x: x[0])
        for _, st in matched:
            computed.update(st.props)
        inline = node.get_attribute("style")
        if inline:
            computed.update(
                CSSParser().parse_inline(inline).props)
        return computed


# ============================================================
# 4. 布局引擎
# ============================================================

@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def intersects(self, o: Rect) -> bool:
        return not (self.right <= o.x or o.right <= self.x
                    or self.bottom <= o.y or o.bottom <= self.y)

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.right and \
            self.y <= y <= self.bottom

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y,
                "width": self.width, "height": self.height}


BLOCK_ELEMENTS = {"html", "body", "div", "p", "h1", "h2", "h3",
                  "h4", "h5", "h6", "ul", "ol", "li", "table",
                  "thead", "tbody", "tr", "td", "th", "form",
                  "section", "article", "header", "footer", "nav",
                  "aside", "main", "figure", "blockquote", "pre",
                  "hr", "fieldset", "dl", "dt", "dd", "video", "audio", "canvas", "svg"}

UA_DISPLAY = dict.fromkeys(BLOCK_ELEMENTS, "block")
UA_DISPLAY.update(dict.fromkeys(("img", "input", "button", "select", "textarea", "video", "canvas", "svg"), "inline-block"))
UA_DISPLAY["li"] = "list-item"

INLINE_TAGS = {"span", "a", "b", "i", "em", "strong", "code",
               "small", "big", "sub", "sup", "label", "img"}


NON_VISUAL = {"head", "style", "script", "meta", "link",
              "title", "base", "template", "noscript"}


class LayoutEngine:
    """盒模型布局引擎。"""

    def __init__(self, viewport_width: float = 1280,
                 viewport_height: float = 720,
                 font_size: float = 16.0):
        self.viewport = Rect(0, 0, viewport_width, viewport_height)
        self.font_size = font_size
        self.char_width = font_size * 0.5
        self.line_height = 1.5

    def measure_text(self, text: str,
                     font_size: float) -> float:
        return len(text) * font_size * 0.5

    def wrap_text(self, text: str, width: float,
                  font_size: float) -> list[str]:
        if width <= 0:
            return [text]
        words = text.split(" ")
        lines: list[str] = []
        cur = ""
        for w in words:
            cand = w if not cur else cur + " " + w
            if self.measure_text(cand, font_size) <= width:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    def box_model(self, style: dict[str, str],
                  content: Rect) -> Rect:
        mt = parse_px(style.get("margin-top", "0"), 0)
        mr = parse_px(style.get("margin-right", "0"), 0)
        mb = parse_px(style.get("margin-bottom", "0"), 0)
        ml = parse_px(style.get("margin-left", "0"), 0)
        bt = parse_px(style.get("border-width", "0"), 0)
        pt = parse_px(style.get("padding-top", "0"), 0)
        pr = parse_px(style.get("padding-right", "0"), 0)
        pb = parse_px(style.get("padding-bottom", "0"), 0)
        parse_px(style.get("padding-left", "0"), 0)
        return Rect(
            x=content.x - ml,
            y=content.y - mt,
            width=content.width + ml + mr + pt + pr + bt * 2,
            height=content.height + mt + mb + pt + pb + bt * 2,
        )

    def layout(self, root: Node,
               style_engine: StyleEngine | None = None
               ) -> list[tuple[Node, Rect]]:
        boxes: list[tuple[Node, Rect]] = []
        se = style_engine or StyleEngine()
        cursor = Rect(0, 0, self.viewport.width, 0)
        self._layout_node(root, se, cursor, 0, boxes)
        return boxes

    def _layout_node(self, node: Node, se: StyleEngine,
                     parent_rect: Rect, depth: int,
                     boxes: list[tuple[Node, Rect]],
                     inherited: dict[str, str] | None = None
                     ) -> None:
        if node.node_type == NodeType.DOCUMENT:
            cur = Rect(0, 0, self.viewport.width, 0)
            for c in node.children:
                self._layout_node(c, se, cur, depth, boxes,
                                  inherited)
            return
        if node.node_type != NodeType.ELEMENT:
            return
        if node.tag in NON_VISUAL:
            return
        style = se.resolve(node, inherited)
        node.computed_style = style
        display = style.get("display", "inline")
        if display == "none":
            return
        fs = parse_px(style.get("font-size", "16"), 16)
        lh = fs * self.line_height

        if node.tag in ("br",):
            parent_rect.y += lh
            return

        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            fs = {"h1": 32, "h2": 24, "h3": 18.72,
                  "h4": 16, "h5": 13.28, "h6": 10.72}.get(node.tag, 16)
            fs = fs
            lh = fs * 1.2

        explicit_w = style.get("width", "auto")
        w = (parent_rect.width if explicit_w == "auto"
             else parse_px(explicit_w, parent_rect.width))
        explicit_h = style.get("height", "auto")

        text = node.inner_text.strip() if not node.children else ""
        if text and not any(c.node_type == NodeType.ELEMENT
                            for c in node.children):
            lines = self.wrap_text(text, w, fs)
            content_h = len(lines) * lh
        elif node.tag == "img":
            content_h = parse_px(style.get("height", "150"),
                                 fs * 4)
        else:
            content_h = 0.0

        content = Rect(parent_rect.x, parent_rect.y, w, content_h)
        border = self.box_model(style, content)
        boxes.append((node, border))

        if display == "block" and node.children:
            has_element = any(c.node_type == NodeType.ELEMENT
                              for c in node.children)
            if not has_element:
                content.height = content_h or lh
            else:
                inner = Rect(content.x, content.y, w, 0)
                for c in node.children:
                    before = inner.y
                    self._layout_node(c, se, inner, depth + 1,
                                      boxes, style)
                    if c.node_type == NodeType.ELEMENT and \
                            c.tag not in INLINE_TAGS:
                        inner.y = max(inner.y, before) + lh * 0.3
                content.height = inner.y - content.y
            if explicit_h != "auto":
                content.height = parse_px(explicit_h, content.height)
            border = self.box_model(style, content)
            for i, (n, _) in enumerate(boxes):
                if n is node:
                    boxes[i] = (node, border)
                    break

        mb = parse_px(style.get("margin-bottom", "0"), 0)
        parent_rect.y = border.bottom + mb


# ============================================================
# 5. JavaScript 引擎
# ============================================================

class JSValue:
    """JS 值。"""

    def __init__(self, value: Any = None,
                 vtype: str = "undefined"):
        self.value = value
        self.type = vtype

    def __repr__(self) -> str:
        return f"JSValue({self.type}: {self.value!r})"

    def to_python(self) -> Any:
        if self.type == "number":
            try:
                return int(self.value)
            except (ValueError, TypeError):
                return float(self.value)
        if self.type == "boolean":
            return bool(self.value)
        if self.type == "null":
            return None
        return self.value

    def to_js(self, v: Any) -> JSValue:
        if v is None:
            return JSValue(None, "null")
        if isinstance(v, bool):
            return JSValue(v, "boolean")
        if isinstance(v, (int, float)):
            return JSValue(v, "number")
        if isinstance(v, str):
            return JSValue(v, "string")
        if isinstance(v, list):
            return JSValue(v, "array")
        if isinstance(v, dict):
            return JSValue(v, "object")
        return JSValue(v, "function")


class JSObject:
    """JS 对象。"""

    def __init__(self, class_name: str = "Object"):
        self.class_name = class_name
        self.properties: dict[str, JSValue] = {}
        self.prototype: JSObject | None = None
        self.methods: dict[str, Callable] = {}

    def set(self, key: str, value: Any) -> None:
        self.properties[key] = JSValue().to_js(value)

    def get(self, key: str) -> Any:
        if key in self.properties:
            return self.properties[key].to_python()
        if key in self.methods:
            return self.methods[key]
        if self.prototype:
            return self.prototype.get(key)
        return None

    def has(self, key: str) -> bool:
        return (key in self.properties or key in self.methods
                or (self.prototype is not None
                    and self.prototype.has(key)))

    def call(self, key: str, *args: Any) -> Any:
        fn = self.get(key)
        if callable(fn):
            return fn(*args)
        raise TypeError(f"{key} is not a function")

    def __repr__(self) -> str:
        return f"JSObject({self.class_name}, {list(self.properties)})"


@dataclass
class ASTNode:
    """JS 抽象语法树节点。"""
    type: str = ""
    value: Any = None
    children: list[ASTNode] = field(default_factory=list)


class JSToken(Enum):
    NUMBER = "number"
    STRING = "string"
    IDENT = "identifier"
    KEYWORD = "keyword"
    OPERATOR = "operator"
    PUNCTUATION = "punctuation"
    EOF = "eof"


@dataclass
class Token:
    type: JSToken = JSToken.EOF
    value: str = ""
    line: int = 0


class JSLexer:
    """JS 词法分析器。"""

    KEYWORDS = {"var", "let", "const", "function", "return", "if",
                "else", "for", "while", "do", "break", "continue",
                "new", "this", "true", "false", "null", "undefined",
                "typeof", "delete", "in", "of", "try", "catch",
                "finally", "throw", "class", "extends", "switch",
                "case", "default"}

    def tokenize(self, source: str) -> list[Token]:
        tokens: list[Token] = []
        i, line = 0, 1
        n = len(source)
        while i < n:
            c = source[i]
            if c == "\n":
                line += 1
                i += 1
                continue
            if c in " \t\r":
                i += 1
                continue
            if source.startswith("//", i):
                j = source.find("\n", i)
                i = n if j < 0 else j
                continue
            if source.startswith("/*", i):
                j = source.find("*/", i + 2)
                i = n if j < 0 else j + 2
                continue
            if c in "\"'":
                quote, buf, i = c, [], i + 1
                while i < n and source[i] != quote:
                    if source[i] == "\\" and i + 1 < n:
                        esc = source[i + 1]
                        buf.append({"n": "\n", "t": "\t",
                                    "r": "\r"}.get(esc, esc))
                        i += 2
                        continue
                    buf.append(source[i])
                    i += 1
                i += 1
                tokens.append(Token(JSToken.STRING,
                                    "".join(buf), line))
                continue
            if c.isdigit() or (c == "." and i + 1 < n
                               and source[i + 1].isdigit()):
                j = i
                while j < n and (source[j].isdigit()
                                 or source[j] in ".eE"
                                 or (source[j] in "+-"
                                     and source[j - 1] in "eE")):
                    j += 1
                tokens.append(Token(JSToken.NUMBER,
                                    source[i:j], line))
                i = j
                continue
            if c.isalpha() or c in "_$":
                j = i
                while j < n and (source[j].isalnum()
                                 or source[j] in "_$"):
                    j += 1
                word = source[i:j]
                tokens.append(Token(
                    JSToken.KEYWORD if word in self.KEYWORDS
                    else JSToken.IDENT, word, line))
                i = j
                continue
            for op in ("===", "!==", "==", "!=", "<=", ">=",
                       "&&", "||", "=>", "++", "--", "+=", "-=",
                       "*=", "/=", "**", "??", "?."):
                if source.startswith(op, i):
                    tokens.append(Token(JSToken.OPERATOR, op, line))
                    i += len(op)
                    break
            else:
                if c in "{}()[];,:":
                    tokens.append(Token(JSToken.PUNCTUATION, c, line))
                else:
                    tokens.append(Token(JSToken.OPERATOR, c, line))
                i += 1
        tokens.append(Token(JSToken.EOF, "", line))
        return tokens


class JSParser:
    """JS 语法分析器（递归下降）。"""

    def __init__(self, source: str):
        self.tokens = JSLexer().tokenize(source)
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, value: str) -> Token:
        t = self.next()
        if t.value != value:
            raise SyntaxError(
                f"第{t.line}行: 期望 {value!r}, "
                f"实际 {t.value!r}")
        return t

    def accept(self, value: str) -> bool:
        if self.peek().value == value:
            self.pos += 1
            return True
        return False

    def parse(self) -> ASTNode:
        body: list[ASTNode] = []
        while self.peek().type != JSToken.EOF:
            body.append(self.statement())
        return ASTNode("Program", None, body)

    def statement(self) -> ASTNode:
        t = self.peek()
        if t.value in ("var", "let", "const"):
            self.next()
            decls: list[ASTNode] = []
            while True:
                name = self.next()
                init = (self.expression()
                        if self.accept("=") else None)
                decls.append(ASTNode(
                    "VariableDeclarator", name.value, [init]
                    if init else []))
                if not self.accept(","):
                    break
            self.accept(";")
            return ASTNode("VariableDeclaration", t.value, decls)
        if t.value == "function":
            self.next()
            name = self.next().value
            params = self.params()
            body = self.block()
            return ASTNode("FunctionDecl", name,
                           [ASTNode("Params", None, params), body])
        if t.value == "return":
            self.next()
            arg = (None if self.peek().value in (";", "}")
                   else self.expression())
            self.accept(";")
            return ASTNode("ReturnStatement", None,
                           [arg] if arg else [])
        if t.value == "if":
            self.next()
            self.expect("(")
            test = self.expression()
            self.expect(")")
            cons = self.statement()
            alt = (self.statement()
                   if self.accept("else") else None)
            return ASTNode("IfStatement", None,
                           [test, cons] + ([alt] if alt else []))
        if t.value == "for":
            self.next()
            self.expect("(")
            if self.peek().value in ("var", "let", "const"):
                kind = self.next().value
                name = self.next().value
                if self.peek().value == "in":
                    self.next()
                    obj = self.expression()
                    self.expect(")")
                    body = self.statement()
                    return ASTNode("ForInStatement", name,
                                   [obj, body, kind])
                self.accept("=")
                init_val = self.expression()
                init = ASTNode("VariableDeclaration", kind, [
                    ASTNode("VariableDeclarator", name, [init_val])])
                self.expect(";")
                test = (None if self.peek().value == ";"
                        else self.expression())
                self.expect(";")
                update = (None if self.peek().value == ")"
                          else self.expression())
                self.expect(")")
                body = self.statement()
                return ASTNode("LoopStatement", "for", [init, test,
                                                         update, body])
            init = (self.expression()
                    if not self.accept(";") else None)
            self.expect(";")
            test = (None if self.peek().value == ";"
                    else self.expression())
            self.expect(";")
            update = (None if self.peek().value == ")"
                      else self.expression())
            self.expect(")")
            body = self.statement()
            return ASTNode("LoopStatement", "for",
                           [x for x in (init, test, update, body)
                            if x])
        if t.value == "while":
            self.next()
            self.expect("(")
            test = self.expression()
            self.expect(")")
            body = self.statement()
            return ASTNode("LoopStatement", "while", [test, body])
        if t.value == "{":
            return self.block()
        expr = self.expression()
        self.accept(";")
        return ASTNode("ExpressionStatement", None, [expr])

    def params(self) -> list[ASTNode]:
        self.expect("(")
        params: list[ASTNode] = []
        if not self.accept(")"):
            while True:
                params.append(ASTNode("Param", self.next().value))
                if not self.accept(","):
                    break
            self.expect(")")
        return params

    def block(self) -> ASTNode:
        self.expect("{")
        body: list[ASTNode] = []
        while self.peek().value != "}":
            if self.peek().type == JSToken.EOF:
                raise SyntaxError("未闭合的代码块")
            body.append(self.statement())
        self.expect("}")
        return ASTNode("BlockStatement", None, body)

    def expression(self) -> ASTNode:
        left = self.assignment()
        while self.peek().value in (",",):
            self.next()
            right = self.assignment()
            left = ASTNode("SequenceExpression", None, [left, right])
        return left

    def assignment(self) -> ASTNode:
        left = self.conditional()
        if self.peek().value in ("=", "+=", "-=", "*=", "/="):
            op = self.next().value
            right = self.assignment()
            return ASTNode("AssignmentExpression", op, [left, right])
        return left

    def conditional(self) -> ASTNode:
        test = self.binary(0)
        if self.accept("?"):
            cons = self.assignment()
            self.expect(":")
            alt = self.assignment()
            return ASTNode("ConditionalExpression", None,
                           [test, cons, alt])
        return test

    PRECEDENCE = [
        ("||", "??", "&&"),
        ("==", "!=", "===", "!=="),
        ("<", ">", "<=", ">=", "instanceof", "in"),
        ("+", "-"),
        ("*", "/", "%"),
    ]

    def binary(self, level: int) -> ASTNode:
        if level >= len(self.PRECEDENCE):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek().value in self.PRECEDENCE[level]:
            op = self.next().value
            right = self.binary(level + 1)
            left = ASTNode("BinaryExpression", op, [left, right])
        return left

    def unary(self) -> ASTNode:
        t = self.peek()
        if t.value in ("!", "-", "+", "typeof", "++", "--"):
            self.next()
            return ASTNode("UnaryExpression", t.value,
                           [self.unary()])
        if t.value == "new":
            self.next()
            callee = self.member()
            args: list[ASTNode] = []
            if self.accept("("):
                args = self.arguments()
            return ASTNode("NewExpression", callee.value, args)
        return self.postfix()

    def member(self) -> ASTNode:
        expr = self.primary()
        while True:
            if self.accept("."):
                prop = self.next().value
                expr = ASTNode("MemberExpression", prop, [expr])
            elif self.accept("["):
                prop = self.expression()
                self.expect("]")
                expr = ASTNode("MemberExpression", None, [expr, prop])
            elif self.accept("("):
                args = self.arguments()
                expr = ASTNode("CallExpression", expr.value,
                               [expr] + args)
            else:
                return expr

    def postfix(self) -> ASTNode:
        expr = self.member()
        if self.peek().value in ("++", "--"):
            op = self.next().value
            expr = ASTNode("UpdateExpression", op, [expr])
        return expr

    def primary(self) -> ASTNode:
        t = self.next()
        if t.type == JSToken.NUMBER:
            v = float(t.value)
            if v.is_integer() and "." not in t.value \
                    and "e" not in t.value.lower():
                v = int(v)
            return ASTNode("Literal", v)
        if t.type == JSToken.STRING:
            return ASTNode("Literal", t.value)
        if t.value in ("true", "false"):
            return ASTNode("Literal", t.value == "true")
        if t.value in ("null", "undefined"):
            return ASTNode("Literal", None)
        if t.value == "this":
            return ASTNode("Identifier", "this")
        if t.value == "function":
            name = "anonymous"
            if self.peek().type == JSToken.IDENT:
                name = self.next().value
            params = self.params()
            body = self.block()
            return ASTNode("FunctionExpr", name,
                           [ASTNode("Params", None, params), body])
        if t.value == "[":
            items: list[ASTNode] = []
            while self.peek().value != "]":
                if self.accept(","):
                    continue
                items.append(self.assignment())
            self.expect("]")
            return ASTNode("ArrayLiteral", None, items)
        if t.value == "{":
            props: list[ASTNode] = []
            while self.peek().value != "}":
                key = self.next()
                if self.accept(":"):
                    props.append(ASTNode(
                        "Property", key.value,
                        [self.assignment()]))
                else:
                    props.append(ASTNode("Property", key.value, []))
                if not self.accept(","):
                    break
            self.expect("}")
            return ASTNode("ObjectLiteral", None, props)
        if t.value == "(":
            expr = self.expression()
            self.expect(")")
            return expr
        if t.type in (JSToken.IDENT, JSToken.KEYWORD):
            return ASTNode("Identifier", t.value)
        raise SyntaxError(f"第{t.line}行: 意外记号 {t.value!r}")

    def arguments(self) -> list[ASTNode]:
        args: list[ASTNode] = []
        if not self.accept(")"):
            while True:
                args.append(self.assignment())
                if not self.accept(","):
                    break
            self.expect(")")
        return args


class JSInterpreter:
    """JS 树遍历解释器。"""

    MAX_DEPTH = 200

    def __init__(self):
        self.global_env: dict[str, Any] = {}
        self.console: list[str] = []
        self.call_stack: list[str] = []
        self._install_builtins()

    def _anon(self, params: list[ASTNode], body: ASTNode,
              closure: dict[str, Any], fname: str) -> Callable:
        def fn(*args: Any) -> Any:
            if len(self.call_stack) >= self.MAX_DEPTH:
                raise RecursionError("调用栈溢出")
            fenv = dict(closure)
            for i, p in enumerate(params):
                fenv[p.value] = args[i] if i < len(args) else None
            self.call_stack.append(fname)
            try:
                return self.execute_block(body.children, fenv)
            finally:
                self.call_stack.pop()
        return fn

    def _install_builtins(self) -> None:
        self.global_env["undefined"] = None
        self.global_env["NaN"] = float("nan")
        self.global_env["Infinity"] = float("inf")
        math_obj = JSObject("Math")
        for k, v in {
            "PI": math.pi, "E": math.e, "LN2": math.log(2),
            "SQRT2": math.sqrt(2), "LN10": math.log(10),
        }.items():
            math_obj.set(k, v)
        for name, fn in {
            "abs": abs, "floor": math.floor, "ceil": math.ceil,
            "sqrt": math.sqrt, "pow": lambda b, e: b ** e,
            "min": min, "max": max, "round": round,
            "log": math.log, "exp": math.exp, "sin": math.sin,
            "cos": math.cos, "tan": math.tan, "atan": math.atan,
            "atan2": math.atan2, "sign": lambda x: (x > 0) - (x < 0),
            "trunc": math.trunc, "hypot": math.hypot,
            "random": lambda: __import__("random").random(),
        }.items():
            math_obj.methods[name] = fn
        self.global_env["Math"] = math_obj
        json_obj = JSObject("JSON")
        json_obj.methods["stringify"] = json.dumps
        json_obj.methods["parse"] = json.loads
        self.global_env["JSON"] = json_obj
        arr_obj = JSObject("Array")
        arr_obj.methods["isArray"] = lambda v: isinstance(v, list)
        self.global_env["Array"] = arr_obj
        self.global_env["parseInt"] = lambda s, b=10: int(str(s), b)
        self.global_env["parseFloat"] = float
        self.global_env["isNaN"] = lambda v: isinstance(v, float) \
            and math.isnan(v)
        self.global_env["String"] = str
        self.global_env["Number"] = float

    def log(self, *args: Any) -> None:
        self.console.append(" ".join(
            str(a) if not isinstance(a, str) else a
            for a in args))

    def run(self, source: str) -> Any:
        ast = JSParser(source).parse()
        scope: dict[str, Any] = {}
        r = self.execute_block(ast.children, scope)
        self.global_env.update(scope)
        return r

    def execute_block(self, body: list[ASTNode],
                      env: dict[str, Any]) -> Any:
        local = env
        result = None
        for stmt in body:
            r = self.execute(stmt, local)
            if isinstance(r, tuple) and r and r[0] == "return":
                return r[1]
        return result

    def execute(self, node: ASTNode | None,
                env: dict[str, Any]) -> Any:
        if node is None:
            return None
        if node.type == "VariableDeclaration":
            for d in node.children:
                val = (self.execute(d.children[0], env)
                       if d.children else None)
                env[d.value] = val
            return None
        if node.type == "FunctionDecl":
            params = node.children[0].children
            body = node.children[1]
            env[node.value] = self._anon(
                params, body, env, node.value)
            return None
        if node.type == "ExpressionStatement":
            return self.evaluate(node.children[0], env)
        if node.type == "ReturnStatement":
            val = (self.evaluate(node.children[0], env)
                   if node.children else None)
            return ("return", val)
        if node.type == "BlockStatement":
            return self.execute_block(node.children, env)
        if node.type == "IfStatement":
            test = self.evaluate(node.children[0], env)
            if self.truthy(test):
                return self.execute(node.children[1], env)
            if len(node.children) > 2:
                return self.execute(node.children[2], env)
            return None
        if node.type == "ForInStatement":
            obj = self.evaluate(node.children[0], env)
            body = node.children[1]
            if isinstance(obj, JSObject):
                keys = list(obj.properties)
            elif isinstance(obj, dict):
                keys = list(obj)
            elif isinstance(obj, (list, str)):
                keys = list(range(len(obj)))
            else:
                keys = []
            for k in keys:
                env[node.value] = k
                r = self.execute(body, env)
                if isinstance(r, tuple) and r[0] == "return":
                    return r
            return None
        if node.type == "LoopStatement":
            kind = node.value
            if kind == "while":
                guard = 0
                while self.truthy(
                        self.evaluate(node.children[0], env)):
                    r = self.execute(node.children[1], env)
                    if isinstance(r, tuple) and r[0] == "return":
                        return r
                    guard += 1
                    if guard > 1_000_000:
                        raise RuntimeError("死循环")
                return None
            init, test, update, body = node.children
            self.execute(init, env)
            guard = 0
            while self.truthy(self.evaluate(test, env)):
                r = self.execute(body, env)
                if isinstance(r, tuple) and r[0] == "return":
                    return r
                self.evaluate(update, env)
                guard += 1
                if guard > 1_000_000:
                    raise RuntimeError("死循环")
            return None
        return self.evaluate(node, env)

    def truthy(self, v: Any) -> bool:
        if v is None or v is False:
            return False
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v != ""
        return True

    def evaluate(self, node: ASTNode,
                 env: dict[str, Any]) -> Any:
        t = node.type
        if t == "Literal":
            return node.value
        if t == "Identifier":
            if node.value in env:
                return env[node.value]
            if node.value in self.global_env:
                return self.global_env[node.value]
            if node.value == "console":
                return {"log": lambda *a: self.log(*a),
                        "error": lambda *a: self.log(*a),
                        "warn": lambda *a: self.log(*a)}
            raise NameError(f"{node.value} 未定义")
        if t == "BinaryExpression":
            return self.binary_op(
                node.value,
                self.evaluate(node.children[0], env),
                self.evaluate(node.children[1], env))
        if t == "UnaryExpression":
            v = self.evaluate(node.children[0], env)
            op = node.value
            if op == "!":
                return not self.truthy(v)
            if op == "-":
                return -v
            if op == "+":
                return +v
            if op == "typeof":
                return self.typeof(v)
            if op in ("++", "--"):
                cur = v if isinstance(v, (int, float)) else 0
                return cur + 1 if op == "++" else cur - 1
        if t == "UpdateExpression":
            base = self.evaluate(node.children[0], env)
            new = base + 1 if node.value == "++" else base - 1
            self.assign_to(node.children[0], new, env)
            return new if node.value == "++" else base
        if t == "LogicalExpression":
            left = self.evaluate(node.children[0], env)
            if node.value == "&&":
                return (self.evaluate(node.children[1], env)
                        if self.truthy(left) else left)
            if node.value == "||":
                return (left if self.truthy(left)
                        else self.evaluate(node.children[1], env))
            return (left if left is not None
                    else self.evaluate(node.children[1], env))
        if t == "ConditionalExpression":
            return (self.evaluate(node.children[1], env)
                    if self.truthy(
                        self.evaluate(node.children[0], env))
                    else self.evaluate(node.children[2], env))
        if t == "AssignmentExpression":
            value = self.evaluate(node.children[1], env)
            op = node.value
            if op != "=":
                cur = self.evaluate(node.children[0], env)
                value = self.binary_op(op[0], cur, value)
            self.assign_to(node.children[0], value, env)
            return value
        if t == "MemberExpression":
            obj = self.evaluate(node.children[0], env)
            if node.value is not None:
                key = node.value
            else:
                key = self.evaluate(node.children[1], env)
            if isinstance(obj, JSObject):
                if not obj.has(key):
                    raise TypeError(f"属性 {key} 不存在")
                return obj.get(key)
            if isinstance(obj, dict):
                if key not in obj:
                    raise TypeError(f"属性 {key} 不存在")
                return obj[key]
            if isinstance(obj, (list, str)):
                idx = int(key)
                if idx >= len(obj):
                    raise TypeError("索引越界")
                return obj[idx]
            raise TypeError("无法读取属性")
        if t == "CallExpression":
            return self.call(node, env)
        if t == "NewExpression":
            ctor = self.global_env.get(node.value)
            if isinstance(ctor, type):
                return ctor()
            if callable(ctor):
                return ctor()
            return JSObject(node.value or "Object")
        if t == "ArrayLiteral":
            return [self.evaluate(c, env) for c in node.children]
        if t == "ObjectLiteral":
            obj: dict[str, Any] = {}
            for prop in node.children:
                if prop.children:
                    obj[prop.value] = self.evaluate(
                        prop.children[0], env)
                else:
                    fn_env = dict(env)
                    params = prop.value
                    body = node
                    obj[prop.value] = self._anon(
                        [], body, fn_env, prop.value)
            return obj
        if t == "FunctionExpr":
            params = node.children[0].children
            body = node.children[1]
            return self._anon(params, body, env, node.value)
        if t == "SequenceExpression":
            r = None
            for c in node.children:
                r = self.evaluate(c, env)
            return r
        return None

    def typeof(self, v: Any) -> str:
        if v is None:
            return "undefined"
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, (int, float)):
            return "number"
        if isinstance(v, str):
            return "string"
        if callable(v):
            return "function"
        return "object"

    def binary_op(self, op: str, a: Any, b: Any) -> Any:
        try:
            if op == "+":
                if isinstance(a, str) or isinstance(b, str):
                    return f"{a}{b}"
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return a / b
            if op == "%":
                return a % b
            if op == "**":
                return a ** b
            if op in ("==", "==="):
                if isinstance(a, (int, float)) and \
                        isinstance(b, (int, float)):
                    return a == b
                if op == "===":
                    return a is b or type(a) is type(b) and a == b
                return a == b
            if op in ("!=", "!=="):
                r = self.binary_op(
                    "==" if op == "!=" else "===", a, b)
                return not r
            if op == "<":
                return a < b
            if op == ">":
                return a > b
            if op == "<=":
                return a <= b
            if op == ">=":
                return a >= b
        except TypeError:
            return None
        return None

    def assign_to(self, target: ASTNode, value: Any,
                  env: dict[str, Any]) -> None:
        if target.type == "Identifier":
            env[target.value] = value
            return
        if target.type == "MemberExpression":
            obj = self.evaluate(target.children[0], env)
            key = (target.value if target.value is not None
                   else self.evaluate(target.children[1], env))
            if isinstance(obj, JSObject):
                obj.set(key, value)
            elif isinstance(obj, dict):
                obj[key] = value
            elif isinstance(obj, list):
                obj[int(key)] = value
            return
        raise TypeError("非法赋值目标")

    def call(self, node: ASTNode, env: dict[str, Any]) -> Any:
        callee_node = node.children[0]
        args = [self.evaluate(a, env) for a in node.children[1:]]
        name = callee_node.value
        if callee_node.type == "MemberExpression":
            obj = self.evaluate(callee_node.children[0], env)
            if name == "log":
                return self.log(*args)
            if isinstance(obj, JSObject):
                if obj.has(name):
                    fn = obj.get(name)
                    if callable(fn):
                        return fn(*args)
            if isinstance(obj, dict) and name in obj:
                fn = obj[name]
                if callable(fn):
                    return fn(*args)
                return fn
            if isinstance(obj, str):
                if name == "toUpperCase":
                    return obj.upper()
                if name == "toLowerCase":
                    return obj.lower()
                if name == "split":
                    return obj.split(args[0]) if args else list(obj)
                if name == "trim":
                    return obj.strip()
                if name == "charAt":
                    i = int(args[0]) if args else 0
                    return obj[i] if i < len(obj) else ""
                if name == "indexOf":
                    return obj.find(args[0])
                if name == "slice":
                    return obj[args[0]:args[1] if len(args) > 1 else None]
                if name == "replace":
                    return obj.replace(args[0], args[1])
                if name == "concat":
                    return obj + (args[0] if args else "")
                if name == "repeat":
                    return obj * int(args[0])
                if name == "padStart":
                    return obj.rjust(int(args[0]),
                                     (args[1] if len(args) > 1 else " ")[0])
                if name == "includes":
                    return args[0] in obj
            if isinstance(obj, list):
                if name in ("push", "pop", "shift", "unshift",
                            "splice", "reverse", "sort", "fill"):
                    if name == "push":
                        obj.append(args[0]) if args else None
                        return len(obj)
                    if name == "pop":
                        return obj.pop() if obj else None
                    if name == "shift":
                        return obj.pop(0) if obj else None
                    if name == "unshift":
                        obj.insert(0, args[0])
                        return len(obj)
                    if name == "reverse":
                        obj.reverse()
                        return obj
                    if name == "sort":
                        obj.sort()
                        return obj
                    if name == "fill":
                        obj[:] = [args[0]] * len(obj)
                        return obj
                if name == "join":
                    sep = args[0] if args else ","
                    return sep.join(str(x) for x in obj)
                if name == "slice":
                    return obj[args[0]:args[1] if len(args) > 1 else None]
                if name == "indexOf":
                    return (obj.index(args[0])
                            if args[0] in obj else -1)
                if name == "includes":
                    return args[0] in obj
                if name == "map":
                    fn = args[0]
                    return [fn(x) for x in obj]
                if name == "filter":
                    fn = args[0]
                    return [x for x in obj if fn(x)]
                if name == "reduce":
                    fn, acc = args[0], (
                        args[1] if len(args) > 1 else None)
                    for x in obj:
                        acc = fn(acc, x)
                    return acc
                if name == "forEach":
                    for x in obj:
                        args[0](x)
                    return None
                if name == "concat":
                    return obj + (args[0] or [])
                if name in ("length",):
                    return len(obj)
            if name == "toString" or name == "valueOf":
                return str(obj)
            if name == "hasOwnProperty":
                return args[0] in (obj
                                   if isinstance(obj, dict) else [])
            raise TypeError(f"{name} 不是函数")
        fn = None
        if name in env:
            fn = env[name]
        elif name in self.global_env:
            fn = self.global_env[name]
        if fn is None:
            raise ReferenceError(f"{name} 未定义")
        if not callable(fn):
            return fn
        return fn(*args)


# ============================================================
# 6. 排版与绘制
# ============================================================

@dataclass
class TextRun:
    text: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    font_size: float = 16.0
    color: str = "#000000"
    font_weight: str = "400"
    font_family: str = "serif"

    @property
    def bbox(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.font_size)


class Painter:
    """绘制器（软件光栅化）。"""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.framebuffer: list[list[tuple[int, int, int]]] = [
            [(255, 255, 255) for _ in range(width)]
            for _ in range(height)]
        self.draw_calls = 0

    def parse_color(self, css: str) -> tuple[int, int, int, int]:
        css = (css or "").strip()
        if css.startswith("#"):
            h = css[1:]
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            if len(h) == 6:
                return (int(h[0:2], 16), int(h[2:4], 16),
                        int(h[4:6], 16), 255)
        if css.startswith("rgba"):
            nums = css[css.find("(") + 1:css.rfind(")")]
            p = [float(x) for x in nums.split(",")]
            while len(p) < 4:
                p.append(255.0)
            if max(p) <= 1.0 and len(p) == 4 and \
                    any(c.isdigit() or c == "." for c in
                            [nums.split(",")[3].strip()[:1]]) is not None:
                pass
            return (int(p[0]), int(p[1]), int(p[2]), int(p[3]))
        named = {"black": (0, 0, 0, 255), "white": (255, 255, 255, 255),
                 "red": (255, 0, 0, 255), "green": (0, 128, 0, 255),
                 "blue": (0, 0, 255, 255), "yellow": (255, 255, 0, 255),
                 "gray": (128, 128, 128, 255),
                 "silver": (192, 192, 192, 255),
                 "navy": (0, 0, 128, 255), "orange": (255, 165, 0, 255)}
        return named.get(css.lower(), (0, 0, 0, 255))

    def clear(self, color: str = "#ffffff") -> None:
        r, g, b, _ = self.parse_color(color)
        self.framebuffer = [[(r, g, b) for _ in range(self.width)]
                            for _ in range(self.height)]
        self.draw_calls = 0

    def fill_rect(self, rect: Rect, color: str) -> int:
        r, g, b, a = self.parse_color(color)
        if a == 0:
            return 0
        x0 = max(0, int(rect.x))
        y0 = max(0, int(rect.y))
        x1 = min(self.width, int(math.ceil(rect.right)))
        y1 = min(self.height, int(math.ceil(rect.bottom)))
        alpha = a / 255.0
        for y in range(y0, y1):
            row = self.framebuffer[y]
            for x in range(x0, x1):
                if alpha >= 1.0:
                    row[x] = (r, g, b)
                else:
                    or_, og, ob = row[x]
                    row[x] = (
                        int(or_ * (1 - alpha) + r * alpha),
                        int(og * (1 - alpha) + g * alpha),
                        int(ob * (1 - alpha) + b * alpha))
        self.draw_calls += 1
        return (x1 - x0) * (y1 - y0)

    def draw_text(self, run: TextRun) -> int:
        cw = run.font_size * 0.5
        ch = run.font_size
        r, g, b, _ = self.parse_color(run.color)
        bold = 1 if str(run.font_weight) in ("bold", "700", "800",
                                             "900") else 0
        x0 = int(run.x)
        for ci, _ in enumerate(run.text):
            bx = x0 + ci * cw
            by = int(run.y)
            xa = max(0, int(bx))
            ya = max(0, by)
            xb = min(self.width, int(bx + cw) + bold)
            yb = min(self.height, int(by + ch))
            for y in range(ya, yb):
                for x in range(xa, xb):
                    on = ((x - bx) % 3 != 0) or (y - by) % 5 < 3
                    if on and (x - bx) < cw - 0.5 + bold:
                        self.framebuffer[y][x] = (r, g, b)
        self.draw_calls += 1
        return len(run.text)

    def stroke_rect(self, rect: Rect, color: str,
                    width: int = 1) -> int:
        total = 0
        total += self.fill_rect(
            Rect(rect.x, rect.y, rect.width, width), color)
        total += self.fill_rect(
            Rect(rect.x, rect.bottom - width,
                 rect.width, width), color)
        total += self.fill_rect(
            Rect(rect.x, rect.y, width, rect.height), color)
        total += self.fill_rect(
            Rect(rect.right - width, rect.y,
                 width, rect.height), color)
        return total

    def to_ppm(self) -> bytes:
        out = bytearray()
        out += f"P6\n{self.width} {self.height}\n255\n".encode()
        for row in self.framebuffer:
            for px in row:
                out += bytes(px)
        return bytes(out)

    def to_png_b64(self) -> str:
        import zlib
        raw = bytearray()
        for row in self.framebuffer:
            raw.append(0)
            for px in row:
                raw += bytes(px)

        def chunk(tag: bytes, data: bytes) -> bytes:
            c = tag + data
            return (len(data).to_bytes(4, "big") + c
                    + zlib.crc32(c).to_bytes(4, "big"))
        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", self.width.to_bytes(4, "big")
                     + self.height.to_bytes(4, "big")
                     + bytes([8, 2, 0, 0, 0]))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        png += chunk(b"IEND", b"")
        return base64.b64encode(png).decode()


class Renderer:
    """渲染器：DOM + CSS + 布局 + 绘制。"""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.painter = Painter(width, height)
        self.layout_engine = LayoutEngine(width, height)
        self.style = StyleEngine()
        self.dom: Node | None = None
        self.boxes: list[tuple[Node, Rect]] = []
        self.text_runs: list[TextRun] = []
        self.scripts: list[str] = []

    def load(self, html_source: str) -> Node:
        self.dom = HTMLTokenizer().parse(html_source)
        for node in self.dom.walk():
            if node.node_type == NodeType.ELEMENT and \
                    node.tag == "style":
                self.style.add_stylesheet(node.inner_text, 10)
            elif node.node_type == NodeType.ELEMENT and \
                    node.tag == "script":
                self.scripts.append(node.inner_text)
        return self.dom

    def layout(self) -> list[tuple[Node, Rect]]:
        if self.dom is None:
            self.dom = Node(NodeType.DOCUMENT)
        self.boxes = self.layout_engine.layout(self.dom, self.style)
        self._build_text_runs()
        return self.boxes

    def _build_text_runs(self) -> None:
        self.text_runs = []
        for node, rect in self.boxes:
            if node.node_type != NodeType.ELEMENT:
                continue
            if node.tag in NON_VISUAL:
                continue
            st = node.computed_style or {}
            text = node.inner_text.strip()
            if not text:
                continue
            if any(c.node_type == NodeType.ELEMENT
                   for c in node.children):
                continue
            fs = parse_px(st.get("font-size", "16"), 16)
            lines = self.layout_engine.wrap_text(text, rect.width, fs)
            lh = fs * self.layout_engine.line_height
            for i, line in enumerate(lines):
                self.text_runs.append(TextRun(
                    text=line,
                    x=rect.x + 4,
                    y=rect.y + 4 + i * lh,
                    width=self.layout_engine.measure_text(line, fs),
                    font_size=fs,
                    color=st.get("color", "#000000"),
                    font_weight=st.get("font-weight", "400"),
                    font_family=st.get("font-family", "serif"),
                ))

    def paint(self) -> bytes:
        self.painter.clear("#ffffff")
        for node, rect in self.boxes:
            if node.node_type != NodeType.ELEMENT:
                continue
            if node.tag in NON_VISUAL:
                continue
            st = node.computed_style or {}
            bg = st.get("background-color", "")
            if bg and bg != "rgba(0,0,0,0)":
                self.painter.fill_rect(rect, bg)
            bw = parse_px(st.get("border-width", "0"), 0)
            if bw > 0:
                bc = st.get("border-color", st.get("color", "#000000"))
                self.painter.stroke_rect(rect, bc, int(bw))
        for run in self.text_runs:
            self.painter.draw_text(run)
        return self.painter.to_ppm()

    def hit_test(self, x: float, y: float) -> Node | None:
        for node, rect in reversed(self.boxes):
            if rect.contains(x, y):
                return node
        return None

    def render(self, html_source: str) -> dict[str, Any]:
        self.load(html_source)
        self.layout()
        pixels = self.paint()
        return {
            "boxes": len(self.boxes),
            "text_runs": len(self.text_runs),
            "draw_calls": self.painter.draw_calls,
            "ppm_bytes": len(pixels),
            "scripts": len(self.scripts),
            "nodes": len(self.dom.walk()) if self.dom else 0,
        }


class BrowserEngine:
    """浏览器引擎。"""

    def __init__(self, width: int = 1280, height: int = 720):
        self.renderer = Renderer(width, height)
        self.interpreter = JSInterpreter()
        self.history: list[str] = []
        self.cache: dict[str, str] = {}
        self.tabs: list[dict[str, Any]] = []
        self.dom_storage: dict[str, dict[str, str]] = {}
        self.session_storage: dict[str, str] = {}
        self.cookies: dict[str, str] = {}
        self.user_agent = ("Mozilla/5.0 (Matha; VirtualCodeEngine) "
                           "MathaBrowser/4.5")
        self._lock = threading.Lock()

    def navigate(self, url: str,
                 html_source: str = "") -> dict[str, Any]:
        if html_source:
            self.cache[url] = html_source
        source = self.cache.get(url, html_source)
        if not source:
            return {"url": url, "error": "无内容"}
        stats = self.renderer.render(source)
        self.history.append(url)
        console: list[str] = []
        for js in self.renderer.scripts:
            try:
                self.interpreter.run(js)
            except Exception as e:
                console.append(f"JS错误: {e}")
        stats.update({
            "url": url,
            "console": self.interpreter.console[-20:],
            "errors": console,
            "history_depth": len(self.history),
        })
        return stats

    def evaluate_js(self, source: str) -> dict[str, Any]:
        try:
            result = self.interpreter.run(source)
            return {"ok": True, "result": result,
                    "console": self.interpreter.console[-10:]}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def set_storage(self, key: str, value: str) -> bool:
        self.dom_storage.setdefault("default", {})[key] = value
        return True

    def get_storage(self, key: str) -> str | None:
        return self.dom_storage.get("default", {}).get(key)

    def set_cookie(self, name: str, value: str) -> bool:
        self.cookies[name] = value
        return True

    def new_tab(self, url: str = "about:blank") -> int:
        self.tabs.append({"url": url, "title": "新标签页",
                          "active": len(self.tabs) == 0})
        return len(self.tabs) - 1

    def get_stats(self) -> dict[str, Any]:
        return {
            "tabs": len(self.tabs),
            "history": len(self.history),
            "cache_entries": len(self.cache),
            "cookies": len(self.cookies),
            "draw_calls": self.renderer.painter.draw_calls,
        }


def create_browser_engine(width: int = 1280,
                          height: int = 720) -> BrowserEngine:
    return BrowserEngine(width, height)


def create_html_parser() -> HTMLTokenizer:
    return HTMLTokenizer()


def create_css_parser() -> CSSParser:
    return CSSParser()


def create_layout_engine(width: float = 1280,
                         height: float = 720) -> LayoutEngine:
    return LayoutEngine(width, height)


def create_js_interpreter() -> JSInterpreter:
    return JSInterpreter()


def create_renderer(width: int = 1280,
                    height: int = 720) -> Renderer:
    return Renderer(width, height)


# ============================================================
# 内置注册
# ============================================================

def _register_browser(builtins: dict) -> None:
    builtins["创建浏览器内核"] = create_browser_engine
    builtins["创建HTML解析器"] = create_html_parser
    builtins["创建CSS解析器"] = create_css_parser
    builtins["创建布局引擎"] = create_layout_engine
    builtins["创建JS解释器"] = create_js_interpreter
    builtins["创建渲染器"] = create_renderer


def _browser_names() -> list[str]:
    return ["创建浏览器内核", "创建HTML解析器", "创建CSS解析器",
            "创建布局引擎", "创建JS解释器", "创建渲染器"]


__all__ = [
    "NodeType", "Node", "CSSStyle", "Rect", "TextRun",
    "HTMLTokenizer", "CSSParser", "StyleEngine",
    "LayoutEngine", "Painter", "Renderer",
    "JSValue", "JSObject", "ASTNode", "JSToken", "Token",
    "JSLexer", "JSParser", "JSInterpreter",
    "BrowserEngine",
    "create_browser_engine", "create_html_parser",
    "create_css_parser", "create_layout_engine",
    "create_js_interpreter", "create_renderer",
    "_register_browser", "_browser_names",
]
