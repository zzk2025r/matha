# -*- coding: utf-8 -*-
"""29d Track B：自举执行面全语料 sweep（boot 面 5 文件链 + 宿主面对拍）。

语料枚举与 ast_vm_matrix 同口径（matha/examples/golden_tests/tests/stdlib
五目录 rglob("*.matha")）。逐文件统一判据：

  boot 面   输出清空 → 扫描 → parse → 注册内建(空环境) → 执行语句 → 输出快照
            （每文件 fresh env0，输出槽复位；bootvm 每 worker 构建一次复用）
  宿主面    host_interp.interpret（每文件新解释器）
  双 ok     输出归一（数值 float 化 / dict 键字符串化）相等 → equal=true；
            不等 → equal=false 记首分歧下标
  单边错误  boot_err / host_err 诚实记录（截断 240 字符）
  超时      per-file get 超时 + 全局轮预算；uncollected 下一轮重试，
            三轮未收 → honest "timeout"（含 worker 崩溃丢任务面）

用法：
  python scripts/selfhost_matrix.py --write [--workers N] [--timeout 秒] [--filter 子串] [--limit N]
  python scripts/selfhost_matrix.py --check        # 全量重跑与快照对拍（重档 lane）
  python scripts/selfhost_matrix.py --structure    # 快结构锁：文件清单一致 + 汇总算术闭合（pytest 门禁用）

快照 docs/selfhost_matrix.json：summary 计数闭合 + files 按路径排序；
不含时间戳（确定性）。known 双面一致遗留语义（输出追踪双记/空输出记 0）
不改判据——equal 只问 boot 与宿主是否一致，不问语义"应该"是什么。

31e：manifest preload 装配镜像（golden_tests/run_golden_tests.py:378 同构）——
golden_tests/cases/<stem>.matha 按 manifest `cases.<stem>.preload` 前置拼接
库源码后双轨跑同一文本（golden 36-39 即此形态，裸读双轨 both_err）。
"""
import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SNAPSHOT = ROOT / "docs" / "selfhost_matrix.json"
CORPUS_DIRS: tuple[str, ...] = ("matha", "examples", "golden_tests", "tests", "stdlib")
BOOT_FILES: tuple[str, ...] = ("matha/lexer.matha", "matha/stdlib.matha",
                               "matha/parser.matha",
                               "matha/runtime/matha_runtime.matha",
                               "matha/interp_matha.matha")
_ERR_TRUNC = 240

# 31e：golden manifest preload 装配（镜像 run_golden_tests.py:378 前置拼接）。
_manifest_cases: dict | None = None


def _manifest_preloads(rel: str) -> list[str]:
    """golden_tests/cases/<stem>.matha 的 manifest preload 路径表；其余语料 []。"""
    global _manifest_cases
    if _manifest_cases is None:
        _manifest_cases = json.loads(
            (ROOT / "golden_tests" / "manifest.json")
            .read_text(encoding="utf-8")).get("cases", {})
    parts = Path(rel).parts
    if len(parts) < 3 or parts[0] != "golden_tests" or parts[1] != "cases":
        return []
    return _manifest_cases.get(Path(rel).stem, {}).get("preload", [])


def _assemble_source(rel: str) -> str:
    """语料源装配：BOM 剥离 + manifest preload 前置拼接（双轨同源）。"""
    src = (ROOT / rel).read_text(encoding="utf-8")
    src = src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src
    for pre in _manifest_preloads(rel):
        src = (ROOT / pre).read_text(encoding="utf-8") + "\n" + src
    return src


