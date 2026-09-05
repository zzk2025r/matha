# Matha 离线部署包

## 概述

本目录包含 Matha 数学编程语言的完整离线安装包。

- 生成时间: 2026-08-31 01:35:51
- Python 版本: 3.14
- 平台: windows-amd64

## 目录结构

```
offline_package/
├── matha-source-*.tar.gz    # Matha 源码包
├── matha-pip-packages-*.tar.gz  # pip 依赖包
├── offline_requirements.txt # 离线依赖清单
├── deploy_offline.py        # 离线部署脚本
├── verify_offline.py        # 离线验证脚本
├── checksums.sha256        # 校验和文件
└── README.md                # 本文件
```

## 离线部署步骤

### 1. 传输到目标机器

将整个 `offline_package/` 目录通过 U 盘、内网传输等方式拷贝到目标机器。

### 2. 运行部署脚本

```bash
# 进入离线包目录
cd offline_package

# 运行部署（会自动安装依赖和运行测试）
python deploy_offline.py

# 或跳过测试加快部署
python deploy_offline.py --skip-tests
```

### 3. 验证安装

```bash
# 验证环境
python deploy_offline.py --check

# 或手动验证
python verify_offline.py
```

### 4. 开始使用

```bash
# 启动 REPL
matha

# 编译运行 Matha 程序
matha run examples/demo.matha

# 编译到 C
matha-cc compile demo.matha -o c

# 编译到 Python
matha-cc compile demo.matha -o python

# 运行测试
python -m unittest discover -s tests -p "test_*.py"
```

## 核心功能（离线可用）

- [x] 解释器/编译器（Lexer → Parser → MIR → CodeGen）
- [x] JIT 函数级编译 + 自动 Memoization
- [x] C/Python/Matha 代码生成
- [x] C++/Rust/Go/Java 代码生成
- [x] 性能 Profiler（火焰图 + Markdown/JSON 报告）
- [x] LSP 语言服务器（补全/悬停/定义跳转/诊断）
- [x] 包管理器（本地包管理）
- [x] API 文档生成（Markdown/HTML/JSON）
- [x] 多语言交叉验证
- [x] 类型系统增强（依赖类型/泛型/子类型）
- [x] CSP 进程级并发
- [x] SQLite 离线存储

## 网络依赖（离线不可用）

- 远程包安装/搜索（`matha install --remote`）
- LLM 意图解析（自动降级到正则解析）
- Growth Engine 网络搜索（自动降级到本地）
- 移动端 WebSocket 协作
- 3D 代码生成 CDN 依赖

## 校验文件完整性

```bash
# 在项目根目录运行
sha256sum -c checksums.sha256

# 或手动计算
python -c "import hashlib; print(hashlib.sha256(open('matha-source-*.tar.gz','rb').read()).hexdigest())"
```
