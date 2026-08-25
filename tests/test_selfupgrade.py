"""自我升级子系统测试：探针 / 沙箱 / 升级。

覆盖四个层次：
  1) 探针（Probe）：只读内省——state/env/func_names/builtin_names/has/func_info
  2) 沙箱（Sandbox）：隔离试运行——隔离、diff（新函数/改函数/新变量/改变量/新构造子）、
     commit/rollback、错误捕获、继承本体、空变更
  3) 升级（upgrade）：沙箱试运行 → 校验 → 合并；成功/运行时错/语法错/verify 通过/
     verify 拒绝/verify 异常/覆写/批量/空源码/含输出/连续升级/失败恢复/模块级函数
  4) Matha 侧自升级内建：升级/试运行/探针_状态/探针_已定义/探针_函数列表/
     升级失败抛错/沙箱内升级隔离/沙箱内试运行

运行：python -m tests.test_selfupgrade
"""

from src.parser import parse
from src.interp import Interpreter, interpret, MathaRuntimeError
from src.selfupgrade import Probe, Sandbox, UpgradeResult, upgrade


def _interp_with(src: str) -> Interpreter:
    """解析并运行源码，返回已装载的解释器。"""
    i = Interpreter()
    i.run(parse(src))
    return i


# ============================================================
# 1) 探针 Probe
# ============================================================

def test_probe_state():
    """探针 state() 反映变量/函数/内建/构造子名与计数。"""
    print("\n--- 探针: state ---")
    i = _interp_with('func 平方(x: Int) -> Int = (x) => x * x')
    st = i.probe().state()
    assert "平方" in st["函数"], st
    assert "ord" in st["内建"], st
    # 自我升级内建也应出现在内建列表
    assert "升级" in st["内建"], st
    assert "探针_状态" in st["内建"], st
    assert st["输出数"] == 0 and st["追踪数"] == 0
    print(f"  ✓ 函数={st['函数']} 内建含 升级/探针_状态")


def test_probe_has_and_func_info():
    """探针 has() / func_info() 查询单个符号。"""
    print("\n--- 探针: has / func_info ---")
    i = _interp_with('func 平方(x: Int) -> Int = (x) => x * x')
    p = i.probe()
    assert p.has("平方") is True
    assert p.has("不存在") is False
    assert p.has("ord") is True  # 内建
    info = p.func_info("平方")
    assert info == {"名": "平方", "参数": ["x"]}, info
    assert p.func_info("不存在") is None
    print("  ✓ has(平方)=T, func_info 参数=['x']")