# ---------------- 30e：boot 面域插件符号注入（拍板①驱动器级） ----------------
#
# Track B 判据 = 同一内建面下 boot 解释器 ≡ 宿主解释器。宿主面内建表 = 真实
# Interpreter 实例 builtins 表（内核 BUILTINS + 懒内核节 + _DOMAIN_BUILTINS +
# 实例级安装），表面名口径 keys()（原始键 ∪ 延迟表 ∪ 解析器全导出清单，
# defer_to_plugins：内核同名符号内核胜出）；boot 面对齐 = 注册内建固定面
# （不动，内核胜出同口径）+ 注入宿主全表面（真实现非桩，排除 boot 已有面
# 同名符号）。资源库面（资源_加载 把资源函数并入宿主解释器 globals、
# 资源_成长 把成长产物函数并入）由驱动器按语料 AST 字面量预执行到 boot env
# （preload_resources——资源源码/成长产物经 boot 解释器真执行；成长走注入的
# 真实现 grow 链取 内容 再预执行，库内已保护资源幂等无文件写入）；运行期
# 调用本身走注入的真实现。自举链零改动——脱宿主纯度维持：链本身不含域插件，
# 域面由驱动器显式注入。解析失败/资源缺失/预执行失败如实跳过——保持
# boot_err，不造假成功。boot 自有面名字从 注册内建(空环境) 运行期探测，
# 不硬编码（链演化自动跟随）。
_inject_table = None


def _adapt_callable(fn):
    """定长多参 Python 函数 → 逐参收集链（VM _invoke 对普通可调用逐参应用
    r=r(a)；签名 n 参直调会缺参 TypeError）。柯里化链（签名 1 参）与变参
    原样直通；必需位数按无默认值参数计（宿主按已给实参调用，缺省参数由
    Python 默认值补齐同口径）；必需关键字参数无法按位喂入——原样直通，
    与宿主同样诚实报错。"""
    import inspect
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn
    n = 0
    for p in sig.parameters.values():
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            if p.default is p.empty:
                n += 1
        elif p.kind is p.VAR_POSITIONAL:
            return fn
        elif p.kind is p.KEYWORD_ONLY and p.default is p.empty:
            return fn
    if n <= 1:
        return fn

    def collect(*got):
        if len(got) >= n:
            return fn(*got)
        return lambda x: collect(*got, x)

    return collect


def boot_surface_names(vm) -> set:
    """boot 自有面名集：注册内建(空环境) 的 env 键 + 链模块命名空间名。"""
    env = vm.call("注册内建", vm.call("空环境"))
    names = {pair[0] for pair in env}
    names |= {"词法器", "标准库", "语法器", "运行时引擎", "解释器"}
    return names


def _host_surface():
    """宿主内建全表面：真实 Interpreter 实例的 builtins 表（内核 BUILTINS +
    _DOMAIN_BUILTINS + 实例级安装：解析_JSON 等懒内核节 + 调用捕获）。表面
    名口径用 table.keys()——LazyBuiltinTable 重写 keys()/_names() = 原始键 ∪
    延迟表 ∪ 解析器全导出清单，即宿主可解析全表面。defer_to_plugins 语义由
    LazyBuiltinTable 取值路径原样保留。"""
    global _inject_table
    if _inject_table is None:
        from src.interp import Interpreter
        _inject_table = Interpreter().builtins
    return _inject_table


# 链判据关键名：宿主同名符号不得注入（env 与 register_builtin 双面都不覆盖）。
# type_of 是链代码（应用函数 等）经 VM globals 分派的判据内建——宿主 type_of 对
# VM Closure 返 "Unknown" 会击穿 "Function" 分支，use 导入的链命名空间函数全体
# 不可调用。boot 面语义 = VM _builtin_type_of（Closure → Function），与宿主面对
# 普通值同名同果（Int/Float/String/List/Dict/Null/Function），仅 VM Closure/
# Partial 这类 boot 专有值不同——恰是 boot 面应有的分类。
_CHAIN_CRITICAL = frozenset({"type_of"})


