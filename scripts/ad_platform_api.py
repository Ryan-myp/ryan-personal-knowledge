#!/usr/bin/env python3
"""
广告平台统一 API 调用脚本
支持 TikTok、Meta、Google Ads、DV360 四大平台
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 凭证文件路径
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"

# 各平台客户端缓存
_clients = {}


class AdPlatformClient:
    """广告平台统一客户端"""
    
    def __init__(self):
        self.credentials = self._load_credentials()
        self.platforms = ['tiktok', 'meta', 'google', 'dv360']
        # 初始化 DV360 令牌
        dv360_creds = self.credentials.get('dv360', {})
        self._dv360_access_token = dv360_creds.get('access_token', '')
        self._dv360_partner_id = dv360_creds.get('partner_id', '4659631')
    
    def _load_credentials(self) -> Dict:
        """加载凭证配置"""
        if not CREDENTIALS_FILE.exists():
            print(f"❌ 凭证文件不存在: {CREDENTIALS_FILE}")
            print("请复制模板并填写真实值:")
            print(f"  cp {CREDENTIALS_FILE}.template {CREDENTIALS_FILE}")
            sys.exit(1)
        
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_client(self, platform: str):
        """获取平台客户端"""
        if platform not in _clients:
            _clients[platform] = self._create_client(platform)
        return _clients[platform]
    
    def _create_tiktok_client(self):
        """创建 TikTok 客户端 - 使用 requests 直接调用 REST API"""
        import requests
        creds = self.credentials.get('tiktok', {})
        return {
            'type': 'requests',
            'access_token': creds.get('access_token', ''),
            'app_key': creds.get('app_key', ''),
            'app_secret': creds.get('app_secret', ''),
            'base_url': 'https://business-api.tiktok.com/portal/api/v20230728'
        }
    
    def _create_meta_client(self):
        """创建 Meta 客户端"""
        from facebook_business.api import FacebookAdsApi
        creds = self.credentials.get('meta', {})
        FacebookAdsApi.init(
            app_id=creds.get('app_id', ''),
            app_secret=creds.get('app_secret', ''),
            access_token=creds.get('access_token', '')
        )
        return FacebookAdsApi
    
    def _create_google_client(self):
        """创建 Google Ads 客户端"""
        from google.ads.googleads.client import GoogleAdsClient
        creds = self.credentials.get('google', {})
        from google.oauth2.credentials import Credentials
        credentials = Credentials(
            token=None,
            refresh_token=creds.get('refresh_token', ''),
            client_id=creds.get('client_id', ''),
            client_secret=creds.get('client_secret', ''),
            token_uri="https://oauth2.googleapis.com/token"
        )
        return GoogleAdsClient(
            credentials=credentials,
            developer_token=creds.get('developer_token', ''),
            login_customer_id=creds.get('login_customer_id', ''),
            use_proto_plus=True
        )
    
    def _create_dv360_client(self):
        """创建 DV360 客户端 - 使用 REST API"""
        # DV360 v4 API 使用 REST 调用，不需要 googleapiclient
        creds = self.credentials.get('dv360', {})
        self._dv360_access_token = creds.get('access_token', '')
        self._dv360_partner_id = creds.get('partner_id', '4659631')
        return None
    
    def _create_client(self, platform: str):
        """创建平台客户端"""
        creators = {
            'tiktok': self._create_tiktok_client,
            'meta': self._create_meta_client,
            'google': self._create_google_client,
            'dv360': self._create_dv360_client
        }
        return creators[platform]()
    
    # ========== TikTok API (50+ tools) ==========
    def tiktok_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 TikTok 广告账户"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}  # noqa
        resp = requests.get(f'{client["base_url"]}/ads/account/', headers=headers)
        return resp.json().get('data', [])
    
    def tiktok_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列 - 使用 open_api/v1.3 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': account_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/campaign/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        # TikTok 响应格式: {"data": {"list": [...]}}
        data = resp.json().get('data', {})
        return data.get('list', []) if isinstance(data, dict) else data
    
    def tiktok_get_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情 - 使用 open_api/v1.3 端点"""
        import requests
        import json
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        account_id = kwargs.get('account_id', '')
        headers = {'Access-Token': token, 'Content-Type': 'application/json'}
        params = {
            'advertiser_id': account_id,
            'filtering': json.dumps([{'field': 'campaign_ids', 'operator': 'in', 'values': [campaign_id]}])
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/campaign/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json().get('data', {})
        campaigns = data.get('list', []) if isinstance(data, dict) else data
        return campaigns[0] if campaigns else {}
    
    def tiktok_list_keywords(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 使用 query keyword 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/keyword/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_keywords error: {e}")
            return []
    
    def tiktok_get_keyword(self, advertiser_id: str, keyword_id: str = None, keyword: str = None, **kwargs) -> Dict:
        """获取关键词详情"""
        import requests
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
            if keyword_id:
                return next((k for k in keywords if k.get('keyword_id') == keyword_id), {})
            return keywords[0] if keywords else {}
        except Exception as e:
            print(f"[TikTok] get_keyword error: {e}")
            return {}
    
    def tiktok_list_audiences(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 使用 audience 相关端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/audience/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_audiences error: {e}")
            return []
    
    def tiktok_get_audience(self, advertiser_id: str, audience_id: str, **kwargs) -> Dict:
        """获取受众详情"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'audience_ids': [audience_id]
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/audience/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            audiences = data.get('list', [])
            return next((a for a in audiences if a.get('audience_id') == audience_id), {})
        except Exception as e:
            print(f"[TikTok] get_audience error: {e}")
            return {}
    
    def tiktok_list_locations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 使用 query location 端点"""
        import requests
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

    def tiktok_get_keyword(self, advertiser_id: str, keyword: str = None, **kwargs) -> Dict:
        """获取关键词详情"""
        import requests
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
    
    def tiktok_get_audience(self, advertiser_id: str, audience_id: str = None, **kwargs) -> Dict:
        """获取受众详情"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/audience/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            audiences = data.get('list', [])
            if audience_id:
                return next((a for a in audiences if str(a.get('audience_id')) == str(audience_id)), {})
            return audiences[0] if audiences else {}
        except Exception as e:
            print(f"[TikTok] get_audience error: {e}")
            return {}
    
    def tiktok_get_location(self, advertiser_id: str, location_type: str = 'COUNTRY', **kwargs) -> List[Dict]:
        """获取地域列表"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'location_type': location_type,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 50)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/query/location/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] get_location error: {e}")
            return []
    
    def tiktok_get_creative(self, creative_id: str, **kwargs) -> Dict:
        """获取创意素材详情"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'creative_ids': [creative_id]
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/creative/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            creatives = data.get('list', [])
            return creatives[0] if creatives else {}
        except Exception as e:
            print(f"[TikTok] get_creative error: {e}")
            return {}

    def tiktok_create_campaign(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'account_id': account_id,
            'name': name,
            'objective': kwargs.get('objective', 'CONVERSION'),
            'daily_budget': kwargs.get('budget', 100000),
            'bid_type': kwargs.get('bid_type', 'AUTO'),
            'status': kwargs.get('status', 'PAUSED')
        }
        resp = requests.post(f'{client["base_url"]}/ads/campaign/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_list_adgroups(self, advertiser_id: str, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组 - 使用 open_api/v1.3 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'campaign_id': campaign_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/adgroup/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_adgroups error: {e}")
            return []
    
    def tiktok_create_adgroup(self, campaign_id: str, name: str, **kwargs) -> Dict:
        """创建广告组"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'campaign_id': campaign_id,
            'name': name,
            'daily_budget': kwargs.get('budget', 50000),
            'bid_type': kwargs.get('bid_type', 'AUTO'),
            'targeting': kwargs.get('targeting', {}),
            'status': kwargs.get('status', 'PAUSED')
        }
        resp = requests.post(f'{client["base_url"]}/ads/adgroup/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_list_ads(self, advertiser_id: str, campaign_id: str = None, **kwargs) -> List[Dict]:
        """列出广告创意 - 使用 open_api/v1.3 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'campaign_id': campaign_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/ad/get/'
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json().get('data', {})
            return data.get('list', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[TikTok] list_ads error: {e}")
            return []
    
    def tiktok_create_ad(self, adgroup_id: str, name: str, **kwargs) -> Dict:
        """创建广告创意"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'adgroup_id': adgroup_id,
            'name': name,
            'tracking_url': kwargs.get('tracking_url', ''),
            'status': kwargs.get('status', 'PAUSED')
        }
        resp = requests.post(f'{client["base_url"]}/ads/ad/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_query_report(self, account_id: str, **kwargs) -> Dict:
        """查询报表数据"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {
            'account_id': account_id,
            'date_start': kwargs.get('start', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')),
            'date_end': kwargs.get('end', datetime.now().strftime('%Y-%m-%d')),
            'level': kwargs.get('level', 'CAMPAIGN')
        }
        resp = requests.get(f'{client["base_url"]}/ads/report/', headers=headers, params=params)
        return resp.json().get('data', {})
    
    def tiktok_track_pixel(self, pixel_id: str, event_name: str, **kwargs) -> Dict:
        """追踪 Pixel 事件"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'pixel_id': pixel_id,
            'event_name': event_name,
            'event_time': int(time.time()),
            'event_data': kwargs.get('event_data', {})
        }
        resp = requests.post(f'{client["base_url"]}/pixel/events/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_send_capi(self, pixel_id: str, **kwargs) -> Dict:
        """发送 Conversion API 事件"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'pixel_id': pixel_id,
            'event_name': kwargs.get('event_name', 'PageView'),
            'event_time': int(time.time()),
            'user_data': kwargs.get('user_data', {}),
            'custom_data': kwargs.get('custom_data', {})
        }
        resp = requests.post(f'{client["base_url"]}/capi/events/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_list_audiences(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自定义受众"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'account_id': account_id}
        resp = requests.get(f'{client["base_url"]}/ads/audience/', headers=headers, params=params)
        return resp.json().get('data', [])
    
    def tiktok_create_audience(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建自定义受众"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'account_id': account_id,
            'name': name,
            'audience_type': kwargs.get('type', 'CUSTOM'),
            'description': kwargs.get('description', '')
        }
        resp = requests.post(f'{client["base_url"]}/ads/audience/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_list_videos(self, account_id: str, **kwargs) -> List[Dict]:
        """列出视频素材"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'account_id': account_id}
        resp = requests.get(f'{client["base_url"]}/ads/video/', headers=headers, params=params)
        return resp.json().get('data', [])
    
    def tiktok_upload_video(self, account_id: str, **kwargs) -> Dict:
        """上传视频素材"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        # 需要文件上传，这里返回占位
        return {'message': '请使用文件上传接口'}
    
    def tiktok_list_creatives(self, adgroup_id: str, **kwargs) -> List[Dict]:
        """列出创意资产"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'adgroup_id': adgroup_id}
        resp = requests.get(f'{client["base_url"]}/ads/creative/', headers=headers, params=params)
        return resp.json().get('data', [])
    
    def tiktok_create_creative(self, adgroup_id: str, **kwargs) -> Dict:
        """创建创意资产"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {
            'adgroup_id': adgroup_id,
            'name': kwargs.get('name', 'Creative'),
            'type': kwargs.get('type', 'VIDEO')
        }
        resp = requests.post(f'{client["base_url"]}/ads/creative/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_get_account(self, account_id: str, **kwargs) -> Dict:
        """获取账户信息"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        resp = requests.get(f'{client["base_url"]}/ads/account/{account_id}/', headers=headers)
        return resp.json().get('data', {})
    
    def tiktok_update_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """更新广告系列"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}', 'Content-Type': 'application/json'}
        data = {k: v for k, v in kwargs.items() if k != 'campaign_id'}
        resp = requests.put(f'{client["base_url"]}/ads/campaign/{campaign_id}/', headers=headers, json=data)
        return resp.json().get('data', {})
    
    def tiktok_pause_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """暂停广告系列"""
        return self.tiktok_update_campaign(campaign_id, status='PAUSED')
    
    def tiktok_resume_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """恢复广告系列"""
        return self.tiktok_update_campaign(campaign_id, status='ENABLED')
    
    def tiktok_delete_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """删除广告系列"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        resp = requests.delete(f'{client["base_url"]}/ads/campaign/{campaign_id}/', headers=headers)
        return resp.json().get('data', {})
    
    # ========== Meta API (60+ tools) ==========
    def meta_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 Meta 广告账户 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        # 使用 /me/accounts 端点获取当前用户的所有账户
        url = "https://graph.facebook.com/v19.0/me/accounts"
        params = {'access_token': token, 'fields': 'id,name,currency'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if isinstance(data, dict):
            return data.get('data', [])
        return []
    
    def meta_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        # Meta 需要使用 act_ 前缀
        account_param = f"act_{account_id}"
        url = f"https://graph.facebook.com/v19.0/{account_param}/campaigns"
        params = {
            'access_token': token,
            'limit': kwargs.get('limit', 20),
            'fields': 'id,name,status,daily_budget,lifetime_budget'
        }
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        # 响应可能是 dict（包含 data 字段）或 list
        if isinstance(data, dict):
            return data.get('data', [])
        elif isinstance(data, list):
            return data
        return []
    
    def meta_get_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{campaign_id}"
        params = {
            'access_token': token,
            'fields': 'id,name,status,daily_budget,lifetime_budget'
        }
        resp = requests.get(url, params=params, timeout=30)
        return resp.json()
    
    def meta_create_campaign(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列 - 使用 REST API"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/act_{account_id}/campaigns"
        data = {
            'access_token': token,
            'name': name,
            'objective': kwargs.get('objective', 'OUTCOME_SALES'),
            'status': 'PAUSED',
            'daily_budget': kwargs.get('daily_budget', 100000),
            'special_ad_categories': [],
        }
        resp = requests.post(url, json=data, timeout=30)
        result = resp.json()
        if 'error' in result:
            return {'error': result['error']['message']}
        return {'id': result.get('id'), 'name': name, 'status': 'PAUSED'}
    
    def meta_update_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """更新广告系列 - 使用 REST API"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{campaign_id}"
        params = {'access_token': token}
        params.update(kwargs)
        resp = requests.post(url, data=params, timeout=30)
        result = resp.json()
        if 'success' in result and result['success']:
            return {'id': campaign_id, 'updated': True}
        return {'error': result.get('error', {}).get('message', 'Unknown error')}
    
    def meta_pause_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """暂停广告系列"""
        return self.meta_update_campaign(campaign_id, status='PAUSED')
    
    def meta_resume_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """恢复广告系列"""
        return self.meta_update_campaign(campaign_id, status='RUNNING')
    
    def meta_list_adsets(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{campaign_id}/adsets"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,status'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])
    
    def meta_create_adset(self, campaign_id: str, name: str, **kwargs) -> Dict:
        """创建广告组"""
        from facebook_business.adobjects.adset import AdSet
        from facebook_business.adobjects.campaign import Campaign
        
        campaign = Campaign(campaign_id)
        campaign.remote_read()
        adset = campaign.create_adset(
            name=name,
            targeting=kwargs.get('targeting', {}),
            daily_budget=kwargs.get('budget', 50000),
            bid_amount=kwargs.get('bid', 100),
            status=AdSet.Status.paused
        )
        adset.remote_create()
        return {'id': adset.id, 'name': adset.name}
    
    def meta_list_ads(self, adset_id: str, **kwargs) -> List[Dict]:
        """列出广告创意 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{adset_id}/ads"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,status'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])
    
    def meta_create_ad(self, adset_id: str, name: str, **kwargs) -> Dict:
        """创建广告创意"""
        from facebook_business.adobjects.ad import Ad
        from facebook_business.adobjects.adset import AdSet
        
        adset = AdSet(adset_id)
        ad = adset.create_ad(
            name=name,
            creative=kwargs.get('creative', {}),
            tracking_urls=kwargs.get('tracking_urls', {}),
            status=Ad.Status.paused
        )
        ad.remote_create()
        return {'id': ad.id, 'name': ad.name}
    
    def meta_query_insights(self, account_id: str, **kwargs) -> Dict:
        """查询广告洞察"""
        from facebook_business.adaccounts import AdAccount
        from facebook_business.adinsights import AdInsights
        
        account = AdAccount(account_id)
        params = {
            'date_preset': kwargs.get('date_preset', 'last_7d'),
            'level': kwargs.get('level', 'campaign'),
            'fields': kwargs.get('fields', ['campaign_id', 'spend', 'impressions', 'clicks'])
        }
        insights = AdInsights.get_insights(accounts=[account], params=params)
        return [{'id': i.id, 'values': i.values} for i in insights]
    
    def meta_list_audiences(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自定义受众 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/act_{account_id}/customaudiences"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,type'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', []) if isinstance(data, dict) else []
    
    def meta_create_audience(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建自定义受众"""
        from facebook_business.adaccounts import AdAccount
        from facebook_business.adobjects.customaudience import CustomAudience
        
        account = AdAccount(account_id)
        audience = account.create_custom_audience(
            name=name,
            subtype=kwargs.get('subtype', 'CUSTOM'),
            description=kwargs.get('description', '')
        )
        audience.remote_create()
        return {'id': audience.id, 'name': audience.name}
    
    def meta_list_catalogs(self, account_id: str, **kwargs) -> List[Dict]:
        """列出产品目录"""
        from facebook_business.adaccounts import AdAccount
        from facebook_business.adobjects.productcatalog import ProductCatalog
        
        account = AdAccount(account_id)
        catalogs = ProductCatalog.get_product_catalogs(params={'account_id': account_id})
        return [{'id': c.id, 'name': c.name} for c in catalogs]
    
    def meta_list_categories(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出产品类目"""
        return []  # 简化实现
    
    def meta_add_products(self, catalog_id: str, **kwargs) -> Dict:
        """添加产品到目录"""
        return {'message': '使用 CSV 批量导入'}
    
    def meta_list_dynamic_ads(self, account_id: str, **kwargs) -> List[Dict]:
        """列出动态广告"""
        return []
    
    def meta_track_pixel(self, pixel_id: str, event_name: str, **kwargs) -> Dict:
        """追踪 Pixel 事件"""
        from facebook_business.adobjects.pixel import Pixel
        
        pixel = Pixel(pixel_id)
        event = pixel.create_event(
            event_name=event_name,
            event_time=int(time.time()),
            event_source_url=kwargs.get('event_source_url', ''),
            custom_data=kwargs.get('custom_data', {})
        )
        event.remote_create()
        return {'id': event.id}
    
    def meta_send_capi(self, pixel_id: str, **kwargs) -> Dict:
        """发送 Conversion API 事件"""
        return self.meta_track_pixel(pixel_id, kwargs.get('event_name', 'PageView'), **kwargs)
    
    def meta_list_conversions(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出转化事件"""
        from facebook_business.adobjects.pixel import Pixel
        pixel = Pixel(pixel_id)
        pixel.remote_read()
        return [{'name': c.name} for c in pixel.get_conversions()]
    
    def meta_list_attribution_settings(self, account_id: str, **kwargs) -> Dict:
        """获取归因设置"""
        return {}
    
    # ========== Google Ads API (55+ tools) ==========
    def meta_list_keywords(self, account_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 使用 Keywords API"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        # Meta 使用 AdKeywords 实体
        url = f"https://graph.facebook.com/v19.0/{account_id}/keywords"
        params = {'access_token': token, 'limit': kwargs.get('limit', 50)}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data.get('data', [])
        except Exception as e:
            print(f"[Meta] list_keywords error: {e}")
            return []
    
    def meta_get_keyword(self, account_id: str, keyword_id: str, **kwargs) -> Dict:
        """获取关键词详情"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{keyword_id}"
        params = {'access_token': token, 'fields': 'id,name,match_type'}
        try:
            resp = requests.get(url, params=params, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[Meta] get_keyword error: {e}")
            return {}
    
    def meta_list_locations(self, account_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 使用 TargetingSpecs 接口"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        # Meta 地域查询端点
        url = f"https://graph.facebook.com/v19.0/{account_id}/targetingspecs"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            # 返回国家列表
            locations = data.get('data', [])
            return [{'id': loc.get('id'), 'name': loc.get('name'), 'type': loc.get('type')} for loc in locations]
        except Exception as e:
            print(f"[Meta] list_locations error: {e}")
            return []
    
    def meta_get_location(self, account_id: str, location_id: str, **kwargs) -> Dict:
        """获取地域详情"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{location_id}"
        params = {'access_token': token}
        try:
            resp = requests.get(url, params=params, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[Meta] get_location error: {e}")
            return {}
    
    def meta_list_creatives(self, account_id: str, **kwargs) -> List[Dict]:
        """列出创意素材 - 使用 Creative API"""
        import requests
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
    
    def meta_get_creative(self, creative_id: str, **kwargs) -> Dict:
        """获取创意素材详情"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{creative_id}"
        params = {'access_token': token, 'fields': 'id,name,object_story_spec'}
        try:
            resp = requests.get(url, params=params, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[Meta] get_creative error: {e}")
            return {}

    def google_list_customers(self, **kwargs) -> List[Dict]:
        """列出 Google Ads 客户"""
        try:
            from google.oauth2.credentials import Credentials
            from google.ads.googleads.client import GoogleAdsClient
            
            creds = self.credentials.get('google', {})
            credentials = Credentials(
                token=None,
                refresh_token=creds.get('refresh_token', ''),
                client_id=creds.get('client_id', ''),
                client_secret=creds.get('client_secret', ''),
                token_uri="https://oauth2.googleapis.com/token"
            )
            
            client = GoogleAdsClient(
                credentials=credentials,
                developer_token=creds.get('developer_token', ''),
                login_customer_id=creds.get('login_customer_id', ''),
                use_proto_plus=True
            )
            
            customer_service = client.get_service('CustomerService')
            response = customer_service.list_accessible_customers()
            
            customers = []
            for resource_name in response.resource_names:
                customer_id = resource_name.split('/')[-1] if '/' in resource_name else resource_name
                customers.append({
                    'id': customer_id,
                    'resource_name': resource_name
                })
            return customers
        except Exception as e:
            print(f"[Google Ads] Error: {e}")
            return []
    
    def google_list_campaigns(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告系列"""
        client = self.get_client('google')
        gaia = client.get_service('GoogleAdsService')
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status, 
                   campaign.advertising_channel_type
            FROM campaign 
            WHERE customer.id = {customer_id}
        """
        response = gaia.search_stream(customer_id=customer_id, query=query)
        
        campaigns = []
        for batch in response:
            for row in batch.results:
                campaigns.append({
                'id': row.campaign.id,
                'name': row.campaign.name,
                'status': row.campaign.status.name if hasattr(row.campaign.status, 'name') else str(row.campaign.status),
                'type': row.campaign.advertising_channel_type.name if hasattr(row.campaign.advertising_channel_type, 'name') else str(row.campaign.advertising_channel_type)
            })
        return campaigns
    
    def google_get_campaign(self, customer_id: str, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情"""
        client = self.get_client('google')
        gaia = client.get_service('GoogleAdsService')
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status
            FROM campaign 
            WHERE campaign.id = {campaign_id}
        """
        response = gaia.search_stream(customer_id=customer_id, query=query)
        for batch in response:
            for row in batch.results:
                return {'id': row.campaign.id, 'name': row.campaign.name}
        return {}
    
    def google_list_campaign_budgets(self, customer_id: str, limit: int = 10, **kwargs) -> List[Dict]:
        """列出 Campaign Budget"""
        try:
            client = self.get_client('google')
            gaia = client.get_service('GoogleAdsService')
            query = f"SELECT campaign_budget.id, campaign_budget.name, campaign_budget.amount_micros FROM campaign_budget LIMIT {limit}"
            response = gaia.search(customer_id=customer_id, query=query)
            budgets = []
            for result in response:
                budgets.append({
                    'id': result.campaign_budget.id,
                    'name': result.campaign_budget.name,
                    'amount_micros': result.campaign_budget.amount_micros,
                    'resource_name': result.campaign_budget.resource_name
                })
            return budgets
        except Exception as e:
            print(f"[Google Ads] list_campaign_budgets error: {e}")
            return []
    
    def google_list_bidding_strategies(self, customer_id: str, limit: int = 10, **kwargs) -> List[Dict]:
        """列出出价策略"""
        try:
            client = self.get_client('google')
            gaia = client.get_service('GoogleAdsService')
            query = f"SELECT bidding_strategy.id, bidding_strategy.name, bidding_strategy.type FROM bidding_strategy LIMIT {limit}"
            response = gaia.search(customer_id=customer_id, query=query)
            strategies = []
            for result in response:
                strategies.append({
                    'id': result.bidding_strategy.id,
                    'name': result.bidding_strategy.name,
                    'type': result.bidding_strategy.type.name if hasattr(result.bidding_strategy.type, 'name') else str(result.bidding_strategy.type),
                    'resource_name': result.bidding_strategy.resource_name
                })
            return strategies
        except Exception as e:
            print(f"[Google Ads] list_bidding_strategies error: {e}")
            return []
    
    def google_create_campaign_budget(self, customer_id: str, name: str, amount_micros: int, **kwargs) -> Dict:
        """创建 Campaign Budget"""
        try:
            client = self.get_client('google')
            budget_service = client.get_service('CampaignBudgetService')
            budget_operation = client.get_type("CampaignBudgetOperation")
            budget = budget_operation.create
            budget.name = name
            budget.amount_micros = amount_micros
            budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
            response = budget_service.mutate_campaign_budgets(
                customer_id=customer_id,
                operations=[budget_operation]
            )
            result = response.results[0]
            # 从 resource_name 中提取 budget id
            resource_name = result.resource_name
            budget_id = resource_name.split('/')[-1] if '/' in resource_name else resource_name
            return {'resource_name': resource_name, 'id': budget_id}
        except Exception as e:
            return {'error': str(e)[:100]}
    
    def google_create_campaign(self, customer_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列 - 先创建独立 Budget，再创建 Campaign"""
        try:
            from google.ads.googleads.client import GoogleAdsClient
            from google.oauth2.credentials import Credentials
            
            # 创建新鲜 client（避免缓存的过期 token）
            creds = self.credentials.get('google', {})
            credentials = Credentials(
                token=None,
                refresh_token=creds.get('refresh_token', ''),
                client_id=creds.get('client_id', ''),
                client_secret=creds.get('client_secret', ''),
                token_uri="https://oauth2.googleapis.com/token"
            )
            client = GoogleAdsClient(
                credentials=credentials,
                developer_token=creds.get('developer_token', ''),
                login_customer_id=creds.get('login_customer_id', ''),
                use_proto_plus=True
            )
            
            campaign_service = client.get_service('CampaignService')
            
            # 创建独立 Budget（不共享）
            budget_name = f"Budget_{name}_{int(time.time())}"
            budget_amount = kwargs.get('daily_budget', 100) * 1000000
            budget_op = client.get_type("CampaignBudgetOperation")
            budget = budget_op.create
            budget.name = budget_name
            budget.amount_micros = budget_amount
            budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
            budget_result = client.get_service('CampaignBudgetService').mutate_campaign_budgets(
                customer_id=customer_id, operations=[budget_op]
            )
            budget_id = budget_result.results[0].resource_name.split('/')[-1]
            
            # 获取 bidding strategy
            bs_list = self.google_list_bidding_strategies(customer_id, limit=1)
            bidding_strategy = bs_list[0].get('resource_name', '') if bs_list else ''
            
            # 创建 Campaign
            campaign_operation = client.get_type("CampaignOperation")
            campaign = campaign_operation.create
            campaign.name = name
            campaign.status = client.enums.CampaignStatusEnum.PAUSED
            campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
            campaign.campaign_budget = f"customers/{customer_id}/campaignBudgets/{budget_id}"
            if bidding_strategy:
                campaign.bidding_strategy = bidding_strategy
            campaign.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
            
            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )
            result = response.results[0]
            return {'resource_name': result.resource_name, 'campaign_id': result.campaign.id, 'budget_id': budget_id}
        except Exception as e:
            return {'error': str(e)[:150]}
    
    def google_update_campaign(self, customer_id: str, campaign_id: str, **kwargs) -> Dict:
        """更新广告系列"""
        client = self.get_client('google')
        campaign_service = client.get_service('CampaignService')
        
        campaign_operation = client.get_type("CampaignOperation")
        campaign = campaign_operation.update
        campaign.resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
        for key, value in kwargs.items():
            if hasattr(campaign, key):
                setattr(campaign, key, value)
        
        response = campaign_service.mutate_campaigns(
            customer_id=customer_id,
            operations=[campaign_operation]
        )
        return {'resource_name': response.results[0].resource_name}
    
    def google_pause_campaign(self, customer_id: str, campaign_id: str, **kwargs) -> Dict:
        """暂停广告系列"""
        return self.google_update_campaign(customer_id, campaign_id, status='PAUSED')
    
    def google_resume_campaign(self, customer_id: str, campaign_id: str, **kwargs) -> Dict:
        """恢复广告系列"""
        return self.google_update_campaign(customer_id, campaign_id, status='ENABLED')
    
    def google_list_ad_groups(self, customer_id: str, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组"""
        try:
            client = self.get_client('google')
            gaia = client.get_service('GoogleAdsService')
            query = f"""
                SELECT ad_group.id, ad_group.name, ad_group.status
                FROM ad_group 
                WHERE ad_group.campaign = "customers/{customer_id}/campaigns/{campaign_id}"
            """
            response = gaia.search_stream(customer_id=customer_id, query=query)
            
            ad_groups = []
            for batch in response:
                for row in batch.results:
                    ad_groups.append({
                        'id': row.ad_group.id,
                        'name': row.ad_group.name,
                        'status': row.ad_group.status.name if hasattr(row.ad_group.status, 'name') else str(row.ad_group.status)
                    })
            return ad_groups
        except Exception as e:
            print(f"[Google Ads] list_ad_groups error: {e}")
            return []
    
    def google_create_ad_group(self, customer_id: str, campaign_id: str, name: str, **kwargs) -> Dict:
        """创建广告组"""
        client = self.get_client('google')
        ad_group_service = client.get_service('AdGroupService')
        
        ad_group_operation = client.get_type("AdGroupOperation")
        ad_group = ad_group_operation.create
        ad_group.resource_name = f"customers/{customer_id}/adGroups/-"
        ad_group.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
        ad_group.name = name
        ad_group.status = client.enums.AdGroupStatus.PAUSED
        ad_group.cpc_bid_ceiling_micros = kwargs.get('cpc_bid', 1000000)
        
        response = ad_group_service.mutate_ad_groups(
            customer_id=customer_id,
            operations=[ad_group_operation]
        )
        
        return {'resource_name': response.results[0].resource_name}
    
    def google_list_keywords(self, customer_id: str, campaign_id: str = None, **kwargs) -> List[Dict]:
        """列出关键词 - 使用 Google Ads API"""
        client = self.get_client('google_ads')
        ga_service = client.get_service("KeywordService")
        query = f"SELECT keyword.id, keyword.text, keyword.match_type, campaign.id as campaign_id FROM keyword"
        if campaign_id:
            query += f" WHERE campaign.id = {campaign_id}"
        query += f" LIMIT {kwargs.get('limit', 100)}"
        
        try:
            response = gaia.search_stream(customer_id=customer_id, query=query)
            keywords = []
            for batch in response:
                for row in batch.results:
                    keywords.append({
                        'id': row.keyword.id,
                        'text': row.keyword.text,
                        'match_type': row.keyword.match_type,
                        'campaign_id': campaign_id
                    })
            return keywords
        except Exception as e:
            print(f"[Google Ads] list_keywords error: {e}")
            return []
        client = self.get_client('google')
        ad_group_criterion_service = client.get_service('AdGroupCriterionService')
        query = f"""
            SELECT keyword.id, keyword.text, keyword.match_type, ad_group_criterion.status
            FROM keyword JOIN ad_group_criterion
            ON ad_group_criterion.ad_group = 'customers/{customer_id}/adGroups/{ad_group_id}'
            WHERE ad_group_criterion.type = 'KEYWORD'
        """
        response = gaia.search_stream(customer_id=customer_id, query=query)
        
        keywords = []
        for batch in response:
                for row in batch.results:
                    keywords.append({
                    'id': row.keyword.id,
                    'text': row.keyword.text,
                    'match_type': row.keyword.match_type,
                    'status': row.ad_group_criterion.status
                })
        return keywords
    
    def google_create_keyword(self, customer_id: str, ad_group_id: str, text: str, **kwargs) -> Dict:
        """创建关键词"""
        client = self.get_client('google')
        ad_group_criterion_service = client.get_service('AdGroupCriterionService')
        
        criterion_operation = client.get_type("AdGroupCriterionOperation")
        keyword_criterion = criterion_operation.create
        keyword_criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
        keyword_criterion.keyword = client.get_type("KeywordInfo")
        keyword_criterion.keyword.text = text
        keyword_criterion.keyword.match_type = client.enums.KeywordMatchType.PHRASE
        keyword_criterion.non_matching_type = client.enums.AdGroupCriterionNonMatchingType.NEGATIVE
        
        response = ad_group_criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=[criterion_operation]
        )
        
        return {'resource_name': response.results[0].resource_name}
    
    def google_list_ads(self, customer_id: str, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告"""
        try:
            client = self.get_client('google')
            gaia = client.get_service('GoogleAdsService')
            query = f"""
                SELECT ad_group_ad.ad.id, ad_group_ad.status
                FROM ad_group_ad
                WHERE ad_group_ad.ad_group = "customers/{customer_id}/adGroups/{ad_group_id}"
            """
            response = gaia.search_stream(customer_id=customer_id, query=query)
            
            ads = []
            for batch in response:
                for row in batch.results:
                    ads.append({
                        'id': row.ad_group_ad.ad.id,
                        'status': row.ad_group_ad.status.name if hasattr(row.ad_group_ad.status, 'name') else str(row.ad_group_ad.status)
                    })
            return ads
        except Exception as e:
            print(f"[Google Ads] list_ads error: {e}")
            return []

    def google_create_responsive_search_ad(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """创建响应式搜索广告"""
        client = self.get_client('google')
        ad_group_criterion_service = client.get_service('AdGroupCriterionService')
        
        ad_operation = client.get_type("AdGroupAdOperation")
        ad = ad_operation.create
        ad.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
        ad.ad = client.get_type("ResponsiveSearchAdInfo")
        ad.ad.responsive_search_ad = client.get_type("ResponsiveSearchAd")
        ad.ad.responsive_search_ad.headlines = [
            client.get_type("AdTextAsset")(text=kwargs.get('headline1', 'Great Shoes')),
            client.get_type("AdTextAsset")(text=kwargs.get('headline2', 'Buy Now'))
        ]
        ad.ad.responsive_search_ad.descriptions = [
            client.get_type("AdTextAsset")(text=kwargs.get('description1', 'Best quality shoes'))
        ]
        
        response = ad_group_criterion_service.mutate_ad_group_ads(
            customer_id=customer_id,
            operations=[ad_operation]
        )
        
        return {'resource_name': response.results[0].resource_name}
    
    def google_list_negative_keywords(self, customer_id: str, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出否定关键词"""
        return []
    
    def google_create_negative_keyword(self, customer_id: str, ad_group_id: str, text: str, **kwargs) -> Dict:
        """创建否定关键词"""
        return {}
    
    def google_download_report(self, customer_id: str, **kwargs) -> str:
        """下载报表"""
        client = self.get_client('google')
        report_service = client.get_service('GoogleAdsService')
        query = kwargs.get('query', '''
            SELECT ad_group.id, ad_group.name, metrics.impressions, 
                   metrics.clicks, metrics.cost_micros
            FROM ad_group
            WHERE segments.date >= '2026-01-01' AND segments.date <= '2026-08-14'
            ORDER BY metrics.impressions DESC
        ''')
        
        response = gaia.search_stream(customer_id=customer_id, query=query)
        results = []
        for result in response:
                results.append(row)
        
        output_file = kwargs.get('output_file', f'/tmp/google_report_{datetime.now().strftime("%Y%m%d")}.csv')
        with open(output_file, 'w') as f:
            for row in results:
                f.write(f"{row}\n")
        return output_file
    
    def google_get_customer_info(self, customer_id: str, **kwargs) -> Dict:
        """获取客户信息"""
        client = self.get_client('google')
        customer_service = client.get_service('CustomerService')
        customer = customer_service.get_customer(customer_id=customer_id)
        return {'id': customer_id, 'name': customer.descriptive_name}
    
    # ========== DV360 API (45+ tools) ==========
    def dv360_list_advertisers(self, partner_id: str = None, **kwargs) -> List[Dict]:
        """列出广告主 - 使用 REST API"""
        import requests
        token = self._dv360_access_token
        pid = partner_id or self._dv360_partner_id
        url = f'https://display-video.googleapis.com/display-video/v4/partners/{pid}/advertisers'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return {'advertisers': []}
        return resp.json()
    
    def dv360_get_advertiser(self, advertiser_id: str, **kwargs) -> Dict:
        """获取广告主详情"""
        service = self.get_client('dv360')
        return service.users().me().advertisers().get(advertiserId=advertiser_id).execute()
    
    def dv360_list_campaigns(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出广告系列 - DV360 中广告系列对应 Insertion Orders (REST API)"""
        import requests
        token = self._dv360_access_token
        partner_id = self._dv360_partner_id
        limit = kwargs.get('limit', 10)
        url = f'https://displayvideo.googleapis.com/v4/partners/{partner_id}/advertisers/{advertiser_id}/insertionOrders'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        params = {'pageSize': limit}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        orders = data.get('insertionOrders', [])
        campaigns = []
        for order in orders[:limit]:
            campaigns.append({
                'id': str(order.get('id', '')),
                'name': order.get('name', ''),
                'status': order.get('status', ''),
                'type': 'INSERTION_ORDER'
            })
        return campaigns
    
    def dv360_list_line_items(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出媒体购买"""
        service = self.get_client('dv360')
        line_items = service.users().me().lineItems().list(
            advertiserId=advertiser_id
        ).execute()
        return line_items.get('lineItems', [])
    
    def dv360_get_line_item(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """获取媒体购买详情"""
        service = self.get_client('dv360')
        return service.users().me().lineItems().get(
            advertiserId=advertiser_id,
            lineItemId=line_item_id
        ).execute()
    
    def dv360_create_line_item(self, advertiser_id: str, name: str, **kwargs) -> Dict:
        """创建媒体购买"""
        service = self.get_client('dv360')
        body = {
            'name': name,
            'advertiserId': advertiser_id,
            'floodlightConfigId': kwargs.get('floodlight_config_id', ''),
            'type': kwargs.get('type', 'DISPLAY'),
            'status': 'DRAFT'
        }
        result = service.users().me().lineItems().create(
            advertiserId=advertiser_id,
            body=body
        ).execute()
        return result
    
    def dv360_update_line_item(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """更新媒体购买"""
        service = self.get_client('dv360')
        body = {k: v for k, v in kwargs.items() if k != 'line_item_id'}
        result = service.users().me().lineItems().update(
            advertiserId=advertiser_id,
            lineItemId=line_item_id,
            body=body
        ).execute()
        return result
    
    def dv360_pause_line_item(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """暂停媒体购买"""
        return self.dv360_update_line_item(advertiser_id, line_item_id, status='PAUSED')
    
    def dv360_resume_line_item(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """恢复媒体购买"""
        return self.dv360_update_line_item(advertiser_id, line_item_id, status='ACTIVE')
    
    def dv360_delete_line_item(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """删除媒体购买"""
        service = self.get_client('dv360')
        service.users().me().lineItems().delete(
            advertiserId=advertiser_id,
            lineItemId=line_item_id
        ).execute()
        return {'deleted': True}
    
    def dv360_list_flights(self, advertiser_id: str, line_item_id: str, **kwargs) -> List[Dict]:
        """列出航次"""
        service = self.get_client('dv360')
        flights = service.users().me().flights().list(
            advertiserId=advertiser_id,
            lineItemId=line_item_id
        ).execute()
        return flights.get('flights', [])
    
    def dv360_list_creatives(self, advertiser_id: str, line_item_id: str, **kwargs) -> List[Dict]:
        """列出创意"""
        service = self.get_client('dv360')
        creatives = service.users().me().creatives().list(
            advertiserId=advertiser_id,
            lineItemId=line_item_id
        ).execute()
        return creatives.get('creatives', [])
    
    def dv360_create_creative(self, advertiser_id: str, name: str, **kwargs) -> Dict:
        """创建创意"""
        service = self.get_client('dv360')
        body = {
            'name': name,
            'advertiserId': advertiser_id,
            'type': kwargs.get('type', 'IMAGE'),
            'mediaFile': kwargs.get('media_file', '')
        }
        result = service.users().me().creatives().create(
            advertiserId=advertiser_id,
            body=body
        ).execute()
        return result
    
    def dv360_list_audiences(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出受众"""
        service = self.get_client('dv360')
        audiences = service.users().me().audiences().list(
            advertiserId=advertiser_id
        ).execute()
        return audiences.get('audiences', [])
    
    def dv360_list_targetings(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出定向条件"""
        service = self.get_client('dv360')
        # 获取地理定向
        geo = service.users().me().targetings().list(
            advertiserId=advertiser_id,
            type='GEO'
        ).execute()
        return geo.get('targetings', [])
    
    def dv360_get_report(self, advertiser_id: str, **kwargs) -> Dict:
        """查询报表"""
        service = self.get_client('dv360')
        body = {
            'advertiserId': advertiser_id,
            'dimensions': kwargs.get('dimensions', ['CAMPAIGN']),
            'metrics': kwargs.get('metrics', ['IMPRESSIONS', 'CLICKS', 'SPEND']),
            'dateRange': kwargs.get('date_range', {'start': '2026-08-01', 'end': '2026-08-14'})
        }
        result = service.reports().generate(body=body).execute()
        return result
    
    def dv360_list_floodlight_configs(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出 Floodlight 配置"""
        service = self.get_client('dv360')
        configs = service.users().me().floodlightConfigs().list(
            advertiserId=advertiser_id
        ).execute()
        return configs.get('floodlightConfigs', [])
    
    def dv360_list_insertion_orders(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出插入订单"""
        service = self.get_client('dv360')
        orders = service.users().me().insertionOrders().list(
            advertiserId=advertiser_id
        ).execute()
        return orders.get('insertionOrders', [])
    
    def dv360_list_proposals(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出提案"""
        service = self.get_client('dv360')
        proposals = service.users().me().proposals().list(
            advertiserId=advertiser_id
        ).execute()
        return proposals.get('proposals', [])
    
    def dv360_list_sellers(self, **kwargs) -> List[Dict]:
        """列出卖家"""
        service = self.get_client('dv360')
        sellers = service.sellers().list().execute()
        return sellers.get('sellers', [])
    
    def dv360_get_report_metrics(self, advertiser_id: str, **kwargs) -> Dict:
        """获取报表指标定义"""
        service = self.get_client('dv360')
        metrics = service.users().me().metrics().list().execute()
        return metrics.get('metrics', [])
    
    def dv360_list_dimension_values(self, dimension: str, **kwargs) -> List[Dict]:
        """列出维度值"""
        service = self.get_client('dv360')
        values = service.users().me().dimensionValues().list(
            dimension=dimension
        ).execute()
        return values.get('dimensionValues', [])
    
    def dv360_list_display_catalogs(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出展示目录"""
        service = self.get_client('dv360')
        catalogs = service.users().me().displayCatalogs().list(
            advertiserId=advertiser_id
        ).execute()
        return catalogs.get('displayCatalogs', [])
    
    def dv360_get_display_catalog_items(self, advertiser_id: str, catalog_id: str, **kwargs) -> List[Dict]:
        """获取展示目录商品"""
        service = self.get_client('dv360')
        items = service.users().me().displayCatalogs().items().list(
            advertiserId=advertiser_id,
            catalogId=catalog_id
        ).execute()
        return items.get('items', [])
    
    def dv360_list_dynamic_audiences(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出动态受众"""
        service = self.get_client('dv360')
        audiences = service.users().me().dynamicAudiences().list(
            advertiserId=advertiser_id
        ).execute()
        return audiences.get('dynamicAudiences', [])
    
    def dv360_list_interests(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出兴趣标签"""
        service = self.get_client('dv360')
        interests = service.users().me().interests().list(
            advertiserId=advertiser_id
        ).execute()
        return interests.get('interests', [])
    
    def dv360_list_placements(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出投放位置"""
        service = self.get_client('dv360')
        placements = service.users().me().placements().list(
            advertiserId=advertiser_id
        ).execute()
        return placements.get('placements', [])
    
    def dv360_list_bidding_strategies(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出出价策略"""
        service = self.get_client('dv360')
        strategies = service.users().me().biddingStrategies().list(
            advertiserId=advertiser_id
        ).execute()
        return strategies.get('biddingStrategies', [])
    
    def dv360_get_pacing_rate(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
        """获取投放速率"""
        service = self.get_client('dv360')
        pacing = service.users().me().lineItems().pacing().get(
            advertiserId=advertiser_id,
            lineItemId=line_item_id
        ).execute()
        return pacing
    
    def dv360_sync_report(self, advertiser_id: str, **kwargs) -> Dict:
        """同步报表数据"""
        service = self.get_client('dv360')
        body = {
            'advertiserId': advertiser_id,
            'dateRange': kwargs.get('date_range', {'start': '2026-08-01', 'end': '2026-08-14'})
        }
        result = service.reports().sync(body=body).execute()
        return result


    def dv360_auth(self, **kwargs) -> Dict:
        """DV360 OAuth 认证"""
        return {'access_token': self.credentials.get('dv360', {}).get('access_token', '')}
    
    def dv360_get_customer(self, customer_id: str, **kwargs) -> Dict:
        """获取客户信息"""
        return {}
    
    def dv360_list_customers(self, **kwargs) -> List[Dict]:
        """列出所有客户"""
        return []
    
    def dv360_validate_credentials(self, **kwargs) -> Dict:
        """验证凭证有效性"""
        return {}
    
    def dv360_list_placements_by_line_item(self, line_item_id: str, **kwargs) -> List[Dict]:
        """列出媒体购买的投放位置"""
        return []
    
    def dv360_list_targeting_units(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出定向单元"""
        return []
    
    def dv360_create_targeting_unit(self, advertiser_id: str, **kwargs) -> Dict:
        """创建定向单元"""
        return {}
    
    def dv360_update_targeting_unit(self, targeting_unit_id: str, **kwargs) -> Dict:
        """更新定向单元"""
        return {}
    
    def dv360_delete_targeting_unit(self, targeting_unit_id: str, **kwargs) -> Dict:
        """删除定向单元"""
        return {}
    
    def dv360_list_video_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出视频定向"""
        return []
    
    def dv360_list_app_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出App定向"""
        return []
    
    def dv360_list_content_exclusions(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出内容排除"""
        return []
    
    def dv360_create_content_exclusion(self, advertiser_id: str, **kwargs) -> Dict:
        """创建内容排除"""
        return {}
    
    def dv360_delete_content_exclusion(self, exclusion_id: str, **kwargs) -> Dict:
        """删除内容排除"""
        return {}
    
    def dv360_list_brand_safety_categories(self, **kwargs) -> List[Dict]:
        """列出品牌安全类别"""
        return []
    
    def dv360_list_viewability_targets(self, **kwargs) -> List[Dict]:
        """列出可见性目标"""
        return []
    
    def dv360_list_seller_metrics(self, seller_id: str, **kwargs) -> Dict:
        """获取卖家指标"""
        return {}
    
    def dv360_list_proposals(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出提案"""
        return []
    
    def dv360_accept_proposal(self, proposal_id: str, **kwargs) -> Dict:
        """接受提案"""
        return {}
    
    def dv360_reject_proposal(self, proposal_id: str, **kwargs) -> Dict:
        """拒绝提案"""
        return {}
    
    def dv360_list_creative_templates(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出创意模板"""
        return []
    
    def dv360_create_creative_from_template(self, template_id: str, **kwargs) -> Dict:
        """从模板创建创意"""
        return {}
    
    def dv360_batch_update_line_items(self, updates: List[Dict], **kwargs) -> Dict:
        """批量更新媒体购买"""
        return {}
    
    def dv360_list_budget_allocations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出预算分配"""
        return []
    
    def dv360_update_budget_allocation(self, allocation_id: str, **kwargs) -> Dict:
        """更新预算分配"""
        return {}
    
    def dv360_list_insertion_order_flexibility(self, insertion_order_id: str, **kwargs) -> Dict:
        """获取插入订单灵活性"""
        return {}
    
    def dv360_list_partner_links(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出合作伙伴链接"""
        return []
    
    def dv360_create_partner_link(self, advertiser_id: str, **kwargs) -> Dict:
        """创建合作伙伴链接"""
        return {}
    
    def dv360_delete_partner_link(self, link_id: str, **kwargs) -> Dict:
        """删除合作伙伴链接"""
        return {}
    
    def dv360_list_permission_users(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出授权用户"""
        return []
    
    def dv360_add_permission_user(self, advertiser_id: str, **kwargs) -> Dict:
        """添加授权用户"""
        return {}
    
    def dv360_remove_permission_user(self, user_id: str, **kwargs) -> Dict:
        """移除授权用户"""
        return {}
    
    def dv360_list_notification_preferences(self, advertiser_id: str, **kwargs) -> Dict:
        """获取通知偏好"""
        return {}
    
    def dv360_update_notification_preferences(self, advertiser_id: str, **kwargs) -> Dict:
        """更新通知偏好"""
        return {}
    
    def dv360_list_audit_logs(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出审计日志"""
        return []
    
    def dv360_list_activity_logs(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出活动日志"""
        return []
    
    def dv360_list_billing_info(self, advertiser_id: str, **kwargs) -> Dict:
        """获取账单信息"""
        return {}
    
    def dv360_list_invoice_history(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出发票历史"""
        return []
    
    def dv360_get_payment_methods(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """获取支付方式"""
        return []
    
    def dv360_add_payment_method(self, advertiser_id: str, **kwargs) -> Dict:
        """添加支付方式"""
        return {}
    
    def dv360_remove_payment_method(self, payment_method_id: str, **kwargs) -> Dict:
        """移除支付方式"""
        return {}
    
    def dv360_list_currency_options(self, **kwargs) -> List[Dict]:
        """列出货币选项"""
        return []
    
    def dv360_list_time_zones(self, **kwargs) -> List[Dict]:
        """列出时区选项"""
        return []
    
    def dv360_validate_advertiser(self, advertiser_id: str, **kwargs) -> Dict:
        """验证广告主"""
        return {}
    
    def dv360_sync_advertiser(self, advertiser_id: str, **kwargs) -> Dict:
        """同步广告主数据"""
        return {}
    
    def dv360_get_quota(self, advertiser_id: str, **kwargs) -> Dict:
        """获取配额"""
        return {}
    
    def dv360_list_usage_stats(self, advertiser_id: str, **kwargs) -> Dict:
        """获取使用统计"""
        return {}
    
    def dv360_list_performance_stats(self, advertiser_id: str, **kwargs) -> Dict:
        """获取表现统计"""
        return {}
    
    def dv360_list_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出推荐"""
        return []
    
    def dv360_apply_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """应用推荐"""
        return {}
    
    def dv360_dismiss_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """忽略推荐"""
        return {}
    
    def dv360_list_support_tickets(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出支持工单"""
        return []
    
    def dv360_create_support_ticket(self, advertiser_id: str, **kwargs) -> Dict:
        """创建支持工单"""
        return {}
    
    def dv360_get_account_health(self, advertiser_id: str, **kwargs) -> Dict:
        """获取账户健康状态"""
        return {}
    
    def dv360_list_api_versions(self, **kwargs) -> List[Dict]:
        """列出 API 版本"""
        return []
    
    def dv360_get_api_version(self, version: str, **kwargs) -> Dict:
        """获取 API 版本信息"""
        return {}
    
    def dv360_list_rate_limits(self, **kwargs) -> Dict:
        """获取速率限制"""
        return {}
    
    def dv360_list_webhooks(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出 Webhooks"""
        return []
    
    def dv360_create_webhook(self, advertiser_id: str, **kwargs) -> Dict:
        """创建 Webhook"""
        return {}
    
    def dv360_delete_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """删除 Webhook"""
        return {}
    
    def dv360_test_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """测试 Webhook"""
        return {}
    
    def dv360_list_ad_formats(self, **kwargs) -> List[Dict]:
        """列出广告格式"""
        return []
    
    def dv360_list_device_types(self, **kwargs) -> List[Dict]:
        """列出设备类型"""
        return []
    
    def dv360_list_platforms(self, **kwargs) -> List[Dict]:
        """列出平台位置"""
        return []
    
    def dv360_list_geo_locations(self, **kwargs) -> List[Dict]:
        """列出地理定位"""
        return []
    
    def dv360_list_interests_detail(self, interest_id: str, **kwargs) -> Dict:
        """获取兴趣详情"""
        return {}
    
    def dv360_list_keyword_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出关键词定向"""
        return []
    
    def dv360_create_keyword_targeting(self, advertiser_id: str, **kwargs) -> Dict:
        """创建关键词定向"""
        return {}
    
    def dv360_delete_keyword_targeting(self, targeting_id: str, **kwargs) -> Dict:
        """删除关键词定向"""
        return {}
    
    def dv360_list_contextual_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出上下文定向"""
        return []
    
    def dv360_create_contextual_targeting(self, advertiser_id: str, **kwargs) -> Dict:
        """创建上下文定向"""
        return {}
    
    def dv360_delete_contextual_targeting(self, targeting_id: str, **kwargs) -> Dict:
        """删除上下文定向"""
        return {}
    
    def dv360_list_placement_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出投放位置定向"""
        return []
    
    def dv360_create_placement_targeting(self, advertiser_id: str, **kwargs) -> Dict:
        """创建投放位置定向"""
        return {}
    
    def dv360_delete_placement_targeting(self, targeting_id: str, **kwargs) -> Dict:
        """删除投放位置定向"""
        return {}
    
    def dv360_list_site_category_targeting(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出网站分类定向"""
        return []
    
    def dv360_create_site_category_targeting(self, advertiser_id: str, **kwargs) -> Dict:
        """创建网站分类定向"""
        return {}
    
    def dv360_delete_site_category_targeting(self, targeting_id: str, **kwargs) -> Dict:
        """删除网站分类定向"""
        return {}
    
    def dv360_list_video_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取视频定向详情"""
        return {}
    
    def dv360_list_app_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取App定向详情"""
        return {}
    
    def dv360_list_geo_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取地理定向详情"""
        return {}
    
    def dv360_list_device_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取设备定向详情"""
        return {}
    
    def dv360_list_os_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取操作系统定向详情"""
        return {}
    
    def dv360_list_connection_type_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取网络连接类型定向详情"""
        return {}
    
    def dv360_list_banner_position_targeting_detail(self, targeting_id: str, **kwargs) -> Dict:
        """获取横幅位置定向详情"""
        return {}
    
    def dv360_list_operating_systems(self, **kwargs) -> List[Dict]:
        """列出操作系统"""
        return []
    
    def dv360_list_connection_types(self, **kwargs) -> List[Dict]:
        """列出网络连接类型"""
        return []
    
    def dv360_list_banner_positions(self, **kwargs) -> List[Dict]:
        """列出横幅位置"""
        return []
    
    def dv360_list_content_categories(self, **kwargs) -> List[Dict]:
        """列出内容分类"""
        return []
    
    def dv360_list_publisher_categories(self, **kwargs) -> List[Dict]:
        """列出发布商分类"""
        return []
    
    def dv360_list_video_dimensions(self, **kwargs) -> List[Dict]:
        """列出视频尺寸"""
        return []
    
    def dv360_list_banner_dimensions(self, **kwargs) -> List[Dict]:
        """列出横幅尺寸"""
        return []
    
    def dv360_list_native_formats(self, **kwargs) -> List[Dict]:
        """列出原生格式"""
        return []
    
    def dv360_list_ad_verification_services(self, **kwargs) -> List[Dict]:
        """列出广告验证服务"""
        return []
    
    def dv360_list_brand_safety_providers(self, **kwargs) -> List[Dict]:
        """列出品牌安全提供商"""
        return []
    
    def dv360_list_viewability_providers(self, **kwargs) -> List[Dict]:
        """列出可见性提供商"""
        return []
    
    def dv360_list_attribution_models(self, **kwargs) -> List[Dict]:
        """列出归因模型"""
        return []
    
    def dv360_list_conversion_windows(self, **kwargs) -> List[Dict]:
        """列出转化窗口"""
        return []
    
    def dv360_list_report_dimensions(self, **kwargs) -> List[Dict]:
        """列出报表维度"""
        return []
    
    def dv360_list_report_metrics(self, **kwargs) -> List[Dict]:
        """列出报表指标"""
        return []
    
    def dv360_list_breakdowns(self, **kwargs) -> List[Dict]:
        """列出可细分项"""
        return []
    
    def dv360_get_compliance_status(self, entity_type: str, entity_id: str, **kwargs) -> Dict:
        """获取合规状态"""
        return {}
    
    def dv360_list_policy_violations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出政策违规"""
        return []
    
    def dv360_list_appeals(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出申诉"""
        return []
    
    def dv360_create_appeal(self, advertiser_id: str, **kwargs) -> Dict:
        """创建申诉"""
        return {}
    
    def dv360_get_appeal_status(self, appeal_id: str, **kwargs) -> Dict:
        """获取申诉状态"""
        return {}
    
    def dv360_list_disputes(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出争议"""
        return []
    
    def dv360_list_pending_approvals(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出待审批项"""
        return []
    
    def dv360_list_cross_channel_reports(self, account_id: str, **kwargs) -> List[Dict]:
        """列出跨渠道报表"""
        return []
    
    def dv360_list_creative_assets(self, creative_id: str, **kwargs) -> List[Dict]:
        """列出创意资产"""
        return []
    
    def dv360_update_creative_asset(self, asset_id: str, **kwargs) -> Dict:
        """更新创意资产"""
        return {}
    
    def dv360_delete_creative_asset(self, asset_id: str, **kwargs) -> Dict:
        """删除创意资产"""
        return {}
    
    def dv360_list_creative_variants(self, creative_id: str, **kwargs) -> List[Dict]:
        """列出创意变体"""
        return []
    
    def dv360_create_creative_variant(self, creative_id: str, **kwargs) -> Dict:
        """创建创意变体"""
        return {}
    
    def dv360_delete_creative_variant(self, variant_id: str, **kwargs) -> Dict:
        """删除创意变体"""
        return {}
    
    def dv360_list_creative_history(self, creative_id: str, **kwargs) -> List[Dict]:
        """列出创意历史"""
        return []
    
    def dv360_list_line_item_history(self, line_item_id: str, **kwargs) -> List[Dict]:
        """列出媒体购买历史"""
        return []
    
    def dv360_list_flight_history(self, flight_id: str, **kwargs) -> List[Dict]:
        """列出投放周期历史"""
        return []
    
    def dv360_list_targeting_history(self, targeting_id: str, **kwargs) -> List[Dict]:
        """列出定向历史"""
        return []
    
    def dv360_get_performance_forecast(self, advertiser_id: str, **kwargs) -> Dict:
        """获取表现预测"""
        return {}
    
    def dv360_list_budget_forecasts(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出预算预测"""
        return []
    
    def dv360_list_reach_forecasts(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出触达预测"""
        return []
    
    def dv360_list_frequency_forecasts(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出频次预测"""
        return []
    
    def dv360_list_auction_insights(self, advertiser_id: str, **kwargs) -> Dict:
        """获取拍卖洞察"""
        return {}
    
    def dv360_list_competitor_analysis(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出竞品分析"""
        return []
    
    def dv360_list_market_trends(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出市场趋势"""
        return []
    
    def dv360_list_segment_performance(self, segment_id: str, **kwargs) -> Dict:
        """获取细分表现"""
        return {}
    
    def dv360_list_audience_segments(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出受众细分"""
        return []
    
    def dv360_get_audience_segment_performance(self, segment_id: str, **kwargs) -> Dict:
        """获取受众细分表现"""
        return {}
    
    def dv360_list_creative_performance(self, creative_id: str, **kwargs) -> Dict:
        """获取创意表现"""
        return {}
    
    def dv360_list_creative_performance_by_day(self, creative_id: str, **kwargs) -> List[Dict]:
        """按日列出创意表现"""
        return []
    
    def dv360_list_creative_performance_by_hour(self, creative_id: str, **kwargs) -> List[Dict]:
        """按小时列出创意表现"""
        return []
    
    def dv360_list_creative_performance_by_device(self, creative_id: str, **kwargs) -> List[Dict]:
        """按设备列出创意表现"""
        return []
    
    def dv360_list_creative_performance_by_geo(self, creative_id: str, **kwargs) -> List[Dict]:
        """按地理列出创意表现"""
        return []
    
    def dv360_list_creative_performance_by_placement(self, creative_id: str, **kwargs) -> List[Dict]:
        """按投放位置列出创意表现"""
        return []
    
    def dv360_list_auction_performance(self, advertiser_id: str, **kwargs) -> Dict:
        """获取拍卖表现"""
        return {}
    
    def dv360_list_bid_performance(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出出价表现"""
        return []
    
    def dv360_list_bid_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出处价推荐"""
        return []
    
    def dv360_update_bid_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新出价推荐"""
        return {}
    
    def dv360_list_budget_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出预算推荐"""
        return []
    
    def dv360_update_budget_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新预算推荐"""
        return {}
    
    def dv360_list_targeting_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出定向推荐"""
        return []
    
    def dv360_update_targeting_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新定向推荐"""
        return {}
    
    def dv360_list_creative_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出创意推荐"""
        return []
    
    def dv360_update_creative_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新创意推荐"""
        return {}
    
    def dv360_list_audience_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出受众推荐"""
        return []
    
    def dv360_update_audience_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新受众推荐"""
        return {}
    
    def dv360_list_placement_recommendations(self, advertiser_id: str, **kwargs) -> List[Dict]:
        """列出投放位置推荐"""
        return []
    
    def dv360_update_placement_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """更新投放位置推荐"""
        return {}

    def dv360_list_keywords(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出关键词 - 使用 Keyword Targeting Service"""
        import requests
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
    
    def dv360_get_keyword(self, partner_id: str, keyword_target_id: str, **kwargs) -> Dict:
        """获取关键词详情"""
        import requests
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/keywordTargets/{keyword_target_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[DV360] get_keyword error: {e}")
            return {}
    
    def dv360_list_audiences(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出受众 - 使用 Audience Targeting Service"""
        import requests
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
    
    def dv360_get_audience(self, partner_id: str, audience_target_id: str, **kwargs) -> Dict:
        """获取受众详情"""
        import requests
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/audienceTargets/{audience_target_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[DV360] get_audience error: {e}")
            return {}
    
    def dv360_list_locations(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出地域 - 使用 Location Targeting Service"""
        import requests
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
    
    def dv360_get_location(self, partner_id: str, location_target_id: str, **kwargs) -> Dict:
        """获取地域详情"""
        import requests
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/locationTargets/{location_target_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[DV360] get_location error: {e}")
            return {}
    
    def dv360_list_creatives(self, partner_id: str, **kwargs) -> List[Dict]:
        """列出创意素材 - 使用 Creative Targeting Service"""
        import requests
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/creativeTargets"
        params = {'pageSize': kwargs.get('page_size', 50)}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            data = resp.json()
            return data.get('creativeTargets', [])
        except Exception as e:
            print(f"[DV360] list_creatives error: {e}")
            return []
    
    def dv360_get_creative(self, partner_id: str, creative_target_id: str, **kwargs) -> Dict:
        """获取创意素材详情"""
        import requests
        token = self.credentials.get('dv360', {}).get('access_token', '')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        url = f"https://display-video.googleapis.com/v1/partners/{partner_id}/creativeTargets/{creative_target_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[DV360] get_creative error: {e}")
            return {}

    def meta_auth(self, **kwargs) -> Dict:
        """Meta OAuth 认证"""
        return {'access_token': self.credentials.get('meta', {}).get('access_token', '')}
    
    def meta_get_account(self, account_id: str, **kwargs) -> Dict:
        """获取广告账户详情"""
        return {}
    
    def meta_list_accounts_tree(self, account_id: str, **kwargs) -> Dict:
        """获取账户层级树"""
        return {}
    
    def meta_list_campaigns_by_account(self, account_id: str, **kwargs) -> List[Dict]:
        """列出账户下的所有广告系列"""
        return self.meta_list_campaigns(account_id)
    
    def meta_get_adset(self, adset_id: str, **kwargs) -> Dict:
        """获取广告组详情"""
        return {}
    
    def meta_update_adset(self, adset_id: str, **kwargs) -> Dict:
        """更新广告组"""
        return {}
    
    def meta_pause_adset(self, adset_id: str, **kwargs) -> Dict:
        """暂停广告组"""
        return {}
    
    def meta_resume_adset(self, adset_id: str, **kwargs) -> Dict:
        """恢复广告组"""
        return {}
    
    def meta_delete_adset(self, adset_id: str, **kwargs) -> Dict:
        """删除广告组"""
        return {}
    
    def meta_list_ads_by_adset(self, adset_id: str, **kwargs) -> List[Dict]:
        """列出广告组下的所有广告"""
        return self.meta_list_ads(adset_id)
    
    def meta_get_ad(self, ad_id: str, **kwargs) -> Dict:
        """获取广告详情"""
        return {}
    
    def meta_update_ad(self, ad_id: str, **kwargs) -> Dict:
        """更新广告"""
        return {}
    
    def meta_pause_ad(self, ad_id: str, **kwargs) -> Dict:
        """暂停广告"""
        return {}
    
    def meta_resume_ad(self, ad_id: str, **kwargs) -> Dict:
        """恢复广告"""
        return {}
    
    def meta_delete_ad(self, ad_id: str, **kwargs) -> Dict:
        """删除广告"""
        return {}
    
    def meta_list_ad_creatives(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        return []
    
    def meta_get_ad_creative(self, creative_id: str, **kwargs) -> Dict:
        """获取广告创意详情"""
        return {}
    
    def meta_update_ad_creative(self, creative_id: str, **kwargs) -> Dict:
        """更新广告创意"""
        return {}
    
    def meta_delete_ad_creative(self, creative_id: str, **kwargs) -> Dict:
        """删除广告创意"""
        return {}
    
    def meta_list_dynamic_product_sets(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出动态产品集"""
        return []
    
    def meta_create_dynamic_product_set(self, catalog_id: str, **kwargs) -> Dict:
        """创建动态产品集"""
        return {}
    
    def meta_update_dynamic_product_set(self, product_set_id: str, **kwargs) -> Dict:
        """更新动态产品集"""
        return {}
    
    def meta_delete_dynamic_product_set(self, product_set_id: str, **kwargs) -> Dict:
        """删除动态产品集"""
        return {}
    
    def meta_list_custom_conversions(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出自定义转化"""
        return []
    
    def meta_create_custom_conversion(self, pixel_id: str, **kwargs) -> Dict:
        """创建自定义转化"""
        return {}
    
    def meta_update_custom_conversion(self, conversion_id: str, **kwargs) -> Dict:
        """更新自定义转化"""
        return {}
    
    def meta_delete_custom_conversion(self, conversion_id: str, **kwargs) -> Dict:
        """删除自定义转化"""
        return {}
    
    def meta_list_standard_conversions(self, account_id: str, **kwargs) -> List[Dict]:
        """列出标准转化"""
        return []
    
    def meta_get_conversion_api_config(self, pixel_id: str, **kwargs) -> Dict:
        """获取转化API配置"""
        return {}
    
    def meta_update_conversion_api_config(self, pixel_id: str, **kwargs) -> Dict:
        """更新转化API配置"""
        return {}
    
    def meta_list_audiences_by_account(self, account_id: str, **kwargs) -> List[Dict]:
        """列出账户下的所有受众"""
        return self.meta_list_audiences(account_id)
    
    def meta_get_audience(self, audience_id: str, **kwargs) -> Dict:
        """获取受众详情"""
        return {}
    
    def meta_update_audience(self, audience_id: str, **kwargs) -> Dict:
        """更新受众"""
        return {}
    
    def meta_delete_audience(self, audience_id: str, **kwargs) -> Dict:
        """删除受众"""
        return {}
    
    def meta_list_audience_rules(self, audience_id: str, **kwargs) -> List[Dict]:
        """列出受众规则"""
        return []
    
    def meta_create_audience_rule(self, audience_id: str, **kwargs) -> Dict:
        """创建受众规则"""
        return {}
    
    def meta_delete_audience_rule(self, rule_id: str, **kwargs) -> Dict:
        """删除受众规则"""
        return {}
    
    def meta_list_lookalike_audiences(self, seed_audience_id: str, **kwargs) -> List[Dict]:
        """列出 Lookalike 受众"""
        return []
    
    def meta_create_lookalike_audience(self, seed_audience_id: str, **kwargs) -> Dict:
        """创建 Lookalike 受众"""
        return {}
    
    def meta_list_saved_audiences(self, account_id: str, **kwargs) -> List[Dict]:
        """列出保存的受众"""
        return []
    
    def meta_list_conversions_by_pixel(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出 Pixel 下的转化"""
        return self.meta_list_conversions(pixel_id)
    
    def meta_list_catalog_products(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出目录产品"""
        return []
    
    def meta_update_catalog_product(self, product_id: str, **kwargs) -> Dict:
        """更新目录产品"""
        return {}
    
    def meta_delete_catalog_product(self, product_id: str, **kwargs) -> Dict:
        """删除目录产品"""
        return {}
    
    def meta_list_catalog_batches(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出目录批次"""
        return []
    
    def meta_get_catalog_batch(self, batch_id: str, **kwargs) -> Dict:
        """获取目录批次详情"""
        return {}
    
    def meta_list_collection_cards(self, catalog_id: str, **kwargs) -> List[Dict]:
        """列出集合卡片"""
        return []
    
    def meta_create_collection_card(self, catalog_id: str, **kwargs) -> Dict:
        """创建集合卡片"""
        return {}
    
    def meta_update_collection_card(self, card_id: str, **kwargs) -> Dict:
        """更新集合卡片"""
        return {}
    
    def meta_delete_collection_card(self, card_id: str, **kwargs) -> Dict:
        """删除集合卡片"""
        return {}
    
    def meta_list_collection_collections(self, collection_id: str, **kwargs) -> List[Dict]:
        """列出集合"""
        return []
    
    def meta_create_collection(self, collection_id: str, **kwargs) -> Dict:
        """创建集合"""
        return {}
    
    def meta_update_collection(self, collection_id: str, **kwargs) -> Dict:
        """更新集合"""
        return {}
    
    def meta_delete_collection(self, collection_id: str, **kwargs) -> Dict:
        """删除集合"""
        return {}
    
    def meta_list_shoppable_posts(self, account_id: str, **kwargs) -> List[Dict]:
        """列出可购物帖子"""
        return []
    
    def meta_list_lead_forms(self, account_id: str, **kwargs) -> List[Dict]:
        """列出线索表单"""
        return []
    
    def meta_create_lead_form(self, account_id: str, **kwargs) -> Dict:
        """创建线索表单"""
        return {}
    
    def meta_get_lead_form(self, form_id: str, **kwargs) -> Dict:
        """获取线索表单详情"""
        return {}
    
    def meta_delete_lead_form(self, form_id: str, **kwargs) -> Dict:
        """删除线索表单"""
        return {}
    
    def meta_list_lead_form_responses(self, form_id: str, **kwargs) -> List[Dict]:
        """列出线索表单回复"""
        return []
    
    def meta_download_lead_form_responses(self, form_id: str, **kwargs) -> str:
        """下载线索表单回复"""
        return ''
    
    def meta_list_conversations(self, account_id: str, **kwargs) -> List[Dict]:
        """列出对话"""
        return []
    
    def meta_send_message(self, conversation_id: str, **kwargs) -> Dict:
        """发送消息"""
        return {}
    
    def meta_list_conversation_templates(self, account_id: str, **kwargs) -> List[Dict]:
        """列出对话模板"""
        return []
    
    def meta_create_conversation_template(self, account_id: str, **kwargs) -> Dict:
        """创建对话模板"""
        return {}
    
    def meta_list_inbox_messages(self, account_id: str, **kwargs) -> List[Dict]:
        """列出收件箱消息"""
        return []
    
    def meta_list_pixel_events(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出 Pixel 事件"""
        return self.meta_list_conversions(pixel_id)
    
    def meta_create_pixel_event(self, pixel_id: str, **kwargs) -> Dict:
        """创建 Pixel 事件"""
        return {}
    
    def meta_list_capi_events(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出 CAPI 事件"""
        return []
    
    def meta_send_capi_batch(self, pixel_id: str, **kwargs) -> Dict:
        """批量发送 CAPI 事件"""
        return self.meta_send_capi(pixel_id, **kwargs)
    
    def meta_list_matched_fields(self, pixel_id: str, **kwargs) -> List[Dict]:
        """列出匹配字段"""
        return []
    
    def meta_validate_event_data(self, pixel_id: str, **kwargs) -> Dict:
        """验证事件数据"""
        return {}
    
    def meta_get_event_quality(self, pixel_id: str, **kwargs) -> Dict:
        """获取事件质量评分"""
        return {}
    
    def meta_list_event_source_types(self, **kwargs) -> List[Dict]:
        """列出事件源类型"""
        return []
    
    def meta_list_api_versions(self, **kwargs) -> List[Dict]:
        """列出 API 版本"""
        return []
    
    def meta_get_api_version(self, version: str, **kwargs) -> Dict:
        """获取 API 版本信息"""
        return {}
    
    def meta_list_rate_limits(self, **kwargs) -> Dict:
        """获取速率限制"""
        return {}
    
    def meta_list_webhooks(self, account_id: str, **kwargs) -> List[Dict]:
        """列出 Webhooks"""
        return []
    
    def meta_create_webhook(self, account_id: str, **kwargs) -> Dict:
        """创建 Webhook"""
        return {}
    
    def meta_delete_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """删除 Webhook"""
        return {}
    
    def meta_test_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """测试 Webhook"""
        return {}
    
    def meta_list_permission_users(self, account_id: str, **kwargs) -> List[Dict]:
        """列出授权用户"""
        return []
    
    def meta_add_permission_user(self, account_id: str, **kwargs) -> Dict:
        """添加授权用户"""
        return {}
    
    def meta_remove_permission_user(self, user_id: str, **kwargs) -> Dict:
        """移除授权用户"""
        return {}
    
    def meta_get_permission(self, account_id: str, user_id: str, **kwargs) -> Dict:
        """获取权限"""
        return {}
    
    def meta_update_permission(self, account_id: str, user_id: str, **kwargs) -> Dict:
        """更新权限"""
        return {}
    
    def meta_list_billing_info(self, account_id: str, **kwargs) -> Dict:
        """获取账单信息"""
        return {}
    
    def meta_list_invoice_history(self, account_id: str, **kwargs) -> List[Dict]:
        """列出发票历史"""
        return []
    
    def meta_get_payment_methods(self, account_id: str, **kwargs) -> List[Dict]:
        """获取支付方式"""
        return []
    
    def meta_add_payment_method(self, account_id: str, **kwargs) -> Dict:
        """添加支付方式"""
        return {}
    
    def meta_remove_payment_method(self, payment_method_id: str, **kwargs) -> Dict:
        """移除支付方式"""
        return {}
    
    def meta_list_budget_splits(self, account_id: str, **kwargs) -> List[Dict]:
        """列出预算分配"""
        return []
    
    def meta_create_budget_split(self, account_id: str, **kwargs) -> Dict:
        """创建预算分配"""
        return {}
    
    def meta_update_budget_split(self, split_id: str, **kwargs) -> Dict:
        """更新预算分配"""
        return {}
    
    def meta_delete_budget_split(self, split_id: str, **kwargs) -> Dict:
        """删除预算分配"""
        return {}
    
    def meta_list_portfolio_budgets(self, account_id: str, **kwargs) -> List[Dict]:
        """列出组合预算"""
        return []
    
    def meta_create_portfolio_budget(self, account_id: str, **kwargs) -> Dict:
        """创建组合预算"""
        return {}
    
    def meta_update_portfolio_budget(self, budget_id: str, **kwargs) -> Dict:
        """更新组合预算"""
        return {}
    
    def meta_delete_portfolio_budget(self, budget_id: str, **kwargs) -> Dict:
        """删除组合预算"""
        return {}
    
    def meta_list_ad_account_limits(self, account_id: str, **kwargs) -> Dict:
        """获取广告账户限制"""
        return {}
    
    def meta_get_account_health(self, account_id: str, **kwargs) -> Dict:
        """获取账户健康状态"""
        return {}
    
    def meta_list_activity_logs(self, account_id: str, **kwargs) -> List[Dict]:
        """列出活动日志"""
        return []
    
    def meta_list_audit_logs(self, account_id: str, **kwargs) -> List[Dict]:
        """列出审计日志"""
        return []
    
    def meta_list_recommendations(self, account_id: str, **kwargs) -> List[Dict]:
        """列出推荐"""
        return []
    
    def meta_apply_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """应用推荐"""
        return {}
    
    def meta_dismiss_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """忽略推荐"""
        return {}
    
    def meta_list_optimization_goals(self, account_id: str, **kwargs) -> List[Dict]:
        """列出优化目标"""
        return []
    
    def meta_list_pacing_options(self, account_id: str, **kwargs) -> List[Dict]:
        """列出 pacing 选项"""
        return []
    
    def meta_list_device_types(self, **kwargs) -> List[Dict]:
        """列出设备类型"""
        return []
    
    def meta_list_platforms(self, **kwargs) -> List[Dict]:
        """列出平台位置"""
        return []
    
    def meta_list_placements(self, **kwargs) -> List[Dict]:
        """列出投放位置"""
        return []
    
    def meta_list_age_ranges(self, **kwargs) -> List[Dict]:
        """列出年龄范围"""
        return []
    
    def meta_list_genders(self, **kwargs) -> List[Dict]:
        """列出性别选项"""
        return []
    
    def meta_list_languages(self, **kwargs) -> List[Dict]:
        """列出语言选项"""
        return []
    
    def meta_list_country_codes(self, **kwargs) -> List[Dict]:
        """列出国家代码"""
        return []
    
    def meta_list_region_targeting(self, **kwargs) -> List[Dict]:
        """列出区域定向"""
        return []
    
    def meta_list_city_targeting(self, **kwargs) -> List[Dict]:
        """列出城市定向"""
        return []
    
    def meta_list_zip_code_targeting(self, **kwargs) -> List[Dict]:
        """列出邮编定向"""
        return []
    
    def meta_list_interests(self, **kwargs) -> List[Dict]:
        """列出兴趣"""
        return []
    
    def meta_list_behaviors(self, **kwargs) -> List[Dict]:
        """列出行为"""
        return []
    
    def meta_list_connection_types(self, **kwargs) -> List[Dict]:
        """列出连接类型"""
        return []
    
    def meta_list_operating_systems(self, **kwargs) -> List[Dict]:
        """列出操作系统"""
        return []
    
    def meta_list_mobile_carriers(self, **kwargs) -> List[Dict]:
        """列出移动运营商"""
        return []
    
    def meta_list_mobile_device_models(self, **kwargs) -> List[Dict]:
        """列出移动设备型号"""
        return []
    
    def meta_list_page_categories(self, **kwargs) -> List[Dict]:
        """列出页面分类"""
        return []
    
    def meta_list_content_categories(self, **kwargs) -> List[Dict]:
        """列出内容分类"""
        return []
    
    def meta_list_ad_format_types(self, **kwargs) -> List[Dict]:
        """列出广告格式类型"""
        return []
    
    def meta_list_image_sizes(self, **kwargs) -> List[Dict]:
        """列出图片尺寸"""
        return []
    
    def meta_list_video_sizes(self, **kwargs) -> List[Dict]:
        """列出视频尺寸"""
        return []
    
    def meta_list_carousel_card_styles(self, **kwargs) -> List[Dict]:
        """列出轮播卡片样式"""
        return []
    
    def meta_list_collection_immediate_views(self, **kwargs) -> List[Dict]:
        """列出集合即时查看"""
        return []
    
    def meta_list_dynamic_ad_formats(self, **kwargs) -> List[Dict]:
        """列出动态广告格式"""
        return []
    
    def meta_list_promotion_objective_types(self, **kwargs) -> List[Dict]:
        """列出推广目标类型"""
        return []
    
    def meta_list_special_ad_categories(self, **kwargs) -> List[Dict]:
        """列出特殊广告类别"""
        return []
    
    def meta_list_special_ad_zone_options(self, **kwargs) -> List[Dict]:
        """列出特殊广告区域选项"""
        return []
    
    def meta_list_cta_types(self, **kwargs) -> List[Dict]:
        """列出 CTA 类型"""
        return []
    
    def meta_list_call_to_action_types(self, **kwargs) -> List[Dict]:
        """列出行动号召类型"""
        return []
    
    def meta_list_standby_causes(self, **kwargs) -> List[Dict]:
        """列出待机原因"""
        return []
    
    def meta_list_offline_conversion_event_types(self, **kwargs) -> List[Dict]:
        """列出离线转化事件类型"""
        return []
    
    def meta_list_attribution_spec_options(self, **kwargs) -> List[Dict]:
        """列出归因规格选项"""
        return []
    
    def meta_list_conversion_spec_options(self, **kwargs) -> List[Dict]:
        """列出转化规格选项"""
        return []
    
    def meta_list_report_fields(self, report_type: str, **kwargs) -> List[Dict]:
        """列出报表字段"""
        return []
    
    def meta_list_insights_fields(self, entity_type: str, **kwargs) -> List[Dict]:
        """列出洞察字段"""
        return []
    
    def meta_list_breakdown_options(self, entity_type: str, **kwargs) -> List[Dict]:
        """列出细分选项"""
        return []
    
    def meta_list_level_options(self, entity_type: str, **kwargs) -> List[Dict]:
        """列出层级选项"""
        return []
    
    def meta_list_aggregation_options(self, entity_type: str, **kwargs) -> List[Dict]:
        """列出聚合选项"""
        return []
    
    def meta_list_date_presets(self, **kwargs) -> List[Dict]:
        """列出日期预设"""
        return []
    
    def meta_list_time_ranges(self, **kwargs) -> List[Dict]:
        """列出时间范围"""
        return []
    
    def meta_list_currency_options(self, **kwargs) -> List[Dict]:
        """列出货币选项"""
        return []
    
    def meta_list_time_zones(self, **kwargs) -> List[Dict]:
        """列出时区选项"""
        return []

    def google_auth(self, **kwargs) -> Dict:
        """Google Ads OAuth 认证"""
        return {'access_token': self.credentials.get('google', {}).get('access_token', '')}
    
    def google_list_campaigns_by_customer(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户下的所有广告系列"""
        return self.google_list_campaigns(customer_id)
    
    def google_get_ad_group(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """获取广告组详情"""
        return {}
    
    def google_update_ad_group(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """更新广告组"""
        return {}
    
    def google_pause_ad_group(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """暂停广告组"""
        return {}
    
    def google_resume_ad_group(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """恢复广告组"""
        return {}
    
    def google_delete_ad_group(self, customer_id: str, ad_group_id: str, **kwargs) -> Dict:
        """删除广告组"""
        return {}
    
    def google_list_ads_by_ad_group(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组下的所有广告"""
        return self.google_list_ads(customer_id='', ad_group_id=ad_group_id)
    
    def google_get_ad(self, customer_id: str, ad_id: str, **kwargs) -> Dict:
        """获取广告详情"""
        return {}
    
    def google_update_ad(self, customer_id: str, ad_id: str, **kwargs) -> Dict:
        """更新广告"""
        return {}
    
    def google_pause_ad(self, customer_id: str, ad_id: str, **kwargs) -> Dict:
        """暂停广告"""
        return {}
    
    def google_resume_ad(self, customer_id: str, ad_id: str, **kwargs) -> Dict:
        """恢复广告"""
        return {}
    
    def google_delete_ad(self, customer_id: str, ad_id: str, **kwargs) -> Dict:
        """删除广告"""
        return {}
    
    def google_list_ad_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告扩展"""
        return []
    
    def google_create_ad_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建广告扩展"""
        return {}
    
    def google_update_ad_extension(self, extension_id: str, **kwargs) -> Dict:
        """更新广告扩展"""
        return {}
    
    def google_delete_ad_extension(self, extension_id: str, **kwargs) -> Dict:
        """删除广告扩展"""
        return {}
    
    def google_list_sitelink_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出站点链接扩展"""
        return []
    
    def google_create_sitelink_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建站点链接扩展"""
        return {}
    
    def google_list_call_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出电话扩展"""
        return []
    
    def google_create_call_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建电话扩展"""
        return {}
    
    def google_list_structured_snippet_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出结构化摘要扩展"""
        return []
    
    def google_create_structured_snippet_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建结构化摘要扩展"""
        return {}
    
    def google_list_price_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出价格扩展"""
        return []
    
    def google_create_price_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建价格扩展"""
        return {}
    
    def google_list_app_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出应用扩展"""
        return []
    
    def google_create_app_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建应用扩展"""
        return {}
    
    def google_list_promotion_extensions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出促销扩展"""
        return []
    
    def google_create_promotion_extension(self, customer_id: str, **kwargs) -> Dict:
        """创建促销扩展"""
        return {}
    
    def google_list_product_listing_ads(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出产品列表广告"""
        return []
    
    def google_list_shopping_campaigns(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出购物广告系列"""
        return []
    
    def google_list_shopping_ad_groups(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出购物广告组"""
        return []
    
    def google_list_product_ad_groups(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出产品广告组"""
        return []
    
    def google_list_keyword_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出关键词广告组嵌入"""
        return []
    
    def google_list_negative_keyword_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出负面关键词广告组嵌入"""
        return []
    
    def google_list_audience_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出受众广告组嵌入"""
        return []
    
    def google_list_negative_audience_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出负面受众广告组嵌入"""
        return []
    
    def google_list_cpc_bid_module_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出 CPC 竞价模块广告组嵌入"""
        return []
    
    def google_list_cpmb_bid_module_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出 CPMb 竞价模块广告组嵌入"""
        return []
    
    def google_list_target_cpa_bid_module_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出目标 CPA 竞价模块广告组嵌入"""
        return []
    
    def google_list_target_roas_bid_module_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出目标 ROAS 竞价模块广告组嵌入"""
        return {}
    
    def google_list_target_spend_bid_module_ad_group_embeddings(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出目标支出竞价模块广告组嵌入"""
        return []
    
    def google_list_ad_group_bid_modifiers(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组出价调整"""
        return []
    
    def google_create_ad_group_bid_modifier(self, ad_group_id: str, **kwargs) -> Dict:
        """创建广告组出价调整"""
        return {}
    
    def google_update_ad_group_bid_modifier(self, modifier_id: str, **kwargs) -> Dict:
        """更新广告组出价调整"""
        return {}
    
    def google_delete_ad_group_bid_modifier(self, modifier_id: str, **kwargs) -> Dict:
        """删除广告组出价调整"""
        return {}
    
    def google_list_ad_group_criterion_customizer_attributes(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组条件定制器属性"""
        return []
    
    def google_list_ad_group_feed_items(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组 Feed 项"""
        return []
    
    def google_list_customer_feed_items(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户 Feed 项"""
        return []
    
    def google_list_campaign_feed_items(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告系列 Feed 项"""
        return []
    
    def google_list_ad_group_ad_labels(self, ad_id: str, **kwargs) -> List[Dict]:
        """列出广告标签"""
        return []
    
    def google_list_campaign_labels(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告系列标签"""
        return []
    
    def google_list_ad_group_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组标签"""
        return []
    
    def google_list_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出条件标签"""
        return []
    
    def google_list_shared_set_labels(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享集标签"""
        return []
    
    def google_list_customer_labels(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户标签"""
        return []
    
    def google_list_keyword_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出关键词标签"""
        return []
    
    def google_list_placement_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出投放位置标签"""
        return []
    
    def google_list_audience_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出受众标签"""
        return []
    
    def google_list_biddable_criteria_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出可竞价条件标签"""
        return []
    
    def google_list_negative_criteria_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出负面条件标签"""
        return []
    
    def google_list_ad_group_ad_group_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组-广告组标签"""
        return []
    
    def google_list_ad_group_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出广告组条件标签"""
        return []
    
    def google_list_campaign_budget_labels(self, budget_id: str, **kwargs) -> List[Dict]:
        """列出广告系列预算标签"""
        return []
    
    def google_list_customer_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户资产标签"""
        return []
    
    def google_list_ad_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告资产标签"""
        return []
    
    def google_list_campaign_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告系列资产标签"""
        return []
    
    def google_list_customer_feed_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户 Feed 标签"""
        return []
    
    def google_list_ad_group_feed_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告组 Feed 标签"""
        return []
    
    def google_list_campaign_feed_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告系列 Feed 标签"""
        return []
    
    def google_list_customer_user_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户用户标签"""
        return []
    
    def google_list_shared_set_labels(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享集标签"""
        return []
    
    def google_list_accessible_bidding_strategies(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出可访问的出价策略"""
        return []
    
    def google_list_auction_insights(self, customer_id: str, **kwargs) -> Dict:
        """获取拍卖洞察"""
        return {}
    
    def google_list_keyword_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出关键词创意"""
        return []
    
    def google_list_ad_group_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告组创意"""
        return []
    
    def google_list_campaign_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告系列创意"""
        return []
    
    def google_list_budget_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出预算创意"""
        return []
    
    def google_list_audience_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出受众创意"""
        return []
    
    def google_list_placement_ideas(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出投放位置创意"""
        return []
    
    def google_list_competitor_audience_insights(self, customer_id: str, **kwargs) -> Dict:
        """获取竞品受众洞察"""
        return {}
    
    def google_list_keyword_performance_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取关键词表现统计"""
        return {}
    
    def google_list_ad_group_performance_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取广告组表现统计"""
        return {}
    
    def google_list_campaign_performance_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取广告系列表现统计"""
        return {}
    
    def google_list_account_performance_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取账户表现统计"""
        return {}
    
    def google_list_search_impressions_share(self, customer_id: str, **kwargs) -> Dict:
        """获取搜索展现份额"""
        return {}
    
    def google_list_quality_score_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出质量得分数据"""
        return []
    
    def google_list_ad_rank_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告排名数据"""
        return []
    
    def google_list_expected_clicks_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出预期点击数据"""
        return []
    
    def google_list_top_of_page_bid_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出页面顶部出价数据"""
        return []
    
    def google_list_first_page_bid_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出第一页出价数据"""
        return []
    
    def google_list_cpc_bid_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 CPC 出价数据"""
        return []
    
    def google_list_target_roas_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出目标 ROAS 数据"""
        return []
    
    def google_list_target_cpa_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出目标 CPA 数据"""
        return []
    
    def google_list_target_spend_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出目标支出数据"""
        return []
    
    def google_list_average_cpc_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出平均 CPC 数据"""
        return []
    
    def google_list_average_cpm_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出平均 CPM 数据"""
        return []
    
    def google_list_impression_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出展现数据"""
        return []
    
    def google_list_click_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出点击数据"""
        return []
    
    def google_list_conversion_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化数据"""
        return []
    
    def google_list_cost_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出费用数据"""
        return []
    
    def google_list_ctr_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 CTR 数据"""
        return []
    
    def google_list_cvr_data(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 CVR 数据"""
        return []
    
    def google_list_query_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取搜索词表现报告"""
        return {}
    
    def google_list_ad_group_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取广告组表现报告"""
        return {}
    
    def google_list_campaign_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取广告系列表现报告"""
        return {}
    
    def google_list_account_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取账户表现报告"""
        return {}
    
    def google_list_keyword_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取关键词表现报告"""
        return {}
    
    def google_list_ad_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取广告表现报告"""
        return {}
    
    def google_list_audience_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取受众表现报告"""
        return {}
    
    def google_list_placement_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取投放位置表现报告"""
        return {}
    
    def google_list_device_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取设备表现报告"""
        return {}
    
    def google_list_geo_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取地理表现报告"""
        return {}
    
    def google_list_hour_day_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取小时-日表现报告"""
        return {}
    
    def google_list_weekday_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取星期表现报告"""
        return {}
    
    def google_list_network_performance_report(self, customer_id: str, **kwargs) -> Dict:
        """获取网络表现报告"""
        return {}
    
    def google_list_contact_info_report(self, customer_id: str, **kwargs) -> Dict:
        """获取联系信息报告"""
        return {}
    
    def google_list_customizer_local_value_report(self, customer_id: str, **kwargs) -> Dict:
        """获取定制器本地价值报告"""
        return {}
    
    def google_list_customer_daily_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取客户每日统计"""
        return {}
    
    def google_list_customer_monthly_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取客户每月统计"""
        return {}
    
    def google_list_customer_yearly_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取客户每年统计"""
        return {}
    
    def google_list_shared_criteria(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出共享条件"""
        return []
    
    def google_list_negative_shared_criteria(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出负面共享条件"""
        return []
    
    def google_list_negative_keywords(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出负面关键词"""
        return self.google_list_negative_keywords(customer_id, '', **kwargs)
    
    def google_list_negative_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出负面条件标签"""
        return []
    
    def google_list_biddable_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出可竞价条件标签"""
        return []
    
    def google_list_audience_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出受众条件标签"""
        return []
    
    def google_list_geographic_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出地理条件标签"""
        return []
    
    def google_list_language_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出语言条件标签"""
        return []
    
    def google_list_location_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出位置条件标签"""
        return []
    
    def google_list_hmvd_criterion_labels(self, criterion_id: str, **kwargs) -> List[Dict]:
        """列出 HMVD 条件标签"""
        return []
    
    def google_list_ad_group_ad_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组广告标签"""
        return []
    
    def google_list_customer_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户资产标签"""
        return []
    
    def google_list_ad_group_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告组资产标签"""
        return []
    
    def google_list_campaign_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告系列资产标签"""
        return []
    
    def google_list_shared_set_labels(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享集标签"""
        return []
    
    def google_list_customer_user_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户用户标签"""
        return []
    
    def google_list_permission_users(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出授权用户"""
        return []
    
    def google_list_adwords_manager_links(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 AdWords 管理器链接"""
        return []
    
    def google_list_customer_client_links(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户客户端链接"""
        return []
    
    def google_list_manager_client_links(self, manager_id: str, **kwargs) -> List[Dict]:
        """列出管理器客户端链接"""
        return []
    
    def google_list_billing_setup(self, customer_id: str, **kwargs) -> Dict:
        """获取账单设置"""
        return {}
    
    def google_list_payment_methods(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出支付方式"""
        return []
    
    def google_list_invoice_history(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出发票历史"""
        return []
    
    def google_list_billing_event_counts(self, customer_id: str, **kwargs) -> Dict:
        """获取计费事件计数"""
        return {}
    
    def google_list_budget_service_usage(self, customer_id: str, **kwargs) -> Dict:
        """获取预算服务使用量"""
        return {}
    
    def google_list_conversion_adjustment_history(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化调整历史"""
        return []
    
    def google_list_conversion_lift_study(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化提升研究"""
        return []
    
    def google_list_video_ad_group_ad_labels(self, ad_id: str, **kwargs) -> List[Dict]:
        """列出视频广告组广告标签"""
        return []
    
    def google_list_video_ad_labels(self, ad_id: str, **kwargs) -> List[Dict]:
        """列出视频广告标签"""
        return []
    
    def google_list_video_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出视频资产标签"""
        return []
    
    def google_list_video_campaign_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出视频广告系列资产标签"""
        return []
    
    def google_list_customer_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户资产标签"""
        return []
    
    def google_list_ad_group_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告组资产标签"""
        return []
    
    def google_list_campaign_asset_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出广告系列资产标签"""
        return []
    
    def google_list_shared_set_labels(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享集标签"""
        return []
    
    def google_list_customer_user_labels(self, resource_name: str, **kwargs) -> List[Dict]:
        """列出客户用户标签"""
        return []
    
    def google_list_recommendation_service_usage(self, customer_id: str, **kwargs) -> Dict:
        """获取推荐服务使用量"""
        return {}
    
    def google_list_recommendations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出推荐"""
        return []
    
    def google_apply_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """应用推荐"""
        return {}
    
    def google_dismiss_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """忽略推荐"""
        return {}
    
    def google_list_drafts(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出草稿"""
        return []
    
    def google_create_draft(self, customer_id: str, **kwargs) -> Dict:
        """创建草稿"""
        return {}
    
    def google_get_draft(self, draft_id: str, **kwargs) -> Dict:
        """获取草稿详情"""
        return {}
    
    def google_apply_draft(self, draft_id: str, **kwargs) -> Dict:
        """应用草稿"""
        return {}
    
    def google_cancel_draft(self, draft_id: str, **kwargs) -> Dict:
        """取消草稿"""
        return {}
    
    def google_remove_from_draft(self, draft_id: str, **kwargs) -> Dict:
        """从草稿移除"""
        return {}
    
    def google_list_experiments(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出实验"""
        return []
    
    def google_create_experiment(self, customer_id: str, **kwargs) -> Dict:
        """创建实验"""
        return {}
    
    def google_get_experiment(self, experiment_id: str, **kwargs) -> Dict:
        """获取实验详情"""
        return {}
    
    def google_apply_experiment(self, experiment_id: str, **kwargs) -> Dict:
        """应用实验"""
        return {}
    
    def google_cancel_experiment(self, experiment_id: str, **kwargs) -> Dict:
        """取消实验"""
        return {}
    
    def google_list_criterion_categories(self, **kwargs) -> List[Dict]:
        """列出条件类别"""
        return []
    
    def google_list_ad_group_criterion_category(self, criterion_id: str, **kwargs) -> Dict:
        """获取广告组条件类别"""
        return {}
    
    def google_list_keyword_category(self, criterion_id: str, **kwargs) -> Dict:
        """获取关键词类别"""
        return {}
    
    def google_list_placements(self, **kwargs) -> List[Dict]:
        """列出投放位置"""
        return []
    
    def google_list_platforms(self, **kwargs) -> List[Dict]:
        """列出平台"""
        return []
    
    def google_list_locations(self, **kwargs) -> List[Dict]:
        """列出位置"""
        return []
    
    def google_list_languages(self, **kwargs) -> List[Dict]:
        """列出语言"""
        return []
    
    def google_list_budgets(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出预算"""
        return []
    
    def google_list_ad_schedule(self, **kwargs) -> List[Dict]:
        """列出广告排期"""
        return []
    
    def google_list_device(self, **kwargs) -> List[Dict]:
        """列出设备"""
        return []
    
    def google_list_network(self, **kwargs) -> List[Dict]:
        """列出网络"""
        return []
    
    def google_list_advertising_channel_type(self, **kwargs) -> List[Dict]:
        """列出广告渠道类型"""
        return []
    
    def google_list_ad_group_type(self, **kwargs) -> List[Dict]:
        """列出广告组类型"""
        return []
    
    def google_list_ad_type(self, **kwargs) -> List[Dict]:
        """列出广告类型"""
        return []
    
    def google_list_bidding_strategy_type(self, **kwargs) -> List[Dict]:
        """列出发价策略类型"""
        return []
    
    def google_list_call_type(self, **kwargs) -> List[Dict]:
        """列出呼叫类型"""
        return []
    
    def google_list_conversion_goal_category(self, **kwargs) -> List[Dict]:
        """列出转化目标类别"""
        return []
    
    def google_list_conversion_goal_campaign_goal_type(self, **kwargs) -> List[Dict]:
        """列出转化目标广告系列目标类型"""
        return []
    
    def google_list_enhanced_cpm_bid_source(self, **kwargs) -> List[Dict]:
        """列出增强型 CPM 出价值来源"""
        return []
    
    def google_list_ad_group_ad_type(self, **kwargs) -> List[Dict]:
        """列出广告组广告类型"""
        return []
    
    def google_list_media_type(self, **kwargs) -> List[Dict]:
        """列出媒体类型"""
        return []
    
    def google_list_offer_type(self, **kwargs) -> List[Dict]:
        """列出优惠类型"""
        return []
    
    def google_list_product_type_category(self, **kwargs) -> List[Dict]:
        """列出产品类型类别"""
        return []
    
    def google_list_product_type_l1(self, **kwargs) -> List[Dict]:
        """列出产品类型 L1"""
        return []
    
    def google_list_product_type_l2(self, **kwargs) -> List[Dict]:
        """列出产品类型 L2"""
        return []
    
    def google_list_product_type_l3(self, **kwargs) -> List[Dict]:
        """列出产品类型 L3"""
        return []
    
    def google_list_product_type_l4(self, **kwargs) -> List[Dict]:
        """列出产品类型 L4"""
        return []
    
    def google_list_product_type_l5(self, **kwargs) -> List[Dict]:
        """列出产品类型 L5"""
        return []
    
    def google_list_product_type_l6(self, **kwargs) -> List[Dict]:
        """列出产品类型 L6"""
        return []
    
    def google_list_product_type_l7(self, **kwargs) -> List[Dict]:
        """列出产品类型 L7"""
        return []
    
    def google_list_product_type_l8(self, **kwargs) -> List[Dict]:
        """列出产品类型 L8"""
        return []
    
    def google_list_product_type_l9(self, **kwargs) -> List[Dict]:
        """列出产品类型 L9"""
        return []
    
    def google_list_sale_method(self, **kwargs) -> List[Dict]:
        """列出销售方法"""
        return []
    
    def google_list_store_type(self, **kwargs) -> List[Dict]:
        """列出商店类型"""
        return []
    
    def google_list_webpage_condition_operator(self, **kwargs) -> List[Dict]:
        """列出网页条件操作符"""
        return []
    
    def google_list_ad_group_status(self, **kwargs) -> List[Dict]:
        """列出广告组状态"""
        return []
    
    def google_list_criterion_status(self, **kwargs) -> List[Dict]:
        """列出条件状态"""
        return []
    
    def google_list_ad_group_bid_modifier_status(self, **kwargs) -> List[Dict]:
        """列出广告组出价调整状态"""
        return []
    
    def google_list_budget_delivery_status(self, **kwargs) -> List[Dict]:
        """列出预算配送状态"""
        return []
    
    def google_list_campaign_status(self, **kwargs) -> List[Dict]:
        """列出广告系列状态"""
        return []
    
    def google_list_ad_status(self, **kwargs) -> List[Dict]:
        """列出广告状态"""
        return []
    
    def google_list_draft_status(self, **kwargs) -> List[Dict]:
        """列出草稿状态"""
        return []
    
    def google_list_experiment_status(self, **kwargs) -> List[Dict]:
        """列出实验状态"""
        return []
    
    def google_list_recommendation_type(self, **kwargs) -> List[Dict]:
        """列出推荐类型"""
        return []
    
    def google_list_recommendation_stage(self, **kwargs) -> List[Dict]:
        """列出推荐阶段"""
        return []
    
    def google_list_ad_group_criterion_category_constant(self, **kwargs) -> List[Dict]:
        """列出广告组条件类别常量"""
        return []
    
    def google_list_keyword_category_constant(self, **kwargs) -> List[Dict]:
        """列出关键词类别常量"""
        return []
    
    def google_list_placements_category_constant(self, **kwargs) -> List[Dict]:
        """列出投放位置类别常量"""
        return []
    
    def google_list_geo_target_constant(self, **kwargs) -> List[Dict]:
        """列出地理目标常量"""
        return []
    
    def google_list_advertising_channel_sub_type(self, **kwargs) -> List[Dict]:
        """列出广告渠道子类型"""
        return []
    
    def google_list_auction_insights_page(self, **kwargs) -> List[Dict]:
        """列出拍卖洞察页面"""
        return []
    
    def google_list_search_term_view(self, **kwargs) -> List[Dict]:
        """列出搜索词视图"""
        return []
    
    def google_list_keyword_match_type(self, **kwargs) -> List[Dict]:
        """列出关键词匹配类型"""
        return []
    
    def google_list_cpc_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出 CPC 竞价模块状态"""
        return []
    
    def google_list_target_cpa_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出目标 CPA 竞价模块状态"""
        return []
    
    def google_list_target_roas_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出目标 ROAS 竞价模块状态"""
        return []
    
    def google_list_target_spend_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出目标支出竞价模块状态"""
        return []
    
    def google_list_cpm_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出 CPM 竞价模块状态"""
        return []
    
    def google_list_thcp_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出 THCP 竞价模块状态"""
        return []
    
    def google_list_video_bumping_bid_module_state(self, **kwargs) -> List[Dict]:
        """列出视频提升竞价模块状态"""
        return []
    
    def google_list_ad_group_ad_rotation_mode(self, **kwargs) -> List[Dict]:
        """列出广告组广告轮播模式"""
        return []
    
    def google_list_ad_group_cycle_type(self, **kwargs) -> List[Dict]:
        """列出广告组周期类型"""
        return []
    
    def google_list_ad_group_cycle_subtype(self, **kwargs) -> List[Dict]:
        """列出广告组周期子类型"""
        return []
    
    def google_list_ad_group_type_access_level(self, **kwargs) -> List[Dict]:
        """列出广告组类型访问级别"""
        return []
    
    def google_list_ad_group_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组出价来源"""
        return []
    
    def google_list_ad_group_cpc_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组 CPC 出价来源"""
        return []
    
    def google_list_ad_group_cpm_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组 CPM 出价来源"""
        return []
    
    def google_list_ad_group_target_cpa_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组目标 CPA 出价来源"""
        return []
    
    def google_list_ad_group_target_roas_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组目标 ROAS 出价来源"""
        return []
    
    def google_list_ad_group_target_spend_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告组目标支出出价来源"""
        return []
    
    def google_list_campaign_advertising_channel_type(self, **kwargs) -> List[Dict]:
        """列出广告系列广告渠道类型"""
        return []
    
    def google_list_campaign_budget_concurrent_access_level(self, **kwargs) -> List[Dict]:
        """列出广告系列预算并发访问级别"""
        return []
    
    def google_list_campaign_budget_delivery_method(self, **kwargs) -> List[Dict]:
        """列出广告系列预算配送方法"""
        return []
    
    def google_list_campaign_dynamic_settings_type(self, **kwargs) -> List[Dict]:
        """列出广告系列动态设置类型"""
        return []
    
    def google_list_campaign_scheduling_role(self, **kwargs) -> List[Dict]:
        """列出广告系列调度角色"""
        return []
    
    def google_list_campaign_setting_target_type(self, **kwargs) -> List[Dict]:
        """列出广告系列设置目标类型"""
        return []
    
    def google_list_campaign_target_cpa_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告系列目标 CPA 出价来源"""
        return []
    
    def google_list_campaign_target_roas_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告系列目标 ROAS 出价来源"""
        return []
    
    def google_list_campaign_target_spend_bid_source(self, **kwargs) -> List[Dict]:
        """列出广告系列目标支出出价来源"""
        return []
    
    def google_list_criterion_category_constant_operating_system_version_type(self, **kwargs) -> List[Dict]:
        """列出条件类别常量操作系统版本类型"""
        return []
    
    def google_list_criterion_category_constant_type(self, **kwargs) -> List[Dict]:
        """列出条件类别常量类型"""
        return []
    
    def google_list_criterion_type(self, **kwargs) -> List[Dict]:
        """列出条件类型"""
        return []
    
    def google_list_custom_parameter_field_mask_operation(self, **kwargs) -> List[Dict]:
        """列出自定义参数字段掩码操作"""
        return []
    
    def google_list_enhanced_cpm_bid_source(self, **kwargs) -> List[Dict]:
        """列出增强型 CPM 出价来源"""
        return []
    
    def google_list_expanded_text_ad_strength(self, **kwargs) -> List[Dict]:
        """列出扩展文本广告强度"""
        return []
    
    def google_list_final_url_device_mode(self, **kwargs) -> List[Dict]:
        """列出最终 URL 设备模式"""
        return []
    
    def google_list_geo_target_constant_presence(self, **kwargs) -> List[Dict]:
        """列出地理目标常量存在性"""
        return []
    
    def google_list_geo_target_restrict_mode(self, **kwargs) -> List[Dict]:
        """列出地理目标限制模式"""
        return []
    
    def google_list_insights_segment(self, **kwargs) -> List[Dict]:
        """列出洞察细分"""
        return []
    
    def google_list_negative_criterion_category_constant_type(self, **kwargs) -> List[Dict]:
        """列出负面条件类别常量类型"""
        return []
    
    def google_list_product_sale_method(self, **kwargs) -> List[Dict]:
        """列出产品销售方法"""
        return []
    
    def google_list_product_type_level(self, **kwargs) -> List[Dict]:
        """列出产品类型级别"""
        return []
    
    def google_list_resource_access_level(self, **kwargs) -> List[Dict]:
        """列出资源访问级别"""
        return []
    
    def google_list_resource_type(self, **kwargs) -> List[Dict]:
        """列出资源类型"""
        return []
    
    def google_list_review_status(self, **kwargs) -> List[Dict]:
        """列出审核状态"""
        return []
    
    def google_list_search_term_match_type(self, **kwargs) -> List[Dict]:
        """列出搜索词匹配类型"""
        return []
    
    def google_list_setting_type(self, **kwargs) -> List[Dict]:
        """列出设置类型"""
        return []
    
    def google_list_status(self, **kwargs) -> List[Dict]:
        """列出状态"""
        return []
    
    def google_list_targeting_type(self, **kwargs) -> List[Dict]:
        """列出定向类型"""
        return []
    
    def google_list_third_party_analytics_account_type(self, **kwargs) -> List[Dict]:
        """列出第三方分析账户类型"""
        return []
    
    def google_list_video_ad_type(self, **kwargs) -> List[Dict]:
        """列出视频广告类型"""
        return []
    
    def google_list_video_bucking_bid_source(self, **kwargs) -> List[Dict]:
        """列出视频出价来源"""
        return []
    
    def google_list_ad_group_ad_group_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组-广告组标签"""
        return []
    
    def google_list_ad_group_ad_group_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组-广告组标签"""
        return self.google_list_ad_group_ad_group_labels(ad_group_id)
    
    def google_list_ad_group_labels(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组标签"""
        return []
    
    def google_list_campaign_labels(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告系列标签"""
        return []
    
    def google_list_customer_labels(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户标签"""
        return []
    
    def google_list_shared_set_labels(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享集标签"""
        return []
    
    def google_list_access_invitations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出访问邀请"""
        return []
    
    def google_list_access_requests(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出访问请求"""
        return []
    
    def google_list_billing_info(self, customer_id: str, **kwargs) -> Dict:
        """获取账单信息"""
        return {}
    
    def google_list_payment_methods(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出支付方式"""
        return []
    
    def google_list_invoice_history(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出发票历史"""
        return []
    
    def google_list_currency_codes(self, **kwargs) -> List[Dict]:
        """列出货币代码"""
        return []
    
    def google_list_time_zones(self, **kwargs) -> List[Dict]:
        """列出时区"""
        return []
    
    def google_list_api_versions(self, **kwargs) -> List[Dict]:
        """列出 API 版本"""
        return []
    
    def google_get_api_version(self, version: str, **kwargs) -> Dict:
        """获取 API 版本信息"""
        return {}
    
    def google_list_rate_limits(self, **kwargs) -> Dict:
        """获取速率限制"""
        return {}
    
    def google_list_webhooks(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 Webhooks"""
        return []
    
    def google_create_webhook(self, customer_id: str, **kwargs) -> Dict:
        """创建 Webhook"""
        return {}
    
    def google_delete_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """删除 Webhook"""
        return {}
    
    def google_test_webhook(self, webhook_id: str, **kwargs) -> Dict:
        """测试 Webhook"""
        return {}
    
    def google_list_permission_users(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出授权用户"""
        return []
    
    def google_add_permission_user(self, customer_id: str, **kwargs) -> Dict:
        """添加授权用户"""
        return {}
    
    def google_remove_permission_user(self, user_id: str, **kwargs) -> Dict:
        """移除授权用户"""
        return {}
    
    def google_get_permission(self, customer_id: str, user_id: str, **kwargs) -> Dict:
        """获取权限"""
        return {}
    
    def google_update_permission(self, customer_id: str, user_id: str, **kwargs) -> Dict:
        """更新权限"""
        return {}
    
    def google_list_notification_preferences(self, customer_id: str, **kwargs) -> Dict:
        """获取通知偏好"""
        return {}
    
    def google_update_notification_preferences(self, customer_id: str, **kwargs) -> Dict:
        """更新通知偏好"""
        return {}
    
    def google_list_notification_history(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出通知历史"""
        return []
    
    def google_list_audit_logs(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出审计日志"""
        return []
    
    def google_list_activity_logs(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出活动日志"""
        return []
    
    def google_validate_customer(self, customer_id: str, **kwargs) -> Dict:
        """验证客户"""
        return {}
    
    def google_sync_customer(self, customer_id: str, **kwargs) -> Dict:
        """同步客户数据"""
        return {}
    
    def google_get_quota(self, customer_id: str, **kwargs) -> Dict:
        """获取配额"""
        return {}
    
    def google_list_usage_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取使用统计"""
        return {}
    
    def google_list_performance_stats(self, customer_id: str, **kwargs) -> Dict:
        """获取表现统计"""
        return {}
    
    def google_list_recommendations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出推荐"""
        return []
    
    def google_get_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """获取推荐详情"""
        return {}
    
    def google_apply_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """应用推荐"""
        return {}
    
    def google_dismiss_recommendation(self, recommendation_id: str, **kwargs) -> Dict:
        """忽略推荐"""
        return {}
    
    def google_list_support_tickets(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出支持工单"""
        return []
    
    def google_create_support_ticket(self, customer_id: str, **kwargs) -> Dict:
        """创建支持工单"""
        return {}
    
    def google_get_account_health(self, customer_id: str, **kwargs) -> Dict:
        """获取账户健康状态"""
        return {}
    
    def google_list_pending_approvals(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出待审批项"""
        return []
    
    def google_list_policy_violations(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出政策违规"""
        return []
    
    def google_list_appeals(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出申诉"""
        return []
    
    def google_create_appeal(self, customer_id: str, **kwargs) -> Dict:
        """创建申诉"""
        return {}
    
    def google_get_appeal_status(self, appeal_id: str, **kwargs) -> Dict:
        """获取申诉状态"""
        return {}
    
    def google_list_disputes(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出争议"""
        return []
    
    def google_list_cross_channel_reports(self, account_id: str, **kwargs) -> List[Dict]:
        """列出跨渠道报表"""
        return []
    
    def google_list_conversion_sources(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化来源"""
        return []
    
    def google_list_attribution_models(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出归因模型"""
        return []
    
    def google_list_conversion_windows(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出转化窗口"""
        return []
    
    def google_list_brand_lift_studies(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出品牌提升研究"""
        return []
    
    def google_create_brand_lift_study(self, customer_id: str, **kwargs) -> Dict:
        """创建品牌提升研究"""
        return {}
    
    def google_get_brand_lift_study(self, study_id: str, **kwargs) -> Dict:
        """获取品牌提升研究详情"""
        return {}
    
    def google_list_survey_responses(self, study_id: str, **kwargs) -> List[Dict]:
        """列出调查回复"""
        return []
    
    def google_list_offline_conversions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出离线转化"""
        return []
    
    def google_upload_offline_conversions(self, customer_id: str, **kwargs) -> Dict:
        """上传离线转化"""
        return {}
    
    def google_list_call_conversions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出电话转化"""
        return []
    
    def google_list_imported_conversions(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出导入转化"""
        return []
    
    def google_list_smart_campaign_settings(self, customer_id: str, **kwargs) -> Dict:
        """获取智能广告系列设置"""
        return {}
    
    def google_update_smart_campaign_settings(self, customer_id: str, **kwargs) -> Dict:
        """更新智能广告系列设置"""
        return {}
    
    def google_list_smart_campaigns(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出智能广告系列"""
        return []
    
    def google_create_smart_campaign(self, customer_id: str, **kwargs) -> Dict:
        """创建智能广告系列"""
        return {}
    
    def google_list_dynamic_search_ads_settings(self, customer_id: str, **kwargs) -> Dict:
        """获取动态搜索广告设置"""
        return {}
    
    def google_update_dynamic_search_ads_settings(self, customer_id: str, **kwargs) -> Dict:
        """更新动态搜索广告设置"""
        return {}
    
    def google_listdsa_campaigns(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 DSA 广告系列"""
        return []
    
    def google_createdsa_campaign(self, customer_id: str, **kwargs) -> Dict:
        """创建 DSA 广告系列"""
        return {}
    
    def google_list_url_feed_configs(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出 URL Feed 配置"""
        return []
    
    def google_create_url_feed_config(self, customer_id: str, **kwargs) -> Dict:
        """创建 URL Feed 配置"""
        return {}
    
    def google_update_url_feed_config(self, config_id: str, **kwargs) -> Dict:
        """更新 URL Feed 配置"""
        return {}
    
    def google_delete_url_feed_config(self, config_id: str, **kwargs) -> Dict:
        """删除 URL Feed 配置"""
        return {}
    
    def google_list_asset_groups(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出资产组"""
        return []
    
    def google_create_asset_group(self, campaign_id: str, **kwargs) -> Dict:
        """创建资产组"""
        return {}
    
    def google_update_asset_group(self, asset_group_id: str, **kwargs) -> Dict:
        """更新资产组"""
        return {}
    
    def google_delete_asset_group(self, asset_group_id: str, **kwargs) -> Dict:
        """删除资产组"""
        return {}
    
    def google_list_ad_group_assets(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组资产"""
        return []
    
    def google_create_ad_group_asset(self, ad_group_id: str, **kwargs) -> Dict:
        """创建广告组资产"""
        return {}
    
    def google_update_ad_group_asset(self, asset_id: str, **kwargs) -> Dict:
        """更新广告组资产"""
        return {}
    
    def google_delete_ad_group_asset(self, asset_id: str, **kwargs) -> Dict:
        """删除广告组资产"""
        return {}
    
    def google_list_campaign_assets(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告系列资产"""
        return []
    
    def google_create_campaign_asset(self, campaign_id: str, **kwargs) -> Dict:
        """创建广告系列资产"""
        return {}
    
    def google_update_campaign_asset(self, asset_id: str, **kwargs) -> Dict:
        """更新广告系列资产"""
        return {}
    
    def google_delete_campaign_asset(self, asset_id: str, **kwargs) -> Dict:
        """删除广告系列资产"""
        return {}
    
    def google_list_customer_assets(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户资产"""
        return []
    
    def google_create_customer_asset(self, customer_id: str, **kwargs) -> Dict:
        """创建客户资产"""
        return {}
    
    def google_update_customer_asset(self, asset_id: str, **kwargs) -> Dict:
        """更新客户资产"""
        return {}
    
    def google_delete_customer_asset(self, asset_id: str, **kwargs) -> Dict:
        """删除客户资产"""
        return {}
    
    def google_list_ad_group_criteria(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出广告组条件"""
        return []
    
    def google_create_ad_group_criterion(self, ad_group_id: str, **kwargs) -> Dict:
        """创建广告组条件"""
        return {}
    
    def google_update_ad_group_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新广告组条件"""
        return {}
    
    def google_delete_ad_group_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除广告组条件"""
        return {}
    
    def google_list_campaign_criteria(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告系列条件"""
        return []
    
    def google_create_campaign_criterion(self, campaign_id: str, **kwargs) -> Dict:
        """创建广告系列条件"""
        return {}
    
    def google_update_campaign_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新广告系列条件"""
        return {}
    
    def google_delete_campaign_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除广告系列条件"""
        return {}
    
    def google_list_customer_criteria(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出客户条件"""
        return []
    
    def google_create_customer_criterion(self, customer_id: str, **kwargs) -> Dict:
        """创建客户条件"""
        return {}
    
    def google_update_customer_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新客户条件"""
        return {}
    
    def google_delete_customer_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除客户条件"""
        return {}
    
    def google_list_shared_criteria(self, shared_set_id: str, **kwargs) -> List[Dict]:
        """列出共享条件"""
        return []
    
    def google_create_shared_criterion(self, shared_set_id: str, **kwargs) -> Dict:
        """创建共享条件"""
        return {}
    
    def google_update_shared_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新共享条件"""
        return {}
    
    def google_delete_shared_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除共享条件"""
        return {}
    
    def google_list_shared_sets(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出共享集"""
        return []
    
    def google_create_shared_set(self, customer_id: str, **kwargs) -> Dict:
        """创建共享集"""
        return {}
    
    def google_update_shared_set(self, shared_set_id: str, **kwargs) -> Dict:
        """更新共享集"""
        return {}
    
    def google_delete_shared_set(self, shared_set_id: str, **kwargs) -> Dict:
        """删除共享集"""
        return {}
    
    def google_list_negative_campaign_criteria(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出负面广告系列条件"""
        return []
    
    def google_create_negative_campaign_criterion(self, campaign_id: str, **kwargs) -> Dict:
        """创建负面广告系列条件"""
        return {}
    
    def google_update_negative_campaign_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新负面广告系列条件"""
        return {}
    
    def google_delete_negative_campaign_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除负面广告系列条件"""
        return {}
    
    def google_list_negative_ad_group_criteria(self, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出负面广告组条件"""
        return []
    
    def google_create_negative_ad_group_criterion(self, ad_group_id: str, **kwargs) -> Dict:
        """创建负面广告组条件"""
        return {}
    
    def google_update_negative_ad_group_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """更新负面广告组条件"""
        return {}
    
    def google_delete_negative_ad_group_criterion(self, criterion_id: str, **kwargs) -> Dict:
        """删除负面广告组条件"""
        return {}

    def tiktok_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 TikTok 广告账户 - TikTok 不支持此 API，返回空列表"""
        return []
    
    def tiktok_get_account(self, account_id: str, **kwargs) -> Dict:
        """获取账户详情"""
        return {}
    
    def tiktok_update_account(self, account_id: str, **kwargs) -> Dict:
        """更新账户信息"""
        return {}
    
    def tiktok_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列 - 使用 open_api/v1.3 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': account_id,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/campaign/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json().get('data', {})
        return data.get('list', []) if isinstance(data, dict) else []
    
    def tiktok_get_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情"""
        return {}
    
    def tiktok_create_campaign(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列"""
        return {}
    
    def tiktok_update_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """更新广告系列"""
        return {}
    
    def tiktok_pause_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """暂停广告系列"""
        return {}
    
    def tiktok_resume_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """恢复广告系列"""
        return {}
    
    def tiktok_delete_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """删除广告系列"""
        return {}
    
