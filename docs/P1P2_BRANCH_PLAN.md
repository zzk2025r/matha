# P1/P2 待办任务拆解 — Git 分支与提交计划

> 生成日期: 2026-08-20
> 基于: docs/V100_Q4_EXECUTION_PLAN.md

---

## 分支总览

| 分支名 | 对应任务 | 优先级 | 状态 |
|---|---|---|---|
| `feat/optimize-memoize-dynamic-args` | P1 #2：参数动态化 | P1 | 已完成 |
| `feat/integration-tests` | P1 #3：集成测试补全 | P1 | 待建 |
| `feat/stress-test-10k` | P1 #4：压力测试扩展 | P1 | 待建 |
| `fix/learn-from-file-encoding` | P2 #5：编码容错 | P2 | 待建 |
| `feat/trig-identities` | P2 #6：三角恒等式规则 | P2 | 待建 |
| `docs/selfupgrade-autodebugger` | P2 #7：文档补全 | P2 | 待建 |
| `fix/test-defects-import` | P2 #8：ImportError 修复 | P2 | 待建 |
| `docs/treesitter-cli-readme` | P2 #9：CLI 文档 | P2 | 待建 |

---

## 已完成的分支

### `feat/optimize-memoize-dynamic-args` ✅

**变更范围：**
- `src/autonomous.py` — `_Sample` 新增 `args` 字段；`profile()` 存储 args；`optimize_memoize()` 使用 `sample.args` 替代硬编码 `[5]`
- `tests/test_autonomous.py` — 新增 `test_optimize_memoize_dynamic_args` 验证动态参数

**提交计划：**
```bash
git add src/autonomous.py tests/test_autonomous.py
git commit -m "feat(autonomous): optimize_memoize 使用采样实际参数替代硬编码 [5]

- _Sample 新增 args 字段，存储 profile() 时的实际参数
- optimize_memoize() 从 sample.args 读取参数，而非硬编码 [5]
- 新增 test_optimize_memoize_dynamic_args：profile('加十',[7]) → 特化函数结果 17

测试: test_autonomous 11/11 通过"
```

---

## 待建分支及提交计划

### `feat/integration-tests` (P1 #3)

**变更范围：** `tests/test_integration/`（新目录）

**提交计划：**
```bash
# 提交 1: 目录结构 + 基础测试框架
git add tests/test_integration/
git commit -m "test(integration): 新增端到端集成测试目录

- tests/test_integration/test_auto_debug_e2e.py: AutoDebugger 完整流程
- tests/test_integration/test_auto_optimize_e2e.py: PerformanceOptimizer 端到端
- tests/test_integration/test_self_grow_e2e.py: SelfGrower 完整生命周期"

# 提交 2: 10+ 个端到端用例
git add tests/test_integration/
git commit -m "test(integration): 补充 10 个端到端集成用例

覆盖场景：
- 未定义函数→恒零函数注入→重新运行
- 未定义变量→@：var=0 注入→重新运行
- 多轮 auto_debug 链式修复
- optimize_memoize 后函数调用验证
- self_grow 从文件学习后调用验证
- Matha 侧 自主_调试/成长 内建调用验证"
```

### `feat/stress-test-10k` (P1 #4)

**变更范围：** `tests/test_performance.py`（或新文件）

**提交计划：**
```bash
git add tests/test_stress_10k.py
git commit -m "test(stress): 扩展压力测试至 10000 次算法一致性验证

- 1000 → 10000 次重复运行，验证 interpreter 一致性
- 验证 AutoDebugger 在大规模运行中的稳定性
- 输出性能报告: 耗时/成功率/内存峰值"
```

### `fix/learn-from-file-encoding` (P2 #5)

**变更范围：** `src/autonomous.py`

**提交计划：**
```bash
git add src/autonomous.py
git commit -m "fix(autonomous): SelfGrower.learn_from_file 添加编码容错

- open() 优先使用 utf-8，失败时 fallback 到 gb18030
- 捕获 UnicodeDecodeError 并返回失败结果而非崩溃
- 新增 test 验证 GBK 编码文件处理"
```

### `feat/trig-identities` (P2 #6)

**变更范围：** `src/matha_growth.py`

**提交计划：**
```bash
git add src/matha_growth.py tests/test_growth_trig.py
git commit -m "feat(growth): 实现 P4 三角恒等式优化规则

实现规则：
- sin²x + cos²x = 1
- tan(x) = sin(x)/cos(x)
- sin(2x) = 2sin(x)cos(x)
- cos(2x) = cos²x - sin²x
- sin(x+y) = sinx·cosy + cosx·siny
- cos(x-y) = cosx·cosy + sinx·siny
- 1+tan²x = sec²x

测试: test_growth_trig 7/7 通过"
```

### `docs/selfupgrade-autodebugger` (P2 #7)

**变更范围：** `docs/20-自我升级子系统.md`

**提交计划：**
```bash
git add docs/20-自我升级子系统.md
git commit -m "docs: 补全 AutoDebugger 和 PerformanceOptimizer 细节文档

- 新增 AutoDebugger 工作原理章节（未定义变量/函数检测逻辑）
- 新增 PerformanceOptimizer 采样与记忆化流程说明
- 更新自成长 SelfGrower 参数特化流程
- 补充 Matha 侧内建函数自主_调试/自主_优化/自主_成长 使用示例"
```

### `fix/test-defects-import` (P2 #8)

**变更范围：** `tests/test_defects.py`

**提交计划：**
```bash
git add tests/test_defects.py
git commit -m "fix(tests): 修复 test_defects.py ImportError

- 修复 MathaPackageManager 导入路径（从 pkg_manager_v2 导入）
- 对齐测试用例与新 API"
```

### `docs/treesitter-cli-readme` (P2 #9)

**变更范围：** `packages/matha_treesitter/README.md`

**提交计划：**
```bash
git add packages/matha_treesitter/README.md
git commit -m "docs(treesitter): 更新 CLI 使用文档

- 新增 CLI 快速开始章节（python -m matha_treesitter rust <source>）
- 补充 --version 和 --output dict 用法
- 更新安装命令包含 pip install -e . 本地开发模式"
```

---

## 执行顺序建议

```
week1:  feat/optimize-memoize-dynamic-args  ✅ 已完成
week2:  feat/integration-tests
week2:  feat/stress-test-10k
week3:  fix/learn-from-file-encoding
week3:  feat/trig-identities
week4:  docs/selfupgrade-autodebugger
week4:  fix/test-defects-import
week4:  docs/treesitter-cli-readme
```

---

**总计：8 个任务，9 个提交（含已完成 1 个）**
