# 符号微积分能力等价表（内核纯标准库实现 ↔ sympy）

阶段 3 第 2 项交付物。旧实现 `src/stdlib/calculus_symbolic.py` 直接
`from sympy import ...`；现由 `src/kernel/symbolic/`（纯标准库）承担全部计算，
门面只做参数转换与错误上报。本表**逐项标注实测结论**，缺口如实列出 ——
内核覆盖不到的表达式一律显式失败（`UnsupportedExpression` /
`LimitUndetermined` / `SeriesUndetermined` / `OdeUnsupported` /
`DomainUndetermined`），**不返回乐观默认值**。

机器可判定的回归锁：`tests/test_kernel_symbolic.py`（103 例；字符串断言的值取自
sympy 1.14 实测输出，任意点泰勒则以邻域逼近真函数的数值一致性锁定）。运行：

```
python -m pytest tests/test_kernel_symbolic.py -q
```

## 1. 术语

| 标记 | 含义 |
|---|---|
| 一致 | 与 sympy 在同一表达式类上给出数学相同的结果（允许代数等价变形差异） |
| 子集 | 只覆盖 sympy 能力的一个真子集；集合外输入显式失败，不降级 |
| 已知偏差 | 数学结论相同，但表示形式/精度与 sympy 输出不同 |

## 2. 求导 `differentiate` / `diff`（`kernel/symbolic/diff.py`）

| 能力 | 判定 | 说明 |
|---|---|---|
| 四则、幂、`exp`、`log`/`ln`、`sqrt`、`abs` | 一致 | 链式法则表驱动 |
| `sin cos tan asin acos atan` | 一致 | `tan(x) → 1/cos(x)**2`（sympy 同形） |
| 乘积/商/复合任意阶 | 一致 | `exp(exp(x)) → exp(x + exp(x))` |
| 偏导 `partial_derivative`、n 阶 `nth_derivative` | 一致 | 多元 `x*y**2 → y**2` |
| `factorial(x)`（Γ 函数导数） | 子集 | 显式 `UnsupportedExpression` |
| 二元 `log(x, 10)` 求导 | 子集 | 仅一元函数支持求导，显式失败 |
| 符号化 `piecewise` / `DiracDelta` | 子集 | 内核无分布语义 |

## 3. 积分 `integrate` / `definite`（`kernel/symbolic/integrate.py`）

| 能力 | 判定 | 实测样本 |
|---|---|---|
| 广义幂法则、一次内函数换元 | 一致 | `x**4 → x**5/5`；`sqrt(2*x+1) → (2*x + 1)**(3/2)/3` |
| 多项式 × 指数/三角（分部积分） | 一致 | `x**2*exp(x)`、`x**2*sin(x)`、`x*log(x) → x**2*log(x)/2 - x**2/4` |
| 三角偶次幂（`math.comb` 精确系数） | 一致 | `sec(x)**2 → tan(x)`；`tan(x)**2 → -x + tan(x)`；`sin(x)**3` |
| 异频三角积（积化和差） | 一致 | `sin(3*x)*cos(2*x) → -cos(5*x)/10 - cos(x)/2` |
| 指数 × 三角（含相位通式） | 一致 | `exp(x)*sin(2*x) → -2*exp(x)*cos(2*x)/5 + exp(x)*sin(2*x)/5` |
| 同底指数合并 | 一致 | `exp(2*x)*exp(-x) → exp(x)`（否则 ODE 积分因子给出冗长解） |
| 真分式部分分式（单极点 + 一次因式 × 不可约二次） | 一致（结构）/ 已知偏差（精度） | `1/(x**3+1)`、`1/(x**2-4)`、`(2*x+1)/(x**2-1)` |
| 定积分 | 一致 | Newton–Leibniz 失败时退自适应 Simpson（纯 stdlib 数值） |

