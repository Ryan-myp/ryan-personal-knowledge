"""
api_clients/dv360_client.py - DV360 API 生产级客户端（纯 Python 实现）

完全绕过 google-auth/cryptography SDK，使用纯 Python + subprocess 实现 JWT 签名。
这样在 cryptography 包有架构问题的环境下也能工作。

认证流程：
1. 用 RSA 私钥生成 JWT Assertion（subprocess openssl）
2. 用 JWT 换取 OAuth2 Access Token
3. 用 Access Token 调用 DV360 API
"""

import json
import time
import base64
import hmac
import hashlib
import logging
import subprocess
import tempfile
import os
import threading
from typing import Any, Optional
from datetime import datetime, timezone

from .base import BasePlatformClient, APIError, AuthError, RateLimitError, TemporaryError, RetryConfig, RateLimiter

logger = logging.getLogger(__name__)


class DV360APIClient(BasePlatformClient):
    """
    DV360 API 客户端（纯 Python，无 cryptography 依赖）
    
    官方文档: https://developers.google.com/display-video/api
    认证: Service Account JWT Bearer (RS256)
    API 版本: v4
    
    不使用 google-auth SDK，自行实现 JWT 签名和 Token 交换。
    """
    
    BASE_URL = "https://display-video.googleapis.com/v4"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = [
        "https://www.googleapis.com/auth/display-video",
        "https://www.googleapis.com/auth/display-video-user-management",
    ]
    
    def __init__(
        self,
        credentials: dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "dv360", retry_config)
        self.sa_email = self.credentials.get('service_account_email', '')
        self.private_key = self.credentials.get('private_key', '')
        self.partner_id = self.credentials.get('partner_id', '')
        self.private_key_id = self.credentials.get('private_key_id', '')
        # Use a caller-provided token as a caller-managed token when no
        # explicit expiry is supplied.  Refreshed state stays in this client
        # and is never written back to the credential dictionary.
        self._access_token: Optional[str] = self.credentials.get('access_token') or None
        raw_expiry = self.credentials.get(
            'access_token_expires_at', self.credentials.get('token_expiry', 0)
        ) or 0
        try:
            self._token_expiry = float(raw_expiry)
        except (TypeError, ValueError):
            self._token_expiry = 0
        self._token_lock = threading.RLock()
        self._rate_limiter = RateLimiter(max_requests=100, period=60)
    
    def _get_access_token(self) -> str:
        """获取或刷新 Access Token"""
        with self._token_lock:
            now = time.time()
            if self._access_token and (
                not self._token_expiry or now < self._token_expiry - 60
            ):
                return self._access_token

            jwt_assertion = self._generate_jwt_assertion()
            resp_data = self._exchange_token(jwt_assertion)

            self._access_token = resp_data['access_token']
            self._token_expiry = now + resp_data.get('expires_in', 3600)

            return self._access_token

    def _reset_auth(self) -> bool:
        """Clear a stale service-account token before one safe read retry."""
        if not (self.sa_email and self.private_key):
            return False
        with self._token_lock:
            self._access_token = None
            self._token_expiry = 0
        return True
    
    def _generate_jwt_assertion(self) -> str:
        """
        生成 JWT Assertion（使用 openssl 命令行，避免 cryptography 依赖）
        """
        header = {"typ": "JWT", "alg": "RS256"}
        # Key IDs are credential-specific. Never substitute a hard-coded
        # production key ID; include it only when the caller supplied one.
        if self.private_key_id:
            header["kid"] = self.private_key_id
        
        now = int(time.time())
        payload = {
            "iss": self.sa_email,
            "sub": self.sa_email,
            "aud": self.TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
            "scope": " ".join(self.SCOPES),
        }
        if self.partner_id:
            payload["partner_id"] = self.partner_id
        
        header_b64 = self._b64url(json.dumps(header, separators=(',', ':')))
        payload_b64 = self._b64url(json.dumps(payload, separators=(',', ':')))
        
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        
        # 使用 openssl 签名（避免 cryptography 依赖）
        signature = self._sign_with_openssl(signing_input)
        signature_b64 = self._b64url(signature)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def _sign_with_openssl(self, data: bytes) -> bytes:
        """使用 openssl 命令行进行 RSA-SHA256 签名"""
        # 将私钥写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(self.private_key)
            key_path = f.name
        
        try:
            # 使用 openssl 签名
            result = subprocess.run(
                ['openssl', 'dgst', '-sha256', '-sign', key_path],
                input=data,
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise APIError(f"openssl sign failed: {result.stderr.decode()}")
            return result.stdout
        finally:
            os.unlink(key_path)
    
    def _exchange_token(self, jwt_assertion: str) -> dict:
        """用 JWT Assertion 换取 Access Token"""
        import requests as _requests
        
        resp = _requests.post(
            self.TOKEN_URL,
            data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': jwt_assertion,
            },
            timeout=self.http_timeout(),
        )
        
        if resp.status_code != 200:
            raise AuthError(f"Failed to exchange token: {resp.text}")
        
        return resp.json()
    
    def _b64url(self, data) -> str:
        """Base64URL 编码"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        self.acquire_rate_limit(self._rate_limiter)
        
        token = self._get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            **kwargs.get('headers', {}),
        }
        
        import requests as _requests
        
        try:
            if method == 'GET':
                resp = _requests.get(url, headers=headers, params=kwargs.get('params'), timeout=self.http_timeout())
            elif method == 'POST':
                resp = _requests.post(url, headers=headers, json=kwargs.get('data'), timeout=self.http_timeout())
            elif method == 'PUT':
                resp = _requests.put(url, headers=headers, json=kwargs.get('data'), timeout=self.http_timeout())
            elif method == 'PATCH':
                resp = _requests.patch(
                    url,
                    headers=headers,
                    json=kwargs.get('data'),
                    timeout=self.http_timeout(),
                )
            elif method == 'DELETE':
                resp = _requests.delete(url, headers=headers, timeout=self.http_timeout())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            try:
                data = resp.json() if resp.content else {}
            except Exception:
                data = {}
            return {
                'status_code': resp.status_code,
                'data': data,
                'headers': dict(resp.headers),
            }
        except _requests.exceptions.Timeout:
            return {'status_code': 504, 'data': {}, 'headers': {}}
        except _requests.exceptions.ConnectionError:
            return {'status_code': 502, 'data': {}, 'headers': {}}
    
    def _extract_data(self, response: dict) -> Any:
        return response.get('data', {})
    
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        data = response.get('data', {})
        
        if status_code == 401:
            # Token 过期，清除缓存并重新获取
            self._access_token = None
            self._token_expiry = 0
            return AuthError("DV360: Token expired, will retry with new token")
        
        if status_code == 403:
            error_msg = data.get('error', {}).get('message', 'Permission denied') if isinstance(data, dict) else 'Permission denied'
            return AuthError(f"DV360: {error_msg}")
        
        if status_code == 429:
            return RateLimitError("DV360: Rate limited", retry_after=60)
        
        if status_code >= 500:
            return TemporaryError(f"DV360 server error {status_code}")

        # Do not treat an empty/non-JSON 4xx response as a successful API
        # call.  Only transient server/rate-limit failures are retryable.
        if status_code >= 400:
            error_msg = "Bad request"
            if isinstance(data, dict):
                error_msg = data.get('error', {}).get('message', error_msg)
            return APIError(
                f"DV360 HTTP {status_code}: {error_msg}",
                status_code=status_code,
                response=data if isinstance(data, dict) else None,
            )
        
        if isinstance(data, dict) and 'error' in data:
            err = data['error']
            message = err.get('message', 'Unknown error')
            code = err.get('code', 'UNKNOWN')
            return APIError(f"DV360 {code}: {message}", status_code=status_code, response=data)
        
        return None

    def _list_pages(
        self, endpoint: str, collection_key: str, params: dict,
        max_pages: int = 100,
    ) -> list:
        """Consume DV360 ``nextPageToken`` pages into one flat list."""
        items: list = []
        page_token = None
        seen_tokens: set[str] = set()
        for _ in range(max_pages):
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            response = self.request_raw("GET", endpoint, params=page_params)
            data = self._response_payload(response)
            page_items = data.get(collection_key, []) if isinstance(data, dict) else []
            if isinstance(page_items, list):
                items.extend(page_items)
            next_token = data.get("nextPageToken") if isinstance(data, dict) else None
            if not next_token or next_token in seen_tokens:
                break
            seen_tokens.add(next_token)
            page_token = next_token
        return items

    @staticmethod
    def _response_payload(response: Any) -> dict[str, Any]:
        """Return DV360 data from either a raw transport or test envelope."""
        if not isinstance(response, dict):
            return {}
        payload = response.get("data", response)
        return payload if isinstance(payload, dict) else {}
    
    # ==================== 账户管理 ====================
    
    def list_advertisers(self, filter: str = None, page_size: int = 20) -> list:
        """获取广告主列表"""
        params = {'pageSize': page_size}
        if filter:
            params['filter'] = filter
        return self._list_pages(
            f"{self.BASE_URL}/advertisers", "advertisers", params
        )
    
    def get_advertiser(self, advertiser_id: str) -> dict:
        """获取广告主详情"""
        result = self.request_raw('GET', f"{self.BASE_URL}/advertisers/{advertiser_id}")
        return self._response_payload(result)
    
    def list_campaigns(self, advertiser_id: str, page_size: int = 20) -> list:
        """获取 Campaign 列表"""
        return self._list_pages(
            f"{self.BASE_URL}/advertisers/{advertiser_id}/campaigns",
            "campaigns", {"pageSize": page_size},
        )
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """获取 Campaign 详情"""
        result = self.request_raw('GET',
                                   f"{self.BASE_URL}/advertisers/{advertiser_id}/campaigns/{campaign_id}")
        return self._response_payload(result)
    
    # ==================== IO (Insertion Order) 管理 ====================
    
    def list_ios(self, advertiser_id: str, page_size: int = 20) -> list:
        """获取 IO 列表"""
        return self._list_pages(
            f"{self.BASE_URL}/advertisers/{advertiser_id}/insertionOrders",
            "insertionOrders", {"pageSize": page_size},
        )
    
    def get_io(self, advertiser_id: str, io_id: str) -> dict:
        """获取 IO 详情"""
        result = self.request_raw('GET', f"{self.BASE_URL}/advertisers/{advertiser_id}/insertionOrders/{io_id}")
        return self._response_payload(result)
    
    def create_io(self, advertiser_id: str, io: dict) -> str:
        """创建 IO"""
        now = datetime.now()
        start_date = io.get('start_date')
        end_date = io.get('end_date')
        try:
            start_seconds = int(
                datetime.strptime(start_date, '%Y-%m-%d')
                .replace(tzinfo=timezone.utc).timestamp()
            ) if start_date else int(now.replace(tzinfo=timezone.utc).timestamp())
            end_seconds = int(
                datetime.strptime(end_date, '%Y-%m-%d')
                .replace(tzinfo=timezone.utc).timestamp()
            ) if end_date else int(
                now.replace(year=now.year + 1, tzinfo=timezone.utc).timestamp()
            )
        except (TypeError, ValueError):
            raise ValueError('start_date/end_date must use YYYY-MM-DD')
        body = {
            'name': io['name'],
            'startDateSeconds': start_seconds,
            'endDateSeconds': end_seconds,
            'spendCapMicros': int(io.get('spend_cap_micros', float(io.get('budget', 1000)) * 1_000_000)),
            'status': io.get('status', 'DRAFT'),
        }
        if io.get('pacing_type'):
            body['pacing'] = {'pacingType': io['pacing_type']}
        if io.get('frequency_cap'):
            body['frequencyCap'] = io['frequency_cap']
        
        result = self.request_raw('POST', f"{self.BASE_URL}/advertisers/{advertiser_id}/insertionOrders", data=body)
        name = self._response_payload(result).get('name', '')
        return name.split('/')[-1] if name else ''
    
    def activate_io(self, advertiser_id: str, io_id: str) -> dict:
        """激活 IO"""
        io = self.get_io(advertiser_id, io_id)
        io['status'] = 'ACTIVE'
        name = f"advertisers/{advertiser_id}/insertionOrders/{io_id}"
        self.request_raw('PATCH', f"{self.BASE_URL}/{name}", data=io)
        return {'success': True, 'io_id': io_id}
    
    def pause_io(self, advertiser_id: str, io_id: str) -> dict:
        """暂停 IO"""
        io = self.get_io(advertiser_id, io_id)
        io['status'] = 'PAUSED'
        name = f"advertisers/{advertiser_id}/insertionOrders/{io_id}"
        self.request_raw('PATCH', f"{self.BASE_URL}/{name}", data=io)
        return {'success': True, 'io_id': io_id}
    
    # ==================== Line Item 管理 ====================
    
    def list_line_items(self, advertiser_id: str, io_id: str = None, page_size: int = 20) -> list:
        """获取 Line Item 列表"""
        parent = f"advertisers/{advertiser_id}"
        if io_id:
            parent += f"/insertionOrders/{io_id}"
        
        return self._list_pages(
            f"{self.BASE_URL}/{parent}/lineItems",
            "lineItems", {"pageSize": page_size},
        )
    
    def create_line_item(self, advertiser_id: str, io_id: str, line_item: dict) -> str:
        """创建 Line Item"""
        raw_goal = line_item.get('goal')
        if isinstance(raw_goal, dict):
            goal = {
                'goalType': raw_goal.get('goalType', raw_goal.get('goal_type', 'IMPRESSIONS')),
            }
            for source, target in (('target_cpa', 'targetCpa'), ('target_roas', 'targetRoas')):
                if raw_goal.get(source) is not None:
                    goal[target] = raw_goal[source]
            # Preserve provider-ready extension fields while normalizing the
            # schema-owned snake_case names above.
            for key, value in raw_goal.items():
                if key not in {'goal_type', 'target_cpa', 'target_roas'}:
                    goal[key] = value
        else:
            goal = raw_goal or {'goalType': 'IMPRESSIONS'}
        body = {
            'name': line_item['name'],
            'goal': goal,
            'targeting': line_item.get('targeting', {}),
            'lineItemType': line_item.get('type', 'SPONSORED'),
            'status': line_item.get('status', 'DRAFT'),
        }
        if line_item.get('budget') is not None:
            body['budget'] = float(line_item['budget'])
        if line_item.get('start_date'):
            body['startDate'] = line_item['start_date']
        if line_item.get('end_date'):
            body['endDate'] = line_item['end_date']
        if line_item.get('bid_strategy'):
            body['bidStrategy'] = line_item['bid_strategy']
        if line_item.get('bid_amount') is not None:
            body['bidAmount'] = float(line_item['bid_amount'])
        
        result = self.request_raw('POST',
                                   f"{self.BASE_URL}/advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems",
                                   data=body)
        name = self._response_payload(result).get('name', '')
        return name.split('/')[-1] if name else ''
    
    def activate_line_item(self, advertiser_id: str, io_id: str, li_id: str) -> dict:
        """激活 Line Item"""
        li = self._get_line_item(advertiser_id, io_id, li_id)
        li['status'] = 'ACTIVE'
        name = f"advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems/{li_id}"
        self.request_raw('PATCH', f"{self.BASE_URL}/{name}", data=li)
        return {'success': True, 'line_item_id': li_id}
    
    def _get_line_item(self, advertiser_id: str, io_id: str, li_id: str) -> dict:
        """获取 Line Item 详情（内部方法）"""
        result = self.request_raw('GET',
                                   f"{self.BASE_URL}/advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems/{li_id}")
        return self._response_payload(result)

    def get_line_item(self, advertiser_id: str, io_id: str, line_item_id: str) -> dict:
        """获取 Line Item 详情。"""
        return self._get_line_item(advertiser_id, io_id, line_item_id)
    
    # ==================== 报表 ====================
    
    def create_report(self, advertiser_id: str, report: dict) -> str:
        """创建报表任务（异步）"""
        result = self.request_raw('POST',
                                   f"{self.BASE_URL}/advertisers/{advertiser_id}/reports",
                                   data=report)
        name = self._response_payload(result).get('name', '')
        return name.split('/')[-1] if name else ''
    
    def get_report_result(self, advertiser_id: str, report_id: str, limit: int = 1000) -> dict:
        """获取报表结果"""
        result = self.request_raw('GET',
                                   f"{self.BASE_URL}/advertisers/{advertiser_id}/reports/{report_id}/rows",
                                   params={'limit': limit})
        return self._response_payload(result)
    
    def get_line_item_report(
        self,
        advertiser_id: str,
        line_item_id: str,
        date_from: str = None,
        date_to: str = None,
    ) -> list:
        """查询 Line Item 级别报表（异步）"""
        from datetime import datetime as dt
        
        date_from = date_from or dt.now().strftime('%Y-%m-%d')
        date_to = date_to or dt.now().strftime('%Y-%m-%d')
        
        report = {
            'name': f"Line Item Report - {line_item_id}",
            'dateRange': {
                'startDate': {'day': int(date_from[8:10]), 'month': int(date_from[5:7]), 'year': int(date_from[:4])},
                'endDate': {'day': int(date_to[8:10]), 'month': int(date_to[5:7]), 'year': int(date_to[:4])},
            },
            'dimensions': ['LINE_ITEM_NAME', 'DATE'],
            'metricColumns': ['IMPRESSIONS', 'CLICKS', 'SPEND'],
            'lineItemFilter': {'lineItemIds': [line_item_id]},
        }
        
        report_id = self.create_report(advertiser_id, report)
        if not report_id:
            raise APIError("DV360 report creation returned no report_id")
        
        # 轮询等待结果（最多 30 秒）
        last_error = None
        for _ in range(30):
            self.sleep_with_budget(1)
            try:
                result = self.get_report_result(advertiser_id, report_id)
                if not isinstance(result, dict):
                    last_error = APIError("DV360 report result has an invalid response envelope")
                    continue
                # An explicit rows field means the asynchronous report is
                # complete, including the valid no-data case.  An envelope
                # without rows is still processing and should be polled.
                if "rows" in result:
                    return result.get("rows") or []
            except AuthError:
                raise
            except APIError as exc:
                last_error = exc
            except Exception as exc:
                last_error = APIError(f"DV360 report polling failed: {exc}")

        if last_error:
            raise APIError(
                f"DV360 report polling timed out or failed: {last_error}"
            )
        raise APIError("DV360 report polling timed out before a result was available")
