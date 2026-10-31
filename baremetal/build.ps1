# build.ps1 — Matha P5 裸机 HAL 的 Windows / PowerShell 构建脚本
#
# 用途：本机没有 make、系统默认 gcc 也编不了 RISC-V 时，用这个脚本一键产出固件。
#   1. 自动收集固件源码：baremetal 根目录及其子树下的全部 .c（main.c、hal\**\*.c），
#      以及 boot\ 下的全部 .S（crt0.S、vector.S）。
#      —— 明确排除 tools\（那是宿主 gcc 跑的 UART/内存/中断“模拟测试”，不能进固件）
#         和 build\（编译产物目录）。
#   2. 自动定位 RISC-V 交叉工具链（riscv-none-elf-gcc），也允许用 -CrossGcc 手动指定。
#   3. 逐个编译到 build\obj\，再链接成 build\matha_hal.elf，并 objcopy 出 matha_hal.bin。
#
# 目标与 baremetal\Makefile 完全一致：SiFive FE310 / RV32IMAC，freestanding。
#
# 运行（在 baremetal 目录下）：
#     powershell -ExecutionPolicy Bypass -File .\build.ps1
#   或先在 PowerShell 里进目录后直接：  .\build.ps1
# 可选参数见下方 param()。

[CmdletBinding()]
param(
    # 手动指定交叉编译器可执行文件（默认自动在 PATH 与常见安装目录里找）。
    [string]$CrossGcc,

    # 只清理并重新编译全部对象（默认就是全量重建；保留此项以兼容脚本调用习惯）。
    [switch]$Clean,

    # 跳过 objcopy（只要 ELF、不产出 .bin）。
    [switch]$SkipBin
)

$ErrorActionPreference = 'Stop'

# ── 0. 路径基准：一律以“脚本所在目录”为根，便于从任意 cwd 调用 ──────────────
$Root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildDir  = Join-Path $Root 'build'
$ObjDir    = Join-Path $BuildDir 'obj'
$LinkScript= Join-Path $Root  'link.ld'
$IncDir    = Join-Path $Root  'include'

# 与 Makefile 保持一致的架构 / ABI。
# 现代 binutils（xPack 15.2）把 CSR 访问拆成独立扩展 zicsr，必须显式列入，
# 否则报 “unrecognized opcode csrr ... extension zicsr required”。
$Arch = 'rv32imac_zicsr'
$Abi  = 'ilp32'

function Write-Step($msg) { Write-Host "[baremetal] $msg" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host "  $msg" }

