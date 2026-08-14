# -*- coding: utf-8 -*-
"""
Meta Marketing API 客户端

官方文档: https://developers.facebook.com/docs/marketing-api
认证方式: OAuth2 Access Token
API 版本: v19.0
"""

from typing import List, Dict, Optional
from api_common import ApiResponse, BaseAdPlatformClient
import requests


class MetaClient(BaseAdPlatformClient):
    """
    Meta Marketing API 客户端
    
    官方文档: https://developers.facebook.com/docs/marketing-api
    认证方式: OAuth2 Access Token
    API 版本: v19.0
    """
    
    def __init__(self, credentials: dict):
        super().__init__(credentials, 'meta')
        self.base_url = "https://graph.facebook.com/v19.0"
        
    def get_token(self) -> str:
        """获取 Meta Access Token"""
        return self.credentials.get('meta', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """发送 Meta API 请求"""
        token = self.get_token()
        if not token:
            return ApiResponse(success=False, error="Missing access_token")
        
        url = f"{self.base_url}/{endpoint}"
        params = {'access_token': token}
        
        try:
            if method == 'GET':
                resp = requests.get(url, params={**params, **kwargs.get('params', {})}, timeout=30)
            else:
                resp = requests.post(url, params=params, json=kwargs.get('data', {}), timeout=30)
            
            data = resp.json()
            if 'error' in data:
                return ApiResponse(success=False, error=data['error'].get('message', 'Unknown error'), data=data)
            
            return ApiResponse(success=True, data=data)
        except Exception as e:
            return ApiResponse(success=False, error=str(e))
    
    # ==================== 账户管理 ====================
    def list_accounts(self, business_id: str = None) -> ApiResponse:
        """获取广告账户列表"""
        endpoint = 'me/accounts'
        if business_id:
            endpoint = f'{business_id}/accounts'
        return self.request('GET', endpoint)
    
    def get_account(self, account_id: str, fields: List[str] = None) -> ApiResponse:
        """获取账户详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,account_id,status'}
        return self.request('GET', f'/{account_id}', params=params)
    
    # ==================== 广告系列管理 ====================
    def list_campaigns(self, account_id: str, fields: List[str] = None) -> ApiResponse:
        """获取广告系列列表"""
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective'}
        return self.request('GET', f'/{account_id}/campaigns', params=params)
    
    def get_campaign(self, account_id: str, campaign_id: str) -> ApiResponse:
        """获取广告系列详情"""
        return self.request('GET', f'/{campaign_id}', params={'fields': 'id,name,status,daily_budget,budget_remaining,objective,adsets,ads'})
    
    def create_campaign(self, account_id: str, campaign: Dict) -> ApiResponse:
        """创建广告系列"""
        return self.request('POST', f'/{account_id}/campaigns', data=campaign)
    
    def update_campaign(self, campaign_id: str, updates: Dict) -> ApiResponse:
        """更新广告系列"""
        return self.request('POST', f'/{campaign_id}', data=updates)
    
    def pause_campaign(self, campaign_id: str) -> ApiResponse:
        """暂停广告系列"""
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> ApiResponse:
        """恢复广告系列"""
        return self.update_campaign(campaign_id, {'status': 'ACTIVE'})
    
    def delete_campaign(self, campaign_id: str) -> ApiResponse:
        """删除广告系列"""
        return self.request('DELETE', f'/{campaign_id}')
    
    # ==================== 广告组管理 ====================
    def list_adsets(self, account_id: str, campaign_id: str = None) -> ApiResponse:
        """获取广告组列表"""
        if campaign_id:
            return self.request('GET', f'/{campaign_id}/adsets', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting'})
        return self.request('GET', f'/{account_id}/adsets', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting'})
    
    def get_adset(self, account_id: str, adset_id: str) -> ApiResponse:
        """获取广告组详情"""
        return self.request('GET', f'/{adset_id}', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting,insights'})
    
    def create_adset(self, account_id: str, adset: Dict) -> ApiResponse:
        """创建广告组"""
        return self.request('POST', f'/{account_id}/adsets', data=adset)
    
    def update_adset(self, adset_id: str, updates: Dict) -> ApiResponse:
        """更新广告组"""
        return self.request('POST', f'/{adset_id}', data=updates)
    
    def pause_adset(self, adset_id: str) -> ApiResponse:
        """暂停广告组"""
        return self.update_adset(adset_id, {'status': 'PAUSED'})
    
    def resume_adset(self, adset_id: str) -> ApiResponse:
        """恢复广告组"""
        return self.update_adset(adset_id, {'status': 'ACTIVE'})
    
    def delete_adset(self, adset_id: str) -> ApiResponse:
        """删除广告组"""
        return self.request('DELETE', f'/{adset_id}')
    
    # ==================== 广告管理 ====================
    def list_ads(self, account_id: str, adset_id: str = None) -> ApiResponse:
        """获取广告列表"""
        if adset_id:
            return self.request('GET', f'/{adset_id}/ads', params={'fields': 'id,name,status,creative'})
        return self.request('GET', f'/{account_id}/ads', params={'fields': 'id,name,status,creative'})
    
    def get_ad(self, account_id: str, ad_id: str) -> ApiResponse:
        """获取广告详情"""
        return self.request('GET', f'/{ad_id}', params={'fields': 'id,name,status,creative,inspection_receipt'})
    
    def create_ad(self, account_id: str, ad: Dict) -> ApiResponse:
        """创建广告"""
        return self.request('POST', f'/{account_id}/ads', data=ad)
    
    def update_ad(self, ad_id: str, updates: Dict) -> ApiResponse:
        """更新广告"""
        return self.request('POST', f'/{ad_id}', data=updates)
    
    def pause_ad(self, ad_id: str) -> ApiResponse:
        """暂停广告"""
        return self.update_ad(ad_id, {'status': 'PAUSED'})
    
    def resume_ad(self, ad_id: str) -> ApiResponse:
        """恢复广告"""
        return self.update_ad(ad_id, {'status': 'ACTIVE'})
    
    def delete_ad(self, ad_id: str) -> ApiResponse:
        """删除广告"""
        return self.request('DELETE', f'/{ad_id}')
    
    # ==================== 受众管理 ====================
    def list_audiences(self, account_id: str) -> ApiResponse:
        """获取受众列表"""
        return self.request('GET', f'/{account_id}/customconversions', params={'fields': 'id,name,category,type'})
    
    def create_audience(self, account_id: str, audience: Dict) -> ApiResponse:
        """创建受众"""
        return self.request('POST', f'/{account_id}/customconversions', data=audience)
    
    def delete_audience(self, audience_id: str) -> ApiResponse:
        """删除受众"""
        return self.request('DELETE', f'/{audience_id}')
    
    # ==================== 商品目录 ====================
    def list_catalogs(self, account_id: str) -> ApiResponse:
        """获取商品目录列表"""
        return self.request('GET', f'/{account_id}/product_catalogs', params={'fields': 'id,name,description,status'})
    
    # ==================== Pixel 和转化 ====================
    def list_pixels(self, account_id: str) -> ApiResponse:
        """获取 Pixel 列表"""
        return self.request('GET', f'/{account_id}/pixel', params={'fields': 'id,name,fired'})
    
    def create_pixel(self, account_id: str, pixel: Dict) -> ApiResponse:
        """创建 Pixel"""
        return self.request('POST', f'/{account_id}/pixels', data=pixel)
    
    # ==================== Insights 报表 ====================
    def get_insights(self, account_id: str, levels: List[str], date_preset: str = 'last_7d', fields: List[str] = None) -> ApiResponse:
        """获取 Insights 数据"""
        params = {'levels': ','.join(levels), 'date_preset': date_preset}
        if fields:
            params['fields'] = ','.join(fields)
        return self.request('GET', f'/{account_id}/insights', params=params)
    
    # ==================== 官方选项数据 ====================
    def get_placement_options(self) -> List[Dict]:
        """获取官方投放位置选项"""
        return [
            {'platform': 'Facebook', 'placement': 'facebook_feed', 'name': '动态消息'},
            {'platform': 'Facebook', 'placement': 'facebook_instream', 'name': '视频插播'},
            {'platform': 'Facebook', 'placement': 'facebook_stories', 'name': '快拍'},
            {'platform': 'Instagram', 'placement': 'instagram_feed', 'name': '动态'},
            {'platform': 'Instagram', 'placement': 'instagram_stories', 'name': '快拍'},
            {'platform': 'Instagram', 'placement': 'instagram_reels', 'name': 'Reels'},
            {'platform': 'Audience Network', 'placement': 'audience_network', 'name': '受众网络'}
        ]
    
    def get_bid_strategy_options(self) -> List[Dict]:
        """获取官方出价策略选项"""
        return [
            {'code': 'LOWEST_COST_WITHOUT_CAP', 'name': '最低成本（无上限）', 'description': '在预算内获得最多结果'},
            {'code': 'LOWEST_COST_WITH_COST_CAP', 'name': '最低成本（有成本上限）', 'description': '控制平均每次结果成本'},
            {'code': 'COST_PER_ESTIMATED_ACTION_RATE', 'name': '目标成本', 'description': '设定目标每次行动成本'},
            {'code': 'BID_AMOUNT', 'name': '手动出价', 'description': '自定义出价金额'},
            {'code': 'HIGHEST_VALUE_WITHOUT_CAP', 'name': '最高价值（无上限）', 'description': '最大化转化价值'},
            {'code': 'RETURON_ON_ADS_SPEND_TARGET', 'name': '广告支出回报率目标', 'description': '设定目标 ROAS'}
        ]
    
    def get_campaign_objective_options(self) -> List[Dict]:
        """获取官方广告目标选项"""
        return [
            {'code': 'BRAND_AWARENESS', 'name': '品牌认知', 'category': 'Awareness'},
            {'code': 'REACH', 'name': '触达', 'category': 'Awareness'},
            {'code': 'TRAFFIC', 'name': '流量', 'category': 'Consideration'},
            {'code': 'ENGAGEMENT', 'name': '互动', 'category': 'Consideration'},
            {'code': 'APP_INSTALLS', 'name': '应用安装', 'category': 'Consideration'},
            {'code': 'VIDEO_VIEWS', 'name': '视频观看', 'category': 'Consideration'},
            {'code': 'LEAD_GENERATION', 'name': '潜在客户', 'category': 'Consideration'},
            {'code': 'MESSAGES', 'name': '消息', 'category': 'Consideration'},
            {'code': 'CONVERSIONS', 'name': '转化', 'category': 'Conversion'},
            {'code': 'CATALOG_SALES', 'name': '商品销售', 'category': 'Conversion'},
            {'code': 'STORE_TRAFFIC', 'name': '到店流量', 'category': 'Conversion'}
        ]
