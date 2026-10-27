# Matha 符号微积分标准库（阶段 4：能力迁回 Matha 自身）

**实测口径**：本文件的每一条都对应有可执行用例
[`tests/test_matha_stdlib_symbolic.py`](../tests/test_matha_stdlib_symbolic.py)
（107 项）。数字与文本都是跑出来的，不是愿望。

---

## 1. 交付物

| 文件 | 角色 | 主要导出 |
|------|------|----------|
| [`matha/library/calculus_diff.matha`](../matha/library/calculus_diff.matha) | 规范形 + 求导规则表 | `规范` / `规范文本` / `求导` / `导数文本` / `n阶导` |
| [`matha/library/algebra_simplify.matha`](../matha/library/algebra_simplify.matha) | 化简与展开 | `化简` / `展开` |
| [`matha/library/calculus_limit.matha`](../matha/library/calculus_limit.matha) | 有理式极限（极点阶 / 洛必达 / 无穷主部） | `极限节点` / `极限文本` / `约分` |
| [`matha/library/calculus_series.matha`](../matha/library/calculus_series.matha) | Maclaurin 系数 | `系数对` / `泰勒系数对` / `麦氏系数` |
| [`src/stdlib/matha_symbolic.py`](../src/stdlib/matha_symbolic.py) | 装载器 + Expr ↔ tagged 互转 + 记账 | `vm()` / `derivative()` / `limit_value()` / `maclaurin_terms()` / `BACKEND_STATS` |
| [`src/stdlib/calculus_symbolic.py`](../src/stdlib/calculus_symbolic.py) | 对外门面（默认走标准库） | `symbolic_derivative` / `nth_derivative` / `simplify_format` / `limit` / `taylor_series` |
| `src/kernel/symbolic/` | stage0 引导实现，**只作对拍基准**，不再是 CLI 默认路径 | — |

装载顺序按依赖拓扑固定为
`calculus_diff → algebra_simplify → calculus_limit → calculus_series`，
四个文件一次性拼成单个 mbc 模块、由 `src.mbc.compiler → src.mbc.vm` 编译执行
（`exec_api.compile_module(..., plugins="off")`，不引入任何领域插件、不 import
`sympy/numpy`）。四个文件属「标准库/扩展包」（`matha/library/`），不内置内核，
符合计划的归档定位。

## 2. 数据表示

Matha 侧用 tag 列表表示表达式（VM 的原生 list/float/str，无 Python 对象穿越）：

```
["num", v] ["var", s] ["neg", e] ["add", a, b] ["sub", a, b]
["mul", a, b] ["div", a, b] ["pow", 底, 指] ["ln", e] ["fn", 名, 参]
```

规范形（`规范`）把节点收敛到 `num/var/add/mul/pow/fn/ln`：`neg`→乘 `-1`、
`sub`→加负、`div`→乘 `-1` 次幂；add 扁平化后按「常数最后、非常数项键升序」重排，
同类项合并；mul 扁平化后数值因子升序相乘、相同因子合成 `pow`。
Python 侧 `matha_symbolic.from_tagged()` 回发成 `Expr`，其中**负整数幂还原为倒数**
（`(x+1)**-2` → `1/(x + 1)**2`），以匹配 stage0 的书写约定。

## 3. 后端路由（`backend` 形参）

| 取值 | 语义 |
|------|------|
| `"auto"`（默认） | 走 Matha 标准库；仅当库显式抛 `不支持: …` 时回退 stage0，并让 `BACKEND_STATS["fallback"] += 1`（**留痕，不静默**） |
| `"matha"` | 强制走标准库，不覆盖即报错（错误信息指向本文件），绝不悄悄用 Python 顶上 |
| `"stage0"` | 只用 Python 引导实现（对拍基准） |

其它值一律 `ValueError`。回退判定只看 `不支持: ` 前缀：VM 内部的真实缺陷
（`IndexError`、未知节点等）**必须上抛**，不允许被伪装成「能力未覆盖」。

## 4. 逐位对拍结果

数值比较一律用精确相等（`==`），**不设容差**——两侧都是同一条 IEEE-754 序列上的
运算，出现尾差就说明结构不同。

| 能力 | 用例数 | 结果 |
|------|--------|------|
| 一阶求导 `symbolic_derivative` | 36 | 文本逐字相同 |
| 高阶导 `nth_derivative` | 8 | 文本逐字相同 |
| 化简 `simplify_format` | 14 | 文本逐字相同 |
| 极限 `limit`（有限点 / 单侧 / ±∞ 有理式） | 12 | 返回值逐位相同 |
| Maclaurin 级数 `taylor_series`（point=0） | 9 | 文本相同；另有同 9 例逐项比对 `(次数, 系数)` 表 |

