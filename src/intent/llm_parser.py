"""Matha — LLM 意图解析器

集成 Claude/DeepSeek/GPT/Gemini/GLM 等 LLM API，将自然语言转换为结构化意图。

【定位 2026-11 · 阶段 1 AI 修复】Claude 分支曾向 Anthropic SDK 传不支持的
response_format（必 TypeError 降级）、Gemini 分支直读未初始化的
_gemini_client（必 AttributeError 降级），两链从未真通过；本轮已直修，
离线 mock 契约锁见 tests/test_llm_parser_backends.py（请求形状/重试/
降级路径，不触网）。口径遵 docs/KNOWN_ISSUES.md §7c：编排与降级契约
已锁，自然语言→代码的输出正确性不背书。

架构：
  自然语言 → LLM 解析 → 结构化意图 → MIR 代码生成（默认 target_lang="mir"）

【阶段 4-1 · 2026-11】新增 target_lang="matha" 可执行轨：提示词约束内核
builtin + `result = 表达式` / `#1：[result]` 约定，降级走正则 Matha 轨
（不产 MIR 预览）；REPL nl 模式经 MATHA_REPL_LLM=1 显式启用（默认关），
接线契约锁见 tests/test_repl_llm_link.py。LLM 回答正确性仍不背书。

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
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _config_api_key(model: str) -> str | None:
    """从 llm_config 加密存储读当前模型的生效密钥（阶段 4-2 统一回退）。

    读取失败（缺 cryptography / 主密钥不匹配 / 配置损坏）不炸调用方：
    返回 None 走「无 key → LLM 调用失败 → 正则兜底留痕」的既有降级链。
    llm_config 直接使用者仍获诚实 ImportError（其自身口径不变）。
    """
    try:
        from src.tools.llm_config import get_llm_config
        return get_llm_config().get_api_key(model)
    except Exception as e:
        logger.warning(f"llm_config 密钥读取失败（视为无 key）: {e}")
        return None


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
    params: dict[str, Any] = field(default_factory=dict)
    target_lang: str = "mir"  # 目标语言
    confidence: float = 0.0
    suggested_code: str = ""
    follow_up_questions: list[str] = field(default_factory=list)
    parse_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """检查意图是否有效。"""
        return self.intent_type != IntentType.UNKNOWN and self.confidence >= 0.5

    def to_dict(self) -> dict:
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

    # Matha 轨提示词（阶段 4-1：LLM 链接入 REPL/CLI）：产可直接经
    # exec_api 执行的 Matha 代码，与正则 Matha 轨同约定（result 绑定 + #1 输出指令）
    SYSTEM_PROMPT_MATHA = """\
你是一个数学计算意图解析器。用户用自然语言描述计算任务，
你需要将其转换为可直接执行的 Matha DSL 代码。

核心原则：
1. 精确性 — 参数提取必须精确，不猜测缺失信息
2. 可执行性 — 生成的 Matha 代码必须能直接运行并产出结果
3. 完整性 — 如果用户输入模糊，在 follow_up_questions 中列出需要澄清的问题

Matha 代码规则：
- 只使用内核 builtin：sin/cos/tan/log/exp/sqrt/abs/floor/round/
  阶乘/素数判定/最大公约数/最小公倍数/max/min/sum/平均值，
  以及纯算术运算 + - * / ** %
- 结果绑定到 result，末行用输出指令 #1：[result]
- 不要生成 Python、import、MIR 或任何非 Matha 语法
- 无法用上述 builtin 表达时，matha_code 置空并在 follow_up_questions 说明

支持的意图类型：
- ARITHMETIC: 算术运算（加减乘除、幂、开方、求和、平均）
- MATH_FUNC: 数学函数（正弦、余弦、对数、素数判定等）
- COMPARISON: 比较运算
- ALGORITHM: 算法实现
"""

    USER_PROMPT_TEMPLATE_MATHA = """\
用户输入：{text}

请解析用户的计算意图，输出 JSON：
{{
  "intent_type": "<类型>",
  "description": "<中文描述>",
  "params": <参数对象>,
  "confidence": <0-1>,
  "matha_code": "<Matha 代码>",
  "follow_up_questions": [<需要追问的问题>]
}}

