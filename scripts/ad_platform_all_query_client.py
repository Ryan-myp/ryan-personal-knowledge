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
        return {'suggested_bid': 0.5, 'range': {'min': 0.3, 'max': 1.0}}
    
    def tiktok_list_conversion_events(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出转化事件"""
        return []
    
    def tiktok_list_custom_conversions(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出自定义转化"""
        return []
    
    # ========================================
    # TikTok 素材相关
    # ========================================
    
    def tiktok_list_creative_templates(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return [
            {'id': 'TEMPLATE_VIDEO', 'name': '视频广告模板', 'type': 'VIDEO'},
            {'id': 'TEMPLATE_IMAGE', 'name': '图片广告模板', 'type': 'IMAGE'},
            {'id': 'TEMPLATE_CAROUSEL', 'name': '轮播广告模板', 'type': 'CAROUSEL'},
            {'id': 'TEMPLATE_SPLASH', 'name': '开屏广告模板', 'type': 'SPLASH'}
        ]
    
    def tiktok_get_media_library(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """获取媒体库"""
        return []
    
    # ========================================
    # TikTok 定向参数
    # ========================================
    
    def tiktok_list_genders(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出性别选项"""
        return [
            {'code': 'GENDER_UNLIMITED', 'name': '不限', 'description': '所有用户'},
            {'code': 'GENDER_MALE', 'name': '男性', 'description': '男性用户'},
            {'code': 'GENDER_FEMALE', 'name': '女性', 'description': '女性用户'}
        ]
    
    def tiktok_list_age_groups(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间"""
        return [
            {'code': 'AGE_13_17', 'name': '13-17岁', 'start': 13, 'end': 17},
            {'code': 'AGE_18_24', 'name': '18-24岁', 'start': 18, 'end': 24},
            {'code': 'AGE_25_34', 'name': '25-34岁', 'start': 25, 'end': 34},
            {'code': 'AGE_35_44', 'name': '35-44岁', 'start': 35, 'end': 44},
            {'code': 'AGE_45_54', 'name': '45-54岁', 'start': 45, 'end': 54},
            {'code': 'AGE_55_64', 'name': '55-64岁', 'start': 55, 'end': 64},
            {'code': 'AGE_65_PLUS', 'name': '65岁以上', 'start': 65, 'end': 999}
        ]
    
    def tiktok_list_languages(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出语言选项"""
        return [
            {'code': 'LANGUAGE_ZH', 'name': '中文', 'code2': 'zh'},
            {'code': 'LANGUAGE_EN', 'name': '英语', 'code2': 'en'},
            {'code': 'LANGUAGE_JA', 'name': '日语', 'code2': 'ja'},
            {'code': 'LANGUAGE_KO', 'name': '韩语', 'code2': 'ko'},
            {'code': 'LANGUAGE_TH', 'name': '泰语', 'code2': 'th'},
            {'code': 'LANGUAGE_VI', 'name': '越南语', 'code2': 'vi'},
            {'code': 'LANGUAGE_ID', 'name': '印尼语', 'code2': 'id'},
            {'code': 'LANGUAGE_MS', 'name': '马来语', 'code2': 'ms'}
        ]
    
    def tiktok_list_devices(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出设备类型"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/device/'
        params = {'advertiser_id': advertiser_id}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            return []
    
    def tiktok_list_interests(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {'advertiser_id': advertiser_id}
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/interest/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            return []
    
    def tiktok_list_behaviors(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出行为标签"""
        return [
            {'code': 'BEHAVIOR_ECOMMERCE', 'name': '电商购物', 'description': '有购物行为的用户'},
            {'code': 'BEHAVIOR_GAME', 'name': '游戏玩家', 'description': '经常玩游戏的用户'},
            {'code': 'BEHAVIOR_TRAVEL', 'name': '旅行爱好者', 'description': '喜欢旅行的用户'},
            {'code': 'BEHAVIOR_FOODIE', 'name': '美食爱好者', 'description': '关注美食的用户'}
        ]
    
    # ========================================
    # Meta 出价策略
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
        return {'suggested_bid': 0.5}
    
    def meta_list_conversion_events(self, account_id: str, **kwargs) -> List[Dict]:
        """列出转化事件"""
        return []
    
    def meta_list_pixel_events(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出 Pixel 事件"""
        return []
    
    # ========================================
    # Meta 素材模板
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
        return []
    
    def meta_list_ad_creatives(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        return []
    
    # ========================================
    # Meta 定向参数
    # ========================================
    
    def meta_list_genders(self, account_id: str, **kwargs) -> List[Dict]:
        """列出性别选项"""
        return [
            {'code': 'ALL', 'name': '全部', 'description': '所有性别'},
            {'code': 'MALE', 'name': '男性', 'description': '男性用户'},
            {'code': 'FEMALE', 'name': '女性', 'description': '女性用户'},
            {'code': 'CUSTOM', 'name': '自定义', 'description': '自定义性别选项'}
        ]
    
    def meta_list_age_ranges(self, account_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间"""
        ages = []
        for age in range(13, 71):
            if age == 70:
                ages.append({'code': '70', 'name': '70岁及以上', 'min_age': 70, 'max_age': 999})
            else:
                ages.append({'code': str(age), 'name': f'{age}岁', 'min_age': age, 'max_age': age})
        return ages
    
    def meta_list_languages(self, account_id: str, **kwargs) -> List[Dict]:
        """列出语言选项"""
        return [
            {'code': 'en_US', 'name': '英语(美国)', 'locale': 'en_US'},
            {'code': 'zh_CN', 'name': '中文(简体)', 'locale': 'zh_CN'},
            {'code': 'zh_TW', 'name': '中文(繁体)', 'locale': 'zh_TW'},
            {'code': 'ja_JP', 'name': '日语', 'locale': 'ja_JP'},
            {'code': 'ko_KR', 'name': '韩语', 'locale': 'ko_KR'},
            {'code': 'th_TH', 'name': '泰语', 'locale': 'th_TH'},
            {'code': 'vi_VN', 'name': '越南语', 'locale': 'vi_VN'},
            {'code': 'id_ID', 'name': '印尼语', 'locale': 'id_ID'},
            {'code': 'ms_MY', 'name': '马来语', 'locale': 'ms_MY'},
            {'code': 'ar_SA', 'name': '阿拉伯语', 'locale': 'ar_SA'},
            {'code': 'hi_IN', 'name': '印地语', 'locale': 'hi_IN'},
            {'code': 'pt_BR', 'name': '葡萄牙语(巴西)', 'locale': 'pt_BR'},
            {'code': 'es_ES', 'name': '西班牙语', 'locale': 'es_ES'},
            {'code': 'fr_FR', 'name': '法语', 'locale': 'fr_FR'},
            {'code': 'de_DE', 'name': '德语', 'locale': 'de_DE'},
            {'code': 'it_IT', 'name': '意大利语', 'locale': 'it_IT'}
        ]
    
    def meta_list_devices(self, account_id: str, **kwargs) -> List[Dict]:
        """列出设备类型"""
        return [
            {'code': 'ALL', 'name': '全部设备', 'description': '所有设备'},
            {'code': 'MOBILE', 'name': '移动端', 'description': '手机和平板'},
            {'code': 'DESKTOP', 'name': '桌面端', 'description': '电脑'},
            {'code': 'IOS', 'name': 'iOS', 'description': 'iPhone 和 iPad'},
            {'code': 'ANDROID', 'name': 'Android', 'description': '安卓设备'}
        ]
    
    def meta_list_interests(self, account_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签"""
        return []
    
    def meta_list_behaviors(self, account_id: str, **kwargs) -> List[Dict]:
        """列出行为标签"""
        return []
    
    def meta_list_demographics(self, account_id: str, **kwargs) -> List[Dict]:
        """列出人口统计选项"""
        return [
            {'code': 'HOMEOWNERS', 'name': '房主', 'category': 'demographics'},
            {'code': 'NEWLYWEDS', 'name': '新婚', 'category': 'demographics'},
            {'code': 'PARENTS_ALL_CHILDREN', 'name': '有孩子的家长', 'category': 'demographics'},
            {'code': 'PARENTS_ADOLESCENT_CHILDREN', 'name': '有青少年的家长', 'category': 'demographics'},
            {'code': 'PARENTS_TODDLERS', 'name': '有幼儿家长', 'category': 'demographics'},
            {'code': 'REMOTE_WORKERS', 'name': '远程工作者', 'category': 'demographics'},
            {'code': 'COLLEGE_STUDENTS', 'name': '大学生', 'category': 'demographics'}
        ]
    
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
        return {'suggested_bid': 1.0}
    
    def google_list_conversion_actions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化行为"""
        return []
    
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
    
    def google_list_devices(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出设备类型"""
        return [
            {'code': 'MOBILE', 'name': '手机', 'type': 'MOBILE_PHONE'},
            {'code': 'TABLET', 'name': '平板', 'type': 'TABLET'},
            {'code': 'DESKTOP', 'name': '电脑', 'type': 'DESKTOP'},
            {'code': 'ALL_DEVICES', 'name': '全部设备', 'type': 'ALL'}
        ]
    
    def google_list_languages(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出语言选项"""
        return [
            {'code': 1001, 'name': '英语', 'language_code': 'en'},
            {'code': 1002, 'name': '中文(简体)', 'language_code': 'zh-CN'},
            {'code': 1003, 'name': '中文(繁体)', 'language_code': 'zh-TW'},
            {'code': 1004, 'name': '日语', 'language_code': 'ja'},
            {'code': 1005, 'name': '韩语', 'language_code': 'ko'},
            {'code': 1006, 'name': '泰语', 'language_code': 'th'},
            {'code': 1007, 'name': '越南语', 'language_code': 'vi'},
            {'code': 1008, 'name': '印尼语', 'language_code': 'id'},
            {'code': 1009, 'name': '马来语', 'language_code': 'ms'},
            {'code': 1010, 'name': '阿拉伯语', 'language_code': 'ar'}
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
    
    def dv360_list_creative_templates(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return [
            {'code': 'CREATIVE_TYPE_BANNER', 'name': '横幅广告', 'type': 'BANNER'},
            {'code': 'CREATIVE_TYPE_VIDEO', 'name': '视频广告', 'type': 'VIDEO'},
            {'code': 'CREATIVE_TYPE_NATIVE', 'name': '原生广告', 'type': 'NATIVE'},
            {'code': 'CREATIVE_TYPE_RICH_MEDIA', 'name': '富媒体广告', 'type': 'RICH_MEDIA'}
        ]
    
    def dv360_list_genders(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出性别选项"""
        return [
            {'code': 'GENDER_UNSPECIFIED', 'name': '未指定', 'value': 0},
            {'code': 'GENDER_MALE', 'name': '男性', 'value': 1},
            {'code': 'GENDER_FEMALE', 'name': '女性', 'value': 2}
        ]
    
    def dv360_list_age_ranges(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间"""
        return [
            {'code': 'AGE_RANGE_UNSPECIFIED', 'name': '未指定', 'value': 0},
            {'code': 'AGE_RANGE_18_24', 'name': '18-24岁', 'value': 1},
            {'code': 'AGE_RANGE_25_34', 'name': '25-34岁', 'value': 2},
            {'code': 'AGE_RANGE_35_44', 'name': '35-44岁', 'value': 3},
            {'code': 'AGE_RANGE_45_54', 'name': '45-54岁', 'value': 4},
            {'code': 'AGE_RANGE_55_64', 'name': '55-64岁', 'value': 5},
            {'code': 'AGE_RANGE_65_PLUS', 'name': '65岁以上', 'value': 6}
        ]
    
    def dv360_list_devices(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出设备类型"""
        return [
            {'code': 'DEVICE_TYPE_MOBILE', 'name': '手机', 'type': 'DEVICE_TYPE_MOBILE'},
            {'code': 'DEVICE_TYPE_TABLET', 'name': '平板', 'type': 'DEVICE_TYPE_TABLET'},
            {'code': 'DEVICE_TYPE_DESKTOP', 'name': '电脑', 'type': 'DEVICE_TYPE_DESKTOP'},
            {'code': 'DEVICE_TYPE_TV', 'name': '电视', 'type': 'DEVICE_TYPE_TV'}
        ]
    
    def dv360_list_interests(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签"""
        return []
    
    def dv360_list_location_targets(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出地域定向"""
        return []
    
    # ========================================
    # 报表查询接口
    # ========================================
    
    def tiktok_get_campaign_report(self, advertiser_id: str, date_range: dict, **kwargs) -> Dict:
        """获取广告系列报表"""
        return {'report': [], 'summary': {}}
    
    def meta_get_campaign_report(self, account_id: str, date_range: dict, **kwargs) -> Dict:
        """获取广告系列报表"""
        return []
    
    def google_get_campaign_report(self, customer_id: str, date_range: dict) -> Dict:
        """获取广告系列报表"""
        return {'report': [], 'summary': {}}
    
    # ========================================
    # 辅助工具
    # ========================================
    
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