## 5. 已知偏差（如实列出，双向锁定）

偏差用例把**两侧文本同时钉死**：任何一侧变化（包括「偏差自己消失了」）都会让用例
失败并提示删除该条。除文本外，还把两侧输出回读成表达式、在若干点上逐位比对数值，
证明偏差只是书写规范不同、不是算错。

### 5.1 规范形书写差异（数值恒等）

| 输入 | stage0 | Matha 标准库 |
|------|--------|--------------|
| `asin(x)` | `1/sqrt(1 - x**2)` | `1/sqrt(-x**2 + 1)` |
| `acos(x)` | `-1/sqrt(1 - x**2)` | `-1/sqrt(-x**2 + 1)` |
| `asin(x)*atan(x)` | `atan(x)/sqrt(1 - x**2) + asin(x)/(x**2 + 1)` | `asin(x)/(x**2 + 1) + atan(x)/sqrt(-x**2 + 1)` |
| `1/(x**2 + 2*x + 1)` | `(-2*x - 2)/(x**4 + 4*x**3 + 6*x**2 + 4*x + 1)` | `-(2*x + 2)/(x**4 + 4*x**3 + 6*x**2 + 4*x + 1)` |
| `exp(-x*x)` | `-2*x*exp(-x*x)` | `-2*x*exp(-x**2)` |

原因：库内 add 项按键升序、负号提到整体之前、`x*x` 合成 `x**2`；stage0 保留求导
规则里手写的 `Sub(1, x**2)` 形态。

### 5.2 stage0 更弱（标准库能力覆盖更多，属计划「能力不降级」的正向证据）

| 输入 | stage0 | Matha 标准库 |
|------|--------|--------------|
| `simplify("1/(x+1) + 1/(x+1)")` | `1/(x + 1) + 1/(x + 1)`（不合并同类分式） | `2/(x + 1)` |
| `limit("(2x+1)/(3x-1)", x, +∞)` | `0.6666666666722222`（采样逼近，末位错） | `0.6666666666666666` = 2/3（精确主部比较） |
| `limit("(x+1)/(x**2+1)", x, +∞)` | `1.00000000001e-11`（应为 0） | `0.0` |
| `taylor_series("ln(1+x)")` | 抛 `SeriesUndetermined`（stage0 `evaluate` 不认识 `ln`） | `x**5/5 - x**4/4 + x**3/3 - x**2/2 + x` |

### 5.3 标准库未覆盖（显式 `不支持`，`auto` 下计数回退）

| 场景 | 行为 |
|------|------|
| `limit("sin(x)/x", x, 0)` | `不支持: 极限库只覆盖有理式（多项式商）……` → `auto` 回退 stage0，`fallback += 1` |
| `taylor_series(..., point≠0)` | `不支持: 级数库只覆盖 point=0 的 Maclaurin 展开` → 回退 stage0 |
| 超越式极限（指数/对数/三角的非常数主部） | 同上，极限库仅在有理式 + 洛必达≤8 层内工作 |

**这些缺口不是假成功**：强制 `backend="matha"` 时直接报错并指向本文件；`auto` 时在
`BACKEND_STATS` 中留痕；`tests/test_matha_stdlib_symbolic.py` 对两类行为都有断言。

## 6. 本轮顺带修复的内核缺陷

`src/kernel/symbolic/latex.py::_mul_body` 在「全部因子都是倒幂」分支用
`_numeral(abs(coef))` 当分子，**吞掉了系数负号**：
`Mul(-1, Pow(Add(x,1), Num(-2)))` 被发成 `1/(x + 1)**2`（树求值为负、文本为正，
两者矛盾）。现改为 `neg = coef < 0` + 分子取绝对值 + 末尾统一加 `-`，
`str/pretty/latex` 三种模式一致。该缺陷会影响所有 `to_str` 消费方，
故修复后重跑了 `tests/test_kernel_symbolic.py`（95 项）与全量门禁。

## 7. 与其它文档的关系

- 阶段 3 的 sympy 替换能力表：[docs/symbolic_parity.md](symbolic_parity.md)
- AST × VM 覆盖矩阵（`.matha` 标准库能跑起来的前提）：[docs/ast_vm_gap.md](ast_vm_gap.md)
- 统一门禁与唯一通过率：`make check`（`scripts/check.py`）