**已知偏差（须如实说明）**：不可约二次因子产生的无理解系数（如 `1/√3`、`√3/2`）
在内核中以 double 存储并打印，形如
`0.5773502691896258*atan((x - 0.5)/0.8660254038)`；sympy 给出
`sqrt(3)*atan(2*sqrt(3)*x/3 - sqrt(3)/3)/3`。数学结论相同，但内核暂无精确
`√` 常量域。打印层用连分数还原有理系数时把 `max_den` 限制为 `1e4`，
宁可显示小数也不把无理解伪造成大分母「精确分数」（`rational_of` 文档记录了这一取舍）。

**可选精确路径（插件化，默认关）**：内核本身仍以 double 存储（代码零改动），但门面
`calculus_symbolic.py` 的文本发射统一过一层 `decorate_numeric`；调用 `enable_exact_algebra()`
（即 `src.algebra.interface.load_plugin("algebra")`）后，上述 double 系数会被小高度整数极小
多项式识别还原为精确根式（如 `1/2*sqrt(2)*atan(x/sqrt(2))`）。未加载时输出逐字节不变；
能力之外（多根式、高次根、超越数）诚实回退 double，绝不臆造。

**缺口（显式失败，非静默）**：

| 表达式 | 行为 |
|---|---|
| `exp(-x**2)`、`sin(x)/x`、`1/(1+exp(x))`、`1/(x*exp(x))`、`sin(1/x)` | 非初等原函数 → `None`（门面转显式错误） |
| `x**x` | 内核无对应原函数规则 → `None` |
| `abs(x)`、`abs(a*x+b)`（线性内函数） | 已覆盖（B 组）：∫|ax+b| = (ax+b)·|ax+b|/(2a)，与 sympy `integrate(Abs(x))=x*Abs(x)/2` 同式（`tests/test_kernel_integrate_abs_piecewise.py` 锁定） |
| 三重及以上不可约因式、高次重根分式 | `_int_proper` 返回 `None` |

## 4. 极限 `limit`（`kernel/symbolic/limit.py`）

求解链：直读 → 函数自身瑕点 → `1^∞` → 商形式（0/0 洛必达）→ `0·∞` 改商 →
共轭有理化 → `t=1/x` 归约 → 广义多项式主部定阶 → 增长级判据表 → Richardson 外推。
**所有由推断路径得到的结论必须通过 `_probe_agrees` 邻域大数佐证**，读数与结论
同势才采纳，否则继续下探直至显式失败。

| 类型 | 判定 | 实测样本 |
|---|---|---|
| 0/0 洛必达 | 一致 | `sin(x)/x → 1`；`(exp(x)-1-x)/x**2 → 0.5`；`sin(2x)/sin(x) → 2`；`(1-cos x)/x**2 → 0.5` |
| `1^∞` | 一致 | `(1+x)**(1/x) → e`；`(1+1/x)**x → e`；`(1+2/x)**x → e**2` |
| 极点单侧极限 | 一致 | `tan(x)` 在 `π/2` 左 `+oo` 右 `-oo`；`1/x` 在 `0` 两侧 |
| 函数端点 | 一致 | `log(x) → -oo`（x→0⁺）；`x**x → 1`（x→0⁺） |
| ∞ 处主部比较 | 一致 | `log(x)/x → 0`；`x*exp(-x) → 0`；`exp(x)/x**2 → oo` |
| ∞−∞ 共轭有理化 | 一致 | `sqrt(x+1)-sqrt(x) → 0` |
| 反三角/Hyperbolic 定值 | 一致 | `atan(x) → π/2`（精确值，不再给 12 位近似） |
| 振荡型 | 子集 | `sin(x)`（x→∞）**显式失败**；sympy 返回 `Interval(-1, 1)` |
| `∞−∞` 非根式、`0^0`/`∞^0` 一般式 | 子集 | 落不完判据链时 `LimitUndetermined` |

## 5. 级数 `taylor` / `maclaurin` / `sum_series`（`kernel/symbolic/series.py`）

