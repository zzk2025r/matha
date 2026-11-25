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
# 本脚本住在 scripts\ 下，仓库根是它的上一级：dist\ src\ docs\ tests\ 与
# pyproject.toml 全在根上（旧写法把它们拼在 scripts\ 之后，恒不存在）。
$RepoRoot = Split-Path -Parent $ScriptDir
# 版本号单一来源 = src\__version__.py（与 matha --version 同一读数）
$VersionFile = Join-Path $RepoRoot "src\__version__.py"
$Version = "未知"
if (Test-Path $VersionFile) {
    $m = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' |
        Select-Object -First 1
    if ($m) { $Version = $m.Matches[0].Groups[1].Value }
}

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

function CreateShortcut($Target, $ShortcutPath, $WorkingDir, $Description, $IconPath, $Arguments) {
    try {
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $Target
        $Shortcut.WorkingDirectory = $WorkingDir
        $Shortcut.Description = $Description
        # 旧签名没有 Arguments 槽，调用方把 "/k cd /d …" 传成了第 5 个参数
        # （= IconPath），快捷方式能建但命令行丢失、图标位置被写成一句 cmd 参数。
        if ($Arguments) {
            $Shortcut.Arguments = $Arguments
        }
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
    try {
        $newPath = "$Path;$currentPath"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
        Log "  ✓ 已添加到系统 PATH: $Path"
    } catch {
        # 非管理员写 Machine PATH 会抛 SecurityException；旧写法没兜，
        # 配合 ErrorActionPreference=Stop 会让「文件已复制完」的安装直接中断。
        # 降级写当前用户 PATH，并如实说明作用域差异。
        Log "  [提示] 系统 PATH 写入失败（需管理员）：$($_.Exception.Message)"
        $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($userPath -notlike "*$Path*") {
            [Environment]::SetEnvironmentVariable("PATH", "$Path;$userPath", "User")
            Log "  ✓ 已改添加到当前用户 PATH: $Path"
        } else {
            Log "  [信息] $Path 已在当前用户 PATH 中"
        }
    }
}

function RemoveFromSystemPath($Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    foreach ($scope in @("Machine", "User")) {
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", $scope)
        if (-not $currentPath) { continue }
        $newPath = $currentPath -split ";" | Where-Object { $_ -and ($_ -ne $Path) }
        $newPath = ($newPath -join ";")
        if ($currentPath -ne $newPath) {
            try {
                [Environment]::SetEnvironmentVariable("PATH", $newPath, $scope)
                Log "  ✓ 已从 $scope PATH 中移除: $Path"
            } catch {
                Log "  [提示] $scope PATH 写入失败（需管理员）：$($_.Exception.Message)"
            }
        }
    }
}

function CreateDesktopShortcuts($InstallDir) {
    if ($NoDesktop) { return }
    Log ""
    Log "创建桌面快捷方式..."
    $Desktop = [Environment]::GetFolderPath("Desktop")

    CreateShortcut "$InstallDir\matha.exe" "$Desktop\Matha REPL.lnk" $InstallDir "Matha REPL 交互式编程环境"
    CreateShortcut "$InstallDir\matha-cc.exe" "$Desktop\Matha 编译器.lnk" $InstallDir "Matha 编译器工具"
    CreateShortcut $InstallDir "$Desktop\Matha 安装目录.lnk" $InstallDir "Matha 安装目录"
}

function CreateStartMenuShortcuts($InstallDir) {
    if ($NoStartMenu) { return }
    Log ""
    Log "创建开始菜单快捷方式..."
    $StartMenu = [Environment]::GetFolderPath("CommonPrograms")
    $MathaGroup = Join-Path $StartMenu "Matha"

    # 旧写法把 New-Item 放在 -NoStartMenu 守卫之外：非管理员下连 -NoStartMenu
    # 都会因 ProgramData 目录不可写而中断整个安装。
    try {
        if (-not (Test-Path $MathaGroup)) {
            New-Item -ItemType Directory -Path $MathaGroup -Force | Out-Null
        }
    } catch {
        Log "  [提示] 所有用户程序组不可写（需管理员），改用当前用户程序组"
        $StartMenu = [Environment]::GetFolderPath("Programs")
        $MathaGroup = Join-Path $StartMenu "Matha"
        New-Item -ItemType Directory -Path $MathaGroup -Force | Out-Null
    }

    CreateShortcut "$InstallDir\matha.exe" "$MathaGroup\Matha REPL.lnk" $InstallDir "Matha REPL"
    CreateShortcut "$InstallDir\matha-cc.exe" "$MathaGroup\Matha 编译器.lnk" $InstallDir "Matha 编译器"
    CreateShortcut "$InstallDir\docs\OFFLINE_GUIDE.md" "$MathaGroup\Matha 离线文档.lnk" $InstallDir "Matha 离线使用指南"
    # 卸载入口指向 powershell -File（.lnk 直接把目标写成 .ps1 只会用编辑器打开脚本）；
    # 旧写法这里实参顺序颠倒（把 .lnk 路径当 Target、把 .ps1 当 ShortcutPath）。
    CreateShortcut "powershell.exe" "$MathaGroup\Matha 卸载.lnk" $InstallDir "卸载 Matha" `
        "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
    CreateShortcut "cmd.exe" "$MathaGroup\打开命令提示符.lnk" $InstallDir "在 Matha 目录打开命令提示符" `
        $null "/k `"cd /d $InstallDir`""
}

function CreateUninstaller($InstallDir) {
    $UninstallerScript = @'
param([switch]$Force)

# 自定位：本脚本由 install.ps1 写进安装目录，运行时取自身所在目录。
# 旧写法硬编 C:\Program Files\Matha——装在别的目录时这份卸载器删的是不存在的路径，
# 真正的安装目录反而留在那儿。
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 版本读数同样取唯一版本源（安装目录里的 src\__version__.py）
$Version = "未知"
$VersionFile = Join-Path $InstallDir "src\__version__.py"
if (Test-Path $VersionFile) {
    $vm = Select-String -Path $VersionFile -Pattern '^__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($vm) { $Version = $vm.Matches[0].Groups[1].Value }
}

Write-Host "卸载 Matha v$Version（$InstallDir）..." -ForegroundColor Yellow

# 先确认这里确实是 Matha 安装目录，再动删除——避免把卸载脚本拷进别的目录后误删
if (-not ((Test-Path (Join-Path $InstallDir "matha.exe")) -or
          (Test-Path (Join-Path $InstallDir "src\matha_main.py")))) {
    Write-Host "[中止] $InstallDir 内没有 Matha 产物，未删除任何内容。" -ForegroundColor Red
    exit 1
}

# 删除整个目录是不可逆动作：默认先确认，-Force 才静默（旧写法 param 声明了 -Force
# 却从没读过——传与不传行为一致，等于既无确认也无强制语义）
if (-not $Force) {
    $ans = Read-Host "确定要卸载 Matha v$Version（$InstallDir）吗？(Y/N)"
    if ($ans -ne "Y" -and $ans -ne "y") {
        Write-Host "已取消卸载。" -ForegroundColor Gray
        exit 0
    }
}

# 删除桌面快捷方式（名字必须与 CreateDesktopShortcuts 写入的一致——
# 旧写法删的是 "Matha.lnk"，而安装时建的是三个带后缀的名字，等于什么都没删）
$Desktop = [Environment]::GetFolderPath("Desktop")
foreach ($lnk in @("Matha REPL.lnk", "Matha 编译器.lnk", "Matha 安装目录.lnk", "Matha.lnk")) {
    Remove-Item (Join-Path $Desktop $lnk) -Force -ErrorAction SilentlyContinue
}

# 删除开始菜单（所有用户组 + 当前用户组，安装时按权限二选一）
foreach ($menu in @(
    (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "Matha"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Matha"))) {
    Remove-Item $menu -Recurse -Force -ErrorAction SilentlyContinue
}

# 从 PATH 中移除（安装时系统作用域写不进去会降级到用户作用域，卸载两侧都要清）
foreach ($scope in @("Machine", "User")) {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", $scope)
    if (-not $currentPath) { continue }
    $kept = $currentPath -split ";" | Where-Object { $_ -and ($_ -ne $InstallDir) }
    $newPath = ($kept -join ";")
    if ($currentPath -ne $newPath) {
        try {
            [Environment]::SetEnvironmentVariable("PATH", $newPath, $scope)
            Write-Host "  ✓ 已从 $scope PATH 中移除: $InstallDir" -ForegroundColor Green
        } catch {
            Write-Host "  [提示] $scope PATH 写入失败（需管理员）" -ForegroundColor Yellow
        }
    }
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

    # 检查是否已安装（-Force 允许覆盖重装：旧写法声明了 -Force 参数却从不读取它，
    # 目录存在时无条件 return，重装只能先手工删目录）
    if ((Test-Path $InstallDir) -and (-not $Force)) {
        Log "[信息] Matha 已安装在: $InstallDir"
        Log "如需重新安装，请加 -Force 或先运行 uninstall.ps1"
        return
    }

    # 创建安装目录
    Log "创建安装目录: $InstallDir"
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    # 复制文件
    Log ""
    Log "复制安装文件..."

    # 主程序（产物落点 = 构建入口的扁平 dist\<名>.exe；缺件即失败，不报假成功）
    $MathaExe = Join-Path $RepoRoot "dist\matha.exe"
    if (-not (Test-Path $MathaExe)) {
        throw "缺少 $MathaExe，请先构建: scripts\build.bat 或 python scripts\build_exe.py --matha"
    }
    Copy-Item $MathaExe "$InstallDir\" -Force
    $sz = [math]::Round((Get-Item (Join-Path $InstallDir "matha.exe")).Length / 1MB, 1)
    Log "  ✓ matha.exe ($sz MB)"
    $MathaCc = Join-Path $RepoRoot "dist\matha-cc.exe"
    if (Test-Path $MathaCc) {
        Copy-Item $MathaCc "$InstallDir\" -Force
        Log "  ✓ matha-cc.exe"
    } else {
        Log "  - matha-cc.exe 未构建，跳过（python scripts\build_exe.py --matha-cc）"
    }

    # 脚本
    if (Test-Path "$RepoRoot\scripts") {
        New-Item -ItemType Directory -Path "$InstallDir\scripts" -Force | Out-Null
        Copy-Item "$RepoRoot\scripts\*.py" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Copy-Item "$RepoRoot\scripts\*.bat" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Copy-Item "$RepoRoot\scripts\*.sh" "$InstallDir\scripts\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ scripts/"
    }

    # 文档
    if (Test-Path "$RepoRoot\docs") {
        New-Item -ItemType Directory -Path "$InstallDir\docs" -Force | Out-Null
        Copy-Item "$RepoRoot\docs\*.md" "$InstallDir\docs\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ docs/"
    }

    # 源文件（全子包递归：src\kernel 与 src\mbc 是解释器/VM 的必需件，
    # 旧写法只拷 compiler/domains/offline/stdlib 四片，装出的树 import 不起来）
    if (Test-Path "$RepoRoot\src") {
        $SrcRoot = Join-Path $RepoRoot "src"
        $DstSrc = Join-Path $InstallDir "src"
        New-Item -ItemType Directory -Path $DstSrc -Force | Out-Null
        Get-ChildItem $SrcRoot -Filter "*.py" -Recurse |
            Where-Object { $_.FullName -notmatch "\\__pycache__\\" } |
            ForEach-Object {
                $parent = Split-Path -Parent $_.FullName.Substring($SrcRoot.Length + 1)
                $dir = if ($parent) { Join-Path $DstSrc $parent } else { $DstSrc }
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
                Copy-Item $_.FullName $dir -Force
            }
        Log "  ✓ src/"
    }

    # 测试
    if (Test-Path "$RepoRoot\tests") {
        New-Item -ItemType Directory -Path "$InstallDir\tests" -Force | Out-Null
        Copy-Item "$RepoRoot\tests\*.py" "$InstallDir\tests\" -Force -ErrorAction SilentlyContinue
        Log "  ✓ tests/"
    }

    # 配置文件
    Copy-Item "$RepoRoot\pyproject.toml" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$RepoRoot\matha.spec" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$RepoRoot\matha-cc.spec" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$RepoRoot\README.md" "$InstallDir\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$RepoRoot\requirements.txt" "$InstallDir\" -Force -ErrorAction SilentlyContinue
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

    $Entry = Join-Path $InstallDir "matha.exe"
    Log ""
    Log "=========================================="
    Log "  安装完成！"
    Log "=========================================="
    Log ""
    Log "使用方法（未加 -AddToPath 时用完整路径或快捷方式）:"
    Log "  `"$Entry`"                 # 统一入口（REPL + 编译器 + 公式生长）"
    Log "  `"$Entry`" eval 'sin(3.14)'  # 计算表达式"
    Log "  `"$Entry`" run demo.matha    # 运行 Matha 文件"
    Log "  `"$Entry`" matha2c demo.matha -o out.c  # 转译为 C"
    Log "  `"$Entry`" ext upgrade <扩展名>          # 升级一个扩展包"
    Log ""
    # 快捷方式段落按开关打印：旧写法在 -NoDesktop -NoStartMenu 下照样声称建了快捷方式
    if ((-not $NoDesktop) -or (-not $NoStartMenu)) {
        Log "快捷方式:"
        if (-not $NoDesktop) { Log "  桌面: Matha REPL / Matha 编译器 / Matha 安装目录" }
        if (-not $NoStartMenu) { Log "  开始菜单: Matha REPL / 编译器 / 离线文档 / Matha 卸载" }
        Log ""
    }
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

    # 删除开始菜单：安装时按权限落在 Programs（用户级）或 CommonPrograms（所有用户），
    # 旧写法只清 CommonPrograms——非管理员装的程序组永远删不掉。
    foreach ($menu in @((Join-Path ([Environment]::GetFolderPath("Programs")) "Matha"),
                        (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "Matha"))) {
        Remove-Item $menu -Recurse -Force -ErrorAction SilentlyContinue
    }
    Log "  ✓ 已删除开始菜单快捷方式"

    # 从 PATH 中移除
    RemoveFromSystemPath $InstallDir

    # 整目录递归删除不可逆：默认先确认，-Force 才静默（旧写法这条路径没有任何确认，
    # 声明了 -Force 也从不读——与它自己生成的卸载脚本口径不一致）
    if (-not $Force) {
        $ans = Read-Host "确定要卸载 Matha v$Version（$InstallDir）吗？(Y/N)"
        if ($ans -ne "Y" -and $ans -ne "y") {
            Log "已取消卸载。"
            return
        }
    }

    # 删除安装目录
    if (Test-Path $InstallDir) {
        # 上面按 %USERPROFILE%\Matha → Program Files 顺序猜目录，猜中的可能只是
        # 用户自己的同名文件夹；确认里面有 Matha 产物再删。
        if (-not ((Test-Path (Join-Path $InstallDir "matha.exe")) -or
                  (Test-Path (Join-Path $InstallDir "src\matha_main.py")))) {
            Log "  [中止] $InstallDir 内没有 Matha 产物，未删除该目录。"
            Log "  如确需删除，请传 -InstallDir 指定真实安装目录。"
            return
        }
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
