"""
core/intent.py - 意图解析与路由实现

借鉴 DAP Agent internal/capabilities/schedule/agent/turn_router.go
和 internal/capabilities/schedule/agent/planning_router.go

实现：
1. LLM-based IntentParser：将自然语言转换为结构化意图
2. SimpleIntentRouter：根据意图类型 + 平台列表，查找对应工具
"""

from __future__ import annotations

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
  "intent_type": "create_campaign | create_asset_group | create_creative | update_campaign | update_adset | update_adgroup | update_ad | pause_campaign | resume_campaign | cross_channel_overview | cross_channel_compare | cross_channel_performance_insights | cross_channel_optimize_budget | cross_channel_export_report | cross_channel_batch_pause | cross_channel_batch_resume | cross_channel_batch_update_budget | boost_post | run_remarketing | download_report",
  "platforms": ["meta", "google", "tiktok", "dv360"],
  "objective": "sales | leads | traffic | brand",
  "campaign_type": "平台 Campaign 类型，如 SEARCH / SHOPPING / APP_INSTALL",
  "budget_daily": 100,
  "duration_days": 7,
  "date_range": "LAST_7_DAYS",
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
        self._custom_intents: set[str] = set()

    def register_intents(self, intents: set[str] | list[str]) -> None:
        """Allow registered Skills to extend the intent contract safely."""
        self._custom_intents.update(str(intent) for intent in (intents or []))
    
    def inject_llm(self, llm_client) -> None:
        """注入自定义 LLM 客户端"""
        self._llm = llm_client
    
    def parse(self, user_input: str, context: ToolContext) -> ParsedIntent:
        """解析用户输入为结构化意图"""
        if self._llm:
            try:
                return self._parse_with_llm(user_input, context)
            except Exception as e:
                print(f"[LLM 解析失败，使用规则解析] {e}")
                return self._parse_with_rules(user_input)
        return self._parse_with_rules(user_input)
    
    def _parse_with_llm(self, user_input: str, context: ToolContext) -> ParsedIntent:
        """使用 LLM 解析意图"""
        prompt = self.PARSE_PROMPT_TEMPLATE.format(user_input=user_input)
        
        messages = [{"role": "system", "content": "你是一个广告投放意图分析助手，只输出 JSON。"}]
        skill_context = (
            context.metadata.get("skill_context")
            if context and isinstance(getattr(context, "metadata", None), dict)
            else None
        )
        if isinstance(skill_context, dict):
            tool_prompt = str(skill_context.get("tool_prompt") or "")
            expert_knowledge = str(skill_context.get("expert_knowledge") or "")
            bounded_context = "\n\n".join(
                part for part in (tool_prompt, expert_knowledge) if part
            )[:6000]
            if bounded_context:
                messages.append({
                    "role": "system",
                    "content": (
                        "以下是当前已注册 Skills 提供的受限工具契约和专家范围。"
                        "只能据此识别意图，不要虚构未注册能力：\n" + bounded_context
                    ),
                })
        if context and getattr(context, "messages", None):
            messages.extend(context.messages[-10:])
        messages.append({"role": "user", "content": prompt})
        
        response = self._llm.call(messages)
        
        # 从响应中提取 JSON
        json_str = self._extract_json(response)
        if json_str:
            data = json.loads(json_str)
            data.setdefault("raw_input", user_input)
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
        if intent_type.startswith("cross_channel") and not platforms:
            platforms = ["meta", "google", "tiktok", "dv360"]
        
        # 检测投放目标
        objective = self._detect_objective(text)

        # Campaign 类型是业务策略校验和平台 payload 选择的独立字段，不能
        # 只依赖 objective 推断。
        campaign_type = self._extract_campaign_type(user_input)
        
        # 检测预算
        budget = self._extract_budget(text)

        # 检测报表日期范围
        date_range = self._extract_date_range(text)
        
        # 检测素材
        materials = self._extract_materials(user_input)
        
        # 从用户输入中提取参数（支持中文和英文）
        platform_params = self._extract_params_from_input(user_input, platforms)
        
        return ParsedIntent(
            intent_type=intent_type,
            raw_input=user_input,
            platforms=platforms,
            objective=objective,
            campaign_type=campaign_type,
            budget=budget,
            date_range=date_range,
            creative_materials=materials,
            platform_params=platform_params,
        )
    
    def _detect_intent_type(self, text: str) -> str:
        """检测意图类型（注意顺序：更具体的规则放在前面）"""
        cross_markers = ["跨渠道", "跨平台", "全渠道", "各平台对比", "渠道对比"]
        compare_words = ["对比", "比较", "compare"]
        batch_markers = ["批量", "多个", "多条", "bulk", "batch"]
        # These are read-only cross-channel analyses. Resolve them before the
        # generic report/create rules so the Runtime can run the two-phase
        # campaign-list + campaign-report workflow.
        is_cross_request = any(marker in text for marker in cross_markers)
        # Creation is a first-class cross-channel workflow.  It must be
        # resolved before the generic cross-channel overview fallback below;
        # otherwise "跨渠道创建 campaign" gets routed to list_campaigns and
        # never reaches the per-platform create chain.
        if is_cross_request and any(kw in text for kw in [
            "创建", "新建", "create", "launch", "投放",
        ]):
            return "create_campaign"
        if is_cross_request and any(kw in text for kw in [
            "预算优化", "优化预算", "预算分配", "分配预算", "allocate budget", "budget optimization",
        ]):
            return "cross_channel_optimize_budget"
        if is_cross_request and any(kw in text for kw in [
            "导出", "export", "下载 csv", "下载csv",
        ]) and any(kw in text for kw in ["报表", "报告", "report", "数据"]):
            return "cross_channel_export_report"
        if is_cross_request and any(kw in text for kw in [
            "洞察", "分析", "优化建议", "performance insight", "insights",
        ]):
            return "cross_channel_performance_insights"
        # Resolve explicit multi-platform comparisons before the generic
        # report rule, so “比较 Meta 和 Google 的报表” remains a comparison.
        if (
            len(self._detect_platforms(text)) >= 2
            and any(kw in text for kw in compare_words)
        ):
            return "cross_channel_compare"
        if any(marker in text for marker in batch_markers):
            if any(kw in text for kw in ["暂停", "停用", "pause", "disable"]):
                return "cross_channel_batch_pause"
            if any(kw in text for kw in ["恢复", "启用", "resume", "enable"]):
                return "cross_channel_batch_resume"
            if any(kw in text for kw in ["预算", "budget"]):
                return "cross_channel_batch_update_budget"
        # 先检查报表查询
        if any(kw in text for kw in ["报表", "report", "下载", "查看数据", "performance", "统计"]):
            return "download_report"
        if any(kw in text for kw in ["line item", "line_item", "行项目"]):
            if any(kw in text for kw in ["详情", "detail", "get "]):
                return "get_line_item"
            if any(kw in text for kw in ["列出", "列表", "查询", "查看", "list", "query"]):
                return "list_line_items"
        if (
            any(kw in text for kw in ["insertion order", "insertion_order", "订单"])
            or re.search(r"(?<![a-z])io(?![a-z])", text)
        ):
            if any(kw in text for kw in ["详情", "detail", "get "]):
                return "get_io"
            if any(kw in text for kw in ["列出", "列表", "查询", "查看", "list", "query"]):
                return "list_ios"
        # 更新/暂停/恢复必须优先于创建，避免“更新广告系列”被识别为 create。
        if any(kw in text for kw in cross_markers):
            if any(kw in text for kw in ["更新", "修改", "编辑", "update", "modify", "edit"]):
                return "update_campaign"
            if any(kw in text for kw in ["暂停", "停用", "pause", "disable"]):
                return "pause_campaign"
            if any(kw in text for kw in ["恢复", "启用", "resume", "enable"]):
                return "resume_campaign"
            return "cross_channel_overview"
        if any(kw in text for kw in ["更新", "修改", "编辑", "update", "modify", "edit"]):
            if any(kw in text for kw in ["line item", "line_item", "行项目"]):
                return "update_line_item"
            if any(kw in text for kw in ["insertion order", "insertion_order", "订单"]):
                return "update_io"
            if any(kw in text for kw in ["asset group", "asset_group", "素材组", "资产组"]):
                return "update_asset_group"
            if any(kw in text for kw in ["广告组", "adset", "ad set"]):
                return "update_adset"
            if any(kw in text for kw in ["ad group", "adgroup"]):
                return "update_adgroup"
            if any(kw in text for kw in ["广告", " ad", "ad "]) and "广告系列" not in text and "campaign" not in text:
                return "update_ad"
            if any(kw in text for kw in ["广告系列", "campaign"]):
                return "update_campaign"
        if any(kw in text for kw in ["暂停", "停用", "pause", "disable"]):
            return "pause_campaign"
        if any(kw in text for kw in ["恢复", "启用", "resume", "enable"]):
            return "resume_campaign"
        # 先检查创建意图（优先级高于列表，避免"创建广告系列"误匹配）
        if any(kw in text for kw in ["asset group", "asset_group", "素材组", "资产组"]):
            if any(kw in text for kw in ["创建", "新建", "create", "add"]):
                return "create_asset_group"
        if any(kw in text for kw in ["创意", "creative", "素材"]) and any(
            kw in text for kw in ["创建", "新建", "create", "add"]
        ):
            return "create_creative"
        if any(kw in text for kw in ["投放", "创建广告", "创建", "promote", "launch ad", "run ad", "新建广告", "创建 campaign"]):
            return "create_campaign"
        # 特定列表查询 - 按优先级排序
        if any(kw in text for kw in ["兴趣类别", "interest", "兴趣"]):
            return "list_interests"
        if any(kw in text for kw in ["地域", "location", "地区"]):
            return "list_locations"
        if any(kw in text for kw in ["设备", "device"]):
            return "list_devices"
        if any(kw in text for kw in ["关键词", "keyword", "keywords"]):
            return "list_keywords"
        if any(kw in text for kw in ["人群包", "audience", "受众"]):
            return "list_audiences"
        if any(kw in text for kw in ["广告组", "ad group", "adgroup"]):
            return "list_adgroups"
        if any(kw in text for kw in ["广告组", "adset", "ad set", "广告集"]):
            return "list_adsets"
        # Campaign 详情查询 — 优先于列表（带 ID 或"详情"关键词）
        if any(kw in text for kw in ["详情", "detail", "information", "信息", "get ", " 的 详情", "的详情", "看看这个"]):
            if any(kw in text for kw in ["Campaign", "campaign", "广告系列"]):
                return "get_campaign"
        # Campaign 列表查询 — 只在明确表达"查询/列出"意图时匹配
        if any(kw in text for kw in ["列出", "列表", "查询", "查看", "list", "query", "search", "获取"]):
            if any(kw in text for kw in ["Campaign", "campaign", "广告系列"]):
                return "list_campaigns"
        if any(kw in text for kw in ["视频", "video"]):
            return "list_videos"
        if any(kw in text for kw in ["图片", "image"]):
            return "list_images"
        if any(kw in text for kw in ["创意", "creative", "素材"]):
            return "list_creatives"
        # "转化广告系列" 是 campaign 类型，不是 conversion 查询
        if any(kw in text for kw in ["转化", "conversion"]) and "广告系列" not in text and "campaign" not in text:
            return "list_conversions"
        if any(kw in text for kw in ["商品目录", "catalog"]):
            return "list_catalogs"
        if any(kw in text for kw in ["商品集", "product set"]):
            return "list_product_sets"
        if any(kw in text for kw in ["应用", "app ", "apps"]):
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

        platform_aliases = {
            "meta": ["meta", "facebook", "instagram"],
            "google": ["google", "google ads", "google-ads", "gads", "谷歌"],
            "tiktok": ["tiktok", "抖音"],
            "dv360": ["dv360", "display video"],
        }

        # Prefer platform-qualified IDs. A single generic campaign_id is only
        # a fallback; copying it to every channel is unsafe for cross-channel
        # management because platform IDs are not globally interchangeable.
        for platform in platforms:
            aliases_for_platform = platform_aliases.get(platform, [platform])
            alias_pattern = "|".join(re.escape(alias) for alias in aliases_for_platform)
            campaign_match = re.search(
                rf"(?:{alias_pattern})\s*(?:campaign|广告系列)[_-]?id\s*[=:]\s*([\w-]+)",
                text,
                re.IGNORECASE,
            )
            if campaign_match:
                params[platform]["campaign_id"] = campaign_match.group(1)
            account_key = {
                "meta": "account_id",
                "google": "customer_id",
                "tiktok": "advertiser_id",
                "dv360": "advertiser_id",
            }.get(platform, "account_id")
            account_match = re.search(
                rf"(?:{alias_pattern})\s*(?:account|ad[_-]?account|customer|advertiser)(?:[_-]?id)?\s*[=:]\s*([\w-]+)",
                text,
                re.IGNORECASE,
            )
            if account_match:
                params[platform][account_key] = account_match.group(1)
        
        # campaign_id 提取 - 支持多种格式
        # 格式1: campaign_id=12345 或 campaign_id: 12345
        campaign_match = re.search(r'campaign[_-]?id[=:\s]+(\d+)', text)
        if campaign_match:
            # A bare ID is only unambiguous for a single platform.  Campaign
            # IDs are provider/account scoped and must never be copied across
            # channels by the parser.
            if len(platforms) == 1:
                params[platforms[0]].setdefault("campaign_id", campaign_match.group(1))
        else:
            # 格式2: campaign 12345 或 campaign ID 12345
            campaign_match = re.search(r'campaign(?:\s+id)?\s+(\d+)', text)
            if campaign_match:
                if len(platforms) == 1:
                    params[platforms[0]].setdefault("campaign_id", campaign_match.group(1))
            else:
                # 格式3: ID: 12345 (大数字，可能是 campaign ID)
                id_match = re.search(r'\bid[:\s]+(\d{10,})', text)
                if id_match:
                    if len(platforms) == 1:
                        params[platforms[0]].setdefault("campaign_id", id_match.group(1))

        # 批量 ID：只有显式平台限定或单平台请求才会写入，避免把一个渠道
        # 的 Campaign ID 误复制到其他渠道。
        # A platform-qualified batch may contain one or many IDs. The old
        # pattern required a comma, so a valid single Google/TikTok/DV360 ID
        # was silently dropped in a multi-platform request.
        batch_id_pattern = r'[\w-]+(?:\s*[,，]\s*[\w-]+)*'
        for platform in platforms:
            aliases_for_platform = platform_aliases.get(platform, [platform])
            alias_pattern = "|".join(re.escape(alias) for alias in aliases_for_platform)
            batch_match = re.search(
                rf"(?:{alias_pattern})\s*(?:campaign|广告系列)[_-]?ids\s*[=:]\s*({batch_id_pattern})",
                text,
                re.IGNORECASE,
            )
            if batch_match:
                ids = [x.strip() for x in re.split(r"[,，]", batch_match.group(1)) if x.strip()]
                params[platform]["campaign_ids"] = list(dict.fromkeys(ids))
                params[platform].setdefault("campaign_id", ids[0])
        if len(platforms) == 1 and "campaign_ids" not in params[platforms[0]]:
            generic_batch_match = re.search(
                rf"campaign[_-]?ids?\s*[=:]\s*({batch_id_pattern})", text, re.IGNORECASE
            )
            if generic_batch_match:
                ids = [x.strip() for x in re.split(r"[,，]", generic_batch_match.group(1)) if x.strip()]
                params[platforms[0]]["campaign_ids"] = list(dict.fromkeys(ids))
                params[platforms[0]].setdefault("campaign_id", ids[0])
        
        # ad_group_id / adgroup_id 提取
        adgroup_match = re.search(r'ad[_-]?group[_-]?id[=:\s]+(\d+)', text)
        if adgroup_match:
            if len(platforms) == 1:
                params[platforms[0]]["ad_group_id"] = adgroup_match.group(1)
        else:
            adgroup_match = re.search(r'adgroup(?:\s+id)?\s+(\d+)', text)
            if adgroup_match:
                if len(platforms) == 1:
                    params[platforms[0]]["ad_group_id"] = adgroup_match.group(1)
        
        # ad_id 提取
        ad_match = re.search(r'ad[_-]?id[=:\s]+(\d+)', text)
        if ad_match:
            if len(platforms) == 1:
                params[platforms[0]]["ad_id"] = ad_match.group(1)
        else:
            ad_match = re.search(r'\bad\s+(?:ID\s+)?(\d{10,})', text)
            if ad_match:
                if len(platforms) == 1:
                    params[platforms[0]]["ad_id"] = ad_match.group(1)

        # DV360 Line Item ID 提取。Campaign ID 不能替代 Line Item ID：两者
        # 属于不同资源层级，混用会把合法查询路由到错误的报表契约。
        line_item_match = re.search(r'line[_ -]?item[_ -]?id[=:\s]+([\w-]+)', text, re.IGNORECASE)
        if line_item_match:
            if "dv360" in platforms:
                params["dv360"]["line_item_id"] = line_item_match.group(1)

        asset_group_match = re.search(
            r'asset[_ -]?group[_ -]?id[=:\s]+([\w-]+)', text, re.IGNORECASE
        )
        if asset_group_match and "google" in platforms:
            params["google"]["asset_group_id"] = asset_group_match.group(1)

        # Parse provider fields that are commonly supplied as explicit
        # key/value pairs.  The LLM path can emit the full structured object,
        # but the rule fallback must be useful too.  Provider-specific values
        # are only assigned to their channel; never copy a TikTok enum into
        # Meta/Google when the request spans multiple platforms.
        provider_param_keys = {
            "tiktok": [
                "objective_type", "promotion_type", "billing_event", "bid_type",
                "placement_type", "deep_bid_type", "budget_mode", "campaign_type",
                "campaign_automation_type", "budget_restriction", "app_id",
                "location_ids", "operating_systems", "age_groups", "gender",
                "landing_url",
            ],
            "meta": ["objective", "optimization_goal", "billing_event", "bidding_strategy"],
            "google": [
                "advertising_channel_type", "bidding_strategy", "target_cpa_micros",
                "target_roas",
            ],
            "dv360": ["campaign_type", "goal_type"],
        }
        array_params = {"location_ids", "operating_systems", "age_groups"}
        numeric_params = {"target_cpa_micros", "target_roas"}

        def parse_parameter_value(key: str, raw_value: str):
            value = raw_value.strip().strip("[](){}").strip().strip("'\"")
            if key in array_params:
                return [
                    item.strip().strip("'\"")
                    for item in re.split(r"[,，]", value)
                    if item.strip()
                ]
            if key in numeric_params:
                try:
                    return float(value) if "." in value else int(value)
                except ValueError:
                    return value
            return value.upper() if key not in {"app_id", "landing_url"} else value

        for platform, keys in provider_param_keys.items():
            if platform not in params:
                continue
            aliases_for_platform = platform_aliases.get(platform, [platform])
            alias_pattern = "|".join(re.escape(alias) for alias in aliases_for_platform)
            for key in keys:
                qualified = re.search(
                    rf"(?:{alias_pattern})\s+{re.escape(key)}\s*[=:：]\s*([^\s;；]+)",
                    user_input,
                    re.IGNORECASE,
                )
                unqualified = None
                if len(platforms) == 1:
                    unqualified = re.search(
                        rf"(?<![\w]){re.escape(key)}\s*[=:：]\s*([^\s;；]+)",
                        user_input,
                        re.IGNORECASE,
                    )
                match = qualified or unqualified
                if match:
                    params[platform][key] = parse_parameter_value(key, match.group(1))
        
        # campaign_name 提取 - 支持 "名称=xxx"、"name: xxx"、"：xxx"、"详情: xxx" 等格式
        name_patterns = [
            r'(?:名称|name)[=:\s]+([^\s,，;；：:]+(?:\s+[^\s,，;；：:]+)*)',
            r'详情[：:\s]+([^\s,，;；]+(?:\s+[^\s,，;；]+)*)',
            r'(?:这个|该|特定)\s*campaign[：:\s]*([A-Za-z0-9_\-]+(?:\s+[A-Za-z0-9_\-]+)*)',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                extracted = name_match.group(1).strip().rstrip('。,.，')
                extracted = re.split(
                    r'\s+(?:预算|budget|目标|objective|跑|持续|duration|天数)\b',
                    extracted,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip()
                if extracted:
                    for p in platforms:
                        params[p]["campaign_name"] = extracted
                    break
        
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

        # 更新请求的最小结构化参数，避免把自然语言原样交给 Handler。
        if any(kw in text for kw in ["更新", "修改", "编辑", "update", "modify", "edit", "暂停", "恢复", "启用"]):
            updates = {}
            status_match = re.search(r'(?:状态|status)[=：:\s]+([\w-]+)', text, re.IGNORECASE)
            if status_match:
                updates["status"] = status_match.group(1).upper()
            if any(kw in text for kw in ["暂停", "pause", "停用", "disable"]):
                updates["status"] = "PAUSED"
            elif any(kw in text for kw in ["恢复", "resume", "启用", "enable"]):
                updates["status"] = "ENABLED"
            if budget_match and any(kw in text for kw in ["更新", "修改", "预算", "budget"]):
                updates["daily_budget"] = float(budget_match.group(1))
            if updates:
                for p in platforms:
                    # Keep independent payloads per provider.  A later
                    # Capability-specific normalization (for example
                    # TikTok campaign_group_status vs Meta status) must never
                    # mutate the object that another channel receives.
                    params[p]["updates"] = dict(updates)
        
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

    def _extract_date_range(self, text: str) -> Optional[str]:
        """Extract a conservative normalized date range for reporting."""
        if any(kw in text for kw in ["昨天", "yesterday"]):
            return "YESTERDAY"
        if any(kw in text for kw in ["今天", "today"]):
            return "TODAY"
        if any(kw in text for kw in ["本月", "this month"]):
            return "THIS_MONTH"
        match = re.search(
            r"(?:最近|过去|近|last|past)\s*(\d+)\s*天",
            text,
            re.IGNORECASE,
        )
        if match:
            return f"LAST_{match.group(1)}_DAYS"
        return None

    def _extract_campaign_type(self, text: str) -> Optional[str]:
        """Extract an explicitly supplied campaign type conservatively.

        Do not guess a provider-specific type from a vague business objective;
        an explicit value is needed before business-policy validation can make
        a safe decision.
        """
        match = re.search(
            r"(?:campaign[_ -]?type|广告系列类型|广告类型|类型)\s*[=:：\s]+([A-Za-z][A-Za-z0-9_-]*)",
            text,
            re.IGNORECASE,
        )
        return match.group(1).upper() if match else None
    
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
        data = dict(data or {})
        # The prompt uses budget_daily for readability while ParsedIntent uses
        # the common ``budget`` field. Normalize aliases before construction.
        if data.get("budget") is None and data.get("budget_daily") is not None:
            data["budget"] = data.get("budget_daily")
        if data.get("date_range") is None and data.get("time_range") is not None:
            data["date_range"] = data.get("time_range")
        valid_intents = {
            "create_campaign", "create_asset_group", "update_campaign", "update_adset",
            "update_adgroup", "update_ad", "pause_campaign", "resume_campaign",
            "cross_channel_overview", "cross_channel_compare",
            "cross_channel_performance_insights", "cross_channel_optimize_budget",
            "cross_channel_export_report", "cross_channel_batch_pause", "cross_channel_batch_resume",
            "cross_channel_batch_update_budget", "boost_post", "run_remarketing",
            "download_report", "list_campaigns", "get_campaign", "list_adgroups",
            "list_adsets", "list_ads", "list_audiences", "list_ios", "get_io",
            "list_line_items", "get_line_item", "chat",
            "update_io", "update_line_item", "update_asset_group",
            "create_creative", "list_creatives", "list_videos", "list_images", "list_keywords",
            "list_conversions", "list_locations", "list_devices", "list_catalogs", "list_apps",
            "list_brand_safety", "list_asset_groups", "list_advertisers",
            "get_adset", "get_adgroup", "get_ad", "get_asset_group",
        }
        valid_intents.update(self._custom_intents)
        if data.get("intent_type") not in valid_intents:
            data["intent_type"] = "chat"

        # 确保 platforms 是列表，并限制为实际注册体系支持的平台。
        platforms = data.get("platforms", [])
        if isinstance(platforms, str):
            platforms = [platforms]
        platform_aliases = {
            "google-ads": "google",
            "google_ads": "google",
            "facebook": "meta",
            "instagram": "meta",
            "抖音": "tiktok",
            "谷歌": "google",
        }
        normalized_platforms = []
        for platform in platforms if isinstance(platforms, list) else []:
            normalized = platform_aliases.get(str(platform).lower(), str(platform).lower())
            if normalized in {"meta", "google", "tiktok", "dv360"} and normalized not in normalized_platforms:
                normalized_platforms.append(normalized)
        data["platforms"] = normalized_platforms

        if data.get("objective") not in {None, "sales", "leads", "traffic", "brand"}:
            data["objective"] = None
        if data.get("campaign_type") is not None:
            data["campaign_type"] = str(data["campaign_type"]).upper()
        if not isinstance(data.get("creative_materials"), list):
            data["creative_materials"] = []
        
        # 确保 platform_params 有所有平台
        params = data.get("platform_params", {})
        params = params if isinstance(params, dict) else {}
        normalized_params = {}
        for key, value in params.items():
            normalized = platform_aliases.get(str(key).lower(), str(key).lower())
            if normalized in {"meta", "google", "tiktok", "dv360"}:
                normalized_params[normalized] = value if isinstance(value, dict) else {}
        for p in normalized_platforms:
            normalized_params.setdefault(p, {})
        data["platform_params"] = normalized_params

        allowed = {
            "intent_type", "raw_input", "platforms", "objective", "campaign_type", "budget",
            "duration_days", "date_range", "creative_materials", "platform_params",
        }
        return {key: value for key, value in data.items() if key in allowed}
        
        return data


class SimpleIntentRouter(IntentRouter):
    """
    根据 Tool 自描述元数据进行发现式路由。

    Tool 的 action/resource_type/intent_types 来自 Capability 或 Skill
    plugin 自己的定义。这里不维护平台工具名称表，因此新增渠道只需要
    注册 Capability + Skill；新增同类 Tool 也不需要修改 Router。

    ``custom_mappings`` 和 ``register_skill_mappings`` 仅保留为外部扩展
    兼容入口，不参与内置渠道路由，也不是新增能力的必填配置。
    """

    def __init__(self, custom_mappings: dict = None):
        self._mappings = {
            str(intent): {str(platform): list(names) for platform, names in platforms.items()}
            for intent, platforms in (custom_mappings or {}).items()
        }
        # Kept as a read-only-era compatibility name for integrations that
        # inspect the router. Built-in routing never writes this map.
        self._capability_mappings = self._mappings
        self._skill_mappings: dict[str, dict[str, list[str]]] = {}

    def register_capability_mappings(self, mappings: dict) -> None:
        """Deprecated extension alias; prefer ToolDefinition metadata."""
        for intent, platforms in (mappings or {}).items():
            self._mappings.setdefault(str(intent), {}).update(
                {str(platform): list(names) for platform, names in (platforms or {}).items()}
            )

    def register_skill_mappings(self, mappings: dict) -> None:
        """Register an explicit plugin extension without a built-in table."""
        for intent_type, platforms in (mappings or {}).items():
            for platform, names in (platforms or {}).items():
                if not names:
                    continue
                self._skill_mappings.setdefault(str(intent_type), {})[
                    str(platform)
                ] = list(names)
                if platform == "google-ads":
                    self._skill_mappings.setdefault(str(intent_type), {})[
                        "google"
                    ] = list(names)

    def get_skill_mapping(self, intent_type: str) -> dict[str, list[str]] | None:
        """Return the authoritative Skill route, if one was registered."""
        mapping = self._skill_mappings.get(str(intent_type))
        if mapping is None:
            return None
        return {platform: list(names) for platform, names in mapping.items()}
    
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
        result: dict[str, list[ToolDefinition]] = {}
        explicit = self._skill_mappings.get(intent.intent_type) or self._mappings.get(intent.intent_type)
        for platform in intent.platforms:
            canonical = {"google": "google-ads", "google_ads": "google-ads"}.get(
                str(platform).lower(), str(platform).lower()
            )
            if explicit is not None:
                names = explicit.get(platform, explicit.get(canonical, []))
                tools = []
                for name in names:
                    try:
                        tools.append(registry.get(name)[0])
                    except KeyError:
                        continue
            else:
                tools = [
                    definition for definition in registry.list_by_platform(canonical)
                    if self._matches_intent(definition, intent.intent_type)
                ]
                tools.sort(key=self._sort_key)
            if tools:
                result[platform] = tools
        
        return result

    @staticmethod
    def _matches_intent(definition: ToolDefinition, intent_type: str) -> bool:
        return str(intent_type) in set(getattr(definition, "intent_types", []) or [])

    @staticmethod
    def _sort_key(definition: ToolDefinition) -> tuple[int, str]:
        # Parent resources are planned before children. The order remains a
        # generic hierarchy rule, not a provider-specific workflow.
        order = {
            "campaign": 10, "io": 20, "ad_set": 20, "ad_group": 20,
            "line_item": 30, "asset_group": 30, "ad": 40, "creative": 40,
        }
        return order.get(getattr(definition, "resource_type", ""), 100), definition.name
    
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
