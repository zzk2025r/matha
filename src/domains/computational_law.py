"""计算法学：法律推理、案例匹配、法规分析、智能合约审计。"""
from __future__ import annotations

import collections
import hashlib
import math
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MAX_CASES = 1000
SIMILARITY_THRESHOLD = 0.7
MATCH_THRESHOLD = 0.3
MAX_CLAUSE_DEPTH = 5


class LegalDomain(Enum):
    CONSTITUTIONAL = "constitutional"
    CIVIL = "civil"
    CRIMINAL = "criminal"
    COMMERCIAL = "commercial"
    IP = "intellectual_property"
    LABOR = "labor"
    ADMINISTRATIVE = "administrative"
    TAX = "tax"
    FAMILY = "family"
    INTERNATIONAL = "international"


class ReasoningRule(Enum):
    SYLLOGISM = "syllogism"
    ANALOGY = "analogy"
    RULE_OF_LAW = "rule_of_law"
    PRECEDENT = "precedent"
    POLICY = "policy"
    PURPOSE = "purpose"
    TEXTUALISM = "textualism"


class ContractClause(Enum):
    PARTIES = "parties"
    SCOPE = "scope"
    CONSIDERATION = "consideration"
    PAYMENT = "payment"
    CONFIDENTIALITY = "confidentiality"
    INDEMNITY = "indemnity"
    LIABILITY = "liability"
    TERMINATION = "termination"
    DISPUTE = "dispute_resolution"
    GOVERNING_LAW = "governning_law"
    FORCE_MAJEURE = "force_majeure"
    IP_ASSIGNMENT = "ip_assignment"
    NON_COMPETE = "non_compete"
    AUDIT_RIGHTS = "audit_rights"
    SEVERABILITY = "severability"


class ComplianceResult(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NA = "not_applicable"


@dataclass
class LegalCase:
    case_id: str = ""
    name: str = ""
    domain: LegalDomain = LegalDomain.CIVIL
    court: str = ""
    decided_at: float = 0.0
    facts: str = ""
    holding: str = ""
    ratio: str = ""
    statutes: list[str] = field(default_factory=list)
    cited_cases: list[str] = field(default_factory=list)
    outcome: str = ""
    tags: list[str] = field(default_factory=list)
    importance: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id, "name": self.name,
            "domain": self.domain.value, "court": self.court,
            "holding": self.holding, "ratio": self.ratio,
            "statutes": list(self.statutes),
            "outcome": self.outcome,
            "importance": self.importance,
        }


@dataclass
class Statute:
    statute_id: str = ""
    title: str = ""
    jurisdiction: str = ""
    article: str = ""
    text: str = ""
    keywords: list[str] = field(default_factory=list)
    penalty: str = ""
    effective_from: float = 0.0
    amended_at: float = 0.0
    version: int = 1


@dataclass
class Clause:
    kind: ContractClause = ContractClause.SCOPE
    text: str = ""
    balanced: bool = True
    mandatory: bool = True
    risk: str = "low"
    depth: int = 0
    parent: Clause | None = None
    children: list[Clause] = field(default_factory=list)

    def add(self, child: Clause) -> Clause:
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)
        return child


@dataclass
class Argument:
    premise: str = ""
    rule: str = ""
    conclusion: str = ""
    strength: float = 0.0
    counter_arguments: list[str] = field(default_factory=list)
    supporting_cases: list[str] = field(default_factory=list)


CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """分词：ASCII 词 + 中文二元组（bigram）。"""
    low = text.lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", low) if len(t) > 1]
    for run in CJK_RE.findall(low):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def cosine(a: str, b: str) -> float:
    ta, tb = collections.Counter(tokenize(a)), \
        collections.Counter(tokenize(b))
    if not ta or not tb:
        return 0.0
    common = set(ta) & set(tb)
    dot = sum(ta[t] * tb[t] for t in common)
    na = math.sqrt(sum(v * v for v in ta.values()))
    nb = math.sqrt(sum(v * v for v in tb.values()))
    return dot / (na * nb) if na and nb else 0.0


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class CaseDatabase:
    """案例库。"""

    def __init__(self):
        self._cases: dict[str, LegalCase] = {}
        self._index: dict[str, set] = collections.defaultdict(set)
        self._lock = threading.Lock()

    def add_case(self, case: LegalCase) -> bool:
        with self._lock:
            if len(self._cases) >= MAX_CASES:
                self._evict()
            self._cases[case.case_id] = case
            for t in tokenize(case.facts + " " + case.holding):
                self._index[t].add(case.case_id)
            return True

    def _evict(self) -> None:
        if not self._cases:
            return
        weakest = min(self._cases.values(),
                      key=lambda c: c.importance)
        self.remove_case(weakest.case_id)

    def remove_case(self, case_id: str) -> bool:
        with self._lock:
            if case_id in self._cases:
                del self._cases[case_id]
                for s in self._index.values():
                    s.discard(case_id)
                return True
        return False

    def get(self, case_id: str) -> LegalCase | None:
        return self._cases.get(case_id)

    def all_cases(self) -> list[LegalCase]:
        return list(self._cases.values())

    def case_match(self, facts: str,
                   threshold: float = MATCH_THRESHOLD
                   ) -> list[tuple[LegalCase, float]]:
        scored: list[tuple[LegalCase, float]] = []
        for case in self._cases.values():
            s = max(cosine(facts, case.facts),
                    jaccard(facts, case.facts))
            if s >= threshold:
                scored.append((case, s))
        scored.sort(key=lambda x: -x[1])
        return scored

    def precedent_search(self, query: str,
                         domain: LegalDomain | None = None,
                         limit: int = 10) -> list[LegalCase]:
        out = []
        for case in self._cases.values():
            if domain and case.domain != domain:
                continue
            s = max(cosine(query, case.ratio or case.holding),
                    cosine(query, case.facts))
            if s >= MATCH_THRESHOLD * 0.4:
                out.append((s, case))
        out.sort(key=lambda x: -x[0])
        return [c for _, c in out[:limit]]


class RegulationAnalyzer:
    """法规分析器。"""

    def __init__(self):
        self._statutes: dict[str, Statute] = {}
        self._lock = threading.Lock()

    def add_statute(self, statute: Statute) -> bool:
        with self._lock:
            self._statutes[statute.statute_id] = statute
            return True

    def get(self, statute_id: str) -> Statute | None:
        return self._statutes.get(statute_id)

    def regulation_analyze(self, statute_id: str) -> dict[str, Any]:
        s = self._statutes.get(statute_id)
        if not s:
            return {"ok": False, "error": "法规不存在"}
        kw = s.keywords or tokenize(s.text)
        risk = "low"
        if any(k in s.penalty for k in ("死刑", "无期", "十年以上")):
            risk = "critical"
        elif any(k in s.penalty for k in ("三年以上", "十年以下")):
            risk = "high"
        elif any(k in s.penalty for k in ("罚款", "拘留", "警告")):
            risk = "medium"
        return {
            "ok": True,
            "statute": statute_id,
            "title": s.title,
            "article": s.article,
            "jurisdiction": s.jurisdiction,
            "version": s.version,
            "keywords": kw,
            "penalty": s.penalty,
            "risk_level": risk,
            "word_count": len(tokenize(s.text)),
        }

    def find_applicable(self, scenario: str,
                        threshold: float = 0.25
                        ) -> list[Statute]:
        out = []
        for s in self._statutes.values():
            sim = max(cosine(scenario, s.text),
                      cosine(scenario, " ".join(s.keywords)))
            if sim >= threshold:
                out.append((sim, s))
        out.sort(key=lambda x: -x[0])
        return [s for _, s in out]

    def amendment_impact(self, statute_id: str,
                         new_text: str) -> dict[str, Any]:
        old = self._statutes.get(statute_id)
        if not old:
            return {"ok": False}
        old_kw, new_kw = set(tokenize(old.text)), set(tokenize(new_text))
        added = new_kw - old_kw
        removed = old_kw - new_kw
        return {
            "ok": True,
            "added_terms": sorted(added)[:20],
            "removed_terms": sorted(removed)[:20],
            "similarity": jaccard(old.text, new_text),
            "material_change": len(added | removed) > 3,
        }


