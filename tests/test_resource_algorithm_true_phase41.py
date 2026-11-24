# -*- coding: utf-8 -*-
"""阶段 41 资源库真化锁（假成功清算批——危险桩真化 + 合法近似补口径注）。

方向 A 拍板：本阶段只动 ``matha/resource/**``（纯 Matha 资源库），``src/`` 零改动、
本体量不变、指令码不变；验证深度为三面（宿主解释 hi / 编译 VM vm / 五文件 boot 链
调用面 boot）。三类地面：

41a/41b/41c 假通过真化：把「算不出也给数」改成可判定的真实现或诚实 None——
  ``HMAC哈希`` 旧体直接返回消息本身（假摘要），现为两轮 131 进制滚动散列（密钥入
  内外两轮）；``死锁充分条件``/``银行家安全性``/``资源分配图含环``/``活锁检测``/
  ``SSTF/SCAN/C_SCAN 总移动``/``LRU 缺页``/``FCFS/RR/HRRN 周转时间`` 旧体是
  「测值不测条件」残形或恒返哨兵；``Dijkstra距离`` 旧桩恒返 [999999…]（28-⑧ 退役，
  现为权重和+1 作无穷 + O(V²) 顺序松弛）；``内部收益率近似`` 旧桩恒返 0.1，现二分
  求根；``二阶极点``/``音频混音``/``直方图均衡化映射``/``sepia 滤镜`` 等同批改真。

41d-1 链面缺失内建家族：boot ``注册内建(空环境)`` 只 47 名（宿主 Interpreter 3020
  名），``exp/log10/log2/ln/π/组合数/asin/acos/atan/atan2`` 在链面直接「未定义变量」
  ——即整个函数在链面不可调用（三面皆假失败）。逐文件改走三面同判路径：指数写
  ``2.718281828459045 ^ x``、对数换底 ``log(x)/log(10.0)``、反三角走二分（``余弦二分``/
  ``正弦二分``/``反正切`` 迭代）、``atan2`` 走 ``象限角``、``组合数`` 走本地
  ``组合数按连乘``。本档 ``test_41d1_*`` 静态锁 52 个资源文件零缺失内建调用位。

41d-2 无定义读数 → None：分母为 0、空表、越界、负方差等无定义口径不再伪造
  ``999.0``/``999999`` 哨兵或 ``0`` 读数（``产率`` 旧以 0 冒充「无基准」，现 None）。
  本档 ``test_41d2_*`` 静态锁零哨兵常量。

41d-3 合法近似补口径注（零语义改动）：长度比文本相似度、固定 365 天日历差、
  非 softmax 的分类置信度、Zeller 同族周几相位等，注释如实写明近似口径与适用域，
  不改返回值。

登记不修（KNOWN_ISSUES 阶段 41）：① 链面注册内建 47-vs-3020 的表差本身（逐文件
  绕开而非扩 ``matha/stdlib.matha``——后者会扰动 Track B 225 语料快照）；
  ② ``√(9)`` 完全平方数渲染分歧（hi/vm ``3`` vs boot ``3.0``，本文件既有边界）。
"""
import os
import pathlib
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src import interp as host_interp
from src.kernel import exec_api
from src.kernel.errors import MathaRuntimeError

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")
_RESOURCE_DIR = _ROOT / "matha" / "resource"

# 链面 注册内建(空环境) 缺失、宿主 Interpreter 有的名字——资源库若直接调用，
# 链面恒「未定义变量」，函数在自举面不可用（本批逐文件绕开的替换口径见模块文档）。
_CHAIN_MISSING_BUILTINS = ["exp", "log10", "log2", "ln", "π", "组合数",
                           "asin", "acos", "atan", "atan2"]


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _strip_comments(src):
    """去掉 ``(* … *)`` 块注释与字符串字面量——静态锁只看可执行位。"""
    out = []
    i = 0
    while i < len(src):
        if src.startswith("(*", i):
            j = src.find("*)", i + 2)
            i = len(src) if j < 0 else j + 2
        elif src[i] in "\"'":
            q = src[i]
            j = i + 1
            while j < len(src):
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                j += 1
            out.append(src[i:j + 1])
            i = j + 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


