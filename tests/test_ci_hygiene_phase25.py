# -*- coding: utf-8 -*-
"""阶段 25e 卫生锁：CI 零外部凭据面（GITHUB_TOKEN 自生面）。

背景（阶段 25 拍板）：外部凭据（PYPI_TOKEN / VSCE_PAT / OVSX_PAT /
DINGTALK_WEBHOOK/SECRET 等）无法获得。25e 把所有依赖外部凭据的发布/通知
面改为 GitHub 自生路径：
  - PyPI 上传 → upload-artifact / GitHub Release 附件（softprops / gh release
    upload，凭据仅 actions 自动注入的 GITHUB_TOKEN）；
  - VS Marketplace / Open VSX（PAT）→ VSIX 作为 Release 附件；
  - 钉钉通知（webhook+secret）→ $GITHUB_STEP_SUMMARY 写入；
  - 休眠 CD 家族（cd-full.yml / docker_build_push.yml / multilang_benchmark.yml）
    与 .github/configs/（dingtalk_notify.yml / dingtalk_templates.sh）删除；
  - 发行物附件可由 `matha app import-release`（阶段 25d）导入本地应用中心，
    形成「CI 只认 GITHUB_TOKEN → 商店导入」的闭环。

本文件不依赖 PyYAML（与 tests/test_ci_hygiene.py 同约定），用文本扫描钉住：

1. `.github/workflows/*.yml` 中 `secrets.X` 引用白名单 = {GITHUB_TOKEN}；
2. `.github/` 全树 "your-company" 计数 = 0（私有 PyPI 占位域名旧伤）；
3. `.github/` 全树 "dingtalk"（大小写不敏感，ASCII）计数 = 0；
4. 25e 删除的休眠 CD 家族 / 共享配置目录确实不存在；
5. 工作流无 `id-token: write`（OIDC 外部凭据面）且无 `twine upload`
   （外部 registry 上传面）；
6. 被替换的通知面确实写 $GITHUB_STEP_SUMMARY；
7. CI→商店闭环：`matha app import-release` 子命令与引擎处理函数真实存在。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"

#: 唯一允许的 secret：actions 自动注入的 GITHUB_TOKEN（自生面）
SECRETS_WHITELIST = {"GITHUB_TOKEN"}

#: 25e 删除的文件（负存在断言）
DELETED_PATHS = [
    ".github/workflows/cd-full.yml",
    ".github/workflows/docker_build_push.yml",
    ".github/workflows/multilang_benchmark.yml",
    ".github/configs",
]

#: 通知面被替换成 Step Summary 的工作流
STEP_SUMMARY_REQUIRED = ["benchmark.yml", "stress_test.yml", "release.yml"]


def _workflow_names() -> list[str]:
    return sorted(p.name for p in WF_DIR.glob("*.yml"))


def _workflow_text(name: str) -> str:
    return (WF_DIR / name).read_text(encoding="utf-8")


def _github_tree_texts() -> list[tuple[str, str]]:
    out = []
    for p in sorted((ROOT / ".github").rglob("*")):
        if p.is_file():
            try:
                out.append((str(p.relative_to(ROOT)), p.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                out.append((str(p.relative_to(ROOT)), ""))
    return out


def test_secrets_whitelist_github_token_only():
    """工作流中所有 secrets.X 引用必须 ∈ {GITHUB_TOKEN}——零用户 secrets。"""
    bad = []
    for name in _workflow_names():
        for m in re.finditer(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", _workflow_text(name)):
            if m.group(1) not in SECRETS_WHITELIST:
                bad.append(f"{name}: secrets.{m.group(1)}")
    assert not bad, "工作流引用了白名单之外的 secrets：\n" + "\n".join(bad)


def test_no_placeholder_registry_domain_in_github_tree():
    """.github/ 全树不得出现私有 PyPI 占位域名（your-company）。"""
    hits = [rel for rel, text in _github_tree_texts() if "your-company" in text]
    assert not hits, "your-company 占位域名残留：\n" + "\n".join(hits)


def test_no_dingtalk_in_github_tree():
    """.github/ 全树不得出现 dingtalk（ASCII，大小写不敏感）——钉钉通知面
    已整体删除（中文「钉钉」注释不算，锁的是引用面：secrets/脚本/配置）。"""
    hits = [rel for rel, text in _github_tree_texts() if re.search(r"dingtalk", text, re.I)]
    assert not hits, "dingtalk 引用残留：\n" + "\n".join(hits)


def test_deleted_dormant_cd_family_absent():
    """25e 删除的休眠 CD 家族与共享配置目录必须真的不存在。"""
    still = [rel for rel in DELETED_PATHS if (ROOT / rel).exists()]
    assert not still, "声明已删除的路径仍存在：\n" + "\n".join(still)


def test_no_oidc_id_token_and_no_external_registry_upload():
    """无 id-token: write（OIDC 外部凭据面）且无 twine upload（外部 registry
    上传面）——发布一律走 GitHub Release 附件。"""
    bad = []
    for name in _workflow_names():
        text = _workflow_text(name)
        if re.search(r"^\s*id-token:\s*write\s*$", text, re.M):
            bad.append(f"{name}: id-token: write")
        if re.search(r"^\s*twine\s+upload\b", text, re.M):
            bad.append(f"{name}: twine upload")
    assert not bad, "外部凭据/外部 registry 发布面残留：\n" + "\n".join(bad)


def test_replaced_notifications_write_step_summary():
    """被替换的钉钉通知工作流必须真的写 $GITHUB_STEP_SUMMARY——
    删除通知面不允许退化成「静默无摘要」。"""
    missing = []
    for name in STEP_SUMMARY_REQUIRED:
        if "GITHUB_STEP_SUMMARY" not in _workflow_text(name):
            missing.append(name)
    assert not missing, "通知面替换后缺 Step Summary 写入：\n" + "\n".join(missing)


def test_store_import_release_closure_exists():
    """CI→商店闭环面：`matha app import-release` 子命令（注册表）与
    cmd_import_release（实现）必须存在——Release 附件导入应用中心的路由。"""
    main_text = (ROOT / "src" / "matha_main.py").read_text(encoding="utf-8")
    assert "import-release" in main_text, "matha_main.py 未注册 app import-release 子命令"
    cli_text = (ROOT / "src" / "app_cli.py").read_text(encoding="utf-8")
    assert "def cmd_import_release" in cli_text, "app_cli.py 缺 cmd_import_release 实现"
