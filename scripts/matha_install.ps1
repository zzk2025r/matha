# Matha v4.4.57 一键安装脚本
# 安装至独立文件夹 ~/Matha，包含使用端+开发端+桌面图标

param(
    [switch]$SkipIcons,
    [switch]$SkipDev
)

$ErrorActionPreference = "Stop"
$Version = "4.4.57"
$RepoURL = "git@github.com:zzk2025r/matha.git"
$RepoURLHTTPS = "https://github.com/zzk2025r/matha.git"
$MathaHome = "$env:USERPROFILE\Matha"
$ClientDir = "$MathaHome\client"
$DevDir = "$MathaHome\dev"
$WorkspaceDir = "$MathaHome\workspace"
$IDEDir = "$MathaHome\MathaIDE"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Matha v$Version 安装程序" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "安装目录: $MathaHome"
Write-Host ""

# 1. 清理旧版本
Write-Host "步骤 1/5: 清理旧版本..." -ForegroundColor Yellow
$oldDirs = @("$env:USERPROFILE\Matha_old", "$env:USERPROFILE\.matha")
foreach ($d in $oldDirs) {
    if (Test-Path $d) {
        try { Remove-Item $d -Recurse -Force -ErrorAction Stop; Write-Host "  已清理: $d" -ForegroundColor Green }
        catch { Write-Host "  [跳过] 无法删除: $d (请手动删除)" -ForegroundColor Gray }
    }
}
# 清理开始菜单旧快捷方式
$oldStartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Matha"
if (Test-Path $oldStartMenu) {
    try { Remove-Item $oldStartMenu -Recurse -Force; Write-Host "  已清理开始菜单快捷方式" -ForegroundColor Green }
    catch { Write-Host "  [跳过] 开始菜单快捷方式" -ForegroundColor Gray }
}

# 2. 创建工作空间
Write-Host "步骤 2/5: 创建工作空间..." -ForegroundColor Yellow
@(
    "$MathaHome\client\src\compiler",
    "$MathaHome\client\src\domains",
    "$MathaHome\client\src\stdlib",
    "$MathaHome\client\src\intent",
    "$MathaHome\client\src\jupyter",
    "$MathaHome\client\src\hardware",
    "$MathaHome\client\docs",
    "$MathaHome\workspace\projects",
    "$MathaHome\workspace\formulas",
    "$MathaHome\MathaIDE\matha_ide\themes",
    "$MathaHome\MathaIDE\matha_ide\extensions"
) | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
Write-Host "  ✓ $MathaHome" -ForegroundColor Green

# 3. 克隆开发端
if (-not $SkipDev) {
    Write-Host "步骤 3/5: 克隆开发端..." -ForegroundColor Yellow
    if (Test-Path $DevDir) { Remove-Item $DevDir -Recurse -Force }
    $cloned = $false
    foreach ($url in @($RepoURL, $RepoURLHTTPS)) {
        $r = git clone --depth 1 $url $DevDir 2>&1
        if ($LASTEXITCODE -eq 0) { $cloned = $true; break }
    }
    if (-not $cloned) {
        New-Item -ItemType Directory -Path $DevDir -Force | Out-Null
        "# Matha 开发端`n请先克隆: git clone $RepoURL`n" | Out-File "$DevDir\README.md" -Encoding UTF8
        Write-Host "  ! 克隆失败，请手动克隆到 $DevDir" -ForegroundColor Gray
    } else {
        Write-Host "  ✓ 开发端: $DevDir" -ForegroundColor Green
    }
} else {
    New-Item -ItemType Directory -Path $DevDir -Force | Out-Null
    Write-Host "  跳过开发端（--skip-dev）" -ForegroundColor Gray
}

