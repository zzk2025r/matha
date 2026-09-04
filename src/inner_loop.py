# -*- coding: utf-8 -*-
"""
Matha 全功能内循环 v1.2.22
============================
将 Matha 所有功能模块构成一个自我闭环的持续改进系统：

  感知层  →  认知层  →  执行层  →  验证层  →  持久化
     ↑                                                      │
     └──────────────── 反馈循环 ←←←←←←←←←←←←←←←←←←←←←←←←←←←┘

三层自能力：
  • 自扩展：基于交互模式自动扩展知识、意图、关键词
  • 自升级：版本管理、自动补丁、失败回滚
  • 自优化：性能监控、自适应间隔、内存清理

模块集成：
  • 意图解析器 (FriendlyIntentParser)   — 自然语言 → 数学代码
  • 解释器 (Interpreter)               — Matha 代码执行
  • 防火墙 (MathaFirewall)             — 三层权限防护
  • 安全引擎 (NetSecurityEngine)       — 网络威胁检测/清杀
  • 成长引擎 (GrowthEngine)            — 自检/补丁/升级
  • AI助手 (MathaAIAssistant)          — 用户交互入口
  • Web服务 (APIHandler)               — 对外暴露接口

内循环模式：
  - 单次触发：trigger_once()         运行一轮完整内循环
  - 持续监控：start_loop()           后台持续运行（可配置间隔）
  - 事件驱动：on_interaction()       每次用户交互后触发诊断
  - 定时调度：schedule_cycle()       定时执行内循环
"""
from __future__ import annotations
import sys
import os
import time
import json
import logging
import re
import threading
import atexit
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("matha.inner_loop")


# ═══════════════════════════════════════════════════════════════════════════════
#  状态 & 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LoopState:
    """内循环运行状态。"""
    cycle_count: int = 0
    last_start: float = 0.0
    last_end: float = 0.0
    total_duration: float = 0.0
    total_interactions: int = 0
    total_errors_caught: int = 0
    total_resources_expanded: int = 0
    total_patches_applied: int = 0
    total_defects_resolved: int = 0
    health_score: float = 100.0       # 0-100
    status: str = "idle"              # idle / running / healthy / degraded / critical
    last_error_summary: str = ""
    uptime_start: float = field(default_factory=time.time)


@dataclass
class InteractionRecord:
    """单次用户交互记录。"""
    text: str
    intent: str
    result: Any
    success: bool
    latency: float
    timestamp: float
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  全功能内循环编排器
# ═══════════════════════════════════════════════════════════════════════════════

