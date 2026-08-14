# -*- coding: utf-8 -*-
"""
Google Ads API 客户端

官方文档: https://developers.google.com/google-ads/api
认证方式: OAuth2 + Developer Token
API 版本: v24.2
"""

from typing import List, Dict, Optional
from api_common import ApiResponse, BaseAdPlatformClient
import requests


class GoogleAdsClient(BaseAdPlatformClient):
    """
    Google Ads API 客户端
    
    官方文档: https://developers.google.com/google-ads/api
    认证方式: OAuth2 + Developer Token
    API 版本: v24.2
    """
    
    def __init__(self, credentials: dict):
        super().__init__(credentials, 'google_ads')
        self.base_url = "https://googleads.googleapis.com/v24"
        self.developer_token = credentials.get('google_ads', {}).get('developer_token', '')
        self.login_customer_id = credentials.get('google_ads', {}).get('login_customer_id', '')
        
    def get_token(self) -> str:
        """获取 Google Ads Access Token"""
        return self.credentials.get('google_ads', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """发送 Google Ads API 请求"""
        token = self.get_token()
        if not token:
            return ApiResponse(success=False, error="Missing access_token")
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'developer-token': self.developer_token,
            'login-customer-id': self.login_customer_id
        }
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params', {}), timeout=30)
            else:
                resp = requests.post(url, headers=headers, json=kwargs.get('data', {}), timeout=30)
            
            data = resp.json()
            if resp.status_code != 200:
                return ApiResponse(success=False, error=data.get('error', {}).get('message', 'API error'), data=data)
            
            return ApiResponse(success=True, data=data)
        except Exception as e:
            return ApiResponse(success=False, error=str(e))
    
    def search(self, customer_id: str, query: str) -> ApiResponse:
        """执行 GAQL 查询"""
        data = {'query': query}
        return self.request('POST', f'customers/{customer_id}:search', data=data)
    
    # ==================== 客户管理 ====================
    def list_customers(self) -> ApiResponse:
        """获取客户账户列表"""
        return self.request('GET', 'customers')
    
    def get_customer(self, customer_id: str) -> ApiResponse:
        """获取客户详情"""
        return self.request('GET', f'customers/{customer_id}')
    
    # ==================== 广告系列管理 ====================
    def list_campaigns(self, customer_id: str, filter: str = None) -> ApiResponse:
        """获取广告系列列表"""
        query = "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type FROM campaign"
        if filter:
            query += f" WHERE {filter}"
        return self.search(customer_id, query)
    
    def get_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """获取广告系列详情"""
        query = f"SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id = {campaign_id}"
        return self.search(customer_id, query)
    
    def create_campaign(self, customer_id: str, campaign: Dict) -> ApiResponse:
        """创建广告系列"""
        return self.request('POST', f'customers/{customer_id}/campaigns', data=campaign)
    
    def update_campaign(self, customer_id: str, campaign_id: str, updates: Dict) -> ApiResponse:
        """更新广告系列"""
        campaign = {'resource_name': f'customers/{customer_id}/campaigns/{campaign_id}', **updates}
        return self.request('PATCH', f'customers/{customer_id}/campaigns/{campaign_id}', data=campaign)
    
    def pause_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """暂停广告系列"""
        return self.update_campaign(customer_id, campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """恢复广告系列"""
        return self.update_campaign(customer_id, campaign_id, {'status': 'ENABLED'})
    
    def delete_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """删除广告系列"""
        return self.request('DELETE', f'customers/{customer_id}/campaigns/{campaign_id}')
    
    # ==================== 广告组管理 ====================
    def list_ad_groups(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """获取广告组列表"""
        query = f"SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group WHERE ad_group.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'"
        return self.search(customer_id, query)
    
    def create_ad_group(self, customer_id: str, ad_group: Dict) -> ApiResponse:
        """创建广告组"""
        return self.request('POST', f'customers/{customer_id}/adGroups', data=ad_group)
    
    def update_ad_group(self, customer_id: str, ad_group_id: str, updates: Dict) -> ApiResponse:
        """更新广告组"""
        return self.request('PATCH', f'customers/{customer_id}/adGroups/{ad_group_id}', data=updates)
    
    def pause_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        """暂停广告组"""
        return self.update_ad_group(customer_id, ad_group_id, {'status': 'PAUSED'})
    
    def resume_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        """恢复广告组"""
        return self.update_ad_group(customer_id, ad_group_id, {'status': 'ENABLED'})
    
    def delete_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        """删除广告组"""
        return self.request('DELETE', f'customers/{customer_id}/adGroups/{ad_group_id}')
    
    # ==================== 关键词管理 ====================
    def list_keywords(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        """获取关键词列表"""
        query = f"SELECT keyword.id, keyword.text, keyword.match_type FROM keyword WHERE keyword.ad_group = 'customers/{customer_id}/adGroups/{ad_group_id}'"
        return self.search(customer_id, query)
    
    def create_keywords(self, customer_id: str, ad_group_id: str, keywords: List[Dict]) -> ApiResponse:
        """创建关键词"""
        operations = []
        for kw in keywords:
            operations.append({
                'resource_name': f'customers/{customer_id}/adGroupCriteria/{ad_group_id}',
                'keyword': {'text': kw['text'], 'match_type': kw.get('match_type', 'PHRASE')}
            })
        return self.request('POST', f'customers/{customer_id}/adGroupCriteria:mutate', data={'operations': operations})
    
    def delete_keywords(self, customer_id: str, keyword_ids: List[str]) -> ApiResponse:
        """删除关键词"""
        operations = [{'resource_name': f'customers/{customer_id}/adGroupCriteria/{kid}', 'remove': True} for kid in keyword_ids]
        return self.request('POST', f'customers/{customer_id}/adGroupCriteria:mutate', data={'operations': operations})
    
    # ==================== 广告管理 ====================
    def list_ads(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        """获取广告列表"""
        query = f"SELECT ad.id, ad.type, ad.status FROM ad WHERE ad.ad_group = 'customers/{customer_id}/adGroups/{ad_group_id}'"
        return self.search(customer_id, query)
    
    def create_ad(self, customer_id: str, ad: Dict) -> ApiResponse:
        """创建广告"""
        return self.request('POST', f'customers/{customer_id}/ads', data=ad)
    
    def update_ad(self, customer_id: str, ad_id: str, updates: Dict) -> ApiResponse:
        """更新广告"""
        return self.request('PATCH', f'customers/{customer_id}/ads/{ad_id}', data=updates)
    
    def pause_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        """暂停广告"""
        return self.update_ad(customer_id, ad_id, {'status': 'PAUSED'})
    
    def resume_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        """恢复广告"""
        return self.update_ad(customer_id, ad_id, {'status': 'ENABLED'})
    
    def delete_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        """删除广告"""
        return self.request('DELETE', f'customers/{customer_id}/ads/{ad_id}')
    
    # ==================== 转化追踪 ====================
    def list_conversion_actions(self, customer_id: str) -> ApiResponse:
        """获取转化行为列表"""
        query = "SELECT conversion_action.id, conversion_action.name, conversion_action.type FROM conversion_action"
        return self.search(customer_id, query)
    
    def create_conversion_action(self, customer_id: str, conversion: Dict) -> ApiResponse:
        """创建转化行为"""
        return self.request('POST', f'customers/{customer_id}/conversionActions', data=conversion)
    
    # ==================== 出价策略 ====================
    def list_bid_strategies(self, customer_id: str) -> ApiResponse:
        """获取出价策略列表"""
        query = "SELECT bidding_strategy.id, bidding_strategy.name, bidding_strategy.type FROM bidding_strategy"
        return self.search(customer_id, query)
    
    def get_bid_suggestion(self, customer_id: str, campaign_id: str) -> ApiResponse:
        """获取出价建议"""
        query = f"SELECT keyword_match_type, metrics.all_conversions, metrics.estimated_ranked_cpc_micros FROM keyword_view WHERE segments.date DURING LAST_30_DAYS AND campaign.id = {campaign_id}"
        return self.search(customer_id, query)
    
    # ==================== 报表 ====================
    def generate_report(self, customer_id: str, date_range: Dict) -> ApiResponse:
        """生成报表"""
        start_date = date_range['start']
        end_date = date_range['end']
        query = f"SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        return self.search(customer_id, query)
    
    # ==================== 官方选项数据 ====================
    def get_campaign_type_options(self) -> List[Dict]:
        """获取官方广告系列类型选项"""
        return [
            {'code': 'SEARCH', 'name': '搜索广告', 'description': '在 Google 搜索结果中展示'},
            {'code': 'DISPLAY', 'name': '展示广告', 'description': '在 Google 展示网络中展示'},
            {'code': 'SHOPPING', 'name': '购物广告', 'description': '展示商品信息'},
            {'code': 'VIDEO', 'name': '视频广告', 'description': '在 YouTube 展示'},
            {'code': 'APP', 'name': '应用广告', 'description': '推广移动应用'},
            {'code': 'MAX', 'name': '全效果广告', 'description': '跨渠道自动化投放'}
        ]
    
    def get_bid_strategy_options(self) -> List[Dict]:
        """获取官方出价策略选项"""
        return [
            {'code': 'MANUAL_CPC', 'name': '手动 CPC', 'description': '手动控制每次点击费用'},
            {'code': 'ENHANCED_CPC', 'name': '增强型 CPC', 'description': '在手动 CPC 基础上优化'},
            {'code': 'TARGET_CPA', 'name': '目标 CPA', 'description': '设定目标每次转化费用'},
            {'code': 'TARGET_ROAS', 'name': '目标 ROAS', 'description': '设定目标广告支出回报率'},
            {'code': 'MAXIMIZE_CLICKS', 'name': '最大化点击量', 'description': '在预算内获得最多点击'},
            {'code': 'MAXIMIZE_CONVERSIONS', 'name': '最大化转化量', 'description': '在预算内获得最多转化'},
            {'code': 'MAXIMIZE_CONVERSION_VALUE', 'name': '最大化转化价值', 'description': '最大化转化收入'},
            {'code': 'TARGET_IMPRESSION_SHARE', 'name': '目标展示份额', 'description': '设定目标展示份额'}
        ]
    
    def get_asset_type_options(self) -> List[Dict]:
        """获取官方资产类型选项"""
        return [
            {'code': 'SITELINK', 'name': '站点链接', 'description': '引导到多个页面'},
            {'code': 'CALL', 'name': '电话展示', 'description': '展示电话号码'},
            {'code': 'STRUCTURED_SNIPPET', 'name': '结构化摘要', 'description': '展示产品特性'},
            {'code': 'CALLOUT', 'name': '促销信息', 'description': '突出卖点'},
            {'code': 'PRICE', 'name': '价格', 'description': '展示产品价格'},
            {'code': 'APP_EXTENSION', 'name': '应用链接', 'description': '推广移动应用'},
            {'code': 'IMAGE', 'name': '图片', 'description': '视觉展示'},
            {'code': 'LEAD_FORM', 'name': '表单', 'description': '收集潜在客户'}
        ]
