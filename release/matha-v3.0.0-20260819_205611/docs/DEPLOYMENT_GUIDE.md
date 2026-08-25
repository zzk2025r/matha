# Matha v4.4 生产环境部署配置说明

> 生成时间：2025-07-26
> 版本：4.4.0

---

## 一、快速部署

### 1.1 完整部署流程

```bash
# 执行完整部署（安装依赖 + 设置环境 + 健康检查）
python deploy_production.py --full-setup --report

# 仅安装核心依赖
python deploy_production.py --install core

# 仅安装可选依赖（推荐）
python deploy_production.py --install optional

# 仅安装全部依赖
python deploy_production.py --install all

# 设置环境变量
python deploy_production.py --setup-env

# 运行健康检查
python deploy_production.py --health-check
```

### 1.2 依赖列表

**核心依赖（必须）**：
- `sympy>=1.14.0` — 符号计算引擎

**可选依赖（推荐）**：
- `numpy>=1.24.0` — 高性能矩阵运算（性能提升 1000-2000x）
- `scipy>=1.10.0` — 科学计算扩展
- `numba>=0.57.0` — JIT 编译优化

**开发依赖**：
- `pytest>=7.0.0` — 测试框架
- `pytest-cov>=4.0.0` — 测试覆盖率
- `black>=23.0.0` — 代码格式化
- `flake8>=6.0.0` — 代码检查

---

## 二、环境变量配置

部署脚本会自动设置以下环境变量：

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `MATHA_ENV` | production | 运行环境 |
| `MATHA_LOG_LEVEL` | INFO | 日志级别 |
| `MATHA_CACHE_SIZE` | 1000 | 缓存最大条目数 |
| `MATHA_MAX_WORKERS` | 4 | 并行工作线程数 |
| `MATHA_SPARSE_THRESHOLD` | 0.9 | 稀疏矩阵阈值 |
| `MATHA_NUMPY_AVAILABLE` | true | NumPy 可用性标志 |
| `MATHA_SYMPY_AVAILABLE` | true | SymPy 可用性标志 |
| `MATHA_SVD_USE_NUMPY` | true | SVD 优先使用 NumPy |
| `MATHA_SVD_MAX_ITER` | 100 | SVD 最大迭代次数 |
| `MATHA_PARALLEL_ENABLED` | true | 并行计算开关 |
| `MATHA_THREAD_POOL_SIZE` | 4 | 线程池大小 |

---

## 三、性能配置

### 3.1 推荐配置（生产环境）

```json
{
  "cache_max_size": 1000,
  "sparse_threshold": 0.9,
  "svd_max_iter": 100,
  "parallel_workers": 4,
  "benchmark_iterations": 10,
  "benchmark_warmup": 3
}
```

### 3.2 性能优化建议

| 优化项 | 配置值 | 预期效果 |
|---|---|---|
| 安装 NumPy | 必须 | 1000-2000x 加速 |
| 启用稀疏检测 | threshold=0.9 | 自动选择最优算法 |
| 并行计算 | workers=4 | 2-3x 加速 |
| 缓存 | max_size=1000 | 1-2x 加速 |

---

## 四、目录结构

部署后会创建以下目录：

```
matha/
├── logs/              # 日志目录
├── data/              # 数据目录
├── cache/             # 缓存目录
├── config/            # 配置文件
│   └── production.json
├── .env               # 环境变量文件
└── docs/              # 文档目录
    ├── DEPLOYMENT_REPORT.md
    └── SVD_Final_Performance_Chart.md
```

---

## 五、健康检查

运行健康检查验证部署状态：

```bash
python deploy_production.py --health-check
```

检查项目：
- [x] Python 版本（需要 3.8+）
- [x] SymPy 安装
- [x] NumPy 安装（可选）
- [x] 环境变量设置
- [x] 必要目录创建
- [x] 基本功能测试

---

## 六、故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|---|---|---|
| SymPy 导入失败 | 未安装 | `pip install sympy>=1.14.0` |
| NumPy 未找到 | 未安装 | `pip install numpy>=1.24.0` |
| 缓存满 | 配置不当 | 调整 `MATHA_CACHE_SIZE` |
| 并行失败 | GIL 限制 | 减少 `MATHA_THREAD_POOL_SIZE` |

### 6.2 查看详细日志

```bash
python deploy_production.py --full-setup --verbose
```

---

## 七、性能基准

### 7.1 预期性能

| 矩阵规模 | 纯 Python | NumPy | 稀疏 SVD (90%+) |
|---|---|---|---|
| 10x10 | 44.58 ms | 0.04 ms | 30.00 ms |
| 50x50 | 1908 ms | 1.00 ms | 950 ms |
| 100x100 | ~15s | ~8 ms | ~7s |
| 500x500 | ~1900s | ~125 ms | ~950s |
| 1000x1000 | ~15000s | ~1s | ~7500s |

### 7.2 优化建议

1. **必须安装 NumPy** — 可获得 1000-2000x 性能提升
2. **启用稀疏优化** — 90%+ 稀疏度矩阵可获得 2-5x 加速
3. **使用并行计算** — 批量计算可获得 2-3x 加速

---

**文档生成时间**：2025-07-26
**文档版本**：v4.4
