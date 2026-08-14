#!/usr/bin/env python3
"""Meta Marketing API 测试脚本"""
import requests
import json
import sys

def load_config():
    """加载凭证配置"""
    try:
        with open('config/ad_platform_credentials.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ 凭证文件不存在")
        sys.exit(1)

def test_meta_api(config):
    """测试 Meta API"""
    token = config['meta']['access_token']
    business_id = config['meta']['business_id']
    
    headers = {'Authorization': f'Bearer {token}'}
    
    print("=" * 60)
    print("🧪 Meta Marketing API 测试")
    print("=" * 60)
    print(f"Business ID: {business_id}")
    print()
    
    results = {}
    
    # 1. 测试用户信息
    print("📋 1. 获取用户信息...")
    try:
        resp = requests.get('https://graph.facebook.com/v18.0/me', 
                          headers=headers, params={'fields': 'id,name'})
        data = resp.json()
        if 'error' in data:
            print(f"   ❌ {data['error']}")
            results['user'] = False
        else:
            print(f"   ✅ {data.get('name')} (ID: {data.get('id')})")
            results['user'] = True
    except Exception as e:
        print(f"   ❌ {e}")
        results['user'] = False
    
    # 2. 获取广告账户
    print("📋 2. 获取广告账户...")
    try:
        resp = requests.get(f'https://graph.facebook.com/v18.0/{business_id}/adaccounts',
                          headers=headers, params={'limit': 10, 'fields': 'id,name,currency'})
        data = resp.json()
        if 'error' in data:
            print(f"   ❌ {data['error']}")
            results['accounts'] = False
        elif 'data' in data:
            accounts = data['data']
            print(f"   ✅ 共 {len(accounts)} 个账户")
            for acc in accounts:
                print(f"      • {acc.get('name', 'N/A')} (ID: {acc.get('id')})")
            results['accounts'] = True
            results['accounts_list'] = accounts
        else:
            print(f"   ⚠️ 响应异常: {data}")
            results['accounts'] = False
    except Exception as e:
        print(f"   ❌ {e}")
        results['accounts'] = False
    
    # 3. 获取广告系列
    print("📋 3. 获取广告系列...")
    try:
        if 'accounts_list' in results and results['accounts_list']:
            account_id = results['accounts_list'][0]['id']
            resp = requests.get(f'https://graph.facebook.com/v18.0/{account_id}/campaigns',
                              headers=headers, params={'limit': 5, 'fields': 'id,name,status,objective'})
            data = resp.json()
            if 'error' in data:
                print(f"   ❌ {data['error']}")
                results['campaigns'] = False
            elif 'data' in data:
                campaigns = data['data']
                print(f"   ✅ 共 {len(campaigns)} 个广告系列")
                for camp in campaigns:
                    print(f"      • {camp.get('name', 'N/A')} [{camp.get('status', 'N/A')}]")
                results['campaigns'] = True
            else:
                print(f"   ⚠️ 响应异常")
                results['campaigns'] = False
        else:
            print("   ⚠️ 跳过（无账户）")
            results['campaigns'] = False
    except Exception as e:
        print(f"   ❌ {e}")
        results['campaigns'] = False
    
    print()
    print("=" * 60)
    if all(results.values()):
        print("✅ 所有测试通过!")
    else:
        print("⚠️ 部分测试失败")
    print("=" * 60)
    
    return results

if __name__ == '__main__':
    config = load_config()
    test_meta_api(config)
