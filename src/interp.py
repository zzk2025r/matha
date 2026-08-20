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
import os
import sys
from src import ast_nodes as ast

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
    b["与"] = _curry_module(2, lambda a, b: a and b)
    b["或"] = _curry_module(2, lambda a, b: a or b)
    b["非"] = lambda x: not x
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
    """运行时错误。"""


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
    if isinstance(seq, (str, list)):
        return len(seq)
    raise MathaRuntimeError(f"len() 需要字符串或列表，实际 {type(seq).__name__}")


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
    def with_elem(elem):
        if not isinstance(lst, list):
            raise MathaRuntimeError(f"append() 需要列表，实际 {type(lst).__name__}")
        return lst + [elem]
    return with_elem


def builtin_list(*args):
    """list() → []；list(x) → [x]"""
    return list(args)


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
    return json.loads(str(text))


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


BUILTINS: dict[str, object] = {
    "ord": builtin_ord,
    "chr": builtin_chr,
    "len": builtin_len,
    "get": builtin_get,
    "slice": builtin_slice,
    "append": builtin_append,
    "list": builtin_list,
    "token": builtin_token,
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
    # 列表操作
    "映射": _curry_module(2, lambda lst, fn: builtin_列表映射(lst, fn)),
    "过滤": _curry_module(2, lambda lst, fn: builtin_列表过滤(lst, fn)),
    "反转": builtin_列表反转,
    "排序": _curry_module(2, lambda lst, reverse: builtin_列表排序(lst, reverse)),
    "展平": builtin_列表展平,
    "求和": builtin_列表求和,
    "去重": builtin_列表去重,
}


def _curry_callable(fn, arity=None):
    """给一个 Python callable 做柯里化包装，使其匹配 Matha 的单参应用。

    对 n 参函数 f(a, b, c)：当应用第一个参数后，返回等待 b、c 的闭包。
    对变长或未知 arity 的函数，若函数返回 callable（如 slice、append），
    则直接应用第一层，后续再应用由解释器继续调用。
    """
    # 已经是单参 callable 或返回 callable 的，原样返回
    return fn


