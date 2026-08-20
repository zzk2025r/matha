# -*- coding: utf-8 -*-
"""
Matha AI Assistant — 小白友好的数学计算助手

功能：
  1. 自然语言 → Matha 代码自动生成
  2. 多步骤任务分解（AI 辅助规划）
  3. 小白友好错误解释（非技术语言）
  4. 数学概念讲解 + 例题
  5. 待办事项管理
  6. 跨平台（Web/PWA/Electron）
"""
from __future__ import annotations
import re
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


# ============================================================
# 意图分类（小白友好版）
# ============================================================

class IntentType(str, Enum):
    算术 = "arithmetic"
    数学函数 = "math_func"
    统计 = "statistics"
    字符串 = "string"
    数组 = "array"
    物理 = "physics"
    工程 = "engineering"
    条件 = "conditional"
    循环 = "loop"
    单位换算 = "unit_convert"
    素数因数 = "number_theory"
    三角函数 = "trig"
    未知 = "unknown"


@dataclass
class Step:
    """任务分解后的单步。"""
    description: str       # 人类可读
    matha_code: str        # 生成的 Matha 代码
    explanation: str       # 小白解释（为什么这样做）


@dataclass
class Task:
    """待办事项。"""
    id: str
    title: str
    status: str = "pending"  # pending / doing / done
    steps: list[Step] = field(default_factory=list)
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class ChatMessage:
    """对话消息。"""
    role: str           # "user" | "assistant" | "system"
    content: str
    type: str = "text"  # text / code / math / error / task
    timestamp: float = field(default_factory=time.time)


# ============================================================
# 小白友好意图解析器
# ============================================================

