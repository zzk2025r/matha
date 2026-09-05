<#
.SYNOPSIS
    Matha Windows 安装程序
.DESCRIPTION
    安装 Matha 独立可执行文件到指定目录，并创建桌面快捷方式、
    开始菜单快捷方式，可选添加到系统 PATH。
.PARAMETER InstallDir
    安装目录（默认: C:\Program Files\Matha）
.PARAMETER NoDesktop
    不创建桌面快捷方式
.PARAMETER NoStartMenu
    不创建开始菜单快捷方式
.PARAMETER AddToPath
    添加到系统 PATH 环境变量
.PARAMETER Quiet
    静默安装（无 GUI）
.PARAMETER Uninstall
    卸载 Matha
.EXAMPLE
    .\install.ps1
    .\install.ps1 -AddToPath
    .\install.ps1 -NoDesktop
    .\install.ps1 -Uninstall
#>
param(
    [string]$InstallDir = "",
    [switch]$NoDesktop,
    [switch]$NoStartMenu,
    [switch]$AddToPath,
    [switch]$Quiet,
    [switch]$Uninstall,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = "4.4"

# 确定安装目录（管理员→Program Files，否则→用户目录，沙箱→项目目录）
if ($Uninstall) {
    $PossibleDirs = @()
    if ($env:USERPROFILE) { $PossibleDirs += "$env:USERPROFILE\Matha" }
    $PossibleDirs += "C:\Program Files\Matha"
    $InstallDir = $null
    foreach ($d in $PossibleDirs) { if (Test-Path $d) { $InstallDir = $d; break } }
    if (-not $InstallDir) { $InstallDir = $PossibleDirs[0] }
} elseif ($InstallDir -eq "") {
    # 检测是否有管理员权限
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        $InstallDir = "C:\Program Files\Matha"
    } else {
        $InstallDir = "$env:USERPROFILE\Matha"
    }
    # 沙箱检测：如果无法写入用户目录，使用项目内目录
    try {
        $testDir = "$InstallDir\test_write"
        New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        Remove-Item $testDir -Force
    } catch {
        $InstallDir = "$PSScriptRoot\..\installed\Matha"
    }
}

function Log($msg) {
    if (-not $Quiet) {
        Write-Host $msg
    }
}

function CreateShortcut($Target, $ShortcutPath, $WorkingDir, $Description, $IconPath) {
    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $Target
        $Shortcut.WorkingDirectory = $WorkingDir
        $Shortcut.Description = $Description
        if ($IconPath) {
            $Shortcut.IconLocation = $IconPath
        }
        $Shortcut.Save()
        Log "  ✓ 快捷方式: $ShortcutPath"
    } catch {
        Log "  ✗ 快捷方式创建失败: $ShortcutPath ($($_.Exception.Message))"
    }
}

function AddToSystemPath($Path) {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
    if ($currentPath -like "*$Path*") {
        Log "  [信息] $Path 已在系统 PATH 中，跳过"
        return
    }
    $newPath = "$Path;$currentPath"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
    Log "  ✓ 已添加到系统 PATH: $Path"
}

function RemoveFromSystemPath($Path) {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
    $newPath = $currentPath -replace [regex]::Escape(";$Path"), ""
    $newPath = $newPath -replace [regex]::Escape("$Path;"), ""
    $newPath = $newPath -replace [regex]::Escape($Path), ""
    if ($currentPath -ne $newPath) {
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
        Log "  ✓ 已从系统 PATH 中移除: $Path"
    }
}

function CreateDesktopShortcuts($InstallDir) {
    Log ""
    Log "创建桌面快捷方式..."
    $Desktop = [Environment]::GetFolderPath("Desktop")

    if (-not $NoDesktop) {
        CreateShortcut "$InstallDir\matha.exe" "$Desktop\Matha REPL.lnk" $InstallDir "Matha REPL 交互式编程环境"
        CreateShortcut "$InstallDir\matha-cc.exe" "$Desktop\Matha 编译器.lnk" $InstallDir "Matha 编译器工具"
        CreateShortcut $InstallDir "$Desktop\Matha 安装目录.lnk" $InstallDir "Matha 安装目录"
    }
}

