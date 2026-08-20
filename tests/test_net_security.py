# -*- coding: utf-8 -*-
"""Matha 网络安全引擎测试套件"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.net_security import (
    NetSecurityEngine, ThreatSignature, ThreatLevel,
    NetworkThreat, MALICIOUS_PORTS, THREAT_SIGNATURES,
)
from src.interp import Interpreter, MathaRuntimeError


# ============================================================
# 单元测试
# ============================================================

def test_engine_init():
    """测试引擎初始化。"""
    print("\n=== 引擎初始化测试 ===")
    engine = NetSecurityEngine()
    assert len(engine.signatures) > 0, "应有默认威胁签名"
    assert len(MALICIOUS_PORTS) > 0, "应有恶意端口定义"
    print(f"  ✓ 引擎初始化: {len(engine.signatures)} 条签名, "
          f"{len(MALICIOUS_PORTS)} 个恶意端口")


def test_scan_threats():
    """测试威胁扫描。"""
    print("\n=== 威胁扫描测试 ===")
    engine = NetSecurityEngine()

    # 扫描可疑IP
    threats = engine.scan_threats(["192.168.1.100", "10.0.0.50", "8.8.8.8"])
    assert isinstance(threats, list), "威胁结果应为列表"
    print(f"  ✓ 扫描3个IP，发现 {len(threats)} 个威胁")

    # 验证威胁结构
    if threats:
        t = threats[0]
        assert "id" in t, "威胁应包含id"
        assert "name" in t, "威胁应包含name"
        assert "level" in t, "威胁应包含level"
        assert "risk_score" in t, "威胁应包含risk_score"
        print(f"  ✓ 威胁结构正确: {t['name']} [{t['level']}] 风险分{t['risk_score']}")


def test_detect_virus():
    """测试病毒检测。"""
    print("\n=== 病毒检测测试 ===")
    engine = NetSecurityEngine()

    # 检测勒索软件行为（匹配 encrypt.?file 模式）
    results = engine.detect_virus("encrypt file ransom note")
    assert len(results) > 0, "应检测到勒索软件签名"
    print(f"  ✓ 'encrypt file ransom note' 匹配 {len(results)} 条签名")

    # 检测反向Shell（匹配 reverse.?shell 模式）
    results = engine.detect_virus("reverse shell meterpreter")
    assert len(results) > 0, "应检测到反向Shell签名"
    print(f"  ✓ 'reverse shell meterpreter' 匹配 {len(results)} 条签名")

    # 检测C2通信（匹配 c2.?beacon 模式）
    results = engine.detect_virus("c2 beacon command control")
    assert len(results) > 0, "应检测到C2通信签名"
    print(f"  ✓ 'c2 beacon' 匹配 {len(results)} 条签名")

    # 无匹配
    results = engine.detect_virus("normal web browsing")
    print(f"  ✓ 'normal web browsing' 匹配 {len(results)} 条签名")


def test_quarantine_and_eliminate():
    """测试隔离与清杀。"""
    print("\n=== 隔离与清杀测试 ===")
    engine = NetSecurityEngine()

    # 先创建一些威胁
    engine.scan_threats(["192.168.1.100"])
    assert engine.threat_count() > 0, "应有威胁"
    print(f"  ✓ 扫描产生 {engine.threat_count()} 个威胁")

    # 获取威胁ID
    threat_id = list(engine._threats.keys())[0]

    # 隔离
    r = engine.quarantine(threat_id)
    assert r["success"], "隔离应成功"
    print(f"  ✓ 隔离威胁 {threat_id}")

    # 清杀
    r = engine.eliminate(threat_id)
    assert r["success"], "清杀应成功"
    print(f"  ✓ 清杀威胁 {threat_id}")

    # 验证状态
    status = engine.threat_status(threat_id)
    assert status["eliminated"] is True, "威胁应已被清杀"
    assert status["quarantined"] is True, "威胁应已被隔离"
    print(f"  ✓ 威胁状态: eliminated={status['eliminated']}, quarantined={status['quarantined']}")


def test_eliminate_all():
    """测试批量清杀。"""
    print("\n=== 批量清杀测试 ===")
    engine = NetSecurityEngine()

    # 创建多个威胁
    engine.scan_threats(["192.168.1.100", "10.0.0.50", "172.16.0.1"])
    total = engine.threat_count()
    assert total > 0, "应有威胁"

    # 批量清杀
    r = engine.eliminate_all()
    assert r["eliminated"] == total, f"应清杀全部 {total} 个威胁"
    print(f"  ✓ 批量清杀: {r['eliminated']}/{r['total']}")

    # 验证
    assert engine.threat_count() == total, "威胁数量不变（已清杀不计入减少）"
    assert engine.eliminated_count() == total, "所有威胁应被清杀"
    print(f"  ✓ 已清杀数量: {engine.eliminated_count()}")


def test_firewall_rules():
    """测试防火墙规则生成。"""
    print("\n=== 防火墙规则生成测试 ===")
    engine = NetSecurityEngine()

    # 创建威胁
    engine.scan_threats(["192.168.1.100", "10.0.0.50"])
    threats = engine.scan_threats(["192.168.1.100"])

    # 生成规则
    rules = engine.generate_firewall_rules(threats[:3])
    assert isinstance(rules, list), "规则应为列表"
    assert len(rules) > 0, "应生成至少1条规则"
    print(f"  ✓ 生成 {len(rules)} 条防火墙规则")

    # 验证规则结构
    for rule in rules:
        assert "action" in rule, "规则应有action"
        assert "source_ip" in rule, "规则应有source_ip"
        assert rule["action"] in ("deny", "monitor"), f"action应为deny或monitor, 实际{rule['action']}"
    print(f"  ✓ 规则结构正确: action={rules[0]['action']}, ip={rules[0]['source_ip']}")


def test_risk_assessment():
    """测试风险评估。"""
    print("\n=== 风险评估测试 ===")
    engine = NetSecurityEngine()

    # 扫描并评估
    engine.scan_threats(["192.168.1.100"])
    report = engine.assess_risk("192.168.1.100")
    assert "risk_score" in report, "评估结果应有risk_score"
    assert "level" in report, "评估结果应有level"
    print(f"  ✓ IP 192.168.1.100: 风险分={report['risk_score']}, 等级={report['level']}")

    # 干净IP
    report2 = engine.assess_risk("8.8.8.8")
    assert report2["threat_count"] == 0, "8.8.8.8 应无威胁"
    assert report2["level"] == "clean", "8.8.8.8 应为干净"
    print(f"  ✓ IP 8.8.8.8: 风险分={report2['risk_score']}, 等级={report2['level']}")


def test_risk_report():
    """测试风险报告。"""
    print("\n=== 风险报告测试 ===")
    engine = NetSecurityEngine()

    # 创建威胁
    engine.scan_threats(["192.168.1.100", "10.0.0.50"])

    report = engine.get_risk_report()
    assert "total_threats" in report, "报告应有total_threats"
    assert "by_level" in report, "报告应有by_level"
    assert "by_category" in report, "报告应有by_category"
    assert "avg_risk_score" in report, "报告应有avg_risk_score"
    print(f"  ✓ 风险报告: 总威胁={report['total_threats']}, "
          f"平均风险={report['avg_risk_score']}, "
          f"等级分布={report['by_level']}")


def test_signature_management():
    """测试签名管理。"""
    print("\n=== 签名管理测试 ===")
    engine = NetSecurityEngine()

    # 列出签名
    sigs = engine.list_signatures()
    assert len(sigs) > 0, "应有默认签名"
    print(f"  ✓ 当前签名数: {len(sigs)}")

    # 添加签名
    ok = engine.add_signature(
        "测试病毒", "test.?virus", "high", "病毒",
        "测试用的威胁签名"
    )
    assert ok is True, "添加签名应成功"
    print(f"  ✓ 添加自定义签名成功")

    # 验证添加
    sigs2 = engine.list_signatures()
    assert len(sigs2) == len(sigs) + 1, "签名数应+1"
    print(f"  ✓ 签名数: {len(sigs)} → {len(sigs2)}")

    # 移除签名
    ok = engine.remove_signature("测试病毒")
    assert ok is True, "移除签名应成功"
    sigs3 = engine.list_signatures()
    assert len(sigs3) == len(sigs), "签名数应恢复"
    print(f"  ✓ 移除自定义签名成功")

    # 重复添加应失败
    ok2 = engine.add_signature(
        "测试病毒", "test.?virus", "high", "病毒", "测试"
    )
    # 先添加
    engine.add_signature("重复测试", "dup.?test", "low", "测试", "测试重复")
    ok3 = engine.add_signature("重复测试", "dup.?test", "low", "测试", "测试重复")
    assert ok3 is False, "重复添加应失败"
    print(f"  ✓ 重复添加签名被拒绝")


def test_threat_report():
    """测试威胁详情报告。"""
    print("\n=== 威胁详情报告测试 ===")
    engine = NetSecurityEngine()
    engine.scan_threats(["192.168.1.100"])

    threat_id = list(engine._threats.keys())[0]
    report = engine.get_threat_report(threat_id)
    assert report is not None, "应返回威胁报告"
    assert report["id"] == threat_id, "报告ID应匹配"
    assert "name" in report, "报告应有name"
    print(f"  ✓ 威胁报告: {report['name']} [{report['level']}]")

    # 不存在的威胁
    report2 = engine.get_threat_report("NONEXISTENT")
    assert "error" in report2, "应返回错误"
    print(f"  ✓ 不存在的威胁返回错误: {report2['error']}")


def test_malicious_ports():
    """测试恶意端口库。"""
    print("\n=== 恶意端口测试 ===")
    assert 4444 in MALICIOUS_PORTS, "4444应为恶意端口"
    assert 31337 in MALICIOUS_PORTS, "31337应为恶意端口"
    assert "Metasploit" in MALICIOUS_PORTS[4444], "4444端口描述应含Metasploit"
    print(f"  ✓ 恶意端口库: {len(MALICIOUS_PORTS)} 个端口")
    print(f"    示例: 4444={MALICIOUS_PORTS[4444]}")
    print(f"    示例: 31337={MALICIOUS_PORTS[31337]}")


def test_threat_signatures():
    """测试威胁签名库。"""
    print("\n=== 威胁签名库测试 ===")
    assert len(THREAT_SIGNATURES) > 0, "应有默认签名"
    categories = set(s.category for s in THREAT_SIGNATURES)
    print(f"  ✓ 威胁签名数: {len(THREAT_SIGNATURES)}")
    print(f"    分类: {categories}")

    # 检查签名结构
    for sig in THREAT_SIGNATURES:
        assert hasattr(sig, 'name'), "签名应有name"
        assert hasattr(sig, 'pattern'), "签名应有pattern"
        assert hasattr(sig, 'level'), "签名应有level"
        assert isinstance(sig.level, ThreatLevel), "level应为ThreatLevel枚举"
    print(f"  ✓ 所有签名结构正确")


def test_interpreter_integration():
    """测试与解释器的集成。"""
    print("\n=== 解释器集成测试 ===")
    interp = Interpreter()

    # 验证内建函数已注册
    net_builtins = [k for k in interp.builtins if k.startswith("威胁") or
                    k.startswith("检测") or k.startswith("隔离") or
                    k.startswith("清杀") or k.startswith("生成") or
                    k.startswith("风险") or k.startswith("防火墙") or
                    k.startswith("添加") or k.startswith("列出") or
                    k.startswith("已清杀")]
    assert len(net_builtins) >= 10, f"应注册至少10个网络安全内建，实际{len(net_builtins)}"
    print(f"  ✓ 注册网络安全内建: {len(net_builtins)} 个")
    print(f"    示例: {net_builtins[:5]}")


def test_end_to_end():
    """端到端测试：扫描 → 评估 → 隔离 → 清杀 → 生成规则。"""
    print("\n=== 端到端测试 ===")
    engine = NetSecurityEngine()

    # 1. 扫描威胁
    threats = engine.scan_threats(["192.168.1.100", "10.0.0.50", "8.8.8.8"])
    print(f"  1. 扫描: 发现 {len(threats)} 个威胁")
    assert len(threats) > 0, "应发现威胁"

    # 2. 风险评估
    report = engine.get_risk_report()
    print(f"  2. 风险报告: 总威胁={report['total_threats']}, 平均风险={report['avg_risk_score']}")

    # 3. 隔离高威胁
    high_threats = [t for t in threats if t.get('level') in ('high', 'critical')]
    for t in high_threats[:2]:
        q = engine.quarantine(t['id'])
        print(f"  3. 隔离: {t['name']} → {'成功' if q['success'] else '失败'}")

    # 4. 生成防火墙规则
    rules = engine.generate_firewall_rules(threats[:3])
    print(f"  4. 防火墙规则: 生成 {len(rules)} 条")
    assert len(rules) > 0, "应生成规则"

    # 5. 清杀所有威胁
    clear = engine.eliminate_all()
    print(f"  5. 清杀: {clear['eliminated']}/{clear['total']}")
    assert clear['eliminated'] > 0, "应有威胁被清杀"

    # 6. 最终报告
    final = engine.get_risk_report()
    print(f"  6. 最终报告: 已清杀={final['eliminated']}, 规则数={final['firewall_rules']}")

    print("  ✓ 端到端流程完成")


def main():
    test_engine_init()
    test_scan_threats()
    test_detect_virus()
    test_quarantine_and_eliminate()
    test_eliminate_all()
    test_firewall_rules()
    test_risk_assessment()
    test_risk_report()
    test_signature_management()
    test_threat_report()
    test_malicious_ports()
    test_threat_signatures()
    test_interpreter_integration()
    test_end_to_end()

    print("\n" + "=" * 50)
    print("  网络安全测试全部完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
