# -*- coding: utf-8 -*-
"""阶段 42 语言收敛锁（纯 Matha 装载器 + 载体原语链面臂 + 终端链面默认后端）。

阶段 42 的判据是「装载与终端命令逻辑不再由宿主 Python 代劳」：装载这件事、命令
逻辑的执行体、OS 载体的调用面都由 Matha 自身完成，宿主只保留 OS 能力实现。三片
各自落地面：

42a 纯 Matha 装载器（``matha/loader.matha``）：模块名表、三级解析序（``matha/``
    → ``.matha_packages/`` 扩展包 → ``matha/library/`` 资源库）、清单 entry/enabled
    语义、依赖摊平、机械单元剔除、缺模块报错文案，逐条镜像宿主 ``src/interp.py``
    的 ``_CN2FILE`` / ``_matha_module_path`` / ``_load_matha_source``。路径为
    **绝对**（装配方注入 boot VM 全局 ``装载根``）——宿主 ``_matha_dir()`` 的首候选
    即仓库根而非 cwd，故终端 ``换目录`` 之后装载仍命中同一批源。

42b 载体原语链面臂：16 条 OS 载体名 + 语言级 ``错误`` 在 ``注册内建`` 固定面有名、
    在 ``应用内建实`` 有逐名臂（双镜像 ``interp_matha.matha`` / ``interp.matha``）；
    二元载体只给一参时按柯里化产偏应用，**不触达宿主实现**；注册无臂的名字如实
    「未知内建函数」，不回落。阶段 43a-2 在本固定面追加第 17 条 ``当前目录``
    （装载器现取 cwd 用），故面名数 59→**60**。

42c 终端链面默认后端：``src/matha_term.py`` 默认后端 = chain（``MATHA_TERM_BACKEND``
    可显式切 host，未知值诚实拒绝，两面无静默回落）；``调试Matha`` 在链面是
    **显式拒绝**（VM 编译链无逐节点轨迹能力），宿主后端保留为对拍/排障入口。

登记不修（KNOWN_ISSUES 阶段 42）：① ``装载根`` 只在 level-1 注入，level-2 装载器
体未注入；③ ``调试Matha`` 链面显式拒绝；④ 终端 运行/调试/扩展命令 经
执行Matha/调试Matha 仍落宿主引擎。② 扩展包扫描的 cwd 根序 —— **阶段 43a-2 退役**
（``当前目录`` 臂 + ``装载包根们`` 逐根扫，双面同判见 phase43 锁）。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from src import interp as host_interp  # noqa: E402
from src import matha_chain, matha_term  # noqa: E402
from src.kernel.errors import MathaRuntimeError  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent

#: 42b 拍板的 16 条 OS 载体原语（逐名补 Matha 臂，非全表面注入）
_CARRIERS = ["执行命令", "执行命令输入", "管道输入", "管道结束", "输入行",
             "列目录", "建目录", "删除路径", "复制文件", "改名", "换目录",
             "路径存在", "执行Matha", "调试Matha", "升级包", "检查包更新"]
#: 阶段 43a-2 追加的第 17 条载体名——装载器 根()/包路径 现取 cwd，使终端
#: 换目录 后链面解析序随宿主面同动（宿主 _package_module_path per-call 读 cwd）
_CARRIERS_43 = ["当前目录"]
#: 语言级 raise 名——终端/标准库 level-2 的显式拒绝路径全走它
_RAISE_NAMES = ["错误"]

#: 双面逐字对拍的终端行（结果帧或异常文案同判；不含改变进程 cwd 的行）
_PARITY_LINES = ["回显 hi", "帮助", "目录 .", "显示文件 小文件.txt",
                 "回显 x > out.txt", "echo a | 查找 a", "目录 一 二",
                 "显示文件 不存在.txt", "退出"]

_SUB_ENV = {k: v for k, v in os.environ.items() if k != "MATHA_TERM_BACKEND"}
_SUB_ENV.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(_ROOT)})


def _call(vm, fn, *args):
    return vm.invoke_value(fn, list(args))


def _norm(path):
    return os.path.normcase(os.path.normpath(str(path)))


def _fwd(path):
    """Matha 字符串字面量里的绝对路径（正斜杠，免反斜杠转义）。"""
    return str(path).replace("\\", "/")


def _parse(vm, src):
    toks = _call(vm, vm.globals["词法器"]["扫描"], src, 0, 1, 1, [])
    return _call(vm, vm.globals["语法器"]["parse"], toks)


def _level2(chain, src, base_env=None):
    """level-2（Matha 数据闭包）执行一段小程序，返回块值。"""
    vm = chain.vm
    vm.outputs.clear()
    res = _call(vm, vm.globals["解释器"]["执行语句"], _parse(vm, src),
                base_env if base_env is not None else chain.env)
    vm.outputs.clear()
    return res[0]


def _face_frames(run, lines):
    """逐行取结果帧；异常按「类名: 文案」入列，使诚实拒绝同样可比。"""
    out = []
    for line in lines:
        try:
            out.append(("ok", repr(run(line))))
        except Exception as e:  # noqa: BLE001
            out.append(("err", f"{type(e).__name__}: {e}"))
    return out


def _seed_dir(d):
    d.mkdir(parents=True, exist_ok=True)
    (d / "小文件.txt").write_text("第一行\n第二行\n", encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def chain():
    """boot 链会话（六文件含纯 Matha 装载器）——进程内复用，装配 ~2s。"""
    return matha_chain.MathaChain()


@pytest.fixture(scope="module")
def vm(chain):
    return chain.vm


@pytest.fixture(scope="module")
def loader(vm):
    return vm.globals["装载器"]


@pytest.fixture(scope="module")
def chain_run(chain):
    """链面终端调用器：装载 终端执行器 一次，命令逻辑跑在 Matha 数据闭包上。"""
    return matha_chain.make_term_runner(chain)


# ============ 42a 纯 Matha 装载器 ============

def test_42a_name_table_mirrors_host(loader, vm):
    """名表 与宿主 ``_CN2FILE`` 逐条同集（含 装载器 自身）。"""
    table = dict((p[0], p[1]) for p in _call(vm, loader["名表"]))
    assert table == host_interp._CN2FILE
    assert table["装载器"] == "loader.matha"


def test_42a_main_path_is_absolute_and_matches_host_rule(loader, vm):
    """主路径 = 装载根 + 名表映射（运行时引擎 特例同宿主），产绝对路径。"""
    assert os.path.isabs(_call(vm, loader["根"]))
    assert _norm(_call(vm, loader["主路径"], "标准库")) == _norm(
        _ROOT / "matha" / "stdlib.matha")
    assert _norm(_call(vm, loader["主路径"], "内核")) == _norm(
        _ROOT / "matha" / "os" / "kernel.matha")
    assert _norm(_call(vm, loader["主路径"], "运行时引擎")) == _norm(
        _ROOT / "matha" / "runtime" / "matha_runtime.matha")
    assert _norm(_call(vm, loader["主路径"], "未登记模块xyz")) == _norm(
        _ROOT / "matha" / "未登记模块xyz.matha")


@pytest.mark.parametrize("名", ["标准库", "内核", "桌面", "资源索引", "运行时引擎",
                                "终端执行器", "装载器", "hello_ext", "不存在的模块xyz"])
def test_42a_three_level_resolution_matches_host(loader, vm, 名):
    """三级解析序结果与宿主 ``_matha_module_path`` 同判（未命中双侧皆空）。"""
    chain_path = _call(vm, loader["路径"], 名)
    host_path = host_interp._matha_module_path(名)
    if host_path is None:
        assert chain_path == ""
    else:
        assert chain_path and os.path.exists(chain_path)
        assert _norm(chain_path) == _norm(host_path)


def test_42a_resolution_is_cwd_independent(loader, vm, tmp_path, monkeypatch):
    """换 cwd 不改装载根：终端 换目录 之后装载仍命中同一批源（宿主 _matha_dir 同口径）。"""
    before = _call(vm, loader["路径"], "标准库")
    monkeypatch.chdir(tmp_path)
    assert _call(vm, loader["根"]) == str(_ROOT)
    assert _call(vm, loader["路径"], "标准库") == before
    assert _norm(before) == _norm(_ROOT / "matha" / "stdlib.matha")


def test_42a_missing_module_message_matches_host(loader, vm):
    """缺模块诚实报错：文案与宿主 FileNotFoundError 逐字同判（异常类名分歧登记不修）。"""
    with pytest.raises(MathaRuntimeError) as exc:
        _call(vm, loader["装载"], "不存在的模块xyz")
    with pytest.raises(FileNotFoundError) as host_exc:
        host_interp._load_matha_source("不存在的模块xyz")
    assert str(exc.value) == str(host_exc.value)
    assert "已查 matha/、.matha_packages/ 扩展包、matha/library/ 资源库" in str(exc.value)


def test_42a_manifest_semantics(loader, vm):
    """清单 entry/enabled 语义与 _package_module_path 同口径（禁用包整包跳过）。"""
    assert _call(vm, loader["启用"], {}) is True
    assert _call(vm, loader["启用"], {"enabled": True}) is True
    assert _call(vm, loader["启用"], {"enabled": False}) is False
    assert _call(vm, loader["入口"], {"entry": "main.matha"}) == "main.matha"
    assert _call(vm, loader["入口"], {}) == ""
    # 43a-2：装包 改带目录参（多根扫描后目录由调用方逐根给出）——禁用包整包跳过
    assert _call(vm, loader["装包"], "/pkg/某包", "某包",
                 {"enabled": False, "entry": "main.matha"}) == ""
    assert _call(vm, loader["包路径"], "不存在的包xyz") == ""


def test_42a_ast_helpers_on_real_sources(loader, vm):
    """内声明/收集使用名/去机械 与真源逐条同判（宿主只执行 ModuleDecl 体）。"""
    for rel, 期望使用 in [("matha/term_engine.matha", ["终端句法器", "标准库", "桌面"]),
                          ("matha/os/kernel.matha", ["标准库"]),
                          ("matha/stdlib.matha", [])]:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        prog = _parse(vm, src)
        inner = _call(vm, loader["内声明"], prog["声明"])
        assert _call(vm, loader["收集使用名"], inner, []) == 期望使用
        assert re.findall(r"^\s*use\s+(\S+)", src, re.M) == 期望使用
    去机械 = _call(vm, loader["去机械"],
                   [{"类型": "机械单元"}, {"类型": "函数定义"}, {"类型": "机械单元"}], [])
    assert [n["类型"] for n in 去机械] == ["函数定义"]


def test_42a_flatten_and_builtin_merge(chain, loader, vm):
    """摊平 使依赖模块裸名可达；并内建 把模块自述别名表并入 ns（宿主 use 回退同路）。"""
    flat = _call(vm, loader["摊平"], chain.env, "某模块", {"f": 1, "g": 2})
    环境包含 = vm.globals["解释器"]["环境包含"]
    for 名 in ("f", "g", "某模块"):
        assert _call(vm, 环境包含, flat, 名) is True
    merged = _call(vm, loader["并内建"], {"a": 1, "内建": {"len": 2}})
    assert merged["a"] == 1 and merged["len"] == 2


def test_42a_load_produces_namespace(loader, vm):
    """装载 经链解释器执行模块体并产命名空间（level-2 数据闭包）。"""
    ns = _call(vm, loader["装载"], "终端句法器")
    assert {"终端解析", "终端帧分析", "建帧"} <= set(ns)


# ============ 42b 载体原语链面臂 ============

def test_42b_carriers_registered_in_chain_surface(chain):
    """16 载体 + 错误 + 43a-2 当前目录 全在 注册内建 固定面上（level-2 可达的前提）。"""
    names = {pair[0] for pair in chain.env}
    assert set(_CARRIERS) | set(_CARRIERS_43) | set(_RAISE_NAMES) <= names
    assert len(names) == 60, f"链面固定面名数变动需同步本锁与 KNOWN_ISSUES: {sorted(names)}"


def test_42b_named_arms_exist_in_both_mirrors():
    """双镜像逐名臂齐全：interp_matha 有臂 + 元数表，interp 有 func_ 包装 + 注册。"""
    matha = (_ROOT / "matha" / "interp_matha.matha").read_text(encoding="utf-8")
    interp = (_ROOT / "matha" / "interp.matha").read_text(encoding="utf-8")
    for name in _CARRIERS + _CARRIERS_43 + _RAISE_NAMES:
        assert re.search(rf'name = "{name}" \?', matha), f"interp_matha 缺 {name} 臂"
        assert re.search(rf'绑定环境\(env\d+, "{name}"', interp), f"interp.matha 缺 {name} 注册"
        assert re.search(rf"func func_{name}\(", interp), f"interp.matha 缺 func_{name} 包装"
    assert re.search(r'name = "复制文件" or name = "改名" or name = "执行命令输入" \? 2 :',
                     matha), "二元载体元数表缺失（偏应用判据）"


def test_42b_level2_readonly_primitives_reach_carrier(chain, tmp_path):
    """level-2 只读原语真达宿主载体：路径存在 / 列目录 返回值如实。"""
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    assert _level2(chain, '{ 输出(路径存在("' + _fwd(f) + '")) }') is True
    assert _level2(chain, '{ 输出(路径存在("' + _fwd(tmp_path / "缺失.txt") + '")) }') is False
    listed = _level2(chain, '{ 输出(列目录("' + _fwd(tmp_path) + '")) }')
    assert [p[0] for p in listed] == ["a.txt"]


def test_42b_level2_binary_carrier_is_partial_and_does_not_touch_host(chain, tmp_path):
    """二元载体单参调用产偏应用，不触达宿主实现（目录零副作用）。"""
    assert _level2(chain, '{ 输出(复制文件("不存在的源xyz.txt")) }') == \
        ["__内建部分__", "复制文件", ["不存在的源xyz.txt"]]
    assert _level2(chain, '{ 输出(改名("不存在的源xyz.txt")) }') == \
        ["__内建部分__", "改名", ["不存在的源xyz.txt"]]
    assert list(tmp_path.iterdir()) == []


def test_42b_registered_without_arm_is_honest(chain, vm):
    """注册无臂的名字如实「未知内建函数」——不静默回落宿主实现。"""
    env2 = _call(vm, vm.globals["解释器"]["绑定环境"],
                 chain.env, "无臂内建", ("__builtin__", "无臂内建"))
    with pytest.raises(MathaRuntimeError) as exc:
        _level2(chain, '{ 输出(无臂内建(1)) }', env2)
    assert str(exc.value) == "未知内建函数: 无臂内建"


def test_42b_error_arm_raises_same_message_as_host(chain):
    """语言级 错误 臂：level-2 显式拒绝经 MathaRuntimeError 上抛，文案不被掩盖。"""
    with pytest.raises(MathaRuntimeError) as exc:
        _level2(chain, '{ 输出(错误("显式拒绝文案")) }')
    assert str(exc.value) == "显式拒绝文案"


# ============ 42c 终端链面默认后端 ============

def test_42c_default_backend_is_chain(monkeypatch):
    """未设环境变量 → 装配链面调用器（不碰宿主引擎）。"""
    monkeypatch.delenv("MATHA_TERM_BACKEND", raising=False)
    seen = []
    monkeypatch.setattr(matha_chain, "make_term_runner",
                        lambda *a, **k: seen.append("chain") or "chain-runner")
    monkeypatch.setattr(matha_term, "_make_host_runner",
                        lambda: seen.append("host") or "host-runner")
    assert matha_term._make_runner() == "chain-runner"
    assert seen == ["chain"]


def test_42c_host_backend_is_explicit(monkeypatch):
    """MATHA_TERM_BACKEND=host 显式切回宿主解释器面（对拍/排障入口）。"""
    monkeypatch.setenv("MATHA_TERM_BACKEND", "host")
    seen = []
    monkeypatch.setattr(matha_chain, "make_term_runner",
                        lambda *a, **k: seen.append("chain") or "chain-runner")
    monkeypatch.setattr(matha_term, "_make_host_runner",
                        lambda: seen.append("host") or "host-runner")
    assert matha_term._make_runner() == "host-runner"
    assert seen == ["host"]


def test_42c_unknown_backend_refused(monkeypatch):
    """未知后端值诚实拒绝，不猜默认。"""
    monkeypatch.setenv("MATHA_TERM_BACKEND", "python")
    with pytest.raises(RuntimeError) as exc:
        matha_term._make_runner()
    assert str(exc.value) == "未知终端后端: python（MATHA_TERM_BACKEND 可用值: chain | host）"


def test_42c_no_silent_fallback_to_host(monkeypatch, capsys, tmp_path):
    """链面装配失败如实报错并以退出码 1 结束——不偷换宿主执行体。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MATHA_TERM_BACKEND", raising=False)

    def boom(*a, **k):
        raise RuntimeError("链面装配失败xyz")

    monkeypatch.setattr(matha_chain, "make_term_runner", boom)
    assert matha_term.run_command("回显 hi") == 1
    out = capsys.readouterr().out
    assert "错误: 链面装配失败xyz" in out and "hi" not in out


