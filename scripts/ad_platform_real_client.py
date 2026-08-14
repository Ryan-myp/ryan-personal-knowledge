# -*- coding: utf-8 -*-
"""
广告平台真实 API 客户端
基于官方文档实现，包含正确的端点、参数和认证方式
"""

import json
import time
import hashlib
import hmac
import base64
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field, asdict


@dataclass
class ApiResponse:
    """API 响应封装"""
    success: bool
    data: Any = None
    error: str = ""
    rate_limit: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'rate_limit': self.rate_limit
        }


class BaseAdPlatformClient:
    """基础广告平台客户端"""
    
    def __init__(self, credentials: dict, platform: str):
        self.credentials = credentials
        self.platform = platform
        self.base_url = ""
        self.token = None
        self.token_expiry = 0
        
    def get_token(self) -> str:
        raise NotImplementedError
        
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        raise NotImplementedError

class TikTokClient(BaseAdPlatformClient):
    """
    TikTok Marketing API 客户端
    
    官方文档: https://business-api.tiktok.com/portal/docs
    认证方式: Access-Token Header
    API 版本: v1.3
    """
    
    def __init__(self, credentials: dict):
        super().__init__(credentials, 'tiktok')
        self.base_url = "https://business-api.tiktok.com"
        self.api_version = "open_api/v1.3"
        
    def get_token(self) -> str:
        return self.credentials.get('tiktok', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        token = self.get_token()
        if not token:
            return ApiResponse(success=False, error="Missing access_token")
        
        url = f"{self.base_url}/{self.api_version}/{endpoint}"
        headers = {'Access-Token': token, 'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=kwargs.get('params', {}), timeout=30)
            else:
                resp = requests.post(url, headers=headers, json=kwargs.get('data', {}), timeout=30)
            
            data = resp.json()
            if data.get('code', 0) != 0:
                return ApiResponse(success=False, error=data.get('message', 'Unknown error'), data=data)
            
            return ApiResponse(success=True, data=data.get('data'))
        except Exception as e:
            return ApiResponse(success=False, error=str(e))
    
    # 账户管理
    def list_accounts(self, advertiser_id: str) -> ApiResponse:
        return self.request('GET', 'account/get/', params={'advertiser_id': advertiser_id})
    
    # 广告系列管理
    def list_campaigns(self, advertiser_id: str, filtering: List[Dict] = None) -> ApiResponse:
        data = {'advertiser_id': int(advertiser_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'campaign/get/', data=data)
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        filtering = [{'field': 'CAMPAIGN_IDS', 'operator': 'IN', 'values': [campaign_id]}]
        return self.list_campaigns(advertiser_id, filtering)
    
    def create_campaign(self, advertiser_id: str, campaign: Dict) -> ApiResponse:
        return self.request('POST', 'campaign/create/', data={'advertiser_id': int(advertiser_id), 'campaign': campaign})
    
    def update_campaign(self, advertiser_id: str, campaign_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', 'campaign/update/', data={'advertiser_id': int(advertiser_id), 'campaign_id': int(campaign_id), 'campaign': updates})
    
    def pause_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 0})
    
    def resume_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 1})
    
    def delete_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        return self.request('POST', 'campaign/delete/', data={'advertiser_id': int(advertiser_id), 'campaign_ids': [int(campaign_id)]})
    
    # 广告组管理
    def list_adgroups(self, advertiser_id: str, campaign_id: str, filtering: List[Dict] = None) -> ApiResponse:
        data = {'advertiser_id': int(advertiser_id), 'campaign_id': int(campaign_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'adgroup/get/', data=data)
    
    def create_adgroup(self, advertiser_id: str, adgroup: Dict) -> ApiResponse:
        return self.request('POST', 'adgroup/create/', data={'advertiser_id': int(advertiser_id), 'ad_group': adgroup})
    
    def update_adgroup(self, advertiser_id: str, adgroup_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', 'adgroup/update/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id), 'ad_group': updates})
    
    def pause_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        return self.update_adgroup(advertiser_id, adgroup_id, {'ad_group_status': 0})
    
    def resume_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        return self.update_adgroup(advertiser_id, adgroup_id, {'ad_group_status': 1})
    
    def delete_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        return self.request('POST', 'adgroup/delete/', data={'advertiser_id': int(advertiser_id), 'ad_group_ids': [int(adgroup_id)]})
    
    # 广告管理
    def list_ads(self, advertiser_id: str, adgroup_id: str, filtering: List[Dict] = None) -> ApiResponse:
        data = {'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'ad/get/', data=data)
    
    def create_ad(self, advertiser_id: str, ad: Dict) -> ApiResponse:
        return self.request('POST', 'ad/create/', data={'advertiser_id': int(advertiser_id), 'ad': ad})
    
    def update_ad(self, advertiser_id: str, ad_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', 'ad/update/', data={'advertiser_id': int(advertiser_id), 'ad_id': int(ad_id), 'ad': updates})
    
    def pause_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        return self.update_ad(advertiser_id, ad_id, {'ad_status': 0})
    
    def resume_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        return self.update_ad(advertiser_id, ad_id, {'ad_status': 1})
    
    def delete_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        return self.request('POST', 'ad/delete/', data={'advertiser_id': int(advertiser_id), 'ad_ids': [int(ad_id)]})
    
    # 关键词管理
    def list_keywords(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        return self.request('POST', 'keyword/get/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id)})
    
    def create_keywords(self, advertiser_id: str, adgroup_id: str, keywords: List[Dict]) -> ApiResponse:
        return self.request('POST', 'keyword/create/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id), 'keywords': keywords})
    
    def delete_keywords(self, advertiser_id: str, keyword_ids: List[str]) -> ApiResponse:
        return self.request('POST', 'keyword/delete/', data={'advertiser_id': int(advertiser_id), 'keyword_ids': [int(kid) for kid in keyword_ids]})
    
    # 受众管理
    def list_audiences(self, advertiser_id: str) -> ApiResponse:
        return self.request('POST', 'audience/get/', data={'advertiser_id': int(advertiser_id)})
    
    def create_audience(self, advertiser_id: str, audience: Dict) -> ApiResponse:
        return self.request('POST', 'audience/create/', data={'advertiser_id': int(advertiser_id), 'audience': audience})
    
    def delete_audience(self, advertiser_id: str, audience_id: str) -> ApiResponse:
        return self.request('POST', 'audience/delete/', data={'advertiser_id': int(advertiser_id), 'audience_id': int(audience_id)})
    
    # 转化追踪
    def list_conversion_events(self, advertiser_id: str) -> ApiResponse:
        return self.request('POST', 'conversion/get/', data={'advertiser_id': int(advertiser_id)})
    
    def create_custom_conversion(self, advertiser_id: str, conversion: Dict) -> ApiResponse:
        return self.request('POST', 'conversion/create/', data={'advertiser_id': int(advertiser_id), 'conversion': conversion})
    
    # 媒体库
    def get_media_library(self, advertiser_id: str) -> ApiResponse:
        return self.request('POST', 'media_library/get/', data={'advertiser_id': int(advertiser_id)})
    
    def upload_image(self, advertiser_id: str, image_data: Dict) -> ApiResponse:
        return self.request('POST', 'media_library/upload/image', data={'advertiser_id': int(advertiser_id), 'image': image_data})
    
    # 报表
    def get_report(self, advertiser_id: str, date_start: str, date_end: str, level: str = 'CAMPAIGN', insights: List[str] = None) -> ApiResponse:
        data = {'advertiser_id': int(advertiser_id), 'date_start': date_start, 'date_end': date_end, 'level': level}
        if insights:
            data['insights'] = insights
        return self.request('POST', 'report/get/', data=data)
    
    # 投放位置选项
    def get_placement_options(self) -> List[Dict]:
        return [
            {'code': 'TikTok Feed', 'name': '推荐页', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_TIKTOK'},
            {'code': 'TikTok Search', 'name': '搜索', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_SEARCH'},
            {'code': 'TikTok Post', 'name': '发布后', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_POST'},
            {'code': 'TikTok Marketplace', 'name': '商城', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_MARKETPLACE'},
            {'code': 'TikTok Series', 'name': '系列', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_SERIES'},
            {'code': 'TikTok Live', 'name': '直播', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_LIVE'}
        ]
    
    # 出价策略选项
    def get_bid_strategy_options(self) -> List[Dict]:
        return [
            {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS', 'name': '最低成本', 'description': '在预算内获得最多转化'},
            {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CLICKS', 'name': '最多点击', 'description': '在预算内获得最多点击'},
            {'code': 'AUTO_BID_TYPE_VALUE_MANUAL', 'name': '手动出价', 'description': '自定义出价金额'},
            {'code': 'BID_TYPE_VALUE_CPA', 'name': '目标 CPA', 'description': '设定目标每次转化费用'}
        ]
    
    # 广告目标选项
    def get_campaign_objective_options(self) -> List[Dict]:
        return [
            {'code': 'SALES', 'name': '销售', 'description': '促成网站或应用内购买'},
            {'code': 'APP_PROMOTION', 'name': '应用推广', 'description': '推广移动应用'},
            {'code': 'LEAD_GENERATION', 'name': '潜在客户', 'description': '收集潜在客户信息'},
            {'code': 'WEBSITE_TRAFFIC', 'name': '网站流量', 'description': '引导用户访问网站'},
            {'code': 'VIDEO_VIEWS', 'name': '视频观看', 'description': '提升视频观看量'},
            {'code': 'ENGAGEMENT', 'name': '互动', 'description': '提升帖子互动'}
        ]


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
        return self.credentials.get('meta', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
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
    
    # 账户管理
    def list_accounts(self, business_id: str = None) -> ApiResponse:
        endpoint = 'me/accounts'
        if business_id:
            endpoint = f'{business_id}/accounts'
        return self.request('GET', endpoint)
    
    def get_account(self, account_id: str, fields: List[str] = None) -> ApiResponse:
        params = {'fields': ','.join(fields) if fields else 'id,name,account_id,status'}
        return self.request('GET', f'/{account_id}', params=params)
    
    # 广告系列管理
    def list_campaigns(self, account_id: str, fields: List[str] = None) -> ApiResponse:
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective'}
        return self.request('GET', f'/{account_id}/campaigns', params=params)
    
    def get_campaign(self, account_id: str, campaign_id: str) -> ApiResponse:
        return self.request('GET', f'/{campaign_id}', params={'fields': 'id,name,status,daily_budget,budget_remaining,objective,adsets,ads'})
    
    def create_campaign(self, account_id: str, campaign: Dict) -> ApiResponse:
        return self.request('POST', f'/{account_id}/campaigns', data=campaign)
    
    def update_campaign(self, campaign_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', f'/{campaign_id}', data=updates)
    
    def pause_campaign(self, campaign_id: str) -> ApiResponse:
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> ApiResponse:
        return self.update_campaign(campaign_id, {'status': 'ACTIVE'})
    
    def delete_campaign(self, campaign_id: str) -> ApiResponse:
        return self.request('DELETE', f'/{campaign_id}')
    
    # 广告组管理
    def list_adsets(self, account_id: str, campaign_id: str = None) -> ApiResponse:
        if campaign_id:
            return self.request('GET', f'/{campaign_id}/adsets', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting'})
        return self.request('GET', f'/{account_id}/adsets', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting'})
    
    def get_adset(self, account_id: str, adset_id: str) -> ApiResponse:
        return self.request('GET', f'/{adset_id}', params={'fields': 'id,name,status,daily_budget,bid_amount,targeting,insights'})
    
    def create_adset(self, account_id: str, adset: Dict) -> ApiResponse:
        return self.request('POST', f'/{account_id}/adsets', data=adset)
    
    def update_adset(self, adset_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', f'/{adset_id}', data=updates)
    
    def pause_adset(self, adset_id: str) -> ApiResponse:
        return self.update_adset(adset_id, {'status': 'PAUSED'})
    
    def resume_adset(self, adset_id: str) -> ApiResponse:
        return self.update_adset(adset_id, {'status': 'ACTIVE'})
    
    def delete_adset(self, adset_id: str) -> ApiResponse:
        return self.request('DELETE', f'/{adset_id}')
    
    # 广告管理
    def list_ads(self, account_id: str, adset_id: str = None) -> ApiResponse:
        if adset_id:
            return self.request('GET', f'/{adset_id}/ads', params={'fields': 'id,name,status,creative'})
        return self.request('GET', f'/{account_id}/ads', params={'fields': 'id,name,status,creative'})
    
    def get_ad(self, account_id: str, ad_id: str) -> ApiResponse:
        return self.request('GET', f'/{ad_id}', params={'fields': 'id,name,status,creative,inspection_receipt'})
    
    def create_ad(self, account_id: str, ad: Dict) -> ApiResponse:
        return self.request('POST', f'/{account_id}/ads', data=ad)
    
    def update_ad(self, ad_id: str, updates: Dict) -> ApiResponse:
        return self.request('POST', f'/{ad_id}', data=updates)
    
    def pause_ad(self, ad_id: str) -> ApiResponse:
        return self.update_ad(ad_id, {'status': 'PAUSED'})
    
    def resume_ad(self, ad_id: str) -> ApiResponse:
        return self.update_ad(ad_id, {'status': 'ACTIVE'})
    
    def delete_ad(self, ad_id: str) -> ApiResponse:
        return self.request('DELETE', f'/{ad_id}')
    
    # 受众管理
    def list_audiences(self, account_id: str) -> ApiResponse:
        return self.request('GET', f'/{account_id}/customconversions', params={'fields': 'id,name,category,type'})
    
    def create_audience(self, account_id: str, audience: Dict) -> ApiResponse:
        return self.request('POST', f'/{account_id}/customconversions', data=audience)
    
    def delete_audience(self, audience_id: str) -> ApiResponse:
        return self.request('DELETE', f'/{audience_id}')
    
    # 商品目录
    def list_catalogs(self, account_id: str) -> ApiResponse:
        return self.request('GET', f'/{account_id}/product_catalogs', params={'fields': 'id,name,description,status'})
    
    # Pixel 和转化
    def list_pixels(self, account_id: str) -> ApiResponse:
        return self.request('GET', f'/{account_id}/pixel', params={'fields': 'id,name,fired'})
    
    def create_pixel(self, account_id: str, pixel: Dict) -> ApiResponse:
        return self.request('POST', f'/{account_id}/pixels', data=pixel)
    
    # Insights 报表
    def get_insights(self, account_id: str, levels: List[str], date_preset: str = 'last_7d', fields: List[str] = None) -> ApiResponse:
        params = {'levels': ','.join(levels), 'date_preset': date_preset}
        if fields:
            params['fields'] = ','.join(fields)
        return self.request('GET', f'/{account_id}/insights', params=params)
    
    # 投放位置选项
    def get_placement_options(self) -> List[Dict]:
        return [
            {'platform': 'Facebook', 'placement': 'facebook_feed', 'name': '动态消息'},
            {'platform': 'Facebook', 'placement': 'facebook_instream', 'name': '视频插播'},
            {'platform': 'Facebook', 'placement': 'facebook_stories', 'name': '快拍'},
            {'platform': 'Instagram', 'placement': 'instagram_feed', 'name': '动态'},
            {'platform': 'Instagram', 'placement': 'instagram_stories', 'name': '快拍'},
            {'platform': 'Instagram', 'placement': 'instagram_reels', 'name': 'Reels'},
            {'platform': 'Audience Network', 'placement': 'audience_network', 'name': '受众网络'}
        ]
    
    # 出价策略选项
    def get_bid_strategy_options(self) -> List[Dict]:
        return [
            {'code': 'LOWEST_COST_WITHOUT_CAP', 'name': '最低成本（无上限）', 'description': '在预算内获得最多结果'},
            {'code': 'LOWEST_COST_WITH_COST_CAP', 'name': '最低成本（有成本上限）', 'description': '控制平均每次结果成本'},
            {'code': 'COST_PER_ESTIMATED_ACTION_RATE', 'name': '目标成本', 'description': '设定目标每次行动成本'},
            {'code': 'BID_AMOUNT', 'name': '手动出价', 'description': '自定义出价金额'},
            {'code': 'HIGHEST_VALUE_WITHOUT_CAP', 'name': '最高价值（无上限）', 'description': '最大化转化价值'},
            {'code': 'RETURON_ON_ADS_SPEND_TARGET', 'name': '广告支出回报率目标', 'description': '设定目标 ROAS'}
        ]
    
    # 广告目标选项
    def get_campaign_objective_options(self) -> List[Dict]:
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
        return self.credentials.get('google_ads', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
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
        data = {'query': query}
        return self.request('POST', f'customers/{customer_id}:search', data=data)
    
    # 客户管理
    def list_customers(self) -> ApiResponse:
        return self.request('GET', 'customers')
    
    def get_customer(self, customer_id: str) -> ApiResponse:
        return self.request('GET', f'customers/{customer_id}')
    
    # 广告系列管理
    def list_campaigns(self, customer_id: str, filter: str = None) -> ApiResponse:
        query = "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type FROM campaign"
        if filter:
            query += f" WHERE {filter}"
        return self.search(customer_id, query)
    
    def get_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        query = f"SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id = {campaign_id}"
        return self.search(customer_id, query)
    
    def create_campaign(self, customer_id: str, campaign: Dict) -> ApiResponse:
        return self.request('POST', f'customers/{customer_id}/campaigns', data=campaign)
    
    def update_campaign(self, customer_id: str, campaign_id: str, updates: Dict) -> ApiResponse:
        campaign = {'resource_name': f'customers/{customer_id}/campaigns/{campaign_id}', **updates}
        return self.request('PATCH', f'customers/{customer_id}/campaigns/{campaign_id}', data=campaign)
    
    def pause_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        return self.update_campaign(customer_id, campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        return self.update_campaign(customer_id, campaign_id, {'status': 'ENABLED'})
    
    def delete_campaign(self, customer_id: str, campaign_id: str) -> ApiResponse:
        return self.request('DELETE', f'customers/{customer_id}/campaigns/{campaign_id}')
    
    # 广告组管理
    def list_ad_groups(self, customer_id: str, campaign_id: str) -> ApiResponse:
        query = f"SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group WHERE ad_group.campaign = \'customers/{customer_id}/campaigns/{campaign_id}\'"
        return self.search(customer_id, query)
    
    def create_ad_group(self, customer_id: str, ad_group: Dict) -> ApiResponse:
        return self.request('POST', f'customers/{customer_id}/adGroups', data=ad_group)
    
    def update_ad_group(self, customer_id: str, ad_group_id: str, updates: Dict) -> ApiResponse:
        return self.request('PATCH', f'customers/{customer_id}/adGroups/{ad_group_id}', data=updates)
    
    def pause_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        return self.update_ad_group(customer_id, ad_group_id, {'status': 'PAUSED'})
    
    def resume_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        return self.update_ad_group(customer_id, ad_group_id, {'status': 'ENABLED'})
    
    def delete_ad_group(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        return self.request('DELETE', f'customers/{customer_id}/adGroups/{ad_group_id}')
    
    # 关键词管理
    def list_keywords(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        query = f"SELECT keyword.id, keyword.text, keyword.match_type FROM keyword WHERE keyword.ad_group = \'customers/{customer_id}/adGroups/{ad_group_id}\'"
        return self.search(customer_id, query)
    
    def create_keywords(self, customer_id: str, ad_group_id: str, keywords: List[Dict]) -> ApiResponse:
        operations = []
        for kw in keywords:
            operations.append({'resource_name': f'customers/{customer_id}/adGroupCriteria/{ad_group_id}', 'keyword': {'text': kw['text'], 'match_type': kw.get('match_type', 'PHRASE')}})
        return self.request('POST', f'customers/{customer_id}/adGroupCriteria:mutate', data={'operations': operations})
    
    def delete_keywords(self, customer_id: str, keyword_ids: List[str]) -> ApiResponse:
        operations = [{'resource_name': f'customers/{customer_id}/adGroupCriteria/{kid}', 'remove': True} for kid in keyword_ids]
        return self.request('POST', f'customers/{customer_id}/adGroupCriteria:mutate', data={'operations': operations})
    
    # 广告管理
    def list_ads(self, customer_id: str, ad_group_id: str) -> ApiResponse:
        query = f"SELECT ad.id, ad.type, ad.status FROM ad WHERE ad.ad_group = \'customers/{customer_id}/adGroups/{ad_group_id}\'"
        return self.search(customer_id, query)
    
    def create_ad(self, customer_id: str, ad: Dict) -> ApiResponse:
        return self.request('POST', f'customers/{customer_id}/ads', data=ad)
    
    def update_ad(self, customer_id: str, ad_id: str, updates: Dict) -> ApiResponse:
        return self.request('PATCH', f'customers/{customer_id}/ads/{ad_id}', data=updates)
    
    def pause_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        return self.update_ad(customer_id, ad_id, {'status': 'PAUSED'})
    
    def resume_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        return self.update_ad(customer_id, ad_id, {'status': 'ENABLED'})
    
    def delete_ad(self, customer_id: str, ad_id: str) -> ApiResponse:
        return self.request('DELETE', f'customers/{customer_id}/ads/{ad_id}')
    
    # 转化追踪
    def list_conversion_actions(self, customer_id: str) -> ApiResponse:
        query = "SELECT conversion_action.id, conversion_action.name, conversion_action.type FROM conversion_action"
        return self.search(customer_id, query)
    
    def create_conversion_action(self, customer_id: str, conversion: Dict) -> ApiResponse:
        return self.request('POST', f'customers/{customer_id}/conversionActions', data=conversion)
    
    # 出价策略
    def list_bid_strategies(self, customer_id: str) -> ApiResponse:
        query = "SELECT bidding_strategy.id, bidding_strategy.name, bidding_strategy.type FROM bidding_strategy"
        return self.search(customer_id, query)
    
    def get_bid_suggestion(self, customer_id: str, campaign_id: str) -> ApiResponse:
        query = f"SELECT keyword_match_type, metrics.all_conversions, metrics.estimated_ranked_cpc_micros FROM keyword_view WHERE segments.date DURING LAST_30_DAYS AND campaign.id = {campaign_id}"
        return self.search(customer_id, query)
    
    # 报表
    def generate_report(self, customer_id: str, date_range: Dict) -> ApiResponse:
        query = f"SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date BETWEEN \'{date_range[\'start\']}\' AND \'{date_range[\'end\']}\'"
        return self.search(customer_id, query)
    
    # 广告系列类型选项
    def get_campaign_type_options(self) -> List[Dict]:
        return [
            {'code': 'SEARCH', 'name': '搜索广告', 'description': '在 Google 搜索结果中展示'},
            {'code': 'DISPLAY', 'name': '展示广告', 'description': '在 Google 展示网络中展示'},
            {'code': 'SHOPPING', 'name': '购物广告', 'description': '展示商品信息'},
            {'code': 'VIDEO', 'name': '视频广告', 'description': '在 YouTube 展示'},
            {'code': 'APP', 'name': '应用广告', 'description': '推广移动应用'},
            {'code': 'MAX', 'name': '全效果广告', 'description': '跨渠道自动化投放'}
        ]
    
    # 出价策略选项
    def get_bid_strategy_options(self) -> List[Dict]:
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
    
    # 资产类型选项
    def get_asset_type_options(self) -> List[Dict]:
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


class DV360Client(BaseAdPlatformClient):
    """
    Display & Video 360 API 客户端
    
    官方文档: https://developers.google.com/display-video/api
    认证方式: Service Account JWT Bearer
    API 版本: v4
    """
    
    def __init__(self, credentials: dict):
        super().__init__(credentials, 'dv360')
        self.base_url = "https://display-video.googleapis.com/v4"
        self.service_account = credentials.get('dv360', {}).get('service_account', {})
        self.partner_id = credentials.get('dv360', {}).get('partner_id', '')
        
    def get_token(self) -> str:
        """使用 Service Account 生成 JWT 并获取 Token"""
        import jwt
        from datetime import datetime, timedelta
        
        if not self.service_account:
            return ""
        
        # 简化实现：实际应使用 Service Account JSON
        return self.credentials.get('dv360', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """发送 DV360 API 请求"""
        token = self.get_token()
        if not token:
            return ApiResponse(success=False, error="Missing access_token")
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, timeout=kwargs.get('timeout', 30))
            else:
                resp = requests.post(url, headers=headers, json=kwargs.get('data', {}), timeout=kwargs.get('timeout', 30))
            
            data = resp.json()
            
            if resp.status_code >= 400:
                return ApiResponse(
                    success=False,
                    error=data.get('error', {}).get('message', 'API error'),
                    data=data
                )
            
            return ApiResponse(success=True, data=data)
        except Exception as e:
            return ApiResponse(success=False, error=str(e))
    
    # 广告主管理
    def list_advertisers(self, partner_id: str = None) -> ApiResponse:
        """获取广告主列表"""
        pid = partner_id or self.partner_id
        return self.request('GET', f'partners/{pid}/advertisers')
    
    def get_advertiser(self, advertiser_id: str) -> ApiResponse:
        """获取单个广告主详情"""
        return self.request('GET', f'advertisers/{advertiser_id}')
    
    # 广告系列管理
    def list_campaigns(self, advertiser_id: str, filter: str = None) -> ApiResponse:
        """获取广告系列列表"""
        endpoint = f'advertisers/{advertiser_id}/campaigns'
        params = {}
        if filter:
            params['filter'] = filter
        return self.request('GET', endpoint, params=params)
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """获取单个广告系列详情"""
        return self.request('GET', f'advertisers/{advertiser_id}/campaigns/{campaign_id}')
    
    def create_campaign(self, advertiser_id: str, campaign: Dict) -> ApiResponse:
        """创建广告系列"""
        return self.request('POST', f'advertisers/{advertiser_id}/campaigns', data=campaign)
    
    def update_campaign(self, advertiser_id: str, campaign_id: str, updates: Dict) -> ApiResponse:
        """更新广告系列"""
        return self.request('PATCH', f'advertisers/{advertiser_id}/campaigns/{campaign_id}', data=updates)
    
    def pause_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """暂停广告系列"""
        return self.update_campaign(advertiser_id, campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """恢复广告系列"""
        return self.update_campaign(advertiser_id, campaign_id, {'status': 'ACTIVE'})
    
    def delete_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """删除广告系列"""
        return self.request('DELETE', f'advertisers/{advertiser_id}/campaigns/{campaign_id}')
    
    # 订单项 (IO) 管理
    def list_insertion_orders(self, advertiser_id: str) -> ApiResponse:
        """获取订单项列表"""
        return self.request('GET', f'advertisers/{advertiser_id}/insertionOrders')
    
    def create_insertion_order(self, advertiser_id: str, io: Dict) -> ApiResponse:
        """创建订单项"""
        return self.request('POST', f'advertisers/{advertiser_id}/insertionOrders', data=io)
    
    # 线条项目 (Line Item) 管理
    def list_line_items(self, advertiser_id: str, io_id: str) -> ApiResponse:
        """获取线条项目列表"""
        return self.request('GET', f'advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems')
    
    def create_line_item(self, advertiser_id: str, io_id: str, line_item: Dict) -> ApiResponse:
        """创建线条项目"""
        return self.request('POST', f'advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems', data=line_item)
    
    # 创意管理
    def list_creatives(self, advertiser_id: str, line_item_id: str = None) -> ApiResponse:
        """获取创意列表"""
        if line_item_id:
            return self.request('GET', f'advertisers/{advertiser_id}/lineItems/{line_item_id}/creatives')
        return self.request('GET', f'advertisers/{advertiser_id}/creatives')
    
    def create_creative(self, advertiser_id: str, creative: Dict) -> ApiResponse:
        """创建创意"""
        return self.request('POST', f'advertisers/{advertiser_id}/creatives', data=creative)
    
    # 报表
    def get_report(self, advertiser_id: str, date_start: str, date_end: str, 
                   level: str = 'CAMPAIGN', dimensions: List[str] = None) -> ApiResponse:
        """获取报表数据"""
        data = {
            'advertiser_id': int(advertiser_id),
            'date_range': {'start_date': date_start, 'end_date': date_end},
            'level': level
        }
        if dimensions:
            data['dimensions'] = dimensions
        return self.request('POST', 'reports/generate', data=data)
    
    # 交易类型选项
    def get_transaction_type_options(self) -> List[Dict]:
        """获取官方交易类型选项"""
        return [
            {'code': 'PROGRAMMATIC_GUARANTEED', 'name': '程序化保量', 'description': '保证展示量的程序化购买'},
            {'code': 'PRIVATE_MARKETPLACE', 'name': '私有市场', 'description': '邀请制的优质库存交易'},
            {'code': 'PREFERRED_DEAL', 'name': '优先交易', 'description': '享有优先购买权的交易'},
            {'code': 'OPEN_AUCTION', 'name': '公开竞价', 'description': '常规公开市场竞价'}
        ]
    
    # 出价策略选项
    def get_bid_strategy_options(self) -> List[Dict]:
        """获取官方出价策略选项"""
        return [
            {'code': 'CPM', 'name': 'CPM', 'description': '按千次展示计费'},
            {'code': 'CPC', 'name': 'CPC', 'description': '按点击计费'},
            {'code': 'CPV', 'name': 'CPV', 'description': '按视频观看计费'},
            {'code': 'OCPM', 'name': 'OCPM', 'description': '优化千次展示'},
            {'code': 'CPA', 'name': 'CPA', 'description': '按转化计费'}
        ]
    
    # 创意格式选项
    def get_creative_format_options(self) -> List[Dict]:
        """获取官方创意格式选项"""
        return [
            {'code': 'DISPLAY_VIDEO_AD', 'name': '展示视频广告', 'description': '标准视频广告'},
            {'code': 'BANNER_AD', 'name': '横幅广告', 'description': '静态或富媒体横幅'},
            {'code': 'NATIVE_AD', 'name': '原生广告', 'description': '与内容融合的广告'},
            {'code': 'HTML5_AD', 'name': 'HTML5 广告', 'description': '交互式 HTML5 广告'},
            {'code': 'VIDEO_PREROLL_AD', 'name': '前贴片视频', 'description': '视频前广告'},
            {'code': 'VIDEO_MIDROLL_AD', 'name': '中贴片视频', 'description': '视频中广告'}
        ]
    
    # 定向维度选项
    def get_targeting_dimension_options(self) -> List[Dict]:
        """获取官方定向维度选项"""
        return [
            {'code': 'GEO', 'name': '地域', 'description': '国家、地区、城市定向'},
            {'code': 'AGE', 'name': '年龄', 'description': '年龄段定向'},
            {'code': 'GENDER', 'name': '性别', 'description': '男/女定向'},
            {'code': 'INTEREST', 'name': '兴趣', 'description': '兴趣标签定向'},
            {'code': 'BEHAVIOR', 'name': '行为', 'description': '用户行为定向'},
            {'code': 'KEYWORD', 'name': '关键词', 'description': '页面关键词定向'},
            {'code': 'PLACEMENT', 'name': '投放位置', 'description': '具体网站/应用定向'},
            {'code': 'APP', 'name': '应用', 'description': '特定应用定向'},
            {'code': 'DEVICE', 'name': '设备', 'description': '手机/平板/电脑定向'},
            {'code': 'OPERATING_SYSTEM', 'name': '操作系统', 'description': 'iOS/Android/Windows定向'}
        ]
