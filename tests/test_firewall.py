# -*- coding: utf-8 -*-
"""Matha 防火墙测试套件"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.firewall import (
    MathaFirewall, FirewallLevel, FirewallPolicy, FirewallRule,
    MathaFirewallException, sandbox_interpret, restricted_interpret, full_interpret,
)
from src.interp import Interpreter, MathaRuntimeError


# ============================================================
# 单元测试
# ============================================================

def test_firewall_level_enum():
    """测试权限级别枚举。"""
    print("\n=== 权限级别测试 ===")
    assert FirewallLevel.沙箱.value == "sandbox"
    assert FirewallLevel.受限.value == "restricted"
    assert FirewallLevel.全功能.value == "full"
    print("  ✓ 三个级别定义正确")


def test_firewall_policy():
    """测试防火墙策略。"""
    print("\n=== 策略测试 ===")
    policy = FirewallPolicy(FirewallLevel.沙箱)

    # 默认拦截
    blocked, reason = policy.is_blocked("读文件")
    assert blocked, "读文件 应被沙箱拦截"
    print(f"  ✓ 读文件 被拦截: {reason}")

    blocked, reason = policy.is_blocked("外部求值")
    assert blocked, "外部求值 应被沙箱拦截"
    print(f"  ✓ 外部求值 被拦截")

    # 纯计算不应被拦截
    blocked, reason = policy.is_blocked("阶乘")
    assert not blocked, "阶乘 不应被拦截"
    print(f"  ✓ 阶乘 允许")

    blocked, reason = policy.is_blocked("平均值")
    assert not blocked, "平均值 不应被拦截"
    print(f"  ✓ 平均值 允许")

    # 受限模式
    policy_restricted = FirewallPolicy(FirewallLevel.受限)
    blocked, _ = policy_restricted.is_blocked("探针_状态")
    assert not blocked, "探针_状态 在受限模式应允许"
    print(f"  ✓ 受限模式: 探针_状态 允许")

    # 全功能模式
    policy_full = FirewallPolicy(FirewallLevel.全功能)
    blocked, _ = policy_full.is_blocked("读文件")
    assert not blocked, "读文件 在全功能模式应允许"
    print(f"  ✓ 全功能模式: 读文件 允许")

    # 自定义规则
    policy2 = FirewallPolicy(FirewallLevel.沙箱)
    policy2.deny("阶乘", "自定义禁止")
    blocked, _ = policy2.is_blocked("阶乘")
    assert blocked, "自定义 deny 应生效"
    print(f"  ✓ 自定义 deny 规则生效")

    policy2.allow("阶乘", "自定义允许")
    blocked, _ = policy2.is_blocked("阶乘")
    assert not blocked, "allow 应覆盖 deny"
    print(f"  ✓ 自定义 allow 规则覆盖 deny")


def test_firewall_exception():
    """测试防火墙异常。"""
    print("\n=== 异常测试 ===")
    exc = MathaFirewallException("读文件", "sandbox", "文件读取会导致隐私泄露")
    assert exc.builtin_name == "读文件"
    assert exc.level == "sandbox"
    assert "读文件" in str(exc)
    assert "隐私泄露" in str(exc)
    print(f"  ✓ MathaFirewallException 包含完整信息")


def test_sandbox_execution():
    """测试沙箱模式下的执行。"""
    print("\n=== 沙箱执行测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)

    # 允许的纯计算
    r = fw.run_interactive("#1：[3 + 5]")
    assert r["success"], f"3+5 应成功: {r}"
    assert 8.0 in r["outputs"], f"期望 8.0 在输出中，实际 {r['outputs']}"
    print(f"  ✓ 3+5 = {r['outputs']}")

    fw.reset()
    r = fw.run_interactive("#1：[阶乘(5)]")
    assert r["success"], f"阶乘(5) 应成功: {r}"
    assert 120 in r["outputs"], f"期望 120 在输出中，实际 {r['outputs']}"
    print(f"  ✓ 阶乘(5) = {r['outputs']}")

    fw.reset()
    r = fw.run_interactive("#1：[平均值([1,2,3,4,5])]")
    assert r["success"], f"平均值 应成功: {r}"
    assert 3.0 in r["outputs"], f"期望 3.0 在输出中，实际 {r['outputs']}"
    print(f"  ✓ 平均值([1,2,3,4,5]) = {r['outputs']}")

    fw.reset()
    r = fw.run_interactive("#1：[素数筛(20)]")
    assert r["success"], f"素数筛 应成功: {r}"
    print(f"  ✓ 素数筛(20) = {r['outputs']}")


def test_sandbox_blocks():
    """测试沙箱拦截危险操作。"""
    print("\n=== 沙箱拦截测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)

    # 拦截文件读取（Matha 字符串用双引号）
    r = fw.run_interactive('#1：[读文件("test.txt")]')
    assert not r["success"], "读文件 应被拦截"
    assert "防火墙" in r["error"], "错误信息应包含防火墙提示"
    print(f"  ✓ 读文件 被拦截: {r['error'][:50]}...")

    # 拦截文件写入
    r = fw.run_interactive('#1：[写文件("out.txt", "hello")]')
    assert not r["success"], "写文件 应被拦截"
    print(f"  ✓ 写文件 被拦截")

    # 拦截外部求值
    r = fw.run_interactive('#1：[外部求值("python", "import os")]')
    assert not r["success"], "外部求值 应被拦截"
    print(f"  ✓ 外部求值 被拦截")

    # 拦截自升级
    r = fw.run_interactive('#1：[升级("#1：[1]")]')
    assert not r["success"], "升级 应被拦截"
    print(f"  ✓ 升级 被拦截")

    # 拦截代码生成
    r = fw.run_interactive('#1：[生成_网页("test")]')
    assert not r["success"], "生成_网页 应被拦截"
    print(f"  ✓ 生成_网页 被拦截")

    print(f"  拦截统计: {fw._blocked_count} 次拦截 / {fw._call_count} 次调用")


def test_full_mode():
    """测试全功能模式不拦截。"""
    print("\n=== 全功能模式测试 ===")
    fw = MathaFirewall(FirewallLevel.全功能)

    # 全功能模式下文件操作应允许（解释器会执行）
    # 注意：这需要测试文件存在，这里只测试拦截逻辑
    policy = fw.policy
    blocked, _ = policy.is_blocked("读文件")
    assert not blocked, "全功能模式下读文件 不应被拦截"
    print(f"  ✓ 全功能模式: 读文件 允许")

    blocked, _ = policy.is_blocked("外部求值")
    assert not blocked, "全功能模式下外部求值 不应被拦截"
    print(f"  ✓ 全功能模式: 外部求值 允许")


def test_status_and_history():
    """测试状态和历史记录。"""
    print("\n=== 状态测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)

    # 初始状态
    status = fw.get_status()
    assert status["level"] == "sandbox"
    assert status["blocked_count"] == 0
    assert status["total_calls"] == 0
    print(f"  ✓ 初始状态正确")

    # 执行后
    fw.run_interactive("#1：[3 + 5]")
    status = fw.get_status()
    assert status["total_calls"] == 1
    assert status["blocked_count"] == 0
    print(f"  ✓ 执行后状态正确")

    # 拦截后（用双引号确保解析为函数调用）
    fw.run_interactive('#1：[读文件("x")]')
    status = fw.get_status()
    assert status["blocked_count"] == 1
    print(f"  ✓ 拦截后状态正确")
    print(f"  历史记录: {status['recent_history']}")


def test_reset():
    """测试重置。"""
    print("\n=== 重置测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)
    fw.run_interactive("#1：[3 + 5]")
    fw.run_interactive('#1：[读文件("x")]')
    assert fw._call_count == 2
    assert fw._blocked_count >= 1  # 至少1次拦截

    fw.reset()
    assert fw._call_count == 0
    assert fw._blocked_count == 0
    assert fw._history == []
    print(f"  ✓ 重置后统计归零")


def test_level_switching():
    """测试级别切换。"""
    print("\n=== 级别切换测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)

    # 沙箱模式拦截读文件（用双引号确保解析为函数调用）
    r = fw.run_interactive('#1：[读文件("x")]')
    assert not r["success"], "沙箱模式应拦截读文件"

    # 切换到全功能
    fw.set_level(FirewallLevel.全功能)
    # 此时读文件不应再被拦截
    policy = fw.policy
    blocked, _ = policy.is_blocked("读文件")
    assert not blocked
    print(f"  ✓ 切换到全功能后读文件允许")

    # 切回沙箱
    fw.set_level(FirewallLevel.沙箱)
    blocked, _ = fw.policy.is_blocked("读文件")
    assert blocked
    print(f"  ✓ 切回沙箱后读文件拦截")


def test_builtins_list():
    """测试被拦截的 builtin 列表。"""
    print("\n=== 拦截列表测试 ===")
    fw = MathaFirewall(FirewallLevel.沙箱)
    blocked = fw.policy.list_blocked()
    assert "读文件" in blocked
    assert "写文件" in blocked
    assert "外部求值" in blocked
    assert "阶乘" not in blocked
    assert "平均值" not in blocked
    print(f"  ✓ 拦截列表正确 (共 {len(blocked)} 项)")
    print(f"    示例: {blocked[:5]}")


def test_matha_rule_file():
    """测试 Matha 规则文件加载。"""
    print("\n=== Matha 规则文件测试 ===")
    rule_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "matha", "firewall_rules.matha")
    if os.path.exists(rule_file):
        with open(rule_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "防火墙_级别" in content
        assert "沙箱拦截列表" in content
        print(f"  ✓ Matha 规则文件存在且格式正确")
    else:
        print(f"  ○ 规则文件不存在（非致命）")


def test_convenience_functions():
    """测试便捷函数。"""
    print("\n=== 便捷函数测试 ===")

    # sandbox_interpret
    outputs, trace = sandbox_interpret("#1：[2 * 3]")
    assert outputs == [6.0], f"期望 [6.0]，实际 {outputs}"
    print(f"  ✓ sandbox_interpret: 2*3 = {outputs}")

    # 沙箱中拦截文件操作（用双引号确保解析为函数调用）
    try:
        sandbox_interpret('#1：[读文件("x")]')
        assert False, "应抛出异常"
    except MathaFirewallException:
        print(f"  ✓ sandbox_interpret 正确拦截文件操作")


def test_math_operation_sandbox():
    """测试沙箱中各种数学运算。"""
    print("\n=== 沙箱数学运算测试 ===")
    tests = [
        ("#1：[3 + 5]", [8.0]),
        ("#1：[10 - 3]", [7.0]),
        ("#1：[4 * 5]", [20.0]),
        ("#1：[15 / 3]", [5.0]),
        ("#1：[2 ^ 8]", [256.0]),
        ("#1：[阶乘(6)]", [720]),
        ("#1：[sqrt(144)]", [12.0]),
        ("#1：[abs(-7)]", [7.0]),
        ("#1：[平均值([10,20,30])]", [20.0]),
        ("#1：[max([1,5,3])]", [5.0]),
        ("#1：[min([1,5,3])]", [1.0]),
    ]

    passed = 0
    for code, expected in tests:
        fw = MathaFirewall(FirewallLevel.沙箱)
        r = fw.run_interactive(code)
        if r["success"] and expected[0] in r["outputs"]:
            passed += 1
        else:
            print(f"  ✗ {code} → {r.get('outputs')} (期望 {expected})")

    print(f"  ✓ {passed}/{len(tests)} 数学运算通过")


def main():
    test_firewall_level_enum()
    test_firewall_policy()
    test_firewall_exception()
    test_sandbox_execution()
    test_sandbox_blocks()
    test_full_mode()
    test_status_and_history()
    test_reset()
    test_level_switching()
    test_builtins_list()
    test_matha_rule_file()
    test_convenience_functions()
    test_math_operation_sandbox()

    print("\n" + "=" * 50)
    print("  防火墙测试全部完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