function CreateStartMenuShortcuts($InstallDir) {
    Log ""
    Log "创建开始菜单快捷方式..."
    $StartMenu = [Environment]::GetFolderPath("CommonPrograms")
    $MathaGroup = Join-Path $StartMenu "Matha"

    if (-not (Test-Path $MathaGroup)) {
        New-Item -ItemType Directory -Path $MathaGroup -Force | Out-Null
    }

    if (-not $NoStartMenu) {
        CreateShortcut "$InstallDir\matha.exe" "$MathaGroup\Matha REPL.lnk" $InstallDir "Matha REPL"
        CreateShortcut "$InstallDir\matha-cc.exe" "$MathaGroup\Matha 编译器.lnk" $InstallDir "Matha 编译器"
        CreateShortcut "$InstallDir\docs\OFFLINE_GUIDE.md" "$MathaGroup\Matha 离线文档.lnk" $InstallDir "Matha 离线使用指南"
        CreateShortcut "$MathaGroup\Matha 卸载.lnk" "$InstallDir\uninstall.ps1" $InstallDir "卸载 Matha"
        CreateShortcut "cmd.exe" "$MathaGroup\打开命令提示符.lnk" $InstallDir "在 Matha 目录打开命令提示符" "/k `"cd /d $InstallDir`""
    }
}

function CreateUninstaller($InstallDir) {
    $UninstallerScript = @'
param([switch]$Force)

$InstallDir = "C:\Program Files\Matha"
$Version = "4.5"

Write-Host "卸载 Matha v$Version..." -ForegroundColor Yellow

# 删除桌面快捷方式（v4.5 单图标）
$Desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item "$Desktop\Matha.lnk" -Force -ErrorAction SilentlyContinue

# 删除开始菜单
$StartMenu = [Environment]::GetFolderPath("CommonPrograms")
$MathaGroup = Join-Path $StartMenu "Matha"
Remove-Item $MathaGroup -Recurse -Force -ErrorAction SilentlyContinue

# 从 PATH 中移除
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -like "*$InstallDir*") {
    $newPath = $currentPath -replace [regex]::Escape(";$InstallDir"), ""
    $newPath = $newPath -replace [regex]::Escape("$InstallDir;"), ""
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
    Write-Host "  ✓ 已从系统 PATH 中移除: $InstallDir" -ForegroundColor Green
}

# 删除安装目录
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "  ✓ 已删除安装目录: $InstallDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "Matha v$Version 已完全卸载。" -ForegroundColor Green
Write-Host "如需重新安装，请运行 install.ps1" -ForegroundColor Gray
'@

    $UninstallerPath = Join-Path $InstallDir "uninstall.ps1"
    Set-Content -Path $UninstallerPath -Value $UninstallerScript -Encoding UTF8
    Log "  ✓ 卸载脚本: $UninstallerPath"
}

function InstallMatha {
    Log ""
    Log "=========================================="
    Log "  Matha v$Version Windows 安装程序"
    Log "=========================================="
    Log ""

    # 检查是否已安装
    if (Test-Path $InstallDir) {
        Log "[信息] Matha 已安装在: $InstallDir"
        Log "如需重新安装，请先运行 uninstall.ps1"
        return
    }

    # 创建安装目录
    Log "创建安装目录: $InstallDir"
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    # 复制文件
    Log ""
    Log "复制安装文件..."

    # 主程序
    Copy-Item "$ScriptDir\dist\matha-offline\matha.exe" "$InstallDir\" -Force
    Copy-Item "$ScriptDir\dist\matha-cc-offline\matha-cc.exe" "$InstallDir\" -Force
    Log "  ✓ matha.exe (18.5 MB)"
    Log "  ✓ matha-cc.exe"

    # 脚本
    if (Test-Path "$ScriptDir\scripts") {
        New-Item -ItemType Directory -Path "$InstallDir\scripts" -Force | Out-Null
        Copy-Item "$ScriptDir\scripts\*.py" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Copy-Item "$ScriptDir\scripts\*.bat" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Copy-Item "$ScriptDir\scripts\*.sh" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ scripts/"
    }

    # 文档
    if (Test-Path "$ScriptDir\docs") {
        New-Item -ItemType Directory -Path "$InstallDir\docs" -Force | Out-Null
        Copy-Item "$ScriptDir\docs\*.md" "$InstallDir\docs\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ docs/"
    }

    # 源文件
    if (Test-Path "$ScriptDir\src") {
        New-Item -ItemType Directory -Path "$InstallDir\src" -Force | Out-Null
        Copy-Item "$ScriptDir\src\*.py" "$InstallDir\src\" -Force -ErrorAction SilentlyContinue
        Get-ChildItem "$ScriptDir\src\compiler" -Filter "*.py" | ForEach-Object {
            Copy-Item $_.FullName "$InstallDir\src\compiler\" -Force
        }
        Get-ChildItem "$ScriptDir\src\domains" -Filter "*.py" | ForEach-Object {
            Copy-Item $_.FullName "$InstallDir\src\domains\" -Force
        }
        Get-ChildItem "$ScriptDir\src\offline" -Filter "*.py" | ForEach-Object {
            Copy-Item $_.FullName "$InstallDir\src\offline\" -Force
        }
        Get-ChildItem "$ScriptDir\src\stdlib" -Filter "*.py" | ForEach-Object {
            Copy-Item $_.FullName "$InstallDir\src\stdlib\" -Force
        }
        Log "  ✓ src/"
    }

    # 测试
    if (Test-Path "$ScriptDir\tests") {
        New-Item -ItemType Directory -Path "$InstallDir\tests" -Force | Out-Null
        Copy-Item "$ScriptDir\tests\*.py" "$InstallDir\tests\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ tests/"
    }

    # 配置文件
    Copy-Item "$ScriptDir\pyproject.toml" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$ScriptDir\matha.spec" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$ScriptDir\matha-cc.spec" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$ScriptDir\README.md" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$ScriptDir\requirements.txt" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Log "  ✓ 配置文件"

    # 创建快捷方式
    CreateDesktopShortcuts $InstallDir
    CreateStartMenuShortcuts $InstallDir

    # 创建卸载程序
    CreateUninstaller $InstallDir

    # 添加到 PATH
    if ($AddToPath) {
        Log ""
        Log "添加到系统 PATH..."
        AddToSystemPath $InstallDir
    }

    Log ""
    Log "=========================================="
    Log "  安装完成！"
    Log "=========================================="
    Log ""
    Log "使用方法:"
    Log "  matha                          # 统一入口（REPL + 编译器 + 公式生长）"
    Log "  matha eval 'sin(3.14)'         # 计算表达式"
    Log "  matha run demo.matha           # 运行 Matha 文件"
    Log "  matha compile demo.matha -o c  # 编译到 C"
    Log "  matha-update                   # 一键更新"
    Log ""
    Log "快捷方式:"
    Log "  桌面: Matha（单一入口）"
    Log "  开始菜单: Matha / Matha 更新"
    Log ""
    Log "安装目录: $InstallDir"
    Log ""
}

function UninstallMatha {
    Log ""
    Log "=========================================="
    Log "  Matha v$Version 卸载程序"
    Log "=========================================="
    Log ""

    # 删除桌面快捷方式
    $Desktop = [Environment]::GetFolderPath("Desktop")
    Remove-Item "$Desktop\Matha REPL.lnk" -Force -ErrorAction SilentlyContinue
    Remove-Item "$Desktop\Matha 编译器.lnk" -Force -ErrorAction SilentlyContinue
    Remove-Item "$Desktop\Matha 安装目录.lnk" -Force -ErrorAction SilentlyContinue
    Log "  ✓ 已删除桌面快捷方式"

    # 删除开始菜单
    $StartMenu = [Environment]::GetFolderPath("CommonPrograms")
    $MathaGroup = Join-Path $StartMenu "Matha"
    Remove-Item $MathaGroup -Recurse -Force -ErrorAction SilentlyContinue
    Log "  ✓ 已删除开始菜单快捷方式"

    # 从 PATH 中移除
    RemoveFromSystemPath $InstallDir

    # 删除安装目录
    if (Test-Path $InstallDir) {
        Remove-Item $InstallDir -Recurse -Force
        Log "  ✓ 已删除安装目录: $InstallDir"
    } else {
        Log "  [信息] 安装目录不存在: $InstallDir"
    }

    Log ""
    Log "=========================================="
    Log "  Matha v$Version 已完全卸载"
    Log "=========================================="
    Log ""
}

# ============================
# 主程序
# ============================
if ($Uninstall) {
    UninstallMatha
} else {
    InstallMatha
}
