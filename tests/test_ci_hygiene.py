# -*- coding: utf-8 -*-
"""CI 配置卫生门禁 —— 把 2026-11 那轮红 CI 取证得到的四类形态变成机器判定。

取证结论（逐条来自 `gh run view --log-failed` 与 `git ls-files` 实测）：

1. `.github/workflows/cd-full.yml` 的 Black 步骤把 shell 写成**多行纯量**，
   值里带未引号包裹的 `echo "::error::…: black …"`，YAML 直接报
   `mapping values are not allowed here`；
2. `.github/workflows/stress_test.yml` 把 `strategy:` 挂在**工作流顶层**
   （该键只允许出现在 job 下）；
3. `.github/workflows/release.yml` 的步骤**同时写了 `uses:` 和 `run:`**
   （一个步骤只能有其一），GitHub 判整文件无效；
4. 多份工作流引用**仓库里不存在的文件/模块**（`src/vm.py`、
   `tests/test_hal_v2.py`、`scripts/benchmark_rust.py`、`--output-dir` 等），
   跑起来只会红。

前 1-3 类的共同表征是：Actions 列表里显示名回退成文件路径、jobs=0、历史连续
failure —— 也就是说「文件被整体拒绝」比「某一步失败」更隐蔽。本文件不依赖
PyYAML（核心安装第三方依赖必须保持 0），用行/缩进扫描把这四类形态钉住。

约定：`ACTIVE_WORKFLOWS` 是唯一的权威回归门（数学内核单测 + lint + native ELF
实跑对拍 + packages 冒烟），只有它们允许 push / pull_request 触发；其余工作流
一律只能 workflow_dispatch（或 tag），且必须写明休眠证据（`DORMANT_MARKER`）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"

#: 允许被 push / pull_request 自动触发的工作流（权威回归门），缺一即视为门禁被削弱
ACTIVE_WORKFLOWS = {"matha-ci.yml", "ci.yml"}

#: GitHub Actions 允许的顶层键；`strategy` / `steps` 之类只能待在 job 里
TOP_LEVEL_KEYS = {
    "name", "on", "env", "permissions", "concurrency", "defaults", "jobs", "run-name",
}

#: 非权威工作流必须携带的证据标记（为什么休眠、根因是什么）
DORMANT_MARKER = "ci-hygiene"

#: run: 里允许「不存在」的产物/临时目录前缀（构建输出，不是仓库文件）
_BUILD_OUTPUT_PREFIXES = (
    "dist/", "build/", ".benchmarks/", "offline_pkg/", "htmlcov/", ".coverage",
    "packages/dist/", "benchmark_", "RELEASE_NOTES_",
)

_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|spec|sh|json|txt|md)\b")


def _files() -> list[str]:
    return sorted(p.name for p in WF_DIR.glob("*.yml"))


def _raw(name: str) -> str:
    return (WF_DIR / name).read_text(encoding="utf-8")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _block_scalar_mask(lines: list[str]) -> list[bool]:
    """标出属于块纯量（`run: |` / `>`）正文的行，扫描时必须跳过它们。"""
    mask = [False] * len(lines)
    head = re.compile(
        r"^(\s*)[\w-]+:\s*[|>][-+]?\d*[-+]?\s*(?:#.*)?$")
    i = 0
    while i < len(lines):
        m = head.match(lines[i])
        if m:
            key_indent = len(m.group(1))
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > key_indent):
                mask[j] = True
                j += 1
            i = j
            continue
        i += 1
    return mask


def _sequence_item_keys(lines: list[str], mask: list[bool]) -> list[tuple[int, int, set[str]]]:
    """返回每个序列项的 (行号, 子键缩进, 该项目的 mapping 键集合)。

    步骤项形如 `- name:` / `- uses:` / `- run:`；`with:` / `branches:` 下的标量
    列表项没有 mapping 键，天然不会误判。
    """
    out = []
    item_re = re.compile(r"^(\s*)-\s+")
    for i, line in enumerate(lines):
        if mask[i] or not line.strip():
            continue
        m = item_re.match(line)
        if not m:
            continue
        child_indent = len(m.group(0))
        keys: set[str] = set()
        first = line[child_indent:]
        km = re.match(r"([\w-]+):", first)
        if km:
            keys.add(km.group(1))
        for j in range(i + 1, len(lines)):
            if mask[j] or not lines[j].strip():
                continue
            ind = _indent(lines[j])
            if ind < child_indent or (ind == child_indent and lines[j][child_indent:child_indent + 1] == "-"):
                break
            if ind == child_indent:
                km = re.match(r"([\w-]+):", lines[j][child_indent:])
                if km:
                    keys.add(km.group(1))
        if keys:
            out.append((i, child_indent, keys))
    return out


def _run_bodies(lines: list[str], mask: list[bool]) -> list[str]:
    """取出所有 `run: |` 块纯量正文（块纯量行本身已在 mask 里）。"""
    bodies = []
    for i, line in enumerate(lines):
        if mask[i] or not re.match(r"^\s*run:\s*[|>]", line):
            continue
        body = []
        for j in range(i + 1, len(lines)):
            if not lines[j].strip():
                body.append("")
                continue
            if _indent(lines[j]) <= _indent(line):
                break
            body.append(lines[j])
        bodies.append("\n".join(body))
    return bodies


def test_authoritative_gate_workflows_still_exist():
    """权威回归门不许被删名或改名，否则「红 CI 收敛」会退化成「没有 CI」。"""
    present = set(_files())
    missing = sorted(ACTIVE_WORKFLOWS - present)
    assert not missing, f"权威回归门工作流缺失：{missing}"


def test_workflows_only_use_valid_top_level_keys():
    """`strategy:` 之类只能待在 job 下；出现在顶层说明 GitHub 会整文件拒绝。"""
    bad = []
    for name in _files():
        for key in re.findall(r"^([A-Za-z_][\w-]*):", _raw(name), re.M):
            if key not in TOP_LEVEL_KEYS:
                bad.append(f"{name}: 顶层未知键 {key!r}")
    assert not bad, "工作流顶层出现非法键：\n" + "\n".join(bad)


def test_no_step_mixes_uses_and_run():
    """一个步骤只能有 uses 或 run；同时出现会让整份工作流失效（release.yml 旧伤）。"""
    bad = []
    for name in _files():
        lines = _raw(name).splitlines()
        mask = _block_scalar_mask(lines)
        for lineno, _, keys in _sequence_item_keys(lines, mask):
            if {"uses", "run"} <= keys:
                bad.append(f"{name}:{lineno + 1} 同一步既有 uses 又有 run")
            elif {"run", "with"} <= keys:
                bad.append(f"{name}:{lineno + 1} run 步骤却带 with")
    assert not bad, "步骤结构违规：\n" + "\n".join(bad)


def test_run_blocks_are_block_scalars_not_plain_multiline():
    """多行 shell 必须用块纯量 `run: |`；纯量续行里的 `: ` 会炸掉 YAML 解析
    （cd-full.yml 旧伤：`echo "::error::…: black …"` 让 GitHub 拒绝整文件）。"""
    bad = []
    for name in _files():
        lines = _raw(name).splitlines()
        mask = _block_scalar_mask(lines)
        for i, line in enumerate(lines):
            if mask[i]:
                continue
            m = re.match(r"^(\s*)run:\s*(\S.*)$", line)
            if not m:
                continue
            val = m.group(2).strip()
            if val.startswith(("|", ">", '"', "'")):
                continue
            key_indent = len(m.group(1))
            nxt_idx = next((k for k in range(i + 1, len(lines)) if lines[k].strip()), None)
            if nxt_idx is not None and _indent(lines[nxt_idx]) > key_indent and not mask[nxt_idx]:
                bad.append(f"{name}:{i + 1} run 为多行纯量 -> {val[:48]!r}")
    assert not bad, "存在会被 YAML 拒绝的 run 写法：\n" + "\n".join(bad)


def test_non_authoritative_workflows_are_not_auto_triggered():
    """除权威门外，任何工作流都不许声明 push.branches / pull_request / schedule，
    且必须写明休眠证据；否则 main 上的红会随每次 push 重新长出来。"""
    bad = []
    for name in _files():
        if name in ACTIVE_WORKFLOWS:
            continue
        raw = _raw(name)
        on_block = re.search(r"^on:\n(.*?)(?=^[A-Za-z_][\w-]*:)", raw, re.M | re.S)
        body = on_block.group(1) if on_block else ""
        for pat, why in (
            (r"^\s{2,}branches(-ignore)?:", "push/pull_request 带分支触发"),
            (r"^  pull_request:", "pull_request 触发"),
            (r"^  schedule:", "定时触发"),
        ):
            if re.search(pat, body, re.M):
                bad.append(f"{name}: {why}")
        if DORMANT_MARKER not in raw:
            bad.append(f"{name}: 缺少休眠证据注释（{DORMANT_MARKER}）")
    assert not bad, "非权威工作流仍会污染 main / PR：\n" + "\n".join(bad)


def test_authoritative_workflows_only_reference_existing_paths():
    """权威门里 run 步骤引用的仓库文件必须真实存在（历史上 `src/deps.py`、
    `src/vm.py` 删除后 CI 仍照着调用，只会红）。"""
    bad = []
    for name in ACTIVE_WORKFLOWS:
        lines = _raw(name).splitlines()
        mask = _block_scalar_mask(lines)
        for body in _run_bodies(lines, mask):
            for token in _PATH_TOKEN_RE.findall(body):
                if token.startswith(_BUILD_OUTPUT_PREFIXES) or "$" in token or "*" in token:
                    continue
                if not (ROOT / token).exists():
                    bad.append(f"{name}: {token}")
    assert not bad, "权威门引用了不存在的文件：\n" + "\n".join(sorted(set(bad)))
