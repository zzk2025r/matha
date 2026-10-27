"""Matha 插件契约 —— 联邦式架构的唯一边界协议。

架构定位（阶段 1 建立）：

    核心主线（内核）  lexer -> parser -> ast_nodes -> mbc.compiler -> mbc.vm
                                                    \\-> mbc.native
    插件支线（联邦）  src.domains.* / src.plugins.*  —— 81 个领域模块

两侧只通过本模块通信。契约的强制性由两处保证：

  1. ``PluginContext`` 在构造时 **不持有任何 VM / 解释器引用**，插件因此物理上
     拿不到 ``vm.frames`` / ``vm.globals`` / ``_stack`` 等私有成员；能做的只有
     登记符号、登记公式、回报诊断。
  2. ``scripts/dep_audit.py`` + ``tests/test_kernel_purity.py`` 做静态双向守卫：
     内核不得 import 插件层；插件层不得 ``from src.<核心模块> import _私有名``。

插件的懒加载由 ``PluginResolver`` 负责：它只读 ``src/domains/manifest.json``
（纯数据，不含代码）就能回答「哪个符号属于哪个插件」，只有真正取用符号时才
``importlib`` 对应模块。因此「未加载即引用」不再产生任何 import 成本，也取代
了原先 ``src/interp.py`` 一次性 eager import 40+ 领域模块的做法。

现有 81 个模块的 ``_register_xxx(builtins: dict)`` 签名由 ``LegacyModulePlugin``
适配层统一包装为 ``exports()``，零改写接入。
"""
from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from types import MappingProxyType
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

PROTOCOL_VERSION = 1

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "domains" / "manifest.json"

# 诊断级别（插件只允许报这三类，不允许直接 print/raise 逃逸）
LEVEL_INFO = "info"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"


# ============================================================
# 诊断
# ============================================================

@dataclass(frozen=True)
class PluginDiagnostic:
    """插件在加载 / 登记过程中产出的结构化诊断。"""

    level: str
    message: str
    plugin: str = ""
    symbol: str = ""

    def format(self) -> str:
        loc = f"[{self.plugin}" + (f":{self.symbol}]" if self.symbol else "]")
        return f"{self.level.upper():7s} {loc} {self.message}"


# ============================================================
# 插件上下文：插件能看到的唯一世界
# ============================================================

class PluginContext:
    """传给插件 ``on_load`` 的上下文，只暴露公开方法。

    设计红线：本类 **不接收也不保存** VM / Interpreter 实例。任何「插件需要读
    栈 / 读全局表」的需求都属于契约误用，应改为让插件把符号登记进来、由核心
    主线在调用点求值。
    """

    def __init__(self, plugin_name: str, *, strict: bool = True) -> None:
        self._plugin = plugin_name
        self._strict = strict
        self._builtins: dict[str, Any] = {}
        self._arities: dict[str, int] = {}
        self._formulas: dict[str, Any] = {}
        self._diagnostics: list[PluginDiagnostic] = []

    # ---- 只读视图 ----
    @property
    def plugin_name(self) -> str:
        return self._plugin

    @property
    def builtins(self) -> Mapping[str, Any]:
        """已登记符号的只读视图（写入口只有 ``register_builtin``）。"""
        return MappingProxyType(self._builtins)

    @property
    def arities(self) -> Mapping[str, int]:
        return MappingProxyType(self._arities)

    @property
    def formulas(self) -> Mapping[str, Any]:
        return MappingProxyType(self._formulas)

    @property
    def diagnostics(self) -> tuple[PluginDiagnostic, ...]:
        return tuple(self._diagnostics)

    # ---- 公开登记接口 ----
    def register_builtin(
        self,
        name: str,
        fn: Any,
        *,
        arity: int | None = None,
        override: bool = False,
    ) -> bool:
        """登记一个内建符号。返回是否写入。

        值可以是函数，也可以是常量表（旧 eager 注册就是 `builtins.update(table)`，
        领域模块大量导出 `公差系数_IT*`、单位表这类非调用值），因此不得要求 callable。
        名字必须是非空字符串；``override=False`` 时重复登记会被拒绝并产生 warning
        诊断（而不是静默覆盖），便于发现跨领域的重名冲突。
        """
        if not isinstance(name, str) or not name:
            self.emit_diagnostic(LEVEL_ERROR, "符号名非法", symbol=str(name))
            return False
        if name in self._builtins and not override:
            self.emit_diagnostic(LEVEL_WARNING, f"符号重名，保留首个登记：{name}", symbol=name)
            return False
        self._builtins[name] = fn
        if arity is not None:
            self._arities[name] = int(arity)
        return True

    def register_formula(self, name: str, spec: Any) -> bool:
        """登记一个公式模式（供 formula_schema / 公式库使用）。"""
        if not isinstance(name, str) or not name:
            return False
        self._formulas[name] = spec
        return True

    def emit_diagnostic(self, level: str, message: str, *, symbol: str = "") -> None:
        """回报一条诊断；诊断被收集而非打印，由宿主决定如何呈现。"""
        self._diagnostics.append(PluginDiagnostic(
            level=level, message=str(message), plugin=self._plugin, symbol=symbol))

    # ---- 内部：仅供 PluginResolver 使用，不对插件暴露 ----
    def _materialized(self) -> dict[str, Any]:
        return self._builtins


