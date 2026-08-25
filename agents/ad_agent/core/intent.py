"""
core/intent.py - 意图解析与路由实现

借鉴 DAP Agent internal/capabilities/schedule/agent/turn_router.go
和 internal/capabilities/schedule/agent/planning_router.go

实现：
1. LLM-based IntentParser：将自然语言转换为结构化意图
2. SimpleIntentRouter：根据意图类型 + 平台列表，查找对应工具
"""

import json
import re
from typing import Any, Optional
from .interfaces import (
    ToolContext, ParsedIntent, IntentParser, IntentRouter,
    ToolDefinition, ToolRegistry
)


class LLMIntentParser(IntentParser):
    """
    基于 LLM 的意图解析器。
    
    通过 Prompt 让 LLM 理解用户意图，输出结构化 JSON。
    可通过 inject_llm() 方法注入自定义 LLM 客户端。
    """
    
    PARSE_PROMPT_TEMPLATE = """
你是广告投放专家助手。请分析用户的投放需求，提取以下信息：

用户输入：{user_input}

请输出 JSON 格式（不要输出其他内容）：
{{
  "intent_type": "create_campaign | boost_post | run_remarketing | download_report",
  "platforms": ["meta", "google", "tiktok", "dv360"],
  "objective": "sales | leads | traffic | brand",
  "budget_daily": 100,
  "duration_days": 7,
  "creative_materials": [
    {{"type": "image", "description": "海报图"}}
  ],
  "platform_params": {{
    "meta": {{}},
    "google": {{}}
  }}
}}

投放目标说明：
- sales：电商销售、转化
- leads：线索收集
- traffic：网站流量
- brand：品牌曝光

平台说明：
- meta：Facebook/Instagram 广告
- google：Google Ads
- tiktok：TikTok Ads
- dv360：Display & Video 360
""".strip()

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 客户端，需实现 call(messages) -> str 方法
                        如果为 None，则使用内置的简易规则解析器
        """
        self._llm = llm_client
    
    def inject_llm(self, llm_client) -> None:
        """注入自定义 LLM 客户端"""
        self._llm = llm_client
    
    def parse(self, user_input: str, context: ToolContext) -> ParsedIntent:
        """解析用户输入为结构化意图"""
        if self._llm:
            return self._parse_with_llm(user_input, context)
        else:
            return self._parse_with_rules(user_input)
    
    def _parse_with_llm(self, user_input: str, context: ToolContext) -> ParsedIntent:
        """使用 LLM 解析意图"""
        prompt = self.PARSE_PROMPT_TEMPLATE.format(user_input=user_input)
        
        messages = [
            {"role": "system", "content": "你是一个广告投放意图分析助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        
        response = self._llm.call(messages)
        
        # 从响应中提取 JSON
        json_str = self._extract_json(response)
        if json_str:
            data = json.loads(json_str)
            return ParsedIntent(**self._normalize_intent(data))
        
        # LLM 失败时 fallback 到规则解析
        return self._parse_with_rules(user_input)
    
    def _parse_with_rules(self, user_input: str) -> ParsedIntent:
        """
        规则解析器（LLM 不可用时的 fallback）。
        
        基于关键词匹配，提取基本意图信息。
        """
        text = user_input.lower()
        
        # 检测意图类型
        intent_type = self._detect_intent_type(text)
        
        # 检测平台
        platforms = self._detect_platforms(text)
        
        # 检测投放目标
        objective = self._detect_objective(text)
        
        # 检测预算
        budget = self._extract_budget(text)
        
        # 检测素材
        materials = self._extract_materials(user_input)
        
        return ParsedIntent(
            intent_type=intent_type,
            raw_input=user_input,
            platforms=platforms,
            objective=objective,
            budget=budget,
            creative_materials=materials,
            platform_params={p: {} for p in platforms},
        )
    
    def _detect_intent_type(self, text: str) -> str:
        """检测意图类型（注意顺序：更具体的规则放在前面）"""
        # 先检查报表查询
        if any(kw in text for kw in ["报表", "report", "下载", "查看数据", "performance", "统计"]):
            return "download_report"
        # 检查列表查询
        if any(kw in text for kw in ["列出", "列表", "查询", "查看", "list", "query", "search", "获取"]):
            return "list_campaigns"
        # 再检查其他意图 - 使用更宽松的匹配
        if any(kw in text for kw in ["投放", "创建广告", "创建", "promote", "launch ad", "run ad", "新建广告", "创建 campaign"]):
            return "create_campaign"
        elif any(kw in text for kw in ["boost", "助推", "加热", "推广帖子", "boost post"]):
            return "boost_post"
        elif any(kw in text for kw in ["再营销", "remarketing", "retargeting", "重定向"]):
            return "run_remarketing"
        # 检查问候和闲聊
        if any(kw in text for kw in ["你好", "hello", "hi", "在吗", "帮助", "help", "你是谁", "支持"]):
            return "chat"
        # 默认返回 chat，不要默认创建
        return "chat"
    
    def _detect_platforms(self, text: str) -> list[str]:
        """检测目标平台"""
        platforms = []
        if any(kw in text for kw in ["meta", "facebook", "ins", "instagram"]):
            platforms.append("meta")
        if any(kw in text for kw in ["google", "gads", "谷歌"]):
            platforms.append("google")
        if any(kw in text for kw in ["tiktok", "抖音"]):
            platforms.append("tiktok")
        if any(kw in text for kw in ["dv360", "display video", "dio"]):
            platforms.append("dv360")
        # 如果没有指定平台，返回空列表（需要用户明确指定）
        return platforms
    
    def _detect_objective(self, text: str) -> Optional[str]:
        """检测投放目标"""
        if any(kw in text for kw in ["销售", "转化", "sales", "conversion"]):
            return "sales"
        elif any(kw in text for kw in ["线索", "lead", "收集表单"]):
            return "leads"
        elif any(kw in text for kw in ["流量", "traffic", "点击"]):
            return "traffic"
        elif any(kw in text for kw in ["品牌", "awareness", "曝光"]):
            return "brand"
        return None
    
    def _extract_budget(self, text: str) -> Optional[float]:
        """提取预算（元）"""
        # 匹配 "预算 100" / "daily 50" / "500元" 等模式
        patterns = [
            r'预算\s*(\d+\.?\d*)\s*[元yuan]*',
            r'daily\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*元/天',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        return None
    
    def _extract_materials(self, text: str) -> list[dict]:
        """提取素材信息"""
        materials = []
        # 简单检测：图片/视频关键词
        if any(kw in text for kw in ["图片", "海报", "image", "poster"]):
            materials.append({"type": "image", "description": "user_provided"})
        if any(kw in text for kw in ["视频", "video", " clip"]):
            materials.append({"type": "video", "description": "user_provided"})
        return materials
    
    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON 块"""
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
    
    def _normalize_intent(self, data: dict) -> dict:
        """规范化解析结果"""
        # 确保 platforms 是列表
        platforms = data.get("platforms", [])
        if isinstance(platforms, str):
            platforms = [platforms]
        data["platforms"] = platforms
        
        # 确保 platform_params 有所有平台
        params = data.get("platform_params", {})
        for p in platforms:
            if p not in params:
                params[p] = {}
        data["platform_params"] = params
        
        return data


