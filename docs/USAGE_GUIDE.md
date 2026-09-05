# Matha 使用文档

> **版本：** v4.5.0  
> **更新日期：** 2026-09-05  
> **Python 要求：** 3.10+  
> **测试通过率：** 344/344 (100%)

---

## 一、快速开始

### 1.1 安装

```powershell
# 方式 1：一键安装（推荐）
cd d:\trae
python scripts/install.py

# 方式 2：指定开发源码路径
python scripts/install.py --dev D:\trae

# 方式 3：强制重装
python scripts/install.py --force
```

安装后自动创建 `~/Matha/` 独立文件夹，包含：
- `matha` — 统一入口（REPL + 编译器 + 公式生长）
- `src/` — 当前版本源码
- `workspace/` — 您的项目、公式、笔记
- `MathaIDE/` — 自举开发环境
- `matha-update` — 一键更新

### 1.2 启动

```powershell
# 方式 A：桌面图标（手动创建）
# 右键桌面 → 新建快捷方式
# 位置: python.exe
# 参数: -m matha
# 起始位置: %USERPROFILE%\Matha

# 方式 B：命令行
cd %USERPROFILE%\Matha
python matha

# 方式 C：直接运行启动器
.\matha
```

### 1.3 验证安装

```powershell
# 检查版本
matha --version
# Matha v4.5.0

# 运行自检
matha test
# 结果: 344 通过, 0 失败

# 查看工具链信息
matha info
```

### 1.4 Git 配置（SSH 推荐）

> **注意：** HTTPS 在部分网络环境下会被 SSL 拦截（连接超时）。推荐使用 SSH。

```powershell
# 检查 SSH 是否可用
ssh -T git@github.com
# 输出: Hi zzk2025r! You've successfully authenticated...

# 配置 SSH 为 GitHub 默认协议（一次性）
git config --global url."git@github.com:".insteadOf "https://github.com/"

# 配置 SSH 密钥（首次）
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub  # 复制输出内容

# 在 GitHub 添加密钥
# Settings → SSH and GPG keys → New SSH key
```

### 1.5 启动 Matha

```powershell
# 启动统一入口（REPL + 编译器 + 公式生长一体化）
matha

# 或直接运行
cd %USERPROFILE%\Matha
python matha
```

### 1.6 更新

```powershell
# 一键更新（从 GitHub 拉取最新版本）
matha-update

# 检查是否有新版本
matha-update --check
```

---

## 二、核心概念

Matha 将编程过程显式划分为**三层**：

```
【*/意图/*】  →  #：机械语言  →  [] 可读命令
自然语言        数学核心          人可检验的输出
```

| 层级 | 说明 | 示例 |
|------|------|------|
| **自然语言输入层** | 用中英文表达意图 | "帮我算一下 100 以内素数" |
| **数学核心层** | 以集合论与类型论为基础的公式化代码 | `func 平方(x) -> Float = (x) => x * x` |
| **可读输出层** | 生成可被人阅读、对比、检验的命令 | `#1：[结果]` |

---

## 三、命令行工具

### 3.1 可用命令

```powershell
matha                    # 启动交互式 REPL
matha eval "expr"        # 计算表达式
matha run file.matha     # 运行 Matha 源文件
matha compile file -o c  # 编译到 C
matha llvm file          # 生成 LLVM IR
matha optimize file -o c # 优化编译
matha debug file         # 调试模式（显示 AST/MIR）
matha build file -o exe  # 构建独立可执行文件
matha test               # 运行编译器测试
matha info               # 工具链信息
matha --version          # 显示版本
```

### 3.2 表达式计算

```powershell
# 基础算术
matha eval "2 + 3 * 4"
# 输出: 14

# 三角函数
matha eval "sin(3.14159) + cos(1.57)"
# 输出: 1.999...

# 开方与幂
matha eval "sqrt(16) + 2^3"
# 输出: 12.0

# 数学常量
matha eval "pi * r^2"  # r 需预先绑定
```