# ============================================================
# 插件协议
# ============================================================

@runtime_checkable
class MathaPlugin(Protocol):
    """联邦插件协议（冻结版本 PROTOCOL_VERSION）。"""

    @property
    def name(self) -> str: ...

    def exports(self) -> dict[str, Any]: ...

    @property
    def arities(self) -> dict[str, int]: ...

    def on_load(self, ctx: PluginContext) -> None: ...


# ============================================================
# 适配层：把 81 个既有领域模块零改写接入协议
# ============================================================

@dataclass
class LegacyModulePlugin:
    """适配 ``def _register_xxx(builtins: dict)`` 风格的既有领域模块。

    由 manifest 条目构造，不要求领域模块做任何改动：

        LegacyModulePlugin.from_spec({
            "name": "mechanics", "module": "src.domains.mechanics",
            "registers": ["_register_mechanics"], "symbols": [...],
        })

    ``registers`` 为 None 时在首次加载后按 ``_register_*`` 名称自动发现（兜底），
    但 manifest 由 ``scripts/gen_domain_manifest.py`` 生成时会写死确切钩子名，
    使运行时不需要 ``dir()`` 扫描。
    """

    name: str
    module: str
    registers: tuple[str, ...] = ()
    display_name: str = ""
    category: str = "general"
    symbols: tuple[str, ...] = ()
    #: 仅声明未注册的名字（*_symtab_names 给出）：语义分析可用，不得当作可加载符号
    declared_symbols: tuple[str, ...] = ()
    arities: dict[str, int] = field(default_factory=dict)
    description: str = ""
    aliases: tuple[str, ...] = ()
    legacy: bool = False

    @classmethod
    def from_spec(cls, spec: dict) -> "LegacyModulePlugin":
        regs = spec.get("registers") or ()
        if isinstance(regs, str):
            regs = (regs,)
        stem = spec["module"].rsplit(".", 1)[-1]
        aliases = tuple(spec.get("aliases") or ()) or (stem,)
        if spec["name"] not in aliases:
            aliases = (spec["name"],) + aliases
        return cls(
            name=spec["name"],
            module=spec["module"],
            registers=tuple(regs),
            display_name=spec.get("display_name", "") or stem,
            category=spec.get("category", "general"),
            symbols=tuple(spec.get("symbols") or ()),
            declared_symbols=tuple(spec.get("declared_symbols") or ()),
            arities=dict(spec.get("arities") or {}),
            description=spec.get("description", ""),
            aliases=aliases,
            legacy=bool(spec.get("legacy", False)),
        )

    # ---- 协议实现 ----
    def load_module(self) -> Any:
        return importlib.import_module(self.module)

    def _hook_names(self, mod: Any) -> tuple[str, ...]:
        if self.registers:
            return tuple(h for h in self.registers if callable(getattr(mod, h, None)))
        # 兜底发现：单钩子或名称与插件同名的钩子
        found = tuple(a for a in dir(mod)
                      if a.startswith("_register_") and callable(getattr(mod, a, None)))
        want = self.name.replace("_", "").lower()
        exact = tuple(h for h in found if h[len("_register_"):].lower() == want)
        return exact or (found if len(found) == 1 else ())

    def collect(self, ctx: PluginContext) -> None:
        """执行领域模块的登记钩子，把结果写入 ctx。"""
        try:
            mod = self.load_module()
        except Exception as e:  # 插件加载失败不得拖垮核心
            ctx.emit_diagnostic(LEVEL_ERROR, f"模块导入失败：{type(e).__name__}: {e}")
            return
        hooks = self._hook_names(mod)
        if not hooks:
            ctx.emit_diagnostic(LEVEL_WARNING, "模块未提供任何 _register_* 钩子")
            return
        # 旧 eager 注册时会逐模块扫描公式能力并标注元数据（src.formula_system）。
        # 插件化后该副作用必须在「真正加载那一刻」保留，否则能力表会静默缺项。
        self._scan_capabilities(mod, ctx)
        for hook in hooks:
            table: dict[str, Any] = {}
            try:
                getattr(mod, hook)(table)
            except Exception as e:
                ctx.emit_diagnostic(
                    LEVEL_ERROR, f"{hook}() 执行失败：{type(e).__name__}: {e}")
                continue
            for sym, val in table.items():
                ctx.register_builtin(
                    sym, val, arity=self.arities.get(sym), override=True)

    def exports(self) -> dict[str, Any]:
        ctx = PluginContext(self.name)
        self.collect(ctx)
        return dict(ctx.builtins)

    @staticmethod
    def _scan_capabilities(mod: Any, ctx: PluginContext) -> None:
        try:
            from src.formula_system import scan_module_capabilities
        except Exception:
            return
        try:
            scan_module_capabilities(mod)
        except Exception as e:
            ctx.emit_diagnostic(
                LEVEL_INFO, f"能力扫描跳过：{type(e).__name__}: {e}")

    @property
    def arities_declared(self) -> dict[str, int]:
        return dict(self.arities)

    def on_load(self, ctx: PluginContext) -> None:
        self.collect(ctx)


