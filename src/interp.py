"""Matha 最小树走式解释器（后端原型 + 字符串/列表 + 词法命令绑定）。

让 Matha 程序的具体部分真正执行：
  - func 定义 → 可调用闭包（支持单参 / 柯里化多参）
  - @ set_up → 初始化状态变量（无值默认 0）
  - 机械段（mech unit）：代码块（绑定 / 输出）、命令链（追踪 + 绑定）、GenStmt
  - 表达式求值：字面量、变量、算术 / 关系运算、函数应用、lambda
  - 标准库内建：ord / chr / len / get / slice / append / list
  - 函数式词法扫描：扫描(src)(pos)(line)(col)(toks) 递归组装 Token
    （Matha 自身 lambda + 递归 + 柯里化，无命令占位符）

定位：规格级→可执行规格的后端。命令字面量现为纯规格追踪标记；
实际字符 I/O 由 matha/lexer.matha 的函数式扫描器承担。

用法：
    from src.interp import interpret, lexer_bootstrap_interpret
    outputs, trace = interpret(source)
    tokens = lexer_bootstrap_interpret(matha_source_text)  # 函数式扫描

调试日志：
    解释器核心循环（声明执行 / 语句分派 / 表达式求值 / 词法主控 / 函数应用）
    均埋了 logging 钩子，默认关闭。两种开启方式：

    1) 环境变量（最便捷，无需改代码）：
        $env:MATHA_DEBUG = "1"      # PowerShell
        set MATHA_DEBUG=1            # cmd
        export MATHA_DEBUG=1         # bash
        之后运行任意测试/脚本即可在 stderr 看到带缩进的执行轨迹。

    2) 代码内显式开启（可精确控制粒度）：
        from src.interp import Interpreter, configure_debug_logging
        configure_debug_logging()    # 装 stderr handler
        interp = Interpreter(debug=True)
        interp.run(program)

        或单次调用：
        from src.interp import interpret
        outputs, trace = interpret(source, debug=True)

    日志命名空间 "matha.interp"，层级：
        INFO  —— 声明/段/命令字面量/Token 组装/函数调用边界
        DEBUG —— 语句分派、表达式求值、绑定、二元运算细节
    每条日志带递归深度缩进（. ）便于追踪嵌套调用栈。
"""

from __future__ import annotations
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any
from src import ast_nodes as ast
from src import text_encoding as _te

logger = logging.getLogger("matha.interp")
# 模块默认挂 NullHandler，避免「No handlers could be found」警告；
# 真正输出由 configure_debug_logging() 或用户自行配置 handler 决定。


def _curry_module(n: int, func):
    """模块级柯里化（供 _build_domain_builtins 使用，对应 Interpreter._curry 的静态方法）。"""
    def builder(args):
        if len(args) == n:
            return func(*args)
        return lambda a: builder(args + [a])
    return builder([])


def _build_domain_builtins() -> dict:
    """构建包含所有领域内建符号的 dict（模块级缓存，仅调用一次）。"""
    from src.mathlib import _register_math_builtins, _register_unit_builtins
    b: dict[str, object] = {}
    _register_math_builtins(b)
    _register_unit_builtins(b)
    _domain_registers = [
        ("src.domains.mechanics", "_register_mechanics"),
        ("src.domains.dynamics", "_register_dynamics"),
        ("src.domains.fluid", "_register_fluid"),
        ("src.domains.thermo", "_register_thermo"),
        ("src.domains.em", "_register_em"),
        ("src.domains.acoustics", "_register_acoustics"),
        ("src.domains.optics", "_register_optics"),
        ("src.domains.structural", "_register_structural"),
        ("src.domains.quantum", "_register_quantum"),
        ("src.domains.celestial", "_register_celestial"),
        ("src.domains.nuclear", "_register_nuclear"),
        ("src.domains.statmech", "_register_statmech"),
        ("src.domains.fluid_exp", "_register_fluid_exp"),
        ("src.domains.biology", "_register_biology"),
        ("src.domains.medical", "_register_medical"),
        ("src.domains.medtools", "_register_medtools"),
        ("src.domains.anatomy", "_register_anatomy"),
        ("src.domains.architecture", "_register_architecture"),
        ("src.domains.building_struct", "_register_building_struct"),
        ("src.domains.mech_design", "_register_mech_design"),
        ("src.domains.kernel_math", "_register_kernel_builtins"),
        # 新增领域
        ("src.domains.chemistry", "_register_chemistry"),
        ("src.domains.computer_science", "_register_computer_science"),
        ("src.domains.electrical", "_register_electrical"),
        ("src.domains.economics", "_register_economics"),
        # AI/游戏/前沿领域
        ("src.domains.ai_data_science", "_register_ai_data_science"),
        ("src.domains.game_dev", "_register_game_dev"),
        ("src.domains.quantum_compute", "_register_quantum_compute"),
        ("src.domains.chaos_fractal", "_register_chaos_fractal"),
        ("src.domains.genetic_algo", "_register_genetic_algo"),
        ("src.domains.creative_coding", "_register_creative_coding"),
        ("src.domains.blockchain", "_register_blockchain"),
        ("src.domains.software_app", "_register_software_app"),
        # 新增领域
        ("src.domains.automation", "_register_automation"),
        ("src.domains.iot_hardware", "_register_iot_hardware"),
        ("src.domains.os_network", "_register_os_network"),
        ("src.domains.audio_video", "_register_audio_video"),
        ("src.domains.graphics", "_register_graphics"),
        ("src.domains.hpc", "_register_hpc"),
        ("src.domains.fintech", "_register_fintech"),
        ("src.domains.autonomous", "_register_autonomous"),
        ("src.domains.aerospace", "_register_aerospace"),
        ("src.domains.bio_computing", "_register_bio_computing"),
        ("src.domains.hardware_reverse", "_register_hardware_reverse"),
        ("src.domains.spatial_meta", "_register_spatial_meta"),
        ("src.domains.algo_trading", "_register_algo_trading"),
        ("src.domains.comp_chem", "_register_comp_chem"),
        ("src.domains.green_tech", "_register_green_tech"),
        ("src.domains.metaverse_arch", "_register_metaverse_arch"),
        ("src.domains.digital_rights", "_register_digital_rights"),
        ("src.domains.acoustics", "_register_acoustics"),
        ("src.domains.graph", "_register_graph"),
    ]
    for mod_path, fn_name in _domain_registers:
        mod = __import__(mod_path, fromlist=[fn_name])
        getattr(mod, fn_name)(b)
        # 自动扫描该模块的公式函数，标注能力元数据
        try:
            from src.formula_system import scan_module_capabilities
            scan_module_capabilities(mod)
        except Exception:
            pass  # 扫描失败不影响内建注册
    b["与"] = _curry_module(2, lambda a, b: a and b)
    b["或"] = _curry_module(2, lambda a, b: a or b)
    b["非"] = lambda x: not x
    b["not"] = lambda x: not x
    return b


# 缓存领域内建符号表（模块级，仅初始化一次；在 _curry 定义之后初始化）
_DOMAIN_BUILTINS: dict | None = None
logger.addHandler(logging.NullHandler())


def configure_debug_logging(stream=None, level: int = logging.DEBUG) -> None:
    """装一个 stderr（或指定 stream）handler，开启 matha.interp 详细日志。

    幂等：重复调用不会叠加 handler。
    """
    if stream is None:
        stream = sys.stderr
    # 去重：已有非 NullHandler 的 StreamHandler 指向同一 stream 则跳过
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler) \
                and getattr(h, "stream", None) is stream:
            return
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        "[%(levelname).1s] %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(level)


def _env_debug_flag() -> bool:
    """读取 MATHA_DEBUG 环境变量。1/true/yes/on（不区分大小写）为真。"""
    v = os.environ.get("MATHA_DEBUG", "").strip().lower()
    return v in ("1", "true", "yes", "on")


class MathaRuntimeError(Exception):
    """运行时错误，携带代码位置信息（行/列）。"""
    __slots__ = ("line", "col")

    def __init__(self, msg: str, line: int = None, col: int = None):
        super().__init__(msg)
        self.line = line
        self.col = col

    def __str__(self) -> str:
        return super().__str__()


class _EnumNamespace:
    """Matha enum 命名空间，支持 类型.整数 这样的属性访问。"""
    def __init__(self, name: str, ctors: list):
        self.name = name
        self.ctors = ctors
        self.line = None
        self.col = None
        for ctor in ctors:
            setattr(self, ctor, ctor)

    def __repr__(self):
        base = f"<{_EnumNamespace.__name__} '{self.name}'>"
        loc = ""
        if self.line is not None:
            loc = f" (L{self.line}"
            if self.col is not None:
                loc += f":C{self.col}"
            loc += ")"
        return base + loc


class _StructInstance:
    """Matha struct 实例，支持 obj.field 和 obj["field"] 访问。"""

    def __init__(self, name: str, fields: list, values: list):
        self._name = name
        self._fields = fields
        self._values = dict(zip(fields, values))
        for f, v in zip(fields, values):
            self.__dict__[f] = v

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value
        setattr(self, key, value)

    def __repr__(self):
        pairs = ", ".join(f"{k}={v!r}" for k, v in self._values.items())
        return f"{self._name}({pairs})"

    def __eq__(self, other):
        if isinstance(other, _StructInstance):
            return self._name == other._name and self._values == other._values
        return False

    def __hash__(self):
        return hash((self._name, tuple(self._values.items())))


def _raise(msg: str, line: int = None, col: int = None) -> None:
    """统一抛出 MathaRuntimeError，携带位置信息。"""
    raise MathaRuntimeError(msg, line=line, col=col)


def builtin_throw(msg: str) -> None:
    """Matha DSL 可用的异常抛出函数（名称避免下划线前缀，兼容词法分析器）。"""
    raise MathaRuntimeError(msg)


class _BreakException(Exception):
    """break 中断循环的内部异常。"""
    pass


class _ContinueException(Exception):
    """continue 继续循环的内部异常。"""
    pass


class _ReturnException(Exception):
    """return 返回的内部异常。"""

    def __init__(self, value):
        self.value = value
        super().__init__()


class _RecPlaceholder:
    """递归函数占位符：在 lambda 求值前预注册，调用时解析为实际函数。"""

    __slots__ = ("name", "_ref", "_interp")

    def __init__(self, name: str):
        self.name = name
        self._ref = [None]  # 通过可变列表实现延迟绑定
        self._interp = None  # 解释器引用

    def __call__(self, arg):
        actual = self._ref[0]
        if actual is None:
            raise MathaRuntimeError(f"递归函数 '{self.name}' 尚未完成初始化")
        if isinstance(actual, tuple) and actual and actual[0] == "__closure__":
            # 4 元组 ("__closure__", params, body, env)
            if len(actual) == 4:
                _, lam, body, captured = actual
                lambda_node = ast.Lambda(params=lam, body=body)
            else:
                # 3 元组 ("__closure__", lambda, captured)
                _, lambda_node, captured = actual
            return self._interp._call_lambda(lambda_node, captured, [arg])
        return actual(arg)


# ============================================================
# 内建标准库（纯 Python 可调用，由解释器模拟柯里化）
# ============================================================

def builtin_ord(c: str) -> int:
    if not isinstance(c, str) or len(c) != 1:
        raise MathaRuntimeError(f"ord() 需要单字符，实际 {c!r}")
    return ord(c)


def builtin_chr(n: int) -> str:
    if not isinstance(n, int):
        raise MathaRuntimeError(f"chr() 需要整数，实际 {n!r}")
    return chr(n)


def builtin_len(seq) -> int:
    if isinstance(seq, (str, list, tuple)):
        return len(seq)
    raise MathaRuntimeError(f"len() 需要字符串或列表或元组，实际 {type(seq).__name__}")


def builtin_get(seq):
    """get(seq)(index) → seq[index]"""
    def at(index: int):
        if not isinstance(seq, (str, list)):
            raise MathaRuntimeError(f"get() 需要字符串或列表，实际 {type(seq).__name__}")
        if not isinstance(index, int):
            raise MathaRuntimeError(f"get() 索引需整数，实际 {index!r}")
        try:
            return seq[index]
        except IndexError:
            raise MathaRuntimeError(f"get() 索引越界: {index} / {len(seq)}")
    return at


def builtin_slice(seq):
    """slice(seq)(start)(end) → seq[start:end]"""
    def start_closure(start: int):
        def end_closure(end: int):
            if not isinstance(seq, (str, list)):
                raise MathaRuntimeError(f"slice() 需要字符串或列表")
            if not isinstance(start, int) or not isinstance(end, int):
                raise MathaRuntimeError(f"slice() 参数需整数")
            return seq[start:end]
        return end_closure
    return start_closure


def builtin_append(lst):
    """append(lst)(elem) → 新列表 lst + [elem]"""
    # 兼容：Matha 词法器部分调用返回 tuple（partial application），转为 list
    if isinstance(lst, tuple):
        lst = list(lst)
    def with_elem(elem):
        if not isinstance(lst, list):
            raise MathaRuntimeError(f"append() 需要列表，实际 {type(lst).__name__}")
        return lst + [elem]
    return with_elem


def builtin_mut_set_at(lst):
    """mut_set_at(lst)(idx)(v) → 原地把 lst[idx] 置为 v，返回 lst。

    唯一的列表可变原语：自举解释器用「占位符 + 原地更新」实现 let rec / and
    互递归绑定（对齐宿主 _RecPlaceholder 的 [None] 可变引用语义）。
    env 为 CONS 共享的 [[name, value], ...] 结构，对共享 pair 的原地修改
    对所有捕获该 env 的闭包同步可见。"""
    if not isinstance(lst, list):
        raise MathaRuntimeError(f"mut_set_at() 需要列表，实际 {type(lst).__name__}")
    def at(idx):
        if not isinstance(idx, int):
            raise MathaRuntimeError(f"mut_set_at() 索引需整数，实际 {idx!r}")
        def with_val(v):
            lst[idx] = v
            return lst
        return with_val
    return at


def builtin_list(*args):
    """list() → []；list(x) → [x]"""
    return list(args)


def builtin_type_of(v) -> str:
    """返回值类型名称（Matha 类型）。供 stdlib 与自举代码使用，
    避免 stdlib 自实现的 type_of 与 str 互相调用造成死循环。"""
    if v is True or v is False or isinstance(v, bool):
        return "Bool"
    if isinstance(v, int):
        return "Int"
    if isinstance(v, float):
        return "Float"
    if isinstance(v, str):
        return "String"
    if isinstance(v, list):
        return "List"
    if isinstance(v, dict):
        return "Dict"
    if isinstance(v, tuple) and len(v) > 0 and v[0] == "__closure__":
        return "Closure"
    return "Unknown"


def builtin_token(ttype):
    """token(类型)(文本)(行)(列) -> Token 字典（柯里化四参构造子）。

    供函数式词法器组装 Token；与原命令占位符时代的
    {"类型":..,"文本":..,"行":..,"列":..} 字典格式一致，保持兼容。
    """
    def with_text(text):
        def with_line(line):
            def with_col(col):
                return {"类型": ttype, "文本": text, "行": line, "列": col}
            return with_col
        return with_line
    return with_text


def builtin_parse_json(text: str):
    """解析_JSON(json字符串) → 嵌套列表/字典。

    把 JSON 数组 [a, b, c] 解析为 Python list，
    供 codegen 的规格树使用。
    """
    import json
    try:
        result = json.loads(str(text))
        logging.getLogger("matha.interp").debug(f"parse_json: {text!r} → {result!r}")
        return result
    except (json.JSONDecodeError, TypeError) as e:
        logging.getLogger("matha.interp").debug(f"parse_json FAILED: {text!r} → {e}")
        raise MathaRuntimeError(f"JSON 解析失败: {e}")