### 3.3 运行 .matha 文件

```matha
# demo.matha
# 定义函数
func 平方(x) -> Float = (x) => x * x
func 立方(x) -> Float = (x) => x * x * x

# 使用函数
result = 平方(5) + 立方(3)

# 输出（段号 1）
#1：[result]
```

```powershell
matha run demo.matha
# 输出: 52
```

### 3.4 编译到 C

```powershell
# 基础编译
matha compile demo.matha -o output.c

# 优化编译
matha optimize demo.matha -o output.c

# 生成 LLVM IR
matha llvm demo.matha -o output.ll
```

### 3.5 调试模式

```powershell
# 显示 AST + MIR + 代码生成全过程
matha debug demo.matha
```

输出示例：
```
Step 1: 词法分析
  Token 数量: 25
    KEYWORD     'func'
    IDENT       '平方'
    PUNCT_LPAREN '('
    ...

Step 2: 语法分析 (AST)
  AST 声明数量: 2
    FuncDecl
    FuncDecl

Step 3: MIR 生成
  MIR 指令数量: 8
  %1 = load_const 5.0
  %2 = mul %1 %1
  ...
```

---

## 四、Matha 语法

### 4.1 基础语法

```matha
# 变量绑定
x = 10
y = 20
z = x + y

# 输出（#1 段号）
#1：[z]
#1: [z + 5]

# 函数定义
func 加法(a, b) -> Float = (a, b) => a + b

# 柯里化函数
func 乘积(a) -> Float = (a) => (b) => a * b
result = 乘积(3)(4)  # 12

# 条件表达式
r = 5 > 3 ? 真 : 假

# 函数式 lambda
add = (a, b) => a + b
result = add(10, 20)
```

### 4.2 循环

```matha
# for 循环
s = 0
for i in range(10):
    s = s + i
#1：[s]  →  输出 45

# 函数式循环（map/filter）
nums = [1, 2, 3, 4, 5]
squares = map((x) => x * x, nums)
evens = filter((x) => x % 2 == 0, nums)
```

### 4.3 数据结构

```matha
# 列表
lst = [1, 2, 3, 4, 5]
first = get(lst, 0)    # 1
length = len(lst)      # 5
appended = append(lst, 6)  # [1, 2, 3, 4, 5, 6]

# 字符串
name = "Matha"
length = len(name)     # 6
upper = upper(name)    # "MATHA"
```

### 4.4 命令字面量

```matha
# 命令块（用【】包裹）
【
    x = 10
    y = 20
    z = x + y
】

# 命令输出（用《》包裹）
《输出结果：z = [z]》
```

### 4.5 全角符号支持

```matha
# 括号（半角/全角均可）
x = （10 + 20）* 2    # 全角括号
y = (10 + 20) * 2     # 半角括号

# 中文标点
result = 计算结果  #1：[result]。

# Unicode 变量名
质量 = 10
加速度 = 9.8
力 = 质量 * 加速度    # 98.0
```

---

## 五、自然语言计算

### 5.1 基本用法

```powershell
# 算术
"帮我算一下 2+3*4"
"100 的 15% 是多少"
"1000 元打八折多少钱"

# 物理
"自由落体 5 秒后速度多少"
"平抛初速度 10m/s，高度 20m，射程多少"
"动能和质量 5kg 速度 10m/s 的物体"

# 几何
"半径 5 的圆面积"
"边长 3 的正三角形面积"
"底 10 高 6 的梯形面积"

# 数论
"1 到 100 的素数"
"60 的质因数分解"
"12 和 18 的最小公倍数"

# 微积分
"求 x^2 的导数"
"求 sin(x) 的积分"
```

### 5.2 意图类型

