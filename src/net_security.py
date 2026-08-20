# -*- coding: utf-8 -*-
"""
Matha 网络安全引擎 — 威胁检测 · 漏洞扫描 · 病毒清杀 · 防火墙管理

设计原则：
  1. 用数学和逻辑方法建模网络安全问题
  2. 支持威胁签名匹配和风险评分
  3. 可检测、隔离、清杀网络威胁
  4. 生成防御规则并与防火墙联动
  5. 所有操作可审计、可追溯

架构：
  ThreatSignature   — 威胁签名定义（模式 + 风险等级）
  NetworkThreat     — 网络威胁对象（IP/端口/行为/风险分）
  VirusSimulator    — 病毒行为模拟器（用于安全测试）
  NetSecurityEngine — 网络安全引擎主类
  内建函数注册：病毒检测、漏洞扫描、威胁清杀、防火墙联动

用法：
    from src.net_security import NetSecurityEngine

    engine = NetSecurityEngine()

    # 检测威胁
    threats = engine.scan_threats(["192.168.1.100", "10.0.0.50"])

    # 清杀病毒
    result = engine.quarantine("THREAT_001")

    # 生成防火墙规则
    rules = engine.generate_firewall_rules(threats)
"""
from __future__ import annotations
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("matha.net_security")


# ============================================================
# 威胁签名数据库
# ============================================================

class ThreatLevel(str, Enum):
    """威胁等级。"""
    低风险 = "low"
    中风险 = "medium"
    高风险 = "high"
    严重 = "critical"


@dataclass
class ThreatSignature:
    """威胁签名 — 匹配模式 + 风险等级 + 描述。"""
    name: str                          # 签名名称
    pattern: str                       # 匹配正则（威胁特征）
    level: ThreatLevel                 # 风险等级
    category: str                      # 分类（病毒/蠕虫/特洛伊/勒索软件/后门）
    description: str                   # 威胁描述
    mitigation: str = ""              # 清杀建议
    cve_ids: list[str] = field(default_factory=list)  # CVE 编号


# 内置威胁签名库（安全研究用）
THREAT_SIGNATURES: list[ThreatSignature] = [
    # ── 网络蠕虫类 ──────────────────────────────────────
    ThreatSignature(
        name="网络蠕虫_端口扫描",
        pattern=r"port.?scan|SYN.?flood|nmap|masscan",
        level=ThreatLevel.高风险,
        category="蠕虫",
        description="检测到端口扫描行为，可能为入侵前兆",
        mitigation="阻断源IP，检查防火墙规则",
    ),
    ThreatSignature(
        name="网络蠕虫_自传播",
        pattern=r"self.?replicate|worm.?propagate|peer.?to.?peer.?spread",
        level=ThreatLevel.严重,
        category="蠕虫",
        description="检测到蠕虫自传播行为",
        mitigation="立即隔离感染主机，阻断网络传播路径",
    ),
    # ── 勒索软件类 ──────────────────────────────────────
    ThreatSignature(
        name="勒索软件_文件加密",
        pattern=r"encrypt.?file|ransom.?note|\.locked|\.encrypted",
        level=ThreatLevel.严重,
        category="勒索软件",
        description="检测到文件加密行为，疑似勒索软件",
        mitigation="断网隔离，备份恢复，分析加密算法",
    ),
    ThreatSignature(
        name="勒索软件_比特币勒索",
        pattern=r"bitcoin|crypto.?wallet|ransom.?payment|decrypt.?key",
        level=ThreatLevel.严重,
        category="勒索软件",
        description="检测到加密货币勒索通信",
        mitigation="阻断支付通道，报告安全事件",
    ),
    # ── 特洛伊木马类 ────────────────────────────────────
    ThreatSignature(
        name="特洛伊_反向shell",
        pattern=r"reverse.?shell|meterpreter|bind.?shell",
        level=ThreatLevel.严重,
        category="特洛伊",
        description="检测到反向Shell连接，攻击者可能已入侵",
        mitigation="阻断外联，分析入侵路径，重置凭据",
    ),
    ThreatSignature(
        name="特洛伊_远程控制",
        pattern=r"remote.?access|backdoor|rat\.exe|c2.?channel",
        level=ThreatLevel.高风险,
        category="特洛伊",
        description="检测到远程控制通信，疑似后门程序",
        mitigation="阻断C2通信，清杀恶意进程",
    ),
    # ── 数据泄露类 ──────────────────────────────────────
    ThreatSignature(
        name="数据泄露_外传敏感数据",
        pattern=r"exfil|data.?theft|credential.?dump|hash.?dump",
        level=ThreatLevel.高风险,
        category="间谍软件",
        description="检测到敏感数据外传行为",
        mitigation="阻断出站连接，审计数据访问日志",
    ),
    ThreatSignature(
        name="数据泄露_密钥窃取",
        pattern=r"ssh.?key|private.?key|\.pem|\.p12|credential.?harvest",
        level=ThreatLevel.严重,
        category="间谍软件",
        description="检测到私钥或凭证窃取行为",
        mitigation="轮换所有密钥和凭证，审计访问权限",
    ),
    # ── 拒绝服务类 ──────────────────────────────────────
    ThreatSignature(
        name="DoS_洪水攻击",
        pattern=r"ddos|syn.?flood|udp.?flood|amplification.?attack",
        level=ThreatLevel.高风险,
        category="DoS",
        description="检测到DDoS攻击特征",
        mitigation="启用流量清洗，联系ISP",
    ),
    # ── 恶意网络行为类 ──────────────────────────────────
    ThreatSignature(
        name="恶意网络_C2通信",
        pattern=r"c2.?beacon|command.?control|dns.?tunnel|covert.?channel",
        level=ThreatLevel.严重,
        category="APT",
        description="检测到C2隐蔽通信信道",
        mitigation="阻断DNS隧道，隔离主机，取证分析",
    ),
    ThreatSignature(
        name="恶意网络_异常外联",
        pattern=r"unknown.?outbound|suspicious.?connection|tor.?node|proxy.?hop",
        level=ThreatLevel.中风险,
        category=" suspicious",
        description="检测到可疑外联行为",
        mitigation="检查出站连接，阻断可疑目标",
    ),
]

