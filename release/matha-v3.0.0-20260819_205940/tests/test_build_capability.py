"""验证 Matha 能否构建各类软件，并评估学科知识充足性。"""
import os, sys, glob

sys.path.insert(0, r"D:\trae")
from src.codegen import codegen
from src.interp import interpret

PASS, FAIL = [], []

def test(name, ok, detail=""):
    if ok:
        PASS.append(name)
        print(f"  ✓ {name}{detail}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}{detail}")

# ============================================================
# 1. Matha 解释器核心
# ============================================================
print("\n【1. Matha 解释器核心】")

def run_interp(name, src, expected_single):
    try:
        out, _ = interpret(src)
        # out 可能是 [val] 或 val
        actual = out[0] if isinstance(out, list) else out
        ok = abs(actual - expected_single) < 0.5
        test(name, ok, f" → {out}")
    except Exception as e:
        test(name, False, f": {e}")

run_interp("算术运算", "#1：[3 + 4 * 2]", 11)
run_interp("函数定义", "func 加(a: Int, b: Int) -> Int = (a, b) => a + b\n#1：[加(3)(4)]", 7)
run_interp("三元条件", "#1：[3 > 2 ? 100 : 200]", 100)
run_interp("递归阶乘", "func 阶乘(n: Int) -> Int = (n) => (n <= 1) ? 1 : n * 阶乘(n - 1)\n#1：[阶乘(5)]", 120)
run_interp("集合求和", "#1：[sum([1,2,3,4,5])]", 15)
run_interp("三角函数", "#1：[sin(3.14159/6)]", 0.5)
run_interp("对数指数", "#1：[exp(1.0)]", 2.718)

# ============================================================
# 2. 网页应用生成
# ============================================================
print("\n【2. 网页应用生成】")
def gen(name, spec, out_dir, checks=None):
    try:
        r = codegen(spec, out_dir)
        if not r.成功:
            test(name, False, f": {r.错误}")
            return False
        files = r.文件
        test(name, True, f" → {files}")
        if checks:
            for cname, check_fn in checks:
                ok = check_fn(out_dir)
                test(f"{name}-{cname}", ok)
        return r.成功
    except Exception as e:
        test(name, False, f": {e}")
        return False

gen("网页-计算器", [
    "应用", "网页", "计算器",
    [["h1", "计算器", [], []], ["input", "", [["id", "display"]], []], ["button", "1", [["onclick", "appendChar(1)"]], []]],
    [["宽度", "400"]]
], "D:/trae/_test_output/web"),

gen("网页-待办清单", [
    "应用", "网页", "待办清单",
    [["h1", "待办清单", [], []], ["input", "", [["id", "todo_input"]], []], ["button", "添加", [["onclick", "addTodo()"]], []]],
    [["宽度", "500"]]
], "D:/trae/_test_output/web_todo"),

# ============================================================
# 3. 桌面应用生成
# ============================================================
print("\n【3. 桌面应用生成】")
gen("桌面-记事本", [
    "应用", "桌面", "记事本",
    [["text", "", [["id", "content"], ["width", "60"], ["height", "20"]], []],
     ["button", "保存", [["onclick", "save_doc"]], []], ["button", "清空", [["onclick", "clear_doc"]], []]],
    [["尺寸", "600x400"]]
], "D:/trae/_test_output/desktop"),

def check_py_valid(d):
    path = os.path.join(d, "main.py")
    if not os.path.exists(path): return False
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        compile(src, "main.py", "exec")
        return True
    except SyntaxError:
        return False
test("桌面-Python语法验证", check_py_valid("D:/trae/_test_output/desktop"), " ✓")

# ============================================================
# 4. 后端服务生成
# ============================================================
print("\n【4. 后端服务生成】")
gen("后端-API服务", [
    "应用", "服务", "API服务",
    [["接口", "GET", "/api/hello", "hello_handler"], ["接口", "POST", "/api/echo", "echo_handler"]],
    [["端口", "8080"]]
], "D:/trae/_test_output/backend"),