| 能力 | 判定 | 实测样本 |
|---|---|---|
| 麦克劳林/泰勒展开 | 一致 | `exp(x)` 5 阶、`log(1+x)`、`sqrt(1+x)`、`tan(x)`、`exp(-x**2)` |
| 非 0 点泰勒 `taylor(f, x, a, n)` | 一致（值 + 表示） | 内核 `series.taylor` 覆盖**任意展开点** `a`，与 sympy `series(...).removeO()` 数值一致；输出已改为 sympy 的 **`(x-a)ⁿ` 中心形式**（不再乘开成 `x` 幂，B 组修），`tests/test_kernel_taylor_centered.py` 逐字锁定 |
| Faulhaber（Σ 多项式，非负整数幂） | 一致 | `Σn=5050`、`Σn**3=3025` |
| 几何/望远镜闭式 | 一致 | `Σ1/2**n → 1`；`Σ1/(n(n+2)) → 0.5952380952380952` |
| `Σ x**n/n! → exp(x)`、`Σ1/n**2 → π²/6` | 一致 | 闭式识别 |
| 负整数幂求和（`Σ1/n`，调和/`polygamma`） | 子集（插件回退已覆盖） | 内核 `SeriesUndetermined`；`级数求和` 插件懒加载 sympy 给 `137/60`/`digamma(5)+EulerGamma`（见第 10 节） |
| 求和变量与项内函数不匹配（`Σk`，k 非求和元） | 子集 | 显式失败 |

## 6. 常微分方程 `solve_ode`（`kernel/symbolic/ode.py`）

| 类型 | 判定 | 实测样本 |
|---|---|---|
| 直接积分 `y^(n) = f(x)` | 一致 | `y'' = -y → C1*cos(x) + C2*sin(x)` |
| 一阶可分离 | 一致 | `y' = y*sin(x) → C1*exp(-cos(x))`；`y' = x**2*y → C1*exp(x**3/3)` |
| 一阶线性积分因子 | 一致 | `y' + 2*y = exp(-x) → C1*exp(-2*x) + exp(-x)`；`y' + 3*y = exp(2*x) → C1*exp(-3*x) + exp(2*x)/5` |
| 二阶常系数齐次（相异/重根/共轭） | 一致 | `y'' + 2*y' + y = 0 → C2*x*exp(-x) + C1*exp(-x)` |
| 待定系数特解（非齐次高阶） | 子集 | 仅覆盖多项式/指数/正弦型右端的部分组合，失败即显式报错 |
| 非线性一阶（`y' = x**2 + y**2`、`y' = (x+y)/x`、`y' = 1/(x+y)`） | 子集（插件回退已覆盖） | 内核 `OdeUnsupported`；`解微分方程` 插件懒加载 sympy 给线性化/Riccati 解（需 Airy 的 `y'=x²+y²` 仍显式失败，见第 10 节） |
| 幂级数解、Laplace 变换 | 子集 | 内核未实现 |

## 7. 连续域与累值界 `continuous_domain` / `accumulated_bounds`（`kernel/symbolic/domain.py`）

**取证结论**：sympy 1.14 已移除 `sympy.calculus.util.accumulated_bounds`
（`ImportError: cannot import name 'accumulated_bounds'`）。旧代码只 import
了这两个名字、**从未调用**，因此这两项**不存在 sympy 基线**；内核给出真实
实现并作为公开 API 暴露，语义如下自证：

- `continuous_domain`：按分母零点、`sqrt/log` 非正、`asin/acos` 越界构造奇点集，
  取补得到升序区间，端点开闭由「该点是否有定义」决定
  （`1/x → (-oo, 0) ∪ (0, oo)`；`sqrt(x) → [0, oo)`；`asin(x) → [-1, 1]`）。
- `accumulated_bounds`：返回函数值聚点界 `(下界, 上界)`。
  振荡型限「单个 `sin`/`cos`（可带变幅）」→ ±振幅；偶次幂 → `[0, 1]`；
  多项式 → 奇次 `(-oo, oo)`、偶次由临界点极值 + 无穷端给出；
  其余走逐连续区间端点极限取 min/max。

