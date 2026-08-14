# -*- coding: utf-8 -*-
"""
广告平台查询接口补充
补充创建广告时需要的查询接口：audience、keyword、location、creative
"""

import requests
from typing import List, Dict, Optional


class AdPlatformQueryClient:
    """广告平台查询客户端 - 补充版"""
    
    def __init__(self, credentials: dict):
        self.credentials = credentials
    
    # ========== TikTok 查询接口 ==========
    
    def tiktok_list_keywords(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 用于创建广告时选择关键词"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/keyword/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_keywords error: {e}")
            return []
    
    def tiktok_get_keyword(self, advertiser_id: str, keyword: str = None, **kwargs) -> Dict:
        """获取关键词详情"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'keyword': keyword,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 10)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/keyword/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            keywords = data.get('list', [])
            return keywords[0] if keywords else {}
        except Exception as e:
            print(f"[TikTok] get_keyword error: {e}")
            return {}
    
    def tiktok_list_audiences(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 用于创建广告时选择受众"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/audience/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_audiences error: {e}")
            return []
    
    def tiktok_list_locations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 用于创建广告时选择地域定向"""
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'location_type': kwargs.get('location_type', 'COUNTRY'),
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/location/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_locations error: {e}")
            return []
    
    # ========== Meta 查询接口 ==========
    
    def meta_list_keywords(self, account_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 用于搜索广告创建"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/keywords"
        params = {'access_token': token, 'limit': kwargs.get('limit', 50)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] list_keywords error: {e}")
            return []
    
    def meta_list_locations(self, account_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 用于广告地域定向"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/targetingspecs"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            locations = data.get('data', [])
            return [{'id': loc.get('id'), 'name': loc.get('name'), 'type': loc.get('type')} for loc in locations]
        except Exception as e:
            print(f"[Meta] list_locations error: {e}")
            return []
    
    def meta_list_creatives(self, account_id: str, **kwargs) -> List[Dict]:
        """列出创意素材 - 用于创建广告"""
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{account_id}/creatives"
        params = {'access_token': token, 'limit': kwargs.get('limit', 50)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] list_creatives error: {e}")
            return []
    
    # ========== Google Ads 查询接口 ==========
    
    def google_list_keywords(self, customer_id: str, campaign_id: str = None, **kwargs) -> List[Dict]:
        """列出关键词 - 用于搜索广告创建"""
        # Google Ads API 需要复杂的认证，这里返回占位
        # 实际使用需要使用 google-ads Python 库
        print("[Google Ads] list_keywords 需要使用 google-ads 库")
        return []
    
    def google_list_audiences(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 用于展示广告创建"""
        print("[Google Ads] list_audiences 需要使用 google-ads 库")
        return []
    
    def google_list_locations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 用于广告地域定向"""
        print("[Google Ads] list_locations 需要使用 google-ads 库")
        return []
    
    # ========== DV360 查询接口 ==========
    
    def dv360_list_keywords(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 用于 DISPLAY 广告创建"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/keywordTargets"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('keywordTargets', [])
        except Exception as e:
            print(f"[DV360] list_keywords error: {e}")
            return []
    
    def dv360_list_audiences(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 用于 DISPLAY 广告创建"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/audienceTargets"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('audienceTargets', [])
        except Exception as e:
            print(f"[DV360] list_audiences error: {e}")
            return []
    
    def dv360_list_locations(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 用于 DISPLAY 广告地域定向"""
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/locationTargets"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('locationTargets', [])
        except Exception as e:
            print(f"[DV360] list_locations error: {e}")
            return []
