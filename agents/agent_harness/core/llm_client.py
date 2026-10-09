"""
core/llm_client.py - LLM 客户端封装

提供统一的 LLM 调用接口，支持 OpenAI 兼容 API。
"""
import os
import json
import logging
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Dict, Any

from ..messages import AgentMessage, ModelTurn, ToolCall

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
        max_tool_calls_per_response: int = 64,
        max_tool_argument_chars: int = 65_536,
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
        if max_tool_calls_per_response <= 0:
            raise ValueError("max_tool_calls_per_response must be positive")
        if max_tool_argument_chars <= 0:
            raise ValueError("max_tool_argument_chars must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.max_tool_calls_per_response = int(max_tool_calls_per_response)
        self.max_tool_argument_chars = int(max_tool_argument_chars)
        
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

    def complete(self, messages, tools, request) -> ModelTurn:
        """Implement the Harness ModelAdapter contract with native Tool calls."""
        provider_messages = self._provider_messages(messages)
        provider_tools = self._provider_tools(tools)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": provider_messages,
            "temperature": 0.1,
        }
        if provider_tools:
            kwargs["tools"] = provider_tools
            kwargs["tool_choice"] = "auto"
        context = getattr(request, "context", None)
        if isinstance(context, dict):
            max_tokens = context.get("max_output_tokens")
            if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
                if max_tokens > 0:
                    kwargs["max_tokens"] = max_tokens

        collector = _ACTIVE_USAGE_COLLECTOR.get()
        if collector is not None:
            collector.add({"llm_requests": 1})
        try:
            response = self._get_client().chat.completions.create(**kwargs)
        except Exception as error:
            logger.error("LLM Tool-call generation failed: %s", type(error).__name__)
            raise
        choice = next(iter(getattr(response, "choices", ()) or ()), None)
        if choice is None:
            raise LLMStructuredOutputError("LLM response did not contain a choice")
        message = getattr(choice, "message", None)
        if message is None:
            raise LLMStructuredOutputError("LLM response did not contain a message")
        allowed_names = {
            self._tool_value(tool, "name") for tool in tools or ()
        }
        raw_calls = tuple(getattr(message, "tool_calls", None) or ())
        if len(raw_calls) > self.max_tool_calls_per_response:
            raise LLMStructuredOutputError(
                "LLM returned too many Tool calls in one response"
            )
        calls = tuple(self._tool_call(item, allowed_names) for item in raw_calls)
        call_ids = [item.id for item in calls]
        if len(call_ids) != len(set(call_ids)):
            raise LLMStructuredOutputError(
                "LLM returned duplicate Tool call ids"
            )
        usage = self._normalize_usage(getattr(response, "usage", None))
        if collector is not None:
            usage["llm_requests"] = 0
            collector.add(usage)
        return ModelTurn(
            content=getattr(message, "content", None) or "",
            tool_calls=calls,
            stop_reason=(
                "tool_call" if calls
                else str(getattr(choice, "finish_reason", None) or "stop")
            ),
            usage=usage,
        )

    @staticmethod
    def _tool_value(tool: Any, key: str, default: Any = None) -> Any:
        if isinstance(tool, dict):
            return tool.get(key, default)
        return getattr(tool, key, default)

    @classmethod
    def _provider_tools(cls, tools: Any) -> list[dict[str, Any]]:
        definitions = []
        for tool in tools or ():
            name = str(cls._tool_value(tool, "name", "") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
                raise LLMStructuredOutputError(
                    "active Tool catalog contains an invalid function name"
                )
            raw_schema = cls._tool_value(tool, "input_schema", {})
            if callable(getattr(raw_schema, "to_dict", None)):
                raw_schema = raw_schema.to_dict()
            schema = dict(raw_schema) if isinstance(raw_schema, dict) else {}
            properties = schema.get("properties")
            parameters = {
                "type": "object",
                "properties": dict(properties) if isinstance(properties, dict) else {},
                "required": [
                    str(item) for item in (schema.get("required") or ())
                    if str(item)
                ],
                "additionalProperties": bool(
                    schema.get("additionalProperties", False)
                ),
            }
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(
                        cls._tool_value(tool, "description", "") or ""
                    )[:1200],
                    "parameters": parameters,
                },
            })
        return definitions

    @staticmethod
    def _message_content(value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise LLMStructuredOutputError(
                "conversation contains non-serializable model content"
            ) from error

    @classmethod
    def _provider_messages(cls, messages: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages or ():
            role = str(cls._tool_value(message, "role", "") or "").strip()
            if role not in {"system", "user", "assistant", "tool"}:
                raise LLMStructuredOutputError(
                    "conversation contains an unsupported message role"
                )
            content = cls._message_content(
                cls._tool_value(message, "content", "")
            )
            item: dict[str, Any] = {"role": role, "content": content}
            if role == "assistant":
                metadata = cls._tool_value(message, "metadata", {})
                raw_calls = (
                    metadata.get("tool_calls", [])
                    if isinstance(metadata, dict) else []
                )
                calls = []
                for call in raw_calls or ():
                    name = str(cls._tool_value(call, "name", "") or "").strip()
                    call_id = str(cls._tool_value(call, "id", "") or "").strip()
                    arguments = cls._tool_value(call, "arguments", {})
                    if not name or not call_id:
                        raise LLMStructuredOutputError(
                            "transcript contains an incomplete Tool call"
                        )
                    calls.append({
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": cls._message_content(arguments),
                        },
                    })
                if calls:
                    item["tool_calls"] = calls
            elif role == "tool":
                call_id = str(
                    cls._tool_value(message, "tool_call_id", "") or ""
                ).strip()
                if not call_id:
                    raise LLMStructuredOutputError(
                        "transcript contains a Tool result without a call id"
                    )
                item["tool_call_id"] = call_id
                name = str(cls._tool_value(message, "name", "") or "").strip()
                if name:
                    item["name"] = name
            result.append(item)
        return result

    def _tool_call(self, value: Any, allowed_names: set[str]) -> ToolCall:
        cls = type(self)
        function = cls._tool_value(value, "function", {})
        name = str(cls._tool_value(function, "name", "") or "").strip()
        call_id = str(cls._tool_value(value, "id", "") or "").strip()
        if (
            not name or len(name) > 64 or not call_id
            or len(call_id) > 128 or name not in allowed_names
        ):
            raise LLMStructuredOutputError(
                "LLM requested a Tool outside the active catalog"
            )
        raw_arguments = cls._tool_value(function, "arguments", "{}")
        if isinstance(raw_arguments, str):
            if len(raw_arguments) > self.max_tool_argument_chars:
                raise LLMStructuredOutputError(
                    "LLM Tool arguments exceeded the configured size limit"
                )
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as error:
                raise LLMStructuredOutputError(
                    "LLM Tool arguments were not valid JSON"
                ) from error
        else:
            arguments = raw_arguments
        if not isinstance(arguments, dict):
            raise LLMStructuredOutputError(
                "LLM Tool arguments must be a JSON object"
            )
        try:
            serialized_arguments = json.dumps(
                arguments, ensure_ascii=False, separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as error:
            raise LLMStructuredOutputError(
                "LLM Tool arguments were not JSON serializable"
            ) from error
        if len(serialized_arguments) > self.max_tool_argument_chars:
            raise LLMStructuredOutputError(
                "LLM Tool arguments exceeded the configured size limit"
            )
        return ToolCall(id=call_id, name=name, arguments=arguments)

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
    max_tool_calls_per_response: int = 64,
    max_tool_argument_chars: int = 65_536,
) -> LLMClient:
    """工厂函数，创建 LLM 客户端"""
    return LLMClient(
        model=model, api_key=api_key, base_url=base_url,
        timeout_seconds=timeout_seconds,
        max_tool_calls_per_response=max_tool_calls_per_response,
        max_tool_argument_chars=max_tool_argument_chars,
    )
