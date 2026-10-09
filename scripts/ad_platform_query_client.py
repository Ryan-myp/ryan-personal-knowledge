# -*- coding: utf-8 -*-
"""
广告平台定向参数查询接口
补充创建广告时需要的完整定向参数：设备、性别、年龄、语言、兴趣、行为等
"""

import re
import requests
from typing import List, Dict, Optional


_GOOGLE_ID = re.compile(r"[0-9]+\Z")
_INTEGER = re.compile(r"[+-]?[0-9]+\Z")


def _google_numeric_id(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if (
        not _GOOGLE_ID.fullmatch(normalized)
        or len(normalized) > 20
        or int(normalized) < 1
    ):
        raise ValueError(f"{field_name} must be a positive numeric identifier")
    return normalized


def _google_query_limit(value, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not _INTEGER.fullmatch(str(value).strip()):
        raise ValueError("limit must be an integer")
    limit = int(value)
    if limit < 1:
        raise ValueError("limit must be a positive integer")
    return min(limit, 1000)


class AdPlatformQueryClient:
    """广告平台定向参数查询客户端"""
    
    def __init__(self, credentials: dict, *, google_ads_client=None):
        self.credentials = credentials
        self._google_ads_client = google_ads_client

    def get_client(self, platform: str):
        if platform != 'google_ads':
            raise ValueError(f"Unsupported SDK client: {platform}")
        if self._google_ads_client is None:
            self._google_ads_client = self._create_google_ads_client()
        return self._google_ads_client

    def _create_google_ads_client(self):
        credentials = self.credentials.get('google', {})
        required = ('client_id', 'client_secret', 'developer_token', 'refresh_token')
        if not all(credentials.get(key) for key in required):
            raise ValueError("Google Ads OAuth credentials and developer token are required")
        try:
            from google.ads.googleads.client import GoogleAdsClient
            from google.oauth2.credentials import Credentials
        except ImportError as error:
            raise RuntimeError("Google Ads SDK is required for Google targeting queries") from error

        oauth_credentials = Credentials(
            token=None,
            refresh_token=credentials['refresh_token'],
            client_id=credentials['client_id'],
            client_secret=credentials['client_secret'],
            token_uri="https://oauth2.googleapis.com/token",
        )
        return GoogleAdsClient(
            credentials=oauth_credentials,
            developer_token=credentials['developer_token'],
            login_customer_id=credentials.get('login_customer_id', ''),
            use_proto_plus=True,
        )

    @staticmethod
    def _request_json(url, *, headers=None, params=None):
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Provider response must be a JSON object")
        return payload

    @staticmethod
    def _list_field(payload, field_name):
        values = payload.get(field_name, [])
        if not isinstance(values, list):
            raise ValueError(f"Provider response field '{field_name}' must be a list")
        return values

    @classmethod
    def _tiktok_list(cls, payload):
        code = payload.get('code')
        if code not in (None, 0, '0'):
            raise RuntimeError(f"TikTok query failed with provider code {code}")
        data = payload.get('data', {})
        if not isinstance(data, dict):
            raise ValueError("TikTok response field 'data' must be an object")
        return cls._list_field(data, 'list')
    
    # ========== TikTok 定向参数查询接口 ==========
    
    def tiktok_list_devices(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出设备类型 - 用于设备定向"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 100)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/device/'
        return self._tiktok_list(self._request_json(url, headers=headers, params=params))
    
    def tiktok_list_genders(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出性别选项 - 用于性别定向"""
        # TikTok 性别是固定枚举值
        return [
            {'code': 'GENDER_UNLIMITED', 'name': '不限', 'description': '所有用户'},
            {'code': 'GENDER_MALE', 'name': '男性', 'description': '男性用户'},
            {'code': 'GENDER_FEMALE', 'name': '女性', 'description': '女性用户'}
        ]
    
    def tiktok_list_age_groups(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间 - 用于年龄定向"""
        # TikTok 年龄是固定枚举值
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
        """列出语言选项 - 用于语言定向"""
        # TikTok 语言是固定枚举值
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
    
    def tiktok_list_interests(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签 - 用于兴趣定向"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/interest/'
        return self._tiktok_list(self._request_json(url, headers=headers, params=params))
    
    def tiktok_list_behaviors(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出行为标签 - 用于行为定向"""
        # 行为标签也是固定枚举值
        return [
            {'code': 'BEHAVIOR_ECOMMERCE', 'name': '电商购物', 'description': '有购物行为的用户'},
            {'code': 'BEHAVIOR_GAME', 'name': '游戏玩家', 'description': '经常玩游戏的用户'},
            {'code': 'BEHAVIOR_TRAVEL', 'name': '旅行爱好者', 'description': '喜欢旅行的用户'},
            {'code': 'BEHAVIOR_FOODIE', 'name': '美食爱好者', 'description': '关注美食的用户'}
        ]
    
    def tiktok_list_interest_categories(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出兴趣分类 - 获取完整的兴趣分类树"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'category_level': kwargs.get('category_level', 1)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/interest/category/'
        return self._tiktok_list(self._request_json(url, headers=headers, params=params))
    
    def tiktok_get_app_list(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出可投放的 APP - 用于应用定向"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 100)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/app/'
        return self._tiktok_list(self._request_json(url, headers=headers, params=params))
    
    def tiktok_get_website_list(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出可投放的网站 - 用于网站定向"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 100)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/site/'
        return self._tiktok_list(self._request_json(url, headers=headers, params=params))
    
    # ========== Meta 定向参数查询接口 ==========
    
    def meta_list_devices(self, account_id: str, **kwargs) -> List[Dict]:
        """列出设备类型 - 用于设备定向"""
        # Meta 设备类型是固定枚举值
        return [
            {'code': 'ALL', 'name': '全部设备', 'description': '所有设备'},
            {'code': 'MOBILE', 'name': '移动端', 'description': '手机和平板'},
            {'code': 'DESKTOP', 'name': '桌面端', 'description': '电脑'},
            {'code': 'IOS', 'name': 'iOS', 'description': 'iPhone 和 iPad'},
            {'code': 'ANDROID', 'name': 'Android', 'description': '安卓设备'}
        ]
    
    def meta_list_genders(self, account_id: str, **kwargs) -> List[Dict]:
        """列出性别选项 - 用于性别定向"""
        return [
            {'code': 'ALL', 'name': '全部', 'description': '所有性别'},
            {'code': 'MALE', 'name': '男性', 'description': '男性用户'},
            {'code': 'FEMALE', 'name': '女性', 'description': '女性用户'},
            {'code': 'CUSTOM', 'name': '自定义', 'description': '自定义性别选项'}
        ]
    
    def meta_list_age_ranges(self, account_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间 - 用于年龄定向"""
        return [
            {
                'code': str(age),
                'name': f'{age}岁' if age < 70 else '70岁及以上',
                'min_age': age,
                'max_age': age if age < 70 else 999,
            }
            for age in range(13, 71)
        ]
    
    def meta_list_languages(self, account_id: str, **kwargs) -> List[Dict]:
        """列出语言选项 - 用于语言定向"""
        # Meta 语言是固定枚举值
        return [
            {'code': '1', 'name': '所有语言', 'description': '所有语言用户'},
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
    
    def meta_list_interests(self, account_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签 - 用于兴趣定向"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/interests"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'limit': kwargs.get('limit', 100)}
        payload = self._request_json(url, headers=headers, params=params)
        return self._list_field(payload, 'data')
    
    def meta_list_behaviors(self, account_id: str, **kwargs) -> List[Dict]:
        """列出行为标签 - 用于行为定向"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/behaviors"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'limit': kwargs.get('limit', 100)}
        payload = self._request_json(url, headers=headers, params=params)
        return self._list_field(payload, 'data')
    
    def meta_list_demographics(self, account_id: str, **kwargs) -> List[Dict]:
        """列出人口统计选项 - 用于精细定向"""
        # Meta 人口统计数据是固定枚举
        return [
            {'code': 'HOMEOWNERS', 'name': '房主', 'category': 'demographics'},
            {'code': 'NEWLYWEDS', 'name': '新婚', 'category': 'demographics'},
            {'code': 'PARENTS_ALL_CHILDREN', 'name': '有孩子的家长', 'category': 'demographics'},
            {'code': 'PARENTS_ADOLESCENT_CHILDREN', 'name': '有青少年的家长', 'category': 'demographics'},
            {'code': 'PARENTS_TODDLERS', 'name': '有幼儿家长', 'category': 'demographics'},
            {'code': 'REMOTE_WORKERS', 'name': '远程工作者', 'category': 'demographics'},
            {'code': 'COLLEGE_STUDENTS', 'name': '大学生', 'category': 'demographics'}
        ]
    
    # ========== Google Ads 定向参数查询接口 ==========
    
    def google_list_devices(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出设备类型 - 用于设备定向"""
        # Google Ads 设备是固定枚举值
        return [
            {'code': 'MOBILE', 'name': '手机', 'type': 'MOBILE_PHONE', 'description': '手机设备'},
            {'code': 'TABLET', 'name': '平板', 'type': 'TABLET', 'description': '平板设备'},
            {'code': 'DESKTOP', 'name': '电脑', 'type': 'DESKTOP', 'description': '桌面电脑'},
            {'code': 'ALL_DEVICES', 'name': '全部设备', 'type': 'ALL', 'description': '所有设备'}
        ]
    
    def google_list_locations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 用于地域定向"""
        customer_id = _google_numeric_id(customer_id, "customer_id")
        limit = _google_query_limit(kwargs.get('limit'), default=200)
        client = self.get_client('google_ads')
        google_ads_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT geo_target_constant.id, geo_target_constant.name, "
            "geo_target_constant.target_type FROM geo_target_constant "
            "WHERE geo_target_constant.status = ENABLED "
            f"LIMIT {limit}"
        )
        response = google_ads_service.search_stream(
            customer_id=customer_id, query=query
        )
        return [
            {
                'id': row.geo_target_constant.id,
                'name': row.geo_target_constant.name,
                'type': row.geo_target_constant.target_type,
            }
            for batch in response
            for row in batch.results
        ]
    
    def google_list_languages(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出语言选项 - 用于语言定向"""
        # Google Ads 语言是固定枚举值
        return [
            {'code': 1000, 'name': '所有语言', 'language_code': 'all'},
            {'code': 1001, 'name': '英语', 'language_code': 'en'},
            {'code': 1002, 'name': '中文(简体)', 'language_code': 'zh-CN'},
            {'code': 1003, 'name': '中文(繁体)', 'language_code': 'zh-TW'},
            {'code': 1004, 'name': '日语', 'language_code': 'ja'},
            {'code': 1005, 'name': '韩语', 'language_code': 'ko'},
            {'code': 1006, 'name': '泰语', 'language_code': 'th'},
            {'code': 1007, 'name': '越南语', 'language_code': 'vi'},
            {'code': 1008, 'name': '印尼语', 'language_code': 'id'},
            {'code': 1009, 'name': '马来语', 'language_code': 'ms'},
            {'code': 1010, 'name': '阿拉伯语', 'language_code': 'ar'},
            {'code': 1011, 'name': '印地语', 'language_code': 'hi'},
            {'code': 1012, 'name': '葡萄牙语', 'language_code': 'pt'},
            {'code': 1013, 'name': '西班牙语', 'language_code': 'es'},
            {'code': 1014, 'name': '法语', 'language_code': 'fr'},
            {'code': 1015, 'name': '德语', 'language_code': 'de'}
        ]
    
    def google_list_audiences(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 用于受众定向"""
        customer_id = _google_numeric_id(customer_id, "customer_id")
        limit = _google_query_limit(kwargs.get('limit'), default=100)
        client = self.get_client('google_ads')
        google_ads_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT user_list.id, user_list.name, user_list.type "
            "FROM user_list "
            f"LIMIT {limit}"
        )
        response = google_ads_service.search_stream(
            customer_id=customer_id, query=query
        )
        return [
            {
                'id': row.user_list.id,
                'name': row.user_list.name,
                'type': row.user_list.type,
            }
            for batch in response
            for row in batch.results
        ]
    
    # ========== DV360 定向参数查询接口 ==========
    
    def dv360_list_devices(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出设备类型 - 用于设备定向"""
        # DV360 设备是固定枚举值
        return [
            {'code': 'DEVICE_TYPE_MOBILE', 'name': '手机', 'type': 'DEVICE_TYPE_MOBILE'},
            {'code': 'DEVICE_TYPE_TABLET', 'name': '平板', 'type': 'DEVICE_TYPE_TABLET'},
            {'code': 'DEVICE_TYPE_DESKTOP', 'name': '电脑', 'type': 'DEVICE_TYPE_DESKTOP'},
            {'code': 'DEVICE_TYPE_TV', 'name': '电视', 'type': 'DEVICE_TYPE_TV'}
        ]
    
    def dv360_list_genders(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出性别选项 - 用于性别定向"""
        return [
            {'code': 'GENDER_UNSPECIFIED', 'name': '未指定', 'value': 0},
            {'code': 'GENDER_MALE', 'name': '男性', 'value': 1},
            {'code': 'GENDER_FEMALE', 'name': '女性', 'value': 2}
        ]
    
    def dv360_list_age_ranges(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出年龄区间 - 用于年龄定向"""
        return [
            {'code': 'AGE_RANGE_UNSPECIFIED', 'name': '未指定', 'value': 0},
            {'code': 'AGE_RANGE_18_24', 'name': '18-24岁', 'value': 1},
            {'code': 'AGE_RANGE_25_34', 'name': '25-34岁', 'value': 2},
            {'code': 'AGE_RANGE_35_44', 'name': '35-44岁', 'value': 3},
            {'code': 'AGE_RANGE_45_54', 'name': '45-54岁', 'value': 4},
            {'code': 'AGE_RANGE_55_64', 'name': '55-64岁', 'value': 5},
            {'code': 'AGE_RANGE_65_PLUS', 'name': '65岁以上', 'value': 6}
        ]
    
    def dv360_list_interests(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签 - 用于兴趣定向"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/interestTargets"
        params = {'pageSize': kwargs.get('page_size', 100)}
        payload = self._request_json(url, headers=headers, params=params)
        return self._list_field(payload, 'interestTargets')
    
    def dv360_list_location_targets(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出地域定向 - 用于地域定向"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/locationTargets"
        params = {'pageSize': kwargs.get('page_size', 100)}
        payload = self._request_json(url, headers=headers, params=params)
        return self._list_field(payload, 'locationTargets')
