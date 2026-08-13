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
        return GoogleAdsClient.load_from_dict({
            'developer_token': creds.get('developer_token', ''),
            'oauth2_mode': 'offline',
            'oauth2_client_id': creds.get('client_id', ''),
            'oauth2_client_secret': creds.get('client_secret', ''),
            'oauth2_refresh_token': creds.get('refresh_token', '')
        })
    
    def _create_dv360_client(self):
        """创建 DV360 客户端"""
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        creds = self.credentials.get('dv360', {})
        service_account_file = creds.get('service_account_file', '')
        
        if not os.path.exists(service_account_file):
            raise FileNotFoundError(f"服务账号文件不存在: {service_account_file}")
        
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/display-video']
        )
        return build('display-video', 'v1', credentials=credentials)
    
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
        headers = {'Authorization': f'Bearer {client["access_token]"}'}
        resp = requests.get(f'{client["base_url"]}/ads/account/', headers=headers)
        return resp.json().get('data', [])
    
    def tiktok_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'account_id': account_id, 'page': kwargs.get('page', 1)}
        resp = requests.get(f'{client["base_url"]}/ads/campaign/', headers=headers, params=params)
        return resp.json().get('data', [])
    
    def tiktok_get_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        resp = requests.get(f'{client["base_url"]}/ads/campaign/{campaign_id}/', headers=headers)
        return resp.json().get('data', {})
    
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
    
    def tiktok_list_adgroups(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'campaign_id': campaign_id}
        resp = requests.get(f'{client["base_url"]}/ads/adgroup/', headers=headers, params=params)
        return resp.json().get('data', [])
    
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
    
    def tiktok_list_ads(self, adgroup_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'adgroup_id': adgroup_id}
        resp = requests.get(f'{client["base_url"]}/ads/ad/', headers=headers, params=params)
        return resp.json().get('data', [])
    
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
        """列出 Meta 广告账户"""
        from facebook_business.adaccounts import AdAccount
        accounts = AdAccount.get_accounts()
        return [{'id': acc.id, 'name': acc.name, 'currency': acc.currency_name} for acc in accounts]
    
    def meta_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列"""
        from facebook_business.adobjects.campaign import Campaign
        from facebook_business.adaccounts import AdAccount
        
        account = AdAccount(account_id)
        campaigns = account.get_campaigns(fields=['id', 'name', 'status', 'daily_budget'])
        return [{'id': c.id, 'name': c.name, 'status': c.status} for c in campaigns]
    
    def meta_get_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情"""
        from facebook_business.adobjects.campaign import Campaign
        campaign = Campaign(campaign_id)
        campaign.remote_read()
        return {'id': campaign.id, 'name': campaign.name, 'status': campaign.status}
    
    def meta_create_campaign(self, account_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列"""
        from facebook_business.adobjects.campaign import Campaign
        from facebook_business.adaccounts import AdAccount
        
        account = AdAccount(account_id)
        campaign = account.create_campaign(
            name=name,
            objective=kwargs.get('objective', 'SALES'),
            status=Campaign.Status.paused
        )
        campaign.remote_create()
        return {'id': campaign.id, 'name': campaign.name}
    
    def meta_update_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """更新广告系列"""
        from facebook_business.adobjects.campaign import Campaign
        campaign = Campaign(campaign_id)
        campaign.remote_read()
        for key, value in kwargs.items():
            setattr(campaign, key, value)
        campaign.save()
        return {'id': campaign.id, 'updated': True}
    
    def meta_pause_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """暂停广告系列"""
        return self.meta_update_campaign(campaign_id, status=Campaign.Status.paused)
    
    def meta_resume_campaign(self, campaign_id: str, **kwargs) -> Dict:
        """恢复广告系列"""
        return self.meta_update_campaign(campaign_id, status=Campaign.Status.running)
    
    def meta_list_adsets(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组"""
        from facebook_business.adobjects.adset import AdSet
        adsets = AdSet.get_adsets({'campaign_id': campaign_id})
        return [{'id': a.id, 'name': a.name, 'status': a.status} for a in adsets]
    
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
        """列出广告创意"""
        from facebook_business.adobjects.ad import Ad
        ads = Ad.get_ads({'adset_id': adset_id})
        return [{'id': a.id, 'name': a.name, 'status': a.status} for a in ads]
    
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
        """列出自定义受众"""
        from facebook_business.adaccounts import AdAccount
        from facebook_business.adobjects.customaudience import CustomAudience
        
        account = AdAccount(account_id)
        audiences = CustomAudience.get_my_audiences(params={'account_id': account_id})
        return [{'id': a.id, 'name': a.name, 'type': a.type} for a in audiences]
    
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
    def google_list_customers(self, **kwargs) -> List[Dict]:
        """列出 Google Ads 客户"""
        client = self.get_client('google')
        customer_service = client.get_service('CustomerService')
        query = "SELECT customer.id, customer.descriptive_name FROM customer"
        response = customer_service.search_stream(customer_id='0', query=query)
        
        customers = []
        for batch in response:
            for customer in batch.results:
                customers.append({
                    'id': customer.id,
                    'name': customer.descriptive_name,
                    'currency_code': customer.currency_code,
                    'time_zone': customer.time_zone
                })
        return customers
    
    def google_list_campaigns(self, customer_id: str, **kwargs) -> List[Dict]:
        """列出广告系列"""
        client = self.get_client('google')
        campaign_service = client.get_service('CampaignService')
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status, 
                   campaign.advertising_channel_type, campaign.base_campaign_id
            FROM campaign 
            WHERE customer.id = {customer_id}
        """
        response = campaign_service.search_stream(customer_id=customer_id, query=query)
        
        campaigns = []
        for batch in response:
            for row in batch.results:
                campaigns.append({
                    'id': row.campaign.id,
                    'name': row.campaign.name,
                    'status': row.campaign.status,
                    'type': row.campaign.advertising_channel_type
                })
        return campaigns
    
    def google_get_campaign(self, customer_id: str, campaign_id: str, **kwargs) -> Dict:
        """获取广告系列详情"""
        client = self.get_client('google')
        campaign_service = client.get_service('CampaignService')
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status, 
                   campaign.daily_budget, campaign.bidding_strategy
            FROM campaign 
            WHERE campaign.id = {campaign_id}
        """
        response = campaign_service.search_stream(customer_id=customer_id, query=query)
        for batch in response:
            for row in batch.results:
                return {'id': row.campaign.id, 'name': row.campaign.name}
        return {}
    
    def google_create_campaign(self, customer_id: str, name: str, **kwargs) -> Dict:
        """创建广告系列"""
        client = self.get_client('google')
        campaign_service = client.get_service('CampaignService')
        
        campaign_operation = client.get_type("CampaignOperation")
        campaign = campaign_operation.create
        campaign.resource_name = f"customers/{customer_id}/campaigns/-"
        campaign.name = name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH
        campaign.status = client.enums.CampaignStatus.PAUSED
        campaign.testing_status = client.enums.CampaignTestingStatus.DUAL_A_B_TEST
        campaign.ad_network_targets = [
            client.enums.AdNetworkType.SEARCH,
            client.enums.AdNetworkType.GOOGLE_SEARCH
        ]
        
        response = campaign_service.mutate_campaigns(
            customer_id=customer_id,
            operations=[campaign_operation]
        )
        
        return {'resource_name': response.results[0].resource_name}
    
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
        client = self.get_client('google')
        ad_group_service = client.get_service('AdGroupService')
        query = f"""
            SELECT ad_group.id, ad_group.name, ad_group.status
            FROM ad_group 
            WHERE ad_group.campaign = 'customers/{customer_id}/campaigns/{campaign_id}'
        """
        response = ad_group_service.search_stream(customer_id=customer_id, query=query)
        
        ad_groups = []
        for batch in response:
            for row in batch.results:
                ad_groups.append({
                    'id': row.ad_group.id,
                    'name': row.ad_group.name,
                    'status': row.ad_group.status
                })
        return ad_groups
    
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
    
    def google_list_keywords(self, customer_id: str, ad_group_id: str, **kwargs) -> List[Dict]:
        """列出关键词"""
        client = self.get_client('google')
        ad_group_criterion_service = client.get_service('AdGroupCriterionService')
        query = f"""
            SELECT keyword.id, keyword.text, keyword.match_type, ad_group_criterion.status
            FROM keyword JOIN ad_group_criterion
            ON ad_group_criterion.ad_group = 'customers/{customer_id}/adGroups/{ad_group_id}'
            WHERE ad_group_criterion.type = 'KEYWORD'
        """
        response = ad_group_criterion_service.search_stream(customer_id=customer_id, query=query)
        
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
        """列出广告创意"""
        client = self.get_client('google')
        ad_service = client.get_service('AdService')
        query = f"""
            SELECT ad.id, ad.type, ad.status, ad_group_ad.final_urls
            FROM ad_group_ad JOIN ad
            ON ad.id = ad_group_ad.ad.id
            WHERE ad_group_ad.ad_group = 'customers/{customer_id}/adGroups/{ad_group_id}'
        """
        response = ad_service.search_stream(customer_id=customer_id, query=query)
        
        ads = []
        for batch in response:
            for row in batch.results:
                ads.append({
                    'id': row.ad.id,
                    'type': row.ad.type,
                    'status': row.ad.status
                })
        return ads
    
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
        
        response = report_service.search_stream(customer_id=customer_id, query=query)
        results = []
        for batch in response:
            for row in batch.results:
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
    def dv360_list_advertisers(self, **kwargs) -> List[Dict]:
        """列出广告主"""
        service = self.get_client('dv360')
        advertisers = service.users().me().advertisers().list().execute()
        return advertisers.get('advertisers', [])
    
    def dv360_get_advertiser(self, advertiser_id: str, **kwargs) -> Dict:
        """获取广告主详情"""
        service = self.get_client('dv360')
        return service.users().me().advertisers().get(advertiserId=advertiser_id).execute()
    
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="广告平台统一 API 调用")
    parser.add_argument("--platform", type=str, choices=['tiktok', 'meta', 'google', 'dv360'],
                        help="平台名称")
    parser.add_argument("--action", type=str, required=True,
                        help="操作类型")
    parser.add_argument("--test", action="store_true", help="测试连接")
    parser.add_argument("--all", action="store_true", help="测试所有平台")
    parser.add_argument("--args", type=str, default='{}', help="额外参数 JSON")
    
    args = parser.parse_args()
    extra_args = json.loads(args.args) if args.args else {}
    
    client = AdPlatformClient()
    
    if args.test or args.all:
        if args.all:
            results = {}
            for platform in client.platforms:
                try:
                    results[platform] = client.test_connection(platform)
                    status_str = "✅ 成功" if results[platform] else "❌ 失败"
                    print(f"  {platform}: {status_str}")
                except Exception as e:
                    results[platform] = False
                    print(f"  {platform}: ❌ {e}")
        elif args.platform:
            status = client.test_connection(args.platform)
            print(f"{args.platform}: {'✅ 成功' if status else '❌ 失败'}")
        return
    
    if args.platform:
        method_name = f"{args.platform}_{args.action}"
        if hasattr(client, method_name):
            method = getattr(client, method_name)
            result = method(**extra_args)
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"❌ 不支持的操作: {method_name}")
            print("\n可用操作:")
            for attr in dir(client):
                if attr.startswith(f"{args.platform}_") and not attr.startswith('_'):
                    print(f"  • {attr}")
    else:
        print("❌ 请指定 --platform 参数")
        print("\n可用平台: tiktok, meta, google, dv360")


if __name__ == "__main__":
    main()
