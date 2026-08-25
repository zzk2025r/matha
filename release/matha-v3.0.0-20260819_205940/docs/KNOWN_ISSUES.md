# Matha v4.3 已知问题

> 版本：4.3.0
> 更新日期：2025-07-26
> 状态：📋 持续跟踪

---

## 已知问题列表

| 编号 | 问题描述 | 影响范围 | 严重程度 | 解决方案 |
|---|---|---|---|---|
| **KNP-001** | LLM 意图解析需要 API Key | LLM 解析功能 | ⚠️ 中 | 安装 anthropic/deepseek SDK 或配置 API Key |
| **KNP-002** | VS Code 插件需要 TypeScript 编译 | VS Code 扩展 | ⚠️ 中 | 安装 Node.js + npm 后运行 `npm install && npm run compile` |
| **KNP-003** | Jupyter 扩展需要 IPython | Jupyter Notebook | ⚠️ 中 | 运行 `pip install ipython jupyter` |
| **KNP-004** | 依赖缓存内存占用随包数量增加 | matha-pkg | ℹ️ 低 | 大型项目手动调用 `resolver.clear_cache()` |
| **KNP-005** | 长文本意图分解准确率下降 | 意图分解 | ⚠️ 中 | 将复杂任务拆分为多个子任务 |
| **KNP-006** | 某些数学函数命名不一致 | 标准库 | ℹ️ 低 | 使用统一别名：`from src.stdlib import *` |
| **KNP-007** | Windows 下 multiprocessing spawn 模式限制 | HAL 并发 | ⚠️ 中 | Worker 函数必须定义在模块顶层 |
| **KNP-008** | LLM 降级时置信度固定为 0.50 | 意图解析 | ℹ️ 低 | 无影响，降级模式正常工作 |

---

## 快速修复

```bash
# 1. 运行预检，查看当前环境状态
python preflight_check.py

# 2. 一键安装所有依赖
python install_dependencies.py --all

# 3. 或按需安装
python install_dependencies.py --vscode   # KNP-002
python install_dependencies.py --jupyter  # KNP-003
python install_dependencies.py --llm      # KNP-001
```

---

## 问题详情

### KNP-001: LLM 意图解析需要 API Key

**现象**：调用 `LLMIntentParser.parse()` 时提示缺少 API Key。

**影响**：
- 无 API Key 时，LLM 解析功能不可用
- 自动降级到正则匹配，准确率略有下降

**解决方案**：
```bash
# 安装 LLM SDK
pip install anthropic      # Claude
pip install deepseek-ai    # DeepSeek
pip install openai         # GPT

# 配置 API Key
export MATHA_LLM_API_KEY=your_key
export MATHA_LLM_MODEL=deepseek-chat
```

**预检提示**：
```
【3. LLM 依赖】
  ⚠️ Claude API ⚠️ 未安装
  ⚠️ GPT API ⚠️ 未安装
  ⚠️ Ollama 本地模型 ⚠️ 未安装
```

---

### KNP-002: VS Code 插件需要 TypeScript 编译

**现象**：VS Code 插件源码需要先编译才能使用。

**影响**：
- 无法直接使用源码，需要编译步骤
- 发布到 Marketplace 需要 vsce 工具

**解决方案**：
```bash
# 一键安装
python install_dependencies.py --vscode

# 或手动安装
cd extensions/vscode-matha
npm install          # 安装依赖
npm run compile      # 编译 TypeScript
vsce package         # 打包为 VSIX
code --install-extension matha-0.1.0.vsix  # 安装到 VS Code
```

**预检提示**：
```
【5. VS Code 插件依赖】
  ✅ Node.js v24.14.1
  ⚠️ npm 未安装
  ⚠️ vsce 未安装
```

---

### KNP-003: Jupyter 扩展需要 IPython

**现象**：在普通 Python 环境中无法使用 `%matha` 命令。

**影响**：
- 需要 Jupyter Notebook 或 IPython 终端
- 无法在普通 Python 脚本中使用魔法命令

**解决方案**：
```bash
# 一键安装
python install_dependencies.py --jupyter

# 或手动安装
pip install ipython jupyter

# 在 Notebook 中使用
%load_ext matha.jupyter
%matha 计算 100 以内所有素数
```

**预检提示**：
```
【4. Jupyter 依赖】
  ⚠️ IPython ⚠️ 未安装
  ⚠️ Jupyter ⚠️ 未安装
```

---

### KNP-004: 依赖缓存内存占用

**现象**：matha-pkg 的依赖解析缓存会占用内存。

**影响**：
- 大型项目（100+ 包）可能占用较多内存
- 默认情况下缓存会在进程结束时自动释放

**解决方案**：
```python
from src.pkg_manager import MathaPackage

pkg = MathaPackage()
# 手动清除缓存
pkg._resolver.clear_cache()
```

---

### KNP-005: 长文本意图分解准确率

**现象**：输入文本超过 100 字时，正则匹配可能无法准确分解意图。

**影响**：
- 复杂任务可能被识别为单个 ATOMIC 节点
- 子意图数量可能少于预期

**解决方案**：
```python
# 推荐：拆分为多个子任务
text1 = "求解方程 x^2 - 3x + 2 = 0"
text2 = "验证 x=1 是否满足方程"
text3 = "计算两个解的乘积"

for text in [text1, text2, text3]:
    root = ide.decompose(text)
    # 处理每个子意图...
```

---

### KNP-006: 数学函数命名不一致

**现象**：部分标准库函数使用英文命名，部分使用中文命名。

**影响**：
- 用户可能需要查找正确的函数名
- API 一致性略有影响

**解决方案**：
```python
# 使用统一入口
from src.stdlib import (
    add, sqrt, factorial,      # 算术
    solve_quadratic,           # 代数
    derivative, integral,      # 微积分
    AND, OR, NOT,              # 逻辑
)

# 或使用别名
from src.stdlib.arithmetic import sqrt as square_root
```

---

### KNP-007: Windows multiprocessing spawn 模式

**现象**：Windows 使用 spawn 模式启动进程，要求 Worker 函数定义在模块顶层。

**影响**：
- 局部函数无法作为 Worker
- 需要调整代码结构

**解决方案**：
```python
# ✓ 正确：模块级函数
def _gpio_writer_worker(worker_id, pin, iterations, result_queue):
    ...

# ✗ 错误：局部函数
def run_test():
    def worker(...):  # 无法序列化
        ...
```

---

### KNP-008: LLM 降级置信度固定

**现象**：当 LLM API 不可用时，降级到正则匹配，置信度固定为 0.50。

**影响**：
- 无法区分高置信度和低置信度的正则匹配结果
- 对下游逻辑可能有影响

**解决方案**：
```python
# 检查是否使用降级模式
if intent.confidence < 0.7:
    print("⚠️  使用正则匹配降级，建议配置 LLM API Key")
```

---

## 问题跟踪

- **GitHub Issues**: https://github.com/your-org/matha/issues
- **邮件反馈**: matha@example.com
- **文档**: https://matha.docs

---

## 版本历史

| 版本 | 日期 | 新增问题 | 已解决 | 状态 |
|---|---|---|---|---|
| v4.3.0 | 2025-07-26 | 8 | 0 | 已知 |
| v4.2.0 | 2025-07-25 | 3 | 2 | 部分 |
| v4.1.0 | 2025-07-24 | 1 | 1 | 已解决 |

---

**最后更新**：2025-07-26
