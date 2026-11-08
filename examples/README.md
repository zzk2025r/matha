# Matha 示例

## 目录结构

```
examples/
├── basic_examples.matha    # 基础示例（可运行）
├── ai/                     # AI 示例（阶段 4 重写，四个可运行 .matha + 门禁锁）
│   ├── neural_network.matha
│   ├── data_pipeline.matha
│   ├── data.csv
│   ├── genetic_algo.matha
│   └── ai_framework.matha
├── game/                   # 游戏开发文档示例（仅 README，代码块未重写不可运行）
└── web/                    # Web 开发文档示例（仅 README，代码块未重写不可运行）
```

## 运行示例

```bash
# 运行 Matha 示例
matha run examples/basic_examples.matha

# AI 示例（自仓库根目录）
matha run examples/ai/neural_network.matha
```

## 示例说明

### basic_examples.matha

包含基础计算、函数定义、列表操作、字符串处理、JSON处理、随机数、领域模块等示例。

### ai/

神经网络训练演示、数据科学管线、遗传算法代码工具、AI 框架矩阵乘法，
全部经主执行链真跑并挂门禁锁（`tests/test_examples_ai.py`），
详见 [ai/README.md](ai/README.md)。

### game/ 与 web/

历史文档示例：README 中的代码块为 Python 风格伪代码，不是合法 Matha，
尚未重写（不在阶段 4 范围）。

---

*Matha v4.6 | 示例*