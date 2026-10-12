# Matha

**自举式领域专用语言与独立可执行编程语言系统**

[![Version](https://img.shields.io/badge/version-4.4-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License](https://img.shields.io/badge/license-BSD--2--Clause-green.svg)]()
[![Tests](https://img.shields.io/badge/tests-1157%20passed-brightgreen.svg)]()
[![Offline](https://img.shields.io/badge/offline-ready-orange.svg)]()

---

## 🎯 核心特性

| 特性 | 说明 |
|------|------|
| **自举实现** | 词法器/解析器/解释器/编译器均由 Matha 自身编写 |
| **多语言代码生成** | C/Python/Rust/Go/Java/C++/JS/Matha 八语言互译 |
| **原生编译** | x86-64 机器码直出，PE64/ELF64/Mach-O 无依赖运行 |
| **JIT 编译** | 函数级即时编译 + 自动 Memoization (斐波那契 19526x 加速) |
| **类型系统** | 依赖类型/泛型/子类型/精炼类型 |
| **CSP 并发** | 进程级并发绕过 Python GIL |
| **54 领域模块** | 物理/工程/AI/金融/生物/化学等全覆盖 |
| **离线可用** | 完整功能零网络依赖，单文件可执行程序 |

---

## 🚀 快速开始

### 方式 1：独立可执行文件（推荐，无需安装 Python）

```bash
# 下载 matha.exe 和 matha-cc.exe
# 直接运行，无需任何环境

# 启动交互式 REPL
matha

# 计算表达式
matha eval "sin(3.14)"

# 运行 Matha 源文件
matha run demo.matha

# 编译到 C
matha-cc compile demo.matha -o output.c

# 编译到 Python
matha-cc compile demo.matha -o output.py
```

### 方式 2：Python 包安装

```bash
# 安装依赖
pip install sympy numpy scipy numba

# 安装 Matha
pip install -e .

# 使用
matha                          # 启动 REPL
matha eval "sin(pi)"           # 计算表达式
matha run demo.matha           # 运行源文件
matha-cc compile demo.matha    # 编译
```

### 方式 3：离线部署（无网络环境）

```bash
# 在有网络机器上打包
python scripts/package_offline.py

# 拷贝到离线机器
# 运行部署
python deploy_offline.py

# 验证
python scripts/verify_offline.py
```

---

## 💡 示例程序

### Hello World

```matha
# hello.matha
func main() -> Void = () =>
  print("Hello, Matha!")
```

```bash
matha run hello.matha
# 输出: Hello, Matha!
```

### 斐波那契数列（展示 JIT + Memoization）

```matha
# fib.matha
func fib(n: Int) -> Int = (n) =>
  if n < 2 then n else fib(n-1) + fib(n-2)

#1：[fib(30)]  # 首次运行较慢
#2：[fib(30)]  # 瞬间完成（Memoization 缓存）
```

```bash
matha run fib.matha
```

### 物理计算（库仑力）

```matha
# coulomb.matha
# 库仑定律: F = k * q1 * q2 / r^2
# 计算两个电荷之间的力

func coulomb_force(k: Float, q1: Float, q2: Float, r: Float) -> Float =
  (k, q1, q2, r) => k * q1 * q2 / (r * r)

@:k = 8.99e9      # 真空介电常数
@:q1 = 1.6e-19    # 电荷 1 (C)
@:q2 = 1.6e-19    # 电荷 2 (C)
@:r = 1e-10       # 距离 (m)

#1：[coulomb_force(k, q1, q2, r)]
```

### 矩阵运算

```matha
# matrix.matha
use 线性代数

@:A = [[1, 2], [3, 4]]
@:B = [[5, 6], [7, 8]]

# 矩阵乘法
#1：[A @ B]
# 行列式
#2：[det(A)]
# 特征值
#3：[eigvals(A)]
```

---

## 📚 学习路径

| 阶段 | 内容 | 预估时间 |
|------|------|----------|
| 入门 | [安装指南](getting-started/installation.md) → [第一个程序](getting-started/first-program.md) → [REPL 使用](getting-started/repl.md) | 30 分钟 |
| 基础 | [语法概览](language-reference/syntax.md) → [表达式](language-reference/expressions.md) → [控制流](language-reference/control-flow.md) | 2 小时 |
| 进阶 | [函数与闭包](language-reference/functions.md) → [模块系统](language-reference/modules.md) → [类型系统](language-reference/types.md) | 4 小时 |
| 实战 | [标准库](stdlib/overview.md) → [领域模块](domains/overview.md) → [多语言转译](advanced/multilang.md) | 6 小时 |
| 专家 | [JIT 优化](advanced/jit.md) → [性能分析](advanced/profiling.md) → [编译器开发](dev/compiler.md) | 持续学习 |

---

## 🏗️ 架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        Matha 用户层                              │
│  .matha 源码  │  REPL  │  可视化编程  │  自然语言输入           │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Matha 核心层                                │
│  词法分析  →  语法分析  →  类型检查  →  MIR 生成  →  优化管线      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      执行后端层                                  │
│  解释器    │  M3V 虚拟机    │  MathaVM    │  x86-64 原生代码    │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      基础设施层                                  │
│  标准库(54域)  │  依赖管理  │  离线存储  │  LSP/诊断  │  包管理器  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 生态系统

| 组件 | 仓库 | 状态 |
|------|------|------|
| 核心语言 | matha | ✅ 活跃 |
| VS Code 扩展 | vscode-matha | ✅ 发布中 |
| 认证服务 | matha-auth | ✅ 生产就绪 |
| Tree-sitter 语法高亮 | matha-treesitter | ✅ 完成 |
| Python 绑定 | matha-python | 🔄 开发中 |
| Rust 绑定 | matha-rs | 📋 计划中 |

---

## 🤝 参与贡献

1. Fork 仓库
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 发起 Pull Request

---

## 📄 许可证

BSD-2-Clause License - 详见 [LICENSE](https://github.com/zzk2025r/matha/blob/main/LICENSE)

---

## 🔗 相关链接

- **GitHub**: https://github.com/zzk2025r/matha
- **PyPI**: https://pypi.org/project/matha/
- **文档**: https://matha.readthedocs.io/
- **问题反馈**: https://github.com/zzk2025r/matha/issues
- **更新日志**: [CHANGELOG.md](../CHANGELOG.md)