# ============================================================
# 文件 I/O
# ============================================================
def builtin_read_file(path: str) -> str:
    """读文件(path) → 文件内容字符串。"""
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise MathaRuntimeError(f"读文件失败: {e}")


def builtin_write_file(path: str, content: str) -> None:
    """写文件(path, 内容) → 无返回值。"""
    try:
        with open(str(path), "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise MathaRuntimeError(f"写文件失败: {e}")


def builtin_append_file(path: str, content: str) -> None:
    """追加文件(path, 内容) → 无返回值。"""
    try:
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise MathaRuntimeError(f"追加文件失败: {e}")


def builtin_parse_json_file(path: str):
    """读JSON文件(path) → 嵌套列表/字典。"""
    import json
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except Exception as e:
        raise MathaRuntimeError(f"读JSON文件失败: {e}")


def builtin_write_json_file(path: str, data) -> None:
    """写JSON文件(path, 数据) → 无返回值。"""
    import json
    try:
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception as e:
        raise MathaRuntimeError(f"写JSON文件失败: {e}")


# ============================================================
# 字符串操作
# ============================================================
def builtin_字符串截取(s: str, start: int, end: int = None) -> str:
    """截取(文本, 起始[, 结束]) → 子串。"""
    if end is not None:
        return str(s)[start:end]
    return str(s)[start:]


def builtin_字符串替换(s: str, old: str, new: str) -> str:
    """替换(文本, 旧, 新) → 新字符串。"""
    return str(s).replace(str(old), str(new))


def builtin_字符串查找(s: str, sub: str) -> int:
    """查找(文本, 子串) → 索引（未找到返回 -1）。"""
    return str(s).find(str(sub))


def builtin_字符串分割(s: str, sep: str = " ") -> list:
    """分割(文本[, 分隔符]) → 列表。"""
    return str(s).split(str(sep) if sep else " ")


def builtin_字符串拼接(sep: str, *parts) -> str:
    """拼接(分隔符, 部分1, 部分2, ...) → 字符串。"""
    return str(sep).join(str(p) for p in parts)


def builtin_字符串去空白(s: str) -> str:
    """去空白(文本) → 去除首尾空白。"""
    return str(s).strip()


def builtin_字符串小写(s: str) -> str:
    """小写(文本) → 全小写。"""
    return str(s).lower()


def builtin_字符串大写(s: str) -> str:
    """大写(文本) → 全大写。"""
    return str(s).upper()


# ============================================================
# 列表操作
# ============================================================
def builtin_列表映射(lst, fn):
    """映射(列表, 函数) → 新列表。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("映射() 需要列表")
    return [fn(x) for x in lst]


def builtin_列表过滤(lst, fn):
    """过滤(列表, 函数) → 新列表。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("过滤() 需要列表")
    return [x for x in lst if fn(x)]


def builtin_列表反转(lst) -> list:
    """反转(列表) → 新列表。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("反转() 需要列表")
    return list(reversed(lst))


def builtin_列表排序(lst, reverse: bool = False) -> list:
    """排序(列表[, 降序]) → 新列表。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("排序() 需要列表")
    return sorted(lst, reverse=bool(reverse))


def builtin_列表展平(nested) -> list:
    """展平(嵌套列表) → 一维列表。"""
    result = []
    def _flatten(x):
        if isinstance(x, (list, tuple)):
            for item in x:
                _flatten(item)
        else:
            result.append(x)
    _flatten(nested)
    return result


def builtin_列表求和(lst) -> float:
    """求和(列表) → 数值和。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("求和() 需要列表")
    return sum(lst)


def builtin_列表去重(lst) -> list:
    """去重(列表) → 去重后列表。"""
    if not isinstance(lst, (list, tuple)):
        raise MathaRuntimeError("去重() 需要列表")
    seen = []
    for x in lst:
        if x not in seen:
            seen.append(x)
    return seen


# ============================================================
# Matha 模块加载（自举路径）
# ============================================================

def _matha_dir() -> Path:
    """定位 matha/ 目录。"""
    _candidates = [
        Path(__file__).parent.parent / "matha",
        Path.cwd().parent / "matha",
        Path.cwd() / "matha",
    ]
    for p in _candidates:
        if p.exists():
            return p
    return Path(__file__).parent.parent / "matha"


def _load_matha_source(module_name: str, matha_dir: Path | None = None) -> str:
    """读取 .matha 源文件。"""
    d = matha_dir or _matha_dir()
    # 中文模块名 → 英文文件名映射（模块声明用中文，源文件用英文）
    _CN2FILE = {
        "词法器": "lexer.matha",
        "语法器": "parser.matha",
        "标准库": "stdlib.matha",
        "解释器": "interp.matha",
        "虚拟机": "vm/matha_vm.matha",
        "自举加载器": "bootstrap_matha.matha",
        "编译器": "compiler_matha.matha",
    }
    if module_name == "运行时引擎":
        path = d / "runtime" / "matha_runtime.matha"
    elif module_name in _CN2FILE:
        path = d / _CN2FILE[module_name]
    else:
        path = d / f"{module_name}.matha"
    if not path.exists():
        raise FileNotFoundError(f"找不到 Matha 模块: {path}")
    return path.read_text(encoding="utf-8")


BUILTINS: dict[str, object] = {
    "ord": builtin_ord,
    "chr": builtin_chr,
    "len": builtin_len,
    "get": builtin_get,
    "slice": builtin_slice,
    "append": builtin_append,
    "mut_set_at": builtin_mut_set_at,
    "list": builtin_list,
    "token": builtin_token,
    "type_of": builtin_type_of,
    "解析_JSON": builtin_parse_json,
    # 类型转换
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
    # 文件 I/O
    "读文件": builtin_read_file,
    "写文件": _curry_module(2, lambda path, content: builtin_write_file(path, content)),
    "追加文件": _curry_module(2, lambda path, content: builtin_append_file(path, content)),
    "读JSON文件": builtin_parse_json_file,
    "写JSON文件": _curry_module(2, lambda path, data: builtin_write_json_file(path, data)),
    # 字符串操作
    "截取": builtin_字符串截取,
    "替换": builtin_字符串替换,
    "查找": builtin_字符串查找,
    "分割": builtin_字符串分割,
    "拼接": builtin_字符串拼接,
    "去空白": builtin_字符串去空白,
    "小写": builtin_字符串小写,
    "大写": builtin_字符串大写,
    # 文本编码（二进制/三进制/十进制）
    "encode_binary": lambda s: _te.encode_binary(str(s)),
    "decode_binary": lambda s: _te.decode_binary(str(s)),
    "encode_ternary": lambda s: _te.encode_ternary(str(s)),
    "decode_ternary": lambda s: _te.decode_ternary(str(s)),
    "encode_decimal": lambda s: _te.encode_decimal(str(s)),
    "decode_decimal": lambda s: _te.decode_decimal(str(s)),
    # 列表操作
    "映射": _curry_module(2, lambda lst, fn: builtin_列表映射(lst, fn)),
    "过滤": _curry_module(2, lambda lst, fn: builtin_列表过滤(lst, fn)),
    "反转": builtin_列表反转,
    "排序": _curry_module(2, lambda lst, reverse: builtin_列表排序(lst, reverse)),
    "展平": builtin_列表展平,
    "求和": builtin_列表求和,
    "去重": builtin_列表去重,
    # 异常控制
    "抛出错误": builtin_throw,
    "错误": builtin_throw,
}


def _curry_callable(fn, arity=None):
    """给一个 Python callable 做柯里化包装，使其匹配 Matha 的单参应用。

    对 n 参函数 f(a, b, c)：当应用第一个参数后，返回等待 b、c 的闭包。
    对变长或未知 arity 的函数，若函数返回 callable（如 slice、append），
    则直接应用第一层，后续再应用由解释器继续调用。
    """
    # 已经是单参 callable 或返回 callable 的，原样返回
    return fn


class _MathaExecWrapper:
    """包装 Matha 执行函数，使其能处理 Python AST 节点。

    当解释器通过 _call_func 调用时，参数以 [arg] 形式传入。
    对于 执行语句/执行声明，第一个参数是 stmt/decl，第二个是 env。
    本包装器直接将调用转发到对应的 Python 方法。
    """
    def __init__(self, interp: "Interpreter", method_name: str):
        self._interp = interp
        self._method = getattr(interp, method_name)

    def __call__(self, arg):
        """单参数调用：arg 是 (stmt, env) 或仅 stmt。"""
        if isinstance(arg, tuple) and len(arg) == 2:
            return self._method(arg[0], arg[1])
        # 单参数调用：arg 是 stmt，env 从 self.env 取
        return self._method(arg, self._interp.env)


class Interpreter:
    """Matha 树走式解释器。"""

    def __init__(self, debug: bool | None = None):
        self.env: dict[str, object] = {}
        self.funcs: dict[str, ast.FuncDef] = {}
        self.constructors: set[str] = set()
        self.outputs: list = []
        self.trace: list[str] = []
        self.builtins: dict[str, object] = dict(BUILTINS)  # 可继承覆写
        # 模块系统：module_name → {name → bound_value}
        self.modules: dict[str, dict] = {}
        self._matha_loaded: bool = False
        # debug=None → 服从 MATHA_DEBUG 环境变量；显式 True/False 优先
        self.debug = _env_debug_flag() if debug is None else bool(debug)
        # 递归深度缩进，让 _eval / _exec_stmt / _call_lambda 嵌套可读
        self._depth: int = 0
        # 若开启 debug 但尚未配置 handler，自动装一个 stderr handler
        if self.debug and not any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
            for h in logger.handlers
        ):
            configure_debug_logging()
        self._install_self_builtins()
        # 复用模块级缓存的领域内建符号（避免每次重建 ~400 个函数对象）
        self.builtins.update(_DOMAIN_BUILTINS)
        # 逻辑运算内建（与/或/非，不改语法层）——已由 _build_domain_builtins 注册，此处跳过

    # ---------- 日志辅助 ----------

    def _log(self, level: int, msg: str) -> None:
        """带递归深度缩进的日志。debug=False 时直接 no-op，零开销。"""
        if not self.debug:
            return
        indent = ". " * self._depth
        logger.log(level, f"{indent}{msg}")

    def _log_enter(self, tag: str, detail: str = "") -> None:
        """进入某个递归节点：打印 + 深度 +1。"""
        if self.debug:
            self._log(logging.DEBUG, f"→ {tag}{(' ' + detail) if detail else ''}")
            self._depth += 1

    def _log_exit(self, tag: str, result: object = None) -> None:
        """离开某个递归节点：深度 -1 + 打印结果。"""
        if self.debug:
            self._depth = max(0, self._depth - 1)
            r = "" if result is None and tag else f" = {self._fmt(result)}"
            self._log(logging.DEBUG, f"← {tag}{r}")

    @staticmethod
    def _fmt(v: object, _depth: int = 0) -> str:
        """值的安全格式化（避免巨型/自引用对象刷屏或死循环）。

        注意：调用点常在 f-string 中无条件求值（即使 debug=False），
        因此这里必须对任意结构保证快速终止。
        """
        if _depth > 3:
            return "…"
        if isinstance(v, str):
            return repr(v[:60] + ("…" if len(v) > 60 else ""))
        if v is None or isinstance(v, (bool, int, float)):
            return repr(v)
        if isinstance(v, tuple) and v and v[0] == "__closure__":
            # 闭包元组：captured env 内含模块命名空间 → 自引用，绝不可 repr
            params = v[1] if len(v) > 1 else []
            try:
                n = len(params)
            except TypeError:
                n = "?"
            return f"<closure {n}参数>"
        if isinstance(v, (list, tuple)):
            if len(v) > 4:
                return f"[{type(v).__name__} len={len(v)}]"
            return ("[" + ", ".join(Interpreter._fmt(x, _depth + 1) for x in v) + "]")
        if isinstance(v, dict):
            if len(v) > 6:
                return f"{{dict keys={list(v.keys())[:8]}}}"
            return ("{" + ", ".join(
                f"{k}: {Interpreter._fmt(x, _depth + 1)}"
                for k, x in list(v.items())[:6]) + "}")
        if callable(v):
            return f"<builtin {getattr(v, '__name__', '?')}>"
        name = getattr(v, "name", None)
        if name is not None and not isinstance(v, type):
            return f"<{type(v).__name__} {name}>"
        return repr(v)[:120]

    # ---------- 入口 ----------

    def run(self, program: ast.Program) -> tuple[list, list[str]]:
        self._log(logging.INFO, f"run: {len(program.decls)} 个顶层声明")
        self._depth = 0
        # 记录注册前的 funcs 集合，用于后续计算模块命名空间
        self._pre_register_funcs = set(self.funcs.keys())
        self._log_enter("register-pass")
        for decl in program.decls:
            self._register(decl)
        self._log_exit("register-pass")
        # 覆盖执行语句/执行声明：使它们能处理 Python AST 节点（测试块路径）
        self._override_matha_exec_funcs()
        self._log_enter("exec-pass")
        # 预处理：收集需要提前执行以注册递归函数的 FuncApp
        self._deferred_calls: set[tuple] = set()
        self._collect_deferred_calls(program.decls, self._deferred_calls, prefix=())
        # 执行声明，遇到延迟调用时先执行前置 FuncDef
        self._exec_with_deferreds(program.decls, self._deferred_calls, ())
        self._log_exit("exec-pass", self.outputs)
        self._log(logging.INFO,
                  f"run 完成: outputs={len(self.outputs)} trace={len(self.trace)}")
        return self.outputs, self.trace

    def _collect_deferred_calls(self, decls, deferred: set, prefix: tuple) -> None:
        """递归收集所有需要延迟执行的 FuncApp。"""
        for i, decl in enumerate(decls):
            if isinstance(decl, ast.FuncApp):
                _func = decl.func
                while isinstance(_func, ast.FuncApp):
                    _func = _func.func
                _fname = _func.name if isinstance(_func, ast.Variable) else None
                if _fname and i > 0:
                    for j in range(i - 1, -1, -1):
                        _prev = decls[j]
                        if isinstance(_prev, ast.FuncDef) and _prev.body is not None:
                            if self._lambda_body_contains(_prev.body, _fname):
                                deferred.add(prefix + (i,))
                                break
            elif isinstance(decl, ast.ModuleDecl):
                self._collect_deferred_calls(decl.decls, deferred, prefix + (i,))

    def _exec_with_deferreds(self, decls, deferred: set, prefix: tuple) -> None:
        """递归执行声明，处理延迟调用。"""
        for i, decl in enumerate(decls):
            key = prefix + (i,)
            self._log(logging.INFO, f"── decl[{key}] {type(decl).__name__} ──")
            if key in deferred:
                self._exec_decl(decls[i - 1])
            if key in deferred:
                continue
            self._exec_decl(decl)
            if isinstance(decl, ast.ModuleDecl):
                self._exec_with_deferreds(decl.decls, deferred, key)

    @staticmethod
    def _lambda_body_contains(body, func_name: str) -> bool:
        """检查 lambda 体中是否包含名为 func_name 的 FuncDef。"""
        if body is None:
            return False
        if isinstance(body, ast.Lambda):
            body = body.body
        if isinstance(body, ast.FuncDef) and body.name == func_name:
            return True
        if isinstance(body, ast.LetBinding) and body.body is not None:
            if isinstance(body.body, ast.FuncDef) and body.body.name == func_name:
                return True
            return Interpreter._lambda_body_contains(body.body, func_name)
        if isinstance(body, ast.CodeBlock):
            for s in body.stmts:
                if Interpreter._lambda_body_contains(s, func_name):
                    return True
        return False

    def call(self, name: str, *args) -> object:
        # funcs 优先于 builtins：用户定义函数可覆写同名内建
        # （如 func c(x) 覆写光速常量 c）
        if name in self.funcs:
            result = self._call_func(self.funcs[name], list(args))
            return result
        if name in self.builtins:
            result = self.builtins[name]
            self._log(logging.DEBUG, f"call builtin '{name}'({args}) → {type(result).__name__}")
            if args:
                for a in args:
                    result = self._apply(result, a)
            elif callable(result):
                # 无参调用：仅允许安全的 0 参内建（list/dict/.../bool）和绑定方法（探针_* 等）
                _ZERO_ARG_BUILTINS = {list, dict, set, tuple, str, int, float, bool}
                if result in _ZERO_ARG_BUILTINS or hasattr(result, '__self__'):
                    result = result()
                    self._log(logging.DEBUG, f"  builtin '{name}'() → {self._fmt(result)}")
                else:
                    raise MathaRuntimeError(f"内建 '{name}'({type(result).__name__}) 需要参数，不可无参调用")
            return result
        # 模块属性调用：如 语法器.parse、词法器.扫描
        if '.' in name:
            mod_name, fn_name = name.split('.', 1)
            if mod_name in self.modules:
                fn = self.modules[mod_name].get(fn_name)
                if fn is not None:
                    return self._call_func_or_closure(fn, list(args))
            if mod_name in self.env:
                obj = self.env[mod_name]
                if isinstance(obj, dict) and fn_name in obj:
                    fn = obj[fn_name]
                    return self._call_func_or_closure(fn, list(args))
        raise MathaRuntimeError(f"未定义函数 '{name}'")

    def load_matha_module(self, module_name: str, matha_dir: Path | None = None) -> bool:
        """从文件系统加载 .matha 模块并注册到解释器。

        支持在运行时通过 use 声明自动加载模块。
        返回 True 表示加载成功，False 表示模块已存在或加载失败。
        """
        # 先从已加载模块中查找（支持中英文名）
        if module_name in self.modules:
            self._log(logging.DEBUG, f"模块 '{module_name}' 已加载，跳过")
            return True
        try:
            from src.parser import parse as _python_parse
            source = _load_matha_source(module_name, matha_dir)
            self._log(logging.INFO, f"load_matha_module: '{module_name}'")
            prog = _python_parse(source)
            # 提取实际的模块名（module 声明中的名称）
            actual_name = module_name
            for decl in prog.decls:
                if isinstance(decl, ast.ModuleDecl):
                    actual_name = decl.name
                    break
            self.run(prog)
            loaded = actual_name in self.modules
            self._log(logging.INFO, f"load_matha_module: '{module_name}' -> '{actual_name}' = {loaded}")
            return loaded
        except Exception as e:
            self._log(logging.ERROR, f"load_matha_module '{module_name}' 失败: {e}")
            return False

    # ---------- 注册 ----------

    def _register(self, decl) -> None:
        if isinstance(decl, ast.FuncDef):
            self.funcs[decl.name] = decl
            self._log(logging.INFO, f"register func '{decl.name}'")
            if decl.else_body is not None:
                self._exec_stmt(decl.else_body)
        elif isinstance(decl, ast.EnumDef):
            self.constructors.update(decl.ctors)
            self._log(logging.INFO,
                      f"register enum '{decl.name}' ctors={decl.ctors}")
        elif isinstance(decl, ast.ModuleDecl):
            self._log(logging.INFO,
                      f"register module '{decl.name}' ({len(decl.decls)} decls)")
            if decl.name not in self.modules:
                for inner in decl.decls:
                    self._register(inner)

    # ---------- 声明执行 ----------

    def _exec_decl(self, decl) -> None:
        if isinstance(decl, ast.SetUp):
            self._log(logging.INFO, f"exec SetUp form='{decl.form}' items={len(decl.items)}")
            self._exec_set_up(decl)
        elif isinstance(decl, ast.MechUnit):
            seg = decl.generate.seg_id
            body = decl.body
            body_type = type(body).__name__ if not isinstance(body, list) else f"list[{len(body)}]"
            self._log(logging.INFO,
                      f"exec MechUnit #{seg} body={body_type}")
            if isinstance(body, list):
                for item in body:
                    self._exec_stmt(item)
            else:
                self._exec_stmt(body)
        elif isinstance(decl, ast.ModuleDecl):
            self._log(logging.INFO, f"exec Module '{decl.name}'")
            if decl.name in self.modules:
                self._log(logging.DEBUG, f"  模块 '{decl.name}' 已加载，跳过重复注册")
            else:
                # 模块命名空间严格隔离：只收集本模块 decls 显式定义的名字，
                # 不扫描全局 self.env（避免把其它模块的符号污染进本模块）。
                local_names: list[str] = []
                local_set: set[str] = set()

                def _register_local(nm: str) -> None:
                    if nm and nm not in local_set:
                        local_set.add(nm)
                        local_names.append(nm)

                for inner in decl.decls:
                    self._exec_decl(inner)
                    # FuncDef 执行后创建 closure 并存入 env
                    if isinstance(inner, ast.FuncDef):
                        closure = ("__closure__", inner.body.params, inner.body.body,
                                   list(self.env.items()))
                        self.env[inner.name] = closure
                        _register_local(inner.name)
                    elif isinstance(inner, ast.LetBinding):
                        _register_local(inner.name)
                    elif isinstance(inner, ast.EnumDef):
                        _register_local(inner.name)
                    elif isinstance(inner, ast.StructDef):
                        _register_local(inner.name)
                    elif isinstance(inner, ast.Binding):
                        # 顶层绑定 target 一般是 Variable
                        tgt = inner.target
                        nm = getattr(tgt, 'name', None)
                        if nm is not None:
                            _register_local(nm)
                # 仅收录本模块定义、且当前在 env 中有值的名字
                module_ns = {}
                for nm in local_names:
                    if nm in self.env:
                        module_ns[nm] = self.env[nm]
                self.modules[decl.name] = module_ns
                # 将模块命名空间作为变量绑定到 env，支持 模块.函数 语法
                self.env[decl.name] = module_ns
        elif isinstance(decl, ast.Binding):
            # 顶层绑定（如 inc = (x) => x + 1）写入全局 env，
            # 使 lambda 变量在各段内可见，与 func 定义行为一致。
            self._log(logging.INFO, f"exec top-level Binding")
            self._exec_stmt(decl)
        elif isinstance(decl, ast.Output):
            self._log(logging.INFO, f"exec top-level Output")
            self._exec_stmt(decl)
        elif isinstance(decl, ast.LetBinding):
            self._log(logging.INFO, f"exec top-level LetBinding '{decl.name}'")
            self._exec_stmt(decl)
        elif isinstance(decl, ast.BinaryOp):
            # 顶层裸表达式（如 1 === 1）：计算并输出
            self._log(logging.INFO, f"exec top-level BinaryOp")
            val = self._eval(decl)
            self.outputs.append(val)
        elif isinstance(decl, ast.UnaryOp):
            # 顶层裸一元表达式（如 ~5、-3、null）
            self._log(logging.INFO, f"exec top-level UnaryOp '{decl.op}'")
            val = self._eval(decl)
            self.outputs.append(val)
        elif isinstance(decl, ast.FuncApp):
            # 顶层函数调用：执行并丢弃返回值
            self._log(logging.DEBUG, f"exec top-level FuncApp")
            self._eval(decl)
        elif isinstance(decl, ast.WhileStmt):
            self._exec_while_stmt(decl)
        elif isinstance(decl, ast.ForStmt):
            self._exec_for_stmt(decl)
        elif isinstance(decl, ast.IfStmt):
            self._exec_if_stmt(decl)
        elif isinstance(decl, ast.BreakStmt):
            self._exec_break()
        elif isinstance(decl, ast.ContinueStmt):
            self._exec_continue()
        elif isinstance(decl, ast.ReturnStmt):
            value = self._eval(decl.value) if decl.value is not None else None
            self._exec_return(value)
        elif isinstance(decl, ast.ThrowStmt):
            self._exec_throw(self._eval(decl.value))
        elif isinstance(decl, ast.TryStmt):
            self._exec_try(decl)
        elif isinstance(decl, ast.SwitchStmt):
            self._exec_switch_stmt(decl)
        elif isinstance(decl, ast.ImportDecl):
            self._log(logging.INFO,
                      f"use {decl.module_name} {decl.import_list}")
            self._exec_use(decl)
        elif isinstance(decl, ast.EnumDef):
            # 为 enum 创建命名空间对象，支持 类型.整数 属性访问
            ns = _EnumNamespace(decl.name, decl.ctors)
            self.env[decl.name] = ns
            self._log(logging.INFO,
                      f"register enum '{decl.name}' ns={ns}")
        elif isinstance(decl, ast.StructDef):
            # struct 注册为工厂函数，返回支持字段访问的对象
            # fields 是 [(name, type), ...] 格式
            field_names = [f[0] for f in decl.fields] if decl.fields else []
            def _struct_factory(*args):
                if len(args) < len(field_names):
                    # 柯里化：参数不足时返回等待剩余参数的部分函数
                    # 支持嵌套 FuncApp 的逐个参数应用
                    remaining = field_names[len(args):]
                    def _partial(*more_args):
                        all_args = list(args) + list(more_args)
                        if len(all_args) != len(field_names):
                            raise MathaRuntimeError(
                                f"struct {decl.name} 期望 {len(field_names)} 个参数，实际 {len(all_args)} 个"
                            )
                        return _StructInstance(decl.name, field_names, all_args)
                    return _partial
                if len(args) != len(field_names):
                    # 允许零参数 struct 的无参调用：Empty()
                    if len(field_names) == 0 and len(args) == 1 and isinstance(args[0], int) and args[0] == 0:
                        args = []
                    else:
                        raise MathaRuntimeError(
                            f"struct {decl.name} 期望 {len(field_names)} 个参数，实际 {len(args)} 个"
                        )
                return _StructInstance(decl.name, field_names, list(args))
            self.env[decl.name] = _struct_factory
            self._log(logging.INFO,
                      f"register struct '{decl.name}' fields={field_names}")
        else:
            self._log(logging.DEBUG, f"skip decl {type(decl).__name__}（无运行时副作用）")

    def _exec_set_up(self, node: ast.SetUp) -> None:
        for item in node.items:
            target = self._target_name(item.target)
            if item.value is not None:
                self._log_enter("set_up", target)
                val = self._eval(item.value)
                self.env[target] = val
                self._log_exit("set_up", val)
                self._log(logging.DEBUG,
                          f"env[{target!r}] = {self._fmt(val)}")
            else:
                self.env.setdefault(target, 0)
                self._log(logging.DEBUG, f"env[{target!r}] = 0 (default)")

    def _exec_if_stmt(self, stmt: ast.IfStmt) -> None:
        """执行 if-else 语句。"""
        cond = self._eval(stmt.cond)
        if cond:
            self._exec_codeblock_or_stmt(stmt.then_block)
        elif stmt.else_block is not None:
            self._exec_codeblock_or_stmt(stmt.else_block)

    def _exec_while_stmt(self, stmt: ast.WhileStmt) -> None:
        """执行 while 循环。"""
        self._log_enter("while")
        iteration = 0
        # 防止无限循环：可通过 MATHA_MAX_ITER 环境变量配置
        max_iter = int(os.environ.get("MATHA_MAX_ITER", "1000000"))
        while iteration < max_iter:
            try:
                if not self._eval(stmt.cond):
                    break
                self._exec_codeblock_or_stmt(stmt.block)
            except _BreakException:
                break
            except _ContinueException:
                pass
            iteration += 1
        self._log_exit("while")

    def _exec_for_stmt(self, stmt: ast.ForStmt) -> None:
        """执行 for 循环，支持 list/tuple/str/dict/set 迭代和元组解构。"""
        self._log_enter("for")
        iterable = self._eval(stmt.iterable)
        # 支持 dict：迭代 items
        if isinstance(iterable, dict):
            iterable = list(iterable.items())
        # 支持 set：转为 list
        if isinstance(iterable, set):
            iterable = list(iterable)
        if not isinstance(iterable, (list, tuple, str)):
            raise MathaRuntimeError(f"for 迭代对象需为列表/元组/字符串/字典/集合，实际 {type(iterable).__name__}")
        # 元组解构：for (a, b) in list_of_tuples
        is_destructured = isinstance(stmt.var, list) and len(stmt.var) > 1
        # 保存循环前变量状态
        _var_saved: dict[str, Any] = {}
        for name in stmt.var:
            _var_saved[name] = self.env.get(name)
        for item in iterable:
            try:
                if is_destructured:
                    if isinstance(item, (tuple, list)) and len(item) == len(stmt.var):
                        for name, val in zip(stmt.var, item):
                            self.env[name] = val
                    else:
                        raise MathaRuntimeError(
                            f"解构失败：期望 {len(stmt.var)} 个元素，实际 {type(item).__name__}"
                        )
                else:
                    self.env[stmt.var[0]] = item
                self._exec_codeblock_or_stmt(stmt.block)
            except _BreakException:
                break
            except _ContinueException:
                pass
        # 清理循环变量
        for name in stmt.var:
            if name in _var_saved:
                self.env[name] = _var_saved[name]
            else:
                self.env.pop(name, None)
        self._log_exit("for")

    def _exec_break(self) -> None:
        """break：中断循环，抛特殊异常让外层捕获。"""
        raise _BreakException()

    def _exec_continue(self) -> None:
        """continue：跳过本次循环迭代，抛特殊异常让外层捕获。"""
        raise _ContinueException()

    def _exec_return(self, value: Any) -> Any:
        """return：从函数返回，抛特殊异常让外层捕获。"""
        raise _ReturnException(value)

    def _exec_throw(self, value: Any) -> None:
        """throw：抛出异常。"""
        raise MathaRuntimeError(f"throw: {value!r}")

    def _exec_try(self, stmt: ast.TryStmt) -> None:
        """执行 try/catch/finally 块。"""
        # 记录正在传播的控制流异常，防止 finally 内的 break/continue/return 替换它
        _propagating: Any = None
        try:
            try:
                self._exec_codeblock_or_stmt(stmt.try_block)
            except _BreakException:
                _propagating = sys.exc_info()[1]
                raise
            except _ContinueException:
                _propagating = sys.exc_info()[1]
                raise
            except _ReturnException:
                _propagating = sys.exc_info()[1]
                raise
            except MathaRuntimeError as e:
                # catch 变量绑定消息字符串（与自举层 try 语义对齐）
                if stmt.catch_var:
                    self.env[stmt.catch_var] = str(e)
                    self._exec_codeblock_or_stmt(stmt.catch_block)
                else:
                    self._exec_codeblock_or_stmt(stmt.catch_block)
        finally:
            if stmt.finally_block is not None:
                try:
                    self._exec_codeblock_or_stmt(stmt.finally_block)
                except (_BreakException, _ContinueException, _ReturnException) as fe:
                    # finally 内的控制流异常不应替换原始传播异常
                    if _propagating is not None:
                        raise _propagating
                    raise

    def _exec_if_else_stmt(self, stmt: ast.IfElseStmt) -> None:
        """执行 if/elif/else 链式语句。"""
        for i, cond in enumerate(stmt.conditions):
            if self._eval(cond):
                self._exec_codeblock_or_stmt(stmt.blocks[i])
                return
        if stmt.else_block is not None:
            self._exec_codeblock_or_stmt(stmt.else_block)

    def _exec_switch_stmt(self, stmt: ast.SwitchStmt) -> None:
        """执行 switch 语句。"""
        value = self._eval(stmt.value)
        for case_val, case_body in stmt.cases:
            evaluated = self._eval(case_val)
            if evaluated == value:
                self._exec_switch_case(case_body)
                return
        if stmt.default_block is not None:
            self._exec_switch_case(stmt.default_block)

    def _exec_switch_case(self, case_body) -> None:
        """执行 switch case 体：支持 Binding 和赋值表达式（result = 20）。"""
        if isinstance(case_body, ast.Binding):
            self._exec_stmt(case_body)
        elif isinstance(case_body, ast.BinaryOp) and case_body.op == "=":
            # case 体中的赋值表达式：result = 20
            target = self._target_name(case_body.left)
            val = self._eval(case_body.right)
            self.env[target] = val
        else:
            self._exec_stmt_or_expr(case_body)

    def _exec_use(self, decl: ast.ImportDecl) -> None:
        """处理 use 语句：从模块导入命名到当前命名空间。"""
        module_name = decl.module_name
        import_list = decl.import_list or []
        alias = decl.alias

        if module_name not in self.modules:
            # 自动从文件加载模块（自举路径）
            self._log(logging.INFO, f"use '{module_name}' 未找到，尝试从文件加载...")
            if not self.load_matha_module(module_name):
                raise MathaRuntimeError(f"未找到模块 '{module_name}'")

        module_ns = self.modules[module_name]
        for name in import_list:
            if name in module_ns:
                target = alias or name
                self.env[target] = module_ns[name]
                self._log(logging.DEBUG, f"use import '{name}' → '{target}'")
            elif name in self.constructors:
                # 兼容：枚举构造函数已在全局 constructors 中
                self.env[name] = name
                self._log(logging.DEBUG, f"use import ctor '{name}'")
            elif name in self.funcs:
                # 兼容：函数已在全局 funcs 中（模块执行时已注册）
                self.env[name] = self.funcs[name]
                self._log(logging.DEBUG, f"use import func '{name}' (from funcs)")
            elif name in self.builtins:
                # 兼容：宿主/VM 内建（如 len/ord/get）可被 use 导入
                self.env[name] = self.builtins[name]
                self._log(logging.DEBUG, f"use import builtin '{name}'")
            else:
                raise MathaRuntimeError(f"模块 '{module_name}' 中未找到 '{name}'")

    def _exec_match_stmt(self, stmt: ast.MatchStmt) -> None:
        """执行 match 模式匹配语句，输出匹配结果。"""
        result = self._eval_match(stmt)
        self.outputs.append(result)
        self._log(logging.INFO, f"[output] += match → {self._fmt(result)}")

    def _eval_match(self, stmt: ast.MatchStmt) -> object:
        """求值 match 表达式，返回匹配结果。"""
        value = self._eval(stmt.scrutinee)
        # 追踪 match 绑定的变量，防止泄漏到外层作用域
        _bound_vars: set[str] = set()
        default_branch = None
        for pattern, guard, body in stmt.branches:
            if guard is not None:
                guard_val = self._eval(guard)
                if not guard_val:
                    continue
            if isinstance(pattern, ast.Variable) and pattern.name == "_":
                # 通配符作为兜底：记录第一个，后续通配符不可达
                if default_branch is None:
                    default_branch = body
                continue
            if self._match_pattern(pattern, value, _bound_vars):
                # 恢复 match 前的变量状态，防止绑定泄漏
                saved_env: dict[str, object] = {k: self.env[k] for k in _bound_vars if k in self.env}
                try:
                    result = self._eval(body)
                finally:
                    for k in _bound_vars:
                        self.env.pop(k, None)
                        if k in saved_env:
                            self.env[k] = saved_env[k]
                self._log(logging.INFO, f"match → {self._fmt(result)}")
                return result
        # 无匹配分支时，尝试默认分支（第一个通配符的 body）
        if default_branch is not None:
            saved_env: dict[str, object] = {k: self.env[k] for k in _bound_vars if k in self.env}
            try:
                result = self._eval(default_branch)
            finally:
                for k in _bound_vars:
                    self.env.pop(k, None)
                    if k in saved_env:
                        self.env[k] = saved_env[k]
            self._log(logging.INFO, f"match (default) → {self._fmt(result)}")
            return result
        raise MathaRuntimeError(f"match 无匹配分支: {self._fmt(value)}")

    def _match_pattern(self, pattern, value, bound_vars: set | None = None) -> bool:
        """模式匹配：字面量相等、构造子匹配、变量绑定。通配符由 _eval_match 单独处理。"""
        if isinstance(pattern, ast.Variable) and pattern.name == "_":
            return False  # 通配符已在前置逻辑处理，此处不应到达
        if isinstance(pattern, ast.IntegerLit):
            return pattern.value == value
        if isinstance(pattern, ast.FloatLit):
            return pattern.value == value
        if isinstance(pattern, ast.StringLit):
            return pattern.value == value
        if isinstance(pattern, ast.BoolLit):
            return pattern.value == value
        # Rust 风格构造子模式：Some(x) 匹配 tuple (None, value) 或 list [None, value]
        if isinstance(pattern, ast.ConstructorPat):
            # 将 value 视为构造子应用：tuple/list 或 dict
            if isinstance(value, (tuple, list)) and len(value) == len(pattern.fields) + 1:
                # value 是 (constructor_name, arg1, arg2, ...) 形式
                if isinstance(value[0], str) and value[0] == pattern.name:
                    for i, field_pat in enumerate(pattern.fields):
                        field_val = value[i + 1]
                        field_bvs: set[str] = set()
                        if not self._match_pattern(field_pat, field_val, field_bvs):
                            return False
                        if bound_vars is not None:
                            bound_vars.update(field_bvs)
                    return True
            # 尝试 dict 形式：{name: arg1, ...}
            if isinstance(value, dict) and pattern.name in value:
                args = value[pattern.name]
                if isinstance(args, (tuple, list)) and len(args) == len(pattern.fields):
                    for i, field_pat in enumerate(pattern.fields):
                        field_bvs: set[str] = set()
                        if not self._match_pattern(field_pat, args[i], field_bvs):
                            return False
                        if bound_vars is not None:
                            bound_vars.update(field_bvs)
                    return True
            return False
        # 变量绑定：匹配任意值，记录绑定的变量名
        if isinstance(pattern, ast.Variable):
            if bound_vars is not None:
                bound_vars.add(pattern.name)
            self.env[pattern.name] = value
            return True
        return False

    def _exec_codeblock_or_stmt(self, node) -> None:
        """统一处理代码块或单条语句的执行。"""
        if isinstance(node, ast.CodeBlock):
            for s in node.stmts:
                self._exec_stmt(s)
        else:
            self._exec_stmt(node)

    # ---------- 语句执行 ----------

    def _exec_stmt(self, stmt) -> None:
        if stmt is None:
            return
        kind = type(stmt).__name__
        self._log(logging.DEBUG, f"stmt {kind}")
        if isinstance(stmt, ast.Binding):
            target = self._target_name(stmt.target)
            self._log_enter(f"bind {target}")
            val = self._eval(stmt.value)
            self.env[target] = val
            self._log_exit(f"bind {target}", val)
            self._log(logging.DEBUG, f"env[{target!r}] = {self._fmt(val)}")
        elif isinstance(stmt, ast.LetBinding):
            # 语句级 let：绑定并执行 body，变量留在 env 中
            # 预注册绑定名（支持递归自引用）
            _saved = self.env.get(stmt.name)
            self.env.setdefault(stmt.name, None)
            val = self._eval(stmt.value)
            self.env[stmt.name] = val
            self._log(logging.DEBUG, f"stmt LetBinding '{stmt.name}' = {self._fmt(val)}")
            if stmt.body is not None:
                self._exec_stmt_or_expr(stmt.body)
            # 不清理语句级 let 变量（与 Binding 行为一致）
        elif isinstance(stmt, ast.LetTupleBinding):
            # 语句级 let 元组解构
            val = self._eval(stmt.value)
            if isinstance(val, tuple):
                for i, name in enumerate(stmt.names):
                    self.env[name] = val[i] if i < len(val) else None
            self._log(logging.DEBUG, f"stmt LetTupleBinding {stmt.names}")
            if stmt.body is not None:
                self._exec_stmt_or_expr(stmt.body)
        elif isinstance(stmt, ast.Output):
            self._log_enter("output")
            val = self._eval(stmt.expr) if stmt.expr is not None else None
            self.outputs.append(val)
            self._log_exit("output", val)
            self._log(logging.INFO, f"[output] += {self._fmt(val)}")
        elif isinstance(stmt, ast.OutputTrail):
            self._log(logging.DEBUG, "OutputTrail → 透传")
            self._exec_stmt(stmt.output)
        elif isinstance(stmt, ast.ListLiteral):
            # ListLiteral 在语句语境中视为输出（如 let x = ... in [1]）
            # 取首个元素作为输出值，兼容自测块 [1] → 输出 1
            result = [self._eval(e) for e in stmt.elements]
            self.outputs.append(result[0] if result else None)
            self._log(logging.INFO, f"[output] += {self._fmt(result[0] if result else None)}")
        elif isinstance(stmt, ast.CodeBlock):
            self._log(logging.DEBUG, f"CodeBlock ({len(stmt.stmts)} stmts)")
            # 预注册所有 let 绑定（支持递归自引用：sum_list = ...sum_list...）
            for s in stmt.stmts:
                if isinstance(s, ast.LetBinding) and s.body is None:
                    self.env.setdefault(s.name, None)
            for i, s in enumerate(stmt.stmts):
                self._log(logging.DEBUG, f"  block[{i}]")
                self._exec_stmt(s)
        elif isinstance(stmt, ast.SetUp):
            self._exec_set_up(stmt)
        elif isinstance(stmt, ast.ReadBlock):
            content = stmt.content
            if isinstance(content, ast.CommandLiteral):
                self.trace.append(f"【{content.text}】")
                self._log(logging.INFO, f"[trace] += 【{content.text}】")
            else:
                self._log(logging.DEBUG, f"ReadBlock content={type(content).__name__}")
        elif isinstance(stmt, ast.GenStmt):
            self._exec_gen_stmt(stmt)
        elif isinstance(stmt, ast.ChainStmt):
            self._log(logging.DEBUG, f"ChainStmt ({len(stmt.stmts)} links)")
            for i, link in enumerate(stmt.stmts):
                self._log(logging.DEBUG, f"  chain[{i}]")
                self._exec_stmt(link)
        elif isinstance(stmt, ast.MechUnit):
            self._exec_stmt(stmt.body)
        elif isinstance(stmt, ast.IfStmt):
            self._exec_if_stmt(stmt)
        elif isinstance(stmt, ast.WhileStmt):
            self._exec_while_stmt(stmt)
        elif isinstance(stmt, ast.ForStmt):
            self._exec_for_stmt(stmt)
        elif isinstance(stmt, ast.MatchStmt):
            self._exec_match_stmt(stmt)
        elif isinstance(stmt, ast.GoStmt):
            self._log_enter("go")
            v = self._eval(stmt.expr)
            self.trace.append(f"go {v}")
            self._log_exit("go", v)
            self._log(logging.INFO, f"[trace] += go {self._fmt(v)}")
        elif isinstance(stmt, ast.FuncApp):
            # 表达式语句：func(...) 无返回值，执行后丢弃结果
            self._eval(stmt)
        elif isinstance(stmt, ast.FuncDef):
            # 代码块内的函数定义：注册到当前解释器（保持向后兼容）
            self.funcs[stmt.name] = stmt
            # 同时创建 closure tuple 存入 env，使递归函数能在闭包中查找自身
            closure = ("__closure__", stmt.body.params, stmt.body.body, list(self.env.items()))
            self.env[stmt.name] = closure
            self._log(logging.INFO, f"exec func '{stmt.name}' in block")
        elif isinstance(stmt, ast.GlobalIdStmt):
            # 全局编号语句：跨文件绑定标记
            self._log(logging.DEBUG, f"exec GlobalIdStmt '{stmt.code_id}'")
        elif isinstance(stmt, ast.BreakStmt):
            self._exec_break()
        elif isinstance(stmt, ast.ContinueStmt):
            self._exec_continue()
        elif isinstance(stmt, ast.ReturnStmt):
            value = self._eval(stmt.value) if stmt.value is not None else None
            self._exec_return(value)
        elif isinstance(stmt, ast.ThrowStmt):
            self._exec_throw(self._eval(stmt.value))
        elif isinstance(stmt, ast.TryStmt):
            self._exec_try(stmt)
        elif isinstance(stmt, ast.SwitchStmt):
            self._exec_switch_stmt(stmt)
        elif isinstance(stmt, ast.IfElseStmt):
            self._exec_if_else_stmt(stmt)
        elif isinstance(stmt, dict):
            self._exec_dict_stmt(stmt)
        else:
            self._log(logging.DEBUG, f"expr-stmt fallback eval {kind}")
            self._eval(stmt)

    def _exec_stmt_or_expr(self, node) -> None:
        """执行语句或表达式：语句走 _exec_stmt，表达式走 _eval。"""
        if isinstance(node, (ast.Binding, ast.Output, ast.OutputTrail, ast.CodeBlock,
                             ast.SetUp, ast.ReadBlock, ast.GenStmt, ast.ChainStmt,
                             ast.MechUnit, ast.IfStmt, ast.WhileStmt, ast.ForStmt,
                             ast.MatchStmt, ast.GoStmt, ast.LetBinding,
                             ast.LetTupleBinding, ast.GlobalIdStmt,
                             ast.BreakStmt, ast.ContinueStmt, ast.ReturnStmt,
                             ast.ThrowStmt, ast.RaiseExpr, ast.TryStmt, ast.SwitchStmt,
                             ast.ListLiteral)):
            self._exec_stmt(node)
        else:
            self._eval(node)

    def _exec_gen_stmt(self, stmt: ast.GenStmt) -> None:
        content = stmt.content
        seg = stmt.generate.seg_id
        ctype = type(content).__name__ if content is not None else "None"
        self._log(logging.DEBUG, f"GenStmt #{seg} content={ctype}")
        if isinstance(content, ast.CommandLiteral):
            # 命令字面量现为纯规格追踪标记（命令占位符机制已移除），
            # 不再分派真实字符处理——实际 I/O 由函数式扫描器承担。
            prefix = f"#{seg}：" if seg is not None else "#："
            self.trace.append(f"{prefix}{content.text}")
            self._log(logging.INFO, f"[trace] += {prefix}{content.text}")
        elif isinstance(content, ast.OutputTrail):
            self._exec_stmt(content.output)
        elif isinstance(content, ast.Output):
            self._exec_stmt(content)
        elif isinstance(content, ast.GoStmt):
            self._exec_stmt(content)
        else:
            self._eval(content)

    # ---------- 表达式求值 ----------

    def _eval(self, expr) -> object:
        # 字面量：高频且无副作用，只 DEBUG 记一行，不做 enter/exit（省深度噪音）
        if isinstance(expr, ast.IntegerLit):
            self._log(logging.DEBUG, f"eval Int {expr.value}")
            return expr.value
        if isinstance(expr, ast.FloatLit):
            self._log(logging.DEBUG, f"eval Float {expr.value}")
            return expr.value
        if isinstance(expr, ast.StringLit):
            self._log(logging.DEBUG, f"eval Str {self._fmt(expr.value)}")
            return expr.value
        if isinstance(expr, ast.BoolLit):
            self._log(logging.DEBUG, f"eval Bool {expr.value}")
            return expr.value
        if isinstance(expr, ast.Variable):
            return self._eval_variable(expr)
        if isinstance(expr, ast.IfExpr):
            # 三元条件 cond ? then : else（短路：仅求值被选中分支）
            self._log_enter("eval If")
            cond = self._eval(expr.cond)
            branch = expr.then if cond else expr.else_
            if isinstance(branch, ast.CodeBlock):
                # 代码块形式：执行后取最后一个输出
                for s in branch.stmts:
                    self._exec_stmt(s)
                r = self.outputs[-1] if self.outputs else None
            else:
                r = self._eval(branch)
            self._log_exit("eval If", r)
            return r
        if isinstance(expr, ast.MatchStmt):
            return self._eval_match(expr)
        if isinstance(expr, ast.BinaryOp):
            return self._eval_binary(expr)
        if isinstance(expr, ast.UnaryOp):
            self._log_enter("eval Unary", f"'{expr.op}'")
            if expr.op == "null":
                # null / none / undefined 关键字：无操作数，直接返回 None
                self._log_exit("eval Unary", None)
                return None
            v = self._eval(expr.operand)
            if expr.op == "-":
                r = -v
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "^":
                r = v ** 0.5
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "++":
                if isinstance(v, (int, float)):
                    r = v + 1
                else:
                    raise MathaRuntimeError(f"++ 仅适用于数值，实际 {type(v).__name__}")
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "--":
                if isinstance(v, (int, float)):
                    r = v - 1
                else:
                    raise MathaRuntimeError(f"-- 仅适用于数值，实际 {type(v).__name__}")
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "!":
                # 逻辑非
                r = not v
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "not":
                # 逻辑非（英文关键字形式）
                r = not v
                self._log_exit("eval Unary", r)
                return r
            if expr.op == "~":
                # 位取反
                if isinstance(v, int):
                    r = ~v
                    self._log_exit("eval Unary", r)
                    return r
                raise MathaRuntimeError(f"~ 仅适用于整数，实际 {type(v).__name__}")
            raise MathaRuntimeError(f"未知一元运算符 '{expr.op}'")
        if isinstance(expr, ast.CodeBlock):
            # 代码块作为表达式：隔离 outputs，防止中间输出泄漏到全局
            saved_outputs = self.outputs
            self.outputs = []
            try:
                for s in expr.stmts:
                    self._exec_stmt(s)
                if self.outputs:
                    return self.outputs[-1]
                # 无输出时，取最后一个非 Output 语句的值
                last = expr.stmts[-1] if expr.stmts else None
                if last is not None and not isinstance(last, ast.Output):
                    return self._eval(last)
                return None
            finally:
                self.outputs = saved_outputs
        if isinstance(expr, ast.TypeOfExpr):
            v = self._eval(expr.operand)
            return type(v).__name__
        if isinstance(expr, ast.IsExpr):
            left_val = self._eval(expr.left)
            right_val = self._eval(expr.right)
            return left_val is right_val
        if isinstance(expr, ast.Belongs):
            # ∈ 属于判断：左操作数是否在右操作数中
            left_val = self._eval(expr.left)
            right_val = self._eval(expr.right)
            if isinstance(right_val, (list, tuple, str, dict, set)):
                return left_val in right_val
            raise MathaRuntimeError(f"∈ 右侧需为序列/集合/字典，实际 {type(right_val).__name__}")
        if isinstance(expr, ast.FuncApp):
            return self._eval_func_app(expr)
        if isinstance(expr, ast.Lambda):
            self._log(logging.DEBUG, "eval Lambda → closure")
            self._log(logging.DEBUG, f"lambda closure captured keys: {list(self.env.keys())}")
            matha_env = getattr(self, '_matha_env', list(self.env.items()))
            return ("__closure__", expr, matha_env)
        if isinstance(expr, ast.LetBinding):
            # let x = val in body — 局部绑定
            # 递归绑定：使用占位符使 lambda 闭包能引用自身
            is_rec = expr.is_recursive
            ph = None
            if expr.is_recursive:
                ph = _RecPlaceholder(expr.name)
                ph._interp = self
                self.env[expr.name] = ph
                # 让 Lambda 捕获的 list 环境也包含占位符，
                # 这样递归调用 _iter(...) 时能在闭包环境中解析到自身
                me = getattr(self, '_matha_env', None)
                if isinstance(me, list):
                    me.append((expr.name, ph))
            # 函数式绑定 let f(args) = body / let rec f(args) = body：
            # parser 把形参放在 expr.params，value 是裸函数体，需包装为 Lambda
            lb_params = getattr(expr, 'params', None)
            if lb_params:
                param_vars = []
                for p in lb_params:
                    pv = p[0] if isinstance(p, tuple) else p
                    if not isinstance(pv, ast.Variable):
                        pv = ast.Variable(name=str(pv))
                    param_vars.append(pv)
                val = self._eval(ast.Lambda(params=param_vars, body=expr.value))
            else:
                val = self._eval(expr.value)
            if expr.is_recursive:
                ph._ref[0] = val  # 通过占位符的引用更新实际值
            else:
                # 普通 let 绑定同步到 list 环境，供内层闭包捕获外层变量
                me2 = getattr(self, '_matha_env', None)
                if isinstance(me2, list):
                    me2.append((expr.name, val))
            self.env[expr.name] = val
            self._log(logging.DEBUG, f"eval LetBinding '{expr.name}' = {self._fmt(val)}")
            if expr.body is not None:
                r = self._eval(expr.body)
            else:
                r = val
            # 清理局部绑定（递归绑定保留在 env 中供闭包访问）
            if not is_rec:
                self.env.pop(expr.name, None)
            return r
        if isinstance(expr, ast.DictLiteral):
            result = {}
            for k, v in zip(expr.keys, expr.values):
                # dict 键：如果是 Variable，取其名称作为字符串键；否则正常求值
                if isinstance(k, ast.Variable):
                    key = k.name
                else:
                    key = self._eval(k)
                result[key] = self._eval(v)
            return result
        if isinstance(expr, ast.ListLiteral):
            return [self._eval(e) for e in expr.elements]
        if isinstance(expr, ast.TupleExpr):
            return tuple(self._eval(e) for e in expr.elements)
        if isinstance(expr, ast.SetConstruct):
            if expr.form == "enumeration":
                return set(self._eval(e) for e in (expr.literals or []))
            elif expr.form == "comprehension":
                # {x | cond} 形式：从 env 中已有的变量推导
                var_name = getattr(expr.variables, "0") if expr.variables else None
                result = set()
                # 简化处理：对 comprehension 形式暂不支持
                raise MathaRuntimeError("集合理解形式暂不支持")
            return result
        if isinstance(expr, ast.LetTupleBinding):
            # let (a, b) = tuple_val in body
            val = self._eval(expr.value)
            if isinstance(val, tuple):
                # 跳过 4 元组 closure 的 "__closure__" 标记：
                # ("__closure__", params, body, env) 应解构为 (params, body, env)
                start = 0
                if len(val) == 4 and val[0] == "__closure__":
                    start = 1
                for i, name in enumerate(expr.names):
                    idx = start + i
                    if idx < len(val):
                        self.env[name] = val[idx]
                    else:
                        self.env[name] = None
                self._log(logging.DEBUG,
                          f"eval LetTupleBinding {expr.names} = {self._fmt(val)}")
                if expr.body is not None:
                    r = self._eval(expr.body)
                else:
                    r = val
            else:
                raise MathaRuntimeError(
                    f"元组解构期望元组，实际得到 {type(val).__name__}")
            # 清理局部绑定
            for name in expr.names:
                self.env.pop(name, None)
            return r
        if isinstance(expr, ast.RaiseExpr):
            # raise <expr>：消息字符串异常（与自举层 调用捕获 语义对齐——
            # 自举层异常只能以消息字符串穿越 VM 帧边界）
            raise MathaRuntimeError(str(self._eval(expr.value)))
        if isinstance(expr, ast.Output):
            # [X] 形式解析为 Output 出现在参数位置
            if expr.expr is None:
                # 空 []
                return []
            inner = self._eval(expr.expr)
            # 如果 inner 是字符串（Matha 没有字面量列表，Parser 把 [a,b,c] 解析为 Output(StringLit)）
            # 将字符串按逗号分隔，逐个尝试转数字
            if isinstance(inner, str):
                parts = [p.strip() for p in inner.split(",") if p.strip()]
                nums = []
                all_ok = True
                for p in parts:
                    try:
                        if "." in p:
                            nums.append(float(p))
                        else:
                            try:
                                nums.append(int(p))
                            except ValueError:
                                nums.append(float(p))
                    except ValueError:
                        all_ok = False
                        break
                if all_ok:
                    return nums
                return inner  # 非数字字符串原样返回
            return [inner]
        if isinstance(expr, ast.IndexExpr):
            container = self._eval(expr.container)
            index = self._eval(expr.index)
            if isinstance(container, (list, tuple, str)) and isinstance(index, int):
                return container[index]
            if isinstance(container, _StructInstance) and isinstance(index, str):
                return container[index]
            # dict 字符串索引：支持 Matha 自举代码中 dict["键"] 形式
            if isinstance(container, dict) and isinstance(index, str):
                return container.get(index)
            raise MathaRuntimeError(f"索引操作不支持: {type(container).__name__}[{index}]")
        if isinstance(expr, ast.SliceExpr):
            container = self._eval(expr.container)
            start = self._eval(expr.start) if expr.start is not None else None
            end = self._eval(expr.end) if expr.end is not None else None
            if isinstance(container, (list, tuple, str)):
                return container[start:end]
            raise MathaRuntimeError(f"切片操作不支持: {type(container).__name__}[{start}:{end}]")
        if isinstance(expr, ast.PathExpr):
            # 属性访问：expr.left.expr.right → getattr(左值, 右值字段名)
            left_val = self._eval(expr.left)
            field_name = expr.right
            if isinstance(left_val, tuple) and isinstance(field_name, int):
                # (a, b, c)[2] 形式：元组索引
                if 0 <= field_name < len(left_val):
                    return left_val[field_name]
                raise MathaRuntimeError(f"元组索引越界: {field_name}")
            if isinstance(left_val, dict) and isinstance(field_name, str):
                v = left_val.get(field_name)
                if v is not None:
                    return v
                # 模块属性 fallback：若对象是模块命名空间且属性缺失，
                # 退回内建函数表查询（让 运行时引擎.sin 等透传到宿主内建 sin）。
                if field_name in self.builtins:
                    return self.builtins[field_name]
                return None
            # 一般属性访问：尝试 getattr
            try:
                return getattr(left_val, field_name)
            except AttributeError:
                # 缺失属性返回 None（支持空 struct 如 Empty().missing）
                if isinstance(left_val, _StructInstance):
                    return None
                raise MathaRuntimeError(f"属性访问失败: {type(left_val).__name__}.{field_name}")
        if isinstance(expr, ast.SafePathExpr):
            # ?. 可选链：null 时返回 None
            left_val = self._eval(expr.left)
            if left_val is None:
                return None
            if expr.is_index:
                idx = self._eval(expr.right)
                if isinstance(left_val, (list, tuple, str)) and isinstance(idx, int):
                    return left_val[idx]
                raise MathaRuntimeError(f"?. 下标访问失败: {type(left_val).__name__}[{idx}]")
            else:
                field_name = expr.right
                try:
                    return getattr(left_val, field_name)
                except AttributeError:
                    return None
        # Matha parser 生成的 dict AST 节点
        if isinstance(expr, dict):
            return self._eval_dict_ast(expr)
        raise MathaRuntimeError(f"暂不支持求值: {type(expr).__name__}")

    def _eval_dict_ast(self, node: dict) -> object:
        """将 Matha parser 生成的 dict AST 节点转为 Python 值。"""
        t = node.get("类型")
        if t == "变量":
            return self._eval_variable(ast.Variable(name=node["名"]))
        if t == "整数":
            return node["值"]
        if t == "浮点":
            return node["值"]
        if t == "字符串":
            return node["值"]
        if t == "布尔":
            return node["值"]
        if t == "二元运算":
            return self._eval_binary(
                ast.BinaryOp(op=node["运算符"],
                             left=node["左"],
                             right=node["右"]))
        if t == "一元运算":
            return self._eval(ast.UnaryOp(op=node["运算符"],
                                          operand=node["操作数"]))
        if t == "if":
            cond = self._eval_dict_ast(node["条件"])
            then_b = self._eval_dict_ast(node["真分支"])
            else_b = self._eval_dict_ast(node["假分支"])
            return then_b if cond else else_b
        if t == "lambda":
            # 返回 closure tuple: ("__closure__", params, body, env)
            # 使用 _matha_env 保证 env 始终是 list-of-tuples
            matha_env = getattr(self, '_matha_env', list(self.env.items()))
            params = [self._eval_dict_ast(p) if isinstance(p, dict) else p
                      for p in node.get("参数", [])]
            body = node.get("体")
            return ("__closure__", params, body, matha_env)
        if t == "函数应用":
            func_val = self._eval_dict_ast(node["函数"])
            arg_val = self._eval_dict_ast(node["参数"])
            return self._apply(func_val, arg_val)
        if t == "列表":
            return [self._eval_dict_ast(e) for e in node.get("元素", [])]
        raise MathaRuntimeError(f"不支持的 dict AST 类型: {t}")

    def _exec_dict_stmt(self, node: dict) -> None:
        """执行 dict AST 语句节点。"""
        t = node.get("类型")
        if t == "绑定":
            name = node.get("名")
            val = self._eval_dict_ast(node.get("值"))
            self.env[name] = val
            self._log(logging.DEBUG, f"dict-bind {name} = {self._fmt(val)}")
        elif t == "if":
            cond = self._eval_dict_ast(node["条件"])
            if cond:
                self._exec_dict_stmt(node["真分支"])
            else:
                self._exec_dict_stmt(node["假分支"])
        elif t == "while":
            self._exec_dict_while(node["条件"], node["体"])
        elif t == "for":
            self._exec_dict_for(node["变量"], node["迭代"], node["体"])
        elif t == "函数定义":
            name = node.get("名")
            body = node.get("体")
            params = [p if not isinstance(p, dict) else self._eval_dict_ast(p)
                      for p in node.get("参数", [])]
            # 创建 lambda：params 可能是 Variable dict 或字符串
            lam_params = []
            for p in params:
                if isinstance(p, dict) and p.get("类型") == "变量":
                    lam_params.append(ast.Variable(name=p["名"]))
                elif isinstance(p, ast.Variable):
                    lam_params.append(p)
                else:
                    lam_params.append(ast.Variable(name=str(p)))
            lam = ast.Lambda(params=lam_params, body=body)
            fdef = ast.FuncDef(name=name, annotation=None,
                               func_type=None, body=lam, else_body=None)
            self.funcs[name] = fdef
            self.env[name] = ("__closure__", lam_params, body, list(self.env.items()))
            self._log(logging.INFO, f"dict-func '{name}'")
        elif t == "程序":
            for stmt in node.get("声明", []):
                self._exec_dict_stmt(stmt)
        else:
            self._log(logging.DEBUG, f"dict-stmt fallback eval {t}")
            self._eval_dict_ast(node)

    def _exec_dict_while(self, cond: dict, body: dict) -> None:
        while self._eval_dict_ast(cond):
            self._exec_dict_stmt(body)

    def _exec_dict_for(self, var_name: str, iterable: dict, body: dict) -> None:
        items = self._eval_dict_ast(iterable)
        if isinstance(items, (list, tuple)):
            for item in items:
                self.env[var_name] = item
                self._exec_dict_stmt(body)

    def _override_matha_exec_funcs(self) -> None:
        """将 Matha 的 执行语句/执行声明 替换为兼容 Python AST 的包装器。"""
        pass

    def _exec_matha_stmt(self, stmt, env) -> tuple:
        """Matha 执行语句：兼容 Python AST 和 dict AST 节点。"""
        if isinstance(stmt, dict):
            # dict AST 节点：使用 dict 路径
            t = stmt.get("类型")
            if t == "绑定":
                v = self._eval_dict_ast(stmt.get("值"))
                new_env = self._exec_matha_bind(env, stmt.get("名"), v)
                return (v, new_env)
            if t == "程序":
                return self._exec_matha_stmt_list(stmt.get("声明", []), env)
            return (None, env)
        # Python AST 节点：使用 Python 路径
        if isinstance(stmt, ast.Binding):
            target = self._target_name(stmt.target)
            v = self._eval(stmt.value)
            new_env = self._exec_matha_bind(env, target, v)
            return (v, new_env)
        if isinstance(stmt, ast.Output):
            val = self._eval(stmt.expr) if stmt.expr is not None else None
            self.outputs.append(val)
            return (val, env)
        if isinstance(stmt, ast.CodeBlock):
            return self._exec_matha_stmt_list(stmt.stmts, env)
        if isinstance(stmt, ast.IfStmt):
            cond = self._eval(stmt.cond)
            if cond:
                return self._exec_matha_stmt(stmt.then, env)
            else:
                return self._exec_matha_stmt(stmt.else_, env)
        if isinstance(stmt, ast.WhileStmt):
            return self._exec_matha_while(stmt.cond, stmt.body, env)
        if isinstance(stmt, ast.ForStmt):
            return self._exec_matha_for(stmt.var_name, stmt.iterable, stmt.body, env)
        if isinstance(stmt, ast.FuncDef):
            self.funcs[stmt.name] = stmt
            closure = ("__closure__", stmt.body.params, stmt.body.body, list(env.items()) if isinstance(env, list) else list(self.env.items()))
            new_env = self._exec_matha_bind(env, stmt.name, closure)
            return (closure, new_env)
        return (None, env)

    def _exec_matha_decl(self, decl, env) -> tuple:
        """Matha 执行声明：兼容 Python AST 和 dict AST 节点。"""
        if isinstance(decl, dict):
            t = decl.get("类型")
            if t == "绑定":
                v = self._eval_dict_ast(decl.get("值"))
                new_env = self._exec_matha_bind(env, decl.get("名"), v)
                return (v, new_env)
            if t == "函数定义":
                v = self._eval_dict_ast(decl.get("体"))
                new_env = self._exec_matha_bind(env, decl.get("名"), v)
                return (v, new_env)
            if t == "程序":
                return self._exec_matha_decl_list(decl.get("声明", []), env)
            return (None, env)
        # Python AST 节点
        if isinstance(decl, ast.Binding):
            target = self._target_name(decl.target)
            v = self._eval(decl.value)
            new_env = self._exec_matha_bind(env, target, v)
            return (v, new_env)
        if isinstance(decl, ast.FuncDef):
            self.funcs[decl.name] = decl
            matha_env = getattr(self, '_matha_env', list(env.items()) if isinstance(env, list) else list(self.env.items()))
            closure = ("__closure__", decl.body.params, decl.body.body, matha_env)
            new_env = self._exec_matha_bind(env, decl.name, closure)
            return (closure, new_env)
        if isinstance(decl, ast.CodeBlock):
            return self._exec_matha_decl_list(decl.stmts, env)
        return (None, env)

    def _exec_matha_stmt_list(self, stmts, env) -> tuple:
        """执行语句列表。"""
        if not stmts:
            return (None, env)
        if isinstance(stmts, dict):
            return self._exec_matha_stmt(stmts, env)
        v, env2 = self._exec_matha_stmt(stmts[0], env)
        _, env3 = self._exec_matha_stmt_list(stmts[1:], env2)
        return (v, env3)

    def _exec_matha_decl_list(self, decls, env) -> tuple:
        """执行声明列表。"""
        if not decls:
            return (None, env)
        v, env2 = self._exec_matha_decl(decls[0], env)
        _, env3 = self._exec_matha_decl_list(decls[1:], env2)
        return (v, env3)

    def _exec_matha_bind(self, env, name, value):
        """绑定环境变量：兼容 list-of-tuples 和 dict。"""
        # 规范化 name：Variable 节点 → 字符串，保证 Matha 代码的 env[0][0] = name 比较正确
        if isinstance(name, ast.Variable):
            name = name.name
        elif isinstance(name, tuple) and name and isinstance(name[0], ast.Variable):
            name = name[0].name
        if isinstance(env, list):
            return [(name, value)] + env
        elif isinstance(env, dict):
            d = dict(env)
            d[name] = value
            return d
        return env

    def _eval_variable(self, node: ast.Variable) -> object:
        name = node.name
        # 统一查找：env → funcs → builtins → constructors
        if name in self.env:
            v = self.env[name]
            self._log(logging.DEBUG,
                      f"eval Var '{name}' → env {self._fmt(v)}")
            # 兼容：lambda dict（Matha 自举路径）转为 closure tuple
            if isinstance(v, dict) and v.get("类型") == "lambda":
                matha_env = getattr(self, '_matha_env', list(self.env.items()))
                v = ("__closure__", v["参数"], v["体"], matha_env)
            return v
        if name in self.funcs:
            self._log(logging.DEBUG, f"eval Var '{name}' → FuncDef")
            return self.funcs[name]
        if name in self.builtins:
            self._log(logging.DEBUG, f"eval Var '{name}' → builtin")
            return self.builtins[name]
        if name in self.constructors:
            self._log(logging.DEBUG, f"eval Var '{name}' → ctor '{name}'")
            return name
        raise MathaRuntimeError(f"未定义变量 '{name}'")

    @staticmethod
    def _ensure_set(v: object) -> set:
        """将值归一化为可迭代的集合。"""
        if isinstance(v, set):
            return v
        if isinstance(v, (list, tuple, str)):
            return set(v)
        return {v}

    def _eval_binary(self, node: ast.BinaryOp) -> object:
        self._log_enter("eval Binary", f"'{node.op}'")
        op = node.op
        # 短路求值：&& || and or 仅在有需要时求值右操作数
        if op == "&&" or op == "and":
            l = self._eval(node.left)
            if not l:
                self._log_exit("eval Binary", l)
                return l
            r = self._eval(node.right)
            result = l and r
            self._log_exit("eval Binary", result)
            return result
        if op == "||" or op == "or":
            l = self._eval(node.left)
            if l:
                self._log_exit("eval Binary", l)
                return l
            r = self._eval(node.right)
            result = l or r
            self._log_exit("eval Binary", result)
            return result
        l = self._eval(node.left)
        r = self._eval(node.right)
        try:
            if op == "+":
                if l is None or r is None:
                    raise MathaRuntimeError(f"+ 操作数含 None: left={l!r}, right={r!r}")
                # 兼容：dict env → list-of-tuples（Matha 自举路径）
                if isinstance(r, dict):
                    r = list(r.items())
                if isinstance(l, dict):
                    l = list(l.items())
                # str 与数值自动转换
                if isinstance(l, str) and isinstance(r, (int, float)):
                    r = str(r)
                elif isinstance(r, str) and isinstance(l, (int, float)):
                    l = str(l)
                result = l + r
                # 注意：result 可能是含闭包的列表（循环结构），裸 repr 会死循环，必须用 _fmt
                self._log(logging.DEBUG, f"  + 结果: {self._fmt(result)}")
            elif op == "-":
                if isinstance(l, (str, list)) or isinstance(r, (str, list)):
                    raise MathaRuntimeError(f"- 不适用于字符串/列表")
                result = l - r
            elif op == "*":
                if isinstance(l, (int, float)) and isinstance(r, (int, float)):
                    result = l * r
                elif isinstance(l, str) and isinstance(r, int):
                    result = l * r
                elif isinstance(l, int) and isinstance(r, str):
                    result = l * r
                else:
                    raise MathaRuntimeError(f"* 操作数类型不支持: left={l!r}({type(l).__name__}), right={r!r}({type(r).__name__})")
                self._log(logging.DEBUG, f"  * 结果: {result!r}")
            elif op == "/":
                if r == 0:
                    raise MathaRuntimeError(f"除零错误: {l!r} / 0")
                result = l / r
                self._log(logging.DEBUG, f"  / 结果: {result!r}")
            elif op == "**":
                if l is None or r is None:
                    raise MathaRuntimeError(f"** 操作数含 None")
                result = l ** r
            elif op == "%":
                if r == 0:
                    raise MathaRuntimeError(f"取模除零错误: {l!r} % 0")
                if l is None or r is None:
                    raise MathaRuntimeError(f"% 操作数含 None: left={l!r}, right={r!r}")
                result = l % r
                self._log(logging.DEBUG, f"  % 结果: {result!r}")
            elif op == "<":
                result = l < r
                self._log(logging.DEBUG, f"  < 结果: {result!r}")
            elif op == ">":
                result = l > r
                self._log(logging.DEBUG, f"  > 结果: {result!r}")
            elif op == "<=":
                result = l <= r
                self._log(logging.DEBUG, f"  <= 结果: {result!r}")
            elif op == ">=":
                result = l >= r
                self._log(logging.DEBUG, f"  >= 结果: {result!r}")
            elif op == "=":
                result = l == r
                self._log(logging.DEBUG, f"  == 结果: {result!r}")
            elif op == "==":
                result = l == r
                self._log(logging.DEBUG, f"  == 结果: {result!r}")
            elif op == "!=":
                result = l != r
                self._log(logging.DEBUG, f"  != 结果: {result!r}")
            elif op == "and":
                if not l:
                    self._log_exit("eval Binary", l)
                    return l
                result = l and r
                self._log(logging.DEBUG, f"  and 结果: {self._fmt(result)}")
                return result
            elif op == "or":
                if l:
                    self._log_exit("eval Binary", l)
                    return l
                result = l or r
                self._log(logging.DEBUG, f"  or 结果: {result!r}")
                return result
            elif op == "&&":
                if not l:
                    self._log_exit("eval Binary", l)
                    return l
                r = self._eval(node.right)
                result = l and r
                self._log(logging.DEBUG, f"  && 结果: {self._fmt(result)}")
                return result
            elif op == "||":
                if l:
                    self._log_exit("eval Binary", l)
                    return l
                r = self._eval(node.right)
                result = l or r
                self._log(logging.DEBUG, f"  || 结果: {self._fmt(result)}")
                return result
            elif op == "===":
                result = (l is r) and type(l) == type(r)
                self._log(logging.DEBUG, f"  === 结果: {result!r}")
                return result
            elif op == "!==":
                result = not ((l is r) and type(l) == type(r))
                self._log(logging.DEBUG, f"  !== 结果: {result!r}")
                return result
            elif op == "//":
                if r == 0:
                    raise MathaRuntimeError(f"整除除零错误: {l!r} // 0")
                result = l // r
                self._log(logging.DEBUG, f"  // 结果: {result!r}")
            elif op == "**":
                if l is None or r is None:
                    raise MathaRuntimeError(f"** 操作数含 None")
                result = l ** r
                self._log(logging.DEBUG, f"  ** 结果: {result!r}")
            elif op == "is":
                result = (l is r)
                self._log(logging.DEBUG, f"  is 结果: {result!r}")
            elif op == "→":
                if l is None:
                    raise MathaRuntimeError(f"→ 左操作数含 None")
                if callable(l):
                    result = l(r)
                elif isinstance(l, tuple) and l and l[0] == "__closure__":
                    if len(l) == 4:
                        params, body, captured = l[1], l[2], l[3]
                        lam = ast.Lambda(params=params, body=body)
                    else:
                        _, lam, captured = l
                    result = self._call_lambda(lam, captured, [r])
                elif isinstance(l, ast.FuncDef):
                    result = self._call_func(l, [r])
                else:
                    raise MathaRuntimeError(f"右箭头运算符 左侧必须可调用，实际 {type(l).__name__}")
            elif op == " in ":
                if isinstance(r, (list, tuple, str, dict, set)):
                    result = l in r
                elif isinstance(r, ast.SetConstruct):
                    result = l in self._eval(r)
                else:
                    raise MathaRuntimeError(f"in 右侧需为序列/集合/字典，实际 {type(r).__name__}")
            # 位运算
            elif op == "&":
                if isinstance(l, int) and isinstance(r, int):
                    result = l & r
                else:
                    raise MathaRuntimeError(f"& 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            elif op == "|":
                if isinstance(l, int) and isinstance(r, int):
                    result = l | r
                else:
                    raise MathaRuntimeError(f"| 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            elif op == "^":
                if isinstance(l, int) and isinstance(r, int):
                    result = l ^ r
                else:
                    raise MathaRuntimeError(f"^ 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            elif op == "⊕":
                if isinstance(l, int) and isinstance(r, int):
                    result = l ^ r
                else:
                    raise MathaRuntimeError(f"⊕ 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            elif op == "<<":
                if isinstance(l, int) and isinstance(r, int):
                    result = l << r
                else:
                    raise MathaRuntimeError(f"<< 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            elif op == ">>":
                if isinstance(l, int) and isinstance(r, int):
                    result = l >> r
                else:
                    raise MathaRuntimeError(f">> 操作数需为整数，actual left={type(l).__name__}, right={type(r).__name__}")
            # 集合运算
            elif op == "∪":
                result = set(self._ensure_set(l)) | set(self._ensure_set(r))
            elif op == "∩":
                result = set(self._ensure_set(l)) & set(self._ensure_set(r))
            elif op == "⊖":
                result = set(self._ensure_set(l)) - set(self._ensure_set(r))
            elif op == "~":
                s = set(self._ensure_set(l))
                u = self.env.get("U")
                if u is not None:
                    result = set(self._ensure_set(u)) - s
                else:
                    result = frozenset() - s
            elif op == "×":
                ls = self._ensure_set(l)
                rs = self._ensure_set(r)
                result = [(a, b) for a in ls for b in rs]
            elif op == "⊆":
                ls = set(self._ensure_set(l))
                rs = set(self._ensure_set(r))
                result = ls <= rs
            # 空值合并
            elif op == "??":
                result = l if l is not None else r
            else:
                raise MathaRuntimeError(f"未知运算符 '{op}'")
        except TypeError as e:
            raise MathaRuntimeError(f"类型错误: {e}") from None
        except ValueError as e:
            raise MathaRuntimeError(f"值错误: {e}") from None
        self._log(logging.DEBUG,
                  f"binary {self._fmt(l)} {op} {self._fmt(r)} → {self._fmt(result)}")
        self._log_exit("eval Binary", result)
        return result

    def _eval_func_app(self, node: ast.FuncApp) -> object:
        self._log_enter("eval FuncApp")
        try:
            func = self._eval(node.func)
        except MathaRuntimeError as e:
            if "未定义变量" in str(e):
                func_name = getattr(getattr(node, 'func', None), 'name', None) or str(node.func)
                raise MathaRuntimeError(f"未定义函数 '{func_name}'") from e
            raise
        arg = self._eval(node.arg)
        self._log(logging.DEBUG,
                  f"apply {self._fmt(func)} ← {self._fmt(arg)}")
        result = self._apply(func, arg)
        self._log_exit("eval FuncApp", result)
        return result

    def _apply(self, func, arg) -> object:
        if callable(func):
            # Python 内建/闭包：直接应用
            self._log(logging.DEBUG, f"apply callable({self._fmt(arg)})")
            return func(arg)
        if isinstance(func, _RecPlaceholder):
            # 递归占位符：转发实际参数，内部解析为已绑定的递归闭包
            return func(arg)
        if isinstance(func, ast.FuncDef):
            self._log(logging.DEBUG, f"apply FuncDef '{func.name}'({self._fmt(arg)})")
            return self._call_func(func, [arg])
        if isinstance(func, tuple) and func and func[0] == "__closure__":
            self._log(logging.DEBUG, "apply closure")
            # Matha 自举路径: 4 元组 ("__closure__", params, body, env)
            # Python 原有路径: 3 元组 ("__closure__", lambda, captured)
            if len(func) == 4:
                params, body, captured = func[1], func[2], func[3]
                lam = ast.Lambda(params=params, body=body)
            else:
                _, lam, captured = func
            return self._call_lambda(lam, captured, [arg])
        raise MathaRuntimeError(f"不可调用的值: {func!r}")

    def _call_func_or_closure(self, fn, args: list) -> object:
        """调用函数或闭包（统一入口）。"""
        if isinstance(fn, tuple) and fn and fn[0] == "__closure__":
            # 闭包：逐个参数应用（柯里化）
            result = fn
            for a in args:
                result = self._apply(result, a)
            return result
        return self._call_func(fn, args)

    def _call_func(self, fdef: ast.FuncDef, args: list) -> object:
        self._log(logging.INFO,
                  f"call func '{fdef.name}' args={[self._fmt(a) for a in args]}")
        return self._call_lambda(fdef.body, self.env, args)

    def _call_lambda(self, lam: ast.Lambda, captured: dict, args: list) -> object:
        params = lam.params
        # 完整应用时也需要拷贝：递归函数会写入局部变量，共享 captured 会导致错误
        # captured 可以是 dict 或 list of tuples（兼容 Matha 自举路径）
        if isinstance(captured, list):
            local = dict(captured)
            self._matha_env = captured  # 保留原始 list-of-tuples 供闭包使用
        else:
            local = dict(captured)
            # 如果是 dict，尝试从 env 中提取 list-of-tuples
            matha_env = getattr(self, '_matha_env', None)
            if matha_env is None:
                matha_env = list(local.items())
            self._matha_env = matha_env
            # 确保 local 也使用 list-of-tuples 格式的 env
            if 'env' in local and not isinstance(local['env'], list):
                local['env'] = list(local['env'].items()) if isinstance(local['env'], dict) else local['env']
        if len(args) < len(params):
            for p, a in zip(params, args):
                local[self._param_name(p)] = a
            remaining = params[len(args):]
            # 将当前已绑定的参数纳入 captured，确保后续偏应用能访问
            # 必须原地修改 captured（list 时）或保留引用（dict 时）
            if isinstance(captured, list):
                # 原地追加：后续从 captured 创建 dict 时能看到新绑定
                captured.extend((self._param_name(p), a) for p, a in zip(params, args))
                self._matha_env = captured
            elif isinstance(self._matha_env, list):
                self._matha_env = list(self._matha_env) + [
                    (self._param_name(p), a)
                    for p, a in zip(params, args)
                ]
            else:
                self._matha_env = list(self._matha_env.items()) + [
                    (self._param_name(p), a)
                    for p, a in zip(params, args)
                ]
            # Flatten nested lambdas when more than 1 param remains:
            # (a)=>(b)=>(c)=>expr applied with [1] → Lambda([b,c], expr)
            # without flattening it would be Lambda([b,c], Lambda([c], expr))
            # which breaks multi-arg partial application chains.
            # For single remaining param (e.g. compose(f)(g)→(x)→...), keep nesting
            # so the final param is properly applied.
            if len(remaining) > 1:
                body = lam.body
                while isinstance(body, ast.Lambda):
                    body = body.body
            else:
                body = lam.body
            self._log(logging.DEBUG,
                      f"lambda partial apply: bound={len(args)}/{len(params)} → closure")
            return ("__closure__", remaining, body, self._matha_env)
        for p, a in zip(params, args):
            local[self._param_name(p)] = a
        # 确保 self._matha_env 包含新绑定的参数，供函数体内创建的闭包使用
        if isinstance(self._matha_env, list):
            self._matha_env = list(self._matha_env) + [
                (self._param_name(p), a) for p, a in zip(params, args)
            ]
        extra = args[len(params):]
        param_names = [self._param_name(p) for p in params]
        self._log(logging.DEBUG,
                  f"lambda enter: params={param_names} args={[self._fmt(a) for a in args]}")
        saved = self.env
        self.env = local
        self._depth += 1 if self.debug else 0
        try:
            try:
                result = self._eval(lam.body)
            except _ReturnException as e:
                result = e.value
        finally:
            self.env = saved
            if self.debug:
                self._depth = max(0, self._depth - 1)
        self._log(logging.DEBUG,
                  f"lambda exit → {self._fmt(result)}")
        if params and extra:
            # 只有结果仍是可调用的闭包时，才继续应用多余参数
            # 避免将多余参数应用到已求值的字面量（如 dict、list）上
            for a in extra:
                is_closure = callable(result) or (isinstance(result, tuple) and result and result[0] == "__closure__")
                self._log(logging.DEBUG,
                          f"lambda extra arg: callable={callable(result)} is_tuple_closure={is_closure} result_type={type(result).__name__}")
                if is_closure:
                    self._log(logging.DEBUG, "lambda apply extra arg")
                    result = self._apply(result, a)
                else:
                    self._log(logging.DEBUG, "lambda drop extra arg (result is literal)")
                    break
        return result

    # ---------- 辅助 ----------

    def _target_name(self, target) -> str:
        if isinstance(target, ast.Variable):
            return target.name
        return str(target)

    def _param_name(self, param) -> str:
        if isinstance(param, ast.Variable):
            return param.name
        return str(param)

    # ============================================================
    # 外部语言互操作：外部求值 / 双实现对比 / 对比升级
    #   依赖 src.foreign（懒导入）。外部代码在独立命名空间/子进程
    #   运行，不污染本体；对比升级复用沙箱隔离。
    # ============================================================

    @staticmethod
    def _curry(n: int, func):
        """生成 n 参柯里化函数：逐个收集参数，满 n 个时调用 func。

        Matha 函数应用是柯里化的（f(a)(b)），多参 Python 内建需
        用此包裹才能在 Matha 中逐参应用。
        """
        def builder(args):
            if len(args) == n:
                return func(*args)
            return lambda a: builder(args + [a])
        return builder([])

    def foreign_eval(self, lang: str, code: str, inputs=None):
        """求值外部语言代码（Python 宿主内 / 其它语言 subprocess）。"""
        from src.foreign import ForeignRunner
        return ForeignRunner().eval(lang, code, inputs)

    def _b_foreign_eval(self, lang: str, code: str):
        """内建 外部求值(语言, 代码) → 求值结果。"""
        return self.foreign_eval(lang, code)

    def _b_compare_impl(self, matha_func: str, foreign_lang: str,
                        foreign_code: str, test_cases: list) -> bool:
        """内建 对比实现(Matha函数名, 外部语言, 外部代码, 输入列表) → bool。

        对每个测试输入（参数列表）对比 Matha 函数与外部函数返回值，
        全部一致返回 True，否则 False。
        """
        from src.foreign import DualComparator
        cmp = DualComparator(self, matha_func, foreign_lang, foreign_code)
        return cmp.compare(test_cases).通过

    def _b_compare_upgrade(self, matha_src: str, matha_func: str,
                           foreign_lang: str, foreign_code: str,
                           test_cases: list) -> list:
        """内建 对比升级(Matha源码, Matha函数名, 外部语言, 外部代码, 输入列表)。

        沙箱试运行 Matha 源码 → 与外部参考对比 → 全通过则提交。
        成功：返回新增/改写函数名列表。失败：抛 MathaRuntimeError。
        """
        from src.foreign import compare_upgrade
        res = compare_upgrade(self, matha_src, matha_func,
                              foreign_lang, foreign_code, test_cases)
        if not res.成功:
            raise MathaRuntimeError(f"对比升级失败: {res.错误}")
        return list(res.变更.get("新函数", [])) + list(res.变更.get("改函数", []))

    # ============================================================
    # 混合语言编译器内建
    # ============================================================

    def _b_hybrid_build(self, task: str, matha_src: str) -> list:
        """内建 混合编译(任务描述, Matha源码)。
        尝试纯Matha → 混合语言 → 诊断 → 升级 → 重构，返回构建结果。"""
        from src.hybrid_compiler import HybridCompiler
        hc = HybridCompiler(self)
        result = hc.build_project(task, matha_src)
        return result

    def _b_hybrid_diagnose(self, source: str) -> list:
        """内建 混合诊断(Matha源码)。返回诊断报告。"""
        from src.hybrid_compiler import HybridCompiler
        hc = HybridCompiler(self)
        return hc.diagnose(source)

    def _b_hybrid_exec(self, mixed_src: str) -> list:
        """内建 混合执行(混合代码)。执行混合语言代码片段。"""
        from src.hybrid_compiler import HybridCompiler
        hc = HybridCompiler(self)
        return hc.mixed_exec(mixed_src)

    def _b_hybrid_translate(self, source: str, target_lang: str) -> list:
        """内建 转译语言(源码, 目标语言名)。双向语言转译。"""
        from src.hybrid_compiler import HybridCompiler
        hc = HybridCompiler(self)
        return hc.translate(source, target_lang)

    def _b_hybrid_refactor(self, hybrid_code: str, source_lang: str) -> list:
        """内建 重构_matha(混合代码, 源语言名)。将混合代码重构为纯Matha。"""
        from src.hybrid_compiler import HybridCompiler
        hc = HybridCompiler(self)
        return hc.refactor(hybrid_code, source_lang)


    # ============================================================
    # 自我升级子系统：探针 / 沙箱 / 升级
    #   依赖 src.selfupgrade（懒导入，避免顶层循环依赖）。
    #   状态化内建（探针_状态 等）由 _install_self_builtins 绑定到
    #   本解释器实例；沙箱克隆后会重新绑定到沙箱自身解释器。
    # ============================================================

    def probe(self):
        """返回本解释器的只读探针视图（Probe）。"""
        from src.selfupgrade import Probe
        return Probe(self)

    def sandbox(self):
        """创建隔离沙箱（克隆本解释器状态）；本体不受沙箱内运行影响。"""
        from src.selfupgrade import Sandbox
        return Sandbox(self)

    def upgrade(self, source: str, verify=None):
        """加载 Matha 源码到沙箱试运行，通过后合并到本解释器。

        verify: 可选 callable(sandbox) -> bool，commit 前校验。
        返回 UpgradeResult（成功时 变更 含 diff）。
        """
        from src.selfupgrade import upgrade as _upgrade
        return _upgrade(self, source, verify)

    def _install_self_builtins(self) -> None:
        """注册依赖本解释器实例的状态化内建（探针 / 沙箱 / 升级）。

        - 0 参语义（探针_状态 / 探针_函数列表）：Matha 语法层无空括号
          调用，但 parser 将 () 解析为 IntegerLit(0)，故 探针_状态()
          实为「应用 探针_状态 于 0」；此处用忽略参数的 callable 实现。
        - 沙箱克隆后必须重新调用本方法，使状态化内建指向沙箱自身解释器。
        """
        b = self.builtins
        b["探针_状态"] = self._b_probe_state
        b["探针_函数列表"] = self._b_func_names
        b["探针_已定义"] = self._b_has
        b["试运行"] = self._b_dry_run
        b["升级"] = self._b_upgrade
        b["外部求值"] = self._curry(2, self._b_foreign_eval)
        b["对比实现"] = self._curry(4, self._b_compare_impl)
        b["对比升级"] = self._curry(5, self._b_compare_upgrade)
        b["空列表"] = []  # 空列表值（[] 在 Matha 中解析为 Output）
        # 混合语言编译器内建
        b["混合编译"] = self._curry(2, self._b_hybrid_build)
        b["混合诊断"] = self._curry(1, self._b_hybrid_diagnose)
        b["混合执行"] = self._curry(1, self._b_hybrid_exec)
        b["转译语言"] = self._curry(2, self._b_hybrid_translate)
        b["重构_matha"] = self._curry(2, self._b_hybrid_refactor)
        # 自主能力内建（调试 / 优化 / 成长）
        b["自主_调试"] = self._curry(2, self._b_auto_debug)
        b["自主_优化"] = self._curry(2, self._b_auto_optimize)
        b["自主_成长"] = self._curry(2, self._b_self_grow)
        # 资源库内建（保护隔离 + 读取 + 自主成长扩展）
        b["资源_列表"] = self._b_library_list
        b["资源_读取"] = self._curry(2, self._b_library_read)
        b["资源_加载"] = self._curry(2, self._b_library_load)
        b["资源_成长"] = self._curry(3, self._b_library_grow)
        # 代码生成内建（成品软件/系统开发）
        b["生成_网页"] = self._curry(1, self._b_gen_web)
        b["生成_桌面"] = self._curry(1, self._b_gen_desktop)
        b["生成_服务"] = self._curry(1, self._b_gen_service)
        b["生成_系统"] = self._curry(1, self._b_gen_system)
        b["生成_游戏"] = self._curry(1, self._b_gen_game)
        b["生成_建模"] = self._curry(1, self._b_gen_model3d)
        b["软件_构建"] = self._curry(1, self._b_build_software)
        # 互操作内建（被其它语言识别解读）
        b["导出_AST"] = self._curry(1, self._b_export_ast)
        b["导出_Token"] = self._curry(1, self._b_export_tokens)
        b["转译_Python"] = self._curry(1, self._b_transpile_python)
        b["转译_JS"] = self._curry(1, self._b_transpile_js)
        b["导出_符号表"] = self._curry(1, self._b_export_symtab)
        # 网络安全内建（威胁检测 · 病毒清杀 · 防火墙联动）
        b["威胁检测"] = self._curry(1, self._b_net_scan)
        b["检测病毒"] = self._curry(1, self._b_net_detect_virus)
        b["隔离威胁"] = self._curry(1, self._b_net_quarantine)
        b["清杀威胁"] = self._curry(1, self._b_net_eliminate)
        b["清杀全部"] = self._curry(0, self._b_net_eliminate_all)
        b["生成防火墙规则"] = self._curry(0, self._b_net_fw_rules)
        b["风险评估"] = self._curry(1, self._b_net_risk_assess)
        b["风险报告"] = self._curry(0, self._b_net_risk_report)
        b["威胁报告"] = self._curry(1, self._b_net_threat_report)
        b["添加威胁签名"] = self._curry(5, self._b_net_add_sig)
        b["列出签名"] = self._curry(0, self._b_net_list_sigs)
        b["威胁数量"] = self._curry(0, self._b_net_threat_count)
        b["已清杀数量"] = self._curry(0, self._b_net_eliminated_count)
        b["防火墙规则列表"] = self._curry(0, self._b_net_fw_list)
        b["威胁状态"] = self._curry(1, self._b_net_threat_status)
        # 病毒创造与高级清杀
        b["创造病毒"] = self._curry(5, self._b_net_create_virus)
        b["批量创造病毒"] = self._curry(2, self._b_net_create_virus_batch)
        b["分析病毒"] = self._curry(1, self._b_net_analyze_virus)
        b["修补漏洞"] = self._curry(2, self._b_net_patch_vuln)
        b["模拟传播"] = self._curry(2, self._b_net_simulate_spread)
        b["高级中和"] = self._curry(2, self._b_net_neutralize)
        b["隔离全部"] = self._curry(0, self._b_net_quarantine_all)
        b["病毒库列表"] = self._curry(0, self._b_net_virus_library)
        b["创建测试场景"] = self._curry(3, self._b_net_create_scenario)
        b["隔离日志"] = self._curry(0, self._b_net_quarantine_log)
        b["清杀日志"] = self._curry(0, self._b_net_elimination_log)
        # 自举模块加载
        b["加载模块_文件"] = self._curry(1, self._b_load_matha_module)

    # ---- 状态化内建实现（返回普通容器，供 Matha 侧消费） ----

    def _b_load_matha_module(self, module_name: str) -> bool:
        """内建 加载模块(模块名) → 从文件系统加载 .matha 模块。"""
        return self.load_matha_module(module_name)

    def _b_probe_state(self, _=None) -> dict:
        return self.probe().state()

    def _b_func_names(self, _=None) -> list:
        return list(self.funcs.keys())

    def _b_has(self, name: str) -> bool:
        return (name in self.env or name in self.funcs
                or name in self.builtins or name in self.constructors)

    def _b_dry_run(self, source: str) -> bool:
        """沙箱试运行源码，不提交。返回是否成功（True=无错）。

        Matha 侧无法内省 dict，故返回 bool 便于条件分支。
        """
        from src.selfupgrade import Sandbox
        sb = Sandbox(self)
        _, _, err = sb.run(source)
        sb.rollback()
        return err is None

    def _b_upgrade(self, source: str) -> list:
        """沙箱试运行 + 通过则提交。

        成功：返回新增/改写的函数名列表（Matha 可 len/get 消费）。
        失败：抛 MathaRuntimeError（本体未被污染，已 rollback）。
        """
        res = self.upgrade(source)
        if not res.成功:
            raise MathaRuntimeError(f"升级失败: {res.错误}")
        return list(res.变更.get("新函数", [])) + list(res.变更.get("改函数", []))


    # ---- 自主能力内建实现（调试 / 优化 / 成长） ----

    def _b_auto_debug(self, source: str, max_attempts: int = 3) -> dict:
        """自主调试：捕获错误 → 生成修复候选 → 沙箱验证 → 提交。

        返回 dict（成功/错误/修复方案/变更）。
        """
        from src.autonomous import auto_debug
        return auto_debug(self, source, int(max_attempts))

    def _b_auto_optimize(self, func_name: str, strategy: str = "memoize") -> dict:
        """自主优化：识别热点 → 记忆化优化 → 等价对比 → 提交。

        返回 dict（成功/热点/优化方案/加速比/变更）。
        """
        from src.autonomous import auto_optimize_memoize
        return auto_optimize_memoize(self, str(func_name))

    def _b_self_grow(self, source: str, desc: str = "") -> dict:
        """自主成长：从源码学习新能力 → 沙箱验证 → 注册。

        返回 dict（成功/学习源/新能力/变更）。
        """
        from src.autonomous import self_grow
        return self_grow(self, source, str(desc))


    # ---- 资源库内建实现（保护隔离 + 读取 + 自主成长扩展） ----

    def _b_library_list(self, _=None) -> list:
        """资源_列表() → 资源库所有条目列表。"""
        from src.library import get_library
        return get_library().list()

    def _b_library_read(self, path: str, _=None) -> str:
        """资源_读取(路径) → 资源内容（只读，保护隔离）。"""
        from src.library import get_library
        content = get_library().read(str(path))
        return content if content is not None else ""

    def _b_library_load(self, path: str, _=None) -> dict:
        """资源_加载(路径) → 沙箱加载资源到本体。

        返回 dict（成功/新函数/错误）。
        """
        from src.library import get_library
        return get_library().load(str(path), self)

    def _b_library_grow(self, requirement: str, discipline: str = "core",
                        name: str = "") -> dict:
        """资源_成长(需求)(学科)(名称) → 自主成长生成新资源。

        子文件资源不足时，资源库主动扩展生成公式代码。
        返回 dict（成功/新资源/学科/错误）。
        """
        from src.library import get_library
        r = get_library().grow(self, str(requirement),
                               str(discipline) or "core",
                               str(name) or None)
        return r.as_dict()

    # ---- 代码生成内建实现（成品软件/系统开发） ----

    def _b_gen_web(self, spec, out_dir: str = None) -> dict:
        """生成_网页(规格[, 输出目录]) → 编译为 HTML/CSS/JS 成品。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _b_gen_desktop(self, spec, out_dir: str = None) -> dict:
        """生成_桌面(规格[, 输出目录]) → 编译为 Python Tkinter 桌面程序。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _b_gen_service(self, spec, out_dir: str = None) -> dict:
        """生成_服务(规格[, 输出目录]) → 编译为 Python HTTP 服务。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _b_gen_system(self, spec, out_dir: str = None) -> dict:
        """生成_系统(规格[, 输出目录]) → 编译为系统脚本。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _b_gen_game(self, spec, out_dir: str = None) -> dict:
        """生成_游戏(规格[, 输出目录]) → 编译为 HTML5 Canvas 游戏。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _b_gen_model3d(self, spec, out_dir: str = None) -> dict:
        """生成_建模(规格[, 输出目录]) → 编译为 Three.js 3D 模型场景。"""
        from src.codegen import codegen
        spec = self._normalize_spec(spec)
        r = codegen(spec, out_dir)
        return r.as_dict()

    def _normalize_spec(self, spec):
        """规格归一化：字符串 → 解析为 JSON 列表；列表原样返回。"""
        if isinstance(spec, str):
            try:
                return json.loads(spec)
            except Exception:
                return spec
        return spec

    def _b_build_software(self, requirement: str) -> dict:
        """软件_构建(需求[, 类型]) → 自主构建成品软件。

        需求描述（如 "计算器网页"）→ 生成规格 → codegen → 输出。
        类型：网页/桌面/服务/系统（自动推断）。
        """
        from src.autonomous import build_software
        return build_software(self, str(requirement))

    # ---- 互操作内建实现（被其它语言识别解读） ----

    def _b_export_ast(self, source: str) -> dict:
        """导出_AST(源码) → 把 Matha 源码的 AST 导出为 JSON dict。

        任何语言可解析此 JSON 识别 Matha 程序结构。
        """
        from src.ast_serializer import program_to_dict
        return program_to_dict(str(source))

    def _b_export_tokens(self, source: str) -> list:
        """导出_Token(源码) → 把 Matha 源码的 Token 流导出为 list。

        任何语言可解析此列表做词法分析。
        """
        from src.ast_serializer import tokens_to_dict
        return tokens_to_dict(str(source))

    def _b_transpile_python(self, source: str) -> str:
        """转译_Python(源码) → 把 Matha 源码转译为 Python 源码字符串。

        Python 可直接运行转译后的代码。
        """
        from src.transpiler import transpile
        return transpile(str(source), "python")

    def _b_transpile_js(self, source: str) -> str:
        """转译_JS(源码) → 把 Matha 源码转译为 JavaScript 源码字符串。

        JavaScript 环境可直接运行转译后的代码。
        """
        from src.transpiler import transpile
        return transpile(str(source), "javascript")

    def _b_export_symtab(self, fmt: str = "json") -> str:
        """导出_符号表([格式]) → 导出 Matha 完整符号表。

        格式："json" | "typescript" | "markdown" | "python"
        让其它语言知道 Matha 提供了哪些函数。
        """
        from src.symtab_exporter import (export_symtab_json,
                                          export_symtab_d_ts,
                                          export_symtab_markdown,
                                          export_symtab_python)
        fmt = str(fmt).lower()
        if fmt in ("json", "JSON"):
            return export_symtab_json(self)
        if fmt in ("typescript", "ts", "d.ts"):
            return export_symtab_d_ts(self)
        if fmt in ("markdown", "md"):
            return export_symtab_markdown(self)
        if fmt in ("python", "py"):
            return export_symtab_python(self)
        return export_symtab_json(self)

    # ============================================================
    # 网络安全内建实现（威胁检测 · 病毒清杀 · 防火墙联动）
    # ============================================================

    def _b_net_scan(self, source_ips: list) -> list:
        """威胁检测(IP列表) → 威胁列表。"""
        from src.net_security import _get_engine
        return _get_engine().scan_threats(source_ips)

    def _b_net_detect_virus(self, behavior: str) -> list:
        """检测病毒(行为描述) → 匹配签名列表。"""
        from src.net_security import _get_engine
        return _get_engine().detect_virus(behavior)

    def _b_net_quarantine(self, threat_id: str) -> dict:
        """隔离威胁(威胁ID) → 操作结果。"""
        from src.net_security import _get_engine
        return _get_engine().quarantine(threat_id)

    def _b_net_eliminate(self, threat_id: str) -> dict:
        """清杀威胁(威胁ID) → 操作结果。"""
        from src.net_security import _get_engine
        return _get_engine().eliminate(threat_id)

    def _b_net_eliminate_all(self, _=None) -> dict:
        """清杀全部(级别?) → 批量清杀结果。"""
        from src.net_security import _get_engine
        return _get_engine().eliminate_all()

    def _b_net_fw_rules(self, _=None) -> list:
        """生成防火墙规则(威胁列表?) → 规则列表。"""
        from src.net_security import _get_engine
        return _get_engine().generate_firewall_rules()

    def _b_net_risk_assess(self, ip: str) -> dict:
        """风险评估(IP) → 风险评估结果。"""
        from src.net_security import _get_engine
        return _get_engine().assess_risk(ip)

    def _b_net_risk_report(self, _=None) -> dict:
        """风险报告() → 整体风险报告。"""
        from src.net_security import _get_engine
        return _get_engine().get_risk_report()

    def _b_net_threat_report(self, threat_id: str) -> dict:
        """威胁报告(威胁ID) → 威胁详情。"""
        from src.net_security import _get_engine
        return _get_engine().get_threat_report(threat_id)

    def _b_net_add_sig(self, name: str, pattern: str, level: str,
                       category: str, description: str) -> bool:
        """添加威胁签名(名称,模式,等级,分类,描述) → 是否成功。"""
        from src.net_security import _get_engine
        return _get_engine().add_signature(name, pattern, level, category, description)

    def _b_net_list_sigs(self, _=None) -> list:
        """列出签名() → 所有威胁签名。"""
        from src.net_security import _get_engine
        return _get_engine().list_signatures()

    def _b_net_threat_count(self, _=None) -> int:
        """威胁数量() → 当前威胁总数。"""
        from src.net_security import _get_engine
        return _get_engine().threat_count()

    def _b_net_eliminated_count(self, _=None) -> int:
        """已清杀数量() → 已清杀威胁数。"""
        from src.net_security import _get_engine
        return _get_engine().eliminated_count()

    def _b_net_fw_list(self, _=None) -> list:
        """防火墙规则列表() → 已生成规则。"""
        from src.net_security import _get_engine
        return _get_engine().get_firewall_rules()

    def _b_net_threat_status(self, threat_id: str) -> dict:
        """威胁状态(威胁ID) → 威胁当前状态。"""
        from src.net_security import _get_engine
        return _get_engine().threat_status(threat_id)

    # ── 病毒创造与高级清杀 ─────────────────────────────────

    def _b_net_create_virus(self, name: str, category: str, level: str,
                            behavior: str, payload: str) -> dict:
        """创造病毒(名称,分类,等级,行为,载荷) → 病毒定义。"""
        from src.net_security import _get_engine
        return _get_engine().create_virus(name, category, level, behavior, payload)

    def _b_net_create_virus_batch(self, count: int, categories: list = None) -> list:
        """批量创造病毒(数量,分类列表?) → 病毒列表。"""
        from src.net_security import _get_engine
        return _get_engine().create_virus_batch(count, categories)

    def _b_net_analyze_virus(self, virus_id: str) -> dict:
        """分析病毒(病毒ID) → 病毒分析报告。"""
        from src.net_security import _get_engine
        return _get_engine().analyze_virus(virus_id)

    def _b_net_patch_vuln(self, vuln_id: str, severity: str = "high") -> dict:
        """修补漏洞(漏洞ID,等级?) → 修补结果。"""
        from src.net_security import _get_engine
        return _get_engine().patch_vulnerability(vuln_id, severity)

    def _b_net_simulate_spread(self, virus_id: str, network_size: int = 10) -> dict:
        """模拟传播(病毒ID,节点数?) → 传播模拟结果。"""
        from src.net_security import _get_engine
        return _get_engine().simulate_spread(virus_id, network_size)

    def _b_net_neutralize(self, threat_id: str, method: str = "automatic") -> dict:
        """高级中和(威胁ID,方法?) → 中和结果。"""
        from src.net_security import _get_engine
        return _get_engine().neutralize(threat_id, method)

    def _b_net_quarantine_all(self, _=None) -> dict:
        """隔离全部() → 隔离结果。"""
        from src.net_security import _get_engine
        return _get_engine().quarantine_all()

    def _b_net_virus_library(self, _=None) -> list:
        """病毒库列表() → 所有病毒列表。"""
        from src.net_security import _get_engine
        return _get_engine().get_virus_library()

    def _b_net_create_scenario(self, name: str, virus_count: int = 5,
                               network_size: int = 20) -> dict:
        """创建测试场景(场景名,病毒数,节点数?) → 场景摘要。"""
        from src.net_security import _get_engine
        return _get_engine().create_test_scenario(name, virus_count, network_size)

    def _b_net_quarantine_log(self, _=None) -> list:
        """隔离日志() → 隔离操作记录。"""
        from src.net_security import _get_engine
        return _get_engine().get_quarantine_log()

    def _b_net_elimination_log(self, _=None) -> list:
        """清杀日志() → 清杀操作记录。"""
        from src.net_security import _get_engine
        return _get_engine().get_elimination_log()


# 延迟初始化：_curry 已定义，现在可以安全地构建缓存
_DOMAIN_BUILTINS = _build_domain_builtins()


def interpret(source: str, debug: bool | None = None) -> tuple[list, list[str]]:
    """解析并执行 Matha 源码，返回 (outputs, trace)。

    debug=None 服从 MATHA_DEBUG 环境变量；显式 True/False 优先。
    自动抬高递归深度以支持大文件和深度递归（自举编译等）。
    """
    # 抬高递归深度以支持大文件/深度递归
    _min_limit = 5000 + len(source) // 10
    _current = sys.getrecursionlimit()
    if _min_limit > _current:
        sys.setrecursionlimit(_min_limit)
    from src.parser import parse
    program = parse(source)
    return Interpreter(debug=debug).run(program)


def lexer_bootstrap_interpret(source: str, debug: bool | None = None) -> list[dict]:
    """用 Matha 自举 lexer 的函数式扫描器 tokenize 一段源码字符串。

    matha/lexer.matha 中定义的纯函数式 扫描(src)(pos)(line)(col)(toks) 由
    Matha 自身语法（lambda + 递归 + 柯里化）实现字符 I/O 与 Token 组装，
    无需命令占位符。本函数加载 lexer.matha 注册函数后直接调用 扫描。

    debug=None 服从 MATHA_DEBUG 环境变量；显式 True/False 优先。
    """
    import os
    import sys
    path = os.path.join(os.path.dirname(__file__), "..", "matha", "lexer.matha")
    with open(path, encoding="utf-8") as f:
        lexer_src = f.read()
    from src.parser import parse
    program = parse(lexer_src)
    interp = Interpreter(debug=debug)
    interp.run(program)
    # 递归深度随源码长度线性增长，抬高栈上限以防长输入爆栈。
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    tokens = interp.call("扫描", source, 0, 1, 1, [])
    return tokens
