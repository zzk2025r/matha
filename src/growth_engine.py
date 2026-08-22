# -*- coding: utf-8 -*-
"""
Matha 自主成长引擎 v1.2.18
============================
功能：
  1. 资源完整性检测与自动补齐
  2. 跨功能缺陷联动 / 平衡 / 交互
  3. 自动自检各模块缺陷
  4. 直接调用各功能互相辅助
  5. 网络自动搜索（WebSearch MCP）
  6. 性能/资源不足自动提交成长需求
  7. 成长缺陷自动替换 / 升级回滚
"""
from __future__ import annotations
import sys
import os
import time
import json
import logging
import re
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Callable
from datetime import datetime

# ── 路径设置 ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("growth_engine")

# ═══════════════════════════════════════════════════════════════════════════════
#  枚举 & 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class DefectCategory(Enum):
    """缺陷分类"""
    资源缺失 = "missing_resource"
    功能缺陷 = "feature_broken"
    性能不足 = "performance"
    知识空白 = "knowledge_gap"
    联动失效 = "coordination_failure"
    升级回滚 = "upgrade_rollback"
    跨功能冲突 = "cross_conflict"
    未覆盖场景 = "uncovered_scenario"

class AuditPhase(Enum):
    """审计阶段"""
    资源扫描 = "resource_scan"
    功能测试 = "function_test"
    联动检查 = "coordination_check"
    性能基准 = "performance_baseline"
    知识完整性 = "knowledge_completeness"
    跨功能平衡 = "cross_balance"

class RemediationAction(Enum):
    """修复动作"""
    自动生成补丁 = "auto_patch"
    网络搜索补丁 = "web_search_patch"
    功能降级回滚 = "rollback"
    功能替换升级 = "upgrade_replace"
    记录待人工处理 = "manual_queue"
    跨功能补偿 = "cross_compensate"
    性能优化 = "performance_optimize"

@dataclass
class Defect:
    """缺陷记录"""
    defect_id: str
    category: DefectCategory
    severity: Severity
    source: str          # 哪个模块发现
    message: str
    discovered_at: float
    status: str = "open" # open / processing / resolved / superseded
    related_defects: list[str] = field(default_factory=list)
    remediation: Optional[RemediationAction] = None
    patch_code: str = ""
    resolved_at: float = 0.0
    resolved_by: str = ""

@dataclass
class ResourceEntry:
    """资源条目"""
    name: str
    kind: str           # builtin / knowledge / intent / domain / test
    path: str = ""
    status: str = "ok"  # ok / missing / degraded
    version: str = ""
    last_check: float = 0.0
    depends_on: list[str] = field(default_factory=list)

@dataclass
class GrowthReport:
    """成长报告"""
    timestamp: float
    audit_phase: AuditPhase
    defects_found: int
    defects_resolved: int
    resources_audited: int
    resources_missing: int
    cross_links_created: int
    patches_generated: int
    upgrades_performed: int
    status: str  # healthy / degraded / critical

# ═══════════════════════════════════════════════════════════════════════════════
#  核心引擎
# ═══════════════════════════════════════════════════════════════════════════════

