# Matha

自举式领域专用语言与解释器系统。

## 系统状态

- **版本：** v3.0
- **领域模块：** 54
- **测试用例：** 364
- **通过率：** 100%

## 快速开始

```bash
# 运行测试
python -m unittest discover -s tests -p "test_*.py"

# 运行单测
python tests/test_bootstrap.py

# 启动 REPL
python matha/repl.py
```

## 项目结构

```
matha/
├── src/                    # 核心源代码
│   ├── domains/           # 54个领域模块
│   ├── interp.py          # 解释器核心
│   ├── vm.py              # MIR 级虚拟机
│   ├── compiler/          # JIT/AOT/LLVM 编译器
│   └── tools/             # 工具（火焰图、性能分析）
├── tests/                  # 测试套件 (364 用例)
├── matha/                  # Matha 源文件
├── scripts/               # 构建脚本
├── docs/                  # 技术文档
└── Makefile               # RISC-V 构建系统
```

## 领域覆盖

| 类别 | 数量 |
|------|------|
| 核心物理/工程 | 29 |
| AI/数据科学 | 8 |
| 新兴领域 | 17 |
| **总计** | **54** |

## 多语言增强 v2.0

- **多语言代码生成**：Python/JS/C/C++/Rust/Go/Java/Matha
- **多语言交叉验证**：MultiLangVerifier 自动编译执行对比
- **CSP 并发模型**：进程级并发绕过 GIL
- **增强类型系统**：依赖类型/子类型/精炼类型
- **性能基准测试**：Matha vs Rust 完整对比框架

## 文档

- [多语言转译技术文档](docs/multilang_translator_technical_doc.md)
- [Matha vs 编程语言对比分析](docs/matha_vs_languages_analysis.md)
- [性能差距分析](docs/performance_gap_analysis.md)
- [基准测试报告](docs/benchmark_rust_report.md)
- [最终交付报告](docs/FINAL_DELIVERY_REPORT_v2.4.0.md)
- [升级报告 v2.5](docs/UPGRADE_REPORT_v2.5.md)