# ============================================================
# 懒解析器
# ============================================================

class PluginResolver:
    """清单驱动的插件懒解析器。

    只有 manifest 数据在初始化时被读入；模块 import 一律推迟到符号真正被取用
    （``resolve_into`` / ``require`` / ``materialize``）那一刻。
    """

    def __init__(self, manifest_path: Path | str = MANIFEST_PATH) -> None:
        self._manifest_path = Path(manifest_path)
        self._plugins: dict[str, LegacyModulePlugin] = {}
        self._order: list[str] = []
        self._alias_index: dict[str, str] = {}
        self._legacy: dict[str, bool] = {}
        # symbol -> 按清单顺序声明它的插件名列表。清单顺序沿用旧 eager 注册顺序，
        # 因此「最后一个」即旧语义下覆盖生效的那个，行为保持一致。
        self._symbol_owners: dict[str, list[str]] = {}
        # 同上，但只含「真正注册出来」的符号（钩子产出）。编译期「未加载领域」
        # 诊断必须用它，否则仅声明名会报出一个加载后仍取不到的符号。
        self._exported_owners: dict[str, list[str]] = {}
        self._contexts: dict[str, PluginContext] = {}
        self._load_errors: list[PluginDiagnostic] = []
        self._load_manifest()

    # ---- 清单 ----
    def _load_manifest(self) -> None:
        if not self._manifest_path.exists():
            self._load_errors.append(PluginDiagnostic(
                LEVEL_WARNING,
                f"插件清单缺失：{self._manifest_path}；"
                f"请运行 python scripts/gen_domain_manifest.py",
                plugin="resolver"))
            return
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self._load_errors.append(PluginDiagnostic(
                LEVEL_ERROR, f"插件清单无法解析：{e}", plugin="resolver"))
            return
        if int(payload.get("protocol_version", 0)) != PROTOCOL_VERSION:
            self._load_errors.append(PluginDiagnostic(
                LEVEL_WARNING,
                f"清单协议版本 {payload.get('protocol_version')} != {PROTOCOL_VERSION}，"
                f"建议重新生成", plugin="resolver"))
        for spec in payload.get("plugins", []):
            try:
                plugin = LegacyModulePlugin.from_spec(spec)
            except KeyError:
                self._load_errors.append(PluginDiagnostic(
                    LEVEL_ERROR, f"清单条目缺少 name/module 字段：{spec}"))
                continue
            self.register(plugin)

    # ---- 注册与查询（不触发 import）----
    def register(self, plugin: LegacyModulePlugin) -> None:
        if plugin.name in self._plugins:
            return
        self._plugins[plugin.name] = plugin
        self._order.append(plugin.name)
        self._legacy[plugin.name] = plugin.legacy
        self._alias_index.setdefault(plugin.name, plugin.name)
        for alias in plugin.aliases:
            self._alias_index.setdefault(alias, plugin.name)
        for sym in plugin.symbols:
            owners = self._symbol_owners.setdefault(sym, [])
            if plugin.name not in owners:
                owners.append(plugin.name)
            exported = self._exported_owners.setdefault(sym, [])
            if plugin.name not in exported:
                exported.append(plugin.name)
        for sym in plugin.declared_symbols:
            owners = self._symbol_owners.setdefault(sym, [])
            if plugin.name not in owners:
                owners.append(plugin.name)

    def unregister(self, name: str) -> bool:
        if name not in self._plugins:
            return False
        self._symbol_owners = {
            s: [o for o in owners if o != name] or []
            for s, owners in self._symbol_owners.items()
        }
        self._symbol_owners = {s: o for s, o in self._symbol_owners.items() if o}
        self._exported_owners = {
            s: [o for o in owners if o != name]
            for s, owners in self._exported_owners.items()
        }
        self._exported_owners = {s: o for s, o in self._exported_owners.items() if o}
        self._alias_index = {a: n for a, n in self._alias_index.items() if n != name}
        self._plugins.pop(name)
        self._order.remove(name)
        self._contexts.pop(name, None)
        return True

    def normalize(self, name: str) -> str | None:
        """把 插件名 / 模块名 / 注册中键 / 中文名 归一为插件唯一名。"""
        if name in self._plugins:
            return name
        return self._alias_index.get(name)

    def plugin(self, name: str) -> LegacyModulePlugin | None:
        return self._plugins.get(name)

    def names(self) -> list[str]:
        return list(self._order)

    def list_plugins(self) -> list[dict]:
        """供 ``matha --list-domains`` 使用：不加载任何模块即可枚举全部插件。"""
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "category": p.category,
                "module": p.module,
                "symbols": len(p.symbols),
                "loaded": p.name in self._contexts,
            }
            for p in (self._plugins[n] for n in self._order)
        ]

    def symbols_of(self, name: str) -> tuple[str, ...]:
        p = self._plugins.get(name)
        return p.symbols if p else ()

    def owner_of(self, symbol: str) -> str | None:
        """返回该符号的生效插件（清单中最后声明者，等同旧覆盖语义）。"""
        owners = self._symbol_owners.get(symbol)
        return owners[-1] if owners else None

    def owners_of(self, symbol: str) -> list[str]:
        """返回该符号的候选插件（按应物化顺序）。

        只要旧 eager 名单内的模块声明过该符号，就只在旧模块里取后者 —— 保证插
        件化后同名符号的取值与旧行为逐字一致，新纳入的模块不会静默遮蔽旧语义。
        """
        owners = list(self._symbol_owners.get(symbol, ()))
        legacy = [o for o in owners if self._legacy.get(o)]
        return legacy or owners

    def legacy_owners_of(self, symbol: str) -> list[str]:
        """仅旧 eager 名单内声明了该符号的插件（判定是否需保持旧覆盖行为）。"""
        return [o for o in self._symbol_owners.get(symbol, ()) if self._legacy.get(o)]

    def owns(self, symbol: str) -> bool:
        return symbol in self._symbol_owners

    def exports_symbol(self, symbol: str) -> bool:
        """该符号是否真的能被某个插件注册出来（而非仅出现在 symtab 声明里）。"""
        return symbol in self._exported_owners

    def exported_symbols(self) -> set[str]:
        return set(self._exported_owners)

    def candidates_for(self, symbol: str, limit: int = 5) -> list[str]:
        """返回声明了该符号的插件名（编译期「未加载领域」诊断用）。"""
        return self.owners_of(symbol)[:limit]

    def known_symbols(self) -> set[str]:
        return set(self._symbol_owners)

    def domain_alias_map(self) -> dict[str, str]:
        """别名（模块名 / 中文名 / registry_key）-> 插件唯一名，供加载指令归一。"""
        out: dict[str, str] = {}
        for name, plugin in self._plugins.items():
            out[name] = name
            out[plugin.module.rsplit(".", 1)[-1]] = name
            if plugin.display_name:
                out[plugin.display_name] = name
            for alias in plugin.aliases:
                out.setdefault(alias, name)
        return out

    def domain_symbol_index(self, exclude: Iterable[str] = ()) -> dict[str, list[str]]:
        """符号名 -> 归属插件名列表，供编译期「未加载领域」诊断使用。

        纯清单运算，不 import 任何领域模块。`exclude` 应传入内核已提供的符号
        （math/regex/time/file + VM 默认内建），否则 `tanh` 这类「插件恰好覆盖了
        内核同名符号」会在用户没写 `@：【加载领域】` 时被误判为不可用 —— 而它其实
        一直能取到内核版本。
        """
        skip = set(exclude)
        index: dict[str, list[str]] = {}
        for sym, owners in self._exported_owners.items():
            if sym in skip:
                continue
            legacy = [o for o in owners if self._legacy.get(o) and o not in skip]
            eff = legacy or [o for o in owners if o not in skip]
            if eff:
                index[sym] = eff
        return index

    # ---- 加载（唯一 import 点）----
    def materialize(self, name: str) -> dict[str, Any]:
        """加载插件并返回其符号表；重复调用返回缓存（不重复 import）。"""
        canonical = self.normalize(name)
        if canonical is None:
            return {}
        ctx = self._contexts.get(canonical)
        if ctx is not None:
            return ctx._materialized()
        plugin = self._plugins.get(canonical)
        if plugin is None:
            return {}
        ctx = PluginContext(canonical)
        plugin.on_load(ctx)
        self._contexts[canonical] = ctx
        self._load_errors.extend(ctx.diagnostics)
        table = ctx._materialized()
        # 清单与实际导出可能漂移（领域模块改了名），此处以实际为准补齐索引，
        # 并把差异记为诊断，避免「静默不一致」。
        for sym in plugin.symbols:
            if sym not in table:
                ctx.emit_diagnostic(
                    LEVEL_WARNING,
                    f"清单列出了 {sym}，但钩子实际未注册它（仅声明名）", symbol=sym)
        for sym in table:
            owners = self._symbol_owners.setdefault(sym, [])
            if canonical not in owners:
                owners.append(canonical)
                if len(owners) == 1:
                    ctx.emit_diagnostic(LEVEL_WARNING, f"清单缺少符号：{sym}", symbol=sym)
            exported = self._exported_owners.setdefault(sym, [])
            if canonical not in exported:
                exported.append(canonical)
        return table

    def materialize_all(self, target: MutableMapping) -> dict[str, Any]:
        """按清单顺序物化一切插件（供「需要完整内建表面」的工具使用）。"""
        merged: dict[str, Any] = {}
        for name in self._order:
            table = self.materialize(name)
            target.update(table)
            merged.update(table)
        return merged

    def resolve_into(self, target: MutableMapping, symbol: str) -> Any:
        """按符号名懒加载其所属插件，并把插件符号表写入 target，返回该符号值。

        同一符号可被多个插件声明（旧 eager 语义下后者覆盖前者），因此按清单
        顺序物化全部候选，取最后一个非空值。找不到归属时返回 None 且不产生
        任何 import。
        """
        owners = self.owners_of(symbol)
        if not owners:
            return None
        value = None
        for owner in owners:
            table = self.materialize(owner)
            target.update(table)
            if symbol in table:
                value = table[symbol]
        return value

    def require(self, name: str, target: MutableMapping) -> dict[str, Any]:
        """显式加载（对应 ``@：【加载领域】，<name>``）：只加载被点名的插件。"""
        canonical = self.normalize(name)
        if canonical is None:
            return {}
        table = self.materialize(canonical)
        target.update(table)
        return table

    def unknown(self, name: str) -> list[str]:
        """未加载诊断的候选提示：按名称近邻给出若干插件名。"""
        import difflib
        canon = self.normalize(name)
        if canon is not None:
            return [canon]
        pool = list(self._alias_index) + list(self._plugins)
        return sorted(set(difflib.get_close_matches(name, pool, n=5, cutoff=0.4)))

    def loaded(self) -> list[str]:
        return sorted(self._contexts)

    def diagnostics(self) -> list[PluginDiagnostic]:
        out = list(self._load_errors)
        for ctx in self._contexts.values():
            out.extend(ctx.diagnostics)
        return out


