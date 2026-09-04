# Matha 问题与诊断系统

> 版本：v4.4.57
> 更新日期：2026-09-05

---

## 一、问题列表（Problems）

### 1.1 已知问题（Known Issues）

| 编号 | 问题描述 | 影响范围 | 严重程度 | 状态 |
|------|---------|---------|---------|------|
| **KNP-001** | LLM 意图解析需要 API Key | LLM 解析功能 | ⚠️ 中 | 已降级可用 |
| **KNP-002** | VS Code 插件需要 TypeScript 编译 | VS Code 扩展 | ⚠️ 中 | 已有预编译版本 |
| **KNP-003** | Jupyter 扩展需要 IPython | Jupyter Notebook | ⚠️ 中 | 按需安装 |
| **KNP-004** | 依赖缓存内存占用随包数量增加 | matha-pkg | ℹ️ 低 | 手动 clear_cache() |
| **KNP-005** | 长文本意图分解准确率下降 | 意图分解 | ⚠️ 中 | 拆分任务 |
| **KNP-006** | 部分数学函数命名不一致 | 标准库 | ℹ️ 低 | 使用统一别名 |
| **KNP-007** | Windows multiprocessing spawn 限制 | HAL 并发 | ⚠️ 中 | Worker 函数放顶层 |
| **KNP-008** | LLM 降级时置信度固定为 0.50 | 意图解析 | ℹ️ 低 | 正常工作 |
| **KNP-009** | 公式表达式含特殊字符解析失败 | 公式系统 | ℹ️ 低 | 使用标准变量名 |
| **KNP-010** | 成长系统需关联 AI 助手才能完整运行 | 成长引擎 | ℹ️ 低 | 传入 assistant 参数 |

### 1.2 最近修复的问题

| 编号 | 问题描述 | 修复版本 | 修复方式 |
|------|---------|---------|---------|
| **FIX-001** | `_get_formula_growth()` 未定义导致 UnifiedGrowth 初始化失败 | v4.4.57 | 新增懒加载函数 |
| **FIX-002** | DomainFormulaRegistry.register_all_domains() 返回 None 导致 += 错误 | v4.4.57 | 修复返回值为公式总数 |
| **FIX-003** | 公式表达式含 `ΔT` 等 Unicode 字符解析失败 | v4.4.57 | 替换为标准 ASCII 变量名 |
| **FIX-004** | `IntentType.公式推导` 缺失导致 KeyError | v4.4.57 | 在 IntentType 枚举中新增 |
| **FIX-005** | 重复的 `等差数列求和` 条目导致 KeyError | v4.4.57 | 删除重复条目 |

---

## 二、诊断系统（Diagnostics）

### 2.1 诊断层级架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Matha 诊断系统架构                              │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │   LSP 诊断层     │  │   IDE 诊断层     │  │  自诊断层    │ │
│  │  (src/lsp.py)    │  │(src/diagnostics  │  │(src/growth   │ │
│  │  - 符号补全      │  │  _v2.py)         │  │  _engine.py) │ │
│  │  - 悬停提示      │  │  - 语法错误高亮  │  │  - 资源审计  │ │
│  │  - 诊断报告      │  │  - 语义错误      │  │  - 缺陷检测  │ │
│  │  - 跳转/定义     │  │  - 修复建议      │  │  - 联动分析  │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────┘ │
│           │                     │                              │
│  ┌────────▼─────────────────────▼──────────────────────────┐  │
│  │              UnifiedDiagnostics（统一层）                 │  │
│  │         (src/unified_diagnostics.py)                     │  │
│  │  - get_diagnostics(source)                              │  │
│  │  - diagnose_source(source, path)                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              HybridCompiler 缺陷报告                      │  │
│  │         (src/hybrid_compiler.py)                          │  │
│  │  - DefectKind: PARSER/INTERPRETER/TYPE/SEMANTIC/COMPILE  │  │
│  │  - Severity: LOW/MEDIUM/HIGH/CRITICAL                    │  │
│  │  - DefectReport: 结构化缺陷报告                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 诊断等级（Severity）

| 等级 | 值 | 含义 | 处理策略 |
|------|---|------|---------|
| `ERROR` | `"error"` | 致命错误，代码无法执行 | 必须修复 |
| `WARNING` | `"warning"` | 潜在问题，可能影响结果 | 建议修复 |
| `INFO` | `"info"` | 提示信息，无影响 | 可选参考 |
| `HINT` | `"hint"` | 优化建议 | 可选参考 |

