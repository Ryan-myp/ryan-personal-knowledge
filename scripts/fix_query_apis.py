#!/usr/bin/env python3
"""
系统性修复 ad_platform_api.py 中的查询接口
"""
import re

with open('scripts/ad_platform_api.py', 'r') as f:
    content = f.read()

print("=== 开始修复 API 方法 ===")
print()

# 1. 修复 TikTok list_campaigns
old = '''    def tiktok_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
        """列出广告系列"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'account_id': account_id, 'page': kwargs.get('page', 1)}
        resp = requests.get(f'{client["base_url"]}/ads/campaign/', headers=headers, params=params)
        return resp.json().get('data', [])'''

new = '''    def tiktok_list_campaigns(self, account_id: str, **kwargs) -> List[Dict]:
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
        return data.get('list', []) if isinstance(data, dict) else data'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 tiktok_list_campaigns")
else:
    print("⚠️  tiktok_list_campaigns 未找到（可能已修复）")

# 2. 修复 TikTok list_adgroups
old = '''    def tiktok_list_adgroups(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'campaign_id': campaign_id}
        resp = requests.get(f'{client["base_url"]}/ads/adgroup/', headers=headers, params=params)
        return resp.json().get('data', [])'''

new = '''    def tiktok_list_adgroups(self, advertiser_id: str, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组 - 使用 open_api/v1.3 端点"""
        import requests
        import json as json_lib
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        params = {
            'advertiser_id': advertiser_id,
            'filtering': json_lib.dumps([{'field': 'campaign_id', 'operator': 'eq', 'values': [campaign_id]}]),
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/adgroup/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json().get('data', {})
        return data.get('list', []) if isinstance(data, dict) else []'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 tiktok_list_adgroups")
else:
    print("⚠️  tiktok_list_adgroups 未找到（可能已修复）")

# 3. 修复 TikTok list_ads
old = '''    def tiktok_list_ads(self, adgroup_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        client = self.get_client('tiktok')
        import requests
        headers = {'Authorization': f'Bearer {client["access_token"]}'}
        params = {'adgroup_id': adgroup_id}
        resp = requests.get(f'{client["base_url"]}/ads/ad/', headers=headers, params=params)
        return resp.json().get('data', [])'''

new = '''    def tiktok_list_ads(self, advertiser_id: str, adgroup_id: str = None, **kwargs) -> List[Dict]:
        """列出广告创意 - 使用 open_api/v1.3 端点"""
        import requests
        import json as json_lib
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        
        filtering = []
        if adgroup_id:
            filtering.append({'field': 'adgroup_id', 'operator': 'eq', 'values': [adgroup_id]})
        
        params = {
            'advertiser_id': advertiser_id,
            'filtering': json_lib.dumps(filtering) if filtering else '{}',
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/ad/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json().get('data', {})
        return data.get('list', []) if isinstance(data, dict) else []'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 tiktok_list_ads")
else:
    print("⚠️  tiktok_list_ads 未找到（可能已修复）")

# 4. 修复 Meta list_accounts
old = '''    def meta_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 Meta 广告账户"""
        from facebook_business.adaccounts import AdAccount
        accounts = AdAccount.get_accounts()
        return [{'id': acc.id, 'name': acc.name, 'currency': acc.currency_name} for acc in accounts]'''

new = '''    def meta_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 Meta 广告账户 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = "https://graph.facebook.com/v19.0/acounts"
        params = {'access_token': token}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 meta_list_accounts")
else:
    print("⚠️  meta_list_accounts 未找到")

# 5. 修复 Meta list_adsets
old = '''    def meta_list_adsets(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组"""
        from facebook_business.adobjects.adset import AdSet
        adsets = AdSet.get_adsets({'campaign_id': campaign_id})
        return [{'id': a.id, 'name': a.name, 'status': a.status} for a in adsets]'''

new = '''    def meta_list_adsets(self, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{campaign_id}/adsets"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,status'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 meta_list_adsets")
else:
    print("⚠️  meta_list_adsets 未找到")

# 6. 修复 Meta list_ads
old = '''    def meta_list_ads(self, adset_id: str, **kwargs) -> List[Dict]:
        """列出广告创意"""
        from facebook_business.adobjects.ad import Ad
        ads = Ad.get_ads({'adset_id': adset_id})
        return [{'id': a.id, 'name': a.name, 'status': a.status} for a in ads]'''

new = '''    def meta_list_ads(self, adset_id: str, **kwargs) -> List[Dict]:
        """列出广告创意 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/{adset_id}/ads"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,status'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 meta_list_ads")
else:
    print("⚠️  meta_list_ads 未找到")

# 7. 修复 Meta list_audiences
old = '''    def meta_list_audiences(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自定义受众"""
        from facebook_business.adaccounts import AdAccount
        from facebook_business.adobjects.customaudience import CustomAudience
        
        account = AdAccount(account_id)
        audiences = CustomAudience.get_my_audiences(params={'account_id': account_id})
        return [{'id': a.id, 'name': a.name, 'type': a.type} for a in audiences]'''

new = '''    def meta_list_audiences(self, account_id: str, **kwargs) -> List[Dict]:
        """列出自定义受众 - 使用 Graph API 直接调用"""
        import requests
        token = self.credentials.get('meta', {}).get('access_token', '')
        url = f"https://graph.facebook.com/v19.0/act_{account_id}/customaudiences"
        params = {'access_token': token, 'limit': kwargs.get('limit', 20), 'fields': 'id,name,type'}
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        return data.get('data', [])'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 meta_list_audiences")
else:
    print("⚠️  meta_list_audiences 未找到")

# 8. 修复 Google Ads 客户端配置
old = '''        return GoogleAdsClient.load_from_dict({
            'developer_token': creds.get('developer_token', ''),
            'oauth2_mode': 'offline',
            'oauth2_client_id': creds.get('client_id', ''),
            'oauth2_client_secret': creds.get('client_secret', ''),
            'oauth2_refresh_token': creds.get('refresh_token', '')
        })'''

new = '''        from google.oauth2.credentials import Credentials
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
        )'''

if old in content:
    content = content.replace(old, new)
    print("✅ 修复 google client 配置")
else:
    print("⚠️  google client 配置未找到（可能已修复）")

# 保存修改
with open('scripts/ad_platform_api.py', 'w') as f:
    f.write(content)

print()
print("=" * 60)
print("✅ 所有修复完成！")
print("=" * 60)
