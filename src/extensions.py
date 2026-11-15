# -*- coding: utf-8 -*-
"""统一扩展注册面（阶段 23d）。

把仓库既有的四个扩展面收进同一份枚举/启停协议：

  ============  ==========================================================
  kind          面                                                         
  ============  ==========================================================
  domain        领域插件（src/domains/manifest.json，懒加载，启停 =
                PluginResolver.unregister / reload 回位）
  feature       特性开关（src/features.DEFAULTS，启停 = set_feature 落地）
  package       用户扩展包（.matha_packages/<包>/；启停标记写进包自己的
                manifest.json "enabled" 字段，内核 use 回退面如实尊重）
  terminal      终端扩展（matha_term_extensions.msh 自启动 + 注册的 .msh
                扩展条目，启停 = extensions.json state）
  ============  ==========================================================

启停状态持久化在项目根 ``.matha/extensions.json``（protocol_version 1）::

    {"protocol_version": 1, "state": {"domain": {"quantum": false},
                                      "feature": {"SCOPED_BLOCKS": true},
                                      "terminal": {"my.msh": false}}}

缺省 = 全部启用（包面缺省看包自身 manifest，无 state 条目）。
宿主入口（matha_main run/eval/repl）在执行前调用 :func:`apply_state`
把状态真实落到各面——不做只摆设的开关。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

PROTOCOL_VERSION = 1
STATE_DIRNAME = ".matha"
STATE_FILENAME = "extensions.json"

TERMINAL_AUTORUN_FILE = "matha_term_extensions.msh"

#: 合法扩展种类（ext CLI 的 kind 实参校验）
KINDS = ("domain", "feature", "package", "terminal")


@dataclass(frozen=True)
class ExtensionInfo:
    """一条扩展的统一视图（版本/启停/来源三协议字段 + 展示补充）。"""
    kind: str
    name: str
    version: str
    source: str
    enabled: bool
    detail: str


# ============================================================
# 状态文件
# ============================================================

def state_path(root: str | Path | None = None) -> Path:
    base = Path(root) if root else Path.cwd()
    return base / STATE_DIRNAME / STATE_FILENAME


def load_state(root: str | Path | None = None) -> dict:
    """读取启停状态文件；不存在返回空 state，损坏如实上抛。"""
    p = state_path(root)
    if not p.exists():
        return {"protocol_version": PROTOCOL_VERSION, "state": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    version = int(data.get("protocol_version", 0))
    if version != PROTOCOL_VERSION:
        raise RuntimeError(
            f"extensions.json 协议版本 {version} != {PROTOCOL_VERSION}")
    state = data.get("state")
    if not isinstance(state, dict):
        raise RuntimeError("extensions.json 缺 state 对象")
    return data


def save_state(data: dict, root: str | Path | None = None) -> Path:
    p = state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    return p


def set_enabled(kind: str, name: str, enabled: bool,
                root: str | Path | None = None) -> dict:
    """记录一条启停覆盖（domain/feature/terminal 三面；package 面见
    :func:`set_package_enabled`——状态在包自己的 manifest.json）。"""
    if kind not in KINDS:
        raise ValueError(f"未知扩展种类 {kind!r}；可用：{', '.join(KINDS)}")
    if kind == "package":
        return set_package_enabled(name, enabled, root)
    data = load_state(root)
    data.setdefault("state", {}).setdefault(kind, {})[name] = bool(enabled)
    save_state(data, root)
    return data


def is_enabled(kind: str, name: str, root: str | Path | None = None) -> bool:
    """查一条启停覆盖；未记录 = 启用。"""
    data = load_state(root)
    entry = data.get("state", {}).get(kind, {})
    return bool(entry.get(name, True))


# ============================================================
# 各面枚举
# ============================================================

def _iter_domain(root) -> list[ExtensionInfo]:
    from src.plugin_api import get_resolver
    state = load_state(root).get("state", {}).get("domain", {})
    out = []
    for p in get_resolver().list_plugins():
        name = p["name"]
        out.append(ExtensionInfo(
            kind="domain", name=name, version="-",
            source=p["module"],
            enabled=bool(state.get(name, True)),
            detail=f"{p['display_name']} · {p['category']} · {p['symbols']} 符号"))
    return out


def _iter_feature(root) -> list[ExtensionInfo]:
    from src import features
    state = load_state(root).get("state", {}).get("feature", {})
    out = []
    for name, on in features.known_states().items():
        out.append(ExtensionInfo(
            kind="feature", name=name, version="-", source="builtin",
            enabled=bool(state.get(name, on)),
            detail="默认开启" if on else "默认关闭"))
    return out


def _iter_package(root) -> list[ExtensionInfo]:
    out = []
    seen_roots = []
    for base in (Path(root) if root else Path.cwd(),
                 Path(__file__).resolve().parent.parent):
        if base in seen_roots:
            continue
        seen_roots.append(base)
        packages = base / ".matha_packages"
        if not packages.is_dir():
            continue
        for pkg_dir in sorted(packages.iterdir()):
            manifest = pkg_dir / "manifest.json"
            if not pkg_dir.is_dir() or not manifest.exists():
                continue
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            name = meta.get("name") or pkg_dir.name
            out.append(ExtensionInfo(
                kind="package", name=name,
                version=str(meta.get("version", "-")),
                source=str(pkg_dir),
                enabled=meta.get("enabled") is not False,
                detail=f"入口 {meta.get('entry', '-')} · 依赖 "
                       f"{', '.join(meta.get('dependencies', [])) or '无'}"))
    return out


def _iter_terminal(root) -> list[ExtensionInfo]:
    base = Path(root) if root else Path.cwd()
    state = load_state(root).get("state", {}).get("terminal", {})
    out = []
    autorun = base / TERMINAL_AUTORUN_FILE
    if autorun.exists():
        out.append(ExtensionInfo(
            kind="terminal", name=TERMINAL_AUTORUN_FILE, version="-",
            source=str(autorun), enabled=bool(state.get(autorun.name, True)),
            detail="REPL 自启动脚本（12e）"))
    for name, on in sorted(state.items()):
        if name == TERMINAL_AUTORUN_FILE:
            continue
        out.append(ExtensionInfo(
            kind="terminal", name=name, version="-",
            source=str(base / name), enabled=bool(on),
            detail="注册的终端扩展（.msh）"))
    return out


def list_extensions(root: str | Path | None = None) -> list[ExtensionInfo]:
    """枚举全部四个扩展面（不加载任何领域模块、不执行任何扩展）。"""
    return (_iter_domain(root) + _iter_feature(root)
            + _iter_package(root) + _iter_terminal(root))


# ============================================================
# 用户扩展包安装/升级（真盘）
# ============================================================

def install_local(path: str | Path, root: str | Path | None = None) -> dict:
    """从本地目录安装用户 .matha 扩展包（复制 .matha 源文件进
    .matha_packages/<包>/ 并写 manifest.json）。

    目录须存在且含至少一个 .matha 文件；包名取包 manifest.json 的 "name"
    （缺省用目录名）；入口 = <包名>.matha（存在时）否则字典序首个 .matha。
    已安装的同名包会被覆盖（升级即重装同一路径）。
    """
    src = Path(path)
    if not src.is_dir():
        raise RuntimeError(f"扩展包目录不存在: {src}")
    matha_files = sorted(src.glob("*.matha"))
    if not matha_files:
        raise RuntimeError(f"扩展包目录没有 .matha 文件: {src}")

    src_manifest = src / "manifest.json"
    meta = {}
    if src_manifest.exists():
        meta = json.loads(src_manifest.read_text(encoding="utf-8"))
    name = str(meta.get("name") or src.name)
    version = str(meta.get("version") or "0.1.0")

    entry = f"{name}.matha"
    if not any(f.name == entry for f in matha_files):
        entry = matha_files[0].name

    base = Path(root) if root else Path.cwd()
    dest = base / ".matha_packages" / name
    dest.mkdir(parents=True, exist_ok=True)
    for f in matha_files:
        shutil.copy2(f, dest / f.name)

    manifest = {
        "name": name,
        "version": version,
        "entry": entry,
        "dependencies": list(meta.get("dependencies", [])),
        "enabled": True,
        "source": str(src.resolve()),
        "installed_at": meta.get("installed_at") or _now(),
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return manifest


def _now() -> float:
    import time
    return time.time()


def install_registry(spec: str, root: str | Path | None = None) -> list[str]:
    """按内置注册表安装（沿用 pkg_manager 真机制：查注册表 → 写盘 manifest）。"""
    from src.pkg_manager import MathaPackage
    mgr = MathaPackage(str(root) if root else None)
    return mgr.install(spec)


def set_package_enabled(name: str, enabled: bool,
                        root: str | Path | None = None) -> dict:
    """扩展包启停：写进包自己的 manifest.json "enabled" 字段（内核 use
    回退面与 ext list 都读它——单一事实源）。"""
    manifest = _package_manifest_path(name, root)
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    meta["enabled"] = bool(enabled)
    manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return meta


def upgrade_package(name: str, root: str | Path | None = None) -> list[str]:
    """升级一个扩展包。

    本地目录包（manifest 带 "source"）→ 从记录的源路径重装（真盘覆盖）；
    注册表包 → pkg_manager_v2.upgrade_package（沿用 os 域 升级包 同机制，
    先还原本地安装集合）。无可用更新时 RuntimeError 如实拒绝。
    """
    manifest = _package_manifest_path(name, root)
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    source = meta.get("source")
    if source:
        old = meta.get("version", "-")
        fresh = install_local(source, root)
        if str(fresh["version"]) == str(old):
            return [name, str(old), str(old), "已最新（源目录版本未变）"]
        return [name, str(old), str(fresh["version"]), "本地源重装"]
    from src.pkg_manager_v2 import MathaPackageManager
    from src.domains.os_module import _restore_installed
    mgr = MathaPackageManager(str(root) if root else None)
    _restore_installed(mgr)
    result = mgr.upgrade_package(name)
    if not result:
        raise RuntimeError(f"升级包: 无可用更新: {name}（未安装或已最新）")
    return result[0].split(" ")


def _package_manifest_path(name: str, root) -> Path:
    for base in (Path(root) if root else Path.cwd(),
                 Path(__file__).resolve().parent.parent):
        manifest = base / ".matha_packages" / name / "manifest.json"
        if manifest.exists():
            return manifest
    raise RuntimeError(f"未安装的扩展包: {name}")


# ============================================================
# 宿主落地：把状态真实应用到各面
# ============================================================

def apply_state(root: str | Path | None = None) -> dict:
    """宿主入口在 run/eval/repl 前调用：状态文件存在才生效（零文件 = 零开销）。

    - feature：逐条 features.set_feature（进程内覆盖，优先级最高）
    - domain：禁用的从 PluginResolver 注销；显式启用的经 reload() 从清单回位
    - package / terminal：不需要进程内落地（use 回退面读包 manifest；
      终端自启动读 state 文件本身）
    返回落地面摘要（供诊断打印）。
    """
    p = state_path(root)
    if not p.exists():
        return {}
    data = load_state(root)
    state = data.get("state", {})
    applied: dict[str, list] = {}

    from src import features
    for name, on in state.get("feature", {}).items():
        features.set_feature(name, bool(on))
        applied.setdefault("feature", []).append(f"{name}={'on' if on else 'off'}")

    domains = state.get("domain", {})
    if domains:
        from src.plugin_api import get_resolver
        resolver = get_resolver()
        changed = []
        for name, on in domains.items():
            canonical = resolver.normalize(str(name))
            if on:
                # 已被 unregister 的名字在别名索引里不存在 → 先回位再校验
                if canonical is None or resolver.plugin(canonical) is None:
                    resolver.reload()
                    canonical = resolver.normalize(str(name))
                    if canonical is None:
                        raise RuntimeError(f"未知领域插件: {name}")
                    changed.append(f"{canonical}=回位")
            else:
                if canonical is None:
                    # 别名索引查不到 = 已停用，或从未存在——查清单甄别，
                    # 已停用态不重复动作（幂等），从未存在诚实拒绝
                    if not _manifest_has_plugin(str(name)):
                        raise RuntimeError(f"未知领域插件: {name}")
                    continue
                if resolver.unregister(canonical):
                    changed.append(f"{canonical}=停用")
        if changed:
            applied["domain"] = changed
    return applied


def _manifest_has_plugin(name: str) -> bool:
    """名字（或别名）是否出现在领域清单里（只读 JSON，不 import 模块）。"""
    from src.plugin_api import MANIFEST_PATH
    path = Path(MANIFEST_PATH)
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    for spec in payload.get("plugins", []):
        if name == spec.get("name") or name in spec.get("aliases", []):
            return True
    return False


__all__ = [
    "PROTOCOL_VERSION", "KINDS", "ExtensionInfo",
    "state_path", "load_state", "save_state",
    "set_enabled", "is_enabled", "set_package_enabled",
    "list_extensions", "apply_state",
    "install_local", "install_registry", "upgrade_package",
]
