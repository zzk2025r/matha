# -*- coding: utf-8 -*-
"""生成插件清单 ``src/domains/manifest.json``（开发期工具，不属于运行时）。

为什么需要它
------------
核心主线要求「内核不 import 任何领域模块」，但语义分析（``src/semantic.py``）
和懒加载解析器（``src/plugin_api.PluginResolver``）都需要知道「哪个符号属于哪个
领域」。若为此去 import 领域模块，耦合又回来了。因此把答案固化成 **纯数据清单**：
本脚本在开发期把每个领域的 ``_register_*`` 钩子跑一遍，记录其导出的符号名，
运行时只读 JSON，不读代码。

清单同时冻结 **加载顺序**：沿用旧 ``src/interp.py`` eager 注册顺序，使跨领域重名
符号的「后注册覆盖前注册」行为在插件化之后保持逐字节一致（由
``PluginResolver.materialize_for`` 按清单顺序物化实现）。

用法
----
    python scripts/gen_domain_manifest.py            # 生成 / 覆盖
    python scripts/gen_domain_manifest.py --check    # 只校验现有清单是否过期

``--check`` 供 ``make check`` 使用：领域模块改了符号却没重生成清单时立即失败。
"""
from __future__ import annotations

import argparse
import datetime
import importlib
import inspect
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MANIFEST_PATH = ROOT / "src" / "domains" / "manifest.json"
DOMAINS_DIR = ROOT / "src" / "domains"
PROTOCOL_VERSION = 1

# 旧 src/interp.py::_build_domain_builtins 的注册顺序（重名符号的覆盖次序以此为准）。
# 删除 eager 注册时必须保留这份顺序，否则跨领域重名符号的取值会发生静默漂移。
LEGACY_REGISTER_ORDER: list[tuple[str, str]] = [
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
    ("src.domains.chemistry", "_register_chemistry"),
    ("src.domains.computer_science", "_register_computer_science"),
    ("src.domains.electrical", "_register_electrical"),
    ("src.domains.economics", "_register_economics"),
    ("src.domains.ai_data_science", "_register_ai_data_science"),
    ("src.domains.game_dev", "_register_game_dev"),
    ("src.domains.quantum_compute", "_register_quantum_compute"),
    ("src.domains.chaos_fractal", "_register_chaos_fractal"),
    ("src.domains.genetic_algo", "_register_genetic_algo"),
    ("src.domains.creative_coding", "_register_creative_coding"),
    ("src.domains.blockchain", "_register_blockchain"),
    ("src.domains.software_app", "_register_software_app"),
    ("src.domains.automation", "_register_automation"),
    ("src.domains.iot_hardware", "_register_iot_hardware"),
    ("src.domains.os_network", "_register_os_network"),
    ("src.domains.audio_video", "_register_av"),
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
    ("src.domains.geospatial", "_register_geo"),
    ("src.domains.astronomy", "_register_astro"),
    ("src.domains.music", "_register_music"),
    ("src.domains.robotics", "_register_robot"),
    ("src.domains.graph", "_register_graph"),
]


def _domain_modules() -> list[str]:
    """src/domains 下全部可作插件的模块名（排除包初始化与注册中心）。"""
    skip = {"__init__.py", "registry.py"}
    out = []
    for p in sorted(DOMAINS_DIR.glob("*.py")):
        if p.name in skip:
            continue
        out.append(f"src.domains.{p.stem}")
    return out


def _registry_meta() -> dict[str, dict]:
    """从 DomainRegistry._DOMAIN_TEMPLATES 取 display_name / category（按模块路径索引）。"""
    try:
        from src.domains.registry import DomainRegistry
    except Exception:
        return {}
    by_module: dict[str, dict] = {}
    for key, tpl in DomainRegistry._DOMAIN_TEMPLATES.items():
        mod = tpl.get("module", "")
        by_module.setdefault(mod, {}).update({
            "registry_key": key,
            "display_name": tpl.get("display_name", ""),
            "category": tpl.get("category", "general"),
            "description": tpl.get("description", ""),
        })
    return by_module


def _cn_name(mod) -> str:
    """从模块 docstring 首行取中文领域名（供 `@：【加载领域】，机械设计` 一类写法使用）。

    约定形式：`Matha 领域扩展模块：机械设计（Mechanical Design）。`；取「：」后、
    「（」/「。」/ 行尾 之前的片段。取不到则返回空串（此时只以模块名为别名）。
    """
    doc = inspect.getdoc(mod) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    for sep in ("：", ":"):
        if sep in first:
            tail = first.split(sep, 1)[1].strip()
            for stop in ("（", "(", "。", ",", "，", " "):
                if stop in tail:
                    tail = tail.split(stop, 1)[0]
            tail = tail.strip()
            if tail and any("\u4e00" <= ch <= "\u9fff" for ch in tail):
                return tail
    return ""


