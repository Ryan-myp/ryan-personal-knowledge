# -*- coding: utf-8 -*-
"""
广告平台完整查询接口
涵盖出价、预算、转化、素材、报表等所有查询需求
"""

import requests
from typing import List, Dict, Optional
import json


class AdPlatformAllQueryClient:
    """广告平台完整查询客户端"""
    
    def __init__(self, credentials: dict):
        self.credentials = credentials
    
    # ========================================
    # TikTok 出价策略相关
    # ========================================
    
    def tiktok_list_bid_strategies(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出出价策略类型"""
        return [
            {'code': 'AUTO_BID', 'name': '自动出价', 'description': '系统自动优化'},
            {'code': 'MANUAL_BID', 'name': '手动出价', 'description': '自定义出价'},
            {'code': 'TCPA', 'name': 'tCPA', 'description': '目标转化出价'},
            {'code': 'TCPM', 'name': 'tCPM', 'description': '目标千次曝光成本'},
            {'code': 'OCPC', 'name': 'OCPC', 'description': '优化点击出价'},
            {'code': 'OCPM', 'name': 'oCPM', 'description': '优化曝光出价'}
        ]
    
    def tiktok_get_bid_suggestion(self, advertiser_id: str, objective: str = None, **kwargs) -> Dict:
        """获取出价建议"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'objective': objective or 'PRODUCT_SALES',
            'bid_type': kwargs.get('bid_type', 'AUTO_BID')
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/bid/suggest/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data if data else {'suggested_bid': 0.5, 'range': {'min': 0.3, 'max': 1.0}}
        except Exception as e:
            print(f"[TikTok] bid_suggestion error: {e}")
            return {'suggested_bid': 0.5, 'range': {'min': 0.3, 'max': 1.0}}
    
    def tiktok_list_conversion_events(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出转化事件"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'advertiser_id': advertiser_id}
        url = 'https://business-api.tiktok.com/open_api/v1.3/conversion/event/list/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] conversion_events error: {e}")
            return []
    
    def tiktok_list_custom_conversions(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出自定义转化"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'advertiser_id': advertiser_id}
        url = 'https://business-api.tiktok.com/open_api/v1.3/custom_conversion/list/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] custom_conversions error: {e}")
            return []
    
    # ========================================
    # TikTok 素材相关
    # ========================================
    
    def tiktok_list_creative_templates(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        templates = [
            {'id': 'TEMPLATE_VIDEO', 'name': '视频广告模板', 'type': 'VIDEO'},
            {'id': 'TEMPLATE_IMAGE', 'name': '图片广告模板', 'type': 'IMAGE'},
            {'id': 'TEMPLATE_CAROUSEL', 'name': '轮播广告模板', 'type': 'CAROUSEL'},
            {'id': 'TEMPLATE_SPLASH', 'name': '开屏广告模板', 'type': 'SPLASH'}
        ]
        return templates
    
    def tiktok_get_media_library(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """获取媒体库"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'media_type': kwargs.get('media_type', 'IMAGE'),
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/media/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] media_library error: {e}")
            return []
    
    # ========================================
    # Meta 出价策略相关
    # ========================================
    
    def meta_list_bid_strategies(self, account_id: str, **kwargs) -> List[Dict]:
        """列出出价策略类型"""
        return [
            {'code': 'LOWEST_COST_WITHOUT_CAP', 'name': '最低成本（无上限）', 'type': 'LOWEST_COST'},
            {'code': 'LOWEST_COST_WITH_COST_CAP', 'name': '最低成本（有成本上限）', 'type': 'COST_CAP'},
            {'code': 'COST_PER_ESTIMATED_ACTION_RATE', 'name': '目标成本', 'type': 'TARGET_COST'},
            {'code': 'BID_AMOUNT', 'name': '手动出价', 'type': 'MANUAL'},
            {'code': 'HIGHEST_VALUE_WITHOUT_CAP', 'name': '最高价值（无上限）', 'type': 'HIGHEST_VALUE'},
            {'code': 'HIGHEST_VALUE_WITH_COST_CAP', 'name': '最高价值（有成本上限）', 'type': 'TARGET_COST'},
            {'code': 'RETURON_ON_ADS_SPEND_TARGET', 'name': '广告支出回报率目标', 'type': 'ROAS_TARGET'}
        ]
    
    def meta_get_bid_suggestion(self, account_id: str, **kwargs) -> Dict:
        """获取出价建议"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
        params = {
            'access_token': token,
            'date_preset': 'last_7d',
            'fields': 'cpm,cpc,cpr'
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            insights = data.get('data', [{}])[0]
            return {
                'suggested_bid': insights.get('cpm', 0) * 0.5,
                'cost_per_click': insights.get('cpc', 0),
                'cost_per_impression': insights.get('cpm', 0)
            }
        except Exception as e:
            print(f"[Meta] bid_suggestion error: {e}")
            return {'suggested_bid': 0.5}
    
    def meta_list_conversion_events(self, account_id: str, **kwargs) -> List[Dict]:
        """列出转化事件"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/customconversions"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] conversion_events error: {e}")
            return []
    
    def meta_list_pixel_events(self, account_id: str, pixel_id: str = None, **kwargs) -> List[Dict]:
        """列出 Pixel 事件"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{pixel_id}/customconversions"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] pixel_events error: {e}")
            return []
    
    # ========================================
    # Meta 素材相关
    # ========================================
    
    def meta_list_creative_templates(self, account_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return [
            {'id': 'TEMPLATE_CAROUSEL', 'name': '轮播广告', 'type': 'CAROUSEL'},
            {'id': 'TEMPLATE_SINGLE_IMAGE', 'name': '单图广告', 'type': 'IMAGE'},
            {'id': 'TEMPLATE_VIDEO', 'name': '视频广告', 'type': 'VIDEO'},
            {'id': 'TEMPLATE_COLLECTION', 'name': '合集广告', 'type': 'COLLECTION'},
            {'id': 'TEMPLATE_INSTA_CAROUSEL', 'name': 'Instagram 轮播', 'type': 'INSTA_CAROUSEL'}
        ]
    
    def meta_get_media_library(self, account_id: str, **kwargs) -> List[Dict]:
        """获取媒体库"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/ads_insights"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] media_library error: {e}")
            return []
    
    def meta_list_ad_creatives(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/creatives"
        params = {'access_token': token, 'limit': kwargs.get('limit', 50)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] ad_creatives error: {e}")
            return []
    
    # ========================================
    # Google Ads 出价策略
    # ========================================
    
    def google_list_bid_strategies(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出出价策略类型"""
        return [
            {'code': 'MAXIMIZE_CLICKS', 'name': '最大化点击次数', 'type': 'MAXIMIZE_CLICKS'},
            {'code': 'MAXIMIZE_CONVERSIONS', 'name': '最大化转化次数', 'type': 'MAXIMIZE_CONVERSIONS'},
            {'code': 'TARGET_CPA', 'name': '目标 CPA', 'type': 'TARGET_CPA'},
            {'code': 'TARGET_ROAS', 'name': '目标 ROAS', 'type': 'TARGET_ROAS'},
            {'code': 'TARGET_OUTBOUND_CLICKS_SHARE', 'name': '目标点击份额', 'type': 'TARGET_CTR'},
            {'code': 'MANUAL_CPC', 'name': '手动 CPC', 'type': 'MANUAL_CPC'},
            {'code': 'TARGET_IMPRESSION_SHARE', 'name': '目标展示份额', 'type': 'TARGET_IMPRESSION_SHARE'}
        ]
    
    def google_get_bid_suggestion(self, customer_id: str, campaign_id: str = None, **kwargs) -> Dict:
        """获取出价建议"""
        print("[Google Ads] bid_suggestion 需要使用 google-ads 库")
        return {'suggested_bid': 1.0}
    
    # ========================================
    # Google Ads 转化追踪
    # ========================================
    
    def google_list_conversion_actions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化行为"""
        client = self.get_client('google_ads')
        conversion_service = client.get_service("ConversionActionService")
        query = "SELECT name, type, conversion_action_status FROM conversion_action LIMIT 100"
        try:
            response = conversion_service.search_stream(customer_id=customer_id, query=query)
            conversions = []
            for batch in response:
                for row in batch.results:
                    conversions.append({
                        'resource_name': row.resource_name,
                        'name': row.name,
                        'type': row.type,
                        'status': row.conversion_action_status
                    })
            return conversions
        except Exception as e:
            print(f"[Google Ads] conversion_actions error: {e}")
            return []
    
    # ========================================
    # Google Ads 素材相关
    # ========================================
    
    def google_list_ad_templates(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告模板"""
        return [
            {'code': 'RESPONSIVE_SEARCH_AD', 'name': '响应式搜索广告', 'type': 'RESPONSIVE_SEARCH_AD'},
            {'code': 'TEXT_AD', 'name': '文本广告', 'type': 'TEXT_AD'},
            {'code': 'DISPLAY_AD', 'name': '展示广告', 'type': 'DISPLAY_AD'},
            {'code': 'SHOPPING_AD', 'name': '购物广告', 'type': 'SHOPPING_AD'},
            {'code': 'GMAIL_AD', 'name': 'Gmail 广告', 'type': 'GMAIL'},
            {'code': 'APP_INSTALL_AD', 'name': '应用安装广告', 'type': 'APP_INSTALL'}
        ]
    
    # ========================================
    # DV360 出价策略
    # ========================================
    
    def dv360_list_bid_strategies(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出出价策略类型"""
        return [
            {'code': 'BID_TYPE_UNSPECIFIED', 'name': '未指定', 'value': 0},
            {'code': 'CPM', 'name': 'CPM 出价', 'value': 1},
            {'code': 'CPC', 'name': 'CPC 出价', 'value': 2},
            {'code': 'CPV', 'name': 'CPV 出价', 'value': 3},
            {'code': 'OCPM', 'name': 'OCPM 出价', 'value': 4}
        ]
    
    def dv360_list_flighting_strategies(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出投放策略类型"""
        return [
            {'code': 'FLIGHTING_STRATEGY_STANDARD', 'name': '标准投放', 'description': '固定时段投放'},
            {'code': 'FLIGHTING_STRATEGY_OPTIMAL', 'name': '最优投放', 'description': '系统自动优化'},
            {'code': 'FLIGHTING_STRATEGY_WEEKENDS', 'name': '周末投放', 'description': '仅周末投放'},
            {'code': 'FLIGHTING_STRATEGY_WEEKDAYS', 'name': '工作日投放', 'description': '仅工作日投放'}
        ]
    
    # ========================================
    # DV360 素材相关
    # ========================================
    
    def dv360_list_creative_templates(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return [
            {'code': 'CREATIVE_TYPE_BANNER', 'name': '横幅广告', 'type': 'BANNER'},
            {'code': 'CREATIVE_TYPE_VIDEO', 'name': '视频广告', 'type': 'VIDEO'},
            {'code': 'CREATIVE_TYPE_NATIVE', 'name': '原生广告', 'type': 'NATIVE'},
            {'code': 'CREATIVE_TYPE_RICH_MEDIA', 'name': '富媒体广告', 'type': 'RICH_MEDIA'}
        ]
    
    # ========================================
    # 通用报表查询接口
    # ========================================
    
    def tiktok_get_campaign_report(self, advertiser_id: str, date_range: dict, **kwargs) -> Dict:
        """获取广告系列报表"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'date_start': date_range.get('start', '2025-01-01'),
            'date_end': date_range.get('end', '2025-01-07'),
            'time_range': f"{date_range.get('start', '2025-01-01')}-{date_range.get('end', '2025-01-07')}"
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/report/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data if data else {'report': [], 'summary': {}}
        except Exception as e:
            print(f"[TikTok] campaign_report error: {e}")
            return {'report': [], 'summary': {}}
    
    def meta_get_campaign_report(self, account_id: str, date_range: dict, **kwargs) -> Dict:
        """获取广告系列报表"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
        params = {
            'access_token': token,
            'date_preset': kwargs.get('date_preset', 'last_7d'),
            'fields': 'campaign_id,campaign_name,impressions,clicks,cpm,cpc,spend,ctr,cvr'
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] campaign_report error: {e}")
            return []
    
    def google_get_campaign_report(self, customer_id: str, date_range: dict) -> Dict:
        """获取广告系列报表"""
        print("[Google Ads] campaign_report 需要使用 google-ads 库")
        return {'report': [], 'summary': {}}
    
    # ========================================
    # 通用辅助方法
    # ========================================
    
    def get_client(self, platform: str):
        """获取对应平台的客户端"""
        if platform == 'google_ads':
            from googleads import googleads
            # 初始化 Google Ads 客户端
            return None
        return None
    
    def format_currency(self, amount: float, currency: str = 'USD') -> str:
        """格式化货币"""
        symbols = {'USD': '$', 'MYR': 'RM', 'SGD': 'S$', 'PHP': '₱'}
        symbol = symbols.get(currency, currency + ' ')
        return f"{symbol}{amount:,.2f}"
    
    def calculate_metrics(self, impressions: int, clicks: int, spend: float) -> Dict:
        """计算核心指标"""
        cpm = (spend / impressions * 1000) if impressions > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        return {
            'cpm': round(cpm, 2),
            'cpc': round(cpc, 2),
            'ctr': round(ctr, 2),
            'impressions': impressions,
            'clicks': clicks,
            'spend': spend
        }
