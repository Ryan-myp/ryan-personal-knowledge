# -*- coding: utf-8 -*-
"""
DV360 (Display & Video 360) API 客户端

官方文档: https://developers.google.com/display-video/api
认证方式: Service Account JWT Bearer
API 版本: v4
"""

from typing import List, Dict, Optional
from api_common import ApiResponse, BaseAdPlatformClient
import requests


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
        """获取 DV360 Access Token"""
        # 简化实现：实际应使用 Service Account 生成 JWT
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
    
    # ==================== 广告主管理 ====================
    def list_advertisers(self, partner_id: str = None) -> ApiResponse:
        """获取广告主列表"""
        pid = partner_id or self.partner_id
        return self.request('GET', f'partners/{pid}/advertisers')
    
    def get_advertiser(self, advertiser_id: str) -> ApiResponse:
        """获取单个广告主详情"""
        return self.request('GET', f'advertisers/{advertiser_id}')
    
    # ==================== 广告系列管理 ====================
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
    
    # ==================== 订单项 (IO) 管理 ====================
    def list_insertion_orders(self, advertiser_id: str) -> ApiResponse:
        """获取订单项列表"""
        return self.request('GET', f'advertisers/{advertiser_id}/insertionOrders')
    
    def create_insertion_order(self, advertiser_id: str, io: Dict) -> ApiResponse:
        """创建订单项"""
        return self.request('POST', f'advertisers/{advertiser_id}/insertionOrders', data=io)
    
    # ==================== 线条项目 (Line Item) 管理 ====================
    def list_line_items(self, advertiser_id: str, io_id: str) -> ApiResponse:
        """获取线条项目列表"""
        return self.request('GET', f'advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems')
    
    def create_line_item(self, advertiser_id: str, io_id: str, line_item: Dict) -> ApiResponse:
        """创建线条项目"""
        return self.request('POST', f'advertisers/{advertiser_id}/insertionOrders/{io_id}/lineItems', data=line_item)
    
    # ==================== 创意管理 ====================
    def list_creatives(self, advertiser_id: str, line_item_id: str = None) -> ApiResponse:
        """获取创意列表"""
        if line_item_id:
            return self.request('GET', f'advertisers/{advertiser_id}/lineItems/{line_item_id}/creatives')
        return self.request('GET', f'advertisers/{advertiser_id}/creatives')
    
    def create_creative(self, advertiser_id: str, creative: Dict) -> ApiResponse:
        """创建创意"""
        return self.request('POST', f'advertisers/{advertiser_id}/creatives', data=creative)
    
    # ==================== 报表 ====================
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
    
    # ==================== 官方选项数据 ====================
    def get_transaction_type_options(self) -> List[Dict]:
        """获取官方交易类型选项"""
        return [
            {'code': 'PROGRAMMATIC_GUARANTEED', 'name': '程序化保量', 'description': '保证展示量的程序化购买'},
            {'code': 'PRIVATE_MARKETPLACE', 'name': '私有市场', 'description': '邀请制的优质库存交易'},
            {'code': 'PREFERRED_DEAL', 'name': '优先交易', 'description': '享有优先购买权的交易'},
            {'code': 'OPEN_AUCTION', 'name': '公开竞价', 'description': '常规公开市场竞价'}
        ]
    
    def get_bid_strategy_options(self) -> List[Dict]:
        """获取官方出价策略选项"""
        return [
            {'code': 'CPM', 'name': 'CPM', 'description': '按千次展示计费'},
            {'code': 'CPC', 'name': 'CPC', 'description': '按点击计费'},
            {'code': 'CPV', 'name': 'CPV', 'description': '按视频观看计费'},
            {'code': 'OCPM', 'name': 'OCPM', 'description': '优化千次展示'},
            {'code': 'CPA', 'name': 'CPA', 'description': '按转化计费'}
        ]
    
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