def inject_domain_builtins(vm, env, skip=frozenset()):
    """宿主内建全表面注入 boot env（Track B 驱动器与 Track A 锁共用面）。

    注入源 = 宿主 Interpreter 实例 builtins 表（内核 + 懒内核节 + 实例级安装，
    defer_to_plugins 保留）∪ 解析器全导出清单；sorted
    确定性注入：可调用值经 28d VM.register_builtin 端口登记 + env 绑定（多参
    经 _adapt_callable 适配），常量值仅绑 env（register_builtin 对非可调用
    诚实拒绝）。skip = boot 自有面名（boot_surface_names）——boot 固定面胜出，
    与宿主 defer_to_plugins「内核同名内核胜出」同口径。_CHAIN_CRITICAL 名
    （type_of）双面都不覆盖：register_builtin 会改写 VM globals 上的链分派
    判据内建，env 绑定会遮蔽用户面 type_of——改绑 VM globals 现值（boot
    _builtin_type_of），用户面 type_of 与链判据同源同语义。解析失败符号（值为
    None 且解析不出）如实跳过——保持 boot_err，不造假成功。"""
    table = _host_surface()
    for name in sorted(table.keys()):
        if name in skip or name in _CHAIN_CRITICAL:
            continue
        try:
            fn = table[name]
        except KeyError:
            # 清单列了名但物化缺符号（清单漂移）：如实跳过，保持 boot_err。
            continue
        if fn is None:
            continue
        adapted = _adapt_callable(fn) if callable(fn) else fn
        env = vm.call("绑定环境", env, name, adapted)
        if callable(adapted):
            try:
                vm.register_builtin(name, adapted)
            except ValueError:
                # 端口面诚实拒绝（保留名/链模块同名函数）：env 面照绑——宿主
                # 内建表与模块函数同名并存同口径，env/模块绑定各自遮蔽生效。
                pass
    env = vm.call("绑定环境", env, "type_of", vm.globals["type_of"])
    return env


def _resource_paths(prog) -> list[str]:
    """扫 boot dict-AST 收集 资源_加载 的资源路径（30e 资源预装载面）。

    两种语料形态：直接字面量 资源_加载("core/arithmetic")（10_library_sub）与
    绑定字面量变量 资源_加载(路径)（10_library_read——路径 由前置
    @：【读取参数】，路径="core/arithmetic" 设值项绑定）。按文档序走树，设值项
    先于调用访问；找不到字面量的变量如实跳过（boot 面保持未预载，与宿主
    运行期资源缺失面一致）。其余资源加载形态（间接变量）不识别——诚实
    保持 boot_err。"""
    binds: dict[str, str] = {}
    paths: list[str] = []

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            t = node.get("类型")
            if t in ("设值项", "绑定"):
                tgt = node.get("目标")
                name = node.get("名") or (tgt.get("名") if isinstance(tgt, dict) else None)
                val = node.get("值")
                if (isinstance(name, str) and isinstance(val, dict)
                        and val.get("类型") == "字符串"
                        and isinstance(val.get("值"), str)):
                    binds.setdefault(name, val["值"])
            elif (t == "函数应用" and isinstance(node.get("函数"), dict)
                  and node["函数"].get("类型") == "变量"
                  and node["函数"].get("名") == "资源_加载"):
                arg = node.get("参数")
                if isinstance(arg, dict) and arg.get("类型") == "字符串":
                    paths.append(arg["值"])
                elif isinstance(arg, dict) and arg.get("类型") == "变量":
                    v = binds.get(arg.get("名"))
                    if isinstance(v, str):
                        paths.append(v)
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v)

    walk(prog)
    return paths


def _grow_calls(prog) -> list[tuple[str, str, str]]:
    """扫 boot dict-AST 收集 资源_成长(需求)(学科)(名称) 三参完整链（30e）。

    柯里化链左脊：外层节点左脊末端为 变量(资源_成长) 且恰三参——中段节点
    （一参/两参）被参数计数过滤，只收完整链。参数为字符串字面量或绑定
    字面量变量；不识别形态如实跳过（boot 面保持未预生成，与宿主运行期
    非字面量形态一致）。"""
    binds: dict[str, str] = {}
    calls: list[tuple[str, str, str]] = []

    def _arg_value(node):
        if (isinstance(node, dict) and node.get("类型") == "字符串"
                and isinstance(node.get("值"), str)):
            return node["值"]
        if isinstance(node, dict) and node.get("类型") == "变量":
            v = binds.get(node.get("名"))
            if isinstance(v, str):
                return v
        return None

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            t = node.get("类型")
            if t in ("设值项", "绑定"):
                tgt = node.get("目标")
                name = node.get("名") or (tgt.get("名") if isinstance(tgt, dict) else None)
                val = node.get("值")
                if (isinstance(name, str) and isinstance(val, dict)
                        and val.get("类型") == "字符串"
                        and isinstance(val.get("值"), str)):
                    binds.setdefault(name, val["值"])
            elif t == "函数应用" and isinstance(node.get("函数"), dict):
                args = []
                cur = node
                while (isinstance(cur, dict) and cur.get("类型") == "函数应用"
                       and isinstance(cur.get("函数"), dict)):
                    args.append(cur.get("参数"))
                    cur = cur["函数"]
                if (isinstance(cur, dict) and cur.get("类型") == "变量"
                        and cur.get("名") == "资源_成长" and len(args) == 3):
                    vals = [_arg_value(a) for a in reversed(args)]
                    if all(isinstance(v, str) for v in vals):
                        calls.append((vals[0], vals[1], vals[2]))
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v)

    walk(prog)
    return calls


