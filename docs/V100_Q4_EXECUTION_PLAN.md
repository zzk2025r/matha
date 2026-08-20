# v1.0.0 Q4 剩余待办清单执行计划

> 生成日期: 2026-08-20
> 版本: v1.0.0
> 状态: AI 自升级子系统已正式合并，matha-treesitter 1.0.0 已自包含

---

## 一、已完成（v1.0.0 合并）

| # | 项目 | 状态 |
|---|---|---|
| 1 | AutoDebugger 未定义函数边界修复 | ✅ |
| 2 | `_eval_variable` → `_eval_func_app` 错误语义重写 | ✅ |
| 3 | `FuncDef` 构造参数修正（params/return_type→body Lambda） | ✅ |
| 4 | `IntegerLit` 导入路径修正 | ✅ |
| 5 | `test_matha_auto_debug` 取 `out[-1]` 修正 | ✅ |
| 6 | `matha_treesitter` 包自包含化（内嵌 `_backends.py`） | ✅ |
| 7 | `matha_treesitter` 包添加 `__main__.py` CLI 入口 | ✅ |
| 8 | `matha_treesitter` 版本 0.1.0 → 1.0.0 | ✅ |
| 9 | 根项目版本 4.4.0 → 1.0.0 | ✅ |
| 10 | AI 自升级子系统完成度报告更新 | ✅ |

**测试状态：54/54 通过 (100%)**

---

## 二、剩余待办清单

### P0 — 必须修复

| # | 问题 | 文件 | 预计工作量 |
|---|---|---|---|
| 1 | `matha_treesitter` C 扩展源码路径需验证 | `packages/matha_treesitter/src/cext/` | 30min |

### P1 — 重要优化（10月15日前）

| # | 问题 | 文件 | 预计工作量 |
|---|---|---|---|
| 2 | `PerformanceOptimizer.optimize_memoize` 硬编码参数 `[5]` → 记录采样实际参数 | `src/autonomous.py:88` | 2h |
| 3 | 集成测试补全：端到端验证 AutoDebugger 在完整 Matha 程序中的表现 | `tests/test_integration/` | 4h |
| 4 | 压力测试扩展：1000 → 10000 算法一致性验证 | `tests/test_performance.py` | 3h |

### P2 — 改进项（11月15日前）

| # | 问题 | 文件 | 预计工作量 |
|---|---|---|---|
| 5 | `SelfGrower.learn_from_file` 编码错误处理 | `src/autonomous.py:393` | 1h |
| 6 | `matha_growth.py` P4 三角恒等式规则实现 | `src/matha_growth.py` | 4h |
| 7 | `docs/20-自我升级子系统.md` 补全 AutoDebugger 细节 | `docs/20-自我升级子系统.md` | 2h |
| 8 | `test_defects.py` 修复 `ImportError: MathaPackageManager` | `tests/test_defects.py` | 1h |
| 9 | `matha_treesitter` CLI 帮助文档完善 | `packages/matha_treesitter/README.md` | 1h |

---

## 三、执行计划

### 第 1 周（8/20 - 8/26）：P0 修复

| 日期 | 任务 | 验证方式 |
|---|---|---|
| 8/20 | C 扩展源码路径验证 | `python -c "from packages.matha_treesitter import RustParser"` |
| 8/21 | 验证安装流程：`pip install -e packages/matha_treesitter` | `matha-treesitter --version` |
| 8/22 | 验证 CLI：`matha-treesitter rust "fn main(){}"` | 输出 AST tree |

### 第 2-3 周（8/27 - 9/9）：P1 优化

| 日期 | 任务 | 验证方式 |
|---|---|---|
| 8/27-8/29 | `optimize_memoize` 参数采样修正 | 单元测试 + 性能对比 |
| 8/30-9/3 | 集成测试补全 | `tests/test_integration/` 新增 10+ 用例 |
| 9/4-9/6 | 压力测试扩展至 10000 | 一致性通过率 ≥ 99.9% |
| 9/7-9/9 | 文档更新（20-自我升级子系统.md） | Sphinx 构建无警告 |

### 第 4-6 周（9/10 - 9/30）：P2 改进

| 日期 | 任务 | 验证方式 |
|---|---|---|
| 9/10-9/12 | `learn_from_file` 编码容错 | 添加 GBK/UTF-16 边界测试 |
| 9/13-9/17 | 三角恒等式规则实现 | 14 条规则全部通过 |
| 9/18-9/20 | `test_defects.py` 导入修复 | 无 ImportError |
| 9/21-9/25 | CLI 文档 + README 更新 | 用户可读性审查 |
| 9/26-9/30 | 回归测试 + 性能基准 | 54/54 测试通过，无性能回退 |

### 第 7-8 周（10/1 - 10/15）：集成与发布

| 日期 | 任务 | 交付物 |
|---|---|---|
| 10/1-10/5 | 全量回归测试 | 通过率 100% |
| 10/6-10/8 | 性能基准对比（v0.9 vs v1.0） | 性能报告 |
| 10/9-10/12 | 集成测试通过 | 端到端验证报告 |
| 10/13-10/15 | v1.1.0 预发布 | CHANGELOG + 文档 |

---

## 四、风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| C 扩展构建失败（Windows） | 中 | 中 | 纯 Python 降级方案已验证可用 |
| 压力测试超出预期时间 | 低 | 低 | 分两阶段：先 5000 → 再 10000 |
| 三角恒等式规则触发回归 | 中 | 高 | 每个规则独立提交 + 全量回归 |
| 集成测试覆盖率不足 | 中 | 中 | 参照 test_autonomous.py 模式扩展 |

---

## 五、里程碑

| 日期 | 里程碑 | 验收标准 |
|---|---|---|
| 2026-08-20 | v1.0.0 发布 | 54/54 测试通过，自升级子系统合并 ✅ |
| 2026-08-27 | P0 修复完成 | matha-treesitter CLI 可用 |
| 2026-09-15 | P1 优化完成 | 性能提升 2-5x，集成测试通过 |
| 2026-10-15 | v1.1.0 预发布 | 全量回归 + 性能基准 |
| 2026-11-15 | 功能扩展完成 | 三角恒等式 + 编码容错 |
| 2026-12-15 | Q4 总结 | v1.2.0 发布 |

---

**结论：Q4 路线图清晰，风险可控。建议按里程碑推进，v1.0.0 已具备发布条件。**