class FriendlyIntentParser:
    """
    将自然语言分解为步骤，生成 Matha 代码，并用小白语言解释。

    工作流程：
      用户输入 → 意图分类 → 参数提取 → 步骤分解 → 代码生成 → 执行 → 结果解释
    """

    # 关键词映射表（用于分类）
    KEYWORD_MAP = {
        IntentType.算术: [
            "加", "减", "乘", "除",
            "+", "-", "×", "÷", "*", "/",
        ],
        IntentType.数学函数: [
            "平方", "立方", "开方", "根号", "幂", "指数",
            "对数", "log", "ln", "绝对值",
        ],
        IntentType.统计: [
            "平均", "均值", "中位数", "标准差", "方差",
            "最大值", "最小值", "求和", "统计", "百分比",
        ],
        IntentType.字符串: [
            "字符串", "文字", "文本", "反转", "拼接", "截取",
            "替换", "查找", "长度", "字数",
        ],
        IntentType.数组: [
            "数组", "列表", "排序", "过滤", "查找", "去重",
            "拆分", "合并", "切片",
        ],
        IntentType.物理: [
            "速度", "加速度", "位移", "力", "质量", "重量",
            "能量", "功", "功率", "压强", "密度",
            "自由落体", "平抛", "斜抛", "圆周",
        ],
        IntentType.工程: [
            "应力", "应变", "惯性矩", "扭矩", "扭转",
            "弯曲", "梁", "轴", "材料", "安全系数",
        ],
        IntentType.三角函数: [
            "sin", "cos", "tan", "正弦", "余弦", "正切",
            "弧度", "角度", "π", "pi",
        ],
        IntentType.素数因数: [
            "素数", "质数", "因数", "因子", "阶乘",
            "最大公约", "最小公倍", "分解",
        ],
        IntentType.单位换算: [
            "换算", "转换", "千米", "米", "厘米", "毫米",
            "千克", "克", "吨", "摄氏度", "华氏度",
        ],
    }

    # 错误解释模板
    ERROR_EXPLANATIONS = {
        "未定义变量": {
            "小白解释": "你用到了一个还没有定义的数。需要先告诉系统它是多少。",
            "怎么修": "在前面加一行声明，比如：@：x=10",
            "例子": "@：x=5\n#1: x + 3 = 结果\n#1: [结果]  →  输出 8",
        },
        "未定义函数": {
            "小白解释": "你调用了一个还没定义的公式。需要先定义它。",
            "怎么修": "加一行函数定义，比如：func 平方(x)->Int=(x)=>x*x",
            "例子": "func 平方(x)->Int=(x)=>x*x\n#1: 平方(5) = 结果\n#1: [结果]  →  输出 25",
        },
        "除零错误": {
            "小白解释": "你试图除以 0，这在数学上没有意义。",
            "怎么修": "检查除数（分母）是否可能为 0。",
            "例子": "如果除数是变量，先判断：if 除数 != 0, 再计算",
        },
        "取模除零错误": {
            "小白解释": "取余运算（%）的除数不能为 0。",
            "怎么修": "检查 % 右边的数是否为 0。",
            "例子": "确保 a % b 中 b ≠ 0",
        },
        "JSON 解析失败": {
            "小白解释": "你输入的内容格式不对，系统无法理解。",
            "怎么修": "检查括号是否配对，逗号是否正确。",
            "例子": "用 [] 包裹数组元素，用 {} 包裹对象",
        },
        "ParseError": {
            "小白解释": "代码语法有误，请检查符号和括号。",
            "怎么修": "Matha 代码需要用特定的符号格式。",
            "例子": "正确格式：#1: a + b = 结果\n错误：#1: a + b",
        },
    }

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._messages: list[ChatMessage] = []

    # ── 意图分类 ─────────────────────────────────────────────

    def classify(self, text: str) -> tuple[IntentType, float]:
        """根据关键词分类，返回 (类型, 置信度)。

        策略：按关键词长度降序排列后匹配，长关键词优先（如"阶乘"优先于"乘"），
        避免短词误匹配长词内含的片段。
        """
        text_lower = text.lower()
        scores: dict[IntentType, float] = {}

        for intent_type, keywords in self.KEYWORD_MAP.items():
            score = 0.0
            # 按长度降序排列，确保长关键词优先匹配
            sorted_kw = sorted(keywords, key=len, reverse=True)
            for kw in sorted_kw:
                if kw in text_lower:
                    # 关键词越长越精确，权重越高
                    weight = 3.0 if len(kw) >= 3 else 2.0 if len(kw) == 2 else 1.0
                    score += weight
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return IntentType.未知, 0.1

        best_type = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[best_type] / total * 0.9 + 0.1
        return best_type, min(confidence, 1.0)

    # ── 参数提取 ─────────────────────────────────────────────

    def extract_numbers(self, text: str) -> list[float]:
        """从文本中提取所有数字。"""
        return [float(x) for x in re.findall(r'-?\d+\.?\d*', text)]

    def extract_range(self, text: str) -> Optional[tuple[int, int]]:
        """提取范围，如 '1到100' → (1, 100)。"""
        m = re.search(r'(\d+)\s*[到至 till ]\s*(\d+)', text)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.search(r'(\d+)\s*到\s*(\d+)', text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def extract_variable(self, text: str) -> Optional[str]:
        """提取变量名。"""
        # 找中文字符变量名
        m = re.search(r'[\u4e00-\u9fa5]{2,8}', text)
        return m.group(0) if m else None

    # ── 步骤分解（核心：AI 辅助规划）─────────────────────────

    def decompose(self, text: str) -> list[Step]:
        """将自然语言分解为可执行的步骤。"""
        intent_type, confidence = self.classify(text)
        numbers = self.extract_numbers(text)
        rng = self.extract_range(text)

        steps = []

        if intent_type == IntentType.算术:
            steps = self._decompose_arithmetic(text, numbers)
        elif intent_type == IntentType.数学函数:
            steps = self._decompose_math_func(text, numbers)
        elif intent_type == IntentType.统计:
            steps = self._decompose_statistics(text, numbers)
        elif intent_type == IntentType.字符串:
            steps = self._decompose_string(text)
        elif intent_type == IntentType.数组:
            steps = self._decompose_array(text, numbers)
        elif intent_type == IntentType.物理:
            steps = self._decompose_physics(text, numbers)
        elif intent_type == IntentType.三角函数:
            steps = self._decompose_trig(text, numbers)
        elif intent_type == IntentType.素数因数:
            steps = self._decompose_number_theory(text, rng, numbers)
        elif intent_type == IntentType.单位换算:
            steps = self._decompose_unit_convert(text, numbers)
        else:
            steps = [Step(
                description="无法理解，请重新描述",
                matha_code="",
                explanation="试试这样说：'计算 3 加 5' 或 '找出 1 到 100 的素数'",
            )]

        return steps

    def _decompose_arithmetic(self, text: str, nums: list[float]) -> list[Step]:
        if len(nums) >= 2:
            op_map = {"加": "+", "减": "-", "乘": "*", "除": "/"}
            op = "+"
            for kw, sym in op_map.items():
                if kw in text:
                    op = sym
                    break
            return [Step(
                description=f"计算 {nums[0]} {op} {nums[1]}",
                matha_code=f"#1：[{nums[0]} {op} {nums[1]}]",
                explanation=f"{nums[0]} 和 {nums[1]} 做 {'加法' if op=='+' else '减法' if op=='-' else '乘法' if op=='*' else '除法'} → 结果",
            )]
        return [Step(
            description="请提供两个数字",
            matha_code="",
            explanation="算术运算需要两个数字，例如：'计算 3 加 5'",
        )]

    def _decompose_math_func(self, text: str, nums: list[float]) -> list[Step]:
        if not nums:
            nums = [0]
        steps = []
        if "平方" in text:
            steps.append(Step("计算平方", f"#1：[{nums[0]} * {nums[0]}]",
                              "平方 = 这个数乘以自己"))
        if "立方" in text:
            steps.append(Step("计算立方", f"#1：[{nums[0]} * {nums[0]} * {nums[0]}]",
                              "立方 = 这个数乘自己三次"))
        if "开方" in text or "根号" in text:
            steps.append(Step("计算平方根", f"#1：[sqrt({nums[0]})]",
                              "平方根 = 哪个数乘自己等于这个数"))
        if "绝对值" in text:
            steps.append(Step("计算绝对值", f"#1：[abs({nums[0]})]",
                              "绝对值 = 去掉负号，只看大小"))
        if "阶乘" in text:
            n = int(nums[0]) if nums else 5
            steps.append(Step(f"计算 {n} 的阶乘",
                              f"#1：[阶乘({n})]",
                              f"{n}! = {n}×{n-1}×...×1"))
        return steps or [Step("请选择要计算的函数", "", "可以计算：平方、立方、开方、绝对值、阶乘")]

    def _decompose_statistics(self, text: str, nums: list[float]) -> list[Step]:
        if not nums:
            nums = [1, 2, 3, 4, 5]
        arr = "[" + ", ".join(str(int(x)) if x == int(x) else str(x) for x in nums) + "]"
        steps = []
        if "平均" in text or "均值" in text:
            steps.append(Step("计算平均值", f"#1：[平均值({arr})]",
                              "平均值 = 所有数加起来除以个数"))
        if "求和" in text or "总和" in text:
            steps.append(Step("计算总和", f"#1：[求和({arr})]",
                              "总和 = 把所有数加起来"))
        if "最大" in text:
            steps.append(Step("找最大值", f"#1：[max({arr})]",
                              "最大值 = 这组数中最大的那个"))
        if "最小" in text:
            steps.append(Step("找最小值", f"#1：[min({arr})]",
                              "最小值 = 这组数中最小的那个"))
        if "排序" in text:
            steps.append(Step("排序", f"#1：[排序({arr})]",
                              "排序 = 从小到大排列"))
        if "中位数" in text:
            steps.append(Step("计算中位数", f"#1：[排序({arr})]",
                              "中位数 = 排序后最中间的那个数"))
        return steps or [Step("请指定统计方式", "", "可以：平均、求和、最大、最小、排序、中位数")]

    def _decompose_string(self, text: str) -> list[Step]:
        # 简单示例
        return [Step("字符串操作", f"#1: StrReverse('hello') = 结果\n#1: [结果]",
                      "字符串反转 = 把文字倒过来写")]

    def _decompose_array(self, text: str, nums: list[float]) -> list[Step]:
        if not nums:
            nums = [3, 1, 2]
        steps = []
        if "排序" in text:
            steps.append(Step("数组排序",
                              f"#1: ArraySort([{','.join(map(str, nums))}]) = 结果\n#1: [结果]",
                              "排序 = 从小到大排列"))
        if "过滤" in text or "查找" in text:
            steps.append(Step("数组查找",
                              f"#1: ArrayFind([{','.join(map(str, nums))}], 3) = 结果\n#1: [结果]",
                              "查找 = 在数组中找某个数"))
        if "去重" in text:
            steps.append(Step("数组去重",
                              f"#1: ArrayUnique([{','.join(map(str, nums))}]) = 结果\n#1: [结果]",
                              "去重 = 去掉重复的数"))
        if "反转" in text:
            steps.append(Step("数组反转",
                              f"#1: ArrayReverse([{','.join(map(str, nums))}]) = 结果\n#1: [结果]",
                              "反转 = 倒过来排列"))
        return steps or [Step("数组操作",
                              f"#1: ArraySort([{','.join(map(str, nums))}]) = 结果\n#1: [结果]",
                              "支持：排序、查找、去重、反转")]

    def _decompose_physics(self, text: str, nums: list[float]) -> list[Step]:
        steps = []
        if "自由落体" in text or "下落" in text:
            if len(nums) >= 1:
                t = nums[0]
                g = 9.80665
                steps.append(Step("自由落体计算",
                                  f"#1：[运动_自由落体位移({t})]",
                                  f"自由落体：从 {t} 秒高处落下，重力加速度 g={g} m/s²"))
            else:
                steps.append(Step("自由落体", "", "请提供下落时间（秒），如：'自由落体 3 秒'"))
        if "斜抛" in text or "射程" in text:
            if len(nums) >= 2:
                v0, angle = nums[0], nums[1]
                steps.append(Step("斜抛射程计算",
                                  f"#1：[运动_斜抛射程({v0}, {angle})]",
                                  f"斜抛：初速度 {v0} m/s，角度 {angle}°，计算最远射程"))
        if "匀速" in text:
            if len(nums) >= 2:
                steps.append(Step("匀速运动",
                                  f"#1：[运动_匀速位移({nums[0]}, {nums[1]})]",
                                  f"匀速：速度 {nums[0]} m/s，时间 {nums[1]}s，计算位移"))
        return steps or [Step("物理计算", "", "支持：自由落体、斜抛、匀速运动、匀变速运动")]

    def _decompose_trig(self, text: str, nums: list[float]) -> list[Step]:
        if not nums:
            nums = [0]
        steps = []
        if "sin" in text.lower() or "正弦" in text:
            steps.append(Step("计算 sin", f"#1：[sin({nums[0]})]",
                              "sin(角度) = 这个角度的正弦值（对边/斜边）"))
        if "cos" in text.lower() or "余弦" in text:
            steps.append(Step("计算 cos", f"#1：[cos({nums[0]})]",
                              "cos(角度) = 这个角度的余弦值（邻边/斜边）"))
        if "tan" in text.lower() or "正切" in text:
            steps.append(Step("计算 tan", f"#1：[tan({nums[0]})]",
                              "tan(角度) = 这个角度的正切值（对边/邻边）"))
        return steps or [Step("三角函数", "", "支持：sin、cos、tan（输入弧度）")]

    def _decompose_number_theory(self, text: str, rng: Optional[tuple], nums: list[float]) -> list[Step]:
        steps = []
        if "阶乘" in text:
            n = int(nums[0]) if nums else 5
            steps.append(Step(f"计算 {n}! = ?",
                              f"#1：[阶乘({n})]",
                              f"{n}! = {n}×{n-1}×...×1"))
        if "素数" in text or "质数" in text:
            if rng:
                a, b = rng
                steps.append(Step(f"找出 {a} 到 {b} 的素数",
                                  f"#1：[素数筛({b})]",
                                  f"素数 = 只能被 1 和自己整除的数，范围 {a}~{b}"))
            elif nums:
                n = int(nums[0])
                steps.append(Step(f"判断 {n} 是否为素数",
                                  f"#1：[素数判定({n})]",
                                  f"素数判定 = 检查 {n} 是否只能被 1 和自己整除"))
        if "因数" in text or "因子" in text:
            if nums:
                n = int(nums[0])
                steps.append(Step(f"找出 {n} 的因数",
                                  f"#1：[IntFactors({n})]",
                                  f"因数 = 能整除 {n} 的所有正整数"))
        return steps or [Step("数论计算", "", "支持：素数判定、找素数、阶乘、因数分解")]

    def _decompose_unit_convert(self, text: str, nums: list[float]) -> list[Step]:
        if not nums:
            nums = [1]
        return [Step("单位换算",
                     f"#1: 换算_千米_米({nums[0]}) = 结果\n#1: [结果]",
                     f"{nums[0]} 千米 = ? 米（1千米 = 1000米）")]

    # ── 执行与结果解释 ───────────────────────────────────────

    def execute_steps(self, steps: list[Step], interp) -> list[dict]:
        """执行步骤列表，返回结果。"""
        results = []
        for step in steps:
            if not step.matha_code:
                results.append({"step": step.description, "status": "skip", "result": None})
                continue
            try:
                from src.parser import parse
                from src.interp import Interpreter
                i = Interpreter()
                outputs, _ = i.run(parse(step.matha_code))
                results.append({
                    "step": step.description,
                    "status": "ok",
                    "result": outputs[-1] if outputs else None,
                })
            except Exception as e:
                results.append({
                    "step": step.description,
                    "status": "error",
                    "result": None,
                    "error": str(e),
                })
        return results

    def explain_error(self, error_msg: str) -> dict:
        """将技术错误翻译为小白语言。"""
        for key, info in self.ERROR_EXPLANATIONS.items():
            if key in error_msg:
                return {
                    "what": info["小白解释"],
                    "how": info["怎么修"],
                    "example": info["例子"],
                }
        # 通用错误解释
        return {
            "what": f"出现了一个错误：{error_msg[:80]}",
            "how": "请检查输入的数字或格式是否正确。",
            "example": "试试：'计算 3 加 5'",
        }

    def explain_intent(self, text: str) -> dict:
        """生成完整意图解释。"""
        intent_type, confidence = self.classify(text)
        steps = self.decompose(text)
        return {
            "type": intent_type.value,
            "confidence": round(confidence, 2),
            "steps": [s.description for s in steps],
            "total_steps": len(steps),
        }

    # ── 数学概念讲解 ─────────────────────────────────────────

    MATH_CONCEPTS = {
        "加法": {
            "是什么": "把两个数合在一起，得到总和。",
            "符号": "+",
            "例子": "3 + 5 = 8，表示 3 个苹果加 5 个苹果，一共 8 个苹果。",
            "生活中的例子": "购物结账、计算人数、统计总数。",
        },
        "乘法": {
            "是什么": "相同数重复相加的快捷方式。",
            "符号": "× 或 *",
            "例子": "3 × 5 = 15，就是 3 个 5 相加：5 + 5 + 5 = 15。",
            "生活中的例子": "买多件商品总价、计算面积（长×宽）。",
        },
        "除法": {
            "是什么": "把一个数平均分成若干份。",
            "符号": "÷ 或 /",
            "例子": "15 ÷ 3 = 5，表示 15 平均分成 3 份，每份 5。",
            "生活中的例子": "分蛋糕、算人均费用、速度=距离÷时间。",
        },
        "平方": {
            "是什么": "一个数乘以它自己。",
            "符号": "x² 或 x*x",
            "例子": "5² = 25，即 5 × 5 = 25。",
            "生活中的例子": "正方形面积（边长×边长）。",
        },
        "开方": {
            "是什么": "平方运算的逆运算，找一个数，它的平方等于原数。",
            "符号": "√x",
            "例子": "√25 = 5，因为 5 × 5 = 25。",
            "生活中的例子": "已知面积求正方形边长。",
        },
        "平均值": {
            "是什么": "所有数加起来除以个数，代表整体水平。",
            "符号": "avg = sum / n",
            "例子": "[3, 5, 7] 的平均值 = (3+5+7)/3 = 5。",
            "生活中的例子": "计算平均成绩、平均温度、平均工资。",
        },
        "素数": {
            "是什么": "只能被 1 和自己整除的大于 1 的数。",
            "例子": "2, 3, 5, 7, 11, 13, 17, 19... 是素数。",
            "生活中的例子": "密码学、随机数生成。",
        },
        "三角函数": {
            "是什么": "描述三角形边角关系的函数。",
            "符号": "sin, cos, tan",
            "例子": "sin(90°) = 1，cos(0°) = 1",
            "生活中的例子": "建筑工程、游戏开发、导航定位。",
        },
    }

    def explain_concept(self, topic: str) -> dict:
        """讲解数学概念。"""
        for key, info in self.MATH_CONCEPTS.items():
            if key in topic or topic in key:
                return {"topic": key, **info}
        return {
            "topic": topic,
            "是什么": f"关于 '{topic}' 的概念",
            "例子": "请尝试输入：加法、乘法、除法、平方、开方、平均值、素数、三角函数",
        }

    # ── 待办事项管理 ─────────────────────────────────────────

    def create_task(self, title: str, steps: list[Step]) -> Task:
        """创建待办事项。"""
        task_id = f"task_{int(time.time() * 1000)}"
        task = Task(id=task_id, title=title, steps=steps)
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> list[Task]:
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]

    def mark_done(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].status = "done"
            return True
        return False

    # ── 对话历史 ─────────────────────────────────────────────

    def add_message(self, msg: ChatMessage):
        self._messages.append(msg)

    def get_history(self, limit: int = 20) -> list[ChatMessage]:
        return self._messages[-limit:]


