# -*- coding: utf-8 -*-
"""v1.2.16 补丁脚本 — 冷门专业自主扩展（干净版，无三重引号嵌套问题）

修复内容：
  1. 语法错误：第64行 stray dot，第174行多余 })
  2. 双重 apply：确保只执行一次替换
"""
import re
import sys
import os

# 切换到项目根目录
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PATH = 'src/ai_assistant.py'
with open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()

original = content
changes = []

# ── 1. IntentType 新增 8 个冷门专业意图 ─────────────────────────────────────
if '概率统计 = "probability"' not in content:
    old = '''    三角函数 = "trig"
    未知 = "unknown"'''
    new = '''    三角函数 = "trig"
    概率统计 = "probability"
    数列 = "sequence"
    几何 = "geometry"
    财务 = "finance"
    烹饪 = "cooking"
    时间计算 = "time_calc"
    配置浓度 = "concentration"
    未知 = "unknown"'''
    content = content.replace(old, new, 1)
    changes.append("IntentType: +8 新类型")

# ── 2. __init__ 增加成长记忆系统 ─────────────────────────────────────────────
if '_failure_log' not in content:
    old = '''        self._learned_patterns: dict[str, IntentType] = {}  # 学习用户表达'''
    new = '''        self._learned_patterns: dict[str, IntentType] = {}  # 学习用户表达
        # ── 成长记忆系统 ────────────────────────────────
        self._failure_log: list[dict] = []       # 执行失败记录
        self._correction_log: list[dict] = []    # 用户纠正记录
        self._growth_log: list[dict] = []        # 成长日志
        self._known_expressions: dict[str, str] = {}  # 已知表达→意图'''
    content = content.replace(old, new, 1)
    changes.append("__init__: +成长记忆系统")

# ── 3. learn() 增强 + 新增方法 ───────────────────────────────────────────────
if '_known_expressions[text] = intent.value' not in content:
    # 在 learn 方法末尾追加持久化代码
    old_learn = '''                self._learned_patterns[word] = intent
        _logger.info(f"学习新模式: \'{text}\' → {intent.value}")'''
    new_learn = '''                self._learned_patterns[word] = intent
        # 持久化到已知表达库
        self._known_expressions[text] = intent.value
        _logger.info(f"学习新模式: \'{text}\' → {intent.value}")
        self._growth_log.append({
            "action": "learn", "text": text,
            "intent": intent.value, "time": time.time()
        })
        _logger.info(f"  [成长] 学习记录已保存，累计 {len(self._growth_log)} 条")

    def record_failure(self, text: str, error: str, intent: IntentType) -> None:
        \"\"\"记录执行失败，用于后续自动学习修复。\"\"\"
        entry = {"text": text, "error": error[:100],
                 "intent": intent.value, "time": time.time()}
        self._failure_log.append(entry)
        _logger.warning(f"  [成长] 记录失败: \'{text}\' → {error[:50]}")
        self._auto_learn_from_failure(text, error)

    def _auto_learn_from_failure(self, text: str, error: str) -> None:
        \"\"\"从失败中自动学习，生成修复建议。\"\"\"
        if "未定义函数" in error:
            m = re.search(r"[未定义]+(?:函数|变量)?\\s*['\\\"]?([^'\\\"]+)['\\\"]?", error)
            if m:
                fn = m.group(1).strip()
                _logger.info(f"  [自动学习] 发现未定义函数: \'{fn}\'，建议添加内建")
                self._growth_log.append({"action": "auto_learn_func",
                                         "suggestion": fn, "time": time.time()})
        if "未定义变量" in error:
            m = re.search(r"[未定义]+(?:变量)?\\s*['\\\"]?([^'\\\"]+)['\\\"]?", error)
            if m:
                var = m.group(1).strip()
                _logger.info(f"  [自动学习] 发现未定义变量: \'{var}\'，建议添加常量")
                self._growth_log.append({"action": "auto_learn_var",
                                         "suggestion": var, "time": time.time()})

    def record_correction(self, original_text: str, original_intent: str,
                          corrected_intent: str) -> None:
        \"\"\"记录用户纠正，用于提升分类准确度。\"\"\"
        entry = {"original": original_text, "original_intent": original_intent,
                 "corrected_intent": corrected_intent, "time": time.time()}
        self._correction_log.append(entry)
        self._known_expressions[original_text] = corrected_intent
        _logger.info(f"  [成长] 用户纠正: \'{original_text}\' {original_intent}→{corrected_intent}")
        words = re.findall(r'[\\u4e00-\\u9fa5]+', original_text)
        for word in words:
            if len(word) >= 2:
                try:
                    self._learned_patterns[word] = IntentType(corrected_intent)
                except ValueError:
                    pass
        self._growth_log.append({"action": "correction", "text": original_text,
                                 "from": original_intent, "to": corrected_intent,
                                 "time": time.time()})

    def get_growth_stats(self) -> dict:
        \"\"\"返回成长统计数据。\"\"\"
        return {
            "total_learned": len(self._learned_patterns),
            "total_failures": len(self._failure_log),
            "total_corrections": len(self._correction_log),
            "total_growth_records": len(self._growth_log),
            "known_expressions": len(self._known_expressions),
            "recent_growth": self._growth_log[-5:] if self._growth_log else []
        }'''
    content = content.replace(old_learn, new_learn, 1)
    changes.append("learn(): +持久化+record_failure+record_correction+get_growth_stats")

