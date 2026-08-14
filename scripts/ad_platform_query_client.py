# -*- coding: utf-8 -*-
"""
广告平台定向参数查询接口
补充创建广告时需要的完整定向参数：设备、性别、年龄、语言、兴趣、行为等
"""

import requests
from typing import List, Dict, Optional


class AdPlatformQueryClient:
    """广告平台定向参数查询客户端"""
    
    def __init__(self, credentials: dict):
        self.credentials = credentials
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_devices error: {e}")
            return []
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_interests error: {e}")
            return []
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_interest_categories error: {e}")
            return []
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] get_app_list error: {e}")
            return []
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] get_website_list error: {e}")
            return []
    
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
            {'code': '13', 'name': '13岁', 'min_age': 13, 'max_age': 13},
            {'code': '14', 'name': '14岁', 'min_age': 14, 'max_age': 14},
            {'code': '15', 'name': '15岁', 'min_age': 15, 'max_age': 15},
            {'code': '16', 'name': '16岁', 'min_age': 16, 'max_age': 16},
            {'code': '17', 'name': '17岁', 'min_age': 17, 'max_age': 17},
            {'code': '18', 'name': '18岁', 'min_age': 18, 'max_age': 18},
            {'code': '19', 'name': '19岁', 'min_age': 19, 'max_age': 19},
            {'code': '20', 'name': '20岁', 'min_age': 20, 'max_age': 20},
            {'code': '21', 'name': '21岁', 'min_age': 21, 'max_age': 21},
            {'code': '22', 'name': '22岁', 'min_age': 22, 'max_age': 22},
            {'code': '23', 'name': '23岁', 'min_age': 23, 'max_age': 23},
            {'code': '24', 'name': '24岁', 'min_age': 24, 'max_age': 24},
            {'code': '25', 'name': '25岁', 'min_age': 25, 'max_age': 25},
            {'code': '26', 'name': '26岁', 'min_age': 26, 'max_age': 26},
            {'code': '27', 'name': '27岁', 'min_age': 27, 'max_age': 27},
            {'code': '28', 'name': '28岁', 'min_age': 28, 'max_age': 28},
            {'code': '29', 'name': '29岁', 'min_age': 29, 'max_age': 29},
            {'code': '30', 'name': '30岁', 'min_age': 30, 'max_age': 30},
            {'code': '31', 'name': '31岁', 'min_age': 31, 'max_age': 31},
            {'code': '32', 'name': '32岁', 'min_age': 32, 'max_age': 32},
            {'code': '33', 'name': '33岁', 'min_age': 33, 'max_age': 33},
            {'code': '34', 'name': '34岁', 'min_age': 34, 'max_age': 34},
            {'code': '35', 'name': '35岁', 'min_age': 35, 'max_age': 35},
            {'code': '36', 'name': '36岁', 'min_age': 36, 'max_age': 36},
            {'code': '37', 'name': '37岁', 'min_age': 37, 'max_age': 37},
            {'code': '38', 'name': '38岁', 'min_age': 38, 'max_age': 38},
            {'code': '39', 'name': '39岁', 'min_age': 39, 'max_age': 39},
            {'code': '40', 'name': '40岁', 'min_age': 40, 'max_age': 40},
            {'code': '41', 'name': '41岁', 'min_age': 41, 'max_age': 41},
            {'code': '42', 'name': '42岁', 'min_age': 42, 'max_age': 42},
            {'code': '43', 'name': '43岁', 'min_age': 43, 'max_age': 43},
            {'code': '44', 'name': '44岁', 'min_age': 44, 'max_age': 44},
            {'code': '45', 'name': '45岁', 'min_age': 45, 'max_age': 45},
            {'code': '46', 'name': '46岁', 'min_age': 46, 'max_age': 46},
            {'code': '47', 'name': '47岁', 'min_age': 47, 'max_age': 47},
            {'code': '48', 'name': '48岁', 'min_age': 48, 'max_age': 48},
            {'code': '49', 'name': '49岁', 'min_age': 49, 'max_age': 49},
            {'code': '50', 'name': '50岁', 'min_age': 50, 'max_age': 50},
            {'code': '51', 'name': '51岁', 'min_age': 51, 'max_age': 51},
            {'code': '52', 'name': '52岁', 'min_age': 52, 'max_age': 52},
            {'code': '53', 'name': '53岁', 'min_age': 53, 'max_age': 53},
            {'code': '54', 'name': '54岁', 'min_age': 54, 'max_age': 54},
            {'code': '55', 'name': '55岁', 'min_age': 55, 'max_age': 55},
            {'code': '56', 'name': '56岁', 'min_age': 56, 'max_age': 56},
            {'code': '57', 'name': '57岁', 'min_age': 57, 'max_age': 57},
            {'code': '58', 'name': '58岁', 'min_age': 58, 'max_age': 58},
            {'code': '59', 'name': '59岁', 'min_age': 59, 'max_age': 59},
            {'code': '60', 'name': '60岁', 'min_age': 60, 'max_age': 60},
            {'code': '61', 'name': '61岁', 'min_age': 61, 'max_age': 61},
            {'code': '62', 'name': '62岁', 'min_age': 62, 'max_age': 62},
            {'code': '63', 'name': '63岁', 'min_age': 63, 'max_age': 63},
            {'code': '64', 'name': '64岁', 'min_age': 64, 'max_age': 64},
            {'code': '65', 'name': '65岁', 'min_age': 65, 'max_age': 65},
            {'code': '66', 'name': '66岁', 'min_age': 66, 'max_age': 66},
            {'code': '67', 'name': '67岁', 'min_age': 67, 'max_age': 67},
            {'code': '68', 'name': '68岁', 'min_age': 68, 'max_age': 68},
            {'code': '69', 'name': '69岁', 'min_age': 69, 'max_age': 69},
            {'code': '70', 'name': '70岁及以上', 'min_age': 70, 'max_age': 999}
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
        params = {'access_token': token, 'limit': kwargs.get('limit', 100)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] list_interests error: {e}")
            return []
    
    def meta_list_behaviors(self, account_id: str, **kwargs) -> List[Dict]:
        """列出行为标签 - 用于行为定向"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/behaviors"
        params = {'access_token': token, 'limit': kwargs.get('limit', 100)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] list_behaviors error: {e}")
            return []
    
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
        client = self.get_client('google_ads')
        location_service = client.get_service("LocationCriterionService")
        query = f"SELECT criterion.id, criterion.name, criterion.type FROM criterion WHERE criterion.type = 'LOCATION' LIMIT {kwargs.get('limit', 200)}"
        try:
            response = location_service.search_stream(customer_id=customer_id, query=query)
            locations = []
            for batch in response:
                for row in batch.results:
                    locations.append({
                        'id': row.criterion.id,
                        'name': row.criterion.name,
                        'type': row.criterion.type,
                        'targeting_type': 'Location'
                    })
            return locations
        except Exception as e:
            print(f"[Google Ads] list_locations error: {e}")
            return []
    
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
        client = self.get_client('google_ads')
        query = f"SELECT keyword.id, keyword.text, keyword.match_type FROM keyword LIMIT {kwargs.get('limit', 100)}"
        # 这里需要使用正确的 Google Ads API 服务
        print("[Google Ads] list_audiences 需要使用 google-ads 库")
        return []
    
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
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('interestTargets', [])
        except Exception as e:
            print(f"[DV360] list_interests error: {e}")
            return []
    
    def dv360_list_location_targets(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出地域定向 - 用于地域定向"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/locationTargets"
        params = {'pageSize': kwargs.get('page_size', 100)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('locationTargets', [])
        except Exception as e:
            print(f"[DV360] list_location_targets error: {e}")
            return []