class SimpleIntentRouter(IntentRouter):
    """
    简单的意图路由器。
    
    工作原理：
    1. 根据 intent_type 查找预定义的 intent_to_tools 映射
    2. 对于每个目标平台，找到对应的工具列表
    3. 返回各平台的工具定义
    
    映射表由 CapabilityModule.configure() 时注入到 Runtime。
    """
    
    # 默认映射：intent_type → {platform: [tool_name, ...]}
    DEFAULT_INTENT_TOOLS = {
        "create_campaign": {
            "meta": [
                "meta_create_campaign",
                "meta_create_ad_set",
                "meta_create_ad",
            ],
            "google": [
                "google_create_campaign",
                "google_create_ad_group",
                "google_create_ad",
            ],
            "tiktok": [
                "tiktok_create_campaign",
                "tiktok_create_ad_group",
                "tiktok_create_ad",
            ],
            "dv360": [
                "dv360_create_campaign",
                "dv360_create_io",
                "dv360_create_line_item",
            ],
        },
        "boost_post": {
            "meta": ["meta_boost_post"],
            "tiktok": ["tiktok_spark_ads_create"],
        },
        "download_report": {
            "meta": ["meta_get_campaign_report"],
            "google": ["google_get_campaign_report"],
            "tiktok": ["tiktok_get_campaign_report"],
            "dv360": ["dv360_get_line_item_report"],
        },
    }
    
    def __init__(self, custom_mappings: dict = None):
        """
        Args:
            custom_mappings: 自定义映射，格式同 DEFAULT_INTENT_TOOLS
                           会与默认映射合并（自定义优先）
        """
        self._mappings = dict(self.DEFAULT_INTENT_TOOLS)
        if custom_mappings:
            for intent_type, platforms in custom_mappings.items():
                self._mappings.setdefault(intent_type, {}).update(platforms)
    
    def route(
        self,
        intent: ParsedIntent,
        registry: ToolRegistry
    ) -> dict[str, list[ToolDefinition]]:
        """
        根据意图路由到各平台的工具。
        
        Returns:
            {platform: [ToolDefinition, ...]}
        """
        result = {}
        mapping = self._mappings.get(intent.intent_type, {})
        
        for platform in intent.platforms:
            tool_names = mapping.get(platform, [])
            tools = []
            for name in tool_names:
                try:
                    defn, _ = registry.get(name)
                    tools.append(defn)
                except KeyError:
                    # 工具未注册，跳过（允许部分平台不支持）
                    pass
            if tools:
                result[platform] = tools
        
        return result
    
    def get_tool_sequence(self, intent: ParsedIntent, registry: ToolRegistry) -> list[tuple[str, ToolDefinition]]:
        """
        获取按顺序排列的工具调用列表。
        
        Returns:
            [(platform, ToolDefinition), ...]
        """
        routed = self.route(intent, registry)
        sequence = []
        for platform, tools in routed.items():
            for tool in tools:
                sequence.append((platform, tool))
        return sequence


