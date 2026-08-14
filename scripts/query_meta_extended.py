#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Marketing API 完整查询工具
支持: Campaign、Ad Set、Ad、Audience 等
注意: Catalog 和 Locations 需要额外的权限配置
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"
API_VERSION = "v19.0"


def load_credentials():
    """加载凭证配置"""
    if not CREDENTIALS_FILE.exists():
        print(f"❌ 凭证文件不存在: {CREDENTIALS_FILE}")
        sys.exit(1)
    
    with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_headers(access_token):
    """获取请求头"""
    return {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }


def get_accounts(config):
    """获取所有关联的 Ad Account"""
    access_token = config['meta']['access_token']
    headers = get_headers(access_token)
    
    print("📋 正在获取关联的 Ad Accounts...")
    url = "https://graph.facebook.com/v19.0/me"
    params = {'fields': 'accounts{name,id}', 'limit': 50}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        accounts = data.get('accounts', {}).get('data', [])
        print(f"✅ 找到 {len(accounts)} 个 Accounts")
        for acc in accounts[:10]:
            print(f"   • {acc.get('name', 'N/A')} (ID: {acc.get('id', 'N/A')})")
        return accounts
    else:
        print(f"❌ 获取 Accounts 失败: {response.status_code}")
        return []


def query_campaigns(config, campaign_id=None, limit=10):
    """查询 Campaigns"""
    access_token = config['meta']['access_token']
    headers = get_headers(access_token)
    
    results = {
        'campaigns': [],
        'adsets': [],
        'ads': []
    }
    
    print("=" * 70)
    print("📊 META CAMPAIGNS")
    print("=" * 70)
    print()
    
    # 获取 Accounts
    accounts = get_accounts(config)
    if not accounts:
        return results
    
    # 查询第一个账户的 Campaigns
    first_account = accounts[0].get('id')
    print(f"📋 正在查询 Account {first_account} 的 Campaigns...")
    campaigns_url = f"https://graph.facebook.com/{API_VERSION}/{first_account}/campaigns"
    params = {
        'access_token': access_token,
        'limit': limit,
        'fields': 'id,name,billing_event,budget_remaining,daily_budget,lifetime_budget,status,created_time'
    }
    response = requests.get(campaigns_url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        results['campaigns'] = data.get('data', [])
        print(f"✅ 找到 {len(results['campaigns'])} 个 Campaigns")
        for camp in results['campaigns'][:5]:
            status_emoji = "🟢" if camp.get('status') == 'ACTIVE' else "⏸️"
            print(f"   {status_emoji} {camp.get('name', 'N/A')} (ID: {camp.get('id', 'N/A')})")
    else:
        print(f"❌ 查询 Campaigns 失败: {response.status_code}")
        print(f"   {response.text[:200]}")
    
    print()
    
    # 如果指定了 campaign_id，查询详细层级
    if campaign_id and results['campaigns']:
        print(f"📋 正在查询 Campaign {campaign_id} 的详细层级...")
        
        # Ad Sets
        adsets_url = f"https://graph.facebook.com/{API_VERSION}/{campaign_id}/adsets"
        params = {'access_token': access_token, 'limit': limit}
        response = requests.get(adsets_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results['adsets'] = data.get('data', [])
            print(f"✅ 找到 {len(results['adsets'])} 个 Ad Sets")
        
        # Ads
        ads_url = f"https://graph.facebook.com/{API_VERSION}/{campaign_id}/ads"
        params = {'access_token': access_token, 'limit': limit}
        response = requests.get(ads_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results['ads'] = data.get('data', [])
            print(f"✅ 找到 {len(results['ads'])} 个 Ads")
    
    print()
    return results


def query_audiences(config, account_id=None, limit=10):
    """查询 Audiences"""
    access_token = config['meta']['access_token']
    headers = get_headers(access_token)
    
    results = {
        'custom_audiences': [],
        'lookalike_audiences': []
    }
    
    print("=" * 70)
    print("👥 META AUDIENCES")
    print("=" * 70)
    print()
    
    # 获取 Accounts
    accounts = get_accounts(config)
    if not accounts:
        return results
    
    # 使用指定的 Account 或第一个 Account
    target_account = account_id or accounts[0].get('id')
    
    print(f"📋 正在查询 Account {target_account} 的 Custom Audiences...")
    url = f"https://graph.facebook.com/{API_VERSION}/{target_account}/customaudiences"
    params = {
        'access_token': access_token,
        'limit': limit,
        'fields': 'id,name,subtype,count,description,retention_time_days'
    }
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        results['custom_audiences'] = data.get('data', [])
        print(f"✅ 找到 {len(results['custom_audiences'])} 个 Custom Audiences")
        for aud in results['custom_audiences'][:5]:
            print(f"   • {aud.get('name', 'N/A')}")
            print(f"     Type: {aud.get('subtype', 'N/A')}, ID: {aud.get('id', 'N/A')}")
    else:
        print(f"❌ 查询 Audiences 失败: {response.status_code}")
        print(f"   {response.text[:200]}")
    
    print()
    return results


def query_catalog(config, catalog_id=None, account_id=None):
    """查询 Catalog (需要 Commerce Manager 配置)"""
    access_token = config['meta']['access_token']
    headers = get_headers(access_token)
    
    results = {
        'catalogs': [],
        'products': [],
        'product_sets': [],
        'error': None
    }
    
    print("=" * 70)
    print("📦 META CATALOG & PRODUCTS")
    print("=" * 70)
    print()
    
    # 尝试获取 Catalogs
    accounts = get_accounts(config)
    if not accounts:
        return results
    
    target_account = account_id or accounts[0].get('id')
    
    print(f"📋 正在查询 Account {target_account} 的 Catalogs...")
    url = f"https://graph.facebook.com/{API_VERSION}/{target_account}/product_catalogs"
    params = {'access_token': access_token, 'limit': 10}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        results['catalogs'] = data.get('data', [])
        print(f"✅ 找到 {len(results['catalogs'])} 个 Catalogs")
        for cat in results['catalogs'][:5]:
            print(f"   • {cat.get('name', 'N/A')} (ID: {cat.get('id', 'N/A')})")
    else:
        error_msg = response.text[:200]
        results['error'] = f"Catalog API 不可用: {response.status_code}"
        print(f"⚠️ {results['error']}")
        print(f"   请确认: 1) 已配置 Commerce Manager  2) 已创建 Catalog")
    
    print()
    return results


def query_locations(config):
    """查询 Targeting Locations"""
    access_token = config['meta']['access_token']
    headers = get_headers(access_token)
    
    results = {
        'countries': [],
        'regions': [],
        'cities': [],
        'error': None
    }
    
    print("=" * 70)
    print("📍 META LOCATIONS")
    print("=" * 70)
    print()
    
    print("⚠️ 说明: Meta Targeting Locations API 需要额外配置")
    print("   建议在 DAP 界面查看地理位置选项")
    print()
    print(" Shopee 主要市场:")
    print("   • ID - Indonesia")
    print("   • TH - Thailand")
    print("   • VN - Vietnam")
    print("   • PH - Philippines")
    print("   • SG - Singapore")
    print("   • MY - Malaysia")
    print()
    
    results['error'] = "API 端点不可用，建议使用 DAP 界面"
    return results


def format_output(results, query_type):
    """格式化输出"""
    print()
    print("=" * 70)
    print("📄 原始 JSON 数据")
    print("=" * 70)
    print(json.dumps(results, indent=2, ensure_ascii=False))


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Meta Marketing API 查询工具')
    parser.add_argument('query_type', choices=['campaigns', 'audiences', 'catalog', 'locations', 'all'],
                       help='查询类型')
    parser.add_argument('--id', '-i', help='Campaign ID 或 Catalog ID')
    parser.add_argument('--account', '-a', help='Account ID (如 act_34877444)')
    parser.add_argument('--limit', '-l', type=int, default=10, help='限制数量')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_credentials()
    
    if 'meta' not in config:
        print("❌ Meta 配置不存在")
        sys.exit(1)
    
    # 执行查询
    if args.query_type == 'campaigns':
        results = query_campaigns(config, args.id, args.limit)
    elif args.query_type == 'audiences':
        results = query_audiences(config, args.account, args.limit)
    elif args.query_type == 'catalog':
        results = query_catalog(config, args.id, args.account)
    elif args.query_type == 'locations':
        results = query_locations(config)
    elif args.query_type == 'all':
        results = {
            'campaigns': query_campaigns(config, args.id, args.limit),
            'audiences': query_audiences(config, args.account, args.limit),
            'catalog': query_catalog(config, args.id, args.account),
            'locations': query_locations(config)
        }
    
    # 输出结果
    format_output(results, args.query_type)
    
    # 业务解读版
    print()
    print("=" * 70)
    print("📊 业务解读版")
    print("=" * 70)
    
    if args.query_type in ['campaigns', 'all']:
        print("\n📌 Campaigns:")
        camps = results.get('campaigns', {}).get('campaigns', [])
        for camp in camps[:5]:
            status = "🟢 ACTIVE" if camp.get('status') == 'ACTIVE' else "⏸️ PAUSED"
            print(f"   • {camp.get('name', 'N/A')} - {status}")
    
    if args.query_type in ['audiences', 'all']:
        print("\n📌 Audiences:")
        auds = results.get('audiences', {}).get('custom_audiences', [])
        for aud in auds[:5]:
            print(f"   • {aud.get('name', 'N/A')} ({aud.get('subtype', 'N/A')})")
    
    if args.query_type in ['catalog', 'all']:
        print("\n📌 Catalogs:")
        cats = results.get('catalog', {}).get('catalogs', [])
        if cats:
            for cat in cats[:5]:
                print(f"   • {cat.get('name', 'N/A')} (ID: {cat.get('id', 'N/A')})")
        else:
            print("   ⚠️ 未找到 Catalog (请确认 Commerce Manager 配置)")


if __name__ == "__main__":
    main()