# 端口威胁库（常见恶意端口）
MALICIOUS_PORTS: dict[int, str] = {
    4444: "Metasploit默认反弹Shell端口",
    5555: "Android调试桥滥用端口",
    6667: "IRC（常用于C2通信）",
    31337: "Back Orifice特洛伊木马端口",
    12345: "NetBus特洛伊木马端口",
    27374: "SubSeven特洛伊木马端口",
    1234: "常见DDoS工具端口",
    2000: "Back Orifice旧版端口",
    65535: "异常高位端口扫描",
}

# 已知恶意IP段（模拟数据，实际应使用威胁情报）
SUSPICIOUS_IP_RANGES: list[tuple[str, str]] = [
    ("10.0.0.0", "10.0.0.255", "内网扫描常见源"),
    ("192.168.255.0", "192.168.255.255", "异常广播段"),
]


# ============================================================
# 网络威胁对象
# ============================================================

@dataclass
class NetworkThreat:
    """网络威胁实例。"""
    threat_id: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    threat_name: str
    threat_level: ThreatLevel
    category: str
    matched_pattern: str
    risk_score: float          # 0.0 ~ 10.0
    detected_at: float = field(default_factory=time.time)
    quarantined: bool = False
    eliminated: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.threat_id,
            "source": f"{self.source_ip}:{self.source_port}",
            "target": f"{self.destination_ip}:{self.destination_port}",
            "name": self.threat_name,
            "level": self.threat_level.value,
            "category": self.category,
            "risk_score": round(self.risk_score, 2),
            "matched": self.matched_pattern,
            "quarantined": self.quarantined,
            "eliminated": self.eliminated,
        }


# ============================================================
# 网络安全引擎
# ============================================================

