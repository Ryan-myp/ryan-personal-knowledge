"""
api_clients/tiktok_client.py - TikTok Ads API 生产级客户端

接入已有 scripts/tiktok_api.py，补全重试、限流、错误分类。
"""

import logging
import time
import json
import re
import hashlib
from pathlib import Path
from datetime import date, timedelta
from typing import Any, Optional
import requests

from .base import BasePlatformClient, APIError, AuthError, RateLimitError, TemporaryError, RetryConfig, RateLimiter

logger = logging.getLogger(__name__)


class TikTokAPIClient(BasePlatformClient):
    """
    TikTok Marketing API 客户端 (open_api/v1.3)
    
    官方文档: https://business-api.tiktok.com/portal/docs
    认证: Access-Token Header
    速率限制: 100次/分钟 per advertiser
    
    关键差异 vs Meta:
    - 所有写操作都需要 advertiser_id
    - 响应结构: {"code": 0, "message": "", "data": {...}}
    - campaign_group_status: 0=暂停, 1=启用
    """
    
    BASE_URL = "https://business-api.tiktok.com"
    API_VERSION = "v1.3"
    SUPPORTED_API_VERSIONS = (API_VERSION,)
    # TikTok's current all-in-one Spark Ads surface replaces the legacy
    # campaign/adgroup/ad creation chain for these objectives.  Keep this
    # catalog next to the Provider adapter so Runtime does not grow a
    # TikTok-specific objective branch.
    ALL_IN_ONE_SPARK_OBJECTIVES = {
        "REACH": {"REACH"},
        "VIDEO_VIEWS": {"ENGAGED_VIEW"},
        "ENGAGEMENT": {"FOLLOWERS", "PAGE_VISIT"},
    }
    SMART_PLUS_OBJECTIVE_MAP = {
        "APP_PROMOTION": "APP_PROMOTION",
        "WEB_CONVERSIONS": "WEB_CONVERSIONS",
        "LEAD_GENERATION": "LEAD_GENERATION",
        # Product/UI aliases. TikTok's Upgraded Smart+ API represents web
        # Traffic and Sales under WEB_CONVERSIONS.
        "TRAFFIC": "WEB_CONVERSIONS",
        "SALES": "WEB_CONVERSIONS",
        "PRODUCT_SALES": "WEB_CONVERSIONS",
    }
    SMART_PLUS_GOALS = {
        "APP_PROMOTION": {"INSTALL", "IN_APP_EVENT", "VALUE"},
        "WEB_CONVERSIONS": {"CLICK", "CONVERT", "TRAFFIC_LANDING_PAGE_VIEW", "VALUE"},
        "LEAD_GENERATION": {"LEAD_GENERATION", "CLICK", "CONVERSATION"},
    }
    
    def __init__(
        self,
        credentials: dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "tiktok", retry_config)
        self.api_version = self._resolve_api_version(
            self.credentials.get("api_version")
        )
        self.api_prefix = f"open_api/{self.api_version}"
        self.access_token = self.credentials.get('access_token', '')
        # 速率限制: 100次/分钟
        self._rate_limiter = RateLimiter(max_requests=100, period=60)

    @staticmethod
    def _normalize_status(value: Any) -> int:
        """Normalize the public status aliases to TikTok's 0/1 field."""
        if value in (0, "0", "PAUSED", "DISABLE", "DISABLED"):
            return 0
        if value in (1, "1", "ACTIVE", "ENABLE", "ENABLED"):
            return 1
        raise ValueError("TikTok campaign status must be 0/1 or PAUSED/ACTIVE")

    @classmethod
    def _resolve_api_version(cls, requested: Any = None) -> str:
        version = str(requested or cls.API_VERSION).strip()
        if version.startswith("open_api/"):
            version = version.split("/", 1)[1]
        if version not in cls.SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported TikTok API version {version!r}; "
                f"supported versions: {list(cls.SUPPORTED_API_VERSIONS)}"
            )
        return version
    
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.BASE_URL}/{self.api_prefix}/{endpoint.lstrip('/')}"

    @staticmethod
    def _payload(result: Any) -> Any:
        """Unwrap a TikTok API envelope while keeping test doubles compatible."""
        if isinstance(result, dict) and "code" in result and "data" in result:
            return result.get("data") or {}
        return result

    @classmethod
    def _data_section(cls, result: Any) -> Any:
        """Return the business payload for both envelope shapes in the wild."""
        payload = cls._payload(result)
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload

    @staticmethod
    def _encode_filtering(filtering: Any, *, id_field: Optional[str] = None) -> Optional[str]:
        """Encode Runtime filter clauses into TikTok's JSON query shape.

        The public Tool contract uses a provider-neutral list of clauses, for
        example ``[{"field": "ADGROUP_IDS", "operator": "IN", ...}]``.
        TikTok v1.3 GET endpoints instead expect ``filtering`` to be a JSON
        object such as ``{"adgroup_ids": ["..."]}``.  Sending the public
        list directly is accepted by ``requests`` but rejected by TikTok as
        ``filtering: invalid json type``; omitting the conversion also makes
        a supposedly scoped lookup return an account-wide first page.
        """
        if filtering in (None, "", [], {}):
            if id_field is None:
                return None
            filtering = {id_field: []}
        if isinstance(filtering, str):
            return filtering
        if isinstance(filtering, dict):
            return json.dumps(filtering, separators=(",", ":"))
        if not isinstance(filtering, list):
            raise ValueError("TikTok filtering must be an object, JSON string, or clause list")

        field_map = {
            "CAMPAIGN_IDS": "campaign_ids",
            "ADGROUP_IDS": "adgroup_ids",
            "AD_GROUP_IDS": "adgroup_ids",
            "AD_IDS": "ad_ids",
            "CREATIVE_IDS": "creative_ids",
            "VIDEO_IDS": "video_ids",
            "IMAGE_IDS": "image_ids",
            "CONVERSION_IDS": "conversion_ids",
            "CATALOG_IDS": "catalog_ids",
        }
        encoded: dict[str, Any] = {}
        for clause in filtering:
            if not isinstance(clause, dict):
                raise ValueError("TikTok filtering clauses must be objects")
            field = str(clause.get("field") or "").upper()
            key = field_map.get(field, field.lower())
            values = clause.get("values")
            if values is None and clause.get("value") is not None:
                values = [clause["value"]]
            if values is None:
                continue
            encoded[key] = values
        if id_field and not encoded:
            encoded[id_field] = []
        return json.dumps(encoded, separators=(",", ":"))

    def _list_pages(self, endpoint: str, params: dict, max_pages: int = 100) -> list:
        """Consume TikTok ``page_info`` pages into one deterministic list."""
        items: list = []
        for page in range(1, max_pages + 1):
            page_params = {**params, "page": page}
            self.acquire_rate_limit(self._rate_limiter)
            response = self.request_raw(
                "GET", self._build_url(endpoint), params=page_params
            )
            if response.get("status_code") != 200:
                break
            envelope = response.get("data", {})
            payload = self._data_section(envelope)
            if isinstance(payload, list):
                # Current v1.3 DMP endpoints return ``data`` as the list and
                # ``page_info`` as a sibling of it.
                page_items = payload
                page_info = (
                    envelope.get("page_info", {})
                    if isinstance(envelope, dict) else {}
                )
            elif isinstance(payload, dict):
                # Keep the parser compatible with older list-shaped endpoint
                # responses that nest items under ``list``.
                page_items = payload.get("list", [])
                page_info = payload.get("page_info", {})
            else:
                raise APIError(f"TikTok {endpoint} returned an invalid list envelope")
            if isinstance(page_items, list):
                items.extend(page_items)
            if not isinstance(page_info, dict):
                break
            try:
                total_page = int(page_info.get("total_page", page))
            except (TypeError, ValueError):
                total_page = page
            if page >= total_page or not page_items:
                break
        return items
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        is_multipart = bool(kwargs.get('files'))
        headers = {'Access-Token': self.access_token, **kwargs.get('headers', {})}
        if not is_multipart:
            headers.setdefault('Content-Type', 'application/json')
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params'), timeout=self.http_timeout())
            elif method == 'POST':
                if is_multipart:
                    resp = requests.post(
                        url, headers=headers, data=kwargs.get('data'),
                        files=kwargs.get('files'), timeout=self.http_timeout(),
                    )
                else:
                    resp = requests.post(url, headers=headers, json=kwargs.get('data'), timeout=self.http_timeout())
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, timeout=self.http_timeout())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            try:
                data = resp.json() if resp.content else {}
            except ValueError:
                data = {}
            return {
                'status_code': resp.status_code,
                'data': data,
                'headers': dict(resp.headers),
            }
        except requests.exceptions.Timeout:
            return {'status_code': 504, 'data': {}, 'headers': {}}
        except requests.exceptions.ConnectionError:
            return {'status_code': 502, 'data': {}, 'headers': {}}
    
    def _extract_data(self, response: dict) -> Any:
        """TikTok 响应结构: {code, message, data}"""
        return self._data_section(response.get('data', {}))
    
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        data = response.get('data', {})
        
        # HTTP status must retain its meaning.  Treating 400/401/403 as a
        # temporary error causes needless GET retries and obscures whether the
        # caller has a malformed request, an expired token, or no permission.
        if status_code == 401:
            return AuthError("TikTok: Invalid or expired access token")
        if status_code == 403:
            message = data.get('message', 'Permission denied') if isinstance(data, dict) else 'Permission denied'
            return AuthError(f"TikTok: {message}")
        if status_code == 429:
            raw_retry_after = response.get('headers', {}).get('Retry-After', 60)
            try:
                retry_after = float(raw_retry_after)
            except (TypeError, ValueError):
                retry_after = 60.0
            return RateLimitError("TikTok HTTP 429: rate limited", retry_after=retry_after)
        if status_code >= 500:
            return TemporaryError(f"TikTok HTTP {status_code}")
        if status_code >= 400:
            message = data.get('message', 'Bad request') if isinstance(data, dict) else 'Bad request'
            return APIError(f"TikTok HTTP {status_code}: {message}", status_code=status_code, response=data)
        
        # API 错误
        code = data.get('code', 0) if isinstance(data, dict) else 0
        message = data.get('message', '') if isinstance(data, dict) else ''
        
        if code == 0:
            return None
        
        # 认证错误
        if code in (1000, 1001, 1002, 1003, 1004):
            return AuthError(f"TikTok auth error {code}: {message}")
        
        # 限流错误
        if code == 2200003:
            return RateLimitError(f"TikTok rate limit: {message}", retry_after=60)
        
        # 可重试的临时错误
        if code in (2000, 2001, 2200001, 2200002, 2200004):
            return TemporaryError(f"TikTok temp error {code}: {message}")
        
        return APIError(f"TikTok error {code}: {message}", status_code=status_code, response=data)
    
    # ==================== 账户管理 ====================
    
    def list_accounts(self, advertiser_ids: list[str]) -> list:
        """获取广告账户信息"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {'advertiser_ids': advertiser_ids}
        result = self.request('POST', 'account/get/', data=data)
        payload = self._data_section(result)
        if isinstance(payload, dict):
            return payload.get('advertisers', payload.get('list', []))
        return payload

    def get_account(self, advertiser_id: str) -> dict:
        """Get one TikTok advertiser through the existing account/get endpoint."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        accounts = self.list_accounts([advertiser_id])
        return next(
            (
                item for item in accounts
                if isinstance(item, dict)
                and str(
                    item.get("advertiser_id")
                    or item.get("account_id")
                    or item.get("id")
                    or ""
                ) == advertiser_id
            ),
            {},
        )
    
    # ==================== Campaign 管理 ====================
    
    def list_campaigns(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取 Campaign 列表"""
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        # Consume a bounded number of provider pages. Runtime applies the
        # response-size limit for cards; the client must still be able to
        # read back a newly-created resource that is not on page one.
        return self._list_pages('campaign/get/', data, max_pages=100)
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """获取 Campaign 详情"""
        # TikTok API 不支持 filtering，直接查询所有 campaign 并过滤
        result = self.list_campaigns(advertiser_id)
        for camp in result:
            if str(camp.get('campaign_id')) == str(campaign_id):
                return camp
        raise APIError(f"TikTok campaign {campaign_id} was not found")
    
    def create_campaign(self, advertiser_id: str, campaign: dict) -> str:
        """创建 Campaign
        
        必需字段:
        - campaign_name: 广告系列名称
        - objective_type: 优化目标 (APP_PROMOTION, PRODUCT_SALES, TRAFFIC, VIDEO_VIEWS, CONVERSIONS, REACH, LEAD_GENERATION, ENGAGEMENT, CATALOG_SALES, SHOP_PURCHASES, WEB_CONVERSIONS)
        - budget_mode: 预算模式 (BUDGET_MODE_DAY, BUDGET_MODE_INFINITE, BUDGET_MODE_DYNAMIC_DAILY_BUDGET, BUDGET_MODE_TOTAL)
        - campaign_type: 广告系列类型 (REGULAR_CAMPAIGN, SMART_CAMPAIGN, etc.)
        
        可选字段:
        - campaign_automation_type: 自动化类型 (MANUAL, SMART_PLUS, etc.)
        - campaign_group_status: 状态 (0=PAUSED, 1=ACTIVE)
        - budget_restriction: 预算限制 (NO_LIMITATION, DAILY_BUDGET, LIFETIME_BUDGET)
        - daily_budget: 每日预算（账户货币；TikTok v1.3 的 wire 字段为 budget）
        - app_promotion_type: APP 推广类型 (APP_RETARGETING, APP_ACQUISITION)
        """
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_name': campaign.get('name', 'Untitled Campaign'),
            'objective_type': campaign.get('objective_type', 'TRAFFIC'),
            'campaign_automation_type': campaign.get('campaign_automation_type', 'MANUAL'),
            # New-structure Campaigns use operation_status on the create
            # endpoint. campaign_group_status is an older update-era field
            # and is silently ignored by the current provider contract.
            'operation_status': (
                'DISABLE'
                if self._normalize_status(campaign.get('status', 0)) == 0
                else 'ENABLE'
            ),
            'budget_restriction': campaign.get('budget_restriction', 'NO_LIMITATION'),
            'budget_mode': campaign.get('budget_mode', 'BUDGET_MODE_INFINITE'),
            'campaign_type': campaign.get('campaign_type', 'REGULAR_CAMPAIGN'),
        }
        # ``daily_budget`` is a Runtime-facing semantic alias. TikTok v1.3
        # expects the account-currency amount in the wire field ``budget``
        # for both daily and total budget modes.
        budget_mode = campaign.get('budget_mode')
        if campaign.get('daily_budget') is not None:
            data['budget'] = float(campaign['daily_budget'])
        elif budget_mode == 'BUDGET_MODE_TOTAL' and campaign.get('budget') is not None:
            data['budget'] = float(campaign['budget'])
        if campaign.get('app_promotion_type'):
            data['app_promotion_type'] = campaign['app_promotion_type']
        # Preserve the explicit creation contract.  Previously these fields
        # were accepted by the tool schema but silently discarded here, which
        # made a dry-run plan differ from the eventual provider request.
        for key in ('budget_restriction', 'budget_mode', 'campaign_type',
                    'campaign_automation_type', 'objective_type'):
            if key in campaign and campaign[key] not in (None, ''):
                data[key] = campaign[key]
        
        result = self.request('POST', 'campaign/create/', data=data)
        payload = self._data_section(result)
        resource_id = payload.get('campaign_id') if isinstance(payload, dict) else None
        return self.require_resource_id(resource_id, "TikTok campaign create")
    
    def update_campaign(self, advertiser_id: str, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign"""
        self.acquire_rate_limit(self._rate_limiter)
        normalized_updates = {key: value for key, value in updates.items() if value is not None}
        daily_budget = normalized_updates.pop('daily_budget', None)
        budget = normalized_updates.pop('budget', None)
        if daily_budget is not None:
            normalized_updates['budget'] = float(daily_budget)
        elif budget is not None:
            normalized_updates['budget'] = float(budget)
        data = {
            'advertiser_id': str(advertiser_id),
            # TikTok v1.3 models hierarchy IDs as strings on create.  Do not
            # coerce them to integers: large IDs are opaque provider values
            # and the API rejects numeric JSON for this field.
            'campaign_id': str(campaign_id),
            'campaign': normalized_updates,
        }
        return self.request('POST', 'campaign/update/', data=data)
    
    def pause_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """暂停 Campaign"""
        self.acquire_rate_limit(self._rate_limiter)
        return self.request(
            'POST', 'campaign/status/update/',
            data={
                'advertiser_id': str(advertiser_id),
                'campaign_ids': [str(campaign_id)],
                'operation_status': 'DISABLE',
            },
        )
    
    def resume_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """恢复 Campaign"""
        self.acquire_rate_limit(self._rate_limiter)
        return self.request(
            'POST', 'campaign/status/update/',
            data={
                'advertiser_id': str(advertiser_id),
                'campaign_ids': [str(campaign_id)],
                'operation_status': 'ENABLE',
            },
        )
    
    def delete_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """删除 Campaign"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_ids': [int(campaign_id)],
        }
        return self.request('POST', 'campaign/delete/', data=data)
    
    # ==================== Ad Group 管理 ====================
    
    def list_adgroups(self, advertiser_id: str, campaign_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取 Ad Group 列表"""
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': str(campaign_id),
            'page_size': page_size,
        }
        data['filtering'] = self._encode_filtering(
            filtering or {'campaign_ids': [str(campaign_id)]}
        )
        rows = self._list_pages('adgroup/get/', data, max_pages=100)
        # TikTok may return an account-wide page despite campaign_id. Enforce
        # the parent relation locally so lookup cards and get operations can
        # never show another Campaign's Ad Groups.
        wanted = str(campaign_id)
        return [
            row for row in rows
            if isinstance(row, dict)
            and str(row.get('campaign_id') or row.get('campaignId') or '') == wanted
        ]
    
    def get_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str) -> dict:
        """获取 Ad Group 详情"""
        # TikTok API 不支持 filtering，直接查询所有 adgroup 并过滤
        result = self.list_adgroups(advertiser_id, campaign_id)
        for ag in result:
            if str(ag.get('adgroup_id')) == str(adgroup_id):
                return ag
        raise APIError(f"TikTok ad group {adgroup_id} was not found")
    
    def create_adgroup(self, advertiser_id: str, campaign_id: str, adgroup: dict) -> str:
        """创建 Ad Group。

        TikTok v1.3's ``adgroup/create`` request is a flat provider payload;
        only the HTTP envelope is shared.  The previous nested ``ad_group``
        object caused required fields such as ``schedule_type`` to be
        invisible to TikTok and made the dry-run contract diverge from live
        behavior.
        """
        self.acquire_rate_limit(self._rate_limiter)
        budget_mode = adgroup.get('budget_mode')
        data = {
            'advertiser_id': str(advertiser_id),
            # Hierarchy IDs are opaque strings in TikTok v1.3 create
            # contracts; numeric JSON is rejected by the provider.
            'campaign_id': str(campaign_id),
            'adgroup_name': adgroup['name'],
            'operation_status': (
                'DISABLE'
                if adgroup.get('status', 0) in (0, '0', 'PAUSED', 'DISABLE')
                else 'ENABLE'
            ),
        }
        daily_budget = adgroup.get('daily_budget')
        budget = adgroup.get('budget')
        if daily_budget is not None:
            data['budget'] = float(daily_budget)
        elif budget is not None and budget_mode != 'BUDGET_MODE_INFINITE':
            data['budget'] = float(budget)
        # New callers use the symbolic values from the parameter catalog;
        # keep the old numeric promote_object_type field for compatibility.
        for key in (
            'promotion_type', 'promote_object_type', 'bid_type', 'placement_type',
            'billing_event', 'deep_bid_type', 'budget_mode',
            'app_id', 'landing_url', 'location_ids', 'operating_systems',
            'age_groups', 'gender', 'auto_targeting_enabled', 'optimization_goal',
            'conversion_id', 'placements', 'promotion_website_type',
            'optimization_event', 'pixel_id', 'brand_safety_type',
            'brand_safety_partner', 'audience_type', 'audience_ids',
            'excluded_audience_ids',
            'catalog_id', 'product_set_id',
            'bid_price', 'conversion_bid_price', 'deep_cpa_bid', 'roas_bid',
            'budget_optmize_on', 'interest_category_ids', 'interest_keyword_ids',
            'interest_keywords', 'purchase_intention_keyword_ids', 'device_model_ids',
            'languages', 'network_types', 'min_android_version', 'min_ios_version',
            'ios14_targeting', 'device_price_ranges', 'contextual_tag_ids',
            'targeting_expansion', 'household_income', 'spending_power',
            'blocked_pangle_app_ids', 'pacing', 'schedule_type', 'schedule_start_time',
            'schedule_end_time', 'dayparting', 'frequency', 'frequency_schedule',
            'product_source', 'shopping_ads_type', 'shopping_ads_retargeting_type',
            'shopping_ads_retargeting_actions_days', 'store_id', 'is_hfss',
        ):
            if key in adgroup and adgroup[key] not in (None, ''):
                data[key] = adgroup[key]
        # The creation contract calls these wire fields start_time/end_time;
        # schedule_* names are the stable Runtime-facing aliases.
        if adgroup.get('schedule_start_time'):
            data['start_time'] = adgroup['schedule_start_time']
        if adgroup.get('schedule_end_time'):
            data['end_time'] = adgroup['schedule_end_time']
        if adgroup.get('promotion_type') == 'CATALOG':
            if not str(adgroup.get('catalog_id') or '').strip():
                raise ValueError('TikTok CATALOG promotion requires catalog_id')
            if not str(adgroup.get('product_set_id') or '').strip():
                raise ValueError('TikTok CATALOG promotion requires product_set_id')
        # 定向
        if adgroup.get('targeting'):
            data['targeting'] = adgroup['targeting']
        
        result = self.request('POST', 'adgroup/create/', data=data)
        payload = self._data_section(result)
        resource_id = (
            payload.get('adgroup_id') or payload.get('ad_group_id')
            if isinstance(payload, dict) else None
        )
        return self.require_resource_id(resource_id, "TikTok ad group create")

    def create_product_sales_adgroup(
        self, advertiser_id: str, campaign_id: str, adgroup: dict
    ) -> str:
        """Create a Product Sales ad group through the regular v1.3 endpoint.

        This is a typed adapter, not a second TikTok endpoint.  The provider
        uses the same ``adgroup/create/`` resource for website, catalog and
        Shop destinations; the typed method keeps the destination checks at
        the provider boundary.
        """
        if not isinstance(adgroup, dict):
            raise ValueError("Product Sales ad group must be an object")
        normalized = dict(adgroup)
        normalized["objective_type"] = "PRODUCT_SALES"
        product_source = str(normalized.get("product_source") or "").upper()
        promotion_type = str(normalized.get("promotion_type") or "").upper()
        if promotion_type not in {"WEBSITE", "CATALOG"}:
            raise ValueError("Product Sales requires promotion_type=WEBSITE or CATALOG")
        if promotion_type == "CATALOG" or product_source == "CATALOG":
            if not str(normalized.get("catalog_id") or "").strip():
                raise ValueError("Product Sales catalog destination requires catalog_id")
            if not str(normalized.get("product_set_id") or "").strip():
                raise ValueError("Product Sales catalog destination requires product_set_id")
        if product_source == "STORE" and not str(normalized.get("store_id") or "").strip():
            raise ValueError("Product Sales Shop destination requires store_id")
        return self.create_adgroup(advertiser_id, campaign_id, normalized)
    
    def update_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str, updates: dict) -> dict:
        """更新 Ad Group"""
        self.acquire_rate_limit(self._rate_limiter)
        normalized_updates = {key: value for key, value in updates.items() if value is not None}
        daily_budget = normalized_updates.pop('daily_budget', None)
        budget = normalized_updates.pop('budget', None)
        if daily_budget is not None:
            normalized_updates['daily_budget'] = int(float(daily_budget) * 100)
        elif budget is not None:
            normalized_updates['budget'] = int(float(budget) * 100)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': str(campaign_id),
            'ad_group_id': str(adgroup_id),
            'ad_group': normalized_updates,
        }
        return self.request('POST', 'adgroup/update/', data=data)

    def update_adgroup_targeting(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str,
        targeting: dict,
    ) -> dict:
        """Update the structured targeting dimensions of one Ad Group.

        Targeting is deliberately a separate adapter from general Ad Group
        metadata updates.  This keeps the Tool contract explicit and lets
        lookup-backed IDs be validated before they reach TikTok's payload.
        """
        if not isinstance(targeting, dict) or not targeting:
            raise ValueError("targeting must be a non-empty object")
        allowed_fields = {
            "location_ids", "operating_systems", "age_groups", "gender",
            "auto_targeting_enabled", "audience_ids", "excluded_audience_ids",
            "interest_category_ids", "device_ids", "carrier_ids", "browser_ids",
        }
        unknown = set(targeting) - allowed_fields
        if unknown:
            raise ValueError(
                f"Unsupported TikTok targeting fields: {sorted(unknown)}"
            )
        normalized: dict[str, Any] = {}
        list_fields = {
            "location_ids", "operating_systems", "age_groups", "audience_ids",
            "excluded_audience_ids", "interest_category_ids", "device_ids",
            "carrier_ids", "browser_ids",
        }
        for field_name, value in targeting.items():
            if value is None:
                continue
            if field_name in list_fields:
                if not isinstance(value, list) or not value:
                    raise ValueError(f"targeting.{field_name} must be a non-empty array")
                if any(item in (None, "") for item in value):
                    raise ValueError(
                        f"targeting.{field_name} must not contain empty values"
                    )
                normalized[field_name] = value
            else:
                normalized[field_name] = value

        operating_systems = normalized.get("operating_systems")
        if operating_systems and any(
            str(value).upper() not in {"ANDROID", "IOS"}
            for value in operating_systems
        ):
            raise ValueError("targeting.operating_systems must contain ANDROID or IOS")
        if operating_systems:
            normalized["operating_systems"] = [
                str(value).upper() for value in operating_systems
            ]
        age_groups = normalized.get("age_groups")
        allowed_age_groups = {
            "AGE_13_17", "AGE_18_24", "AGE_25_34", "AGE_35_44",
            "AGE_45_54", "AGE_55_64", "AGE_65+",
        }
        if age_groups and any(str(value) not in allowed_age_groups for value in age_groups):
            raise ValueError(
                f"targeting.age_groups must contain only {sorted(allowed_age_groups)}"
            )
        if age_groups:
            normalized["age_groups"] = [str(value).upper() for value in age_groups]
        if "gender" in normalized and normalized["gender"] not in {
            "GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE",
        }:
            normalized_gender = str(normalized["gender"]).upper()
            if normalized_gender not in {
                "GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE",
            }:
                raise ValueError(
                    "targeting.gender must be GENDER_UNLIMITED, GENDER_MALE or GENDER_FEMALE"
                )
            normalized["gender"] = normalized_gender
        if not normalized:
            raise ValueError("targeting must contain a supported non-null field")

        self.acquire_rate_limit(self._rate_limiter)
        data = {
            "advertiser_id": str(advertiser_id),
            "campaign_id": int(campaign_id),
            "ad_group_id": int(adgroup_id),
            "ad_group": normalized,
        }
        return self.request("POST", "adgroup/update/", data=data)

    def update_ad(self, advertiser_id: str, adgroup_id: str, ad_id: str, updates: dict) -> dict:
        """Update an Ad using TikTok's advertiser/ad-group scoped endpoint."""
        self.acquire_rate_limit(self._rate_limiter)
        normalized_updates = {
            key: value for key, value in updates.items() if value is not None
        }
        if "status" in normalized_updates and "ad_status" not in normalized_updates:
            normalized_updates["ad_status"] = normalized_updates.pop("status")
        data = {
            "advertiser_id": str(advertiser_id),
            "ad_group_id": int(adgroup_id),
            "ad_id": int(ad_id),
            "ad": normalized_updates,
        }
        return self.request("POST", "ad/update/", data=data)
    
    def pause_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str) -> dict:
        """暂停 Ad Group"""
        return self.update_adgroup(advertiser_id, campaign_id, adgroup_id, {'ad_group_status': 0})
    
    # ==================== Ad 管理 ====================
    
    def list_ads(self, advertiser_id: str, adgroup_id: str, page_size: int = 20) -> list:
        """获取 Ad 列表"""
        data = {
            'advertiser_id': str(advertiser_id),
            # TikTok's scoped Ad query uses a JSON ``adgroup_ids`` filter;
            # ``ad_group_id`` as a top-level query parameter is ignored and
            # returns an account-wide page.
            'filtering': json.dumps(
                {'adgroup_ids': [str(adgroup_id)]}, separators=(',', ':')
            ),
            'page_size': page_size,
        }
        rows = self._list_pages('ad/get/', data, max_pages=100)
        # Apply the same defense for an account-wide Ad page.
        wanted = str(adgroup_id)
        return [
            row for row in rows
            if isinstance(row, dict)
            and str(
                row.get('adgroup_id')
                or row.get('ad_group_id')
                or row.get('adgroupId')
                or ''
            ) == wanted
        ]
    
    def get_ad(self, advertiser_id: str, adgroup_id: str, ad_id: str) -> dict:
        """获取 Ad 详情"""
        # TikTok API 不支持 filtering，直接查询所有 ad 并过滤
        result = self.list_ads(advertiser_id, adgroup_id)
        for ad in result:
            if str(ad.get('ad_id')) == str(ad_id):
                return ad
        raise APIError(f"TikTok ad {ad_id} was not found")
    
    def create_ad(self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict) -> str:
        """创建 Ad using TikTok v1.3's creative-list payload.

        TikTok's ``ad/create/`` endpoint has a flat request envelope, but the
        actual ad fields are required inside ``creatives``. The public Tool
        input stays flat and this client performs the provider translation.
        """
        self.acquire_rate_limit(self._rate_limiter)
        creative = {}
        supplied_creatives = ad.get('creatives')
        if isinstance(supplied_creatives, list) and supplied_creatives:
            if not isinstance(supplied_creatives[0], dict):
                raise ValueError('creatives must contain objects')
            creative = dict(supplied_creatives[0])
        elif isinstance(supplied_creatives, dict):
            creative = dict(supplied_creatives)

        creative.update({
            'ad_name': ad.get('name', creative.get('ad_name', 'Untitled Ad')),
            'operation_status': ad.get(
                'operation_status',
                'DISABLE' if ad.get('status', 0) in (0, '0', 'PAUSED', 'DISABLE') else 'ENABLE',
            ),
        })
        if ad.get('landing_page_url'):
            creative['landing_page_url'] = ad['landing_page_url']
        if ad.get('conversion_id') is not None:
            creative['conversion_id'] = ad['conversion_id']
        if ad.get('text'):
            text_payload = ad['text']
            creative['ad_text'] = (
                text_payload.get('ad_text')
                if isinstance(text_payload, dict) else text_payload
            )
        if ad.get('media'):
            creative['media'] = ad['media']
        # Keep every field declared by the provider-owned ad contracts. The
        # generic adapter remains useful for formats without a dedicated
        # builder, but it must not silently discard a valid provider field.
        for key in (
            'ad_format', 'status', 'video_id', 'image_ids', 'spark_post_id',
            'page_id', 'tracking_pixel_id', 'operation_status', 'creative_type',
            'display_name', 'catalog_id', 'product_set_id', 'call_to_action',
            'call_to_action_id', 'ad_text', 'identity_id', 'identity_type',
            'tiktok_item_id', 'promotion_type', 'app_id', 'app_promotion_type',
            'operating_systems', 'deep_link', 'tracking_url', 'promote_object', 'ad_text_settings',
            'brand_safety', 'run_time_settings',
            'deeplink', 'deeplink_type', 'click_tracking_url',
            'impression_tracking_url', 'video_view_tracking_url',
            'dynamic_destination', 'dynamic_format', 'product_specific_type',
            'sku_ids', 'item_group_ids', 'shopping_ads_deeplink_type',
            'shopping_ads_fallback_type', 'shopping_ads_video_package_id',
            'shopping_ads_word_set', 'promotional_music_disabled',
            'item_duet_status', 'item_stitch_status', 'instant_product_page_used',
            'playable_url',
        ):
            if key != 'status' and key in ad and ad[key] not in (None, ''):
                creative[key] = ad[key]
        if creative.get('ad_format') and not creative.get('creative_type'):
            creative.pop('creative_type', None)
        if ad.get('ad_text') and not creative.get('ad_text'):
            creative['ad_text'] = ad['ad_text']

        data = {
            'advertiser_id': str(advertiser_id),
            'adgroup_id': str(adgroup_id),
            'creatives': [creative],
        }
        result = self.request('POST', 'ad/create/', data=data)
        payload = self._data_section(result)
        resource_id = None
        if isinstance(payload, dict):
            resource_id = payload.get('ad_id')
            ad_ids = payload.get('ad_ids')
            if resource_id is None and isinstance(ad_ids, list) and ad_ids:
                resource_id = ad_ids[0]
            if resource_id is None:
                creatives = payload.get('creatives')
                if isinstance(creatives, list) and creatives:
                    first = creatives[0]
                    if isinstance(first, dict):
                        resource_id = first.get('ad_id')
        return self.require_resource_id(resource_id, "TikTok ad create")

    def create_product_sales_ad(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict
    ) -> str:
        """Create a typed Product Sales ad through ``ad/create/``."""
        if not isinstance(ad, dict):
            raise ValueError("Product Sales ad must be an object")
        normalized = dict(ad)
        normalized["objective_type"] = "PRODUCT_SALES"
        product_source = str(normalized.get("product_source") or "").upper()
        promotion_type = str(normalized.get("promotion_type") or "").upper()
        if promotion_type == "CATALOG" or product_source == "CATALOG":
            if not str(normalized.get("catalog_id") or "").strip():
                raise ValueError("Product Sales catalog destination requires catalog_id")
            if not str(normalized.get("product_set_id") or "").strip():
                raise ValueError("Product Sales catalog destination requires product_set_id")
        if product_source == "STORE" and not str(normalized.get("store_id") or "").strip():
            raise ValueError("Product Sales Shop destination requires store_id")
        ad_format = str(normalized.get("ad_format") or "").upper()
        if ad_format in {"SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL"}:
            return self._create_format_ad(
                advertiser_id, campaign_id, adgroup_id, normalized, ad_format,
                {
                    "SINGLE_VIDEO": ("video_id", "media", "creatives"),
                    "SINGLE_IMAGE": ("image_ids", "media", "creatives"),
                    "CAROUSEL": ("image_ids", "media", "creatives"),
                }[ad_format],
                min_image_count=2 if ad_format == "CAROUSEL" else 0,
            )
        if not any(
            normalized.get(field) not in (None, "", {}, [])
            for field in (
                "media", "creatives", "video_id", "image_ids",
                "sku_ids", "item_group_ids", "product_set_id",
            )
        ):
            raise ValueError(
                "Product Sales ad requires media, creatives, an asset ID, or product selection"
            )
        return self.create_ad(advertiser_id, campaign_id, adgroup_id, normalized)

    def _create_format_ad(
        self,
        advertiser_id: str,
        campaign_id: str,
        adgroup_id: str,
        ad: dict,
        format_name: str,
        asset_fields: tuple[str, ...],
        min_image_count: int = 0,
    ) -> str:
        """Create a typed ad after validating its format-specific asset shape."""
        if not isinstance(ad, dict):
            raise ValueError("ad must be an object")
        normalized = dict(ad)
        normalized["ad_format"] = format_name
        if not any(normalized.get(field) for field in asset_fields):
            raise ValueError(
                f"{format_name} ad requires one of: {', '.join(asset_fields)}"
            )
        if min_image_count:
            image_ids = normalized.get("image_ids")
            if image_ids and (
                not isinstance(image_ids, list) or len(image_ids) < min_image_count
            ):
                raise ValueError(
                    f"{format_name} ad image_ids must contain at least {min_image_count} items"
                )
        return self.create_ad(advertiser_id, campaign_id, adgroup_id, normalized)

    def create_single_video_ad(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict
    ) -> str:
        """Create a single-video ad through TikTok's ad-create endpoint."""
        return self._create_format_ad(
            advertiser_id, campaign_id, adgroup_id, ad, "SINGLE_VIDEO",
            ("video_id", "tiktok_item_id", "media", "creatives"),
        )

    def create_single_image_ad(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict
    ) -> str:
        """Create a single-image ad through TikTok's ad-create endpoint."""
        return self._create_format_ad(
            advertiser_id, campaign_id, adgroup_id, ad, "SINGLE_IMAGE",
            ("image_ids", "media", "creatives"),
        )

    def create_carousel_ad(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict
    ) -> str:
        """Create a carousel ad with at least two image IDs when image IDs are used."""
        return self._create_format_ad(
            advertiser_id, campaign_id, adgroup_id, ad, "CAROUSEL",
            ("image_ids", "media", "creatives"), min_image_count=2,
        )

    def create_lead_ad(
        self,
        advertiser_id: str,
        campaign_id: str,
        adgroup_id: str,
        ad: dict,
    ) -> str:
        """Create a Lead Generation ad bound to a TikTok Instant Page.

        TikTok's v1.3 ad-create contract represents an Instant Form with
        ``page_id``. The form/page is created by the Instant Page Editor SDK,
        not by an Ads API Lead Form CRUD endpoint.
        """
        if not isinstance(ad, dict):
            raise ValueError("lead ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        if not page_id or not page_id.isdigit():
            raise ValueError("page_id is required and must contain digits only")
        normalized = dict(ad)
        normalized["page_id"] = int(page_id)
        normalized.pop("form_id", None)
        normalized.pop("promote_object", None)
        return self.create_ad(advertiser_id, campaign_id, adgroup_id, normalized)

    def create_app_ad(
        self,
        advertiser_id: str,
        campaign_id: str,
        adgroup_id: str,
        ad: dict,
    ) -> str:
        """Create a TikTok App Promotion install/event ad."""
        if not isinstance(ad, dict):
            raise ValueError("app ad must be an object")
        app_id = str(ad.get("app_id") or "").strip()
        promotion_type = str(ad.get("promotion_type") or "").upper()
        operating_systems = ad.get("operating_systems")
        if not app_id or promotion_type not in {"APP_ANDROID", "APP_IOS"}:
            raise ValueError("app_id and a valid promotion_type are required")
        if not isinstance(operating_systems, list) or not operating_systems:
            raise ValueError("operating_systems is required")
        expected_os = "ANDROID" if promotion_type == "APP_ANDROID" else "IOS"
        if expected_os not in {str(value).upper() for value in operating_systems}:
            raise ValueError(f"{promotion_type} requires operating_systems to include {expected_os}")

        normalized = dict(ad)
        normalized["app_id"] = app_id
        normalized["promotion_type"] = promotion_type
        normalized["promote_object"] = {
            "app_install": {"app_id": app_id},
        }
        return self.create_ad(advertiser_id, campaign_id, adgroup_id, normalized)
    
    # ==================== Spark Ads（达人原生广告）====================
    
    def create_spark_ad(
        self,
        advertiser_id: str,
        campaign_id: str,
        adgroup_id: str,
        spark_post_id: str,
    ) -> str:
        """
        创建 Spark Ads（使用达人已有帖子进行投放）
        
        spark_post_id: 达人帖子 ID（格式：{post_id}@{user_id}）
        """
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group_id': int(adgroup_id),
            'ad': {
                'ad_name': f"Spark Ad - {spark_post_id}",
                'spark_post_id': spark_post_id,
                'ad_status': 1,
            }
        }
        result = self.request('POST', 'ad/create/', data=data)
        payload = self._data_section(result)
        resource_id = payload.get('ad_id') if isinstance(payload, dict) else None
        return self.require_resource_id(resource_id, "TikTok Spark Ad create")

    def _smart_plus_status(self, payload: dict[str, Any]) -> str:
        value = payload.get("operation_status", payload.get("status", "DISABLE"))
        if value in (0, "0", "PAUSED", "DISABLE", "DISABLED", None, ""):
            return "DISABLE"
        if value in (1, "1", "ACTIVE", "ENABLE", "ENABLED"):
            return "ENABLE"
        raise ValueError("TikTok Smart+ operation_status must be ENABLE or DISABLE")

    def _smart_plus_objective(self, value: Any) -> tuple[str, str]:
        public = str(value or "").strip().upper()
        provider = self.SMART_PLUS_OBJECTIVE_MAP.get(public)
        if not provider:
            raise ValueError(
                "TikTok Upgraded Smart+ supports APP_PROMOTION, WEB_CONVERSIONS "
                "and LEAD_GENERATION (Traffic/Sales map to WEB_CONVERSIONS)"
            )
        return public, provider

    @staticmethod
    def _smart_plus_response(result: Any, resource: str) -> dict[str, Any]:
        data = TikTokAPIClient._data_section(result)
        if not isinstance(data, dict):
            raise APIError(f"TikTok Smart+ {resource} create returned an invalid response")
        return data

    def create_smart_plus_campaign(
        self, advertiser_id: str, campaign: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an Upgraded Smart+ campaign using the current endpoint."""
        if not isinstance(campaign, dict):
            raise ValueError("TikTok Smart+ campaign payload must be an object")
        public_objective, objective = self._smart_plus_objective(
            campaign.get("objective_type") or campaign.get("objective")
        )
        campaign = {**campaign, "request_id": str(campaign.get("request_id") or time.time_ns())}
        for field in ("request_id", "campaign_name"):
            if campaign.get(field) in (None, ""):
                raise ValueError(f"TikTok Smart+ campaign requires {field}")
        if public_objective == "APP_PROMOTION":
            for field in ("app_promotion_type", "app_id"):
                if campaign.get(field) in (None, "", []):
                    raise ValueError(f"APP_PROMOTION requires {field}")
        if objective == "WEB_CONVERSIONS":
            destination = str(campaign.get("sales_destination") or "").upper()
            if public_objective == "TRAFFIC":
                destination = "WEBSITE"
            if not destination:
                raise ValueError("WEB_CONVERSIONS requires sales_destination")
            campaign = {**campaign, "sales_destination": destination}

        wire_fields = {
            "request_id", "operation_status", "objective_type", "app_promotion_type",
            "sales_destination", "is_search_campaign", "catalog_enabled", "catalog_type",
            "campaign_type", "is_promotional_campaign", "app_id", "gaming_ad_compliance_agreement",
            "campaign_app_profile_page_state", "disable_skan_campaign", "campaign_name",
            "special_industries", "budget_optimize_on", "budget_mode", "budget",
            "budget_auto_adjust_strategy", "budget_auto_adjust_max_amount",
            "smart_plus_adgroup_mode",
        }
        data = {"advertiser_id": str(advertiser_id)}
        data.update({
            key: value for key, value in campaign.items()
            if key in wire_fields and value not in (None, "", [])
        })
        data["objective_type"] = objective
        data["operation_status"] = self._smart_plus_status(campaign)
        if public_objective == "TRAFFIC":
            data["sales_destination"] = "WEBSITE"
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "smart_plus/campaign/create/", data=data)
        response = self._smart_plus_response(result, "campaign")
        if not response.get("campaign_id"):
            raise APIError("TikTok Smart+ campaign response missing campaign_id")
        return response

    def create_smart_plus_adgroup(
        self, advertiser_id: str, campaign_id: str, adgroup: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an Upgraded Smart+ ad group using the current endpoint."""
        if not isinstance(adgroup, dict):
            raise ValueError("TikTok Smart+ ad group payload must be an object")
        adgroup = {**adgroup, "request_id": str(adgroup.get("request_id") or time.time_ns())}
        for field in (
            "request_id", "adgroup_name", "promotion_type", "optimization_goal",
            "bid_type", "billing_event", "schedule_type", "schedule_start_time",
        ):
            if adgroup.get(field) in (None, "", []):
                raise ValueError(f"TikTok Smart+ ad group requires {field}")
        objective = str(adgroup.get("objective_type") or "WEB_CONVERSIONS").upper()
        public_objective, provider_objective = self._smart_plus_objective(objective)
        goal = str(adgroup.get("optimization_goal") or "").upper()
        allowed = self.SMART_PLUS_GOALS[provider_objective]
        if goal not in allowed:
            raise ValueError(
                f"optimization_goal={goal} is not valid for {public_objective}; "
                f"expected one of {sorted(allowed)}"
            )
        if public_objective == "APP_PROMOTION":
            if adgroup.get("promotion_type") not in {"APP_ANDROID", "APP_IOS"}:
                raise ValueError("APP_PROMOTION requires promotion_type=APP_ANDROID or APP_IOS")
            if adgroup.get("app_id") in (None, "", []):
                raise ValueError("APP_PROMOTION requires app_id")
            if adgroup.get("billing_event") != "OCPM":
                raise ValueError("APP_PROMOTION requires billing_event=OCPM")
            if goal == "IN_APP_EVENT" and adgroup.get("optimization_event") in (None, ""):
                raise ValueError("IN_APP_EVENT requires optimization_event")
        elif public_objective == "TRAFFIC" and adgroup.get("promotion_type") != "WEBSITE":
            raise ValueError("TRAFFIC requires promotion_type=WEBSITE")
        locations = adgroup.get("location_ids")
        if not adgroup.get("saved_audience_id") and (
            not isinstance(locations, list) or not locations
        ):
            raise ValueError("TikTok Smart+ ad group requires location_ids or saved_audience_id")
        if adgroup.get("bid_type") == "BID_TYPE_CUSTOM":
            bid_field = "conversion_bid_price" if goal in {"CONVERT", "TRAFFIC_LANDING_PAGE_VIEW"} else "bid_price"
            if adgroup.get(bid_field) in (None, ""):
                raise ValueError(f"BID_TYPE_CUSTOM requires {bid_field}")
        if adgroup.get("schedule_type") == "SCHEDULE_START_END" and not adgroup.get("schedule_end_time"):
            raise ValueError("SCHEDULE_START_END requires schedule_end_time")

        wire_fields = {
            "request_id", "operation_status", "adgroup_name", "catalog_id", "product_set_id",
            "promotion_type", "promotion_target_type", "optimization_goal", "optimization_event",
            "app_attribution_source", "app_data_source", "app_id", "location_ids",
            "saved_audience_id", "gender", "age_groups", "operating_systems", "placement_type",
            "placements", "targeting_optimization_mode", "bid_type", "bid_price",
            "conversion_bid_price", "deep_bid_type", "roas_bid", "billing_event", "budget_mode",
            "budget", "schedule_type", "schedule_start_time", "schedule_end_time", "frequency",
            "frequency_schedule", "identity_type", "identity_id", "identity_authorized_bc_id",
            "pixel_id", "tracking_pixel_id",
        }
        data = {"advertiser_id": str(advertiser_id), "campaign_id": str(campaign_id)}
        data.update({
            key: value for key, value in adgroup.items()
            if key in wire_fields and value not in (None, "", [])
        })
        data["operation_status"] = self._smart_plus_status(adgroup)
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "smart_plus/adgroup/create/", data=data)
        response = self._smart_plus_response(result, "adgroup")
        if not response.get("adgroup_id"):
            raise APIError("TikTok Smart+ ad group response missing adgroup_id")
        return response

    def create_smart_plus_ad(
        self, advertiser_id: str, campaign_id: str, adgroup_id: str,
        ad: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an Upgraded Smart+ ad with a closed creative contract."""
        if not isinstance(ad, dict):
            raise ValueError("TikTok Smart+ ad payload must be an object")
        ad = {**ad, "request_id": str(ad.get("request_id") or time.time_ns())}
        for field in ("request_id", "ad_name"):
            if ad.get(field) in (None, ""):
                raise ValueError(f"TikTok Smart+ ad requires {field}")
        if not any(ad.get(field) not in (None, "", []) for field in ("tiktok_item_id", "video_id", "image_ids")):
            raise ValueError("TikTok Smart+ ad requires tiktok_item_id, video_id or image_ids")
        if ad.get("identity_type") in {"TT_USER", "BC_AUTH_TT", "AUTH_CODE"} and not ad.get("identity_id"):
            raise ValueError("Spark Ads require identity_id")
        if ad.get("identity_type") == "BC_AUTH_TT" and not ad.get("identity_authorized_bc_id"):
            raise ValueError("identity_type=BC_AUTH_TT requires identity_authorized_bc_id")

        wire_fields = {
            "request_id", "operation_status", "ad_name", "ad_format", "tiktok_item_id",
            "video_id", "image_ids", "ad_text", "identity_type", "identity_id",
            "identity_authorized_bc_id", "call_to_action_id", "landing_page_url", "deeplink",
            "dark_post_status",
        }
        data = {
            "advertiser_id": str(advertiser_id),
            "campaign_id": str(campaign_id),
            "adgroup_id": str(adgroup_id),
        }
        data.update({
            key: value for key, value in ad.items()
            if key in wire_fields and value not in (None, "", [])
        })
        data["operation_status"] = self._smart_plus_status(ad)
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "smart_plus/ad/create/", data=data)
        response = self._smart_plus_response(result, "ad")
        if not response.get("smart_plus_ad_id") and not response.get("ad_id"):
            raise APIError("TikTok Smart+ ad response missing smart_plus_ad_id")
        return response

    def create_all_in_one_spark_ad(
        self, advertiser_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a current TikTok all-in-one Spark Ads campaign.

        TikTok documents ``business/spark_ad/create`` as the current one-step
        surface for Reach, Video Views and Community Interaction. It
        creates the Campaign, Ad Group and Spark Ad in one provider request;
        it is not the legacy ``campaign/create`` + ``adgroup/create`` +
        ``ad/create`` chain.

        The method intentionally accepts a provider-shaped payload rather than
        reconstructing one from a generic Runtime object.  The Capability owns
        the closed Tool schema, while this adapter owns provider conditionals
        and the endpoint contract.
        """
        if not isinstance(payload, dict):
            raise ValueError("TikTok all-in-one Spark Ads payload must be an object")

        normalized = dict(payload)
        objective = str(normalized.get("objective_type") or "").upper()
        goals = self.ALL_IN_ONE_SPARK_OBJECTIVES.get(objective)
        if goals is None:
            raise ValueError(
                "TikTok all-in-one Spark Ads supports objective_type "
                "REACH, VIDEO_VIEWS or ENGAGEMENT"
            )
        optimization_goal = str(normalized.get("optimization_goal") or "").upper()
        if optimization_goal not in goals:
            raise ValueError(
                f"optimization_goal={optimization_goal or '<empty>'} is not valid "
                f"for objective_type={objective}; expected one of {sorted(goals)}"
            )

        for field in (
            "campaign_name", "adgroup_name", "ad_name", "budget_mode",
            "budget", "schedule_type", "schedule_start_time", "bid_type",
            "identity_type", "identity_id", "tiktok_item_id",
        ):
            if normalized.get(field) in (None, "", []):
                raise ValueError(f"TikTok all-in-one Spark Ads requires {field}")

        location_ids = normalized.get("location_ids")
        saved_audience_id = normalized.get("saved_audience_id")
        if not saved_audience_id and (
            not isinstance(location_ids, list) or not location_ids
        ):
            raise ValueError(
                "TikTok all-in-one Spark Ads requires location_ids or saved_audience_id"
            )

        budget_mode = str(normalized.get("budget_mode") or "").upper()
        if budget_mode not in {"BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"}:
            raise ValueError(
                "all-in-one Spark Ads budget_mode must be BUDGET_MODE_DAY or BUDGET_MODE_TOTAL"
            )
        try:
            normalized["budget"] = float(normalized["budget"])
        except (TypeError, ValueError) as exc:
            raise ValueError("TikTok Spark Ads budget must be numeric") from exc
        if normalized["budget"] <= 0:
            raise ValueError("TikTok Spark Ads budget must be greater than zero")

        schedule_type = str(normalized.get("schedule_type") or "").upper()
        if schedule_type not in {"SCHEDULE_FROM_NOW", "SCHEDULE_START_END"}:
            raise ValueError(
                "all-in-one Spark Ads schedule_type must be SCHEDULE_FROM_NOW or SCHEDULE_START_END"
            )
        if budget_mode == "BUDGET_MODE_TOTAL" and schedule_type != "SCHEDULE_START_END":
            raise ValueError(
                "BUDGET_MODE_TOTAL requires schedule_type=SCHEDULE_START_END"
            )
        if schedule_type == "SCHEDULE_START_END" and not normalized.get("schedule_end_time"):
            raise ValueError(
                "SCHEDULE_START_END requires schedule_end_time"
            )

        bid_type = str(normalized.get("bid_type") or "").upper()
        if bid_type not in {"BID_TYPE_NO_BID", "BID_TYPE_CUSTOM"}:
            raise ValueError(
                "all-in-one Spark Ads bid_type must be BID_TYPE_NO_BID or BID_TYPE_CUSTOM"
            )
        if bid_type == "BID_TYPE_CUSTOM":
            bid_field = (
                "conversion_bid_price"
                if optimization_goal in {"TRAFFIC_LANDING_PAGE_VIEW", "FOLLOWERS"}
                else "bid_price"
            )
            if normalized.get(bid_field) in (None, ""):
                raise ValueError(
                    f"bid_type=BID_TYPE_CUSTOM requires {bid_field} for {optimization_goal}"
                )

        if objective == "REACH":
            for field in ("frequency", "frequency_schedule"):
                if normalized.get(field) in (None, ""):
                    raise ValueError(f"Reach Spark Ads requires {field}")

        if optimization_goal in {"CLICK", "TRAFFIC_LANDING_PAGE_VIEW"}:
            for field in ("call_to_action", "landing_page_url"):
                if normalized.get(field) in (None, ""):
                    raise ValueError(
                        f"{optimization_goal} Spark Ads requires {field}"
                    )
        elif optimization_goal == "PAGE_VISIT":
            if normalized.get("call_to_action") in (None, ""):
                raise ValueError("PAGE_VISIT Spark Ads requires call_to_action")
        elif normalized.get("call_to_action") and not normalized.get("landing_page_url"):
            raise ValueError(
                "landing_page_url is required when call_to_action is specified"
            )

        if str(normalized.get("identity_type") or "").upper() == "BC_AUTH_TT" and not normalized.get(
            "identity_authorized_bc_id"
        ):
            raise ValueError(
                "identity_type=BC_AUTH_TT requires identity_authorized_bc_id"
            )

        # Do not forward Runtime-only fields or silently pass arbitrary input
        # through to a provider endpoint.  Add a field here only after it is
        # present in the official v1.3 contract and the Tool schema.
        wire_fields = {
            "campaign_name", "objective_type", "adgroup_name", "saved_audience_id",
            "location_ids", "gender", "age_groups", "budget_mode", "budget",
            "schedule_type", "schedule_start_time", "schedule_end_time",
            "optimization_goal", "frequency", "frequency_schedule", "bid_type",
            "bid_price", "conversion_bid_price", "ad_name", "identity_type",
            "identity_id", "identity_authorized_bc_id", "tiktok_item_id",
            "call_to_action", "landing_page_url",
        }
        data = {"advertiser_id": str(advertiser_id)}
        data.update({
            key: value for key, value in normalized.items()
            if key in wire_fields and value not in (None, "", [])
        })
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "business/spark_ad/create/", data=data)
        payload_data = self._data_section(result)
        if not isinstance(payload_data, dict):
            raise APIError("TikTok all-in-one Spark Ads returned an invalid response")
        for resource in ("campaign_id", "adgroup_id", "ad_id"):
            if not payload_data.get(resource):
                raise APIError(
                    f"TikTok all-in-one Spark Ads response missing {resource}"
                )
        return payload_data
    
    # ==================== 报表查询 ====================
    
    def get_campaign_report(
        self,
        advertiser_id: str,
        campaign_ids: list[str],
        time_range: Any = None,
        report_type: str = "CAMPAIGN",
    ) -> list:
        """
        查询 Campaign 级别报表
        
        report_type: "CAMPAIGN" | "ADGROUP" | "AD"
        """
        self.acquire_rate_limit(self._rate_limiter)
        
        data = {
            'advertiser_id': str(advertiser_id),
            'report_name': f"report_{int(time.time())}",
            'report_type': report_type,
            'data_content': {
                'columns': [
                    'campaign_group_id', 'campaign_group_name',
                    'impressions', 'clicks', 'ctr', 'cpc', 'spend',
                    'conversions', 'conversion_rate', 'cost_per_conversion',
                ],
                'time_range': self._normalize_time_range(time_range),
                'filtering': [
                    {'field': 'CAMPAIGN_IDS', 'operator': 'IN', 'values': [int(x) for x in campaign_ids]}
                ],
            }
        }
        # 先创建报表任务
        create_result = self.request('POST', 'report/task/create/', data=data)
        create_payload = self._data_section(create_result)
        task_id = create_payload.get('task_id', '') if isinstance(create_payload, dict) else ''
        
        if not task_id:
            raise APIError("TikTok report task creation returned no task_id")
        
        # 轮询获取结果
        return self._poll_report_result(advertiser_id, task_id)
    
    def _poll_report_result(self, advertiser_id: str, task_id: str, max_wait: int = 30) -> list:
        """轮询报表任务结果"""
        for i in range(max_wait):
            self.sleep_with_budget(1)
            data = {'advertiser_id': str(advertiser_id), 'task_id': task_id}
            result = self.request('POST', 'report/task/info/get/', data=data)
            
            payload = self._data_section(result)
            if not isinstance(payload, dict):
                raise APIError("TikTok report task returned an invalid response envelope")
            status = payload.get("status")
            if status in (2, "2", "COMPLETED", "SUCCESS"):
                content = payload.get('content', {})
                if isinstance(content, list):
                    return content
                if isinstance(content, dict):
                    rows = content.get('data', content.get('list', []))
                    if isinstance(rows, list):
                        return rows
                return []
            if status in (3, "3", "FAILED", "ERROR"):
                message = payload.get("message") or payload.get("error_message") or "unknown error"
                raise APIError(f"TikTok report task failed: {message}")
        
        raise APIError("TikTok report task polling timed out")
    
    def get_adgroup_report(
        self,
        advertiser_id: str,
        campaign_id: str,
        adgroup_ids: list[str] = None,
        time_range: dict = None,
    ) -> list:
        """查询 Ad Group 级别报表"""
        filtering = []
        if adgroup_ids:
            filtering.append({'field': 'ADGROUP_IDS', 'operator': 'IN', 'values': [int(x) for x in adgroup_ids]})
        
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'report_name': f"adgroup_report_{int(time.time())}",
            'report_type': "ADGROUP",
            'data_content': {
                'columns': ['ad_group_id', 'ad_group_name', 'impressions', 'clicks', 'spend', 'conversions'],
                'time_range': self._normalize_time_range(
                    time_range or 'LAST_7_DAYS'
                ),
                'filtering': filtering,
            }
        }
        result = self.request('POST', 'report/task/create/', data=data)
        payload = self._data_section(result)
        task_id = payload.get('task_id', '') if isinstance(payload, dict) else ''
        if not task_id:
            raise APIError("TikTok ad group report task creation returned no task_id")
        return self._poll_report_result(advertiser_id, task_id)

    
    # ==================== 人群定向查询 ====================
    
    def list_audiences(
        self, advertiser_id: str, custom_audience_ids: list[str] = None,
        page_size: int = 20,
    ) -> list:
        """获取人群包列表"""
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if custom_audience_ids:
            data['custom_audience_ids'] = [str(item) for item in custom_audience_ids]
        return self._list_pages('dmp/custom_audience/list/', data)

    def get_audience(self, advertiser_id: str, audience_id: str) -> dict:
        """获取人群包详情"""
        advertiser_id = str(advertiser_id or '').strip()
        audience_id = str(audience_id or '').strip()
        if not advertiser_id.isdigit() or not audience_id.isdigit():
            raise ValueError("advertiser_id and audience_id must contain digits only")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            'GET', 'dmp/custom_audience/get/',
            params={
                'advertiser_id': advertiser_id,
                'custom_audience_ids': [audience_id],
            },
        )
        payload = self._data_section(result)
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict) and isinstance(first.get('audience_details'), list):
                return first['audience_details'][0] if first['audience_details'] else {}
            return first if isinstance(first, dict) else {}
        if isinstance(payload, dict):
            details = payload.get('audience_details')
            if isinstance(details, list) and details:
                return details[0]
            return payload
        return {}

    def create_audience(self, advertiser_id: str, audience: dict) -> str:
        """Create a TikTok customer-file custom audience."""
        if not isinstance(audience, dict):
            raise ValueError("audience must be an object")
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        name = str(audience.get("name") or audience.get("custom_audience_name") or "").strip()
        calculate_type = str(audience.get("calculate_type") or "").strip().upper()
        file_paths = audience.get("file_paths")
        calculate_type_values = {
            "EMAIL_SHA256": "8", "FIRST_MD5": "7", "FIRST_SHA256": "6",
            "GAID_MD5": "13", "GAID_SHA256": "16", "IDFA_MD5": "12",
            "IDFA_SHA256": "15", "MAID_MD5": "7", "MAID_SHA256": "6",
            "MULTIPLE_TYPES": "100", "PHONE_SHA256": "9",
        }
        if not name or len(name) > 128:
            raise ValueError("audience name must contain 1-128 characters")
        if calculate_type not in calculate_type_values:
            raise ValueError("unsupported TikTok calculate_type")
        if not isinstance(file_paths, list) or not file_paths or len(file_paths) > 500:
            raise ValueError("file_paths must contain 1-500 uploaded file paths")
        if any(not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16}", path) for path in file_paths):
            raise ValueError("file_paths must contain TikTok file paths returned by upload")
        data = {
            "advertiser_id": advertiser_id,
            "custom_audience_name": name,
            "calculate_type": calculate_type_values[calculate_type],
            "file_paths": file_paths,
        }
        for key in ("retention_in_days", "audience_sub_type", "audience_enhancement"):
            if audience.get(key) is not None:
                data[key] = audience[key]
        result = self.request("POST", "dmp/custom_audience/create/", data=data)
        payload = self._data_section(result)
        resource_id = None
        if isinstance(payload, dict):
            resource_id = (
                payload.get("audience_id")
                or payload.get("custom_audience_id")
                or payload.get("id")
            )
        return self.require_resource_id(resource_id, "TikTok audience create")

    def update_audience(
        self, advertiser_id: str, audience_id: str, updates: dict,
    ) -> dict:
        """Update a TikTok custom audience name or uploaded file set.

        TikTok requires file operations to reference paths returned by
        ``upload_audience_file``. Raw customer identifiers are never accepted
        at this provider boundary.
        """
        advertiser_id = str(advertiser_id or "").strip()
        audience_id = str(audience_id or "").strip()
        if not advertiser_id.isdigit() or not audience_id.isdigit():
            raise ValueError("advertiser_id and audience_id must contain digits only")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        allowed = {
            "custom_audience_name", "file_paths", "action",
            "audience_enhancement", "audience_sub_type", "context_info",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported TikTok audience update fields: {sorted(unknown)}")
        payload = {key: value for key, value in updates.items() if value is not None}
        has_name = payload.get("custom_audience_name") not in (None, "")
        file_paths = payload.get("file_paths")
        has_files = file_paths not in (None, [], "")
        if not has_name and not has_files:
            raise ValueError("updates requires custom_audience_name or file_paths")
        if has_name:
            name = str(payload["custom_audience_name"]).strip()
            if not name or len(name) > 128:
                raise ValueError("custom_audience_name must contain 1-128 characters")
            payload["custom_audience_name"] = name
        if has_files:
            if not isinstance(file_paths, list) or not file_paths or len(file_paths) > 50:
                raise ValueError("file_paths must contain 1-50 uploaded file paths")
            if any(not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16}", path) for path in file_paths):
                raise ValueError("file_paths must contain TikTok file paths returned by upload")
            payload["file_paths"] = file_paths
            action = str(payload.get("action", "REPLACE")).upper()
            if action not in {"REPLACE", "APPEND", "REMOVE"}:
                raise ValueError("action must be REPLACE, APPEND or REMOVE")
            payload["action"] = action
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "POST", "dmp/custom_audience/update/",
            data={
                "advertiser_id": advertiser_id,
                "custom_audience_id": audience_id,
                **payload,
            },
        )
        return result if isinstance(result, dict) else {"result": result}

    def upload_audience_file(
        self, advertiser_id: str, file_path: str, calculate_type: str,
        file_name: str = None,
    ) -> dict:
        """Upload an encrypted CSV/TXT file and return TikTok's file_path."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        calculate_type_values = {
            "EMAIL_SHA256": "8", "FIRST_MD5": "7", "FIRST_SHA256": "6",
            "GAID_MD5": "13", "GAID_SHA256": "16", "IDFA_MD5": "12",
            "IDFA_SHA256": "15", "MAID_MD5": "7", "MAID_SHA256": "6",
            "MULTIPLE_TYPES": "100", "PHONE_SHA256": "9",
        }
        calculate_key = str(calculate_type or "").strip().upper()
        if calculate_key not in calculate_type_values:
            raise ValueError(
                "calculate_type must be one of "
                + ", ".join(sorted(calculate_type_values))
            )
        path = Path(str(file_path or "")).expanduser()
        if not path.is_file():
            raise ValueError("file_path must point to an existing file")
        if path.suffix.lower() not in {".csv", ".txt"}:
            raise ValueError("file_path must use a .csv or .txt extension")
        if path.stat().st_size <= 0:
            raise ValueError("audience upload file must not be empty")
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("audience upload file cannot exceed 100 MiB")
        digest = hashlib.md5()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        upload_name = str(file_name or path.name).strip()
        if not upload_name or Path(upload_name).name != upload_name:
            raise ValueError("file_name must be a simple filename")
        if Path(upload_name).suffix.lower() not in {".csv", ".txt"}:
            raise ValueError("file_name must use a .csv or .txt extension")
        self.acquire_rate_limit(self._rate_limiter)
        with path.open("rb") as stream:
            result = self.request(
                "POST", "dmp/custom_audience/file/upload/",
                data={
                    "advertiser_id": advertiser_id,
                    "calculate_type": calculate_type_values[calculate_key],
                    "file_name": upload_name,
                    "file_signature": digest.hexdigest(),
                },
                files={"file": (upload_name, stream, "text/plain")},
            )
        if isinstance(result, dict):
            return result
        return {"result": result}

    def delete_audience(self, advertiser_id: str, audience_id: str) -> dict:
        """删除 TikTok 自定义或相似受众。"""
        advertiser_id = str(advertiser_id or "").strip()
        audience_id = str(audience_id or "").strip()
        if not advertiser_id.isdigit() or not audience_id.isdigit():
            raise ValueError("advertiser_id and audience_id must contain digits only")
        self.request(
            "POST", "dmp/custom_audience/delete/",
            data={"advertiser_id": advertiser_id, "custom_audience_ids": [audience_id]},
        )
        return {"success": True, "audience_id": audience_id}
    
    def list_interest_categories(
        self,
        advertiser_id: str = None,
        version: int = 2,
        placements: list[str] = None,
        special_industries: list[str] = None,
        language: str = "en",
    ) -> list:
        """获取账户范围内 TikTok v1.3 兴趣类别列表。"""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        try:
            version = int(version)
        except (TypeError, ValueError) as exc:
            raise ValueError("version must be 1 or 2") from exc
        if version not in {1, 2}:
            raise ValueError("version must be 1 or 2")
        language = str(language or "en").strip().lower()
        if language not in {
            "en", "zh", "ja", "de", "es", "fr", "id", "it", "ko",
            "ru", "th", "tr", "vi", "ar", "pt", "ms",
        }:
            raise ValueError("unsupported interest category language")
        if placements is not None and (not isinstance(placements, list) or not placements):
            raise ValueError("placements must be a non-empty list when provided")
        params: dict[str, Any] = {
            "advertiser_id": advertiser_id, "version": version, "language": language,
        }
        if placements:
            params["placements"] = placements
        if special_industries:
            params["special_industries"] = special_industries
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("GET", "tool/interest_category/", params=params)
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("interest_categories", [])) if isinstance(payload, dict) else []

    def list_action_categories(
        self, advertiser_id: str, special_industries: list[str] = None
    ) -> list:
        """获取 TikTok v1.3 行业/特殊行业 Action 类别。"""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if special_industries is not None and not isinstance(special_industries, list):
            raise ValueError("special_industries must be a list")
        params: dict[str, Any] = {"advertiser_id": advertiser_id}
        if special_industries:
            params["special_industries"] = special_industries
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("GET", "tool/action_category/", params=params)
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("action_categories", [])) if isinstance(payload, dict) else []

    def list_languages(self, advertiser_id: str) -> list:
        """获取 TikTok 官方语言定向选项。"""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "GET", "tool/language/", params={"advertiser_id": advertiser_id}
        )
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("languages", [])) if isinstance(payload, dict) else []

    def list_device_models(self, advertiser_id: str) -> list:
        """获取 TikTok 官方设备型号定向选项。"""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "GET", "tool/device_model/", params={"advertiser_id": advertiser_id}
        )
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("device_models", [])) if isinstance(payload, dict) else []

    def recommend_interest_keywords(
        self,
        advertiser_id: str,
        keyword: str,
        language: str = "en",
        limit: int = 50,
        mode: str = "FUZZ_MATCH",
        audience_type: str = "GENERAL_INTEREST",
    ) -> list:
        """根据种子词获取 TikTok 兴趣定向推荐。"""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        keyword = str(keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")
        language = str(language or "en").strip().lower()
        if language not in {
            "fr", "id", "it", "ja", "ms", "ar", "vi", "en", "ru", "es",
            "th", "tr", "hi", "zh", "de", "ko",
        }:
            raise ValueError("unsupported keyword language")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be between 1 and 50") from exc
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        mode = str(mode or "FUZZ_MATCH").strip().upper()
        if mode not in {"FUZZ_MATCH", "SEMANTIC_RECOMMEND"}:
            raise ValueError("unsupported interest keyword recommendation mode")
        audience_type = str(audience_type or "GENERAL_INTEREST").strip().upper()
        if audience_type not in {"GENERAL_INTEREST", "PURCHASE_INTENTION"}:
            raise ValueError("unsupported interest keyword audience type")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "GET", "tool/interest_keyword/recommend/", params={
                "advertiser_id": advertiser_id,
                "keyword": keyword,
                "language": language,
                "limit": limit,
                "mode": mode,
                "audience_type": audience_type,
            }
        )
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("keywords", [])) if isinstance(payload, dict) else []
    
    def get_interest_category(self, category_id: str) -> dict:
        """获取兴趣类别详情"""
        data = {'category_id': category_id}
        result = self.request('GET', 'interest_category/get/', params=data)
        payload = self._data_section(result)
        return payload if isinstance(payload, dict) else {}
    
    # ==================== 地域定向查询 ====================
    
    def list_locations(self, location_type: str = None) -> list:
        """获取地域列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {}
        if location_type:
            data['location_type'] = location_type
        result = self.request('GET', 'location/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def search_locations(self, keyword: str, location_type: str = None) -> list:
        """搜索地域"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {'keyword': keyword}
        if location_type:
            data['location_type'] = location_type
        result = self.request('GET', 'location/search/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []

    def list_regions(
        self,
        advertiser_id: str,
        placements: list[str],
        objective_type: str,
        promotion_target_type: str = None,
        operating_system: str = None,
        brand_safety_type: str = None,
        brand_safety_partner: str = None,
        level_range: str = None,
        rf_campaign_type: str = None,
    ) -> list:
        """Get available regions from TikTok's official Tool Region API.

        Region availability depends on placement and campaign objective. The
        older location helper remains available for generic targeting, while
        this method exposes the provider-owned context required by v1.3.
        """
        advertiser_id = str(advertiser_id or '').strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if not isinstance(placements, list) or not placements:
            raise ValueError("placements must be a non-empty array")
        objective_type = str(objective_type or '').strip()
        if not objective_type:
            raise ValueError("objective_type is required")
        params: dict[str, Any] = {
            'advertiser_id': advertiser_id,
            # TikTok's query decoder expects the repeated structured value as
            # a JSON array string. Passing a Python list through requests
            # produces ``placements=PLACEMENT_TIKTOK`` and the provider
            # rejects it with error 40002.
            'placements': json.dumps(placements, separators=(',', ':')),
            'objective_type': objective_type,
        }
        for key, value in (
            ('promotion_target_type', promotion_target_type),
            ('operating_system', operating_system),
            ('brand_safety_type', brand_safety_type),
            ('brand_safety_partner', brand_safety_partner),
            ('level_range', level_range),
            ('rf_campaign_type', rf_campaign_type),
        ):
            if value not in (None, ''):
                params[key] = value
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'tool/region/', params=params)
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get(
                'region_info',
                payload.get('list', payload.get('regions', payload.get('locations', []))),
            )
        return []
    
    # ==================== 设备定向查询 ====================
    
    def list_devices(self) -> list:
        """获取设备列表"""
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'device/get/')
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_operating_systems(self) -> list:
        """获取操作系统列表"""
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'os/get/')
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_carriers(self) -> list:
        """获取运营商列表"""
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'carrier/get/')
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_browsers(self) -> list:
        """获取浏览器列表"""
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'browser/get/')
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    # ==================== 创意素材查询 ====================
    
    def list_creatives(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取创意列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        result = self.request('GET', 'creative/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []

    def get_creative(self, advertiser_id: str, creative_id: str) -> dict:
        """Get one Creative through the existing creative/get endpoint."""
        advertiser_id = str(advertiser_id or "").strip()
        creative_id = str(creative_id or "").strip()
        if not advertiser_id or not creative_id:
            raise ValueError("advertiser_id and creative_id must not be empty")
        creatives = self.list_creatives(
            advertiser_id,
            filtering=[{
                "field": "CREATIVE_IDS",
                "operator": "IN",
                "values": [creative_id],
            }],
            page_size=1,
        )
        return next(
            (
                item for item in creatives
                if isinstance(item, dict)
                and str(item.get("creative_id") or item.get("id") or "") == creative_id
            ),
            {},
        )
    
    def list_videos(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取广告素材库视频列表。

        ``video/get/`` is not a v1.3 ad-asset endpoint.  TikTok's current
        contract exposes advertiser-owned ad videos through
        ``file/video/ad/search/``; keeping that mapping here means the
        capability and Skill do not need to know provider endpoint details.
        """
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        # Asset rows contain preview URLs and can be much larger than normal
        # resource rows.  Return one bounded page here; callers can narrow
        # with ``filtering`` and request another page through the provider
        # adapter without overflowing Runtime's result budget.
        return self._list_pages('file/video/ad/search/', data, max_pages=1)

    def get_video(self, advertiser_id: str, video_id: str) -> dict:
        """Get one video asset through the existing video/get endpoint."""
        advertiser_id = str(advertiser_id or "").strip()
        video_id = str(video_id or "").strip()
        if not advertiser_id or not video_id:
            raise ValueError("advertiser_id and video_id must not be empty")
        videos = self.list_videos(
            advertiser_id,
            filtering=[{
                "field": "VIDEO_IDS",
                "operator": "IN",
                "values": [video_id],
            }],
            page_size=1,
        )
        return next(
            (
                item for item in videos
                if isinstance(item, dict)
                and str(item.get("video_id") or item.get("id") or "") == video_id
            ),
            {},
        )
    
    def list_images(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取广告素材库图片列表。"""
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        return self._list_pages('file/image/ad/search/', data, max_pages=1)

    def get_image(self, advertiser_id: str, image_id: str) -> dict:
        """Get one image asset through the existing image/get endpoint."""
        advertiser_id = str(advertiser_id or "").strip()
        image_id = str(image_id or "").strip()
        if not advertiser_id or not image_id:
            raise ValueError("advertiser_id and image_id must not be empty")
        images = self.list_images(
            advertiser_id,
            filtering=[{
                "field": "IMAGE_IDS",
                "operator": "IN",
                "values": [image_id],
            }],
            page_size=1,
        )
        return next(
            (
                item for item in images
                if isinstance(item, dict)
                and str(item.get("image_id") or item.get("id") or "") == image_id
            ),
            {},
        )

    # ==================== 创意素材上传 ====================

    @staticmethod
    def _validate_media_file(file_path: str, allowed_suffixes: set[str], label: str) -> Path:
        path = Path(str(file_path or "")).expanduser()
        if not path.is_file():
            raise ValueError(f"{label} file_path must point to an existing file")
        if path.suffix.lower() not in allowed_suffixes:
            suffixes = ", ".join(sorted(allowed_suffixes))
            raise ValueError(f"{label} file_path must use one of: {suffixes}")
        if path.stat().st_size <= 0:
            raise ValueError(f"{label} file must not be empty")
        return path

    @staticmethod
    def _media_file_signature(path: Path) -> str:
        digest = hashlib.md5()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _media_upload_name(file_name: Optional[str], path: Optional[Path], label: str) -> str:
        name = str(file_name or (path.name if path else "")).strip()
        if not name or Path(name).name != name:
            raise ValueError(f"{label} file_name must be a simple filename")
        if len(name) > 100:
            name = name[:100]
        return name

    @staticmethod
    def _media_upload_type(
        upload_type: Optional[str], file_path: Optional[str], asset_url: Optional[str],
        asset_id: Optional[str], label: str,
    ) -> str:
        provided = [bool(file_path), bool(asset_url), bool(asset_id)]
        if sum(provided) != 1:
            raise ValueError(
                f"{label} upload requires exactly one of file_path, url, or asset_id"
            )
        value = str(upload_type or "").strip().upper()
        if not value:
            value = "UPLOAD_BY_FILE" if file_path else (
                "UPLOAD_BY_URL" if asset_url else "UPLOAD_BY_FILE_ID"
            )
        valid = {"UPLOAD_BY_FILE", "UPLOAD_BY_URL", "UPLOAD_BY_FILE_ID", "UPLOAD_BY_VIDEO_ID"}
        if value not in valid:
            raise ValueError(f"unsupported {label} upload_type")
        if file_path and value != "UPLOAD_BY_FILE":
            raise ValueError(f"{label} file_path requires upload_type=UPLOAD_BY_FILE")
        if asset_url and value != "UPLOAD_BY_URL":
            raise ValueError(f"{label} url requires upload_type=UPLOAD_BY_URL")
        if asset_id and value not in {"UPLOAD_BY_FILE_ID", "UPLOAD_BY_VIDEO_ID"}:
            raise ValueError(f"{label} asset_id requires a file/video ID upload type")
        return value

    def upload_image(
        self,
        advertiser_id: str,
        file_path: Optional[str] = None,
        image_url: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
        upload_type: Optional[str] = None,
    ) -> dict:
        """Upload an image to TikTok's advertiser Asset Library.

        The endpoint accepts a local multipart file, a provider-reachable URL,
        or an existing file repository ID.  The returned image ID is the only
        value that downstream ad creation needs; raw file bytes never enter a
        Tool result or persisted Runtime state.
        """
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        upload_kind = self._media_upload_type(
            upload_type, file_path, image_url, file_id, "image"
        )
        if file_id and upload_kind != "UPLOAD_BY_FILE_ID":
            raise ValueError("file_id requires upload_type=UPLOAD_BY_FILE_ID")
        path = None
        if file_path:
            path = self._validate_media_file(
                file_path, {".jpg", ".jpeg", ".png", ".webp"}, "image"
            )
        name = self._media_upload_name(file_name, path, "image") if (file_name or path) else None
        form_data: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "upload_type": upload_kind,
        }
        files = None
        if path:
            form_data["file_name"] = name
            form_data["image_signature"] = self._media_file_signature(path)
            stream = path.open("rb")
            files = {"image_file": (name, stream, "application/octet-stream")}
        elif image_url:
            form_data["image_url"] = str(image_url).strip()
            if name:
                form_data["file_name"] = name
        else:
            form_data["file_id"] = str(file_id).strip()
            if name:
                form_data["file_name"] = name
        self.acquire_rate_limit(self._rate_limiter)
        try:
            result = self.request("POST", "file/image/ad/upload/", data=form_data, files=files)
        finally:
            if files:
                files["image_file"][1].close()
        payload = self._data_section(result)
        if not isinstance(payload, dict):
            raise APIError("TikTok image upload returned an invalid response envelope")
        image_id = payload.get("image_id") or payload.get("id")
        if not image_id:
            raise APIError("TikTok image upload returned no image_id")
        return {"image_id": str(image_id), "asset": payload}

    def upload_video(
        self,
        advertiser_id: str,
        file_path: Optional[str] = None,
        video_url: Optional[str] = None,
        video_id: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None,
        upload_type: Optional[str] = None,
        flaw_detect: Optional[bool] = None,
        auto_fix_enabled: Optional[bool] = None,
        auto_bind_enabled: Optional[bool] = None,
        is_third_party: Optional[bool] = None,
    ) -> dict:
        """Upload or bind a video in TikTok's advertiser Asset Library."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if video_id and file_id:
            raise ValueError("video upload accepts only one of video_id or file_id")
        asset_id = video_id or file_id
        upload_kind = self._media_upload_type(
            upload_type, file_path, video_url, asset_id, "video"
        )
        if video_id and upload_kind != "UPLOAD_BY_VIDEO_ID":
            raise ValueError("video_id requires upload_type=UPLOAD_BY_VIDEO_ID")
        if file_id and upload_kind != "UPLOAD_BY_FILE_ID":
            raise ValueError("file_id requires upload_type=UPLOAD_BY_FILE_ID")
        path = None
        if file_path:
            path = self._validate_media_file(
                file_path, {".mp4", ".mov", ".m4v", ".avi", ".webm"}, "video"
            )
        name = self._media_upload_name(file_name, path, "video") if (file_name or path) else None
        form_data: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "upload_type": upload_kind,
        }
        for key, value in (
            ("flaw_detect", flaw_detect), ("auto_fix_enabled", auto_fix_enabled),
            ("auto_bind_enabled", auto_bind_enabled), ("is_third_party", is_third_party),
        ):
            if value is not None:
                form_data[key] = value
        files = None
        if path:
            form_data["file_name"] = name
            form_data["video_signature"] = self._media_file_signature(path)
            stream = path.open("rb")
            files = {"video_file": (name, stream, "application/octet-stream")}
        elif video_url:
            form_data["video_url"] = str(video_url).strip()
            if name:
                form_data["file_name"] = name
        elif video_id:
            form_data["video_id"] = str(video_id).strip()
        else:
            form_data["file_id"] = str(file_id).strip()
        self.acquire_rate_limit(self._rate_limiter)
        try:
            result = self.request("POST", "file/video/ad/upload/", data=form_data, files=files)
        finally:
            if files:
                files["video_file"][1].close()
        payload = self._data_section(result)
        if not isinstance(payload, dict):
            raise APIError("TikTok video upload returned an invalid response envelope")
        result_video_id = payload.get("video_id") or payload.get("id")
        if not result_video_id:
            raise APIError("TikTok video upload returned no video_id")
        return {"video_id": str(result_video_id), "asset": payload}
    
    # ==================== 转化追踪查询 ====================
    
    def list_conversions(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取转化事件列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        result = self.request('GET', 'conversion/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def get_conversion(self, advertiser_id: str, conversion_id: str) -> dict:
        """获取转化事件详情"""
        filtering = [{'field': 'CONVERSION_IDS', 'operator': 'IN', 'values': [int(conversion_id)]}]
        result = self.list_conversions(advertiser_id, filtering=filtering)
        return result[0] if result else {}

    # ==================== Pixel 管理 ====================

    def list_pixels(
        self, advertiser_id: str, pixel_ids: list[str] = None, page_size: int = 20
    ) -> list:
        """List TikTok Pixels for an advertiser."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id:
            raise ValueError("advertiser_id must not be empty")
        if pixel_ids is not None:
            if not isinstance(pixel_ids, list) or not pixel_ids:
                raise ValueError("pixel_ids must be a non-empty list when provided")
            pixel_ids = [str(value or "").strip() for value in pixel_ids]
            if any(not value for value in pixel_ids):
                raise ValueError("pixel_ids must contain non-empty values")
        data = {"advertiser_id": advertiser_id, "page_size": page_size}
        if pixel_ids:
            data["pixel_ids"] = pixel_ids
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("GET", "pixel/get/", params=data)
        payload = self._data_section(result)
        if not isinstance(payload, dict):
            return []
        return payload.get("list", []) if isinstance(payload.get("list"), list) else []

    def get_pixel(self, advertiser_id: str, pixel_id: str) -> dict:
        """Get one TikTok Pixel and keep the advertiser scope explicit."""
        pixel_id = str(pixel_id or "").strip()
        if not pixel_id:
            raise ValueError("pixel_id must not be empty")
        pixels = self.list_pixels(advertiser_id, pixel_ids=[pixel_id], page_size=1)
        return next(
            (item for item in pixels if isinstance(item, dict) and str(
                item.get("pixel_id") or item.get("id") or item.get("code")
            ) == pixel_id),
            {},
        )

    def create_pixel(self, advertiser_id: str, pixel: dict) -> str:
        """Create a TikTok Website or App Pixel."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id:
            raise ValueError("advertiser_id must not be empty")
        if not isinstance(pixel, dict):
            raise ValueError("pixel must be an object")
        allowed = {"name", "object_type", "tracking_url"}
        unknown = sorted(set(pixel) - allowed)
        if unknown:
            raise ValueError(f"unsupported pixel fields: {', '.join(unknown)}")
        name = str(pixel.get("name") or "").strip()
        object_type = str(pixel.get("object_type") or "").strip().upper()
        if not name or object_type not in {"WEBSITE", "APP"}:
            raise ValueError("pixel name and object_type=WEBSITE or APP are required")
        data = {
            "advertiser_id": advertiser_id,
            "name": name,
            "object_type": object_type,
        }
        if pixel.get("tracking_url") is not None:
            tracking_url = str(pixel["tracking_url"]).strip()
            if not tracking_url:
                raise ValueError("tracking_url must not be empty when provided")
            data["tracking_url"] = tracking_url
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "pixel/create/", data=data)
        payload = self._data_section(result)
        pixel_id = payload.get("pixel_id") or payload.get("id") if isinstance(payload, dict) else None
        return self.require_resource_id(pixel_id, "TikTok pixel create")

    def update_pixel(self, advertiser_id: str, pixel_id: str, updates: dict) -> dict:
        """Update the Pixel name supported by TikTok's Pixel update edge."""
        advertiser_id = str(advertiser_id or "").strip()
        pixel_id = str(pixel_id or "").strip()
        if not advertiser_id or not pixel_id:
            raise ValueError("advertiser_id and pixel_id must not be empty")
        if not self.get_pixel(advertiser_id, pixel_id):
            raise PermissionError(
                f"TikTok pixel {pixel_id} does not belong to advertiser {advertiser_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = sorted(set(updates) - {"name"})
        if unknown:
            raise ValueError(f"unsupported pixel update fields: {', '.join(unknown)}")
        name = str(updates.get("name") or "").strip()
        if not name:
            raise ValueError("pixel update name must not be empty")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "pixel/update/", data={
            "advertiser_id": advertiser_id,
            "pixel_id": pixel_id,
            "name": name,
        })
        return {"success": True, "pixel_id": pixel_id, "result": result}

    # ==================== Pixel 事件发送 ====================

    @staticmethod
    def _validate_pixel_code(pixel_id: str) -> str:
        pixel_code = str(pixel_id or "").strip()
        if not pixel_code:
            raise ValueError("pixel_id must not be empty")
        return pixel_code

    @staticmethod
    def _validate_pixel_event(event: dict) -> dict:
        if not isinstance(event, dict):
            raise ValueError("pixel event must be an object")
        event_name = str(event.get("event") or "").strip()
        if not event_name:
            raise ValueError("pixel event requires event")
        normalized = dict(event)
        normalized["event"] = event_name
        for field in ("context", "properties"):
            if field in normalized and normalized[field] is not None and not isinstance(normalized[field], dict):
                raise ValueError(f"pixel event {field} must be an object")
        if "timestamp" in normalized and normalized["timestamp"] is not None:
            if not isinstance(normalized["timestamp"], str) or not normalized["timestamp"].strip():
                raise ValueError("pixel event timestamp must be a non-empty ISO 8601 string")
        return normalized

    def send_pixel_event(self, advertiser_id: str, pixel_id: str, event: dict) -> dict:
        """Send one event through TikTok's v1.3 Pixel Track endpoint."""
        # ``advertiser_id`` scopes the Tool request and rate-limit accounting;
        # TikTok's Pixel Track body itself is keyed by pixel_code.
        if not str(advertiser_id or "").strip():
            raise ValueError("advertiser_id must not be empty")
        pixel_code = self._validate_pixel_code(pixel_id)
        payload = self._validate_pixel_event(event)
        payload["pixel_code"] = pixel_code
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "pixel/track/", data=payload)
        return result if isinstance(result, dict) else {"result": result}

    def send_pixel_events(self, advertiser_id: str, pixel_id: str, events: list[dict]) -> dict:
        """Send a batch through TikTok's v1.3 Pixel Batch endpoint."""
        if not str(advertiser_id or "").strip():
            raise ValueError("advertiser_id must not be empty")
        if not isinstance(events, list) or not events:
            raise ValueError("events must be a non-empty list")
        if len(events) > 50:
            raise ValueError("events must contain at most 50 items")
        pixel_code = self._validate_pixel_code(pixel_id)
        batch = []
        for event in events:
            normalized = self._validate_pixel_event(event)
            normalized["type"] = "track"
            batch.append(normalized)
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "POST", "pixel/batch/", data={"pixel_code": pixel_code, "batch": batch}
        )
        return result if isinstance(result, dict) else {"result": result}

    def create_creative_portfolio(
        self,
        advertiser_id: str,
        creative_portfolio_type: str = "CTA",
        portfolio_content: list[dict] = None,
    ) -> dict:
        """Create a TikTok v1.3 Creative Portfolio."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id:
            raise ValueError("advertiser_id must not be empty")
        portfolio_type = str(creative_portfolio_type or "CTA").strip().upper()
        allowed_types = {
            "CTA", "CARD", "PREMIUM_BADGE", "STICKER", "DOWNLOAD_CARD", "PRODUCT_CARD",
        }
        if portfolio_type not in allowed_types:
            raise ValueError(f"creative_portfolio_type must be one of {sorted(allowed_types)}")
        if portfolio_content is not None:
            if not isinstance(portfolio_content, list) or not portfolio_content:
                raise ValueError("portfolio_content must be a non-empty list when provided")
            if len(portfolio_content) > 100 or any(not isinstance(item, dict) for item in portfolio_content):
                raise ValueError("portfolio_content must contain at most 100 objects")
        data = {
            "advertiser_id": advertiser_id,
            "creative_portfolio_type": portfolio_type,
        }
        if portfolio_content is not None:
            data["portfolio_content"] = portfolio_content
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "creative/portfolio/create/", data=data)
        return result if isinstance(result, dict) else {"result": result}

    def get_creative_portfolio(
        self, advertiser_id: str, creative_portfolio_id: str
    ) -> dict:
        """Get a TikTok v1.3 Creative Portfolio by advertiser scope."""
        advertiser_id = str(advertiser_id or "").strip()
        creative_portfolio_id = str(creative_portfolio_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if not creative_portfolio_id:
            raise ValueError("creative_portfolio_id is required")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "POST", "creative/portfolio/get/", data={
                "advertiser_id": advertiser_id,
                "creative_portfolio_id": creative_portfolio_id,
            },
        )
        return self.require_resource_object(
            result if isinstance(result, dict) else {},
            "TikTok creative portfolio get",
        )

    def preview_creative_portfolio(
        self,
        advertiser_id: str,
        creative_portfolio_id: str,
        preview_type: str = "CARD",
    ) -> dict:
        """Create a TikTok Creative Portfolio preview link/iframe."""
        advertiser_id = str(advertiser_id or "").strip()
        creative_portfolio_id = str(creative_portfolio_id or "").strip()
        preview_type = str(preview_type or "CARD").strip().upper()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if not creative_portfolio_id:
            raise ValueError("creative_portfolio_id is required")
        if preview_type != "CARD":
            raise ValueError("preview_type must be CARD")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request(
            "POST", "creative/ads_preview/create/", data={
                "advertiser_id": advertiser_id,
                "preview_type": preview_type,
                "card_id": creative_portfolio_id,
            },
        )
        return result if isinstance(result, dict) else {"result": result}

    # ==================== Identity 管理 ====================

    def create_identity(self, advertiser_id: str, display_name: str, image_uri: str) -> dict:
        """Create a TikTok customized user identity."""
        advertiser_id = str(advertiser_id or "").strip()
        display_name = str(display_name or "").strip()
        image_uri = str(image_uri or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if not display_name or len(display_name) > 100:
            raise ValueError("display_name must be between 1 and 100 characters")
        if not image_uri:
            raise ValueError("image_uri is required")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("POST", "identity/create/", data={
            "advertiser_id": advertiser_id,
            "display_name": display_name,
            "image_uri": image_uri,
        })
        return result if isinstance(result, dict) else {"result": result}

    def list_identities(
        self,
        advertiser_id: str,
        identity_type: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list:
        """List advertiser identities supported by the safe Tool contract."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if identity_type is not None and str(identity_type).upper() not in {
            "CUSTOMIZED_USER", "AUTH_CODE", "TT_USER",
        }:
            raise ValueError("unsupported identity_type")
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("page must be positive and page_size must be between 1 and 100") from exc
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("page must be positive and page_size must be between 1 and 100")
        params: dict[str, Any] = {
            "advertiser_id": advertiser_id, "page": page, "page_size": page_size,
        }
        if identity_type:
            params["identity_type"] = str(identity_type).upper()
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("GET", "identity/get/", params=params)
        payload = self._data_section(result)
        if isinstance(payload, list):
            return payload
        return payload.get("list", payload.get("identities", [])) if isinstance(payload, dict) else []

    def get_identity(self, advertiser_id: str, identity_id: str) -> dict:
        """Get one advertiser identity through the existing identity/get endpoint."""
        advertiser_id = str(advertiser_id or "").strip()
        identity_id = str(identity_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if not identity_id:
            raise ValueError("identity_id is required")
        identities = self.list_identities(advertiser_id, page_size=100)
        return next(
            (
                item for item in identities
                if isinstance(item, dict)
                and str(item.get("identity_id") or item.get("id") or "") == identity_id
            ),
            {},
        )

    def get_identity_video_info(
        self, advertiser_id: str, identity_type: str, identity_id: str, item_id: str
    ) -> dict:
        """Get owned TikTok post information for an AUTH_CODE or TT_USER identity."""
        advertiser_id = str(advertiser_id or "").strip()
        identity_type = str(identity_type or "").strip().upper()
        identity_id = str(identity_id or "").strip()
        item_id = str(item_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if identity_type not in {"AUTH_CODE", "TT_USER"}:
            raise ValueError("identity_type must be AUTH_CODE or TT_USER")
        if not identity_id or not item_id:
            raise ValueError("identity_id and item_id are required")
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request("GET", "identity/video/info/", params={
            "advertiser_id": advertiser_id,
            "identity_type": identity_type,
            "identity_id": identity_id,
            "item_id": item_id,
        })
        return result if isinstance(result, dict) else {"result": result}
    
    # ==================== 商品目录查询 ====================

    @staticmethod
    def _validate_catalog_query(
        advertiser_id: str,
        filtering: Optional[list],
        page_size: int,
    ) -> tuple[str, Optional[list], int]:
        """Validate the shared v1.3 Catalog/Product Set query contract."""
        advertiser_id = str(advertiser_id or "").strip()
        if not advertiser_id.isdigit():
            raise ValueError("advertiser_id must contain digits only")
        if filtering is not None and not isinstance(filtering, list):
            raise ValueError("filtering must be an array when provided")
        try:
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("page_size must be between 1 and 100") from exc
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        return advertiser_id, filtering, page_size
    
    def list_catalogs(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """List TikTok Catalogs through the official v1.3 read endpoint."""
        advertiser_id, filtering, page_size = self._validate_catalog_query(
            advertiser_id, filtering, page_size
        )
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': advertiser_id,
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        result = self.request('GET', 'catalog/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []

    def get_catalog(self, advertiser_id: str, catalog_id: str) -> dict:
        """Get one Catalog through the existing catalog/get endpoint."""
        catalog_id = str(catalog_id or "").strip()
        if not catalog_id:
            raise ValueError("catalog_id must not be empty")
        catalogs = self.list_catalogs(
            advertiser_id,
            filtering=[{
                "field": "CATALOG_IDS",
                "operator": "IN",
                "values": [catalog_id],
            }],
            page_size=1,
        )
        return next(
            (
                item for item in catalogs
                if isinstance(item, dict)
                and str(item.get("catalog_id") or item.get("id") or "") == catalog_id
            ),
            {},
        )
    
    def list_product_sets(self, advertiser_id: str, catalog_id: str = None, filtering: list = None, page_size: int = 20) -> list:
        """List TikTok Product Sets through the official v1.3 read endpoint."""
        advertiser_id, filtering, page_size = self._validate_catalog_query(
            advertiser_id, filtering, page_size
        )
        if catalog_id is not None and not str(catalog_id).strip():
            raise ValueError("catalog_id must not be empty when provided")
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': advertiser_id,
            'page_size': page_size,
        }
        if catalog_id:
            data['catalog_id'] = str(catalog_id)
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        result = self.request('GET', 'product_set/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []

    def get_product_set(
        self, advertiser_id: str, catalog_id: str, product_set_id: str
    ) -> dict:
        """Get one Product Set through the existing product_set/get endpoint."""
        product_set_id = str(product_set_id or "").strip()
        if not product_set_id:
            raise ValueError("product_set_id must not be empty")
        product_sets = self.list_product_sets(
            advertiser_id,
            catalog_id=catalog_id,
            filtering=[{
                "field": "PRODUCT_SET_IDS",
                "operator": "IN",
                "values": [product_set_id],
            }],
            page_size=1,
        )
        return next(
            (
                item for item in product_sets
                if isinstance(item, dict)
                and str(
                    item.get("product_set_id") or item.get("id") or ""
                ) == product_set_id
            ),
            {},
        )

    def validate_product_selection(
        self, advertiser_id: str, catalog_id: str, product_set_id: str
    ) -> dict:
        """Validate that a product set reference belongs to a catalog.

        TikTok does not expose a separate feed-validation endpoint in the
        currently supported API contract.  This read operation verifies the
        strongest check available without inventing one: the product set is
        returned by ``product_set/get`` for the supplied catalog.
        """
        catalog_id = str(catalog_id or "").strip()
        product_set_id = str(product_set_id or "").strip()
        if not catalog_id or not product_set_id:
            raise ValueError("catalog_id and product_set_id are required")
        product_sets = self.list_product_sets(advertiser_id, catalog_id=catalog_id)
        match = next(
            (
                item for item in product_sets
                if str(item.get("product_set_id") or item.get("id") or "") == product_set_id
            ),
            None,
        )
        return {
            "valid": match is not None,
            "catalog_id": catalog_id,
            "product_set_id": product_set_id,
            "product_set": match,
            "checked_via": "product_set/get",
        }
    
    # ==================== 应用信息查询 ====================
    
    def list_apps(self, filtering: list = None, page_size: int = 20) -> list:
        """获取应用列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {'page_size': page_size}
        if filtering:
            data['filtering'] = self._encode_filtering(filtering)
        result = self.request('GET', 'app/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    # ==================== 品牌安全查询 ====================
    
    def list_brand_safety(self) -> list:
        """获取品牌安全类别列表"""
        self.acquire_rate_limit(self._rate_limiter)
        result = self.request('GET', 'brand_safety/get/')
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    # ==================== 统计报告查询 ====================
    
    def get_report(self, advertiser_id: str, report_type: str = 'CAMPAIGN', date_preset: str = 'LAST_7_DAYS', time_range: dict = None) -> dict:
        """获取统计报告"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'report_type': report_type,
            'date_preset': date_preset,
        }
        if time_range:
            data['time_range'] = self._normalize_time_range(time_range)
        # BasePlatformClient transports JSON request bodies through ``data``.
        # Passing ``json=`` here silently produced an empty body in the
        # provider adapter.
        result = self.request('POST', 'statistics/get/', data=data)
        payload = self._data_section(result)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _normalize_time_range(time_range: Any) -> dict:
        """Convert supported report presets into TikTok's ISO date shape."""
        if isinstance(time_range, dict):
            start_value = time_range.get("start_date")
            end_value = time_range.get("end_date")
            preset_values = {"TODAY", "YESTERDAY", "THIS_MONTH"}
            if isinstance(start_value, str):
                start_upper = start_value.upper()
                if start_upper in preset_values or re.fullmatch(
                    r"LAST_(\d+)_DAYS", start_upper
                ):
                    normalized = TikTokAPIClient._normalize_time_range(start_upper)
                    if isinstance(end_value, str) and re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}", end_value
                    ):
                        normalized["end_date"] = end_value
                    return normalized
            if isinstance(end_value, str) and end_value.upper() in preset_values:
                normalized_end = date.today()
                if end_value.upper() == "YESTERDAY":
                    normalized_end -= timedelta(days=1)
                elif end_value.upper() == "THIS_MONTH":
                    normalized_end = normalized_end.replace(day=1)
                result = dict(time_range)
                result["end_date"] = normalized_end.isoformat()
                return result
            return dict(time_range)
        if time_range in (None, ""):
            time_range = "LAST_7_DAYS"
        preset = str(time_range).upper()
        end = date.today()
        if preset == "TODAY":
            start = end
        elif preset == "YESTERDAY":
            start = end = end - timedelta(days=1)
        elif preset == "THIS_MONTH":
            start = end.replace(day=1)
        else:
            match = re.fullmatch(r"LAST_(\d+)_DAYS", preset)
            if not match:
                raise ValueError(
                    "TikTok report time_range must be an object or a supported date preset"
                )
            days = max(int(match.group(1)), 1)
            start = end - timedelta(days=days - 1)
        return {"start_date": start.isoformat(), "end_date": end.isoformat()}
