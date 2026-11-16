"""Matha 领域扩展模块：自主能力（Autonomous Capability）。

插件面符号（自主_调试 / 自主_优化 / 自主_成长 / 资源_加载 / 资源_成长 /
软件_构建）的 VM 注册面。宿主解释器把这些符号直接注册在内建表
（src/interp.py：直接绑定运行中的解释器本体）；VM 侧经官方入口
（src/kernel/exec_api）运行时由领域解析器按清单物化本模块。能力实现
（调试器/优化器/成长器/资源库/软件构建）内部自建解释器或沙箱验证，
不消费运行上下文，因此注入全新的共享语境解释器即可与宿主面收敛。
"""

from __future__ import annotations

_context_singleton = None


def _context():
    """共享语境解释器（惰性创建，全部能力符号共用一个本体）。"""
    global _context_singleton
    if _context_singleton is None:
        from src.interp import Interpreter
        _context_singleton = Interpreter()
    return _context_singleton


def _curry1(func):
    def with_first(a): return func(a)
    return with_first

def _curry2(func):
    def with_first(a): return lambda b: func(a, b)
    return with_first

def _curry3(func):
    def w1(a):
        def w2(b): return lambda c: func(a, b, c)
        return w2
    return w1


def _自主_调试(源码, 次数):
    """自主调试：捕获错误 → 生成修复候选 → 沙箱验证 → 提交。"""
    from src.autonomous import auto_debug
    return auto_debug(_context(), 源码, int(次数))


def _自主_优化(函数名, 策略):
    """自主优化：识别热点 → 记忆化优化 → 等价对比 → 提交（策略与宿主面一致，不参与分派）。"""
    from src.autonomous import auto_optimize_memoize
    return auto_optimize_memoize(_context(), str(函数名))


def _自主_成长(源码, 描述):
    """自主成长：从源码学习新能力 → 沙箱验证 → 注册。"""
    from src.autonomous import self_grow
    return self_grow(_context(), 源码, str(描述))


def _资源_加载(路径, _0):
    """资源_加载(路径)(0) → 沙箱加载资源到本体。"""
    from src.library import get_library
    return get_library().load(str(路径), _context())


def _资源_成长(需求, 学科, 名称):
    """资源_成长(需求)(学科)(名称) → 资源库自主扩展生成新资源。"""
    from src.library import get_library
    r = get_library().grow(_context(), str(需求), str(学科) or "core",
                           str(名称) or None)
    return r.as_dict()


def _软件_构建(需求):
    """软件_构建(需求) → 自主构建成品软件。"""
    from src.autonomous import build_software
    return build_software(_context(), str(需求))


def _normalize_spec(spec):
    """规格归一化：字符串可解析为 JSON 列表则解析，否则原样（与宿主面一致）。"""
    if isinstance(spec, str):
        try:
            import json
            return json.loads(spec)
        except Exception:
            return spec
    return spec