class NetSecurityEngine:
    """
    网络安全引擎 — 威胁检测 · 漏洞扫描 · 病毒清杀 · 防火墙联动。

    功能：
      - scan_threats()        扫描网络威胁
      - detect_virus()        检测已知病毒特征
      - quarantine()          隔离威胁源
      - eliminate()           清杀威胁
      - generate_fw_rules()   生成防火墙规则
      - assess_risk()         风险评估
      - get_threat_report()   生成威胁报告
    """

    def __init__(self, signatures: Optional[list[ThreatSignature]] = None):
        self.signatures = signatures or list(THREAT_SIGNATURES)
        self._threats: dict[str, NetworkThreat] = {}
        self._quarantine_log: list[dict] = []
        self._elimination_log: list[dict] = []
        self._firewall_rules: list[dict] = []
        logger.info(f"网络安全引擎初始化: {len(self.signatures)} 条签名, "
                     f"{len(MALICIOUS_PORTS)} 个恶意端口")

    # ── 威胁检测 ─────────────────────────────────────────

    def scan_threats(self, source_ips: list[str],
                     dest_ip: str = "127.0.0.1",
                     dest_port: int = 80) -> list[dict]:
        """
        扫描指定IP的威胁，返回威胁列表。

        source_ips: 待扫描的源IP列表
        dest_ip: 目标IP
        dest_port: 目标端口

        返回: 威胁字典列表
        """
        threats = []
        for src_ip in source_ips:
            # 1. 端口威胁检测
            for port, desc in MALICIOUS_PORTS.items():
                if self._is_suspicious_port(port):
                    threat = self._create_threat(
                        src_ip, dest_ip, port,
                        "恶意端口_" + str(port),
                        ThreatLevel.中风险,
                        "端口扫描",
                        f"端口{port}: {desc}",
                        risk_score=5.0,
                    )
                    threats.append(threat.to_dict())

            # 2. 签名匹配（模拟行为分析）
            for sig in self.signatures:
                if re.search(sig.pattern, src_ip.lower(), re.IGNORECASE):
                    threat = self._create_threat(
                        src_ip, dest_ip, dest_port,
                        sig.name, sig.level, sig.category,
                        sig.description,
                        matched_pattern=sig.pattern,
                        mitigation=sig.mitigation,
                        risk_score=self._calc_risk(sig.level),
                    )
                    threats.append(threat.to_dict())

            # 3. IP信誉检查
            reputation = self._check_ip_reputation(src_ip)
            if reputation["score"] < 3.0:
                threat = self._create_threat(
                    src_ip, dest_ip, dest_port,
                    "低信誉IP",
                    ThreatLevel.中风险,
                    "可疑网络",
                    f"IP信誉分 {reputation['score']}/10，可能为恶意节点",
                    risk_score=10.0 - reputation["score"],
                )
                threats.append(threat.to_dict())

        logger.info(f"扫描完成: 输入 {len(source_ips)} 个IP, 发现 {len(threats)} 个威胁")
        return threats

    def detect_virus(self, behavior_pattern: str) -> list[dict]:
        """
        根据行为模式检测潜在病毒。

        behavior_pattern: 可疑行为描述（如 "文件加密"、"反弹shell"）

        返回: 匹配的威胁列表
        """
        matches = []
        pattern_lower = behavior_pattern.lower()
        for sig in self.signatures:
            if re.search(sig.pattern, pattern_lower, re.IGNORECASE):
                matches.append({
                    "signature": sig.name,
                    "level": sig.level.value,
                    "category": sig.category,
                    "description": sig.description,
                    "mitigation": sig.mitigation,
                    "risk_score": self._calc_risk(sig.level),
                })
        logger.info(f"病毒检测: 模式'{behavior_pattern}'匹配 {len(matches)} 条签名")
        return matches

    # ── 威胁隔离与清杀 ───────────────────────────────────

    def quarantine(self, threat_id: str) -> dict:
        """隔离指定威胁。"""
        if threat_id not in self._threats:
            return {"success": False, "error": f"威胁 {threat_id} 不存在"}
        threat = self._threats[threat_id]
        threat.quarantined = True
        entry = {
            "id": threat_id,
            "action": "quarantine",
            "threat": threat.threat_name,
            "source": f"{threat.source_ip}:{threat.source_port}",
            "timestamp": time.time(),
        }
        self._quarantine_log.append(entry)
        logger.info(f"🔒 隔离威胁: {threat_id} ({threat.threat_name})")
        return {"success": True, **entry}

    def eliminate(self, threat_id: str) -> dict:
        """清杀指定威胁。"""
        if threat_id not in self._threats:
            return {"success": False, "error": f"威胁 {threat_id} 不存在"}
        threat = self._threats[threat_id]
        threat.quarantined = True
        threat.eliminated = True
        entry = {
            "id": threat_id,
            "action": "eliminate",
            "threat": threat.threat_name,
            "source": f"{threat.source_ip}:{threat.source_port}",
            "timestamp": time.time(),
        }
        self._elimination_log.append(entry)
        logger.info(f"🛡️ 清杀威胁: {threat_id} ({threat.threat_name})")
        return {"success": True, **entry}

    def eliminate_all(self, level: Optional[str] = None) -> dict:
        """批量清杀威胁。"""
        results = []
        target_ids = list(self._threats.keys())
        if level:
            target_ids = [tid for tid, t in self._threats.items()
                          if t.threat_level.value == level]
        for tid in target_ids:
            result = self.eliminate(tid)
            if result["success"]:
                results.append(result)
        logger.info(f"批量清杀: {len(results)}/{len(target_ids)} 个威胁已清杀")
        return {"eliminated": len(results), "total": len(target_ids), "results": results}

    # ── 防火墙规则生成 ───────────────────────────────────

    def generate_firewall_rules(self, threats: Optional[list[dict]] = None) -> list[dict]:
        """
        根据威胁列表生成防火墙规则。

        返回: 规则列表，每条包含动作、源IP、目标端口、描述
        """
        if threats is None:
            threats = [t.to_dict() for t in self._threats.values()]

        rules = []
        seen_ips = set()
        for t in threats:
            src = t.get("source", "")
            src_ip = src.split(":")[0] if src else ""
            if src_ip and src_ip not in seen_ips and self._is_valid_ip(src_ip):
                level = t.get("level", "medium")
                action = "deny" if level in ("high", "critical") else "monitor"
                rule = {
                    "action": action,
                    "source_ip": src_ip,
                    "threat": t.get("name", ""),
                    "level": level,
                    "description": f"阻断 {t.get('name', 'unknown')} 威胁源",
                }
                rules.append(rule)
                seen_ips.add(src_ip)
                self._firewall_rules.append(rule)

        logger.info(f"生成防火墙规则: {len(rules)} 条")
        return rules

    def get_firewall_rules(self) -> list[dict]:
        """获取已生成的防火墙规则列表。"""
        return list(self._firewall_rules)

    # ── 风险评估 ─────────────────────────────────────────

    def assess_risk(self, ip: str) -> dict:
        """评估指定IP的威胁风险。"""
        threats = [t for t in self._threats.values() if t.source_ip == ip]
        if not threats:
            return {"ip": ip, "risk_score": 0.0, "threat_count": 0, "level": "clean"}

        max_risk = max(t.risk_score for t in threats)
        total_risk = sum(t.risk_score for t in threats)
        avg_risk = total_risk / len(threats)

        if max_risk >= 8.0:
            level = "critical"
        elif max_risk >= 6.0:
            level = "high"
        elif max_risk >= 4.0:
            level = "medium"
        else:
            level = "low"

        return {
            "ip": ip,
            "risk_score": round(max_risk, 2),
            "avg_risk": round(avg_risk, 2),
            "threat_count": len(threats),
            "level": level,
            "threats": [t.to_dict() for t in threats],
        }

    def get_risk_report(self) -> dict:
        """生成整体风险报告。"""
        total = len(self._threats)
        by_level = {}
        for t in self._threats.values():
            lv = t.threat_level.value
            by_level[lv] = by_level.get(lv, 0) + 1

        by_category = {}
        for t in self._threats.values():
            cat = t.category
            by_category[cat] = by_category.get(cat, 0) + 1

        avg_risk = (sum(t.risk_score for t in self._threats.values()) / total
                    if total > 0 else 0)

        return {
            "total_threats": total,
            "by_level": by_level,
            "by_category": by_category,
            "avg_risk_score": round(avg_risk, 2),
            "quarantined": sum(1 for t in self._threats.values() if t.quarantined),
            "eliminated": sum(1 for t in self._threats.values() if t.eliminated),
            "firewall_rules": len(self._firewall_rules),
        }

    # ── 威胁报告 ─────────────────────────────────────────

    def get_threat_report(self, threat_id: str) -> dict:
        """获取单个威胁的详细信息。"""
        if threat_id not in self._threats:
            return {"error": f"威胁 {threat_id} 不存在"}
        t = self._threats[threat_id]
        return {
            "id": t.threat_id,
            "source": f"{t.source_ip}:{t.source_port}",
            "target": f"{t.destination_ip}:{t.destination_port}",
            "name": t.threat_name,
            "level": t.threat_level.value,
            "category": t.category,
            "risk_score": t.risk_score,
            "matched_pattern": t.matched_pattern,
            "quarantined": t.quarantined,
            "eliminated": t.eliminated,
            "detected_at": t.detected_at,
        }

    # ── 签名管理 ─────────────────────────────────────────

    def add_signature(self, name: str, pattern: str, level: str,
                      category: str, description: str,
                      mitigation: str = "") -> bool:
        """添加自定义威胁签名。"""
        if name in [s.name for s in self.signatures]:
            return False
        self.signatures.append(ThreatSignature(
            name=name, pattern=pattern,
            level=ThreatLevel(level),
            category=category,
            description=description,
            mitigation=mitigation,
        ))
        logger.info(f"添加威胁签名: {name}")
        return True

    def remove_signature(self, name: str) -> bool:
        """移除威胁签名。"""
        before = len(self.signatures)
        self.signatures = [s for s in self.signatures if s.name != name]
        return len(self.signatures) < before

    def list_signatures(self) -> list[dict]:
        """列出所有威胁签名。"""
        return [{"name": s.name, "level": s.level.value,
                 "category": s.category, "pattern": s.pattern}
                for s in self.signatures]

    def threat_count(self) -> int:
        """返回当前威胁总数。"""
        return len(self._threats)

    def eliminated_count(self) -> int:
        """返回已清杀威胁数。"""
        return sum(1 for t in self._threats.values() if t.eliminated)

    def threat_status(self, threat_id: str) -> dict:
        """返回威胁当前状态。"""
        if threat_id not in self._threats:
            return {"error": f"威胁 {threat_id} 不存在"}
        t = self._threats[threat_id]
        return {
            "id": t.threat_id,
            "name": t.threat_name,
            "level": t.threat_level.value,
            "quarantined": t.quarantined,
            "eliminated": t.eliminated,
            "risk_score": t.risk_score,
        }

    # ── 内部工具方法 ─────────────────────────────────────

    def _create_threat(self, source_ip: str, dest_ip: str,
                       dest_port: int, name: str, level: ThreatLevel,
                       category: str, description: str,
                       matched_pattern: str = "",
                       mitigation: str = "",
                       risk_score: float = 5.0) -> NetworkThreat:
        """创建威胁实例。"""
        threat_id = f"THREAT_{uuid.uuid4().hex[:8].upper()}"
        threat = NetworkThreat(
            threat_id=threat_id,
            source_ip=source_ip,
            destination_ip=dest_ip,
            source_port=self._random_source_port(),
            destination_port=dest_port,
            threat_name=name,
            threat_level=level,
            category=category,
            matched_pattern=matched_pattern or description,
            risk_score=risk_score,
        )
        self._threats[threat_id] = threat
        logger.debug(f"创建威胁: {threat_id} = {name} [{level.value}]")
        return threat

    def _calc_risk(self, level: ThreatLevel) -> float:
        """根据威胁等级计算风险分。"""
        return {"low": 3.0, "medium": 6.0, "high": 8.0, "critical": 10.0}[level.value]

    def _is_suspicious_port(self, port: int) -> bool:
        """检查端口是否为恶意端口。"""
        return port in MALICIOUS_PORTS

    def _check_ip_reputation(self, ip: str) -> dict:
        """检查IP信誉（模拟）。"""
        # 基于IP最后一段做哈希，模拟信誉评分
        try:
            last_octet = int(ip.split(".")[-1])
            # 常见恶意IP特征：最后一段在特定范围
            suspicious_ranges = [0, 1, 2, 127, 255]
            if last_octet in suspicious_ranges:
                return {"score": 2.0, "reason": "保留/特殊IP段"}
            if last_octet > 200:
                return {"score": 4.0, "reason": "高位IP段，可疑"}
            return {"score": 7.0, "reason": "正常IP段"}
        except (ValueError, IndexError):
            return {"score": 5.0, "reason": "无法解析IP"}

    def _is_valid_ip(self, ip: str) -> bool:
        """检查是否为有效IPv4地址。"""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    @staticmethod
    def _random_source_port() -> int:
        """生成随机源端口（模拟）。"""
        import random
        return random.randint(1024, 65535)