class ClauseExtractor:
    """合同条款抽取器。"""

    KEYWORDS = {
        ContractClause.CONFIDENTIALITY:
            ["保密", "机密", "confidential", "nda"],
        ContractClause.INDEMNITY: ["赔偿", "补偿", "indemnif"],
        ContractClause.LIABILITY: ["责任", "赔偿上限", "liability"],
        ContractClause.TERMINATION: ["终止", "解除", "terminat"],
        ContractClause.DISPUTE: ["仲裁", "诉讼", "dispute", "仲裁地"],
        ContractClause.GOVERNING_LAW: ["管辖", "适用法律", "governing"],
        ContractClause.FORCE_MAJEURE: ["不可抗力", "force majeure"],
        ContractClause.IP_ASSIGNMENT: ["知识产权归属", "ip assign"],
        ContractClause.NON_COMPETE: ["竞业限制", "non-compete"],
        ContractClause.AUDIT_RIGHTS: ["审计权", "audit"],
        ContractClause.PAYMENT: ["付款", "价款", "payment", "结算"],
        ContractClause.SEVERABILITY: ["可分割", "severab"],
    }

    def __init__(self, depth: int = MAX_CLAUSE_DEPTH):
        self.max_depth = depth
        self._clauses: list[Clause] = []

    def clause_extract(self, contract_text: str
                       ) -> list[Clause]:
        self._clauses = []
        Clause(kind=ContractClause.SCOPE,
                      text=contract_text)
        segments = self._segment(contract_text)
        for seg in segments:
            kind = self.classify(seg)
            if kind is None:
                continue
            self._clauses.append(Clause(kind=kind, text=seg))
        return self._clauses

    def _segment(self, text: str) -> list[str]:
        parts = re.split(r"[。；;\n]|(?=\d+\.\s)", text)
        return [p.strip() for p in parts if len(p.strip()) >= 6]

    def classify(self, segment: str) -> ContractClause | None:
        low = segment.lower()
        for kind, kws in self.KEYWORDS.items():
            if any(k in low for k in kws):
                return kind
        return None

    def missing_mandatory(self) -> list[ContractClause]:
        present = {c.kind for c in self._clauses}
        mandatory = [
            ContractClause.PARTIES, ContractClause.SCOPE,
            ContractClause.PAYMENT, ContractClause.TERMINATION,
            ContractClause.DISPUTE, ContractClause.GOVERNING_LAW,
        ]
        return [m for m in mandatory if m not in present]