# ── 4. ERROR_EXPLANATIONS 扩充 ───────────────────────────────────────────────
if '"未定义函数"' not in content:
    old_err = '''        "ParseError": {
            "小白解释": "代码语法有误，请检查符号和括号。",
            "怎么修": "Matha 代码需要用特定的符号格式。",
            "例子": "正确格式：#1: a + b = 结果\\n错误：#1: a + b",
        },
    }'''
    new_err = '''        "ParseError": {
            "小白解释": "代码语法有误，请检查符号和括号。",
            "怎么修": "Matha 代码需要用特定的符号格式。",
            "例子": "正确格式：#1: a + b = 结果\\n错误：#1: a + b",
        },
        "未定义函数": {
            "小白解释": "你调用了一个还没有定义的公式。需要先定义它。",
            "怎么修": "加一行函数定义，比如：func 打折价(原价,折扣)->Float=(原价)=>原价*折扣/10",
            "例子": "func 打折价(原价,折扣)->Float=(原价)=>原价*折扣/10\\n#1: 打折价(100, 8) = 结果\\n#1: [结果]",
        },
        "未定义变量": {
            "小白解释": "你用到了一个还没有定义的数。需要先告诉系统它是多少。",
            "怎么修": "在前面加一行声明，比如：@：x=10",
            "例子": "@：原价=100\\n#1: 原价 * 0.8 = 结果\\n#1: [结果]",
        },
        "除零错误": {
            "小白解释": "你试图除以 0，这在数学上没有意义。",
            "怎么修": "检查除数（分母）是否可能为 0。",
            "例子": "如果除数是变量，先判断：if 除数 != 0, 再计算",
        },
    }'''
    content = content.replace(old_err, new_err, 1)
    changes.append("ERROR_EXPLANATIONS: +未定义函数/变量/除零")

