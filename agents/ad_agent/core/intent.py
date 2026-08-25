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
        
        # 从用户输入中提取参数（支持中文和英文）
        platform_params = self._extract_params_from_input(user_input, platforms)
        
        return ParsedIntent(
            intent_type=intent_type,
            raw_input=user_input,
            platforms=platforms,
            objective=objective,
            budget=budget,
            creative_materials=materials,
            platform_params=platform_params,
        )
    
    def _detect_intent_type(self, text: str) -> str:
        """检测意图类型（注意顺序：更具体的规则放在前面）"""
        # 先检查报表查询
        if any(kw in text for kw in ["报表", "report", "下载", "查看数据", "performance", "统计"]):
            return "download_report"
        # 先检查创建意图（优先级高于列表，避免"创建广告系列"误匹配）
        if any(kw in text for kw in ["投放", "创建广告", "创建", "promote", "launch ad", "run ad", "新建广告", "创建 campaign"]):
            return "create_campaign"
        # 特定列表查询 - 按优先级排序
        if any(kw in text for kw in ["兴趣类别", "interest", "兴趣"]):
            return "list_interests"
        if any(kw in text for kw in ["地域", "location", "地区"]):
            return "list_locations"
        if any(kw in text for kw in ["设备", "device"]):
            return "list_devices"
        if any(kw in text for kw in ["人群包", "audience", "受众"]):
            return "list_audiences"
        if any(kw in text for kw in ["广告组", "ad group", "adgroup"]):
            return "list_adgroups"
        if any(kw in text for kw in ["广告组", "adset", "ad set", "广告集"]):
            return "list_adsets"
        # Campaign 列表查询 — 只在明确表达"查询/列出"意图时匹配
        if any(kw in text for kw in ["列出", "列表", "查询", "查看", "list", "query", "search", "获取"]):
            if any(kw in text for kw in ["Campaign", "campaign", "广告系列"]):
                return "list_campaigns"
        if any(kw in text for kw in ["创意", "creative", "素材"]):
            return "list_creatives"
        # "转化广告系列" 是 campaign 类型，不是 conversion 查询
        if any(kw in text for kw in ["转化", "conversion"]) and "广告系列" not in text and "campaign" not in text:
            return "list_conversions"
        if any(kw in text for kw in ["商品目录", "catalog"]):
            return "list_catalogs"
        if any(kw in text for kw in ["商品集", "product set"]):
            return "list_product_sets"
        if any(kw in text for kw in ["应用", "app "]):
            return "list_apps"
        if any(kw in text for kw in ["品牌安全", "brand safety"]):
            return "list_brand_safety"
        # Ad 级别查询 — 排除"广告系列"（campaign）和"广告主"（advertiser）
        if ("广告" in text or " ad" in text or "ad " in text) and "广告系列" not in text and "广告主" not in text and "adgroup" not in text and "ad_group" not in text:
            return "list_ads"
        elif any(kw in text for kw in ["boost", "助推", "加热", "推广帖子", "boost post"]):
            return "boost_post"
        elif any(kw in text for kw in ["再营销", "remarketing", "retargeting", "重定向"]):
            return "run_remarketing"
        # 检查问候和闲聊
        if any(kw in text for kw in ["你好", "hello", "hi", "在吗", "帮助", "help", "你是谁", "支持"]):
            return "chat"
        # 默认返回 chat，不要默认创建
        return "chat"
    
    def _extract_params_from_input(self, user_input: str, platforms: list[str]) -> dict:
        """
        从用户输入中提取参数。
        支持格式：
        - "campaign_id=12345"
        - "名称=test"
        - "budget 50"
        - "campaign 12345"
        - "ID: 12345"
        """
        params = {p: {} for p in platforms}
        text = user_input.lower()
        
        # campaign_id 提取 - 支持多种格式
        import re
        # 格式1: campaign_id=12345 或 campaign_id: 12345
        campaign_match = re.search(r'campaign[_-]?id[=:\s]+(\d+)', text)
        if campaign_match:
            for p in platforms:
                params[p]["campaign_id"] = campaign_match.group(1)
        else:
            # 格式2: campaign 12345 或 campaign ID 12345
            campaign_match = re.search(r'campaign(?:\s+id)?\s+(\d+)', text)
            if campaign_match:
                for p in platforms:
                    params[p]["campaign_id"] = campaign_match.group(1)
            else:
                # 格式3: ID: 12345 (大数字，可能是 campaign ID)
                id_match = re.search(r'\bid[:\s]+(\d{10,})', text)
                if id_match:
                    for p in platforms:
                        params[p]["campaign_id"] = id_match.group(1)
        
        # ad_group_id / adgroup_id 提取
        adgroup_match = re.search(r'ad[_-]?group[_-]?id[=:\s]+(\d+)', text)
        if adgroup_match:
            for p in platforms:
                params[p]["ad_group_id"] = adgroup_match.group(1)
        else:
            adgroup_match = re.search(r'adgroup(?:\s+id)?\s+(\d+)', text)
            if adgroup_match:
                for p in platforms:
                    params[p]["ad_group_id"] = adgroup_match.group(1)
        
        # ad_id 提取
        ad_match = re.search(r'ad[_-]?id[=:\s]+(\d+)', text)
        if ad_match:
            for p in platforms:
                params[p]["ad_id"] = ad_match.group(1)
        else:
            ad_match = re.search(r'\bad\s+(?:ID\s+)?(\d{10,})', text)
            if ad_match:
                for p in platforms:
                    params[p]["ad_id"] = ad_match.group(1)
        
        # campaign_name 提取
        name_match = re.search(r'(?:名称|name)[=:\s]+([^\s,，;；]+(?:\s+[^\s,，;；]+)*)', text)
        if name_match:
            for p in platforms:
                params[p]["campaign_name"] = name_match.group(1).strip()
        
        # budget 提取
        budget_match = re.search(r'(?:预算|budget)[=:\s]*(\d+(?:\.\d+)?)', text)
        if budget_match:
            for p in platforms:
                params[p]["budget"] = float(budget_match.group(1))
        
        # objective 提取
        objective_match = re.search(r'(?:目标|objective)[=:\s]+([A-Z_]+)', text)
        if objective_match:
            for p in platforms:
                params[p]["objective"] = objective_match.group(1)
        
        # date_range 提取 - 支持 "最近7天"、"last_7_days" 等
        date_patterns = [
            (r'最近(\d+)天', lambda m: {"start_date": f"LAST_{m.group(1)}_DAYS", "end_date": "TODAY"}),
            (r'last\s*(\d+)\s*days?', lambda m: {"start_date": f"LAST_{m.group(1)}_DAYS", "end_date": "TODAY"}),
            (r'(\d{4})-(\d{2})-(\d{2})\s*至\s*(\d{4})-(\d{2})-(\d{2})', lambda m: {"start_date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "end_date": f"{m.group(4)}-{m.group(5)}-{m.group(6)}"}),
        ]
        for pattern, handler in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_range = handler(match)
                if date_range:
                    for p in platforms:
                        params[p]["date_range"] = date_range
                break
        
        return params
    
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
        "list_campaigns": {
            "meta": ["meta_list_campaigns"],
            "google": ["google_list_campaigns"],
            "tiktok": ["tiktok_list_campaigns"],
            "dv360": [],
        },
        "list_adgroups": {
            "meta": ["meta_list_ad_sets"],
            "google": ["google_list_ad_groups"],
            "tiktok": ["tiktok_list_adgroups"],
        },
        "list_adsets": {
            "meta": ["meta_list_ad_sets"],
            "tiktok": ["tiktok_list_adgroups"],
        },
        "list_ads": {
            "meta": ["meta_list_ads"],
            "tiktok": ["tiktok_list_ads"],
        },
        "list_audiences": {
            "meta": ["meta_list_audiences"],
            "tiktok": ["tiktok_list_audiences"],
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