def test_probe_env_func_names_builtin_names():
    """探针 env()/func_names()/builtin_names() 返回快照。"""
    print("\n--- 探针: env/func_names/builtin_names ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x\n@:计数 = 7')
    p = i.probe()
    # env 快照含变量
    env = p.env()
    assert env["计数"] == 7, env
    # func_names 含自定义函数
    fns = p.func_names()
    assert "f" in fns, fns
    # builtin_names 含 ord/chr 等纯函数与升级内建
    bns = p.builtin_names()
    assert "ord" in bns and "升级" in bns, bns
    # 快照独立：修改返回的 dict 不影响本体
    env["注入"] = 999
    assert "注入" not in i.env
    print("  ✓ env(计数=7); func_names 含 f; builtin_names 含 ord/升级; 快照独立")


def test_probe_has_constructor():
    """探针 has() 识别枚举构造子。"""
    print("\n--- 探针: 构造子识别 ---")
    i = _interp_with('enum 色 { 红 绿 蓝 }')
    p = i.probe()
    assert p.has("红") is True
    assert p.has("绿") is True
    assert p.has("蓝") is True
    assert p.has("紫") is False  # 未定义的构造子
    st = i.probe().state()
    assert {"红", "绿", "蓝"}.issubset(set(st["构造子"])), st
    print("  ✓ has(红/绿/蓝)=T, has(紫)=F; state 构造子含三色")


# ============================================================
# 2) 沙箱 Sandbox
# ============================================================

def test_sandbox_isolation():
    """沙箱中运行代码不污染本体解释器。"""
    print("\n--- 沙箱: 隔离 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    outs, trace, err = sb.run('func 新增(x: Int) -> Int = (x) => x + 1')
    assert err is None, err
    # 沙箱内可调用新增函数
    assert sb.call("新增", 5) == 6
    # 本体未受影响：新增函数不存在于本体
    assert "新增" not in i.funcs, "本体被污染！"
    assert i.call("基础", 9) == 9
    print("  ✓ 沙箱内定义 新增 可调用；本体 funcs 未变")


def test_sandbox_diff_and_commit():
    """沙箱 diff() 检测变更；commit() 合并到本体。"""
    print("\n--- 沙箱: diff/commit ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    sb.run('func 新增A(x: Int) -> Int = (x) => x + 1')
    d = sb.diff()
    assert "新增A" in d["新函数"], d
    # commit 前本体无 新增A
    assert "新增A" not in i.funcs
    sb.commit()
    # commit 后本体有 新增A
    assert "新增A" in i.funcs
    assert i.call("新增A", 10) == 11
    # commit 后沙箱作废
    try:
        sb.run("func 再来(x: Int) -> Int = (x) => x")
        raise AssertionError("沙箱 commit 后应不可再用")
    except MathaRuntimeError:
        pass
    print("  ✓ diff 检出 新增A；commit 后本体可调用；沙箱作废")


def test_sandbox_rollback():
    """沙箱 rollback() 丢弃变更，本体不受影响。"""
    print("\n--- 沙箱: rollback ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    sb.run('func 丢弃(x: Int) -> Int = (x) => x + 1')
    sb.rollback()
    assert "丢弃" not in i.funcs
    # rollback 后沙箱作废
    try:
        sb.call("丢弃", 1)
        raise AssertionError("沙箱 rollback 后应不可再用")
    except MathaRuntimeError:
        pass
    print("  ✓ rollback 后本体无 丢弃；沙箱作废")


def test_sandbox_redef_function_detected():
    """沙箱覆写已有函数时，diff 的 改函数 检测到。"""
    print("\n--- 沙箱: 覆写检测 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x + 1')
    assert i.call("f", 1) == 2
    sb = i.sandbox()
    sb.run('func f(x: Int) -> Int = (x) => x + 100')
    d = sb.diff()
    assert "f" in d["改函数"], d
    assert sb.call("f", 1) == 101  # 沙箱内已覆写
    assert i.call("f", 1) == 2     # 本体仍是旧版
    sb.commit()
    assert i.call("f", 1) == 101   # commit 后本体用新版
    print("  ✓ 覆写 f 被 diff 检出；commit 后本体升级到新版")


def test_sandbox_runtime_error_captured():
    """沙箱 run() 捕获运行时错，error 为字符串；本体不受影响。"""
    print("\n--- 沙箱: 运行时错误捕获 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    outs, trace, err = sb.run('#1：[未定义量]')
    assert err is not None
    assert isinstance(err, str), type(err)
    assert "未定义" in err, err
    # 本体仍可用
    assert i.call("基础", 1) == 1
    print(f"  ✓ error 为 str 含 '未定义'；本体 基础(1)=1 仍可用")


def test_sandbox_parse_error_captured():
    """沙箱 run() 捕获语法错，error 含 ParseError。"""
    print("\n--- 沙箱: 语法错误捕获 ---")
    i = _interp_with('')
    sb = i.sandbox()
    outs, trace, err = sb.run('func 错(x: Int -> Int = (x) => x')
    assert err is not None
    assert "ParseError" in err or "Parse" in err, err
    print(f"  ✓ error 含 ParseError；错误前缀: {err[:40]}")


def test_sandbox_diff_vars_and_ctors():
    """沙箱 diff() 检测新变量、改变量、新构造子。"""
    print("\n--- 沙箱: diff 变量/构造子 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x\n@:a = 10')
    sb = i.sandbox()
    sb.run('#：{\n  b = 20\n  a = 99\n  [a]\n  [b]\n}\nenum 色 { 红 绿 }')
    d = sb.diff()
    assert d["新变量"] == {"b": 20}, d["新变量"]
    assert d["改变量"] == {"a": 99}, d["改变量"]
    assert set(d["新构造子"]) == {"红", "绿"}, d["新构造子"]
    assert d["新函数"] == [], d["新函数"]
    print("  ✓ 新变量={b:20}; 改变量={a:99}; 新构造子={红,绿}")


def test_sandbox_inherits_parent_functions():
    """沙箱继承本体函数，沙箱内可调用本体已注册函数。"""
    print("\n--- 沙箱: 继承本体函数 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x + 1')
    sb = i.sandbox()
    # 沙箱内直接调用本体函数
    assert sb.call("基础", 9) == 10
    # 沙箱内运行源码也可调用本体函数
    outs, _, err = sb.run('#：{ [基础(100)] }')
    assert err is None, err
    assert outs == [101], outs
    print("  ✓ 沙箱 call/源码 均可调用本体 基础")


def test_sandbox_empty_source_no_diff():
    """沙箱运行空源码，diff 全空，本体不变。"""
    print("\n--- 沙箱: 空源码无变更 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    outs, _, err = sb.run('')
    assert err is None, err
    assert outs == [], outs
    d = sb.diff()
    assert d == {
        "新函数": [], "改函数": [],
        "新变量": {}, "改变量": {}, "新构造子": [],
    }, d
    sb.rollback()
    print("  ✓ 空源码 → diff 全空；rollback 后本体不变")


def test_sandbox_call_after_dispose_raises():
    """沙箱 commit 后 call() 也应抛错（一次性语义全覆盖）。"""
    print("\n--- 沙箱: 作废后 call 抛错 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    sb.run('func g(x: Int) -> Int = (x) => x + 1')
    sb.commit()
    try:
        sb.call("g", 1)
        raise AssertionError("commit 后 call 应抛错")
    except MathaRuntimeError:
        pass
    # diff 也应抛
    try:
        sb.diff()
        raise AssertionError("commit 后 diff 应抛错")
    except MathaRuntimeError:
        pass
    print("  ✓ commit 后 call/diff 均抛 MathaRuntimeError")


# ============================================================
# 3) 升级 upgrade()
# ============================================================

def test_upgrade_success():
    """升级成功：新函数进入本体，返回 diff。"""
    print("\n--- 升级: 成功 ---")
    i = _interp_with('func 加一(x: Int) -> Int = (x) => x + 1')
    r = i.upgrade('func 立方(x: Int) -> Int = (x) => x * x * x')
    assert r.成功 is True, r.错误
    assert "立方" in r.变更["新函数"]
    assert i.call("立方", 3) == 27
    print("  ✓ 升级提交 立方；本体 立方(3)=27")


def test_upgrade_runtime_error_no_pollution():
    """升级源码运行时出错 → 失败回滚，本体不被污染。"""
    print("\n--- 升级: 运行时错误回滚 ---")
    i = _interp_with('func 加一(x: Int) -> Int = (x) => x + 1')
    r = i.upgrade('#1：[未定义量]')
    assert r.成功 is False
    assert "未定义" in (r.错误 or ""), r.错误
    assert "未定义量" not in i.env
    # 本体原有函数仍可用
    assert i.call("加一", 41) == 42
    print(f"  ✓ 运行时错回滚；本体 加一(41)=42 仍可用")


def test_upgrade_parse_error_no_pollution():
    """升级源码语法错 → 失败回滚。"""
    print("\n--- 升级: 语法错误回滚 ---")
    i = _interp_with('func 加一(x: Int) -> Int = (x) => x + 1')
    r = i.upgrade('func 错的(x: Int -> Int = (x) => x')  # 缺括号
    assert r.成功 is False
    assert r.错误 is not None
    assert "错的" not in i.funcs
    print(f"  ✓ 语法错回滚；错误前缀: {(r.错误 or '')[:30]}")


def test_upgrade_verify_pass():
    """verify 回调通过 → 提交。"""
    print("\n--- 升级: verify 通过 ---")
    i = _interp_with('')
    r = i.upgrade(
        'func 双倍(x: Int) -> Int = (x) => x * 2',
        verify=lambda sb: sb.call("双倍", 5) == 10,
    )
    assert r.成功 is True, r.错误
    assert i.call("双倍", 7) == 14
    print("  ✓ verify 校验 双倍(5)=10 通过；提交后 双倍(7)=14")


def test_upgrade_verify_rejects():
    """verify 回调返回 False → 不提交，本体无新函数。"""
    print("\n--- 升级: verify 拒绝 ---")
    i = _interp_with('')
    r = i.upgrade(
        'func 错误版(x: Int) -> Int = (x) => x + 1',
        verify=lambda sb: sb.call("错误版", 5) == 100,  # 故意不满足
    )
    assert r.成功 is False
    assert "校验" in (r.错误 or ""), r.错误
    assert "错误版" not in i.funcs
    print("  ✓ verify 返回 False → 不提交；本体无 错误版")


def test_upgrade_verify_exception_rolls_back():
    """verify 回调抛异常 → 回滚，错误信息含异常。"""
    print("\n--- 升级: verify 异常回滚 ---")
    i = _interp_with('')

    def bad_verify(sb):
        raise ValueError("校验器自身出错")

    r = i.upgrade('func 临时(x: Int) -> Int = (x) => x', verify=bad_verify)
    assert r.成功 is False
    assert "校验异常" in (r.错误 or ""), r.错误
    assert "临时" not in i.funcs
    print("  ✓ verify 抛异常 → 回滚；本体无 临时")


def test_upgrade_result_as_dict():
    """UpgradeResult.as_dict() 返回普通 dict。"""
    print("\n--- 升级: 结果字典 ---")
    i = _interp_with('')
    r = i.upgrade('func f(x: Int) -> Int = (x) => x')
    d = r.as_dict()
    assert d["成功"] is True
    assert "新函数" in d["变更"]
    print("  ✓ as_dict 含 成功/变更")


def test_upgrade_redefine_function():
    """升级覆写已有函数 → diff 归类为 改函数，本体用新版。"""
    print("\n--- 升级: 覆写已有函数 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x + 1')
    assert i.call("f", 1) == 2
    r = i.upgrade('func f(x: Int) -> Int = (x) => x + 100')
    assert r.成功 is True, r.错误
    assert "f" in r.变更["改函数"], r.变更
    assert "f" not in r.变更["新函数"], r.变更  # 不应算作新增
    assert i.call("f", 1) == 101
    print("  ✓ 覆写 f 归类改函数；本体 f(1)=101")


def test_upgrade_empty_source():
    """升级空源码 → 成功但无变更，本体不变。"""
    print("\n--- 升级: 空源码 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    r = i.upgrade('')
    assert r.成功 is True, r.错误
    assert r.变更 == {
        "新函数": [], "改函数": [],
        "新变量": {}, "改变量": {}, "新构造子": [],
    }, r.变更
    assert i.call("f", 5) == 5  # 本体不变
    print("  ✓ 空源码 成功无变更；本体 f(5)=5")


def test_upgrade_batch_functions():
    """升级批量定义多个函数 → 全部进入本体。"""
    print("\n--- 升级: 批量函数 ---")
    i = _interp_with('')
    src = (
        'func 加(x: Int) -> Int = (x) => x + 1\n'
        'func 减(x: Int) -> Int = (x) => x - 1\n'
        'func 乘(x: Int) -> Int = (x) => x * 2'
    )
    r = i.upgrade(src)
    assert r.成功 is True, r.错误
    assert set(r.变更["新函数"]) == {"加", "减", "乘"}, r.变更
    assert i.call("加", 1) == 2
    assert i.call("减", 5) == 4
    assert i.call("乘", 3) == 6
    print("  ✓ 批量 加/减/乘 全部提交；本体可调用")


def test_upgrade_with_outputs():
    """升级源码含输出 → outputs 回传到结果，不污染本体 outputs。"""
    print("\n--- 升级: 含输出 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    r = i.upgrade('#1：[42]\n#2：[f(5)]')
    assert r.成功 is True, r.错误
    assert r.输出 == [42, 5], r.输出
    # 本体 outputs 不应被沙箱输出污染
    assert i.outputs == [], i.outputs
    print("  ✓ 沙箱输出 [42, 5] 回传；本体 outputs 仍为空")


def test_upgrade_consecutive():
    """连续多次升级：每次在前次基础上叠加。"""
    print("\n--- 升级: 连续多次 ---")
    i = _interp_with('')
    r1 = i.upgrade('func a(x: Int) -> Int = (x) => x + 1')
    r2 = i.upgrade('func b(x: Int) -> Int = (x) => x + 2')
    r3 = i.upgrade('func c(x: Int) -> Int = (x) => x + 3')
    assert r1.成功 and r2.成功 and r3.成功
    assert i.call("a", 0) == 1
    assert i.call("b", 0) == 2
    assert i.call("c", 0) == 3
    # 探针确认三函数都在
    assert {"a", "b", "c"}.issubset(set(i.probe().func_names()))
    print("  ✓ 连续升级 a/b/c 全部可用")


def test_upgrade_failure_then_recovery():
    """升级失败后可再次升级成功（可恢复性）。"""
    print("\n--- 升级: 失败后恢复 ---")
    i = _interp_with('func g(x: Int) -> Int = (x) => x')
    rf = i.upgrade('#1：[未定义量]')
    assert rf.成功 is False
    # 本体未被污染，可继续升级
    rs = i.upgrade('func h(x: Int) -> Int = (x) => x + 1')
    assert rs.成功 is True, rs.错误
    assert i.call("h", 1) == 2
    assert i.call("g", 5) == 5  # 原有仍可用
    print("  ✓ 失败后可恢复；g/h 均可用")


def test_upgrade_probe_reflects_change():
    """升级后探针状态反映新函数。"""
    print("\n--- 升级: 探针反映变更 ---")
    i = _interp_with('func 原(x: Int) -> Int = (x) => x')
    before = i.probe().state()
    assert "新" not in before["函数"]
    i.upgrade('func 新(x: Int) -> Int = (x) => x + 1')
    after = i.probe().state()
    assert "新" in after["函数"], after
    assert "原" in after["函数"]
    # 函数数应增加
    assert len(after["函数"]) == len(before["函数"]) + 1
    print("  ✓ 升级前 无'新'；升级后 '新'出现，函数数 +1")


def test_upgrade_module_level_function():
    """模块级 upgrade() 函数直接调用（不通过 Interpreter 方法）。"""
    print("\n--- 升级: 模块级函数 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    r = upgrade(i, 'func g(x: Int) -> Int = (x) => x + 1')
    assert r.成功 is True, r.错误
    assert "g" in r.变更["新函数"]
    assert i.call("g", 9) == 10
    print("  ✓ upgrade(i, src) 模块级调用；g(9)=10")


def test_upgrade_verify_can_inspect_diff():
    """verify 回调可读取沙箱 diff 做更复杂校验。"""
    print("\n--- 升级: verify 检查 diff ---")
    i = _interp_with('')

    def verify_has_two_new(sb):
        d = sb.diff()
        return len(d["新函数"]) == 2  # 期望恰好两个新函数

    r = i.upgrade(
        'func 甲(x: Int) -> Int = (x) => x\n'
        'func 乙(x: Int) -> Int = (x) => x',
        verify=verify_has_two_new,
    )
    assert r.成功 is True, r.错误
    assert len(r.变更["新函数"]) == 2
    print("  ✓ verify 读取 diff 新函数数=2 通过")


# ============================================================
# 4) Matha 侧自升级内建
# ============================================================

def test_matha_builtin_upgrade():
    """Matha 代码调用 升级(...) 加载新函数并立即使用。"""
    print("\n--- Matha 内建: 升级 ---")
    src = r'''
func 加一(x: Int) -> Int = (x) => x + 1
#：{
  新函数 = 升级("func 翻倍(x: Int) -> Int = (x) => x * 2")
  [新函数]
  [翻倍(21)]
  [探针_已定义("翻倍")]
  [探针_已定义("加一")]
  函数表 = 探针_函数列表()
  [len(函数表)]
}
'''
    out, _ = interpret(src)
    assert out[0] == ["翻倍"], out        # 升级返回新函数名列表
    assert out[1] == 42, out              # 翻倍(21)
    assert out[2] is True                 # 探针_已定义("翻倍")
    assert out[3] is True                 # 探针_已定义("加一")
    assert out[4] == 2, out               # len(函数表) = 加一+翻倍
    print("  ✓ Matha 升级 翻倍；翻倍(21)=42；探针/函数列表 可用")


def test_matha_builtin_dry_run():
    """Matha 试运行(...) 返回 bool，不提交。"""
    print("\n--- Matha 内建: 试运行 ---")
    src = r'''
#：{
  好 = 试运行("func 临时(x: Int) -> Int = (x) => x + 1")
  坏 = 试运行("#1：[未定义量]")
  [好]
  [坏]
  [探针_已定义("临时")]
}
'''
    out, _ = interpret(src)
    assert out[0] is True, out            # 干净定义 → True
    assert out[1] is False, out           # 运行时错 → False
    assert out[2] is False, out           # 未提交 → 临时 未定义
    print("  ✓ 试运行 干净=T / 运行时错=F；未提交")


def test_matha_builtin_upgrade_failure_raises():
    """Matha 升级失败源码 → 抛 MathaRuntimeError，本体不污染。"""
    print("\n--- Matha 内建: 升级失败抛错 ---")
    src = r'''
func 根(x: Int) -> Int = (x) => x
#：{
  升级("#1：[未定义量]")
  [根(5)]
}
'''
    try:
        interpret(src)
        raised = False
    except MathaRuntimeError as ex:
        raised = True
        assert "升级失败" in str(ex), str(ex)
    assert raised, "升级失败应抛 MathaRuntimeError"
    print("  ✓ 升级失败抛 MathaRuntimeError（含 '升级失败'）")


def test_matha_nested_upgrade_in_sandbox():
    """沙箱内调用 升级 不影响本体（层间隔离）。"""
    print("\n--- Matha 内建: 沙箱内升级隔离 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    # Python 侧：用沙箱试运行一段「调用 升级」的 Matha 代码
    sb = i.sandbox()
    src = (
        '#：{\n'
        '  升级("func 沙箱内(x: Int) -> Int = (x) => x + 1")\n'
        '  [沙箱内(1)]\n'
        '}'
    )
    outs, _, err = sb.run(src)
    assert err is None, err
    assert outs == [2], outs
    # 沙箱内 升级 提交到了沙箱解释器，但本体不应有 沙箱内
    assert "沙箱内" not in i.funcs, "沙箱内升级泄漏到本体！"
    # 本体仍只有 基础
    assert i.call("基础", 5) == 5
    sb.rollback()
    print("  ✓ 沙箱内 升级 沙箱内(1)=2；本体未受影响")


def test_matha_builtin_probe_state():
    """Matha 探针_状态() 返回 dict（经 Python 侧校验类型与内容）。"""
    print("\n--- Matha 内建: 探针_状态 ---")
    i = _interp_with('func f(x: Int) -> Int = (x) => x')
    # Matha 侧无法直接输出 dict 字面量，改用 Python 侧调用内建验证返回类型
    st = i.call("探针_状态")
    assert isinstance(st, dict), type(st)
    assert "f" in st["函数"], st
    assert "升级" in st["内建"], st
    print(f"  ✓ 探针_状态() 返回 dict；函数={st['函数']} 内建含 升级")


def test_matha_builtin_dry_run_parse_error():
    """Matha 试运行 对语法错源码返回 False。"""
    print("\n--- Matha 内建: 试运行语法错 ---")
    src = r'''
#：{
  坏 = 试运行("func 错(x: Int -> Int = (x) => x")
  [坏]
  [探针_已定义("错")]
}
'''
    out, _ = interpret(src)
    assert out[0] is False, out       # 语法错 → False
    assert out[1] is False, out       # 未提交
    print("  ✓ 试运行 语法错 → False；未提交")


def test_matha_builtin_upgrade_returns_multiple_names():
    """Matha 升级 批量函数返回多元素函数名列表。"""
    print("\n--- Matha 内建: 升级批量返回 ---")
    src = r'''
#：{
  名表 = 升级("func 甲(x: Int) -> Int = (x) => x + 1
func 乙(x: Int) -> Int = (x) => x + 2")
  [len(名表)]
  [甲(1)]
  [乙(1)]
}
'''
    out, _ = interpret(src)
    assert out[0] == 2, out           # 两个新函数
    assert out[1] == 2, out           # 甲(1)
    assert out[2] == 3, out           # 乙(1)
    print("  ✓ 升级批量 → len(名表)=2；甲(1)=2 乙(1)=3")


def test_matha_builtin_dry_run_in_sandbox():
    """沙箱内调用 试运行 不提交到沙箱自身（双重隔离）。"""
    print("\n--- Matha 内建: 沙箱内试运行 ---")
    i = _interp_with('func 基础(x: Int) -> Int = (x) => x')
    sb = i.sandbox()
    src = (
        '#：{\n'
        '  好 = 试运行("func 临时(x: Int) -> Int = (x) => x + 1")\n'
        '  [好]\n'
        '  [探针_已定义("临时")]\n'
        '}'
    )
    outs, _, err = sb.run(src)
    assert err is None, err
    assert outs == [True, False], outs  # 试运行成功但不提交 → 临时未定义
    # 沙箱内也无 临时（试运行不提交）
    assert "临时" not in sb.interp.funcs
    sb.rollback()
    print("  ✓ 沙箱内 试运行 成功但不提交；临时 未定义")


# ============================================================
# runner
# ============================================================

def _run_all():
    tests = [
        # 探针
        test_probe_state,
        test_probe_has_and_func_info,
        test_probe_env_func_names_builtin_names,
        test_probe_has_constructor,
        # 沙箱
        test_sandbox_isolation,
        test_sandbox_diff_and_commit,
        test_sandbox_rollback,
        test_sandbox_redef_function_detected,
        test_sandbox_runtime_error_captured,
        test_sandbox_parse_error_captured,
        test_sandbox_diff_vars_and_ctors,
        test_sandbox_inherits_parent_functions,
        test_sandbox_empty_source_no_diff,
        test_sandbox_call_after_dispose_raises,
        # 升级
        test_upgrade_success,
        test_upgrade_runtime_error_no_pollution,
        test_upgrade_parse_error_no_pollution,
        test_upgrade_verify_pass,
        test_upgrade_verify_rejects,
        test_upgrade_verify_exception_rolls_back,
        test_upgrade_result_as_dict,
        test_upgrade_redefine_function,
        test_upgrade_empty_source,
        test_upgrade_batch_functions,
        test_upgrade_with_outputs,
        test_upgrade_consecutive,
        test_upgrade_failure_then_recovery,
        test_upgrade_probe_reflects_change,
        test_upgrade_module_level_function,
        test_upgrade_verify_can_inspect_diff,
        # Matha 自升级内建
        test_matha_builtin_upgrade,
        test_matha_builtin_dry_run,
        test_matha_builtin_upgrade_failure_raises,
        test_matha_nested_upgrade_in_sandbox,
        test_matha_builtin_probe_state,
        test_matha_builtin_dry_run_parse_error,
        test_matha_builtin_upgrade_returns_multiple_names,
        test_matha_builtin_dry_run_in_sandbox,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except (AssertionError, MathaRuntimeError, Exception) as ex:
            failed += 1
            print(f"  ✗ {t.__name__} 失败: {type(ex).__name__}: {ex}")
            import traceback
            traceback.print_exc()
    print(f"\n{'='*52}")
    print(f"自我升级测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
