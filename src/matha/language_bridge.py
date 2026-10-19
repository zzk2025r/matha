"""Matha 语言桥（Language Bridge）— 吞噬式成长的语言级扩展

吞噬式成长三阶段（语言级）：
  1. 吞噬 (devour)  — 按语言提取函数定义（签名/类型/副作用/文档），
                      理解其它语言的结构
  2. 转化 (convert) — 函数体为单一表达式时用内置表达式直译器翻译为
                      Matha 表达式；无法直译时用『无中生有』模板生成
                      带元数据的骨架（保证 API 面完整进入 Matha 世界）
  3. 融合 (fuse)    — 生成的 Matha 模块用 Matha parser 自验证后写入
                      matha/generated/

支持语言：rust / go / js / c / python

使用方式：
  from src.matha.language_bridge import LanguageBridge
  bridge = LanguageBridge()
  record = bridge.devour('rust', rust_source, 'my_module')
  bridge.fuse(record)          # 验证 + 写文件
"""
from __future__ import annotations

import ast as pyast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from src import features

logger = logging.getLogger(__name__)

# 生成模块输出目录（项目根/matha/generated）
_OUT_DIR = Path(__file__).parent.parent.parent / "matha" / "generated"


# ============================================================
#  记录结构
# ============================================================

@dataclass
class FunctionSig:
    """转化后的 Matha 函数签名与函数体。"""
    name: str
    params: list = field(default_factory=list)      # [(名, 类型或'')]
    ret: str = ""                                   # 返回类型（'' → 发射 Value）
    body: str = ""                                  # Matha 表达式（正文）
    doc: str = ""                                   # 来源文档/注释
    effects: str = ""                               # 副作用标注（pure/io/...）
    generated: bool = False                         # True = 无中生有模板生成
    origin: str = ""                                # 原语言定义（调试）


@dataclass
class DevourRecord:
    """一次吞噬操作的完整记录。"""
    lang: str
    module_name: str
    functions: list = field(default_factory=list)   # [FunctionSig]
    matha_source: str = ""                          # 生成的 Matha 模块源码
    steps: list = field(default_factory=list)       # 吞噬步骤（调试用）
    success: bool = True
    error: str = ""
    verified: bool = False                          # fuse 时通过 parser 验证
    written: str | None = None                   # 写入的文件路径

    def summary(self) -> str:
        status = "✓" if self.success else "✗"
        n_full = sum(1 for f in self.functions if not f.generated)
        n_gen = sum(1 for f in self.functions if f.generated)
        return (f"[{status}] 吞噬 {self.lang}:{self.module_name} → "
                f"{n_full} 个完整函数 + {n_gen} 个无中生有骨架")


# ============================================================
#  统一表达式直译器（递归下降 → Matha 表达式）
# ============================================================

_TOKEN_RE = re.compile(r"""
    (?P<num>\d+\.\d+|\d+)                     |
    (?P<name>[A-Za-z_\u4e00-\u9fff]\w*)       |
    (?P<op>\*\*|//|==|!=|<=|>=|&&|\|\||[-+*/%^<>?:!,()]) |
    (?P<str>"[^"]*"|'[^']*')
""", re.VERBOSE)

# 运算符 → Matha
_OP_MAP = {"**": "^", "^": "^", "==": "=", "!=": "≠",
           "&&": "and", "||": "or"}
# 常用数学函数名（各语言 → Matha 内建）。
# Matha 内建与 Python **同名**（实测 解释器 + MBC-VM 双端可用：sqrt/sin/cos/tan/
# exp/log/log10/ln/abs/floor/ceil/pow/atan/asin/acos/atan2/round/hypot/sum），
# 故绝大多数无需映射。此前整表写作 `func_xxx`，而 `func_*` 全库不存在 —— 直译
# 出来的函数体一调用数学函数就报「未定义函数 func_abs」。现只保留真正需要改名的项。
# `max`/`min` Matha 无可用同名内建，**不入表**（保持原名透传，不再制造假名）。
_FN_MAP = {"fabs": "abs"}

# Matha 侧（解释器 / MBC-VM / 原生）**都**没有的 Python 内建：调用点一旦直译，
# 运行期必然报「未定义函数」。与其产出「能解析但跑不起来」的代码，不如整个表达式
# 不可译，回落到无中生有骨架（宁可不译，不可错译）。
# 每一项均在解释器 + MBC-VM 两端实测确认名字未定义。
# 注：`range` 目前解释器无、VM 仅 1 参、原生仅 2 参 —— 三端语义尚未统一，故一并
# 拒绝；待运行时把 `range` 补齐为四端一致后再放行（见迁移方案「待办」）。
_UNAVAILABLE_FNS = frozenset({
    "enumerate", "zip", "map", "filter", "sorted", "reversed", "any", "all",
    "isinstance", "dict", "set", "tuple", "iter", "next", "open", "hash",
    "divmod", "repr", "id", "input", "range",
})