@pytest.fixture(scope="module")
def bootvm():
    """五文件 boot 链（Track B boot 面同源）——链面调用执行体。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


def _boot_run(vm, src):
    vm.call("输出清空")
    toks = vm.call("扫描", src, 0, 1, 1, [])
    prog = vm.call("parse", toks)
    env = vm.call("注册内建", vm.call("空环境"))
    for nm, ns in vm._chain_nss.items():
        env = vm.call("绑定环境", env, nm, ns)
    vm.call("执行语句", prog, env)
    return list(vm.call("输出快照"))


def _vm_run(src):
    outs, err = exec_api.run_checked(src)
    if err is not None:
        raise err if isinstance(err, BaseException) else RuntimeError(str(err))
    return outs


def _face(fn):
    try:
        return ("ok", [str(x) for x in fn()])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {str(e)[:90]}")


def _whole(rel, drv):
    return _strip_bom((_RESOURCE_DIR / rel).read_text(encoding="utf-8")) + "\n" + drv + "\n"


def _three(bootvm, rel, drv):
    src = _whole(rel, drv)
    return (_face(lambda: host_interp.interpret(src)[0]),
            _face(lambda: _boot_run(bootvm, src)),
            _face(lambda: _vm_run(src)))


# ============================================================
# 41 三面同判 + 正典读数锁（hi == boot == vm，且读数入锁）
# ============================================================
# 每项 (资源文件, 驱动语句, 正典输出串列表)。ERR 表示三面同判的诚实报错（消息入锁）。
# 手算可得的读数（中位数/方差/组合数/Dijkstra/周转时间/LRU…）按定义核对；
# 浮点近似族（对数、反三角二分、BS、VaR）锁的是「三面同源」而非与解析值逐位相等。
ERR = "ERR"  # 三面同判的诚实报错（消息不入锁，只锁「三面同判且报错」）

_VALUE_CASES = [
    ("statistics/analysis.matha",
     '输出(中位数([4.0, 1.0, 3.0, 2.0]))',
     ['2.5']),
    ("statistics/analysis.matha",
     '输出(中位数([3.0, 1.0, 2.0]))',
     ['2.0']),
    ("statistics/analysis.matha",
     '输出(中位数([]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(平均值([1.0, 2.0, 3.0]))',
     ['2.0']),
    ("statistics/analysis.matha",
     '输出(平均值([]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(方差(2.0, [1.0, 2.0, 3.0]))',
     ['0.6666666666666666']),
    ("statistics/analysis.matha",
     '输出(方差(1.0, []))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(标准差(4.0))',
     ['2.0']),
    ("statistics/analysis.matha",
     '输出(标准差(-1.0))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(标准差([1.0, 2.0, 3.0]))',
     ERR),  # TypeError: must be real number, not list
    ("statistics/analysis.matha",
     '输出(标准差(None))',
     ERR),  # TypeError: must be real number, not NoneType
    ("statistics/analysis.matha",
     '输出(标准差("a"))',
     ERR),  # TypeError: must be real number, not str
    ("statistics/analysis.matha",
     '输出(是负数([1.0]))',
     ['False']),
    ("statistics/analysis.matha",
     '输出(是负数(-2))',
     ['True']),
    ("statistics/analysis.matha",
     '输出(极差([]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(极差([1.0, 5.0, 3.0]))',
     ['4.0']),
    ("statistics/analysis.matha",
     '输出(最大值([]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(最小值([]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(协方差([1.0, 2.0], [3.0, 5.0]))',
     ['0.5']),
    ("statistics/analysis.matha",
     '输出(协方差([], []))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(协方差([1.0], [1.0, 2.0]))',
     ['0.0']),
    ("statistics/analysis.matha",
     '输出(相关系数([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]))',
     ['1.0']),
    ("statistics/analysis.matha",
     '输出(相关系数([1.0, 1.0], [2.0, 5.0]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(相关系数([1.0, 2.0], [5.0, 2.0]))',
     ['-1.0']),
    ("statistics/analysis.matha",
     '输出(线性回归斜率([1.0, 2.0], [5.0, 9.0]))',
     ['4.0']),
    ("statistics/analysis.matha",
     '输出(线性回归斜率([1.0, 1.0], [2.0, 4.0]))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(线性回归斜率([], []))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(二项分布概率(2, 5, 0.5))',
     ['0.3125']),
    ("statistics/analysis.matha",
     '输出(二项分布概率(6, 5, 0.5))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(二项分布概率(2, 5, 1.5))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(二项分布概率(2, 0, 0.5))',
     ['None']),
    ("statistics/analysis.matha",
     '输出(组合数按连乘(10, 3))',
     ['120.0']),
    ("statistics/analysis.matha",
     '输出(复制列表([1.0, 2.0]))',
     ['[1.0, 2.0]']),
    ("statistics/analysis.matha",
     'let a = [3.0, 1.0]\n输出(排序(a))\n输出(a)',
     ['[1.0, 3.0]', '[3.0, 1.0]']),
    ("statistics/analysis.matha",
     '输出(求和乘积([1.0, 2.0, 3.0], [4.0, 5.0]))',
     ['14.0']),
    ("statistics/analysis.matha",
     '输出(正态概率密度(0.0, 0.0, 1.0))',
     ['0.3989424488876037']),
    ("math/exponent_logarithm.matha",
     '输出(常用对数(1000.0))',
     ['2.9999999999999996']),
    ("math/exponent_logarithm.matha",
     '输出(二进制对数(8.0))',
     ['3.0']),
    ("math/exponent_logarithm.matha",
     '输出(常用对数(0.0))',
     ERR),  # ValueError: expected a positive input, got 0.0
    ("math/exponent_logarithm.matha",
     '输出(二进制对数(-1.0))',
     ERR),  # ValueError: expected a positive input, got -1.0
    ("math/trigonometry_advanced.matha",
     '输出(反正弦(0.5))',
     ['0.5235987755982983']),
    ("math/trigonometry_advanced.matha",
     '输出(反正弦(2.0))',
     ['None']),
    ("math/trigonometry_advanced.matha",
     '输出(反余弦(0.5))',
     ['1.0471975511965979']),
    ("math/trigonometry_advanced.matha",
     '输出(反正切(1.0))',
     ['0.7853981633974496']),
    ("math/trigonometry_advanced.matha",
     '输出(度转弧度(180.0))',
     ['3.141592653589793']),
    ("math/trigonometry_advanced.matha",
     '输出(正弦加法公式(0.3, 0.7))',
     ['0.8414709848078965']),
    ("math/trigonometry_advanced.matha",
     '输出(余弦定理(3.0, 4.0, 1.5707963267948966))',
     ['5.0']),
    ("math/trigonometry_advanced.matha",
     '输出(三角形面积海伦(3.0, 4.0, 5.0))',
     ['6.0']),
    ("math/conic_sections.matha",
     '输出(向量夹角(1.0, 0.0, 0.0, 1.0))',
     ['1.570796326794898']),
    ("math/conic_sections.matha",
     '输出(正n边形内角(6))',
     ['120.0']),
    ("math/conic_sections.matha",
     '输出(椭圆周长近似(3.0, 4.0))',
     ['22.21439592707846']),
    ("tools/utility_math.matha",
     '输出(数据熵(["a", "b"], [0.5, 0.5]))',
     ['1.0']),
    ("tools/utility_math.matha",
     '输出(数据熵(["a"], [1.0]))',
     ['0.0']),
    ("tools/utility_math.matha",
     '输出(信噪比(100.0, 1.0))',
     ['20.0']),
    ("tools/utility_math.matha",
     '输出(信噪比(1.0, 0.0))',
     ['None']),
    ("tools/utility_math.matha",
     '输出(香农编码长度(0.25))',
     ['2.0']),
    ("tools/utility_math.matha",
     '输出(香农编码长度(0))',
     ['None']),
    ("tools/utility_math.matha",
     '输出(色彩深度位数(256))',
     ['8']),
    ("tools/utility_math.matha",
     '输出(色彩深度位数(300))',
     ['9']),
    ("tools/utility_math.matha",
     '输出(色彩深度位数(1))',
     ['None']),
    ("tools/utility_math.matha",
     '输出(JPEG压缩率(100, 25))',
     ['4.0']),
    ("tools/utility_math.matha",
     '输出(JPEG压缩率(100, 0))',
     ['None']),
    ("tools/utility_math.matha",
     '输出(长度换算(2.0, "米", "厘米"))',
     ['200.0']),
    ("tools/utility_math.matha",
     '输出(长度换算(1.0, "米", "光年"))',
     ['None']),
    ("tools/utility_math.matha",
     '输出(温度换算(100.0, "摄氏", "华氏"))',
     ['212.0']),
    ("tools/utility_math.matha",
     '输出(周几计算(2026, 11, 24))',
     ['0']),
    ("tools/utility_math.matha",
     '输出(周几计算(2000, 1, 1))',
     ['4']),
    ("tools/utility_math.matha",
     '输出(日期差(2026, 11, 1, 2026, 11, 24))',
     ['23']),
    ("tools/utility_math.matha",
     '输出(时间戳转日期(1700000000))',
     ['2023']),
    ("tools/utility_math.matha",
     '输出(时间戳转日期(0))',
     ['1970']),
    ("apps/lifestyle_math.matha",
     '输出(大圆距离(0.6, 0.1, 0.6, 0.2))',
     ['525.7514242120836']),
    ("apps/lifestyle_math.matha",
     '输出(方位角(0.0, 0.0, 0.0, 1.0))',
     ['90.0']),
    ("apps/lifestyle_math.matha",
     '输出(预估到达时间(10.0, 5.0))',
     ['2.0']),
    ("apps/lifestyle_math.matha",
     '输出(预估到达时间(10.0, 0.0))',
     ['None']),
    ("apps/lifestyle_math.matha",
     '输出(导航路径长度([1.0, 4.0, 2.0]))',
     ['5.0']),
    ("apps/lifestyle_math.matha",
     '输出(导航路径长度([]))',
     ['0.0']),
    ("apps/lifestyle_math.matha",
     '输出(BMI(70.0, 1.75))',
     ['22.857142857142858']),
    ("apps/lifestyle_math.matha",
     '输出(BMI(70.0, 0.0))',
     ['None']),
    ("apps/media_math.matha",
     '输出(灰度化(200, 100, 50))',
     ['124.2']),
    ("apps/media_math.matha",
     '输出(亮度调整(0.5, 0.3))',
     ['0.8']),
    ("apps/media_math.matha",
     '输出(直方图均衡化映射(1, [0, 2, 2, 0], 4))',
     ['2']),
    ("apps/media_math.matha",
     '输出(缓冲时间(1000, 500.0))',
     ['16.0']),
    ("apps/media_math.matha",
     '输出(缓冲时间(1000, 0.0))',
     ['None']),
    ("apps/media_math.matha",
     '输出(音频均衡器(1000.0, 1000.0, 1.0, 6.0, 44100))',
     ['1.995262314968882']),
    ("apps/media_math.matha",
     '输出(sepia滤镜(100, 100, 100))',
     ['(1.0, 1.0, 1.0)']),
    ("apps/media_math.matha",
     '输出(sepia滤镜(0.5, 0.5, 0.5))',
     ['(0.6755, 0.6015, 0.4685)']),
    ("apps/media_math.matha",
     '输出(饱和度调整(0.4, 0.8, 0.2, 0.5))',
     ['(0.506, 0.7060000000000001, 0.406)']),
    ("apps/social_ecommerce.matha",
     '输出(消息队列长度(5, 3))',
     ['2']),
    ("apps/social_ecommerce.matha",
     '输出(积分抵扣(1000, 0.01, 300.0))',
     ['10.0']),
    ("apps/social_ecommerce.matha",
     '输出(协同过滤相似度([1.0, 2.0], [1.0, 2.0]))',
     ['0.9999999999999998']),
    ("apps/social_ecommerce.matha",
     '输出(优先值([10, 5, 1]))',
     ['10']),
    ("apps/education_news.matha",
     '输出(内容相关性("abc", "abcde"))',
     ['0.6']),
    ("apps/education_news.matha",
     '输出(内容相关性("", ""))',
     ['None']),
    ("apps/education_news.matha",
     '输出(内容相关性("ab", "ab"))',
     ['1.0']),
    ("apps/education_news.matha",
     '输出(热度排序得分(10, 2, 1, 0.5))',
     ['10.5']),
    ("apps/education_news.matha",
     '输出(加权平均分([80.0, 90.0], [1, 2]))',
     ['86.66666666666667']),
    ("apps/education_news.matha",
     '输出(百分等级(70.0, 60.0, 10.0))',
     ['84']),
    ("apps/education_news.matha",
     '输出(GPA计算([4.0, 3.0], [3, 4]))',
     ['3.4285714285714284']),
    ("apps/education_news.matha",
     '输出(关键词提取("x", ["a", "b", "c", "d", "e", "f"]))',
     ["['a', 'b', 'c', 'd', 'e']"]),
    ("apps/education_news.matha",
     '输出(新闻分类置信度([1.0, 2.0], [0.5, 0.5]))',
     ['1.5']),
    ("apps/education_news.matha",
     '输出(学习曲线(10.0, 1.0, 0.2))',
     ['0.8807970779778823']),
    ("apps/education_news.matha",
     '输出(协同过滤推荐得分([1.0, 2.0], [1.0, 2.0]))',
     ['0.9999999999999998']),
    ("cs/os_concepts.matha",
     '输出(最佳适配分配([100, 500, 200], 300))',
     ['1']),
    ("cs/os_concepts.matha",
     '输出(最佳适配分配([100, 500, 200], 600))',
     ['-1']),
    ("cs/os_concepts.matha",
     '输出(最佳适配分配([], 10))',
     ['-1']),
    ("cs/os_concepts.matha",
     '输出(首次适配分配([100, 500, 200], 300))',
     ['1']),
    ("cs/os_concepts.matha",
     '输出(目录深度("/a/b/c"))',
     ['3']),
    ("cs/os_concepts.matha",
     '输出(文件名("/a/b/c.txt"))',
     ['c.txt']),
    ("cs/os_concepts.matha",
     '输出(按分隔切分("a,b,c", ","))',
     ["['a', 'b', 'c']"]),
    ("cs/os_concepts.matha",
     '输出(进程数量上限(1000, 3))',
     ['333']),
    ("cs/os_concepts.matha",
     '输出(进程数量上限(1000, 0))',
     ['0']),
    ("cs/os_concepts.matha",
     '输出(内存碎片率(100, 40))',
     ['0.6']),
    ("cs/os_concepts.matha",
     '输出(文件路径合法(""))',
     ['False']),
    ("os/deadlock_sync_math.matha",
     '输出(生产者吞吐量(5, 3, 10))',
     ['3']),
    ("os/deadlock_sync_math.matha",
     '输出(消费者利用率(8, 4))',
     ['1.0']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([10, 3], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([1, 1], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))',
     ['False']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([3, 3, 1], [[7, 5, 3], [4, 2, 2], [2, 5, 4], [2, 2, 8], [1, 3, 2]], [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [3, 1, 4]]))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([3, 3, 0], [[7, 5, 3], [4, 2, 2], [2, 5, 4], [2, 2, 8], [1, 3, 2]], [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [3, 1, 4]]))',
     ['False']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([10], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))',
     ['False']),
    ("os/deadlock_sync_math.matha",
     '输出(银行家安全性([], [], []))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(资源分配图含环(2, [[0, 1], [1, 0]], [[1, 0], [0, 1]]))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(活锁检测([1, 2, 1, 2]))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(哲学家进餐存活(1))',
     ['True']),
    ("os/deadlock_sync_math.matha",
     '输出(哲学家进餐存活(5))',
     ['False']),
    ("os/deadlock_sync_math.matha",
     '输出(信号量wait(0))',
     ['-1']),
    ("os/deadlock_sync_math.matha",
     '输出(读者写者公平性(3, 1))',
     ['0.25']),
    ("os/memory_math.matha",
     '输出(LRU缺页次数([1, 2, 3, 1, 2, 3], 2))',
     ['6']),
    ("os/memory_math.matha",
     '输出(LRU缺页次数([], 2))',
     ['0']),
    ("os/memory_math.matha",
     '输出(内部碎片率(8, 5))',
     ['0.375']),
    ("os/memory_math.matha",
     '输出(页对齐浪费率(5, 4096))',
     ['0.998779296875']),
    ("os/memory_math.matha",
     '输出(有效访问开销(0.9, 1.0, 100.0))',
     ['10.899999999999999']),
    ("os/scheduling_math.matha",
     '输出(FCFS周转时间([0, 1], [5, 3]))',
     ['[5, 7]']),
    ("os/scheduling_math.matha",
     '输出(RR周转时间([0, 0], [5, 4], 2))',
     ['[9, 8]']),
    ("os/scheduling_math.matha",
     '输出(HRRN周转时间([0, 1], [5, 3]))',
     ['[5, 7]']),
    ("os/scheduling_math.matha",
     '输出(平均周转时间([5.0, 8.0]))',
     ['6.5']),
    ("os/filesystem_math.matha",
     '输出(SSTF总移动([100, 50, 90], 60))',
     ['60']),
    ("os/filesystem_math.matha",
     '输出(SCAN总移动([100, 50, 90], 60, "上"))',
     ['90']),
    ("os/filesystem_math.matha",
     '输出(C_SCAN总移动([100, 50, 90], 60))',
     ['90']),
    ("os/os_concepts_math.matha",
     '输出(LRU缺页([1, 2, 3, 1, 2, 3], 2))',
     ['6']),
    ("os/os_concepts_math.matha",
     '输出(TCP慢启动(1, 4))',
     ['16']),
    ("logic/advanced_math.matha",
     '输出(Dijkstra距离(3, [[0, 1, 4], [1, 2, 1]], 0))',
     ['[0, 4, 5]']),
    ("logic/advanced_math.matha",
     '输出(Dijkstra距离(4, [[0, 1, 1], [1, 2, 2], [0, 2, 5], [2, 3, 1]], 0))',
     ['[0, 1, 3, 4]']),
    ("logic/advanced_math.matha",
     '输出(Dijkstra距离(3, [[0, 1, 4]], 5))',
     ['[-1, -1, -1]']),
    ("logic/advanced_math.matha",
     '输出(Dijkstra距离(3, [[0, 1, 4]], 0))',
     ['[0, 4, -1]']),
    ("logic/advanced_math.matha",
     '输出(找零([25, 10, 5, 1], 63, 0, 0))',
     ['6']),
    ("logic/advanced_math.matha",
     '输出(列表含([1, 2], 2))',
     ['True']),
    ("logic/discrete_math.matha",
     '输出(蕴含(真, 假))',
     ['False']),
    ("logic/discrete_math.matha",
     '输出(等价(真, 假))',
     ['False']),
    ("logic/discrete_math.matha",
     '输出(组合数(5, 2))',
     ['10.0']),
    ("logic/discrete_math.matha",
     '输出(排列数(5, 2))',
     ['20.0']),
    ("logic/discrete_math.matha",
     '输出(幂集基数(4))',
     ['16']),
    ("finance/advanced.matha",
     '输出(正态分位数(0.5))',
     ['0.0']),
    ("finance/advanced.matha",
     '输出(正态分位数(1.5))',
     ['None']),
    ("finance/advanced.matha",
     '输出(正态分位数(0))',
     ['None']),
    ("finance/advanced.matha",
     '输出(VaR_参数法(1000.0, 0.95, 0.02))',
     ['32.904228802876304']),
    ("finance/advanced.matha",
     '输出(VaR_参数法(1000.0, 1.5, 0.02))',
     ['None']),
    ("finance/advanced.matha",
     '输出(BlackScholes_看涨(100.0, 100.0, 1.0, 0.05, 0.2))',
     ['10.450575415435083']),
    ("finance/advanced.matha",
     '输出(BlackScholes_看涨(100.0, 100.0, 0.0, 0.05, 0.2))',
     ['0.0']),
    ("finance/advanced.matha",
     '输出(投资组合波动率([0.5, 0.5], [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]]))',
     ['1.5']),
    ("finance/advanced.matha",
     '输出(投资组合波动率([0.5, 0.5], [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]))',
     ['0.0']),
    ("finance/advanced.matha",
     '输出(投资组合波动率([0.5, 0.5], [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]))',
     ['1.0']),
    ("finance/advanced.matha",
     '输出(投资组合收益([0.5, 0.5], [0.02, 0.04]))',
     ['0.03']),
    ("finance/advanced.matha",
     '输出(标准差([1.0, 2.0, 3.0]))',
     ['1.0']),
    ("finance/advanced.matha",
     '输出(误差函数(0.0))',
     ['9.999999717180685e-10']),
    ("finance/math.matha",
     '输出(净现值([100.0, 100.0], 0.1))',
     ['190.9090909090909']),
    ("finance/advanced.matha",
     '输出(内部收益率近似([500.0, 500.0, 500.0], 1000.0))',
     ['0.23375192852825866']),
    ("finance/advanced.matha",
     '输出(内部收益率近似([], 1000.0))',
     ['None']),
    ("security/crypto_math.matha",
     '输出(摘要("abc", 1000))',
     ['191']),
    ("security/crypto_math.matha",
     '输出(HMAC哈希("k", "m"))',
     ['73587586']),
    ("security/crypto_math.matha",
     '输出(HMAC哈希("k2", "m"))',
     ['707180483']),
    ("security/crypto_math.matha",
     '输出(HMAC哈希("k", "m2"))',
     ['737130747']),
    ("security/crypto_math.matha",
     '输出(密码强度评分("Abcdef1!"))',
     ['41']),
    ("security/crypto_math.matha",
     '输出(密码强度评分("abc"))',
     ['14']),
    ("security/crypto_math.matha",
     '输出(有杂类字符("ab"))',
     ['False']),
    ("security/crypto_math.matha",
     '输出(有杂类字符("a!b"))',
     ['True']),
    ("platforms/emerging_math.matha",
     '输出(共识机制效率(4, "PBFT"))',
     ['0.75']),
    ("platforms/emerging_math.matha",
     '输出(共识机制效率(0, "PoW"))',
     ['None']),
    ("platforms/emerging_math.matha",
     '输出(哈希前导零数("00abc"))',
     ['2']),
    ("platforms/emerging_math.matha",
     '输出(区块高度差(5, 3))',
     ['2']),
    ("platforms/emerging_math.matha",
     '输出(工作量证明难度("00ff", "00aa"))',
     ['True']),
    ("embedded/industrial_math.matha",
     '输出(二阶极点(1, 3, 2))',
     ['[-2.0, -1.0]']),
    ("embedded/industrial_math.matha",
     '输出(二阶极点(1, 0, 1))',
     ['[]']),
    ("embedded/industrial_math.matha",
     '输出(异或数(6, 3))',
     ['5']),
    ("embedded/industrial_math.matha",
     '输出(I2C总线速度(100000, 0))',
     ['None']),
    ("embedded/industrial_math.matha",
     '输出(梯形图非门(真))',
     ['False']),
    ("cs/game_apps_math.matha",
     '输出(颜色分量("#80ff00"))',
     ['[128, 255, 0]']),
    ("cs/game_apps_math.matha",
     '输出(音频混音([1.0, 2.0], [3.0, 4.0], 0.5))',
     ['[2.0, 3.0]']),
    ("cs/game_apps_math.matha",
     '输出(落点(0.0, 0.0, 1.0, 1.0))',
     ['(0.0, 0.0)']),
    ("cs/game_apps_math.matha",
     '输出(经验值计算(10, 5))',
     ['3500.0']),
    ("cs/game_apps_math.matha",
     '输出(单十六(15))',
     ['f']),
    ("cs/game_algorithms.matha",
     '输出(A星距离(0.0, 0.0, 3.0, 4.0))',
     ['5.0']),
    ("cs/game_algorithms.matha",
     '输出(A星曼哈顿距离(0, 0, 3, 4))',
     ['7']),
    ("cs/game_algorithms.matha",
     '输出(圆形碰撞(0.0, 0.0, 1.0, 2.0, 0.0, 1.5))',
     ['True']),
    ("physics/optics.matha",
     '输出(放大率(2.0, 4.0))',
     ['-2.0']),
    ("physics/optics.matha",
     '输出(临界角(1.5, 1.0))',
     ['0.7297276562269652']),
    ("physics/optics.matha",
     '输出(单缝衍射第一极小角(2.0, 1.0))',
     ['0.5235987755982983']),
    ("physics/optics.matha",
     '输出(单缝衍射第一极小角(0.5, 1.0))',
     ['None']),
    ("physics/electromagnetism.matha",
     '输出(阻抗(3.0, 7.0, 4.0))',
     ['4.242640687119285']),
    ("physics/electromagnetism.matha",
     '输出(谐振频率(1.0, 1.0))',
     ['0.15915507752443828']),
    ("extended/modeling_math.matha",
     '输出(三相功率(380.0, 10.0, 0.9))',
     ['5923.61376188556']),
    ("extended/modeling_math.matha",
     '输出(一阶响应(1.0, 1.0))',
     ['0.6321205588285577']),
    ("extended/modeling_math.matha",
     '输出(疲劳寿命(50.0, 100.0, 1000))',
     ['10000']),
    ("extended/modeling_math.matha",
     '输出(疲劳寿命(0.0, 100.0, 1000))',
     ['None']),
    ("extended/modeling_math.matha",
     '输出(变压器变比(10, 0))',
     ['None']),
    ("航空航天/orbital_math.matha",
     '输出(大圆距离(0.0, 0.0, 0.0, 1.0, 6371.0))',
     ['111.19492664455832']),
    ("航空航天/orbital_math.matha",
     '输出(轨道倾角(0.5, 1.0))',
     ['29.999999999999964']),
    ("航空航天/orbital_math.matha",
     '输出(轨道倾角(2.0, 1.0))',
     ['None']),
    ("航空航天/orbital_math.matha",
     '输出(火箭方程(300.0, 10.0, 1.0))',
     ['6776.507928681477']),
    ("航空航天/orbital_math.matha",
     '输出(第一宇宙速度(6.674e-11, 5.972e24, 6.371e6))',
     ['7909.503055253881']),
    ("航空航天/orbital_math.matha",
     '输出(马赫数(300.0, 340.0))',
     ['0.8823529411764706']),
    ("航空航天/orbital_math.matha",
     '输出(升阻比(1.0, 0.0))',
     ['None']),
    ("geography/info.matha",
     '输出(大圆距离(0.0, 0.0, 0.0, 1.0))',
     ['1.0000000000000009']),
    ("geography/info.matha",
     '输出(时区差(120.0, 0.0))',
     ['8.0']),
    ("geography/info.matha",
     '输出(坡度计算(3.0, 4.0))',
     ['75.0']),
    ("geography/info.matha",
     '输出(坡度计算(3.0, 0.0))',
     ['None']),
    ("geography/info.matha",
     '输出(海拔气压(0.0))',
     ['101.325']),
    ("chemistry/stoichiometry.matha",
     '输出(pH值(0.001))',
     ['2.9999999999999996']),
    ("chemistry/stoichiometry.matha",
     '输出(pH值(0.0))',
     ['None']),
    ("chemistry/stoichiometry.matha",
     '输出(pKa到Ka(3.0))',
     ['0.001']),
    ("chemistry/stoichiometry.matha",
     '输出(产率(10.0, 20.0))',
     ['50.0']),
    ("chemistry/stoichiometry.matha",
     '输出(产率(10.0, 0.0))',
     ['None']),
    ("chemistry/stoichiometry.matha",
     '输出(产率(0.0, 20.0))',
     ['0.0']),
]

_IDS = [f"{i:02d}-{Path(rel).stem}" for i, (rel, _, _) in enumerate(_VALUE_CASES)]


@pytest.mark.parametrize("rel,drv,expect", _VALUE_CASES, ids=_IDS)
def test_41_resource_three_face_values(bootvm, rel, drv, expect):
    """资源库真化函数：hi / boot 链 / vm 三面输出逐字同判，且等于入锁的正典读数。"""
    h, b, v = _three(bootvm, rel, drv)
    assert h == b == v, (rel, drv, h, b, v)
    if expect == "ERR":
        assert h[0] == "err", (rel, drv, h)
    else:
        assert h == ("ok", expect), (rel, drv, h, expect)


# ============================================================
# 41d-1 链面缺失内建零出现（静态锁）
# ============================================================

def _missing_builtin_hits(text, name):
    """``name(`` 调用位（可执行段）计数，排除同名 ``func name`` 本地定义。"""
    calls = re.findall(r"(?<![A-Za-z0-9_一-鿿])" + re.escape(name) + r"\s*\(", text)
    defs = re.findall(r"func\s+" + re.escape(name) + r"\b", text)
    return len(calls) - len(defs)


def test_41d1_resource_files_present():
    """资源库语料规模锁（本批口径：52 个纯 Matha 资源文件全部纳入静态扫描）。"""
    files = sorted(pathlib.Path("matha/resource").rglob("*.matha"))
    assert len(files) == 52, len(files)


@pytest.mark.parametrize("name", _CHAIN_MISSING_BUILTINS)
def test_41d1_chain_missing_builtin_zero_call_sites(name):
    """链面缺失内建在资源库可执行位零出现（出现即链面「未定义变量」= 函数不可用）。"""
    hits = []
    for p in sorted(_RESOURCE_DIR.rglob("*.matha")):
        text = _strip_comments(p.read_text(encoding="utf-8"))
        n = _missing_builtin_hits(text, name)
        if n > 0:
            hits.append((p.name, n))
    assert hits == [], hits


def test_41d1_replacement_idioms_run_on_chain(bootvm):
    """替换口径本身在链面可跑（指数 ^ / 换底 log / 反三角二分 / 本地组合数）。"""
    cases = [
        ("math/exponent_logarithm.matha", '输出(常用对数(1000.0))'),
        ("math/exponent_logarithm.matha", '输出(二进制对数(8.0))'),
        ("math/trigonometry_advanced.matha", '输出(反正弦(0.5))'),
        ("math/trigonometry_advanced.matha", '输出(反正切(1.0))'),
        ("statistics/analysis.matha", '输出(组合数按连乘(10, 3))'),
        ("apps/lifestyle_math.matha", '输出(方位角(0.0, 0.0, 0.0, 1.0))'),
    ]
    for rel, drv in cases:
        h, b, v = _three(bootvm, rel, drv)
        assert h == b == v and h[0] == "ok", (rel, drv, h, b, v)


# ============================================================
# 41d-2 无定义读数不伪造哨兵（静态锁）
# ============================================================

@pytest.mark.parametrize("pattern", [r"999999", r"999\.0", r"-999"])
def test_41d2_no_sentinel_constants_in_executable_position(pattern):
    """可执行位零哨兵常量（注释里「旧体返回 999.0」的口径说明不算）。"""
    hits = []
    for p in sorted(_RESOURCE_DIR.rglob("*.matha")):
        text = _strip_comments(p.read_text(encoding="utf-8"))
        if re.search(pattern, text):
            hits.append(p.name)
    assert hits == [], hits


def test_41d2_undefined_readings_are_none(bootvm):
    """无定义族三面同判 None（不是 0、不是 999.0、不是崩溃）。"""
    cases = [
        ("statistics/analysis.matha", '输出(平均值([]))'),
        ("statistics/analysis.matha", '输出(中位数([]))'),
        ("statistics/analysis.matha", '输出(极差([]))'),
        ("statistics/analysis.matha", '输出(标准差(-1.0))'),
        ("statistics/analysis.matha", '输出(协方差([], []))'),
        ("statistics/analysis.matha", '输出(二项分布概率(6, 5, 0.5))'),
        ("chemistry/stoichiometry.matha", '输出(pH值(0.0))'),
        ("chemistry/stoichiometry.matha", '输出(产率(10.0, 0.0))'),
        ("apps/lifestyle_math.matha", '输出(预估到达时间(10.0, 0.0))'),
        ("tools/utility_math.matha", '输出(信噪比(1.0, 0.0))'),
        ("tools/utility_math.matha", '输出(长度换算(1.0, "米", "光年"))'),
        ("platforms/emerging_math.matha", '输出(共识机制效率(0, "PoW"))'),
        ("extended/modeling_math.matha", '输出(疲劳寿命(0.0, 100.0, 1000))'),
        ("finance/advanced.matha", '输出(正态分位数(1.5))'),
        ("航空航天/orbital_math.matha", '输出(升阻比(1.0, 0.0))'),
    ]
    for rel, drv in cases:
        h, b, v = _three(bootvm, rel, drv)
        assert h == b == v == ("ok", ["None"]), (rel, drv, h, b, v)


# ============================================================
# 41c 真算法语义锁（不只看读数，还断结构性质的真）
# ============================================================

def test_41c_hmac_hash_actually_keyed(bootvm):
    """HMAC哈希 真化：不再是消息本身，且密钥/消息任一改动都换摘要（三面同判）。"""
    same_k = _three(bootvm, "security/crypto_math.matha", '输出(HMAC哈希("k", "m"))')
    diff_k = _three(bootvm, "security/crypto_math.matha", '输出(HMAC哈希("k2", "m"))')
    diff_m = _three(bootvm, "security/crypto_math.matha", '输出(HMAC哈希("k", "m2"))')
    for trio in (same_k, diff_k, diff_m):
        assert trio[0] == trio[1] == trio[2], trio
    out = same_k[0][1][0]
    assert out != "m", out
    assert diff_k[0][1] != diff_m[0][1] != same_k[0][1]
    # 确定性：同入参同输出
    assert _three(bootvm, "security/crypto_math.matha",
                  '输出(HMAC哈希("k", "m"))')[0] == same_k[0]


def test_41c_dijkstra_real_shortest_paths(bootvm):
    """Dijkstra距离 真化（28-⑧ 退役）：可达按最短路、不可达记 -1、起点越界全 -1。"""
    cases = [
        # 0→1(4)、1→2(1)：d = [0, 4, 5]（权重为整，表逐元素整）
        ('输出(Dijkstra距离(3, [[0, 1, 4], [1, 2, 1]], 0))', ["[0, 4, 5]"]),
        # 0→2(5) 直连劣于 0→1→2(1+2)；2→3(1) ⇒ [0, 1, 3, 4]
        ('输出(Dijkstra距离(4, [[0, 1, 1], [1, 2, 2], [0, 2, 5], [2, 3, 1]], 0))',
         ["[0, 1, 3, 4]"]),
        ('输出(Dijkstra距离(3, [[0, 1, 4]], 5))', ["[-1, -1, -1]"]),
        ('输出(Dijkstra距离(3, [[0, 1, 4]], 0))', ["[0, 4, -1]"]),
    ]
    for drv, expect in cases:
        h, b, v = _three(bootvm, "logic/advanced_math.matha", drv)
        assert h == b == v == ("ok", expect), (drv, h, b, v)


def test_41c_copy_and_sort_do_not_alias(bootvm):
    """复制列表/排序 真化：排序不改入参（旧 ``复制列表`` 直接返回同一对象）。"""
    drv = 'let a = [3.0, 1.0]\n输出(排序(a))\n输出(a)'
    h, b, v = _three(bootvm, "statistics/analysis.matha", drv)
    assert h == b == v == ("ok", ["[1.0, 3.0]", "[3.0, 1.0]"]), (h, b, v)


def test_41c_median_uses_int_division(bootvm):
    """中位数 真化：偶数长度走 ``//``（``/`` 恒浮除，旧式落 索引操作不支持: list[1.5]）。"""
    for drv, expect in [('输出(中位数([4.0, 1.0, 3.0, 2.0]))', ["2.5"]),
                        ('输出(中位数([3.0, 1.0, 2.0]))', ["2.0"]),
                        ('输出(中位数([5.0]))', ["5.0"])]:
        h, b, v = _three(bootvm, "statistics/analysis.matha", drv)
        assert h == b == v == ("ok", expect), (drv, h, b, v)


def test_41c_banker_and_cycle_detect_decide(bootvm):
    """银行家安全性/资源分配图含环：判定随入参真的变（旧桩恒真/恒假）。

    Need = 最大需求 − 已分配：`[10, 3]` 先满足 P0（Need [7, 0]）后 Work = [13, 8]
    再满足 P1（Need [−2, 6]）⇒ 安全；`[1, 1]` 两个进程都满足不了 ⇒ 不安全。
    """
    ok = _three(bootvm, "os/deadlock_sync_math.matha",
                '输出(银行家安全性([10, 3], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))')
    bad = _three(bootvm, "os/deadlock_sync_math.matha",
                 '输出(银行家安全性([1, 1], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))')
    for trio in (ok, bad):
        assert trio[0] == trio[1] == trio[2], trio
    assert ok[0] == ("ok", ["True"]), ok
    assert bad[0] == ("ok", ["False"]), bad
    # 维度不齐（可用资源比需求行短）= 非法声明，取保守答 False 而非越过末尾下标崩
    mismatch = _three(bootvm, "os/deadlock_sync_math.matha",
                      '输出(银行家安全性([10], [[10, 5], [2, 8]], [[3, 5], [4, 2]]))')
    assert mismatch[0] == ("ok", ["False"]), mismatch
    # 资源分配图含环：P0 等 P1 占有 r1、P1 等 P0 占有 r0 ⇒ 等待图成环；
    # 只有一方向等待 ⇒ 无环（旧桩恒返 假，两者同答）。
    环 = _three(bootvm, "os/deadlock_sync_math.matha",
                '输出(资源分配图含环(2, [[1, 0], [0, 1]], [[0, 1], [1, 0]]))')
    无环 = _three(bootvm, "os/deadlock_sync_math.matha",
                  '输出(资源分配图含环(2, [[1, 0], [0, 0]], [[0, 0], [1, 0]]))')
    for trio in (环, 无环):
        assert trio[0] == trio[1] == trio[2], trio
    assert 环[0] == ("ok", ["True"]), 环
    assert 无环[0] == ("ok", ["False"]), 无环


# ============================================================
# 登记锁（阶段 41 登记不修项防漂移）
# ============================================================

def test_41x_sqrt_perfect_square_rendering_registration(bootvm):
    """登记②：完全平方数 ``√(9)`` 渲染分歧——hi/vm 出 ``3``、boot 链出 ``3.0``。

    既有边界（非本批引入）：链面 sqrt 走纯 Matha 牛顿迭代恒浮点，宿主/VM 面
    走 Python ``math.sqrt`` 后整值化。非完全平方（``√(2)``）三面逐位同判。
    本锁只防漂移，不锁正确性。
    """
    for drv, hi_v, boot_v in [('输出(√(9))', "3", "3.0"), ('输出(√(4))', "2", "2.0")]:
        h, b, v = _three(bootvm, "math/algebra_advanced.matha", drv)
        assert h == v == ("ok", [hi_v]), (drv, h, v)
        assert b == ("ok", [boot_v]), (drv, b)
    h, b, v = _three(bootvm, "math/algebra_advanced.matha", '输出(√(2))')
    assert h == b == v == ("ok", ["1.4142135623730951"]), (h, b, v)


def test_41x_carrier_exception_class_registration(bootvm):
    """登记：None 参与算术的异常载体类名分歧（hi MathaRuntimeError vs boot/vm TypeError）。

    本批真化后的 None 口径把「无定义」表达为值，故只有 *调用方* 误用 None 才落到
    这一族；三面消息文本同判、类名异判——38-①/40-③ 同族，登记不修。
    """
    for drv in ['输出(1 - None)', '输出(None - 1.0)']:
        h, b, v = _three(bootvm, "statistics/analysis.matha", drv)
        assert h[0] == b[0] == v[0] == "err", (drv, h, b, v)
        assert h[1].startswith("MathaRuntimeError: 类型错误: "), (drv, h)
        assert b[1].startswith("TypeError: ") and v[1].startswith("TypeError: "), (drv, b, v)
        assert h[1].split("类型错误: ", 1)[1] == b[1].split("TypeError: ", 1)[1], (drv, h, b)
        assert b[1] == v[1], (drv, b, v)


def test_41x_zero_dependency_boundary():
    """边界锁：零依赖边界不因资源库批改变（pyproject dependencies 仍为空表）。"""
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies\s*=\s*\[\s*\]", text, re.M), "依赖表非空"
