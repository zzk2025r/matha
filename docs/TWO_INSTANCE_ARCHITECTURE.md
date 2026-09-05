# Matha 双实例架构设计文档

> **版本：** v4.4.57  
> **日期：** 2026-09-05  
> **状态：** 生产架构

---

## 一、架构概述

Matha 采用**双实例 + 自举更新**架构，将"使用"与"开发"彻底分离，实现安全更新和持续演进。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Matha 双实例架构总览                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                    ~/Matha/  (用户工作空间根目录)                      │     │
│  │                                                                     │     │
│  │  ┌──────────────────────┐          ┌──────────────────────┐        │     │
│  │  │  client/  (使用端)    │          │  dev/   (更新端)      │        │     │
│  │  │                      │          │                      │        │     │
│  │  │  matha.exe           │          │  ~/trae/ (开发源码)    │        │     │
│  │  │  matha-cc.exe        │          │  ├── src/             │        │     │
│  │  │  src/ (只读快照)      │          │  ├── tests/           │        │     │
│  │  │  docs/ (离线文档)     │          │  ├── scripts/         │        │     │
│  │  │  config.json         │          │  └── .git/             │        │     │
│  │  │  update.py           │          │                      │        │     │
│  │  │  (自举更新器)         │          │  功能：               │        │     │
│  │  │                      │          │  • 开发/测试/升级      │        │     │
│  │  │  功能：               │          │  • 编译/运行/调试      │        │     │
│  │  │  • 日常计算/学习      │          │  • 提交 GitHub        │        │     │
│  │  │  • REPL交互          │          │                      │        │     │
│  │  │  • .matha 文件运行   │          │  安装位置：           │        │     │
│  │  │  • 公式推导/生长      │          │  git clone 或源码目录 │        │     │
│  │  └──────────┬───────────┘          └──────────┬───────────┘        │     │
│  │             │                                 │                     │     │
│  │             │        自举更新                   │                     │     │
│  │             │  ┌──────────────┐               │                     │     │
│  │             ├─▶│ GitHub Repo  │◀──────────────┤                     │     │
│  │             │  └──────────────┘               │                     │     │
│  │             │     ↑ push              pull ↑   │                     │     │
│  │             │                                 │                     │     │
│  │  ┌──────────▼───────────┐                     │                     │     │
│  │  │  workspace/ (用户工作区) │                   │                     │
│  │  │                      │                     │                     │
│  │  │  projects/           │                     │                     │
│  │  │  formulas/           │                     │                     │
│  │  │  .matha 文件          │                     │                     │
│  │  └──────────────────────┘                     │                     │
│  │                                             │                     │
│  └─────────────────────────────────────────────┘                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                        自举更新闭环                                    │     │
│  │                                                                     │     │
│  │  dev (开发端)         GitHub           client (使用端)                 │     │
│  │      │    push ───────────────▶      pull ───────────▶  增量更新       │     │
│  │      │    (commit)                (git pull)        (update.py)        │     │
│  │      │◀───────────────────────      │                    │             │     │
│  │      │    git clone/pull            │                    │             │     │
│  │      │                              │                    │             │     │
│  │  开发者提交新代码                  使用端自动检测           更新完成       │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

### 2.1 用户工作空间 (`~/Matha/`)