# Python 复合赋值运算符 → Matha 运算符（语句块直译用）
_PY_AUG_OPS = {pyast.Add: "+", pyast.Sub: "-", pyast.Mult: "*", pyast.Div: "/",
               pyast.Mod: "%", pyast.Pow: "^", pyast.FloorDiv: "//"}


def matha_expr(source: str) -> str | None:
    """将外部语言的单个表达式翻译为 Matha 表达式；失败返回 None。"""
    # 输入规范化：list/tuple → 空格连接的字符串
    if isinstance(source, (list, tuple)):
        source = " ".join(str(x) for x in source)
    elif source is not None and not isinstance(source, str):
        source = str(source)
    if not source:
        return None
    tokens = []
    pos = 0
    for m in _TOKEN_RE.finditer(source):
        if m.start() != pos and source[pos:m.start()].strip():
            return None  # 存在无法识别的片段
        pos = m.end()
        if m.lastgroup == "num":
            tokens.append(("num", m.group()))
        elif m.lastgroup == "name":
            tokens.append(("name", m.group()))
        elif m.lastgroup == "op":
            tokens.append(("op", m.group()))
        elif m.lastgroup == "str":
            tokens.append(("str", m.group()))
    if not tokens or pos != len(source.rstrip("; ")):
        # 尾部分号容忍
        if pos < len(source) and source[pos:].strip(" ;"):
            return None

    idx = [0]

    def peek():
        return tokens[idx[0]] if idx[0] < len(tokens) else (None, None)

    def take():
        tok = peek()
        idx[0] += 1
        return tok

    def atom() -> str | None:
        kind, val = take()
        if kind == "num":
            return val
        if kind == "str":
            return '"' + val.strip('"\'') + '"'
        if kind == "name":
            if val == "true":
                return "真"
            if val == "false":
                return "假"
            nxt_kind, nxt = peek()
            if nxt_kind == "op" and nxt == "(":
                take()
                args = []
                if not (peek() == ("op", ")")):
                    args.append(expr())
                    while peek() == ("op", ","):
                        take()
                        args.append(expr())
                if peek() != ("op", ")"):
                    return None
                take()
                return f"{_FN_MAP.get(val, val)}({', '.join(args)})"
            return val
        if kind == "op" and val == "(":
            inner = expr()
            if inner is None or peek() != ("op", ")"):
                return None
            take()
            return f"({inner})"
        if kind == "op" and val == "-":
            inner = atom()
            return f"-{inner}" if inner else None
        if kind == "op" and val == "!":
            inner = atom()
            return f"not {inner}" if inner else None
        return None

    def power() -> str | None:
        base = atom()
        if base is None:
            return None
        if peek() == ("op", "^") or peek() == ("op", "**"):
            take()
            exp = power()
            if exp is None:
                return None
            return f"{base} ^ {exp}"
        return base

    def binary(next_fn, ops) -> str | None:
        left = next_fn()
        if left is None:
            return None
        while True:
            kind, val = peek()
            if kind == "op" and val in ops:
                take()
                right = next_fn()
                if right is None:
                    return None
                left = f"({left} {_OP_MAP.get(val, val)} {right})"
            else:
                return left

    def multiplicative():
        return binary(power, ("*", "/", "%"))

    def additive():
        return binary(multiplicative, ("+", "-"))

    def comparison():
        return binary(additive, ("<", ">", "<=", ">=", "==", "!="))

    def logical():
        return binary(comparison, ("&&", "||"))

    def expr() -> str | None:
        cond = logical()
        if cond is None:
            return None
        if peek() == ("op", "?"):
            take()
            then = expr()
            if then is None or peek() != ("op", ":"):
                return None
            take()
            other = expr()
            if other is None:
                return None
            return f"{cond} ? {then} : {other}"
        return cond

    result = expr()
    if result is None or idx[0] != len(tokens):
        return None
    return result


# ============================================================
#  各语言函数发现模式
# ============================================================

# (名字, 参数串, 返回类型, 函数体) — 函数体允许一层嵌套花括号
_BODY = r"([^{}]*(?:\{[^{}]*\}[^{}]*)*)"

_FUNC_PATTERNS = {
    "rust": re.compile(
        rf"fn\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?:->\s*(?P<ret>[^\{{]+?))?\s*\{{(?P<body>{_BODY})\}}", re.DOTALL),
    "go": re.compile(
        rf"func\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?:\((?P<retp>[^)]*)\)|(?P<ret>[^\{{]+?))?\s*\{{(?P<body>{_BODY})\}}", re.DOTALL),
    "js": re.compile(
        rf"function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?::\s*(?P<ret>[\w\[\]<>| ]+))?\s*\{{(?P<body>{_BODY})\}}", re.DOTALL),
    "c": re.compile(
        rf"(?P<ret>\w[\w\s\*]*?)\s+\**(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*\{{(?P<body>{_BODY})\}}", re.DOTALL),
}


