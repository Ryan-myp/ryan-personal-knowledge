# -*- coding: utf-8 -*-
"""
TikTok Marketing API 客户端

官方文档: https://business-api.tiktok.com/portal/docs
认证方式: Access-Token Header
API 版本: v1.3
"""

import json
from typing import List, Dict, Optional
from api_common import ApiResponse, BaseAdPlatformClient
import requests


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
        """获取 TikTok Access Token"""
        return self.credentials.get('tiktok', {}).get('access_token', '')
    
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """发送 TikTok API 请求"""
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
    
    # ==================== 账户管理 ====================
    def list_accounts(self, advertiser_id: str) -> ApiResponse:
        """获取广告账户信息"""
        return self.request('GET', 'account/get/', params={'advertiser_id': advertiser_id})
    
    # ==================== 广告系列管理 ====================
    def list_campaigns(self, advertiser_id: str, filtering: List[Dict] = None) -> ApiResponse:
        """获取广告系列列表"""
        data = {'advertiser_id': int(advertiser_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'campaign/get/', data=data)
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """获取单个广告系列详情"""
        filtering = [{'field': 'CAMPAIGN_IDS', 'operator': 'IN', 'values': [campaign_id]}]
        return self.list_campaigns(advertiser_id, filtering)
    
    def create_campaign(self, advertiser_id: str, campaign: Dict) -> ApiResponse:
        """创建广告系列"""
        return self.request('POST', 'campaign/create/', data={'advertiser_id': int(advertiser_id), 'campaign': campaign})
    
    def update_campaign(self, advertiser_id: str, campaign_id: str, updates: Dict) -> ApiResponse:
        """更新广告系列"""
        return self.request('POST', 'campaign/update/', data={'advertiser_id': int(advertiser_id), 'campaign_id': int(campaign_id), 'campaign': updates})
    
    def pause_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """暂停广告系列"""
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 0})
    
    def resume_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """恢复广告系列"""
        return self.update_campaign(advertiser_id, campaign_id, {'campaign_group_status': 1})
    
    def delete_campaign(self, advertiser_id: str, campaign_id: str) -> ApiResponse:
        """删除广告系列"""
        return self.request('POST', 'campaign/delete/', data={'advertiser_id': int(advertiser_id), 'campaign_ids': [int(campaign_id)]})
    
    # ==================== 广告组管理 ====================
    def list_adgroups(self, advertiser_id: str, campaign_id: str, filtering: List[Dict] = None) -> ApiResponse:
        """获取广告组列表"""
        data = {'advertiser_id': int(advertiser_id), 'campaign_id': int(campaign_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'adgroup/get/', data=data)
    
    def create_adgroup(self, advertiser_id: str, adgroup: Dict) -> ApiResponse:
        """创建广告组"""
        return self.request('POST', 'adgroup/create/', data={'advertiser_id': int(advertiser_id), 'ad_group': adgroup})
    
    def update_adgroup(self, advertiser_id: str, adgroup_id: str, updates: Dict) -> ApiResponse:
        """更新广告组"""
        return self.request('POST', 'adgroup/update/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id), 'ad_group': updates})
    
    def pause_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        """暂停广告组"""
        return self.update_adgroup(advertiser_id, adgroup_id, {'ad_group_status': 0})
    
    def resume_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        """恢复广告组"""
        return self.update_adgroup(advertiser_id, adgroup_id, {'ad_group_status': 1})
    
    def delete_adgroup(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        """删除广告组"""
        return self.request('POST', 'adgroup/delete/', data={'advertiser_id': int(advertiser_id), 'ad_group_ids': [int(adgroup_id)]})
    
    # ==================== 广告管理 ====================
    def list_ads(self, advertiser_id: str, adgroup_id: str, filtering: List[Dict] = None) -> ApiResponse:
        """获取广告列表"""
        data = {'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id)}
        if filtering:
            data['filtering'] = filtering
        return self.request('POST', 'ad/get/', data=data)
    
    def create_ad(self, advertiser_id: str, ad: Dict) -> ApiResponse:
        """创建广告"""
        return self.request('POST', 'ad/create/', data={'advertiser_id': int(advertiser_id), 'ad': ad})
    
    def update_ad(self, advertiser_id: str, ad_id: str, updates: Dict) -> ApiResponse:
        """更新广告"""
        return self.request('POST', 'ad/update/', data={'advertiser_id': int(advertiser_id), 'ad_id': int(ad_id), 'ad': updates})
    
    def pause_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        """暂停广告"""
        return self.update_ad(advertiser_id, ad_id, {'ad_status': 0})
    
    def resume_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        """恢复广告"""
        return self.update_ad(advertiser_id, ad_id, {'ad_status': 1})
    
    def delete_ad(self, advertiser_id: str, ad_id: str) -> ApiResponse:
        """删除广告"""
        return self.request('POST', 'ad/delete/', data={'advertiser_id': int(advertiser_id), 'ad_ids': [int(ad_id)]})
    
    # ==================== 关键词管理 ====================
    def list_keywords(self, advertiser_id: str, adgroup_id: str) -> ApiResponse:
        """获取关键词列表"""
        return self.request('POST', 'keyword/get/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id)})
    
    def create_keywords(self, advertiser_id: str, adgroup_id: str, keywords: List[Dict]) -> ApiResponse:
        """创建关键词"""
        return self.request('POST', 'keyword/create/', data={'advertiser_id': int(advertiser_id), 'ad_group_id': int(adgroup_id), 'keywords': keywords})
    
    def delete_keywords(self, advertiser_id: str, keyword_ids: List[str]) -> ApiResponse:
        """删除关键词"""
        return self.request('POST', 'keyword/delete/', data={'advertiser_id': int(advertiser_id), 'keyword_ids': [int(kid) for kid in keyword_ids]})
    
    # ==================== 受众管理 ====================
    def list_audiences(self, advertiser_id: str) -> ApiResponse:
        """获取受众列表"""
        return self.request('POST', 'audience/get/', data={'advertiser_id': int(advertiser_id)})
    
    def create_audience(self, advertiser_id: str, audience: Dict) -> ApiResponse:
        """创建受众"""
        return self.request('POST', 'audience/create/', data={'advertiser_id': int(advertiser_id), 'audience': audience})
    
    def delete_audience(self, advertiser_id: str, audience_id: str) -> ApiResponse:
        """删除受众"""
        return self.request('POST', 'audience/delete/', data={'advertiser_id': int(advertiser_id), 'audience_id': int(audience_id)})
    
    # ==================== 转化追踪 ====================
    def list_conversion_events(self, advertiser_id: str) -> ApiResponse:
        """获取转化事件列表"""
        return self.request('POST', 'conversion/get/', data={'advertiser_id': int(advertiser_id)})
    
    def create_custom_conversion(self, advertiser_id: str, conversion: Dict) -> ApiResponse:
        """创建自定义转化"""
        return self.request('POST', 'conversion/create/', data={'advertiser_id': int(advertiser_id), 'conversion': conversion})
    
    # ==================== 媒体库 ====================
    def get_media_library(self, advertiser_id: str) -> ApiResponse:
        """获取媒体库"""
        return self.request('POST', 'media_library/get/', data={'advertiser_id': int(advertiser_id)})
    
    def upload_image(self, advertiser_id: str, image_data: Dict) -> ApiResponse:
        """上传图片"""
        return self.request('POST', 'media_library/upload/image', data={'advertiser_id': int(advertiser_id), 'image': image_data})
    
    # ==================== 报表 ====================
    def get_report(self, advertiser_id: str, date_start: str, date_end: str, 
                   level: str = 'CAMPAIGN', insights: List[str] = None) -> ApiResponse:
        """获取报表数据"""
        data = {'advertiser_id': int(advertiser_id), 'date_start': date_start, 'date_end': date_end, 'level': level}
        if insights:
            data['insights'] = insights
        return self.request('POST', 'report/get/', data=data)
    
    # ==================== 官方选项数据 ====================
    def get_placement_options(self) -> List[Dict]:
        """获取官方投放位置选项"""
        return [
            {'code': 'TikTok Feed', 'name': '推荐页', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_TIKTOK'},
            {'code': 'TikTok Search', 'name': '搜索', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_SEARCH'},
            {'code': 'TikTok Post', 'name': '发布后', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_POST'},
            {'code': 'TikTok Marketplace', 'name': '商城', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_MARKETPLACE'},
            {'code': 'TikTok Series', 'name': '系列', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_SERIES'},
            {'code': 'TikTok Live', 'name': '直播', 'api_code': 'AUTOMATIC_PLACEMENT_TYPE_LIVE'}
        ]
    
    def get_bid_strategy_options(self) -> List[Dict]:
        """获取官方出价策略选项"""
        return [
            {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS', 'name': '最低成本', 'description': '在预算内获得最多转化'},
            {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CLICKS', 'name': '最多点击', 'description': '在预算内获得最多点击'},
            {'code': 'AUTO_BID_TYPE_VALUE_MANUAL', 'name': '手动出价', 'description': '自定义出价金额'},
            {'code': 'BID_TYPE_VALUE_CPA', 'name': '目标 CPA', 'description': '设定目标每次转化费用'}
        ]
    
    def get_campaign_objective_options(self) -> List[Dict]:
        """获取官方广告目标选项"""
        return [
            {'code': 'SALES', 'name': '销售', 'description': '促成网站或应用内购买'},
            {'code': 'APP_PROMOTION', 'name': '应用推广', 'description': '推广移动应用'},
            {'code': 'LEAD_GENERATION', 'name': '潜在客户', 'description': '收集潜在客户信息'},
            {'code': 'WEBSITE_TRAFFIC', 'name': '网站流量', 'description': '引导用户访问网站'},
            {'code': 'VIDEO_VIEWS', 'name': '视频观看', 'description': '提升视频观看量'},
            {'code': 'ENGAGEMENT', 'name': '互动', 'description': '提升帖子互动'}
        ]