| 意图类型 | 关键词示例 |
|---------|-----------|
| 算术 | 加、减、乘、除、倍、打折 |
| 数学函数 | 平方、立方、开方、根号、对数 |
| 物理 | 速度、加速度、动能、重力、自由落体 |
| 几何 | 面积、周长、体积、半径、边长 |
| 素数因数 | 素数、质数、因数、阶乘、分解 |
| 单位换算 | 千米→米、摄氏度→华氏度、磅→千克 |
| 三角函数 | sin、cos、tan、弧度、角度 |
| 公式推导 | 推导、组合、生成、公式生长 |

### 5.3 公式推导

```powershell
# 组合公式
"帮我组合动能和动量公式"

# 推导公式
"对圆面积公式求导"
"推导动能公式"

# 生成公式
"生成一个力相关的公式"
"自动公式生长"
```

---

## 六、成长引擎

### 6.1 内循环

```python
from src.inner_loop import MathaInnerLoop

loop = MathaInnerLoop()

# 单次运行
result = loop.trigger_once(verbose=True)
print(f"健康分: {result['health_score']}")
print(f"状态: {result['status']}")  # healthy / degraded / critical

# 持续运行（后台线程）
loop.start_loop(interval=30.0)

# 停止
loop.stop_loop()

# 查看状态
status = loop.get_status()
```

### 6.2 公式生长

```python
from src.unified_growth import get_unified_growth

ug = get_unified_growth()

# 公式组合：动能 + 动量 → Ek = p²/(2m)
result = ug.formula_grow(op_type="compose", names=["动能", "动量"])

# 公式推导：对圆面积求导 → 圆周长
result = ug.formula_grow(op_type="infer", formula_name="圆面积", var="r")

# 自动化成长（组合+推导+生成）
result = ug.formula_grow(
    op_type="auto",
    max_combinations=5,
    max_derivatives=10,
)

# 领域公式总览
summary = ug.domain_formula_summary()
print(f"已加载领域: {summary['loaded_domains']}")
print(f"总公式数: {summary['total_formulas']}")

# 公式编译为 Python/C
result = ug.compile_formula("牛顿第二定律", optimize=True)
print(result["python"])
print(result["c"])
```

### 6.3 资源审计

```python
from src.growth_engine import GrowthEngine

engine = GrowthEngine()

# 资源审计（13项检查）
resources = engine.audit_resources()
for r in resources:
    status = "✓" if r.status == "ok" else "✗"
    print(f"  {status} {r.name}: {r.status}")

# 自诊断
defects = engine.self_diagnose()
for d in defects:
    print(f"[{d.severity.value}] {d.message}")

# 缺陷统计
stats = engine.get_defect_stats()
print(f"总缺陷: {stats['total']}, 开放: {stats['open']}")
```

---

## 七、诊断系统

### 7.1 源码诊断

```python
from src.unified_diagnostics import get_diagnostics, diagnose_source

# 获取诊断结果
diagnostics = get_diagnostics("x = 1 + ;  # 语法错误")
for d in diagnostics:
    print(f"[{d.severity.value}] L{d.line}: {d.message}")
    print(f"  建议: {d.fix}")

# LSP 格式输出
import json
print(json.dumps([d.to_lsp() for d in diagnostics], indent=2, ensure_ascii=False))
```

### 7.2 增强诊断

```python
from src.diagnostics_v2 import EnhancedDiagnosticCollector, Severity, ContextAnalyzer

collector = EnhancedDiagnosticCollector()
collector.add_error("未定义变量 'abc'", line=3, code="UNDEFINED_VAR",
                    fix="检查变量名拼写，或添加绑定: abc = ?")
collector.add_warning("函数未使用", line=10, code="UNUSED_FUNC")

print(collector.summary())
# "诊断: 1 错误, 1 警告, 重复错误 0 种"

# 上下文分析
analyzer = ContextAnalyzer("x = 1 + abc", line=1, col=8)
context = analyzer.get_context(radius=3)  # 前后3行
similar = analyzer.find_similar_vars("abc")  # 相似变量名
```

---

## 八、公式系统

### 8.1 公式注册

