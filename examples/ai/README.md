# AI 开发示例（阶段 4 重写：全部可运行）

本目录四个 `.matha` 示例均经主执行链真跑，并由 `tests/test_examples_ai.py`
入门禁锁（干净子进程 exec_api 运行 + 手算对拍）。历史上这里的六个
Python 风格伪代码块（`create_neural_network(input_size=784)` 等）不是
合法 Matha，已全部移除。

## 运行

```bash
# 自仓库根目录运行（data_pipeline 的 CSV 为相对路径）
matha run examples/ai/neural_network.matha
matha run examples/ai/data_pipeline.matha
matha run examples/ai/genetic_algo.matha
matha run examples/ai/ai_framework.matha
```

## 示例与预期输出

### 1. neural_network.matha — 前馈网络训练演示

`创建神经网络 → 添加层 → 训练模型 → 前向传播/预测` 全链。
预期：训练结果 `epochs_trained=100`、损失历史真读数；前向/预测输出
为 (0,1) 区间概率值。

口径：默认配置（100 轮、lr=0.001）为 API 演示，XOR **未收敛**
（loss≈0.25）；训练有效性主张不背书，收敛闭环由
`tests/test_neural_network_plugin.py` 与 `tests/test_ml_models_phase4.py`
（MLP XOR 真收敛）背书。

### 2. data_pipeline.matha — 数据科学管线

`创建数据集 → 加载CSV → 划分训练测试 → 归一化 → 准确率` 全链
（数据为本目录 `data.csv`）。
预期手算：准确率 `0.8`（4/5）；两半均为等差列，归一化后皆
`[[0,0],[1,1]]`。

### 3. genetic_algo.matha — 遗传算法与AI编写代码

预期手算：`NESMA估算(100) = 50.0`；`代码优化("a  b") = "a b"`；
`代码生成("func {name}(x) = x + {k}", {"name": "f", "k": 3})`
`= "func f(x) = x + 3"`。

### 4. ai_framework.matha — AI 框架数值腿

预期手算：`[[1,2],[3,4]] × [[5,6],[7,8]] = [[19,22],[43,50]]`；
`创建张量([2, 3])` 得 shape=(2,3) 零张量。

## 显式拒绝边界（不假成功）

- **CNN/RNN**：仓库内无背书实现，`创建CNN`/`创建RNN` 虽可构造，
  但 `添加卷积层`/`添加LSTM` 等构建方法显式抛 `NotImplementedError`
  （锁见 `tests/test_neural_network_plugin.py`）。
- **Matha 闭包跨语言回调**：`遗传算法进化`/`精英保留`/`超参数搜索`
  需要 Python 可调用适应度函数，传入 Matha 闭包显式抛 `ValueError`
  （锁见 `tests/test_genetic_algo_plugin.py`）。
- **ml.py 九种经典算法**（线性/逻辑回归、KMeans、决策树、随机森林、
  MLP、KNN、SVM、朴素贝叶斯）走 legacy registry 通道，不经
  `【加载领域】` 指令；Python 侧用法与行为锁见
  `tests/test_ml_models.py` / `tests/test_ml_models_phase4.py`。

---

*Matha v4.6 | AI 开发示例（阶段 4 重写）*