# -*- coding: utf-8 -*-
"""阶段 5 第 3 项：文档如实化（数字与代码不许漂移）。

重构前 README / MATHA_COMPARISON 里写着「通过率 100%」「综合评分 9.0/10」
「87+ 领域模块」「缺陷已解决 271/271」「五个维度全部 10/10」——全是手写的
**愿望**，与仓库里真实存在的东西无关，也没人能复现。本文件把它变成机器判定：

  1. 权威文档（README / MATHA_COMPARISON / docs/ARCHITECTURE / docs/index /
     docs/KNOWN_ISSUES / docs/CHANGELOG）里出现的每个数字都必须等于
     `scripts/repo_facts.py` 现场数出来的值；
  2. 自评类脏词（评分 / 满分 / 「缺陷已全部解决」的具体数字形式）一律禁止出现；
  3. `docs/` 顶层文档数量受控（≤ 10 份现状文档，其余进 `docs/history/`）；
  4. 主执行链那句话必须在架构文档里 —— 文档不能悄悄改口。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from scripts.repo_facts import facts  # noqa: E402

DOCS = ROOT / "docs"
README = (ROOT / "README.md").read_text(encoding="utf-8")
COMPARISON = (ROOT / "MATHA_COMPARISON.md").read_text(encoding="utf-8")
ARCH = (DOCS / "ARCHITECTURE.md").read_text(encoding="utf-8")
INDEX = (DOCS / "index.md").read_text(encoding="utf-8")
ISSUES = (DOCS / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
CHANGELOG = (DOCS / "CHANGELOG.md").read_text(encoding="utf-8")

#: 这些旧口径是「愿望数字」，任何时候回到文档里都算造假
FORBIDDEN_CLAIMS = (
    "9.0/10", "10/10", "全维度", "87+", "46+", "271/271", "缺陷已解决",
    "128/128", "21/21", "1157", "通过率：100%", "通过率：** 100%",
    "综合评分",
)
#: 允许逐条出现的例外：KNOWN_ISSUES 里以判据形式引用的旧值（采样逼近那一条）
FORBIDDEN_DOCS = {
    "README.md": README,
    "MATHA_COMPARISON.md": COMPARISON,
    "docs/ARCHITECTURE.md": ARCH,
    "docs/index.md": INDEX,
    "docs/CHANGELOG.md": CHANGELOG,
}

MAINLINE = "src/lexer.py → src/parser.py → src/ast_nodes.py"

_VER_TOKEN_RE = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b")


def test_no_wish_number_claims_survive():
    bad = []
    for name, txt in FORBIDDEN_DOCS.items():
        for tok in FORBIDDEN_CLAIMS:
            if tok in txt:
                bad.append(f"{name}: {tok}")
    assert not bad, "现状文档里仍有自评/愿望数字：\n" + "\n".join(sorted(bad))


@pytest.mark.parametrize("key,token", [
    ("domain_plugins", "**领域插件：** {v}"),
    ("golden_cases", "**黄金用例：** {v}"),
    ("matha_files", "**`.matha` 语料：** {v}"),
    ("test_files", "**测试文件：** {v}"),
    ("kernel_plugins", "**内核外工具插件：** {v}"),
])
def test_readme_numbers_match_the_repo(key, token):
    v = facts()[key]
    assert token.format(v=v) in README, f"README 里找不到 {token.format(v=v)}"


def test_readme_declares_zero_third_party_deps_and_pinned_version():
    f = facts()
    assert f["third_party_deps"] == []
    assert "**核心安装第三方依赖：** 0" in README
    assert f"**版本：** v{f['version']}" in README, "README 版本必须来自唯一版本源"


def test_readme_corpus_gap_is_stated_not_hidden():
    """158 个语料 / 19 个解析失败必须写成两个数，只报前者就是粉饰。"""
    matrix = json.loads((DOCS / "ast_vm_gap.json").read_text(encoding="utf-8"))
    n_fail = len(matrix["unparseable"])
    assert f"**`.matha` 语料：** {facts()['matha_files']}" in README
    assert f"{n_fail} 个属语法层遗留" in README, "README 未如实标注语料解析失败数"


def test_architecture_keeps_the_single_mainline():
    assert MAINLINE in ARCH
    assert "src/mbc/compiler.py → src/mbc/vm.py" in ARCH
    # 归档/删除的后端必须被点名，不许含糊成「多后端并行」
    for gone in ("legacy_mir_vm", "m3v_vm", "mir_opt"):
        assert gone in ARCH, f"架构文档未说明 {gone} 的去向"
    assert "`src/kernel/math_builtin.py`" in ARCH and "`src/kernel/regex_builtin.py`" in ARCH


def test_architecture_numbers_match_repo_facts():
    f = facts()
    assert f"{f['core_py_lines']:,} 行" in ARCH, "架构文档的核心体量已过期"
    assert f"{f['domain_plugins']} 个领域插件" in ARCH


def test_docs_top_level_stays_authoritative_and_small():
    top = sorted(p.name for p in DOCS.glob("*.md"))
    assert len(top) <= 10, f"现状文档超量，请把一次性报告移进 docs/history/：{top}"
    for must in ("index.md", "ARCHITECTURE.md", "DEP_BASELINE.md", "ast_vm_gap.md",
                 "symbolic_parity.md", "matha_stdlib_symbolic.md", "KNOWN_ISSUES.md"):
        assert must in top, f"权威文档缺失 {must}"
    assert (DOCS / "history").is_dir() and (DOCS / "spec").is_dir()


def test_index_lists_every_authoritative_doc():
    for p in sorted(DOCS.glob("*.md")):
        assert p.name in INDEX or p.name == "index.md", f"docs/index.md 漏了 {p.name}"


def test_known_issues_still_has_real_gaps():
    """「已知问题」文档如果变成空话，就说明有人在粉饰太平。"""
    assert "NI-001" in ISSUES and "NI-002" in ISSUES
    assert "native_known_gaps" in ISSUES
    matrix = json.loads((DOCS / "ast_vm_gap.json").read_text(encoding="utf-8"))
    assert str(len(matrix["unparseable"])) in ISSUES, "未如实写出语料解析失败数"


def test_no_stale_doc_files_left_at_root():
    """根目录只留面向读者的文档，报告类一律进 docs/。"""
    allowed = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
               "MATHA_COMPARISON.md", "PUBLISH.md", "SECURITY.md", "LICENSE"}
    stray = sorted(p.name for p in ROOT.glob("*.md") if p.name not in allowed)
    assert not stray, f"根目录仍有历史报告未归档：{stray}"


def test_version_token_appears_only_as_current_in_docs():
    from src.__version__ import __version__ as v  # noqa: F401
    # README 以 `v4.6.0` 的形式写版本，故不前置 \b（仍要求版本数字后接边界）
    assert re.search(rf"{re.escape(v)}\b", README), "README 未写当前版本"
    assert not re.search(r"\bv4\.3\b|\bv4\.4\b|\bv4\.5\b", README)


#: CHANGELOG 里只允许两个特殊形式存在旧版本号：历史条目标题（docs/index.md
#: 声明过「旧版本号只允许出现在这里」）与本文件的「规矩」声明行。
_CHANGELOG_VERSION_LINE_OK = re.compile(r"^#{1,3} |^> ")


def test_changelog_current_entry_matches_single_version_source():
    """CHANGELOG 当前版本条目必须等于唯一版本源，且不得多出一个现行条目。"""
    import importlib

    ver = importlib.import_module("src.__version__")
    assert f"## v{ver.__version__}（" in CHANGELOG, \
        f"CHANGELOG 缺少与唯一版本源一致的当前条目标题 v{ver.__version__}"
    n_current = len(re.findall(rf"^## v{re.escape(ver.__version__)}（", CHANGELOG, re.M))
    assert n_current == 1, f"现行版本条目应恰好 1 个，实际 {n_current}"


def test_changelog_numbers_match_repo_facts():
    """CHANGELOG 正文的可复现数字不许与仓库现场漂移（漂移即红）。"""
    f = facts()
    locked = {
        "**领域插件：** 条目 {domain_plugins} 个领域插件": f"**{f['domain_plugins']} 个领域插件**",
        "工具插件 kernel_plugins": f"**{f['kernel_plugins']} 个内核外工具插件**",
        "黄金用例 golden_cases": f"黄金用例 **{f['golden_cases']}** 例",
        "native 已知缺口 golden_native_gaps": f"已知缺口 **{f['golden_native_gaps']}** 例",
        "标准库 matha_library_files": f"（{f['matha_library_files']} 个 `.matha` 文件",
    }
    bad = [f"{what} -> 应含 {tok!r}" for what, tok in locked.items() if tok not in CHANGELOG]
    assert not bad, "CHANGELOG 数字与 repo_facts 漂移：\n" + "\n".join(bad)
    # 核心安装零第三方依赖是版本源同源声明，不能漂回非 0
    assert f["third_party_deps"] == []
    assert "核心安装第三方依赖 **0**" in CHANGELOG


def test_changelog_old_versions_only_in_entry_headings_and_rules():
    """旧版本号（与唯一版本源不同的 vX.Y）只允许出现在条目标题与规矩声明行。"""
    import importlib

    want = f"v{importlib.import_module('src.__version__').__version__}"
    bad = []
    for line in CHANGELOG.splitlines():
        for tok in set(_VER_TOKEN_RE.findall(line)):
            if tok != want and not _CHANGELOG_VERSION_LINE_OK.match(line):
                bad.append(f"{tok}: {line.strip()[:60]}")
    assert not bad, "旧版本号离开了条目标题/规矩声明行：\n" + "\n".join(bad)