def _boot_exec_bind(vm, content, env, skip=frozenset()):
    """boot 解释器真执行 content 源码，env 新增名绑定进 env（预装载共用面）。

    扫描→parse→注册内建→注入→执行语句；预执行失败/输出槽复位后如实返回
    原 env（不绑）——保持 boot_err。"""
    try:
        vm.call("输出清空")
        toks = vm.call("扫描", content, 0, 1, 1, [])
        rprog = vm.call("parse", toks)
        renv = vm.call("注册内建", vm.call("空环境"))
        renv = inject_domain_builtins(vm, renv, skip=skip)
        before = {p[0] for p in renv}
        _, renv2 = vm.call("执行语句", rprog, renv)
        vm.call("输出清空")
    except Exception:
        vm.call("输出清空")
        return env
    fresh: dict = {}
    for p in renv2:
        if p[0] not in before and p[0] not in fresh:
            fresh[p[0]] = p[1]
    for name in sorted(fresh):
        env = vm.call("绑定环境", env, name, fresh[name])
    return env


def preload_resources(vm, prog, env, skip=frozenset()):
    """资源预装载（30e）：宿主面 资源_加载 经沙箱把资源函数并入解释器
    globals（src/library.py Library.load）、资源_成长 把成长产物函数并入
    运行中解释器（_b_library_grow 沙箱验证 + commit），boot env 函数化线程
    无法由注入函数改写——驱动器按语料 AST 字面量预执行到 boot env。

    资源经 boot 解释器真执行（_boot_exec_bind）；成长走注入的真实现 grow 链
    （GrowResult 新资源 → 资源库取回已入库源码）再预执行——库内已保护资源
    幂等（不覆盖已保护资源，无文件写入）。预执行失败/资源不存在如实不绑
    ——保持 boot_err。运行期 资源_加载/资源_成长 调用本身走注入的真实现
    （与宿主 _b_library_* 同实现同值），语义闭环：定义面来自同一资源的
    boot 真执行。"""
    seen: set = set()
    from src.library import get_library
    lib = get_library()
    paths = _resource_paths(prog)
    if paths:
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            entry = lib.get_entry(str(path))
            if entry is None:
                continue
            env = _boot_exec_bind(vm, entry.content, env, skip)
    for req, disc, name in _grow_calls(prog):
        key = (req, disc, name)
        if key in seen:
            continue
        seen.add(key)
        grow_fn = None
        for p in env:
            if p[0] == "资源_成长":
                grow_fn = p[1]
                break
        if not callable(grow_fn):
            continue
        try:
            r = grow_fn(req)(disc)(name)
        except Exception:
            continue
        if isinstance(r, dict) and r.get("成功") and isinstance(r.get("新资源"), str):
            entry = lib.get_entry(r["新资源"])
            if entry is not None:
                env = _boot_exec_bind(vm, entry.content, env, skip)
    return env


def corpus_files(filter_sub: str | None = None, limit: int | None = None) -> list[str]:
    files: list[str] = []
    for d in CORPUS_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.matha")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in BOOT_FILES:
                continue
            files.append(rel)
    if filter_sub:
        files = [f for f in files if filter_sub in f]
    if limit:
        files = files[:limit]
    return files


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


def _first_div(a, b):
    """首分歧下标（归一层），无分歧返回 None。"""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return None
    if isinstance(na, list) and isinstance(nb, list):
        for i in range(min(len(na), len(nb))):
            if na[i] != nb[i]:
                return i
        return min(len(na), len(nb))
    return "?"


# ---------------- worker ----------------

_worker_vm = None

_WARMUP_TIMEOUT = 1800.0


def _warm(_i):
    return None


