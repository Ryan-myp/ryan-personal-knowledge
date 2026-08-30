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
    CAMPAIGN_BUDGET_UPDATE_FIELDS = {
        "name", "daily_budget", "budget", "delivery_method", "explicitly_shared",
    }
    CAMPAIGN_CRITERION_UPDATE_FIELDS = {"status", "negative", "bid_modifier"}
    CONVERSION_ACTION_TYPES = {
        "AD_CALL", "CLICK_TO_CALL", "GOOGLE_PLAY_DOWNLOAD",
        "GOOGLE_PLAY_IN_APP_PURCHASE", "UPLOAD_CALLS", "UPLOAD_CLICKS",
        "WEBPAGE", "WEBSITE_CALL", "STORE_SALES_DIRECT_UPLOAD", "STORE_SALES",
        "FIREBASE_ANDROID_FIRST_OPEN", "FIREBASE_ANDROID_IN_APP_PURCHASE",
        "FIREBASE_ANDROID_CUSTOM", "FIREBASE_IOS_FIRST_OPEN",
        "FIREBASE_IOS_IN_APP_PURCHASE", "FIREBASE_IOS_CUSTOM",
        "THIRD_PARTY_APP_ANALYTICS_ANDROID_FIRST_OPEN",
        "THIRD_PARTY_APP_ANALYTICS_ANDROID_IN_APP_PURCHASE",
        "THIRD_PARTY_APP_ANALYTICS_ANDROID_CUSTOM",
        "THIRD_PARTY_APP_ANALYTICS_IOS_FIRST_OPEN",
        "THIRD_PARTY_APP_ANALYTICS_IOS_IN_APP_PURCHASE",
        "THIRD_PARTY_APP_ANALYTICS_IOS_CUSTOM", "ANDROID_APP_PRE_REGISTRATION",
        "ANDROID_INSTALLS_ALL_OTHER_APPS", "FLOODLIGHT_ACTION",
        "FLOODLIGHT_TRANSACTION", "GOOGLE_HOSTED", "LEAD_FORM_SUBMIT",
        "SEARCH_ADS_360", "SMART_CAMPAIGN_AD_CLICKS_TO_CALL",
        "SMART_CAMPAIGN_MAP_CLICKS_TO_CALL", "SMART_CAMPAIGN_MAP_DIRECTIONS",
        "SMART_CAMPAIGN_TRACKED_CALLS", "STORE_VISITS", "WEBPAGE_CODELESS",
        "UNIVERSAL_ANALYTICS_GOAL", "UNIVERSAL_ANALYTICS_TRANSACTION",
        "GOOGLE_ANALYTICS_4_CUSTOM", "GOOGLE_ANALYTICS_4_PURCHASE",
    }
    CONVERSION_ACTION_CATEGORIES = {
        "DEFAULT", "PAGE_VIEW", "PURCHASE", "SIGNUP", "DOWNLOAD", "ADD_TO_CART",
        "BEGIN_CHECKOUT", "SUBSCRIBE_PAID", "PHONE_CALL_LEAD", "IMPORTED_LEAD",
        "SUBMIT_LEAD_FORM", "BOOK_APPOINTMENT", "REQUEST_QUOTE", "GET_DIRECTIONS",
        "OUTBOUND_CLICK", "CONTACT", "ENGAGEMENT", "STORE_VISIT", "STORE_SALE",
        "QUALIFIED_LEAD", "CONVERTED_LEAD",
    }
    CONVERSION_ACTION_STATUSES = {"ENABLED", "REMOVED", "HIDDEN"}
    CONVERSION_ACTION_COUNTING_TYPES = {"ONE_PER_CLICK", "MANY_PER_CLICK"}
    CONVERSION_ACTION_UPDATE_FIELDS = {
        "name", "status", "category", "counting_type", "primary_for_goal",
        "include_in_conversions_metric", "click_through_lookback_window_days",
        "view_through_lookback_window_days", "value_settings",
    }
    CAMPAIGN_CRITERION_TYPES = {
        "LOCATION", "LANGUAGE", "DEVICE", "USER_LIST", "USER_INTEREST",
        "AGE_RANGE", "GENDER", "PARENTAL_STATUS", "INCOME_RANGE",
        "CONTENT_LABEL", "PLACEMENT", "TOPIC",
    }
    
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

    @classmethod
    def _normalize_customer_client(cls, row: dict) -> dict:
        """Normalize one manager-account customer_client GAQL row."""
        client = row.get("customerClient", row.get("customer_client", {}))
        if not isinstance(client, dict):
            client = {}
        return {
            "id": client.get("id"),
            "resource_name": client.get("resourceName", client.get("resource_name")),
            "client_customer": client.get(
                "clientCustomer", client.get("client_customer")
            ),
            "level": client.get("level"),
            "manager": client.get("manager"),
            "descriptive_name": client.get(
                "descriptiveName", client.get("descriptive_name")
            ),
            "currency_code": client.get(
                "currencyCode", client.get("currency_code")
            ),
            "time_zone": client.get("timeZone", client.get("time_zone")),
            "status": client.get("status"),
        }

    def list_customer_clients(self, page_size: int = 100) -> list[dict]:
        """List enabled child customers visible from the selected manager."""
        self._numeric_id(self.customer_id, "customer_id")
        query = (
            "SELECT customer_client.id, customer_client.resource_name, "
            "customer_client.client_customer, customer_client.level, "
            "customer_client.manager, customer_client.descriptive_name, "
            "customer_client.currency_code, customer_client.time_zone, "
            "customer_client.status FROM customer_client "
            "WHERE customer_client.status = 'ENABLED'"
        )
        return [
            self._normalize_customer_client(row)
            for row in self._search_all(query, page_size=page_size)
        ]

    @classmethod
    def _normalize_conversion_action(cls, row: dict) -> dict:
        """Normalize a GAQL conversion action row for Tool consumers."""
        action = row.get("conversionAction", row.get("conversion_action", {}))
        if not isinstance(action, dict):
            action = {}
        value_settings = action.get(
            "valueSettings", action.get("value_settings", {})
        )
        if not isinstance(value_settings, dict):
            value_settings = {}
        return {
            "id": action.get("id"),
            "resource_name": action.get("resourceName", action.get("resource_name")),
            "name": action.get("name"),
            "status": action.get("status"),
            "type": action.get("type"),
            "category": action.get("category"),
            "origin": action.get("origin"),
            "owner_customer": action.get(
                "ownerCustomer", action.get("owner_customer")
            ),
            "counting_type": action.get(
                "countingType", action.get("counting_type")
            ),
            "click_through_lookback_window_days": action.get(
                "clickThroughLookbackWindowDays",
                action.get("click_through_lookback_window_days"),
            ),
            "view_through_lookback_window_days": action.get(
                "viewThroughLookbackWindowDays",
                action.get("view_through_lookback_window_days"),
            ),
            "value_settings": {
                "default_value": value_settings.get(
                    "defaultValue", value_settings.get("default_value")
                ),
                "always_use_default_value": value_settings.get(
                    "alwaysUseDefaultValue",
                    value_settings.get("always_use_default_value"),
                ),
            },
        }

    def list_conversion_actions(self, page_size: int = 100) -> list[dict]:
        """List conversion actions configured for the selected customer."""
        query = (
            "SELECT conversion_action.id, conversion_action.resource_name, "
            "conversion_action.name, conversion_action.status, "
            "conversion_action.type, conversion_action.category, "
            "conversion_action.origin, conversion_action.owner_customer, "
            "conversion_action.counting_type, "
            "conversion_action.click_through_lookback_window_days, "
            "conversion_action.view_through_lookback_window_days, "
            "conversion_action.value_settings.default_value, "
            "conversion_action.value_settings.always_use_default_value "
            "FROM conversion_action"
        )
        return [
            self._normalize_conversion_action(row)
            for row in self._search_all(query, page_size=page_size)
        ]

    def get_conversion_action(self, conversion_action_id: str) -> dict:
        """Get one conversion action by numeric ID."""
        conversion_action_id = self._numeric_id(
            conversion_action_id, "conversion_action_id"
        )
        query = (
            "SELECT conversion_action.id, conversion_action.resource_name, "
            "conversion_action.name, conversion_action.status, "
            "conversion_action.type, conversion_action.category, "
            "conversion_action.origin, conversion_action.owner_customer, "
            "conversion_action.counting_type, "
            "conversion_action.click_through_lookback_window_days, "
            "conversion_action.view_through_lookback_window_days, "
            "conversion_action.value_settings.default_value, "
            "conversion_action.value_settings.always_use_default_value "
            f"FROM conversion_action WHERE conversion_action.id = {conversion_action_id}"
        )
        payload = self._response_payload(self._search(query))
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        if rows and isinstance(rows[0], dict):
            return self._normalize_conversion_action(rows[0])
        raise APIError(
            f"Google conversion action {conversion_action_id} was not found"
        )

    def create_conversion_action(self, action: dict[str, Any]) -> str:
        """Create one Google Ads ConversionAction through customer mutate."""
        if not isinstance(action, dict):
            raise ValueError("conversion action must be an object")
        name = str(action.get("name") or "").strip()
        action_type = str(action.get("type") or "").strip().upper()
        category = str(action.get("category") or "").strip().upper()
        if not name:
            raise ValueError("conversion action name is required")
        if action_type not in self.CONVERSION_ACTION_TYPES:
            raise ValueError(
                f"type must be one of {sorted(self.CONVERSION_ACTION_TYPES)}"
            )
        if category not in self.CONVERSION_ACTION_CATEGORIES:
            raise ValueError(
                f"category must be one of {sorted(self.CONVERSION_ACTION_CATEGORIES)}"
            )
        status = str(action.get("status") or "ENABLED").strip().upper()
        if status not in self.CONVERSION_ACTION_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(self.CONVERSION_ACTION_STATUSES)}"
            )
        counting_type = str(
            action.get("counting_type") or "MANY_PER_CLICK"
        ).strip().upper()
        if counting_type not in self.CONVERSION_ACTION_COUNTING_TYPES:
            raise ValueError(
                "counting_type must be ONE_PER_CLICK or MANY_PER_CLICK"
            )

        payload: dict[str, Any] = {
            "name": name,
            "type": action_type,
            "category": category,
            "status": status,
            "countingType": counting_type,
        }
        for key in (
            "primary_for_goal", "include_in_conversions_metric",
            "click_through_lookback_window_days",
            "view_through_lookback_window_days",
        ):
            value = action.get(key)
            if value is None:
                continue
            if key.endswith("_days"):
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key} must be a positive integer") from exc
                if value <= 0:
                    raise ValueError(f"{key} must be a positive integer")
            payload[self._camel_case(key)] = value

        value_settings = action.get("value_settings")
        if value_settings is not None:
            payload["valueSettings"] = self._normalize_conversion_value_settings(
                value_settings
            )
        response = self._mutate("conversionActions", {"create": payload})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(
                f"ConversionAction mutate returned no resource name: {response}"
            )
        return str(resource_name.rsplit("/", 1)[-1])

    @staticmethod
    def _normalize_conversion_value_settings(value_settings: Any) -> dict[str, Any]:
        if not isinstance(value_settings, dict) or not value_settings:
            raise ValueError("value_settings must be a non-empty object")
        allowed = {
            "default_value", "default_currency_code", "always_use_default_value",
        }
        unknown = set(value_settings) - allowed
        if unknown:
            raise ValueError(
                f"Unsupported Google value_settings fields: {sorted(unknown)}"
            )
        result: dict[str, Any] = {}
        for key, value in value_settings.items():
            if value is None:
                continue
            if key == "default_value":
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("default_value must be a number") from exc
            result[GoogleAdsAPIClient._camel_case(key)] = value
        if not result:
            raise ValueError("value_settings must contain a non-null field")
        return result

    def update_conversion_action(
        self, conversion_action_id: str, updates: dict[str, Any]
    ) -> dict:
        """Update mutable ConversionAction fields with an explicit mask."""
        conversion_action_id = self._numeric_id(
            conversion_action_id, "conversion_action_id"
        )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.CONVERSION_ACTION_UPDATE_FIELDS
        if unknown:
            raise ValueError(
                f"Unsupported Google ConversionAction update fields: {sorted(unknown)}"
            )
        normalized: dict[str, Any] = {}
        update_paths: list[str] = []
        for key, value in updates.items():
            if value is None:
                continue
            if key == "name":
                value = str(value).strip()
                if not value:
                    raise ValueError("name must not be empty")
            elif key == "status":
                value = str(value).strip().upper()
                if value not in self.CONVERSION_ACTION_STATUSES:
                    raise ValueError(
                        f"status must be one of {sorted(self.CONVERSION_ACTION_STATUSES)}"
                    )
            elif key == "category":
                value = str(value).strip().upper()
                if value not in self.CONVERSION_ACTION_CATEGORIES:
                    raise ValueError(
                        f"category must be one of {sorted(self.CONVERSION_ACTION_CATEGORIES)}"
                    )
            elif key == "counting_type":
                value = str(value).strip().upper()
                if value not in self.CONVERSION_ACTION_COUNTING_TYPES:
                    raise ValueError(
                        "counting_type must be ONE_PER_CLICK or MANY_PER_CLICK"
                    )
            elif key.endswith("_days"):
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key} must be a positive integer") from exc
                if value <= 0:
                    raise ValueError(f"{key} must be a positive integer")
            if key == "value_settings":
                value = self._normalize_conversion_value_settings(value)
                normalized["valueSettings"] = value
                update_paths.extend(
                    f"valueSettings.{self._camel_case(field)}"
                    for field in value
                )
            else:
                wire_key = self._camel_case(key)
                normalized[wire_key] = value
                update_paths.append(wire_key)
        if not normalized:
            raise ValueError("updates must contain a supported non-null field")
        resource_name = (
            f"customers/{self.customer_id}/conversionActions/{conversion_action_id}"
        )
        self._mutate("conversionActions", {
            "update": {"resourceName": resource_name, **normalized},
            "updateMask": {"paths": update_paths},
        })
        return {"success": True, "conversion_action_id": conversion_action_id}

    def delete_conversion_action(self, conversion_action_id: str) -> dict:
        """Remove one Google Ads ConversionAction."""
        conversion_action_id = self._numeric_id(
            conversion_action_id, "conversion_action_id"
        )
        self._mutate("conversionActions", {
            "remove": (
                f"customers/{self.customer_id}/conversionActions/"
                f"{conversion_action_id}"
            )
        })
        return {"success": True, "conversion_action_id": conversion_action_id}

    @classmethod
    def _normalize_bidding_strategy(cls, row: dict) -> dict:
        """Normalize a GAQL bidding strategy row for Tool consumers."""
        strategy = row.get("biddingStrategy", row.get("bidding_strategy", {}))
        if not isinstance(strategy, dict):
            strategy = {}
        return {
            "id": strategy.get("id"),
            "resource_name": strategy.get(
                "resourceName", strategy.get("resource_name")
            ),
            "name": strategy.get("name"),
            "status": strategy.get("status"),
            "type": strategy.get("type"),
        }

    def list_bidding_strategies(self, page_size: int = 100) -> list[dict]:
        """List bidding strategies configured for the selected customer."""
        query = (
            "SELECT bidding_strategy.id, bidding_strategy.resource_name, "
            "bidding_strategy.name, bidding_strategy.status, bidding_strategy.type "
            "FROM bidding_strategy"
        )
        return [
            self._normalize_bidding_strategy(row)
            for row in self._search_all(query, page_size=page_size)
        ]

    def get_bidding_strategy(self, bidding_strategy_id: str) -> dict:
        """Get one bidding strategy by numeric ID."""
        bidding_strategy_id = self._numeric_id(
            bidding_strategy_id, "bidding_strategy_id"
        )
        query = (
            "SELECT bidding_strategy.id, bidding_strategy.resource_name, "
            "bidding_strategy.name, bidding_strategy.status, bidding_strategy.type "
            f"FROM bidding_strategy WHERE bidding_strategy.id = {bidding_strategy_id}"
        )
        payload = self._response_payload(self._search(query))
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        if rows and isinstance(rows[0], dict):
            return self._normalize_bidding_strategy(rows[0])
        raise APIError(
            f"Google bidding strategy {bidding_strategy_id} was not found"
        )

    @classmethod
    def _normalize_user_list(cls, row: dict) -> dict:
        """Normalize a GAQL user-list row for audience lookup Tools."""
        user_list = row.get("userList", row.get("user_list", {}))
        if not isinstance(user_list, dict):
            user_list = {}
        return {
            "id": user_list.get("id"),
            "resource_name": user_list.get(
                "resourceName", user_list.get("resource_name")
            ),
            "name": user_list.get("name"),
            "description": user_list.get("description"),
            "type": user_list.get("type"),
            "membership_status": user_list.get(
                "membershipStatus", user_list.get("membership_status")
            ),
            "membership_life_span": user_list.get(
                "membershipLifeSpan", user_list.get("membership_life_span")
            ),
            "size_for_display": user_list.get(
                "sizeForDisplay", user_list.get("size_for_display")
            ),
            "size_for_search": user_list.get(
                "sizeForSearch", user_list.get("size_for_search")
            ),
        }

    def list_user_lists(self, page_size: int = 100) -> list[dict]:
        """List first-party user lists configured for the selected customer."""
        query = (
            "SELECT user_list.id, user_list.resource_name, user_list.name, "
            "user_list.description, user_list.type, user_list.membership_status, "
            "user_list.membership_life_span, user_list.size_for_display, "
            "user_list.size_for_search FROM user_list"
        )
        return [
            self._normalize_user_list(row)
            for row in self._search_all(query, page_size=page_size)
        ]

    def get_user_list(self, user_list_id: str) -> dict:
        """Get one first-party user list by numeric ID."""
        user_list_id = self._numeric_id(user_list_id, "user_list_id")
        query = (
            "SELECT user_list.id, user_list.resource_name, user_list.name, "
            "user_list.description, user_list.type, user_list.membership_status, "
            "user_list.membership_life_span, user_list.size_for_display, "
            "user_list.size_for_search "
            f"FROM user_list WHERE user_list.id = {user_list_id}"
        )
        payload = self._response_payload(self._search(query))
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        if rows and isinstance(rows[0], dict):
            return self._normalize_user_list(rows[0])
        raise APIError(f"Google user list {user_list_id} was not found")
    
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

    def create_keywords(
        self,
        ad_group_id: str,
        keywords: list[dict],
        status: str = "PAUSED",
    ) -> list[str]:
        """Create keyword criteria in one customer-level mutate request.

        Each item is provider-shaped only at the Capability boundary; this
        method owns the Google Ads ``AdGroupCriterion`` wire payload. Writes
        are currently intercepted by Runtime in dry-run mode.
        """
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        if not isinstance(keywords, list) or not keywords:
            raise ValueError("keywords must be a non-empty list")
        criterion_status = str(status or "PAUSED").upper()
        if criterion_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("keyword status must be ENABLED or PAUSED")

        operations = []
        for index, keyword in enumerate(keywords):
            if not isinstance(keyword, dict):
                raise ValueError(f"keywords[{index}] must be an object")
            text = str(keyword.get("text") or "").strip()
            if not text:
                raise ValueError(f"keywords[{index}].text is required")
            match_type = str(keyword.get("match_type") or "BROAD").upper()
            if match_type not in {"BROAD", "PHRASE", "EXACT"}:
                raise ValueError(
                    f"keywords[{index}].match_type must be BROAD, PHRASE or EXACT"
                )
            criterion = {
                "adGroup": f"customers/{self.customer_id}/adGroups/{ad_group_id}",
                "status": str(keyword.get("status") or criterion_status).upper(),
                "keyword": {"text": text, "matchType": match_type},
            }
            if criterion["status"] not in {"ENABLED", "PAUSED"}:
                raise ValueError(f"keywords[{index}].status must be ENABLED or PAUSED")
            if keyword.get("negative"):
                criterion["negative"] = True
            if keyword.get("cpc_bid_micros") is not None:
                bid = int(keyword["cpc_bid_micros"])
                if bid < 0:
                    raise ValueError(f"keywords[{index}].cpc_bid_micros must be non-negative")
                criterion["cpcBidMicros"] = bid
            operations.append({"create": criterion})

        response = self._mutate_operations("adGroupCriteria", operations)
        data = self._response_payload(response)
        results = data.get("results", []) if isinstance(data, dict) else []
        resource_ids = []
        for result in results:
            if isinstance(result, dict) and result.get("resourceName"):
                resource_ids.append(str(result["resourceName"]).rsplit("/", 1)[-1])
        if len(resource_ids) != len(operations):
            raise APIError(
                f"Google keyword mutate returned {len(resource_ids)} resources for "
                f"{len(operations)} operations: {response}"
            )
        return resource_ids

    def create_product_group(
        self,
        ad_group_id: str,
        product_group_type: str,
        value: Any = None,
        partition_type: str = "UNIT",
        parent_criterion_id: str = None,
        cpc_bid_micros: int = None,
        bidding_category_level: str = "LEVEL1",
    ) -> str:
        """Create one Shopping product partition criterion.

        Google Shopping product groups are not a standalone resource.  They
        are ``AdGroupCriterion`` mutations whose ``listingGroup`` contains a
        root or dimension-specific case value.  Keep this translation here so
        the Capability/Tool contract remains provider-neutral.
        """
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        group_type = str(product_group_type or "").strip().lower()
        partition = str(partition_type or "UNIT").strip().upper()
        if partition not in {"UNIT", "SUBDIVISION"}:
            raise ValueError("partition_type must be UNIT or SUBDIVISION")

        supported_types = {
            "all_products",
            *(f"product_type_{level}" for level in range(1, 6)),
            "brand", "condition",
            *(f"custom_label_{index}" for index in range(5)),
            "channel", "item_id", "bidding_category",
        }
        if group_type not in supported_types:
            raise ValueError(f"Unsupported product_group_type: {product_group_type}")

        listing_group: dict[str, Any] = {"type": partition}
        if parent_criterion_id:
            listing_group["parentAdGroupCriterion"] = self._criterion_resource_name(
                ad_group_id, parent_criterion_id
            )
        if group_type != "all_products":
            if value in (None, ""):
                raise ValueError(f"{group_type} requires value")
            listing_group["caseValue"] = self._product_case_value(
                group_type, value, bidding_category_level
            )

        criterion: dict[str, Any] = {
            "adGroup": f"customers/{self.customer_id}/adGroups/{ad_group_id}",
            "listingGroup": listing_group,
        }
        if cpc_bid_micros is not None:
            cpc_bid_micros = int(cpc_bid_micros)
            if cpc_bid_micros < 0:
                raise ValueError("cpc_bid_micros must be non-negative")
            criterion["cpcBidMicros"] = cpc_bid_micros

        response = self._mutate_operations(
            "adGroupCriteria", [{"create": criterion}]
        )
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"Product group mutate returned no resource name: {response}")
        return str(resource_name).rsplit("/", 1)[-1]

    # ==================== Campaign Criterion ====================

    @staticmethod
    def _criterion_resource_reference(
        value: Any, prefix: str, field_name: str, customer_id: str = ""
    ) -> str:
        """Normalize a Google Ads criterion reference without path injection."""
        raw = str(value or "").strip()
        if not raw:
            raise ValueError(f"{field_name} is required")
        if re.fullmatch(rf"{re.escape(prefix)}/\d+", raw):
            return raw
        if re.fullmatch(r"\d+", raw):
            return f"{prefix}/{raw}"
        if prefix in {"userLists", "userInterests"}:
            customer = str(customer_id or "").strip()
            if not re.fullmatch(r"\d+", customer):
                raise ValueError("customer_id must contain digits only")
            match = re.fullmatch(rf"customers/{customer}/{re.escape(prefix)}/(\d+)", raw)
            if match:
                return raw
        raise ValueError(f"{field_name} must be a numeric ID or {prefix}/<id> resource name")

    @staticmethod
    def _criterion_enum_info(value: Any, allowed: set[str], field_name: str) -> dict[str, str]:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise ValueError(f"{field_name} must be one of {sorted(allowed)}")
        return {"type": normalized}

    def _campaign_criterion_query(self, where: str = "") -> str:
        """Return the explicit GAQL projection used by criterion reads."""
        query = (
            "SELECT campaign.id, campaign_criterion.criterion_id, "
            "campaign_criterion.type, campaign_criterion.status, "
            "campaign_criterion.negative, campaign_criterion.bid_modifier, "
            "campaign_criterion.location.geo_target_constant, "
            "campaign_criterion.language.language_constant, "
            "campaign_criterion.user_list.user_list, "
            "campaign_criterion.user_interest.user_interest_category, "
            "campaign_criterion.device.type, campaign_criterion.age_range.type, "
            "campaign_criterion.gender.type, campaign_criterion.parental_status.type, "
            "campaign_criterion.income_range.type, campaign_criterion.content_label.type, "
            "campaign_criterion.placement.url, campaign_criterion.topic.topic_constant "
            "FROM campaign_criterion"
        )
        return f"{query} WHERE {where}" if where else query

    @classmethod
    def _normalize_campaign_criterion(cls, row: dict) -> dict:
        criterion = row.get("campaignCriterion", row.get("campaign_criterion", {})) or {}
        campaign = row.get("campaign", {}) or {}

        def value(*keys: str) -> Any:
            current: Any = criterion
            for key in keys:
                if not isinstance(current, dict):
                    return None
                current = current.get(key, current.get(cls._camel_case(key)))
            return current

        result = {
            "id": value("criterion_id"),
            "criterion_id": value("criterion_id"),
            "campaign_id": campaign.get("id"),
            "type": value("type"),
            "status": value("status"),
            "negative": value("negative"),
            "bid_modifier": value("bid_modifier"),
            "location_id": value("location", "geo_target_constant"),
            "language_id": value("language", "language_constant"),
            "user_list_id": value("user_list", "user_list"),
            "user_interest_id": value(
                "user_interest", "user_interest_category"
            ),
            "device": value("device", "type"),
            "age_range": value("age_range", "type"),
            "gender": value("gender", "type"),
            "parental_status": value("parental_status", "type"),
            "income_range": value("income_range", "type"),
            "content_label": value("content_label", "type"),
            "placement_url": value("placement", "url"),
            "topic_id": value("topic", "topic_constant", "topicConstant"),
            "resource_name": criterion.get("resourceName", criterion.get("resource_name")),
        }
        return result

    def list_campaign_criteria(
        self, campaign_id: str = None, page_size: int = 100
    ) -> list[dict]:
        """List CampaignCriterion targeting/exclusion rows."""
        where = ""
        if campaign_id is not None:
            where = f"campaign.id = {self._numeric_id(campaign_id, 'campaign_id')}"
        rows = self._search_all(
            self._campaign_criterion_query(where), page_size=page_size
        )
        return [self._normalize_campaign_criterion(row) for row in rows]

    def get_campaign_criterion(self, campaign_id: str, criterion_id: str) -> dict:
        """Get one CampaignCriterion by its Campaign-scoped criterion ID."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        criterion_id = self._numeric_id(criterion_id, "criterion_id")
        rows = self._search_all(
            self._campaign_criterion_query(
                f"campaign.id = {campaign_id} "
                f"AND campaign_criterion.criterion_id = {criterion_id}"
            ),
            page_size=1,
        )
        if not rows:
            raise APIError(
                f"Google campaign criterion {campaign_id}~{criterion_id} was not found"
            )
        return self._normalize_campaign_criterion(rows[0])

    def _build_campaign_criterion(
        self, campaign_id: str, spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Translate one neutral criterion spec into Google's one-of payload."""
        if not isinstance(spec, dict):
            raise ValueError("criteria items must be objects")
        criterion_type = str(spec.get("criterion_type") or "").strip().upper()
        if criterion_type not in self.CAMPAIGN_CRITERION_TYPES:
            raise ValueError(
                f"criterion_type must be one of {sorted(self.CAMPAIGN_CRITERION_TYPES)}"
            )
        criterion: dict[str, Any] = {
            "campaign": f"customers/{self.customer_id}/campaigns/{campaign_id}",
            "status": str(spec.get("status") or "PAUSED").upper(),
            "negative": bool(spec.get("negative", False)),
        }
        if criterion["status"] not in {"ENABLED", "PAUSED"}:
            raise ValueError("new CampaignCriterion status must be ENABLED or PAUSED")
        if spec.get("bid_modifier") is not None:
            try:
                bid_modifier = float(spec["bid_modifier"])
            except (TypeError, ValueError) as exc:
                raise ValueError("bid_modifier must be a non-negative number") from exc
            if bid_modifier < 0:
                raise ValueError("bid_modifier must be a non-negative number")
            criterion["bidModifier"] = bid_modifier

        if criterion_type == "LOCATION":
            criterion["location"] = {
                "geoTargetConstant": self._criterion_resource_reference(
                    spec.get("location_id"), "geoTargetConstants", "location_id"
                )
            }
        elif criterion_type == "LANGUAGE":
            criterion["language"] = {
                "languageConstant": self._criterion_resource_reference(
                    spec.get("language_id"), "languageConstants", "language_id"
                )
            }
        elif criterion_type == "USER_LIST":
            criterion["userList"] = {
                "userList": self._criterion_resource_reference(
                    spec.get("user_list_id"), "userLists", "user_list_id", self.customer_id
                )
            }
        elif criterion_type == "USER_INTEREST":
            criterion["userInterest"] = {
                "userInterestCategory": self._criterion_resource_reference(
                    spec.get("user_interest_id"),
                    "userInterests", "user_interest_id", self.customer_id,
                )
            }
        elif criterion_type == "DEVICE":
            criterion["device"] = self._criterion_enum_info(
                spec.get("device"), {"MOBILE", "TABLET", "DESKTOP", "CONNECTED_TV"}, "device"
            )
        elif criterion_type == "AGE_RANGE":
            criterion["ageRange"] = self._criterion_enum_info(
                spec.get("age_range"), {
                    "AGE_RANGE_18_24", "AGE_RANGE_25_34", "AGE_RANGE_35_44",
                    "AGE_RANGE_45_54", "AGE_RANGE_55_64", "AGE_RANGE_65_UP",
                    "AGE_RANGE_UNDETERMINED",
                }, "age_range"
            )
        elif criterion_type == "GENDER":
            criterion["gender"] = self._criterion_enum_info(
                spec.get("gender"), {"MALE", "FEMALE", "UNDETERMINED"}, "gender"
            )
        elif criterion_type == "PARENTAL_STATUS":
            criterion["parentalStatus"] = self._criterion_enum_info(
                spec.get("parental_status"), {"PARENT", "NOT_A_PARENT", "UNDETERMINED"}, "parental_status"
            )
        elif criterion_type == "INCOME_RANGE":
            criterion["incomeRange"] = self._criterion_enum_info(
                spec.get("income_range"), {
                    "INCOME_RANGE_0_50", "INCOME_RANGE_50_60", "INCOME_RANGE_60_70",
                    "INCOME_RANGE_70_80", "INCOME_RANGE_80_90", "INCOME_RANGE_90_100",
                    "INCOME_RANGE_UNDETERMINED",
                }, "income_range"
            )
        elif criterion_type == "CONTENT_LABEL":
            criterion["contentLabel"] = self._criterion_enum_info(
                spec.get("content_label"), {
                    "CONTENT_LABEL_DLT", "CONTENT_LABEL_DL_G", "CONTENT_LABEL_DL_PG",
                    "CONTENT_LABEL_DL_T", "CONTENT_LABEL_DL_MA", "CONTENT_LABEL_DLV",
                    "CONTENT_LABEL_DNS", "CONTENT_LABEL_UNRATED",
                }, "content_label"
            )
        elif criterion_type == "PLACEMENT":
            placement = str(spec.get("placement_url") or "").strip()
            if not placement or any(char in placement for char in "\r\n"):
                raise ValueError("placement_url is required and must be a single line")
            criterion["placement"] = {"url": placement}
        elif criterion_type == "TOPIC":
            criterion["topic"] = {
                "topicConstant": self._criterion_resource_reference(
                    spec.get("topic_id"), "topicConstants", "topic_id"
                )
            }
        return criterion

    def create_campaign_criteria(
        self, campaign_id: str, criteria: list[dict[str, Any]]
    ) -> list[str]:
        """Create a bounded batch of CampaignCriterion mutations."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("criteria must be a non-empty list")
        if len(criteria) > 1000:
            raise ValueError("criteria cannot contain more than 1000 items")
        operations = [
            {"create": self._build_campaign_criterion(campaign_id, spec)}
            for spec in criteria
        ]
        response = self._mutate_operations("campaignCriteria", operations)
        data = self._response_payload(response)
        results = data.get("results", []) if isinstance(data, dict) else []
        resource_ids = []
        for result in results:
            if isinstance(result, dict) and result.get("resourceName"):
                resource_id = str(result["resourceName"]).rsplit("/", 1)[-1]
                # CampaignCriterion resource names use the composite
                # ``campaign_id~criterion_id`` key.  Return the criterion ID
                # expected by the Tool contract; the parent campaign remains
                # an explicit input on subsequent get/update/delete calls.
                resource_ids.append(resource_id.rsplit("~", 1)[-1])
        if len(resource_ids) != len(operations):
            raise APIError(
                f"Google CampaignCriterion mutate returned {len(resource_ids)} resources "
                f"for {len(operations)} operations: {response}"
            )
        return resource_ids

    def update_campaign_criterion(
        self, campaign_id: str, criterion_id: str, updates: dict[str, Any]
    ) -> dict:
        """Update the small mutable CampaignCriterion field set."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        criterion_id = self._numeric_id(criterion_id, "criterion_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.CAMPAIGN_CRITERION_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported Google CampaignCriterion update fields: {sorted(unknown)}")
        patch: dict[str, Any] = {
            "resourceName": (
                f"customers/{self.customer_id}/campaignCriteria/"
                f"{campaign_id}~{criterion_id}"
            )
        }
        mask: list[str] = []
        if "status" in updates:
            status = str(updates["status"] or "").upper()
            if status not in {"ENABLED", "PAUSED", "REMOVED"}:
                raise ValueError("status must be ENABLED, PAUSED or REMOVED")
            patch["status"] = status
            mask.append("status")
        if "negative" in updates:
            if not isinstance(updates["negative"], bool):
                raise ValueError("negative must be boolean")
            patch["negative"] = updates["negative"]
            mask.append("negative")
        if "bid_modifier" in updates:
            try:
                bid_modifier = float(updates["bid_modifier"])
            except (TypeError, ValueError) as exc:
                raise ValueError("bid_modifier must be a non-negative number") from exc
            if bid_modifier < 0:
                raise ValueError("bid_modifier must be a non-negative number")
            patch["bidModifier"] = bid_modifier
            mask.append("bidModifier")
        if not mask:
            raise ValueError("updates must contain a supported non-null field")
        self._mutate("campaignCriteria", {
            "update": patch,
            "updateMask": {"paths": mask},
        })
        return {"success": True, "campaign_id": campaign_id, "criterion_id": criterion_id}

    def delete_campaign_criterion(self, campaign_id: str, criterion_id: str) -> dict:
        """Remove one CampaignCriterion by its campaign-scoped resource name."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        criterion_id = self._numeric_id(criterion_id, "criterion_id")
        resource_name = (
            f"customers/{self.customer_id}/campaignCriteria/"
            f"{campaign_id}~{criterion_id}"
        )
        self._mutate("campaignCriteria", {"remove": resource_name})
        return {
            "success": True,
            "campaign_id": campaign_id,
            "criterion_id": criterion_id,
        }

    def _criterion_resource_name(self, ad_group_id: str, criterion_id: Any) -> str:
        """Normalize a parent criterion ID without allowing path injection."""
        value = str(criterion_id or "").strip()
        full_prefix = re.fullmatch(
            r"customers/([A-Za-z0-9_-]+)/adGroupCriteria/(\d+~\d+)", value
        )
        if full_prefix:
            if full_prefix.group(1) != str(self.customer_id):
                raise ValueError("parent_criterion_id belongs to another customer")
            if not full_prefix.group(2).startswith(f"{ad_group_id}~"):
                raise ValueError("parent_criterion_id must belong to the supplied ad_group_id")
            return value
        if not re.fullmatch(r"\d+~\d+", value):
            raise ValueError(
                "parent_criterion_id must be '<ad_group_id>~<criterion_id>' "
                "or a full AdGroupCriterion resource name"
            )
        if not value.startswith(f"{ad_group_id}~"):
            raise ValueError("parent_criterion_id must belong to the supplied ad_group_id")
        return f"customers/{self.customer_id}/adGroupCriteria/{value}"

    @classmethod
    def _product_case_value(
        cls, group_type: str, value: Any, bidding_category_level: str
    ) -> dict[str, Any]:
        if group_type.startswith("product_type_"):
            level = group_type.rsplit("_", 1)[-1]
            return {"productType": {"level": f"LEVEL{level}", "value": str(value)}}
        if group_type == "brand":
            return {"productBrand": {"value": str(value)}}
        if group_type == "condition":
            condition = str(value).upper()
            if condition not in {"NEW", "USED", "REFURBISHED"}:
                raise ValueError("condition must be NEW, USED or REFURBISHED")
            return {"productCondition": {"condition": condition}}
        if group_type.startswith("custom_label_"):
            index = group_type.rsplit("_", 1)[-1]
            return {"productCustomLabel": {"index": f"INDEX{index}", "value": str(value)}}
        if group_type == "channel":
            channel = str(value).upper()
            if channel not in {"ONLINE", "LOCAL"}:
                raise ValueError("channel must be ONLINE or LOCAL")
            return {"productChannel": {"channel": channel}}
        if group_type == "item_id":
            return {"productItemId": {"value": str(value)}}
        if group_type == "bidding_category":
            category_id = str(value).strip()
            if not re.fullmatch(r"-?\d+", category_id):
                raise ValueError("bidding_category value must be a numeric category ID")
            level = str(bidding_category_level or "LEVEL1").upper()
            if level not in {f"LEVEL{item}" for item in range(1, 6)}:
                raise ValueError("bidding_category_level must be LEVEL1 through LEVEL5")
            return {"productBiddingCategory": {"level": level, "id": int(category_id)}}
        raise ValueError(f"Unsupported product_group_type: {group_type}")
    
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

    @staticmethod
    def _normalize_asset(row: dict) -> dict:
        """Normalize one GAQL Asset row without dropping typed asset data."""
        asset = row.get("asset", row) or {}
        text_asset = asset.get("textAsset", asset.get("text_asset", {})) or {}
        image_asset = asset.get("imageAsset", asset.get("image_asset", {})) or {}
        full_size = image_asset.get("fullSize", image_asset.get("full_size", {})) or {}
        video_asset = asset.get(
            "youtubeVideoAsset", asset.get("youtube_video_asset", {})
        ) or {}
        return {
            "id": asset.get("id"),
            "resource_name": asset.get("resourceName", asset.get("resource_name")),
            "name": asset.get("name"),
            "type": asset.get("type"),
            "text": text_asset.get("text"),
            "image_url": full_size.get("url"),
            "youtube_video_id": video_asset.get(
                "youtubeVideoId", video_asset.get("youtube_video_id")
            ),
            "final_urls": asset.get("finalUrls", asset.get("final_urls", [])) or [],
            "final_mobile_urls": asset.get(
                "finalMobileUrls", asset.get("final_mobile_urls", [])
            ) or [],
        }

    def list_assets(self, customer_id: str = None, page_size: int = 100) -> list[dict]:
        """List reusable customer-level Assets through GAQL."""
        scoped = self.for_customer(customer_id) if customer_id else self
        query = (
            "SELECT asset.id, asset.resource_name, asset.name, asset.type, "
            "asset.text_asset.text, asset.image_asset.full_size.url, "
            "asset.youtube_video_asset.youtube_video_id, asset.final_urls, "
            "asset.final_mobile_urls FROM asset"
        )
        return [
            scoped._normalize_asset(row)
            for row in scoped._search_all(query, page_size=page_size)
        ]

    def get_asset(self, asset_id: str, customer_id: str = None) -> dict:
        """Get one reusable customer-level Asset by numeric ID."""
        asset_id = self._numeric_id(asset_id, "asset_id")
        scoped = self.for_customer(customer_id) if customer_id else self
        query = (
            "SELECT asset.id, asset.resource_name, asset.name, asset.type, "
            "asset.text_asset.text, asset.image_asset.full_size.url, "
            "asset.youtube_video_asset.youtube_video_id, asset.final_urls, "
            "asset.final_mobile_urls FROM asset "
            f"WHERE asset.id = {asset_id}"
        )
        items = scoped._response_payload(scoped._search(query)).get("results", [])
        if items:
            return scoped._normalize_asset(items[0])
        raise APIError(f"Google asset {asset_id} was not found")

    # ==================== CampaignBudget 管理 ====================

    @staticmethod
    def _normalize_campaign_budget(row: dict) -> dict:
        budget = row.get("campaignBudget", row.get("campaign_budget", row)) or {}
        return {
            "id": budget.get("id"),
            "resource_name": budget.get("resourceName", budget.get("resource_name")),
            "name": budget.get("name"),
            "amount_micros": budget.get("amountMicros", budget.get("amount_micros")),
            "delivery_method": budget.get("deliveryMethod", budget.get("delivery_method")),
            "explicitly_shared": budget.get("explicitlyShared", budget.get("explicitly_shared")),
            "status": budget.get("status"),
            "reference_count": budget.get("referenceCount", budget.get("reference_count")),
        }

    def list_campaign_budgets(self, page_size: int = 100) -> list[dict]:
        """List customer CampaignBudget resources through GAQL."""
        query = (
            "SELECT campaign_budget.id, campaign_budget.resource_name, "
            "campaign_budget.name, campaign_budget.amount_micros, "
            "campaign_budget.delivery_method, campaign_budget.explicitly_shared, "
            "campaign_budget.status, campaign_budget.reference_count "
            "FROM campaign_budget"
        )
        return [self._normalize_campaign_budget(row) for row in self._search_all(query, page_size=page_size)]

    def get_campaign_budget(self, budget_id: str) -> dict:
        """Get one CampaignBudget by numeric ID."""
        budget_id = self._numeric_id(budget_id, "budget_id")
        query = (
            "SELECT campaign_budget.id, campaign_budget.resource_name, "
            "campaign_budget.name, campaign_budget.amount_micros, "
            "campaign_budget.delivery_method, campaign_budget.explicitly_shared, "
            "campaign_budget.status, campaign_budget.reference_count "
            f"FROM campaign_budget WHERE campaign_budget.id = {budget_id}"
        )
        rows = self._search(query)
        payload = self._response_payload(rows)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if results:
            return self._normalize_campaign_budget(results[0])
        raise APIError(f"Google campaign budget {budget_id} was not found")

    def create_campaign_budget(
        self,
        name: str,
        daily_budget: float,
        delivery_method: str = "STANDARD",
        explicitly_shared: bool = False,
    ) -> str:
        """Create a standalone CampaignBudget and return its numeric ID."""
        if not str(name or "").strip():
            raise ValueError("name is required")
        try:
            amount_micros = int(float(daily_budget) * 1_000_000)
        except (TypeError, ValueError) as exc:
            raise ValueError("daily_budget must be greater than 0") from exc
        if amount_micros <= 0:
            raise ValueError("daily_budget must be greater than 0")
        delivery_method = str(delivery_method or "STANDARD").upper()
        if delivery_method != "STANDARD":
            raise ValueError("Google Ads currently supports STANDARD delivery for CampaignBudget")
        response = self._mutate("campaignBudgets", {"create": {
            "name": name,
            "amountMicros": amount_micros,
            "deliveryMethod": delivery_method,
            "explicitlyShared": bool(explicitly_shared),
        }})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"CampaignBudget mutate returned no resource name: {response}")
        return str(resource_name.rsplit("/", 1)[-1])

    def update_campaign_budget(self, budget_id: str, updates: dict) -> dict:
        """Update the supported mutable CampaignBudget fields."""
        budget_id = self._numeric_id(budget_id, "budget_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.CAMPAIGN_BUDGET_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported Google CampaignBudget update fields: {sorted(unknown)}")
        normalized = {key: value for key, value in updates.items() if value is not None}
        if "budget" in normalized and "daily_budget" in normalized:
            raise ValueError("use only one of budget or daily_budget")
        amount = normalized.pop("daily_budget", normalized.pop("budget", None))
        if amount is not None:
            try:
                amount_micros = int(float(amount) * 1_000_000)
            except (TypeError, ValueError) as exc:
                raise ValueError("daily_budget must be greater than 0") from exc
            if amount_micros <= 0:
                raise ValueError("daily_budget must be greater than 0")
            normalized["amount_micros"] = amount_micros
        if "delivery_method" in normalized:
            normalized["delivery_method"] = str(normalized["delivery_method"]).upper()
            if normalized["delivery_method"] != "STANDARD":
                raise ValueError("Google Ads currently supports STANDARD delivery for CampaignBudget")
        if not normalized:
            raise ValueError("updates must contain a supported non-null field")
        patch = {"resourceName": f"customers/{self.customer_id}/campaignBudgets/{budget_id}"}
        patch.update(normalized)
        self._mutate("campaignBudgets", {
            "update": self._camel_case_keys(patch),
            "updateMask": {"paths": sorted(self._camel_case(key) for key in normalized)},
        })
        return {"success": True, "budget_id": budget_id}

    def delete_campaign_budget(self, budget_id: str) -> dict:
        """Remove an unreferenced CampaignBudget."""
        budget_id = self._numeric_id(budget_id, "budget_id")
        resource_name = f"customers/{self.customer_id}/campaignBudgets/{budget_id}"
        self._mutate("campaignBudgets", {"remove": resource_name})
        return {"success": True, "budget_id": budget_id}
    
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
        advertising_channel_sub_type: str = None,
        shopping_setting: dict = None,
        campaign_goal_setting: dict = None,
        video_setting: dict = None,
        targeting_setting: dict = None,
        network_setting: dict = None,
        final_url_suffix: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> str:
        """
        创建 Campaign（需要先创建 CampaignBudget）
        
        advertising_channel_type: SEARCH | SHOPPING | MAX | MULTI_CHANNEL | VIDEO | DISPLAY
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

        if advertising_channel_sub_type:
            campaign_data['advertisingChannelSubType'] = advertising_channel_sub_type
        for field_name, value in (
            ('shoppingSetting', shopping_setting),
            ('campaignGoalSetting', campaign_goal_setting),
            ('videoSetting', video_setting),
            ('targetingSetting', targeting_setting),
            ('networkSetting', network_setting),
        ):
            if value is not None:
                if not isinstance(value, dict):
                    raise ValueError(f"{field_name} must be an object")
                campaign_data[field_name] = self._camel_case_keys(value)
        if final_url_suffix:
            campaign_data['finalUrlSuffix'] = final_url_suffix

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

    def create_responsive_display_ad(
        self,
        ad_group_id: str,
        name: str,
        final_url: str,
        headlines: list[Any],
        long_headline: Any,
        descriptions: list[Any],
        business_name: str,
        marketing_images: list[dict] = None,
        square_marketing_images: list[dict] = None,
        logos: list[dict] = None,
        landscape_logos: list[dict] = None,
        videos: list[Any] = None,
        call_to_action_text: str = None,
        main_color: str = None,
        accent_color: str = None,
        allow_flexible_color: bool = None,
        ad_type: str = None,
        status: str = None,
    ) -> str:
        """Create a Google Responsive Display AdGroupAd mutation."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        if ad_type and str(ad_type).upper() != "RESPONSIVE_DISPLAY_AD":
            raise ValueError(
                "Google create_responsive_display_ad supports only RESPONSIVE_DISPLAY_AD"
            )
        if not str(name or "").strip() or not str(final_url or "").strip():
            raise ValueError("name and final_url are required")
        if not isinstance(headlines, list) or not 3 <= len(headlines) <= 5:
            raise ValueError("Responsive Display Ad requires 3 to 5 headlines")
        if not isinstance(descriptions, list) or not 1 <= len(descriptions) <= 5:
            raise ValueError("Responsive Display Ad requires 1 to 5 descriptions")
        if not str(business_name or "").strip():
            raise ValueError("business_name is required")

        display_info: dict[str, Any] = {
            "headlines": [self._text_asset(item) for item in headlines],
            "longHeadline": self._text_asset(long_headline),
            "descriptions": [self._text_asset(item) for item in descriptions],
            "businessName": business_name,
        }
        for field_name, values in (
            ("marketingImages", marketing_images),
            ("squareMarketingImages", square_marketing_images),
            ("logoImages", logos),
            ("landscapeLogoImages", landscape_logos),
            ("youtubeVideos", videos),
        ):
            if values:
                display_info[field_name] = [self._asset_reference(item) for item in values]
        for field_name, value in (
            ("callToActionText", call_to_action_text),
            ("mainColor", main_color),
            ("accentColor", accent_color),
            ("allowFlexibleColor", allow_flexible_color),
        ):
            if value is not None:
                display_info[field_name] = value

        ad_data = {
            "adGroup": f"customers/{self.customer_id}/adGroups/{ad_group_id}",
            "status": status or "PAUSED",
            "ad": {
                "name": name,
                "finalUrls": [final_url],
                "responsiveDisplayAd": display_info,
            },
        }
        response = self._mutate("adGroupAds", {"create": ad_data})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"Responsive Display Ad mutate returned no resource name: {response}")
        return str(resource_name).rsplit("/", 1)[-1]

    def create_video_ad(
        self,
        ad_group_id: str,
        name: str,
        video_ad_format: str,
        video_id: str,
        final_url: str,
        display_url: str = None,
        action_button_label: str = None,
        action_headline: str = None,
        companion_banner: dict = None,
        ad_type: str = None,
        status: str = None,
    ) -> str:
        """Build a Google Video Ad mutation for the selected video format.

        The Runtime exposes this as a dry-run-only Tool for now.  Keeping the
        provider payload in this adapter lets a future Google API revision be
        upgraded here without changing the Skill or central Runtime.
        """
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        video_ad_format = str(video_ad_format or "").upper()
        format_fields = {
            "SKIPPABLE_IN_STREAM": "inStream",
            "NON_SKIPPABLE_IN_STREAM": "nonSkippable",
            "BUMPER": "bumper",
            "OUTSTREAM": "outStream",
        }
        if video_ad_format not in format_fields:
            raise ValueError(
                "video_ad_format must be SKIPPABLE_IN_STREAM, NON_SKIPPABLE_IN_STREAM, "
                "BUMPER or OUTSTREAM"
            )
        if not str(name or "").strip() or not str(video_id or "").strip():
            raise ValueError("name and video_id are required")
        if not str(final_url or "").strip():
            raise ValueError("final_url is required")

        video_ad: dict[str, Any] = {
            "videoId": video_id,
            format_fields[video_ad_format]: {},
        }
        for field_name, value in (
            ("displayUrl", display_url),
            ("actionButtonLabel", action_button_label),
            ("actionHeadline", action_headline),
            ("companionBanner", companion_banner),
        ):
            if value is not None:
                video_ad[field_name] = (
                    self._camel_case_keys(value) if isinstance(value, dict) else value
                )

        ad_data = {
            "adGroup": f"customers/{self.customer_id}/adGroups/{ad_group_id}",
            "status": status or "PAUSED",
            "ad": {
                "name": name,
                "finalUrls": [final_url],
                "videoAd": video_ad,
            },
        }
        response = self._mutate("adGroupAds", {"create": ad_data})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"Video Ad mutate returned no resource name: {response}")
        return str(resource_name).rsplit("/", 1)[-1]

    @classmethod
    def _text_asset(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("text asset cannot be empty")
            return {"text": value}
        if isinstance(value, dict) and value:
            return cls._camel_case_keys(value)
        raise ValueError("text asset must be a non-empty string or object")

    @classmethod
    def _asset_reference(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("asset reference cannot be empty")
            return {"asset": value}
        if isinstance(value, dict) and value:
            return cls._camel_case_keys(value)
        raise ValueError("asset reference must be a non-empty string or object")
    
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
        return self._mutate_operations(resource, [operation])

    def _mutate_operations(self, resource: str, operations: list[dict]) -> dict:
        """Execute a bounded batch of Google Ads mutate operations."""
        if not isinstance(operations, list) or not operations:
            raise ValueError("mutate operations must be a non-empty list")
        url = f"{self.BASE_URL}/customers/{self.customer_id}/{resource}:mutate"
        response = self.request_raw('POST', url, data={'operations': operations})
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
