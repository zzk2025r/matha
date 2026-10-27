# Matha 使用指南（PowerShell）

## 一、下载安装

### 方法 1：pip 安装（推荐）
```powershell
# 安装 Matha
pip install matha

# 验证安装
matha --version
```

### 方法 2：源码安装
```powershell
# 克隆仓库
git clone https://github.com/zzk2025r/matha.git
cd matha

# 安装依赖
pip install -e .

# 验证
python -m src.matha_main --version
```

### 方法 3：离线安装
```powershell
# 使用离线包
tar -xzf offline_package/matha-pip-packages-20260831.tar.gz
pip install --no-index --find-links=./offline_package matha
```

---

## 二、运行方式

### 1. 交互式 REPL
```powershell
# 启动 REPL
matha

# 或
python -m src.matha_main
```

### 2. 表达式计算
```powershell
# 单行表达式
matha eval "sin(3.14) + cos(1.57)"

# 复杂表达式
matha eval "2 + 3 * 4"
matha eval "sqrt(16) + pi"
```

### 3. 运行 .matha 文件
```powershell
# 运行 Matha 源文件
matha run demo.matha

# 带调试信息
matha run demo.matha --debug
```

### 4. 编译到 C
```powershell
# 编译到 C 代码
matha compile demo.matha -o output.c

# 优化编译
matha optimize demo.matha -o output.c

# 生成 LLVM IR
matha llvm demo.matha -o output.ll
```

### 5. 调试模式
```powershell
# 显示 AST + MIR + 代码生成
matha debug demo.matha
```

---

## 三、基本语法

### 变量与输出
```matha
# 赋值
x = 10
y = 20

# 输出（段号 1）
#1：[x + y]
#1: [结果]
```

### 函数定义
```matha
# 定义函数
func 平方(x) -> Float = (x) => x * x

# 调用函数
result = 平方(5)
#1：[result]  →  输出 25
```

### 条件表达式
```matha
# 三元表达式
r = 5 > 3 ? 真 : 假
#1：[r]
```

### 循环
```matha
# for 循环
for i in range(5):
    s = s + i
#1：[s]
```

### 函数式语法（Lambda + 柯里化）
```matha
# Lambda 函数
add = (a, b) => a + b

# 柯里化
mul = (a) => (b) => a * b
result = mul(3)(4)  # 12
```

---

## 四、数学计算

### 内置数学函数
```python
# 三角函数
sin(0), cos(0), tan(pi/4)
asin(1), acos(0), atan(1)

# 对数指数
log(2.71828), log10(100), log2(8)
exp(1), sqrt(16), pow(2, 3)

# 常量
pi, e, tau, phi
```

### 物理常量
```python
G       # 万有引力常数 6.674e-11
c       # 光速 299792458 m/s
g       # 重力加速度 9.80665 m/s²
h_planck # 普朗克常数 6.626e-34
N_A     # 阿伏伽德罗常数 6.022e23
R       # 气体常数 8.314 J/(mol·K)
```

---

## 五、自然语言计算

### 公式推导意图
```powershell
# 组合公式
"帮我组合动能和动量公式"

# 推导公式
"对圆面积公式求导"

# 生成公式
"生成一个力相关的公式"
```

### 常见问题
```powershell
# 算术
"帮我算一下 2+3*4"
"100 的 15% 是多少"

# 物理
"自由落体 5 秒后速度多少"
"平抛初速度 10m/s，高度 20m，射程多少"

# 几何
"半径 5 的圆面积"
"边长 3 的正三角形面积"

# 微积分
"求 x^2 的导数"
"求 sin(x) 的积分"
```

---

## 六、成长引擎

### 查看状态
```powershell
# 查看成长引擎状态
from src.growth_engine import GrowthEngine
e = GrowthEngine()
stats = e.get_growth_stats()
print(stats)

# 资源审计
resources = e.audit_resources()
for r in resources:
    print(f"{r.name}: {r.status}")
```

### 公式生长
```powershell
# 自动化公式生长
from src.unified_growth import get_unified_growth
ug = get_unified_growth()

# 公式组合
result = ug.formula_grow(op_type="compose", names=["动能", "动量"])

# 公式推导
result = ug.formula_grow(op_type="infer", formula_name="动能", var="v")

# 自动化成长
result = ug.formula_grow(op_type="auto", max_combinations=5, max_derivatives=10)

# 领域公式总览
summary = ug.domain_formula_summary()

# 公式编译
compile_result = ug.compile_formula("牛顿第二定律")
print(compile_result["python"])
print(compile_result["c"])
```

---

## 七、多语言代码生成

```python
from src.formula_compiler import FormulaCompiler
from src.formula_system import FormulaRegistry

reg = FormulaRegistry()
reg.register_geometric_defaults()

compiler = FormulaCompiler(reg)

# 编译单个公式
result = compiler.compile_formula("圆面积")
print("Python:", result.python_code)
print("C:", result.c_code)

# 编译所有公式
results = compiler.compile_all(optimize=True)
```

---

## 八、内循环成长

```python
from src.inner_loop import MathaInnerLoop

loop = MathaInnerLoop()

# 单次运行
result = loop.trigger_once(verbose=True)
print(f"健康分: {result['health_score']}")
print(f"状态: {result['status']}")

# 持续运行（后台线程）
loop.start_loop(interval=30.0)

# 查看状态
status = loop.get_status()
print(status)

# 停止
loop.stop_loop()
```

---

## 九、测试

```powershell
# 运行全部测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_matha_growth.py -v
pytest tests/test_unified_layers.py -v
pytest tests/test_matha_compiler.py -v

# 运行集成测试
pytest tests/test_integration/ -v
```