def _worker_init():
    global _worker_vm
    sys.setrecursionlimit(20000)
    sys.set_int_max_str_digits(0)
    from src import ast_nodes as ast
    from src.kernel.errors import MathaRuntimeError
    from src.mbc.compiler import Compiler
    from src.mbc.vm import VM
    from src.parser import parse as py_parse

    def _strip_bom(src):
        return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src

    comp = Compiler()
    decls = []
    chain_asts = {}
    for rel in BOOT_FILES:
        prog = py_parse(_strip_bom(
            (ROOT / rel).read_text(encoding="utf-8")))
        chain_asts[rel] = prog
        decls.extend(prog.decls)
    comp.compile_program(ast.Program(decls=decls))
    _worker_vm = VM(comp.mod)
    _worker_vm.run()
    _worker_vm.globals["MathaRuntimeError"] = MathaRuntimeError
    # 链模块 ns 预绑定（driver 面，29d）：只绑定在场的链模块命名空间。
    global _worker_nss, _chain_structs
    _worker_nss = {nm: _worker_vm.globals[nm]
                   for nm in ("词法器", "标准库", "语法器", "运行时引擎", "解释器")
                   if isinstance(_worker_vm.globals.get(nm), dict)}
    # 链模块 struct 工厂合成（30b）：编译面模块 ns 刻意不收 struct（VM 面无码，
    # compiler.py「语料经 做X 函数构造」）；宿主面 use 从解释器装载的模块 ns 含
    # struct 工厂。此处从链文件 AST 合成解释器形状工厂
    # ["__struct工厂__", 名, 字段名们]（boot 应用函数 30a 臂可调用），供
    # _ensure_module 链命中时并入 ns 副本——Token 一类跨模块 use 才能解析。
    _chain_structs = {}
    for rel, prog in chain_asts.items():
        for d in prog.decls:
            if isinstance(d, ast.ModuleDecl):
                factories = {}
                for inner in d.decls:
                    if isinstance(inner, ast.StructDef):
                        factories[inner.name] = [
                            "__struct工厂__", inner.name,
                            [f[0] for f in inner.fields]]
                if factories:
                    _chain_structs[d.name] = factories
    # boot 自有面名集（30e）：注册内建 固定面 + 链 ns 名——域符号注入跳过集
    global _boot_skip
    _boot_skip = frozenset(boot_surface_names(_worker_vm))


_worker_nss = {}
_boot_skip: frozenset = frozenset()


# ---------------- 30b：driver 面 use 跨模块懒装载（宿主 _exec_use 镜像） ----------------
#
# 语料文件的 `use X` 在 boot 面由 导入绑定 从 env 解析（29d 起），非链模块需
# driver 预装载入 env0：解析序 matha/（_CN2FILE 同表镜像 → <名>.matha）→
# matha/library/**（stem 命中），与宿主 _load_matha_source 前两级一致；链模块
# （词法器/标准库/语法器/运行时引擎/解释器）已编译进 boot 链，直接命中
# _worker_nss。模块经 boot 解释器 执行语句 预执行（顶层 机械单元 自测块过滤，
# 宿主载入中跳过自测块同构），命名空间取 执行模块体 绑定的 env 名（R1 同名
# 冲突不绑定时如实 None）。循环导入诚实报错；模块体输出经 输出清空 丢弃。

_CN2FILE = {
    "词法器": "lexer.matha",
    "语法器": "parser.matha",
    "标准库": "stdlib.matha",
    "解释器": "interp.matha",
    "虚拟机": "vm/matha_vm.matha",
    "自举加载器": "bootstrap_matha.matha",
    "编译器": "compiler_matha.matha",
    "自然语言词法器": "nl_lexer.matha",
    "自然语言句法器": "nl_parser.matha",
    "自然语言执行器": "nl_engine.matha",
    "用户词典": "nl_dict.matha",
    "自然语言英语词法器": "nl_lexer_en.matha",
    "自然语言英语句法器": "nl_parser_en.matha",
    "自然语言英语执行器": "nl_engine_en.matha",
    "终端词法器": "term_lexer.matha",
    "终端句法器": "term_parser.matha",
    "终端执行器": "term_engine.matha",
    "应用中心": "store_engine.matha",
    "内核": "os/kernel.matha",
    "桌面": "os/desktop.matha",
    "资源索引": "library/index.matha",
}