def _discover_hooks(mod) -> list[str]:
    """模块内所有「单参 dict」形态的 ``_register_*`` 钩子。"""
    names = [a for a in dir(mod) if a.startswith("_register_")]
    out = []
    for n in sorted(names):
        fn = getattr(mod, n, None)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        positional = [p for p in sig.parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(positional) == 1:
            out.append(n)
    return out


def _symbol_names(mod, hooks: list[str]) -> tuple[list[str], list[str]]:
    """跑一遍钩子收集导出符号，返回 (实际注册名, 仅声明名)。

    第一个列表是「可加载的真实符号」（_register_* 跑出来的）；第二个额外包含部分
    领域提供的 `*_symtab_names` 声明名（只供语义分析知道「这个名字属于本领域」，
    并不保证已注册）。两者必须分开：把仅声明名当作可加载符号，会让「未加载领域」
    诊断报出实际取不到的符号。
    """
    registered: list[str] = []
    for h in hooks:
        table: dict = {}
        try:
            getattr(mod, h)(table)
        except Exception as e:
            print(f"  ! {mod}.{h}() 执行失败：{type(e).__name__}: {e}")
            continue
        for k in table:
            if k not in registered:
                registered.append(k)
    declared: list[str] = []
    # 补充声明式符号表（部分领域提供 _xxx_symtab_names，可能含未注册名）
    for attr in dir(mod):
        if attr.endswith("_symtab_names") or attr == "kernel_symtab_names":
            fn = getattr(mod, attr, None)
            if callable(fn):
                try:
                    for k in fn() or []:
                        if isinstance(k, str) and k not in registered and k not in declared:
                            declared.append(k)
                except TypeError:
                    continue
                except Exception:
                    continue
    return registered, declared


def build_manifest() -> dict:
    ordered: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for mod_path, hook in LEGACY_REGISTER_ORDER:
        if mod_path not in seen:
            seen.add(mod_path)
            ordered.append((mod_path, [hook]))
    all_modules = _domain_modules()
    for mod_path in all_modules:
        if mod_path not in seen:
            seen.add(mod_path)
            ordered.append((mod_path, []))

    meta_by_module = _registry_meta()
    legacy_modules = {m for m, _ in LEGACY_REGISTER_ORDER}
    plugins: list[dict] = []
    failures: list[str] = []

    for mod_path, hinted_hooks in ordered:
        if mod_path not in all_modules:
            failures.append(f"{mod_path}: 文件不存在")
            continue
        try:
            mod = importlib.import_module(mod_path)
        except Exception as e:
            failures.append(f"{mod_path}: import {type(e).__name__}: {e}")
            continue
        discovered = _discover_hooks(mod)
        hooks = [h for h in hinted_hooks if h in discovered] or discovered
        if not hooks:
            failures.append(f"{mod_path}: 无 _register_* 钩子（不作为插件导出符号）")
        symbols = _symbol_names(mod, hooks) if hooks else ([], [])
        registered, declared = symbols
        info = meta_by_module.get(mod_path, {})
        stem = mod_path.rsplit(".", 1)[-1]
        cn = _cn_name(mod)
        aliases = [stem]
        for key in ("registry_key", "display_name"):
            v = info.get(key, "")
            if v and v not in aliases:
                aliases.append(v)
        if cn and cn not in aliases:
            aliases.append(cn)
        display = info.get("display_name", "") or ""
        if not display or display == stem:
            display = cn or display or stem
        plugins.append({
            "name": stem,
            "module": mod_path,
            "display_name": display,
            "cn_name": cn,
            "category": info.get("category", "general"),
            "description": info.get("description", ""),
            "aliases": aliases,
            "registers": hooks,
            "symbols": sorted(registered),
            # 仅声明、未注册的名字：语义分析可用，但不得当作可加载符号
            "declared_symbols": sorted(declared),
            # 旧 interp eager 注册过的模块：其符号是已有语义，插件化后必须逐字节
            # 保持旧覆盖规则；仅新纳入的模块不得反过来遮蔽旧模块的同名符号。
            "legacy": mod_path in legacy_modules,
        })

    return {
        "_comment": (
            "Matha 领域插件清单 —— 纯数据，由 scripts/gen_domain_manifest.py 生成，"
            "请勿手改。运行时 src/plugin_api.PluginResolver 只读此文件即可完成符号→"
            "插件的归属判定，从而不在启动时 import 任何领域模块。plugins 数组的顺序"
            "即加载顺序（沿用旧 interp eager 注册顺序），跨领域重名符号按后者覆盖。"
        ),
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "generator": "scripts/gen_domain_manifest.py",
        "plugins": plugins,
        "unavailable": sorted(failures),
    }


def _strip_volatile(payload: dict) -> dict:
    """比对时忽略时间戳等易变字段。"""
    return {k: v for k, v in payload.items() if k not in ("generated_at",)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="只校验现有清单是否与代码一致，不写文件")
    ap.add_argument("--out", default=str(MANIFEST_PATH))
    args = ap.parse_args()

    fresh = build_manifest()
    out_path = pathlib.Path(args.out)
    n_sym = sum(len(p["symbols"]) for p in fresh["plugins"])
    n_dec = sum(len(p["declared_symbols"]) for p in fresh["plugins"])
    print(f"插件 {len(fresh['plugins'])} 个 | 可加载符号 {n_sym} 个 | "
          f"仅声明符号 {n_dec} 个 | 不可用 {len(fresh['unavailable'])} 个")
    for f in fresh["unavailable"]:
        print(f"  - {f}")

    if args.check:
        if not out_path.exists():
            print(f"[FAIL] 清单缺失：{out_path}")
            return 1
        current = json.loads(out_path.read_text(encoding="utf-8"))
        if _strip_volatile(current) != _strip_volatile(fresh):
            print(f"[FAIL] 清单已过期，请运行：python scripts/gen_domain_manifest.py")
            return 1
        print("[OK] 清单与代码一致")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"已写入 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