def _params_from_str(lang: str, params_str: str, ret_str: str) -> list:
    """各语言参数串 → [(名, Matha 类型)]。"""
    params = []
    _T = {"i32": "Int", "i64": "Int", "u32": "Int", "u64": "Int", "usize": "Int",
          "isize": "Int", "f32": "Float", "f64": "Float", "float": "Float",
          "double": "Float", "int": "Int", "bool": "Bool", "Bool": "Bool",
          "String": "String", "str": "String", "string": "String",
          "number": "Float", "any": "", "char": "String"}
    for raw in params_str.split(","):
        raw = raw.strip().replace("&", "").replace("*", "").replace("mut ", "").strip()
        if not raw:
            continue
        parts = raw.replace(":", " ").split()
        if lang == "go" and len(parts) >= 2:
            name, typ = parts[0], parts[-1]
        elif lang == "c":
            name, typ = parts[-1], (parts[0] if len(parts) >= 2 else "")
        else:  # rust / js: name 或 name: Type
            name = parts[0]
            typ = parts[1] if len(parts) >= 2 and "=" not in parts[1] else ""
            if "=" in raw:  # js 默认参数
                name = raw.split("=")[0].replace(":", " ").split()[0]
                typ = ""
        # go 共享类型: "a, b float64" 由调用侧预处理
        params.append((name, _T.get(typ, typ if typ in ("Int", "Float", "Bool", "String") else "")))
    return params


# ============================================================
#  语言桥主体
# ============================================================

def _sanitize_ident(name: str) -> str:
    """Matha 标识符清洗：不能以下划线/数字开头。"""
    name = re.sub(r"^[_0-9]+", "", name)
    return name or "fn"