_module_cache: dict = {}
_chain_structs: dict = {}


def _augment_chain_ns(name: str):
    """链模块 ns 补齐 struct 工厂（30b）：编译面 ns + AST 合成工厂副本。

    编译面函数/枚举权威（VM Closure 值），仅并入编译面缺失的 struct 工厂
    （解释器形状 ["__struct工厂__",...]）；副本缓存，编译面原 ns 不改写。"""
    base = _worker_nss[name]
    factories = _chain_structs.get(name)
    if not factories:
        return base
    merged = dict(base)
    for sn, factory in factories.items():
        if sn not in merged:
            merged[sn] = factory
    return merged


def _module_path(name: str):
    rel = _CN2FILE.get(name)
    if rel:
        p = ROOT / "matha" / rel
        if p.exists():
            return p
    p = ROOT / "matha" / f"{name}.matha"
    if p.exists():
        return p
    lib = ROOT / "matha" / "library"
    if lib.is_dir():
        for p in sorted(lib.rglob("*.matha")):
            if p.stem == name:
                return p
    return None


def _collect_use_names(node, acc: list) -> list:
    if isinstance(node, list):
        for x in node:
            _collect_use_names(x, acc)
    elif isinstance(node, dict):
        if node.get("类型") == "导入" and node.get("模块名"):
            acc.append(node["模块名"])
        for v in node.values():
            if isinstance(v, (list, dict)):
                _collect_use_names(v, acc)
    return acc


def _ensure_module(name: str, in_flight: frozenset):
    if name in _module_cache:
        return _module_cache[name]
    if name in _worker_nss:
        ns = _augment_chain_ns(name)
        _module_cache[name] = ns
        return ns
    if name in in_flight:
        raise RuntimeError(f"循环导入: {name}")
    path = _module_path(name)
    if path is None:
        raise FileNotFoundError(f"找不到 Matha 模块: {name}")
    src = path.read_text(encoding="utf-8")
    src = src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src
    _worker_vm.call("输出清空")
    toks = _worker_vm.call("扫描", src, 0, 1, 1, [])
    prog = _worker_vm.call("parse", toks)
    env_m = _worker_vm.call("注册内建", _worker_vm.call("空环境"))
    env_m = inject_domain_builtins(_worker_vm, env_m, skip=_boot_skip)
    env_m = preload_resources(_worker_vm, prog, env_m, skip=_boot_skip)
    for nm, ns in _worker_nss.items():
        env_m = _worker_vm.call("绑定环境", env_m, nm, ns)
    for dep in _collect_use_names(prog.get("声明", []), []):
        dep_ns = _ensure_module(dep, in_flight | {name})
        if dep_ns is not None:
            env_m = _worker_vm.call("绑定环境", env_m, dep, dep_ns)
    if isinstance(prog.get("声明"), list):
        prog = dict(prog, 声明=[d for d in prog["声明"]
                               if not (isinstance(d, dict)
                                       and d.get("类型") == "机械单元")])
    _, env_m2 = _worker_vm.call("执行语句", prog, env_m)
    ns = None
    for pair in env_m2:
        if pair[0] == name:
            ns = pair[1]
            break
    _worker_vm.call("输出清空")
    _module_cache[name] = ns
    return ns