# ── 1. 定位交叉工具链 ───────────────────────────────────────────────────────
function Resolve-CrossGcc([string]$Explicit) {
    if ($Explicit) {
        if (Test-Path $Explicit) { return (Resolve-Path $Explicit).Path }
        $found = Get-Command $Explicit -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
        throw "找不到指定的交叉编译器：$Explicit"
    }

    # 1a. 先看 PATH
    $cmd = Get-Command 'riscv-none-elf-gcc' -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # 1b. 常见安装目录里搜（含 xPack 的带版本号目录）
    $patterns = @(
        'riscv-none-elf-gcc*.exe',
        'riscv64-unknown-elf-gcc*.exe',
        'riscv32-unknown-elf-gcc*.exe'
    )
    $searchRoots = @(
        'C:\Program Files', 'C:\Program Files (x86)',
        'D:\', 'C:\'
    )
    foreach ($sr in $searchRoots) {
        if (-not (Test-Path $sr)) { continue }
        foreach ($p in $patterns) {
            $hit = Get-ChildItem -Path $sr -Recurse -Filter $p -ErrorAction SilentlyContinue |
                   Where-Object { $_.FullName -match '\\bin\\' } |
                   Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    throw "未检测到 RISC-V 交叉工具链（riscv-none-elf-gcc）。`n请用 -CrossGcc <路径> 指定，或先安装 xPack riscv-none-elf-gcc 并加入 PATH。"
}

try {
    $CC = Resolve-CrossGcc $CrossGcc
} catch {
    Write-Host "[baremetal] 错误：$_" -ForegroundColor Red
    exit 1
}

# 由 gcc 路径推导同工具链的 objcopy / size（把结尾的 gcc.exe / gcc 换掉）。
function Sibling-Tool($gccPath, $toolName) {
    $dir = Split-Path -Parent $gccPath
    # 只去掉结尾的 gcc(.exe)，保留前缀里的连字符：
    # riscv-none-elf-gcc.exe -> 前缀 riscv-none-elf-  -> riscv-none-elf-objcopy.exe
    $prefix = (Split-Path -Leaf $gccPath) -replace 'gcc(\.exe)?$', ''
    $cand = Join-Path $dir ($prefix + $toolName + '.exe')
    if (Test-Path $cand) { return $cand }
    $candNoExt = Join-Path $dir ($prefix + $toolName)
    if (Test-Path $candNoExt) { return $candNoExt }
    return $null
}
$Objcopy = Sibling-Tool $CC 'objcopy'
$Size    = Sibling-Tool $CC 'size'

Write-Step "交叉编译器：$CC"
if (-not (Test-Path $LinkScript)) {
    Write-Host "[baremetal] 错误：缺少链接脚本 $LinkScript" -ForegroundColor Red
    exit 1
}

# ── 2. 清理 / 建目录（本脚本恒为全量重建，避免残留旧对象）──────────────────
if (Test-Path $ObjDir) { Remove-Item -Recurse -Force $ObjDir }
New-Item -ItemType Directory -Force -Path $ObjDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

# ── 3. 收集源码 ─────────────────────────────────────────────────────────────
# 固件 .c：根目录下除 tools\、build\ 之外的全部；.S：boot\ 下的全部。
$CSources = Get-ChildItem -Path $Root -Recurse -Filter '*.c' -ErrorAction SilentlyContinue |
            Where-Object {
                $rel = $_.FullName.Substring($Root.Length).TrimStart('\')
                ($rel -notmatch '^tools\\') -and ($rel -notmatch '^build\\')
            } | Sort-Object FullName

$SSources = Get-ChildItem -Path (Join-Path $Root 'boot') -Recurse -Filter '*.S' -ErrorAction SilentlyContinue |
            Sort-Object FullName

if (-not $CSources -and -not $SSources) {
    Write-Host "[baremetal] 错误：没有收集到任何源文件（.c / .S）。" -ForegroundColor Red
    exit 1
}

Write-Step ("收集到 {0} 个 .c、{1} 个 .S：" -f @($CSources).Count, @($SSources).Count)
foreach ($f in $CSources) { Write-Info ("[C ] " + $f.FullName.Substring($Root.Length).TrimStart('\')) }
foreach ($f in $SSources) { Write-Info ("[S ] " + $f.FullName.Substring($Root.Length).TrimStart('\')) }

# ── 4. 编译：每个源文件 → build\obj\<相对路径>.o（保留子目录避免同名冲突）───
$cflags = @(
    "-march=$Arch", "-mabi=$Abi",
    '-Os', '-ffreestanding', '-nostdlib',
    '-Wall', '-Wextra',
    "-I$IncDir"
)

$Objects = @()
foreach ($src in @($CSources) + @($SSources)) {
    $rel    = $src.FullName.Substring($Root.Length).TrimStart('\')          # 如 hal\drivers\uart.c
    $relNoExt = [System.IO.Path]::ChangeExtension($rel, '.o')              # 如 hal\drivers\uart.o
    $objPath = Join-Path $ObjDir $relNoExt                                 # build\obj\hal\drivers\uart.o
    $objParent = Split-Path -Parent $objPath
    if (-not (Test-Path $objParent)) { New-Item -ItemType Directory -Force -Path $objParent | Out-Null }

    Write-Info ("  [CC] $rel")
    & $CC @cflags -c $src.FullName -o $objPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[baremetal] 编译失败：$rel" -ForegroundColor Red
        exit 1
    }
    $Objects += $objPath
}

# ── 5. 链接：统一走交叉 gcc 驱动（它会把 march/mabi 翻译成正确的 ld 仿真目标）。
#    裸 ld 不接受 -march/-mabi（其 -m 含义是“仿真模式”），所以这里绝不用裸 ld。
#    -Wl,--nmagic 含逗号，必须作为单个参数整体传入。
$elfPath = Join-Path $BuildDir 'matha_hal.elf'
Write-Step "链接 -> $elfPath"
$linkArgs = @(
    "-march=$Arch", "-mabi=$Abi",
    '-nostdlib',
    "-T", $LinkScript,
    '-Wl,--nmagic',
    '-o', $elfPath
) + $Objects
& $CC @linkArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[baremetal] 链接失败。" -ForegroundColor Red
    exit 1
}

# ── 6. objcopy 出裸二进制（可选）───────────────────────────────────────────
if (-not $SkipBin) {
    $binPath = Join-Path $BuildDir 'matha_hal.bin'
    if ($Objcopy) {
        Write-Info "  [BIN] $binPath"
        & $Objcopy -O binary $elfPath $binPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[baremetal] objcopy 失败（不影响已产出的 ELF）。" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[baremetal] 未找到 objcopy，跳过生成 .bin。" -ForegroundColor Yellow
    }
}

# ── 7. 报告 ─────────────────────────────────────────────────────────────────
if ($Size) {
    Write-Step "段大小："
    & $Size $elfPath
}
Write-Step "固件产出完成："
Write-Info ("  ELF : " + $elfPath + "  (" + [int](Get-Item $elfPath).Length + " bytes)")
if (-not $SkipBin -and (Test-Path (Join-Path $BuildDir 'matha_hal.bin'))) {
    $bp = Join-Path $BuildDir 'matha_hal.bin'
    Write-Info ("  BIN : " + $bp + "  (" + [int](Get-Item $bp).Length + " bytes)")
}