# ── 5. MATH_CONCEPTS 扩充 ────────────────────────────────────────────────────
if '"概率"' not in content or '"单利"' not in content:
    old_conc = '''        "三角函数": {
            "是什么": "描述三角形边角关系的函数。",
            "符号": "sin, cos, tan",
            "例子": "sin(90°) = 1，cos(0°) = 1",
            "生活中的例子": "建筑工程、游戏开发、导航定位。",
        },
    }'''
    new_conc = '''        "三角函数": {
            "是什么": "描述三角形边角关系的函数。",
            "符号": "sin, cos, tan",
            "例子": "sin(90°) = 1，cos(0°) = 1",
            "生活中的例子": "建筑工程、游戏开发、导航定位。",
        },
        "概率": {
            "是什么": "一个事件发生的可能性，用 0 到 1 之间的数表示。",
            "符号": "P(A)",
            "例子": "掷硬币正面朝上的概率 = 1/2 = 0.5",
            "生活中的例子": "天气预报降雨概率、彩票中奖率。",
        },
        "期望值": {
            "是什么": "随机事件的长期平均结果。",
            "符号": "E[X]",
            "例子": "掷骰子的期望值 = (1+2+3+4+5+6)/6 = 3.5",
            "生活中的例子": "保险精算、投资预期收益。",
        },
        "等差数列": {
            "是什么": "后一项减前一项的差是固定值的数列。",
            "符号": "a_n = a_1 + (n-1)d",
            "例子": "2, 5, 8, 11... 公差 d=3，第10项 = 2+(10-1)*3 = 29",
            "生活中的例子": "阶梯定价、等间距种植。",
        },
        "等比数列": {
            "是什么": "后一项除以前一项的比是固定值的数列。",
            "符号": "a_n = a_1 * r^(n-1)",
            "例子": "2, 6, 18, 54... 公比 r=3，第5项 = 2*3^4 = 162",
            "生活中的例子": "细胞分裂、复利增长。",
        },
        "长方形面积": {
            "是什么": "长乘以宽。",
            "符号": "S = 长 × 宽",
            "例子": "长5米宽3米的房间，面积 = 5 × 3 = 15 平方米",
            "生活中的例子": "房间面积、地板面积。",
        },
        "圆的面积": {
            "是什么": "π乘以半径的平方。",
            "符号": "S = πr²",
            "例子": "半径3米的圆形花坛，面积 ≈ 28.27 平方米",
            "生活中的例子": "圆形花坛、披萨面积。",
        },
        "单利": {
            "是什么": "利息只按本金计算，不加入本金复利。",
            "符号": "利息 = 本金 × 利率 × 时间",
            "例子": "存10000元，年利率5%，3年后利息 = 1500元",
            "生活中的例子": "定期存款、国债利息。",
        },
        "复利": {
            "是什么": "利息加入本金继续产生利息，利滚利。",
            "符号": "本利和 = 本金 × (1+利率)^时间",
            "例子": "存10000元，年利率5%，3年后 ≈ 11576元",
            "生活中的例子": "银行存款复利、基金定投。",
        },
        "折扣": {
            "是什么": "原价乘以折扣比例（打X折 = 原价×X/10）。",
            "符号": "折后价 = 原价 × 折扣/10",
            "例子": "原价200元打七折 = 140元",
            "生活中的例子": "商场促销、双十一打折。",
        },
        "配比浓度": {
            "是什么": "溶质质量除以溶液总质量。",
            "符号": "浓度 = 溶质 / (溶质 + 溶剂) × 100%",
            "例子": "10克盐溶在90克水里，浓度 = 10%",
            "生活中的例子": "调制饮料、配制消毒液。",
        },
        "配速": {
            "是什么": "跑每公里所需的时间。",
            "符号": "配速 = 时间 / 距离",
            "例子": "跑10公里用了50分钟，配速 = 5分钟/公里",
            "生活中的例子": "跑步训练、马拉松配速。",
        },
    }'''
    content = content.replace(old_conc, new_conc, 1)
    changes.append("MATH_CONCEPTS: +12 新概念")

# ── 6. SYNONYM_MAP 扩充 ─────────────────────────────────────────────────────
if '"利息"' not in content:
    old_syn = '''        "射程": ["射程", "飞多远", "飞多高", "落点", "飞行距离"],
    }'''
    new_syn = '''        "射程": ["射程", "飞多远", "飞多高", "落点", "飞行距离"],
        "打折": ["打折", "折扣", "打X折", "优惠", "降价", "贵了", "便宜了", "贵多少", "便宜多少", "满减"],
        "利息": ["利息", "单利", "复利", "利滚利", "年化利率", "存款利率", "贷款利率"],
        "面积": ["面积", "平方", "平方米", "平方厘米", "平方千米", "亩"],
        "概率": ["概率", "可能性", "几率", "概率论", "期望", "期望值"],
        "数列": ["等差", "等比", "数列", "递推", "通项", "求和"],
        "浓度": ["浓度", "配比", "稀释", "溶质", "溶液", "百分比浓度"],
        "配速": ["配速", "每公里", "每分钟", "跑速", "时速"],
        "体积": ["体积", "容积", "升", "毫升", "立方米", "立方厘米"],
    }'''
    content = content.replace(old_syn, new_syn, 1)
    changes.append("SYNONYM_MAP: +9 新组")

# ── 写入文件 ─────────────────────────────────────────────────────────────────
if content != original:
    with open(PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ 已应用 {len(changes)} 项更改到 {PATH}:")
    for c in changes:
        print(f"    - {c}")
else:
    print("✓ 所有更改已应用，无需重复操作")

# ── 验证语法 ─────────────────────────────────────────────────────────────────
try:
    import ast
    ast.parse(content)
    print("✓ 语法检查通过")
except SyntaxError as e:
    print(f"✗ 语法错误: {e}")
    sys.exit(1)

# ── 验证导入 ─────────────────────────────────────────────────────────────────
try:
    import importlib
    if 'src.ai_assistant' in sys.modules:
        importlib.reload(sys.modules['src.ai_assistant'])
    else:
        import src.ai_assistant
    print("✓ 导入检查通过")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

print("\n补丁应用完成！")
