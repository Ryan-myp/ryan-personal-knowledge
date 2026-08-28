"""
api_clients/google_ads_client.py - Google Ads API 生产级客户端（HTTP 直调版）

绕过 google-ads SDK（有架构兼容问题），直接用 REST API。
认证: Bearer Token + Developer Token + Login Customer ID

层级结构:
Customer → Campaign → AdGroup → Ad
"""

import logging
import time
import json
import copy
import re
import threading
from typing import Any, Optional
from datetime import datetime
import requests

from .base import BasePlatformClient, APIError, AuthError, RateLimitError, TemporaryError, RetryConfig, RateLimiter

logger = logging.getLogger(__name__)


class GoogleAdsAPIClient(BasePlatformClient):
    """
    Google Ads API 客户端（HTTP 直调，v24）
    
    官方文档: https://developers.google.com/google-ads/api/docs/start
    认证: OAuth2 Access Token + Developer Token
    
    速率限制: 10,000 CUPM（Customer Units Per Minute）
    """
    
    API_VERSION = "v24"
    SUPPORTED_API_VERSIONS = (API_VERSION,)
    BASE_URL = f"https://googleads.googleapis.com/{API_VERSION}"
    DATE_LITERALS = {
        "TODAY", "YESTERDAY", "LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS",
        "THIS_MONTH", "LAST_MONTH", "THIS_WEEK_SUN_TODAY", "THIS_WEEK_MON_TODAY",
    }
    CAMPAIGN_UPDATE_FIELDS = {"name", "status", "daily_budget", "budget"}
    AD_GROUP_UPDATE_FIELDS = {
        "name", "status", "type", "cpc_bid", "cpc_bid_micros",
    }
    # Google Ads treats most ad payload fields as immutable after creation.
    # Keep the live adapter deliberately narrow; the ToolSchema can still
    # preview richer creative changes until a dedicated asset mutation is
    # verified.
    AD_UPDATE_FIELDS = {"status"}
    ASSET_GROUP_UPDATE_FIELDS = {"name", "status"}
    
    def __init__(
        self,
        credentials: dict,
        customer_id: str = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "google", retry_config)
        self.api_version = self._resolve_api_version(
            self.credentials.get("api_version")
        )
        self.base_url = f"https://googleads.googleapis.com/{self.api_version}"
        # Keep the existing endpoint builders version-aware while preserving
        # the public class constant used by older integrations.
        self.BASE_URL = self.base_url
        self.customer_id = customer_id or self.credentials.get('customer_id', '')
        self.developer_token = self.credentials.get('developer_token', '')
        self.login_customer_id = self.credentials.get('login_customer_id', self.customer_id)
        self._rate_limiter = RateLimiter(max_requests=1000, period=60)  # 保守限流
        # Token state is deliberately kept outside credentials.  A supplied
        # access token without an expiry is treated as caller-managed and is
        # usable until the API rejects it; refresh is only attempted when an
        # explicit expiry says it is stale or no access token exists.
        self._access_token = self.credentials.get('access_token', '')
        self._token_expiry = self.credentials.get('access_token_expires_at', 0) or 0
        self._token_lock = threading.RLock()

    @classmethod
    def _resolve_api_version(cls, requested: Any = None) -> str:
        version = str(requested or cls.API_VERSION).strip()
        if version not in cls.SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported Google Ads API version {version!r}; "
                f"supported versions: {list(cls.SUPPORTED_API_VERSIONS)}"
            )
        return version
    
    def _ensure_valid_token(self) -> str:
        """确保 access_token 有效，过期则自动刷新"""
        with self._token_lock:
            now = time.time()

            # 如果调用方提供了未过期 token，直接使用。没有 expiry 的 token
            # 由调用方管理，避免错误地要求 refresh_token。
            if self._access_token and (
                not self._token_expiry or self._token_expiry > now + 60
            ):
                return self._access_token

            refresh_token = self.credentials.get('refresh_token', '')
            if not refresh_token:
                raise AuthError("No refresh_token available")

            client_id = self.credentials.get('client_id', '')
            client_secret = self.credentials.get('client_secret', '')

            token_url = "https://oauth2.googleapis.com/token"
            resp = requests.post(token_url, data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }, timeout=self.http_timeout())

            if resp.status_code != 200:
                raise AuthError(f"Failed to refresh token: {resp.text}")

            token_info = resp.json()
            self._access_token = token_info['access_token']
            self._token_expiry = now + token_info.get('expires_in', 3600)

            return self._access_token

    def _reset_auth(self) -> bool:
        """Allow one safe read retry only when refresh credentials exist."""
        if not self.credentials.get('refresh_token'):
            return False
        with self._token_lock:
            self._access_token = ''
            self._token_expiry = 0
        return True

    def for_customer(self, customer_id: str) -> "GoogleAdsAPIClient":
        """Return an account-scoped view without mutating this client.

        A Runtime can serve multiple Google customers concurrently.  The old
        handlers changed ``self.customer_id`` for every request, so one
        request could silently run against the account selected by another
        request.  The shallow copy keeps the credential/token and rate-limit
        state shared while isolating the mutable customer selector.
        """
        scoped = copy.copy(self)
        scoped.customer_id = str(customer_id)
        return scoped
    
    def _build_headers(self) -> dict:
        token = self._ensure_valid_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'developer-token': self.developer_token,
            'login-customer-id': self.login_customer_id,
        }

    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        self.acquire_rate_limit(self._rate_limiter)
        
        headers = {**self._build_headers(), **kwargs.pop('headers', {})}
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params'), timeout=self.http_timeout())
            elif method == 'POST':
                resp = requests.post(url, headers=headers, json=kwargs.get('data'), timeout=self.http_timeout())
            elif method == 'PUT':
                resp = requests.put(url, headers=headers, json=kwargs.get('data'), timeout=self.http_timeout())
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, timeout=self.http_timeout())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            try:
                data = resp.json() if resp.content else {}
            except Exception:
                # 响应体为空或非 JSON（如 HTML 错误页）
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
        data = response.get('data', {})
        return data
    
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        data = response.get('data', {})
        
        # 认证错误
        if status_code == 401:
            return AuthError(f"Google Ads: Invalid or expired token (HTTP {status_code})")
        
        # 权限/资源错误
        if status_code == 403:
            error_msg = data.get('error', {}).get('message', 'Permission denied')
            return AuthError(f"Google Ads: {error_msg}")
        
        # 限流
        if status_code == 429:
            return RateLimitError("Google Ads: Rate limited", retry_after=60)
        
        # 临时错误
        if status_code >= 500:
            return TemporaryError(f"Google Ads server error {status_code}")

        # Preserve an HTTP failure even when a proxy returns an empty or
        # non-JSON body. Only 5xx/explicitly retryable errors may be retried.
        if status_code >= 400:
            error_msg = "Bad request"
            if isinstance(data, dict):
                error_msg = data.get('error', {}).get('message', error_msg)
            return APIError(
                f"Google Ads HTTP {status_code}: {error_msg}",
                status_code=status_code,
                response=data if isinstance(data, dict) else None,
            )
        
        # API 业务错误
        if isinstance(data, dict) and 'error' in data:
            err = data['error']
            message = err.get('message', 'Unknown error')
            code = err.get('code', 'UNKNOWN')
            return APIError(f"Google Ads {code}: {message}", status_code=status_code, response=data)
        
        return None
    
    # ==================== Campaign 管理 ====================
    
    def list_campaigns(self, filter_query: str = None, page_size: int = 100) -> list:
        """获取 Campaign 列表"""
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign.advertising_channel_type, campaign.bidding_strategy "
            "FROM campaign"
        )
        if filter_query:
            query += f" WHERE {filter_query}"
        results = self._search_all(query, page_size=page_size)
        # 解析嵌套结构：result['data']['results'][i]['campaign']
        campaigns = []
        for r in results:
            camp = r.get('campaign', {})
            # 标准化字段名
            campaigns.append({
                'id': camp.get('id'),
                'resource_name': camp.get('resourceName'),
                'name': camp.get('name'),
                'status': camp.get('status'),
                'advertising_channel_type': camp.get('advertisingChannelType'),
                'bidding_strategy': camp.get('biddingStrategy'),
            })
        return campaigns
    
    def get_campaign(self, campaign_id: str) -> dict:
        """获取 Campaign 详情"""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type, campaign.bidding_strategy
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """
        results = self._search(query)
        items = self._response_payload(results).get('results', [])
        if items:
            camp = items[0].get('campaign', {})
            return {
                'id': camp.get('id'),
                'resource_name': camp.get('resourceName'),
                'name': camp.get('name'),
                'status': camp.get('status'),
                'advertising_channel_type': camp.get('advertisingChannelType'),
                'bidding_strategy': camp.get('biddingStrategy'),
            }
        raise APIError(f"Google campaign {campaign_id} was not found")
    
    def list_ad_groups(self, campaign_id: str, page_size: int = 100) -> list:
        """获取 Ad Group 列表"""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        query = f"""
            SELECT ad_group.id, ad_group.name, ad_group.status,
                   ad_group.type
            FROM ad_group
            WHERE campaign.id = {campaign_id}
        """
        results = self._search_all(query, page_size=page_size)
        # 解析嵌套结构：result['data']['results'][i]['adGroup']
        ad_groups = []
        for r in results:
            ag = r.get('adGroup', r.get('ad_group', {}))
            ad_groups.append({
                'id': ag.get('id'),
                'resource_name': ag.get('resourceName'),
                'name': ag.get('name'),
                'status': ag.get('status'),
                'type': ag.get('type'),
            })
        return ad_groups
    
    def get_ad_group(self, ad_group_id: str) -> dict:
        """获取 Ad Group 详情"""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        query = f"""
            SELECT ad_group.id, ad_group.name, ad_group.status,
                   ad_group.type
            FROM ad_group
            WHERE ad_group.id = {ad_group_id}
        """
        results = self._search(query)
        items = self._response_payload(results).get('results', [])
        if items:
            ag = items[0].get('adGroup', {})
            return {
                'id': ag.get('id'),
                'resource_name': ag.get('resourceName'),
                'name': ag.get('name'),
                'status': ag.get('status'),
                'type': ag.get('type'),
            }
        raise APIError(f"Google ad group {ad_group_id} was not found")
    
    def list_ads(self, ad_group_id: str, page_size: int = 100) -> list:
        """获取 Ad 列表"""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        # Google Ads GAQL 需要使用 ad.ad_group 资源名
        query = f"""
            SELECT ad.id, ad.name, ad.status
            FROM ad
            WHERE ad.ad_group = 'customers/{self.customer_id}/adGroups/{ad_group_id}'
        """
        results = self._search_all(query, page_size=page_size)
        # 解析嵌套结构：result['data']['results'][i]['ad']
        ads = []
        for r in results:
            ad = r.get('ad', {})
            ads.append({
                'id': ad.get('id'),
                'resource_name': ad.get('resourceName'),
                'name': ad.get('name'),
                'status': ad.get('status'),
            })
        return ads

    def list_keywords(
        self,
        campaign_id: str = None,
        ad_group_id: str = None,
        page_size: int = 100,
    ) -> list:
        """List keyword criteria with optional Campaign/Ad Group filters."""
        query = (
            "SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id, "
            "ad_group_criterion.status, ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type "
            "FROM ad_group_criterion "
            "WHERE ad_group_criterion.type = KEYWORD"
        )
        if campaign_id is not None:
            query += f" AND campaign.id = {self._numeric_id(campaign_id, 'campaign_id')}"
        if ad_group_id is not None:
            query += f" AND ad_group.id = {self._numeric_id(ad_group_id, 'ad_group_id')}"

        rows = self._search_all(query, page_size=page_size)
        keywords = []
        for row in rows:
            criterion = row.get("adGroupCriterion", row.get("ad_group_criterion", {})) or {}
            keyword = criterion.get("keyword", {}) or {}
            campaign = row.get("campaign", {}) or {}
            ad_group = row.get("adGroup", row.get("ad_group", {})) or {}
            keywords.append({
                "id": criterion.get("criterionId", criterion.get("criterion_id")),
                "campaign_id": campaign.get("id"),
                "ad_group_id": ad_group.get("id"),
                "text": keyword.get("text"),
                "match_type": keyword.get("matchType", keyword.get("match_type")),
                "status": criterion.get("status"),
            })
        return keywords
    
    def get_ad(self, ad_id: str) -> dict:
        """获取 Ad 详情"""
        ad_id = self._numeric_id(ad_id, "ad_id")
        query = f"""
            SELECT ad.id, ad.name, ad.status
            FROM ad
            WHERE ad.id = {ad_id}
        """
        results = self._search(query)
        items = self._response_payload(results).get('results', [])
        if items:
            ad = items[0].get('ad', {})
            return {
                'id': ad.get('id'),
                'resource_name': ad.get('resourceName'),
                'name': ad.get('name'),
                'status': ad.get('status'),
            }
        raise APIError(f"Google ad {ad_id} was not found")
    
    # ==================== PMax Asset Group 管理 ====================
    
    def list_asset_groups(self, campaign_id: str, page_size: int = 100) -> list:
        """获取 PMax Campaign 的 Asset Group 列表"""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        query = f"""
            SELECT asset_group.id, asset_group.name, asset_group.status
            FROM asset_group
            WHERE campaign.id = {campaign_id}
        """
        results = self._search_all(query, page_size=page_size)
        asset_groups = []
        for r in results:
            ag = r.get('assetGroup', {})
            asset_groups.append({
                'id': ag.get('id'),
                'resource_name': ag.get('resourceName'),
                'name': ag.get('name'),
                'status': ag.get('status'),
            })
        return asset_groups
    
    def get_asset_group(self, asset_group_id: str) -> dict:
        """获取 PMax Asset Group 详情"""
        asset_group_id = self._numeric_id(asset_group_id, "asset_group_id")
        query = f"""
            SELECT asset_group.id, asset_group.name, asset_group.status
            FROM asset_group
            WHERE asset_group.id = {asset_group_id}
        """
        results = self._search(query)
        items = self._response_payload(results).get('results', [])
        if items:
            ag = items[0].get('assetGroup', {})
            return {
                'id': ag.get('id'),
                'resource_name': ag.get('resourceName'),
                'name': ag.get('name'),
                'status': ag.get('status'),
            }
        raise APIError(f"Google asset group {asset_group_id} was not found")
    
    def create_campaign(
        self,
        name: str,
        advertising_channel_type: str,
        bidding_strategy: str,
        daily_budget: float,
        target_cpa_micros: int = None,
        target_roas: float = None,
        target_impression_share: float = None,
        status: str = None,
        networks: list[str] = None,
        app_campaign_setting: dict = None,
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """
        创建 Campaign（需要先创建 CampaignBudget）
        
        advertising_channel_type: SEARCH | SHOPPING | PERFORMANCE_MAX | VIDEO | DISPLAY | APP
        bidding_strategy: MANUAL_CPC | TARGET_CPA | MAXIMIZE_CONVERSIONS | TARGET_ROAS
        """
        try:
            daily_budget = float(daily_budget)
        except (TypeError, ValueError) as exc:
            raise ValueError("daily_budget must be a positive number") from exc
        if daily_budget <= 0:
            raise ValueError("daily_budget must be greater than 0")
        # Google Ads REST writes go through the customer-level mutate
        # endpoints.  Resource-level POST/PUT endpoints look plausible but
        # are not Google Ads API contracts.
        # Step 1: 创建预算
        budget_name = f"Budget for {name}"
        budget_amount_micros = int(daily_budget * 1_000_000)
        budget_data = {
            'name': budget_name,
            'amountMicros': budget_amount_micros,
            'deliveryMethod': 'STANDARD',
            'explicitlyShared': True,
        }
        budget_resp = self._mutate('campaignBudgets', {'create': budget_data})
        budget_resource_name = self._mutation_resource_name(budget_resp)

        # Step 2: 创建 Campaign（初始状态 PAUSED）
        campaign_data = {
            'name': name,
            'advertisingChannelType': advertising_channel_type,
            'status': status or 'PAUSED',
            'campaignBudget': budget_resource_name,
        }

        if start_date:
            campaign_data['startDate'] = start_date
        if end_date:
            campaign_data['endDate'] = end_date
        if networks:
            selected = {str(network).upper() for network in networks}
            campaign_data['networkSettings'] = {
                'targetGoogleSearch': 'GOOGLE_SEARCH' in selected,
                'targetSearchNetwork': 'SEARCH_PARTNERS' in selected,
                'targetContentNetwork': 'DISPLAY_NETWORK' in selected,
            }

        if app_campaign_setting is not None:
            if not isinstance(app_campaign_setting, dict):
                raise ValueError("app_campaign_setting must be an object")
            app_id = app_campaign_setting.get("app_id")
            app_store = app_campaign_setting.get("app_store")
            if not app_id or not app_store:
                raise ValueError("app_campaign_setting requires app_id and app_store")
            campaign_data['appCampaignSetting'] = self._camel_case_keys(
                app_campaign_setting
            )
        
        # 出价策略附加参数
        strategy = (bidding_strategy or 'MAXIMIZE_CONVERSIONS').upper()
        if strategy == 'MANUAL_CPC':
            campaign_data['manualCpc'] = {}
        elif strategy == 'TARGET_CPA':
            campaign_data['targetCpa'] = {
                'targetCpaMicros': (
                    50000000 if target_cpa_micros is None else target_cpa_micros
                ),
            }
        elif strategy == 'TARGET_ROAS':
            campaign_data['targetRoas'] = {
                'targetRoas': 4.0 if target_roas is None else target_roas
            }
        elif strategy == 'MAXIMIZE_CLICKS':
            campaign_data['maximizeClicks'] = {}
        elif strategy == 'MAXIMIZE_CONVERSION_VALUE':
            campaign_data['maximizeConversionValue'] = {}
            if target_roas is not None:
                campaign_data['maximizeConversionValue']['targetRoas'] = target_roas
        elif strategy == 'TARGET_IMPRESSION_SHARE':
            campaign_data['targetImpressionShare'] = {
                'location': 'ANYWHERE_ON_PAGE',
                'locationFractionMicros': int(float(
                    0.5 if target_impression_share is None else target_impression_share
                ) * 1_000_000),
            }
        else:
            campaign_data['maximizeConversions'] = {}

        try:
            campaign_resp = self._mutate('campaigns', {'create': campaign_data})
        except Exception:
            # Budget creation and campaign creation are separate mutate calls.
            # Best-effort cleanup avoids leaving an unreferenced budget behind.
            try:
                self._mutate('campaignBudgets', {'remove': budget_resource_name})
            except Exception:
                logger.exception("Failed to compensate orphaned campaign budget")
            raise

        campaign_resource_name = self._mutation_resource_name(campaign_resp)
        if not campaign_resource_name:
            raise APIError(f"Campaign mutate returned no resource name: {campaign_resp}")
        return str(campaign_resource_name.split('/')[-1])
    
    def update_campaign(self, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign"""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.CAMPAIGN_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported Google Campaign update fields: {sorted(unknown)}")

        resource_name = f"customers/{self.customer_id}/campaigns/{campaign_id}"
        campaign_updates = {
            key: value for key, value in updates.items()
            if key not in {"daily_budget", "budget"}
        }
        if campaign_updates:
            patch_data = {'resourceName': resource_name, **campaign_updates}
            operation = {
                'update': self._camel_case_keys(patch_data),
                'updateMask': {
                    'paths': [self._camel_case(key) for key in campaign_updates],
                },
            }
            self._mutate('campaigns', operation)

        if "daily_budget" in updates or "budget" in updates:
            budget = updates.get("daily_budget", updates.get("budget"))
            try:
                amount_micros = int(float(budget) * 1_000_000)
            except (TypeError, ValueError):
                raise ValueError("daily_budget must be a positive number")
            if amount_micros <= 0:
                raise ValueError("daily_budget must be greater than 0")
            budget_resource = self._get_campaign_budget_resource(campaign_id)
            if not budget_resource:
                raise APIError("Campaign budget resource could not be resolved")
            self._mutate("campaignBudgets", {
                "update": {
                    "resourceName": budget_resource,
                    "amountMicros": amount_micros,
                },
                "updateMask": {"paths": ["amountMicros"]},
            })
        return {'success': True, 'campaign_id': campaign_id}

    def _update_resource(
        self,
        resource: str,
        resource_id: str,
        updates: dict,
        allowed_fields: set[str],
        result_key: str,
    ) -> dict:
        """Run one validated customer-level Google Ads update mutation."""
        resource_id = self._numeric_id(resource_id, result_key)
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - allowed_fields
        if unknown:
            raise ValueError(
                f"Unsupported Google {result_key} update fields: {sorted(unknown)}"
            )

        normalized = {
            key: value for key, value in updates.items() if value is not None
        }
        if "cpc_bid" in normalized:
            try:
                normalized["cpc_bid_micros"] = int(
                    float(normalized.pop("cpc_bid")) * 1_000_000
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("cpc_bid must be a positive number") from exc
        patch = {
            "resourceName": f"customers/{self.customer_id}/{resource}/{resource_id}",
            **normalized,
        }
        self._mutate(resource, {
            "update": self._camel_case_keys(patch),
            "updateMask": {
                "paths": [self._camel_case(key) for key in normalized],
            },
        })
        return {"success": True, result_key: resource_id}

    def update_ad_group(self, ad_group_id: str, updates: dict) -> dict:
        """Update mutable Google Ads Ad Group fields."""
        return self._update_resource(
            "adGroups", ad_group_id, updates,
            self.AD_GROUP_UPDATE_FIELDS, "ad_group_id",
        )

    def update_ad(self, ad_id: str, updates: dict) -> dict:
        """Update mutable Google Ads AdGroupAd fields."""
        return self._update_resource(
            "adGroupAds", ad_id, updates,
            self.AD_UPDATE_FIELDS, "ad_id",
        )

    def update_asset_group(self, asset_group_id: str, updates: dict) -> dict:
        """Update mutable Performance Max Asset Group fields."""
        return self._update_resource(
            "assetGroups", asset_group_id, updates,
            self.ASSET_GROUP_UPDATE_FIELDS, "asset_group_id",
        )
    
    def pause_campaign(self, campaign_id: str) -> dict:
        """暂停 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> dict:
        """恢复 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'ENABLED'})
    
    def create_ad_group(
        self,
        campaign_id: str,
        name: str,
        cpc_bid_micros: int = 500000,
        type: str = "SEARCH_DYNAMIC_ADS",
        status: str = None,
        targeting: dict = None,
    ) -> str:
        """创建 Ad Group"""
        ad_group_data = {
            'name': name,
            'status': status or 'PAUSED',
            'campaign': f'customers/{self.customer_id}/campaigns/{campaign_id}',
            'type': type,
            'cpcBidMicros': cpc_bid_micros,
        }
        if targeting:
            # ``targeting`` is a provider-ready targetingSetting object. More
            # granular criteria are separate Google Ads resources and should
            # be added as a dedicated Tool instead of being silently dropped.
            ad_group_data['targetingSetting'] = self._camel_case_keys(targeting)
        
        resp = self._mutate('adGroups', {'create': ad_group_data})
        resource_name = self._mutation_resource_name(resp)
        if not resource_name:
            raise APIError(f"Ad group mutate returned no resource name: {resp}")
        return str(resource_name.split('/')[-1])
    
    # ==================== Ad 管理 ====================
    
    def create_search_ad(
        self,
        ad_group_id: str,
        headlines: list[str],
        descriptions: list[str],
        final_url: str,
        ad_type: str = None,
        path1: str = None,
        path2: str = None,
        responsive_search_ad: dict = None,
        status: str = None,
    ) -> str:
        """创建响应式搜索广告"""
        if ad_type and str(ad_type).upper() != "RESPONSIVE_SEARCH_AD":
            raise ValueError(
                "Google create_search_ad currently supports only RESPONSIVE_SEARCH_AD"
            )
        ad_data = {
            'adGroup': f'customers/{self.customer_id}/adGroups/{ad_group_id}',
            'status': status or 'PAUSED',
            'ad': {
                'finalUrls': [final_url],
                'responsiveSearchAd': responsive_search_ad or {
                    'headlines': [{'text': h} for h in headlines[:15]],
                    'descriptions': [{'text': d} for d in descriptions[:4]],
                },
            },
        }
        rsa = ad_data['ad'].get('responsiveSearchAd')
        if isinstance(rsa, dict):
            if path1:
                rsa['path1'] = path1
            if path2:
                rsa['path2'] = path2
        resp = self._mutate('adGroupAds', {'create': ad_data})
        resource_name = self._mutation_resource_name(resp)
        if not resource_name:
            raise APIError(f"Ad mutate returned no resource name: {resp}")
        return str(resource_name.split('/')[-1])
    
    # ==================== PMax Asset 管理 ====================
    
    def create_pmax_asset_group(
        self,
        campaign_id: str,
        name: str,
        headlines: list[dict],
        descriptions: list[dict] = None,
        images: list[dict] = None,
        videos: list[str] = None,
    ) -> str:
        """
        创建 PMax Asset Group
        
        headlines: [{"text": "...", "pin_field": "HEADLINE"}, ...]
        """
        # A resource-shaped placeholder is dangerous here: callers could
        # persist it as if Google had accepted the multi-step mutation.  The
        # Capability is dry-run-only until a real AssetService implementation
        # is available, so fail explicitly if this adapter is called directly.
        raise NotImplementedError(
            "Google PMax Asset Group creation requires a verified AssetService adapter"
        )
    
    # ==================== 报表查询 ====================
    
    def get_campaign_report(
        self,
        campaign_ids: list[str],
        date_from: str = "LAST_30_DAYS",
        date_to: str = "TODAY",
        metrics: list[str] = None,
    ) -> list:
        """
        查询 Campaign 级别报表
        
        注意：Google Ads API 不支持直接按日期范围查询，
        需要使用 date range 字面量或 segments.date
        
        date_from/date_to 支持:
        - "LAST_30_DAYS", "YESTERDAY", "TODAY", "THIS_MONTH"
        - 或具体日期: "2024-01-01"
        """
        default_metrics = [
            'metrics.impressions', 'metrics.clicks', 'metrics.cost_micros',
            'metrics.ctr', 'metrics.average_cpc', 'metrics.conversions',
            'metrics.cost_per_conversion',
        ]
        
        campaign_ids = [self._numeric_id(cid, "campaign_id") for cid in (campaign_ids or [])]
        if not campaign_ids:
            return []
        where_clause = " OR ".join([f"campaign.id = {cid}" for cid in campaign_ids])
        date_clause = self._date_clause(date_from, date_to)
        
        query = f"""
            SELECT 
                campaign.id, campaign.name, campaign.status,
                segments.date,
                {', '.join(metrics or default_metrics)}
            FROM campaign
            WHERE {where_clause}
              AND {date_clause}
        """
        
        result = self._search(query)
        # _search returns the raw transport envelope, while some test/fake
        # clients return the extracted payload.  Accept both shapes.
        payload = self._response_payload(result)
        return payload.get('results', []) if isinstance(payload, dict) else []
    
    def get_adgroup_report(
        self,
        campaign_id: str,
        adgroup_ids: list[str] = None,
        date_from: str = "LAST_30_DAYS",
        date_to: str = "TODAY",
    ) -> list:
        """查询 Ad Group 级别报表"""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        date_clause = self._date_clause(date_from, date_to)
        where_clause = f"campaign.id = {campaign_id}"
        if adgroup_ids:
            safe_adgroup_ids = [self._numeric_id(value, "ad_group_id") for value in adgroup_ids]
            where_clause += f" AND ad_group.id IN ({', '.join(safe_adgroup_ids)})"
        
        query = f"""
            SELECT 
                campaign.id, campaign.name,
                ad_group.id, ad_group.name,
                segments.date,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.cost_per_conversion
            FROM ad_group
            WHERE {where_clause}
              AND {date_clause}
        """
        
        result = self._search(query)
        payload = self._response_payload(result)
        return payload.get('results', []) if isinstance(payload, dict) else []
    
    # ==================== 辅助方法 ====================

    @staticmethod
    def _numeric_id(value: Any, field_name: str) -> str:
        """Validate IDs before interpolating them into GAQL."""
        value = str(value or "").strip()
        if not re.fullmatch(r"\d+", value):
            raise ValueError(f"{field_name} must contain digits only")
        return value

    @staticmethod
    def _response_payload(response: Any) -> dict[str, Any]:
        """Return the Google Ads JSON payload from raw or extracted data.

        The production transport returns ``{status_code, data, headers}``,
        while lightweight adapters often return the already-extracted
        ``{"results": [...]}`` object.  Keep that tolerance at the client
        boundary instead of making each read method guess the envelope.
        """
        if not isinstance(response, dict):
            return {}
        payload = response.get("data", response)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _safe_limit(value: Any) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 100
        return min(max(value, 1), 10_000)

    @classmethod
    def _date_clause(cls, date_from: str, date_to: str) -> str:
        """Build valid GAQL date syntax for literals or ISO dates."""
        start = str(date_from or "LAST_30_DAYS").upper()
        end = str(date_to or "TODAY").upper()
        if start in cls.DATE_LITERALS and end in {"TODAY", start}:
            return f"segments.date DURING {start}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", end
        ):
            return f"segments.date BETWEEN '{start}' AND '{end}'"
        if start in cls.DATE_LITERALS and end == "TODAY":
            return f"segments.date DURING {start}"
        raise ValueError(
            "Google date range must be a supported DURING literal or two ISO dates"
        )

    def _get_campaign_budget_resource(self, campaign_id: str) -> str:
        """Resolve the budget resource required by Campaign budget updates."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        result = self._search(
            "SELECT campaign.campaign_budget "
            f"FROM campaign WHERE campaign.id = {campaign_id} LIMIT 1"
        )
        payload = self._response_payload(result)
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        if not rows or not isinstance(rows[0], dict):
            return ""
        campaign = rows[0].get("campaign", {}) or {}
        budget = campaign.get("campaignBudget", campaign.get("campaign_budget", {}))
        if isinstance(budget, dict):
            return str(budget.get("resourceName") or budget.get("resource_name") or "")
        return str(budget or "")

    def _search(
        self, query: str, page_token: str = None, page_size: int = None,
    ) -> dict:
        """执行 GAQL 查询"""
        # 使用 customer_id 进行搜索（不是 login_customer_id）
        # login_customer_id 仅用于 header 中的权限验证
        # 注意: 端点格式是 /customers/{id}/googleAds:search (斜线不是冒号)
        url = f"{self.BASE_URL}/customers/{self.customer_id}/googleAds:search"
        data = {'query': query}
        if page_token:
            data['pageToken'] = page_token
        if page_size is not None:
            data['pageSize'] = self._safe_limit(page_size)
        # GAQL search is read-only despite using POST, so it is safe to retry
        # when the provider returns a transient failure.
        return self.request_raw('POST', url, data=data, retry_non_idempotent=True)

    def _search_all(
        self, query: str, page_size: int = 100, max_pages: int = 100,
    ) -> list[dict]:
        """Fetch all GAQL pages while bounding malformed-token loops."""
        rows: list[dict] = []
        page_token = None
        seen_tokens: set[str] = set()
        for _ in range(max_pages):
            response = self._search(
                query, page_token=page_token, page_size=page_size
            )
            payload = self._response_payload(response)
            page_rows = payload.get('results', []) if isinstance(payload, dict) else []
            if isinstance(page_rows, list):
                rows.extend(row for row in page_rows if isinstance(row, dict))
            next_token = payload.get('nextPageToken') if isinstance(payload, dict) else None
            if not next_token or next_token in seen_tokens:
                break
            seen_tokens.add(next_token)
            page_token = next_token
        return rows

    def _mutate(self, resource: str, operation: dict) -> dict:
        """Execute one Google Ads customer-level mutate operation."""
        url = f"{self.BASE_URL}/customers/{self.customer_id}/{resource}:mutate"
        response = self.request_raw('POST', url, data={'operations': [operation]})
        status = response.get('status_code', 200)
        if status not in (200, 201, 202):
            raise APIError(
                f"Google Ads {resource} mutate returned HTTP {status}",
                status_code=status, response=response,
            )
        return response

    @staticmethod
    def _mutation_resource_name(response: dict) -> str:
        data = GoogleAdsAPIClient._response_payload(response)
        results = data.get('results', []) if isinstance(data, dict) else []
        if results and isinstance(results[0], dict):
            return results[0].get('resourceName', '')
        # Accept a small legacy/fake envelope while keeping production parsing
        # aligned with the Google Ads mutate response.
        return data.get('resourceName', '') if isinstance(data, dict) else ''

    @staticmethod
    def _camel_case(value: str) -> str:
        parts = value.split('_')
        return parts[0] + ''.join(part[:1].upper() + part[1:] for part in parts[1:])

    @classmethod
    def _camel_case_keys(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {cls._camel_case(str(key)): cls._camel_case_keys(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._camel_case_keys(item) for item in value]
        return value
    
    def _format_value(self, value) -> Any:
        """格式化 API 返回值"""
        if isinstance(value, dict):
            return {k: self._format_value(v) for k, v in value.items()}
        return value