| 表达式 | 内核结论 | 依据 |
|---|---|---|
| `sin(x)` / `cos(x)` | `(-1, 1)` | 振幅 |
| `2*sin(x)` | `(-2, 2)` | 振幅极限 |
| `sin(x)**2` | `(0, 1)` | 偶次幂恒非负 |
| `x**2` / `x**2+2*x` | `(0, oo)` / `(-1, oo)` | 临界点 + 无穷端 |
| `x**3` | `(-oo, oo)` | 奇次 |
| `1/x` / `1/x**2` | `(-oo, oo)` / `(0, oo)` | 分段端点极限 |
| `log(x)` / `sqrt(x)` | `(-oo, oo)` / `[0, oo)` 端点界 | 端点极限 |
| `atan(x)` | `(-π/2, π/2)` | 精确端点 |
| `cos(x)+sin(x)`、`sin(x)*cos(x)` | **显式失败** | 需极值分析/和差化积，内核缺口 |
| 区间内部有极值的非多项式函数 | 可能高估 | 端点判据不含内部驻点，如实标注为已知偏差 |

## 8. 化简与输出 `simplify` / `expand` / `cancel` / `latex`（`simplify.py`、`latex.py`）

| 能力 | 判定 | 说明 |
|---|---|---|
| 展开、合并同类项、有理约简、标准形 | 一致 | 稀疏多项式表示（原子 = 变量或 `sin(2*x)`/`exp(x)` 整体） |
| `to_str` / `to_latex` / `to_pretty` | 一致 | `x**2+2*x+1 → x^{2} + 2 x + 1 → x² + 2x + 1` |
| LaTeX/文本反解析（替 `sympy.parse_expr`） | 子集 | 覆盖内核函数表内的记法；未收录记法显式失败 |
| 无理解系数打印 | 已知偏差 | 见第 3 节 |

## 9. 总体缺口清单（禁止被当作「假成功」）

1. 非初等原函数：`exp(-x**2)`、`sin(x)/x`、`x**x`、`1/(1+e^x)` 等（`abs(x)` 已于 B 组补分段原函数规则）。
2. 特殊函数体系：`factorial` 求导、Airy、Bessel、`digamma/polygamma`、`DiracDelta`。
3. 二元函数记法：`log(x, base)` 的求导与化简。
4. 非线性 ODE（Riccati、齐次型 `y'=(x+y)/x`、克莱罗型）与高阶非齐次特解。
5. 振荡型极限（`sin(x)` at ∞）与三角和式累值界。
6. 精确代数数（`√`、单位根）系数域 —— 内核当前以 double 表示、默认打印为小数；
   可选代数数插件（`enable_exact_algebra()`）在门面发射层把落在二次域 ℚ(√d) 的系数
   还原为精确根式（默认关、内核零改动，能力之外诚实回退）。
7. 多变量积分、含参积分、主值积分（Cauchy PV）。

以上 7 项在内核中**全部走显式失败路径**，由 `src.stdlib.calculus_symbolic`
门面转成带说明的错误；错误文案统一指向本文档。

## 10. 懒加载插件回退层（`src/domains/symbolic_*.py`）

内核纯净化重构把重后端（sympy）留在**领域插件层**：内核引擎优先作答，只有
显式抛缺口（`OdeUnsupported` / `SeriesUndetermined`）时才在调用点动态
`import sympy`，取用一次才物化一个插件（启动成本恒为 0）。已铺开的回退件：

| 插件 | 符号 | 覆盖缺口 | 取证 |
|---|---|---|---|
| `symbolic_calculus` | `integrate` / `积分` | 非初等原函数（`exp(-x²)`…） | `tests/test_plugin_load.py` |
| `symbolic_ode` | `解微分方程` / `ode` | 非线性一阶 ODE（齐次/Riccati） | `tests/test_plugin_ode.py` |
| `symbolic_series` | `级数求和` / `sum_series` | 负整数幂求和（调和/交错） | `tests/test_plugin_series.py` |

红线：插件**不导出裸单字母符号**（否则经 `LazyBuiltinTable` 成员判定改写
「未定义名即报错」的内核契约）；回退到 sympy 时输出为 sympy 打印串，与内核
标准串不保证逐字同形；sympy 也解不了的（如需 Airy 的 `y'=x²+y²`、振荡型极限）
仍**显式抛错并指向本文档**，绝不返回「无法求解」之类假成功。
