# Matha 独立可执行文件构建指南

## 概述

Matha 现在支持打包为**独立可执行文件**，无需安装 Python 即可运行。

---

## 构建方式

### 方式 1: PyInstaller（推荐，单次构建）

**前置条件：** 在有网络的机器上安装 PyInstaller

```bash
# 1. 安装 PyInstaller
pip install pyinstaller

# 2. 构建 matha REPL
pyinstaller --onefile --console --name matha --hidden-import=src.repl src/repl.py

# 3. 构建 matha-cc 编译器
pyinstaller --onefile --console --name matha-cc --hidden-import=src.compiler.matha_cc_cli src/compiler/matha_cc_cli.py
```

**生成的文件：**
- `dist/matha.exe` — Matha REPL 独立可执行文件（Windows）
- `dist/matha` — Matha REPL 独立可执行文件（Linux/macOS）
- `dist/matha-cc.exe` — 编译器独立可执行文件

---

### 方式 2: build.bat / build.sh 脚本

```bash
# Windows
scripts\build.bat

# Linux/macOS
chmod +x scripts/build.sh
./scripts/build.sh
```

---

### 方式 3: build_exe.py 脚本

```bash
python scripts/build_exe.py              # 构建全部
python scripts/build_exe.py --matha      # 仅构建 matha
python scripts/build_exe.py --matha-cc   # 仅构建 matha-cc
python scripts/build_exe.py --onefile    # 单文件模式
```

---

## 可执行文件功能

### matha（REPL 入口）
```bash
# 启动交互式 REPL
matha

# 计算表达式
matha eval "sin(3.14)"

# 运行 Matha 源文件
matha run demo.matha

# 显示版本
matha --version

# 调试模式
matha --debug
```

### matha-cc（编译器入口）
```bash
# 编译为 C
matha-cc compile demo.matha -o output.c

# 编译并运行
matha-cc run demo.matha

# 生成 LLVM IR
matha-cc llvm demo.matha -o output.ll

# 优化编译
matha-cc optimize demo.matha -O2

# 显示工具链信息
matha-cc info

# 运行测试
matha-cc test
```

---

## 离线部署可执行文件

### 打包
```bash
# 在有网络机器上构建
pip install pyinstaller
pyinstaller --onefile --console matha.spec
pyinstaller --onefile --console matha-cc.spec

# 生成的文件
dist/
├── matha/
│   └── matha.exe      # 独立可执行文件
└── matha-cc/
    └── matha-cc.exe   # 独立编译器
```

### 传输到离线机器
将整个 `dist/` 目录拷贝到目标机器，无需安装 Python。

---

## 构建产物说明

| 文件 | 大小（估算） | 说明 |
|------|-------------|------|
| `dist/matha/matha.exe` | ~50 MB | Matha REPL 独立可执行文件 |
| `dist/matha-cc/matha-cc.exe` | ~30 MB | Matha 编译器独立可执行文件 |

> **注意**：实际大小取决于包含的模块数量。使用 `--onefile` 模式时，首次启动会有解包延迟。

---

## 常见问题

### Q: 构建失败，提示找不到模块？
A: 在 spec 文件的 `hiddenimports` 中添加缺失的模块路径。

### Q: 可执行文件启动很慢？
A: 这是 `--onefile` 模式的正常行为，首次启动需要解包。可使用 `--onedir` 模式加速。

### Q: 离线机器上无法运行？
A: 确保在相同架构（x64/arm64）和操作系统上构建。

### Q: 如何减小可执行文件大小？
A: 在 spec 文件的 `excludes` 中添加不需要的模块（如 matplotlib, tkinter 等）。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `matha.spec` | PyInstaller 配置（matha REPL） |
| `matha-cc.spec` | PyInstaller 配置（matha-cc 编译器） |
| `scripts/build_exe.py` | Python 打包脚本 |
| `scripts/build.bat` | Windows 批处理脚本 |
| `scripts/build.sh` | Linux/macOS 脚本 |
| `src/repl.py` | REPL 入口（已添加 main()） |
| `src/compiler/matha_cc_cli.py` | 编译器 CLI 入口 |
| `pyproject.toml` | 包配置（已更新 entry points） |