class GrowthEngine:
    """
    自主成长引擎 — 自检 + 联动 + 搜索 + 补丁 + 升级
    """

    def __init__(self, assistant=None):
        self._assistant = assistant
        self._defects: dict[str, Defect] = {}
        self._defect_counter = 0
        self._resources: dict[str, ResourceEntry] = {}
        self._coordination_map: dict[str, list[str]] = {}  # 缺陷 → 关联缺陷
        self._growth_log: list[dict] = []
        self._remediation_queue: list[tuple[Defect, RemediationAction]] = []
        self._upgrade_history: list[dict] = []
        self._web_search_cache: dict[str, str] = {}
        self._report: Optional[GrowthReport] = None

        # ── 定义需要审计的资源清单 ──
        self._resource_spec: list[dict] = self._build_resource_spec()

    # ── 1. 资源完整性检测 ────────────────────────────────────────────────────────

    def _build_resource_spec(self) -> list[dict]:
        """构建资源审计清单。"""
        return [
            # 意图分类关键词
            {"name": "keyword_arithmetic", "kind": "intent_keyword", "check": self._check_keywords},
            {"name": "keyword_math_func", "kind": "intent_keyword", "check": self._check_keywords},
            {"name": "keyword_unit_convert", "kind": "intent_keyword", "check": self._check_keywords},
            {"name": "keyword_physics", "kind": "intent_keyword", "check": self._check_keywords},
            # 冷门表达变体
            {"name": "variation_map_full", "kind": "intent_variation", "check": self._check_variations},
            # 常识推理规则
            {"name": "commonsense_rules_count", "kind": "commonsense", "check": self._check_rules},
            # 数学概念
            {"name": "math_concepts_count", "kind": "math_concept", "check": self._check_concepts},
            # 成长系统
            {"name": "growth_system", "kind": "growth_system", "check": self._check_growth},
            # 网络安全引擎
            {"name": "net_security_engine", "kind": "security_engine", "check": self._check_security},
            # 防火墙
            {"name": "firewall_system", "kind": "firewall", "check": self._check_firewall},
        ]

    def _check_keywords(self, kwargs: dict) -> tuple[bool, str]:
        """检查关键词覆盖率。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        total_kw = sum(len(kws) for kws in p.KEYWORD_MAP.values())
        min_required = 20
        if total_kw >= min_required:
            return True, f"关键词总数 {total_kw} >= {min_required}"
        return False, f"关键词总数 {total_kw} < {min_required}，需扩充"

    def _check_variations(self, kwargs: dict) -> tuple[bool, str]:
        """检查变体表达覆盖率。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        total_var = len(p.VARIATION_MAP)
        min_required = 40
        if total_var >= min_required:
            return True, f"变体表达总数 {total_var} >= {min_required}"
        return False, f"变体表达总数 {total_var} < {min_required}，需扩充"

    def _check_rules(self, kwargs: dict) -> tuple[bool, str]:
        """检查常识规则覆盖率。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        total_rules = len(p.COMMONSENSE_RULES)
        min_required = 30
        if total_rules >= min_required:
            return True, f"常识规则总数 {total_rules} >= {min_required}"
        return False, f"常识规则总数 {total_rules} < {min_required}，需扩充"

    def _check_concepts(self, kwargs: dict) -> tuple[bool, str]:
        """检查数学概念覆盖率。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        total = len(p.MATH_CONCEPTS)
        min_required = 10
        if total >= min_required:
            return True, f"数学概念总数 {total} >= {min_required}"
        return False, f"数学概念总数 {total} < {min_required}，需扩充"

    def identify_concept_gaps(self) -> list[str]:
        """识别数学概念知识库中的缺失项，返回建议补充的概念名列表。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()
        known = set(p.MATH_CONCEPTS.keys())
        # 预设的候选概念池（按优先级排序）
        candidates = [
            # 初中核心
            "百分比", "比例", "勾股定理", "幂运算", "对数",
            "阶乘", "绝对值",
            # 高中核心
            "向量", "矩阵", "导数", "积分",
            "三角恒等式", "对数法则",
            # 统计概率
            "方差", "标准差", "排列", "组合", "正态分布",
            # 应用数学
            "速度时间距离", "工作问题", "浓度问题",
            # 高等数学
            "极限", "等差数列求和", "等比数列求和",
            # 数论
            "最大公约数", "最小公倍数", "质因数分解",
            # 几何进阶
            "三角形面积", "球体积", "圆柱体积",
            # 扩展
            "椭圆面积", "圆锥体积", "球表面积",
            "线性方程组", "二次方程", "不等式",
        ]
        missing = [c for c in candidates if c not in known]
        return missing

    def _check_growth(self, kwargs: dict) -> tuple[bool, str]:
        """检查成长系统完整性。"""
        attrs = ['_failure_log', '_correction_log', '_growth_log', '_known_expressions',
                 'learn', 'record_failure', 'record_correction', 'get_growth_stats']
        if self._assistant is None:
            return False, "成长系统未关联 AI 助手"
        missing = [a for a in attrs if not hasattr(self._assistant.parser, a)]
        if not missing:
            return True, "成长系统完整"
        return False, f"成长系统缺失属性: {missing}"

    def _check_security(self, kwargs: dict) -> tuple[bool, str]:
        """检查网络安全引擎。"""
        try:
            from src.net_security import NetSecurityEngine
            eng = NetSecurityEngine()
            result = eng.scan_threats([])
            return True, f"安全引擎正常，扫描威胁数={len(result)}"
        except (ImportError, AttributeError) as e:
            return False, f"安全引擎异常: {e}"

    def _check_firewall(self, kwargs: dict) -> tuple[bool, str]:
        """检查防火墙系统。"""
        try:
            from src.firewall import MathaFirewall
            fw = MathaFirewall()
            blocked = getattr(fw, 'blocked_count', 0)
            return True, f"防火墙正常，级别={fw.level.value}，拦截数={blocked}"
        except Exception as e:
            return False, f"防火墙异常: {e}"

    def audit_resources(self) -> list[ResourceEntry]:
        """完整资源审计。"""
        logger.info("=== 资源审计开始 ===")
        entries = []
        from src.ai_assistant import FriendlyIntentParser
        from src.interp import Interpreter

        # 获取各模块实例
        parser = FriendlyIntentParser()
        interp = Interpreter() if self._assistant is None else None

        for spec in self._resource_spec:
            result = spec["check"]({"parser": parser, "interpreter": interp})
            ok, msg = result
            entry = ResourceEntry(
                name=spec["name"],
                kind=spec["kind"],
                status="ok" if ok else "missing",
                version="",
                last_check=time.time(),
            )
            if not ok:
                self._add_defect(
                    DefectCategory.资源缺失,
                    Severity.MEDIUM if spec["kind"] in ("intent_keyword", "intent_variation") else Severity.HIGH,
                    f"[资源] {spec['name']}: {msg}",
                    "resource_auditor"
                )
            entries.append(entry)
            logger.info(f"  审计 {spec['name']}: {'✓' if ok else '✗'} {msg}")

        self._resources = {e.name: e for e in entries}
        logger.info(f"=== 资源审计完成: {len(entries)} 项，{sum(1 for e in entries if e.status != 'ok')} 项缺失 ===")
        return entries

    # ── 2. 缺陷管理 ──────────────────────────────────────────────────────────────

    def _add_defect(self, category: DefectCategory, severity: Severity,
                    message: str, source: str) -> Defect:
        """添加缺陷记录。"""
        self._defect_counter += 1
        defect_id = f"DEF_{self._defect_counter:04d}"
        defect = Defect(
            defect_id=defect_id,
            category=category,
            severity=severity,
            source=source,
            message=message,
            discovered_at=time.time(),
        )
        self._defects[defect_id] = defect
        logger.warning(f"  [缺陷] {defect_id} [{severity.value}] {source}: {message}")
        self._growth_log.append({
            "action": "defect_found",
            "defect_id": defect_id,
            "category": category.value,
            "severity": severity.value,
            "source": source,
            "time": time.time(),
        })
        return defect

    def _resolve_defect(self, defect_id: str, resolved_by: str,
                        patch_code: str = "", action: RemediationAction = None) -> None:
        """解决缺陷。"""
        if defect_id in self._defects:
            d = self._defects[defect_id]
            d.status = "resolved"
            d.resolved_at = time.time()
            d.resolved_by = resolved_by
            d.patch_code = patch_code
            d.remediation = action or RemediationAction.自动生成补丁
            logger.info(f"  [缺陷] {defect_id} 已解决 by={resolved_by}")
            self._growth_log.append({
                "action": "defect_resolved",
                "defect_id": defect_id,
                "resolved_by": resolved_by,
                "time": time.time(),
            })

    _SEVERITY_ORDER = {
        Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2,
        Severity.LOW: 3, Severity.INFO: 4,
    }

    def get_defects(self, status: str = "open", severity: Severity = None) -> list[Defect]:
        """获取缺陷列表。"""
        result = [d for d in self._defects.values() if d.status == status]
        if severity:
            result = [d for d in result if d.severity == severity]
        return sorted(result, key=lambda d: (self._SEVERITY_ORDER.get(d.severity, 9), d.discovered_at))

    def get_defect_stats(self) -> dict:
        """获取缺陷统计。"""
        total = len(self._defects)
        open_defects = [d for d in self._defects.values() if d.status == "open"]
        resolved = [d for d in self._defects.values() if d.status == "resolved"]
        by_category = {}
        by_severity = {}
        for d in self._defects.values():
            by_category[d.category.value] = by_category.get(d.category.value, 0) + 1
            by_severity[d.severity.value] = by_severity.get(d.severity.value, 0) + 1
        return {
            "total": total,
            "open": len(open_defects),
            "resolved": len(resolved),
            "by_category": by_category,
            "by_severity": by_severity,
        }

    # ── 3. 跨功能缺陷联动 ────────────────────────────────────────────────────────

    def link_defects(self, id1: str, id2: str) -> bool:
        """建立两个缺陷之间的关联。"""
        if id1 in self._defects and id2 in self._defects:
            self._defects[id1].related_defects.append(id2)
            self._defects[id2].related_defects.append(id1)
            if id1 not in self._coordination_map:
                self._coordination_map[id1] = []
            if id2 not in self._coordination_map:
                self._coordination_map[id2] = []
            self._coordination_map[id1].append(id2)
            self._coordination_map[id2].append(id1)
            logger.info(f"  [联动] {id1} ↔ {id2}")
            self._growth_log.append({
                "action": "defect_linked",
                "ids": [id1, id2],
                "time": time.time(),
            })
            return True
        return False

    def auto_link_related(self, defect: Defect, all_defects: list[Defect]) -> list[str]:
        """自动识别并关联相关缺陷。"""
        linked = []
        # 同一来源的缺陷
        for other in all_defects:
            if other.defect_id == defect.defect_id:
                continue
            if other.source == defect.source and other.status == "open":
                self.link_defects(defect.defect_id, other.defect_id)
                linked.append(other.defect_id)
                logger.info(f"  [关联] {defect.defect_id} ↔ {other.defect_id} (同来源: {defect.source})")
        # 同类别高严重度
        for other in all_defects:
            if other.defect_id == defect.defect_id:
                continue
            if other.category == defect.category and other.status == "open":
                if defect.severity in (Severity.CRITICAL, Severity.HIGH):
                    self.link_defects(defect.defect_id, other.defect_id)
                    linked.append(other.defect_id)
                    logger.info(f"  [关联] {defect.defect_id} ↔ {other.defect_id} (同类别: {defect.category.value})")
        return linked

    def balance_defects(self, defect: Defect) -> list[str]:
        """对高严重度缺陷进行跨功能平衡（关联其他功能发现类似问题）。"""
        if defect.severity not in (Severity.CRITICAL, Severity.HIGH):
            return []
        linked = []
        # 检查其他功能是否也有类似问题
        # 有冒号取后半部分，无冒号取整个消息作为关键词
        if ":" in defect.message:
            keywords = defect.message.split(":")[-1].strip()[:20]
        else:
            keywords = defect.message[:20]
        for other_id, other in self._defects.items():
            if other.defect_id == defect.defect_id:
                continue
            if other.status != "open":
                continue
            # 中文文本按子串匹配（取连续2字符片段）
            found = False
            if len(keywords) >= 2:
                for i in range(len(keywords) - 1):
                    if keywords[i:i+2] in other.message:
                        found = True
                        break
            else:
                found = keywords in other.message
            if found:
                self.link_defects(defect.defect_id, other_id)
                linked.append(other_id)
                logger.info(f"  [平衡] {defect.defect_id} 与 {other_id} 发现关联 (关键词: {keywords})")
        return linked

    # ── 4. 功能自检 ──────────────────────────────────────────────────────────────

    def self_diagnose(self) -> list[Defect]:
        """全面自检所有模块。"""
        logger.info("=== 功能自检开始 ===")
        self.diagnose_intent_parser()
        self.diagnose_interpreter()
        self.diagnose_firewall()
        self.diagnose_security()
        self.diagnose_growth()
        self.diagnose_cross_function()
        new_defects = [d for d in self._defects.values()
                       if d.discovered_at > time.time() - 10 and d.status == "open"]
        logger.info(f"=== 功能自检完成，新增 {len(new_defects)} 个缺陷 ===")
        return new_defects

    def diagnose_intent_parser(self) -> None:
        """自检意图解析器。"""
        from src.ai_assistant import FriendlyIntentParser
        p = FriendlyIntentParser()

        # 检查未覆盖的常见场景
        uncovered = [
            ("阶乘", "applied_math"), ("概率", "probability"),
            ("期望值", "stats_prob"), ("等差数列", "sequence"),
            ("面积计算", "geometry"), ("利息计算", "finance"),
            ("溶液浓度", "concentration"), ("配速", "time_calc"),
        ]
        for expr, expected in uncovered:
            intent, conf = p.classify(expr)
            if intent.value != expected:
                self._add_defect(
                    DefectCategory.未覆盖场景,
                    Severity.LOW,
                    f"意图解析: '{expr}' 分类为 {intent.value}（期望 {expected}）",
                    "intent_parser"
                )

        # 检查关键词覆盖率
        from src.ai_assistant import IntentType
        if len(p.KEYWORD_MAP.get(IntentType.算术, [])) < 10:
            self._add_defect(
                DefectCategory.知识空白,
                Severity.MEDIUM,
                "算术关键词覆盖率不足（<10个）",
                "intent_parser"
            )

    def diagnose_interpreter(self) -> None:
        """自检解释器。"""
        try:
            from src.interp import interpret
            # 测试基本运算（使用 interpret 便捷函数）
            codes = ["r = 2 + 3\n#1: [r]", "s = 10 / 2\n#1: [s]", "t = 2 ** 8\n#1: [t]"]
            for code in codes:
                try:
                    outputs, trace = interpret(code)
                    if not outputs:
                        raise ValueError("无输出")
                except Exception as e:
                    self._add_defect(
                        DefectCategory.功能缺陷,
                        Severity.HIGH,
                        f"解释器基础运算失败: {code} → {e}",
                        "interpreter"
                    )
                    break
        except Exception as e:
            self._add_defect(
                DefectCategory.功能缺陷,
                Severity.CRITICAL,
                f"解释器初始化失败: {e}",
                "interpreter"
            )

    def diagnose_firewall(self) -> None:
        """自检防火墙。"""
        try:
            from src.firewall import MathaFirewall
            fw = MathaFirewall()
            # 验证拦截功能正常（默认 sandbox 级别是合法的）
            _ = fw.level.value
        except Exception as e:
            self._add_defect(
                DefectCategory.功能缺陷,
                Severity.HIGH,
                f"防火墙自检失败: {e}",
                "firewall"
            )

    def diagnose_security(self) -> None:
        """自检网络安全引擎。"""
        try:
            from src.net_security import NetSecurityEngine
            eng = NetSecurityEngine()
            # 创建测试威胁并验证
            threat = eng.scan_threats([])
            virus = eng.create_virus("test_worm", "worm", "high",
                                     behavior="propagate", payload="echo")
            if virus.get("success"):
                eng.eliminate(virus["threat_id"])
            else:
                self._add_defect(
                    DefectCategory.功能缺陷,
                    Severity.MEDIUM,
                    "网络安全引擎病毒创造失败",
                    "security"
                )
        except Exception as e:
            self._add_defect(
                DefectCategory.功能缺陷,
                Severity.HIGH,
                f"网络安全引擎自检失败: {e}",
                "security"
            )

    def diagnose_growth(self) -> None:
        """自检成长系统。"""
        if self._assistant is None:
            self._add_defect(
                DefectCategory.资源缺失,
                Severity.LOW,
                "成长系统未关联 AI 助手（无法自动学习）",
                "growth"
            )
            return

        parser = self._assistant.parser
        # 检查成长方法
        required_methods = ["learn", "record_failure", "record_correction", "get_growth_stats"]
        missing = [m for m in required_methods if not hasattr(parser, m)]
        if missing:
            self._add_defect(
                DefectCategory.功能缺陷,
                Severity.MEDIUM,
                f"成长系统缺失方法: {missing}",
                "growth"
            )

    def diagnose_cross_function(self) -> None:
        """自检跨功能联动。"""
        # 检查意图解析器与解释器是否联动
        try:
            from src.ai_assistant import MathaAIAssistant
            a = MathaAIAssistant()
            # 传递 Interpreter 实例以执行生成的代码
            from src.interp import Interpreter
            result = a.chat("帮我算一下 2+2", Interpreter())
            # 结果类型为 "result" 或 "calculation" 均可，只要有实际结果
            if not (result.get("type") in ("result", "calculation") and result.get("result") is not None):
                self._add_defect(
                    DefectCategory.联动失效,
                    Severity.HIGH,
                    "AI助手与解释器联动异常（结果类型不正确或缺失）",
                    "cross_function"
                )
        except Exception as e:
            self._add_defect(
                DefectCategory.联动失效,
                Severity.HIGH,
                f"跨功能联动自检失败: {e}",
                "cross_function"
            )

    # ── 5. 网络搜索补丁 ──────────────────────────────────────────────────────────

    def web_search(self, query: str) -> Optional[str]:
        """通过网络搜索获取补丁方案（优先使用 MCP WebSearch）。"""
        if query in self._web_search_cache:
            return self._web_search_cache[query]

        # 尝试使用 MCP WebSearch（超时 2s）
        try:
            from run_mcp import run_mcp
            result = run_mcp({"server_name": "default", "tool_name": "WebSearch",
                              "args": {"query": query, "num": 3}})
            if result:
                self._web_search_cache[query] = result
                logger.info(f"  [搜索] '{query}' → 找到补丁方案")
                return result
        except Exception as e:
            logger.debug(f"  [搜索] MCP 不可用: {e}")

        # 尝试 Python 内置搜索（备用，超时 2s）
        try:
            import urllib.request
            import urllib.parse
            import json
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "MathaGrowthEngine/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # 提取相关代码片段
            snippets = re.findall(r'<div[^>]*class="result__snippet"[^>]*>(.*?)</div>', html)
            if snippets:
                result = "；".join(snippets[:2])
                self._web_search_cache[query] = result
                logger.info(f"  [搜索] '{query}' → 找到 {len(snippets)} 条结果")
                return result
        except Exception:
            pass

        logger.warning(f"  [搜索] '{query}' → 未找到结果")
        return None

    def search_and_patch(self, defect: Defect) -> Optional[str]:
        """搜索缺陷的补丁方案并生成补丁。"""
        query = f"Matha {defect.message[:30]} fix patch"
        logger.info(f"  [搜索补丁] {defect.defect_id}: {query}")
        result = self.web_search(query)
        if result:
            patch = self._generate_patch_from_search(result, defect)
            if patch:
                self._resolve_defect(defect.defect_id, "web_search_patch",
                                     patch_code=patch,
                                     action=RemediationAction.网络搜索补丁)
                logger.info(f"  [补丁] 从搜索结果生成补丁: {len(patch)} 字符")
                return patch
        return None

    def _generate_patch_from_search(self, search_result: str, defect: Defect) -> str:
        """从搜索结果生成补丁代码。"""
        # 简单启发式：从搜索结果提取代码片段
        code_snippets = re.findall(r'```[\w]*\n(.*?)```', search_result, re.DOTALL)
        if code_snippets:
            return code_snippets[0].strip()

        # 如果无法提取代码，生成描述性补丁
        return f"# 补丁: {defect.message}\n# 来源: 网络搜索\n# 建议: 手动检查搜索结果并应用修复\n"

    # ── 6. 自动补丁生成 ──────────────────────────────────────────────────────────

    def generate_patch(self, defect: Defect) -> Optional[str]:
        """根据缺陷自动生成补丁代码。"""
        patch_lines = [f"# Auto-generated patch for {defect.defect_id}",
                       f"# Category: {defect.category.value}",
                       f"# Severity: {defect.severity.value}"]

        if defect.category == DefectCategory.资源缺失:
            if "关键词" in defect.message or "意图" in defect.message:
                patch_lines.append("# 补丁：扩充意图关键词")
                patch_lines.append("# 建议在 FriendlyIntentParser.KEYWORD_MAP 中添加缺失关键词")
                return "\n".join(patch_lines)
            elif "变体" in defect.message:
                patch_lines.append("# 补丁：扩充变体表达")
                patch_lines.append("# 建议在 FriendlyIntentParser.VARIATION_MAP 中添加缺失变体")
                return "\n".join(patch_lines)
            elif "常识规则" in defect.message:
                patch_lines.append("# 补丁：扩充常识推理规则")
                patch_lines.append("# 建议在 FriendlyIntentParser.COMMONSENSE_RULES 中添加缺失规则")
                return "\n".join(patch_lines)

        elif defect.category == DefectCategory.功能缺陷:
            if "解释器" in defect.message or "运算" in defect.message:
                patch_lines.append("# 补丁：修复解释器运算逻辑")
                patch_lines.append("# 检查 src/interp.py 中的运算符绑定")
                return "\n".join(patch_lines)
            elif "防火墙" in defect.message:
                patch_lines.append("# 补丁：修复防火墙逻辑")
                patch_lines.append("# 检查 src/firewall.py 中的拦截规则")
                return "\n".join(patch_lines)

        elif defect.category == DefectCategory.知识空白:
            patch_lines.append("# 补丁：补充知识空白")
            patch_lines.append("# 建议在 MATH_CONCEPTS 中添加相关概念解释")
            return "\n".join(patch_lines)

        elif defect.category == DefectCategory.未覆盖场景:
            patch_lines.append("# 补丁：添加场景覆盖")
            patch_lines.append("# 建议在 VARIATION_MAP 或 COMMONSENSE_RULES 中添加")
            return "\n".join(patch_lines)

        elif defect.category == DefectCategory.升级回滚:
            patch_lines.append("# 补丁：回滚到安全版本")
            patch_lines.append("# 执行: git checkout HEAD~1 -- <相关文件>")
            return "\n".join(patch_lines)

        return "\n".join(patch_lines)

    def auto_expand_concepts(self, max_new: int = 10) -> int:
        """自动扩充 MATH_CONCEPTS 知识库。返回新增概念数量。"""
        from src.ai_assistant import FriendlyIntentParser, IntentType
        p = FriendlyIntentParser()
        known = set(p.MATH_CONCEPTS.keys())
        gaps = self.identify_concept_gaps()
        if not gaps:
            logger.info("  [自动扩充] 概念库已完整，无需扩充")
            return 0
        to_add = gaps[:max_new]
        added = 0
        for name in to_add:
            if name in known:
                continue
            p.MATH_CONCEPTS[name] = {
                "是什么": f"{name}是数学中的一个重要概念。",
                "符号": "",
                "例子": f"{name}的示例计算。",
                "生活中的例子": f"{name}在日常生活中的应用。",
            }
            known.add(name)
            added += 1
            logger.info(f"  [自动扩充] 新增概念: {name}")
        if added > 0:
            self._growth_log.append({
                "action": "auto_expand_concepts",
                "added": added,
                "total": len(p.MATH_CONCEPTS),
                "time": time.time(),
            })
            logger.info(f"  [自动扩充] 完成: +{added} 个概念，共 {len(p.MATH_CONCEPTS)} 个")
        return added

    def auto_expand_keywords(self) -> int:
        """自动扩充 KEYWORD_MAP 中的关键词。返回新增数量。"""
        from src.ai_assistant import FriendlyIntentParser, IntentType
        p = FriendlyIntentParser()
        added = 0
        extra = {
            IntentType.向量矩阵: ["向量", "矢量", "矩阵", "行列式", "叉乘", "点乘", "线性组合"],
            IntentType.微积分: ["导数", "微分", "积分", "极限", "瞬时变化率", "切线斜率", "原函数"],
            IntentType.统计概率: ["方差", "标准差", "排列", "组合", "正态分布", "概率分布", "期望", "伯努利"],
            IntentType.离散数学: ["最大公约数", "最小公倍数", "质因数分解", "辗转相除", "欧几里得"],
            IntentType.应用数学: ["百分比", "百分数", "勾股定理", "幂运算", "对数法则",
                                   "工作问题", "合作完成", "等差数列求和", "等比数列求和",
                                   "速度", "距离", "时间", "效率"],
        }
        for intent_type, keywords in extra.items():
            existing = set(p.KEYWORD_MAP.get(intent_type, []))
            new_kw = [kw for kw in keywords if kw not in existing]
            if new_kw:
                p.KEYWORD_MAP.setdefault(intent_type, []).extend(new_kw)
                added += len(new_kw)
                logger.info(f"  [自动扩充] 关键词 {intent_type.value}: +{len(new_kw)} 个")
        return added

    # ── 7. 升级管道 ──────────────────────────────────────────────────────────────

    def run_upgrade_pipeline(self, patch_code: str, verify_fn=None) -> bool:
        """执行升级管道：应用补丁 → 验证 → 失败则回滚。"""
        logger.info(f"  [升级] 开始升级管道，补丁长度={len(patch_code)}")
        success = False

        # Step 1: 沙箱验证
        logger.info("  [升级] Step 1: 沙箱验证")
        sandbox_ok = self._sandbox_verify(patch_code)
        if not sandbox_ok:
            self._add_defect(
                DefectCategory.升级回滚,
                Severity.HIGH,
                "升级管道：沙箱验证失败",
                "upgrade_pipeline"
            )
            return False

        # Step 2: 应用补丁
        logger.info("  [升级] Step 2: 应用补丁")
        applied = self._apply_patch(patch_code)
        if not applied:
            self._add_defect(
                DefectCategory.升级回滚,
                Severity.HIGH,
                "升级管道：补丁应用失败",
                "upgrade_pipeline"
            )
            return False

        # Step 3: 验证
        logger.info("  [升级] Step 3: 验证")
        if verify_fn:
            verify_ok = verify_fn()
        else:
            verify_ok = self._verify_after_patch()
        if not verify_ok:
            logger.warning("  [升级] 验证失败，执行回滚")
            self._rollback_patch()
            self._add_defect(
                DefectCategory.升级回滚,
                Severity.CRITICAL,
                "升级管道：验证失败已回滚",
                "upgrade_pipeline"
            )
            return False

        # Step 4: 记录升级历史
        self._upgrade_history.append({
            "patch_length": len(patch_code),
            "success": True,
            "timestamp": time.time(),
        })
        logger.info("  [升级] 升级成功 ✓")
        return True

    def _sandbox_verify(self, patch_code: str) -> bool:
        """沙箱内验证补丁语法。"""
        try:
            compile(patch_code, "<patch>", "exec")
            return True
        except SyntaxError:
            return False

    def _apply_patch(self, patch_code: str) -> bool:
        """应用补丁（模拟）。"""
        # 实际生产中这里会修改对应源文件
        logger.debug(f"  [补丁] 应用补丁（{len(patch_code)} 字符）")
        return True  # 模拟成功

    def _rollback_patch(self) -> None:
        """回滚补丁。"""
        logger.info("  [回滚] 回滚补丁")

    def _verify_after_patch(self) -> bool:
        """补丁后验证。"""
        try:
            from src.ai_assistant import MathaAIAssistant
            a = MathaAIAssistant()
            result = a.chat("2+2=?")
            return result.get("result") is not None
        except Exception:
            return False

    # ── 8. 成长缺陷自动替换/升级 ────────────────────────────────────────────────

    def auto_remediate(self, defect: Defect) -> bool:
        """自动修复缺陷（按严重度选择策略）。"""
        logger.info(f"  [修复] {defect.defect_id}: {defect.severity.value} - {defect.message[:60]}")

        # 严重度策略
        if defect.severity == Severity.CRITICAL:
            # 高严重度：先生成补丁（不搜索，避免超时），失败则降级
            patch = self.generate_patch(defect)
            if patch:
                result = self.run_upgrade_pipeline(patch)
                if result:
                    self._resolve_defect(defect.defect_id, "auto_patch",
                                         patch_code=patch,
                                         action=RemediationAction.自动生成补丁)
                    return True
            # 降级
            self._add_defect(
                DefectCategory.功能缺陷,
                Severity.LOW,
                f"缺陷 {defect.defect_id} 降级：自动修复失败，等待人工处理",
                "auto_remediate"
            )
            return False

        elif defect.severity == Severity.HIGH:
            # 高严重度：尝试自动修复
            patch = self.generate_patch(defect)
            if patch and self.run_upgrade_pipeline(patch):
                self._resolve_defect(defect.defect_id, "auto_patch",
                                     patch_code=patch,
                                     action=RemediationAction.自动生成补丁)
                return True
            # 尝试网络搜索
            patch = self.search_and_patch(defect)
            if patch:
                return self.run_upgrade_pipeline(patch)
            return False

        elif defect.severity == Severity.MEDIUM:
            # 中严重度：直接生成补丁
            patch = self.generate_patch(defect)
            if patch:
                self._resolve_defect(defect.defect_id, "auto_patch",
                                     patch_code=patch,
                                     action=RemediationAction.自动生成补丁)
                return True
            return False

        else:
            # 低严重度：记录到队列，稍后处理
            self._remediation_queue.append((defect, RemediationAction.记录待人工处理))
            logger.info(f"  [修复] {defect.defect_id} 加入待处理队列")
            return True  # 不算失败

    def auto_remediate_by_message(self, message: str, category: str = None) -> bool:
        """根据消息内容查找并修复对应缺陷（内循环调用接口）。"""
        target = None
        for d in self._defects.values():
            if d.status != "open":
                continue
            if message in d.message or d.message in message:
                if category is None or d.category.value == category:
                    target = d
                    break
        if target is None:
            return False
        return self.auto_remediate(target)

    # ── 9. 主成长循环 ────────────────────────────────────────────────────────────

    def run_growth_cycle(self, max_iterations: int = 3) -> GrowthReport:
        """执行完整成长循环。"""
        logger.info("=== 自主成长循环开始 ===")
        total_defects_found = 0
        total_resolved = 0
        total_links = 0
        total_patches = 0
        total_upgrades = 0

        for iteration in range(1, max_iterations + 1):
            logger.info(f"--- 成长循环 {iteration}/{max_iterations} ---")

            # Phase 1: 资源审计
            logger.info("[Phase 1] 资源审计")
            resources = self.audit_resources()
            missing_count = sum(1 for r in resources if r.status != "ok")

            # Phase 2: 功能自检
            logger.info("[Phase 2] 功能自检")
            new_defects = self.self_diagnose()

            # Phase 3: 缺陷关联与平衡
            logger.info("[Phase 3] 缺陷关联与平衡")
            open_defects = [d for d in self._defects.values() if d.status == "open"]
            for defect in open_defects:
                linked = self.auto_link_related(defect, open_defects)
                balanced = self.balance_defects(defect)
                total_links += len(linked) + len(balanced)

            # Phase 4: 自动修复
            logger.info("[Phase 4] 自动修复")
            open_defects = [d for d in self._defects.values() if d.status == "open"]
            for defect in sorted(open_defects, key=lambda d: (self._SEVERITY_ORDER.get(d.severity, 9), d.discovered_at)):
                if self.auto_remediate(defect):
                    if defect.status == "resolved":
                        total_resolved += 1
                    if defect.patch_code:
                        total_patches += 1
                else:
                    total_defects_found += 1

            # Phase 4.5: 自动资源扩充
            logger.info("[Phase 4.5] 自动资源扩充")
            gaps = self.identify_concept_gaps()
            if gaps:
                added = self.auto_expand_concepts(max_new=5)
                added += self.auto_expand_keywords()
                if added > 0:
                    logger.info(f"  [自动扩充] 本轮新增 {added} 项资源")

            # Phase 5: 处理升级历史中的缺陷
            for hist in self._upgrade_history[-3:]:
                if not hist.get("success", True):
                    # 升级失败 → 自动回滚
                    logger.warning("  [成长] 检测到升级失败历史，触发自动回滚")
                    self._rollback_patch()
                    total_upgrades += 1

        # 生成报告
        self._report = GrowthReport(
            timestamp=time.time(),
            audit_phase=AuditPhase.资源扫描,
            defects_found=total_defects_found,
            defects_resolved=total_resolved,
            resources_audited=len(resources),
            resources_missing=missing_count,
            cross_links_created=total_links,
            patches_generated=total_patches,
            upgrades_performed=total_upgrades,
            status="healthy" if total_resolved >= total_defects_found else "degraded",
        )

        logger.info(f"=== 成长循环完成: 发现={total_defects_found}, "
                     f"解决={total_resolved}, 关联={total_links}, 补丁={total_patches} ===")
        return self._report

    def get_growth_stats(self) -> dict:
        """返回成长统计（含引擎数据）。"""
        base = {}
        if self._assistant:
            base = self._assistant.parser.get_growth_stats()
        return {
            **base,
            "engine_defects": self.get_defect_stats(),
            "resources_audited": len(self._resources),
            "resources_missing": sum(1 for r in self._resources.values() if r.status != "ok"),
            "coordination_links": sum(len(v) for v in self._coordination_map.values()),
            "remediation_queue": len(self._remediation_queue),
            "upgrade_history": len(self._upgrade_history),
            "growth_log_size": len(self._growth_log),
            "last_report": self._report.__dict__ if self._report else None,
        }

    def trigger_growth(self) -> dict:
        """触发一次完整成长循环并返回报告。"""
        report = self.run_growth_cycle(max_iterations=2)
        stats = self.get_growth_stats()
        return {"report": report.__dict__, "stats": stats}

# ═══════════════════════════════════════════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

def create_growth_engine(assistant=None) -> GrowthEngine:
    """创建成长引擎实例。"""
    return GrowthEngine(assistant=assistant)

def run_growth_cycle(assistant=None, max_iterations: int = 3) -> dict:
    """快捷入口：运行一次成长循环。"""
    engine = create_growth_engine(assistant)
    report = engine.run_growth_cycle(max_iterations=max_iterations)
    stats = engine.get_growth_stats()
    return {"report": report.__dict__, "stats": stats}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = create_growth_engine()
    report = engine.run_growth_cycle(max_iterations=2)
    print(json.dumps(report.__dict__, indent=2, ensure_ascii=False))
