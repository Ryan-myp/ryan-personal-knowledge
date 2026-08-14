#!/usr/bin/env python3
"""
DV360 Campaign 完整查询工具 - 双格式输出
注意：DV360 API 需要服务账号认证
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
    flights = data.get('flights', [])
    
    lines.append("📌 Campaign（广告系列）:")
    lines.append(f"   • 名称: {campaign.get('display_name', 'N/A')}")
    status = campaign.get('status', 'N/A')
    status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
    lines.append(f"   • 状态: {status_emoji}")
    budget = campaign.get('default_flight_budget', {}).get('amount_micros', '0')
    if budget:
        lines.append(f"   • 预算: ${float(budget) / 1000000:.2f}")
    advertiser_id = campaign.get('advertiser_id', 'N/A')
    lines.append(f"   • 广告主 ID: {advertiser_id}")
    lines.append("")
    
    lines.append("📌 Flight（投放周期）:")
    for i, flight in enumerate(flights[:5], 1):
        lines.append(f"   --- 飞行 {i} ---")
        lines.append(f"   • 名称: {flight.get('display_name', 'N/A')}")
        status = flight.get('status', 'N/A')
        status_emoji = "🟢 运行中" if status == 'ACTIVE' else "⏸️ 已暂停"
        lines.append(f"   • 状态: {status_emoji}")
        budget = flight.get('budget', {}).get('amount_micros', '0')
        if budget:
            lines.append(f"   • 预算: ${float(budget) / 1000000:.2f}")
        start_time = flight.get('start_time_range', {}).get('start_timestamp_millis', 'N/A')
        end_time = flight.get('start_time_range', {}).get('end_timestamp_millis', 'N/A')
        lines.append(f"   • 时间: {start_time} ~ {end_time}")
        lines.append("")
    
    lines.append("📌 Line Item（媒体购买）:")
    line_items = data.get('line_items', [])
    for i, item in enumerate(line_items[:3], 1):
        lines.append(f"   --- 媒体购买 {i} ---")
        lines.append(f"   • 名称: {item.get('display_name', 'N/A')}")
        status = item.get('status', 'N/A')
        lines.append(f"   • 状态: {status}")
        lines.append("")
    
    return "\n".join(lines)


def query_dv360_campaign(config, campaign_id):
    """
    DV360 API 查询
    注意：需要服务账号 JSON 密钥文件
    """
    result = {
        'campaign': {},
        'flights': [],
        'line_items': [],
        'note': 'DV360 API 需要服务账号配置'
    }
    
    dv360_config = config.get('dv360', {})
    service_account_file = dv360_config.get('service_account_file', '')
    
    if not service_account_file or not os.path.exists(service_account_file):
        result['error'] = '未配置 DV360 服务账号文件'
        result['note'] = f"""
📌 DV360 API 使用说明:

1. 在 Google Cloud Console 创建服务账号并下载 JSON 密钥
2. 在 ad_platform_credentials.json 中配置:
   {{
     "dv360": {{
       "service_account_file": "/path/to/service-account.json",
       "customer_id": "YOUR_CUSTOMER_ID"
     }}
   }}

3. 使用示例:
   from googleapiclient.discovery import build
   from google.oauth2 import service_account
   
   credentials = service_account.Credentials.from_service_account_file(
       'service-account.json',
       scopes=['https://www.googleapis.com/auth/display-video']
   )
   service = build('displayvideo', 'v1', credentials=credentials)
   
   # 查询 Campaign
   campaigns = service.campaigns().list(parent=f'advertisers/{advertiser_id}').execute()
"""
        return result
    
    result['note'] = 'DV360 API 需要进一步集成，请参考上方使用说明'
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='DV360 Campaign 完整查询工具')
    parser.add_argument('campaign_id', help='Campaign ID')
    args = parser.parse_args()
    
    config = load_credentials()
    
    print("=" * 70)
    print("🔍 DV360 Campaign 完整查询")
    print(f"   Campaign ID: {args.campaign_id}")
    print("=" * 70)
    print()
    
    data = query_dv360_campaign(config, args.campaign_id)
    
    print("[原始数据] DV360:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print()
    
    explanation = format_explanation(data)
    print(explanation)
    
    print("=" * 70)


if __name__ == '__main__':
    main()
