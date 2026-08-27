"""
api_clients/tiktok_client.py - TikTok Ads API 生产级客户端

接入已有 scripts/tiktok_api.py，补全重试、限流、错误分类。
"""

import logging
import time
import json
import re
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
    API_VERSION = "open_api/v1.3"
    
    def __init__(
        self,
        credentials: dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "tiktok", retry_config)
        self.access_token = self.credentials.get('access_token', '')
        # 速率限制: 100次/分钟
        self._rate_limiter = RateLimiter(max_requests=100, period=60)
    
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.BASE_URL}/{self.API_VERSION}/{endpoint.lstrip('/')}"

    def _list_pages(self, endpoint: str, params: dict, max_pages: int = 100) -> list:
        """Consume TikTok ``page_info`` pages into one deterministic list."""
        items: list = []
        for page in range(1, max_pages + 1):
            page_params = {**params, "page": page}
            self._rate_limiter.acquire()
            response = self.request_raw(
                "GET", self._build_url(endpoint), params=page_params
            )
            if response.get("status_code") != 200:
                break
            envelope = response.get("data", {})
            payload = envelope.get("data", {}) if isinstance(envelope, dict) else {}
            page_items = payload.get("list", []) if isinstance(payload, dict) else []
            if isinstance(page_items, list):
                items.extend(page_items)
            page_info = payload.get("page_info", {}) if isinstance(payload, dict) else {}
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
        headers = {
            'Access-Token': self.access_token,
            'Content-Type': 'application/json',
            **kwargs.get('headers', {}),
        }
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params'), timeout=self.http_timeout())
            elif method == 'POST':
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
        data = response.get('data', {})
        return data
    
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
        self._rate_limiter.acquire()
        data = {'advertiser_ids': advertiser_ids}
        result = self.request('POST', 'account/get/', data=data)
        return result.get('advertisers', []) if isinstance(result, dict) else result
    
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
        return {}
    
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
        - daily_budget: 每日预算（单位：分）
        - app_promotion_type: APP 推广类型 (APP_RETARGETING, APP_ACQUISITION)
        """
        self._rate_limiter.acquire()
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
        # 可选字段
        if campaign.get('daily_budget'):
            data['daily_budget'] = int(campaign['daily_budget'] * 100)  # 转为分
        if campaign.get('app_promotion_type'):
            data['app_promotion_type'] = campaign['app_promotion_type']
        # Preserve the explicit creation contract.  Previously these fields
        # were accepted by the tool schema but silently discarded here, which
        # made a dry-run plan differ from the eventual provider request.
        for key in ('budget', 'budget_restriction', 'budget_mode', 'campaign_type',
                    'campaign_automation_type', 'objective_type'):
            if key in campaign and campaign[key] not in (None, ''):
                data[key] = campaign[key]
        
        result = self.request('POST', 'campaign/create/', data=data)
        return str(result.get('campaign_id', '')) if isinstance(result, dict) else ''
    
    def update_campaign(self, advertiser_id: str, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'campaign': updates,
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
        self._rate_limiter.acquire()
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
        return {}
    
    def create_adgroup(self, advertiser_id: str, campaign_id: str, adgroup: dict) -> str:
        """创建 Ad Group"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group': {
                'ad_group_name': adgroup['name'],
                'ad_group_status': adgroup.get('status', 1),
                'tracking_url': adgroup.get('tracking_url', ''),
                'bid_amount': int(adgroup.get('bid_amount', 500)),  # 单位为分
                'daily_budget': int(adgroup.get('daily_budget', 50) * 100),
            }
        }
        # New callers use the symbolic values from the parameter catalog;
        # keep the old numeric promote_object_type field for compatibility.
        for key in (
            'promotion_type', 'promote_object_type', 'bid_type', 'placement_type',
            'billing_event', 'deep_bid_type', 'budget_mode', 'budget',
            'app_id', 'landing_url', 'location_ids', 'operating_systems',
            'age_groups', 'gender', 'auto_targeting_enabled', 'optimization_goal',
        ):
            if key in adgroup and adgroup[key] not in (None, ''):
                data['ad_group'][key] = adgroup[key]
        # 定向
        if adgroup.get('targeting'):
            data['ad_group']['targeting'] = adgroup['targeting']
        
        result = self.request('POST', 'adgroup/create/', data=data)
        return str(result.get('ad_group_id', '')) if isinstance(result, dict) else ''
    
    def update_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str, updates: dict) -> dict:
        """更新 Ad Group"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group_id': int(adgroup_id),
            'ad_group': updates,
        }
        return self.request('POST', 'adgroup/update/', data=data)
    
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
        return {}
    
    def create_ad(self, advertiser_id: str, campaign_id: str, adgroup_id: str, ad: dict) -> str:
        """创建 Ad"""
        self._rate_limiter.acquire()
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
        if ad.get('text'):
            data['ad']['text'] = ad['text']
        
        result = self.request('POST', 'ad/create/', data=data)
        return str(result.get('ad_id', '')) if isinstance(result, dict) else ''
    
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
        self._rate_limiter.acquire()
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
        return str(result.get('ad_id', '')) if isinstance(result, dict) else ''
    
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
        self._rate_limiter.acquire()
        
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
        task_id = create_result.get('task_id', '') if isinstance(create_result, dict) else ''
        
        if not task_id:
            return []
        
        # 轮询获取结果
        return self._poll_report_result(advertiser_id, task_id)
    
    def _poll_report_result(self, advertiser_id: str, task_id: str, max_wait: int = 30) -> list:
        """轮询报表任务结果"""
        for i in range(max_wait):
            time.sleep(1)
            data = {'advertiser_id': str(advertiser_id), 'task_id': task_id}
            result = self.request('POST', 'report/task/info/get/', data=data)
            
            if isinstance(result, dict) and result.get('status') in (2, 3):  # COMPLETED/FAILED
                if result.get('status') == 2:
                    return result.get('content', {}).get('data', [])
                return []
        
        return []
    
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
                'time_range': time_range or {'start_date': 'LAST_7_DAYS', 'end_date': 'TODAY'},
                'filtering': filtering,
            }
        }
        result = self.request('POST', 'report/task/create/', data=data)
        task_id = result.get('task_id', '') if isinstance(result, dict) else ''
        return self._poll_report_result(advertiser_id, task_id) if task_id else []

    
    # ==================== 人群定向查询 ====================
    
    def list_audiences(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取人群包列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'audience/get/', params=data)
        audiences = result.get('audience_list', []) if isinstance(result, dict) else []
        return audiences
    
    def get_audience(self, advertiser_id: str, audience_id: str) -> dict:
        """获取人群包详情"""
        filtering = [{'field': 'AUDIENCE_IDS', 'operator': 'IN', 'values': [int(audience_id)]}]
        result = self.list_audiences(advertiser_id, filtering=filtering)
        return result[0] if result else {}
    
    def list_interest_categories(self, parent_ids: list = None) -> list:
        """获取兴趣类别列表"""
        self._rate_limiter.acquire()
        data = {}
        if parent_ids:
            data['parent_ids'] = parent_ids
        result = self.request('GET', 'interest_category/list/', params=data)
        return result.get('list', []) if isinstance(result, dict) else []
    
    def get_interest_category(self, category_id: str) -> dict:
        """获取兴趣类别详情"""
        data = {'category_id': category_id}
        result = self.request('GET', 'interest_category/get/', params=data)
        return result.get('data', {}) if isinstance(result, dict) else {}
    
    # ==================== 地域定向查询 ====================
    
    def list_locations(self, location_type: str = None) -> list:
        """获取地域列表"""
        self._rate_limiter.acquire()
        data = {}
        if location_type:
            data['location_type'] = location_type
        result = self.request('GET', 'location/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def search_locations(self, keyword: str, location_type: str = None) -> list:
        """搜索地域"""
        self._rate_limiter.acquire()
        data = {'keyword': keyword}
        if location_type:
            data['location_type'] = location_type
        result = self.request('GET', 'location/search/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 设备定向查询 ====================
    
    def list_devices(self) -> list:
        """获取设备列表"""
        self._rate_limiter.acquire()
        result = self.request('GET', 'device/get/')
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_operating_systems(self) -> list:
        """获取操作系统列表"""
        self._rate_limiter.acquire()
        result = self.request('GET', 'os/get/')
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_carriers(self) -> list:
        """获取运营商列表"""
        self._rate_limiter.acquire()
        result = self.request('GET', 'carrier/get/')
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_browsers(self) -> list:
        """获取浏览器列表"""
        self._rate_limiter.acquire()
        result = self.request('GET', 'browser/get/')
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 创意素材查询 ====================
    
    def list_creatives(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取创意列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'creative/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_videos(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取视频列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'video/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_images(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取图片列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'image/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 转化追踪查询 ====================
    
    def list_conversions(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取转化事件列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'conversion/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def get_conversion(self, advertiser_id: str, conversion_id: str) -> dict:
        """获取转化事件详情"""
        filtering = [{'field': 'CONVERSION_IDS', 'operator': 'IN', 'values': [int(conversion_id)]}]
        result = self.list_conversions(advertiser_id, filtering=filtering)
        return result[0] if result else {}
    
    # ==================== 商品目录查询 ====================
    
    def list_catalogs(self, advertiser_id: str, filtering: list = None, page_size: int = 20) -> list:
        """获取商品目录列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'catalog/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    def list_product_sets(self, advertiser_id: str, catalog_id: str = None, filtering: list = None, page_size: int = 20) -> list:
        """获取商品集列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if catalog_id:
            data['catalog_id'] = str(catalog_id)
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'product_set/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 应用信息查询 ====================
    
    def list_apps(self, filtering: list = None, page_size: int = 20) -> list:
        """获取应用列表"""
        self._rate_limiter.acquire()
        data = {'page_size': page_size}
        if filtering:
            data['filtering'] = filtering
        result = self.request('GET', 'app/get/', params=data)
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 品牌安全查询 ====================
    
    def list_brand_safety(self) -> list:
        """获取品牌安全类别列表"""
        self._rate_limiter.acquire()
        result = self.request('GET', 'brand_safety/get/')
        return result.get('data', {}).get('list', []) if isinstance(result, dict) else []
    
    # ==================== 统计报告查询 ====================
    
    def get_report(self, advertiser_id: str, report_type: str = 'CAMPAIGN', date_preset: str = 'LAST_7_DAYS', time_range: dict = None) -> dict:
        """获取统计报告"""
        self._rate_limiter.acquire()
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
        return result.get('data', {}) if isinstance(result, dict) else {}

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