# ─── 预定义的意图规则（供 Capability 覆盖默认规则使用）────────────

INTENT_RULES = {
    "create_campaign": {
        "meta": {
            "description": "Meta Marketing API 广告投放",
            "required_tools": ["meta_create_campaign", "meta_create_ad_set", "meta_create_ad"],
            "params_template": {
                "campaign_name": "{objective}_campaign_{timestamp}",
                "objective": "OUTCOME_SALES",
                "daily_budget": "{{budget}}",
            }
        },
        "google": {
            "description": "Google Ads 广告投放",
            "required_tools": ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
            "params_template": {
                "campaign_name": "{objective}_campaign",
                "advertising_channel_type": "SEARCH",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            }
        },
        "tiktok": {
            "description": "TikTok Ads 广告投放",
            "required_tools": ["tiktok_create_campaign", "tiktok_create_ad_group", "tiktok_create_ad"],
            "params_template": {
                "campaign_name": "{objective}_campaign",
                "objective": "PRODUCT_SALES",
                "daily_budget": "{{budget}}",
            }
        },
        "dv360": {
            "description": "DV360 广告投放",
            "required_tools": ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"],
            "params_template": {
                "campaign_name": "{objective}_campaign",
                "goal_type": "IMPRESSIONS",
            }
        },
    }
}
