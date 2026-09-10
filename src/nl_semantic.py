# -*- coding: utf-8 -*-
"""
Matha 自然语言时代语义词典（Era-Aware Semantic Dictionary）

设计原则：
  1. 每个词/短语在不同历史时代有不同语义
  2. 系统根据当前时代（2026年）选择最合适的语义
  3. 支持跨时代追溯，可指定历史时代查询
  4. 每个语义条目包含：词义、数学映射、领域分类、时代标签

时代划分：
  - 先秦 (前221年前)  — 古典数学、算术、几何萌芽
  - 汉唐 (220-907)    — 九章算术、孙子定理
  - 宋元 (960-1368)   — 方程术、内插法、天元术
  - 明清 (1368-1911)  — 算法化、西方数学传入
  - 近代 (1911-1949)  — 现代数学体系建立
  - 现代 (1949-2000)  — 计算机数学、离散数学
  - 当代 (2000-至今)   — AI数学、符号计算、跨学科

用法：
  from src.nl_semantic import NLDictionary

  dict = NLDictionary()
  result = dict.lookup("速度", era="当代")
  # → {"meaning": "位移对时间的变化率", "math": "v = Δs/Δt", ...}
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
#  语义条目
# ============================================================

@dataclass
class SemanticEntry:
    """一个词的语义条目。"""
    word: str
    meaning: str          # 词义描述
    math_symbol: str      # 数学符号/变量名
    math_expr: str        # 数学表达式（可选）
    domain: str           # 领域分类
    era: str              # 时代标签
    note: str = ""        # 备注
    aliases: list[str] = field(default_factory=list)  # 同义词


# ============================================================
#  时代语义词典
# ============================================================

class NLDictionary:
    """
    自然语言时代语义词典。

    支持：
      - lookup(word, era="当代") → 查询某词在指定时代的语义
      - list_eras(word) → 列出某词所有时代的语义
      - build_definitions(nl_text, era="当代") → 从自然语言提取条目并赋予定义
      - resolve_ambiguity(word, context, era="当代") → 消歧
    """

    # ── 基础词义库 ──────────────────────────────────────────────
    _CORE_ENTRIES: list[dict] = [
        # ═══ 运动学（含跨时代语义）═══
        # 速度：从"急速"到物理量
        {"word": "速度", "meaning": "急速，快速（形容词，古义）", "math_symbol": "—", "math_expr": "—", "domain": "古汉语", "era": "先秦"},
        {"word": "速度", "meaning": "位移对时间的变化率（物理量，近代）", "math_symbol": "v", "math_expr": "v = ds/dt", "domain": "运动学", "era": "近代"},
        {"word": "速度", "meaning": "速度矢量，含方向；相速度/群速度", "math_symbol": "v", "math_expr": "v = d**r/dt 或 v_p = ω/k", "domain": "运动学", "era": "现代"},
        {"word": "速度", "meaning": "相速度/群速度，波传播特性", "math_symbol": "v_p/v_g", "math_expr": "v_p = ω/k", "domain": "近代物理", "era": "当代"},
        {"word": "速率", "meaning": "路程对时间的变化率（标量）", "math_symbol": "v", "math_expr": "v = ds/dt", "domain": "运动学", "era": "近代"},
        {"word": "加速度", "meaning": "速度对时间的变化率", "math_symbol": "a", "math_expr": "a = dv/dt = d²s/dt²", "domain": "运动学", "era": "近代"},
        {"word": "位移", "meaning": "位置的变化量（矢量）", "math_symbol": "s", "math_expr": "s = s_f - s_0", "domain": "运动学", "era": "先秦"},
        {"word": "路程", "meaning": "运动轨迹的实际长度（标量）", "math_symbol": "s", "math_expr": "s = ∫|v|dt", "domain": "运动学", "era": "先秦"},
        # 力：从"体力"到基本相互作用
        {"word": "力", "meaning": "体力，气力；用力（动词/名词，古义）", "math_symbol": "—", "math_expr": "—", "domain": "古汉语", "era": "先秦"},
        {"word": "力", "meaning": "力，作用（宋元，初步力学概念）", "math_symbol": "力", "math_expr": "—", "domain": "古力学", "era": "宋元"},
        {"word": "力", "meaning": "物体间的相互作用，改变运动状态（牛顿力学）", "math_symbol": "F", "math_expr": "F = m*a", "domain": "动力学", "era": "近代"},
        {"word": "力", "meaning": "四种基本相互作用之一（引力/电磁力/强核力/弱核力）", "math_symbol": "F", "math_expr": "F = G*m1*m2/r²", "domain": "物理学", "era": "当代"},
        {"word": "质量", "meaning": "物体惯性的量度", "math_symbol": "m", "math_expr": "m = F/a", "domain": "动力学", "era": "近代"},
        {"word": "功", "meaning": "力在位移方向上的累积效应", "math_symbol": "W", "math_expr": "W = F*s*cos(θ)", "domain": "动力学", "era": "近代"},
        {"word": "能", "meaning": "物体做功的能力", "math_symbol": "E", "math_expr": "E = mc² (质能等价)", "domain": "动力学", "era": "现代"},
        {"word": "动能", "meaning": "物体因运动而具有的能量", "math_symbol": "Ek", "math_expr": "Ek = ½*m*v²", "domain": "动力学", "era": "近代"},
        {"word": "势能", "meaning": "物体因位置而具有的能量", "math_symbol": "Ep", "math_expr": "Ep = m*g*h", "domain": "动力学", "era": "近代"},
        {"word": "动量", "meaning": "质量与速度的乘积", "math_symbol": "p", "math_expr": "p = m*v", "domain": "动力学", "era": "近代"},
        {"word": "冲量", "meaning": "力对时间的累积效应", "math_symbol": "I", "math_expr": "I = F*t = Δp", "domain": "动力学", "era": "近代"},

        # ═══ 几何（含跨时代语义）═══
        # 面积：从田亩到积分
        {"word": "面积", "meaning": "田亩的面积，古代丈量土地的单位（古义）", "math_symbol": "亩", "math_expr": "1亩 = 60平方丈", "domain": "古代算术", "era": "先秦"},
        {"word": "面积", "meaning": "平面图形所占平面的大小（几何定义）", "math_symbol": "S", "math_expr": "S = 长*宽 (矩形)", "domain": "几何", "era": "宋元"},
        {"word": "面积", "meaning": "积分定义的区域度量", "math_symbol": "S", "math_expr": "S = ∫∫_D dA", "domain": "微积分", "era": "近代"},
        {"word": "面积", "meaning": "黎曼度量下的面积元", "math_symbol": "A", "math_expr": "A = ∫∫ √(EG-F²) du dv", "domain": "微分几何", "era": "当代"},
        {"word": "周长", "meaning": "封闭图形边界的总长度", "math_symbol": "C", "math_expr": "C = 2*π*r (圆)", "domain": "几何", "era": "先秦"},
        {"word": "体积", "meaning": "立体图形所占空间的大小", "math_symbol": "V", "math_expr": "V = 长*宽*高 (长方体)", "domain": "几何", "era": "先秦"},
        {"word": "半径", "meaning": "圆心到圆周上任意一点的距离", "math_symbol": "r", "math_expr": "r = d/2", "domain": "几何", "era": "先秦"},
        {"word": "直径", "meaning": "通过圆心的弦", "math_symbol": "d", "math_expr": "d = 2*r", "domain": "几何", "era": "先秦"},
        {"word": "底", "meaning": "几何体的底面或底边", "math_symbol": "a", "math_expr": "—", "domain": "几何", "era": "先秦"},
        {"word": "高", "meaning": "从底面到顶点的垂直距离", "math_symbol": "h", "math_expr": "—", "domain": "几何", "era": "先秦"},
        {"word": "斜边", "meaning": "直角三角形中最长的边", "math_symbol": "c", "math_expr": "c² = a² + b²", "domain": "几何", "era": "先秦"},
        # 线/点：从实物到抽象
        {"word": "线", "meaning": "丝线，线条（实物）", "math_symbol": "—", "math_expr": "—", "domain": "古汉语", "era": "先秦"},
        {"word": "线", "meaning": "几何学中无宽度的直线", "math_symbol": "l", "math_expr": "l: y = kx + b", "domain": "几何", "era": "先秦"},
        {"word": "线", "meaning": "曲线，参数曲线", "math_symbol": "γ", "math_expr": "γ(t) = (x(t), y(t))", "domain": "分析几何", "era": "近代"},
        {"word": "线", "meaning": "数据线，网络连接", "math_symbol": "link", "math_expr": "link = (u, v)", "domain": "计算机科学", "era": "当代"},
        {"word": "点", "meaning": "点滴，少量（古义）", "math_symbol": "—", "math_expr": "—", "domain": "古汉语", "era": "先秦"},
        {"word": "点", "meaning": "几何学中无大小的位置", "math_symbol": "P", "math_expr": "P ∈ ℝ²", "domain": "几何", "era": "先秦"},
        {"word": "点", "meaning": "坐标点，空间中的位置", "math_symbol": "P", "math_expr": "P = (x, y, z) ∈ ℝ³", "domain": "解析几何", "era": "近代"},
        {"word": "点", "meaning": "数据点，样本点", "math_symbol": "x_i", "math_expr": "x_i ∈ ℝⁿ", "domain": "统计学", "era": "现代"},
        {"word": "点", "meaning": "神经网络节点，图节点", "math_symbol": "v", "math_expr": "v ∈ V (图论)", "domain": "图论", "era": "当代"},

        # 数：从"数目"到抽象数学概念
        {"word": "数", "meaning": "计数，数目（古义）", "math_symbol": "—", "math_expr": "—", "domain": "古汉语", "era": "先秦"},
        {"word": "数", "meaning": "术数，占卜；数目字（汉代）", "math_symbol": "数", "math_expr": "—", "domain": "古代算术", "era": "汉唐"},
        {"word": "数", "meaning": "抽象数字，实数/复数体系", "math_symbol": "n", "math_expr": "n ∈ ℝ", "domain": "代数", "era": "近代"},
        {"word": "数", "meaning": "数值，数据，数量（计算机科学）", "math_symbol": "num", "math_expr": "num ∈ ℝⁿ", "domain": "计算机科学", "era": "当代"},

        # 代数
        {"word": "和", "meaning": "两个或多个数相加的结果", "math_symbol": "Σ", "math_expr": "a + b", "domain": "算术", "era": "先秦"},
        {"word": "差", "meaning": "两个数相减的结果", "math_symbol": "Δ", "math_expr": "a - b", "domain": "算术", "era": "先秦"},
        {"word": "积", "meaning": "两个或多个数相乘的结果", "math_symbol": "Π", "math_expr": "a * b", "domain": "算术", "era": "先秦"},
        {"word": "商", "meaning": "两数相除的结果", "math_symbol": "÷", "math_expr": "a / b", "domain": "算术", "era": "先秦"},
        {"word": "平方", "meaning": "一个数自乘", "math_symbol": "x²", "math_expr": "x * x", "domain": "代数", "era": "先秦"},
        {"word": "立方", "meaning": "一个数自乘三次", "math_symbol": "x³", "math_expr": "x * x * x", "domain": "代数", "era": "先秦"},
        {"word": "开方", "meaning": "求一个数的方根", "math_symbol": "√", "math_expr": "x = √a (a = x²)", "domain": "代数", "era": "先秦"},
        {"word": "对数", "meaning": "幂运算的逆运算", "math_symbol": "log", "math_expr": "log_b(a) = c ↔ b^c = a", "domain": "代数", "era": "明清"},
        {"word": "指数", "meaning": "幂运算中的次方数", "math_symbol": "n", "math_expr": "a^n", "domain": "代数", "era": "明清"},

        # 集合
        {"word": "并集", "meaning": "两个集合所有元素的合集", "math_symbol": "∪", "math_expr": "A ∪ B = {x | x∈A ∨ x∈B}", "domain": "集合论", "era": "现代"},
        {"word": "交集", "meaning": "两个集合共同元素的合集", "math_symbol": "∩", "math_expr": "A ∩ B = {x | x∈A ∧ x∈B}", "domain": "集合论", "era": "现代"},
        {"word": "差集", "meaning": "属于A但不属于B的元素", "math_symbol": "⊖", "math_expr": "A ⊖ B = {x | x∈A ∧ x∉B}", "domain": "集合论", "era": "现代"},
        {"word": "子集", "meaning": "一个集合的所有元素属于另一个集合", "math_symbol": "⊆", "math_expr": "A ⊆ B ↔ ∀x(x∈A → x∈B)", "domain": "集合论", "era": "现代"},
        {"word": "笛卡尔积", "meaning": "两个集合所有有序对的集合", "math_symbol": "×", "math_expr": "A × B = {(a,b) | a∈A ∧ b∈B}", "domain": "集合论", "era": "现代"},

        # 统计
        {"word": "平均", "meaning": "所有数据之和除以数据个数", "math_symbol": "μ", "math_expr": "μ = Σx_i / n", "domain": "统计", "era": "近代"},
        {"word": "标准差", "meaning": "数据偏离平均值的程度", "math_symbol": "σ", "math_expr": "σ = √(Σ(x_i-μ)²/n)", "domain": "统计", "era": "现代"},
        {"word": "概率", "meaning": "事件发生的可能性大小", "math_symbol": "P", "math_expr": "P(A) = |A|/|Ω|", "domain": "概率", "era": "近代"},

        # 当代AI/计算
        {"word": "学习率", "meaning": "模型参数每次更新的步长", "math_symbol": "η", "math_expr": "θ := θ - η*∇L", "domain": "机器学习", "era": "当代"},
        {"word": "损失", "meaning": "模型预测与真实值之间的误差", "math_symbol": "L", "math_expr": "L = Σ(y_pred - y_true)²", "domain": "机器学习", "era": "当代"},
        {"word": "梯度", "meaning": "函数在各方向上的变化率向量", "math_symbol": "∇f", "math_expr": "∇f = (∂f/∂x₁, ∂f/∂x₂, ...)", "domain": "机器学习", "era": "当代"},
        {"word": "权重", "meaning": "神经网络中连接两个节点的参数", "math_symbol": "w", "math_expr": "y = Σ(w_i * x_i) + b", "domain": "机器学习", "era": "当代"},
        {"word": "特征", "meaning": "描述数据对象的属性或维度", "math_symbol": "x", "math_expr": "x = [x₁, x₂, ..., x_n]", "domain": "机器学习", "era": "当代"},
        {"word": "维度", "meaning": "数据空间的独立坐标轴数量", "math_symbol": "n", "math_expr": "x ∈ ℝⁿ", "domain": "线性代数", "era": "当代"},
        {"word": "矩阵", "meaning": "按矩形排列的数表", "math_symbol": "A", "math_expr": "A ∈ ℝᵐˣⁿ", "domain": "线性代数", "era": "近代"},
        {"word": "向量", "meaning": "有大小和方向的量", "math_symbol": "v", "math_expr": "v = (v₁, v₂, ..., v_n)", "domain": "线性代数", "era": "近代"},
        {"word": "张量", "meaning": "向量和矩阵的推广，多维数组", "math_symbol": "T", "math_expr": "T[i,j,k,...]", "domain": "线性代数", "era": "当代"},
        {"word": "嵌入", "meaning": "将离散对象映射到连续向量空间", "math_symbol": "e", "math_expr": "e = f(word) ∈ ℝᵈ", "domain": "机器学习", "era": "当代"},
        {"word": "注意力", "meaning": "模型对输入不同部分的关注权重", "math_symbol": "α", "math_expr": "α_ij = softmax(Qi·Kj/√d)", "domain": "机器学习", "era": "当代"},
        {"word": "上下文", "meaning": "模型处理时参考的周边信息", "math_symbol": "ctx", "math_expr": "ctx = [token₁, token₂, ...]", "domain": "NLP", "era": "当代"},
        {"word": "语义", "meaning": "语言表达的含义", "math_symbol": "sem", "math_expr": "sem(text) → vector ∈ ℝᵈ", "domain": "NLP", "era": "当代"},
        {"word": "定义", "meaning": "对概念内涵的精确规定", "math_symbol": "def", "math_expr": "def 概念 = {必要且充分条件}", "domain": "逻辑", "era": "当代"},
        {"word": "条目", "meaning": "列表中的一项记录", "math_symbol": "item", "math_expr": "item ∈ list", "domain": "数据结构", "era": "当代"},
        {"word": "时代", "meaning": "具有共同特征的历史时期", "math_symbol": "era", "math_expr": "era ∈ {先秦,汉唐,宋元,明清,近代,现代,当代}", "domain": "时间", "era": "当代"},
        {"word": "转化", "meaning": "从一种形式变为另一种形式", "math_symbol": "f", "math_expr": "y = f(x)", "domain": "映射", "era": "当代"},
        {"word": "公式", "meaning": "用数学符号表达的规律", "math_symbol": "φ", "math_expr": "φ: 自然语言 → 数学表达式", "domain": "元数学", "era": "当代"},
        {"word": "代码", "meaning": "计算机可执行的指令序列", "math_symbol": "cod", "math_expr": "cod = compile(公式)", "domain": "计算机科学", "era": "当代"},
        {"word": "自然语言", "meaning": "人类日常使用的语言（如中文、英文）", "math_symbol": "NL", "math_expr": "NL = {词,短语,句子}", "domain": "语言学", "era": "当代"},
        {"word": "理解", "meaning": "对语言含义的解析和把握", "math_symbol": "understand", "math_expr": "understand(NL) → 语义表示", "domain": "认知科学", "era": "当代"},
        {"word": "消歧", "meaning": "消除词汇的多义性", "math_symbol": "disambiguate", "math_expr": "disambiguate(word, context) → 唯一语义", "domain": "NLP", "era": "当代"},
    ]

    # 每个词的别名映射
    _ALIAS_MAP: dict[str, list[str]] = {
        "速度": ["速率", "快慢", "速率大小"],
        "加速度": ["加减速度", "加速"],
        "面积": ["覆盖面", "表面大小"],
        "体积": ["容积", "容量"],
        "并集": ["合集", "或集"],
        "交集": ["共集", "与集"],
        "位移": ["位置变化", "形变"],
        "力": ["作用力", "推力", "拉力"],
        "质量": ["物质量", "惯性质量"],
        "功": ["做功", "力学功"],
        "能": ["能量", "效能"],
        "动能": ["运动能"],
        "势能": ["位能", "潜在能"],
        "动量": ["运动量", "quantity of motion"],
        "标准差": ["均方根偏差", "均方差"],
        "矩阵": ["阵列", "表"],
        "向量": ["矢量", "direction"],
        "张量": ["多元阵列"],
        "梯度": ["斜率向量", "gradient"],
        "权重": ["权值", "weight"],
        "特征": ["属性", "feature"],
        "维度": ["维数", "dimension"],
        "嵌入": ["嵌入向量", "embedding"],
        "注意力": ["attention机制"],
        "上下文": ["语境", "context"],
        "语义": ["意义", "meaning"],
        "定义": ["界定", "definition"],
        "条目": ["项目", "项"],
        "时代": ["时期", "era"],
        "转化": ["转换", "transform"],
        "公式": ["式子", "formula"],
        "代码": ["程序", "source code"],
        "自然语言": ["口语", "人类语言"],
        "理解": ["解析", "interpret"],
        "消歧": ["去歧义", "disambiguation"],
        "线": ["直线", "曲线", "线条"],
        "点": ["节点", "端点", "datum"],
        "数": ["数字", "数值", "数量", "数据"],
    }

    # 时代关键词
    _ERA_KEYWORDS: dict[str, list[str]] = {
        "先秦": ["古", "周", "春秋", "战国", "九章", "算经", "勾股", "方程", "开方"],
        "汉唐": ["汉", "唐", "九章算术", "孙子", "张丘建", "算经十书"],
        "宋元": ["宋", "元", "天元术", "四元术", "秦九韶", "朱世杰"],
        "明清": ["明", "清", "西方", "传入", "利玛窦", "测量法"],
        "近代": ["近代", "现代数学", "微积分", "牛顿", "莱布尼茨", "微分", "积分"],
        "现代": ["现代", "集合论", "公理化", "离散", "计算机", "图论"],
        "当代": ["当代", "AI", "人工智能", "机器学习", "深度学习", "大模型", "自然语言", "语义", "上下文"],
    }

    def __init__(self):
        self._entries: dict[str, list[SemanticEntry]] = {}
        self._build_index()

    def _build_index(self):
        """构建词到语义条目的索引。"""
        for entry_dict in self._CORE_ENTRIES:
            word = entry_dict["word"]
            # 从 _ALIAS_MAP 补充别名
            aliases = entry_dict.get("aliases", []) + self._ALIAS_MAP.get(word, [])
            entry = SemanticEntry(
                word=word,
                meaning=entry_dict["meaning"],
                math_symbol=entry_dict["math_symbol"],
                math_expr=entry_dict.get("math_expr", ""),
                domain=entry_dict["domain"],
                era=entry_dict["era"],
                note=entry_dict.get("note", ""),
                aliases=aliases,
            )
            if word not in self._entries:
                self._entries[word] = []
            self._entries[word].append(entry)

            # 注册别名
            for alias in entry.aliases:
                if alias not in self._entries:
                    self._entries[alias] = []
                self._entries[alias].append(entry)

    def lookup(self, word: str, era: str = "当代") -> Optional[SemanticEntry]:
        """
        查询某词在指定时代的语义。

        Args:
            word: 要查询的词
            era: 时代（默认"当代"）

        Returns:
            SemanticEntry 或 None
        """
        candidates = self._entries.get(word, [])
        if not candidates:
            return None

        # 优先匹配指定时代
        for entry in candidates:
            if entry.era == era:
                return entry

        # 其次匹配"近代"或"现代"
        for entry in candidates:
            if entry.era in ("近代", "现代"):
                return entry

        # 最后返回最早的条目
        return candidates[0]

    def list_eras(self, word: str) -> list[SemanticEntry]:
        """列出某词在所有时代的语义。"""
        return self._entries.get(word, [])

    def resolve_ambiguity(self, word: str, context: str, era: str = "当代") -> Optional[SemanticEntry]:
        """
        根据上下文消歧。

        Args:
            word: 有歧义的词
            context: 上下文文本
            era: 时代

        Returns:
            消歧后的语义条目
        """
        candidates = self._entries.get(word, [])
        if len(candidates) <= 1:
            return candidates[0] if candidates else None

        # 简单消歧：检查上下文关键词
        best_match = None
        best_score = 0

        for entry in candidates:
            score = 0
            # 领域匹配
            if entry.domain in context or any(kw in context for kw in entry.domain):
                score += 3
            # 时代匹配
            if entry.era == era:
                score += 2
            # 词义关键词匹配
            for kw in entry.meaning.split("，") + entry.meaning.split("、"):
                if kw.strip() and kw.strip() in context:
                    score += 1
            if score > best_score:
                best_score = score
                best_match = entry

        return best_match if best_match else candidates[0]

    def extract_words(self, text: str) -> list[tuple[str, int, int]]:
        """
        从自然语言文本中提取已知词汇及其位置。

        Returns:
            [(word, start_pos, end_pos), ...]
        """
        results = []
        # 按长度降序排列词，避免短词匹配覆盖长词
        sorted_words = sorted(self._entries.keys(), key=len, reverse=True)
        for word in sorted_words:
            pattern = re.compile(re.escape(word))
            for match in pattern.finditer(text):
                results.append((word, match.start(), match.end()))
        return results

    def build_semantic_map(self, text: str, era: str = "当代") -> dict[str, SemanticEntry]:
        """
        从文本构建完整的语义映射。

        处理重叠匹配，优先选择更长的匹配。

        Returns:
            {word: SemanticEntry}
        """
        extracted = self.extract_words(text)
        # 按起始位置排序，处理重叠
        extracted.sort(key=lambda x: (x[1], -x[2]))

        result = {}
        used_ranges = []
        for word, start, end in extracted:
            # 检查是否与已选范围重叠
            overlap = False
            for us, ue in used_ranges:
                if start < ue and end > us:
                    overlap = True
                    break
            if not overlap:
                entry = self.lookup(word, era=era)
                if entry:
                    result[word] = entry
                    used_ranges.append((start, end))
        return result


# ============================================================
#  便捷函数
# ============================================================

def create_dictionary() -> NLDictionary:
    """创建并返回语义词典实例。"""
    return NLDictionary()


def lookup(word: str, era: str = "当代") -> Optional[SemanticEntry]:
    """便捷查询：lookup(word, era) → SemanticEntry"""
    return NLDictionary().lookup(word, era)


def list_all_eras(word: str) -> list[SemanticEntry]:
    """列出某词的所有时代语义。"""
    return NLDictionary().list_eras(word)
