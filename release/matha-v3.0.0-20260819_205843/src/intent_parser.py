# -*- coding: utf-8 -*-
"""Matha 意图识别解析器 — v2.2

将自然语言输入转换为计算意图描述，
供 Matha 引擎自动编译和执行。

架构：
  自然语言 → 意图分类 → 参数提取 → 目标语言选择 → 代码生成
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum, auto


# ============================================================
# 意图类型
# ============================================================

class IntentType(Enum):
    """计算意图类型。"""
    ARITHMETIC = auto()     # 算术运算
    STRING_OP = auto()      # 字符串操作
    ARRAY_OP = auto()       # 数组操作
    CONDITIONAL = auto()    # 条件判断
    LOOP = auto()           # 循环迭代
    FUNCTION = auto()       # 函数定义
    DATA_STRUCT = auto()    # 数据结构
    ALGORITHM = auto()      # 算法实现
    MATH_FUNC = auto()      # 数学函数
    COMPARISON = auto()     # 比较运算
    CONVERSION = auto()     # 类型转换
    FILE_IO = auto()        # 文件操作
    UNKNOWN = auto()


@dataclass
class Intent:
    """计算意图描述。"""
    intent_type: IntentType
    description: str
    params: dict = field(default_factory=dict)
    target_lang: str = "python"  # 目标语言
    confidence: float = 0.0
    suggested_code: str = ""
    errors: list = field(default_factory=list)

    def is_valid(self) -> bool:
        return self.intent_type != IntentType.UNKNOWN and self.confidence > 0.3


# ============================================================
# 意图分类器
# ============================================================

class IntentClassifier:
    """意图分类器。"""

    # 算术关键词
    _ARITHMETIC_PATTERNS = [
        (r'计算|算|求|加减乘除|加上|减去|乘以|除以|平方|开方|幂|次方', IntentType.ARITHMETIC),
        (r'总和|合计|累加|求和|平均|均值', IntentType.ARITHMETIC),
        (r'最大|最小|最高|最低', IntentType.COMPARISON),
    ]

    # 字符串关键词
    _STRING_PATTERNS = [
        (r'(字符串|文字|文本|拼接|连接|替换|截取|拆分|反转|统计字数|长度)', IntentType.STRING_OP),
        (r'(判断包含|是否含有|开始|结尾)', IntentType.STRING_OP),
    ]

    # 数组关键词
    _ARRAY_PATTERNS = [
        (r'(数组|列表|序列|排序|过滤|映射|归约|去重|分块|扁平)', IntentType.ARRAY_OP),
        (r'(遍历|迭代|循环处理)', IntentType.LOOP),
    ]

    # 条件关键词
    _CONDITIONAL_PATTERNS = [
        (r'(如果|假如|判断|是否|条件|分支)', IntentType.CONDITIONAL),
    ]

    # 循环关键词
    _LOOP_PATTERNS = [
        (r'(循环|迭代|遍历|从.*到|依次|逐个)', IntentType.LOOP),
    ]

    # 数学函数关键词（中文不用 \b 因为中文字符非 word char）
    # 用 (?!\u7ec4) 避免 "对数" 误匹配 "对数组" 中的 "对数"
    _MATH_PATTERNS = [
        (r'正弦(?![\u4e00-\u9fff])|余弦(?![\u4e00-\u9fff])|正切(?![\u4e00-\u9fff])|对数(?![\u4e00-\u9fff])|指数(?![\u4e00-\u9fff])|平方根(?![\u4e00-\u9fff])|绝对值(?![\u4e00-\u9fff])|取整(?![\u4e00-\u9fff])|舍入(?![\u4e00-\u9fff])', IntentType.MATH_FUNC),
        (r'gcd|lcm|素数|质数|因数|因子|阶乘|斐波那契', IntentType.MATH_FUNC),
    ]

    # 转换关键词
    _CONVERSION_PATTERNS = [
        (r'(转换|转化|类型|整数转|字符串转|转成|罗马数字)', IntentType.CONVERSION),
    ]

    # 函数定义关键词
    _FUNCTION_PATTERNS = [
        (r'(定义函数|创建一个函数|函数名为|函数叫)', IntentType.FUNCTION),
    ]

    def classify(self, text: str) -> IntentType:
        """对文本进行分类，返回最匹配的意图类型。

        优先级：MATH_FUNC > ARITHMETIC > STRING_OP > ARRAY_OP > ...
        """
        text_lower = text.lower()
        scores: dict[IntentType, int] = {}

        # 先检查高优先级模式
        for pattern, intent_type in self._MATH_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 2  # 高权重

        for pattern, intent_type in self._ARITHMETIC_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._STRING_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._ARRAY_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._CONDITIONAL_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._LOOP_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._CONVERSION_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        for pattern, intent_type in self._FUNCTION_PATTERNS:
            if re.search(pattern, text_lower):
                scores[intent_type] = scores.get(intent_type, 0) + 1

        if not scores:
            return IntentType.UNKNOWN

        return max(scores, key=scores.get)


# ============================================================
# 参数提取器
# ============================================================

class ParamExtractor:
    """从自然语言中提取参数。"""

    # 数字模式
    _NUM_PATTERN = re.compile(r'-?\d+\.?\d*')
    # 变量名模式
    _VAR_PATTERN = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b')
    # 范围模式 如 "1到100"
    _RANGE_PATTERN = re.compile(r'(\d+)\s*[到至从]*\s*(\d+)')

    def extract_numbers(self, text: str) -> list[float]:
        """提取所有数字。"""
        return [float(x) for x in self._NUM_PATTERN.findall(text)]

    def extract_variables(self, text: str) -> list[str]:
        """提取变量名（排除关键词）。"""
        keywords = {'如果', '当', '为', '等于', '大于', '小于', '并且', '或者',
                    '循环', '对于', '每个', '返回', '函数', '定义', '数组',
                    '字符串', '列表', '整数', '浮点', '布尔', '真', '假'}
        vars_found = self._VAR_PATTERN.findall(text)
        return [v for v in vars_found if v.lower() not in keywords]

    def extract_range(self, text: str) -> Optional[tuple[int, int]]:
        """提取范围 (start, end)。"""
        m = self._RANGE_PATTERN.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None


# ============================================================
# 代码生成器
# ============================================================

class CodeGenerator:
    """根据意图生成目标语言代码。"""

    def generate_python(self, intent: Intent) -> str:
        """生成 Python 代码。"""
        it = intent.intent_type
        params = intent.params

        templates = {
            IntentType.ARITHMETIC: self._gen_arithmetic,
            IntentType.STRING_OP: self._gen_string_op,
            IntentType.ARRAY_OP: self._gen_array_op,
            IntentType.MATH_FUNC: self._gen_math_func,
            IntentType.CONDITIONAL: self._gen_conditional,
            IntentType.LOOP: self._gen_loop,
            IntentType.CONVERSION: self._gen_conversion,
        }

        gen_fn = templates.get(it, self._gen_generic)
        return gen_fn(intent, params)

    def _gen_arithmetic(self, intent: Intent, params: dict) -> str:
        nums = params.get('numbers', [])
        if len(nums) >= 2:
            return f"result = {nums[0]} + {nums[1]}"
        return "result = 0  # 需要具体数字"

    def _gen_string_op(self, intent: Intent, params: dict) -> str:
        s = params.get('text', '""')
        return f'result = str({s})'

    def _gen_array_op(self, intent: Intent, params: dict) -> str:
        items = params.get('items', [])
        return f"result = {items}"

    def _gen_math_func(self, intent: Intent, params: dict) -> str:
        nums = params.get('numbers', [])
        if nums:
            return f"import math\nresult = math.sqrt({nums[0]})"
        return "import math\nresult = 0"

    def _gen_conditional(self, intent: Intent, params: dict) -> str:
        return "if condition:\n    result = True\nelse:\n    result = False"

    def _gen_loop(self, intent: Intent, params: dict) -> str:
        nums = params.get('numbers', [])
        start, end = (nums[0], nums[1]) if len(nums) >= 2 else (0, 10)
        return f"result = []\nfor i in range({int(start)}, {int(end)}):\n    result.append(i)"

    def _gen_conversion(self, intent: Intent, params: dict) -> str:
        return "result = int(text)"

    def _gen_generic(self, intent: Intent, params: dict) -> str:
        return f"# 意图: {intent.description}\n# 参数: {params}\nresult = None"

    def generate(self, intent: Intent, target_lang: str = "python") -> str:
        """根据目标语言生成代码。"""
        if target_lang == "python":
            return self.generate_python(intent)
        elif target_lang == "rust":
            return self._gen_rust(intent)
        elif target_lang == "go":
            return self._gen_go(intent)
        return self.generate_python(intent)

    def _gen_rust(self, intent: Intent) -> str:
        return f"// 意图: {intent.description}\n// 目标: Rust\nlet result = 0i32;"

    def _gen_go(self, intent: Intent) -> str:
        return f"// 意图: {intent.description}\n// 目标: Go\nvar result int = 0"


# ============================================================
# 主意图解析器
# ============================================================

class IntentParser:
    """意图解析器 — 自然语言 → 计算意图 → 代码。"""

    def __init__(self):
        self.classifier = IntentClassifier()
        self.extractor = ParamExtractor()
        self.generator = CodeGenerator()

    def parse(self, text: str, target_lang: str = "python") -> Intent:
        """解析自然语言，返回计算意图。

        参数:
            text: 自然语言输入
            target_lang: 目标编程语言（默认 python）

        返回:
            Intent 对象，包含意图类型、参数、生成代码等
        """
        intent = Intent(
            intent_type=IntentType.UNKNOWN,
            description=text,
            target_lang=target_lang,
            confidence=0.0,
        )

        # 1. 分类
        intent.intent_type = self.classifier.classify(text)
        intent.description = self._describe_intent(intent.intent_type, text)

        # 2. 提取参数
        nums = self.extractor.extract_numbers(text)
        vars_found = self.extractor.extract_variables(text)
        rng = self.extractor.extract_range(text)

        intent.params = {
            "numbers": nums,
            "variables": vars_found,
            "range": rng,
            "raw_text": text,
        }

        # 3. 置信度
        intent.confidence = self._calc_confidence(intent, text)

        # 4. 生成代码
        if intent.confidence > 0.3:
            intent.suggested_code = self.generator.generate(intent, target_lang)

        return intent

    def _describe_intent(self, itype: IntentType, text: str) -> str:
        """将意图类型转为描述。"""
        descriptions = {
            IntentType.ARITHMETIC: "算术运算",
            IntentType.STRING_OP: "字符串操作",
            IntentType.ARRAY_OP: "数组操作",
            IntentType.CONDITIONAL: "条件判断",
            IntentType.LOOP: "循环迭代",
            IntentType.FUNCTION: "函数定义",
            IntentType.MATH_FUNC: "数学函数",
            IntentType.COMPARISON: "比较运算",
            IntentType.CONVERSION: "类型转换",
            IntentType.FILE_IO: "文件操作",
            IntentType.UNKNOWN: "未知意图",
        }
        return descriptions.get(itype, "未分类")

    def _calc_confidence(self, intent: Intent, text: str) -> float:
        """计算置信度。"""
        if intent.intent_type == IntentType.UNKNOWN:
            return 0.0
        # 基础置信度
        base = 0.5
        # 参数丰富度加分
        params = intent.params
        score = base
        if params.get("numbers"):
            score += 0.2
        if params.get("variables"):
            score += 0.1
        if params.get("range"):
            score += 0.1
        # 文本长度惩罚（过短可能不完整）
        if len(text) < 3:
            score -= 0.2
        return max(0.0, min(1.0, score))

    def explain(self, intent: Intent) -> str:
        """将意图转为自然语言解释。"""
        if not intent.is_valid():
            return "无法识别计算意图，请重新描述。"

        lines = [
            f"识别意图: {intent.description}",
            f"类型: {intent.intent_type.name}",
            f"置信度: {intent.confidence:.0%}",
        ]

        params = intent.params
        if params.get("numbers"):
            lines.append(f"数值参数: {params['numbers']}")
        if params.get("variables"):
            lines.append(f"变量名: {params['variables']}")
        if params.get("range"):
            s, e = params["range"]
            lines.append(f"范围: [{s}, {e}]")

        if intent.suggested_code:
            lines.append("")
            lines.append("生成代码:")
            lines.append(intent.suggested_code)

        return "\n".join(lines)


# ============================================================
# 便捷入口
# ============================================================

def parse_intent(text: str, target_lang: str = "python") -> Intent:
    """便捷函数：解析自然语言为计算意图。"""
    parser = IntentParser()
    return parser.parse(text, target_lang)


def explain_intent(text: str, target_lang: str = "python") -> str:
    """便捷函数：解析并解释自然语言意图。"""
    parser = IntentParser()
    intent = parser.parse(text, target_lang)
    return parser.explain(intent)