```python
from src.formula_system import Formula, FormulaRegistry
from src.symbolic import Var, Mul, Num

reg = FormulaRegistry()

# 注册公式
reg.register(Formula(
    name="牛顿第二定律",
    expr=Mul(Var("m"), Var("a")),
    params=["F", "m", "a"],
    domain="动力学",
    notes="F = m × a",
))

# 批量注册几何默认公式
reg.register_geometric_defaults()
print(f"公式总数: {len(reg.list_formulas())}")
```

### 8.2 公式查询

```python
# 查询公式
f = reg.get("圆面积")
print(f.evaluate({"半径": 5}))  # 78.5398...

# 参数等价关系
from src.formula_system import ParamEquivalence
reg.add_equivalence(ParamEquivalence(
    lhs="长", rhs="底",
    formula_a="长方形面积", formula_b="平行四边形面积"
))

# 推导
result = reg.derive("平行四边形面积", "底", "长")
print(result)  # "✓ 长方形面积"

# 交叉语言验证
reg.cross_language_verify()
```

### 8.3 符号表达式

```python
from src.symbolic import symbol_expr, simplify_expr, diff_expr, eval_expr

# 解析表达式（支持中文变量名）
e = symbol_expr("质量 * 加速度")
print(e.free_vars())  # {'质量', '加速度'}
print(e.evaluate({"质量": 10, "加速度": 9.8}))  # 98.0

# 简化
simplified = simplify_expr(symbol_expr("x + 0"))
print(simplified)  # x

# 求导
deriv = diff_expr(symbol_expr("x^2 + 3*x"), "x")
print(deriv)  # (2 * x) + 3
print(eval_expr(deriv, x=2))  # 7.0
```

---

## 九、Jupyter 集成

```python
# 加载扩展
%load_ext matha.jupyter

# 单行计算
%matha 计算 100 以内所有素数

# 多行代码
%%matha
func 阶乘(n) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)
result = 阶乘(6)
#1：[result]
```

> **注意：** Jupyter 扩展需要 `pip install ipython jupyter`。未安装时自动跳过，不影响核心功能。

---

## 十、移动应用

### 10.1 Flutter 移动端

```powershell
# 构建移动端
cd mobile
flutter build web    # Web 版本
flutter build apk    # Android
flutter build ios    # iOS
```

### 10.2 离线使用

```powershell
# 使用离线包
tar -xzf offline_package/matha-source-20260831.tar.gz
pip install ./offline_package/matha-source/

# Pyodide WASM 运行时（浏览器内执行）
# mobile/lib/pyodide/pyodide_bridge.dart
```

---

## 十一、Web IDE

```powershell
# 启动 Web 服务
python -m src.compiler.matha_cc_cli --serve

# 或直接打开
start web/index.html
```

---

## 十二、VSCode 扩展

```powershell
# 安装
cd extensions/vscode-matha
npm install
npm run compile
code --install-extension matha-0.1.0.vsix

# 开发模式
npm run watch
```

功能：
- 语法高亮
- 符号补全
- 悬停提示
- 实时诊断

---

## 十三、配置

### 13.1 环境变量

```powershell
# LLM 配置（可选）
$env:MATHA_LLM_API_KEY = "your_key"
$env:MATHA_LLM_MODEL = "deepseek-chat"

# 调试模式
$env:MATHA_DEBUG = "1"

# 离线模式
$env:MATHA_OFFLINE = "1"
```

### 13.2 语言加载策略

```
┌─────────────────────────────────────────────────────────┐
│  默认激活                                                 │
│  • lexer/parser/interp/REPL（零外部依赖）                 │
│  • 正则意图解析                                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  非默认 / 按需加载                                        │
│  • Python Stdlib  (stdlib/*.py, mathlib.py)              │
│  • symbol_codegen (Python/C/JS 代码生成)                  │
│  • Rust/Go/JS 前端  (tree-sitter 可选)                    │
│  • LLM 解析         (anthropic/deepseek/openai 可选)       │
└─────────────────────────────────────────────────────────┘
```

### 13.3 性能调优

