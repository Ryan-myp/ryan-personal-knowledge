"""
core/llm_client.py - LLM 客户端封装

提供统一的 LLM 调用接口，支持 OpenAI 兼容 API。
"""
import os
import json
import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMUsageCollector:
    """Collect backend-reported usage for one context-local application turn."""

    _COUNTERS = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cache_read_input_tokens",
        "cache_write_input_tokens",
        "llm_requests",
    )

    def __init__(self) -> None:
        self._usage = {key: 0 for key in self._COUNTERS}
        self._lock = threading.Lock()

    def add(self, usage: Dict[str, int]) -> None:
        with self._lock:
            for key in self._COUNTERS:
                self._usage[key] += max(0, int(usage.get(key, 0) or 0))

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._usage)


_ACTIVE_USAGE_COLLECTOR: ContextVar[LLMUsageCollector | None] = ContextVar(
    "ad_agent_llm_usage_collector",
    default=None,
)


@contextmanager
def capture_llm_usage():
    """Collect usage from nested LLMClient calls without shared-client races."""
    collector = LLMUsageCollector()
    token = _ACTIVE_USAGE_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _ACTIVE_USAGE_COLLECTOR.reset(token)


class LLMStructuredOutputError(ValueError):
    """The model response could not satisfy a structured JSON contract."""


class LLMClient:
    """
    LLM 客户端，封装 OpenAI API 调用。
    
    使用方式：
        client = LLMClient()
        response = client.call(messages)
    """
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        timeout_seconds: float = 30.0,
    ):
        """
        Args:
            model: 模型名称；未显式传入时从 LLM_MODEL 读取
            api_key: API Key，默认从环境变量读取
            base_url: API 基础 URL，用于兼容其他 OpenAI 格式 API
        """
        self.model = model or os.environ.get("LLM_MODEL", "").strip()
        if not self.model:
            raise ValueError("LLM_MODEL 未设置；请通过配置或构造参数提供模型名称")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        
        # 懒加载 OpenAI 客户端
        self._client = None
    
    def _get_client(self):
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {}
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                kwargs["timeout"] = self.timeout_seconds
                self._client = OpenAI(**kwargs)
            except ImportError:
                logger.error("❌ 未安装 openai 包，请运行: pip install openai")
                raise
        
        return self._client
    
    def call(self, messages: list[dict], temperature: float = 0.1) -> str:
        """
        调用 LLM，返回文本响应。
        
        Args:
            messages: 消息列表，格式 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数，控制随机性
            
        Returns:
            LLM 响应文本
        """
        text, _usage = self.call_with_usage(messages, temperature)
        return text

    def call_with_usage(
        self, messages: list[dict], temperature: float = 0.1,
    ) -> tuple[str, dict[str, int]]:
        """Call the configured model backend and return text plus token counters."""
        try:
            client = self._get_client()
            collector = _ACTIVE_USAGE_COLLECTOR.get()
            if collector is not None:
                collector.add({"llm_requests": 1})
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            text = response.choices[0].message.content or ""
            usage = self._normalize_usage(getattr(response, "usage", None))
            if collector is not None:
                usage["llm_requests"] = 0
                collector.add(usage)
            return text, usage
        except Exception as e:
            # External exception text can contain request URLs or headers.
            # Keep logs useful without copying model/transport payloads into
            # the application log stream.
            logger.error("LLM 调用失败: %s", type(e).__name__)
            raise

    @staticmethod
    def _usage_value(value: Any, key: str) -> Any:
        if isinstance(value, dict):
            return value.get(key)
        return getattr(value, key, None)

    @classmethod
    def _first_usage_number(cls, value: Any, *paths: tuple[str, ...]) -> int:
        for path in paths:
            current = value
            for key in path:
                current = cls._usage_value(current, key)
                if current is None:
                    break
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                return max(0, int(current))
        return 0

    @classmethod
    def _normalize_usage(cls, usage: Any) -> dict[str, int]:
        """Normalize common OpenAI-compatible token/cache usage shapes."""
        input_tokens = cls._first_usage_number(
            usage, ("prompt_tokens",), ("input_tokens",),
        )
        output_tokens = cls._first_usage_number(
            usage, ("completion_tokens",), ("output_tokens",),
        )
        total_tokens = cls._first_usage_number(
            usage, ("total_tokens",),
        ) or input_tokens + output_tokens
        cache_read = cls._first_usage_number(
            usage,
            ("prompt_tokens_details", "cached_tokens"),
            ("input_tokens_details", "cached_tokens"),
            ("input_tokens_details", "cache_read_tokens"),
            ("cache_read_input_tokens",),
            ("cached_input_tokens",),
        )
        cache_write = cls._first_usage_number(
            usage,
            ("prompt_tokens_details", "cache_write_tokens"),
            ("input_tokens_details", "cache_creation_tokens"),
            ("cache_creation_input_tokens",),
            ("cache_write_input_tokens",),
        )
        if input_tokens:
            cache_read = min(cache_read, input_tokens)
            cache_write = min(cache_write, input_tokens)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_write_input_tokens": cache_write,
            "llm_requests": 1,
        }
    
    def call_json(self, messages: list[dict], temperature: float = 0.1) -> dict:
        """
        调用 LLM，返回 JSON 响应。
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            
        Returns:
            解析后的 JSON 对象
        """
        text = self.call(messages, temperature)
        
        # 尝试从响应中提取 JSON
        json_str = self._extract_json(text)
        if json_str:
            try:
                value = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error("LLM JSON 解析失败: %s", type(e).__name__)
            else:
                if isinstance(value, dict):
                    return value
                logger.error("LLM JSON 顶层类型不是 object")

        # A raw model string is not a valid structured result. Returning it
        # as a normal dict is a contract footgun: callers may interpret the
        # presence of a response as a successful parse and skip validation.
        raise LLMStructuredOutputError(
            "LLM response did not contain a valid JSON object"
        )
    
    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """从文本中提取 JSON 块"""
        import re
        
        # 尝试匹配 ```json ... ``` 或独立的 JSON 对象
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # 尝试匹配最外层 JSON
        brace_count = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    return text[start:i+1]
        
        return None


def create_llm_client(
    model: str = None, api_key: str = None, base_url: str = None,
    timeout_seconds: float = 30.0,
) -> LLMClient:
    """工厂函数，创建 LLM 客户端"""
    return LLMClient(
        model=model, api_key=api_key, base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
