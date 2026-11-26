"""阶段 46 锁档：46-1 真缺陷片——`stdlib.to_upper` 的自由名 `acc` 真修 + latent 名口径收口。

拍板口径（阶段 46）：路线 = 有界清算循环（每轮 = 可判定判据 + 可回滚提交）；本轮
切片 = 先收 46-摸底取证出的**真缺陷**，再进 46a 的原生 OS 载体族。

46 摸底结论（逐项当场实测，非读文档）：阶段 45 登记的「boot 全链 25 个 latent
宿主注入名」按**载体归属**分三类——
  A 20 名在 `build_boot_vm()` 产物的 `vm.globals` 里（宿主 Python 载体已就位）；
  B 4 名由 os 域插件惰性物化（`PluginResolver` 有 owner：执行命令 / 执行命令输入 /
    升级包 / 检查包更新）；
  C 1 名**谁都没有**——`acc`。它不是宿主注入名，而是 `matha/stdlib.matha` 里
    `to_upper` 的自由变量：递归函数 `_map(i, acc)` 的形参被写进了 `let rec … in
    _map(0, acc)` 的体尾（对位的 `to_lower` 写的是 `_map(0, "")`）。hi / vm / 链面
    三面同判 `未定义变量 'acc'`——这条从来不是「脱宿主」缺口，而是一个一旦被调用
    就必然失败的死函数臂。名集因此 25 → **24**，且 C 类归零。

判据面（也是「假脱宿主」的防线）：
- 46a 语料静态锁：`_map(0, acc)` 绝迹、两函数种子对称。
- 46b 链面真读数（走产品分派体 `应用内建实`，不是自造调用形）+ `to_lower` 不回归。
- 46c/46d 真原生 PE64 正反控：新形逐字给出手算读数；把 `acc` 注回文本再编一次，
  运行期 rc≠0 + stderr「未定义变量」——证明收益来自这次改动而非调用形偶然不同。
- 46e **分类判据**：boot 全链每个 latent 名都必须有 A 或 B 类载体归属。这条把摸底
  的分类动作固化成机器判定，此后语料级自由名再也无法冒充「宿主注入缺口」。
- 46f 名集/计数与阶段 45 锁档同源（`_BOOT_LATENT` 去掉 `acc`、24 名、读位 32）。
- 46g stdlib 单片 latent 归零（与 45d-6 词法器单片同规格）。
- 46h 口径锁：boot 链 LOAD_GLOBAL 名与 `_UNRESOLVED_GLOBALS` 的交集只落在**特殊发射
  位**（`None` / `_empty_dict` 在编译期拒绝分支之前已处理），即「24 是下界」这句口径
  本身成立——不锁它，24 就会被读成「宿主注入缺口的上界」，而真正的下界含义是
  「至少还差这 24 个载体」。
- 46i 面分歧如实登记：`to_upper` 只在链面注册面（宿主 `src/**` 零载体），hi 面仍
  「未定义变量 'to_upper'」——41-① 表差族的新成员，本片不扩宿主表。
- 46j 文档口径与机器读数同源：四份文档的 latent 名数/读位数锚点由 `_latent_reads` 的
  实测值动态拼出（附「25 是时点读数 ⇒ 必须有归因指针」的条件锁），把「文档写 25、
  代码给 24」这类漂移变成门禁失败而不是下一次摸底的发现。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.mbc import native  # noqa: E402
from src.mbc import opcodes as OP  # noqa: E402
from tests.test_native_selfhost_phase45 import (  # noqa: E402
    _BOOT_LATENT, _compile, _latent_reads)

_STDLIB_TXT = (_ROOT / "matha" / "stdlib.matha").read_text(encoding="utf-8")
_INTERP_MATHA_TXT = (_ROOT / "matha" / "interp_matha.matha").read_text(encoding="utf-8")

#: 手算对拍表——小写转大写、非字母原样、空串；对位 to_lower 一并锁住不回归。
_UPPER_CASES = [
    ("aB", "AB"),
    ("Hello, World! 123", "HELLO, WORLD! 123"),
    ("", ""),
    ("abc_é中", "ABC_é中"),
    ("z", "Z"),
    ("0-9 ~!", "0-9 ~!"),
]
_LOWER_CASES = [("AB", "ab"), ("Hello, World! 123", "hello, world! 123"), ("", "")]

_DRIVER = ("".join(f'输出(to_upper("{s}"))\n' for s, _ in _UPPER_CASES)
           + "".join(f'输出(to_lower("{s}"))\n' for s, _ in _LOWER_CASES))
_EXPECTED = ([e for _, e in _UPPER_CASES] + [e for _, e in _LOWER_CASES])


def _func_body(txt: str, header: str) -> str:
    """取 `func <header>` 到下一个空行为止的函数体（stdlib 里函数以空行分隔）。"""
    i = txt.index(f"func {header}")
    j = txt.index("\n\n", i)
    return txt[i:j]


@pytest.fixture(scope="module")
def chain():
    from src.matha_chain import MathaChain
    return MathaChain()


def _face_builtin(chain, name: str, arg: str):
    """走产品分派体 应用内建实（`interp_matha.matha` 的 to_upper / to_lower 臂在此）。"""
    return chain.vm.call("应用内建实", name, [arg], chain.env)


def _exe(tag: str, sources: list[str]) -> Path:
    """每个用例独立 exe 名——Windows 下固定名会被上一进程的映像锁住。"""
    p = Path(tempfile.gettempdir()) / f"p46_{tag}.exe"
    p.write_bytes(native.compile_sources_to_exe(sources))
    return p


def _run_exe(p: Path) -> tuple[int, list[str], str]:
    r = subprocess.run([str(p)], capture_output=True, timeout=180)
    return (r.returncode & 0xFFFFFFFF,
            r.stdout.decode("utf-8", "replace").splitlines(),
            r.stderr.decode("utf-8", "replace"))


# ==================== 46a 语料静态锁 ====================


def test_46a_stdlib_has_no_free_acc_in_to_upper():
    """`_map(0, acc)` 绝迹——`let rec` 的形参不在 `in` 体里，写下即成死函数。"""
    assert "_map(0, acc)" not in _STDLIB_TXT
    assert "acc: String" in _STDLIB_TXT, "acc 作为 _map 形参名本应仍在（只消失于体尾实参位）"


def test_46a_upper_and_lower_are_seed_symmetric():
    """两函数的递归种子同为 `_map(0, "")`——不对称即一侧把种子写成了自由名。"""
    assert _func_body(_STDLIB_TXT, "to_lower").count('_map(0, "")') == 1
    assert _func_body(_STDLIB_TXT, "to_upper").count('_map(0, "")') == 1


# ==================== 46b 链面真读数 ====================


@pytest.mark.parametrize("src,expect", _UPPER_CASES)
def test_46b_chain_face_to_upper_true_read(chain, src, expect):
    assert _face_builtin(chain, "to_upper", src) == expect


@pytest.mark.parametrize("src,expect", _LOWER_CASES)
def test_46b_chain_face_to_lower_unchanged(chain, src, expect):
    assert _face_builtin(chain, "to_lower", src) == expect


# ==================== 46c/46d 真原生 PE64 正反控 ====================


def test_46c_native_exe_reads_the_same_values_without_python():
    """标准库 + 驱动一次链接成真映像，读数与手算逐字同判（产物不经 Python）。"""
    rc, out, err = _run_exe(_exe("upper_true", [_STDLIB_TXT, _DRIVER]))
    assert rc == 0, f"rc={rc} err={err[:200]}"
    assert out == _EXPECTED, f"输出分歧：{out} != {_EXPECTED}"


def test_46d_native_exe_with_the_bug_reinjected_fails_honestly():
    """反向控：把 `acc` 注回 `to_upper` 体尾再编一次——运行期非零退出 + 诚实点名。

    这条证明 46c 的收益来自本次改动，而不是「驱动写法恰好绕开了缺陷」。
    """
    i = _STDLIB_TXT.index("func to_upper")
    buggy = _STDLIB_TXT[:i] + _STDLIB_TXT[i:].replace('_map(0, "")', "_map(0, acc)", 1)
    assert "_map(0, acc)" in buggy
    rc, out, err = _run_exe(_exe("upper_old", [buggy, '输出(to_upper("aB"))\n']))
    assert rc != 0, f"旧形竟跑通：{out}"
    assert out == [], out
    assert "未定义变量" in err, err[:200]


# ==================== 46e/46f/46g latent 名口径与分类判据 ====================

_DOMAIN_INERT = {"执行命令", "执行命令输入", "升级包", "检查包更新"}


@pytest.fixture(scope="module")
def boot_vm():
    from src.matha_chain import build_boot_vm
    return build_boot_vm()


@pytest.fixture(scope="module")
def boot_latent():
    from src.matha_chain import BOOT_FILES
    return _latent_reads(_compile(list(BOOT_FILES)).mod)


def test_46e_every_latent_name_has_a_host_carrier_or_a_domain_owner(boot_vm, boot_latent):
    """latent 名 ⊆（boot `vm.globals` ∪ 域插件 known_symbols）——C 类必须恒为空。

    把摸底的一次性分类动作固化在此：`acc` 当年正是「谁都没有」却被记成宿主注入名，
    使 25 这个数既高估了载体缺口、又掩盖了一个真缺陷。新增 C 类名会直接撞这里。
    """
    from src.plugin_api import get_resolver
    resolver = getattr(boot_vm, "domain_resolver", None) or get_resolver()
    owners = set(boot_vm.globals) | set(resolver.known_symbols())
    cls_c = sorted(n for n in boot_latent if n not in owners)
    assert cls_c == [], f"语料级自由名冒充宿主缺口：{cls_c}"
    assert _DOMAIN_INERT <= set(boot_latent), "os 域惰性名集变化，本条口径需重新取证"


def test_46f_latent_set_is_the_documented_24_with_phase45_table_minus_acc(boot_latent):
    """名集锁：现行 24 名 = 阶段 45 的 25 名去掉 `acc`；读位总数 32。"""
    assert "acc" not in _BOOT_LATENT, "阶段 45 名集应已随本片收口去掉 acc（见其 _BOOT_LATENT 注）"
    assert set(boot_latent) == _BOOT_LATENT, (
        f"名集漂移：新增 {sorted(set(boot_latent) - _BOOT_LATENT)}，"
        f"消失 {sorted(_BOOT_LATENT - set(boot_latent))}")
    assert len(boot_latent) == 24, f"latent 名数：{len(boot_latent)}"
    assert sum(boot_latent.values()) == 32, boot_latent


def test_46g_stdlib_fragment_alone_has_no_latent_name():
    """标准库单片 latent 归零——与 45d-6 的词法器单片同规格正向锁。"""
    assert _latent_reads(_compile(["matha/stdlib.matha"]).mod) == {}


def test_46h_latent_count_is_a_lower_bound_unresolved_names_are_emitted(boot_latent):
    """口径锁：boot 链里与 `_UNRESOLVED_GLOBALS` 相交的名只落在编译期特殊发射位。

    `_latent_reads` 刻意跳过 `_UNRESOLVED_GLOBALS`，而 native 对该集合的常规分支是
    **编译期** `NativeNotSupported` 拒绝——若 boot 链真有名落到那里，45a5 的「全链
    编译通过」就会红。此处相交只剩 `None` / `_empty_dict`，二者在拒绝分支之前已按
    静态对象处理，故「24 是下界」这句口径成立。
    """
    from src.matha_chain import BOOT_FILES
    mod = _compile(list(BOOT_FILES)).mod
    names: set[str] = set()
    for code in [mod.main_code] + [f.code for f in mod.functions.values()]:
        for ins in code:
            if len(ins) > 1 and ins[0] == OP.LOAD_GLOBAL:
                v = mod.constants[ins[1]]
                if isinstance(v, str):
                    names.add(v)
    hit = sorted(names & set(native._UNRESOLVED_GLOBALS))
    assert hit == ["None", "_empty_dict"], f"特殊发射位/编译期拒绝位漂移：{hit}"
    assert "None" not in boot_latent and "_empty_dict" not in boot_latent


# ==================== 46j 文档口径与机器读数同源 ====================

#: 四份文档里承载 latent 口径的落点。锚点由 `len(boot_latent)` / 读位总数动态拼出，
#: 所以文档一旦与 `_latent_reads` 脱钩就红——阶段 45 的「25」正是被写成现行值后
#: 掩盖了一个真缺陷，只改文字不锁读数即会复现。
_DOC_LATENT_ANCHORS = {
    "README.md": ("latent 名集 25→**{n}**", "总读位 33→{g}"),
    "docs/ARCHITECTURE.md": ("latent 名集 25→**{n}**", "总读位 33→{g}"),
    "docs/CHANGELOG.md": ("latent 名集 25→**{n}**", "总读位 33→{g}"),
    "docs/KNOWN_ISSUES.md": ("latent 名集 25→**{n}**", "总读位 33→{g}"),
}
#: 文档中出现「25 个 latent / 登记 25 名」这类时点读数时，同文档必须给出归因指针。
_HISTORICAL_READINGS = ("25 个 latent", "登记 25 名")
_ATTRIBUTION_POINTER = "阶段 46 摸底"


def _flat(rel: str) -> str:
    """压平空白后比对——文档条目按 ~90 列折行，锚点跨行是常态而非异常。"""
    return " ".join((_ROOT / rel).read_text(encoding="utf-8").split())


@pytest.mark.parametrize("rel", sorted(_DOC_LATENT_ANCHORS))
def test_46j_docs_state_latent_counts_that_match_the_machine(rel, boot_latent):
    n, g = len(boot_latent), sum(boot_latent.values())
    assert (n, g) == (24, 32), "46f 的名集口径变了，本条锚点需同步取证"
    flat = _flat(rel)
    for tmpl in _DOC_LATENT_ANCHORS[rel]:
        assert tmpl.format(n=n, g=g) in flat, f"{rel} 的 latent 口径与实测不符：{tmpl}"
    for stale in _HISTORICAL_READINGS:
        if stale in flat:
            assert _ATTRIBUTION_POINTER in flat, (
                f"{rel} 写了时点读数「{stale}」却没有「{_ATTRIBUTION_POINTER}」归因指针")


# ==================== 46i 面分歧如实登记 ====================


def test_46i_to_upper_is_chain_face_only_host_has_no_carrier():
    """`to_upper` 只在链面注册面存在：宿主 `src/**` 零载体，hi 面仍点名未定义。

    41-①（链面注册内建表 vs 宿主表差）的新成员——本片只修真缺陷，不扩宿主表。
    分派臂与 `stdlib.matha` 内建表条目同时锁在位，否则 46b 的真读数无意义。
    """
    from src.interp import BUILTINS as HOST_BASE_BUILTINS
    from src.interp import interpret

    assert 'name = "to_upper" ? 标准库.to_upper(num_to_str(args[0])) :' in _INTERP_MATHA_TXT
    assert '"to_upper": to_upper,' in _STDLIB_TXT
    assert "to_upper" not in HOST_BASE_BUILTINS
    host_hits = [p.relative_to(_ROOT).as_posix() for p in (_ROOT / "src").rglob("*.py")
                 if "to_upper" in p.read_text(encoding="utf-8", errors="replace")]
    assert host_hits == [], f"宿主已补 to_upper 载体，本条登记需重新取证：{host_hits}"
    with pytest.raises(Exception) as ei:
        interpret('输出(to_upper("aB"))\n')
    assert "未定义变量 'to_upper'" in str(ei.value)
