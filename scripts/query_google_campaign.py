#!/usr/bin/env python3
"""
Google Ads Campaign 完整查询工具 - 双格式输出
注意：Google Ads API 需要完整的 OAuth 配置
"""

import os
import sys
import json
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
    ad_groups = data.get('ad_groups', [])
    ads = data.get('ads', [])
    
    lines.append("📌 Campaign（广告系列）:")
    lines.append(f"   • 名称: {campaign.get('name', 'N/A')}")
    status = campaign.get('status', 'N/A')
    status_emoji = "🟢 运行中" if status == 'ENABLED' else "⏸️ 已暂停"
    lines.append(f"   • 状态: {status_emoji}")
    budget = campaign.get('manual_cpm_bid_ceiling_micros', '0')
    if budget:
        lines.append(f"   • 预算: ${float(budget) / 1000000:.2f}")
    lines.append(f"   • 投放方式: {campaign.get('campaign_budget_collection_method', 'N/A')}")
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
    
    return "\n".join(lines)


def query_google_campaign(config, campaign_resource_name):
    """
    Google Ads API 查询
    注意：需要安装 google-ads 库并配置 OAuth
    """
    result = {
        'campaign': {},
        'ad_groups': [],
        'ads': [],
        'note': 'Google Ads API 需要完整 OAuth 配置，请使用 google-ads Python SDK'
    }
    
    # 检查是否有配置
    google_config = config.get('google', {})
    if not google_config.get('developer_token'):
        result['error'] = '未配置 Google Ads Developer Token'
        return result
    
    result['note'] = f"""
📌 Google Ads API 使用说明:

1. 安装 SDK:
   pip install google-ads

2. 创建配置文件 google-ads.yaml:
   developer_token: YOUR_DEVELOPER_TOKEN
   refresh_token: YOUR_REFRESH_TOKEN
   client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
    login_customer_id: YOUR_CUSTOMER_ID

3. 使用示例:
   from google.ads.googleads.client import GoogleAdsClient
   client = GoogleAdsClient.load_from_storage('google-ads.yaml')
   
   # 查询 Campaign
   campaign_service = client.get_service("CampaignService")
   query = f'SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.id = {campaign_resource_name}'
   results = client.get_service('GoogleAdsService').search(request=query)
   
   # 查询 Ad Groups
   ad_group_service = client.get_service('AdGroupService')
   query = f'SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group WHERE campaign.resource_name = "{campaign_resource_name}"'
   
   # 查询 Ads  
   ad_service = client.get_service('AdService')
   query = f'SELECT ad.id, ad.name, ad.type, ad.status FROM ad WHERE ad_group.resource_name IN ({ad_group_ids})'
"""
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Google Ads Campaign 完整查询工具')
    parser.add_argument('campaign_id', help='Campaign Resource Name (如: customers/123/campaigns/456)')
    args = parser.parse_args()
    
    config = load_credentials()
    
    print("=" * 70)
    print("🔍 GOOGLE ADS Campaign 完整查询")
    print(f"   Campaign: {args.campaign_id}")
    print("=" * 70)
    print()
    
    data = query_google_campaign(config, args.campaign_id)
    
    print("[原始数据] GOOGLE ADS:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print()
    
    explanation = format_explanation(data)
    print(explanation)
    
    print("=" * 70)


if __name__ == '__main__':
    main()