# 4. 复制使用端源码
Write-Host "步骤 4/5: 复制使用端源码..." -ForegroundColor Yellow
$srcSrc = "$DevDir\src"
if (Test-Path $srcSrc) {
    $dstSrc = "$ClientDir\src"
    if (Test-Path $dstSrc) { Remove-Item $dstSrc -Recurse -Force }
    Copy-Item $srcSrc -Destination $dstSrc -Recurse -Force
    $pyCount = (Get-ChildItem $dstSrc -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "  ✓ 使用端: $pyCount 个 Python 文件 → $ClientDir\src" -ForegroundColor Green
} else {
    Write-Host "  ! 开发端源码不可用，使用端将为空" -ForegroundColor Gray
}

# 复制文档
$srcDocs = "$DevDir\docs"
if (Test-Path $srcDocs) {
    $dstDocs = "$ClientDir\docs"
    Copy-Item "$srcDocs\*.md" -Destination $dstDocs -Force -ErrorAction SilentlyContinue
}

# 复制测试
$dstTests = "$ClientDir\tests"
New-Item -ItemType Directory -Path $dstTests -Force | Out-Null
@("test_matha_growth.py", "test_unified_layers.py", "test_matha_compiler.py") | ForEach-Object {
    $s = "$DevDir\tests\$_"
    if (Test-Path $s) { Copy-Item $s -Destination $dstTests -Force }
}

# 创建 update.py
$updateScript = @"
"""Matha 自举更新器 v$Version"""
from pathlib import Path
import subprocess, json, tempfile, shutil

CLIENT = Path(r"$ClientDir")
CONFIG = CLIENT / "config.json"
REPO = "$RepoURL"
REPO_HTTPS = "$RepoURLHTTPS"

def update():
    temp = Path(tempfile.mkdtemp(prefix="matha_up_"))
    try:
        for url in [REPO, REPO_HTTPS]:
            r = subprocess.run(["git","clone","--depth","1",url,str(temp)],capture_output=True,timeout=60)
            if r.returncode == 0: break
        else:
            print("无法连接 GitHub"); return False
        src_src = temp/"src"; dst_src = CLIENT/"src"
        if src_src.exists():
            if dst_src.exists(): shutil.rmtree(dst_src)
            shutil.copytree(src_src, dst_src)
        src_docs = temp/"docs"; dst_docs = CLIENT/"docs"
        if src_docs.exists():
            if dst_docs.exists(): shutil.rmtree(dst_docs)
            shutil.copytree(src_docs, dst_docs)
        print("更新成功!")
        return True
    finally:
        if temp.exists(): shutil.rmtree(temp, ignore_errors=True)

if __name__ == "__main__":
    update()
"@
($updateScript + "`n").ToCharArray() | ForEach-Object { $_ } | Out-File "$ClientDir\update.py" -Encoding UTF8

# 创建 config.json
$config = @{
    version           = $Version
    name              = "Matha"
    auto_update       = $true
    update_interval   = 24
    client_dir        = $ClientDir
    dev_dir           = $DevDir
    workspace_dir     = $WorkspaceDir
    ide_dir           = $IDEDir
    github_repo       = $RepoURL
    installed_at      = (Get-Date).ToString("o")
}
$config | ConvertTo-Json -Depth 5 | Out-File "$ClientDir\config.json" -Encoding UTF8
$config | ConvertTo-Json -Depth 5 | Out-File "$MathaHome\matha-home.json" -Encoding UTF8
Write-Host "  ✓ 配置已创建" -ForegroundColor Green

# 5. 创建桌面快捷方式
if (-not $SkipIcons) {
    Write-Host "步骤 5/5: 创建桌面快捷方式..." -ForegroundColor Yellow
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $WshShell = New-Object -ComObject WScript.Shell

    # REPL 快捷方式
    $lnk1 = $WshShell.CreateShortcut("$Desktop\Matha REPL.lnk")
    $lnk1.TargetPath = "python.exe"
    $lnk1.Arguments = "-m src.matha_main"
    $lnk1.WorkingDirectory = $ClientDir
    $lnk1.Description = "Matha REPL 交互式编程环境"
    $lnk1.Save()

    # 编译器快捷方式
    $lnk2 = $WshShell.CreateShortcut("$Desktop\Matha 编译器.lnk")
    $lnk2.TargetPath = "python.exe"
    $lnk2.Arguments = "-m src.compiler.matha_cc_cli"
    $lnk2.WorkingDirectory = $ClientDir
    $lnk2.Description = "Matha 编译器工具"
    $lnk2.Save()

    # 打开目录快捷方式
    $lnk3 = $WshShell.CreateShortcut("$Desktop\Matha 安装目录.lnk")
    $lnk3.TargetPath = $MathaHome
    $lnk3.Save()

    Write-Host "  ✓ 桌面快捷方式: Matha REPL / Matha 编译器 / Matha 安装目录" -ForegroundColor Green
}

# 创建开始菜单
$StartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Matha"
if (-not (Test-Path $StartMenu)) { New-Item -ItemType Directory -Path $StartMenu -Force | Out-Null }
$WshShell = New-Object -ComObject WScript.Shell
$WshShell.CreateShortcut("$StartMenu\Matha REPL.lnk").TargetPath = "python.exe"
$WshShell.CreateShortcut("$StartMenu\Matha REPL.lnk").Arguments = "-m src.matha_main"
$WshShell.CreateShortcut("$StartMenu\Matha REPL.lnk").WorkingDirectory = $ClientDir
$WshShell.CreateShortcut("$StartMenu\Matha REPL.lnk").Save()
$WshShell.CreateShortcut("$StartMenu\Matha 编译器.lnk").TargetPath = "python.exe"
$WshShell.CreateShortcut("$StartMenu\Matha 编译器.lnk").Arguments = "-m src.compiler.matha_cc_cli"
$WshShell.CreateShortcut("$StartMenu\Matha 编译器.lnk").WorkingDirectory = $ClientDir
$WshShell.CreateShortcut("$StartMenu\Matha 编译器.lnk").Save()
$WshShell.CreateShortcut("$StartMenu\打开安装目录.lnk").TargetPath = $MathaHome
$WshShell.CreateShortcut("$StartMenu\打开安装目录.lnk").Save()

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Matha v$Version 安装完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "目录结构:"
Write-Host "  $MathaHome/"
Write-Host "  ├── client/      ← 使用端（日常计算/学习）"
Write-Host "  │   ├── src/     ← 242 个 Python 文件"
Write-Host "  │   ├── docs/    ← 134 个文档"
Write-Host "  │   ├── tests/   ← 测试套件"
Write-Host "  │   ├── config.json"
Write-Host "  │   └── update.py ← 自举更新器"
Write-Host "  ├── dev/         ← 更新端（开发/测试/升级）"
Write-Host "  ├── workspace/   ← 用户工作区（.matha 项目）"
Write-Host "  ├── MathaIDE/    ← 自举开发环境（JSON 可识别）"
Write-Host "  └── matha-home.json ← 工作空间配置"
Write-Host ""
Write-Host "使用方法:"
Write-Host "  cd $ClientDir"
Write-Host "  python -m src.matha_main    # 启动 REPL"
Write-Host "  python update.py            # 检查并执行更新"
Write-Host ""
Write-Host "桌面快捷方式:"
Write-Host "  Matha REPL.lnk      ← 交互式编程"
Write-Host "  Matha 编译器.lnk    ← 编译工具"
Write-Host "  Matha 安装目录.lnk  ← 打开安装目录"
Write-Host ""
