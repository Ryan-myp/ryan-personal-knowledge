#!/usr/bin/env python3
"""
广告 Campaign 完整查询工具 - 双格式输出
支持 Meta、TikTok、Google Ads、DV360 四大平台
输出格式：原始数据(JSON) + 业务解读版(中文)
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# 凭证文件路径
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"


def load_credentials():
    """加载凭证配置"""
    if not CREDENTIALS_FILE.exists():
        print(f"❌ 凭证文件不存在: {CREDENTIALS_FILE}")
        print("请复制模板并填写真实值:")
        print(f"  cp {CREDENTIALS_FILE}.template {CREDENTIALS_FILE}")
        sys.exit(1)
    
    with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_explanation(platform, data):
    """生成业务可读的解释版"""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("📊 业务解读版")
    lines.append("=" * 70)
    lines.append("")
    
    if platform == 'meta':
        camp = data.get('campaign', {})
        adsets = data.get('adsets', {})
        ads = data.get('ads', [])
        creative = data.get('creative', {})
        catalog = data.get('catalog', {})
        products = data.get('products', [])
        
        # Campaign 解读
        lines.append("📌 Campaign（广告系列）:")
        lines.append(f"   • 名称: {camp.get('name', 'N/A')}")
        status_emoji = "⏸️ 已暂停" if camp.get('status') == 'PAUSED' else "🟢 运行中"
        lines.append(f"   • 状态: {status_emoji}")
        lines.append(f"   • 目标: {camp.get('objective', 'N/A').replace('_', ' ').title()}")
        lines.append(f"   • 日预算: ${camp.get('daily_budget', '0')}")
        lines.append(f"   • 剩余预算: ${camp.get('budget_remaining', '0')}")
        lines.append(f"   • 创建时间: {camp.get('created_time', 'N/A')}")
        promo = camp.get('promoted_object', {})
        if promo:
            lines.append(f"   • 推广商品: Catalog ID {promo.get('product_catalog_id', 'N/A')}")
        lines.append("")
        
        # Ad Set 解读
        lines.append("📌 Ad Set（广告组）:")
        for i, adset in enumerate(adsets.get('data', []), 1):
            lines.append(f"   --- 广告组 {i} ---")
            lines.append(f"   • 名称: {adset.get('name', 'N/A')}")
            eff_status = adset.get('effective_status', adset.get('status', 'N/A'))
            status_emoji = "🟢 有效" if eff_status == 'ACTIVE' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji} (effective: {eff_status})")
            lines.append(f"   • 优化目标: {adset.get('optimization_goal', 'N/A').replace('_', ' ').title()}")
            lines.append(f"   • 计费方式: {adset.get('billing_event', 'N/A').replace('_', ' ').title()}")
            lines.append(f"   • 预算剩余: ${adset.get('budget_remaining', '0')}")
            target = adset.get('targeting', {})
            if target:
                countries = target.get('geo_locations', {}).get('countries', [])
                age_range = f"{target.get('age_min', 'N/A')}-{target.get('age_max', 'N/A')}"
                lines.append(f"   • 定向: {', '.join(countries)} | 年龄 {age_range}")
            lines.append("")
        
        # Ad 解读
        lines.append("📌 Ad（广告）:")
        for i, ad in enumerate(ads, 1):
            lines.append(f"   --- 广告 {i} ---")
            lines.append(f"   • 名称: {ad.get('name', 'N/A')}")
            eff_status = ad.get('effective_status', ad.get('status', 'N/A'))
            status_emoji = "🟢 有效" if eff_status == 'ACTIVE' else "⏸️ 已暂停"
            lines.append(f"   • 状态: {status_emoji}")
            creative_id = ad.get('creative', {}).get('id', 'N/A')
            lines.append(f"   • 素材 ID: {creative_id}")
        lines.append("")
        
        # Creative 解读
        if creative:
            lines.append("📌 Creative（广告素材）:")
            lines.append(f"   • 标题: {creative.get('title', 'N/A')}")
            obj_type = creative.get('object_type', 'N/A')
            lines.append(f"   • 类型: {obj_type}")
            thumbnail = creative.get('thumbnail_url', '')
            if thumbnail:
                lines.append(f"   • 缩略图: {thumbnail[:80]}...")
            lines.append("")
        
        # Catalog 解读
        if catalog:
            lines.append("📌 Product Catalog（商品目录）:")
            lines.append(f"   • 名称: {catalog.get('name', 'N/A')}")
            product_count = catalog.get('product_count', 0)
            lines.append(f"   • 产品数量: {int(product_count):,}")
            lines.append("")
        
        # Products 解读
        if products:
            lines.append("📌 商品列表 (前10个):")
            for i, prod in enumerate(products[:10], 1):
                name = prod.get('name', 'N/A')
                if len(name) > 40:
                    name = name[:37] + "..."
                price = prod.get('price', 'N/A')
                avail = prod.get('availability', 'N/A')
                stock_emoji = "✅" if avail == 'in stock' else "❌"
                lines.append(f"   {i}. {name}")
                lines.append(f"      价格: {price} | 库存: {stock_emoji} {avail}")
            lines.append("")
    
    elif platform == 'tiktok':
        campaign = data.get('campaign', {})
        ad_groups = data.get('ad_groups', {}).get('data', [])
        ads = data.get('ads', {}).get('data', [])
        creatives = data.get('creatives', {}).get('data', [])
        
        lines.append("📌 Campaign（广告系列）:")
        lines.append(f"   • 名称: {campaign.get('name', 'N/A')}")
        status = campaign.get('status', {}).get('status_name', 'N/A')
        status_emoji = "⏸️ 已暂停" if status == 'PAUSED' else "🟢 运行中"
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


def query_meta(config, campaign_id):
    """查询 Meta Campaign"""
    token = config['meta']['access_token']
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
    parser.add_argument('platform', choices=['meta', 'tiktok', 'google', 'dv360'], help='广告平台')
    parser.add_argument('campaign_id', help='Campaign ID')
    args = parser.parse_args()
    
    config = load_credentials()
    
    print("=" * 70)
    print(f"🔍 {args.platform.upper()} Campaign 完整查询")
    print(f"   Campaign ID: {args.campaign_id}")
    print("=" * 70)
    print()
    
    # 查询数据
    if args.platform == 'meta':
        data = query_meta(config, args.campaign_id)
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
