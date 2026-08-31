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
$Version = "4.4"

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
$StartMenu = [Environment]::GetFolderPath("CommonPrograms")
$MathaGroup = Join-Path $StartMenu "Matha"
Remove-Item $MathaGroup -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  ✓ 已删除开始菜单快捷方式" -ForegroundColor Green

# 从 PATH 中移除
Write-Host "从系统 PATH 中移除..." -ForegroundColor Cyan
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -like "*$InstallDir*") {
    $newPath = $currentPath -replace [regex]::Escape(";$InstallDir"), ""
    $newPath = $newPath -replace [regex]::Escape("$InstallDir;"), ""
    $newPath = $newPath -replace [regex]::Escape($InstallDir), ""
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
    Write-Host "  ✓ 已从系统 PATH 中移除: $InstallDir" -ForegroundColor Green
} else {
    Write-Host "  [信息] $InstallDir 不在系统 PATH 中" -ForegroundColor Gray
}

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