def _生成_网页(规格):
    """生成_网页(规格) → 编译为 HTML/CSS/JS 成品。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _生成_桌面(规格):
    """生成_桌面(规格) → 编译为 Python Tkinter 桌面程序。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _生成_服务(规格):
    """生成_服务(规格) → 编译为 Python HTTP 服务。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _生成_系统(规格):
    """生成_系统(规格) → 编译为系统脚本。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _生成_游戏(规格):
    """生成_游戏(规格) → 编译为 HTML5 Canvas 游戏。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _生成_建模(规格):
    """生成_建模(规格) → 编译为 Three.js 3D 模型场景。"""
    from src.codegen import codegen
    return codegen(_normalize_spec(规格), None).as_dict()


def _merge_source_functions(runtime, source: str, names=None) -> list[str]:
    """把 Matha 源码定义的函数编译进运行中 VM 的全局表（平铺合并）。

    与宿主面「合并进运行中的解释器」同构：宿主经 Sandbox.commit 写
    interp.funcs，VM 面经 compile_program + Closure 写 globals。
    names=None 时合并源码定义的全部函数。
    """
    from src.parser import parse
    from src.mbc.compiler import compile_program
    from src.mbc.vm import Closure
    mod = compile_program(parse(source))
    merged = []
    for name in (names if names is not None else list(mod.functions)):
        fn = mod.functions.get(name)
        if fn is not None:
            # 跨模块移植：函数指令的常量下标指向来源模块的池（VM 分派按帧取池）
            fn.consts = mod.constants
            # 函数体 MAKE_CLOSURE 同样按来源模块的表解析（__lam_N 按模块独立计数）
            fn.functions = mod.functions
            runtime.globals[name] = Closure(fn, runtime.main_frame)
            merged.append(name)
    return merged


def _eval_module_let(node, runtime):
    """模块级 let 值的最小求值面（被载模块合并用）。

    语料形态：数值/字符串/布尔字面量、字典/列表字面量（值可为已合并
    函数名的 Variable 引用，如 编译器 二元运算表、运行时引擎 内建函数表）。
    其余形态诚实拒绝——use 合并面不承诺任意表达式求值。
    """
    from src import ast_nodes as ast
    if isinstance(node, ast.IntegerLit | ast.FloatLit | ast.StringLit | ast.BoolLit):
        return node.value
    if isinstance(node, ast.DictLiteral):
        return {_eval_module_let(k, runtime): _eval_module_let(v, runtime)
                for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.ListLiteral):
        return [_eval_module_let(e, runtime) for e in node.elements]
    if isinstance(node, ast.UnaryOp) and node.op == "null":
        return None
    if isinstance(node, ast.Variable):
        v = runtime.globals.get(node.name)
        if v is None:
            raise RuntimeError(f"模块级 let 引用未合并的名字 '{node.name}'")
        return v
    raise RuntimeError(f"模块级 let 含暂不支持的形态 {type(node).__name__}")


def _merge_module_source(runtime, source: str) -> tuple[str | None, list[str]]:
    """use 编译面：模块级合并——函数/枚举/模块级 let 落 globals + 命名空间绑定。

    与宿主 ModuleDecl 注册同构（self.modules[name] = module_ns 且
    env[name] = module_ns）：合并全部函数；枚举成员物化为字符串全局
    （宿主 constructors 语义，裸枚举变量 → 名字字符串）+ 枚举名 dict
    （支持 类型.整数 点号访问）；模块级 let 按 _eval_module_let 物化。
    被载模块的自测块不执行（与宿主 _loading_module 跳过同构）。
    返回 (模块声明名, 合并函数名列表)。
    """
    from src import ast_nodes as ast
    from src.parser import parse
    from src.mbc.compiler import compile_program
    from src.mbc.vm import Closure
    prog = parse(source)
    actual_name = None
    for decl in prog.decls:
        if isinstance(decl, ast.ModuleDecl):
            actual_name = decl.name
            break
    mod = compile_program(prog)
    ns: dict = {}
    for name, fn in mod.functions.items():
        fn.consts = mod.constants
        fn.functions = mod.functions
        cl = Closure(fn, runtime.main_frame)
        runtime.globals[name] = cl
        ns[name] = cl
    for decl in prog.decls:
        scope = decl.decls if isinstance(decl, ast.ModuleDecl) else [decl]
        for inner in scope:
            if isinstance(inner, ast.EnumDef):
                members = [c.name if isinstance(c, ast.Variable) else str(c)
                           for c in inner.ctors]
                for nm in members:
                    runtime.globals[nm] = nm
                    ns[nm] = nm
                # 枚举名 → {构造子: 构造子} dict（与编译器 EnumDef 发射同构）
                runtime.globals[inner.name] = {m: m for m in members}
                ns[inner.name] = runtime.globals[inner.name]
            elif isinstance(inner, ast.LetBinding):
                v = _eval_module_let(inner.value, runtime)
                runtime.globals[inner.name] = v
                ns[inner.name] = v
    if actual_name is not None:
        runtime.globals[actual_name] = ns
    return actual_name, list(mod.functions)


def make_runtime(runtime):
    """官方入口注入面：返回绑定运行中 VM 的效果面胶水内建。

    资源_加载 / 资源_成长 的效果（把资源函数合并进运行本体）必须落在
    运行中的 VM 上——宿主面内建绑定运行中的解释器（src.interp 内建表），
    VM 面由 src.kernel.exec_api 注入本工厂产物（setdefault，不覆盖
    程序自定义同名函数）。其余能力符号（自主_* / 软件_构建）自建
    解释器/沙箱验证、不消费运行上下文，解析器物化面即已收敛。
    """
    from src.library import get_library
    ctx = _context()

    def _资源_加载(路径, _0):
        r = get_library().load(str(路径), ctx)
        if r.get("成功"):
            entry = get_library().get_entry(str(路径))
            if entry is not None:
                _merge_source_functions(runtime, entry.content, r["新函数"])
        return r

    def _资源_成长(需求, 学科, 名称):
        r = get_library().grow(ctx, str(需求), str(学科) or "core",
                               str(名称) or None)
        d = r.as_dict()
        if r.成功 and r.内容:
            _merge_source_functions(runtime, r.内容)
        return d

    return {"资源_加载": _curry2(_资源_加载), "资源_成长": _curry3(_资源_成长)}


def make_module_loader(runtime):
    """use 编译面胶水工厂：加载模块(模块名) 把被 use 模块合并进运行中 VM。

    与宿主 load_matha_module 同构（matha/ 源文件 → 编译 → 合并进运行
    本体；幂等 loaded-set 按声明名/请求名双重去重）。裸 VM /
    plugins="off" 无此全局，use 语句诚实报「未定义名 加载模块」。
    """
    from src.interp import load_matha_source
    loaded: set[str] = set()

    def _加载模块(模块名: str) -> list[str]:
        name = str(模块名)
        if name in loaded:
            return []
        actual, merged = _merge_module_source(runtime, load_matha_source(name))
        loaded.add(name)
        if actual is not None:
            loaded.add(actual)
        return merged

    return _加载模块


# ---- 阶段 24g：热启动/热重载（mtime 热重载，双面同文消息） ----

HOT_TARGET_ERR = "热启动/热重载: 目标须为非空文本（模块名或 .matha 文件路径）"
HOT_NOT_STARTED = "热重载: 「{}」尚未热启动——先调用 热启动(模块名或路径)"
HOT_NO_FILE = "热重载: 源文件已不存在: {}"
HOT_NO_PATH = "热重载: 无法跟踪源文件（模块来自纯文本解析面），热重载不可用"


def make_hotreload_runtime(runtime):
    """热启动/热重载 运行时胶水工厂（阶段 24g，官方入口注入面）。

    与宿主面 src.interp 内建 _b_hot_start/_b_hot_reload 同语义：
    热启动(目标) 装载模块（.matha 文件路径优先，模块名走 matha/ →
    安装包 → 资源库 三级解析）+ 记录 mtime 快照；热重载(目标) 对比
    mtime——未变更如实返回 重载=False，已变更重编译合并（globals
    直接覆盖，与 use 合并同机制）+ 更新快照。消息常量与宿主面同源
    （src.interp 惰性导入），双面逐字一致；声明数同口径（parse 顶层
    声明数）。被载模块自测块不执行（_merge_module_source 只合并
    函数/枚举/let，与宿主 _loading_module 跳过同构）。
    """
    from src.interp import hot_reload_pair
    from src.parser import parse
    from pathlib import Path
    snaps: dict[str, tuple[str, float | None]] = {}

    def _装载(source, target):
        from src import ast_nodes as ast
        prog = parse(source)
        actual = target
        for decl in prog.decls:
            if isinstance(decl, ast.ModuleDecl):
                actual = decl.name
                break
        _merge_module_source(runtime, source)
        return actual, len(prog.decls)

    def _热启动(target):
        if not isinstance(target, str) or not target:
            raise ValueError(HOT_TARGET_ERR)
        source, path = hot_reload_pair(target)
        actual, n = _装载(source, target)
        mtime = path.stat().st_mtime if path is not None else None
        snaps[target] = (str(path) if path is not None else "", mtime)
        return {"模块": actual, "已加载": True, "声明数": n,
                "路径": str(path) if path is not None else "",
                "时间戳": mtime if mtime is not None else 0.0}

    def _热重载(target):
        if not isinstance(target, str) or not target:
            raise ValueError(HOT_TARGET_ERR)
        snap = snaps.get(target)
        if snap is None:
            raise ValueError(HOT_NOT_STARTED.format(target))
        path_str, old_mtime = snap
        if not path_str:
            raise ValueError(HOT_NO_PATH)
        p = Path(path_str)
        if not p.is_file():
            raise ValueError(HOT_NO_FILE.format(path_str))
        cur = p.stat().st_mtime
        if cur == old_mtime:
            return {"模块": target, "重载": False, "声明数": 0,
                    "路径": path_str, "时间戳": cur}
        source, _ = p.read_text(encoding="utf-8"), p
        actual, n = _装载(source, target)
        snaps[target] = (path_str, cur)
        return {"模块": actual, "重载": True, "声明数": n,
                "路径": path_str, "时间戳": cur}

    return {"热启动": _热启动, "热重载": _热重载}


def _register_capability(builtins: dict) -> None:
    builtins["自主_调试"] = _curry2(_自主_调试)
    builtins["自主_优化"] = _curry2(_自主_优化)
    builtins["自主_成长"] = _curry2(_自主_成长)
    builtins["资源_加载"] = _curry2(_资源_加载)
    builtins["资源_成长"] = _curry3(_资源_成长)
    builtins["软件_构建"] = _curry1(_软件_构建)
    builtins["生成_网页"] = _curry1(_生成_网页)
    builtins["生成_桌面"] = _curry1(_生成_桌面)
    builtins["生成_服务"] = _curry1(_生成_服务)
    builtins["生成_系统"] = _curry1(_生成_系统)
    builtins["生成_游戏"] = _curry1(_生成_游戏)
    builtins["生成_建模"] = _curry1(_生成_建模)


def _capability_symtab_names() -> list[str]:
    return ["自主_调试", "自主_优化", "自主_成长",
            "资源_加载", "资源_成长", "软件_构建",
            "生成_网页", "生成_桌面", "生成_服务",
            "生成_系统", "生成_游戏", "生成_建模"]


__all__ = [
    "_自主_调试", "_自主_优化", "_自主_成长",
    "_资源_加载", "_资源_成长", "_软件_构建",
    "_生成_网页", "_生成_桌面", "_生成_服务",
    "_生成_系统", "_生成_游戏", "_生成_建模",
    "_register_capability", "_capability_symtab_names",
    "_merge_source_functions", "_merge_module_source",
    "make_runtime", "make_module_loader", "make_hotreload_runtime",
    "HOT_TARGET_ERR", "HOT_NOT_STARTED", "HOT_NO_FILE", "HOT_NO_PATH",
]
