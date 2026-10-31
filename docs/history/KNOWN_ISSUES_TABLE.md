# Matha v4.3 发布说明 - 已知问题

> 版本：4.3.0
> 日期：2025-07-26

---

## 已知问题

| 编号 | 问题描述 | 影响范围 | 严重程度 | 解决方案 |
|---|---|---|---|---|
| KNP-001 | LLM 意图解析需要 API Key | LLM 解析功能 | ⚠️ 中 | 安装 anthropic/deepseek SDK 或配置 API Key |
| KNP-002 | VS Code 插件需要 TypeScript 编译 | VS Code 扩展 | ⚠️ 中 | 安装 Node.js + npm 后运行 `npm install && npm run compile` |
| KNP-003 | Jupyter 扩展需要 IPython | Jupyter Notebook | ⚠️ 中 | 运行 `pip install ipython jupyter` |
| KNP-004 | 依赖缓存内存占用随包数量增加 | matha-pkg | ℹ️ 低 | 大型项目手动调用 `resolver.clear_cache()` |
| KNP-005 | 长文本意图分解准确率下降 | 意图分解 | ⚠️ 中 | 将复杂任务拆分为多个子任务 |
| KNP-006 | 某些数学函数命名不一致 | 标准库 | ℹ️ 低 | 使用统一别名：`from src.stdlib import *` |
| KNP-007 | Windows 下 multiprocessing spawn 模式限制 | HAL 并发 | ⚠️ 中 | Worker 函数必须定义在模块顶层 |
| KNP-008 | LLM 降级时置信度固定为 0.50 | 意图解析 | ℹ️ 低 | 无影响，降级模式正常工作 |

---

## 快速修复

```bash
# 1. 运行预检
python preflight_check.py

# 2. 安装缺少的依赖
pip install anthropic openai ipython jupyter
npm install -g vsce

# 3. 配置 API Key
export MATHA_LLM_API_KEY=your_key
export MATHA_LLM_MODEL=deepseek-chat
```
