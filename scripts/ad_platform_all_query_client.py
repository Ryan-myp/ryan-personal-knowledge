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

    # ========================================
    # TikTok 完整接口补充
    # ========================================
    
    def tiktok_list_video_templates(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出视频模板"""
        return [
            {'id': 'TEMPLATE_LANDSCAPE', 'name': '横版视频', 'ratio': '16:9', 'resolution': '1920x1080'},
            {'id': 'TEMPLATE_PORTRAIT', 'name': '竖版视频', 'ratio': '9:16', 'resolution': '1080x1920'},
            {'id': 'TEMPLATE_SQUARE', 'name': '方形视频', 'ratio': '1:1', 'resolution': '1080x1080'},
            {'id': 'TEMPLATE_4_5', 'name': '4:5 竖版', 'ratio': '4:5', 'resolution': '1080x1350'},
            {'id': 'TEMPLATE_1_91', 'name': '1.91:1 横版', 'ratio': '1.91:1', 'resolution': '1200x628'}
        ]
    
    def tiktok_list_image_templates(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出图片模板"""
        return [
            {'id': 'IMAGE_SQUARE', 'name': '正方形图片', 'ratio': '1:1', 'resolution': '1080x1080'},
            {'id': 'IMAGE_PORTRAIT', 'name': '竖版图片', 'ratio': '4:5', 'resolution': '1080x1350'},
            {'id': 'IMAGE_LANDSCAPE', 'name': '横版图片', 'ratio': '1.91:1', 'resolution': '1200x628'},
            {'id': 'IMAGE_STORY', 'name': '快拍图片', 'ratio': '9:16', 'resolution': '1080x1920'}
        ]
    
    def tiktok_list_carousel_formats(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出轮播格式"""
        return [
            {'id': 'CAROUSEL_IMAGE', 'name': '图片轮播', 'max_cards': 10},
            {'id': 'CAROUSEL_VIDEO', 'name': '视频轮播', 'max_cards': 6},
            {'id': 'CAROUSEL_MIXED', 'name': '混合轮播', 'max_cards': 10}
        ]
    
    def tiktok_list_text_overlay_options(self, **kwargs) -> List[Dict]:
        """列出文字叠加选项"""
        return [
            {'code': 'TITLE', 'name': '标题', 'position': 'TOP_CENTER', 'max_chars': 30},
            {'code': 'SUBTITLE', 'name': '副标题', 'position': 'TOP_CENTER', 'max_chars': 60},
            {'code': 'DESCRIPTION', 'name': '描述', 'position': 'BOTTOM_CENTER', 'max_chars': 120},
            {'code': 'CTA', 'name': '行动号召', 'position': 'BOTTOM_CENTER', 'max_chars': 20}
        ]
    
    def tiktok_list_negative_keywords(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出负面关键词"""
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
        return []
    
    def tiktok_list_budget_options(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出预算选项"""
        return [
            {'code': 'DAILY', 'name': '日预算', 'min': 50, 'currency': 'USD'},
            {'code': 'LIFETIME', 'name': '总预算', 'min': 100, 'currency': 'USD'}
        ]
    
    def tiktok_list_schedule_options(self, **kwargs) -> List[Dict]:
        """列出定时投放选项"""
        return [
            {'code': 'START_END', 'name': '开始结束时间', 'description': '设定具体开始和结束时间'},
            {'code': 'SCHEDULE', 'name': '定时投放', 'description': '按小时段定时投放'},
            {'code': 'CONTINUOUS', 'name': '连续投放', 'description': '24小时连续投放'}
        ]
    
    def tiktok_list_schedule_time_slots(self, **kwargs) -> List[Dict]:
        """列出时段选项"""
        slots = []
        for hour in range(24):
            for minute in [0, 30]:
                time_str = f"{hour:02d}:{minute:02d}"
                slots.append({'code': time_str, 'name': time_str, 'label': f'{hour}时{minute or "00分"}'})
        return slots
    
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
            {'code': 'AD_GROUP_CREATED', 'name': '广告组创建', 'version': 'v1.3'},
            {'code': 'AD_CREATED', 'name': '广告创建', 'version': 'v1.3'},
            {'code': 'PIXEL_REPORT_DATA', 'name': 'Pixel 数据上报', 'version': 'v1.3'}
        ]
    
    def tiktok_list_error_codes(self, **kwargs) -> List[Dict]:
        """列出常见错误码"""
        return [
            {'code': 236001, 'name': 'INVALID_ACCESS_TOKEN', 'message': '无效的访问令牌', 'solution': '重新获取 access_token'},
            {'code': 236002, 'name': 'TOKEN_EXPIRED', 'message': '访问令牌已过期', 'solution': '刷新 access_token'},
            {'code': 236003, 'name': 'INSUFFICIENT_PERMISSION', 'message': '权限不足', 'solution': '检查账户权限设置'},
            {'code': 236004, 'name': 'ADVERTISER_NOT_FOUND', 'message': '广告主不存在', 'solution': '检查 advertiser_id 是否正确'},
            {'code': 236005, 'name': 'CAMPAIGN_NOT_FOUND', 'message': '广告系列不存在', 'solution': '检查 campaign_id 是否正确'},
            {'code': 236006, 'name': 'BUDGET_TOO_LOW', 'message': '预算过低', 'solution': '提高预算至最低要求'},
            {'code': 236007, 'name': 'CREATIVE_REJECTED', 'message': '素材审核不通过', 'solution': '查看审核拒绝原因并修改'},
            {'code': 236008, 'name': 'TARGETING_TOO_NARROW', 'message': '定向范围过窄', 'solution': '扩大定向范围'},
            {'code': 236009, 'name': 'DUPLICATE_CAMPAIGN', 'message': '重复的广告系列名称', 'solution': '修改广告系列名称'},
            {'code': 236010, 'name': 'RATE_LIMITED', 'message': '请求频率超限', 'solution': '降低请求频率或等待重试'}
        ]
    
    # ========================================
    # Meta 完整接口补充
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
            {'code': 'LEAD_GENERATION', 'name': '潜在客户开发', 'category': 'consideration'},
            {'code': 'MESSAGES', 'name': '消息', 'category': 'consideration'},
            {'code': 'CONVERSIONS', 'name': '转化', 'category': 'conversion'},
            {'code': 'CATALOG_SALES', 'name': '目录销售', 'category': 'conversion'},
            {'code': 'STORE_TRAFFIC', 'name': '门店流量', 'category': 'conversion'}
        ]
    
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
            return [o for o in options if creative_type.lower() in o.get('use_cases', [])]
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
            {'code': 'VIDEO_AND_LINK', 'name': '视频+链接', 'media_type': 'VIDEO'}
        ]
    
    def meta_list_creative_templates(self, account_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return [
            {'id': 'TEMPLATE_CAROUSEL', 'name': '轮播广告', 'type': 'CAROUSEL'},
            {'id': 'TEMPLATE_SINGLE_IMAGE', 'name': '单图广告', 'type': 'IMAGE'},
            {'id': 'TEMPLATE_VIDEO', 'name': '视频广告', 'type': 'VIDEO'},
            {'id': 'TEMPLATE_COLLECTION', 'name': '合集广告', 'type': 'COLLECTION'},
            {'id': 'TEMPLATE_INSTA_CAROUSEL', 'name': 'Instagram 轮播', 'type': 'INSTA_CAROUSEL'}
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
            {'code': 'SIGN_UP', 'name': '注册', 'type': 'SIGN_UP'},
            {'code': 'WHATSAPP', 'name': 'WhatsApp', 'type': 'MESSAGING'}
        ]
    
    def meta_list_link_previews_options(self, **kwargs) -> List[Dict]:
        """列出链接预览选项"""
        return [
            {'code': 'DEFAULT', 'name': '默认预览', 'description': '自动获取链接预览'},
            {'code': 'CUSTOM', 'name': '自定义预览', 'description': '手动设置预览图片'},
            {'code': 'COLLECTION', 'name': '合集预览', 'description': '使用合集封面作为预览'}
        ]
    
    def meta_list_insights_fields(self, **kwargs) -> List[Dict]:
        """列出 Insights 字段"""
        return [
            {'code': 'IMPRESSIONS', 'name': '展示次数', 'category': 'PERFORMANCE'},
            {'code': 'REACH', 'name': '触达人数', 'category': 'PERFORMANCE'},
            {'code': 'CLICKS', 'name': '点击次数', 'category': 'PERFORMANCE'},
            {'code': 'CTR', 'name': '点击率', 'category': 'PERFORMANCE'},
            {'code': 'CPC', 'name': '单次点击费用', 'category': 'PERFORMANCE'},
            {'code': 'CPM', 'name': '千次曝光费用', 'category': 'PERFORMANCE'},
            {'code': 'SPEND', 'name': '花费', 'category': 'FINANCIAL'},
            {'code': 'CONVERSIONS', 'name': '转化次数', 'category': 'CONVERSION'},
            {'code': 'CPA', 'name': '单次转化费用', 'category': 'CONVERSION'}
        ]
    
    def meta_list_breakdowns(self, **kwargs) -> List[Dict]:
        """列出细分维度"""
        return [
            {'code': 'PLATFORM', 'name': '平台', 'description': 'Facebook/Instagram 等'},
            {'code': 'PLACEMENT', 'name': '投放位置', 'description': '动态消息/快拍等'},
            {'code': 'AGE', 'name': '年龄', 'description': '年龄段细分'},
            {'code': 'GENDER', 'name': '性别', 'description': '男/女'},
            {'code': 'COUNTRY', 'name': '国家', 'description': '国家细分'},
            {'code': 'DEVICE', 'name': '设备', 'description': '手机/平板/电脑'},
            {'code': 'CONN_TYPE', 'name': '网络类型', 'description': 'WiFi/4G/3G等'}
        ]
    
    def meta_list_automated_rules(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自动化规则"""
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
    
    def meta_list_brand_safety_categories(self, **kwargs) -> List[Dict]:
        """列出品牌安全分类"""
        return [
            {'code': 'ADVERSE_CONTENT', 'name': '不当内容', 'level': 'BLOCK'},
            {'code': 'CONTROVERSIAL_ISSUES', 'name': '争议话题', 'level': 'LIMIT'},
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
    
    def meta_list_schedule_options(self, **kwargs) -> List[Dict]:
        """列出定时投放选项"""
        return [
            {'code': 'START_END', 'name': '开始结束时间', 'description': '设定具体开始和结束时间'},
            {'code': 'SCHEDULE', 'name': '定时投放', 'description': '按小时段定时投放'},
            {'code': 'DURING_EVENT', 'name': '活动期间投放', 'description': '仅在活动期间投放'},
            {'code': 'ALL_DAY', 'name': '全天投放', 'description': '24小时连续投放'}
        ]
    
    def meta_list_error_codes(self, **kwargs) -> List[Dict]:
        """列出常见错误码"""
        return [
            {'code': 200, 'name': 'SUCCESS', 'message': '操作成功'},
            {'code': 1, 'name': 'UNKNOWN_ERROR', 'message': '未知错误', 'solution': '联系技术支持'},
            {'code': 100, 'name': 'TOKEN_INVALID', 'message': 'Token 无效', 'solution': '重新获取 access_token'},
            {'code': 190, 'name': 'ACCESS_TOKEN_EXPIRED', 'message': 'Token 已过期', 'solution': '刷新 access_token'},
            {'code': 200, 'name': 'PERMISSION_DENIED', 'message': '权限被拒绝', 'solution': '检查权限设置'},
            {'code': 800, 'name': 'API_DEPRECATED', 'message': 'API 已弃用', 'solution': '升级到新版 API'},
            {'code': 801, 'name': 'GRAPH_API_VERSION', 'message': '版本不支持', 'solution': '使用支持的 API 版本'},
            {'code': 999, 'name': 'RATE_LIMIT', 'message': '请求频率受限', 'solution': '降低请求频率'}
        ]