```
~/Matha/
├── client/                    ← 使用端（稳定版，日常使用）
│   ├── matha.exe              ← 主程序（编译后的可执行文件）
│   ├── matha-cc.exe           ← 编译器后端
│   ├── matha-dev.exe          ← 开发模式启动器
│   ├── src/                   ← 只读源码快照（随版本更新）
│   │   ├── __init__.py
│   │   ├── lexer.py           ← 词法分析
│   │   ├── parser.py          ← 语法分析
│   │   ├── interp.py          ← 解释器
│   │   ├── stdlib/            ← 标准库
│   │   ├── domains/           ← 领域模块
│   │   └── ...
│   ├── docs/                  ← 离线文档（与版本绑定）
│   │   ├── USAGE_GUIDE.md
│   │   ├── ARCHITECTURE_v4.4.md
│   │   └── ...
│   ├── config.json            ← 使用端配置
│   │   {
│   │     "version": "4.4.57",
│   │     "auto_update": true,
│   │     "update_interval_hours": 24,
│   │     "github_repo": "zzk2025r/matha",
│   │     "branch": "main",
│   │     "language": "zh-CN"
│   │   }
│   ├── update.py              ← 自举更新器（核心！）
│   ├── matha-workspace.ini    ← 工作空间配置
│   └── README.md
│
├── dev/                       ← 更新端（开发/测试/升级）
│   └── matha/                 ← git clone 的完整仓库
│       ├── src/
│       ├── tests/
│       ├── scripts/
│       └── docs/
│
├── workspace/                 ← 用户工作区（所有用户文件）
│   ├── projects/              ← 用户的 .matha 项目
│   ├── formulas/              ← 用户自定义公式
│   ├── notebooks/             ← Jupyter 笔记
│   └── .matha_cache/          ← 缓存（独立于客户端）
│
└── MathaIDE/                  ← Matha IDE（以 Matha 为基础的开发环境）
    ├── matha_ide.matha        ← IDE 核心逻辑（用 Matha 编写！）
    ├── matha_ide.py           ← Python 运行时
    └── ...
```

### 2.2 开发端（`~/trae/` 或任意开发目录）

```
~/trae/                        ← 开发者工作目录（非 Matha 用户空间）
├── src/                       ← 开发源码
├── tests/                     ← 测试套件
├── scripts/                   ← 构建/部署脚本
├── docs/                      ← 开发文档
├── matha/                     ← Matha 源码（可符号链接到 ~/Matha/dev/matha/）
├── .git/                      ← Git 版本控制
└── pyproject.toml             ← 项目配置
```

---

## 三、自举更新机制

### 3.1 更新触发条件

| 条件 | 行为 |
|------|------|
| 启动时检测到新代码变更 | 提示用户是否需要更新 |
| 定时检查（config.json 配置） | 每 24 小时自动检查 |
| 手动触发（`matha update`） | 立即执行 |
| 开发者推送 GitHub | 使用端下次启动时检测 |

### 3.2 增量更新算法

```python
# update.py 核心逻辑
def bootstrap_update():
    # 1. 检查 GitHub 最新版本
    latest = get_github_latest_tag()  # v4.4.58

    # 2. 比较版本
    current = get_installed_version()  # v4.4.57
    if latest == current:
        return {"status": "up-to-date"}

    # 3. 增量下载（只下载变更部分）
    diff_files = get_diff_files(current, latest)

    # 4. 备份当前 client/src/
    backup = create_backup("client/src")

    # 5. 应用更新
    for f in diff_files:
        apply_patch(f)

    # 6. 运行自检
    if not run_tests():
        restore_backup(backup)
        return {"status": "rollback"}

    # 7. 更新版本号
    update_version_ling(latest)

    return {"status": "success", "version": latest}
```

### 3.3 安全机制

| 安全特性 | 说明 |
|---------|------|
| 版本签名验证 | 所有更新文件经 GPG/SHA256 签名 |
| 回滚机制 | 更新失败自动回滚到上一版本 |
| 测试先行 | 更新前运行全套测试，失败则中止 |
| 权限隔离 | 使用端只读，开发者独立写入 |
| 网络隔离 | 支持离线更新（从 dev 端拷贝） |

---

## 四、Matha IDE（自举开发环境）

### 4.1 设计理念

> **Matha IDE 由 Matha 自身编写，任何系统可识别运行。**

