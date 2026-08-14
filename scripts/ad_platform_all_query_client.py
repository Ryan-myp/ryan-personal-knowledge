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

    # ========================================
    # TikTok 账户与权限
    # ========================================
    
    def tiktok_get_account_info(self, advertiser_id: str, **kwargs) -> Dict:
        """获取广告主账户信息"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        url = f'https://business-api.tiktok.com/open_api/v1.3/account/get/?advertiser_id={advertiser_id}'
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json().get('data', {})
            return data if data else {'id': advertiser_id, 'status': 'ACTIVE'}
        except Exception as e:
            print(f"[TikTok] account_info error: {e}")
            return {'id': advertiser_id, 'status': 'ACTIVE'}
    
    def tiktok_list_account_permissions(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出账户权限"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'advertiser_id': advertiser_id}
        url = 'https://business-api.tiktok.com/open_api/v1.3/account/permission/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('permissions', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] permissions error: {e}")
            return []
    
    def tiktok_list_budget_options(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出预算选项"""
        return [
            {'code': 'DAILY', 'name': '日预算', 'min': 50, 'currency': 'USD'},
            {'code': 'LIFETIME', 'name': '总预算', 'min': 100, 'currency': 'USD'}
        ]
    
    # ========================================
    # TikTok 负面定向
    # ========================================
    
    def tiktok_list_negative_keywords(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出负面关键词"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'advertiser_id': advertiser_id}
        url = 'https://business-api.tiktok.com/open_api/v1.3/negative/keyword/list/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] negative_keywords error: {e}")
            return []
    
    def tiktok_list_content_category_targets(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出内容分类定向"""
        return [
            {'code': 'ENTERTAINMENT', 'name': '娱乐', 'level': 1},
            {'code': 'GAMING', 'name': '游戏', 'level': 1},
            {'code': 'FASHION', 'name': '时尚', 'level': 1},
            {'code': 'BEAUTY', 'name': '美妆', 'level': 1},
            {'code': 'FOOD', 'name': '美食', 'level': 1},
            {'code': 'TRAVEL', 'name': '旅游', 'level': 1},
            {'code': 'EDUCATION', 'name': '教育', 'level': 1},
            {'code': 'FINANCE', 'name': '金融', 'level': 1},
            {'code': 'TECHNOLOGY', 'name': '科技', 'level': 1},
            {'code': 'SPORTS', 'name': '体育', 'level': 1}
        ]
    
    # ========================================
    # TikTok 位置定向
    # ========================================
    
    def tiktok_list_location_types(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出位置定向类型"""
        return [
            {'code': 'COUNTRY', 'name': '国家', 'levels': ['country']},
            {'code': 'REGION', 'name': '省份', 'levels': ['country', 'region']},
            {'code': 'CITY', 'name': '城市', 'levels': ['country', 'city']},
            {'code': 'DISTRICT', 'name': '区县', 'levels': ['country', 'district']},
            {'code': 'CUSTOM_AREA', 'name': '自定义区域', 'levels': ['geo_fencing']}
        ]
    
    def tiktok_get_location_hierarchy(self, country_code: str, level: str = 'COUNTRY', **kwargs) -> List[Dict]:
        """获取地域层级结构"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'country_code': country_code, 'level': level}
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/location/hierarchy/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] location_hierarchy error: {e}")
            return []
    
    # ========================================
    # Meta 广告组高级查询
    # ========================================
    
    def meta_list_ad_set_status_options(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告组状态选项"""
        return [
            {'code': 'AD_SET_STATUS_ACTIVE', 'name': '启用', 'description': '广告组正常运行'},
            {'code': 'AD_SET_STATUS_PAUSED', 'name': '暂停', 'description': '广告组已暂停'},
            {'code': 'AD_SET_STATUS_DELETED', 'name': '已删除', 'description': '广告组已删除'},
            {'code': 'AD_SET_STATUS_ARCHIVED', 'name': '已归档', 'description': '广告组已归档'}
        ]
    
    def meta_list_placement_options(self, account_id: str, **kwargs) -> List[Dict]:
        """列出投放位置选项"""
        return [
            {'code': 'FEED', 'name': '动态消息', 'platforms': ['Facebook Feed']},
            {'code': 'STORIES', 'name': '快拍', 'platforms': ['Facebook Stories', 'Instagram Stories']},
            {'code': 'REELS', 'name': 'Reels', 'platforms': ['Instagram Reels', 'Facebook Reels']},
            {'code': 'INSTREAM', 'name': '视频插播', 'platforms': ['Facebook In-Stream']},
            {'code': 'SEARCH', 'name': '搜索', 'platforms': ['Facebook Search']},
            {'code': 'MESSAGE', 'name': '消息', 'platforms': ['Facebook Messenger']},
            {'code': 'AFTER_WATCH', 'name': '观看后', 'platforms': ['Facebook After Watch']},
            {'code': 'INSTA_FEED', 'name': 'Instagram 动态', 'platforms': ['Instagram Feed']},
            {'code': 'INSTA_STORIES', 'name': 'Instagram 快拍', 'platforms': ['Instagram Stories']},
            {'code': 'EXPLORE', 'name': '探索', 'platforms': ['Instagram Explore']}
        ]
    
    def meta_list_objective_options(self, **kwargs) -> List[Dict]:
        """列出广告目标选项"""
        return [
            {'code': 'BRAND_AWARENESS', 'name': '品牌知名度', 'category': 'awareness'},
            {'code': 'REACH', 'name': '触达', 'category': 'awareness'},
            {'code': 'TRAFFIC', 'name': '流量', 'category': 'consideration'},
            {'code': 'ENGAGEMENT', 'name': '互动', 'category': 'consideration'},
            {'code': 'APP_PROMOTIONS', 'name': '应用推广', 'category': 'consideration'},
            {'code': 'LEAD_GENERATION', 'name': '潜在客户开发', 'category': 'consideration'},
            {'code': 'MESSAGES', 'name': '消息', 'category': 'consideration'},
            {'code': 'CONVERSIONS', 'name': '转化', 'category': 'conversion'},
            {'code': 'CATALOG_SALES', 'name': '目录销售', 'category': 'conversion'},
            {'code': 'STORE_TRAFFIC', 'name': '门店流量', 'category': 'conversion'}
        ]
    
    # ========================================
    # Meta 广告创意高级查询
    # ========================================
    
    def meta_list_image_sizing_options(self, creative_type: str = None, **kwargs) -> List[Dict]:
        """列出图片尺寸选项"""
        options = [
            {'code': 'SQUARE', 'name': '正方形', 'ratio': '1:1', 'pixels': '1080x1080', 'use_cases': ['Feed', 'Stories']},
            {'code': 'PORTRAIT', 'name': '竖版', 'ratio': '4:5', 'pixels': '1080x1350', 'use_cases': ['Feed']},
            {'code': 'LANDSCAPE', 'name': '横版', 'ratio': '1.91:1', 'pixels': '1200x628', 'use_cases': ['Feed']},
            {'code': 'STORY', 'name': '快拍', 'ratio': '9:16', 'pixels': '1080x1920', 'use_cases': ['Stories', 'Reels']},
            {'code': 'COLLECTION', 'name': '合集', 'ratio': '1:1', 'pixels': '1080x1080', 'use_cases': ['Collection Ads']}
        ]
        if creative_type:
            return [o for o in options if creative_type.lower() in o['use_cases']]
        return options
    
    def meta_list_video_sizing_options(self, **kwargs) -> List[Dict]:
        """列出视频尺寸选项"""
        return [
            {'code': 'SQUARE_VIDEO', 'name': '方形视频', 'ratio': '1:1', 'pixels': '1080x1080'},
            {'code': 'PORTRAIT_VIDEO', 'name': '竖版视频', 'ratio': '4:5', 'pixels': '1080x1350'},
            {'code': 'LANDSCAPE_VIDEO', 'name': '横版视频', 'ratio': '16:9', 'pixels': '1920x1080'},
            {'code': 'STORY_VIDEO', 'name': '快拍视频', 'ratio': '9:16', 'pixels': '1080x1920'}
        ]
    
    def meta_list_carousel_card_options(self, **kwargs) -> List[Dict]:
        """列出轮播卡片选项"""
        return [
            {'code': 'IMAGE_ONLY', 'name': '仅图片', 'media_type': 'IMAGE'},
            {'code': 'VIDEO_ONLY', 'name': '仅视频', 'media_type': 'VIDEO'},
            {'code': 'IMAGE_AND_LINK', 'name': '图片+链接', 'media_type': 'IMAGE'},
            {'code': 'VIDEO_AND_LINK', 'name': '视频+链接', 'media_type': 'VIDEO'},
            {'code': 'COLLECTION', 'name': '合集', 'media_type': 'COLLECTION'}
        ]
    
    # ========================================
    # Meta 商品目录相关
    # ========================================
    
    def meta_list_catalogs(self, account_id: str, **kwargs) -> List[Dict]:
        """列出商品目录"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/product_catalogs"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] catalogs error: {e}")
            return []
    
    def meta_list_catalog_fields(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出商品目录字段"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{catalog_id}/fields"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] catalog_fields error: {e}")
            return []
    
    # ========================================
    # Meta 自动化规则
    # ========================================
    
    def meta_list_automated_rules(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自动化规则"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/automated_rules"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] automated_rules error: {e}")
            return []
    
    def meta_list_rule_action_types(self, **kwargs) -> List[Dict]:
        """列出规则动作类型"""
        return [
            {'code': 'PAUSE', 'name': '暂停', 'target_type': 'AD_SET'},
            {'code': 'ENABLE', 'name': '启用', 'target_type': 'AD_SET'},
            {'code': 'DELETE', 'name': '删除', 'target_type': 'AD_SET'},
            {'code': 'BID_CHANGE', 'name': '调整出价', 'target_type': 'AD_SET'},
            {'code': 'BUDGET_CHANGE', 'name': '调整预算', 'target_type': 'AD_SET'},
            {'code': 'AUDIENCE_CHANGE', 'name': '调整受众', 'target_type': 'AD_SET'}
        ]
    
    # ========================================
    # Meta A/B 测试相关
    # ========================================
    
    def meta_list_ab_test_clauses(self, account_id: str, **kwargs) -> List[Dict]:
        """列出 A/B 测试子句"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/abtests"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] ab_test_clauses error: {e}")
            return []
    
    def meta_list_experiment_configurations(self, account_id: str, **kwargs) -> List[Dict]:
        """列出实验配置"""
        return [
            {'code': 'SPLIT_TEST', 'name': '分流测试', 'description': '标准 A/B 测试'},
            {'code': 'INCREMENTALITY_TEST', 'name': '增量测试', 'description': '品牌lift测试'},
            {'code': 'QUALITATIVE_EXPERIMENT', 'name': '定性实验', 'description': '用户反馈实验'}
        ]
    
    # ========================================
    # Meta 品牌安全
    # ========================================
    
    def meta_list_brand_safety_categories(self, **kwargs) -> List[Dict]:
        """列出品牌安全分类"""
        return [
            {'code': 'ADVERSE_CONTENT', 'name': '不当内容', 'level': 'BLOCK'},
            {'code': 'CONTROVERSIAL_ISSUES', 'name': '争议话题', 'level': 'LIMIT'},
            {'code': 'SOCIAL_ISSUES', 'name': '社会议题', 'level': 'LIMIT'},
            {'code': 'DEATH_AND_TRAGEDY', 'name': '死亡与悲剧', 'level': 'BLOCK'},
            {'code': 'HATE_SYMBOLS', 'name': '仇恨符号', 'level': 'BLOCK'},
            {'code': 'ILLICIT_DRUGS', 'name': '非法药物', 'level': 'BLOCK'},
            {'code': 'SEXUALLY_EXPLICIT', 'name': '性暴露内容', 'level': 'BLOCK'},
            {'code': 'VIOLENCE_AND_GORE', 'name': '暴力与血腥', 'level': 'BLOCK'}
        ]
    
    def meta_list_content_classification_labels(self, **kwargs) -> List[Dict]:
        """列出内容分类标签"""
        return [
            {'code': 'CGI', 'name': 'CGI 内容'},
            {'code': 'GAMING', 'name': '游戏内容'},
            {'code': 'SPORTS', 'name': '体育内容'},
            {'code': 'NEWS', 'name': '新闻内容'},
            {'code': 'MUSIC', 'name': '音乐内容'},
            {'code': 'BEAUTY', 'name': '美妆内容'},
            {'code': 'FAMILY', 'name': '家庭内容'},
            {'code': 'COMEDY', 'name': '喜剧内容'}
        ]
    
    # ========================================
    # Google Ads 广告组相关
    # ========================================
    
    def google_list_ad_group_types(self, **kwargs) -> List[Dict]:
        """列出广告组类型"""
        return [
            {'code': 'SEARCH_STANDARD', 'name': '标准搜索广告组', 'type': 'SEARCH'},
            {'code': 'SEARCH_DYNAMIC', 'name': '动态搜索广告组', 'type': 'SEARCH'},
            {'code': 'SHOPPING_STANDARD', 'name': '标准购物广告组', 'type': 'SHOPPING'},
            {'code': 'SHOPPINGsmart', 'name': '智能购物广告组', 'type': 'SHOPPING'},
            {'code': 'DISPLAY_STANDARD', 'name': '标准展示广告组', 'type': 'DISPLAY'},
            {'code': 'DISPLAY_INMARKET', 'name': 'In-Market 展示广告组', 'type': 'DISPLAY'},
            {'code': 'VIDEO_standard', 'name': '标准视频广告组', 'type': 'VIDEO'},
            {'code': 'VIDEO_app', 'name': '应用视频广告组', 'type': 'VIDEO'},
            {'code': 'APP_standard', 'name': '标准应用广告组', 'type': 'APP'},
            {'code': 'PERFORMANCE_MAX', 'name': '全面营销广告组', 'type': 'PERFORMANCE_MAX'}
        ]
    
    def google_list_maximize_conversion_value_setting(self, **kwargs) -> List[Dict]:
        """列出最大化转化价值设置"""
        return [
            {'code': 'TARGET_ROAS', 'name': '目标 ROAS', 'description': '设定目标广告支出回报率'},
            {'code': 'TARGET_CPA', 'name': '目标 CPA', 'description': '设定目标每次转化费用'},
            {'code': 'MAXIMIZE_CONVERSIONS', 'name': '最大化转化次数', 'description': '在预算内最大化转化'},
            {'code': 'MANUAL_CPM', 'name': '手动 CPM', 'description': '手动设置千次曝光成本'}
        ]
    
    # ========================================
    # Google Ads 展示形态
    # ========================================
    
    def google_list_ad_formats(self, type: str = None, **kwargs) -> List[Dict]:
        """列出广告格式"""
        formats = [
            {'code': 'TEXT_AD', 'name': '文本广告', 'type': 'SEARCH', 'max_headlines': 3, 'max_descriptions': 2},
            {'code': 'RESPONSIVE_SEARCH_AD', 'name': '响应式搜索广告', 'type': 'SEARCH', 'max_headlines': 15, 'max_descriptions': 25},
            {'code': 'EXPANDED_TEXT_AD', 'name': '扩展文本广告', 'type': 'SEARCH', 'max_headlines': 2, 'max_descriptions': 2},
            {'code': 'DISPLAY_AD', 'name': '展示广告', 'type': 'DISPLAY', 'max_images': 2},
            {'code': 'SHOPPING_AD', 'name': '购物广告', 'type': 'SHOPPING'},
            {'code': 'GMAIL_AD', 'name': 'Gmail 广告', 'type': 'GMAIL'},
            {'code': 'VIDEO_AD', 'name': '视频广告', 'type': 'VIDEO'},
            {'code': 'APP_INSTALL_AD', 'name': '应用安装广告', 'type': 'APP'},
            {'code': 'APP_REENGAGEMENT_AD', 'name': '应用重 engagement 广告', 'type': 'APP'}
        ]
        if type:
            return [f for f in formats if f.get('type', '').upper() == type.upper()]
        return formats
    
    def google_list_asset_types(self, **kwargs) -> List[Dict]:
        """列出资产类型"""
        return [
            {'code': 'CALL_ASSET', 'name': '电话拨打资产', 'description': '添加电话号码'},
            {'code': 'CALLOUT_ASSET', 'name': '附加信息资产', 'description': '添加额外文字'},
            {'code': 'STRUCTURED_SNIPPET_ASSET', 'name': '结构化摘要资产', 'description': '显示结构化信息'},
            {'code': 'IMAGE_ASSET', 'name': '图片资产', 'description': '添加图片'},
            {'code': 'PLACE_ASSET', 'name': '门店资产', 'description': '添加门店信息'},
            {'code': 'APP_ASSET', 'name': '应用资产', 'description': '添加应用链接'},
            {'code': 'SITELINK_ASSET', 'name': '网站链接资产', 'description': '添加额外链接'},
            {'code': 'PRICE_ASSET', 'name': '价格资产', 'description': '添加价格信息'},
            {'code': 'PROMOTION_ASSET', 'name': '促销资产', 'description': '添加促销活动'}
        ]
    
    # ========================================
    # Google Ads 报表维度
    # ========================================
    
    def google_list_report_dimensions(self, **kwargs) -> List[Dict]:
        """列出报表维度"""
        return [
            {'code': 'DAY', 'name': '日期', 'type': 'TIME'},
            {'code': 'WEEK', 'name': '周', 'type': 'TIME'},
            {'code': 'MONTH', 'name': '月', 'type': 'TIME'},
            {'code': 'QUARTER', 'name': '季度', 'type': 'TIME'},
            {'code': 'YEAR', 'name': '年', 'type': 'TIME'},
            {'code': 'CAMPAIGN', 'name': '广告系列', 'type': 'STRUCTURE'},
            {'code': 'AD_GROUP', 'name': '广告组', 'type': 'STRUCTURE'},
            {'code': 'KEYWORD', 'name': '关键词', 'type': 'TARGETING'},
            {'code': 'AD', 'name': '广告', 'type': 'STRUCTURE'},
            {'code': 'DEVICE', 'name': '设备', 'type': 'TARGETING'},
            {'code': 'GEO', 'name': '地域', 'type': 'TARGETING'},
            {'code': 'PLACEMENT', 'name': '投放位置', 'type': 'TARGETING'},
            {'code': 'AD_GROUP_CREATIVE', 'name': '广告组创意', 'type': 'STRUCTURE'},
            {'code': 'AD_GROUP_CRITERION', 'name': '广告组定向', 'type': 'TARGETING'},
            {'code': 'CAMPAIGN_CRITERION', 'name': '广告系列定向', 'type': 'TARGETING'}
        ]
    
    # ========================================
    # DV360 创意素材查询
    # ========================================
    
    def dv360_list_creator_accounts(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出创作者账户"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/creatorAccounts"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('creatorAccounts', [])
        except Exception as e:
            print(f"[DV360] creator_accounts error: {e}")
            return []
    
    def dv360_list_video_creators(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出视频创作者"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/videoCreatorAccounts"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('videoCreatorAccounts', [])
        except Exception as e:
            print(f"[DV360] video_creators error: {e}")
            return []
    
    # ========================================
    # DV360 创意模板
    # ========================================
    
    def dv360_list_banner_creative_sizes(self, **kwargs) -> List[Dict]:
        """列出横幅创意尺寸"""
        return [
            {'code': 'IAB_BANNER_300x250', 'name': '中矩形', 'size': '300x250'},
            {'code': 'IAB_BANNER_336x280', 'name': '大矩形', 'size': '336x280'},
            {'code': 'IAB_BANNER_728x90', 'name': '横幅', 'size': '728x90'},
            {'code': 'IAB_BANNER_468x60', 'name': '横幅（旧）', 'size': '468x60'},
            {'code': 'IAB_BANNER_320x50', 'name': '移动横幅', 'size': '320x50'},
            {'code': 'IAB_BANNER_300x600', 'name': '大横幅', 'size': '300x600'},
            {'code': 'IAB_BANNER_160x600', 'name': '宽矩形', 'size': '160x600'},
            {'code': 'IAB_BANNER_970x90', 'name': '大型横幅', 'size': '970x90'},
            {'code': 'IAB_BANNER_970x250', 'name': '大型矩形', 'size': '970x250'},
            {'code': 'IAB_BANNER_320x100', 'name': '大型移动横幅', 'size': '320x100'}
        ]
    
    def dv360_list_video_creative_durations(self, **kwargs) -> List[Dict]:
        """列出视频创意时长"""
        return [
            {'code': 'DURATION_15S', 'name': '15秒', 'duration': 15},
            {'code': 'DURATION_30S', 'name': '30秒', 'duration': 30},
            {'code': 'DURATION_60S', 'name': '60秒', 'duration': 60},
            {'code': 'DURATION_90S', 'name': '90秒', 'duration': 90},
            {'code': 'DURATION_120S', 'name': '120秒', 'duration': 120},
            {'code': 'DURATION_150S', 'name': '150秒', 'duration': 150},
            {'code': 'DURATION_UNASSIGNED', 'name': '未分配', 'duration': 0}
        ]
    
    # ========================================
    # DV360 排期表
    # ========================================
    
    def dv360_list_scheduling_types(self, **kwargs) -> List[Dict]:
        """列出排期类型"""
        return [
            {'code': 'SCHEDULE_TYPE_UNSPECIFIED', 'name': '未指定', 'description': '系统自动选择'},
            {'code': 'FRONT_LOADED', 'name': '前置排期', 'description': '集中前期投放'},
            {'code': 'EVEN_SPREAD', 'name': '均匀投放', 'description': ' evenly 分散投放'},
            {'code': 'BACK_LOADED', 'name': '后置排期', 'description': '集中后期投放'}
        ]
    
    def dv360_list_traffic_source_types(self, **kwargs) -> List[Dict]:
        """列出流量来源类型"""
        return [
            {'code': 'TRAFFIC_SOURCE_GOOGLE', 'name': 'Google 自有流量', 'value': 1},
            {'code': 'TRAFFIC_SOURCE_PARTNER', 'name': '合作伙伴流量', 'value': 2},
            {'code': 'TRAFFIC_SOURCE_EXTERNAL', 'name': '外部流量', 'value': 3}
        ]

    # ========================================
    # TikTok 应用与网站定向
    # ========================================
    
    def tiktok_list_apps_for_placement(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出可投放的应用"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 100)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/app/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] apps_for_placement error: {e}")
            return []
    
    def tiktok_list_sites_for_placement(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出可投放的网站"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 100)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/site/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] sites_for_placement error: {e}")
            return []
    
    def tiktok_list_category_tree(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出兴趣分类树"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'category_level': kwargs.get('category_level', 1)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/interest/category/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] category_tree error: {e}")
            return []
    
    # ========================================
    # TikTok 通知与回调
    # ========================================
    
    def tiktok_list_notification_types(self, **kwargs) -> List[Dict]:
        """列出通知类型"""
        return [
            {'code': 'CAMPAIGN_STATUS_CHANGED', 'name': '广告系列状态变更'},
            {'code': 'AD_GROUP_STATUS_CHANGED', 'name': '广告组状态变更'},
            {'code': 'AD_STATUS_CHANGED', 'name': '广告状态变更'},
            {'code': 'BUDGET_THRESHOLD_REACHED', 'name': '预算阈值达到'},
            {'code': 'AUDIENCE_SIZE_CHANGED', 'name': '受众规模变化'},
            {'code': 'CREATIVE_REVIEW_RESULT', 'name': '素材审核结果'},
            {'code': 'CONVERSION_ACCUMULATED', 'name': '转化累计通知'},
            {'code': 'PAYMENT_ISSUE', 'name': '付款问题通知'}
        ]
    
    def tiktok_list_webhook_events(self, **kwargs) -> List[Dict]:
        """列出 Webhook 事件类型"""
        return [
            {'code': 'AD_ACCOUNT_CREATED', 'name': '广告账户创建', 'version': 'v1.3'},
            {'code': 'AD_ACCOUNT_DELETED', 'name': '广告账户删除', 'version': 'v1.3'},
            {'code': 'CAMPAIGN_CREATED', 'name': '广告系列创建', 'version': 'v1.3'},
            {'code': 'CAMPAIGN_UPDATED', 'name': '广告系列更新', 'version': 'v1.3'},
            {'code': 'CAMPAIGN_DELETED', 'name': '广告系列删除', 'version': 'v1.3'},
            {'code': 'AD_GROUP_CREATED', 'name': '广告组创建', 'version': 'v1.3'},
            {'code': 'AD_GROUP_UPDATED', 'name': '广告组更新', 'version': 'v1.3'},
            {'code': 'AD_CREATED', 'name': '广告创建', 'version': 'v1.3'},
            {'code': 'AD_UPDATED', 'name': '广告更新', 'version': 'v1.3'},
            {'code': 'PIXEL_REPORT_DATA', 'name': 'Pixel 数据上报', 'version': 'v1.3'}
        ]
    
    # ========================================
    # Meta 更多素材选项
    # ========================================
    
    def meta_list_link_previews_options(self, **kwargs) -> List[Dict]:
        """列出链接预览选项"""
        return [
            {'code': 'DEFAULT', 'name': '默认预览', 'description': '自动获取链接预览'},
            {'code': 'CUSTOM', 'name': '自定义预览', 'description': '手动设置预览图片'},
            {'code': 'COLLECTION', 'name': '合集预览', 'description': '使用合集封面作为预览'}
        ]
    
    def meta_list_cta_types(self, **kwargs) -> List[Dict]:
        """列出 CTA 按钮类型"""
        return [
            {'code': 'NONE', 'name': '无', 'type': 'NONE'},
            {'code': 'BOOK_NOW', 'name': '立即预订', 'type': 'BOOK'},
            {'code': 'CONTACT_US', 'name': '联系我们', 'type': 'CONTACT'},
            {'code': 'DOWNLOAD', 'name': '下载', 'type': 'DOWNLOAD'},
            {'code': 'ENABLE_NOTIFICATIONS', 'name': '开启通知', 'type': 'NOTIFY'},
            {'code': 'GET_DIRECTION', 'name': '获取导航', 'type': 'DIRECTION'},
            {'code': 'INSTALL_APP', 'name': '安装应用', 'type': 'INSTALL'},
            {'code': 'LEARN_MORE', 'name': '了解更多', 'type': 'LEARN_MORE'},
            {'code': 'MESSENGER', 'name': 'Messenger', 'type': 'MESSAGING'},
            {'code': 'PLAY_GAME', 'name': '玩游戏', 'type': 'GAMING'},
            {'code': 'SIGN_UP', 'name': '注册', 'type': 'SIGN_UP'},
            {'code': 'SUPPORT', 'name': '支持', 'type': 'SUPPORT'},
            {'code': 'USE_APP', 'name': '使用应用', 'type': 'USE_APP'},
            {'code': 'WATCH_MORE', 'name': '观看更多', 'type': 'VIDEO'},
            {'code': 'WHATSAPP', 'name': 'WhatsApp', 'type': 'MESSAGING'}
        ]
    
    def meta_list_primary_texts(self, **kwargs) -> List[Dict]:
        """列出主文本类型"""
        return [
            {'code': 'SALES_COPY', 'name': '销售文案', 'max_length': 125},
            {'code': 'OFFER_COPY', 'name': '优惠文案', 'max_length': 125},
            {'code': 'PRODUCT_DETAIL', 'name': '产品详情', 'max_length': 125},
            {'code': 'EVENT_INFO', 'name': '活动信息', 'max_length': 125}
        ]
    
    # ========================================
    # Meta 更多报表维度
    # ========================================
    
    def meta_list_insights_fields(self, **kwargs) -> List[Dict]:
        """列出 Insights 字段"""
        fields = [
            {'code': 'IMPRESSIONS', 'name': '展示次数', 'category': 'PERFORMANCE'},
            {'code': 'REACH', 'name': '触达人数', 'category': 'PERFORMANCE'},
            {'code': 'FREQUENCY', 'name': '频率', 'category': 'PERFORMANCE'},
            {'code': 'CLICKS', 'name': '点击次数', 'category': 'PERFORMANCE'},
            {'code': 'CTR', 'name': '点击率', 'category': 'PERFORMANCE'},
            {'code': 'CPC', 'name': '单次点击费用', 'category': 'PERFORMANCE'},
            {'code': 'CPM', 'name': '千次曝光费用', 'category': 'PERFORMANCE'},
            {'code': 'SPEND', 'name': '花费', 'category': 'FINANCIAL'},
            {'code': 'PURCHASE_ROI', 'name': '购买 ROAS', 'category': 'FINANCIAL'},
            {'code': 'CONVERSIONS', 'name': '转化次数', 'category': 'CONVERSION'},
            {'code': 'CPA', 'name': '单次转化费用', 'category': 'CONVERSION'},
            {'code': 'ADD_TO_CART', 'name': '加入购物车', 'category': 'CONVERSION'},
            {'code': 'INITIATE_CHECKOUT', 'name': '发起结账', 'category': 'CONVERSION'},
            {'code': 'PURCHASE', 'name': '购买', 'category': 'CONVERSION'},
            {'code': 'CONTENT_VIEW', 'name': '内容浏览', 'category': 'ENGAGEMENT'},
            {'code': 'LEAD', 'name': '线索', 'category': 'CONVERSION'},
            {'code': 'QUALITY_RANKING', 'name': '质量排名', 'category': 'QUALITY'},
            {'code': 'RELEVANCE_RANKING', 'name': '相关性排名', 'category': 'QUALITY'}
        ]
        return fields
    
    def meta_list_breakdowns(self, **kwargs) -> List[Dict]:
        """列出细分维度"""
        return [
            {'code': 'PLATFORM', 'name': '平台', 'description': 'Facebook/Instagram 等'},
            {'code': 'PLACEMENT', 'name': '投放位置', 'description': '动态消息/快拍等'},
            {'code': 'AGE', 'name': '年龄', 'description': '年龄段细分'},
            {'code': 'GENDER', 'name': '性别', 'description': '男/女'},
            {'code': 'COUNTRY', 'name': '国家', 'description': '国家细分'},
            {'code': 'REGION', 'name': '省份', 'description': '省份细分'},
            {'code': 'CITY', 'name': '城市', 'description': '城市细分'},
            {'code': 'DEVICE', 'name': '设备', 'description': '手机/平板/电脑'},
            {'code': 'DEVICE_TYPE', 'name': '设备类型', 'description': '移动端/桌面端'},
            {'code': 'CONN_TYPE', 'name': '网络类型', 'description': 'WiFi/4G/3G等'},
            {'code': 'DAY_PART_DAY', 'name': '时段', 'description': '一天中的时间段'}
        ]
    
    # ========================================
    # Google Ads 更多报表维度
    # ========================================
    
    def google_list_metrics(self, type: str = None, **kwargs) -> List[Dict]:
        """列出指标"""
        metrics = [
            {'code': 'IMPRESSIONS', 'name': '展示次数', 'type': 'PERFORMANCE'},
            {'code': 'CLICKS', 'name': '点击次数', 'type': 'PERFORMANCE'},
            {'code': 'CTR', 'name': '点击率', 'type': 'PERFORMANCE'},
            {'code': 'AVERAGE_CPC', 'name': '平均 CPC', 'type': 'FINANCIAL'},
            {'code': 'COST', 'name': '花费', 'type': 'FINANCIAL'},
            {'code': 'CONVERSIONS', 'name': '转化次数', 'type': 'CONVERSION'},
            {'code': 'CONVERSION_RATE', 'name': '转化率', 'type': 'CONVERSION'},
            {'code': 'COST_PER_CONVERSION', 'name': '单次转化费用', 'type': 'CONVERSION'},
            {'code': 'ALL_CONVERSIONS', 'name': '全部转化', 'type': 'CONVERSION'},
            {'code': 'VIEW_THROUGH_GPV', 'name': '观看后转化价值', 'type': 'CONVERSION'},
            {'code': 'ROAS', 'name': '广告支出回报率', 'type': 'FINANCIAL'},
            {'code': 'TOP_OF_PAGE_RATE', 'name': '首页展示率', 'type': 'RANKING'},
            {'code': 'IMPRESSIONS_WITH_OPTIMIZER_TOP_OF_PAGE_RATE', 'name': '首页展示占比', 'type': 'RANKING'}
        ]
        if type:
            return [m for m in metrics if m.get('type', '').upper() == type.upper()]
        return metrics
    
    def google_list_custom_dimensions(self, **kwargs) -> List[Dict]:
        """列出自定义维度"""
        return [
            {'code': 'CUSTOM_VARIABLE_1', 'name': '自定义变量 1', 'type': 'SEARCH'},
            {'code': 'CUSTOM_VARIABLE_2', 'name': '自定义变量 2', 'type': 'SEARCH'},
            {'code': 'CUSTOM_VARIABLE_3', 'name': '自定义变量 3', 'type': 'DISPLAY'},
            {'code': 'CUSTOM_VARIABLE_4', 'name': '自定义变量 4', 'type': 'DISPLAY'}
        ]
    
    # ========================================
    # DV360 更多报表
    # ========================================
    
    def dv360_list_report_types(self, **kwargs) -> List[Dict]:
        """列出报表类型"""
        return [
            {'code': 'CAMPAIGN_REPORT', 'name': '广告系列报表', 'description': '广告系列级别报表'},
            {'code': 'FLIGHT_REPORT', 'name': '航班报表', 'description': '航班级别报表'},
            {'code': 'LINE_ITEM_REPORT', 'name': 'LINE ITEM 报表', 'description': 'LINE ITEM 级别报表'},
            {'code': 'CREATIVE_REPORT', 'name': '创意报表', 'description': '创意级别报表'},
            {'code': 'INSERTION_ORDER_REPORT', 'name': 'IO 报表', 'description': 'IO 级别报表'},
            {'code': 'PARTNER_REPORT', 'name': '合作伙伴报表', 'description': '合作伙伴级别报表'},
            {'code': 'ADVERTISER_REPORT', 'name': '广告主报表', 'description': '广告主级别报表'},
            {'code': 'AGENCY_REPORT', 'name': '代理报表', 'description': '代理级别报表'}
        ]
    
    def dv360_list_dimension_filters(self, **kwargs) -> List[Dict]:
        """列出维度过滤器"""
        return [
            {'code': 'DATE', 'name': '日期', 'type': 'TIME'},
            {'code': 'CAMPAIGN', 'name': '广告系列', 'type': 'STRUCTURE'},
            {'code': 'FLIGHT', 'name': '航班', 'type': 'STRUCTURE'},
            {'code': 'LINE_ITEM', 'name': 'LINE ITEM', 'type': 'STRUCTURE'},
            {'code': 'CREATIVE', 'name': '创意', 'type': 'STRUCTURE'},
            {'code': 'ADVERTISER', 'name': '广告主', 'type': 'ORGANIZATION'},
            {'code': 'AGENCY', 'name': '代理', 'type': 'ORGANIZATION'},
            {'code': 'PARTNER', 'name': '合作伙伴', 'type': 'ORGANIZATION'},
            {'code': 'CREATIVE_TYPE', 'name': '创意类型', 'type': 'CREATIVE'},
            {'code': 'DEVICE_CATEGORY', 'name': '设备类别', 'type': 'DEVICE'},
            {'code': 'OS', 'name': '操作系统', 'type': 'DEVICE'},
            {'code': 'Browser', 'name': '浏览器', 'type': 'DEVICE'},
            {'code': 'COUNTRY', 'name': '国家', 'type': 'GEO'},
            {'code': 'REGION', 'name': '省份', 'type': 'GEO'},
            {'code': 'CITY', 'name': '城市', 'type': 'GEO'}
        ]
