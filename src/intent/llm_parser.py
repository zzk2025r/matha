# -*- coding: utf-8 -*-
"""Matha v4.2 — LLM 意图解析器

集成 Claude/DeepSeek/GPT 等 LLM API，将自然语言转换为结构化意图。

架构：
  自然语言 → LLM 解析 → 结构化意图 → MIR 代码生成

支持的后端：
  - claude (Anthropic)
  - deepseek (DeepSeek)
  - gpt (OpenAI)
  - local (Ollama 本地模型)

用法：
  from src.intent.llm_parser import LLMIntentParser

  # 方式 1: Claude
  parser = LLMIntentParser(api_key="sk-ant-...", model="claude-3-5-sonnet")

  # 方式 2: DeepSeek（低成本）
  parser = LLMIntentParser(api_key="sk-...", model="deepseek-chat")

  # 方式 3: 本地 Ollama
  parser = LLMIntentParser(model="llama3.2", base_url="http://localhost:11434/v1")

  # 解析意图
  intent = parser.parse("计算 100 以内所有素数")
  print(intent.suggested_code)
"""
from __future__ import annotations
import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


# ============================================================
# 意图类型定义
# ============================================================

class IntentType(Enum):
    """计算意图类型。"""
    ARITHMETIC = auto()      # 算术运算
    STRING_OP = auto()       # 字符串操作
    ARRAY_OP = auto()        # 数组操作
    CONDITIONAL = auto()     # 条件判断
    LOOP = auto()            # 循环迭代
    FUNCTION = auto()        # 函数定义
    DATA_STRUCT = auto()     # 数据结构
    ALGORITHM = auto()       # 算法实现
    MATH_FUNC = auto()       # 数学函数
    COMPARISON = auto()      # 比较运算
    CONVERSION = auto()      # 类型转换
    GEOMETRY = auto()        # 几何计算
    STATISTICS = auto()      # 统计分析
    UNKNOWN = auto()


@dataclass
class Intent:
    """计算意图描述。"""
    intent_type: IntentType
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    target_lang: str = "mir"  # 目标语言
    confidence: float = 0.0
    suggested_code: str = ""
    follow_up_questions: List[str] = field(default_factory=list)
    parse_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """检查意图是否有效。"""
        return self.intent_type != IntentType.UNKNOWN and self.confidence >= 0.5

    def to_dict(self) -> Dict:
        """序列化为字典。"""
        return {
            "intent_type": self.intent_type.name,
            "description": self.description,
            "params": self.params,
            "target_lang": self.target_lang,
            "confidence": self.confidence,
            "suggested_code": self.suggested_code,
            "follow_up_questions": self.follow_up_questions,
            "parse_time_ms": self.parse_time_ms,
        }


# ============================================================
# JSON Schema 定义（LLM 输出结构约束）
# ============================================================

INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": [it.name for it in IntentType if it != IntentType.UNKNOWN],
            "description": "意图类型"
        },
        "description": {
            "type": "string",
            "description": "意图的中文描述"
        },
        "params": {
            "type": "object",
            "description": "提取的参数（键值对）"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "置信度 0-1"
        },
        "mir_code": {
            "type": "string",
            "description": "生成的机械语言代码（MIR 格式）"
        },
        "follow_up_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "需要追问用户的问题列表（可选）"
        }
    },
    "required": ["intent_type", "description", "params", "confidence"]
}


# ============================================================
# LLM 意图解析器
# ============================================================

class LLMIntentParser:
    """
    基于 LLM API 的意图解析器（v4.2 核心组件）。

    支持的后端：
      - claude (Anthropic)
      - deepseek (DeepSeek)
      - gpt (OpenAI)
      - local (Ollama 本地模型)

    使用方式：
        parser = LLMIntentParser(api_key="sk-...", model="claude-3-5-sonnet")
        intent = parser.parse("计算 100 以内所有素数")
    """

    # 系统提示词模板
    SYSTEM_PROMPT = """\
你是一个数学计算意图解析器。用户用自然语言描述计算任务，
你需要将其转换为结构化的机械语言（MIR）代码。

核心原则：
1. 代码即数学 — 生成的 MIR 必须是数学公式化的，而非命令式代码
2. 精确性 — 参数提取必须精确，不猜测缺失信息
3. 可验证性 — 生成的 MIR 必须能通过类型检查
4. 完整性 — 如果用户输入模糊，在 follow_up_questions 中列出需要澄清的问题

支持的意图类型：
- ARITHMETIC: 算术运算（加减乘除、幂、开方）
- MATH_FUNC: 数学函数（正弦、余弦、对数、素数等）
- ARRAY_OP: 数组操作（排序、过滤、映射、归约）
- COMPARISON: 比较运算
- ALGORITHM: 算法实现（素数筛选、排序算法等）
"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """\
用户输入：{text}

