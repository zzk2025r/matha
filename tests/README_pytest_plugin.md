# HAL 性能测试 Pytest 插件

提供 pytest fixture 和 marker，方便快速运行 HAL 压力测试。

## 安装

```bash
pip install pytest -q
```

## 用法

```bash
# 运行所有 HAL 性能测试
pytest tests/test_hal_perf.py -v

# 运行特定测试
pytest tests/test_hal_perf.py -k "test_10khz"

# 运行基准测试
pytest tests/test_hal_perf.py --benchmark

# 指定测试时长
pytest tests/test_hal_perf.py --duration 10

# 指定目标频率
pytest tests/test_hal_perf.py --frequency 20000
```

## 测试用例

| 测试类 | 测试方法 | 说明 |
|---|---|---|
| Test10kHzStress | test_single_write_10khz | 单次写入 10kHz |
| Test10kHzStress | test_batch_write_10khz | 批量写入 10kHz |
| TestConcurrentAccess | test_concurrent_write | 8 线程并发写入 |
| TestQueueProtection | test_queue_overflow_handling | 队列溢出保护 |
| TestBenchmark | test_write_latency | 写入延迟 < 10μs |
| TestBenchmark | test_throughput | 吞吐量 ≥ 100K ops/sec |

## Fixtures

| Fixture | 说明 |
|---|---|
| `hal_ops` | HAL 操作对象 |
| `gpio_device` | GPIO 设备 (pin 18) |
| `multi_gpio_devices` | 多路 GPIO 设备 [18,19,20,21] |
| `async_logger` | 异步日志记录器 |
| `perf_monitor` | 性能监控器 |

## CI 集成

已在 `.github/workflows/stress_test.yml` 中集成：

```yaml
- name: 运行 pytest 性能测试
  run: |
    pip install pytest -q
    python -m pytest tests/test_hal_perf.py -v --benchmark
```

## 钉钉通知

测试成功/失败时自动发送钉钉通知：

```yaml
- name: 钉钉通知 - 成功
  if: success()
  run: |
    curl -X POST "$DINGTALK_WEBHOOK" ...

- name: 钉钉通知 - 失败
  if: failure()
  run: |
    curl -X POST "$DINGTALK_WEBHOOK" ...
```

需要在 GitHub Secrets 中配置：
- `DINGTALK_WEBHOOK`: 钉钉机器人 Webhook URL
