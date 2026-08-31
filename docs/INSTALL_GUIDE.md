# Matha Windows 安装程序使用指南

## 概述

Matha 提供三种 Windows 安装方式，均支持创建桌面快捷方式。

---

## 方式 1: PowerShell 安装程序（推荐）

### 安装
```powershell
# 以管理员权限运行
cd d:\trae
powershell -ExecutionPolicy Bypass -File scripts\install.ps1

# 可选参数
.\scripts\install.ps1 -AddToPath       # 添加到系统 PATH
.\scripts\install.ps1 -NoDesktop        # 不创建桌面快捷方式
.\scripts\install.ps1 -NoStartMenu      # 不创建开始菜单快捷方式
```

### 卸载
```powershell
# 交互确认
.\scripts\uninstall.ps1

# 强制卸载（无确认）
.\scripts\uninstall.ps1 -Force
```

### 安装功能
- ✅ 安装 `matha.exe` 和 `matha-cc.exe` 到 `C:\Program Files\Matha`
- ✅ 创建桌面快捷方式：
  - `Matha REPL` — 启动交互式编程环境
  - `Matha 编译器` — 编译工具
  - `Matha 安装目录` — 打开安装目录
- ✅ 创建开始菜单快捷方式：
  - `Matha REPL`
  - `Matha 编译器`
  - `Matha 离线文档`
  - `Matha 卸载`
  - `打开命令提示符`
- ✅ 可选添加到系统 PATH

---

## 方式 2: 批处理安装程序

### 安装
```cmd
cd d:\trae
scripts\install.bat
```

### 卸载
```cmd
scripts\uninstall.bat
```

---

## 方式 3: 手动安装（无需安装程序）

```powershell
# 1. 创建安装目录
New-Item -ItemType Directory -Path "C:\Program Files\Matha" -Force

# 2. 复制文件
Copy-Item "dist\matha-offline\matha.exe" "C:\Program Files\Matha\"
Copy-Item "dist\matha-cc-offline\matha-cc.exe" "C:\Program Files\Matha\"

# 3. 创建桌面快捷方式
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\Matha REPL.lnk")
$shortcut.TargetPath = "C:\Program Files\Matha\matha.exe"
$shortcut.WorkingDirectory = "C:\Program Files\Matha"
$shortcut.Description = "Matha REPL 交互式编程环境"
$shortcut.Save()

$shortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\Matha 编译器.lnk")
$shortcut.TargetPath = "C:\Program Files\Matha\matha-cc.exe"
$shortcut.WorkingDirectory = "C:\Program Files\Matha"
$shortcut.Description = "Matha 编译器工具"
$shortcut.Save()
```

---

## 快捷方式说明

| 快捷方式 | 位置 | 功能 |
|---------|------|------|
| Matha REPL | 桌面/开始菜单 | 启动交互式 REPL |
| Matha 编译器 | 桌面/开始菜单 | 启动编译器工具 |
| Matha 安装目录 | 桌面/开始菜单 | 打开安装目录 |
| Matha 离线文档 | 开始菜单 | 打开离线使用指南 |
| 打开命令提示符 | 开始菜单 | 在 Matha 目录打开 cmd |
| Matha 卸载 | 开始菜单 | 卸载程序 |

---

## 添加到系统 PATH

安装时可选添加到系统 PATH，安装后 `matha` 和 `matha-cc` 命令可在任意目录使用：

```powershell
# 安装时添加
.\scripts\install.ps1 -AddToPath

# 手动添加
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;C:\Program Files\Matha", "User")

# 验证
$env:PATH -split ";" | Select-String "Matha"
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `scripts/install.ps1` | PowerShell 安装程序（推荐） |
| `scripts/uninstall.ps1` | PowerShell 卸载程序 |
| `scripts/install.bat` | 批处理安装程序 |
| `scripts/uninstall.bat` | 批处理卸载程序 |
| `scripts/create_shortcut.js` | 快捷方式创建脚本（bat 版依赖） |
| `scripts/matha_installer.nsi` | NSIS 安装程序脚本（需安装 NSIS） |
| `scripts/matha_installer.iss` | Inno Setup 安装程序脚本（需安装 Inno Setup） |
| `scripts/build_installer.py` | 自动构建安装程序脚本 |

---

## 离线安装包结构

```
offline_package/
├── dist/
│   ├── matha-offline/
│   │   └── matha.exe              # 独立可执行文件 (18.5 MB)
│   └── matha-cc-offline/
│       └── matha-cc.exe           # 编译器独立可执行文件
├── scripts/
│   ├── install.ps1                # PowerShell 安装程序（含桌面快捷方式）
│   ├── uninstall.ps1              # PowerShell 卸载程序
│   ├── install.bat                # 批处理安装程序
│   └── uninstall.bat              # 批处理卸载程序
├── src/                           # 源代码
├── tests/                         # 测试套件
├── docs/                          # 文档
├── pyproject.toml                 # 包配置
├── README.md                      # 使用说明
└── requirements.txt               # 依赖清单
```

---

## 使用步骤（离线机器）

```powershell
# 1. 将 offline_package/ 拷贝到离线机器

# 2. 运行安装程序
cd offline_package
powershell -ExecutionPolicy Bypass -File scripts\install.ps1

# 3. 验证安装
matha --version
matha eval "sin(3.14)"

# 4. 双击桌面快捷方式
#    - Matha REPL → 启动交互式编程
#    - Matha 编译器 → 启动编译器工具
```
