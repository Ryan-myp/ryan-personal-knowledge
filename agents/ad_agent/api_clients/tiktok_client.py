"""
api_clients/tiktok_client.py - TikTok Ads API 生产级客户端

接入已有 scripts/tiktok_api.py，补全重试、限流、错误分类。
"""

import logging
import time
import json
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
        self.access_token = credentials.get('access_token', '')
        # 速率限制: 100次/分钟
        self._rate_limiter = RateLimiter(max_requests=100, period=60)
    
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.BASE_URL}/{self.API_VERSION}/{endpoint.lstrip('/')}"
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        headers = {
            'Access-Token': self.access_token,
            'Content-Type': 'application/json',
            **kwargs.get('headers', {}),
        }
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params'), timeout=30)
            elif method == 'POST':
                resp = requests.post(url, headers=headers, json=kwargs.get('data'), timeout=30)
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return {
                'status_code': resp.status_code,
                'data': resp.json() if resp.content else {},
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
        
        # HTTP 错误
        if status_code != 200:
            return TemporaryError(f"TikTok HTTP {status_code}")
        
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
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        # 使用 _do_request 获取原始响应
        url = self._build_url('campaign/get/')
        resp = self._do_request('GET', url, params=data)
        # 解析 TikTok 响应结构: data.data.list
        if resp.get('status_code') == 200:
            inner = resp.get('data', {})
            # TikTok API 返回结构: {code, message, data: {list: [...]}}
            return inner.get('data', {}).get('list', [])
        return []
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> dict:
        """获取 Campaign 详情"""
        filtering = [{'field': 'CAMPAIGN_IDS', 'operator': 'IN', 'values': [int(campaign_id)]}]
        result = self.list_campaigns(advertiser_id, filtering=filtering)
        return result[0] if result else {}
    
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
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'page_size': page_size,
        }
        if filtering:
            data['filtering'] = filtering
        result = self.request('POST', 'adgroup/get/', data=data)
        adgroups = result.get('ad_group_list', []) if isinstance(result, dict) else []
        return adgroups
    
    def get_adgroup(self, advertiser_id: str, campaign_id: str, adgroup_id: str) -> dict:
        """获取 Ad Group 详情"""
        filtering = [{'field': 'ADGROUP_IDS', 'operator': 'IN', 'values': [int(adgroup_id)]}]
        result = self.list_adgroups(advertiser_id, campaign_id, filtering=filtering)
        return result[0] if result else {}
    
    def create_adgroup(self, advertiser_id: str, campaign_id: str, adgroup: dict) -> str:
        """创建 Ad Group"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group': {
                'ad_group_name': adgroup['name'],
                'ad_group_status': adgroup.get('status', 1),
                'promote_object_type': adgroup.get('promote_object_type', 0),  # 0=APP, 1=LandingPage
                'tracking_url': adgroup.get('tracking_url', ''),
                'bid_type': adgroup.get('bid_type', 0),  # 0=AUTO, 1=MANUAL
                'bid_amount': int(adgroup.get('bid_amount', 500)),  # 单位为分
                'daily_budget': int(adgroup.get('daily_budget', 50) * 100),
                'placement_type': adgroup.get('placement_type', -1),  # -1=AUTO
            }
        }
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
    
    def list_ads(self, advertiser_id: str, campaign_id: str, adgroup_id: str, page_size: int = 20) -> list:
        """获取 Ad 列表"""
        self._rate_limiter.acquire()
        data = {
            'advertiser_id': str(advertiser_id),
            'campaign_id': int(campaign_id),
            'ad_group_id': int(adgroup_id),
            'page_size': page_size,
        }
        result = self.request('POST', 'ad/get/', data=data)
        ads = result.get('ad_list', []) if isinstance(result, dict) else []
        return ads
    
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
        time_range: dict = None,
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
                'time_range': time_range or {'start_date': 'LAST_7_DAYS', 'end_date': 'TODAY'},
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
            data['time_range'] = time_range
        result = self.request('POST', 'statistics/get/', json=data)
        return result.get('data', {}) if isinstance(result, dict) else {}
