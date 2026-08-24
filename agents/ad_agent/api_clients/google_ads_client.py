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
    
    BASE_URL = "https://googleads.googleapis.com/v24"
    
    def __init__(
        self,
        credentials: dict,
        customer_id: str = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "google", retry_config)
        self.customer_id = customer_id or credentials.get('customer_id', '')
        self.developer_token = credentials.get('developer_token', '')
        self.login_customer_id = credentials.get('login_customer_id', self.customer_id)
        self._rate_limiter = RateLimiter(max_requests=1000, period=60)  # 保守限流
    
    def _build_headers(self) -> dict:
        token = self.credentials.get('access_token', '')
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'developer-token': self.developer_token,
            'login-customer-id': self.login_customer_id,
        }
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        self._rate_limiter.acquire()
        
        headers = {**self._build_headers(), **kwargs.pop('headers', {})}
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params'), timeout=30)
            elif method == 'POST':
                resp = requests.post(url, headers=headers, json=kwargs.get('data'), timeout=30)
            elif method == 'PUT':
                resp = requests.put(url, headers=headers, json=kwargs.get('data'), timeout=30)
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            data = resp.json() if resp.content else {}
            
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
            "campaign.advertising_channel_type, campaign.bidding_strategy,"
            "campaign.optimization_goal, campaign.campaign_budget "
            "FROM campaign"
        )
        if filter_query:
            query += f" WHERE {filter_query}"
        query += f" LIMIT {page_size}"
        
        result = self._search(query)
        return result.get('results', [])
    
    def get_campaign(self, campaign_id: str) -> dict:
        """获取 Campaign 详情"""
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type, campaign.bidding_strategy,
                   campaign.optimization_goal
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """
        results = self._search(query)
        return results.get('results', [{}])[0] if results.get('results') else {}
    
    def create_campaign(
        self,
        name: str,
        advertising_channel_type: str,
        bidding_strategy: str,
        daily_budget: float,
        target_cpa_micros: int = None,
        target_roas: float = None,
    ) -> str:
        """
        创建 Campaign（需要先创建 CampaignBudget）
        
        advertising_channel_type: SEARCH | SHOPPING | PERFORMANCE_MAX | VIDEO | DISPLAY | APP
        bidding_strategy: MANUAL_CPC | TARGET_CPA | MAXIMIZE_CONVERSIONS | TARGET_ROAS
        """
        # Step 1: 创建预算
        budget_name = f"Budget for {name}"
        budget_amount_micros = int(daily_budget * 1_000_000)
        
        budget_url = f"{self.BASE_URL}/customers/{self.customer_id}/campaignBudgets"
        budget_data = {
            'resourceName': f'customers/{self.customer_id}/campaignBudgets/-',
            'name': budget_name,
            'amountMicros': budget_amount_micros,
            'deliveryMethod': 'STANDARD',
            'explicitlyShared': True,
        }
        
        budget_resp = self._do_request('POST', budget_url, data=budget_data)
        budget_resource_name = budget_resp.get('data', {}).get('resourceName', '')
        
        if not budget_resource_name:
            raise APIError(f"Failed to create campaign budget: {budget_resp}")
        
        # Step 2: 创建 Campaign（初始状态 PAUSED）
        campaign_data = {
            'resourceName': f'customers/{self.customer_id}/campaigns/-',
            'name': name,
            'advertisingChannelType': advertising_channel_type,
            'status': 'PAUSED',
            'campaignBudget': budget_resource_name,
            'biddingStrategy': bidding_strategy,
            'finalUrlsAllowed': True,
        }
        
        # 出价策略附加参数
        if bidding_strategy == 'TARGET_CPA':
            campaign_data['targetCpaMicros'] = target_cpa_micros or 50000000
        elif bidding_strategy == 'TARGET_ROAS':
            campaign_data['targetRoas'] = target_roas or 4.0
        elif bidding_strategy == 'MAXIMIZE_CONVERSIONS':
            campaign_data['maximizeConversionValue'] = False
        
        campaign_url = f"{self.BASE_URL}/customers/{self.customer_id}/campaigns"
        campaign_resp = self._do_request('POST', campaign_url, data=campaign_data)
        
        campaign_resource_name = campaign_resp.get('data', {}).get('resourceName', '')
        campaign_id = campaign_resource_name.split('/')[-1] if campaign_resource_name else ''
        
        return str(campaign_id)
    
    def update_campaign(self, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign"""
        resource_name = f"customers/{self.customer_id}/campaigns/{campaign_id}"
        patch_data = {
            'resourceName': resource_name,
        }
        patch_data.update(updates)
        
        url = f"{self.BASE_URL}/{resource_name}"
        resp = self._do_request('PUT', url, data=patch_data)
        return {'success': True, 'campaign_id': campaign_id}
    
    def pause_campaign(self, campaign_id: str) -> dict:
        """暂停 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> dict:
        """恢复 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'ENABLED'})
    
    # ==================== Ad Group 管理 ====================
    
    def list_ad_groups(self, campaign_id: str, page_size: int = 100) -> list:
        """获取 Ad Group 列表"""
        query = f"""
            SELECT ad_group.id, ad_group.name, ad_group.status,
                   ad_group.cpc_bid_micros, ad_group.type
            FROM ad_group
            WHERE ad_group.campaign = 'customers/{self.customer_id}/campaigns/{campaign_id}'
            LIMIT {page_size}
        """
        result = self._search(query)
        return result.get('results', [])
    
    def create_ad_group(
        self,
        campaign_id: str,
        name: str,
        cpc_bid_micros: int = 500000,
        type: str = "SEARCH_DYNAMIC_ADS",
    ) -> str:
        """创建 Ad Group"""
        ad_group_data = {
            'resourceName': f'customers/{self.customer_id}/adGroups/-',
            'name': name,
            'status': 'PAUSED',
            'campaign': f'customers/{self.customer_id}/campaigns/{campaign_id}',
            'type': type,
            'cpcBidMicros': cpc_bid_micros,
        }
        
        url = f"{self.BASE_URL}/customers/{self.customer_id}/adGroups"
        resp = self._do_request('POST', url, data=ad_group_data)
        
        resource_name = resp.get('data', {}).get('resourceName', '')
        ad_group_id = resource_name.split('/')[-1] if resource_name else ''
        return str(ad_group_id)
    
    # ==================== Ad 管理 ====================
    
    def create_search_ad(
        self,
        ad_group_id: str,
        headlines: list[str],
        descriptions: list[str],
        final_url: str,
    ) -> str:
        """创建响应式搜索广告"""
        ad_data = {
            'resourceName': f'customers/{self.customer_id}/ads/-',
            'type': 'RESPONSIVE_SEARCH_AD',
            'status': 'PAUSED',
            'finalUrls': [final_url],
            'responseSearchAd': {
                'headlineParts': [{'partText': h} for h in headlines[:15]],
                'descriptionParts': [{'partText': d} for d in descriptions[:4]],
            },
        }
        
        url = f"{self.BASE_URL}/customers/{self.customer_id}/ads"
        resp = self._do_request('POST', url, data=ad_data)
        
        resource_name = resp.get('data', {}).get('resourceName', '')
        ad_id = resource_name.split('/')[-1] if resource_name else ''
        return str(ad_id)
    
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
        # PMax Asset Group 需要通过 AssetService 创建
        # 这里返回占位符，实际需要调用 Google Ads API 的 AssetService
        logger.warning("PMax Asset Group requires AssetService - placeholder returned")
        return f"pmax_ag_{campaign_id}_{int(time.time())}"
    
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
        
        where_clause = " OR ".join([f"campaign.id = {cid}" for cid in campaign_ids])
        
        query = f"""
            SELECT 
                campaign.id, campaign.name, campaign.status,
                segments.date,
                {', '.join(metrics or default_metrics)}
            FROM campaign
            WHERE {where_clause}
              AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        """
        
        result = self._search(query)
        return result.get('results', [])
    
    def get_adgroup_report(
        self,
        campaign_id: str,
        adgroup_ids: list[str] = None,
        date_from: str = "LAST_30_DAYS",
        date_to: str = "TODAY",
    ) -> list:
        """查询 Ad Group 级别报表"""
        where_clause = f"campaign.id = {campaign_id}"
        if adgroup_ids:
            where_clause += f" AND ad_group.id IN ({', '.join(adgroup_ids)})"
        
        query = f"""
            SELECT 
                campaign.id, campaign.name,
                ad_group.id, ad_group.name,
                segments.date,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.cost_per_conversion
            FROM ad_group
            WHERE {where_clause}
              AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        """
        
        result = self._search(query)
        return result.get('results', [])
    
    # ==================== 辅助方法 ====================
    
    def _search(self, query: str) -> dict:
        """执行 GAQL 查询"""
        url = f"{self.BASE_URL}/customers/{self.customer_id}:search"
        data = {'query': query}
        return self._do_request('POST', url, data=data)
    
    def _format_value(self, value) -> Any:
        """格式化 API 返回值"""
        if isinstance(value, dict):
            return {k: self._format_value(v) for k, v in value.items()}
        return value
