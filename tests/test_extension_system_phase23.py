# -*- coding: utf-8 -*-
"""阶段 23 三锁：臃肿优化 + 解析缓存 + 统一扩展面。

拍板面（三件全选）：
  - 23a 内建惰性化：terminal/time/json 三节 LazyKernelFn（首调才 import，
    默认行为不变，`callable` 双面函数判定对 LazyKernelFn 天然成立）
  - 23b CLI 诚实化：features 单源 DEFAULTS/known_states（INLINE_CACHE 默认
    on 如实显示）；启动地板（python 启动 + stdlib + spawn）登记不修
  - 23c 解析缓存 opt-in：PARSE_CACHE 开关（默认关），键 = 源码 + 开关状态
    + 自定义运算符版本，LRU 上限 32；matha_main 简单命令收进命令表
  - 23d 统一扩展面：src/extensions.py 四面同一协议（domain/feature/package/
    terminal，版本/启停/来源），matha ext list/enable/disable/install/upgrade，
    启停真落地（resolver unregister/reload、set_feature、包 manifest 单一
    事实源、终端 autorun 条目），用户 .matha 扩展包 use 加载

- 对拍：扩展四面枚举形态 / 特性单源 / 缓存命中同对象
- 闭环：启停真化（feature 开关生效、domain 停用符号不可用、包 use 加载/
  禁用拒绝、终端条目执行/跳过）/ 安装升级真盘 / CLI smoke
- 边界：无状态文件零开销 / 未知域名诚实拒绝 / 协议版本校验 / LRU 驱逐 /
  matha/ 内置模块解析不受包回退影响 / 裸默认路径零缓存
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import custom_ops, features
from src.extensions import (KINDS, PROTOCOL_VERSION, ExtensionInfo,
                            apply_state, install_local, list_extensions,
                            load_state, set_enabled, set_package_enabled,
                            state_path)
from src.kernel import exec_api


@pytest.fixture()
def ext_root(tmp_path, monkeypatch):
    """临时项目根 + 进程内特征/注册表隔离。"""
    monkeypatch.chdir(tmp_path)
    features.clear_feature()
    custom_ops.clear()
    yield tmp_path
    features.clear_feature()
    custom_ops.clear()


# ============================================================
# 23b：特性开关单源诚实化
# ============================================================

def test_features_known_states_per_flag_defaults():
    """known_states 用各开关自己的默认值（INLINE_CACHE 默认 on 如实显示）。"""
    states = features.known_states()
    assert states == {"SCOPED_BLOCKS": False, "STACK_ENGINE": False,
                      "INLINE_CACHE": True, "PARSE_CACHE": False}
    assert features.KNOWN_FEATURES == tuple(features.DEFAULTS)
    assert features.state_tuple() == tuple(sorted(states.items()))


def test_features_state_tuple_reflects_overrides():
    """set_feature 后 state_tuple 变化（解析缓存键正确感知开关状态）。"""
    before = features.state_tuple()
    features.set_feature("SCOPED_BLOCKS", True)
    after = features.state_tuple()
    assert before != after
    assert dict(after)["SCOPED_BLOCKS"] is True


# ============================================================
# 23a：内建惰性化（默认行为不变 + 首调物化）
# ============================================================

def test_lazy_kernel_fn_materializes_on_first_call():
    """LazyKernelFn 首调物化：VM 时间面/宿主 JSON+终端面各自转发真实现。"""
    from src.kernel.lazy_kernel import LazyKernelFn
    from src.mbc.vm import _default_builtins
    b = _default_builtins()
    assert isinstance(b["获取时间戳"], LazyKernelFn)
    ts = b["获取时间戳"]()
    assert isinstance(ts, (int, float))
    assert b["获取时间戳"]._impl is not None
    from src.interp import BUILTINS
    assert isinstance(BUILTINS["解析_JSON"], LazyKernelFn)
    assert BUILTINS["解析_JSON"]('{"a": 1}') == {"a": 1}


def test_vm_defaults_lazy_sections_callable_shaped():
    """VM defaults 三节同为 LazyKernelFn 且 callable（双面函数判定不变）。"""
    from src.kernel.lazy_kernel import LazyKernelFn
    from src.mbc.vm import _default_builtins
    b = _default_builtins()
    for name in ("获取时间戳", "解析_JSON", "当前目录"):
        assert isinstance(b[name], LazyKernelFn) and callable(b[name])


def test_import_does_not_eager_load_kernel_sections():
    """23a 收益锁：import src.interp 后重内核节不在 sys.modules。"""
    import subprocess
    code = (
        "import sys, src.interp\n"
        "heavy = [m for m in ('src.kernel.terminal_builtin',"
        " 'src.kernel.time_builtin', 'src.kernel.json_builtin')"
        " if m in sys.modules]\n"
        "print('heavy:', heavy)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "heavy: []" in r.stdout


# ============================================================
# 23c：解析缓存 opt-in
# ============================================================

def test_parse_cache_default_off_no_caching(ext_root):
    """默认关闭：parse 不写缓存、重复解析各回各的树。"""
    from src.parser import _PARSE_CACHE, parse
    src = "输出(1 + 2)\n"
    a = parse(src)
    assert _PARSE_CACHE == {}
    b = parse(src)
    assert a is not b


def test_parse_cache_hit_same_tree_and_invalidation(ext_root):
    """开启后命中同一棵 AST；开关/自定义运算符变化即未命中。"""
    from src.parser import parse
    features.set_feature("PARSE_CACHE", True)
    src = "输出(1 + 2)\n"
    a = parse(src)
    assert parse(src) is a
    # 开关变化 → 新键
    features.set_feature("SCOPED_BLOCKS", True)
    assert parse(src) is not a
    features.clear_feature("SCOPED_BLOCKS")
    # 自定义运算符注册 → 版本号 +1 → 新键
    v0 = custom_ops.version()
    custom_ops.register("⊕", 60, "left")
    assert custom_ops.version() == v0 + 1
    assert parse(src) is not a


def test_parse_cache_lru_bound(ext_root):
    """LRU 上限 32：第 33 个不同源入键后总量不超。"""
    from src.parser import _PARSE_CACHE, _PARSE_CACHE_MAX, parse
    features.set_feature("PARSE_CACHE", True)
    for i in range(_PARSE_CACHE_MAX + 1):
        parse(f"输出({i})\n")
    assert len(_PARSE_CACHE) == _PARSE_CACHE_MAX


def test_parse_cache_speedup_on_hit(ext_root):
    """收益锁：命中路径显著快于重新解析（同一大文件二次 parse）。"""
    import time
    from src.parser import parse
    src = (ROOT / "matha" / "stdlib.matha").read_text(encoding="utf-8")
    features.set_feature("PARSE_CACHE", True)
    parse(src)
    t0 = time.perf_counter()
    for _ in range(10):
        parse(src)
    warm = (time.perf_counter() - t0) / 10
    assert warm < 0.01, f"命中应近零成本，实测 {warm * 1000:.2f} ms"


def test_parse_cache_ast_shared_readonly(ext_root):
    """共享树只读消费：缓存命中树与全新解析树逐字段一致（行为等价）。"""
    import dataclasses
    from src.parser import parse
    features.set_feature("PARSE_CACHE", True)
    src = "func 加(a, b) -> Int = a + b\n输出(加(1, 2))\n"
    cached = parse(src)
    features.set_feature("PARSE_CACHE", False)
    fresh = parse(src)
    assert repr(cached) == repr(fresh)


# ============================================================
# 23d：统一扩展面——协议与枚举
# ============================================================

def test_extension_protocol_shapes(ext_root):
    """四面同一协议：kind ∈ KINDS，ExtensionInfo 含版本/启停/来源三协议字段。"""
    assert KINDS == ("domain", "feature", "package", "terminal")
    rows = list_extensions()
    assert rows, "语料仓库至少有 domain/feature 两面"
    for e in rows:
        assert isinstance(e, ExtensionInfo)
        assert e.kind in KINDS
        assert isinstance(e.enabled, bool) and e.source
    kinds = {e.kind for e in rows}
    assert {"domain", "feature"} <= kinds


def test_state_file_protocol_validation(ext_root):
    """协议版本不符 / 缺 state 如实拒绝；未记录 = 启用。"""
    (ext_root / ".matha").mkdir()
    p = state_path(ext_root)
    p.write_text(json.dumps({"protocol_version": 99, "state": {}}),
                 encoding="utf-8")
    with pytest.raises(RuntimeError, match="协议版本"):
        load_state(ext_root)
    p.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION}),
                 encoding="utf-8")
    with pytest.raises(RuntimeError, match="state"):
        load_state(ext_root)
    p.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION,
                             "state": {}}), encoding="utf-8")
    assert set_enabled("feature", "PARSE_CACHE", True, ext_root)


def test_apply_state_no_file_zero_cost(ext_root):
    """无状态文件：apply_state 零落地（返回空 dict，进程特征不被触碰）。"""
    assert apply_state(ext_root) == {}
    assert features.is_enabled("PARSE_CACHE", default=False) is False


def test_apply_state_feature_face(ext_root):
    """feature 面真落地：state 文件写的开关进 features 进程内覆盖。"""
    (ext_root / ".matha").mkdir()
    (ext_root / ".matha" / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"feature": {"PARSE_CACHE": True}}}),
        encoding="utf-8")
    summary = apply_state(ext_root)
    assert features.is_enabled("PARSE_CACHE") is True
    assert summary["feature"] == ["PARSE_CACHE=on"]


def test_apply_state_domain_disable_and_restore(ext_root):
    """domain 面真落地：停用后 resolver 不再持有；启用经 reload() 回位。"""
    from src.plugin_api import get_resolver
    resolver = get_resolver()
    d = ext_root / ".matha"
    d.mkdir()
    (d / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"domain": {"quantum": False}}}),
        encoding="utf-8")
    assert resolver.plugin("quantum") is not None
    summary = apply_state(ext_root)
    assert resolver.plugin("quantum") is None
    assert resolver.normalize("quantum") is None
    assert summary["domain"] == ["quantum=停用"]
    # 重复停用幂等（已注销不再重复报告）
    assert apply_state(ext_root).get("domain") is None
    (d / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"domain": {"quantum": True}}}),
        encoding="utf-8")
    summary = apply_state(ext_root)
    assert resolver.plugin("quantum") is not None
    assert summary["domain"] == ["quantum=回位"]


def test_apply_state_unknown_domain_rejected(ext_root):
    """未知领域插件诚实拒绝（不静默吞）。"""
    d = ext_root / ".matha"
    d.mkdir()
    (d / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"domain": {"不存在的域": False}}}),
        encoding="utf-8")
    with pytest.raises(RuntimeError, match="未知领域插件"):
        apply_state(ext_root)


def test_disabled_domain_symbols_unavailable(ext_root):
    """闭环：停用领域后其符号在 exec_api 面真实不可用。"""
    (ext_root / ".matha").mkdir()
    (ext_root / ".matha" / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"domain": {"thermo": False}}}),
        encoding="utf-8")
    apply_state(ext_root)
    outputs, err = exec_api.run_checked("输出(R_气体常数)")
    assert err is not None and outputs == []
    # 卫生回位：全局注册表恢复全清单（后续测试共享同一 resolver）。
    (ext_root / ".matha" / "extensions.json").write_text(
        json.dumps({"protocol_version": 1,
                    "state": {"domain": {"thermo": True}}}),
        encoding="utf-8")
    assert apply_state(ext_root).get("domain") == ["thermo=回位"]


# ============================================================
# 23d：用户扩展包（真盘安装 / use 加载 / 启停单一事实源）
# ============================================================

def _make_pkg(root: Path, name: str = "方积", entry: str = "方积.matha",
              version: str = "0.1.0") -> Path:
    src = root / "pkg_src"
    src.mkdir(exist_ok=True)
    (src / entry).write_text(
        "(* 测试扩展包 *)\nfunc 加倍(x) -> Value = (x) => (x * 2)\n",
        encoding="utf-8")
    (src / "manifest.json").write_text(
        json.dumps({"name": name, "version": version}, ensure_ascii=False),
        encoding="utf-8")
    return src


def test_install_local_real_disk(ext_root):
    """安装 = 真复制 .matha 进 .matha_packages/<名>/ + manifest 落盘。"""
    src = _make_pkg(ext_root, name="mypkg", entry="mypkg.matha")
    meta = install_local(src, ext_root)
    assert meta["name"] == "mypkg" and meta["version"] == "0.1.0"
    assert meta["entry"] == "mypkg.matha"
    dest = ext_root / ".matha_packages" / "mypkg"
    assert (dest / "mypkg.matha").exists()
    assert (dest / "manifest.json").exists()


def test_install_local_rejects_empty_dir(ext_root):
    """没有 .matha 文件的目录如实拒绝（不假成功）。"""
    empty = ext_root / "empty_pkg"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="没有 .matha"):
        install_local(empty, ext_root)
    with pytest.raises(RuntimeError, match="目录不存在"):
        install_local(ext_root / "nope", ext_root)


def test_package_use_loads_entry(ext_root):
    """闭环：安装后的包经 use 真加载（函数平铺合并 + 命名空间语义同 use）。"""
    src = _make_pkg(ext_root, name="mypkg", entry="mypkg.matha")
    install_local(src, ext_root)
    outputs, err = exec_api.run_checked("use mypkg\n输出(加倍(21))")
    assert err is None and outputs == [42]


def test_package_disable_single_source(ext_root):
    """包启停 = 包 manifest.json "enabled" 字段（单一事实源，内核回退面尊重）。"""
    src = _make_pkg(ext_root, name="mypkg", entry="mypkg.matha")
    install_local(src, ext_root)
    meta = set_package_enabled("mypkg", False, ext_root)
    assert meta["enabled"] is False
    disk = json.loads(
        (ext_root / ".matha_packages" / "mypkg" / "manifest.json")
        .read_text(encoding="utf-8"))
    assert disk["enabled"] is False
    rows = [e for e in list_extensions(ext_root)
            if e.kind == "package" and e.name == "mypkg"]
    assert rows and rows[0].enabled is False
    outputs, err = exec_api.run_checked("use mypkg\n输出(加倍(21))")
    assert err is not None, "禁用包后 use 须如实失败"
    set_package_enabled("mypkg", True, ext_root)
    outputs, err = exec_api.run_checked("use mypkg\n输出(加倍(21))")
    assert err is None and outputs == [42]


def test_builtin_modules_take_priority_over_packages(ext_root):
    """matha/ 内置模块解析不受包回退影响：matha/ 命中永不走 .matha_packages。"""
    from src.interp import _load_matha_source
    text = _load_matha_source("stdlib")
    assert "标准库" in text or "func" in text
    assert _load_matha_source("词法器")


def test_upgrade_local_source_reinstall(ext_root):
    """本地源包升级 = 从记录源路径重装（版本未变如实报告已最新）。"""
    src = _make_pkg(ext_root, name="mypkg", entry="mypkg.matha",
                    version="0.2.0")
    install_local(src, ext_root)
    from src.extensions import upgrade_package
    result = upgrade_package("mypkg", ext_root)
    assert result[0] == "mypkg" and result[1] == "0.2.0"
    assert "已最新" in result[3]


def test_upgrade_uninstalled_rejected(ext_root):
    """未安装的包升级如实拒绝。"""
    from src.extensions import upgrade_package
    with pytest.raises(RuntimeError, match="未安装的扩展包"):
        upgrade_package("不存在", ext_root)


# ============================================================
# 23d：终端扩展面
# ============================================================

def test_terminal_extension_entries_execute_and_skip(ext_root, monkeypatch):
    """注册的 .msh 条目经 autorun 真执行；禁用条目跳过；缺失文件如实打印。"""
    from src import matha_term
    (ext_root / "demo.msh").write_text("回显 hi\n", encoding="utf-8")
    set_enabled("terminal", "demo.msh", True, ext_root)
    seen = []

    def fake_run(line):
        seen.append(line)
        return {"输出": [f"[{line}]"], "退出": False}

    monkeypatch.chdir(ext_root)
    matha_term._autorun_extensions(fake_run)
    assert seen == ["回显 hi"]

    set_enabled("terminal", "demo.msh", False, ext_root)
    seen.clear()
    matha_term._autorun_extensions(fake_run)
    assert seen == []


def test_terminal_legacy_autorun_file_listed(ext_root):
    """12e 遗产面：matha_term_extensions.msh 在场即进 terminal 枚举（可停用）。"""
    (ext_root / "matha_term_extensions.msh").write_text("# 注释\n",
                                                        encoding="utf-8")
    rows = [e for e in list_extensions(ext_root) if e.kind == "terminal"]
    assert len(rows) == 1 and rows[0].name == "matha_term_extensions.msh"
    assert rows[0].enabled is True
    set_enabled("terminal", "matha_term_extensions.msh", False, ext_root)
    rows = [e for e in list_extensions(ext_root) if e.kind == "terminal"]
    assert rows[0].enabled is False


# ============================================================
# 23d：CLI 面
# ============================================================

def _cli(*argv, cwd):
    import subprocess
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "src.matha_main", *argv],
                          capture_output=True, text=True, cwd=cwd,
                          env=env, timeout=120)


def test_cli_ext_list_and_toggle(ext_root):
    """ext list 四面表 + enable/disable 落盘 + 帮助面诚实。"""
    r = _cli("ext", "list", cwd=ext_root)
    assert r.returncode == 0
    assert "领域插件" in r.stdout and "特性开关" in r.stdout
    assert "合计" in r.stdout
    r = _cli("ext", "disable", "domain", "thermo", cwd=ext_root)
    assert r.returncode == 0 and "已停用" in r.stdout
    data = json.loads(state_path(ext_root).read_text(encoding="utf-8"))
    assert data["state"]["domain"]["thermo"] is False
    r = _cli("ext", "enable", "domain", "thermo", cwd=ext_root)
    assert r.returncode == 0 and "已启用" in r.stdout
    r = _cli("ext", "disable", "domain", "不存在的域", cwd=ext_root)
    assert r.returncode == 0  # 写盘诚实；生效时 apply_state 才拒绝


def test_cli_ext_install_package_and_msh(ext_root):
    """ext install 双形态：目录 → 扩展包；.msh → 终端扩展注册。"""
    src = _make_pkg(ext_root, name="mypkg", entry="mypkg.matha")
    r = _cli("ext", "install", str(src), cwd=ext_root)
    assert r.returncode == 0 and "已安装" in r.stdout and "use mypkg" in r.stdout
    (ext_root / "demo.msh").write_text("回显 hi\n", encoding="utf-8")
    r = _cli("ext", "install", "demo.msh", cwd=ext_root)
    assert r.returncode == 0 and "已注册" in r.stdout
    data = json.loads(state_path(ext_root).read_text(encoding="utf-8"))
    assert data["state"]["terminal"]["demo.msh"] is True


def test_cli_ext_help_lists_actions(ext_root):
    """ext 子命令面：list/enable/disable/install/upgrade 全部在 help 中。"""
    r = _cli("ext", "--help", cwd=ext_root)
    assert r.returncode == 0
    for word in ("list", "enable", "disable", "install", "upgrade"):
        assert word in r.stdout


def test_cli_command_table_parity(ext_root):
    """命令表化锁：_tool_cmds 注册的命令名与 argparse 帮助面一致（30 条）。"""
    from src.matha_main import _build_parser
    parser = _build_parser()
    subactions = next(a for a in parser._actions
                      if isinstance(a, __import__("argparse")._SubParsersAction))
    names = set(subactions.choices)
    for cmd in ("typecheck", "mtest", "format", "async", "doc", "viz",
                "compile2", "http", "git", "bld", "db", "ai", "compiler",
                "game2", "sec2", "ui", "devops", "blockchain2", "media",
                "geo2", "robot2", "devdrv", "osapi", "gfxdrv", "crypto",
                "mathbase", "browser", "mobile", "law", "geek", "ext"):
        assert cmd in names, f"命令表缺 {cmd}"


def test_cli_features_lists_all_flags(ext_root):
    """matha features 四开关齐全且 INLINE_CACHE 显示 on（23b 诚实化锁）。"""
    r = _cli("features", cwd=ext_root)
    assert r.returncode == 0
    assert "SCOPED_BLOCKS" in r.stdout and "STACK_ENGINE" in r.stdout
    assert "INLINE_CACHE" in r.stdout and "PARSE_CACHE" in r.stdout
    assert "on" in r.stdout and "off" in r.stdout
