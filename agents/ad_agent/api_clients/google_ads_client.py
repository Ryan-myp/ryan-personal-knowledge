"""
api_clients/google_ads_client.py - Google Ads API 生产级客户端（HTTP 直调版）

绕过 google-ads SDK（有架构兼容问题），直接用 REST API。
认证: Bearer Token + Developer Token + Login Customer ID

层级结构:
Customer → Campaign → AdGroup → Ad
"""

from __future__ import annotations

import logging
import time
import json
import copy
import re
import threading
import csv
import base64
from pathlib import Path
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
    CHANNEL_TYPE_ALIASES = {
        # Keep the adapter tolerant of terminology found in older campaign
        # briefs while always emitting the current Google Ads enum.
        "MAX": "PERFORMANCE_MAX",
        "APP": "MULTI_CHANNEL",
    }
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
    USER_LIST_UPLOAD_KEY_TYPES = {
        "CONTACT_INFO", "CRM_ID", "MOBILE_ADVERTISING_ID",
    }
    USER_LIST_DATA_SOURCE_TYPES = {
        "FIRST_PARTY", "THIRD_PARTY_CREDIT_BUREAU",
        "THIRD_PARTY_VOTER_FILE", "THIRD_PARTY_PARTNER_DATA",
    }
    USER_LIST_UPDATE_FIELDS = {
        "name", "description", "membership_life_span", "integration_code",
        "eligible_for_search",
    }
    KEYWORD_UPDATE_FIELDS = {"status", "cpc_bid_micros", "cpc_bid"}
    PRODUCT_GROUP_UPDATE_FIELDS = {"status", "cpc_bid_micros", "cpc_bid"}
    USER_LIST_UPLOAD_COLUMNS = {"hashed_email", "hashed_phone_number"}
    MAX_USER_LIST_UPLOAD_BYTES = 100 * 1024 * 1024
    MAX_USER_LIST_UPLOAD_ROWS = 100_000
    BIDDING_STRATEGY_TYPES = {
        "MANUAL_CPC", "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_CPA", "TARGET_ROAS", "TARGET_IMPRESSION_SHARE",
    }
    # ExperimentService/ExperimentArmService enums are provider contracts;
    # keep them here with the payload adapter rather than in Runtime or a
    # workflow.  The values are from the Google Ads API v24 proto.
    EXPERIMENT_TYPES = {
        "DISPLAY_AND_VIDEO_360", "AD_VARIATION", "YOUTUBE_CUSTOM",
        "DISPLAY_CUSTOM", "SEARCH_CUSTOM", "DISPLAY_AUTOMATED_BIDDING_STRATEGY",
        "SEARCH_AUTOMATED_BIDDING_STRATEGY", "SHOPPING_AUTOMATED_BIDDING_STRATEGY",
        "SMART_MATCHING", "HOTEL_CUSTOM", "OPTIMIZE_ASSETS", "ADOPT_AI_MAX",
        "ADOPT_BROAD_MATCH_KEYWORDS", "PMAX_REPLACEMENT_SHOPPING",
    }
    EXPERIMENT_STATUSES = {
        "ENABLED", "REMOVED", "HALTED", "PROMOTED", "SETUP", "INITIATED", "GRADUATED",
    }
    EXPERIMENT_METRICS = {
        "CLICKS", "IMPRESSIONS", "COST", "CONVERSIONS_PER_INTERACTION_RATE",
        "COST_PER_CONVERSION", "CONVERSIONS_VALUE_PER_COST", "AVERAGE_CPC", "CTR",
        "INCREMENTAL_CONVERSIONS", "COMPLETED_VIDEO_VIEWS", "CUSTOM_ALGORITHMS",
        "CONVERSIONS", "CONVERSION_VALUE",
    }
    EXPERIMENT_METRIC_DIRECTIONS = {
        "NO_CHANGE", "INCREASE", "DECREASE", "NO_CHANGE_OR_INCREASE",
        "NO_CHANGE_OR_DECREASE",
    }
    VIDEO_EXPERIMENT_SUBTYPES = {"DEMAND_GEN_ASSET", "ASSET", "ASSET_UPLIFT"}
    OPTIMIZE_ASSETS_EXPERIMENT_SUBTYPES = {
        "ADD_ASSETS_TO_ASSETLESS_RETAIL", "ADD_VIDEO_ASSETS_TO_VIDEOLESS", "COMPARE_ASSETS",
    }
    EXPERIMENT_UPDATE_FIELDS = {
        "name", "description", "suffix", "start_date", "end_date", "status", "goals",
    }
    TARGET_IMPRESSION_SHARE_LOCATIONS = {
        "ANYWHERE_ON_PAGE", "TOP_OF_PAGE", "ABSOLUTE_TOP_OF_PAGE",
    }
    ASSET_TYPES = {"TEXT", "IMAGE", "YOUTUBE_VIDEO", "MEDIA_BUNDLE"}
    ASSET_MIME_TYPES = {"IMAGE_JPEG", "IMAGE_GIF", "IMAGE_PNG", "HTML5_AD_ZIP"}
    # CampaignAsset and AssetGroupAsset both use the provider's FieldType
    # enum.  Keep the enum in the client because it is part of the v24
    # payload contract, not a workflow concern.
    CAMPAIGN_ASSET_FIELD_TYPES = {
        "HEADLINE", "DESCRIPTION", "LONG_HEADLINE", "MARKETING_IMAGE",
        "MEDIA_BUNDLE", "YOUTUBE_VIDEO", "LOGO", "LANDSCAPE_LOGO",
        "BUSINESS_NAME", "CALL_TO_ACTION", "CALLOUT", "SITELINK",
        "STRUCTURED_SNIPPET", "PRICE", "PROMOTION", "MOBILE_APP",
        "CALL", "LEAD_FORM", "HOTEL_CALLOUT", "BOOK_ON_GOOGLE",
    }
    ASSET_GROUP_ASSET_FIELD_TYPES = {
        "HEADLINE", "LONG_HEADLINE", "DESCRIPTION", "MARKETING_IMAGE",
        "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE", "LOGO",
        "LANDSCAPE_LOGO", "YOUTUBE_VIDEO", "MEDIA_BUNDLE",
        "CALL_TO_ACTION_SELECTION", "BUSINESS_NAME",
    }
    MAX_ASSET_UPLOAD_BYTES = 50 * 1024 * 1024
    
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

    @staticmethod
    def _normalize_experiment(row: dict) -> dict[str, Any]:
        """Normalize one GAQL Experiment row without exposing wire casing."""
        experiment = row.get("experiment", {}) if isinstance(row, dict) else {}
        if not isinstance(experiment, dict):
            experiment = {}
        return {
            "id": experiment.get("id"),
            "resource_name": experiment.get(
                "resourceName", experiment.get("resource_name")
            ),
            "name": experiment.get("name"),
            "description": experiment.get("description"),
            "status": experiment.get("status"),
            "type": experiment.get("type"),
            "start_date": experiment.get("startDate", experiment.get("start_date")),
            "end_date": experiment.get("endDate", experiment.get("end_date")),
            "suffix": experiment.get("suffix"),
            "base_campaign": experiment.get(
                "baseCampaign", experiment.get("base_campaign")
            ),
            "experiment_campaign": experiment.get(
                "experimentCampaign", experiment.get("experiment_campaign")
            ),
        }

    def list_experiments(
        self, query: str | None = None, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List Google Ads Experiments through the read-only GAQL surface."""
        query = query or (
            "SELECT experiment.id, experiment.resource_name, experiment.name, "
            "experiment.description, experiment.status, experiment.type, "
            "experiment.start_date, experiment.end_date, experiment.suffix, "
            "experiment.base_campaign, experiment.experiment_campaign "
            "FROM experiment"
        )
        return [
            self._normalize_experiment(row)
            for row in self._search_all(query, page_size=page_size)
        ]

    def list_experiment_arms(
        self, query: str | None = None, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List Google Ads Experiment Arms through the read-only GAQL surface."""
        query = query or (
            "SELECT experiment_arm.id, experiment_arm.resource_name, "
            "experiment_arm.name, experiment_arm.experiment, "
            "experiment_arm.control, experiment_arm.traffic_split "
            "FROM experiment_arm"
        )
        rows = self._search_all(query, page_size=page_size)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            arm = row.get("experimentArm", row.get("experiment_arm", {}))
            if not isinstance(arm, dict):
                arm = {}
            normalized.append({
                "id": arm.get("id"),
                "resource_name": arm.get(
                    "resourceName", arm.get("resource_name")
                ),
                "name": arm.get("name"),
                "experiment": arm.get("experiment"),
                "control": arm.get("control"),
                "traffic_split": arm.get(
                    "trafficSplit", arm.get("traffic_split")
                ),
            })
        return normalized

    @staticmethod
    def _iso_date(value: Any, field: str) -> str:
        """Validate the provider's YYYY-MM-DD date contract."""
        text = str(value or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ValueError(f"{field} must use YYYY-MM-DD format")
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{field} must be a valid calendar date") from exc
        return text

    @classmethod
    def _experiment_goals(cls, goals: Any) -> list[dict[str, str]]:
        if goals is None:
            return []
        if not isinstance(goals, list) or not goals:
            raise ValueError("goals must be a non-empty list when supplied")
        normalized = []
        for index, goal in enumerate(goals):
            if not isinstance(goal, dict):
                raise ValueError(f"goals[{index}] must be an object")
            unknown = set(goal) - {"metric", "direction"}
            if unknown:
                raise ValueError(f"Unsupported experiment goal fields: {sorted(unknown)}")
            metric = str(goal.get("metric") or "").strip().upper()
            direction = str(goal.get("direction") or "").strip().upper()
            if metric not in cls.EXPERIMENT_METRICS:
                raise ValueError(
                    f"goals[{index}].metric must be one of {sorted(cls.EXPERIMENT_METRICS)}"
                )
            if direction not in cls.EXPERIMENT_METRIC_DIRECTIONS:
                raise ValueError(
                    f"goals[{index}].direction must be one of "
                    f"{sorted(cls.EXPERIMENT_METRIC_DIRECTIONS)}"
                )
            normalized.append({"metric": metric, "direction": direction})
        return normalized

    @classmethod
    def _experiment_payload(
        cls, experiment: dict[str, Any], *, require_name_and_type: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(experiment, dict) or not experiment:
            raise ValueError("experiment must be a non-empty object")
        allowed = {
            "name", "description", "suffix", "type", "status", "start_date", "end_date",
            "goals", "sync_enabled", "video_experiment_subtype",
            "optimize_assets_experiment_subtype",
        }
        unknown = set(experiment) - allowed
        if unknown:
            raise ValueError(f"Unsupported Google Experiment fields: {sorted(unknown)}")
        payload: dict[str, Any] = {}
        name = str(experiment.get("name") or "").strip()
        if require_name_and_type and not name:
            raise ValueError("experiment name is required")
        if name:
            if not 1 <= len(name) <= 1024:
                raise ValueError("experiment name must be 1..1024 characters")
            payload["name"] = name
        experiment_type = str(experiment.get("type") or "").strip().upper()
        if require_name_and_type and experiment_type not in cls.EXPERIMENT_TYPES:
            raise ValueError(
                f"type must be one of {sorted(cls.EXPERIMENT_TYPES)}"
            )
        if experiment_type:
            if experiment_type not in cls.EXPERIMENT_TYPES:
                raise ValueError(
                    f"type must be one of {sorted(cls.EXPERIMENT_TYPES)}"
                )
            payload["type"] = experiment_type
        for key, max_length in (("description", 2048), ("suffix", 255)):
            if experiment.get(key) is not None:
                value = str(experiment[key])
                if key == "description" and not value.strip():
                    raise ValueError("description must not be empty when supplied")
                if len(value) > max_length:
                    raise ValueError(f"{key} must be at most {max_length} characters")
                payload[cls._camel_case(key)] = value
        if experiment.get("status") is not None:
            status = str(experiment["status"]).strip().upper()
            if status not in cls.EXPERIMENT_STATUSES:
                raise ValueError(
                    f"status must be one of {sorted(cls.EXPERIMENT_STATUSES)}"
                )
            payload["status"] = status
        for key in ("start_date", "end_date"):
            if experiment.get(key) is not None:
                payload[cls._camel_case(key)] = cls._iso_date(experiment[key], key)
        if experiment.get("goals") is not None:
            payload["goals"] = cls._experiment_goals(experiment["goals"])
        if experiment.get("sync_enabled") is not None:
            if not isinstance(experiment["sync_enabled"], bool):
                raise ValueError("sync_enabled must be boolean")
            payload["syncEnabled"] = experiment["sync_enabled"]
        for input_key, wire_key, allowed_values in (
            ("video_experiment_subtype", "videoExperiment", cls.VIDEO_EXPERIMENT_SUBTYPES),
            ("optimize_assets_experiment_subtype", "optimizeAssetsExperiment", cls.OPTIMIZE_ASSETS_EXPERIMENT_SUBTYPES),
        ):
            if experiment.get(input_key) is not None:
                value = str(experiment[input_key]).strip().upper()
                if value not in allowed_values:
                    raise ValueError(f"{input_key} must be one of {sorted(allowed_values)}")
                nested_key = (
                    "videoExperimentSubtype"
                    if input_key == "video_experiment_subtype"
                    else "optimizeAssetsExperimentSubtype"
                )
                payload[wire_key] = {nested_key: value}
        return payload

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Get one Google Experiment through the read-only GAQL surface."""
        experiment_id = self._numeric_id(experiment_id, "experiment_id")
        query = (
            "SELECT experiment.id, experiment.resource_name, experiment.name, "
            "experiment.description, experiment.status, experiment.type, "
            "experiment.start_date, experiment.end_date, experiment.suffix, "
            "experiment.base_campaign, experiment.experiment_campaign "
            f"FROM experiment WHERE experiment.id = {experiment_id}"
        )
        rows = self._search(query)
        payload = self._response_payload(rows)
        result_rows = payload.get("results", []) if isinstance(payload, dict) else []
        if result_rows and isinstance(result_rows[0], dict):
            return self._normalize_experiment(result_rows[0])
        raise APIError(f"Google experiment {experiment_id} was not found")

    def create_experiment(self, experiment: dict[str, Any]) -> str:
        """Create one Experiment through ExperimentService.MutateExperiments."""
        payload = self._experiment_payload(experiment)
        response = self._mutate("experiments", {"create": payload})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"Experiment mutate returned no resource name: {response}")
        return str(resource_name.rsplit("/", 1)[-1])

    def update_experiment(self, experiment_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update only fields supported by the Experiment resource mask."""
        experiment_id = self._numeric_id(experiment_id, "experiment_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.EXPERIMENT_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported Google Experiment update fields: {sorted(unknown)}")
        payload = self._experiment_payload(updates, require_name_and_type=False)
        if not payload:
            raise ValueError("updates must contain a supported non-null field")
        update_mask = [self._camel_case(key) for key in updates if updates.get(key) is not None]
        # Nested goals use the resource field name; the mask remains stable
        # even though the REST payload uses camelCase.
        resource_name = f"customers/{self.customer_id}/experiments/{experiment_id}"
        self._mutate("experiments", {
            "update": {"resourceName": resource_name, **payload},
            "updateMask": {"paths": update_mask},
        })
        return {"success": True, "experiment_id": experiment_id}

    def delete_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Remove one Experiment through ExperimentService."""
        experiment_id = self._numeric_id(experiment_id, "experiment_id")
        self._mutate("experiments", {
            "remove": f"customers/{self.customer_id}/experiments/{experiment_id}"
        })
        return {"success": True, "experiment_id": experiment_id}

    def _experiment_action(self, action: str, experiment_id: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        experiment_id = self._numeric_id(experiment_id, "experiment_id")
        endpoint = f"customers/{self.customer_id}/experiments/{experiment_id}:{action}"
        response = self.request_raw("POST", endpoint, data=extra or {})
        status = response.get("status_code", 200)
        if status not in (200, 201, 202):
            raise APIError(
                f"Google Experiment {action} returned HTTP {status}",
                status_code=status, response=response,
            )
        return {
            "success": True,
            "experiment_id": experiment_id,
            "operation": action,
            "response": self._response_payload(response),
        }

    def schedule_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._experiment_action("schedule", experiment_id)

    def end_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._experiment_action("end", experiment_id)

    def graduate_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._experiment_action("graduate", experiment_id)

    def promote_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._experiment_action("promote", experiment_id)

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
    def _build_bidding_scheme(
        cls, strategy: dict[str, Any], *, require_type: bool = True
    ) -> tuple[str, dict[str, Any], list[str]]:
        """Translate stable strategy fields to one Google bidding scheme."""
        strategy_type = str(strategy.get("strategy_type") or "").strip().upper()
        if require_type and strategy_type not in cls.BIDDING_STRATEGY_TYPES:
            raise ValueError(
                f"strategy_type must be one of {sorted(cls.BIDDING_STRATEGY_TYPES)}"
            )
        if not strategy_type:
            raise ValueError("strategy_type is required when changing bid settings")

        def positive_number(field: str, *, maximum: float | None = None) -> Any:
            value = strategy.get(field)
            if value is None:
                raise ValueError(f"{field} is required for {strategy_type}")
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field} must be a positive number") from exc
            if value <= 0 or (maximum is not None and value > maximum):
                limit = f" and at most {maximum}" if maximum is not None else ""
                raise ValueError(f"{field} must be greater than 0{limit}")
            return int(value) if field.endswith("_micros") else value

        def optional_micros(fields: tuple[str, ...]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for field in fields:
                value = strategy.get(field)
                if value is None:
                    continue
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{field} must be a non-negative integer") from exc
                if value < 0:
                    raise ValueError(f"{field} must be a non-negative integer")
                result[cls._camel_case(field)] = value
            return result

        if strategy_type == "MANUAL_CPC":
            scheme_key = "manualCpc"
            scheme = {}
            if strategy.get("enhanced_cpc_enabled") is not None:
                if not isinstance(strategy["enhanced_cpc_enabled"], bool):
                    raise ValueError("enhanced_cpc_enabled must be boolean")
                scheme["enhancedCpcEnabled"] = strategy["enhanced_cpc_enabled"]
            paths = ["manualCpc.enhancedCpcEnabled"] if scheme else []
        elif strategy_type == "MAXIMIZE_CONVERSIONS":
            scheme_key = "maximizeConversions"
            scheme = optional_micros(("cpc_bid_ceiling_micros", "cpc_bid_floor_micros"))
            if strategy.get("target_cpa_micros") is not None:
                scheme["targetCpaMicros"] = positive_number("target_cpa_micros")
            paths = [f"maximizeConversions.{key}" for key in scheme]
        elif strategy_type == "MAXIMIZE_CONVERSION_VALUE":
            scheme_key = "maximizeConversionValue"
            scheme = optional_micros(("cpc_bid_ceiling_micros", "cpc_bid_floor_micros"))
            if strategy.get("target_roas") is not None:
                scheme["targetRoas"] = positive_number("target_roas", maximum=1000.0)
            paths = [f"maximizeConversionValue.{key}" for key in scheme]
        elif strategy_type == "TARGET_CPA":
            scheme_key = "targetCpa"
            scheme = {
                "targetCpaMicros": positive_number("target_cpa_micros"),
                **optional_micros(("cpc_bid_ceiling_micros", "cpc_bid_floor_micros")),
            }
            paths = [f"targetCpa.{key}" for key in scheme]
        elif strategy_type == "TARGET_ROAS":
            scheme_key = "targetRoas"
            scheme = {
                "targetRoas": positive_number("target_roas", maximum=1000.0),
                **optional_micros(("cpc_bid_ceiling_micros", "cpc_bid_floor_micros")),
            }
            paths = [f"targetRoas.{key}" for key in scheme]
        else:
            scheme_key = "targetImpressionShare"
            location = str(
                strategy.get("target_impression_share_location") or ""
            ).strip().upper()
            if location not in cls.TARGET_IMPRESSION_SHARE_LOCATIONS:
                raise ValueError(
                    "target_impression_share_location must be one of "
                    f"{sorted(cls.TARGET_IMPRESSION_SHARE_LOCATIONS)}"
                )
            share = strategy.get("target_impression_share")
            try:
                share = float(share)
            except (TypeError, ValueError) as exc:
                raise ValueError("target_impression_share must be between 0 and 1") from exc
            if not 0 < share <= 1:
                raise ValueError("target_impression_share must be between 0 and 1")
            scheme = {
                "location": location,
                "locationFractionMicros": int(share * 1_000_000),
                "cpcBidCeilingMicros": positive_number("cpc_bid_ceiling_micros"),
            }
            paths = [f"targetImpressionShare.{key}" for key in scheme]
        return scheme_key, scheme, paths

    def create_bidding_strategy(self, strategy: dict[str, Any]) -> str:
        """Create a Google Ads portfolio BiddingStrategy."""
        if not isinstance(strategy, dict):
            raise ValueError("strategy must be an object")
        name = str(strategy.get("name") or "").strip()
        if not name:
            raise ValueError("bidding strategy name is required")
        if len(name) > 255:
            raise ValueError("bidding strategy name must be at most 255 characters")
        scheme_key, scheme, _paths = self._build_bidding_scheme(strategy)
        response = self._mutate("biddingStrategies", {
            "create": {"name": name, scheme_key: scheme},
        })
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(
                f"BiddingStrategy mutate returned no resource name: {response}"
            )
        return str(resource_name.rsplit("/", 1)[-1])

    def update_bidding_strategy(
        self, bidding_strategy_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a strategy name or verified mutable portfolio bid fields."""
        bidding_strategy_id = self._numeric_id(
            bidding_strategy_id, "bidding_strategy_id"
        )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        allowed = {
            "name", "strategy_type", "target_cpa_micros", "target_roas",
            "target_impression_share", "target_impression_share_location",
            "cpc_bid_ceiling_micros", "cpc_bid_floor_micros",
            "enhanced_cpc_enabled",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(
                f"Unsupported Google BiddingStrategy update fields: {sorted(unknown)}"
            )

        resource: dict[str, Any] = {
            "resourceName": (
                f"customers/{self.customer_id}/biddingStrategies/"
                f"{bidding_strategy_id}"
            )
        }
        update_paths: list[str] = []
        if updates.get("name") is not None:
            name = str(updates["name"]).strip()
            if not name:
                raise ValueError("name must not be empty")
            if len(name) > 255:
                raise ValueError("name must be at most 255 characters")
            resource["name"] = name
            update_paths.append("name")

        setting_updates = {
            key: value for key, value in updates.items()
            if key not in {"name", "strategy_type"}
        }
        if setting_updates:
            scheme_key, scheme, paths = self._build_bidding_scheme(
                updates, require_type=True
            )
            resource[scheme_key] = scheme
            update_paths.extend(paths)
        if not update_paths:
            raise ValueError("updates must contain a supported non-null field")
        self._mutate("biddingStrategies", {
            "update": resource,
            "updateMask": {"paths": update_paths},
        })
        return {"success": True, "bidding_strategy_id": bidding_strategy_id}

    def delete_bidding_strategy(self, bidding_strategy_id: str) -> dict[str, Any]:
        """Remove one Google Ads portfolio BiddingStrategy."""
        bidding_strategy_id = self._numeric_id(
            bidding_strategy_id, "bidding_strategy_id"
        )
        self._mutate("biddingStrategies", {
            "remove": (
                f"customers/{self.customer_id}/biddingStrategies/"
                f"{bidding_strategy_id}"
            )
        })
        return {"success": True, "bidding_strategy_id": bidding_strategy_id}

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

    def create_user_list(self, user_list: dict[str, Any]) -> str:
        """Create a first-party CRM-based UserList.

        The provider owns the wire translation here.  The Capability only
        exposes the stable business contract, while this method maps it to
        ``UserList.crmBasedUserList`` and the customer-level mutate endpoint.
        """
        if not isinstance(user_list, dict):
            raise ValueError("user_list must be an object")
        name = str(user_list.get("name") or "").strip()
        if not name:
            raise ValueError("user list name is required")
        if len(name) > 255:
            raise ValueError("user list name must be at most 255 characters")

        description = user_list.get("description")
        if description is not None:
            description = str(description).strip()
            if len(description) > 1000:
                raise ValueError("user list description must be at most 1000 characters")

        membership_life_span = user_list.get("membership_life_span", 540)
        try:
            membership_life_span = int(membership_life_span)
        except (TypeError, ValueError) as exc:
            raise ValueError("membership_life_span must be an integer from 0 to 540") from exc
        if not 0 <= membership_life_span <= 540:
            raise ValueError("membership_life_span must be an integer from 0 to 540")

        upload_key_type = str(
            user_list.get("upload_key_type") or "CONTACT_INFO"
        ).strip().upper()
        if upload_key_type not in self.USER_LIST_UPLOAD_KEY_TYPES:
            raise ValueError(
                f"upload_key_type must be one of {sorted(self.USER_LIST_UPLOAD_KEY_TYPES)}"
            )
        data_source_type = str(
            user_list.get("data_source_type") or "FIRST_PARTY"
        ).strip().upper()
        if data_source_type not in self.USER_LIST_DATA_SOURCE_TYPES:
            raise ValueError(
                f"data_source_type must be one of {sorted(self.USER_LIST_DATA_SOURCE_TYPES)}"
            )
        app_id = user_list.get("app_id")
        if upload_key_type == "MOBILE_ADVERTISING_ID" and not str(app_id or "").strip():
            raise ValueError("app_id is required for MOBILE_ADVERTISING_ID user lists")

        crm_based_user_list: dict[str, Any] = {
            "uploadKeyType": upload_key_type,
            "dataSourceType": data_source_type,
        }
        if app_id is not None:
            app_id = str(app_id).strip()
            if app_id:
                crm_based_user_list["appId"] = app_id
        payload: dict[str, Any] = {
            "name": name,
            "membershipLifeSpan": membership_life_span,
            "crmBasedUserList": crm_based_user_list,
        }
        if description:
            payload["description"] = description
        if user_list.get("integration_code") is not None:
            integration_code = str(user_list["integration_code"]).strip()
            if integration_code:
                payload["integrationCode"] = integration_code
        if user_list.get("eligible_for_search") is not None:
            payload["eligibleForSearch"] = bool(user_list["eligible_for_search"])

        response = self._mutate("userLists", {"create": payload})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"UserList mutate returned no resource name: {response}")
        return str(resource_name.rsplit("/", 1)[-1])

    def update_user_list(
        self, user_list_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the verified mutable fields of a UserList."""
        user_list_id = self._numeric_id(user_list_id, "user_list_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.USER_LIST_UPDATE_FIELDS
        if unknown:
            raise ValueError(
                f"Unsupported Google UserList update fields: {sorted(unknown)}"
            )

        normalized: dict[str, Any] = {}
        update_paths: list[str] = []
        for key, value in updates.items():
            if value is None:
                continue
            if key in {"name", "description", "integration_code"}:
                value = str(value).strip()
                if key == "name" and not value:
                    raise ValueError("name must not be empty")
                if key == "name" and len(value) > 255:
                    raise ValueError("name must be at most 255 characters")
                if key == "description" and len(value) > 1000:
                    raise ValueError("description must be at most 1000 characters")
            elif key == "membership_life_span":
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("membership_life_span must be an integer from 0 to 540") from exc
                if not 0 <= value <= 540:
                    raise ValueError("membership_life_span must be an integer from 0 to 540")
            elif key == "eligible_for_search":
                if not isinstance(value, bool):
                    raise ValueError("eligible_for_search must be boolean")
            wire_key = self._camel_case(key)
            normalized[wire_key] = value
            update_paths.append(wire_key)
        if not normalized:
            raise ValueError("updates must contain a supported non-null field")

        resource_name = f"customers/{self.customer_id}/userLists/{user_list_id}"
        self._mutate("userLists", {
            "update": {"resourceName": resource_name, **normalized},
            "updateMask": {"paths": update_paths},
        })
        return {"success": True, "user_list_id": user_list_id}

    def delete_user_list(self, user_list_id: str) -> dict[str, Any]:
        """Remove one Google Ads UserList."""
        user_list_id = self._numeric_id(user_list_id, "user_list_id")
        self._mutate("userLists", {
            "remove": f"customers/{self.customer_id}/userLists/{user_list_id}"
        })
        return {"success": True, "user_list_id": user_list_id}

    @classmethod
    def _read_hashed_user_list_file(cls, file_path: str) -> tuple[list[dict[str, Any]], int]:
        """Read a strict hashed Customer Match CSV/TSV without retaining raw IDs."""
        path = Path(str(file_path or "")).expanduser()
        if path.suffix.lower() not in {".csv", ".tsv"}:
            raise ValueError("file_path must point to a .csv or .tsv file")
        if not path.is_file():
            raise ValueError("file_path must point to an existing regular file")
        if path.stat().st_size > cls.MAX_USER_LIST_UPLOAD_BYTES:
            raise ValueError("user list upload file is too large")

        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        operations: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            try:
                header = [str(item or "").strip() for item in next(reader)]
            except StopIteration as exc:
                raise ValueError("user list upload file must have a header") from exc
            if not header or any(not item for item in header):
                raise ValueError("user list upload header contains an empty column")
            if len(header) != len(set(header)):
                raise ValueError("user list upload header must not contain duplicates")
            unknown = set(header) - cls.USER_LIST_UPLOAD_COLUMNS
            if unknown or not set(header):
                raise ValueError(
                    "user list upload columns may only be hashed_email and hashed_phone_number"
                )

            rows_read = 0
            for row in reader:
                rows_read += 1
                if rows_read > cls.MAX_USER_LIST_UPLOAD_ROWS:
                    raise ValueError("user list upload contains too many rows")
                if len(row) != len(header):
                    raise ValueError(f"user list upload row {rows_read} has the wrong number of columns")
                identifiers: list[dict[str, str]] = []
                for column, value in zip(header, row):
                    value = str(value or "").strip()
                    if not value:
                        continue
                    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
                        raise ValueError(
                            f"user list upload row {rows_read} contains a non-SHA-256 {column} value"
                        )
                    identifiers.append({GoogleAdsAPIClient._camel_case(column): value.lower()})
                if identifiers:
                    operations.append({"create": {"userIdentifiers": identifiers}})
            if not operations:
                raise ValueError("user list upload file contains no hashed identifiers")
        return operations, len(operations)

    def upload_user_list_data(
        self, user_list_id: str, file_path: str
    ) -> dict[str, Any]:
        """Upload hashed Customer Match identifiers through an offline job.

        Only SHA-256 hex values in CSV/TSV columns named ``hashed_email`` and
        ``hashed_phone_number`` are accepted.  The method never returns the
        uploaded identifiers or the source file contents.
        """
        user_list_id = self._numeric_id(user_list_id, "user_list_id")
        operations, row_count = self._read_hashed_user_list_file(file_path)
        user_list_resource = f"customers/{self.customer_id}/userLists/{user_list_id}"

        create_response = self.request_raw(
            "POST",
            f"{self.BASE_URL}/customers/{self.customer_id}/offlineUserDataJobs:create",
            data={
                "job": {
                    "type": "CUSTOMER_MATCH_USER_LIST",
                    "customerMatchUserListMetadata": {
                        "userList": user_list_resource,
                    },
                }
            },
        )
        create_status = create_response.get("status_code", 200)
        if create_status not in (200, 201, 202):
            raise APIError(
                f"Google OfflineUserDataJob create returned HTTP {create_status}",
                status_code=create_status, response=create_response,
            )
        job_resource = self._response_payload(create_response).get("resourceName", "")
        if not job_resource:
            raise APIError("OfflineUserDataJob create returned no resource name")

        add_response = self.request_raw(
            "POST", f"{job_resource}:addOperations",
            data={"operations": operations},
        )
        add_status = add_response.get("status_code", 200)
        if add_status not in (200, 201, 202):
            raise APIError(
                f"Google OfflineUserDataJob addOperations returned HTTP {add_status}",
                status_code=add_status, response=add_response,
            )

        run_response = self.request_raw("POST", f"{job_resource}:run", data={})
        run_status = run_response.get("status_code", 200)
        if run_status not in (200, 201, 202):
            raise APIError(
                f"Google OfflineUserDataJob run returned HTTP {run_status}",
                status_code=run_status, response=run_response,
            )
        job_id = str(job_resource).rsplit("/", 1)[-1]
        return {
            "success": True,
            "job_id": job_id,
            "job_resource_name": str(job_resource),
            "user_list_id": user_list_id,
            "rows_uploaded": row_count,
            "status": "RUNNING",
        }
    
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

    def update_keyword(
        self, ad_group_id: str, criterion_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update mutable fields on one Google AdGroupCriterion keyword."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        criterion_id = self._numeric_id(criterion_id, "criterion_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.KEYWORD_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported Google keyword update fields: {sorted(unknown)}")

        normalized = {key: value for key, value in updates.items() if value is not None}
        if not normalized:
            raise ValueError("updates must contain at least one non-null field")
        if "status" in normalized:
            normalized["status"] = str(normalized["status"]).upper()
            if normalized["status"] not in {"ENABLED", "PAUSED"}:
                raise ValueError("keyword status must be ENABLED or PAUSED")
        if "cpc_bid" in normalized:
            try:
                normalized["cpc_bid_micros"] = int(
                    float(normalized.pop("cpc_bid")) * 1_000_000
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("cpc_bid must be a non-negative number") from exc
        if "cpc_bid_micros" in normalized:
            try:
                normalized["cpc_bid_micros"] = int(normalized["cpc_bid_micros"])
            except (TypeError, ValueError) as exc:
                raise ValueError("cpc_bid_micros must be a non-negative integer") from exc
            if normalized["cpc_bid_micros"] < 0:
                raise ValueError("cpc_bid_micros must be a non-negative integer")

        resource_name = (
            f"customers/{self.customer_id}/adGroupCriteria/"
            f"{ad_group_id}~{criterion_id}"
        )
        patch = {"resourceName": resource_name, **normalized}
        self._mutate("adGroupCriteria", {
            "update": self._camel_case_keys(patch),
            "updateMask": {
                "paths": [self._camel_case(key) for key in normalized],
            },
        })
        return {"success": True, "ad_group_id": ad_group_id, "keyword_id": criterion_id}

    def delete_keyword(self, ad_group_id: str, criterion_id: str) -> dict[str, Any]:
        """Remove one Google AdGroupCriterion keyword."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        criterion_id = self._numeric_id(criterion_id, "criterion_id")
        resource_name = (
            f"customers/{self.customer_id}/adGroupCriteria/"
            f"{ad_group_id}~{criterion_id}"
        )
        self._mutate("adGroupCriteria", {"remove": resource_name})
        return {"success": True, "ad_group_id": ad_group_id, "keyword_id": criterion_id}

    def create_product_group(
        self,
        ad_group_id: str,
        product_group_type: str,
        value: Any = None,
        partition_type: str = "UNIT",
        parent_criterion_id: str = None,
        cpc_bid_micros: int = None,
        bidding_category_level: str = "LEVEL1",
    ) -> dict[str, Any]:
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
        # ``AdGroupCriterion`` resource names use the composite
        # ``ad_group_id~criterion_id`` key.  The Tool contract exposes the
        # criterion ID separately because the parent ad group is already an
        # explicit input to get/update/delete, matching keyword lifecycle
        # methods and the GAQL ``criterion_id`` field.
        return str(resource_name).rsplit("/", 1)[-1].rsplit("~", 1)[-1]

    def _product_group_query(self, where: str = "") -> str:
        """Return the GAQL projection for Standard Shopping listing groups."""
        query = (
            "SELECT ad_group.id, ad_group_criterion.criterion_id, "
            "ad_group_criterion.resource_name, ad_group_criterion.status, "
            "ad_group_criterion.cpc_bid_micros, "
            "ad_group_criterion.listing_group.type, "
            "ad_group_criterion.listing_group.parent_ad_group_criterion, "
            "ad_group_criterion.listing_group.case_value.product_brand.value, "
            "ad_group_criterion.listing_group.case_value.product_bidding_category.id, "
            "ad_group_criterion.listing_group.case_value.product_bidding_category.level, "
            "ad_group_criterion.listing_group.case_value.product_channel.channel, "
            "ad_group_criterion.listing_group.case_value.product_condition.condition, "
            "ad_group_criterion.listing_group.case_value.product_custom_label.index, "
            "ad_group_criterion.listing_group.case_value.product_custom_label.value, "
            "ad_group_criterion.listing_group.case_value.product_item_id.value, "
            "ad_group_criterion.listing_group.case_value.product_type.level, "
            "ad_group_criterion.listing_group.case_value.product_type.value "
            "FROM ad_group_criterion"
        )
        filters = ["ad_group_criterion.type = LISTING_GROUP"]
        if where:
            filters.append(where)
        return f"{query} WHERE {' AND '.join(filters)}"

    @classmethod
    def _normalize_product_group(cls, row: dict) -> dict[str, Any]:
        """Flatten a Google listing-group criterion for the Tool contract."""
        criterion = row.get("adGroupCriterion", row.get("ad_group_criterion", {})) or {}
        ad_group = row.get("adGroup", row.get("ad_group", {})) or {}
        listing = criterion.get("listingGroup", criterion.get("listing_group", {})) or {}
        case = listing.get("caseValue", listing.get("case_value", {})) or {}

        def nested(value: dict, *keys: str) -> Any:
            current: Any = value
            for key in keys:
                if not isinstance(current, dict):
                    return None
                current = current.get(key, current.get(cls._camel_case(key)))
            return current

        dimensions = (
            ("productType", "product_type", "product_type"),
            ("productBrand", "product_brand", "brand"),
            ("productCondition", "product_condition", "condition"),
            ("productCustomLabel", "product_custom_label", "custom_label"),
            ("productChannel", "product_channel", "channel"),
            ("productItemId", "product_item_id", "item_id"),
            ("productBiddingCategory", "product_bidding_category", "bidding_category"),
        )
        product_group_type = "all_products"
        value: Any = None
        for camel_key, snake_key, dimension in dimensions:
            detail = case.get(camel_key, case.get(snake_key))
            if not isinstance(detail, dict):
                continue
            product_group_type = dimension
            if dimension == "product_type":
                level = nested(detail, "level")
                if level:
                    product_group_type = f"product_type_{str(level).upper().replace('LEVEL', '')}"
                value = nested(detail, "value")
            elif dimension == "custom_label":
                index = nested(detail, "index")
                if index:
                    product_group_type = f"custom_label_{str(index).upper().replace('INDEX', '')}"
                value = nested(detail, "value")
            elif dimension == "bidding_category":
                value = nested(detail, "id")
            elif dimension == "condition":
                value = nested(detail, "condition")
            elif dimension == "channel":
                value = nested(detail, "channel")
            else:
                value = nested(detail, "value")
            break

        resource_name = criterion.get("resourceName", criterion.get("resource_name"))
        criterion_id = criterion.get("criterionId", criterion.get("criterion_id"))
        return {
            "id": criterion_id,
            "product_group_id": criterion_id,
            "ad_group_id": ad_group.get("id"),
            "resource_name": resource_name,
            "status": criterion.get("status"),
            "cpc_bid_micros": criterion.get(
                "cpcBidMicros", criterion.get("cpc_bid_micros")
            ),
            "partition_type": listing.get("type"),
            "product_group_type": product_group_type,
            "value": value,
            "parent_criterion_id": listing.get(
                "parentAdGroupCriterion", listing.get("parent_ad_group_criterion")
            ),
        }

    def list_product_groups(self, ad_group_id: str, page_size: int = 100) -> list[dict]:
        """List Standard Shopping listing-group criteria under one ad group."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        rows = self._search_all(
            self._product_group_query(f"ad_group.id = {ad_group_id}"),
            page_size=page_size,
        )
        return [self._normalize_product_group(row) for row in rows]

    def get_product_group(self, ad_group_id: str, product_group_id: str) -> dict:
        """Get one Standard Shopping listing-group criterion."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        product_group_id = self._numeric_id(product_group_id, "product_group_id")
        rows = self._search_all(
            self._product_group_query(
                f"ad_group.id = {ad_group_id} "
                f"AND ad_group_criterion.criterion_id = {product_group_id}"
            ),
            page_size=1,
        )
        if not rows:
            raise APIError(
                f"Google product group {ad_group_id}~{product_group_id} was not found"
            )
        return self._normalize_product_group(rows[0])

    def update_product_group(
        self, ad_group_id: str, product_group_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update mutable fields on one listing-group criterion."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        product_group_id = self._numeric_id(product_group_id, "product_group_id")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - self.PRODUCT_GROUP_UPDATE_FIELDS
        if unknown:
            raise ValueError(
                f"Unsupported Google product group update fields: {sorted(unknown)}"
            )
        normalized = {key: value for key, value in updates.items() if value is not None}
        if not normalized:
            raise ValueError("updates must contain at least one non-null field")
        if "status" in normalized:
            normalized["status"] = str(normalized["status"]).upper()
            if normalized["status"] not in {"ENABLED", "PAUSED", "REMOVED"}:
                raise ValueError("product group status must be ENABLED, PAUSED or REMOVED")
        if "cpc_bid" in normalized:
            try:
                normalized["cpc_bid_micros"] = int(
                    float(normalized.pop("cpc_bid")) * 1_000_000
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("cpc_bid must be a non-negative number") from exc
        if "cpc_bid_micros" in normalized:
            try:
                normalized["cpc_bid_micros"] = int(normalized["cpc_bid_micros"])
            except (TypeError, ValueError) as exc:
                raise ValueError("cpc_bid_micros must be a non-negative integer") from exc
            if normalized["cpc_bid_micros"] < 0:
                raise ValueError("cpc_bid_micros must be a non-negative integer")

        resource_name = (
            f"customers/{self.customer_id}/adGroupCriteria/"
            f"{ad_group_id}~{product_group_id}"
        )
        self._mutate("adGroupCriteria", {
            "update": self._camel_case_keys({"resourceName": resource_name, **normalized}),
            "updateMask": {
                "paths": [self._camel_case(key) for key in normalized],
            },
        })
        return {
            "success": True,
            "ad_group_id": ad_group_id,
            "product_group_id": product_group_id,
        }

    def delete_product_group(self, ad_group_id: str, product_group_id: str) -> dict[str, Any]:
        """Remove one Standard Shopping listing-group criterion."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        product_group_id = self._numeric_id(product_group_id, "product_group_id")
        resource_name = (
            f"customers/{self.customer_id}/adGroupCriteria/"
            f"{ad_group_id}~{product_group_id}"
        )
        self._mutate("adGroupCriteria", {"remove": resource_name})
        return {
            "success": True,
            "ad_group_id": ad_group_id,
            "product_group_id": product_group_id,
        }

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

    @classmethod
    def _read_asset_file(cls, file_path: str, *, allowed_suffixes: set[str]) -> bytes:
        path = Path(str(file_path or "")).expanduser()
        if path.suffix.lower() not in allowed_suffixes:
            suffixes = ", ".join(sorted(allowed_suffixes))
            raise ValueError(f"file_path must use one of: {suffixes}")
        if not path.is_file():
            raise ValueError("file_path must point to an existing regular file")
        if path.stat().st_size > cls.MAX_ASSET_UPLOAD_BYTES:
            raise ValueError("asset upload file is too large")
        return path.read_bytes()

    def create_asset(self, asset: dict[str, Any]) -> str:
        """Create a reusable Google Asset through AssetService.

        AssetService accepts text, image, YouTube video and HTML5 media
        bundle assets.  Text is sent as text content; binary assets are read
        from a caller-selected local file and encoded only for the provider
        request.  Assets are immutable after creation in the Google Ads API.
        """
        if not isinstance(asset, dict):
            raise ValueError("asset must be an object")
        asset_type = str(asset.get("asset_type") or "").strip().upper()
        if asset_type not in self.ASSET_TYPES:
            raise ValueError(f"asset_type must be one of {sorted(self.ASSET_TYPES)}")
        payload: dict[str, Any] = {}
        if asset.get("name") is not None:
            name = str(asset["name"]).strip()
            if not name:
                raise ValueError("name must not be empty")
            if len(name) > 255:
                raise ValueError("name must be at most 255 characters")
            payload["name"] = name
        if asset.get("final_urls") is not None:
            final_urls = asset["final_urls"]
            if not isinstance(final_urls, list) or not final_urls:
                raise ValueError("final_urls must be a non-empty list when provided")
            payload["finalUrls"] = [str(url).strip() for url in final_urls]
        if asset.get("final_mobile_urls") is not None:
            final_mobile_urls = asset["final_mobile_urls"]
            if not isinstance(final_mobile_urls, list):
                raise ValueError("final_mobile_urls must be a list")
            payload["finalMobileUrls"] = [str(url).strip() for url in final_mobile_urls]
        if asset.get("tracking_url_template") is not None:
            payload["trackingUrlTemplate"] = str(asset["tracking_url_template"]).strip()
        if asset.get("final_url_suffix") is not None:
            payload["finalUrlSuffix"] = str(asset["final_url_suffix"]).strip()

        if asset_type == "TEXT":
            text = str(asset.get("text") or "").strip()
            if not text:
                raise ValueError("text is required for TEXT assets")
            payload["textAsset"] = {"text": text}
        elif asset_type == "YOUTUBE_VIDEO":
            video_id = str(asset.get("youtube_video_id") or "").strip()
            video_title = str(asset.get("youtube_video_title") or "").strip()
            if not video_id or not video_title:
                raise ValueError(
                    "youtube_video_id and youtube_video_title are required for YOUTUBE_VIDEO assets"
                )
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                raise ValueError("youtube_video_id must be an 11-character YouTube ID")
            payload["youtubeVideoAsset"] = {
                "youtubeVideoId": video_id,
                "youtubeVideoTitle": video_title,
            }
        else:
            file_path = asset.get("file_path")
            if asset_type == "IMAGE":
                mime_type = str(asset.get("mime_type") or "").strip().upper()
                if mime_type not in {"IMAGE_JPEG", "IMAGE_GIF", "IMAGE_PNG"}:
                    raise ValueError(
                        "mime_type must be IMAGE_JPEG, IMAGE_GIF or IMAGE_PNG for IMAGE assets"
                    )
                suffixes = {
                    "IMAGE_JPEG": {".jpg", ".jpeg"},
                    "IMAGE_GIF": {".gif"},
                    "IMAGE_PNG": {".png"},
                }[mime_type]
                raw = self._read_asset_file(file_path, allowed_suffixes=suffixes)
                payload["imageAsset"] = {
                    "data": base64.b64encode(raw).decode("ascii"),
                    "fileSize": len(raw),
                    "mimeType": mime_type,
                }
            else:
                raw = self._read_asset_file(file_path, allowed_suffixes={".zip"})
                payload["mediaBundleAsset"] = {
                    "data": base64.b64encode(raw).decode("ascii"),
                }

        response = self._mutate("assets", {"create": payload})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"Asset mutate returned no resource name: {response}")
        return str(resource_name.rsplit("/", 1)[-1])

    def delete_asset(self, asset_id: str, customer_id: str = None) -> dict:
        """Remove a reusable customer-level Asset through AssetService.

        Google Ads Assets are immutable in content. Removal is a separate
        mutate operation and is rejected while the asset is still referenced.
        """
        asset_id = self._numeric_id(asset_id, "asset_id")
        scoped = self.for_customer(customer_id) if customer_id else self
        if not str(scoped.customer_id or "").strip():
            raise ValueError("customer_id is required to remove an asset")
        resource_name = f"customers/{scoped.customer_id}/assets/{asset_id}"
        scoped._mutate("assets", {"remove": resource_name})
        return {"success": True, "asset_id": asset_id}

    def _customer_resource_name(
        self, value: Any, collection: str, field_name: str
    ) -> str:
        """Normalize an ID/resource name and enforce the current customer scope."""
        value = str(value or "").strip()
        customer = self._numeric_id(self.customer_id, "customer_id")
        if re.fullmatch(r"\d+", value):
            return f"customers/{customer}/{collection}/{value}"
        match = re.fullmatch(
            rf"customers/(\d+)/{re.escape(collection)}/(\d+)", value
        )
        if match:
            if match.group(1) != customer:
                raise ValueError(f"{field_name} belongs to another customer")
            return value
        raise ValueError(
            f"{field_name} must be a numeric ID or a customer-scoped "
            f"{collection} resource name"
        )

    @staticmethod
    def _normalize_asset_link(row: dict, resource_key: str) -> dict:
        """Normalize a CampaignAsset/AssetGroupAsset GAQL row."""
        snake_key = {
            "campaignAsset": "campaign_asset",
            "assetGroupAsset": "asset_group_asset",
        }.get(resource_key, resource_key)
        link = row.get(resource_key, row.get(snake_key, row)) or {}

        def value(*keys: str) -> Any:
            current: Any = link
            for key in keys:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
                if current is None:
                    current = link.get(GoogleAdsAPIClient._camel_case(key))
            return current

        return {
            "resource_name": value("resource_name"),
            "campaign": value("campaign"),
            "asset_group": value("asset_group"),
            "asset": value("asset"),
            "field_type": value("field_type"),
            "status": value("status"),
            "primary_status": value("primary_status"),
            "primary_status_reasons": value("primary_status_reasons") or [],
        }

    def list_campaign_assets(
        self, campaign_id: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List assets attached to one Campaign through GAQL."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        query = (
            "SELECT campaign_asset.resource_name, campaign_asset.campaign, "
            "campaign_asset.asset, campaign_asset.field_type, campaign_asset.status, "
            "campaign_asset.primary_status, campaign_asset.primary_status_reasons "
            "FROM campaign_asset "
            f"WHERE campaign.id = {campaign_id}"
        )
        return [
            self._normalize_asset_link(row, "campaignAsset")
            for row in self._search_all(query, page_size=page_size)
        ]

    def create_campaign_asset(
        self, campaign_id: str, asset_id: str, field_type: str
    ) -> str:
        """Attach one reusable Asset to a Campaign."""
        campaign = self._customer_resource_name(campaign_id, "campaigns", "campaign_id")
        asset = self._customer_resource_name(asset_id, "assets", "asset_id")
        field_type = str(field_type or "").strip().upper()
        if field_type not in self.CAMPAIGN_ASSET_FIELD_TYPES:
            raise ValueError(
                f"field_type must be one of {sorted(self.CAMPAIGN_ASSET_FIELD_TYPES)}"
            )
        response = self._mutate("campaignAssets", {"create": {
            "campaign": campaign,
            "asset": asset,
            "fieldType": field_type,
        }})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"CampaignAsset mutate returned no resource name: {response}")
        return str(resource_name)

    def delete_campaign_asset(
        self, campaign_id: str, asset_id: str, field_type: str
    ) -> dict[str, Any]:
        """Remove one Campaign-to-Asset association."""
        campaign = self._customer_resource_name(campaign_id, "campaigns", "campaign_id")
        asset = self._customer_resource_name(asset_id, "assets", "asset_id")
        field_type = str(field_type or "").strip().upper()
        if field_type not in self.CAMPAIGN_ASSET_FIELD_TYPES:
            raise ValueError(
                f"field_type must be one of {sorted(self.CAMPAIGN_ASSET_FIELD_TYPES)}"
            )
        campaign_number = campaign.rsplit("/", 1)[-1]
        asset_number = asset.rsplit("/", 1)[-1]
        resource_name = (
            f"customers/{self.customer_id}/campaignAssets/"
            f"{campaign_number}~{asset_number}~{field_type}"
        )
        self._mutate("campaignAssets", {"remove": resource_name})
        return {
            "success": True,
            "campaign_id": campaign_number,
            "asset_id": asset_number,
            "field_type": field_type,
            "resource_name": resource_name,
        }

    def list_asset_group_assets(
        self, asset_group_id: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List assets attached to one PMax AssetGroup through GAQL."""
        asset_group_id = self._numeric_id(asset_group_id, "asset_group_id")
        query = (
            "SELECT asset_group_asset.resource_name, asset_group_asset.asset_group, "
            "asset_group_asset.asset, asset_group_asset.field_type, "
            "asset_group_asset.status, asset_group_asset.primary_status, "
            "asset_group_asset.primary_status_reasons "
            "FROM asset_group_asset "
            f"WHERE asset_group.id = {asset_group_id}"
        )
        return [
            self._normalize_asset_link(row, "assetGroupAsset")
            for row in self._search_all(query, page_size=page_size)
        ]

    def create_asset_group_asset(
        self, asset_group_id: str, asset_id: str, field_type: str
    ) -> str:
        """Attach one reusable Asset to a PMax AssetGroup."""
        asset_group = self._customer_resource_name(
            asset_group_id, "assetGroups", "asset_group_id"
        )
        asset = self._customer_resource_name(asset_id, "assets", "asset_id")
        field_type = str(field_type or "").strip().upper()
        if field_type not in self.ASSET_GROUP_ASSET_FIELD_TYPES:
            raise ValueError(
                f"field_type must be one of {sorted(self.ASSET_GROUP_ASSET_FIELD_TYPES)}"
            )
        response = self._mutate("assetGroupAssets", {"create": {
            "assetGroup": asset_group,
            "asset": asset,
            "fieldType": field_type,
        }})
        resource_name = self._mutation_resource_name(response)
        if not resource_name:
            raise APIError(f"AssetGroupAsset mutate returned no resource name: {response}")
        return str(resource_name)

    def delete_asset_group_asset(
        self, asset_group_id: str, asset_id: str, field_type: str
    ) -> dict[str, Any]:
        """Remove one PMax AssetGroup-to-Asset association."""
        asset_group = self._customer_resource_name(
            asset_group_id, "assetGroups", "asset_group_id"
        )
        asset = self._customer_resource_name(asset_id, "assets", "asset_id")
        field_type = str(field_type or "").strip().upper()
        if field_type not in self.ASSET_GROUP_ASSET_FIELD_TYPES:
            raise ValueError(
                f"field_type must be one of {sorted(self.ASSET_GROUP_ASSET_FIELD_TYPES)}"
            )
        asset_group_number = asset_group.rsplit("/", 1)[-1]
        asset_number = asset.rsplit("/", 1)[-1]
        resource_name = (
            f"customers/{self.customer_id}/assetGroupAssets/"
            f"{asset_group_number}~{asset_number}~{field_type}"
        )
        self._mutate("assetGroupAssets", {"remove": resource_name})
        return {
            "success": True,
            "asset_group_id": asset_group_number,
            "asset_id": asset_number,
            "field_type": field_type,
            "resource_name": resource_name,
        }

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
        target_impression_share_location: str = None,
        cpc_bid_ceiling_micros: int = None,
        target_cpm_micros: int = None,
        target_cpv_micros: int = None,
        status: str = None,
        networks: list[str] = None,
        app_campaign_setting: dict = None,
        advertising_channel_sub_type: str = None,
        shopping_setting: dict = None,
        campaign_goal_setting: dict = None,
        video_setting: dict = None,
        targeting_setting: dict = None,
        network_setting: dict = None,
        demand_gen_campaign_settings: dict = None,
        hotel_setting: dict = None,
        local_campaign_setting: dict = None,
        travel_campaign_settings: dict = None,
        local_services_campaign_settings: dict = None,
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
        advertising_channel_type = self.CHANNEL_TYPE_ALIASES.get(
            str(advertising_channel_type or "").upper(),
            str(advertising_channel_type or "").upper(),
        )
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
            ('demandGenCampaignSettings', demand_gen_campaign_settings),
            ('hotelSetting', hotel_setting),
            ('localCampaignSetting', local_campaign_setting),
            ('travelCampaignSettings', travel_campaign_settings),
            ('localServicesCampaignSettings', local_services_campaign_settings),
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
        if network_setting is not None:
            if not isinstance(network_setting, dict):
                raise ValueError("network_setting must be an object")
            campaign_data['networkSettings'] = self._camel_case_keys(network_setting)
        if networks:
            selected = {str(network).upper() for network in networks}
            network_settings = dict(campaign_data.get('networkSettings', {}))
            network_settings.update({
                'targetGoogleSearch': 'GOOGLE_SEARCH' in selected,
                'targetSearchNetwork': 'SEARCH_PARTNERS' in selected,
                'targetContentNetwork': 'DISPLAY_NETWORK' in selected,
            })
            # The explicit convenience list supplies the canonical network
            # switches; provider-shaped switches already supplied above are
            # retained for fields not represented by the convenience list.
            network_settings.update(campaign_data.get('networkSettings', {}))
            campaign_data['networkSettings'] = network_settings

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
        if strategy == 'TARGET_CPM' and int(target_cpm_micros or 0) <= 0:
            raise ValueError("TARGET_CPM requires a positive target_cpm_micros")
        if strategy == 'TARGET_CPV' and int(target_cpv_micros or 0) <= 0:
            raise ValueError("TARGET_CPV requires a positive target_cpv_micros")
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
                'location': target_impression_share_location or 'ANYWHERE_ON_PAGE',
                'locationFractionMicros': int(float(
                    0.5 if target_impression_share is None else target_impression_share
                ) * 1_000_000),
            }
            if cpc_bid_ceiling_micros is not None:
                campaign_data['targetImpressionShare']['cpcBidCeilingMicros'] = int(
                    cpc_bid_ceiling_micros
                )
        elif strategy == 'MANUAL_CPM':
            campaign_data['manualCpm'] = {}
        elif strategy == 'MANUAL_CPV':
            campaign_data['manualCpv'] = {}
        elif strategy == 'TARGET_CPM':
            campaign_data['targetCpm'] = {
                'targetCpmMicros': int(target_cpm_micros or 0),
            }
        elif strategy == 'TARGET_CPV':
            campaign_data['targetCpv'] = {
                'targetCpvMicros': int(target_cpv_micros or 0),
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

    def delete_campaign(self, campaign_id: str) -> dict:
        """Remove a Google Ads Campaign through the customer mutate API."""
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        resource_name = f"customers/{self.customer_id}/campaigns/{campaign_id}"
        self._mutate("campaigns", {"remove": resource_name})
        return {"success": True, "campaign_id": campaign_id}

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

    def delete_ad_group(self, ad_group_id: str) -> dict:
        """Remove a Google Ads Ad Group through the customer mutate API."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        resource_name = f"customers/{self.customer_id}/adGroups/{ad_group_id}"
        self._mutate("adGroups", {"remove": resource_name})
        return {"success": True, "ad_group_id": ad_group_id}

    def update_ad(self, ad_id: str, updates: dict) -> dict:
        """Update mutable Google Ads AdGroupAd fields."""
        return self._update_resource(
            "adGroupAds", ad_id, updates,
            self.AD_UPDATE_FIELDS, "ad_id",
        )

    def delete_ad(self, ad_group_id: str, ad_id: str) -> dict:
        """Remove an AdGroupAd using Google's composite resource name."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        ad_id = self._numeric_id(ad_id, "ad_id")
        resource_name = (
            f"customers/{self.customer_id}/adGroupAds/{ad_group_id}~{ad_id}"
        )
        self._mutate("adGroupAds", {"remove": resource_name})
        return {
            "success": True,
            "ad_group_id": ad_group_id,
            "ad_id": ad_id,
        }

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
        demand_gen_ad_group_settings: dict = None,
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
        if demand_gen_ad_group_settings is not None:
            if not isinstance(demand_gen_ad_group_settings, dict):
                raise ValueError("demand_gen_ad_group_settings must be an object")
            ad_group_data['demandGenAdGroupSettings'] = self._camel_case_keys(
                demand_gen_ad_group_settings
            )
        
        resp = self._mutate('adGroups', {'create': ad_group_data})
        resource_name = self._mutation_resource_name(resp)
        if not resource_name:
            raise APIError(f"Ad group mutate returned no resource name: {resp}")
        return str(resource_name.split('/')[-1])

    def _specialized_ad_plan(
        self,
        ad_group_id: str,
        name: str,
        ad_field: str,
        ad_payload: dict[str, Any],
        *,
        final_url: str = None,
        status: str = None,
    ) -> dict[str, Any]:
        """Build a standard v24 AdGroupAd plan for a specialized Ad payload."""
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        if not str(name or "").strip():
            raise ValueError("name is required")
        status = str(status or "PAUSED").upper()
        if status not in {"PAUSED", "ENABLED"}:
            raise ValueError("status must be PAUSED or ENABLED")
        customer = str(self.customer_id or "").strip()
        if not re.fullmatch(r"\d+", customer):
            raise ValueError("customer_id must contain digits only")
        ad: dict[str, Any] = {"name": str(name).strip(), ad_field: ad_payload}
        if final_url:
            ad["finalUrls"] = [str(final_url).strip()]
        ad_group_ad_resource = f"customers/{customer}/adGroupAds/-1"
        operation = {
            "adGroupAds": {
                "create": {
                    "resourceName": ad_group_ad_resource,
                    "adGroup": f"customers/{customer}/adGroups/{ad_group_id}",
                    "status": status,
                    "ad": ad,
                }
            }
        }
        return {
            "ad_resource_name": f"customers/{customer}/ads/-1",
            "ad_group_id": ad_group_id,
            "format": ad_field,
            "operation": operation,
            "execution_status": "planned",
            "mode": "dry_run",
            "live_support": False,
            "requires_verified_live_adapter": True,
        }

    def create_demand_gen_multi_asset_ad(
        self, ad_group_id: str, name: str, final_url: str,
        headlines: list[Any], descriptions: list[Any], business_name: str,
        marketing_images: list[Any] = None, square_marketing_images: list[Any] = None,
        portrait_marketing_images: list[Any] = None, tall_portrait_marketing_images: list[Any] = None,
        classic_display_images: list[Any] = None, logo_images: list[Any] = None,
        call_to_action_text: str = None, status: str = None,
    ) -> dict[str, Any]:
        if not isinstance(headlines, list) or not headlines:
            raise ValueError("headlines must be a non-empty list")
        if not isinstance(descriptions, list) or not descriptions:
            raise ValueError("descriptions must be a non-empty list")
        if not str(business_name or "").strip():
            raise ValueError("business_name is required")
        payload: dict[str, Any] = {
            "headlines": [self._text_asset(item) for item in headlines],
            "descriptions": [self._text_asset(item) for item in descriptions],
            "businessName": business_name,
        }
        for wire_name, values in (
            ("marketingImages", marketing_images), ("squareMarketingImages", square_marketing_images),
            ("portraitMarketingImages", portrait_marketing_images),
            ("tallPortraitMarketingImages", tall_portrait_marketing_images),
            ("classicDisplayImages", classic_display_images), ("logoImages", logo_images),
        ):
            if values:
                payload[wire_name] = [self._asset_reference(item) for item in values]
        if call_to_action_text is not None:
            payload["callToActionText"] = call_to_action_text
        return self._specialized_ad_plan(
            ad_group_id, name, "demandGenMultiAssetAd", payload,
            final_url=final_url, status=status,
        )

    def create_demand_gen_carousel_ad(
        self, ad_group_id: str, name: str, final_url: str,
        headline: str, description: str, carousel_cards: list[dict[str, Any]],
        business_name: str = None, logo_image: Any = None,
        call_to_action_text: str = None, status: str = None,
    ) -> dict[str, Any]:
        if not isinstance(carousel_cards, list) or len(carousel_cards) < 2:
            raise ValueError("carousel_cards must contain at least 2 cards")
        payload: dict[str, Any] = {
            "headline": self._text_asset(headline),
            "description": self._text_asset(description),
            "carouselCards": [self._camel_case_keys(card) for card in carousel_cards],
        }
        if business_name:
            payload["businessName"] = business_name
        if logo_image is not None:
            payload["logoImage"] = self._asset_reference(logo_image)
        if call_to_action_text is not None:
            payload["callToActionText"] = call_to_action_text
        return self._specialized_ad_plan(
            ad_group_id, name, "demandGenCarouselAd", payload,
            final_url=final_url, status=status,
        )

    def create_demand_gen_video_responsive_ad(
        self, ad_group_id: str, name: str, business_name: str,
        videos: list[Any], headlines: list[Any], descriptions: list[Any],
        final_url: str = None, long_headlines: list[Any] = None,
        logo_images: list[Any] = None, companion_banners: list[Any] = None,
        call_to_actions: list[Any] = None, breadcrumb1: str = None,
        breadcrumb2: str = None, status: str = None,
    ) -> dict[str, Any]:
        if not isinstance(videos, list) or not videos:
            raise ValueError("videos must be a non-empty list")
        if not isinstance(headlines, list) or not headlines:
            raise ValueError("headlines must be a non-empty list")
        if not isinstance(descriptions, list) or not descriptions:
            raise ValueError("descriptions must be a non-empty list")
        payload: dict[str, Any] = {
            "businessName": self._text_asset(business_name),
            "videos": [self._asset_reference(item) for item in videos],
            "headlines": [self._text_asset(item) for item in headlines],
            "descriptions": [self._text_asset(item) for item in descriptions],
        }
        for wire_name, values in (
            ("longHeadlines", long_headlines), ("logoImages", logo_images),
            ("companionBanners", companion_banners), ("callToActions", call_to_actions),
        ):
            if values:
                converter = self._text_asset if wire_name == "longHeadlines" else self._asset_reference
                payload[wire_name] = [converter(item) for item in values]
        for wire_name, value in (("breadcrumb1", breadcrumb1), ("breadcrumb2", breadcrumb2)):
            if value is not None:
                payload[wire_name] = value
        return self._specialized_ad_plan(
            ad_group_id, name, "demandGenVideoResponsiveAd", payload,
            final_url=final_url, status=status,
        )

    def create_demand_gen_product_ad(
        self, ad_group_id: str, name: str, headline: Any, description: Any,
        business_name: Any, logo_image: Any, call_to_action: Any,
        final_url: str = None, breadcrumb1: str = None, breadcrumb2: str = None,
        status: str = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "headline": self._text_asset(headline),
            "description": self._text_asset(description),
            "businessName": self._text_asset(business_name),
            "logoImage": self._asset_reference(logo_image),
            "callToAction": self._asset_reference(call_to_action),
        }
        for wire_name, value in (("breadcrumb1", breadcrumb1), ("breadcrumb2", breadcrumb2)):
            if value is not None:
                payload[wire_name] = value
        return self._specialized_ad_plan(
            ad_group_id, name, "demandGenProductAd", payload,
            final_url=final_url, status=status,
        )

    def create_hotel_ad(self, ad_group_id: str, name: str, status: str = None) -> dict[str, Any]:
        return self._specialized_ad_plan(
            ad_group_id, name, "hotelAd", {}, status=status,
        )

    def create_local_ad(
        self, ad_group_id: str, name: str, final_url: str,
        headlines: list[Any], descriptions: list[Any], path1: str = None,
        path2: str = None, logo_images: list[Any] = None, videos: list[Any] = None,
        marketing_images: list[Any] = None, call_to_actions: list[Any] = None,
        status: str = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "headlines": [self._text_asset(item) for item in headlines],
            "descriptions": [self._text_asset(item) for item in descriptions],
        }
        for wire_name, value in (("path1", path1), ("path2", path2)):
            if value is not None:
                payload[wire_name] = value
        for wire_name, values in (
            ("logoImages", logo_images), ("videos", videos),
            ("marketingImages", marketing_images), ("callToActions", call_to_actions),
        ):
            if values:
                payload[wire_name] = [self._asset_reference(item) for item in values]
        return self._specialized_ad_plan(
            ad_group_id, name, "localAd", payload,
            final_url=final_url, status=status,
        )

    def create_smart_campaign_ad(
        self, ad_group_id: str, name: str, final_url: str,
        headlines: list[Any], descriptions: list[Any], status: str = None,
    ) -> dict[str, Any]:
        payload = {
            "headlines": [self._text_asset(item) for item in headlines],
            "descriptions": [self._text_asset(item) for item in descriptions],
        }
        return self._specialized_ad_plan(
            ad_group_id, name, "smartCampaignAd", payload,
            final_url=final_url, status=status,
        )

    def create_travel_ad(self, ad_group_id: str, name: str, status: str = None) -> dict[str, Any]:
        return self._specialized_ad_plan(
            ad_group_id, name, "travelAd", {}, status=status,
        )

    def create_app_ad(
        self,
        ad_group_id: str,
        name: str,
        headlines: list[Any],
        descriptions: list[Any],
        images: list[Any] = None,
        videos: list[Any] = None,
        html5_media_bundles: list[Any] = None,
        status: str = None,
    ) -> dict[str, Any]:
        """Build a Google AppAd mutation plan without provider I/O.

        App campaign creative is an ``Ad.appAd`` payload attached to an App
        campaign Ad Group.  The product deliberately exposes this adapter as
        dry-run-only until the selected test customer has verified the exact
        AssetService/AdGroupAd mutation sequence.  Keeping the provider-shaped
        plan here means that verification later changes this adapter, not the
        Skill, Runtime, or route metadata.
        """
        ad_group_id = self._numeric_id(ad_group_id, "ad_group_id")
        if not str(name or "").strip():
            raise ValueError("name is required")
        if not isinstance(headlines, list) or not 2 <= len(headlines) <= 5:
            raise ValueError("App Ad requires 2 to 5 headlines")
        if not isinstance(descriptions, list) or not 2 <= len(descriptions) <= 5:
            raise ValueError("App Ad requires 2 to 5 descriptions")
        status = str(status or "PAUSED").upper()
        if status not in {"PAUSED", "ENABLED"}:
            raise ValueError("status must be PAUSED or ENABLED")

        app_ad: dict[str, Any] = {
            "headlines": [self._text_asset(item) for item in headlines],
            "descriptions": [self._text_asset(item) for item in descriptions],
        }
        for field_name, values in (
            ("images", images),
            ("youtubeVideos", videos),
            ("html5MediaBundles", html5_media_bundles),
        ):
            if values:
                if not isinstance(values, list):
                    raise ValueError(f"{field_name} must be a list")
                app_ad[field_name] = [self._asset_reference(item) for item in values]

        customer = str(self.customer_id or "").strip()
        if not re.fullmatch(r"\d+", customer):
            raise ValueError("customer_id must contain digits only")
        ad_resource_name = f"customers/{customer}/ads/-1"
        operation = {
            "adGroupAds": {
                "create": {
                    "resourceName": ad_resource_name,
                    "adGroup": f"customers/{customer}/adGroups/{ad_group_id}",
                    "status": status,
                    "ad": {
                        "name": str(name).strip(),
                        "appAd": app_ad,
                    },
                }
            }
        }
        return {
            "ad_resource_name": ad_resource_name,
            "ad_group_id": ad_group_id,
            "operation": operation,
            "execution_status": "planned",
            "mode": "dry_run",
            "live_support": False,
            "requires_verified_live_adapter": True,
        }
    
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
        *,
        asset_group_type: str = "PERFORMANCE_MAX",
        final_urls: list[str] = None,
        long_headlines: list[dict] = None,
        logos: list[dict] = None,
        final_mobile_urls: list[str] = None,
        status: str = "PAUSED",
    ) -> dict[str, Any]:
        """Build a verified-shape PMax mutation plan without provider I/O.

        PMax creation spans AssetGroup, Asset and AssetGroupAsset mutations.
        The current product contract intentionally exposes this as a
        dry-run-only operation: the returned plan contains temporary resource
        names and can be reviewed before a separately approved live adapter is
        introduced.  It must never be mistaken for a provider success.
        """
        campaign_id = self._numeric_id(campaign_id, "campaign_id")
        if not str(name or "").strip():
            raise ValueError("name is required")
        if str(asset_group_type or "").upper() != "PERFORMANCE_MAX":
            raise ValueError("asset_group_type must be PERFORMANCE_MAX")
        status = str(status or "PAUSED").upper()
        if status not in {"PAUSED", "ENABLED"}:
            raise ValueError("status must be PAUSED or ENABLED")
        if not isinstance(final_urls, list) or not final_urls:
            raise ValueError("final_urls must be a non-empty list")
        if not isinstance(headlines, list) or len(headlines) < 3:
            raise ValueError("headlines must contain at least 3 assets")
        if not isinstance(long_headlines, list) or not long_headlines:
            raise ValueError("long_headlines must contain at least 1 asset")
        if not isinstance(descriptions, list) or len(descriptions) < 2:
            raise ValueError("descriptions must contain at least 2 assets")

        customer = str(self.customer_id or "").strip()
        if not re.fullmatch(r"\d+", customer):
            raise ValueError("customer_id must contain digits only")
        asset_group_resource = f"customers/{customer}/assetGroups/-1"
        operations: list[dict[str, Any]] = [{
            "resource": "assetGroups",
            "operation": {
                "create": {
                    "resourceName": asset_group_resource,
                    "campaign": f"customers/{customer}/campaigns/{campaign_id}",
                    "name": str(name).strip(),
                    "assetGroupType": "PERFORMANCE_MAX",
                    "status": status,
                    "finalUrls": [str(url).strip() for url in final_urls],
                    **({
                        "finalMobileUrls": [str(url).strip() for url in final_mobile_urls]
                    } if final_mobile_urls else {}),
                }
            },
        }]

        temporary_asset_id = -2

        def asset_resource(value: Any, field_type: str) -> str:
            nonlocal temporary_asset_id
            if isinstance(value, str):
                value = {"asset": value}
            if not isinstance(value, dict) or not value:
                raise ValueError(f"{field_type} asset must be an object or resource name")
            reference = value.get("asset") or value.get("resource_name") or value.get("asset_id")
            if reference not in (None, ""):
                reference = str(reference).strip()
                if reference.startswith("customers/"):
                    return reference
                if not re.fullmatch(r"\d+", reference):
                    raise ValueError(f"{field_type} asset reference must be a Google Asset ID or resource name")
                return f"customers/{customer}/assets/{reference}"
            text = str(value.get("text") or "").strip()
            if field_type not in {"HEADLINE", "LONG_HEADLINE", "DESCRIPTION"} or not text:
                raise ValueError(
                    f"{field_type} requires an existing asset reference; only text assets can be created in the plan"
                )
            resource = f"customers/{customer}/assets/{temporary_asset_id}"
            temporary_asset_id -= 1
            operations.append({
                "resource": "assets",
                "operation": {"create": {
                    "resourceName": resource,
                    "name": str(value.get("name") or f"pmax_{field_type.lower()}"),
                    "textAsset": {"text": text},
                }},
            })
            return resource

        for field_name, field_type, values in (
            ("headlines", "HEADLINE", headlines),
            ("long_headlines", "LONG_HEADLINE", long_headlines),
            ("descriptions", "DESCRIPTION", descriptions),
            ("images", "MARKETING_IMAGE", images or []),
            ("logos", "LOGO", logos or []),
            ("videos", "YOUTUBE_VIDEO", videos or []),
        ):
            for value in values:
                resource = asset_resource(value, field_type)
                operations.append({
                    "resource": "assetGroupAssets",
                    "operation": {"create": {
                        "assetGroup": asset_group_resource,
                        "asset": resource,
                        "fieldType": field_type,
                    }},
                })
        return {
            "mode": "dry_run",
            "execution_status": "planned",
            "live_support": False,
            "requires_verified_live_adapter": True,
            "asset_group_resource_name": asset_group_resource,
            "operations": operations,
        }
    
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