```
┌─────────────────────────────────────────────────────────────┐
│                     Matha IDE 架构                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              用户界面层 (HTML/CSS/JS 或 Flutter)         ││
│  │         编辑器 / REPL / 文件浏览器 / 调试器              ││
│  └─────────────────────────┬───────────────────────────────┘│
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐│
│  │              Matha 运行时层 (matha_ide.matha)            ││
│  │  • 语法高亮引擎 (用 Matha 编写)                          ││
│  │  • 实时诊断 (用 Matha 编写)                              ││
│  │  • 代码补全 (用 Matha 编写)                              ││
│  │  • 公式编辑器 (用 Matha 编写)                            ││
│  │  • 版本管理器 (用 Matha 编写)                            ││
│  └─────────────────────────┬───────────────────────────────┘│
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐│
│  │              Matha 内核层 (lexer/parser/interp)           ││
│  │  标准 Matha 解释器 + 编译器                              ││
│  └─────────────────────────┬───────────────────────────────┘│
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐│
│  │              系统适配层 (Python/JS/Fortran)               ││
│  │  跨平台支持: Windows/Linux/macOS + Mobile/Web             ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 4.2 使用方式

```powershell
# 启动 Matha IDE
matha ide

# 或从使用端启动
~/Matha/client/matha-ide.exe

# 在浏览器中打开 Web IDE
matha ide --web
```

### 4.3 IDE 功能（Matha 自举）

| 功能 | 说明 |
|------|------|
| 语法高亮 | 用 Matha 编写的词法分析器 |
| 实时诊断 | 用 Matha 编写的错误检测器 |
| 代码补全 | 基于语义分析的智能补全 |
| 公式编辑器 | 所见即所得的公式输入 |
| 项目管理 | 使用 Matha 编写的版本控制集成 |
| 调试器 | 步进式调试 Matha 代码 |
|  REPL | 增强型交互式环境 |

---

## 五、安装流程

### 5.1 使用端安装（新用户）

```powershell
# 一键安装（创建 ~/Matha 工作空间）
pip install matha
matha setup --workspace

# 或使用 PowerShell 脚本
cd ~/trae
.\scripts\install-workspace.ps1
```

安装后自动创建：
- `~/Matha/client/` — 使用端
- `~/Matha/workspace/` — 用户工作区
- `~/Matha/config.json` — 配置

### 5.2 开发者安装（开发端）

```powershell
# 克隆开发仓库
git clone git@github.com:zzk2025r/matha.git ~/trae
cd ~/trae
pip install -e .

# 创建符号链接（可选）
# 将 dev/matha 链接到开发目录
cmd /c mklink /D "C:\Users\Admin\Matha\dev\matha" "D:\trae"
```

### 5.3 更新流程

```powershell
# 使用端手动更新
matha update

# 开发者推送更新
cd ~/trae
git add .
git commit -m "更新说明"
git push origin main

# 使用端下次启动自动检测新版本
# 或通过 matha update 立即更新
```

---

## 六、系统兼容性

| 平台 | 使用端支持 | 开发端支持 | IDE 支持 |
|------|-----------|-----------|---------|
| Windows | ✅ | ✅ | ✅ |
| Linux | ✅ | ✅ | ✅ |
| macOS | ✅ | ✅ | ✅ |
| Android/iOS | ✅ (Flutter) | ❌ | ❌ |
| Web 浏览器 | ✅ | ✅ (Node.js) | ✅ |
| WASM | ✅ | ❌ | ✅ |

**识别标准：**
- 任何识别 Python 的系统可运行 `matha` 命令
- 任何识别 JSON 的系统可读取 `config.json`
- 任何识别 `.matha` 扩展名的系统可打开 Matha 文件
- Matha IDE 以标准格式（HTML/JSON/MMA）输出，可被其他系统集成

---

## 七、文件识别规则

Matha 系统使用以下文件扩展名和格式，可被任何系统识别：

| 文件类型 | 扩展名 | 格式 | 说明 |
|---------|--------|------|------|
| Matha 源码 | `.matha` | 文本 | 数学核心代码 |
| 配置文件 | `.json` | JSON | 标准 JSON 格式 |
| 文档 | `.md` | Markdown | 通用文档格式 |
| 数据 | `.csv` | CSV | 标准表格数据 |
| 日志 | `.log` | 文本 | 系统日志 |
| 缓存 | `.json` | JSON | JIT/编译缓存 |
| IDE 配置 | `.matharc` | 文本 | Matha IDE 配置 |
| 公式库 | `.matha` | 文本 | 可导入导出 |