# ============================================================
# Matha 内建函数（注册到解释器）
# ============================================================

# 全局引擎实例（懒初始化）
_engine: Optional[NetSecurityEngine] = None

def _get_engine() -> NetSecurityEngine:
    global _engine
    if _engine is None:
        _engine = NetSecurityEngine()
    return _engine


def builtin_威胁检测(source_ips: list) -> list:
    """威胁检测(source_ips) → 威胁列表。"""
    engine = _get_engine()
    return engine.scan_threats(source_ips)


def builtin_检测病毒(behavior: str) -> list:
    """检测病毒(行为模式) → 匹配签名列表。"""
    engine = _get_engine()
    return engine.detect_virus(behavior)


def builtin_隔离威胁(threat_id: str) -> dict:
    """隔离威胁(威胁ID) → 操作结果。"""
    engine = _get_engine()
    return engine.quarantine(threat_id)


def builtin_清杀威胁(threat_id: str) -> dict:
    """清杀威胁(威胁ID) → 操作结果。"""
    engine = _get_engine()
    return engine.eliminate(threat_id)


def builtin_清杀全部(level: str = "") -> dict:
    """清杀全部威胁(级别) → 批量操作结果。"""
    engine = _get_engine()
    return engine.eliminate_all(level or None)


def builtin_生成防火墙规则(threats: list = None) -> list:
    """生成防火墙规则(威胁列表) → 规则列表。"""
    engine = _get_engine()
    return engine.generate_firewall_rules(threats)


