# Matha

自举式领域专用语言与解释器系统。

## 系统状态

- **版本：** v3.0
- **领域模块：** 54
- **测试用例：** 300
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
│   └── tools/             # 工具（火焰图、性能分析）
├── tests/                  # 测试套件
├── matha/                  # Matha 源文件
├── scripts/               # 构建脚本
└── docs/                  # 技术文档
```

## 领域覆盖

| 类别 | 数量 |
|------|------|
| 核心物理/工程 | 29 |
| AI/数据科学 | 8 |
| 新兴领域 | 17 |
| **总计** | **54** |

## 文档

- [最终交付报告](docs/FINAL_DELIVERY_REPORT_v2.4.0.md)
- [升级报告 v2.5](docs/UPGRADE_REPORT_v2.5.md)
- [WASM 打包指南](docs/WASM_PACKAGING_GUIDE.md)
- [协作协议](docs/COLLABORATION_PROTOCOL.md)
- [性能分析](docs/PERFORMANCE_REPORT.md)
