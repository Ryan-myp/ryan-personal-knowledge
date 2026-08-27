"""
core/llm_client.py - LLM 客户端封装

提供统一的 LLM 调用接口，支持 OpenAI 兼容 API。
"""
import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


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
            model: 模型名称，默认使用 config.yaml 中的配置
            api_key: API Key，默认从环境变量读取
            base_url: API 基础 URL，用于兼容其他 OpenAI 格式 API
        """
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
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
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise
    
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
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}, 原始响应: {text}")
        
        return {"raw": text}
    
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