注意：
- matha_code 形态固定为 result = 表达式，末行 #1：[result]
- 如果参数缺失或无法用内核 builtin 表达，matha_code 置空并在 follow_up_questions 中说明
- confidence 表示你对解析结果的置信度
"""

    @staticmethod
    def _load_dotenv(path: str = ".env") -> None:
        """尝试加载 .env 文件中的环境变量（不覆盖已存在的）。"""
        import os
        env_path = Path(path)
        if not env_path.is_file():
            # 向上查找最多 4 层
            for parent in Path().resolve().parents[:4]:
                env_path = parent / ".env"
                if env_path.is_file():
                    break
            else:
                return
        try:
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        except Exception as e:
            logger.debug(f"加载 .env 失败: {e}")

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        cache_dir: str = ".matha_cache",
        target_lang: str = "mir",
    ):
        """
        初始化 LLM 意图解析器。

        Args:
            api_key: API 密钥（可选，从环境变量 / .env 读取）
            model: 模型名称（可选，从 MATHA_LLM_MODEL 环境变量读取，默认 glm-4-flash）
            base_url: API 基础 URL（可选）
            timeout: 请求超时时间（秒，默认 60）
            cache_dir: 缓存目录
            target_lang: 代码生成目标（"mir" 默认 / "matha" REPL 可执行轨）
        """
        if target_lang not in ("mir", "matha"):
            raise ValueError(f"target_lang 须为 'mir' 或 'matha'，实得 {target_lang!r}")
        self.target_lang = target_lang
        # 加载 .env 文件（不覆盖已有环境变量）
        self._load_dotenv()

        import os
        self.model = model or os.environ.get("MATHA_LLM_MODEL", "claude-3-5-sonnet")
        self.base_url = base_url
        self.timeout = timeout
        self._api_client = None
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._template_cache: dict[str, Intent] = {}

        # 设置 API 密钥 — 按模型类型优先查找对应的提供商 key
        if api_key:
            self._api_key = api_key
        else:
            model_lower = self.model.lower()
            env_keys: list[str]
            if "glm" in model_lower or "chatglm" in model_lower:
                env_keys = ["ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY"]
            elif "deepseek" in model_lower:
                env_keys = ["DEEPSEEK_API_KEY", "MATHA_LLM_API_KEY"]
            elif "claude" in model_lower:
                env_keys = ["ANTHROPIC_API_KEY", "MATHA_LLM_API_KEY"]
            elif "gemini" in model_lower:
                env_keys = ["GEMINI_API_KEY", "MATHA_LLM_API_KEY"]
            elif "gpt" in model_lower or "4o" in model_lower:
                env_keys = ["OPENAI_API_KEY", "MATHA_LLM_API_KEY"]
            else:
                env_keys = ["MATHA_LLM_API_KEY"]
            for ek in env_keys:
                val = os.environ.get(ek)
                if val:
                    self._api_key = val
                    break
            else:
                self._api_key = None
            # 阶段 4-2：env 缺 key 时回退 llm_config 加密存储（优先级最低）
            if self._api_key is None:
                self._api_key = _config_api_key(self.model)

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
        elif "chatglm" in self.model.lower() or "glm" in self.model.lower():
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
        # 归一化 text：list/tuple 拼接为字符串，避免 'list' object has no attribute 'strip'
        text = (" ".join(str(x) for x in text) if isinstance(text, (list, tuple)) else str(text))
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
        """调用 LLM API 解析意图（带重试和兼容处理）。"""
        if self.target_lang == "matha":
            system_prompt = self.SYSTEM_PROMPT_MATHA
            user_prompt = self.USER_PROMPT_TEMPLATE_MATHA.format(text=text)
        else:
            system_prompt = self.SYSTEM_PROMPT
            user_prompt = self.USER_PROMPT_TEMPLATE.format(text=text)

        # 判断是否需要 response_format（glm 系列部分模型不支持 json_object）
        model_lower = self.model.lower()
        is_glm = "glm" in model_lower
        # glm-4-flash / glm-4-plus 等支持 json_object，但老版 chatglm 不支持
        supports_json_format = not is_glm or "glm-4" in model_lower

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 重试参数
        max_retries = int(os.environ.get("MATHA_LLM_MAX_RETRIES", "3"))
        base_delay = float(os.environ.get("MATHA_LLM_RETRY_DELAY", "1.0"))

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                if "claude" in model_lower:
                    client = self._get_client()
                    # Anthropic SDK 无 response_format 参数（传入即 TypeError，
                    # 历史缺陷：三次重试全崩后静默降级正则）；JSON 形状由提示词约束
                    response = client.messages.create(
                        model=self.model,
                        max_tokens=1024,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                        timeout=self.timeout,
                    )
                    raw_json = response.content[0].text
                elif "gemini" in model_lower:
                    raw_json = self._call_gemini(user_prompt)
                else:
                    # OpenAI 兼容接口（含 ChatGLM / GLM / DeepSeek / GPT 等）
                    client = self._get_client()
                    kwargs = {
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": 1024,
                        "timeout": self.timeout,
                    }
                    if supports_json_format:
                        kwargs["response_format"] = {"type": "json_object"}
                    response = client.chat.completions.create(**kwargs)
                    raw_json = response.choices[0].message.content or "{}"

                # 成功：解析并返回
                return self._parse_llm_response(raw_json, text)

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                status_code = getattr(e, "status_code", None) or getattr(e, "http_status", None)

                # 判断是否为可重试错误
                retryable = (
                    status_code in (408, 429, 500, 502, 503, 504)
                    or "timeout" in error_msg
                    or "timed out" in error_msg
                    or "connection" in error_msg
                    or "rate limit" in error_msg
                    or "429" in error_msg
                    or "500" in error_msg
                    or "502" in error_msg
                    or "503" in error_msg
                    or "serviceunavailable" in error_msg
                )

                # response_format 不兼容：去掉后重试一次
                if "response_format" in error_msg or "json_object" in error_msg:
                    logger.warning(f"LLM 不支持 response_format，去掉后重试: {e}")
                    supports_json_format = False
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue

                if retryable and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # 指数退避 1s, 2s, 4s
                    logger.warning(f"LLM 调用失败(第{attempt}次)，{delay:.1f}s 后重试: {e}")
                    time.sleep(delay)
                    continue

                # 不可重试或已达最大重试次数
                logger.error(f"LLM API 调用失败(第{attempt}次): {e}")
                break

        # 所有重试失败 → 降级到正则解析
        logger.error(f"LLM 最终调用失败，降级正则解析: {last_error}")
        return self._fallback_regex_parse(text)

    def _call_gemini(self, user_prompt: str) -> str:
        """调用 Gemini API 解析意图。"""
        # 先走懒初始化：历史直读未初始化的 _gemini_client 即 AttributeError，
        # 被重试环吞掉后静默降级正则，Gemini 链从未真通过
        self._get_client()
        genai = self._gemini_client
        model = genai.GenerativeModel(self.model)
        system_prompt = (self.SYSTEM_PROMPT_MATHA if self.target_lang == "matha"
                         else self.SYSTEM_PROMPT)
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
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
        for field_name in required:
            if field_name not in data:
                logger.warning(f"LLM 响应缺少字段: {field_name}")
                data[field_name] = "" if field_name == "description" else ({} if field_name == "params" else 0.0)

        # 构建 Intent 对象
        try:
            intent_type = IntentType[data["intent_type"]]
        except KeyError:
            intent_type = IntentType.UNKNOWN
            data["intent_type"] = "UNKNOWN"

        code_field = "matha_code" if self.target_lang == "matha" else "mir_code"
        intent = Intent(
            intent_type=intent_type,
            description=data.get("description", ""),
            params=data.get("params", {}),
            target_lang=self.target_lang,
            confidence=float(data.get("confidence", 0.5)),
            suggested_code=data.get(code_field, ""),
            follow_up_questions=data.get("follow_up_questions", []),
        )

        return intent

    def _fallback_regex_parse(self, text: str) -> Intent:
        """降级到正则解析。"""
        if self.target_lang == "matha":
            return self._fallback_matha_parse(text)
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
        rule_matches = sum(1 for kw in root.text if any(k in root.text.lower() for k in ["加", "减", "乘", "除", "算", "求", "多少"]))
        dynamic_confidence = min(0.9, 0.3 + rule_matches * 0.1 + len(root.text) * 0.005)

        return Intent(
            intent_type=fallback_type,
            description=text,
            confidence=dynamic_confidence,
            suggested_code=root.to_math_code(),
            follow_up_questions=["LLM 解析失败，使用正则兜底"],
        )

    def _fallback_matha_parse(self, text: str) -> Intent:
        """Matha 轨降级：走正则 Matha 代码生成轨（可执行），不产 MIR 预览。"""
        from src.intent_parser import IntentParser as RegexIntentParser
        regex_intent = RegexIntentParser().parse(text, target_lang="matha")
        type_by_name = {t.name: t for t in IntentType}
        marker = "LLM 解析失败，使用正则兜底"
        return Intent(
            intent_type=type_by_name.get(regex_intent.intent_type.name, IntentType.UNKNOWN),
            description=regex_intent.description,
            params=regex_intent.params,
            target_lang="matha",
            confidence=regex_intent.confidence,
            suggested_code=regex_intent.suggested_code,
            follow_up_questions=[marker],
            errors=[*regex_intent.errors, marker],
        )

    def _cache_key(self, text: str) -> str:
        """生成缓存键（含 target_lang，防 mir/matha 两轨互相污染）。"""
        import hashlib
        return hashlib.md5(f"{self.target_lang}:{text}".encode()).hexdigest()[:16]

    def clear_cache(self):
        """清空缓存。"""
        self._template_cache.clear()

    def get_supported_models(self) -> list[str]:
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
            "glm-4-flash",
            "glm-4-plus",
            "glm-4-0520",
            "glm-4-long",
            "glm-4-air",
            "glm-4-airx",
            "qwen-max",
            "qwen-plus",
        ]

    def _get_gemini_client(self):
        """获取 Gemini 客户端。"""
        try:
            import google.generativeai as genai
            api_key = (self._api_key or os.environ.get("GEMINI_API_KEY")
                       or _config_api_key(self.model))
            if not api_key:
                raise ValueError("请提供 Gemini API 密钥")
            genai.configure(api_key=api_key)
            return genai
        except ImportError:
            raise ImportError("请安装 google-generativeai: pip install google-generativeai")

    def _get_chatglm_client(self):
        """获取 ChatGLM / GLM 客户端（智谱AI OpenAI 兼容接口）。"""
        try:
            from openai import OpenAI
            api_key = (self._api_key or os.environ.get("ZHIPUAI_API_KEY")
                       or os.environ.get("MATHA_LLM_API_KEY")
                       or _config_api_key(self.model))
            base_url = self.base_url or "https://open.bigmodel.cn/api/paas/v4"
            return OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)
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
# REPL/CLI 接线（阶段 4-1）：默认关闭，MATHA_REPL_LLM=1 显式启用
# ============================================================

def llm_nl_enabled() -> bool:
    """REPL nl 模式是否启用 LLM 链（默认关，正则轨零依赖离线可用）。"""
    return os.environ.get("MATHA_REPL_LLM", "").strip().lower() in ("1", "on", "true", "yes")


_MATHA_PARSER: LLMIntentParser | None = None


def parse_nl_matha(text: str) -> Intent:
    """REPL nl 模式 LLM 链入口：产 Matha 轨 Intent（失败时内部降级正则 Matha 轨）。

    返回的 Intent 与正则轨 Intent 字段同名（intent_type/description/confidence/
    suggested_code/errors），两个 REPL 的 explain 与执行门可直接消费。
    LLM 真实 API 的回答正确性不背书（口径见 docs/KNOWN_ISSUES.md §7c）。
    """
    global _MATHA_PARSER
    if _MATHA_PARSER is None:
        _MATHA_PARSER = LLMIntentParser(target_lang="matha")
    return _MATHA_PARSER.parse(text)


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
    print("  Matha v4.2 — LLM 意图解析器")
    print("=" * 60)
    print(f"\n输入: {args.text!r}")
    print(f"模型: {args.model}")

    try:
        result = explain_intent(args.text, model=args.model)
        print(result)
    except Exception as e:
        print(f"\n错误: {e}")
        print("\n提示: 请设置 MATHA_LLM_API_KEY 环境变量或使用 --model local")
