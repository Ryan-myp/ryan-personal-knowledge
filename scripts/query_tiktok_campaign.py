#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
TikTok Campaign 完整查询工具 - 双格式输出
支持原始数据(JSON) + 业务解读版(中文)
"""

import os
import sys
import json
import requests
from pathlib import Path

CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"


def load_credentials():
    if not CREDENTIALS_FILE.exists():
        print(f"❌ 凭证文件不存在: {CREDENTIALS_FILE}")
        sys.exit(1)
    with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_explanation(data):
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("📊 业务解读版")
    lines.append("=" * 70)
    lines.append("")
    
    campaign = data.get('campaign', {})
    ad_groups = data.get('ad_groups', {}).get('data', [])
    ads = data.get('ads', {}).get('data', [])
    creatives = data.get('creatives', {}).get('data', [])
    
    lines.append("📌 Campaign（广告系列）:")
    lines.append(f"   • 名称: {campaign.get('name', 'N/A')}")
    status = campaign.get('status', {}).get('status_name', 'N/A')
    status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
    lines.append(f"   • 状态: {status_emoji}")
    lines.append(f"   • 日预算: ${campaign.get('daily_budget', '0')}")
    lines.append(f"   • 创建时间: {campaign.get('create_time', 'N/A')}")
    lines.append("")
    
    lines.append("📌 Ad Group（广告组）:")
    for i, ad_group in enumerate(ad_groups[:5], 1):
        lines.append(f"   --- 广告组 {i} ---")
        lines.append(f"   • 名称: {ad_group.get('name', 'N/A')}")
        status = ad_group.get('status', {}).get('status_name', 'N/A')
        status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
        lines.append(f"   • 状态: {status_emoji}")
        lines.append(f"   • 日预算: ${ad_group.get('daily_budget', '0')}")
        targeting = ad_group.get('targeting', {})
        if targeting:
            locations = targeting.get('geo_locations', {}).get('locations', [])
            lines.append(f"   • 定向: {', '.join([str(l.get('location_id', '')) for l in locations[:3]])}")
        lines.append("")
    
    lines.append("📌 Ad（广告）:")
    for i, ad in enumerate(ads[:5], 1):
        lines.append(f"   --- 广告 {i} ---")
        lines.append(f"   • 名称: {ad.get('name', 'N/A')}")
        status = ad.get('status', {}).get('status_name', 'N/A')
        status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
        lines.append(f"   • 状态: {status_emoji}")
        lines.append("")
    
    lines.append("📌 Creative（广告素材）:")
    for i, creative in enumerate(creatives[:3], 1):
        lines.append(f"   --- 素材 {i} ---")
        lines.append(f"   • 名称: {creative.get('name', 'N/A')}")
        images = creative.get('images', [])
        videos = creative.get('videos', [])
        if images:
            lines.append(f"   • 图片数: {len(images)}")
        if videos:
            lines.append(f"   • 视频数: {len(videos)}")
    lines.append("")
    
    return "\n".join(lines)


def query_tiktok_campaign(config, campaign_id):
    access_token = config['tiktok']['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    result = {'campaign': {}, 'ad_groups': {}, 'ads': {}, 'creatives': {}}
    
    # 1. Campaign
    resp = requests.get(
        f'https://business-api.tiktok.com/portal/api/v20230728/campaigns/{campaign_id}',
        headers=headers, params={'fields': 'id,name,status,daily_budget,create_time'}
    )
    if resp.status_code == 200:
        data = resp.json()
        if 'data' in data:
            result['campaign'] = data['data']
    
    # 2. Ad Groups
    resp = requests.get(
        f'https://business-api.tiktok.com/portal/api/v20230728/campaigns/{campaign_id}/adgroups',
        headers=headers, params={'page_size': 10, 'fields': 'id,name,status,daily_budget,targeting'}
    )
    if resp.status_code == 200:
        data = resp.json()
        if 'data' in data:
            result['ad_groups'] = data
    
    # 3. Ads
    ads_list = []
    for adgroup in result['ad_groups'].get('data', []):
        adgroup_id = adgroup['id']
        resp = requests.get(
            f'https://business-api.tiktok.com/portal/api/v20230728/adgroups/{adgroup_id}/ads',
            headers=headers, params={'page_size': 10}
        )
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data:
                ads_list.extend(data['data'])
    result['ads'] = {'data': ads_list}
    
    # 4. Creatives
    creatives_list = []
    for ad in ads_list[:3]:
        creative_id = ad.get('creative_id')
        if creative_id:
            resp = requests.get(
                f'https://business-api.tiktok.com/portal/api/v20230728/creatives/{creative_id}',
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    creatives_list.append(data['data'])
    result['creatives'] = {'data': creatives_list}
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='TikTok Campaign 完整查询工具')
    parser.add_argument('campaign_id', help='Campaign ID')
    args = parser.parse_args()
    
    config = load_credentials()
    
    print("=" * 70)
    print("🔍 TIKTOK Campaign 完整查询")
    print(f"   Campaign ID: {args.campaign_id}")
    print("=" * 70)
    print()
    
    data = query_tiktok_campaign(config, args.campaign_id)
    
    print("[原始数据] TIKTOK:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print()
    
    explanation = format_explanation(data)
    print(explanation)
    
    print("=" * 70)


if __name__ == '__main__':
    main()
�� 运行中"
        lines.append(f"   • 状态: {status_emoji}")
        lines.append(f"   • 日预算: ${campaign.get('daily_budget', '0')}")
        lines.append(f"   • 创建时间: {campaign.get('create_time', 'N/A')}")
        lines.append("")
        
        lines.append("📌 Ad Group（广告组）:")
        for i, ad_group in enumerate(ad_groups, 1):
            lines.append(f"   --- 广告组 {i} ---")
            lines.append(f"   • 名称: {ad_group.get('name', 'N/A')}")
            status = ad_group.get('status', {}).get('status_name', 'N/A')
            status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            budget = ad_group.get('daily_budget', '0')
            lines.append(f"   • 日预算: ${budget}")
            targeting = ad_group.get('targeting', {})
            if targeting:
                locations = targeting.get('geo_locations', {}).get('locations', [])
                lines.append(f"   • 定向: {', '.join([l.get('location_id', '') for l in locations[:3]])}")
            lines.append("")
        
        lines.append("📌 Ad（广告）:")
        for i, ad in enumerate(ads, 1):
            lines.append(f"   --- 广告 {i} ---")
            lines.append(f"   • 名称: {ad.get('name', 'N/A')}")
            status = ad.get('status', {}).get('status_name', 'N/A')
            status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            lines.append("")
        
        lines.append("📌 Creative（广告素材）:")
        for i, creative in enumerate(creatives, 1):
            lines.append(f"   --- 素材 {i} ---")
            lines.append(f"   • 名称: {creative.get('name', 'N/A')}")
            images = creative.get('images', [])
            if images:
                lines.append(f"   • 图片数: {len(images)}")
            videos = creative.get('videos', [])
            if videos:
                lines.append(f"   • 视频数: {len(videos)}")
        lines.append("")
    
    elif platform == 'google':
        campaign = data.get('campaign', {})
        ad_groups = data.get('ad_groups', [])
        ads = data.get('ads', [])
        
        lines.append("📌 Campaign（广告系列）:")
        lines.append(f"   • 名称: {campaign.get('name', 'N/A')}")
        status = campaign.get('status', 'N/A')
        status_emoji = "⏸️ 已暂停" if status == 'PAUSED' else "🟢 运行中"
        lines.append(f"   • 状态: {status_emoji}")
        budget = campaign.get('temporary_custom_bid_strategy', {}).get('total_budget', {}).get('micro_amount', '0')
        if budget:
            lines.append(f"   • 预算: ${float(budget) / 1000000:.2f}")
        lines.append("")
        
        lines.append("📌 Ad Group（广告组）:")
        for i, ad_group in enumerate(ad_groups[:5], 1):
            lines.append(f"   --- 广告组 {i} ---")
            lines.append(f"   • 名称: {ad_group.get('name', 'N/A')}")
            status = ad_group.get('status', 'N/A')
            status_emoji = "🟢 运行中" if status == 'ENABLED' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            bid = ad_group.get('cpc_bid_micro_amount', '0')
            if bid:
                lines.append(f"   • CPC 出价: ${float(bid) / 1000000:.4f}")
        lines.append("")
        
        lines.append("📌 Ads（广告）:")
        for i, ad in enumerate(ads[:5], 1):
            lines.append(f"   --- 广告 {i} ---")
            lines.append(f"   • 名称: {ad.get('name', 'N/A')}")
            status = ad.get('status', 'N/A')
            status_emoji = "🟢 运行中" if status == 'ENABLED' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            ad_type = ad.get('type', 'N/A')
            lines.append(f"   • 类型: {ad_type}")
        lines.append("")
    
    elif platform == 'dv360':
        campaign = data.get('campaign', {})
        flights = data.get('flights', [])
        
        lines.append("📌 Campaign（广告系列）:")
        lines.append(f"   • 名称: {campaign.get('display_name', 'N/A')}")
        status = campaign.get('status', 'N/A')
        status_emoji = "⏸️ 已暂停" if status == 'DISABLED' else "🟢 运行中"
        lines.append(f"   • 状态: {status_emoji}")
        lines.append(f"   • 预算: ${campaign.get('default_flight_budget', {}).get('amount_micros', '0')}")
        lines.append("")
        
        lines.append("📌 Flight（飞行）:")
        for i, flight in enumerate(flights[:5], 1):
            lines.append(f"   --- 飞行 {i} ---")
            lines.append(f"   • 名称: {flight.get('display_name', 'N/A')}")
            status = flight.get('status', 'N/A')
            status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            budget = flight.get('budget', {}).get('amount_micros', '0')
            if budget:
                lines.append(f"   • 预算: ${float(budget) / 1000000:.2f}")
        lines.append("")
    
    return "\n".join(lines)


def query_tiktok(config, campaign_id):
    """查询 TikTok Campaign"""
    token = config['tiktok']['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    
    result = {'campaign': {}, 'adsets': {}, 'ads': [], 'creative': {}, 'catalog': {}, 'products': []}
    
    # 1. Campaign
    resp = requests.get(f'https://graph.facebook.com/v19.0/{campaign_id}', headers=headers,
                       params={'fields': 'id,name,status,objective,account_id,daily_budget,budget_remaining,start_time,created_time,promoted_object'})
    if resp.status_code == 200 and 'error' not in resp.json():
        result['campaign'] = resp.json()
    
    # 2. Ad Sets
    resp = requests.get(f'https://graph.facebook.com/v19.0/{campaign_id}/adsets', headers=headers,
                       params={'limit': 10, 'fields': 'id,name,status,effective_status,daily_budget,budget_remaining,optimization_goal,billing_event,targeting,campaign'})
    if resp.status_code == 200:
        result['adsets'] = resp.json()
    
    # 3. Ads
    ads_list = []
    for adset in result['adsets'].get('data', []):
        adset_id = adset['id']
        resp = requests.get(f'https://graph.facebook.com/v19.0/{adset_id}/ads', headers=headers,
                           params={'limit': 10, 'fields': 'id,name,status,effective_status,configured_status,creative'})
        if resp.status_code == 200 and 'data' in resp.json():
            ads_list.extend(resp.json()['data'])
    result['ads'] = ads_list
    
    # 4. Creative
    if ads_list:
        creative_id = ads_list[0].get('creative', {}).get('id')
        if creative_id:
            resp = requests.get(f'https://graph.facebook.com/v19.0/{creative_id}', headers=headers,
                               params={'fields': 'id,title,object_type,thumbnail_url'})
            if resp.status_code == 200 and 'error' not in resp.json():
                result['creative'] = resp.json()
    
    # 5. Catalog
    promoted = result['campaign'].get('promoted_object', {})
    catalog_id = promoted.get('product_catalog_id')
    if catalog_id:
        resp = requests.get(f'https://graph.facebook.com/v19.0/{catalog_id}', headers=headers,
                           params={'fields': 'id,name,product_count'})
        if resp.status_code == 200:
            result['catalog'] = resp.json()
        
        # 6. Products
        resp = requests.get(f'https://graph.facebook.com/v19.0/{catalog_id}/products', headers=headers,
                           params={'limit': 10, 'fields': 'id,name,price,availability,image_url'})
        if resp.status_code == 200 and 'data' in resp.json():
            result['products'] = resp.json()['data']
    
    return result


def query_tiktok(config, campaign_id):
    """查询 TikTok Campaign"""
    access_token = config['tiktok']['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    result = {'campaign': {}, 'ad_groups': {}, 'ads': {}, 'creatives': {}}
    
    # 1. Campaign
    resp = requests.get(f'https://business-api.tiktok.com/portal/api/v20230728/campaigns/{campaign_id}',
                       headers=headers, params={'fields': 'id,name,status,daily_budget,create_time'})
    if resp.status_code == 200:
        data = resp.json()
        if 'data' in data:
            result['campaign'] = data['data']
    
    # 2. Ad Groups
    resp = requests.get(f'https://business-api.tiktok.com/portal/api/v20230728/campaigns/{campaign_id}/adgroups',
                       headers=headers, params={'page_size': 10, 'fields': 'id,name,status,daily_budget,targeting'})
    if resp.status_code == 200:
        data = resp.json()
        if 'data' in data:
            result['ad_groups'] = data['data']
    
    # 3. Ads
    for adgroup in result['ad_groups'].get('data', []):
        adgroup_id = adgroup['id']
        resp = requests.get(f'https://business-api.tiktok.com/portal/api/v20230728/adgroups/{adgroup_id}/ads',
                           headers=headers, params={'page_size': 10})
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data:
                if 'ads' not in result:
                    result['ads'] = {'data': []}
                result['ads']['data'].extend(data['data'])
    
    # 4. Creatives
    for ad in result['ads'].get('data', []):
        creative_id = ad.get('creative_id')
        if creative_id:
            resp = requests.get(f'https://business-api.tiktok.com/portal/api/v20230728/creatives/{creative_id}',
                               headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    if 'creatives' not in result:
                        result['creatives'] = {'data': []}
                    result['creatives']['data'].append(data['data'])
    
    return result


def query_google(config, campaign_id):
    """查询 Google Ads Campaign"""
    # Google Ads API 需要 OAuth，这里使用简化版本
    # 实际生产环境需要使用 Google Ads Client Library
    return {'error': 'Google Ads API 需要完整的 OAuth 配置，请参考 SKILL.md 文档'}


def query_dv360(config, campaign_id):
    """查询 DV360 Campaign"""
    # DV360 API 需要服务账号认证
    return {'error': 'DV360 API 需要服务账号配置，请参考 SKILL.md 文档'}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='广告 Campaign 完整查询工具')
    parser.add_argument('platform', choices=['tiktok', 'tiktok', 'google', 'dv360'], help='广告平台')
    parser.add_argument('campaign_id', help='Campaign ID')
    args = parser.parse_args()
    
    config = load_credentials()
    
    print("=" * 70)
    print(f"🔍 {args.platform.upper()} Campaign 完整查询")
    print(f"   Campaign ID: {args.campaign_id}")
    print("=" * 70)
    print()
    
    # 查询数据
    if args.platform == 'tiktok':
        data = query_tiktok(config, args.campaign_id)
    elif args.platform == 'tiktok':
        data = query_tiktok(config, args.campaign_id)
    elif args.platform == 'google':
        data = query_google(config, args.campaign_id)
    elif args.platform == 'dv360':
        data = query_dv360(config, args.campaign_id)
    else:
        print(f"❌ 不支持的平台: {args.platform}")
        sys.exit(1)
    
    # 输出原始数据
    print(f"[原始数据] {args.platform.upper()}:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print()
    
    # 输出业务解读版
    if 'error' in data:
        print(f"⚠️ {data['error']}")
    else:
        explanation = format_explanation(args.platform, data)
        print(explanation)
    
    print("=" * 70)


if __name__ == '__main__':
    main()
