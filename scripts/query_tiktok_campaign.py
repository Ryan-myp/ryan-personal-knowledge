#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    """加载凭证配置"""
    if not CREDENTIALS_FILE.exists():
        print(f"[ERROR] Credentials file not found: {CREDENTIALS_FILE}")
        sys.exit(1)
    with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_status(status):
    """格式化状态显示"""
    status_map = {
        'CAMPAIGN_STATUS_ENABLE': ('✅', 'RUNNING'),
        'CAMPAIGN_STATUS_DISABLE': ('⛔', 'DISABLED'),
        'CAMPAIGN_STATUS_PAUSE': ('⏸️', 'PAUSED'),
        'ADGROUP_STATUS_ENABLE': ('✅', 'RUNNING'),
        'ADGROUP_STATUS_DISABLE': ('⛔', 'DISABLED'),
        'ADGROUP_STATUS_CAMPAIGN_DISABLE': ('⛔', 'CAMPAIGN_DISABLE'),
        'AD_STATUS_ENABLE': ('✅', 'RUNNING'),
        'AD_STATUS_DISABLE': ('⛔', 'DISABLED'),
        'AD_STATUS_CAMPAIGN_DISABLE': ('⛔', 'CAMPAIGN_DISABLE'),
    }
    emoji, text = status_map.get(status, ('❓', status))
    return f"{emoji} {text}"