class SmartContractAuditor:
    """智能合约审计器。"""

    DANGEROUS = [
        ("delegatecall", "外部委托调用可被劫持", "critical"),
        ("selfdestruct", "自毁函数会永久销毁合约", "critical"),
        ("tx.origin", "tx.origin 鉴权可被钓鱼绕过", "critical"),
        ("block.timestamp", "出块时间可被矿工操纵", "high"),
        ("blockhash", "区块哈希不可靠", "medium"),
        ("unchecked", "未检查的调用返回值", "high"),
        ("call.value", "value 转账需校验", "medium"),
        ("assembly", "内联汇编绕过类型检查", "medium"),
        ("suicide", "suicide 等同 selfdestruct", "critical"),
        ("sha3", "sha3 已被 keccak256 取代", "low"),
    ]

    def __init__(self):
        self._findings: list[dict[str, Any]] = []
        self._score = 100

    def audit(self, source: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        low = source.lower()
        for pattern, desc, severity in self.DANGEROUS:
            occurrences = low.count(pattern)
            if occurrences:
                findings.append({
                    "pattern": pattern, "description": desc,
                    "severity": severity, "count": occurrences,
                    "line": self._find_line(source, pattern),
                })
        if "require(" not in low and "modifier" not in low \
                and "revert" not in low:
            findings.append({
                "pattern": "no-require",
                "description": "缺少输入校验（require/revert）",
                "severity": "high", "count": 1, "line": 0,
            })
        if "spdx" not in low and "license" not in low:
            findings.append({
                "pattern": "no-license",
                "description": "缺少 SPDX 许可证标识",
                "severity": "low", "count": 1, "line": 0,
            })
        self._findings = findings
        penalty = {"critical": 25, "high": 12,
                   "medium": 6, "low": 2}
        self._score = max(0, 100 - sum(
            penalty.get(f["severity"], 0) for f in findings))
        return {
            "score": self._score,
            "findings": findings,
            "critical": sum(1 for f in findings
                            if f["severity"] == "critical"),
            "total": len(findings),
            "grade": ("A" if self._score >= 90 else
                      "B" if self._score >= 75 else
                      "C" if self._score >= 60 else
                      "D" if self._score >= 40 else "F"),
        }

    def _find_line(self, source: str,
                   pattern: str) -> int:
        for i, line in enumerate(source.splitlines(), 1):
            if pattern.lower() in line.lower():
                return i
        return 0

    def findings(self) -> list[dict[str, Any]]:
        return list(self._findings)

    def gas_estimate(self, source: str) -> dict[str, int]:
        lines = source.count("\n") + 1
        return {
            "lines": lines,
            "storage_slots": source.count("mapping(") * 2,
            "external_calls": (source.count(".call")
                               + source.count("delegatecall")),
            "est_gas": 21000 + lines * 320 + source.count("for ")
            * 8000,
        }


class ComplianceChecker:
    """合规检查器。"""

    RULES = {
        "gdpr": [
            ("个人数据", ["encrypt", "anonymize"]),
            ("数据主体权利", ["delete", "portability"]),
        ],
        "pci_dss": [
            ("卡数据加密", ["encrypt", "tokenize"]),
            ("访问控制", ["rbac", "mfa"]),
        ],
        "soc2": [
            ("变更管理", ["approval", "review"]),
            ("监控告警", ["alert", "monitor"]),
        ],
    }

    def __init__(self):
        self._results: list[dict[str, Any]] = []

    def compliance_check(self, framework: str,
                         system_description: str
                         ) -> dict[str, Any]:
        rules = self.RULES.get(framework.lower())
        if not rules:
            return {"ok": False, "error": f"未知框架 {framework}"}
        low = system_description.lower()
        results = []
        for requirement, keywords in rules:
            found = [k for k in keywords if k in low]
            status = (ComplianceResult.PASS if found
                      else ComplianceResult.FAIL)
            results.append({
                "requirement": requirement,
                "keywords_found": found,
                "status": status.value,
            })
        passed = sum(1 for r in results
                     if r["status"] == ComplianceResult.PASS.value)
        self._results = results
        return {
            "ok": True,
            "framework": framework.upper(),
            "results": results,
            "score": passed / len(results) if results else 0.0,
        }

    def latest(self) -> list[dict[str, Any]]:
        return list(self._results)


class LegalReasoner:
    """法律推理引擎。"""

    def __init__(self, cases: CaseDatabase | None = None,
                 statutes: RegulationAnalyzer | None = None):
        self.cases = cases or CaseDatabase()
        self.statutes = statutes or RegulationAnalyzer()
        self._cache: dict[str, Argument] = {}

    def legal_reasoning(self, query: str,
                        domain: LegalDomain | None = None
                        ) -> Argument:
        if query in self._cache:
            return self._cache[query]
        precedents = self.cases.precedent_search(query, domain, 5)
        applicable = self.statutes.find_applicable(query)
        arg = Argument()
        arg.premise = query
        arg.rule = (f"依据 {applicable[0].statute_id}"
                    if applicable else "依据一般法理原则")
        arg.supporting_cases = [c.case_id for c in precedents]
        if precedents:
            arg.conclusion = (
                f"参照 {precedents[0].name}，"
                f"可类推适用：{precedents[0].holding[:60]}")
            base = 0.4
            for c in precedents:
                base += c.importance * 0.05
        else:
            arg.conclusion = "无明确判例，需依体系解释"
            base = 0.2
        if applicable:
            base += 0.15
        arg.strength = min(1.0, base)
        if len(precedents) < 2:
            arg.counter_arguments.append("判例数量不足，存在类推风险")
        if not applicable:
            arg.counter_arguments.append("未检索到直接适用法规")
        self._cache[query] = arg
        return arg

    def argument_builder(self, position: str,
                         facts: str) -> dict[str, Any]:
        supporting = self.cases.case_match(facts)
        counter = self.cases.case_match(
            "反例 " + facts, MATCH_THRESHOLD * 0.6)
        weaknesses = []
        if len(supporting) < 3:
            weaknesses.append("支持判例少于3个")
        if not supporting:
            weaknesses.append("无支持判例，论证基础薄弱")
        return {
            "position": position,
            "supporting_strength": round(
                sum(s for _, s in supporting) / max(1, len(supporting)), 4),
            "supporting_count": len(supporting),
            "counter_count": len(counter),
            "weaknesses": weaknesses,
            "recommendation": ("论证充分" if len(supporting) >= 3
                               else "需补充判例支撑"),
        }

    def sentencing_range(self, case_id: str) -> dict[str, Any]:
        case = self.cases.get(case_id)
        if not case:
            return {"ok": False}
        base = {"刑事": (3, 15), "民事": (0, 0),
                "商业": (0, 0)}.get(case.domain.value, (0, 0))
        factor = min(2.0, 0.5 + case.importance * 0.3)
        return {
            "ok": True,
            "domain": case.domain.value,
            "min_years": base[0] * factor,
            "max_years": base[1] * factor,
            "prior_outcome": case.outcome,
        }

    def liability_assess(self, facts: str) -> dict[str, Any]:
        matched = self.cases.case_match(facts, 0.3)
        if not matched:
            return {"liability": "unclear", "confidence": 0.0}
        top_case, sim = matched[0]
        return {
            "liability": ("liable" if sim > 0.6 else "contestable"),
            "confidence": round(sim, 4),
            "basis": top_case.name,
            "similar_cases": len(matched),
        }

    def contract_verify(self, contract_text: str) -> dict[str, Any]:
        ex = ClauseExtractor()
        clauses = ex.clause_extract(contract_text)
        missing = ex.missing_mandatory()
        conflicts = self._find_conflicts(clauses)
        risk = "low"
        if missing:
            risk = "high"
        if conflicts:
            risk = "critical"
        return {
            "ok": risk != "critical",
            "clauses_found": len(clauses),
            "kinds": [c.kind.value for c in clauses],
            "missing_mandatory": [m.value for m in missing],
            "conflicts": conflicts,
            "risk_level": risk,
            "hash": hashlib.sha256(
                contract_text.encode()).hexdigest()[:16],
        }

    def _find_conflicts(self, clauses: list[Clause]
                        ) -> list[str]:
        conflicts = []
        kinds = [c.kind for c in clauses]
        if (ContractClause.LIABILITY in kinds
                and ContractClause.INDEMNITY in kinds):
            liab = next(c for c in clauses
                        if c.kind == ContractClause.LIABILITY)
            indem = next(c for c in clauses
                         if c.kind == ContractClause.INDEMNITY)
            if "无限" in indem.text and "上限" in liab.text:
                conflicts.append("赔偿无限 与 责任上限 条款冲突")
        if (ContractClause.TERMINATION in kinds
                and ContractClause.GOVERNING_LAW in kinds):
            term = next(c for c in clauses
                        if c.kind == ContractClause.TERMINATION)
            law = next(c for c in clauses
                       if c.kind == ContractClause.GOVERNING_LAW)
            if "任意" in term.text and "不得" in law.text:
                conflicts.append("任意终止权 与 管辖约定 冲突")
        return conflicts


class LegalEngine:
    """计算法学统一入口。"""

    def __init__(self):
        self.cases = CaseDatabase()
        self.statutes = RegulationAnalyzer()
        self.reasoner = LegalReasoner(self.cases, self.statutes)
        self.auditor = SmartContractAuditor()
        self.compliance = ComplianceChecker()

    def seed(self) -> int:
        samples = [
            LegalCase(
                case_id="CN-2021-001", name="腾讯诉搜狗不正当竞争",
                domain=LegalDomain.COMMERCIAL,
                court="最高人民法院", decided_at=time.time(),
                facts="被告在搜索服务中劫持流量并篡改结果页面",
                holding="网络服务提供者不得以技术手段干扰同业",
                ratio="未正当商业行为破坏竞争秩序应承担连带责任",
                statutes=["反不正当竞争法"],
                outcome="胜诉", importance=5,
            ),
            LegalCase(
                case_id="CN-2020-015", name="著作权侵权责任认定",
                domain=LegalDomain.IP,
                court="北京市高级人民法院",
                decided_at=time.time(),
                facts="未经许可复制发行他人作品并获利",
                holding="复制发行行为构成侵权应赔偿",
                ratio="实质性相似加接触即构成侵权",
                statutes=["著作权法"], outcome="胜诉", importance=4,
            ),
            LegalCase(
                case_id="CN-2019-088", name="合同违约金过高调整",
                domain=LegalDomain.CIVIL,
                court="上海市第二中级人民法院",
                decided_at=time.time(),
                facts="约定违约金超过实际损失百分之三十",
                holding="违约金超过损失百分之三十可请求调减",
                ratio="以履行损失为基准审查违约金比例",
                statutes=["合同法"], outcome="部分支持", importance=3,
            ),
        ]
        for c in samples:
            self.cases.add_case(c)
        statutes = [
            Statute(statute_id="反不正当竞争法",
                    title="反不正当竞争法", jurisdiction="CN",
                    article="第二条",
                    text="经营者不得以不正当手段从事市场竞争",
                    keywords=["不正当竞争", "流量劫持"],
                    penalty="民事赔偿",
                    effective_from=time.time() - 86400 * 3650),
            Statute(statute_id="著作权法",
                    title="中华人民共和国著作权法",
                    jurisdiction="CN", article="第五十二条",
                    text="未经许可复制发行他人作品的应当承担停止侵害"
                         "消除影响赔礼道歉赔偿损失等民事责任",
                    keywords=["著作权", "复制发行", "侵权"],
                    penalty="民事赔偿+行政处罚",
                    effective_from=time.time() - 86400 * 3650),
            Statute(statute_id="刑法-侵犯知识产权",
                    title="刑法第二百一十四条", jurisdiction="CN",
                    article="第二百一十四条",
                    text="销售明知是侵犯著作权的作品的处三年以下有期徒刑",
                    keywords=["销售", "侵权", "著作权"],
                    penalty="三年以下有期徒刑或拘役并处罚金",
                    effective_from=time.time() - 86400 * 3650),
        ]
        for s in statutes:
            self.statutes.add_statute(s)
        return len(samples) + len(statutes)


def create_legal_engine() -> LegalEngine:
    engine = LegalEngine()
    engine.seed()
    return engine


def case_match(facts: str, threshold: float = MATCH_THRESHOLD
               ) -> list[tuple[str, float]]:
    engine = create_legal_engine()
    return [(c.name, s) for c, s in
            engine.cases.case_match(facts, threshold)]


def precedent_search(query: str, limit: int = 5
                     ) -> list[dict[str, Any]]:
    return [c.to_dict() for c in
            create_legal_engine().cases.precedent_search(
                query, limit=limit)]


def regulation_analyze(statute_id: str) -> dict[str, Any]:
    return create_legal_engine().statutes.regulation_analyze(
        statute_id)


def clause_extract(contract_text: str) -> list[dict[str, str]]:
    ex = ClauseExtractor()
    return [{"kind": c.kind.value, "text": c.text}
            for c in ex.clause_extract(contract_text)]


def contract_verify(contract_text: str) -> dict[str, Any]:
    return create_legal_engine().reasoner.contract_verify(
        contract_text)


def compliance_check(framework: str,
                     system_description: str) -> dict[str, Any]:
    return create_legal_engine().compliance.compliance_check(
        framework, system_description)


def sentencing_range(case_id: str) -> dict[str, Any]:
    return create_legal_engine().reasoner.sentencing_range(case_id)


def liability_assess(facts: str) -> dict[str, Any]:
    return create_legal_engine().reasoner.liability_assess(facts)


def legal_reasoning(query: str) -> dict[str, Any]:
    arg = create_legal_engine().reasoner.legal_reasoning(query)
    return {
        "premise": arg.premise, "rule": arg.rule,
        "conclusion": arg.conclusion,
        "strength": round(arg.strength, 4),
        "counter_arguments": arg.counter_arguments,
        "supporting_cases": arg.supporting_cases,
    }


def argument_builder(position: str,
                     facts: str) -> dict[str, Any]:
    return create_legal_engine().reasoner.argument_builder(
        position, facts)


def smart_contract_audit(source: str) -> dict[str, Any]:
    return create_legal_engine().auditor.audit(source)


def _register_computational_law(builtins: dict) -> None:
    builtins["case_match"] = case_match
    builtins["precedent_search"] = precedent_search
    builtins["regulation_analyze"] = regulation_analyze
    builtins["clause_extract"] = clause_extract
    builtins["contract_verify"] = contract_verify
    builtins["compliance_check"] = compliance_check
    builtins["sentencing_range"] = sentencing_range
    builtins["liability_assess"] = liability_assess
    builtins["legal_reasoning"] = legal_reasoning
    builtins["argument_builder"] = argument_builder
    builtins["smart_contract_audit"] = smart_contract_audit
    builtins["创建法学引擎"] = create_legal_engine


__all__ = [
    "LegalDomain", "ReasoningRule", "ContractClause",
    "ComplianceResult", "LegalCase", "Statute", "Clause",
    "Argument", "CaseDatabase", "RegulationAnalyzer",
    "ClauseExtractor", "SmartContractAuditor",
    "ComplianceChecker", "LegalReasoner", "LegalEngine",
    "create_legal_engine", "case_match", "precedent_search",
    "regulation_analyze", "clause_extract", "contract_verify",
    "compliance_check", "sentencing_range", "liability_assess",
    "legal_reasoning", "argument_builder", "smart_contract_audit",
    "_register_computational_law",
]