def _run_one(rel: str) -> dict:
    src = _assemble_source(rel)
    entry = {"path": rel}
    b_outs = b_err = None
    try:
        _worker_vm.call("输出清空")
        toks = _worker_vm.call("扫描", src, 0, 1, 1, [])
        prog = _worker_vm.call("parse", toks)
        env0 = _worker_vm.call("注册内建", _worker_vm.call("空环境"))
        env0 = inject_domain_builtins(_worker_vm, env0, skip=_boot_skip)
        env0 = preload_resources(_worker_vm, prog, env0, skip=_boot_skip)
        for nm, ns in _worker_nss.items():
            env0 = _worker_vm.call("绑定环境", env0, nm, ns)
        for dep in _collect_use_names(prog.get("声明", []), []):
            dep_ns = _ensure_module(dep, frozenset())
            if dep_ns is not None:
                env0 = _worker_vm.call("绑定环境", env0, dep, dep_ns)
        _worker_vm.call("执行语句", prog, env0)
        b_outs = list(_worker_vm.call("输出快照"))
    except Exception as e:
        b_err = f"{type(e).__name__}: {e}"[:_ERR_TRUNC]
    h_outs = h_err = None
    try:
        from src import interp as host_interp
        h_outs, _trace = host_interp.interpret(src)
    except Exception as e:
        h_err = f"{type(e).__name__}: {e}"[:_ERR_TRUNC]
    entry["boot"] = "ok" if b_err is None else "err"
    entry["host"] = "ok" if h_err is None else "err"
    if b_err is not None:
        entry["boot_err"] = b_err
    if h_err is not None:
        entry["host_err"] = h_err
    if b_err is None and h_err is None:
        equal = _norm(b_outs) == _norm(h_outs)
        entry["equal"] = equal
        if not equal:
            entry["first_div"] = _first_div(b_outs, h_outs)
            entry["n_boot_outs"] = len(b_outs)
            entry["n_host_outs"] = len(h_outs)
        elif b_outs:
            entry["n_outs"] = len(b_outs)
    return entry


def _classify(entry: dict) -> str:
    if entry.get("boot") == "timeout" or entry.get("host") == "timeout":
        return "timeout"
    b, h = entry.get("boot"), entry.get("host")
    if b == "ok" and h == "ok":
        return "both_ok_equal" if entry.get("equal") else "both_ok_differ"
    if b == "err" and h == "err":
        return "both_err"
    if b == "err":
        return "boot_err_host_ok"
    if h == "err":
        return "boot_ok_host_err"
    return "unknown"


# ---------------- sweep driver ----------------

def run_sweep(files: list[str], workers: int, timeout: float) -> list[dict]:
    results: dict[str, dict] = {}
    pending = list(files)
    rounds = 0
    while pending and rounds < 3:
        rounds += 1
        ctx = mp.get_context("spawn")
        pool = ctx.Pool(processes=workers, initializer=_worker_init)
        try:
            # 31g：warmup barrier——worker init（boot 链编译）移出单文件 get
            # 预算：首批 apply_async 的 get(timeout) 会在 init 期间到期而把
            # 文件误记 timeout（30f 快照 timeout 2 即此竞态伪影——
            # matha/interp.matha 自测块仅数语句，真重档只有 stdlib_symbols
            # 数据初始化面）。warmup 超时 = 池初始化失败，如实整轮 timeout。
            try:
                pool.map_async(_warm, range(workers * 2)).get(
                    timeout=_WARMUP_TIMEOUT)
            except mp.TimeoutError:
                break
            asyncs = [(rel, pool.apply_async(_run_one, (rel,))) for rel in pending]
            uncollected = []
            for rel, a in asyncs:
                try:
                    results[rel] = a.get(timeout=timeout)
                except mp.TimeoutError:
                    uncollected.append(rel)
            pending = [rel for rel in uncollected if rel not in results]
        finally:
            pool.terminate()
            pool.join()
    for rel in pending:
        results[rel] = {"path": rel, "boot": "timeout", "host": "timeout"}
    return [results[rel] for rel in files]