class Interpreter:
    """Matha 树走式解释器。"""

    def __init__(self, debug: bool | None = None):
        self.env: dict[str, object] = {}
        self.funcs: dict[str, ast.FuncDef] = {}
        self.constructors: set[str] = set()
        self.outputs: list = []
        self.trace: list[str] = []
        self.builtins: dict[str, object] = dict(BUILTINS)  # 可继承覆写
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
    def _fmt(v: object) -> str:
        """值的安全格式化（避免巨型对象刷屏）。"""
        if isinstance(v, str):
            return repr(v[:60] + ("…" if len(v) > 60 else ""))
        if isinstance(v, list):
            n = len(v)
            return f"[list len={n}]" if n > 8 else repr(v)
        if isinstance(v, dict):
            return f"{{dict keys={list(v.keys())}}}" if len(v) > 6 else repr(v)
        return repr(v)

    # ---------- 入口 ----------

    def run(self, program: ast.Program) -> tuple[list, list[str]]:
        self._log(logging.INFO, f"run: {len(program.decls)} 个顶层声明")
        self._depth = 0
        self._log_enter("register-pass")
        for decl in program.decls:
            self._register(decl)
        self._log_exit("register-pass")
        self._log_enter("exec-pass")
        for i, decl in enumerate(program.decls):
            self._log(logging.INFO, f"── decl[{i}] {type(decl).__name__} ──")
            self._exec_decl(decl)
        self._log_exit("exec-pass", self.outputs)
        self._log(logging.INFO,
                  f"run 完成: outputs={len(self.outputs)} trace={len(self.trace)}")
        return self.outputs, self.trace

    def call(self, name: str, *args) -> object:
        # funcs 优先于 builtins：用户定义函数可覆写同名内建
        # （如 func c(x) 覆写光速常量 c）
        if name in self.funcs:
            return self._call_func(self.funcs[name], list(args))
        if name in self.builtins:
            result = self.builtins[name]
            if args:
                for a in args:
                    result = self._apply(result, a)
            elif callable(result):
                # 无参调用：Matha 级别的 0 参（如 list()）
                result = result()
            return result
        raise MathaRuntimeError(f"未定义函数 '{name}'")

    # ---------- 注册 ----------

    def _register(self, decl) -> None:
        if isinstance(decl, ast.FuncDef):
            self.funcs[decl.name] = decl
            self._log(logging.INFO, f"register func '{decl.name}'")
        elif isinstance(decl, ast.EnumDef):
            self.constructors.update(decl.ctors)
            self._log(logging.INFO,
                      f"register enum '{decl.name}' ctors={decl.ctors}")
        elif isinstance(decl, ast.ModuleDecl):
            self._log(logging.INFO,
                      f"register module '{decl.name}' ({len(decl.decls)} decls)")
            for inner in decl.decls:
                self._register(inner)

    # ---------- 声明执行 ----------

    def _exec_decl(self, decl) -> None:
        if isinstance(decl, ast.SetUp):
            self._log(logging.INFO, f"exec SetUp form='{decl.form}' items={len(decl.items)}")
            self._exec_set_up(decl)
        elif isinstance(decl, ast.MechUnit):
            seg = decl.generate.seg_id
            self._log(logging.INFO,
                      f"exec MechUnit #{seg} body={type(decl.body).__name__}")
            self._exec_stmt(decl.body)
        elif isinstance(decl, ast.ModuleDecl):
            self._log(logging.INFO, f"exec Module '{decl.name}'")
            for inner in decl.decls:
                self._exec_decl(inner)
        elif isinstance(decl, ast.Binding):
            # 顶层绑定（如 inc = (x) => x + 1）写入全局 env，
            # 使 lambda 变量在各段内可见，与 func 定义行为一致。
            self._log(logging.INFO, f"exec top-level Binding")
            self._exec_stmt(decl)
        elif isinstance(decl, ast.Output):
            self._log(logging.INFO, f"exec top-level Output")
            self._exec_stmt(decl)
        elif isinstance(decl, ast.FuncApp):
            # 顶层函数调用：执行并丢弃返回值
            self._log(logging.DEBUG, f"exec top-level FuncApp")
            self._eval(decl)
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
        max_iter = 10000  # 防止无限循环
        while self._eval(stmt.cond) and iteration < max_iter:
            self._exec_codeblock_or_stmt(stmt.block)
            iteration += 1
        self._log_exit("while")

    def _exec_for_stmt(self, stmt: ast.ForStmt) -> None:
        """执行 for 循环。"""
        self._log_enter("for")
        iterable = self._eval(stmt.iterable)
        if not isinstance(iterable, (list, tuple, str)):
            raise MathaRuntimeError(f"for 迭代对象需为列表/元组/字符串，实际 {type(iterable).__name__}")
        for item in iterable:
            self.env[stmt.var] = item
            self._exec_codeblock_or_stmt(stmt.block)
        self._log_exit("for")

    def _exec_match_stmt(self, stmt: ast.MatchStmt) -> None:
        """执行 match 模式匹配语句，输出匹配结果。"""
        result = self._eval_match(stmt)
        self.outputs.append(result)
        self._log(logging.INFO, f"[output] += match → {self._fmt(result)}")

    def _eval_match(self, stmt: ast.MatchStmt) -> object:
        """求值 match 表达式，返回匹配结果。"""
        value = self._eval(stmt.scrutinee)
        default_branch = None
        for pattern, body in stmt.branches:
            if isinstance(pattern, ast.Variable) and pattern.name == "_":
                default_branch = body
                continue
            if self._match_pattern(pattern, value):
                result = self._eval(body)
                self._log(logging.INFO, f"match → {self._fmt(result)}")
                return result
        # 无匹配分支时，尝试默认分支
        if default_branch is not None:
            result = self._eval(default_branch)
            self._log(logging.INFO, f"match (default) → {self._fmt(result)}")
            return result
        raise MathaRuntimeError(f"match 无匹配分支: {self._fmt(value)}")

    def _match_pattern(self, pattern, value) -> bool:
        """简单模式匹配：字面量相等或通配符 _。"""
        if isinstance(pattern, ast.Variable) and pattern.name == "_":
            return True
        if isinstance(pattern, ast.IntegerLit):
            return pattern.value == value
        if isinstance(pattern, ast.FloatLit):
            return pattern.value == value
        if isinstance(pattern, ast.StringLit):
            return pattern.value == value
        if isinstance(pattern, ast.BoolLit):
            return pattern.value == value
        # 变量绑定：匹配任意值
        if isinstance(pattern, ast.Variable):
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
            self.env.setdefault(stmt.name, None)
            val = self._eval(stmt.value)
            self.env[stmt.name] = val
            self._log(logging.DEBUG, f"stmt LetBinding '{stmt.name}' = {self._fmt(val)}")
            if stmt.body is not None:
                self._exec_stmt_or_expr(stmt.body)
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
        else:
            self._log(logging.DEBUG, f"expr-stmt fallback eval {kind}")
            self._eval(stmt)

    def _exec_stmt_or_expr(self, node) -> None:
        """执行语句或表达式：语句走 _exec_stmt，表达式走 _eval。"""
        if isinstance(node, (ast.Binding, ast.Output, ast.OutputTrail, ast.CodeBlock,
                             ast.SetUp, ast.ReadBlock, ast.GenStmt, ast.ChainStmt,
                             ast.MechUnit, ast.IfStmt, ast.WhileStmt, ast.ForStmt,
                             ast.MatchStmt, ast.GoStmt, ast.LetBinding,
                             ast.LetTupleBinding)):
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
            raise MathaRuntimeError(f"未知一元运算符 '{expr.op}'")
        if isinstance(expr, ast.FuncApp):
            return self._eval_func_app(expr)
        if isinstance(expr, ast.Lambda):
            self._log(logging.DEBUG, "eval Lambda → closure")
            self._log(logging.DEBUG, f"lambda closure captured keys: {list(self.env.keys())}")
            return ("__closure__", expr, dict(self.env))
        if isinstance(expr, ast.LetBinding):
            # let x = val in body — 局部绑定
            val = self._eval(expr.value)
            self.env[expr.name] = val
            self._log(logging.DEBUG, f"eval LetBinding '{expr.name}' = {self._fmt(val)}")
            if expr.body is not None:
                r = self._eval(expr.body)
            else:
                r = val
            # 清理局部绑定
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
        if isinstance(expr, ast.LetTupleBinding):
            # let (a, b) = tuple_val in body
            val = self._eval(expr.value)
            if isinstance(val, tuple):
                for i, name in enumerate(expr.names):
                    if i < len(val):
                        self.env[name] = val[i]
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
                return left_val.get(field_name)
            # 一般属性访问：尝试 getattr
            try:
                return getattr(left_val, field_name)
            except AttributeError:
                raise MathaRuntimeError(f"属性访问失败: {type(left_val).__name__}.{field_name}")
        raise MathaRuntimeError(f"暂不支持求值: {type(expr).__name__}")

    def _eval_variable(self, node: ast.Variable) -> object:
        name = node.name
        # 统一查找：env → funcs → builtins → constructors
        if name in self.env:
            v = self.env[name]
            self._log(logging.DEBUG,
                      f"eval Var '{name}' → env {self._fmt(v)}")
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
        raise MathaRuntimeError(f"未定义的函数或变量 '{name}'")

    def _eval_binary(self, node: ast.BinaryOp) -> object:
        self._log_enter("eval Binary", f"'{node.op}'")
        l = self._eval(node.left)
        r = self._eval(node.right)
        op = node.op
        if op == "+":
            result = l + r
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
                raise MathaRuntimeError(f"* 操作数类型不支持")
        elif op == "/":
            # 除法统一使用精确除法（float），整数除法需用 //
            if r == 0:
                raise MathaRuntimeError("除零错误")
            result = l / r
        elif op == "^":
            result = l ** r
        elif op == "%":
            result = l % r
        elif op == "<":
            result = l < r
        elif op == ">":
            result = l > r
        elif op == "<=":
            result = l <= r
        elif op == ">=":
            result = l >= r
        elif op == "=":
            result = l == r
        elif op == "!=":
            result = l != r
        elif op == "and":
            result = l and r
        elif op == "or":
            result = l or r
        elif op == "→":
            # 右箭头：等价于函数应用 a → b → a(b)
            if callable(l):
                result = l(r)
            elif isinstance(l, tuple) and l and l[0] == "__closure__":
                _, lam, captured = l
                result = self._call_lambda(lam, captured, [r])
            elif isinstance(l, ast.FuncDef):
                result = self._call_func(l, [r])
            else:
                raise MathaRuntimeError(f"右箭头运算符 左侧必须可调用，实际 {type(l).__name__}")
        else:
            raise MathaRuntimeError(f"未知运算符 '{op}'")
        self._log(logging.DEBUG,
                  f"binary {self._fmt(l)} {op} {self._fmt(r)} → {self._fmt(result)}")
        self._log_exit("eval Binary", result)
        return result

    def _eval_func_app(self, node: ast.FuncApp) -> object:
        self._log_enter("eval FuncApp")
        func = self._eval(node.func)
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
        if isinstance(func, ast.FuncDef):
            self._log(logging.DEBUG, f"apply FuncDef '{func.name}'({self._fmt(arg)})")
            return self._call_func(func, [arg])
        if isinstance(func, tuple) and func and func[0] == "__closure__":
            self._log(logging.DEBUG, "apply closure")
            _, lam, captured = func
            return self._call_lambda(lam, captured, [arg])
        raise MathaRuntimeError(f"不可调用的值: {func!r}")

    def _call_func(self, fdef: ast.FuncDef, args: list) -> object:
        self._log(logging.INFO,
                  f"call func '{fdef.name}' args={[self._fmt(a) for a in args]}")
        return self._call_lambda(fdef.body, self.env, args)

    def _call_lambda(self, lam: ast.Lambda, captured: dict, args: list) -> object:
        params = lam.params
        # 完整应用时也需要拷贝：递归函数会写入局部变量，共享 captured 会导致错误
        local = dict(captured)
        if len(args) < len(params):
            for p, a in zip(params, args):
                local[self._param_name(p)] = a
            remaining = params[len(args):]
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
            return ("__closure__", ast.Lambda(params=remaining, body=body), local)
        for p, a in zip(params, args):
            local[self._param_name(p)] = a
        extra = args[len(params):]
        param_names = [self._param_name(p) for p in params]
        self._log(logging.DEBUG,
                  f"lambda enter: params={param_names} args={[self._fmt(a) for a in args]}")
        saved = self.env
        self.env = local
        self._depth += 1 if self.debug else 0
        try:
            result = self._eval(lam.body)
        finally:
            self.env = saved
            if self.debug:
                self._depth = max(0, self._depth - 1)
        self._log(logging.DEBUG,
                  f"lambda exit → {self._fmt(result)}")
        if params:
            for a in extra:
                self._log(logging.DEBUG, "lambda apply extra arg")
                result = self._apply(result, a)
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

    # ---- 状态化内建实现（返回普通容器，供 Matha 侧消费） ----

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


# 延迟初始化：_curry 已定义，现在可以安全地构建缓存
_DOMAIN_BUILTINS = _build_domain_builtins()


def interpret(source: str, debug: bool | None = None) -> tuple[list, list[str]]:
    """解析并执行 Matha 源码，返回 (outputs, trace)。

    debug=None 服从 MATHA_DEBUG 环境变量；显式 True/False 优先。
    """
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