### 2.3 错误类型（ErrorKind）

```python
# src/diagnostics.py - MathaErrorKind
SYNTAX_EXPECTED       # 期望某语法元素
SYNTAX_UNTERMINATED   # 字符串/注释未终止
SYNTAX_INVALID_TOKEN  # 无效 token

UNDEFINED_VAR         # 未定义变量
TYPE_MISMATCH         # 类型不匹配
UNDEFINED_FUNC        # 未定义函数
REDEFINED_VAR         # 变量重复定义
SCOPE_ERROR           # 作用域错误

DIVISION_BY_ZERO      # 除零错误
INDEX_OUT_OF_RANGE    # 索引越界
TYPE_ERROR            # 类型错误

SUGGEST_IMPORT        # 建议导入
SUGGEST_FIX           # 建议修复
```

### 2.4 诊断收集器

```python
from src.unified_diagnostics import get_diagnostics, diagnose_source
from src.diagnostics_v2 import EnhancedDiagnosticCollector, Severity, Diagnostic

# 统一接口（推荐）
diagnostics = get_diagnostics("x = 1 + ;  # 语法错误")
for d in diagnostics:
    print(f"[{d.severity.value}] L{d.line}: {d.message}")
    print(f"  建议: {d.fix}")

# 增强接口
collector = EnhancedDiagnosticCollector()
collector.add_error("未定义变量 'abc'", line=3, code="UNDEFINED_VAR",
                    fix="检查变量名拼写，或添加绑定: abc = ?")
collector.add_warning("函数未使用", line=10, code="UNUSED_FUNC")

print(collector.summary())  # "诊断: 1 错误, 1 警告, 重复错误 0 种"
print(collector.to_json())  # LSP 格式 JSON
```

### 2.5 LSP 诊断

```python
from src.lsp import MathaLSP

lsp = MathaLSP()

# 语法/语义诊断
diagnostics = lsp.diagnostics(source_code, filepath="demo.matha")

# 符号补全
completions = lsp.complete("sin(", position=(5, 10))

# 悬停提示
hover = lsp.hover("牛顿第二定律", position=(3, 5))

# 跳转到定义
definitions = lsp.goto_definition("平方", position=(10, 8))
```

### 2.6 上下文分析与修复建议

```python
from src.diagnostics_v2 import ContextAnalyzer, ErrorHistory

# 上下文分析
analyzer = ContextAnalyzer(source, line=10, col=5)
context = analyzer.get_context(radius=3)  # 前后3行
similar_vars = analyzer.find_similar_vars("x")  # 相似变量名
similar_funcs = analyzer.find_similar_funcs("sin", known_funcs)  # 相似函数

# 错误历史追踪
history = ErrorHistory(max_entries=100)
history.record(diagnostic)
duplicates = history.get_duplicates()  # 重复错误
recent = history.get_recent(n=10)      # 最近10条
```

---

## 三、自诊断系统（Self-Diagnosis）

### 3.1 成长引擎自诊断

```python
from src.growth_engine import GrowthEngine, DefectCategory, Severity

engine = GrowthEngine()

# 全面自检
defects = engine.self_diagnose()
for d in defects:
    print(f"[{d.severity.value}] {d.category.value}: {d.message}")

# 缺陷统计
stats = engine.get_defect_stats()
print(f"总缺陷: {stats['total']}, 开放: {stats['open']}, 已解决: {stats['resolved']}")
print(f"按类别: {stats['by_category']}")
print(f"按严重度: {stats['by_severity']}")

# 获取缺陷列表
critical = engine.get_defects(severity=Severity.CRITICAL)
high = engine.get_defects(severity=Severity.HIGH)
```

### 3.2 缺陷分类

| 分类 | 值 | 说明 |
|------|---|------|
| `资源缺失` | `missing_resource` | 模块/资源未找到 |
| `功能缺陷` | `feature_broken` | 功能异常或崩溃 |
| `性能不足` | `performance` | 性能低于阈值 |
| `知识空白` | `knowledge_gap` | 知识库不完整 |
| `联动失效` | `coordination_failure` | 模块间协作失败 |
| `升级回滚` | `upgrade_rollback` | 升级失败需回滚 |
| `跨功能冲突` | `cross_conflict` | 不同功能间的冲突 |
| `未覆盖场景` | `uncovered_scenario` | 场景未被识别 |