def summarize(entries: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for e in entries:
        c = _classify(e)
        counts[c] = counts.get(c, 0) + 1
    summary = {"files": len(entries)}
    for key in ("both_ok_equal", "both_ok_differ", "boot_err_host_ok",
                "boot_ok_host_err", "both_err", "timeout"):
        summary[key] = counts.get(key, 0)
    return summary


def build_snapshot(files, entries) -> dict:
    # 条目按 corpus_files 枚举序输出（目录分组序）——与 structure_check 的
    # 文件清单逐位对拍同源；worker 完成序不稳定，全局字母序与枚举序不一致。
    by = {e["path"]: e for e in entries}
    return {
        "version": 1,
        "corpus_dirs": list(CORPUS_DIRS),
        "boot_files": list(BOOT_FILES),
        "summary": summarize(entries),
        "files": [by[rel] for rel in files],
        "enumerated": len(files),
    }


def write_snapshot(args) -> int:
    files = corpus_files(args.filter, args.limit)
    print(f"[selfhost_matrix] 语料 {len(files)} 文件，workers={args.workers} "
          f"timeout={args.timeout}s")
    entries = run_sweep(files, args.workers, args.timeout)
    snap = build_snapshot(files, entries)
    print("[selfhost_matrix] 汇总:", json.dumps(snap["summary"], ensure_ascii=False))
    differs = [e for e in snap["files"] if _classify(e) == "both_ok_differ"]
    for e in differs[:20]:
        print(f"  [differ] {e['path']} first_div={e.get('first_div')} "
              f"n_boot={e.get('n_boot_outs')} n_host={e.get('n_host_outs')}")
    errs = [e for e in snap["files"] if _classify(e).endswith("host_ok")]
    for e in errs[:10]:
        print(f"  [boot_err] {e['path']} {e.get('boot_err')}")
    if args.filter or args.limit:
        print("[selfhost_matrix] 子集试跑（--filter/--limit）：不写快照")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"[selfhost_matrix] 快照写入 {SNAPSHOT}")
    return 0


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def check_snapshot(args) -> tuple[bool, str]:
    snap = load_snapshot()
    files = corpus_files(args.filter, args.limit)
    if args.filter or args.limit:
        return False, "--check 不支持 --filter/--limit（全量对拍口径）"
    if snap.get("enumerated") != len(files) or \
       [e["path"] for e in snap["files"]] != files:
        return False, "快照文件清单与当前语料枚举不一致（需 --write 重生成）"
    entries = run_sweep(files, args.workers, args.timeout)
    problems = []
    old_by = {e["path"]: e for e in snap["files"]}
    for e in entries:
        old = old_by.get(e["path"])
        if old is None:
            problems.append(f"{e['path']}: 快照缺条目")
            continue
        if _classify(old) != _classify(e):
            problems.append(f"{e['path']}: 分类漂移 {_classify(old)} -> {_classify(e)}")
        elif _classify(e) == "both_ok_differ":
            if old.get("first_div") != e.get("first_div"):
                problems.append(f"{e['path']}: 首分歧漂移 "
                                f"{old.get('first_div')} -> {e.get('first_div')}")
    new_summary = summarize(entries)
    if new_summary != snap["summary"]:
        problems.append(f"汇总漂移: {snap['summary']} -> {new_summary}")
    return (not problems), ("；".join(problems[:20]) if problems else "一致")


def structure_check() -> tuple[bool, str]:
    """快结构锁（pytest 门禁）：文件清单一致 + 汇总算术闭合 + 条目形态。"""
    if not SNAPSHOT.exists():
        return False, "快照缺失 docs/selfhost_matrix.json（先 --write）"
    snap = load_snapshot()
    files = corpus_files()
    if snap.get("enumerated") != len(files) or \
       [e["path"] for e in snap["files"]] != files:
        return False, "快照文件清单与当前语料枚举不一致（需 --write 重生成）"
    s = snap["summary"]
    total = (s["both_ok_equal"] + s["both_ok_differ"] + s["boot_err_host_ok"]
             + s["boot_ok_host_err"] + s["both_err"] + s["timeout"])
    if total != s["files"] or s["files"] != len(snap["files"]):
        return False, f"汇总算术不闭合: {s}"
    for e in snap["files"]:
        if _classify(e) == "unknown":
            return False, f"{e['path']}: 条目形态未知"
        if e["path"] in BOOT_FILES:
            return False, f"{e['path']}: boot 链文件不应入 sweep"
    return True, f"结构闭合 files={s['files']}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="29d 自举执行面全语料 sweep")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--structure", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="单文件双轨预算（31g 治理：120→600——boot 面柯里化递归"
                         "真慢档 golden 37/38 实测 ~65-300s 量级，120s 误记 timeout；"
                         "warmup 已把 worker init 移出预算）")
    ap.add_argument("--filter", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    if args.write:
        return write_snapshot(args)
    if args.check:
        ok, msg = check_snapshot(args)
        print(f"[selfhost_matrix --check] {'一致' if ok else '漂移'}: {msg}")
        return 0 if ok else 1
    ok, msg = structure_check()
    print(f"[selfhost_matrix --structure] {'闭合' if ok else '不闭合'}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