class LanguageBridge:
    """语言桥：吞噬 / 转化 / 融合其它语言。"""

    _EXT_LANG = {
        ".rs": "rust", ".go": "go", ".js": "js", ".ts": "js",
        ".c": "c", ".h": "c", ".py": "python",
    }
    _FRONTENDS = {
        "rust": ("src.multi_lang_frontend", "RustFrontend"),
        "go": ("src.multi_lang_frontend", "GoFrontend"),
        "js": ("src.multi_lang_frontend", "JSFrontend"),
        "c": ("src.multi_lang_frontend", "CFrontend"),
    }

    def __init__(self, out_dir: Path | None = None):
        self._out_dir = Path(out_dir) if out_dir else _OUT_DIR

    # ------------------------------------------------------------------
    # 对外主入口
    # ------------------------------------------------------------------

    def devour(self, lang: str, source: str, module_name: str) -> DevourRecord:
        """吞噬一段外部语言源码，转化为 Matha 模块。"""
        lang = lang.lower()
        steps = [f"吞噬 {lang} 源码 {len(source)} 字符 → 模块 {module_name}"]
        try:
            if lang == "python":
                functions, py_steps = self._devour_python(source)
            elif lang in _FUNC_PATTERNS:
                functions, py_steps = self._devour_foreign(lang, source)
            else:
                return DevourRecord(lang, module_name, [], "", steps,
                                    success=False, error=f"不支持的语言: {lang}")
            steps.extend(py_steps)
            matha_src = self._emit_module(module_name, functions, lang)
            steps.append(f"生成 Matha 模块 {len(matha_src)} 字符")
            record = DevourRecord(lang, module_name, functions, matha_src, steps)
            logger.info(f"  [语言桥] {record.summary()}")
            return record
        except Exception as ex:
            logger.warning(f"  [语言桥] 吞噬失败: {ex}")
            return DevourRecord(lang, module_name, [], "", steps,
                                success=False, error=str(ex))

    def devour_file(self, path: str | Path, module_name: str | None = None) -> DevourRecord:
        """吞噬一个外部语言源文件（按扩展名识别语言）。"""
        p = Path(path)
        if not p.exists():
            return DevourRecord("?", p.stem, [], "", [f"文件不存在: {path}"],
                                success=False, error="文件不存在")
        lang = self._EXT_LANG.get(p.suffix.lower(), "")
        source = p.read_text(encoding="utf-8")
        return self.devour(lang, source, module_name or p.stem)

    def fuse(self, record: DevourRecord, write: bool = True) -> bool:
        """融合：验证生成的 Matha 模块（parser 自检），可选写入 generated/ 目录。"""
        if not record.success:
            return False
        from src.parser import parse
        try:
            parse(record.matha_source)
            record.verified = True
            record.steps.append("Matha parser 验证通过")
        except Exception as ex:
            record.success = False
            record.error = f"生成代码未通过 Matha parser 验证: {ex}"
            record.steps.append(record.error)
            logger.warning(f"  [语言桥] {record.error}")
            return False

        if write:
            self._out_dir.mkdir(parents=True, exist_ok=True)
            out = self._out_dir / f"{record.module_name}.matha"
            out.write_text(record.matha_source, encoding="utf-8")
            record.written = str(out)
            record.steps.append(f"已写入 {out}")
        logger.info(f"  [语言桥] 融合完成: {record.module_name}")
        return True

    # ------------------------------------------------------------------
    # 吞噬：外部语言（rust / go / js / c）
    # ------------------------------------------------------------------

    def _devour_foreign(self, lang: str, source: str) -> tuple[list, list]:
        """函数发现 → 表达式直译 / 无中生有。前端用于『理解』（类型+副作用）。"""
        types, effects, steps = {}, {}, []
        # 理解：借用既有前端做类型推断与副作用分析（失败不影响转化）
        if lang in self._FRONTENDS:
            import importlib
            mod_path, cls_name = self._FRONTENDS[lang]
            try:
                frontend = getattr(importlib.import_module(mod_path), cls_name)()
                types.update(frontend.infer_types(source) or {})
                effects.update(frontend.analyze_effects(source) or {})
                steps.append(f"理解: 前端 {cls_name} 类型 {len(types)} 项, 副作用 {len(effects)} 项")
            except Exception as ex:
                steps.append(f"理解: 前端辅助分析跳过 ({ex})")

        functions = []
        for m in _FUNC_PATTERNS[lang].finditer(source):
            fname = m.group("name")
            params_str = m.group("params")
            ret_raw = (m.groupdict().get("ret") or m.groupdict().get("retp") or "").strip()
            body = m.group("body")
            if lang == "c":
                ret = {"int": "Int", "float": "Float", "double": "Float",
                       "bool": "Bool", "void": ""}.get(ret_raw.strip(), "")
            else:
                ret = self._map_type(ret_raw)
            params = _params_from_str(lang, params_str, ret_raw)

            body_expr = self._body_to_expr(body)
            doc = self._preceding_doc(source, m.start())
            if body_expr is not None:
                functions.append(FunctionSig(
                    name=fname, params=params, ret=ret, body=body_expr,
                    doc=doc, effects=effects.get(fname, ""),
                    origin=f"{lang} fn {fname}"))
                steps.append(f"  {fname}: 直译 → {body_expr}")
            else:
                functions.append(FunctionSig(
                    name=fname, params=params, ret=ret,
                    body=f'抛出错误("无中生有骨架: {fname} 体内含控制流, 需补全")',
                    doc=doc, effects=effects.get(fname, ""), generated=True,
                    origin=f"{lang} fn {fname} (体未直译)"))
                steps.append(f"  {fname}: 无中生有骨架")
        return functions, steps

    def _map_type(self, typ: str) -> str:
        """外部类型名 → Matha 类型名。"""
        return {"i32": "Int", "i64": "Int", "u32": "Int", "u64": "Int",
                "usize": "Int", "isize": "Int", "int": "Int",
                "f32": "Float", "f64": "Float", "float": "Float",
                "double": "Float", "number": "Float", "bool": "Bool",
                "String": "String", "str": "String", "string": "String",
                }.get(typ.strip().strip("()").split(",")[0].strip(), "")

    def _body_to_expr(self, body: str) -> str | None:
        """函数体 → Matha 表达式：优先单一表达式/return，否则翻译 if/else 控制流。"""
        text = body.strip()
        simple = text.rstrip(";").strip()
        m = re.fullmatch(r"return\s+(.+)", simple, re.DOTALL)
        if m:
            simple = m.group(1).strip()
        if (simple and ";" not in simple and "{" not in simple and "}" not in simple
                and not re.search(r"\b(if|for|while|let|var|const|match|switch|loop)\b", simple)):
            direct = matha_expr(simple)
            if direct is not None:
                return direct
        return self._foreign_stmts_to_expr(text)

    def _foreign_stmts_to_expr(self, text: str) -> str | None:
        """外部语言语句块 → 单一 Matha 表达式（return / if-else / 局部绑定）。

        支持：return、if/else（含提前返回）、let/var/const/= 局部绑定。循环等
        仍返回 None → 交由无中生有骨架。
        """
        text = text.strip()
        while text.endswith(";"):
            text = text[:-1].strip()
        if not text:
            return None
        m = re.match(r"return\b(.*)$", text, re.DOTALL)
        if m:
            expr = m.group(1).strip().rstrip(";").strip()
            return matha_expr(expr) if expr else "null"
        if re.match(r"if\b", text):
            return self._foreign_if_to_expr(text)
        for pat in (r"(?:let|var|const)\s+(?P<name>\w+)(?:\s*:\s*[\w\[\]<>|,\s]+?)?\s*=\s*(?P<val>[^;]+);\s*(?P<rest>.+)$",
                    r"(?P<name>\w+)\s*:=\s*(?P<val>[^;]+);\s*(?P<rest>.+)$",
                    r"(?P<name>\w+)\s*=\s*(?P<val>[^;]+);\s*(?P<rest>.+)$"):
            bm = re.match(pat, text, re.DOTALL)
            if bm:
                val = matha_expr(bm.group("val").strip())
                inner = self._foreign_stmts_to_expr(bm.group("rest"))
                if val is not None and inner is not None:
                    return f"let {_sanitize_ident(bm.group('name'))} = {val} in {inner}"
                return None
        if "{" not in text and "}" not in text:
            return matha_expr(text)
        return None

    def _foreign_if_to_expr(self, text: str) -> str | None:
        """外部语言 if/else（含提前返回）→ Matha 三元表达式。"""
        rest = text[2:].lstrip()
        if rest.startswith("("):
            depth, end = 0, -1
            for i, ch in enumerate(rest):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end < 0:
                return None
            cond_text, rest = rest[1:end], rest[end + 1:].lstrip()
        else:
            j = rest.find("{")
            if j < 0:
                return None
            cond_text, rest = rest[:j], rest[j:]
        cond = matha_expr(cond_text.strip())
        if cond is None:
            return None
        then_block, after = self._take_brace_block(rest.lstrip())
        if then_block is None:
            return None
        then = self._foreign_stmts_to_expr(then_block)
        if then is None:
            return None
        after = after.strip()
        if after.startswith("else"):
            tail = after[4:].lstrip()
            if tail.startswith("if"):
                other = self._foreign_if_to_expr(tail)
                if other is None:
                    return None
                after = ""
            elif tail.startswith("{"):
                eb, after = self._take_brace_block(tail)
                other = self._foreign_stmts_to_expr(eb) if eb is not None else None
                if other is None:
                    return None
                after = after.strip()
            else:
                return None
        elif after:
            other = self._foreign_stmts_to_expr(after)   # 提前 return：后续为 else 分支
            after = ""
            if other is None:
                return None
        else:
            return None
        if after:
            return None
        return f"{cond} ? {then} : {other}"

    @staticmethod
    def _take_brace_block(s: str):
        """取出起始的花括号块，返回 (块内容, 剩余文本)；失败返回 (None, s)。"""
        if not s.startswith("{"):
            return None, s
        depth = 0
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[1:i], s[i + 1:]
        return None, s

    def _preceding_doc(self, source: str, pos: int) -> str:
        """提取函数定义前的注释作为文档。"""
        head = source[:pos].rstrip()
        for pat in (r"(?://[!/]?|#)(.*)$", r"/\*\*(.*?)\*/", r"/\*(.*?)\*/"):
            matches = re.findall(pat, head, re.DOTALL | re.MULTILINE)
            if matches:
                text = matches[-1].strip() if isinstance(matches[-1], str) else matches[-1][0].strip()
                if text and not text.startswith("=="):
                    return text.split("\n")[0].strip()
                break
        return ""

    # ------------------------------------------------------------------
    # 吞噬：Python 路径（ast 提取 + 表达式翻译 + 无中生有模板）
    # ------------------------------------------------------------------

    def _devour_python(self, source: str) -> tuple[list, list]:
        """吞噬 Python 源码：提取函数签名，算术体直接翻译，其余无中生有。"""
        tree = pyast.parse(source)
        doc = (pyast.get_docstring(tree) or "").split("\n")[0]
        steps = [f"Python ast 解析: {len(tree.body)} 个顶层节点" +
                 (f", 模块: {doc}" if doc else "")]

        functions = []
        for node in tree.body:
            if not isinstance(node, (pyast.FunctionDef, pyast.AsyncFunctionDef)):
                continue
            params = [(_sanitize_ident(a.arg), self._py_ann_to_matha(a.annotation))
                      for a in node.args.args if a.arg not in ("self", "cls")]
            ret = self._py_ann_to_matha(node.returns)
            body_expr = self._py_body_to_expr(node)
            block_body = None
            if body_expr is None and features.scoped_blocks():
                # SCOPED_BLOCKS 开启：控制流体可译为语句块（局部绑定 + 循环）
                block_body = self._py_body_to_block(node)
            fdoc = (pyast.get_docstring(node) or "").split("\n")[0]
            if body_expr is not None:
                functions.append(FunctionSig(
                    name=node.name, params=params, ret=ret, body=body_expr,
                    doc=fdoc, origin=f"python def {node.name}"))
                steps.append(f"  {node.name}: 直译 → {body_expr}")
            elif block_body is not None:
                functions.append(FunctionSig(
                    name=_sanitize_ident(node.name), params=params, ret=ret,
                    body=block_body, doc=fdoc,
                    origin=f"python def {node.name} (语句块直译)"))
                steps.append(f"  {node.name}: 语句块直译 → {block_body}")
            else:
                functions.append(FunctionSig(
                    name=_sanitize_ident(node.name), params=params, ret=ret,
                    body=f'抛出错误("无中生有骨架: {node.name} 来自 Python, 需补全")',
                    doc=fdoc, generated=True,
                    origin=f"python def {node.name} (体未直译)"))
                steps.append(f"  {node.name}: 无中生有骨架")
        return functions, steps

    def _py_ann_to_matha(self, ann) -> str:
        """Python 类型注解 → Matha 类型名。"""
        if ann is None:
            return ""
        name = getattr(ann, "id", None) or getattr(ann, "attr", None)
        if name is None and isinstance(ann, pyast.Constant):
            name = str(ann.value)
        return {"int": "Int", "float": "Float", "str": "String",
                "bool": "Bool", "list": "List", "dict": "Dict"}.get(
                    str(name).lower(), "")

    def _py_body_to_expr(self, fn: pyast.FunctionDef) -> str | None:
        """函数体（单一表达式 / 局部绑定 / if-return 控制流）→ Matha 表达式。"""
        stmts = [s for s in fn.body
                 if not (isinstance(s, pyast.Expr) and isinstance(s.value, pyast.Constant))]
        return self._py_stmts_to_expr(stmts)

    def _py_body_to_block(self, fn: pyast.FunctionDef) -> str | None:
        """函数体 → Matha 代码块体 `{ ... }`（局部绑定 / if 语句 / while / for 循环）。

        仅在 `SCOPED_BLOCKS` 开启时使用。结构为「语句序列 + 末尾表达式（隐式返回）」，
        末尾 `return X` 直接作为块的尾表达式；其余位置的 `return`/`break`/`continue`
        译为同名语句。限制：`raise`、方法调用等仍返回 None → 交由无中生有骨架。
        """
        stmts = [s for s in fn.body
                 if not (isinstance(s, pyast.Expr) and isinstance(s.value, pyast.Constant))]
        if not stmts:
            return None
        last = stmts[-1]
        body_stmts = stmts
        if isinstance(last, pyast.Return):
            tail = "null" if last.value is None else self._py_expr(last.value)
            body_stmts = stmts[:-1]
        elif isinstance(last, pyast.Expr):
            tail = self._py_expr(last.value)
            body_stmts = stmts[:-1]
        else:
            tail = "null"
        if tail is None:
            return None
        lines: list[str] = []
        for s in body_stmts:
            sub = self._py_stmt_lines(s, 1, in_loop=False)
            if sub is None:
                return None
            lines.extend(sub)
        lines.append("  " + tail)
        return "{\n" + "\n".join(lines) + "\n}"

    def _py_block_lines(self, stmts: list, ind: int, in_loop: bool) -> list[str] | None:
        """语句列表（if / loop 体）→ Matha 行列表；含不支持的语句则返回 None。"""
        out: list[str] = []
        for s in stmts:
            sub = self._py_stmt_lines(s, ind, in_loop)
            if sub is None:
                return None
            out.extend(sub)
        return out

    def _py_stmt_lines(self, stmt, ind: int, in_loop: bool) -> list[str] | None:
        """Python 语句 → Matha 代码块内的行列表（不含尾部换行）。

        支持：单目标赋值、复合赋值、`return`、`break`、`continue`、if/else 语句、
        while、for。
        """
        pad = "  " * ind
        if isinstance(stmt, pyast.Pass):
            return []
        if isinstance(stmt, pyast.Expr) and isinstance(stmt.value, pyast.Constant):
            return []                                   # 文档串 / 裸常量 → 忽略
        if isinstance(stmt, pyast.Assign) and stmt.targets:
            val = self._py_expr(stmt.value)
            if val is None:
                return None
            targets = stmt.targets
            if len(targets) > 1:
                # 链式赋值 `a = b = v`：先写最右目标，其余逐个取其值，
                # 避免 v 被重复求值（副作用 / 开销）。
                if not all(isinstance(t, pyast.Name) for t in targets):
                    return None
                names = [_sanitize_ident(t.id) for t in reversed(targets)]
                return [f"{pad}{names[0]} = {val}"] + \
                       [f"{pad}{n} = {names[0]}" for n in names[1:]]
            t0 = targets[0]
            if isinstance(t0, pyast.Name):
                return [f"{pad}{_sanitize_ident(t0.id)} = {val}"]
            if isinstance(t0, (pyast.Tuple, pyast.List)):
                # 元组解包 `a, b = expr` → Matha `(a, b) = expr`。
                # 解包右侧必须是 Matha **元组** `(…)`：`(a, b) = [1, 2]` 解释器
                # 不认（未定义变量 'a'），故字面量元组单独渲染，不走列表分支。
                if not t0.elts or not all(isinstance(e, pyast.Name) for e in t0.elts):
                    return None
                if isinstance(stmt.value, pyast.Tuple):
                    parts = [self._py_expr(e) for e in stmt.value.elts]
                    if len(parts) != len(t0.elts) or any(p is None for p in parts):
                        return None
                    val = "(" + ", ".join(parts) + ")"
                names = ", ".join(_sanitize_ident(e.id) for e in t0.elts)
                return [f"{pad}({names}) = {val}"]
            if isinstance(t0, pyast.Subscript):
                # 下标赋值 `xs[i] = v` → 原地更新内建 mut_set_at（解释器/VM 双端可用）
                if not isinstance(t0.value, pyast.Name):
                    return None
                base = _sanitize_ident(t0.value.id)
                idx = self._py_expr(t0.slice)
                if idx and val:
                    return [f"{pad}mut_set_at({base}, {idx}, {val})"]
            return None
        if isinstance(stmt, pyast.AugAssign) and isinstance(stmt.target, pyast.Name):
            op = _PY_AUG_OPS.get(type(stmt.op))
            val = self._py_expr(stmt.value)
            if op is None or val is None:
                return None
            n = _sanitize_ident(stmt.target.id)
            return [f"{pad}{n} = {n} {op} {val}"]
        if isinstance(stmt, pyast.Return):
            val = "null" if stmt.value is None else self._py_expr(stmt.value)
            if val is None:
                return None
            return [f"{pad}return {val}"]
        if isinstance(stmt, pyast.Break):
            return [f"{pad}break"]
        if isinstance(stmt, pyast.Continue):
            return [f"{pad}continue"]
        if isinstance(stmt, pyast.If):
            cond = self._py_expr(stmt.test)
            if cond is None:
                return None
            out = [f"{pad}if {cond} {{"]
            then = self._py_block_lines(stmt.body, ind + 1, in_loop)
            if then is None:
                return None
            out.extend(then)
            if stmt.orelse:
                out.append(f"{pad}}} else {{")
                other = self._py_block_lines(stmt.orelse, ind + 1, in_loop)
                if other is None:
                    return None
                out.extend(other)
            out.append(f"{pad}}}")
            return out
        if isinstance(stmt, pyast.While):
            if stmt.orelse:
                # while-else / for-else 的 else 在「未 break」时执行，需要 break
                # 标记位；Matha 亦无对应语法。此前**静默丢弃** else 分支 → 直接
                # 产出语义错误的代码，改为拒绝直译，交由无中生有骨架。
                return None
            cond = self._py_expr(stmt.test)
            if cond is None:
                return None
            body = self._py_block_lines(stmt.body, ind + 1, True)
            if body is None:
                return None
            return [f"{pad}while {cond} {{", *body, f"{pad}}}"]
        if isinstance(stmt, pyast.For):
            if stmt.orelse:
                return None               # 同上：for-else 不静默丢弃
            tgt = stmt.target
            if isinstance(tgt, pyast.Name):
                tname = _sanitize_ident(tgt.id)
            elif isinstance(tgt, (pyast.Tuple, pyast.List)) and tgt.elts and \
                    all(isinstance(e, pyast.Name) for e in tgt.elts):
                # `for i, v in pairs:` → Matha `for (i, v) in pairs { }`
                tname = "(" + ", ".join(_sanitize_ident(e.id) for e in tgt.elts) + ")"
            else:
                return None
            it = self._py_expr(stmt.iter)
            if it is None:
                return None
            body = self._py_block_lines(stmt.body, ind + 1, True)
            if body is None:
                return None
            return [f"{pad}for {tname} in {it} {{", *body, f"{pad}}}"]
        return None

    def _py_stmts_to_expr(self, stmts: list) -> str | None:
        """Python 语句列表 → 单一 Matha 表达式（let-in / 三元）；无法直译返回 None。

        支持：return、单目标赋值（let 绑定）、复合赋值（a += e）、if/else（含
        提前返回）。循环、raise、多目标赋值等仍返回 None → 交由无中生有骨架。
        """
        if not stmts:
            return None
        head, rest = stmts[0], stmts[1:]
        if isinstance(head, pyast.Return):
            return self._py_expr(head.value) if head.value is not None else "null"
        if (isinstance(head, pyast.Assign) and len(head.targets) == 1
                and isinstance(head.targets[0], pyast.Name)):
            val = self._py_expr(head.value)
            inner = self._py_stmts_to_expr(rest)
            if val is None or inner is None:
                return None
            return f"let {_sanitize_ident(head.targets[0].id)} = {val} in {inner}"
        if isinstance(head, pyast.AugAssign) and isinstance(head.target, pyast.Name):
            op = {pyast.Add: "+", pyast.Sub: "-", pyast.Mult: "*", pyast.Div: "/",
                  pyast.Mod: "%", pyast.Pow: "^", pyast.FloorDiv: "//"}.get(type(head.op))
            val = self._py_expr(head.value)
            inner = self._py_stmts_to_expr(rest)
            if op and val and inner:
                n = _sanitize_ident(head.target.id)
                return f"let {n} = ({n} {op} {val}) in {inner}"
            return None
        if isinstance(head, pyast.If):
            return self._py_if_to_expr(head, rest)
        return None

    def _py_if_to_expr(self, node, rest: list) -> str | None:
        """Python if（+ else / 提前返回）→ Matha 三元表达式。"""
        cond = self._py_expr(node.test)
        then = self._py_stmts_to_expr(node.body)
        if node.orelse:
            other = self._py_stmts_to_expr(node.orelse)
        elif rest:
            other = self._py_stmts_to_expr(rest)   # 提前 return：后续语句为 else 分支
        else:
            other = "null"                          # 无 else 且无后续 → 隐式返回 None
        if cond is None or then is None or other is None:
            return None
        return f"{cond} ? {then} : {other}"

    def _py_expr(self, node) -> str | None:
        """Python 表达式 → Matha 表达式（算术/比较/布尔子集）。"""
        if isinstance(node, pyast.Constant):
            if node.value is None:
                return "null"
            if isinstance(node.value, bool):
                return "真" if node.value else "假"
            if isinstance(node.value, (int, float)):
                return str(node.value)
            if isinstance(node.value, str):
                return f'"{node.value}"'
            return None
        if isinstance(node, pyast.Name):
            return node.id
        if isinstance(node, (pyast.List, pyast.Tuple)):
            parts = [self._py_expr(e) for e in node.elts]
            if any(p is None for p in parts):
                return None
            return "[" + ", ".join(parts) + "]"
        if isinstance(node, pyast.Subscript):
            # 下标读 `xs[i]` → Matha `xs[i]`；切片语义四端未统一，暂拒绝
            if isinstance(node.slice, pyast.Slice):
                return None
            base = self._py_expr(node.value)
            idx = self._py_expr(node.slice)
            if base and idx:
                return f"{base}[{idx}]"
            return None
        if isinstance(node, pyast.UnaryOp):
            inner = self._py_expr(node.operand)
            if inner is None:
                return None
            if isinstance(node.op, pyast.USub):
                return f"-({inner})"
            if isinstance(node.op, pyast.Not):
                return f"not ({inner})"
            return None
        if isinstance(node, pyast.BinOp):
            op = {pyast.Add: "+", pyast.Sub: "-", pyast.Mult: "*",
                  pyast.Div: "/", pyast.Mod: "%", pyast.Pow: "^",
                  pyast.FloorDiv: "//"}.get(type(node.op))
            l, r = self._py_expr(node.left), self._py_expr(node.right)
            if op and l and r:
                return f"({l} {op} {r})"
            return None
        if isinstance(node, pyast.BoolOp):
            sym = "and" if isinstance(node.op, pyast.And) else "or"
            parts = [self._py_expr(v) for v in node.values]
            if any(p is None for p in parts):
                return None
            return parts[0] if len(parts) == 1 else "(" + f" {sym} ".join(parts) + ")"
        if isinstance(node, pyast.Compare):
            return self._py_compare(node)
        if isinstance(node, pyast.Call):
            fn = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if _FN_MAP.get(fn, fn) in _UNAVAILABLE_FNS:
                return None                      # Matha 无此名 → 拒绝直译，落骨架
            args = [self._py_expr(a) for a in node.args]
            if all(args):
                return f"{_FN_MAP.get(fn, fn)}({', '.join(args)})"
            return None
        if isinstance(node, pyast.IfExp):
            c, t, e = (self._py_expr(node.test), self._py_expr(node.body),
                       self._py_expr(node.orelse))
            return f"{c} ? {t} : {e}" if all((c, t, e)) else None
        return None

    def _py_compare(self, node) -> str | None:
        """Python 比较（含链式 a < b < c）→ Matha 比较表达式。"""
        syms = {pyast.Eq: "=", pyast.NotEq: "≠", pyast.Lt: "<",
                pyast.Gt: ">", pyast.LtE: "<=", pyast.GtE: ">="}
        left = self._py_expr(node.left)
        if left is None:
            return None
        parts = []
        for op, comp in zip(node.ops, node.comparators):
            right = self._py_expr(comp)
            sym = syms.get(type(op))
            if right is None or sym is None:
                return None
            parts.append(f"{left} {sym} {right}")
            left = right
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else "(" + " and ".join(parts) + ")"

    # ------------------------------------------------------------------
    # 发射 Matha 模块
    # ------------------------------------------------------------------

    def _sig_line(self, f: FunctionSig) -> str:
        """单函数 → Matha func 定义行。"""
        params = ", ".join(p if t == "" else f"{p}: {t}" for p, t in f.params)
        args = ", ".join(p for p, _ in f.params)
        ret = f" -> {f.ret}" if f.ret else " -> Value"
        return f"  func {f.name}({params}){ret} = ({args}) => {f.body}"

    def _emit_module(self, module_name: str, functions: list, lang: str) -> str:
        """函数列表 → 完整 Matha 模块源码。"""
        lines = [
            "(* ============================================================",
            f"   模块: {module_name}",
            f"   来源: 语言桥吞噬 {lang} 生成（直译 + 无中生有混合）",
            "   ============================================================ *)",
            "",
            f"module {module_name} {{",
            "",
        ]
        for f in functions:
            if f.doc:
                lines.append(f"  (* {f.doc} *)")
            if f.generated:
                lines.append(f"  (* [无中生有] {f.origin} *)")
            lines.append(self._sig_line(f))
            lines.append("")
        lines.append("}")
        return "\n".join(lines)
