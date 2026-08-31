# Matha Windows 安装程序 - 双击运行
# 版本: 4.4
# 功能: 安装 + 创建桌面快捷方式 + 可选添加到 PATH

$Version = "4.4"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MathaDist = Join-Path $ScriptDir "dist"
$InstallDir = ""

# 检测安装目录
$PossibleDirs = @()
if ($env:USERPROFILE) { $PossibleDirs += "$env:USERPROFILE\Matha" }
$PossibleDirs += "C:\Program Files\Matha"
$PossibleDirs += "$env:APPDATA\Matha"

foreach ($d in $PossibleDirs) {
    if (Test-Path $d) { $InstallDir = $d; break }
}
if (-not $InstallDir -and $env:USERPROFILE) {
    $InstallDir = "$env:USERPROFILE\Matha"
}
if (-not $InstallDir) {
    $InstallDir = "$env:TEMP\Matha"
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Matha v$Version Windows 安装程序" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "安装目录: $InstallDir" -ForegroundColor Gray
Write-Host ""

# 检查是否已安装
if (Test-Path "$InstallDir\matha.exe") {
    Write-Host "[信息] Matha 已安装，快捷方式已存在" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "双击桌面快捷方式 'Matha REPL' 启动使用。" -ForegroundColor Green
    Write-Host ""
    Read-Host "按回车键退出"
    exit 0
}

# 创建安装目录
Write-Host "创建安装目录..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# 复制文件
Write-Host "复制安装文件..." -ForegroundColor Cyan
$distOffline = Join-Path $MathaDist "matha-offline"
$distCc = Join-Path $MathaDist "matha-cc-offline"

if (Test-Path "$distOffline\matha.exe") {
    Copy-Item "$distOffline\matha.exe" "$InstallDir\" -Force
    Write-Host "  [OK] matha.exe" -ForegroundColor Green
}
if (Test-Path "$distCc\matha-cc.exe") {
    Copy-Item "$distCc\matha-cc.exe" "$InstallDir\" -Force
    Write-Host "  [OK] matha-cc.exe" -ForegroundColor Green
}

# 复制文档
if (Test-Path (Join-Path $ScriptDir "docs")) {
    $docsDir = Join-Path $InstallDir "docs"
    New-Item -ItemType Directory -Path $docsDir -Force | Out-Null
    Get-ChildItem (Join-Path $ScriptDir "docs") -Filter "*.md" | ForEach-Object {
        Copy-Item $_.FullName "$docsDir\" -Force
    }
    Write-Host "  [OK] docs/" -ForegroundColor Green
}

# 复制源文件
if (Test-Path (Join-Path $ScriptDir "src")) {
    $srcDir = Join-Path $InstallDir "src"
    New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
    Get-ChildItem (Join-Path $ScriptDir "src") -Filter "*.py" -Recurse | ForEach-Object {
        $relDir = $_.FullName.Substring((Join-Path $ScriptDir "src").Length + 1).Replace('\', '/')
        $targetDir = Join-Path $srcDir ($relDir -replace '/[^/]+$','')
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        Copy-Item $_.FullName "$targetDir\" -Force
    }
    Write-Host "  [OK] src/" -ForegroundColor Green
}

# 复制测试
if (Test-Path (Join-Path $ScriptDir "tests")) {
    $testsDir = Join-Path $InstallDir "tests"
    New-Item -ItemType Directory -Path $testsDir -Force | Out-Null
    Get-ChildItem (Join-Path $ScriptDir "tests") -Filter "*.py" | ForEach-Object {
        Copy-Item $_.FullName "$testsDir\" -Force
    }
    Write-Host "  [OK] tests/" -ForegroundColor Green
}

# 复制配置
@("pyproject.toml", "README.md", "requirements.txt", "matha.spec", "matha-cc.spec") | ForEach-Object {
    $src = Join-Path $ScriptDir $_
    if (Test-Path $src) { Copy-Item $src "$InstallDir\" -Force }
}
Write-Host "  [OK] 配置文件" -ForegroundColor Green

# 创建桌面快捷方式
Write-Host ""
Write-Host "创建桌面快捷方式..." -ForegroundColor Cyan
$Desktop = [Environment]::GetFolderPath("Desktop")
$WshShell = New-Object -ComObject WScript.Shell

try {
    $lnk = $WshShell.CreateShortcut("$Desktop\Matha REPL.lnk")
    $lnk.TargetPath = "$InstallDir\matha.exe"
    $lnk.WorkingDirectory = $InstallDir
    $lnk.Description = "Matha REPL 交互式编程环境"
    $lnk.Save()
    Write-Host "  [OK] 桌面: Matha REPL" -ForegroundColor Green
} catch {
    Write-Host "  [!] 桌面快捷方式创建失败: $($_.Exception.Message)" -ForegroundColor Yellow
}

try {
    $lnk = $WshShell.CreateShortcut("$Desktop\Matha 编译器.lnk")
    $lnk.TargetPath = "$InstallDir\matha-cc.exe"
    $lnk.WorkingDirectory = $InstallDir
    $lnk.Description = "Matha 编译器工具"
    $lnk.Save()
    Write-Host "  [OK] 桌面: Matha 编译器" -ForegroundColor Green
} catch {
    Write-Host "  [!] 桌面快捷方式创建失败: $($_.Exception.Message)" -ForegroundColor Yellow
}

try {
    $lnk = $WshShell.CreateShortcut("$Desktop\Matha 安装目录.lnk")
    $lnk.TargetPath = $InstallDir
    $lnk.Description = "Matha 安装目录"
    $lnk.Save()
    Write-Host "  [OK] 桌面: Matha 安装目录" -ForegroundColor Green
} catch {
    Write-Host "  [!] 桌面快捷方式创建失败: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 创建开始菜单快捷方式
Write-Host ""
Write-Host "创建开始菜单快捷方式..." -ForegroundColor Cyan
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Matha"
New-Item -ItemType Directory -Path $StartMenu -Force | Out-Null

try {
    $lnk = $WshShell.CreateShortcut("$StartMenu\Matha REPL.lnk")
    $lnk.TargetPath = "$InstallDir\matha.exe"
    $lnk.WorkingDirectory = $InstallDir
    $lnk.Save()
} catch {}

try {
    $lnk = $WshShell.CreateShortcut("$StartMenu\Matha 编译器.lnk")
    $lnk.TargetPath = "$InstallDir\matha-cc.exe"
    $lnk.WorkingDirectory = $InstallDir
    $lnk.Save()
} catch {}

try {
    $lnk = $WshShell.CreateShortcut("$StartMenu\Matha 离线文档.lnk")
    $lnk.TargetPath = "$InstallDir\docs\OFFLINE_GUIDE.md"
    $lnk.Save()
} catch {}

try {
    $lnk = $WshShell.CreateShortcut("$StartMenu\Matha 卸载.lnk")
    $lnk.TargetPath = "$InstallDir\uninstall.ps1"
    $lnk.Save()
} catch {}

try {
    $lnk = $WshShell.CreateShortcut("$StartMenu\打开命令提示符.lnk")
    $lnk.TargetPath = "cmd.exe"
    $lnk.Arguments = "/k cd /d `"$InstallDir`""
    $lnk.WorkingDirectory = $InstallDir
    $lnk.Save()
} catch {}

Write-Host "  [OK] 开始菜单: Matha 程序组" -ForegroundColor Green

# 创建卸载脚本
$uninstallContent = @"
# Matha 卸载程序
param([switch]$Force)
$InstallDir = "$InstallDir"
$Version = "$Version"
Write-Host "卸载 Matha v$Version..." -ForegroundColor Yellow
Remove-Item "$env:USERPROFILE\Desktop\Matha REPL.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\Desktop\Matha 编译器.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\Desktop\Matha 安装目录.lnk" -Force -ErrorAction SilentlyContinue
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Matha"
Remove-Item $StartMenu -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
Write-Host "Matha v$Version 已卸载。" -ForegroundColor Green
"@
Set-Content -Path "$InstallDir\uninstall.ps1" -Value $uninstallContent -Encoding UTF8
Write-Host "  [OK] 卸载脚本: uninstall.ps1" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Matha v$Version 安装完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Cyan
Write-Host "  1. 双击桌面快捷方式 'Matha REPL' 启动" -ForegroundColor White
Write-Host "  2. 或打开命令提示符，运行: matha" -ForegroundColor White
Write-Host ""
Write-Host "安装目录: $InstallDir" -ForegroundColor Gray
Write-Host ""
Read-Host "按回车键退出"