def builtin_风险评估(ip: str) -> dict:
    """风险评估(IP地址) → 风险评估结果。"""
    engine = _get_engine()
    return engine.assess_risk(ip)


def builtin_风险报告() -> dict:
    """风险报告() → 整体风险报告。"""
    engine = _get_engine()
    return engine.get_risk_report()


def builtin_威胁报告(threat_id: str) -> dict:
    """威胁报告(威胁ID) → 威胁详情。"""
    engine = _get_engine()
    result = engine.get_threat_report(threat_id)
    return result if result else {"error": f"威胁 {threat_id} 不存在"}


def builtin_添加签名(name: str, pattern: str, level: str,
                     category: str, description: str) -> bool:
    """添加签名(名称, 模式, 等级, 分类, 描述) → 是否成功。"""
    engine = _get_engine()
    return engine.add_signature(name, pattern, level, category, description)


def builtin_列出签名() -> list:
    """列出签名() → 所有威胁签名。"""
    engine = _get_engine()
    return engine.list_signatures()


def builtin_威胁数量() -> int:
    """威胁数量() → 当前威胁总数。"""
    engine = _get_engine()
    return len(engine._threats)


def builtin_已清杀数量() -> int:
    """已清杀数量() → 已清杀威胁数。"""
    engine = _get_engine()
    return sum(1 for t in engine._threats.values() if t.eliminated)


def builtin_防火墙规则列表() -> list:
    """防火墙规则列表() → 已生成规则。"""
    engine = _get_engine()
    return engine.get_firewall_rules()


def builtin_威胁状态(threat_id: str) -> dict:
    """威胁状态(威胁ID) → 威胁当前状态。"""
    engine = _get_engine()
    if threat_id not in engine._threats:
        return {"error": f"威胁 {threat_id} 不存在"}
    t = engine._threats[threat_id]
    return {
        "id": t.threat_id,
        "name": t.threat_name,
        "level": t.threat_level.value,
        "quarantined": t.quarantined,
        "eliminated": t.eliminated,
        "risk_score": t.risk_score,
    }
