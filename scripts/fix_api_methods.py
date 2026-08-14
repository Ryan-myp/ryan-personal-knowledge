#!/usr/bin/env python3
"""
修复 ad_platform_api.py 中的查询接口
"""
import re

# 读取原文件
with open('scripts/ad_platform_api.py', 'r') as f:
    content = f.read()

# 1. 修复 TikTok 查询方法
tiktok_fixes = [
    # list_accounts - 这个端点不存在，返回空列表
    (r'''    def tiktok_list_accounts\(self, \*\*kwargs\) -> List\[Dict\]:
        """列出 TikTok 广告账户"""
        client = self.get_client\('tiktok'\)
        import requests
        headers = \{'Authorization': f'Bearer \{client\["access_token"\]\}'\}  # noqa
        resp = requests.get\(f'\{client\["base_url"\]\}/ads/account/', headers=headers\)
        return resp.json\(\)\.get\('data', \[\]\)''',
     '''    def tiktok_list_accounts(self, **kwargs) -> List[Dict]:
        """列出 TikTok 广告账户 - 注意: TikTok 没有直接列出账户的 API，返回空列表"""
        # TikTok 不支持通过 API 列出 advertiser，需要已知 advertiser_id
        return []'''),
    
    # list_adgroups - 修正端点
    (r'''    def tiktok_list_adgroups\(self, campaign_id: str, \*\*kwargs\) -> List\[Dict\]:
        """列出广告组"""
        client = self.get_client\('tiktok'\)
        import requests
        headers = \{'Authorization': f'Bearer \{client\["access_token"\]\}'\}
        params = \{'campaign_id': campaign_id\}
        resp = requests.get\(f'\{client\["base_url"\]\}/ads/adgroup/', headers=headers, params=params\)
        return resp.json\(\)\.get\('data', \[\]\)''',
     '''    def tiktok_list_adgroups(self, advertiser_id: str, campaign_id: str, **kwargs) -> List[Dict]:
        """列出广告组 - 使用 open_api/v1.3 端点"""
        import requests
        token = self.credentials.get('tiktok', {}).get('access_token', '')
        headers = {'Access-Token': token}
        import json as json_lib
        params = {
            'advertiser_id': advertiser_id,
            'filtering': json_lib.dumps([{'field': 'campaign_id', 'operator': 'eq', 'values': [campaign_id]}]),
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 20)
        }
        url = 'https://business-api.tiktok.com/open_api/v1.3/adgroup/get/'
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json().get('data', {})
        return data.get('list', []) if isinstance(data, dict) else []'''),
    
    # list_ads - 修正端点
    (r'''    def tiktok_list_ads\(self, adgroup_id: str, \*\*kwargs\) -> List\[Dict\]:
        """列出广告创意"""
        client = self.get_client\('tiktok'\)
        import requests
        headers = \{'Authorization': f'Bearer \{client\["access_token"\]\}'\}
        params = \{'adgroup_id': adgroup_id\}
        resp = requests.get\(f'\{client\["base_url"\]\}/ads/ad/', headers=headers, params=params\)
        return resp.json\(\)\.get\('data', \[\]\)''',
     '''    def tiktok_list_ads(self, advertiser_id: str, adgroup_id: str = None, **kwargs) -> List[Dict]:
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
        return data.get('list', []) if isinstance(data, dict) else []'''),
]

print("正在修复 TikTok 查询方法...")
for old, new in tiktok_fixes:
    if old in content:
        content = content.replace(old, new)
        print(f"  ✅ 已修复")
    else:
        # 尝试使用正则
        match = re.search(old, content)
        if match:
            content = content[:match.start()] + new + content[match.end():]
            print(f"  ✅ 已修复 (正则)")
        else:
            print(f"  ⚠️ 未找到匹配")

# 保存修改
with open('scripts/ad_platform_api.py', 'w') as f:
    f.write(content)

print("\n✅ TikTok 方法修复完成")
print("\n注意: 需要进一步修复:")
print("  - Meta SDK 导入问题")
print("  - Google Ads 客户端配置")
print("  - DV360 服务账号配置")