# ============================================================
# 主控制器
# ============================================================

class MathaAIAssistant:
    """Matha AI 助手 — 小白友好型数学计算平台。"""

    def __init__(self):
        self.parser = FriendlyIntentParser()
        self._history: list[dict] = []

    def chat(self, text: str, interp=None) -> dict:
        """
        处理用户输入，返回结构化响应。

        返回:
          {
            "reply": str,          # 给用户的回复
            "code": str,           # 生成的 Matha 代码
            "steps": list,         # 分解步骤
            "result": Any,         # 执行结果
            "explanation": str,    # 结果解释
            "type": str            # text / error / task
          }
        """
        text = text.strip()
        if not text:
            return {"reply": "请输入你的问题，例如：'计算 3 加 5'", "type": "text"}

        # 1. 分类意图
        intent_type, confidence = self.parser.classify(text)

        # 2. 分解步骤
        steps = self.parser.decompose(text)

        # 3. 生成代码
        code_lines = []
        for step in steps:
            if step.matha_code:
                code_lines.append(step.matha_code)

        matha_code = "\n".join(code_lines) if code_lines else ""

        # 4. 执行
        result = None
        error = None
        if matha_code and interp:
            try:
                from src.parser import parse
                from src.interp import Interpreter
                i = interp or Interpreter()
                outputs, _ = i.run(parse(matha_code))
                result = outputs[-1] if outputs else None
            except Exception as e:
                error = str(e)

        # 5. 生成回复
        if error:
            explanation = self.parser.explain_error(error)
            reply = (
                f"⚠️ 遇到问题：{explanation['what']}\n\n"
                f"💡 怎么修：{explanation['how']}\n\n"
                f"📝 示例：\n{explanation['example']}"
            )
            return {
                "reply": reply,
                "code": matha_code,
                "steps": [s.description for s in steps],
                "result": None,
                "explanation": explanation,
                "type": "error",
                "intent": intent_type.value,
                "confidence": round(confidence, 2),
            }

        if result is not None:
            reply = (
                f"✅ 计算结果：{result}\n\n"
                f"📋 分解步骤：\n" +
                "\n".join(f"  {i+1}. {s.description}" for i, s in enumerate(steps))
            )
            return {
                "reply": reply,
                "code": matha_code,
                "steps": [s.description for s in steps],
                "result": result,
                "explanation": steps[0].explanation if steps else "",
                "type": "result",
                "intent": intent_type.value,
                "confidence": round(confidence, 2),
            }

        # 无结果，给出引导
        reply = (
            f"🤔 我理解你的意图是「{intent_type.value}」"
            f"（置信度 {confidence:.0%}）\n\n"
            f"📝 可以这样表达：\n"
            f"  • '计算 3 加 5'\n"
            f"  • '找出 1 到 100 的素数'\n"
            f"  • '计算 5 的阶乘'\n"
            f"  • '自由落体 3 秒'\n"
            f"  • '求 [1,2,3,4,5] 的平均值'"
        )
        return {
            "reply": reply,
            "code": "",
            "steps": [s.description for s in steps],
            "result": None,
            "explanation": "",
            "type": "guide",
            "intent": intent_type.value,
            "confidence": round(confidence, 2),
        }

    def help(self) -> str:
        return """
🎯 Matha AI 助手使用指南
━━━━━━━━━━━━━━━━━━━━━━━━
模式 1：直接计算
  输入：计算 3 加 5
  输入：求 100 的平方根

模式 2：统计运算
  输入：求 [1,2,3,4,5] 的平均值
  输入：找出这组数的最大值

模式 3：物理计算
  输入：自由落体 3 秒
  输入：斜抛 30度，速度 20

模式 4：数论
  输入：找出 1 到 100 的素数
  输入：5 的阶乘是多少

模式 5：数学概念
  输入：什么是素数
  输入：解释三角函数

模式 6：查看帮助
  输入：help
  输入：模式切换 nl/intent
"""
