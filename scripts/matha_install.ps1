# Matha 一键安装脚本
# 安装至独立文件夹 ~/Matha，包含使用端+开发端+桌面图标

param(
    [switch]$SkipIcons,
    [switch]$SkipDev
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
# 版本号单一来源 = src\__version__.py（旧写法硬编 4.4.57，与 matha --version 打架）
$VersionFile = Join-Path $RepoRoot "src\__version__.py"
$Version = "未知"
if (Test-Path $VersionFile) {
    $vm = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($vm) { $Version = $vm.Matches[0].Groups[1].Value }
}
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
$oldStartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Matha"
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
$pyCount = 0
$docCount = 0
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

# 4b. 冻结独立入口：本地已构建 matha.exe 就随使用端一起装
#     （安装后的入口优先指向冻结 exe，Python 源码模式只作兜底）
$FrozenExe = Join-Path $RepoRoot "dist\matha.exe"
$FrozenCc = Join-Path $RepoRoot "dist\matha-cc.exe"
if (Test-Path $FrozenExe) {
    Copy-Item $FrozenExe "$ClientDir\" -Force
    Write-Host "  ✓ 冻结入口: matha.exe → $ClientDir" -ForegroundColor Green
} else {
    Write-Host "  - 未找到 $FrozenExe，本次仅装源码使用端；构建: scripts\build.bat" -ForegroundColor Gray
}
if (Test-Path $FrozenCc) {
    Copy-Item $FrozenCc "$ClientDir\" -Force
    Write-Host "  ✓ 冻结入口: matha-cc.exe → $ClientDir" -ForegroundColor Green
}

# 假成功守卫：既无冻结 exe 又无 Python 源码的使用端 = 什么都没装。
# 旧写法照样打印「Matha v$Version 安装完成！」并给出入口指引。
if ($pyCount -eq 0 -and -not (Test-Path "$ClientDir\matha.exe")) {
    Write-Host ""
    Write-Host "[中止] 使用端为空：开发端 src 不可用且 $RepoRoot\dist\matha.exe 不存在。" -ForegroundColor Red
    Write-Host "       未写配置、未建快捷方式。先构建冻结产物 scripts\build.bat，" -ForegroundColor Gray
    Write-Host "       或去掉 -SkipDev 以克隆开发端源码。" -ForegroundColor Gray
    exit 1
}

# 复制文档
$srcDocs = "$DevDir\docs"
if (Test-Path $srcDocs) {
    $dstDocs = "$ClientDir\docs"
    Copy-Item "$srcDocs\*.md" -Destination $dstDocs -Force -ErrorAction SilentlyContinue
    $docCount = (Get-ChildItem $dstDocs -Filter "*.md" -ErrorAction SilentlyContinue | Measure-Object).Count
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
# 整体写盘。旧写法 `(...).ToCharArray() | ForEach-Object | Out-File` 让 Out-File 收到
# 逐字符流并为每个对象补换行，生成的 update.py 变成竖排字符垃圾（33 行脚本 → 1192 行）。
($updateScript + "`n") | Set-Content "$ClientDir\update.py" -Encoding UTF8 -NoNewline

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

# 入口指向：冻结 exe 优先（独立进程，非 python 脚本），未构建时回落源码模式
function Get-EntryTarget {
    param([string]$Exe, [string]$Module)
    if (Test-Path $Exe) {
        return @{ Target = $Exe; Arguments = ""; Mode = "冻结 exe 独立进程" }
    }
    return @{ Target = "python.exe"; Arguments = "-m $Module"; Mode = "源码模式（本机无 $Exe）" }
}

# 注：WshShell.CreateShortcut 每次调用返回一个全新的快捷方式对象——
# 旧写法 $WshShell.CreateShortcut(...).TargetPath = "python.exe" 后另起一句
# 再 CreateShortcut(...).Save()，属性挂在被丢弃的对象上，存出来的 .lnk 无目标。
function New-MathaShortcut {
    param($Shell, [string]$Path, [string]$Target, [string]$Arguments,
          [string]$WorkDir, [string]$Description)
    $lnk = $Shell.CreateShortcut($Path)
    $lnk.TargetPath = $Target
    if ($Arguments) { $lnk.Arguments = $Arguments }
    if ($WorkDir) { $lnk.WorkingDirectory = $WorkDir }
    if ($Description) { $lnk.Description = $Description }
    $lnk.Save()
}

$ReplEntry = Get-EntryTarget "$ClientDir\matha.exe" "src.matha_main"
$CcEntry = Get-EntryTarget "$ClientDir\matha-cc.exe" "src.compiler.matha_cc_cli"

# 5. 创建桌面快捷方式
if (-not $SkipIcons) {
    Write-Host "步骤 5/5: 创建桌面快捷方式..." -ForegroundColor Yellow
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $WshShell = New-Object -ComObject WScript.Shell

    New-MathaShortcut $WshShell "$Desktop\Matha REPL.lnk" `
        $ReplEntry.Target $ReplEntry.Arguments $ClientDir "Matha REPL 交互式编程环境"
    New-MathaShortcut $WshShell "$Desktop\Matha 编译器.lnk" `
        $CcEntry.Target $CcEntry.Arguments $ClientDir "Matha 编译器工具"
    New-MathaShortcut $WshShell "$Desktop\Matha 安装目录.lnk" $MathaHome `
        "" "" "Matha 安装目录"

    Write-Host "  ✓ 桌面快捷方式: Matha REPL / Matha 编译器 / Matha 安装目录" -ForegroundColor Green
    Write-Host "    入口形态: REPL=$($ReplEntry.Mode) / 编译器=$($CcEntry.Mode)" -ForegroundColor Gray
}

# 创建开始菜单（与桌面图标同一开关：-SkipIcons 时两类快捷方式都不建，尾部摘要也不得声称）
if (-not $SkipIcons) {
    $StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Matha"
    if (-not (Test-Path $StartMenu)) { New-Item -ItemType Directory -Path $StartMenu -Force | Out-Null }
    $WshShell = New-Object -ComObject WScript.Shell
    New-MathaShortcut $WshShell "$StartMenu\Matha REPL.lnk" `
        $ReplEntry.Target $ReplEntry.Arguments $ClientDir "Matha REPL"
    New-MathaShortcut $WshShell "$StartMenu\Matha 编译器.lnk" `
        $CcEntry.Target $CcEntry.Arguments $ClientDir "Matha 编译器"
    New-MathaShortcut $WshShell "$StartMenu\打开安装目录.lnk" $MathaHome "" "" "Matha 安装目录"
    Write-Host "  ✓ 开始菜单: Matha REPL / Matha 编译器 / 打开安装目录" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Matha v$Version 安装完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "目录结构:"
Write-Host "  $MathaHome/"
Write-Host "  ├── client/      ← 使用端（日常计算/学习）"
Write-Host "  │   ├── src/     ← $pyCount 个 Python 文件"
Write-Host "  │   ├── docs/    ← $docCount 个文档"
Write-Host "  │   ├── tests/   ← 测试套件"
Write-Host "  │   ├── config.json"
Write-Host "  │   └── update.py ← 自举更新器"
if (Test-Path "$ClientDir\matha.exe") {
    Write-Host "  │   ├── matha.exe     ← 冻结独立入口"
    Write-Host "  │   └── matha-cc.exe  ← 冻结编译器入口"
}
Write-Host "  ├── dev/         ← 更新端（开发/测试/升级）"
Write-Host "  ├── workspace/   ← 用户工作区（.matha 项目）"
Write-Host "  ├── MathaIDE/    ← 自举开发环境（JSON 可识别）"
Write-Host "  └── matha-home.json ← 工作空间配置"
Write-Host ""
Write-Host "使用方法（入口形态：$($ReplEntry.Mode)）:"
Write-Host "  cd $ClientDir"
if (Test-Path "$ClientDir\matha.exe") {
    Write-Host "  .\matha.exe repl              # 启动 REPL（冻结 exe 独立进程）"
    Write-Host "  .\matha.exe eval 'sin(3.14)'    # 计算表达式"
} else {
    Write-Host "  python -m src.matha_main    # 启动 REPL（源码模式）"
}
Write-Host "  python update.py            # 检查并执行更新"
Write-Host ""
if (-not $SkipIcons) {
    Write-Host "桌面快捷方式:"
    Write-Host "  Matha REPL.lnk      ← 交互式编程"
    Write-Host "  Matha 编译器.lnk    ← 编译工具"
    Write-Host "  Matha 安装目录.lnk  ← 打开安装目录"
    Write-Host ""
}
