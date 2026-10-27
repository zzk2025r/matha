# HAL v4.1 生产环境部署检查清单

> 基于性能报告：docs/HAL_PERFORMANCE_REPORT_v4.1.md  
> 更新时间：2025-07-26  
> 版本：v4.1 (异步队列优化版)

---

## 一、部署前检查

### 1.1 环境要求

- [ ] Python ≥ 3.8 (当前: 3.11 ✅)
- [ ] 内存占用 < 50MB (当前: ~10MB ✅)
- [ ] 无外部依赖 (当前: 仅标准库 ✅)
- [ ] 支持 asyncio (Python 3.7+ ✅)

### 1.2 异步队列参数评估

| 参数 | 当前值 | 推荐值 | 评估 | 状态 |
|---|---|---|---|---|
| `maxsize` | 1000 | 1000 | ✅ 安全系数 666x | 无需调整 |
| `_enabled` | False | False | ✅ 生产默认关闭 | 无需调整 |
| 消费线程 | 1 | 1 | ✅ 足够 | 无需调整 |
| 丢弃策略 | 静默丢弃 | 静默丢弃 | ✅ 符合预期 | 无需调整 |
| ERROR 降级 | 同步写入 | 同步写入 | ✅ 确保不丢失 | 无需调整 |

**结论**：当前配置适合生产环境，无需调整。

### 1.3 性能验收

| 指标 | 最低要求 | 当前值 | 状态 |
|---|---|---|---|
| 单次写入延迟 | < 100μs | 3.2μs | ✅ 31x 超标 |
| 批量写入延迟 | < 100μs | 5.0μs | ✅ 20x 超标 |
| 吞吐量 | ≥ 10K ops/sec | 430K ops/sec | ✅ 43x 超标 |
| 并发访问 (8线程) | ≥ 80K ops/sec | 247K ops/sec | ✅ 3x 超标 |
| 错误率 | = 0 | 0 | ✅ 通过 |
| 队列溢出处理 | 不崩溃 | graceful degrade | ✅ 通过 |

---

## 二、配置检查

### 2.1 生产环境配置

```python
# src/hardware/hal.py 生产配置
import logging

# 关闭 HAL 日志（生产默认）
logging.getLogger("matha.hal").setLevel(logging.CRITICAL)

# 或仅开启 ERROR
logging.getLogger("matha.hal").setLevel(logging.ERROR)

# 异步队列默认关闭
# AsyncHALLogger._enabled = False (默认)
```

### 2.2 监控指标阈值

| 指标 | 警告阈值 | 严重阈值 |
|---|---|---|
| 丢弃日志数 | > 100/分钟 | > 1000/分钟 |
| 队列深度 | > 500 | > 900 |
| 写入错误率 | > 0.1% | > 1% |
| P99 延迟 | > 50μs | > 100μs |
| 吞吐下降 | < 80% 基准 | < 50% 基准 |

---

## 三、部署步骤

```bash
# 1. 安装
pip install -r requirements.txt

# 2. 冒烟测试（快速验证核心功能）
python -m unittest tests.test_hardware_hal tests.test_hal_queue_protection -v

# 3. 压力测试（验证性能）
python tests/stress_test_10khz.py --frequency 10000 --duration 5

# 4. pytest 回归测试
pytest tests/test_hal_perf.py -v

# 5. 启动服务
python main.py
```

---

## 四、测试覆盖

| 测试模块 | 用例数 | 状态 |
|---|---|---|
| test_intent_decomposer | 28 | ✅ |
| test_hardware_hal | 14 | ✅ |
| test_language_adapters | 16 | ✅ |
| test_hal_queue_protection | 4 | ✅ |
| test_llm_parser | 14 | ✅ |
| test_arithmetic | 28 | ✅ |
| **总计** | **104** | **✅** |

---

## 五、回滚预案

| 场景 | 措施 | 时间 |
|---|---|---|
| 性能不达标 | 回退 v4.0 | 5 分钟 |
| 队列溢出频繁 | 增大 maxsize 到 5000 | 1 分钟 |
| 并发崩溃 | 禁用异步日志 | 1 分钟 |
| 内存泄漏 | 重启服务 | 2 分钟 |
| 日志丢失 | 降级同步日志 | 30 秒 |

---

## 六、CI/CD 集成

### 6.1 GitHub Actions 工作流

| 工作流 | 触发条件 | 钉钉通知 |
|---|---|---|
| stress_test.yml | push/定时/手动 | ✅ 成功/失败 |
| benchmark.yml | push/定时/手动 | ✅ 成功/失败 |

### 6.2 钉钉通知配置

```yaml
env:
  DINGTALK_WEBHOOK: ${{ secrets.DINGTALK_WEBHOOK }}

# 成功通知
curl -X POST "$DINGTALK_WEBHOOK" -d '{"msgtype":"text","text":{"content":"✅ HAL 压力测试通过"}}'

# 失败通知
curl -X POST "$DINGTALK_WEBHOOK" -d '{"msgtype":"text","text":{"content":"❌ HAL 压力测试失败"}}'
```

### 6.3 配置步骤

1. 在钉钉群添加**自定义机器人**
2. 获取 **Webhook URL**
3. 在 GitHub → Settings → Secrets 添加：
   - 名称：`DINGTALK_WEBHOOK`
   - 值：机器人 Webhook URL

---

## 七、检查清单总结

- [x] Python ≥ 3.8
- [x] 单元测试全部通过 (104/104)
- [x] 压力测试通过 (10kHz, 零错误)
- [x] 队列保护机制验证通过
- [x] 生产日志级别设为 CRITICAL
- [x] CI 流水线配置完成
- [x] 钉钉通知配置完成
- [ ] 监控告警配置（待外部系统对接）
- [x] 回滚预案文档就绪
- [x] 性能基准数据记录

**结论**：✅ 当前配置适合生产环境部署

---

## 八、快速命令

```bash
# 运行所有测试
python -m unittest discover -s tests -p "test_*.py" -v

# 运行 pytest 性能测试
pytest tests/test_hal_perf.py -v

# 运行压力测试
python tests/stress_test_10khz.py --frequency 10000 --duration 5

# 运行冒烟测试
python -m unittest tests.test_hardware_hal tests.test_hal_queue_protection -v
```
