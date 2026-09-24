"""
api_clients/meta_client.py - Meta Marketing API 生产级客户端

接入已有 scripts/meta_api.py 的真实 API，补全：
- 自动重试（指数退避）
- 速率限制检测与等待
- 统一错误分类
"""

from __future__ import annotations

import json
import logging
import re
import time
import threading
from typing import Any, Optional
from urllib.parse import urlparse
import requests

from .base import BasePlatformClient, APIError, AuthError, RateLimitError, TemporaryError, RetryConfig, RateLimiter

logger = logging.getLogger(__name__)


class MetaAPIClient(BasePlatformClient):
    """
    Meta Marketing API 客户端 (v19.0)
    
    官方文档: https://developers.facebook.com/docs/marketing-api
    认证: OAuth2 Access Token
    
    速率限制: 
    - App 级: 2000 次/小时
    - 广告账户级: 50 次/10秒
    """
    
    API_VERSION = "v19.0"
    SUPPORTED_API_VERSIONS = (API_VERSION,)
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    def __init__(
        self,
        credentials: dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "meta", retry_config)
        self.api_version = self._resolve_api_version(
            self.credentials.get("api_version")
        )
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.access_token = self.credentials.get('access_token', '')
        # App 级限流器: 2000次/小时
        self._app_rate_limiter = RateLimiter(max_requests=2000, period=3600)
        # 账户级限流器: 50次/10秒
        self._account_rate_limiters: dict[str, RateLimiter] = {}
        self._account_rate_limiters_lock = threading.RLock()

    @classmethod
    def _resolve_api_version(cls, requested: Any = None) -> str:
        """Resolve a version against the Tool Source's explicit support list."""
        version = str(requested or cls.API_VERSION).strip()
        if version not in cls.SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported Meta API version {version!r}; "
                f"supported versions: {list(cls.SUPPORTED_API_VERSIONS)}"
            )
        return version
    
    def _get_account_limiter(self, account_id: str) -> RateLimiter:
        with self._account_rate_limiters_lock:
            if account_id not in self._account_rate_limiters:
                self._account_rate_limiters[account_id] = RateLimiter(max_requests=50, period=10)
            return self._account_rate_limiters[account_id]
    
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        params = dict(kwargs.get('params') or {})
        params['access_token'] = self.access_token
        
        headers = kwargs.get('headers', {})
        
        # 合并 params
        final_params = {**params, **kwargs.get('extra_params', {})}
        
        try:
            if method == 'GET':
                resp = requests.get(url, params=final_params, headers=headers, timeout=self.http_timeout())
            elif method == 'POST':
                resp = requests.post(url, params=final_params, json=kwargs.get('data'), headers=headers, timeout=self.http_timeout())
            elif method == 'DELETE':
                resp = requests.delete(url, params=final_params, headers=headers, timeout=self.http_timeout())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            try:
                data = resp.json() if resp.content else {}
            except ValueError:
                # Proxies and upstream gateways sometimes return HTML/plain text.
                # Preserve the HTTP status so the common error classifier can
                # still surface a useful failure instead of leaking JSON errors.
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
        """从响应中提取数据"""
        data = response.get('data', {})
        
        # 分页处理
        if isinstance(data, dict) and 'paging' in data:
            return {
                'data': data.get('data', []),
                'paging': data.get('paging', {}),
            }
        return data
    
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        """解析 Meta API 错误"""
        data = response.get('data', {})
        
        # 认证错误
        if status_code == 401:
            return AuthError("Meta API: Invalid or expired access token")

        if status_code == 403:
            message = "Permission denied"
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    message = error.get("message", message)
            return AuthError(f"Meta API: {message}")
        
        # 速率限制
        if status_code == 429:
            raw_retry_after = response.get('headers', {}).get('Retry-After', 60)
            try:
                retry_after = float(raw_retry_after)
            except (TypeError, ValueError):
                # Request IDs are not durations; never let a malformed header
                # turn a rate-limit response into an uncaught ValueError.
                retry_after = 60.0
            return RateLimitError("Meta API: Rate limit exceeded", retry_after=retry_after)

        if status_code >= 500:
            return TemporaryError(f"Meta API server error {status_code}")

        # A gateway or provider may return an empty/non-JSON 4xx body. It is
        # still a failed request and must never fall through as success.
        if status_code >= 400:
            message = "Bad request"
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message") or message)
                    # Meta often puts the actionable validation reason in
                    # error_user_msg while keeping message as the generic
                    # "Invalid parameter". Surface only provider diagnostic
                    # text and stable numeric metadata; request credentials
                    # and raw error_data remain outside the exception.
                    user_message = str(error.get("error_user_msg") or "").strip()
                    user_title = str(error.get("error_user_title") or "").strip()
                    if user_title and user_title.lower() not in message.lower():
                        message = f"{message} ({user_title})"
                    if user_message and user_message.lower() not in message.lower():
                        message = f"{message}: {user_message}"
                    if error.get("code") is not None:
                        message = f"{message} [code={error.get('code')}"
                        if error.get("error_subcode") is not None:
                            message += f", subcode={error.get('error_subcode')}"
                        message += "]"
            return APIError(
                f"Meta API HTTP {status_code}: {message}",
                status_code=status_code,
                response=data if isinstance(data, dict) else None,
            )
        
        # 业务错误（data 中有 error 字段）
        if isinstance(data, dict) and 'error' in data:
            error = data['error']
            message = error.get('message', 'Unknown error')
            code = error.get('code', 0)
            error_type = error.get('type', 'UnknownError')
            
            # 临时性错误（可重试）
            if code in (4, 17, 32, 80000, 80001, 80002, 80003):
                return TemporaryError(f"Meta API error {code}: {message}")
            
            # 认证相关
            if code in (190, 803, 80004, 80005, 80006, 80007, 80008, 80009, 80010):
                return AuthError(f"Meta API auth error {code}: {message}")
            
            return APIError(f"Meta API error {code}: {message}", status_code=status_code, response=data)
        
        return None
    
    # ==================== 账户管理 ====================
    
    def list_accounts(
        self, business_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List accessible Meta ad accounts without masking Graph API failures."""
        if isinstance(limit, bool):
            raise ValueError("account list limit must be between 1 and 1000")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "account list limit must be between 1 and 1000"
            ) from exc
        if not 1 <= limit <= 1000:
            raise ValueError("account list limit must be between 1 and 1000")

        selected_business_id = business_id or self.credentials.get("business_id")
        fields = "id,account_id,name,account_status,currency,timezone_name"
        if selected_business_id:
            clean_business_id = self._clean_meta_id(
                selected_business_id, "business_id"
            )
            scope_id = clean_business_id
            endpoint = f"/{clean_business_id}/owned_ad_accounts"
        else:
            scope_id = "me"
            endpoint = "/me/adaccounts"
        return self._list_graph_pages(
            scope_id,
            endpoint,
            {"limit": limit, "fields": fields},
        )

    def list_businesses(
        self, fields: list[str] | None = None, limit: int = 25
    ) -> list[dict[str, Any]]:
        """List businesses visible to the current Meta user/token."""
        selected_fields = ",".join(fields) if fields else (
            "id,name,verification_status,primary_page"
        )
        return self._list_graph_pages(
            "user",
            "/me/businesses",
            {"limit": limit, "fields": selected_fields},
        )

    def get_business(
        self, business_id: str, fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Get one Meta Business Manager object."""
        business_id = self._clean_meta_id(business_id, "business_id")
        selected_fields = ",".join(fields) if fields else (
            "id,name,verification_status,primary_page,owned_ad_accounts,"
            "owned_pages"
        )
        return self.require_resource_object(
            self.request(
                "GET", f"/{business_id}",
                extra_params={"fields": selected_fields},
            ),
            "Meta business get",
        )

    def get_account(self, account_id: str, fields: list = None) -> dict:
        """Get one AdAccount node using Meta's ``act_`` object identifier."""
        account_id = self._clean_meta_id(account_id, "account_id")
        params = {
            'fields': ','.join(fields) if fields else (
                'id,name,account_id,account_status,currency,timezone_name'
            )
        }
        return self.request(
            'GET', f"/act_{account_id}", extra_params=params
        )

    def search_targeting(
        self, account_id: str, query: str, search_type: str = "adinterest", limit: int = 25
    ) -> list[dict[str, Any]]:
        """Search account-independent targeting options via Meta's Graph API.

        The returned IDs are provider values used inside an Ad Set targeting
        payload.  This is deliberately read-only; selecting an option for a
        later create request is handled by Runtime's signed selection-token
        flow rather than by trusting a copied ID.
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        query = str(query or "").strip()
        if not query:
            raise ValueError("targeting search query must be non-empty")
        search_type = str(search_type or "adinterest").strip().lower()
        valid_types = {
            "adinterest", "adgeolocation", "adlocale", "adzipcode",
            "adworkposition", "adtargetingcategory",
        }
        if search_type not in valid_types:
            raise ValueError(f"Unsupported Meta targeting search type: {search_type}")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("targeting search limit must be between 1 and 100")
        return self._list_graph_pages(
            account_id,
            f"/act_{account_id}/targetingsearch",
            {"q": query, "type": search_type, "limit": limit},
        )

    def _list_graph_pages(
        self, account_id: str, endpoint: str, params: dict,
        item_key: str = "data", max_pages: int = 100,
    ) -> list:
        """Consume Graph API cursor pages without leaking paging envelopes."""
        items: list = []
        # Graph's ``limit`` is a page size, but callers of the Tool Source
        # contract use it as the total discovery bound.  Do not walk an
        # entire large account merely to populate a picker or ownership
        # check; that can also make a child-create confirmation appear stuck.
        raw_limit = params.get("limit") if isinstance(params, dict) else None
        total_limit = (
            int(raw_limit)
            if isinstance(raw_limit, int) and not isinstance(raw_limit, bool)
            and raw_limit > 0 else None
        )
        after = None
        seen_cursors: set[str] = set()
        for _ in range(max_pages):
            page_params = dict(params)
            # Meta Graph treats ``limit`` as the size of one page. Runtime
            # callers use it as a bounded total discovery limit, so cap the
            # wire value to a provider-safe page size and enforce the total
            # locally below. Sending limit=1000 can make some Graph edges
            # return a provider 500 even when the account is valid.
            if total_limit is not None:
                page_params["limit"] = min(total_limit, 100)
            if after:
                page_params["after"] = after
            self.acquire_rate_limit(self._get_account_limiter(account_id))
            result = self.request("GET", endpoint, extra_params=page_params)
            if isinstance(result, dict) and isinstance(result.get(item_key), list):
                page_items = result[item_key]
            elif isinstance(result, list):
                page_items = result
            else:
                page_items = []
            items.extend(page_items)
            if total_limit is not None and len(items) >= total_limit:
                return items[:total_limit]

            paging = result.get("paging", {}) if isinstance(result, dict) else {}
            cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}
            next_after = cursors.get("after") if isinstance(cursors, dict) else None
            if not next_after or next_after in seen_cursors:
                break
            seen_cursors.add(next_after)
            after = next_after
        return items

    def list_audiences(self, account_id: str, limit: int = 25) -> list:
        """获取广告账户下的 Custom Audience 列表。"""
        clean_id = self._clean_meta_id(account_id, "account_id")
        return self._list_graph_pages(
            clean_id,
            f"/act_{clean_id}/customaudiences",
            {
                'limit': limit,
                # ``approximate_count`` was removed from the current Graph
                # custom-audience projection.  Keeping it here makes an
                # otherwise valid lookup fail with Graph error #100, which in
                # turn prevents the creation card from offering audience
                # choices.  Counts are optional metadata; the stable fields
                # below are sufficient for selection and auditing.
                'fields': 'id,name,subtype,delivery_status',
            },
        )

    def create_custom_conversion(self, account_id: str, conversion: dict) -> str:
        """Create a Meta Custom Conversion for an account-owned Pixel.

        Meta documents creation on ``/{ad-account}/customconversions``.  The
        generated Meta SDK also exposes the account edge and node-level
        read/update/delete operations.  Keep those operations explicit here
        rather than forwarding arbitrary Graph paths from a Tool.
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(conversion, dict):
            raise ValueError("conversion must be an object")
        allowed_fields = {
            "pixel_id", "name", "rule", "action_source_type", "advanced_rule",
            "custom_event_type", "default_conversion_value", "description",
        }
        unknown = sorted(set(conversion) - allowed_fields)
        if unknown:
            raise ValueError(f"unsupported custom conversion fields: {', '.join(unknown)}")
        pixel_id = self._clean_meta_id(conversion.get("pixel_id"), "pixel_id")
        if not self.resource_belongs_to_account(account_id, "pixel", pixel_id):
            raise PermissionError(
                f"Meta pixel {pixel_id} does not belong to account {account_id}"
            )
        name = str(conversion.get("name") or "").strip()
        rule = str(conversion.get("rule") or "").strip()
        if not name or not rule:
            raise ValueError("custom conversion name and rule are required")
        data: dict[str, Any] = {
            "event_source_id": pixel_id,
            "name": name,
            "rule": rule,
        }
        for field_name in (
            "action_source_type", "advanced_rule", "custom_event_type", "description",
        ):
            if conversion.get(field_name) is not None:
                value = conversion[field_name]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} must be a non-empty string")
                data[field_name] = value.strip()
        if conversion.get("default_conversion_value") is not None:
            try:
                value = float(conversion["default_conversion_value"])
            except (TypeError, ValueError) as exc:
                raise ValueError("default_conversion_value must be a non-negative number") from exc
            if value < 0:
                raise ValueError("default_conversion_value must be non-negative")
            data["default_conversion_value"] = value
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/act_{account_id}/customconversions", data=data)
        resource_id = result.get("id") if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta custom conversion create")

    def list_custom_conversions(
        self, account_id: str, fields: list[str] | None = None, limit: int = 25
    ) -> list:
        """List Custom Conversions owned by a Meta ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("custom conversion limit must be between 1 and 1000")
        return self._list_graph_pages(
            account_id,
            f"/act_{account_id}/customconversions",
            {
                "limit": limit,
                "fields": ",".join(fields) if fields else (
                    "id,name,rule,advanced_rule,custom_event_type,action_source_type,"
                    "default_conversion_value,description,event_source_id,creation_time"
                ),
            },
        )

    def get_custom_conversion(
        self, account_id: str, custom_conversion_id: str, fields: list[str] | None = None
    ) -> dict:
        """Get one Custom Conversion after account ownership verification."""
        account_id = self._clean_meta_id(account_id, "account_id")
        custom_conversion_id = self._clean_meta_id(
            custom_conversion_id, "custom_conversion_id"
        )
        if not self.resource_belongs_to_account(
            account_id, "custom_conversion", custom_conversion_id
        ):
            raise PermissionError(
                f"Meta custom conversion {custom_conversion_id} does not belong to account "
                f"{account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,rule,advanced_rule,custom_event_type,action_source_type,"
                "default_conversion_value,description,event_source_id,creation_time"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{custom_conversion_id}", extra_params=params),
            "Meta custom conversion get",
        )

    def update_custom_conversion(
        self, account_id: str, custom_conversion_id: str, updates: dict
    ) -> dict:
        """Update the mutable Custom Conversion fields exposed by Meta."""
        account_id = self._clean_meta_id(account_id, "account_id")
        custom_conversion_id = self._clean_meta_id(
            custom_conversion_id, "custom_conversion_id"
        )
        if not self.resource_belongs_to_account(
            account_id, "custom_conversion", custom_conversion_id
        ):
            raise PermissionError(
                f"Meta custom conversion {custom_conversion_id} does not belong to account "
                f"{account_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        allowed = {"name", "default_conversion_value", "description"}
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ValueError(
                "Unsupported Meta Custom Conversion update fields: "
                + ", ".join(unknown)
            )
        data: dict[str, Any] = {}
        if "name" in updates:
            name = str(updates["name"] or "").strip()
            if not name:
                raise ValueError("Custom conversion name must be a non-empty string")
            data["name"] = name
        if "description" in updates:
            description = updates["description"]
            if not isinstance(description, str):
                raise ValueError("Custom conversion description must be a string")
            data["description"] = description
        if "default_conversion_value" in updates:
            try:
                value = float(updates["default_conversion_value"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "default_conversion_value must be a non-negative number"
                ) from exc
            if value < 0:
                raise ValueError("default_conversion_value must be non-negative")
            data["default_conversion_value"] = value
        if not data:
            raise ValueError("updates must contain a supported non-null field")
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{custom_conversion_id}", data=data)
        return {
            "success": True,
            "custom_conversion_id": custom_conversion_id,
            "result": result,
        }

    def delete_custom_conversion(
        self, account_id: str, custom_conversion_id: str
    ) -> dict:
        """Delete a Custom Conversion after account ownership verification."""
        account_id = self._clean_meta_id(account_id, "account_id")
        custom_conversion_id = self._clean_meta_id(
            custom_conversion_id, "custom_conversion_id"
        )
        if not self.resource_belongs_to_account(
            account_id, "custom_conversion", custom_conversion_id
        ):
            raise PermissionError(
                f"Meta custom conversion {custom_conversion_id} does not belong to account "
                f"{account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{custom_conversion_id}")
        return {"success": True, "custom_conversion_id": custom_conversion_id}

    @staticmethod
    def _clean_meta_id(value: Any, field_name: str) -> str:
        """Validate a Graph object/account ID before URL construction."""
        raw = str(value or "").strip()
        if raw.startswith("act_"):
            raw = raw[4:]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
            raise ValueError(f"{field_name} must be a simple Meta object ID")
        return raw

    @classmethod
    def _ad_account_edge(cls, account_id: Any, edge: str) -> str:
        """Build a Marketing API edge using Meta's required ``act_`` ID."""
        clean_id = cls._clean_meta_id(account_id, "account_id")
        return f"/act_{clean_id}/{str(edge).lstrip('/')}"

    def get_audience(self, account_id: str, audience_id: str, fields: list = None) -> dict:
        """Get one Custom/Lookalike Audience visible to an ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        audience_id = self._clean_meta_id(audience_id, "audience_id")
        # The account is intentionally part of the Tool contract even though
        # Graph addresses the object by ID.  Verify visibility so a token
        # shared across accounts cannot read an unrelated Audience.
        if not self.resource_belongs_to_account(account_id, "audience", audience_id):
            raise PermissionError(
                f"Meta audience {audience_id} does not belong to account {account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,subtype,delivery_status"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{audience_id}", extra_params=params),
            "Meta audience get",
        )

    def create_audience(self, account_id: str, audience: dict) -> str:
        """Create a Meta Custom or Lookalike Audience.

        ``rule`` and ``lookalike_spec`` are JSON objects in the Tool contract,
        but Meta's Graph endpoint expects JSON-encoded parameter strings.
        This translation remains provider-owned and is never performed by
        Runtime or a business Skill.
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(audience, dict):
            raise ValueError("audience must be an object")
        name = str(audience.get("name") or "").strip()
        subtype = str(audience.get("subtype") or "").strip().upper()
        if not name or subtype not in {"CUSTOM", "LOOKALIKE"}:
            raise ValueError("audience name and subtype=CUSTOM or LOOKALIKE are required")

        data: dict[str, Any] = {"name": name, "subtype": subtype}
        for field_name in (
            "description", "customer_file_source", "retention_days", "prefill",
            "pixel_id", "event_source_group",
        ):
            if audience.get(field_name) is not None:
                data[field_name] = audience[field_name]
        if audience.get("rule") is not None:
            if not isinstance(audience["rule"], dict):
                raise ValueError("rule must be an object")
            data["rule"] = json.dumps(audience["rule"], separators=(",", ":"))

        if subtype == "LOOKALIKE":
            origin_id = self._clean_meta_id(
                audience.get("origin_audience_id"), "origin_audience_id"
            )
            country = str(audience.get("country") or "").strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", country):
                raise ValueError("country must be a two-letter ISO country code")
            try:
                ratio = float(audience.get("ratio", 0.01))
            except (TypeError, ValueError) as exc:
                raise ValueError("ratio must be between 0.01 and 0.20") from exc
            if not 0.01 <= ratio <= 0.20:
                raise ValueError("ratio must be between 0.01 and 0.20")
            lookalike_type = str(audience.get("lookalike_type", "similarity")).lower()
            if lookalike_type not in {"similarity", "reach"}:
                raise ValueError("lookalike_type must be similarity or reach")
            data["origin_audience_id"] = origin_id
            data["lookalike_spec"] = json.dumps({
                "country": country,
                "ratio": ratio,
                "type": lookalike_type,
            }, separators=(",", ":"))

        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/act_{account_id}/customaudiences", data=data)
        resource_id = result.get("id") if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta audience create")

    def update_audience(
        self, account_id: str, audience_id: str, updates: dict
    ) -> dict:
        """Update the supported mutable Custom Audience fields."""
        account_id = self._clean_meta_id(account_id, "account_id")
        audience_id = self._clean_meta_id(audience_id, "audience_id")
        if not self.resource_belongs_to_account(account_id, "audience", audience_id):
            raise PermissionError(
                f"Meta audience {audience_id} does not belong to account {account_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        allowed = {
            "name", "description", "retention_days", "rule",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported Meta Audience update fields: {sorted(unknown)}")
        data = {key: value for key, value in updates.items() if value is not None}
        if "rule" in data:
            if not isinstance(data["rule"], dict):
                raise ValueError("rule must be an object")
            data["rule"] = json.dumps(data["rule"], separators=(",", ":"))
        if not data:
            raise ValueError("updates must contain a supported non-null field")
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{audience_id}", data=data)
        return {"success": True, "audience_id": audience_id, "result": result}

    def delete_audience(self, account_id: str, audience_id: str) -> dict:
        """Delete a Custom Audience after account ownership verification."""
        account_id = self._clean_meta_id(account_id, "account_id")
        audience_id = self._clean_meta_id(audience_id, "audience_id")
        if not self.resource_belongs_to_account(account_id, "audience", audience_id):
            raise PermissionError(
                f"Meta audience {audience_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{audience_id}")
        return {"success": True, "audience_id": audience_id}

    def upload_audience_users(
        self, account_id: str, audience_id: str,
        upload_schema: list[str], upload_data: list[list[str]],
    ) -> dict:
        """Upload pre-hashed customer identifiers to a Custom Audience.

        The Tool contract intentionally accepts only SHA-256 values.  The
        service must not receive raw email addresses or phone numbers because
        those values could otherwise enter request logs, audit records, or
        model context.  Normalization and hashing remain the caller's
        responsibility before invoking this provider boundary.
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        audience_id = self._clean_meta_id(audience_id, "audience_id")
        if not self.resource_belongs_to_account(account_id, "audience", audience_id):
            raise PermissionError(
                f"Meta audience {audience_id} does not belong to account {account_id}"
            )
        allowed_schema = {
            "EMAIL", "PHONE", "FN", "LN", "ZIP", "CT", "ST", "COUNTRY", "DOB",
            "DOBY", "DOBM", "DOBD", "GEN", "MADID", "EXTERN_ID",
        }
        if not isinstance(upload_schema, list) or not upload_schema:
            raise ValueError("upload_schema must be a non-empty list")
        normalized_schema = [str(item or "").strip().upper() for item in upload_schema]
        if len(set(normalized_schema)) != len(normalized_schema) or any(
            item not in allowed_schema for item in normalized_schema
        ):
            raise ValueError("upload_schema contains an unsupported or duplicate field")
        if not isinstance(upload_data, list) or not upload_data:
            raise ValueError("upload_data must be a non-empty list")
        if len(upload_data) > 10000:
            raise ValueError("upload_data cannot contain more than 10000 rows")
        rows: list[list[str]] = []
        for row_index, row in enumerate(upload_data):
            if not isinstance(row, list) or len(row) != len(normalized_schema):
                raise ValueError(
                    f"upload_data[{row_index}] must contain one SHA-256 value per schema field"
                )
            normalized_row: list[str] = []
            for value_index, value in enumerate(row):
                value_text = str(value or "").strip().lower()
                if not re.fullmatch(r"[0-9a-f]{64}", value_text):
                    raise ValueError(
                        f"upload_data[{row_index}][{value_index}] must be a SHA-256 hex digest"
                    )
                normalized_row.append(value_text)
            rows.append(normalized_row)
        payload = json.dumps(
            {"schema": normalized_schema, "data": rows},
            ensure_ascii=False, separators=(",", ":"),
        )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request(
            "POST", f"/{audience_id}/users", data={"payload": payload}
        )
        return self.require_resource_object(result, "Meta audience source upload")

    def list_catalogs(self, account_id: str, limit: int = 25) -> list:
        """获取广告账户可用的商品目录。"""
        clean_id = self._clean_meta_id(account_id, "account_id")
        # Catalog ownership is exposed on the Business node, not on the ad
        # account node.  Keep the account argument as the Runtime scope, but
        # use the credential-bound Business ID for the provider edge; never
        # accept a business ID from the tool payload.
        business_id = self._clean_meta_id(
            self.credentials.get("business_id"), "business_id"
        )
        if not business_id:
            raise ValueError("Meta credentials must include business_id to list catalogs")
        return self._list_graph_pages(
            business_id,
            f"/{business_id}/owned_product_catalogs",
            {
                'limit': limit,
                'fields': 'id,name,vertical,product_count,feed_count',
            },
        )

    def get_catalog(self, account_id: str, catalog_id: str, fields: list = None) -> dict:
        """Get one Catalog after verifying it is visible under the ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        if not self.resource_belongs_to_account(account_id, "catalog", catalog_id):
            raise PermissionError(
                f"Meta catalog {catalog_id} does not belong to account {account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,vertical,product_count,feed_count,created_time,updated_time"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{catalog_id}", extra_params=params),
            "Meta catalog get",
        )

    def create_catalog(self, business_id: str, catalog: dict) -> str:
        """Create a Product Catalog under an explicitly supplied Business ID.

        Meta's Catalog creation endpoint is Business-scoped rather than
        ad-account-scoped.  Keep that distinction visible in the Tool
        contract instead of silently treating ``account_id`` as a Business.
        """
        business_id = self._clean_meta_id(business_id, "business_id")
        if not isinstance(catalog, dict):
            raise ValueError("catalog must be an object")
        name = str(catalog.get("name") or "").strip()
        vertical = str(catalog.get("vertical") or "").strip().lower()
        if not name or not vertical:
            raise ValueError("catalog name and vertical are required")
        allowed_verticals = {
            "commerce", "destination_items", "flights", "home_listings",
            "hotels", "vehicles",
        }
        if vertical not in allowed_verticals:
            raise ValueError(
                f"Unsupported Meta catalog vertical {vertical!r}; "
                f"expected one of {sorted(allowed_verticals)}"
            )
        data = {"name": name, "vertical": vertical}
        if catalog.get("is_checkout") is not None:
            data["is_checkout"] = bool(catalog["is_checkout"])
        self.acquire_rate_limit(self._get_account_limiter(business_id))
        result = self.request(
            "POST", f"/{business_id}/owned_product_catalogs", data=data
        )
        resource_id = result.get("id") if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta catalog create")

    def update_catalog(self, account_id: str, catalog_id: str, updates: dict) -> dict:
        """Update the supported mutable Catalog fields after ownership check."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        if not self.resource_belongs_to_account(account_id, "catalog", catalog_id):
            raise PermissionError(
                f"Meta catalog {catalog_id} does not belong to account {account_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - {"name"}
        if unknown:
            raise ValueError(f"Unsupported Meta Catalog update fields: {sorted(unknown)}")
        name = str(updates.get("name") or "").strip()
        if not name:
            raise ValueError("Catalog name must be a non-empty string")
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{catalog_id}", data={"name": name})
        return {"success": True, "catalog_id": catalog_id, "result": result}

    def delete_catalog(self, account_id: str, catalog_id: str) -> dict:
        """Delete a Catalog after ownership verification."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        if not self.resource_belongs_to_account(account_id, "catalog", catalog_id):
            raise PermissionError(
                f"Meta catalog {catalog_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{catalog_id}")
        return {"success": True, "catalog_id": catalog_id}

    def list_product_sets(
        self, account_id: str, catalog_id: str, limit: int = 25
    ) -> list:
        """获取商品目录下的商品集。"""
        account_id = self._clean_meta_id(account_id, "account_id")
        clean_id = str(catalog_id).strip()
        clean_id = self._clean_meta_id(clean_id, "catalog_id")
        if not self.resource_belongs_to_account(account_id, "catalog", clean_id):
            raise PermissionError(
                f"Meta catalog {clean_id} does not belong to account {account_id}"
            )
        return self._list_graph_pages(
            clean_id,
            f"/{clean_id}/product_sets",
            {
                'limit': limit,
                'fields': 'id,name,filter,product_count',
            },
        )

    def get_product_set(
        self, account_id: str, catalog_id: str, product_set_id: str,
        fields: list = None,
    ) -> dict:
        """Get one Product Set after Catalog/account ownership checks."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        product_set_id = self._clean_meta_id(product_set_id, "product_set_id")
        if not self._product_set_belongs_to_catalog(
            account_id, catalog_id, product_set_id
        ):
            raise PermissionError(
                f"Meta product set {product_set_id} is not in catalog {catalog_id} "
                f"for account {account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,filter,product_count,updated_time"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{product_set_id}", extra_params=params),
            "Meta product set get",
        )

    def create_product_set(
        self, account_id: str, catalog_id: str, product_set: dict
    ) -> str:
        """Create a Product Set under an account-owned Catalog."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        if not self.resource_belongs_to_account(account_id, "catalog", catalog_id):
            raise PermissionError(
                f"Meta catalog {catalog_id} does not belong to account {account_id}"
            )
        if not isinstance(product_set, dict):
            raise ValueError("product_set must be an object")
        name = str(product_set.get("name") or "").strip()
        if not name:
            raise ValueError("product set name is required")
        data: dict[str, Any] = {"name": name}
        if product_set.get("filter") is not None:
            if not isinstance(product_set["filter"], dict):
                raise ValueError("product set filter must be an object")
            data["filter"] = json.dumps(
                product_set["filter"], separators=(",", ":")
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{catalog_id}/product_sets", data=data)
        resource_id = result.get("id") if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta product set create")

    def update_product_set(
        self, account_id: str, catalog_id: str, product_set_id: str, updates: dict
    ) -> dict:
        """Update a Product Set after Catalog/account ownership checks."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        product_set_id = self._clean_meta_id(product_set_id, "product_set_id")
        if not self._product_set_belongs_to_catalog(
            account_id, catalog_id, product_set_id
        ):
            raise PermissionError(
                f"Meta product set {product_set_id} is not in catalog {catalog_id} "
                f"for account {account_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - {"name", "filter"}
        if unknown:
            raise ValueError(
                f"Unsupported Meta Product Set update fields: {sorted(unknown)}"
            )
        data: dict[str, Any] = {}
        if "name" in updates:
            name = str(updates["name"] or "").strip()
            if not name:
                raise ValueError("Product set name must be a non-empty string")
            data["name"] = name
        if "filter" in updates:
            if not isinstance(updates["filter"], dict):
                raise ValueError("product set filter must be an object")
            data["filter"] = json.dumps(updates["filter"], separators=(",", ":"))
        if not data:
            raise ValueError("updates must contain a supported non-null field")
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{product_set_id}", data=data)
        return {"success": True, "product_set_id": product_set_id, "result": result}

    def delete_product_set(
        self, account_id: str, catalog_id: str, product_set_id: str
    ) -> dict:
        """Delete a Product Set after Catalog/account ownership checks."""
        account_id = self._clean_meta_id(account_id, "account_id")
        catalog_id = self._clean_meta_id(catalog_id, "catalog_id")
        product_set_id = self._clean_meta_id(product_set_id, "product_set_id")
        if not self._product_set_belongs_to_catalog(
            account_id, catalog_id, product_set_id
        ):
            raise PermissionError(
                f"Meta product set {product_set_id} is not in catalog {catalog_id} "
                f"for account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{product_set_id}")
        return {"success": True, "product_set_id": product_set_id}

    def _product_set_belongs_to_catalog(
        self, account_id: str, catalog_id: str, product_set_id: str
    ) -> bool:
        """Check a Product Set through the account-visible Catalog edge."""
        if not self.resource_belongs_to_account(account_id, "catalog", catalog_id):
            return False
        product_sets = self._list_graph_pages(
            catalog_id,
            f"/{catalog_id}/product_sets",
            {
                "limit": 100,
                "fields": "id",
            },
        )
        return any(
            isinstance(item, dict) and str(item.get("id")) == str(product_set_id)
            for item in product_sets
        )

    def list_pages(self, account_id: str, limit: int = 25) -> list:
        """List Facebook Pages usable as a Meta ad identity.

        Older Marketing API versions exposed ``promotable_pages`` on the ad
        account. Meta v19 no longer exposes that edge, so fall back to the
        current user's Page list. The fallback deliberately does not return
        Page access tokens and callers must still use the selected Page ID
        explicitly; it never guesses a Page for a live creative.
        """
        clean_id = str(account_id).replace("act_", "")
        try:
            return self._list_graph_pages(
                clean_id,
                f"/act_{clean_id}/promotable_pages",
                {"limit": limit, "fields": "id,name,category"},
            )
        except APIError as exc:
            # Only fall back for the removed/unsupported edge. Permission,
            # auth and other provider failures must remain visible.
            message = str(exc).lower()
            if exc.status_code != 400 or "unknown path" not in message:
                raise
            return self._list_graph_pages(
                clean_id,
                "/me/accounts",
                {"limit": limit, "fields": "id,name,category,tasks"},
            )

    def list_pixels(self, account_id: str, limit: int = 25) -> list:
        """List Meta Pixels owned by an ad account."""
        clean_id = str(account_id).replace("act_", "")
        return self._list_graph_pages(
            clean_id,
            f"/act_{clean_id}/adspixels",
            {"limit": limit, "fields": "id,name,last_fired_time"},
        )

    def get_pixel(self, account_id: str, pixel_id: str, fields: list = None) -> dict:
        """Get one Meta Pixel after verifying it belongs to the ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        pixel_id = self._clean_meta_id(pixel_id, "pixel_id")
        if not self.resource_belongs_to_account(account_id, "pixel", pixel_id):
            raise PermissionError(
                f"Meta pixel {pixel_id} does not belong to account {account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,last_fired_time,creation_time,owner_ad_account"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{pixel_id}", extra_params=params),
            "Meta pixel get",
        )

    def send_conversion_events(
        self,
        account_id: str,
        pixel_id: str,
        events: list[dict],
        test_event_code: str | None = None,
    ) -> dict:
        """Send a validated batch to Meta's Conversions API."""
        account_id = self._clean_meta_id(account_id, "account_id")
        pixel_id = self._clean_meta_id(pixel_id, "pixel_id")
        if not isinstance(events, list) or not events:
            raise ValueError("events must be a non-empty array")
        if len(events) > 1000:
            raise ValueError("events cannot contain more than 1000 items")
        required_fields = {"event_name", "event_time", "action_source", "user_data"}
        allowed_action_sources = {
            "website", "app", "physical_store", "phone_call", "chat", "email", "other",
        }
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                raise ValueError(f"events[{index}] must be an object")
            missing = sorted(required_fields - set(event))
            if missing:
                raise ValueError(
                    f"events[{index}] is missing required fields: {', '.join(missing)}"
                )
            if not isinstance(event["user_data"], dict):
                raise ValueError(f"events[{index}].user_data must be an object")
            if not isinstance(event["event_name"], str) or not event["event_name"].strip():
                raise ValueError(f"events[{index}].event_name must be a non-empty string")
            if event["action_source"] not in allowed_action_sources:
                raise ValueError(
                    f"events[{index}].action_source must be one of "
                    f"{sorted(allowed_action_sources)}"
                )
            try:
                event_time = int(event["event_time"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"events[{index}].event_time must be an integer") from exc
            if event_time <= 0:
                raise ValueError(f"events[{index}].event_time must be positive")
        if not self.resource_belongs_to_account(account_id, "pixel", pixel_id):
            raise PermissionError(
                f"Meta pixel {pixel_id} does not belong to account {account_id}"
            )
        data: dict[str, Any] = {"data": events}
        if test_event_code not in (None, ""):
            data["test_event_code"] = str(test_event_code).strip()
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{pixel_id}/events", data=data)
        return self.require_resource_object(result, "Meta Conversions API events")

    def list_lead_forms(self, page_id: str, limit: int = 25) -> list:
        """List Instant Forms published on a Facebook Page."""
        page_id = str(page_id or "").strip()
        if not page_id:
            raise ValueError("page_id is required")
        return self._list_graph_pages(
            page_id,
            f"/{page_id}/leadgen_forms",
            {"limit": limit, "fields": "id,name,status,created_time,updated_time"},
        )

    def get_lead_form(self, page_id: str, form_id: str, fields: list = None) -> dict:
        """Get one Instant Form after verifying it belongs to the Page."""
        page_id = self._clean_meta_id(page_id, "page_id")
        form_id = self._clean_meta_id(form_id, "form_id")
        forms = self.list_lead_forms(page_id, limit=100)
        if not any(
            isinstance(item, dict) and str(item.get("id")) == form_id
            for item in forms
        ):
            raise PermissionError(
                f"Meta lead form {form_id} does not belong to page {page_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,status,created_time,updated_time,page,questions,"
                "privacy_policy_url,follow_up_action"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{form_id}", extra_params=params),
            "Meta lead form get",
        )

    def list_leads(
        self,
        page_id: str,
        form_id: str,
        fields: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """List leads submitted to a Page-owned Instant Form."""
        page_id = self._clean_meta_id(page_id, "page_id")
        form_id = self._clean_meta_id(form_id, "form_id")
        # Prove the form belongs to the requested Page before reading leads.
        self.get_lead_form(page_id, form_id, fields=["id"])
        selected_fields = ",".join(fields) if fields else (
            "id,created_time,field_data,form_id,ad_id,ad_name,"
            "campaign_id,campaign_name,adset_id,adset_name,is_organic"
        )
        return self._list_graph_pages(
            form_id,
            f"/{form_id}/leads",
            {"limit": limit, "fields": selected_fields},
        )

    def get_lead(
        self,
        page_id: str,
        form_id: str,
        lead_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get one Lead after verifying its parent Instant Form."""
        lead_id = self._clean_meta_id(lead_id, "lead_id")
        leads = self.list_leads(page_id, form_id, fields=fields, limit=1000)
        return next(
            (
                item for item in leads
                if isinstance(item, dict)
                and str(item.get("id") or "") == lead_id
            ),
            {},
        )

    def create_lead_form(self, page_id: str, form: dict) -> str:
        """Create a Page-owned Meta Lead Ads Instant Form.

        Meta expects the structured question and presentation blocks as JSON
        strings on the Graph API wire.  This method owns that translation;
        the Tool Source owns the closed input contract and Runtime owns dry-run
        and account authorization gates.
        """
        page_id = self._clean_meta_id(page_id, "page_id")
        if not isinstance(form, dict):
            raise ValueError("lead form must be an object")
        name = str(form.get("name") or "").strip()
        questions = form.get("questions")
        privacy_policy = form.get("privacy_policy")
        if not name or not isinstance(questions, list) or not questions:
            raise ValueError("name and a non-empty questions list are required")
        if not isinstance(privacy_policy, dict):
            raise ValueError("privacy_policy must be an object")
        if not str(privacy_policy.get("url") or "").strip() or not str(
            privacy_policy.get("link_text") or ""
        ).strip():
            raise ValueError("privacy_policy requires url and link_text")
        for index, question in enumerate(questions):
            if not isinstance(question, dict):
                raise ValueError(f"questions[{index}] must be an object")
            question_type = str(question.get("type") or "").upper()
            if not question_type:
                raise ValueError(f"questions[{index}].type is required")
            if question_type == "CUSTOM" and (
                not str(question.get("key") or "").strip()
                or not str(question.get("label") or "").strip()
            ):
                raise ValueError(
                    f"questions[{index}] CUSTOM questions require key and label"
                )

        data: dict[str, Any] = {
            "name": name,
            "questions": json.dumps(questions, ensure_ascii=False, separators=(",", ":")),
            "privacy_policy": json.dumps(
                privacy_policy, ensure_ascii=False, separators=(",", ":")
            ),
        }
        for field in ("follow_up_action_url", "locale"):
            if form.get(field) not in (None, ""):
                data[field] = form[field]
        for field in ("context_card", "thank_you_page"):
            if form.get(field) is not None:
                if not isinstance(form[field], dict):
                    raise ValueError(f"{field} must be an object")
                data[field] = json.dumps(
                    form[field], ensure_ascii=False, separators=(",", ":")
                )
        if form.get("is_for_calling") is not None:
            data["is_for_calling"] = bool(form["is_for_calling"])
        self.acquire_rate_limit(self._get_account_limiter(page_id))
        result = self.request("POST", f"/{page_id}/leadgen_forms", data=data)
        resource_id = result.get("id") if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta lead form create")

    def update_lead_form(self, page_id: str, form_id: str, updates: dict) -> dict:
        """Update the supported mutable field of a Page-owned Instant Form."""
        page_id = self._clean_meta_id(page_id, "page_id")
        form_id = self._clean_meta_id(form_id, "form_id")
        if not isinstance(updates, dict) or not str(updates.get("name") or "").strip():
            raise ValueError("updates.name is required for Meta lead form update")
        # Graph IDs are not globally writable merely because the token can
        # address them; prove Page ownership before the mutation.
        self.get_lead_form(page_id, form_id, fields=["id"])
        self.acquire_rate_limit(self._get_account_limiter(page_id))
        return self.require_resource_object(
            self.request("POST", f"/{form_id}", data={"name": updates["name"]}),
            "Meta lead form update",
        )
    
    # ==================== Campaign 管理 ====================
    
    def list_campaigns(self, account_id: str, fields: list = None, limit: int = 25) -> dict:
        """获取 Campaign 列表"""
        # 去除可能的 act_ 前缀
        clean_id = account_id.replace('act_', '')
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective'}
        return self._list_graph_pages(
            clean_id,
            f"/act_{clean_id}/campaigns",
            {**params, 'limit': limit},
        )
    
    def get_campaign(self, campaign_id: str, fields: list = None) -> dict:
        """获取 Campaign 详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective,adsets,ads'}
        return self.require_resource_object(
            self.request('GET', f"/{campaign_id}", extra_params=params),
            "Meta campaign get",
        )

    def resource_belongs_to_account(
        self, account_id: str, resource_type: str, resource_id: str
    ) -> bool:
        """Verify a Graph object is visible under the selected ad account.

        Graph object IDs are globally addressable for a token.  Runtime
        account allowlisting alone therefore does not prove that an object ID
        belongs to the selected account.  This explicit lookup is used before
        direct object reads/updates for live-capable handlers.
        """
        if not account_id or not resource_id:
            return False
        resource_id = str(resource_id)
        resource_type = {
            "ad_set": "adset", "ad_group": "adset", "audiences": "audience",
            "pixels": "pixel",
        }.get(str(resource_type or "").lower(), str(resource_type or "").lower())

        # Graph object IDs are globally addressable. For objects that expose
        # ``account_id`` (notably Ad Creative), a node read is both cheaper
        # and more complete than searching an arbitrary first page of the
        # account edge. If the provider omits the ownership field, retain the
        # bounded edge lookup as a conservative fallback.
        if resource_type == "creative":
            try:
                node = self.require_resource_object(
                    self.request(
                        "GET", f"/{self._clean_meta_id(resource_id, 'creative_id')}",
                        extra_params={"fields": "id,account_id"},
                    ),
                    "Meta creative ownership lookup",
                )
                owner_id = str(node.get("account_id") or "").replace("act_", "")
                if owner_id:
                    return owner_id == str(account_id).replace("act_", "")
            except APIError:
                # Keep the existing bounded list fallback for older API
                # versions/tokens that cannot read account_id on the node.
                pass
        if resource_type == "campaign":
            items = self.list_campaigns(account_id, limit=1000)
        elif resource_type == "adset":
            items = self.list_adsets(account_id, limit=1000)
        elif resource_type == "ad":
            items = self.list_ads(account_id, limit=1000)
        elif resource_type == "audience":
            items = self.list_audiences(account_id, limit=1000)
        elif resource_type == "pixel":
            items = self.list_pixels(account_id, limit=1000)
        elif resource_type == "custom_conversion":
            items = self.list_custom_conversions(account_id, limit=1000)
        elif resource_type == "creative":
            items = self.list_creatives(account_id, limit=1000)
        elif resource_type == "catalog":
            items = self.list_catalogs(account_id, limit=1000)
        else:
            return False
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                continue
            identifiers = {
                item.get("id"), item.get("campaign_id"), item.get("adset_id"),
                item.get("ad_id"), item.get("audience_id"),
                item.get("pixel_id"), item.get("catalog_id"),
                item.get("custom_conversion_id"),
            }
            if resource_id in {str(value) for value in identifiers if value is not None}:
                return True
        return False
    
    def create_campaign(self, account_id: str, campaign: dict, live: bool = False) -> dict:
        """创建 Campaign
        
        Meta Graph API 要求：
        - objective: 必须使用有效值（OUTCOME_SALES, OUTCOME_AWARENESS 等）
        - special_ad_categories: 必须指定（NONE 表示不限制）
        - is_adset_budget_sharing_enabled: 不使用 campaign budget 时必须指定
        """
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        
        # 验证 objective
        valid_objectives = [
            'APP_INSTALLS', 'PRODUCT_CATALOG_SALES', 'CONVERSIONS', 
            'TRAFFIC', 'LINK_CLICKS', 'OUTCOME_SALES', 
            'OUTCOME_APP_PROMOTION', 'OUTCOME_TRAFFIC',
            'OUTCOME_AWARENESS', 'OUTCOME_LEADS', 'OUTCOME_ENGAGEMENT',
            'OUTCOME_CONVERSIONS', 'OUTCOME_MESSAGES'
        ]
        objective = campaign.get('objective', 'OUTCOME_SALES')
        if objective not in valid_objectives:
            raise ValueError(f"Invalid objective '{objective}'. Valid values: {valid_objectives}")
        
        special_ad_categories = campaign.get('special_ad_categories', 'NONE')
        if isinstance(special_ad_categories, str):
            special_ad_categories = [special_ad_categories]
        if not isinstance(special_ad_categories, list):
            raise ValueError("Meta special_ad_categories must be a string or list")
        special_ad_categories = [str(category).upper() for category in special_ad_categories]
        allowed_special_categories = {"NONE", "EMPLOYMENT", "HOUSING", "CREDIT"}
        unknown_categories = set(special_ad_categories) - allowed_special_categories
        if unknown_categories:
            raise ValueError(
                "Unsupported Meta special_ad_categories: "
                + ", ".join(sorted(unknown_categories))
            )
        if "NONE" in special_ad_categories and len(special_ad_categories) > 1:
            raise ValueError("Meta special_ad_categories=NONE cannot be combined with another category")

        requested_status = str(campaign.get('status') or 'PAUSED').upper()
        if requested_status not in {'PAUSED', 'ACTIVE'}:
            raise ValueError("Meta Campaign status must be PAUSED or ACTIVE")
        if live and requested_status != 'PAUSED':
            raise ValueError("Meta live creation only allows PAUSED Campaigns")
        data = {
            'name': campaign['name'],
            'objective': objective,
            # Graph API models this as an array even when the caller selects
            # the single ``NONE`` category.
            'special_ad_categories': special_ad_categories,
            'is_adset_budget_sharing_enabled': False,
        }
        if campaign.get('buying_type') is not None:
            data['buying_type'] = campaign['buying_type']
        data['status'] = requested_status
        daily_budget = campaign.get('daily_budget', campaign.get('budget'))
        if daily_budget is not None:
            data['daily_budget'] = str(int(float(daily_budget) * 100))  # 转为分
        if campaign.get('lifetime_budget') is not None:
            data['lifetime_budget'] = str(int(float(campaign['lifetime_budget']) * 100))
        if campaign.get('spend_cap') is not None:
            data['spend_cap'] = str(int(float(campaign['spend_cap']) * 100))
        if 'start_time' in campaign:
            data['start_time'] = campaign['start_time']
        if 'end_time' in campaign:
            data['end_time'] = campaign['end_time']
        for field_name in ('catalog_id', 'conversion_specs', 'messaging_apps'):
            if campaign.get(field_name) is not None:
                value = campaign[field_name]
                data[field_name] = json.dumps(value) if isinstance(value, (dict, list)) else value
        
        if not live:
            return {
                "mode": "dry_run",
                "execution_status": "planned",
                "live_support": True,
                "campaign_id": None,
                "account_id": str(account_id),
                "operation": {self._ad_account_edge(account_id, "campaigns"): {"create": data}},
            }
        result = self.request('POST', self._ad_account_edge(account_id, "campaigns"), data=data)
        resource_id = result.get('id') if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta campaign create")
    
    def update_campaign(self, campaign_id: str, updates: dict, live: bool = False) -> dict:
        """更新 Campaign"""
        data = {k: v for k, v in updates.items() if v is not None}
        daily_budget = data.pop('daily_budget', data.pop('budget', None))
        if daily_budget is not None:
            data['daily_budget'] = str(int(float(daily_budget) * 100))
        if not live:
            return {
                "mode": "dry_run", "execution_status": "planned", "live_support": True,
                "campaign_id": str(campaign_id), "operation": {f"/{campaign_id}": {"update": data}},
            }
        return self.request('POST', f"/{campaign_id}", data=data)
    
    def pause_campaign(self, campaign_id: str) -> dict:
        """暂停 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> dict:
        """恢复 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'ACTIVE'})

    def delete_campaign(self, account_id: str, campaign_id: str) -> dict:
        """Delete a Campaign after proving it belongs to the ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        campaign_id = self._clean_meta_id(campaign_id, "campaign_id")
        if not self.resource_belongs_to_account(account_id, "campaign", campaign_id):
            raise PermissionError(
                f"Meta campaign {campaign_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{campaign_id}")
        return {"success": True, "campaign_id": campaign_id}
    
    # ==================== Ad Set 管理 ====================
    
    def list_adsets(self, account_id: str, campaign_id: str = None, limit: int = 25) -> list:
        """获取 Ad Set 列表"""
        clean_account_id = self._clean_meta_id(account_id, "account_id")
        # Meta's account-level ``/{ad-account}/adsets`` edge accepts a
        # ``campaign_id`` query parameter in some API versions but ignores
        # it in others.  Query the Campaign node edge when a parent was
        # supplied so a lookup can never mix Ad Sets from another campaign.
        parent_campaign_id = None
        if campaign_id not in (None, ""):
            parent_campaign_id = self._clean_meta_id(campaign_id, "campaign_id")
            endpoint = f"/{parent_campaign_id}/adsets"
        else:
            endpoint = f"/act_{clean_account_id}/adsets"
        params = {
            'limit': limit,
            'fields': 'id,name,status,budget_remaining,daily_budget,campaign{id,name}'
        }
        rows = self._list_graph_pages(clean_account_id, endpoint, params)
        # Keep a second boundary in case a provider proxy returns a broader
        # page than requested.  Do not silently return unscoped rows.
        if parent_campaign_id:
            return [
                row for row in rows
                if isinstance(row, dict)
                and str(
                    (row.get("campaign") or {}).get("id")
                    if isinstance(row.get("campaign"), dict)
                    else row.get("campaign_id") or ""
                ) == parent_campaign_id
            ]
        return rows
    
    def get_adset(self, adset_id: str, fields: list = None) -> dict:
        """获取 Ad Set 详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,campaign_id,status,daily_budget,bid_amount,targeting'}
        return self.require_resource_object(
            self.request('GET', f"/{adset_id}", extra_params=params),
            "Meta ad set get",
        )
    
    def create_adset(self, account_id: str, campaign_id: str, adset: dict, live: bool = False) -> str:
        """创建 Ad Set
        
        Meta Graph API 要求：
        - optimization_goal: 必须使用有效值
        - billing_event: 必须指定
        - targeting: 必须指定（即使是空对象）
        - bid_amount: 仅在 BID_CAP/COST_CAP 策略下指定
        """
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        
        # 确保 targeting 是 JSON 字符串
        targeting = adset.get('targeting', {'geo_locations': {'countries': ['US']}})
        if isinstance(targeting, dict):
            targeting = json.dumps(targeting)
        
        daily_budget = adset.get('daily_budget', adset.get('budget'))
        bid_strategy = adset.get(
            'bid_strategy', adset.get('bidding_strategy', 'LOWEST_COST_WITHOUT_CAP')
        )
        bid_amount = adset.get('bid_amount')
        if bid_strategy in {"LOWEST_COST_WITH_BID_CAP", "COST_CAP"} and bid_amount is None:
            raise ValueError(f"Meta {bid_strategy} requires bid_amount")
        if bid_amount is not None and bid_strategy not in {
            "LOWEST_COST_WITH_BID_CAP", "COST_CAP",
        }:
            raise ValueError(
                f"Meta {bid_strategy} does not accept bid_amount; use a bid-cap strategy"
            )
        if bid_strategy == "LOWEST_COST_WITH_MIN_ROAS" and adset.get("roas_average_floor") is None:
            raise ValueError("Meta LOWEST_COST_WITH_MIN_ROAS requires roas_average_floor")
        requested_status = str(adset.get('status') or 'PAUSED').upper()
        if requested_status not in {'PAUSED', 'ACTIVE'}:
            raise ValueError("Meta Ad Set status must be PAUSED or ACTIVE")
        if live and requested_status != 'PAUSED':
            raise ValueError("Meta live creation only allows PAUSED Ad Sets")
        data = {
            'name': adset['name'],
            'campaign_id': campaign_id,
            'optimization_goal': adset.get('optimization_goal', 'REACH'),
            'billing_event': adset.get('billing_event', 'IMPRESSIONS'),
            'targeting': targeting,
            'status': requested_status,
        }
        # Always preserve the selected strategy on the wire.  The test
        # account can carry a different account-level default (including a
        # bid-cap strategy); omitting the field therefore does not mean
        # "lowest cost without cap" to Graph.  The input validation above
        # still prevents capped strategies without their required amount.
        data['bid_strategy'] = bid_strategy
        if bid_amount is not None:
            data['bid_amount'] = str(bid_amount)
        # ``promoted_object`` is required by several conversion/app/catalog
        # optimization goals. Preserve the complete schema-declared object
        # instead of silently dropping it before the Graph request.
        promoted_object = adset.get('promoted_object')
        if promoted_object is not None:
            if not isinstance(promoted_object, dict):
                raise ValueError("Meta Ad Set promoted_object must be an object")
            data['promoted_object'] = json.dumps(promoted_object)
        if adset.get('roas_average_floor') is not None:
            data['roas_average_floor'] = str(adset['roas_average_floor'])
        for field_name in ('lead_gen_config', 'product_set_id', 'messaging_apps'):
            if adset.get(field_name) is not None:
                value = adset[field_name]
                data[field_name] = json.dumps(value) if isinstance(value, (dict, list)) else value
        if daily_budget is not None:
            data['daily_budget'] = str(int(float(daily_budget) * 100))
        elif adset.get('lifetime_budget') is not None:
            data['lifetime_budget'] = str(int(float(adset['lifetime_budget']) * 100))
        if 'start_time' in adset:
            data['start_time'] = adset['start_time']
        if 'end_time' in adset:
            data['end_time'] = adset['end_time']
        if not live:
            return {
                "mode": "dry_run",
                "execution_status": "planned",
                "live_support": True,
                "adset_id": None,
                "account_id": str(account_id),
                "campaign_id": str(campaign_id),
                "operation": {self._ad_account_edge(account_id, "adsets"): {"create": data}},
            }
        result = self.request('POST', self._ad_account_edge(account_id, "adsets"), data=data)
        resource_id = result.get('id') if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta ad set create")
    
    def update_adset(self, adset_id: str, updates: dict, live: bool = False) -> dict:
        """更新 Ad Set"""
        data = {k: v for k, v in updates.items() if v is not None}
        # Accept the historical client-side alias while normalizing the
        # provider payload to Meta's official Graph field name.
        if 'bidding_strategy' in data and 'bid_strategy' not in data:
            data['bid_strategy'] = data.pop('bidding_strategy')
        if 'bid_amount' in data:
            data['bid_amount'] = str(data['bid_amount'])
        if 'daily_budget' in data:
            data['daily_budget'] = str(int(float(data['daily_budget']) * 100))
        if isinstance(data.get('targeting'), dict):
            data['targeting'] = json.dumps(data['targeting'])
        if not live:
            return {
                "mode": "dry_run", "execution_status": "planned", "live_support": True,
                "adset_id": str(adset_id), "operation": {f"/{adset_id}": {"update": data}},
            }
        return self.request('POST', f"/{adset_id}", data=data)
    
    def pause_adset(self, adset_id: str) -> dict:
        """暂停 Ad Set"""
        return self.update_adset(adset_id, {'status': 'PAUSED'})

    def delete_adset(self, account_id: str, adset_id: str) -> dict:
        """Delete an Ad Set after proving it belongs to the ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        adset_id = self._clean_meta_id(adset_id, "adset_id")
        if not self.resource_belongs_to_account(account_id, "ad_set", adset_id):
            raise PermissionError(
                f"Meta ad set {adset_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{adset_id}")
        return {"success": True, "adset_id": adset_id}
    
    # ==================== Ad 管理 ====================
    
    def list_ads(self, account_id: str, adset_id: str = None, limit: int = 25) -> list:
        """获取 Ad 列表"""
        clean_account_id = self._clean_meta_id(account_id, "account_id")
        # As with Ad Sets, the account-level Ad edge may ignore an
        # ``adset_id`` query parameter.  A parent node edge is the provider
        # contract that gives us a reliably scoped read-back.
        parent_adset_id = None
        if adset_id not in (None, ""):
            parent_adset_id = self._clean_meta_id(adset_id, "adset_id")
            endpoint = f"/{parent_adset_id}/ads"
        else:
            endpoint = f"/act_{clean_account_id}/ads"
        params = {
            'limit': limit,
            'fields': 'id,name,status,adset_id'
        }
        rows = self._list_graph_pages(clean_account_id, endpoint, params)
        if parent_adset_id:
            return [
                row for row in rows
                if isinstance(row, dict)
                and str(row.get("adset_id") or row.get("ad_set_id") or "")
                == parent_adset_id
            ]
        return rows
    
    def get_ad(self, ad_id: str, fields: list = None) -> dict:
        """获取 Ad 详情"""
        params = {
            'fields': ','.join(fields) if fields else 'id,name,status,adset_id'
        }
        return self.require_resource_object(
            self.request('GET', f"/{ad_id}", extra_params=params),
            "Meta ad get",
        )
    
    def create_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """创建 Ad
        
        Meta Graph API 要求：
        - creative: 必须是有效的 JSON 对象（包含 page_id 和 link_data）
        - 需要使用有效的 Facebook Page ID
        """
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        
        # 构建 creative 参数
        creative = {}
        if ad.get('creative_id'):
            creative['creative_id'] = ad['creative_id']
        elif ad.get('object_story_spec'):
            creative['object_story_spec'] = ad['object_story_spec']
        elif ad.get('creative'):
            creative = ad['creative']
        else:
            # Never invent a Page, destination URL, or advertising message.
            # A live create must be explicit about its creative ownership and
            # destination; dry-run planning does not need a provider payload.
            raise ValueError(
                "Meta Ad creative is required: provide creative_id or "
                "object_story_spec"
            )
        
        requested_status = str(ad.get('status') or 'PAUSED').upper()
        if requested_status not in {'PAUSED', 'ACTIVE'}:
            raise ValueError("Meta Ad status must be PAUSED or ACTIVE")
        if live and requested_status != 'PAUSED':
            raise ValueError("Meta live creation only allows PAUSED Ads")
        data = {
            'name': ad.get('name', 'Untitled Ad'),
            'adset_id': adset_id,
            'creative': json.dumps(creative),  # 必须是 JSON 字符串
            'body': ad.get('body', ''),
            'title': ad.get('title', ''),
            'description': ad.get('description', ''),
            'url_tags': ad.get('url_tags', ''),
            'status': requested_status,
        }
        # 素材
        if ad.get('media') or ad.get('image_url'):
            media = ad.get('media', [{'type': 'image', 'url': ad.get('image_url')}])
            if not isinstance(media, list) or not media or not isinstance(media[0], dict):
                raise ValueError("Meta Ad media must contain at least one object")
            media_url = media[0].get('url')
            if not media_url:
                raise ValueError("Meta Ad media requires a non-empty url")
            data['creative'] = json.dumps({'attachment_link': media_url})
        
        if not live:
            return {
                "mode": "dry_run",
                "execution_status": "planned",
                "live_support": True,
                "ad_id": None,
                "account_id": str(account_id),
                "adset_id": str(adset_id),
                "operation": {self._ad_account_edge(account_id, "ads"): {"create": data}},
            }
        result = self.request('POST', self._ad_account_edge(account_id, "ads"), data=data)
        resource_id = result.get('id') if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta ad create")

    def create_lead_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """Create a Lead Ads ad wired to an existing Instant Form.

        The form is selected by its account/page-scoped ID; form discovery and
        publication validation remain separate read operations.  This method
        only owns the provider-specific ``object_story_spec`` translation.
        """
        if not isinstance(ad, dict):
            raise ValueError("lead ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        form_id = str(ad.get("form_id") or "").strip()
        if not page_id or not form_id:
            raise ValueError("page_id and form_id are required")
        cta_type = str(ad.get("call_to_action_type") or "SIGN_UP").upper()
        if cta_type not in {"SIGN_UP", "LEARN_MORE", "CONTACT_US"}:
            raise ValueError("Unsupported Lead Ads CTA type")

        link_data: dict[str, Any] = {
            "message": ad.get("message", ""),
            "name": ad.get("headline", ""),
            "description": ad.get("description", ""),
            "call_to_action": {
                "type": cta_type,
                "value": {"lead_gen_form_id": form_id},
            },
        }
        if ad.get("link"):
            link_data["link"] = ad["link"]
        return self.create_ad(
            account_id,
            adset_id,
            {
                "name": ad.get("name", "Untitled Lead Ad"),
                "status": ad.get("status", "PAUSED"),
                "object_story_spec": {"page_id": page_id, "link_data": link_data},
            },
            live=live,
        )

    def create_catalog_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """Create a Catalog/Dynamic Product Ad provider payload."""
        if not isinstance(ad, dict):
            raise ValueError("catalog ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        product_set_id = str(ad.get("product_set_id") or "").strip()
        link = str(ad.get("link") or "").strip()
        if not page_id or not product_set_id or not link:
            raise ValueError("page_id, product_set_id and link are required")

        ad_style = str(ad.get("ad_style") or "CAROUSEL").upper()
        if ad_style not in {"CAROUSEL", "COLLAGE", "PRODUCT_SET"}:
            raise ValueError("Unsupported Catalog Ad style")
        cta_type = str(ad.get("call_to_action_type") or "SHOP_NOW").upper()
        if cta_type not in {"SHOP_NOW", "LEARN_MORE", "BUY_NOW"}:
            raise ValueError("Unsupported Catalog Ad CTA type")

        format_options = {
            "CAROUSEL": "carousel_images_multi_items",
            "COLLAGE": "carousel_slideshows",
            "PRODUCT_SET": "single_image",
        }
        template_data: dict[str, Any] = {
            "link": link,
            "message": ad.get("message", ""),
            "name": ad.get("headline", ""),
            "description": ad.get("description", ""),
            "call_to_action": {"type": cta_type},
            # Product set selection belongs to the parent Ad Set's
            # ``promoted_object``. Meta rejects it inside template_data.
            # Keep the selected format explicit for the supported catalog
            # creative contract.
            "format_option": format_options[ad_style],
        }
        return self.create_ad(
            account_id,
            adset_id,
            {
                "name": ad.get("name", "Untitled Catalog Ad"),
                "status": ad.get("status", "PAUSED"),
                "object_story_spec": {
                    "page_id": page_id,
                    "template_data": template_data,
                },
            },
            live=live,
        )
    
    def create_messaging_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """Create a click-to-message ad with a provider-shaped story spec."""
        if not isinstance(ad, dict):
            raise ValueError("messaging ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        messaging_app = str(ad.get("messaging_app") or "").upper().strip()
        cta_type = str(ad.get("call_to_action_type") or "").upper().strip()
        if not page_id or messaging_app not in {"MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"}:
            raise ValueError("page_id and a supported messaging_app are required")
        expected_cta = "WHATSAPP" if messaging_app == "WHATSAPP" else "SEND_MESSAGE"
        if cta_type != expected_cta:
            raise ValueError(f"{messaging_app} destination requires {expected_cta} CTA")

        link_data: dict[str, Any] = {
            "message": ad.get("message", ""),
            "name": ad.get("headline", ""),
            "description": ad.get("description", ""),
            "call_to_action": {"type": cta_type},
        }
        if ad.get("link"):
            link_data["link"] = ad["link"]
        return self.create_ad(
            account_id,
            adset_id,
            {
                "name": ad.get("name", "Untitled Messaging Ad"),
                "status": ad.get("status", "PAUSED"),
                "object_story_spec": {
                    "page_id": page_id,
                    "link_data": link_data,
                },
            },
            live=live,
        )

    def create_link_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """Create a website-link image or video ad."""
        if not isinstance(ad, dict):
            raise ValueError("link ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        link = str(ad.get("link") or "").strip()
        media_type = str(ad.get("media_type") or "IMAGE").upper().strip()
        cta_type = str(ad.get("call_to_action_type") or "LEARN_MORE").upper().strip()
        if not page_id or not link:
            raise ValueError("page_id and link are required")
        if media_type not in {"IMAGE", "VIDEO"}:
            raise ValueError("media_type must be IMAGE or VIDEO")
        if cta_type not in {"LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US"}:
            raise ValueError("Unsupported link ad CTA type")

        if media_type == "VIDEO":
            video_id = str(ad.get("video_id") or "").strip()
            if not video_id:
                raise ValueError("VIDEO link creatives require video_id")
            creative_spec = {
                "page_id": page_id,
                "video_data": {
                    "video_id": video_id,
                    "message": ad.get("message", ""),
                    "title": ad.get("headline", ""),
                    "call_to_action": {
                        "type": cta_type,
                        "value": {"link": link},
                    },
                },
            }
        else:
            link_data: dict[str, Any] = {
                "link": link,
                "message": ad.get("message", ""),
                "name": ad.get("headline", ""),
                "description": ad.get("description", ""),
                "call_to_action": {"type": cta_type},
            }
            if ad.get("image_hash"):
                link_data["image_hash"] = ad["image_hash"]
            creative_spec = {"page_id": page_id, "link_data": link_data}

        return self.create_ad(
            account_id,
            adset_id,
            {
                "name": ad.get("name", "Untitled Link Ad"),
                "status": ad.get("status", "PAUSED"),
                "object_story_spec": creative_spec,
            },
            live=live,
        )

    def create_engagement_ad(self, account_id: str, adset_id: str, ad: dict, live: bool = False) -> str:
        """Create a post-engagement or video-views ad."""
        if not isinstance(ad, dict):
            raise ValueError("engagement ad must be an object")
        page_id = str(ad.get("page_id") or "").strip()
        engagement_type = str(ad.get("engagement_type") or "").upper().strip()
        if not page_id or engagement_type not in {"POST_ENGAGEMENT", "VIDEO_VIEWS"}:
            raise ValueError(
                "page_id and engagement_type=POST_ENGAGEMENT or VIDEO_VIEWS are required"
            )

        if engagement_type == "POST_ENGAGEMENT":
            post_id = str(ad.get("post_id") or "").strip()
            if not post_id:
                raise ValueError("POST_ENGAGEMENT creatives require post_id")
            creative_spec = {"page_id": page_id, "post_id": post_id}
        else:
            video_id = str(ad.get("video_id") or "").strip()
            cta_type = str(ad.get("call_to_action_type") or "WATCH_VIDEO").upper().strip()
            if not video_id:
                raise ValueError("VIDEO_VIEWS creatives require video_id")
            if cta_type != "WATCH_VIDEO":
                raise ValueError("VIDEO_VIEWS creatives require WATCH_VIDEO CTA")
            creative_spec = {
                "page_id": page_id,
                "video_data": {
                    "video_id": video_id,
                    "message": ad.get("message", ""),
                    "title": ad.get("headline", ""),
                    "call_to_action": {"type": cta_type},
                },
            }

        return self.create_ad(
            account_id,
            adset_id,
            {
                "name": ad.get("name", "Untitled Engagement Ad"),
                "status": ad.get("status", "PAUSED"),
                "object_story_spec": creative_spec,
            },
            live=live,
        )

    def update_ad(self, ad_id: str, updates: dict, live: bool = False) -> dict:
        """更新 Ad"""
        data = {k: v for k, v in updates.items() if v is not None}
        if not live:
            return {
                "mode": "dry_run", "execution_status": "planned", "live_support": True,
                "ad_id": str(ad_id), "operation": {f"/{ad_id}": {"update": data}},
            }
        return self.request('POST', f"/{ad_id}", data=data)
    
    def pause_ad(self, ad_id: str) -> dict:
        """暂停 Ad"""
        return self.update_ad(ad_id, {'status': 'PAUSED'})

    def delete_ad(self, account_id: str, ad_id: str) -> dict:
        """Delete an Ad after proving it belongs to the ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        ad_id = self._clean_meta_id(ad_id, "ad_id")
        if not self.resource_belongs_to_account(account_id, "ad", ad_id):
            raise PermissionError(
                f"Meta ad {ad_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{ad_id}")
        return {"success": True, "ad_id": ad_id}
    
    # ==================== Creative 管理 ====================
    
    def create_creative(self, account_id: str, creative: dict, live: bool = False) -> dict | str:
        """Build or create a Creative.

        Creative creation is a write operation and must obey the same
        provider-boundary live switch as Campaign/Ad Set/Ad creation.  The
        dry-run branch deliberately performs no Graph request.
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        story_spec = {
            'page_id': creative.get('page_id', ''),
            'link_data': {
                'message': creative.get('message', ''),
                'link': creative.get('link', ''),
                'image_hash': creative.get('image_hash', ''),
            },
        }
        call_to_action_type = str(
            creative.get('call_to_action_type') or ''
        ).strip().upper()
        if call_to_action_type:
            story_spec['link_data']['call_to_action'] = {
                'type': call_to_action_type,
                'value': {'link': creative.get('link', '')},
            }
        data = {
            'name': creative.get('name', 'Creative'),
            # Raw Graph requests need the SDK's JSON encoding explicitly.
            'object_story_spec': json.dumps(story_spec, separators=(',', ':')),
        }
        if creative.get('image_url'):
            story_spec['link_data']['image_url'] = creative['image_url']
            data['object_story_spec'] = json.dumps(story_spec, separators=(',', ':'))

        if not live:
            return {
                "mode": "dry_run",
                "execution_status": "planned",
                "live_support": True,
                "creative_id": None,
                "account_id": account_id,
                "operation": {f"/act_{account_id}/adcreatives": {"create": data}},
            }

        self.acquire_rate_limit(self._get_account_limiter(account_id))
        
        # Meta's account edge is named ``adcreatives`` for both listing and
        # creation. ``creatives`` is not a writable ad-account edge.
        result = self.request('POST', f"/act_{account_id}/adcreatives", data=data)
        resource_id = result.get('id') if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta creative create")

    def list_creatives(self, account_id: str, limit: int = 25) -> list:
        """List ad creatives owned by a Meta ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        return self._list_graph_pages(
            account_id,
            f"/act_{account_id}/adcreatives",
            {
                "limit": limit,
                "fields": "id,name,object_story_spec,thumbnail_url,body,title,call_to_action_type",
            },
        )

    # ==================== Image / Video Asset 管理 ====================

    @staticmethod
    def _require_https_asset_url(value: Any, field_name: str) -> str:
        """Accept only provider-fetchable HTTP(S) asset URLs."""
        url = str(value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
        return url

    def list_image_assets(self, account_id: str, limit: int = 25) -> list:
        """List image assets uploaded to a Meta ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("image asset limit must be between 1 and 1000")
        result = self.request(
            "GET", f"/act_{account_id}/adimages",
            extra_params={
                "limit": limit,
                # Picker/creation flows only need a stable asset reference and
                # display metadata.  Do not pull the provider's signed image
                # URLs into Runtime context; they can be very large and are
                # not needed to submit an image-hash creative.
                "fields": "hash,name,original_width,original_height,created_time",
            },
        )
        # Meta's adimages edge returns an object keyed by filename/hash rather
        # than the usual Graph ``data`` list. Normalize it at the Provider
        # boundary so Runtime and Skills see one stable list shape.
        if isinstance(result, dict) and isinstance(result.get("images"), dict):
            assets = []
            for key, value in result["images"].items():
                if isinstance(value, dict):
                    asset = dict(value)
                    asset.setdefault("name", key)
                    assets.append(asset)
            return assets[:limit]
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            return result["data"][:limit]
        return result[:limit] if isinstance(result, list) else []

    def upload_image_asset(self, account_id: str, asset: dict) -> dict:
        """Upload one remotely hosted image and return its provider hash."""
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(asset, dict):
            raise ValueError("image asset must be an object")
        unknown = sorted(set(asset) - {"image_url", "name"})
        if unknown:
            raise ValueError(f"unsupported Meta image asset fields: {', '.join(unknown)}")
        image_url = self._require_https_asset_url(asset.get("image_url"), "image_url")
        data: dict[str, Any] = {"url": image_url}
        if asset.get("name") is not None:
            name = str(asset["name"]).strip()
            if not name:
                raise ValueError("image asset name must be non-empty when provided")
            data["name"] = name
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/act_{account_id}/adimages", data=data)
        if isinstance(result, dict) and isinstance(result.get("images"), dict):
            entries = [value for value in result["images"].values() if isinstance(value, dict)]
            if len(entries) == 1:
                result = entries[0]
        result = self.require_resource_object(result, "Meta image asset upload")
        if not str(result.get("hash") or "").strip():
            raise APIError("Meta image asset upload response did not contain an image hash")
        return result

    def list_video_assets(self, account_id: str, limit: int = 25) -> list:
        """List video assets uploaded to a Meta ad account."""
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("video asset limit must be between 1 and 1000")
        return self._list_graph_pages(
            account_id,
            f"/act_{account_id}/advideos",
            {
                "limit": limit,
                "fields": "id,title,description,status,created_time,permalink_url",
            },
        )

    def upload_video_asset(self, account_id: str, asset: dict) -> dict:
        """Start a Meta video upload from a remotely hosted file URL."""
        account_id = self._clean_meta_id(account_id, "account_id")
        if not isinstance(asset, dict):
            raise ValueError("video asset must be an object")
        unknown = sorted(set(asset) - {"file_url", "title", "description"})
        if unknown:
            raise ValueError(f"unsupported Meta video asset fields: {', '.join(unknown)}")
        file_url = self._require_https_asset_url(asset.get("file_url"), "file_url")
        data: dict[str, Any] = {"file_url": file_url}
        for field_name in ("title", "description"):
            if asset.get(field_name) is not None:
                value = str(asset[field_name]).strip()
                if not value:
                    raise ValueError(f"video asset {field_name} must be non-empty when provided")
                data[field_name] = value
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.require_resource_object(
            self.request("POST", f"/act_{account_id}/advideos", data=data),
            "Meta video asset upload",
        )
        if not str(result.get("id") or "").strip():
            raise APIError("Meta video asset upload response did not contain a video ID")
        return result

    def get_creative(self, account_id: str, creative_id: str, fields: list = None) -> dict:
        """Get one Creative after verifying account ownership."""
        account_id = self._clean_meta_id(account_id, "account_id")
        creative_id = self._clean_meta_id(creative_id, "creative_id")
        if not self.resource_belongs_to_account(account_id, "creative", creative_id):
            raise PermissionError(
                f"Meta creative {creative_id} does not belong to account {account_id}"
            )
        params = {
            "fields": ",".join(fields) if fields else (
                "id,name,object_story_spec,thumbnail_url,body,title,call_to_action_type"
            )
        }
        return self.require_resource_object(
            self.request("GET", f"/{creative_id}", extra_params=params),
            "Meta creative get",
        )

    def update_creative(self, account_id: str, creative_id: str, updates: dict) -> dict:
        """Update the supported mutable Creative field."""
        account_id = self._clean_meta_id(account_id, "account_id")
        creative_id = self._clean_meta_id(creative_id, "creative_id")
        if not self.resource_belongs_to_account(account_id, "creative", creative_id):
            raise PermissionError(
                f"Meta creative {creative_id} does not belong to account {account_id}"
            )
        if not isinstance(updates, dict) or not updates:
            raise ValueError("updates must be a non-empty object")
        unknown = set(updates) - {"name"}
        if unknown:
            raise ValueError(f"Unsupported Meta Creative update fields: {sorted(unknown)}")
        name = str(updates.get("name") or "").strip()
        if not name:
            raise ValueError("Creative name must be a non-empty string")
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        result = self.request("POST", f"/{creative_id}", data={"name": name})
        return {"success": True, "creative_id": creative_id, "result": result}

    def delete_creative(self, account_id: str, creative_id: str) -> dict:
        """Delete a Creative after account ownership verification."""
        account_id = self._clean_meta_id(account_id, "account_id")
        creative_id = self._clean_meta_id(creative_id, "creative_id")
        if not self.resource_belongs_to_account(account_id, "creative", creative_id):
            raise PermissionError(
                f"Meta creative {creative_id} does not belong to account {account_id}"
            )
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        self.request("DELETE", f"/{creative_id}")
        return {"success": True, "creative_id": creative_id}
    
    # ==================== 报表查询 ====================
    
    def get_campaign_report(
        self,
        account_id: str,
        campaign_ids: list[str],
        time_range: Any = None,
        fields: list = None,
        level: str = "campaign",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query bounded Insights rows at Campaign, Ad Set or Ad level.
        
        Args:
            account_id: 广告账户 ID
            campaign_ids: IDs for the selected reporting level
            time_range: date preset or a {since, until} date range
            fields: 指标字段列表
            level: Insights level ("campaign" | "adset" | "ad")
            limit: Maximum total result rows across cursor pages
        """
        account_id = self._clean_meta_id(account_id, "account_id")
        level = str(level or "campaign").strip().lower()
        level_id_fields = {
            "campaign": ("campaign.id", "campaign_id"),
            "adset": ("adset.id", "adset_id"),
            "ad": ("ad.id", "ad_id"),
        }
        if level not in level_id_fields:
            raise ValueError("level must be campaign, adset, or ad")
        if not isinstance(campaign_ids, (list, tuple)):
            raise ValueError("report IDs must be an array")
        normalized_ids = [
            self._clean_meta_id(value, f"{level}_id")
            for value in campaign_ids
        ]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("report IDs must not contain duplicates")
        if isinstance(limit, bool):
            raise ValueError("report limit must be between 1 and 10000")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("report limit must be between 1 and 10000") from exc
        if not 1 <= limit <= 10_000:
            raise ValueError("report limit must be between 1 and 10000")
        filter_field, level_id_field = level_id_fields[level]
        default_fields = [
            "campaign_id",
            *([level_id_field] if level != "campaign" else []),
            "impressions", "clicks", "ctr", "cpc", "spend",
            "purchase_roas", "cost_per_result", "actions", "action_values",
        ]
        selected_fields = fields or default_fields
        if (
            not isinstance(selected_fields, list)
            or any(not isinstance(field, str) or not field.strip() for field in selected_fields)
        ):
            raise ValueError("fields must be an array of non-empty strings")
        params = {
            'level': level,
            'fields': ','.join(selected_fields),
            'limit': limit,
        }
        if normalized_ids:
            params["filtering"] = json.dumps([
                {
                    'field': filter_field,
                    'operator': 'IN',
                    'value': normalized_ids,
                }
            ])
        if isinstance(time_range, dict):
            since = time_range.get("since", time_range.get("start_date"))
            until = time_range.get("until", time_range.get("end_date"))
            if not since or not until:
                raise ValueError(
                    "time_range must provide since/until or start_date/end_date"
                )
            params["time_range"] = json.dumps(
                {"since": str(since), "until": str(until)},
                separators=(",", ":"),
            )
        else:
            params["date_preset"] = str(time_range or "last_7d").strip().lower()

        return self._list_graph_pages(
            account_id,
            self._ad_account_edge(account_id, "insights"),
            params,
        )

    def get_adset_report(
        self,
        account_id: str,
        adset_ids: list[str],
        time_range: Any = None,
        fields: list = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """查询 Ad Set 级别报表"""
        return self.get_campaign_report(
            account_id, adset_ids, time_range, fields, "adset", limit
        )

    def get_ad_report(
        self,
        account_id: str,
        ad_ids: list[str],
        time_range: Any = None,
        fields: list = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """查询 Ad 级别报表"""
        return self.get_campaign_report(
            account_id, ad_ids, time_range, fields, "ad", limit
        )
    
    # ==================== 助推/Spark ====================
    
    def boost_post(self, account_id: str, page_id: str, post_id: str, budget: float, duration_days: int) -> str:
        """
        为 Page 帖子创建 Boost（对应 meta_boost_post 工具）
        
        注意：Boost Post 是 Meta 特有的功能，将已有帖子变成广告
        """
        self.acquire_rate_limit(self._get_account_limiter(account_id))
        
        # Boost 需要通过 PromotedObject 创建
        data = {
            'object_story_id': f"{page_id}_{post_id}",
            'daily_budget': str(int(budget * 100)),
            'scheduled_publish_time': int(time.time()),
            'promoted_object': {'page_id': page_id},
        }
        
        result = self.request('POST', f"/{account_id}/promoted_objects", data=data)
        resource_id = result.get('id') if isinstance(result, dict) else None
        return self.require_resource_id(resource_id, "Meta boost post")
