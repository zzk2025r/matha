# HAL 运维部署操作手册

> 版本：v4.2  
> 适用环境：生产 / 预发布 / 开发  
> 更新日期：2025-07-26

---

## 一、概述

Matha HAL v4.2 已完成 multiprocessing 并发改造，解决 Python GIL 导致的并发瓶颈。本文档面向运维团队，说明部署配置、参数调优和故障排查。

---

## 二、Worker 配置参数

### 2.1 核心参数

| 参数 | 默认值 | 推荐值 | 说明 |
|---|---|---|---|
| `MATHA_WORKERS` | 8 | **等于 CPU 核数** | 并发 Worker 进程数 |
| `MATHA_ITERATIONS` | 3000 | 1000-10000 | 每个 Worker 测试迭代次数 |
| `MATHA_TARGET_FREQ` | 100000 | 10000-100000 | 目标频率 (Hz) |
| `MATHA_CHANNELS` | 4 | 1-8 | GPIO 通道数 |

### 2.2 参数计算公式

```
推荐 Worker 数 = CPU 物理核数（不考虑超线程）
推荐队列大小 = 峰值速率 × 2秒缓冲
```

### 2.3 检测 CPU 核数

```bash
# Linux / macOS
nproc
# 或
sysctl -n hw.ncpu

# Windows PowerShell
[System.Environment]::ProcessorCount
```

### 2.4 生产环境推荐配置

```bash
# 4 核机器（当前测试环境）
MATHA_WORKERS=4
MATHA_TARGET_FREQ=400000

# 8 核机器（推荐生产环境）
MATHA_WORKERS=8
MATHA_TARGET_FREQ=800000

# 16 核机器（高性能服务器）
MATHA_WORKERS=16
MATHA_TARGET_FREQ=1600000
```

---

## 三、部署步骤

### 3.1 环境检查

```bash
# 1. 检查 Python 版本
python --version  # 需要 ≥ 3.8

# 2. 检查 CPU 核数
nproc  # 记录此值，用于配置 MATHA_WORKERS

# 3. 运行冒烟测试
python -m unittest tests.test_hardware_hal tests.test_hal_queue_protection -v
```

### 3.2 部署配置

```yaml
# .env 或 systemd 环境变量
MATHA_WORKERS=4              # 根据 CPU 核数调整
MATHA_LOG_LEVEL=CRITICAL     # 生产环境关闭日志
MATHA_ASYNC_QUEUE_ENABLED=false  # 异步队列默认关闭
MATHA_LLM_API_KEY=           # LLM 意图解析器（可选）
```

### 3.3 启动服务

```bash
# 方式 1：直接启动
python main.py

# 方式 2：使用 gunicorn（推荐生产）
gunicorn main:app --workers 4 --timeout 30

# 方式 3：使用 supervisor
supervisorctl restart matha-hal
```

### 3.4 验证部署

```bash
# 运行全量测试
python -m unittest discover -s tests -p "test_*.py" -v

# 运行压力测试
python tests/stress_test_10khz.py --frequency 10000 --duration 5

# 运行 multiprocessing 测试
python tests/test_hal_multiprocessing.py --workers 4 --iterations 3000
```

---

## 四、性能监控

### 4.1 关键指标

| 指标 | 警告阈值 | 严重阈值 | 行动 |
|---|---|---|---|
| 吞吐量 | < 80% 基准 | < 50% 基准 | 检查 Worker 配置 |
| P99 延迟 | > 20μs | > 50μs | 检查 GIL 竞争 |
| 队列丢弃 | > 100/分钟 | > 1000/分钟 | 增大队列大小 |
| 错误率 | > 0.1% | > 1% | 检查硬件 |

### 4.2 监控命令

```bash
# 查看当前性能
python -c "
from src.hardware.hal import _hal_async_logger
print(_hal_async_logger.get_stats())
"

# 运行性能基准
python -m pytest tests/test_hal_perf.py::TestBenchmark -v
```

### 4.3 日志查看

```bash
# 生产环境日志级别：CRITICAL（仅错误）
# 调试环境日志级别：DEBUG

tail -f /var/log/matha/hal.log | grep -E "ERROR|WARNING"
```

---

## 五、故障排查

### 5.1 吞吐量不达标

**症状**：实际吞吐量 < 目标 80%

**排查步骤**：
1. 检查 Worker 数是否等于 CPU 核数
2. 检查是否有其他高 CPU 进程
3. 运行 `stress_test_10khz.py` 验证基线性能

**解决方案**：
```bash
# 调整 Worker 数
export MATHA_WORKERS=$(nproc)

# 或手动指定
python tests/test_hal_multiprocessing.py --workers 4 --iterations 3000
```

### 5.2 延迟 spikes

**症状**：P99.9 延迟突然跳升

**排查步骤**：
1. 检查是否使用 multiprocessing 模式
2. 检查日志 I/O 是否开启
3. 检查队列是否频繁溢出

**解决方案**：
```python
# 确保使用 multiprocessing
from src.hardware.hal import run_multiprocess_stress_test
result = run_multiprocess_stress_test(num_workers=4)

# 关闭日志
import logging
logging.getLogger("matha.hal").setLevel(logging.CRITICAL)
```

### 5.3 进程创建失败

**症状**：`RuntimeError: can't start new thread`

**排查步骤**：
1. 检查系统进程数限制
2. 检查内存是否充足

**解决方案**：
```bash
# 增加进程限制
ulimit -u 4096

# 减少 Worker 数
export MATHA_WORKERS=2
```

---

## 六、CI/CD 配置

### 6.1 GitHub Actions 工作流

[.github/workflows/stress_test.yml](../.github/workflows/stress_test.yml)

```yaml
env:
  MATHA_WORKERS: 4  # 根据 CI Runner 核数调整
  MATHA_ENV: ${{ matrix.env }}
```

### 6.2 自动Worker配置

```bash
# 检测 CI 环境 CPU 核数并自动配置
export MATHA_WORKERS=$(nproc 2>/dev/null || echo 4)
python tests/test_hal_multiprocessing.py --workers $MATHA_WORKERS --iterations 3000
```

---

## 七、变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2025-07-26 | v4.2 | multiprocessing 改造，解决 GIL 问题 |
| 2025-07-26 | v4.1 | 异步队列批处理优化 |
| 2025-07-25 | v4.0 | 初始版本 |

---

## 八、相关链接

- [HAL 性能对比报告](./MULTIPROCESSING_COMPARISON_REPORT.md)
- [GIL 问题技术文档](./techdocs/gil_multiprocessing_fix.md)
- [部署检查清单](./DEPLOYMENT_CHECKLIST_v4.1.md)
- [最终交付文档](./HAL_V4.1_FINAL_DELIVERY.md)
