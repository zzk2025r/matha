# Matha Windows 安装程序 - 双击运行
# 功能: 安装 + 创建桌面/开始菜单快捷方式 + 生成卸载脚本
# 注: 本脚本不改 PATH（安装目录未入 PATH，命令行须用完整路径或快捷方式）
#
# 本脚本住在 scripts\ 下：仓库根是它的上一级，dist\ docs\ src\ tests\ 与
# pyproject.toml 全在根上。旧写法把产物拼在 $ScriptDir 之后（scripts\dist\
# matha-offline\matha.exe），路径双重错误（基目录错 + 已退役的嵌套产物布局），
# Test-Path 恒假却被静默跳过，脚本照样打印「安装完成！」——属假成功。

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$MathaDist = Join-Path $RepoRoot "dist"
$InstallDir = ""

# 版本号单一来源 = src\__version__.py（安装脚本不各自硬编，避免与 matha --version 打架）
$VersionFile = Join-Path $RepoRoot "src\__version__.py"
$Version = "未知"
if (Test-Path $VersionFile) {
    $m = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($m) { $Version = $m.Matches[0].Groups[1].Value }
}

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

# 复制文件（平铺产物口径：dist\matha.exe / dist\matha-cc.exe，与
# scripts\build.bat、.github\workflows\build.yml、scripts\build_exe.py 同判）
Write-Host "复制安装文件..." -ForegroundColor Cyan
$MathaExe = Join-Path $MathaDist "matha.exe"
if (-not (Test-Path $MathaExe)) {
    Write-Host "[错误] 缺少 $MathaExe" -ForegroundColor Red
    Write-Host "请先构建: scripts\build.bat 或 python scripts\build_exe.py --matha" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}
Copy-Item $MathaExe "$InstallDir\" -Force
$sz = [math]::Round((Get-Item (Join-Path $InstallDir "matha.exe")).Length / 1MB, 1)
Write-Host "  [OK] matha.exe ($sz MB)" -ForegroundColor Green

$MathaCc = Join-Path $MathaDist "matha-cc.exe"
if (Test-Path $MathaCc) {
    Copy-Item $MathaCc "$InstallDir\" -Force
    Write-Host "  [OK] matha-cc.exe" -ForegroundColor Green
} else {
    Write-Host "  - matha-cc.exe 未构建，跳过（python scripts\build_exe.py --matha-cc）" -ForegroundColor Gray
}

# 复制文档
if (Test-Path (Join-Path $RepoRoot "docs")) {
    $docsDir = Join-Path $InstallDir "docs"
    New-Item -ItemType Directory -Path $docsDir -Force | Out-Null
    Get-ChildItem (Join-Path $RepoRoot "docs") -Filter "*.md" | ForEach-Object {
        Copy-Item $_.FullName "$docsDir\" -Force
    }
    Write-Host "  [OK] docs/" -ForegroundColor Green
}

# 复制源文件
if (Test-Path (Join-Path $RepoRoot "src")) {
    $srcDir = Join-Path $InstallDir "src"
    New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
    Get-ChildItem (Join-Path $RepoRoot "src") -Filter "*.py" -Recurse | ForEach-Object {
        $relDir = $_.FullName.Substring((Join-Path $RepoRoot "src").Length + 1).Replace('\', '/')
        $targetDir = Join-Path $srcDir ($relDir -replace '/[^/]+$','')
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        Copy-Item $_.FullName "$targetDir\" -Force
    }
    Write-Host "  [OK] src/" -ForegroundColor Green
}

# 复制测试
if (Test-Path (Join-Path $RepoRoot "tests")) {
    $testsDir = Join-Path $InstallDir "tests"
    New-Item -ItemType Directory -Path $testsDir -Force | Out-Null
    Get-ChildItem (Join-Path $RepoRoot "tests") -Filter "*.py" | ForEach-Object {
        Copy-Item $_.FullName "$testsDir\" -Force
    }
    Write-Host "  [OK] tests/" -ForegroundColor Green
}

# 复制配置
@("pyproject.toml", "README.md", "requirements.txt", "matha.spec", "matha-cc.spec") | ForEach-Object {
    $src = Join-Path $RepoRoot $_
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
# 字面 here-string + 运行时自定位。旧写法是双引号 here-string，把安装时的
# $InstallDir / $env:USERPROFILE / $env:APPDATA 全烧进产物——卸载器一挪位置就删错
# 目录；且 param 声明了 -Force 却从不读，整目录递归删除前没有任何确认。
$uninstallContent = @'
# Matha 卸载程序
param([switch]$Force)
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = "未知"
$VersionFile = Join-Path $InstallDir "src\__version__.py"
if (Test-Path $VersionFile) {
    $vm = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($vm) { $Version = $vm.Matches[0].Groups[1].Value }
}
Write-Host "卸载 Matha v$Version（$InstallDir）..." -ForegroundColor Yellow

# 先确认这里确实是 Matha 安装目录，再动删除
if (-not ((Test-Path (Join-Path $InstallDir "matha.exe")) -or
          (Test-Path (Join-Path $InstallDir "src\matha_main.py")))) {
    Write-Host "[中止] $InstallDir 内没有 Matha 产物，未删除任何内容。" -ForegroundColor Red
    exit 1
}

if (-not $Force) {
    $ans = Read-Host "确定要卸载 Matha v$Version（$InstallDir）吗？(Y/N)"
    if ($ans -ne "Y" -and $ans -ne "y") {
        Write-Host "已取消卸载。" -ForegroundColor Gray
        exit 0
    }
}

# 桌面取 shell 目录：Desktop 被重定向（OneDrive）时 %USERPROFILE%\Desktop 是错路径
$Desktop = [Environment]::GetFolderPath("Desktop")
foreach ($lnk in @("Matha REPL.lnk", "Matha 编译器.lnk", "Matha 安装目录.lnk")) {
    Remove-Item (Join-Path $Desktop $lnk) -Force -ErrorAction SilentlyContinue
}
foreach ($menu in @((Join-Path ([Environment]::GetFolderPath("Programs")) "Matha"),
                    (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "Matha"))) {
    Remove-Item $menu -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-Item $InstallDir -Recurse -Force
Write-Host "Matha v$Version 已卸载。" -ForegroundColor Green
'@
Set-Content -Path "$InstallDir\uninstall.ps1" -Value $uninstallContent -Encoding UTF8
Write-Host "  [OK] 卸载脚本: uninstall.ps1" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Matha v$Version 安装完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Cyan
Write-Host "  1. 双击桌面快捷方式 'Matha REPL' 启动" -ForegroundColor White
Write-Host "  2. 或在命令提示符运行: `"$InstallDir\matha.exe`" eval 'sin(3.14)'" -ForegroundColor White
Write-Host "     （安装目录未加入 PATH）" -ForegroundColor Gray
Write-Host "  3. 卸载: `"$InstallDir\uninstall.ps1`"" -ForegroundColor White
Write-Host ""
Write-Host "安装目录: $InstallDir" -ForegroundColor Gray
Write-Host ""
Read-Host "按回车键退出"