### 3.3 内循环诊断

```python
from src.inner_loop import MathaInnerLoop

loop = MathaInnerLoop()

# 认知层诊断
diagnosis = loop.cognitive_diagnose()
print(f"健康分: {diagnosis['health_score']}")
print(f"状态: {diagnosis['status']}")  # healthy / degraded / critical
print(f"缺陷数: {diagnosis['defects_found']}")

# 完整内循环（感知→认知→执行→验证→持久化）
result = loop.run_cycle(verbose=True)
```

---

## 四、混合编译器缺陷报告

```python
from src.hybrid_compiler import HybridCompiler, DefectKind, Severity

compiler = HybridCompiler()

# 诊断源码
defects = compiler.diagnose(source_code, context="math")
for d in defects:
    print(f"[{d.severity.value}] {d.kind.value}: {d.message}")
    print(f"  建议: {d.suggestion}")
    print(f"  混合方案: {d.hybrid_workaround}")

# 一键诊断+报告
report = compiler.diagnose_and_report(source_code)
print(report.to_dict())
```

---

## 五、资源审计

```python
from src.growth_engine import GrowthEngine

engine = GrowthEngine()

# 完整资源审计
resources = engine.audit_resources()
for r in resources:
    status = "✓" if r.status == "ok" else "✗"
    print(f"  {status} {r.name}: {r.status} ({r.kind})")

# 统计
missing = [r.name for r in resources if r.status != "ok"]
print(f"缺失资源: {missing}")
```

**当前审计项（13项）：**

| 资源名 | 类型 | 状态 | 说明 |
|-------|------|------|------|
| keyword_arithmetic | intent_keyword | ✓ | 算术关键词 |
| keyword_math_func | intent_keyword | ✓ | 数学函数关键词 |
| keyword_unit_convert | intent_keyword | ✓ | 单位换算关键词 |
| keyword_physics | intent_keyword | ✓ | 物理关键词 |
| variation_map_full | intent_variation | ✓ | 变体表达 |
| commonsense_rules_count | commonsense | ✓ | 常识规则 |
| math_concepts_count | math_concept | ✓ | 数学概念 |
| growth_system | growth_system | ⚠️ | 需关联 AI 助手 |
| net_security_engine | security_engine | ✓ | 安全引擎 |
| firewall_system | firewall | ✓ | 防火墙 |
| formula_registry | formula_resource | ✓ | 公式注册表 |
| domain_formulas | domain_formula | ✓ | 领域公式 |
| formula_growth_engine | formula_growth | ✓ | 公式成长引擎 |

---

## 六、快速诊断命令

```powershell
# PowerShell 快速诊断
python -c "
from src.growth_engine import GrowthEngine
e = GrowthEngine()
resources = e.audit_resources()
print(f'资源审计: {sum(1 for r in resources if r.status==\"ok\")}/{len(resources)} OK')
defects = e.self_diagnose()
print(f'自诊断缺陷: {len(defects)}')
stats = e.get_defect_stats()
print(f'缺陷统计: {stats}')
"

python -c "
from src.unified_diagnostics import get_diagnostics
# 测试语法诊断
d = get_diagnostics('x = 1 + ;')
print(f'诊断结果: {len(d)} 条')
for diag in d:
    print(f'  [{diag.severity.value}] {diag.message}')
"
```

---

## 七、错误解释模板（小白友好）

```python
from src.ai_assistant import FriendlyIntentParser

parser = FriendlyIntentParser()

# 获取错误解释
explanation = parser.explain_error("未定义变量 'abc'")
print(explanation["小白解释"])  # "你用到了一个还没有定义的数..."
print(explanation["怎么修"])    # "在前面加一行声明..."
print(explanation["例子"])      # "示例代码..."
```

---

## 八、诊断输出格式（LSP 兼容）

```json
{
  "message": "未定义变量 'abc'",
  "severity": "error",
  "range": {
    "start": {"line": 2, "character": 5},
    "end": {"line": 2, "character": 8}
  },
  "source": "matha",
  "code": "UNDEFINED_VAR",
  "codeDescription": {"href": "https://matha.dev/diagnostics/UNDEFINED_VAR"},
  "fixes": [{"label": "修复", "edit": {"text": "abc = 0"}}],
  "relatedInformation": [
    {"uri": "file:///demo.matha", "range": {"start": {"line": 0, "character": 0}}}
  ]
}
```
