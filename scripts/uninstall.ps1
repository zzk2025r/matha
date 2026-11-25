<#
.SYNOPSIS
    Matha Windows 卸载程序
.DESCRIPTION
    卸载 Matha 并清理所有快捷方式和注册表项。
.PARAMETER Force
    强制卸载（无确认提示）
.EXAMPLE
    .\uninstall.ps1
    .\uninstall.ps1 -Force
#>
param([switch]$Force)

# 支持管理员安装目录
$PossibleDirs = @()
if ($env:USERPROFILE) { $PossibleDirs += "$env:USERPROFILE\Matha" }
$PossibleDirs += "C:\Program Files\Matha"
$InstallDir = $null
foreach ($d in $PossibleDirs) {
    if (Test-Path $d) { $InstallDir = $d; break }
}
if (-not $InstallDir) { $InstallDir = $PossibleDirs[0] }
# 目录靠猜测得到（%USERPROFILE%\Matha → Program Files），猜中的完全可能只是用户
# 自己的同名文件夹：先确认里面有 Matha 产物，否则什么都删不了、也改不了 PATH。
if (-not ((Test-Path (Join-Path $InstallDir "matha.exe")) -or
          (Test-Path (Join-Path $InstallDir "src\matha_main.py")))) {
    Write-Host "[中止] $InstallDir 内没有 Matha 产物，未做任何改动。" -ForegroundColor Red
    Write-Host "真实安装目录请用 install.ps1 -Uninstall -InstallDir <路径> 指定。" -ForegroundColor Gray
    exit 1
}
# 版本号取自唯一版本源（已安装树的 src\__version__.py，其次仓库检出），不再硬编
$Version = "未知"
foreach ($vf in @((Join-Path $InstallDir "src\__version__.py"),
                  (Join-Path $PSScriptRoot "..\src\__version__.py"))) {
    if (Test-Path $vf) {
        $vm = Select-String -Path $vf -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($vm) { $Version = $vm.Matches[0].Groups[1].Value; break }
    }
}

Write-Host "==========================================" -ForegroundColor Yellow
Write-Host "  Matha v$Version 卸载程序" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow
Write-Host ""

# 确认卸载
if (-not $Force) {
    $confirm = Read-Host "确定要卸载 Matha v$Version 吗？(Y/N)"
    if ($confirm -ne "Y" -and $confirm -ne "y") {
        Write-Host "已取消卸载。" -ForegroundColor Gray
        exit 0
    }
}

# 删除桌面快捷方式
Write-Host ""
Write-Host "删除桌面快捷方式..." -ForegroundColor Cyan
$Desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item "$Desktop\Matha REPL.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$Desktop\Matha 编译器.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$Desktop\Matha 安装目录.lnk" -Force -ErrorAction SilentlyContinue
Write-Host "  ✓ 已删除桌面快捷方式" -ForegroundColor Green

# 删除开始菜单
Write-Host "删除开始菜单快捷方式..." -ForegroundColor Cyan
# 安装脚本写的是「当前用户」程序组（%APPDATA%\...\Programs\Matha），
# 旧写法只清 CommonPrograms（所有用户），用户级程序组永远删不掉
foreach ($menu in @((Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Matha"),
                   (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "Matha"))) {
    Remove-Item $menu -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "  ✓ 已删除开始菜单快捷方式" -ForegroundColor Green

# 从 PATH 中移除（逐条目比对，两个作用域都走一遍）
# 旧写法两处问题：只处理 Machine 作用域（用户级安装的 PATH 项永远留残），
# 且非管理员下 SetEnvironmentVariable("PATH", …, "Machine") 直接抛异常打断脚本。
Write-Host "从 PATH 中移除..." -ForegroundColor Cyan
$removed = $false
foreach ($scope in @("Machine", "User")) {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", $scope)
    if (-not $currentPath) { continue }
    $newPath = ($currentPath -split ";" | Where-Object { $_ -and ($_ -ne $InstallDir) }) -join ";"
    if ($currentPath -eq $newPath) { continue }
    try {
        [Environment]::SetEnvironmentVariable("PATH", $newPath, $scope)
        Write-Host "  ✓ 已从 $scope PATH 中移除: $InstallDir" -ForegroundColor Green
        $removed = $true
    } catch {
        Write-Host "  [提示] $scope PATH 写入失败（需管理员）：$($_.Exception.Message)" -ForegroundColor Yellow
    }
}
if (-not $removed) { Write-Host "  [信息] $InstallDir 不在 PATH 中" -ForegroundColor Gray }

# 删除安装目录
Write-Host "删除安装目录..." -ForegroundColor Cyan
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "  ✓ 已删除安装目录: $InstallDir" -ForegroundColor Green
} else {
    Write-Host "  [信息] 安装目录不存在: $InstallDir" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Matha v$Version 已完全卸载" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "如需重新安装，请运行 install.ps1" -ForegroundColor Gray
Write-Host ""