# ============================================================
# 懒内建表：把「内核 + 插件」折叠成一张对外行为与旧 eager 表一致的 dict
# ============================================================

class LazyBuiltinTable(dict):
    """按需拉取插件的内建表（取代旧 ``src/interp.py`` 的 eager 全量注册）。

    对使用方保持与普通 dict 完全一致的语义，区别仅在代价：

    * 名字类查询（``in`` / ``len`` / ``keys`` / ``iter``）只读清单，**不 import**；
    * 取值类查询（``[k]`` / ``get`` / ``items`` / ``values``）才物化相关插件；
    * 内核符号（math/regex/time/file）构造时已就位，永远不触发插件加载。

    因此只用到数学内建的程序仍然只加载内核，引用领域符号时才拉入对应那一个
    插件 —— 这正是验收标准「仅 ``matha eval "sin(pi)"`` 时 sys.modules 不出现
    任何领域模块」的实现基础。
    """

    def __init__(self, data=None, *, resolver: PluginResolver | None = None,
                 lazy: bool = True) -> None:
        super().__init__(data or {})
        self._resolver = resolver
        self._lazy = lazy and resolver is not None
        # 被旧 eager 领域模块覆盖过的名字：暂存在此，取值时先试插件，
        # 插件不可用则回退内核值（既保持旧语义，又不提前 import）。
        self._deferred: dict[str, Any] = {}

    @property
    def resolver(self) -> PluginResolver | None:
        return self._resolver

    def defer_to_plugins(self, names) -> int:
        """把 names 中「旧行为由领域插件覆盖内核」的条目转为懒解析。

        旧 ``src/interp.py`` 先注册内核内建、再用领域模块覆盖同名符号；完全懒化后
        若直接保留内核值，这些符号会错取内核版本。此处把它们从表中摘出、挂到
        ``_deferred``，首次取用时先走插件解析，插件未提供则自动回退。
        返回被转延迟的符号数。
        """
        if not self._lazy:
            return 0
        n = 0
        for name in names:
            if not self._resolver.legacy_owners_of(name):
                continue
            if not super().__contains__(name):
                continue
            self._deferred[name] = super().__getitem__(name)
            super().__delitem__(name)
            n += 1
        return n

    # ---- 取值：触发懒加载（dict.__getitem__ 会自动调到 __missing__）----
    def __missing__(self, key: str):
        if self._lazy and isinstance(key, str):
            value = self._resolver.resolve_into(self, key)
            if value is not None:
                return value
        if isinstance(key, str) and key in self._deferred:
            return self._deferred[key]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        self._materialize_known()
        return super().items()

    def materialized_items(self):
        """只返回已物化条目（不触发任何插件 import）。

        供「继承现有内建表但不想拉入全量领域」的调用点使用，如沙箱克隆。
        """
        return list(dict.items(self)) + [(k, v) for k, v in self._deferred.items()
                                        if not dict.__contains__(self, k)]

    def values(self):
        self._materialize_known()
        return super().values()

    def copy(self):
        return LazyBuiltinTable(dict(self.items()), resolver=self._resolver,
                                 lazy=self._lazy)

    # ---- 名字：不触发加载 ----
    def __contains__(self, key) -> bool:
        if super().__contains__(key) or (isinstance(key, str) and key in self._deferred):
            return True
        return bool(self._lazy) and self._resolver.exports_symbol(key)

    def __len__(self) -> int:
        return len(self._names())

    def __iter__(self):
        return iter(self._names())

    def keys(self):
        return frozenset(self._names())

    def _names(self) -> set:
        names = set(dict.keys(self)) | set(self._deferred)
        if self._lazy:
            # 只计可真正注册的符号：旧 eager 表里也没有「仅声明名」，多算会让
            # `x in builtins` 与旧行为不一致。
            names |= self._resolver.exported_symbols()
        return names

    def _materialize_known(self) -> None:
        """物化尚未来自插件的全部已知符号（仅在需要真实可调用对象时）。"""
        if self._lazy:
            pending = self._resolver.exported_symbols() - set(dict.keys(self))
            for sym in sorted(pending):
                self._resolver.resolve_into(self, sym)
        for sym, val in list(self._deferred.items()):
            if not super().__contains__(sym):
                self[sym] = val


# ============================================================
# 单例
# ============================================================

_resolver: PluginResolver | None = None


def get_resolver(reload: bool = False) -> PluginResolver:
    """全局插件解析器（进程内单例，清单只读一次）。"""
    global _resolver
    if _resolver is None or reload:
        _resolver = PluginResolver()
    return _resolver


__all__ = [
    "PROTOCOL_VERSION",
    "MANIFEST_PATH",
    "PluginDiagnostic",
    "PluginContext",
    "MathaPlugin",
    "LegacyModulePlugin",
    "PluginResolver",
    "LazyBuiltinTable",
    "get_resolver",
]