def test_42c_boot_files_and_matrix_mirror():
    """装载器 进 boot 链六文件；宿主与 Track B 名表镜像同步（boot 快照不含 loader）。"""
    assert "matha/loader.matha" in matha_chain.BOOT_FILES
    from scripts import selfhost_matrix
    assert selfhost_matrix._CN2FILE["装载器"] == "loader.matha"
    assert "matha/loader.matha" not in selfhost_matrix.BOOT_FILES


def test_42c_loading_root_injected(vm, loader):
    """装载根 由装配方注入 boot VM 全局，值即仓库根（level-1 可见）。"""
    assert vm.globals["装载根"] == str(_ROOT)
    assert _call(vm, loader["根"]) == str(_ROOT)


def test_42c_term_faces_parity(chain_run, tmp_path, monkeypatch):
    """链面与宿主面终端逐行同判：结果帧与诚实拒绝文案一起可比（两面各自独立目录）。"""
    host_run = matha_term._make_host_runner()
    results = []
    for run, d in ((chain_run, _seed_dir(tmp_path / "chain")),
                   (host_run, _seed_dir(tmp_path / "host"))):
        monkeypatch.chdir(d)
        results.append(_face_frames(run, _PARITY_LINES))
    monkeypatch.chdir(tmp_path)
    assert results[0] == results[1], "\n".join(
        f"{line!r}\n  chain={a}\n  host ={b}"
        for line, a, b in zip(_PARITY_LINES, results[0], results[1]))