请解析用户的计算意图，输出 JSON：
{{
  "intent_type": "<类型>",
  "description": "<中文描述>",
  "params": <参数对象>,
  "confidence": <0-1>,
  "mir_code": "<机械语言代码>",
  "follow_up_questions": [<需要追问的问题>]
}}

注意：
- mir_code 必须是有效的数学表达式或算法描述
- 如果参数缺失，在 follow_up_questions 中说明
- confidence 表示你对解析结果的置信度
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet",
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        cache_dir: str = ".matha_cache",
    ):
        """
        初始化 LLM 意图解析器。

        Args:
            api_key: API 密钥（可选，从环境变量读取）
            model: 模型名称
            base_url: API 基础 URL（可选）
            timeout: 请求超时时间（秒）
            cache_dir: 缓存目录
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._api_client = None
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._template_cache: Dict[str, Intent] = {}

        # 设置 API 密钥
        if api_key:
            self._api_key = api_key
        else:
            import os
            self._api_key = os.environ.get("MATHA_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _get_client(self):
        """延迟获取 API 客户端。"""
        if self._api_client is not None:
            return self._api_client

        if "claude" in self.model.lower():
            try:
                from anthropic import Anthropic
                kwargs = {"api_key": self._api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._api_client = Anthropic(**kwargs)
            except ImportError:
                raise ImportError("请安装 anthropic: pip install anthropic")
        elif "deepseek" in self.model.lower():
            try:
                from openai import OpenAI
                kwargs = {"api_key": self._api_key, "base_url": self.base_url or "https://api.deepseek.com"}
                self._api_client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        elif "gpt" in self.model.lower() or "4o" in self.model.lower():
            try:
                from openai import OpenAI
                kwargs = {"api_key": self._api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._api_client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        elif "gemini" in self.model.lower():
            # Gemini 使用专用 SDK
            self._gemini_client = self._get_gemini_client()
            return None
        elif "chatglm" in self.model.lower():
            # ChatGLM 使用 OpenAI 兼容接口
            self._api_client = self._get_chatglm_client()
        else:
            # 默认使用 OpenAI 兼容接口
            try:
                from openai import OpenAI
                kwargs = {"api_key": self._api_key or "sk-placeholder", "base_url": self.base_url or "http://localhost:11434/v1"}
                self._api_client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")

        return self._api_client

    def parse(self, text: str, strict: bool = True) -> Intent:
        """
        解析自然语言，返回意图对象。

        Args:
            text: 用户输入的自然语言
            strict: 是否严格模式（置信度 < 0.7 时返回错误）

        Returns:
            Intent 对象
        """
        if not text or not text.strip():
            return Intent(
                intent_type=IntentType.UNKNOWN,
                description="输入为空",
                confidence=0.0,
                follow_up_questions=["请提供有效的计算任务描述"],
            )

        text = text.strip()
        start = time.perf_counter()

        # 检查缓存
        cache_key = self._cache_key(text)
        if cache_key in self._template_cache:
            intent = self._template_cache[cache_key]
            intent.parse_time_ms = 0.0  # 缓存命中不计时间
            return intent

        # 调用 LLM
        try:
            intent = self._call_llm(text)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            # 降级到正则解析
            intent = self._fallback_regex_parse(text)

        intent.parse_time_ms = (time.perf_counter() - start) * 1000

        # 缓存结果
        if intent.confidence >= 0.7:
            self._template_cache[cache_key] = intent

        # 严格模式检查
        if strict and intent.confidence < 0.5:
            intent.errors.append(f"置信度太低 ({intent.confidence:.0%})，建议提供更明确的描述")

        return intent

    def _call_llm(self, text: str) -> Intent:
        """调用 LLM API 解析意图。"""
        user_prompt = self.USER_PROMPT_TEMPLATE.format(text=text)

        try:
            if "claude" in self.model.lower():
                client = self._get_client()
                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                )
                raw_json = response.content[0].text
            elif "gemini" in self.model.lower():
                raw_json = self._call_gemini(user_prompt)
            elif "chatglm" in self.model.lower():
                client = self._get_client()
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1024,
                    response_format={"type": "json_object"},
                    timeout=self.timeout,
                )
                raw_json = response.choices[0].message.content or "{}"
            else:
                client = self._get_client()
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1024,
                    response_format={"type": "json_object"},
                    timeout=self.timeout,
                )
                raw_json = response.choices[0].message.content or "{}"

        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return self._fallback_regex_parse(text)

        # 解析 JSON 响应
        return self._parse_llm_response(raw_json, text)

    def _call_gemini(self, user_prompt: str) -> str:
        """调用 Gemini API 解析意图。"""
        genai = self._gemini_client
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            f"{self.SYSTEM_PROMPT}\n\n{user_prompt}",
            generation_config={"response_mime_type": "application/json"}
        )
        return response.text

    def _parse_llm_response(self, raw_json: str, original_text: str) -> Intent:
        """解析 LLM 返回的 JSON 响应。"""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"LLM 返回无效 JSON: {e}")
            return self._fallback_regex_parse(original_text)

        # 验证必要字段
        required = ["intent_type", "description", "params", "confidence"]
        for field in required:
            if field not in data:
                logger.warning(f"LLM 响应缺少字段: {field}")
                data[field] = "" if field == "description" else ({} if field == "params" else 0.0)

        # 构建 Intent 对象
        try:
            intent_type = IntentType[data["intent_type"]]
        except KeyError:
            intent_type = IntentType.UNKNOWN
            data["intent_type"] = "UNKNOWN"

        intent = Intent(
            intent_type=intent_type,
            description=data.get("description", ""),
            params=data.get("params", {}),
            target_lang="mir",
            confidence=float(data.get("confidence", 0.5)),
            suggested_code=data.get("mir_code", ""),
            follow_up_questions=data.get("follow_up_questions", []),
        )

        return intent

    def _fallback_regex_parse(self, text: str) -> Intent:
        """降级到正则解析。"""
        from src.intent.intent_decomposer import IntentDecomposer
        ide = IntentDecomposer()
        root = ide.decompose(text)

        # 根据节点类型映射到 IntentType
        node_type_map = {
            "ATOMIC": IntentType.ARITHMETIC,
            "COMPLEX": IntentType.ALGORITHM,
            "CONSTRAINT": IntentType.COMPARISON,
            "CONTEXT": IntentType.ARRAY_OP,
            "QUESTION": IntentType.UNKNOWN,
        }
        fallback_type = node_type_map.get(root.node_type.name, IntentType.UNKNOWN)

        # KNP-008: 动态计算降级置信度（基于文本长度和规则匹配数）
        import re
        rule_matches = sum(1 for kw in root.text if any(k in root.text.lower() for k in ["加", "减", "乘", "除", "算", "求", "多少"]))
        dynamic_confidence = min(0.9, 0.3 + rule_matches * 0.1 + len(root.text) * 0.005)

        return Intent(
            intent_type=fallback_type,
            description=text,
            confidence=dynamic_confidence,
            suggested_code=root.to_math_code(),
            follow_up_questions=["LLM 解析失败，使用正则兜底"],
        )

    def _cache_key(self, text: str) -> str:
        """生成缓存键。"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:16]

    def clear_cache(self):
        """清空缓存。"""
        self._template_cache.clear()

    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表。"""
        return [
            "claude-3-5-sonnet",
            "claude-3-opus",
            "deepseek-chat",
            "deepseek-coder",
            "gpt-4o",
            "gpt-4-turbo",
            "llama3.2",
            "llama3",
            # 新增后端
            "gemini-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "chatglm3-6b",
            "chatglm-6b",
            "qwen-max",
            "qwen-plus",
        ]

    def _get_gemini_client(self):
        """获取 Gemini 客户端。"""
        try:
            import google.generativeai as genai
            api_key = self._api_key or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("请提供 Gemini API 密钥")
            genai.configure(api_key=api_key)
            return genai
        except ImportError:
            raise ImportError("请安装 google-generativeai: pip install google-generativeai")

    def _get_chatglm_client(self):
        """获取 ChatGLM 客户端（通过 OpenAI 兼容接口）。"""
        try:
            from openai import OpenAI
            api_key = self._api_key or os.environ.get("ZHIPUAI_API_KEY")
            base_url = self.base_url or "https://open.bigmodel.cn/api/paas/v4"
            return OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")


# ============================================================
# 便捷函数
# ============================================================

def parse_intent(text: str, model: str = "claude-3-5-sonnet", **kwargs) -> Intent:
    """便捷函数：解析自然语言为意图。"""
    parser = LLMIntentParser(model=model, **kwargs)
    return parser.parse(text)


def explain_intent(text: str, model: str = "claude-3-5-sonnet", **kwargs) -> str:
    """便捷函数：解释意图。"""
    intent = parse_intent(text, model=model, **kwargs)
    return f"""
意图: {intent.intent_type.name}
描述: {intent.description}
置信度: {intent.confidence:.0%}
代码: {intent.suggested_code}
追问: {intent.follow_up_questions}
"""


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM 意图解析器")
    parser.add_argument("text", help="自然语言输入")
    parser.add_argument("--model", default="claude-3-5-sonnet", help="模型名称")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    print("=" * 60)
    print(f"  Matha v4.2 — LLM 意图解析器")
    print("=" * 60)
    print(f"\n输入: {args.text!r}")
    print(f"模型: {args.model}")

    try:
        result = explain_intent(args.text, model=args.model)
        print(result)
    except Exception as e:
        print(f"\n错误: {e}")
        print("\n提示: 请设置 MATHA_LLM_API_KEY 环境变量或使用 --model local")