# ============================================================
# 5. 系统脚本生成
# ============================================================
print("\n【5. 系统脚本生成】")
gen("系统-部署脚本", [
    "应用", "系统", "部署脚本",
    [["endpoint", "exec", "/build", "mkdir -p build"], ["endpoint", "file", "/readme", "echo OK"]],
    []
], "D:/trae/_test_output/system"),

# ============================================================
# 6. 游戏生成
# ============================================================
print("\n【6. 游戏生成】")
def check_canvas(d):
    html = os.path.join(d, "index.html")
    if not os.path.exists(html): return False
    with open(html, encoding="utf-8") as f:
        src = f.read()
    return "canvas" in src and "requestAnimationFrame" in src
gen("游戏-打砖块", [
    "应用", "游戏", "打砖块",
    [["角色", "player", []], ["敌人", "enemy", []], ["收集", "ball", []], ["文字", "得分: 0", []]],
    [["宽度", "800"], ["高度", "600"], ["帧率", "60"], ["背景", "#000"]]
], "D:/trae/_test_output/game"),
test("游戏-Canvas验证", check_canvas("D:/trae/_test_output/game"), " ✓")

# ============================================================
# 7. 3D建模生成
# ============================================================
print("\n【7. 3D建模生成】")
def check_threejs(d):
    html = os.path.join(d, "index.html")
    if not os.path.exists(html): return False
    with open(html, encoding="utf-8") as f:
        src = f.read()
    return "three" in src.lower()
gen("3D建模-太阳系", [
    "应用", "建模", "太阳系",
    [["球体", "太阳", {"r": 0.5, "颜色": "#FFD700"}],
     ["球体", "地球", {"r": 0.1, "颜色": "#4169E1"}],
     ["光源", "环境光", {"type": "ambient"}],
     ["光源", "方向光", {"type": "directional"}]],
    [["宽度", "800"], ["高度", "600"], ["动画", "旋转"]]
], "D:/trae/_test_output/model3d"),
test("3D建模-Three.js验证", check_threejs("D:/trae/_test_output/model3d"), " ✓")

# ============================================================
# 8. 学科知识充足性评估
# ============================================================
print("\n【8. 学科知识充足性评估】")
counts = {
    "resource": len(glob.glob("matha/resource/**/*.matha", recursive=True)),
    "knowledge": len(glob.glob("matha/knowledge/**/*.matha", recursive=True)),
    "library": len(glob.glob("matha/library/**/*.matha", recursive=True)),
    "domains": len(glob.glob("src/domains/**/*.py", recursive=True)),
}
for k, v in counts.items():
    print(f"  {k}: {v} 文件")

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = len(PASS) + len(FAIL)
print(f"构建能力: {len(PASS)}/{total} 通过")
if FAIL:
    print(f"失败: {', '.join(FAIL)}")
print("=" * 60)

print("\n【知识缺口清单】")
gaps = [
    ("3D建模数学", "变换矩阵/四元数/透视投影/法线计算", "medium"),
    ("游戏开发算法", "A*寻路/碰撞检测/空间分割/状态机", "medium"),
    ("Web应用", "HTTP协议/REST API设计/状态管理/本地存储", "high"),
    ("桌面应用", "事件驱动/文件I/O/路径处理/剪贴板", "medium"),
    ("操作系统", "进程管理/内存管理/文件系统/系统调用", "high"),
    ("金融数学", "期权定价(Black-Scholes)/风险评估/投资组合", "low"),
    ("数据库概念", "SQL基础/关系代数/索引/事务", "medium"),
    ("离散数学进阶", "图算法/动态规划/贪心算法", "medium"),
]
for domain, content, severity in gaps:
    icon = "●" if severity == "high" else ("◐" if severity == "medium" else "○")
    print(f"  {icon} {domain}: {content}")
print("=" * 60)

sys.exit(0 if not FAIL else 1)