```python
from src.growth_engine import GrowthEngine
from src.pkg_manager import clear_pkg_cache, get_pkg_cache_size

# 查看缓存状态
print(get_pkg_cache_size())

# 清理缓存
clear_pkg_cache()

# 调整内循环间隔
loop = MathaInnerLoop()
loop._interval = 60.0  # 60秒（默认30秒）
```

---

## 十四、常见问题

### Q: 没有 API Key 能用吗？
**A:** 可以。正则意图解析为默认主路径，LLM 为可选增强。无 API Key 时自动降级。

### Q: 公式中可以使用中文变量名吗？
**A:** 可以。`symbol_expr("质量 * 加速度")` 支持中文 Unicode 变量。

### Q: 如何在没有网络的环境下使用？
**A:** Matha 完全支持离线使用。核心功能无需网络，公式库/领域模块均本地可用。

### Q: Windows 下 multiprocessing 有问题？
**A:** Worker 函数需定义在模块顶层（不能是 lambda/局部函数）。运行 `python -c "from src.windows_mp_check import get_spawn_warnings; print(get_spawn_warnings())"` 检查。

### Q: 内存占用过高？
**A:** 大型项目调用 `from src.pkg_manager import clear_pkg_cache; clear_pkg_cache()` 清理缓存。

---

## 十五、网络与部署故障排除

### 15.1 GitHub HTTPS 连接失败

**症状：** `Failed to connect to github.com:443 after 21000 ms: Could not connect to server`

**原因：** 部分网络环境（企业防火墙/审查）阻断 HTTPS 443 端口的 TLS 握手，但 TCP 443 端口开放。

**解决方案：切换 SSH 协议**

```powershell
# 1. 确认 SSH 可用
ssh -T git@github.com

# 2. 修改远程 URL 为 SSH
git remote set-url origin git@github.com:zzk2025r/matha.git

# 3. 推送
git push origin main
```

**永久配置（全局）：**
```powershell
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

### 15.2 SSL 握手失败（curl 28）

```powershell
# 强制使用 HTTP/1.1 + schannel
git -c http.version=HTTP/1.1 -c http.sslBackend=schannel push origin main
```

### 15.3 .gitconfig.lock 文件残留

```powershell
# 清除锁文件
Get-Process git -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item "$env:USERPROFILE\.gitconfig.lock" -Force
```

### 15.4 离线环境

```powershell
# 使用离线包
tar -xzf offline_package/matha-pip-packages-20260831.tar.gz
pip install --no-index --find-links=./offline_package matha
```

---

## 十六、参考文档

| 文档 | 路径 |
|------|------|
| 架构文档 | [docs/ARCHITECTURE_v4.4.md](docs/ARCHITECTURE_v4.4.md) |
| 问题与诊断 | [docs/PROBLEMS_AND_DIAGNOSTICS.md](docs/PROBLEMS_AND_DIAGNOSTICS.md) |
| 成长引擎升级 | [docs/GROWTH_ENGINE_UPGRADE_v4.4.57.md](docs/GROWTH_ENGINE_UPGRADE_v4.4.57.md) |
| PowerShell 指南 | [docs/MATHA_POWERSHELL_GUIDE.md](docs/MATHA_POWERSHELL_GUIDE.md) |
| 已知问题 | [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) |
| API 参考 | [docs/api_reference.md](docs/api_reference.md) |
| EBNF 语法 | [docs/17-完整语法EBNF.md](docs/17-完整语法EBNF.md) |

---

## 十七、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v4.4.50 | 2026-08 | 初始发布 |
| v4.4.55 | 2026-09 | 成长引擎升级（公式生长融合） |
| v4.4.56 | 2026-09 | Parser 规范化 (case...of→match...{}) |
| v4.4.57 | 2026-09 | **当前版本**: 解决 KNP-001~010 + Python 非默认语言 + SSH 配置 |

---

## 十八、许可证

Matha 由 Sapiens AI 开发，采用 MIT 许可证。
