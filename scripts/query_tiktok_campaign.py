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


def format_explanation(data):
    """格式化业务解读"""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("[BUSINESS VIEW]")
    lines.append("=" * 70)
    lines.append("")

    campaign = data.get('campaign', {})
    ad_groups = data.get('ad_groups', {}).get('data', [])
    ads = data.get('ads', {}).get('data', [])
    creatives = data.get('creatives', {}).get('data', [])

    lines.append("Campaign (广告系列):")
    lines.append(f"   Name: {campaign.get('campaign_name', 'N/A')}")
    status = campaign.get('secondary_status', campaign.get('operation_status', 'N/A'))
    status_map = {
        'CAMPAIGN_STATUS_ENABLE': '[RUNNING]',
        'CAMPAIGN_STATUS_DISABLE': '[DISABLED]',
        'ENABLE': '[RUNNING]',
        'DISABLE': '[DISABLED]',
        'PAUSE': '[PAUSED]'
    }
    status_emoji = status_map.get(status, f'[{status}]')
    lines.append(f"   Status: {status_emoji} ({status})")
    budget = campaign.get('budget', 0)
    lines.append(f"   Daily Budget: ${budget}")
    lines.append(f"   Create Time: {campaign.get('create_time', 'N/A')}")
    lines.append("")

    lines.append("Ad Groups (广告组):")
    if ad_groups:
        for i, ad_group in enumerate(ad_groups[:5], 1):
            lines.append(f"   --- Ad Group {i} ---")
            lines.append(f"   Name: {ad_group.get('adgroup_name', ad_group.get('name', 'N/A'))}")
            lines.append(f"   ID: {ad_group.get('adgroup_id', ad_group.get('id', 'N/A'))}")
            lines.append("")
    else:
        lines.append("   (No ad groups found)")
        lines.append("")

    lines.append("Ads (广告):")
    if ads:
        for i, ad in enumerate(ads[:5], 1):
            lines.append(f"   --- Ad {i} ---")
            lines.append(f"   Name: {ad.get('ad_name', ad.get('name', 'N/A'))}")
            lines.append(f"   ID: {ad.get('ad_id', ad.get('id', 'N/A'))}")
            lines.append("")
    else:
        lines.append("   (No ads found)")
        lines.append("")

    lines.append("Creatives (素材):")
    if creatives:
        for i, creative in enumerate(creatives[:5], 1):
            lines.append(f"   --- Creative {i} ---")
            lines.append(f"   Title: {creative.get('title', 'N/A')}")
            lines.append(f"   ID: {creative.get('creative_id', creative.get('id', 'N/A'))}")
            lines.append("")
    else:
        lines.append("   (No creatives found)")
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
        print(f"Usage: {sys.argv[0]} <campaign_id>")
        sys.exit(1)

    config = load_credentials()
    tiktok_config = config.get('tiktok', {})

    if not tiktok_config:
        print("\n[ERROR] TikTok credentials not configured")
        sys.exit(1)

    access_token = tiktok_config.get('access_token', '')
    bc_id = tiktok_config.get('bc_id', '')
    # 从 BC ID 推导 advertiser_id (TikTok BC ID 和 advertiser_id 通常是同一个值)
    advertiser_id = bc_id

    if not access_token:
        print("\n[ERROR] TikTok access_token not configured")
        sys.exit(1)

    campaign_id = sys.argv[1]

    print(f"\n[TIKTOK QUERY] Campaign: {campaign_id}")
    print(f"   BC ID: {bc_id}")
    print("-" * 70)

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
    # 输出原始 JSON
    print("\n[RAW DATA] TIKTOK:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 输出业务解读
    print(format_explanation(result))


if __name__ == "__main__":
    main()