def format_explanation(data):
    """格式化业务解读"""
    lines = []
    
    campaign = data.get('campaign', {})
    ad_groups_data = data.get('ad_groups', {})
    ads_data = data.get('ads', {})
    
    ad_groups = ad_groups_data.get('list', []) if isinstance(ad_groups_data, dict) else []
    ads = ads_data.get('list', []) if isinstance(ads_data, dict) else []
    
    # 分隔线
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + " 📊 TIKTOK CAMPAIGN REPORT".ljust(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    lines.append("")
    
    # Campaign 信息
    lines.append("┌─ CAMPAIGN ─" + "─" * 62 + "┐")
    lines.append(f"│ 📌 ID          │ {campaign.get('campaign_id', 'N/A')}")
    lines.append(f"│ 📝 Name        │ {campaign.get('campaign_name', 'N/A')}")
    status = campaign.get('secondary_status', campaign.get('operation_status', ''))
    lines.append(f"│ 🚦 Status      │ {format_status(status)}")
    budget = campaign.get('budget', 0)
    lines.append(f"│ 💰 Budget      │ ${budget:,.2f}" if budget > 0 else "│ 💰 Budget      │ None")
    lines.append(f"│ 🎯 Objective   │ {campaign.get('objective_type', 'N/A')}")
    lines.append(f"│ 📱 Destination │ {campaign.get('sales_destination', 'N/A') or 'Web'}")
    lines.append(f"│ 📅 Created     │ {campaign.get('create_time', 'N/A')}")
    lines.append(f"│ 🔧 Automation  │ {campaign.get('campaign_automation_type', 'N/A')}")
    lines.append("└" + "─" * 62 + "┘")
    lines.append("")
    
    # Ad Groups 统计
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + f" AD GROUPS ({len(ad_groups):>2} total)".ljust(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    for i, ag in enumerate(ad_groups[:10], 1):
        ag_status = format_status(ag.get('secondary_status', ag.get('operation_status', '')))
        name = ag.get('adgroup_name', 'N/A')
        lines.append(f"")
        lines.append(f"  [{i:2d}] {name}")
        lines.append(f"       ID    : {ag.get('adgroup_id', 'N/A')}")
        lines.append(f"       Status: {ag_status}")
        lines.append(f"       Goal  : {ag.get('optimization_goal', 'N/A')} | Bid: {ag.get('bid_type', 'N/A')} | Bill: {ag.get('billing_event', 'N/A')}")
    if len(ad_groups) > 10:
        lines.append(f"")
        lines.append(f"  ... and {len(ad_groups) - 10} more ad groups")
    lines.append("")
    
    # Ads 统计
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + f" ADS (First AdGroup: {len(ads):>2} total)".ljust(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    for i, ad in enumerate(ads[:5], 1):
        ad_status = format_status(ad.get('secondary_status', ad.get('operation_status', '')))
        name = ad.get('ad_name', 'N/A')[:50]
        creator = ad.get('display_name', 'N/A') or 'N/A'
        lines.append(f"")
        lines.append(f"  [{i}] {name}")
        lines.append(f"      ID      : {ad.get('ad_id', 'N/A')}")
        lines.append(f"      Creator : {creator}")
        lines.append(f"      Status  : {ad_status}")
        lines.append(f"      Format  : {ad.get('ad_format', 'N/A')}")
    if len(ads) > 5:
        lines.append(f"")
        lines.append(f"  ... and {len(ads) - 5} more ads")
    lines.append("")
    lines.append("")
    
    # 关键指标汇总
    lines.append("┌─ SUMMARY ─" + "─" * 62 + "┐")
    lines.append(f"│ Campaign Status : {format_status(campaign.get('secondary_status', campaign.get('operation_status', '')))}")
    lines.append(f"│ Total Ad Groups : {len(ad_groups)}")
    lines.append(f"│ Total Ads       : {len(ads)}")
    lines.append(f"│ RTA ID          : {campaign.get('rta_id', 'N/A')}")
    lines.append(f"│ Campaign Type   : {campaign.get('campaign_type', 'N/A')}")
    lines.append("└" + "─" * 62 + "┘")
    lines.append("")
    
    return "\n".join(lines)


def query_campaign(access_token, advertiser_id, campaign_id):
    """查询 Campaign 详情"""
    headers = {
        'Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    url = f'https://business-api.tiktok.com/open_api/v1.3/campaign/get/'
    params = {
        'advertiser_id': advertiser_id,
        'filtering': json.dumps({'campaign_ids': [campaign_id]})
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    return response.json()


def query_ad_groups(access_token, advertiser_id, campaign_id):
    """查询 Ad Groups"""
    headers = {
        'Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    url = f'https://business-api.tiktok.com/open_api/v1.3/adgroup/get/'
    params = {
        'advertiser_id': advertiser_id,
        'filtering': json.dumps({'campaign_id': campaign_id})
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    return response.json()


def query_ads(access_token, advertiser_id, adgroup_id):
    """查询 Ads"""
    headers = {
        'Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    url = f'https://business-api.tiktok.com/open_api/v1.3/ad/get/'
    params = {
        'advertiser_id': advertiser_id,
        'filtering': json.dumps({'adgroup_id': adgroup_id})
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    return response.json()


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <campaign_id> [advertiser_id]")
        print(f"Example: {sys.argv[0]} 1836521788460274 7397068114548195329")
        sys.exit(1)

    config = load_credentials()
    tiktok_config = config.get('tiktok', {})

    if not tiktok_config:
        print("\n[ERROR] TikTok credentials not configured")
        sys.exit(1)

    access_token = tiktok_config.get('access_token', '')
    bc_id = tiktok_config.get('bc_id', '')

    if not access_token:
        print("\n[ERROR] TikTok access_token not configured")
        sys.exit(1)

    campaign_id = sys.argv[1]
    advertiser_id = sys.argv[2] if len(sys.argv) > 2 else bc_id

    print(f"\n🔍 Querying TikTok Campaign...")
    print(f"   Campaign ID: {campaign_id}")
    print(f"   Advertiser ID: {advertiser_id}")
    print()

    # 查询 Campaign
    campaign_data = query_campaign(access_token, advertiser_id, campaign_id)

    if campaign_data.get('code') != 0:
        print(f"[ERROR] API Error: {campaign_data.get('message', 'Unknown error')}")
        sys.exit(1)

    # 提取 Campaign 数据
    campaign_list = campaign_data.get('data', {}).get('list', [])
    if not campaign_list:
        print(f"[ERROR] Campaign {campaign_id} not found")
        sys.exit(1)

    campaign = campaign_list[0]

    # 查询 Ad Groups
    ad_groups_data = query_ad_groups(access_token, advertiser_id, campaign_id)
    ad_groups_list = ad_groups_data.get('data', {}).get('list', []) if ad_groups_data.get('code') == 0 else []

    # 查询 Ads (第一个 Ad Group)
    ads_list = []
    first_adgroup_id = None
    if ad_groups_list:
        first_adgroup_id = ad_groups_list[0].get('adgroup_id')
        ads_data = query_ads(access_token, advertiser_id, first_adgroup_id)
        ads_list = ads_data.get('data', {}).get('list', []) if ads_data.get('code') == 0 else []

    # 构建完整数据
    result = {
        "campaign": campaign,
        "ad_groups": {"total": len(ad_groups_list), "list": ad_groups_list[:10]},
        "ads": {"total": len(ads_list), "list": ads_list[:5]},
        "creatives": {}
    }

    # 输出原始 JSON
    print("=" * 70)
    print("[RAW DATA] TIKTOK")
    print("=" * 70)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 输出业务解读
    print(format_explanation(result))


if __name__ == "__main__":
    main()