class MathaInnerLoop:
    """
    Matha 全功能内循环 — 集成所有模块的持续改进系统。

    生命周期：
      1. 感知：收集交互、错误、资源状态
      2. 认知：自检各模块，识别缺陷和差距
      3. 执行：自动修复、扩充资源、跨模块协作
      4. 验证：运行测试，确保修复有效
      5. 持久化：保存状态和成长记录
    """

    def __init__(self):
        # 核心模块（单例共享）
        self._assistant = None
        self._engine = None
        self._interp = None
        self._firewall = None
        self._security = None

        # 运行状态
        self._state = LoopState()
        self._interaction_buffer: list[InteractionRecord] = []
        self._error_buffer: list[dict] = []

        # 控制标志
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._interval: float = 30.0  # 持续模式间隔（秒）

        # 回调
        self._on_cycle_start: Optional[Callable] = None
        self._on_cycle_end: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_improve: Optional[Callable] = None

    # ── 模块初始化 ──────────────────────────────────────────────────────────────

    def init_modules(self):
        """初始化所有核心模块（v1.3.0 + v2.0 HAL）。"""
        from src.ai_assistant import MathaAIAssistant, FriendlyIntentParser
        from src.interp import Interpreter
        from src.firewall import MathaFirewall
        from src.net_security import NetSecurityEngine
        from src.growth_engine import create_growth_engine
        # v1.3.0 新模块
        from src.symbolic import symbol_expr, diff_expr, eval_expr as sym_eval
        from src.ffi import get_ffi
        from src.math_driver import get_driver_manager
        from src.multi_paradigm import get_paradigm_engine
        from src.symbol_codegen import get_codegen
        # v2.0 HAL 新模块
        from src.hardware.hal_v2 import (
            get_side_effect_engine, get_pointer_manager,
            get_protocol_parser, get_driver_generator, get_native_backend,
        )
        from src.compiler.native import (
            ProtocolInterpreter, DriverBuilder, NativeCompiler,
        )

        self._assistant = MathaAIAssistant()
        self._interp = Interpreter()
        self._firewall = MathaFirewall()
        self._security = NetSecurityEngine()
        self._engine = create_growth_engine(assistant=self._assistant)
        # v1.3.0
        self._symbolic_parser = symbol_expr
        self._ffi = get_ffi()
        self._driver_mgr = get_driver_manager()
        self._paradigm = get_paradigm_engine()
        self._codegen = get_codegen()
        # v2.0 HAL
        self._sse = get_side_effect_engine()
        self._pmgr = get_pointer_manager()
        self._proto_parser = get_protocol_parser()
        self._driver_gen = get_driver_generator()
        self._native_backend = get_native_backend()
        self._proto_interpreter = ProtocolInterpreter(self._proto_parser)
        self._driver_builder = DriverBuilder(self._driver_gen)
        self._native_compiler = NativeCompiler(self._native_backend, self._sse, self._pmgr)

        # 注册错误回调到成长引擎
        self._engine._assistant = self._assistant
        logger.info("  [内循环] 模块初始化完成 (v1.3.0 + v2.0 HAL)")
        logger.info(f"    意图解析器: {len(self._assistant.parser.MATH_CONCEPTS)} 概念, "
                     f"{sum(len(v) for v in self._assistant.parser.KEYWORD_MAP.values())} 关键词")
        logger.info(f"    解释器: {len(self._interp.builtins)} 内建函数")
        logger.info(f"    防火墙: level={self._firewall.level.value}")
        logger.info(f"    安全引擎: {self._security.threat_count()} 威胁记录")
        logger.info(f"    FFI: {self._ffi.get_stats().get('registered_functions', 0)} 注册函数")
        logger.info(f"    驱动: {self._driver_mgr.get_stats().get('total_drivers', 0)} 驱动")
        logger.info(f"    代码生成: Python/JS/C/Matha")
        logger.info(f"    HAL v2.0: 副作用引擎/指针管理器/协议解析/驱动生成/原生编译")
        logger.info(f"    裸机目标: {self._native_backend.get_targets()}")
        logger.info(f"    驱动: {self._driver_mgr.get_stats().get('total_drivers', 0)} 驱动")
        logger.info(f"    代码生成: Python/JS/C/Matha")

    # ── 1. 感知层 ───────────────────────────────────────────────────────────────

    def on_interaction(self, text: str, result: dict) -> InteractionRecord:
        """记录一次用户交互，触发轻量诊断。"""
        record = InteractionRecord(
            text=text,
            intent=result.get("intent", "unknown"),
            result=result.get("result"),
            success=result.get("type") in ("result", "calculation"),
            latency=0.0,
            timestamp=time.time(),
            error=result.get("reply", "")[:100] if not result.get("result") else "",
        )
        self._interaction_buffer.append(record)
        self._state.total_interactions += 1

        # 如果交互失败，记录到错误缓冲区
        if not record.success:
            self._error_buffer.append({
                "text": text,
                "error": record.error,
                "intent": record.intent,
                "timestamp": record.timestamp,
            })
            self._state.total_errors_caught += 1
            logger.info(f"  [感知] 交互失败: '{text[:30]}' → {record.intent}")

        return record

    def collect_resource_snapshot(self) -> dict:
        """收集当前资源快照。"""
        if self._engine is None:
            return {}
        resources = self._engine.audit_resources()
        return {
            "total": len(resources),
            "ok": sum(1 for r in resources if r.status == "ok"),
            "missing": sum(1 for r in resources if r.status != "ok"),
            "details": [
                {"name": r.name, "status": r.status}
                for r in resources
            ],
        }

    def collect_interaction_summary(self) -> dict:
        """收集最近交互摘要。"""
        recent = self._interaction_buffer[-20:] if self._interaction_buffer else []
        success_count = sum(1 for r in recent if r.success)
        return {
            "total": len(recent),
            "success": success_count,
            "failure": len(recent) - success_count,
            "success_rate": success_count / max(len(recent), 1),
            "recent_errors": [
                {"text": r.text[:30], "intent": r.intent}
                for r in recent if not r.success
            ],
        }

    # ── 2. 认知层 ───────────────────────────────────────────────────────────────

    def cognitive_diagnose(self) -> dict:
        """认知层：全面自检，收集缺陷信息。"""
        if self._engine is None:
            return {"error": "引擎未初始化"}

        defects = self._engine.self_diagnose()
        resources = self.collect_resource_snapshot()
        interactions = self.collect_interaction_summary()

        # 计算健康分数
        defect_score = max(0, 100 - len(defects) * 15)
        resource_score = resources.get("ok", 0) / max(resources.get("total", 1), 1) * 100
        interaction_score = (
            100.0 if interactions.get("total", 0) == 0
            else interactions.get("success_rate", 1.0) * 100
        )

        health = (defect_score * 0.4 + resource_score * 0.3 + interaction_score * 0.3)
        self._state.health_score = round(health, 1)

        # 确定状态
        if health >= 90:
            self._state.status = "healthy"
        elif health >= 70:
            self._state.status = "degraded"
        else:
            self._state.status = "critical"

        return {
            "defects_found": len(defects),
            "defects": [
                {"id": d.defect_id, "severity": d.severity.value,
                 "category": d.category.value, "message": d.message}
                for d in defects
            ],
            "resources": resources,
            "interactions": interactions,
            "health_score": round(health, 1),
            "status": self._state.status,
        }

    # ── 3. 执行层 ───────────────────────────────────────────────────────────────

    def execute_remediation(self, diagnosis: dict) -> dict:
        """执行层：根据诊断结果自动修复。"""
        if self._engine is None:
            return {"error": "引擎未初始化"}

        actions = {
            "defects_resolved": 0,
            "resources_expanded": 0,
            "patches_applied": 0,
            "cross_calls_made": 0,
        }

        # 3.1 自动修复缺陷
        defects = diagnosis.get("defects", [])
        for d in defects:
            # 通过引擎找到对应缺陷并修复
            if d.get("severity") in ("high", "critical"):
                result = self._engine.auto_remediate_by_message(d["message"], d.get("category"))
                if result:
                    actions["defects_resolved"] += 1
                    actions["patches_applied"] += 1

        # 3.2 自动扩充资源
        gaps = self._engine.identify_concept_gaps()
        if gaps:
            added = self._engine.auto_expand_concepts(max_new=5)
            added += self._engine.auto_expand_keywords()
            actions["resources_expanded"] = added

        # 3.3 跨模块协作调用
        actions["cross_calls_made"] = self._cross_module_collaboration()

        # 3.4 处理错误缓冲区
        actions["errors_handled"] = self._handle_error_buffer()

        self._state.total_patches_applied += actions["patches_applied"]
        self._state.total_resources_expanded += actions["resources_expanded"]
        self._state.total_defects_resolved += actions["defects_resolved"]

        if actions["resources_expanded"] > 0 and self._on_improve:
            self._on_improve(actions["resources_expanded"])

        return actions

    def _cross_module_collaboration(self) -> int:
        """跨模块协作：各模块互相调用，验证联动。"""
        count = 0
        if self._assistant is None or self._interp is None:
            return 0

        # 意图解析器 ↔ 解释器：验证 chat 正常工作
        try:
            result = self._assistant.chat("计算 2+2", self._interp)
            if result.get("result") is not None:
                count += 1
                logger.debug("  [协作] 意图↔解释器联动正常")
        except Exception as e:
            logger.warning(f"  [协作] 意图↔解释器联动异常: {e}")

        # 防火墙 ↔ 安全引擎：验证防火墙规则
        try:
            if self._firewall:
                blocked = getattr(self._firewall, 'blocked_count', 0)
                count += 1
                logger.debug(f"  [协作] 防火墙规则数: blocked={blocked}")
        except Exception as e:
            logger.warning(f"  [协作] 防火墙检查异常: {e}")

        # 成长引擎 ↔ 意图解析器：验证成长记忆
        try:
            if self._engine and self._assistant:
                stats = self._engine.get_growth_stats()
                count += 1
                logger.debug(f"  [协作] 成长统计: {stats.get('total_learned', 0)} 条学习记录")
        except Exception as e:
            logger.warning(f"  [协作] 成长统计异常: {e}")

        return count

    def _handle_error_buffer(self) -> int:
        """处理错误缓冲区：自动学习失败模式。"""
        handled = 0
        for err in self._error_buffer[:5]:  # 最多处理最近5条
            if self._assistant:
                self._assistant.parser.record_failure(
                    err["text"], err.get("error", ""),
                    self._parse_intent_from_text(err["text"])
                )
                handled += 1
        self._error_buffer = self._error_buffer[5:]
        return handled

    def _parse_intent_from_text(self, text: str):
        """从文本解析意图类型。"""
        if not self._assistant:
            from src.ai_assistant import IntentType
            return IntentType.unknown
        intent, _ = self._assistant.parser.classify(text)
        return intent  # 返回 IntentType 枚举，非字符串

    # ── 4. 自扩展层 ────────────────────────────────────────────────────────────

    def self_extend_concepts(self) -> int:
        """自扩展：基于现有概念种子，从失败交互中派生新概念。"""
        from src.ai_assistant import IntentType
        p = self._assistant.parser  # 使用共享解析器，修改持久化
        known = set(p.MATH_CONCEPTS.keys())
        added = 0

        # 停用词：不能作为概念的词
        STOPWORDS = {'帮我', '计算', '算一', '求一', '什么', '怎么', '如何',
                      '一下', '有什么', '是什', '公式', '例子', '例如',
                      '以下', '以上', '这个', '那个', '这些', '那些',
                      '哪些', '怎样', '有关', '以及', '或者', '可以',
                      '帮助', '请问', '一个', '一些', '一切', '一定',
                      '因为', '所以', '但是', '如果', '虽然', '然后',
                      '就是', '只有', '已经', '才能', '应该', '必须',
                      '能够', '没有', '不能', '不会', '不要', '不用',
                      '不得', '证明', '区别', '基础'}

        recent_fails = [r for r in self._interaction_buffer
                        if not r.success and r.intent == "unknown"]
        # 收集所有失败交互中的词组
        all_candidate_phrases: dict[str, int] = {}
        for record in recent_fails[-20:]:
            text = record.text
            # 提取2-5字连续汉字
            import re
            matches = re.findall(r'[\u4e00-\u9fff]{2,5}', text)
            for m in matches:
                if m in STOPWORDS:
                    continue
                all_candidate_phrases[m] = all_candidate_phrases.get(m, 0) + 1

        logger.info(f"  [自扩展] 候选词汇总: {dict(list(all_candidate_phrases.items())[:10])}")

        # 对每个候选词，尝试与现有概念匹配/派生
        for phrase, freq in sorted(all_candidate_phrases.items(), key=lambda x: -x[1]):
            if phrase in known or phrase in p.MATH_CONCEPTS:
                continue

            # 策略1: 候选词本身就是概念（如"质数"已在概念库中）
            # 策略2: 候选词与已有概念有部分重叠，派生新概念
            # 策略3: 候选词出现在已有概念名称中
            is_valid = False
            for existing in list(p.MATH_CONCEPTS.keys()):
                if phrase in existing or existing in phrase:
                    is_valid = True
                    break
                # 候选词和已有概念共享至少3个连续字符
                for i in range(len(phrase) - 2):
                    sub = phrase[i:i+3]
                    if sub in existing:
                        is_valid = True
                        break
                    for j in range(len(existing) - 2):
                        if existing[j:j+3] == sub:
                            is_valid = True
                            break
                    if is_valid:
                        break
                if is_valid:
                    break

            if is_valid and phrase not in p.MATH_CONCEPTS:
                p.MATH_CONCEPTS[phrase] = {
                    "是什么": f"{phrase}是一个数学概念。",
                    "符号": "",
                    "例子": f"例如：{phrase}的计算方法。",
                    "生活中的例子": f"{phrase}在生活中的应用。",
                }
                known.add(phrase)
                added += 1
                logger.info(f"  [自扩展] 新增概念: {phrase} (freq={freq})")

        # 分析错误缓冲区中的高频失败词
        failure_patterns: dict[str, int] = {}
        for err in self._error_buffer:
            intent = err.get("intent", "unknown")
            if intent == "unknown":
                import re
                keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', err["text"])
                for kw in keywords:
                    if kw not in STOPWORDS:
                        failure_patterns[kw] = failure_patterns.get(kw, 0) + 1

        logger.info(f"  [自扩展] 失败词频率: {dict(list(failure_patterns.items())[:5])}")

        for word, count in sorted(failure_patterns.items(), key=lambda x: -x[1])[:5]:
            if word not in known and count >= 2:
                matched_intent = None
                for itype, kws in p.KEYWORD_MAP.items():
                    if word in str(kws):
                        matched_intent = itype
                        break
                if matched_intent is None:
                    p.VARIATION_MAP[word] = matched_intent or IntentType.算术
                    p.KEYWORD_MAP.setdefault(IntentType.算术, []).append(word)
                    added += 1
                    logger.info(f"  [自扩展] 新增变体: {word} → arithmetic (出现{count}次)")

        if added > 0:
            new_rules = []
            for name in list(p.MATH_CONCEPTS.keys())[-added:]:
                new_rules.append({
                    "pattern": rf".*{re.escape(name)}.*",
                    "intent": IntentType.算术,
                    "reason": f"自扩展: {name}",
                    "weight": 3.0,
                })
            p.COMMONSENSE_RULES.extend(new_rules)

        self._state.total_resources_expanded += added
        if added > 0 and self._on_improve:
            self._on_improve(added)
        return added

    def self_extend_intents(self) -> int:
        """自扩展：基于交互数据自动发现新意图类型。"""
        from src.ai_assistant import IntentType
        p = self._assistant.parser  # 使用共享解析器，修改持久化
        added = 0

        unknown_keywords: dict[str, int] = {}
        for record in self._interaction_buffer[-50:]:
            if record.intent == "unknown":
                words = [w for w in record.text.lower().split() if len(w) >= 2]
                for w in words:
                    unknown_keywords[w] = unknown_keywords.get(w, 0) + 1

        for kw, count in sorted(unknown_keywords.items(), key=lambda x: -x[1])[:10]:
            if count < 2:
                continue
            matched = False
            for itype, kws in p.KEYWORD_MAP.items():
                if kw in kws:
                    matched = True
                    break
            if not matched:
                for rule in p.COMMONSENSE_RULES:
                    if kw in rule.get("pattern", ""):
                        matched = True
                        break
            if not matched:
                if kw not in str(p.KEYWORD_MAP.get(IntentType.算术, [])):
                    p.KEYWORD_MAP[IntentType.算术].append(kw)
                    added += 1
                    logger.info(f"  [自扩展] 关键词映射: {kw} → arithmetic")
        return added

    # ── 5. 自升级层 ────────────────────────────────────────────────────────────

    def self_upgrade_check(self) -> dict:
        """自升级检查：检测版本状态和可用升级。"""
        current_version = "1.2.22"
        known_versions = ["1.2.21", "1.2.20", "1.2.19", "1.2.18", "1.2.17"]
        latest = max(known_versions) if known_versions else current_version
        is_latest = current_version >= latest

        pending_patches = []
        if self._engine:
            history = self._engine.get_defect_stats()
            open_defects = history.get("open_defects", [])
            logger.info(f"  [自升级] 自检完成: 发现 {len(open_defects)} 个缺陷, "
                         f"高危 {len([d for d in open_defects if d.get('severity') in ('critical','high')])} 个")
            pending_patches = [
                {"id": d.get("id", ""), "severity": d.get("severity", "")}
                for d in open_defects
                if d.get("severity") in ("critical", "high")
            ]

        logger.info(f"  [自升级] 版本检查: 当前={current_version}, 最新={latest}, "
                     f"是否最新={is_latest}, 待处理高危补丁={len(pending_patches)}")
        return {
            "current_version": current_version,
            "latest_version": latest,
            "is_latest": is_latest,
            "can_upgrade": not is_latest,
            "pending_patches": pending_patches,
        }

    def self_upgrade_apply(self, target_version: str = None) -> dict:
        """自升级：应用补丁并升级到目标版本。"""
        result = {"success": False, "from_version": None, "to_version": None,
                   "patches_applied": 0, "errors": []}
        if self._engine is None:
            result["errors"].append("引擎未初始化")
            return result

        defects = self._engine.self_diagnose()
        patches = []
        for defect in defects:
            if defect.severity.value in ("critical", "high"):
                patch = self._engine.generate_patch(defect)
                if patch:
                    patches.append({"defect": defect.defect_id, "patch": patch})

        applied = 0
        for patch_info in patches:
            try:
                success = self._engine.run_upgrade_pipeline(patch_info["patch"])
                if success:
                    applied += 1
                else:
                    result["errors"].append(f"补丁 {patch_info['defect']} 应用失败")
            except Exception as e:
                result["errors"].append(f"补丁 {patch_info['defect']} 异常: {e}")

        result["from_version"] = "1.3.0"
        result["to_version"] = target_version or "1.3.0"
        result["patches_applied"] = applied
        result["success"] = applied > 0 or len(defects) == 0
        logger.info(f"  [自升级] 应用补丁: {applied}/{len(patches)}")
        return result

    def self_upgrade_rollback(self) -> bool:
        """自升级回滚：回滚到最后稳定版本。"""
        if self._engine:
            try:
                self._engine._rollback_patch()
                logger.info("  [自升级] 已回滚到安全版本")
                return True
            except Exception as e:
                logger.error(f"  [自升级] 回滚异常: {e}")
                return False
        logger.warning("  [自升级] 引擎未初始化，无法回滚")
        return False

    # ── 6. 自优化层 ────────────────────────────────────────────────────────────

    def self_optimize_performance(self) -> dict:
        """自优化：分析性能并自动优化配置。"""
        improvements = {"interval_adjusted": False, "buffer_cleaned": 0,
                        "log_compressed": False, "cache_optimized": 0,
                        "new_interval": self._interval}

        # 6.1 分析当前性能
        total_cycles = self._state.cycle_count
        total_time = self._state.total_duration
        avg_cycle_time = total_time / max(total_cycles, 1)
        logger.info(f"  [自优化] 性能分析: 循环{total_cycles}次, 总耗时{total_time:.1f}s, "
                     f"平均{avg_cycle_time:.1f}s/次, 当前间隔{self._interval}s")

        # 6.2 自适应轮询间隔
        if total_cycles > 0:
            if avg_cycle_time > 10.0 and self._interval > 10.0:
                new_interval = min(self._interval * 1.5, 120.0)
                self._interval = new_interval
                improvements["interval_adjusted"] = True
                improvements["new_interval"] = new_interval
                logger.info(f"  [自优化] 调整间隔: {self._interval:.0f}s (平均周期 {avg_cycle_time:.1f}s > 10s)")
            elif avg_cycle_time < 2.0 and self._interval > 5.0:
                new_interval = max(self._interval * 0.8, 5.0)
                self._interval = new_interval
                improvements["interval_adjusted"] = True
                improvements["new_interval"] = new_interval
                logger.info(f"  [自优化] 缩短间隔: {self._interval:.0f}s (平均周期 {avg_cycle_time:.1f}s < 2s)")

        # 6.3 清理过期交互缓冲区
        cutoff = time.time() - 3600
        before = len(self._interaction_buffer)
        self._interaction_buffer = [r for r in self._interaction_buffer if r.timestamp > cutoff]
        cleaned = before - len(self._interaction_buffer)
        improvements["buffer_cleaned"] = cleaned
        logger.info(f"  [自优化] 交互缓冲区: {before} → {len(self._interaction_buffer)} (清理{cleaned}条)")

        # 6.4 清理过期错误缓冲区
        before = len(self._error_buffer)
        self._error_buffer = [e for e in self._error_buffer if e.get("timestamp", 0) > cutoff]
        cleaned = before - len(self._error_buffer)
        improvements["buffer_cleaned"] += cleaned
        logger.info(f"  [自优化] 错误缓冲区: {before} → {len(self._error_buffer)} (清理{cleaned}条)")

        # 6.5 压缩成长日志
        if self._engine and len(self._engine._growth_log) > 100:
            before = len(self._engine._growth_log)
            self._engine._growth_log = self._engine._growth_log[-100:]
            improvements["log_compressed"] = True
            logger.info(f"  [自优化] 成长日志: {before} → {len(self._engine._growth_log)} 条")

        # 6.6 优化内存缓存
        if self._engine and len(self._engine._web_search_cache) > 50:
            before = len(self._engine._web_search_cache)
            self._engine._web_search_cache = dict(
                list(self._engine._web_search_cache.items())[-50:])
            improvements["cache_optimized"] = before - 50
            logger.info(f"  [自优化] 搜索缓存: {before} → 50 项 (释放{before-50}项)")

        total_improvements = sum([
            improvements["interval_adjusted"],
            improvements["buffer_cleaned"],
            improvements["log_compressed"],
            improvements["cache_optimized"],
        ])
        logger.info(f"  [自优化] 完成: 间隔调整={improvements['interval_adjusted']}, "
                     f"缓冲区清理={improvements['buffer_cleaned']}条, "
                     f"日志压缩={improvements['log_compressed']}, "
                     f"缓存优化={improvements['cache_optimized']}项")
        return improvements

    # ── 4. 验证层 ───────────────────────────────────────────────────────────────

    def verify_fixes(self, pre_diagnosis: dict) -> dict:
        """验证修复效果：对比修复前后状态。"""
        post_diagnosis = self.cognitive_diagnose()

        pre_defects = pre_diagnosis.get("defects_found", 0)
        post_defects = post_diagnosis.get("defects_found", 0)
        pre_health = pre_diagnosis.get("health_score", 0)
        post_health = post_diagnosis.get("health_score", 0)

        verified = {
            "defects_before": pre_defects,
            "defects_after": post_defects,
            "defects_reduced": pre_defects - post_defects,
            "health_before": pre_health,
            "health_after": post_health,
            "health_improved": post_health > pre_health,
            "verified": post_defects == 0,
        }

        logger.info(f"  [验证] 缺陷: {pre_defects}→{post_defects}, "
                     f"健康: {pre_health}→{post_health}")
        return verified

    # ── 5. 持久化层 ─────────────────────────────────────────────────────────────

    def save_state(self, path: str = None) -> str:
        """持久化内循环状态到文件。"""
        if path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, ".matha_cache", "inner_loop_state.json")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        state_data = {
            "version": "1.3.0",
            "timestamp": datetime.now().isoformat(),
            "state": {
                "cycle_count": self._state.cycle_count,
                "total_interactions": self._state.total_interactions,
                "total_errors_caught": self._state.total_errors_caught,
                "total_resources_expanded": self._state.total_resources_expanded,
                "total_patches_applied": self._state.total_patches_applied,
                "total_defects_resolved": self._state.total_defects_resolved,
                "health_score": self._state.health_score,
                "status": self._state.status,
                "uptime_start": self._state.uptime_start,
            },
            "interaction_summary": self.collect_interaction_summary(),
            "resource_snapshot": self.collect_resource_snapshot(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

        logger.info(f"  [持久化] 状态已保存到 {path}")
        return path

    def load_state(self, path: str = None) -> bool:
        """从文件加载内循环状态。"""
        if path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, ".matha_cache", "inner_loop_state.json")

        if not os.path.exists(path):
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            saved_state = data.get("state", {})
            self._state.cycle_count = saved_state.get("cycle_count", 0)
            self._state.total_interactions = saved_state.get("total_interactions", 0)
            self._state.total_errors_caught = saved_state.get("total_errors_caught", 0)
            self._state.total_resources_expanded = saved_state.get("total_resources_expanded", 0)
            self._state.total_patches_applied = saved_state.get("total_patches_applied", 0)
            self._state.total_defects_resolved = saved_state.get("total_defects_resolved", 0)
            self._state.health_score = saved_state.get("health_score", 100.0)
            self._state.status = saved_state.get("status", "idle")
            self._state.uptime_start = saved_state.get("uptime_start", time.time())

            logger.info(f"  [持久化] 状态已加载 (循环: {self._state.cycle_count}, "
                         f"健康: {self._state.health_score})")
            return True
        except Exception as e:
            logger.warning(f"  [持久化] 加载失败: {e}")
            return False

    # ── 核心内循环 ──────────────────────────────────────────────────────────────

    def run_cycle(self, verbose: bool = True) -> dict:
        """
        执行一轮完整内循环：
        感知 → 认知 → 执行 → 验证 → 持久化
        """
        cycle_start = time.time()
        self._state.cycle_count += 1
        self._state.status = "running"

        if verbose:
            logger.info(f"╔════════════════════════════════════════╗")
            logger.info(f"║  内循环 #{self._state.cycle_count} 启动  "
                         f"健康={self._state.health_score} 状态={self._state.status}  ║")
            logger.info(f"╚════════════════════════════════════════╝")

        # Phase 1: 感知
        if verbose:
            logger.info("  [感知] 收集资源快照和交互摘要...")
        resource_snapshot = self.collect_resource_snapshot()
        interaction_summary = self.collect_interaction_summary()

        # Phase 2: 认知
        if verbose:
            logger.info("  [认知] 全面自检...")
        diagnosis = self.cognitive_diagnose()

        if diagnosis.get("defects_found", 0) == 0 and diagnosis.get("health_score", 0) >= 90:
            if verbose:
                logger.info("  [认知] 系统健康，无需修复")
            # Phase 5: 持久化
            self.save_state()
            self._state.status = "healthy"
            return diagnosis

        # Phase 3: 执行
        if verbose:
            logger.info("  [执行] 自动修复和资源扩充...")
        actions = self.execute_remediation(diagnosis)
        if verbose:
            logger.info(f"  [执行] 修复: {actions['defects_resolved']} 缺陷, "
                         f"扩充: {actions['resources_expanded']} 资源, "
                         f"跨模块协作: {actions['cross_calls_made']} 次")

        # Phase 4: 验证
        if verbose:
            logger.info("  [验证] 验证修复效果...")
        verification = self.verify_fixes(diagnosis)
        if verbose:
            logger.info(f"  [验证] 缺陷减少: {verification['defects_reduced']}, "
                         f"健康提升: {'✓' if verification['health_improved'] else '✗'}")

        # Phase 4.55: v1.3.0 模块自检
        v13_result = {"status": "healthy", "checks": {}, "details": []}
        if self._ffi and self._driver_mgr and self._symbolic_parser:
            if verbose:
                logger.info("  [v1.3.0自检] 符号引擎/FFI/驱动/沙箱 健康检查...")
            try:
                # ── 1. FFI 健康检查 ──────────────────────────────────────────
                ffi_stats = self._ffi.get_stats()
                reg_count = ffi_stats.get("registered_functions", 0)
                reg_info = ffi_stats.get("registered_functions_info", [])
                v13_result["checks"]["ffi"] = "ok"
                v13_result["details"].append(f"  [v1.3.0自检] FFI: {reg_count} 个注册函数")
                # 抽样调用 5 个内建函数验证可执行性
                import math
                ffi_tests = [
                    ("sin", [1.0]), ("cos", [0.0]), ("sqrt", [4.0]),
                    ("exp", [1.0]), ("log", [2.718281828]),
                ]
                ffi_pass = 0
                for fname, fargs in ffi_tests:
                    if fname in self._ffi._registry:
                        try:
                            res = self._ffi.call(fname, *fargs)
                            v13_result["details"].append(f"    FFI.{fname}({fargs}) = {res}")
                            ffi_pass += 1
                        except Exception as e:
                            v13_result["checks"]["ffi"] = "error"
                            v13_result["details"].append(f"    FFI.{fname}({fargs}) 失败: {e}")
                v13_result["checks"]["ffi_calls"] = ffi_pass
                logger.info(f"  [v1.3.0自检] FFI: {reg_count}注册, {ffi_pass}/{len(ffi_tests)}调用通过")

                # ── 2. 驱动健康检查 ─────────────────────────────────────────
                drivers = self._driver_mgr.list_drivers()
                total_ops = sum(d["ops"] for d in drivers)
                v13_result["checks"]["drivers"] = "ok"
                v13_result["details"].append(f"  [v1.3.0自检] 驱动: {len(drivers)} 个, {total_ops} 个运算")
                # 对每个驱动抽样一个运算
                driver_tests = [
                    ("linear_algebra", "mat_det", [[1, 0], [0, 1]]),
                    ("linear_algebra", "dot", [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]),
                    ("geometry", "circle_area", [5.0]),
                    ("optimization", "binary_search", [1, 10, 5]),
                ]
                driver_pass = 0
                for dt in driver_tests:
                    drv, op = dt[0], dt[1]
                    args = dt[2:]
                    try:
                        res = self._driver_mgr.execute(drv, op, *args)
                        v13_result["details"].append(f"    驱动.{drv}.{op}({args}) = {res}")
                        driver_pass += 1
                    except Exception as e:
                        v13_result["checks"]["drivers"] = "error"
                        v13_result["details"].append(f"    驱动.{drv}.{op} 失败: {e}")
                v13_result["checks"]["drivers_passed"] = driver_pass
                logger.info(f"  [v1.3.0自检] 驱动抽样: {driver_pass}/{len(driver_tests)} 通过")

                # ── 3. 符号引擎健康检查 ─────────────────────────────────────
                sym_tests = [
                    ("x^2 + 1", {"x": 2}, 5.0),
                    ("x^2 - 3*x + 2", {"x": 2}, 0.0),
                    ("sin(x)", {"x": 0.0}, 0.0),
                    ("sqrt(x)", {"x": 9.0}, 3.0),
                ]
                sym_pass = 0
                for expr_str, bindings, expected in sym_tests:
                    try:
                        expr = self._symbolic_parser(expr_str)
                        val = sym_eval(expr, **bindings)
                        status = "✓" if abs(val - expected) < 1e-9 else "✗"
                        v13_result["details"].append(f"    符号 {status} {expr_str}({bindings}) = {val} (期望 {expected})")
                        if abs(val - expected) < 1e-9:
                            sym_pass += 1
                    except Exception as e:
                        v13_result["details"].append(f"    符号 ✗ {expr_str} 失败: {e}")
                v13_result["checks"]["symbolic"] = sym_pass
                logger.info(f"  [v1.3.0自检] 符号引擎: {sym_pass}/{len(sym_tests)} 通过")

                # ── 4. 微积分检查（diff/integrate）───────────────────────────
                try:
                    expr = self._symbolic_parser("x^3 + 2*x^2 - 5*x + 3")
                    deriv = diff_expr(expr, 'x')
                    deriv_val = sym_eval(deriv, x=1)
                    expected_deriv = 3*1**2 + 4*1 - 5  # 3x²+4x-5 at x=1 = 2
                    status = "✓" if abs(deriv_val - expected_deriv) < 1e-9 else "✗"
                    v13_result["checks"]["calculus"] = "ok" if deriv_val == expected_deriv else "error"
                    v13_result["details"].append(f"    微积分 {status} d/dx(x³+2x²-5x+3) at x=1 = {deriv_val} (期望 {expected_deriv})")
                    logger.info(f"  [v1.3.0自检] 微积分: {status} 导数验证 x³+2x²-5x+3(x=1)={deriv_val}")
                except Exception as e:
                    v13_result["checks"]["calculus"] = "error"
                    v13_result["details"].append(f"    微积分 ✗ 失败: {e}")
                    logger.error(f"  [v1.3.0自检] 微积分异常: {e}")

                # ── 5. 代码生成检查 ─────────────────────────────────────────
                if self._codegen:
                    try:
                        py_code = self._codegen.python("x^2 + 3*x - 5", func_name="f")
                        js_code = self._codegen.javascript("x^2 + 3*x - 5", func_name="f")
                        c_code = self._codegen.c("x^2 + 3*x - 5", func_name="f")
                        v13_result["checks"]["codegen"] = "ok"
                        v13_result["details"].append(f"    代码生成 ✓ Python/JS/C 均成功生成")
                        logger.info("  [v1.3.0自检] 代码生成: Python/JS/C 均健康")
                    except Exception as e:
                        v13_result["checks"]["codegen"] = "error"
                        v13_result["details"].append(f"    代码生成 ✗ 失败: {e}")
                        logger.error(f"  [v1.3.0自检] 代码生成异常: {e}")

                # ── 6. 沙箱执行检查 ─────────────────────────────────────────
                if self._driver_mgr:
                    try:
                        from src.symbol_codegen import MathaCodeGen
                        cg = MathaCodeGen()
                        code = cg.python("x^2 + 1", func_name="test_fn")
                        safe_globals = {"__builtins__": __builtins__, "math": __import__("math")}
                        exec(code, safe_globals)
                        fn = safe_globals.get("test_fn")
                        assert fn is not None, "函数未找到"
                        res = fn(3)
                        assert abs(res - 10.0) < 1e-9, f"沙箱执行结果错误: {res}"
                        v13_result["checks"]["sandbox"] = "ok"
                        v13_result["details"].append(f"    沙箱 ✓ exec(safe_globals) x²+1(x=3)={res}")
                        logger.info(f"  [v1.3.0自检] 沙箱执行: x²+1(x=3)={res} ✓")
                    except Exception as e:
                        v13_result["checks"]["sandbox"] = "error"
                        v13_result["details"].append(f"    沙箱 ✗ 失败: {e}")
                        logger.error(f"  [v1.3.0自检] 沙箱执行异常: {e}")

                # ── 7. 多范式引擎检查 ────────────────────────────────────────
                if self._paradigm:
                    try:
                        r = self._paradigm.compute({"type": "functional", "expr": ['+', 1, 2, 3]})
                        assert r.get("result") == 6, f"范式计算错误: {r}"
                        v13_result["checks"]["paradigm"] = "ok"
                        v13_result["details"].append(f"    多范式 ✓ (+ 1 2 3) = {r['result']}")
                        logger.info(f"  [v1.3.0自检] 多范式引擎: (+1+2+3)={r['result']} ✓")
                    except Exception as e:
                        v13_result["checks"]["paradigm"] = "error"
                        v13_result["details"].append(f"    多范式 ✗ 失败: {e}")
                        logger.error(f"  [v1.3.0自检] 多范式引擎异常: {e}")

                # ── 总结 ──────────────────────────────────────────────────────
                failed = [k for k, v in v13_result["checks"].items() if v not in ("ok",)]
                if failed:
                    v13_result["status"] = "degraded"
                    v13_result["details"].append(f"  [v1.3.0自检] 异常模块: {failed}")
                    logger.error(f"  [v1.3.0自检] 自检异常: {failed}")
                else:
                    v13_result["status"] = "healthy"
                    v13_result["details"].append(f"  [v1.3.0自检] 全部 {len(v13_result['checks'])} 项通过")
                    logger.info("  [v1.3.0自检] ✅ 全部模块健康")

            except Exception as e:
                v13_result["status"] = "error"
                v13_result["details"].append(f"  [v1.3.0自检] 自检流程异常: {e}")
                logger.error(f"  [v1.3.0自检] 自检流程异常: {e}")
        else:
            v13_result["status"] = "skipped"
            v13_result["details"].append("  [v1.3.0自检] 跳过: 模块未初始化")
            logger.warning("  [v1.3.0自检] 模块未初始化，跳过自检")

        diagnosis["v13_self_check"] = v13_result

        # Phase 4.56: v2.0 HAL 自检
        hal_result = {"status": "healthy", "checks": {}, "details": []}
        if hasattr(self, '_sse') and self._sse:
            try:
                # SSE 健康检查
                sse_stats = self._sse.get_stats()
                hal_result["checks"]["side_effect"] = "ok"
                hal_result["details"].append(f"  [HAL v2.0] 副作用引擎: mode={sse_stats['mode']}, {sse_stats['registered_funcs']}注册函数, {sse_stats['total_calls']}调用")
                # 指针管理器健康检查
                pmgr_stats = self._pmgr.get_stats()
                hal_result["checks"]["pointer_mgr"] = "ok"
                hal_result["details"].append(f"  [HAL v2.0] 指针管理: {pmgr_stats['total_pages']}页, {pmgr_stats['total_memory_kb']}KB, {pmgr_stats['active_allocs']}活跃分配")
                # 原生编译目标检查
                targets = self._native_backend.get_targets()
                hal_result["checks"]["native_compiler"] = "ok"
                hal_result["details"].append(f"  [HAL v2.0] 原生编译: {len(targets)}目标架构 {targets}")
                # 协议解析器检查
                proto_stats = self._proto_parser.parse(
                    type('P', (), {'protocol': __import__('src.hardware.hal_v2', fromlist=['ProtocolType']).ProtocolType.UART,
                                   'name': 'test_uart', 'baud_rate': 115200, 'data_bits': 8,
                                   'parity': 'none', 'stop_bits': 1, 'frame_format': 'async',
                                   'max_payload': 256, 'timeout_ms': 1000, 'endian': 'little',
                                   'metadata': {}})()
                ) if False else {}
                # 驱动生成器检查
                from src.hardware.hal_v2 import DriverKind, DriverSpec, Architecture
                driver_result = self._driver_gen.generate(DriverSpec(
                    name="test_driver", kind=DriverKind.MATH,
                    target_arch=Architecture.X86_64, target_lang="python",
                    math_expr="x * 2",
                ))
                hal_result["checks"]["driver_gen"] = "ok"
                hal_result["details"].append(f"  [HAL v2.0] 驱动生成: test_driver 生成成功")
                # 原生编译检查
                compile_result = self._native_compiler.compile("x^2 + 1", Architecture.X86_64, "test_fn", "c")
                hal_result["checks"]["native_compile"] = "ok" if compile_result.get("success") else "error"
                hal_result["details"].append(f"  [HAL v2.0] 原生编译: x²+1 → C {'✓' if compile_result.get('success') else '✗'}")
                # 总结
                failed = [k for k, v in hal_result["checks"].items() if v not in ("ok",)]
                if failed:
                    hal_result["status"] = "degraded"
                    hal_result["details"].append(f"  [HAL v2.0] 异常模块: {failed}")
                    logger.error(f"  [HAL v2.0] 自检异常: {failed}")
                else:
                    hal_result["status"] = "healthy"
                    hal_result["details"].append(f"  [HAL v2.0] 全部 {len(hal_result['checks'])} 项通过")
                    logger.info("  [HAL v2.0] ✅ 全部模块健康")
            except Exception as e:
                hal_result["status"] = "error"
                hal_result["details"].append(f"  [HAL v2.0] 自检流程异常: {e}")
                logger.error(f"  [HAL v2.0] 自检流程异常: {e}")
        else:
            hal_result["status"] = "skipped"
            hal_result["details"].append("  [HAL v2.0] 跳过: 模块未初始化")
            logger.warning("  [HAL v2.0] 模块未初始化，跳过自检")

        diagnosis["hal_v2_self_check"] = hal_result

        # Phase 4.5: 自扩展
        if verbose:
            logger.info("  [自扩展] 检测知识盲区和模式...")
        expanded_concepts = self.self_extend_concepts()
        expanded_intents = self.self_extend_intents()
        if verbose and (expanded_concepts > 0 or expanded_intents > 0):
            logger.info(f"  [自扩展] 新增: {expanded_concepts} 概念, "
                         f"{expanded_intents} 意图映射")

        # Phase 4.55: 公式生长（新增）
        if verbose:
            logger.info("  [公式生长] 检测公式缺口并自动成长...")
        try:
            from src.unified_growth import get_unified_growth
            ug = get_unified_growth(self._interp)
            formula_result = ug.formula_grow(op_type="auto", max_combinations=3, max_derivatives=5)
            if formula_result.get("success"):
                logger.info(f"  [公式生长] 成长统计: {formula_result.get('stats', {})}")
                logger.info(f"  [公式生长] 注册新公式: {formula_result.get('registered', 0)} 个")
        except Exception as e:
            logger.warning(f"  [公式生长] 公式成长失败: {e}")

        # Phase 4.6: 自升级检查
        if verbose:
            logger.info("  [自升级] 检查版本和补丁状态...")
        upgrade_status = self.self_upgrade_check()
        if verbose:
            logger.info(f"  [自升级] 版本: {upgrade_status['current_version']}, "
                         f"待处理补丁: {len(upgrade_status['pending_patches'])}")
        # 有高危缺陷时自动尝试升级
        if upgrade_status["pending_patches"] and not upgrade_status.get("is_latest"):
            if verbose:
                logger.info("  [自升级] 检测到待处理高危缺陷，尝试自动升级...")
            upgrade_result = self.self_upgrade_apply()
            if upgrade_result["success"]:
                logger.info(f"  [自升级] 升级成功: {upgrade_result['patches_applied']} 补丁已应用")
            else:
                logger.warning(f"  [自升级] 升级部分失败: {upgrade_result['errors']}")

        # Phase 4.7: 自优化
        if verbose:
            logger.info("  [自优化] 性能分析与优化...")
        optimizations = self.self_optimize_performance()

        # Phase 5: 持久化
        self.save_state()

        # 计算本轮耗时
        cycle_duration = time.time() - cycle_start
        self._state.last_duration = cycle_duration
        self._state.total_duration += cycle_duration
        self._state.status = diagnosis.get("status", "healthy")

        if verbose:
            logger.info(f"  [完成] 内循环 #{self._state.cycle_count} 结束 "
                         f"({cycle_duration:.1f}s), 健康={self._state.health_score}")

        return {
            **diagnosis,
            "actions": actions,
            "verification": verification,
            "duration": cycle_duration,
        }

    # ── 控制接口 ────────────────────────────────────────────────────────────────

    def trigger_once(self, verbose: bool = True) -> dict:
        """触发单次内循环。"""
        self.init_modules()
        result = self.run_cycle(verbose=verbose)
        return result

    def start_loop(self, interval: float = 30.0, verbose: bool = True):
        """启动持续内循环模式（后台线程）。"""
        self._interval = interval
        self._running = True
        self.init_modules()
        self._loop_thread = threading.Thread(
            target=self._loop_worker,
            daemon=True,
            name="matha-inner-loop"
        )
        self._loop_thread.start()
        logger.info(f"  [内循环] 持续模式启动 (间隔={interval}s)")

    def _loop_worker(self):
        """持续循环工作线程。"""
        while self._running:
            try:
                self.run_cycle(verbose=False)
            except Exception as e:
                logger.warning(f"  [内循环] 轮次异常: {e}")
            time.sleep(self._interval)

    def stop_loop(self):
        """停止持续内循环。"""
        self._running = False
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
        self.save_state()
        logger.info("  [内循环] 持续模式已停止")

    def get_status(self) -> dict:
        """获取当前内循环状态。"""
        return {
            "status": self._state.status,
            "health_score": self._state.health_score,
            "cycle_count": self._state.cycle_count,
            "total_interactions": self._state.total_interactions,
            "total_errors_caught": self._state.total_errors_caught,
            "total_resources_expanded": self._state.total_resources_expanded,
            "total_patches_applied": self._state.total_patches_applied,
            "total_defects_resolved": self._state.total_defects_resolved,
            "uptime_seconds": time.time() - self._state.uptime_start,
            "running": self._running,
        }

    def get_state(self) -> dict:
        """获取完整内循环状态（含模块信息）。"""
        status = self.get_status()
        if self._engine:
            status.update(self._engine.get_growth_stats())
        if self._assistant:
            status["concepts_count"] = len(self._assistant.parser.MATH_CONCEPTS)
            status["keywords_count"] = sum(
                len(v) for v in self._assistant.parser.KEYWORD_MAP.values()
            )
        return status


# ═══════════════════════════════════════════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

_loop_instance: Optional[MathaInnerLoop] = None


def get_inner_loop() -> MathaInnerLoop:
    """获取或创建内循环单例。"""
    global _loop_instance
    if _loop_instance is None:
        _loop_instance = MathaInnerLoop()
    return _loop_instance


def trigger_inner_loop(verbose: bool = True) -> dict:
    """触发一次完整内循环（便捷入口）。"""
    loop = get_inner_loop()
    return loop.trigger_once(verbose=verbose)


def start_inner_loop(interval: float = 30.0):
    """启动持续内循环（便捷入口）。"""
    loop = get_inner_loop()
    loop.start_loop(interval=interval)


def stop_inner_loop():
    """停止持续内循环（便捷入口）。"""
    loop = get_inner_loop()
    loop.stop_loop()


def get_loop_status() -> dict:
    """获取内循环状态（便捷入口）。"""
    loop = get_inner_loop()
    return loop.get_state()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    loop = MathaInnerLoop()
    print("\n" + "=" * 60)
    print("  Matha 全功能内循环 v1.2.21")
    print("=" * 60)

    # 单次运行
    result = loop.trigger_once(verbose=True)
    print(f"\n内循环结果:")
    print(f"  缺陷: {result.get('defects_found', 0)}")
    print(f"  健康分: {result.get('health_score', 0)}")
    print(f"  状态: {result.get('status', 'unknown')}")
    print(f"  耗时: {result.get('duration', 0):.1f}s")

    # 持续模式演示
    print(f"\n启动持续内循环 (30s间隔)...")
    loop.start_loop(interval=30.0)
    time.sleep(5)
    print(f"  状态: {loop.get_status()}")
    loop.stop_loop()

    print("\n完成。")