def test_42c_refusal_wording_matches_host(chain_run, tmp_path, monkeypatch):
    """显式拒绝路径端到端同判（42b 的 错误 臂此前被「未定义变量 '错误'」掩盖）。"""
    host_run = matha_term._make_host_runner()
    monkeypatch.chdir(_seed_dir(tmp_path))
    链 = _face_frames(chain_run, ["目录 一 二", "显示文件 不存在.txt"])
    宿 = _face_frames(host_run, ["目录 一 二", "显示文件 不存在.txt"])
    assert 链 == 宿
    assert 链[0] == ("err", "MathaRuntimeError: 目录: 至多 1 个参数, 实得 2")
    assert 链[1][0] == "err" and "read_file 失败" in 链[1][1]


def test_42c_debug_is_explicit_refusal_on_chain(chain_run):
    """调试Matha 在链面显式拒绝（VM 编译链无逐节点轨迹），并指向宿主后端。"""
    with pytest.raises(RuntimeError) as exc:
        chain_run('调试 "let 值 = 5 in 输出(值 + 1)"')
    msg = str(exc.value)
    assert "调试Matha 需要宿主解释器后端" in msg
    assert "MATHA_TERM_BACKEND=host" in msg


def test_42c_default_subprocess_backend_is_chain(tmp_path):
    """真 subprocess 默认后端 = 链面：调试 的显式拒绝文案只可能来自链面。"""
    r = subprocess.run([sys.executable, "-m", "src.matha_term", "-c", '调试 "输出(1)"'],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=_SUB_ENV, timeout=600, cwd=str(tmp_path))
    assert "调试Matha 需要宿主解释器后端" in r.stdout, r.stdout + r.stderr
