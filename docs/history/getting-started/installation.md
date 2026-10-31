# 安装指南

## 系统要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10 | 3.11+ |
| 操作系统 | Windows 10 / Ubuntu 20.04 / macOS 12 | Windows 11 / Ubuntu 22.04 / macOS 14 |
| 内存 | 512 MB | 2 GB+ |
| 磁盘 | 100 MB | 1 GB+ |

---

## 安装方式对比

| 方式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **独立可执行文件** | 生产部署、无 Python 环境、快速试用 | 零依赖、启动快、便于分发 | 体积较大 (~18MB)、无法动态加载 Python 模块 |
| **Python 包** | 开发调试、集成到 Python 项目、插件开发 | 完整功能、可扩展、调试方便 | 需要 Python 环境、依赖管理 |
| **离线部署包** | 无网络环境、安全合规、批量部署 | 完全离线、版本锁定、可审计 | 首次打包需联网、体积最大 |

---

## 方式 1：独立可执行文件（推荐）

### Windows

```powershell
# 下载最新版本
# 从 GitHub Releases 下载 matha.exe 和 matha-cc.exe

# 验证
.\matha.exe --version
.\matha-cc.exe info

# 添加到 PATH（可选）
$env:PATH += ";C:\path\to\matha"
```

### Linux / macOS

```bash
# 下载并授权
chmod +x matha matha-cc

# 移动到 PATH 目录
sudo mv matha matha-cc /usr/local/bin/

# 验证
matha --version
matha-cc info
```

### 验证安装

```bash
# 启动 REPL
matha
# 应显示 Matha REPL 提示符

# 计算表达式
matha eval "sin(pi)"
# 应输出: 1.2246467991473532e-16

# 运行测试程序
echo 'func main() = () => print("OK")' > test.matha
matha run test.matha
# 应输出: OK
```

---

## 方式 2：Python 包安装

### 从源码安装（开发模式）

```bash
# 克隆仓库
git clone https://github.com/zzk2025r/matha.git
cd matha

# 安装核心依赖
pip install sympy

# 安装性能依赖（可选，推荐）
pip install numpy scipy numba

# 以开发模式安装
pip install -e .

# 安装开发工具
pip install -e ".[dev]"
```

### 验证安装

```bash
# 检查版本
matha --version
# 输出: Matha 4.4

# 运行测试套件
python -m pytest tests/ -v --tb=short
# 应显示 1157 passed
```

---

## 方式 3：离线部署

### 打包（在有网络的机器上）

```bash
# 确保已安装 matha
pip install -e .

# 打包离线依赖
python scripts/package_offline.py --output-dir offline_pkg

# 打包结果
# offline_pkg/
# ├── matha_offline_python311_win_amd64.tar.gz
# ├── matha_offline_python311_linux_x86_64.tar.gz
# └── deploy_offline.py
```

### 部署（在目标离线机器上）

```bash
# 解压对应平台的包
tar -xzf matha_offline_python311_linux_x86_64.tar.gz

# 运行部署脚本
python deploy_offline.py --package-dir offline_pkg

# 验证
python scripts/verify_offline.py --quick
```

---

## 常见问题

### Q: `matha` 命令未找到
**A**: 确保安装目录在 PATH 环境变量中，或使用完整路径运行。

### Q: 导入错误 `ModuleNotFoundError: No module named 'numpy'`
**A**: 性能依赖为可选安装，运行 `pip install numpy scipy numba` 启用。

### Q: Windows 下中文乱码
**A**: 设置终端编码 `chcp 65001` 或使用 Windows Terminal。

### Q: 离线部署后 `matha` 不可用
**A**: 检查 `deploy_offline.py` 输出日志，确认 Python 路径正确。

---

## 下一步

- [第一个程序](first-program.md) - 编写并运行你的第一个 Matha 程序
- [REPL 使用](repl.md) - 交互式开发环境指南
- [编译器使用](compiler.md) - 编译到 C/Python/Rust 等目标语言