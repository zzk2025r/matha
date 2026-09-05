# Matha 工作空间安装脚本（PowerShell）
# 使用示例：
#   .\scripts\setup_workspace.ps1
#   .\scripts\setup_workspace.ps1 -DevPath "D:\trae"
#   .\scripts\setup_workspace.ps1 -Force

param(
    [string]$DevPath = "",
    [switch]$Force,
    [switch]$SkipDev,
    [switch]$SkipIDE,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Version = "4.4.57"
$RepoURL = "git@github.com:zzk2025r/matha.git"
$RepoURLHTTPS = "https://github.com/zzk2025r/matha.git"
$MathaHome = if ($env:MATHA_HOME) { $env:MATHA_HOME } else { "$env:USERPROFILE\.matha-home" }

function Log($msg) {
    if (-not $Quiet) { Write-Host $msg }
}

Log ""
Log "=========================================="
Log "  Matha 工作空间安装器 v$Version"
Log "=========================================="
Log ""
Log "目标目录: $MathaHome"

# 检查已存在
if (Test-Path $MathaHome -and -not $Force) {
    $existing = Get-ChildItem $MathaHome -ErrorAction SilentlyContinue
    if ($existing) {
        Log ""
        Log "  [信息] 工作空间已存在: $MathaHome"
        Log "  要重新安装，请添加 -Force 参数"
        Log ""
        Log "当前内容:"
        foreach ($item in $existing) {
            Log "  - $($item.Name)"
        }
        exit 0
    }
}

# 创建根目录
New-Item -ItemType Directory -Path $MathaHome -Force | Out-Null

# matha-home.json
$homeConfig = @{
    matha_home    = $MathaHome
    version       = $Version
    client_dir    = "$MathaHome\client"
    dev_dir       = "$MathaHome\dev"
    workspace_dir = "$MathaHome\workspace"
    ide_dir       = "$MathaHome\MathaIDE"
    github_repo   = $RepoURL
    created_at    = (Get-Date).ToString("o")
}
$homeConfig | ConvertTo-Json -Depth 3 | Out-File "$MathaHome\matha-home.json" -Encoding UTF8

# ── 创建 client（使用端）─────────────────────────────────────
$clientDir = "$MathaHome\client"
New-Item -ItemType Directory -Path $clientDir -Force | Out-Null
$subdirs = @("src/compiler","src/domains","src/stdlib","src/intent",
             "src/jupyter","src/hardware","docs","config")
foreach ($sub in $subdirs) {
    New-Item -ItemType Directory -Path "$clientDir\$sub" -Force | Out-Null
}
Log "  ✓ 创建使用端: $clientDir"

# config.json
$clientConfig = @{
    version                 = $Version
    name                    = "Matha"
    description             = "自举式领域专用编程语言"
    auto_update             = $true
    update_interval_hours   = 24
    github_repo             = $RepoURL
    github_repo_https       = $RepoURLHTTPS
    branch                  = "main"
    language                = $env:MATHA_LANG ?? "zh-CN"
    ide_enabled             = $true
    ssl_backend             = "schannel"
    http_version            = "HTTP/1.1"
}
$clientConfig | ConvertTo-Json -Depth 3 | Out-File "$clientDir\config.json" -Encoding UTF8

# update.py
$updateScript = @'
"""Matha 自举更新器 - 从 GitHub 或开发端更新使用端"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

VERSION = "4.4.57"
REPO_URL = "git@github.com:zzk2025r/matha.git"
REPO_URL_HTTPS = "https://github.com/zzk2025r/matha.git"
CLIENT_DIR = Path(__file__).parent
CONFIG_FILE = CLIENT_DIR / "config.json"

def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}

def save_config(c): CONFIG_FILE.write_text(json.dumps(c, indent=2), encoding="utf-8")

def get_latest_tag():
    for url in [REPO_URL, REPO_URL_HTTPS]:
        try:
            r = subprocess.run(["git","ls-remote","--tags","--refs",url,"refs/tags/v*"],
                             capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                tags = [l.split("/")[-1] for l in r.stdout.strip().split("\n") if l.strip()]
                if tags: return sorted(tags)[-1]
        except: pass
    return None

def update_from_github():
    temp = Path(tempfile.mkdtemp(prefix="matha_up_"))
    try:
        for url in [REPO_URL, REPO_URL_HTTPS]:
            r = subprocess.run(["git","clone","--depth","1",url,str(temp)],
                             capture_output=True, timeout=60)
            if r.returncode == 0: break
        else:
            print("  ✗ 无法连接 GitHub"); return False
        src_src = temp/"src"; dst_src = CLIENT_DIR/"src"
        if src_src.exists():
            if dst_src.exists(): shutil.rmtree(dst_src)
            shutil.copytree(src_src, dst_src)
        src_docs = temp/"docs"; dst_docs = CLIENT_DIR/"docs"
        if src_docs.exists():
            if dst_docs.exists(): shutil.rmtree(dst_docs)
            shutil.copytree(src_docs, dst_docs)
        cfg = load_config(); latest = get_latest_tag()
        if latest: cfg["version"] = latest; save_config(cfg)
        print(f"  ✓ 更新成功: {cfg.get('version', VERSION)}")
        return True
    finally:
        if temp.exists(): shutil.rmtree(temp, ignore_errors=True)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--from-dev", help="从开发端更新"); p.add_argument("--check", action="store_true")
    a = p.parse_args(); cfg = load_config()
    cur = cfg.get("version", VERSION)
    if a.check:
        latest = get_latest_tag()
        if latest and latest != cur:
            print(f"  新版本: {latest} (当前: {cur})")
            print("  运行 python update.py 更新")
        else: print(f"  已是最新: {cur}")
    elif a.from_dev:
        src = Path(a.from_dev)/"src"
        dst = CLIENT_DIR/"src"
        if src.exists():
            if dst.exists(): shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  ✓ 从开发端更新完成: {a.from_dev}")
    else:
        print("  从 GitHub 更新...")
        update_from_github()
'@
$updateScript | Out-File "$clientDir\update.py" -Encoding UTF8

# README
$readme = @"
# Matha 使用端

**版本：** $Version
**工作空间：** $clientDir

## 快速开始

\`\`\`powershell
# 启动 REPL
python -m src.matha_main

# 或使用快捷命令
matha
\`\`\`

## 目录结构

- \`src/\` — 只读源码（随版本更新）
- \`docs/\` — 离线文档
- \`config.json\` — 使用端配置
- \`update.py\` — 自举更新器

## 更新

\`\`\`powershell
# 检查更新
python update.py --check

# 手动更新
python update.py
\`\`\`
"@
$readme | Out-File "$clientDir\README.md" -Encoding UTF8

# ── 创建 workspace（用户工作区）─────────────────────────────
$workspaceDir = "$MathaHome\workspace"
New-Item -ItemType Directory -Path "$workspaceDir\projects" -Force | Out-Null
New-Item -ItemType Directory -Path "$workspaceDir\formulas" -Force | Out-Null
New-Item -ItemType Directory -Path "$workspaceDir\notebooks" -Force | Out-Null
New-Item -ItemType Directory -Path "$workspaceDir\.matha_cache\python" -Force | Out-Null
New-Item -ItemType Directory -Path "$workspaceDir\.matha_cache\rust" -Force | Out-Null
Log "  ✓ 创建工作区: $workspaceDir"

# ── 创建 dev（更新端）───────────────────────────────────────
$devDir = "$MathaHome\dev"
if (-not $SkipDev) {
    if ($DevPath -and (Test-Path $DevPath)) {
        # 尝试符号链接
        try {
            if (Test-Path $devDir) {
                if (Test-Path $devDir -PathType Leaf) { Remove-Item $devDir -Force }
                else { Remove-Item $devDir -Recurse -Force }
            }
            cmd /c mklink /D "`"$devDir`" `"$DevPath`"" 2>&1 | Out-Null
            Log "  ✓ 符号链接: $devDir -> $DevPath"
        } catch {
            Log "  [警告] 符号链接失败，创建空目录"
            New-Item -ItemType Directory -Path $devDir -Force | Out-Null
        }
    } else {
        Log "  尝试克隆开发仓库..."
        $cloneSucceeded = $false
        foreach ($url in @($RepoURL, $RepoURLHTTPS)) {
            try {
                $r = git clone --depth 1 $url $devDir 2>&1
                if ($LASTEXITCODE -eq 0) { $cloneSucceeded = $true; break }
            } catch { continue }
        }
        if (-not $cloneSucceeded) {
            Log "  ! 克隆失败，创建空目录: $devDir"
            New-Item -ItemType Directory -Path $devDir -Force | Out-Null
            "@# Matha 开发端`n`n请先克隆仓库：`n`` powershell`ngit clone $RepoURL`n```"@ | Out-File "$devDir\README.md" -Encoding UTF8
        } else {
            Log "  ✓ 已克隆到: $devDir"
        }
    }
} else {
    New-Item -ItemType Directory -Path $devDir -Force | Out-Null
    Log "  跳过更新端创建（--skip-dev）"
}

# ── 创建 Matha IDE（自举开发环境）────────────────────────────
$ideDir = "$MathaHome\MathaIDE"
New-Item -ItemType Directory -Path "$ideDir\matha_ide\themes" -Force | Out-Null
New-Item -ItemType Directory -Path "$ideDir\matha_ide\extensions" -Force | Out-Null
New-Item -ItemType Directory -Path "$ideDir\matha_ide\schemas" -Force | Out-Null
Log "  ✓ 创建 IDE: $ideDir"

# IDE 配置（JSON，任何系统可识别）
$ideConfig = @{
    name        = "Matha IDE"
    version     = $Version
    description = "以 Matha 为基础的开发环境"
    type        = "matha-ide"
    syntax      = @{
        file_extensions = @(".matha")
        lexer           = "src.lexer"
        parser          = "src.parser"
    }
    languages   = @("matha","python","c","rust","go","js")
    features    = @("syntax_highlighting","realtime_diagnostic",
                    "code_completion","formula_editor","version_control","repl")
    auto_update = $true
    update_source = "github"
}
$ideConfig | ConvertTo-Json -Depth 5 | Out-File "$ideDir\matha_ide.json" -Encoding UTF8

# JSON Schema（插件规范，任何 IDE 可识别）
$pluginSchema = @{
    '$schema' = "http://json-schema.org/draft-07/schema#"
    title     = "Matha IDE Plugin Spec"
    type      = "object"
    properties = @{
        name        = @{ type = "string" };
        version     = @{ type = "string" };
        description = @{ type = "string" };
        entry       = @{ type = "string"; description = "Plugin entry file" };
        commands    = @{ type = "array"; items = @{ type = "string" } };
        languages   = @{ type = "array"; items = @{ type = "string" } };
    }
    required = @("name","version","entry")
}
$pluginSchema | ConvertTo-Json -Depth 5 | Out-File "$ideDir\matha_ide\schemas\plugin.schema.json" -Encoding UTF8

# IDE README
$ideReadme = @"
# Matha IDE

**版本：** $Version
**基础：** Matha 自举开发环境

## 设计理念

> **Matha IDE 由 Matha 自身编写，任何系统可识别与使用。**

## 跨系统识别

| 系统 | 识别方式 |
|------|---------|
| VSCode | 安装 .vsix 插件（基于 matha_ide.json） |
| JetBrains | 通过 language plugin 协议 |
| Flutter | 通过 pubspec.yaml 识别 |
| Web | 通过 manifest.json 识别 |
| 任何系统 | 读取 matha_ide.json 配置文件 |

## 文件结构

\`\`\`
MathaIDE/
├── matha_ide.json          ← IDE 配置（JSON，任何系统可读）
├── matha_ide/
│   ├── schemas/            ← JSON Schema 插件规范
│   ├── themes/             ← 语法高亮主题
│   └── extensions/         ← 插件目录
└── README.md
\`\`\`
"@
$ideReadme | Out-File "$ideDir\README.md" -Encoding UTF8

# 更新根配置
$homeConfig = Get-Content "$MathaHome\matha-home.json" -Raw | ConvertFrom-Json
$homeConfig.created_at = (Get-Date).ToString("o")
$homeConfig | ConvertTo-Json -Depth 3 | Out-File "$MathaHome\matha-home.json" -Encoding UTF8

Log ""
Log "=========================================="
Log "  Matha v$Version 工作空间安装完成！"
Log "=========================================="
Log ""
Log "目录结构:"
Log "  $MathaHome/"
Log "  ├── client/      ← 使用端（日常计算/学习）"
Log "  │   ├── src/     ← 只读源码"
Log "  │   ├── docs/    ← 离线文档"
Log "  │   ├── config.json"
Log "  │   └── update.py ← 自举更新器"
Log "  ├── dev/         ← 更新端（开发/测试/升级）"
Log "  ├── workspace/   ← 用户工作区（.matha 文件）"
Log "  │   ├── projects/"
Log "  │   └── formulas/"
Log "  ├── MathaIDE/    ← Matha IDE（自举开发环境）"
Log "  └── matha-home.json ← 工作空间配置"
Log ""
Log "使用方法:"
Log "  cd $clientDir"
Log "  python -m src.matha_main   # 启动 REPL"
Log "  python update.py           # 检查更新"
Log ""
Log "开发者:"
Log "  git clone $RepoURL  # 克隆开发仓库"
Log "  # 或将 $DevPath 符号链接到 $devDir"
Log ""
Log "环境变量:"
Log "  MATHA_HOME=$MathaHome"
Log "  MATHA_LANG=zh-CN           # 可选：设置语言"
Log "=========================================="
