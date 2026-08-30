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
    
    # ==================== Campaign 管理 ====================
    
    def list_campaigns(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取 Campaign 列表"""
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        return self._list_pages('campaign/get/', data)
    
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
        - daily_budget: 每日预算（账户货币；发送给 API 时转换为分）
        - app_promotion_type: APP 推广类型 (APP_RETARGETING, APP_ACQUISITION)
        """
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_name': campaign.get('name', 'Untitled Campaign'),
            'objective_type': campaign.get('objective_type', 'TRAFFIC'),
            'campaign_automation_type': campaign.get('campaign_automation_type', 'MANUAL'),
            'campaign_group_status': campaign.get('status', 1),
            'budget_restriction': campaign.get('budget_restriction', 'NO_LIMITATION'),
            'budget_mode': campaign.get('budget_mode', 'BUDGET_MODE_INFINITE'),
            'campaign_type': campaign.get('campaign_type', 'REGULAR_CAMPAIGN'),
        }
        # 预算输入使用账户货币、API 使用分。预算模式决定发送日预算
        # 还是总预算，避免把 ``budget`` 原样透传后由服务端猜单位。
        budget_mode = campaign.get('budget_mode')
        if campaign.get('daily_budget') is not None:
            data['daily_budget'] = int(float(campaign['daily_budget']) * 100)
        elif budget_mode == 'BUDGET_MODE_TOTAL' and campaign.get('budget') is not None:
            data['budget'] = int(float(campaign['budget']) * 100)
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
            normalized_updates['daily_budget'] = int(float(daily_budget) * 100)
        elif budget is not None:
            normalized_updates['budget'] = int(float(budget) * 100)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'campaign': normalized_updates,
        }
        return self.request('POST', 'campaign/update/', data=data)
    
    def pause_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """暂停 Campaign"""
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 0})
    
    def resume_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """恢复 Campaign"""
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 1})
    
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
            'campaign_id': int(campaign_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        return self._list_pages('adgroup/get/', data)
    
    def get_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str) -> dict:
        """获取 Ad Group 详情"""
        # TikTok API 不支持 filtering，直接查询所有 adgroup 并过滤
        result = self.list_adgroups(advertiser_id, campaign_id)
        for ag in result:
            if str(ag.get('adgroup_id')) == str(adgroup_id):
                return ag
        raise APIError(f"TikTok ad group {adgroup_id} was not found")
    
    def create_adgroup(self, advertiser_id: str, campaign_id: str, adgroup: dict) -> str:
        """创建 Ad Group"""
        self.acquire_rate_limit(self._rate_limiter)
        budget_mode = adgroup.get('budget_mode')
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group': {
                'ad_group_name': adgroup['name'],
                'ad_group_status': adgroup.get('status', 1),
                'tracking_url': adgroup.get('tracking_url', ''),
                'bid_amount': int(adgroup.get('bid_amount', 500)),  # 单位为分
            }
        }
        daily_budget = adgroup.get('daily_budget')
        budget = adgroup.get('budget')
        if daily_budget is not None:
            data['ad_group']['daily_budget'] = int(float(daily_budget) * 100)
        elif budget is not None and budget_mode != 'BUDGET_MODE_INFINITE':
            data['ad_group']['budget'] = int(float(budget) * 100)
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
        ):
            if key in adgroup and adgroup[key] not in (None, ''):
                data['ad_group'][key] = adgroup[key]
        # 定向
        if adgroup.get('targeting'):
            data['ad_group']['targeting'] = adgroup['targeting']
        
        result = self.request('POST', 'adgroup/create/', data=data)
        payload = self._data_section(result)
        resource_id = payload.get('ad_group_id') if isinstance(payload, dict) else None
        return self.require_resource_id(resource_id, "TikTok ad group create")
    
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
            'campaign_id': int(campaign_id),
            'ad_group_id': int(adgroup_id),
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
            'ad_group_id': int(adgroup_id),
            'page_size': page_size,
        }
        return self._list_pages('ad/get/', data)
    
    def get_ad(self, advertiser_id: str, adgroup_id: str, ad_id: str) -> dict:
        """获取 Ad 详情"""
        # TikTok API 不支持 filtering，直接查询所有 ad 并过滤
        result = self.list_ads(advertiser_id, adgroup_id)
        for ad in result:
            if str(ad.get('ad_id')) == str(ad_id):
                return ad
        raise APIError(f"TikTok ad {ad_id} was not found")
    
    def create_ad(self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict) -> str:
        """创建 Ad"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group_id': int(adgroup_id),
            'ad': {
                'ad_name': ad.get('name', 'Untitled Ad'),
                'ad_status': ad.get('status', 1),
                'landing_page_url': ad.get('landing_page_url', ''),
                'conversion_id': ad.get('conversion_id', 0),
            }
        }
        # 素材
        if ad.get('media'):
            data['ad']['media'] = ad['media']
        if ad.get('creatives'):
            data['ad']['creatives'] = ad['creatives']
        if ad.get('text'):
            data['ad']['text'] = ad['text']
        # Keep every field declared by the provider-owned ad contracts.  The
        # generic adapter remains useful for formats without a dedicated
        # builder, but it must not silently discard a valid provider field.
        for key in (
            'ad_format', 'status', 'video_id', 'image_ids', 'spark_post_id',
            'page_id', 'tracking_pixel_id', 'operation_status', 'creative_type',
            'display_name', 'catalog_id', 'product_set_id', 'call_to_action',
            'identity_id', 'promotion_type', 'app_id', 'app_promotion_type',
            'operating_systems', 'deep_link', 'tracking_url', 'promote_object', 'ad_text_settings',
            'brand_safety', 'run_time_settings',
        ):
            if key in ad and ad[key] not in (None, ''):
                data['ad'][key] = ad[key]
        
        result = self.request('POST', 'ad/create/', data=data)
        payload = self._data_section(result)
        resource_id = payload.get('ad_id') if isinstance(payload, dict) else None
        return self.require_resource_id(resource_id, "TikTok ad create")

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
    
    def list_interest_categories(self, parent_ids: list = None) -> list:
        """获取兴趣类别列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {}
        if parent_ids:
            data['parent_ids'] = parent_ids
        result = self.request('GET', 'interest_category/list/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
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
            'placements': placements,
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
            return payload.get('list', payload.get('regions', payload.get('locations', [])))
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
            data['filtering'] = filtering
        result = self.request('GET', 'creative/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_videos(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取视频列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'video/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_images(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取图片列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'image/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []

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
            data['filtering'] = filtering
        result = self.request('GET', 'conversion/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def get_conversion(self, advertiser_id: str, conversion_id: str) -> dict:
        """获取转化事件详情"""
        filtering = [{'field': 'CONVERSION_IDS', 'operator': 'IN', 'values': [int(conversion_id)]}]
        result = self.list_conversions(advertiser_id, filtering=filtering)
        return result[0] if result else {}

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
    
    # ==================== 商品目录查询 ====================
    
    def list_catalogs(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取商品目录列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'catalog/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    def list_product_sets(self, advertiser_id: str, catalog_id: str = None, filtering: list = None, page_size: int = 20) -> list:
        """获取商品集列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if catalog_id:
            data['catalog_id'] = str(catalog_id)
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'product_set/get/', params=data)
        payload = self._data_section(result)
        return payload.get('list', []) if isinstance(payload, dict) else []
    
    # ==================== 应用信息查询 ====================
    
    def list_apps(self, filtering: list = None, page_size: int = 20) -> list:
        """获取应用列表"""
        self.acquire_rate_limit(self._rate_limiter)
        data = {'page_size': page_size}
        if filtering:
            data['filtering'] = filtering
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
