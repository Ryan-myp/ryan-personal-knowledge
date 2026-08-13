#!/usr/bin/env python3
"""
广告平台统一 API 调用脚本
支持 TikTok、Meta、Google Ads、DV360 四大平台
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 凭证文件路径
CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"

# 各平台客户端缓存
_clients = {}


class AdPlatformClient:
    """广告平台统一客户端"""
    
    def __init__(self):
        self.credentials = self._load_credentials()
        self.platforms = ['tiktok', 'meta', 'google', 'dv360']
    
    def _load_credentials(self) -> Dict:
        """加载凭证配置"""
        if not CREDENTIALS_FILE.exists():
            print(f"❌ 凭证文件不存在: {CREDENTIALS_FILE}")
            print("请复制模板并填写真实值:")
            print(f"  cp {CREDENTIALS_FILE}.template {CREDENTIALS_FILE}")
            sys.exit(1)
        
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_client(self, platform: str):
        """获取平台客户端"""
        if platform not in _clients:
            _clients[platform] = self._create_client(platform)
        return _clients[platform]
    
    def _create_client(self, platform: str):
        """创建平台客户端"""
        if platform == 'tiktok':
            return self._create_tiktok_client()
        elif platform == 'meta':
            return self._create_meta_client()
        elif platform == 'google':
            return self._create_google_client()
        elif platform == 'dv360':
            return self._create_dv360_client()
        else:
            raise ValueError(f"不支持的平台: {platform}")
    
    def _create_tiktok_client(self):
        """创建 TikTok 客户端"""
        try:
            from tiktokads.business.sdk import Client
            creds = self.credentials.get('tiktok', {})
            return Client(
                access_token=creds.get('access_token', ''),
                app_key=creds.get('app_key', ''),
                app_secret=creds.get('app_secret', '')
            )
        except ImportError:
            print("❌ 请先安装 TikTok SDK: pip install tiktok-api")
            sys.exit(1)
    
    def _create_meta_client(self):
        """创建 Meta 客户端"""
        try:
            from facebook_business.api import FacebookAdsApi
            creds = self.credentials.get('meta', {})
            FacebookAdsApi.init(
                app_id=creds.get('app_id', ''),
                app_secret=creds.get('app_secret', ''),
                access_token=creds.get('access_token', '')
            )
            return FacebookAdsApi
        except ImportError:
            print("❌ 请先安装 Meta SDK: pip install facebook-business")
            sys.exit(1)
    
    def _create_google_client(self):
        """创建 Google Ads 客户端"""
        try:
            from google.ads.googleads.client import GoogleAdsClient
            creds = self.credentials.get('google', {})
            return GoogleAdsClient.load_from_dict({
                'developer_token': creds.get('developer_token', ''),
                'oauth2_mode': 'offline',
                'oauth2_client_id': creds.get('client_id', ''),
                'oauth2_client_secret': creds.get('client_secret', ''),
                'oauth2_refresh_token': creds.get('refresh_token', '')
            })
        except ImportError:
            print("❌ 请先安装 Google Ads SDK: pip install google-ads")
            sys.exit(1)
    
    def _create_dv360_client(self):
        """创建 DV360 客户端"""
        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
            creds = self.credentials.get('dv360', {})
            service_account_file = creds.get('service_account_file', '')
            
            if not os.path.exists(service_account_file):
                raise FileNotFoundError(f"服务账号文件不存在: {service_account_file}")
            
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/display-video']
            )
            
            return build('display-video', 'v1', credentials=credentials)
        except ImportError:
            print("❌ 请先安装 Google API 客户端: pip install google-api-python-client")
            sys.exit(1)
    
    # ========== TikTok 操作 ==========
    
    def tiktok_list_accounts(self) -> List[Dict]:
        """列出 TikTok 账户"""
        client = self.get_client('tiktok')
        # 实际实现需要调用 TikTok API
        return []
    
    def tiktok_create_campaign(self, account_id: str, name: str, budget: int) -> Dict:
        """创建 TikTok 广告系列"""
        client = self.get_client('tiktok')
        # 实际实现需要调用 TikTok API
        return {}
    
    def tiktok_track_pixel(self, pixel_id: str, event_name: str, event_data: Dict) -> Dict:
        """追踪 TikTok Pixel 事件"""
        client = self.get_client('tiktok')
        # 实际实现需要调用 TikTok API
        return {}
    
    # ========== Meta 操作 ==========
    
    def meta_list_accounts(self) -> List[Dict]:
        """列出 Meta 账户"""
        from facebook_business.adaccounts import AdAccount
        accounts = AdAccount.get_accounts()
        return [{'id': acc.id, 'name': acc.name} for acc in accounts]
    
    def meta_create_campaign(self, account_id: str, name: str, objective: str) -> Dict:
        """创建 Meta 广告系列"""
        from facebook_business.adobjects.campaign import Campaign
        from facebook_business.adaccounts import AdAccount
        
        account = AdAccount(account_id)
        campaign = account.create_campaign(
            name=name,
            objective=objective,
            status=Campaign.Status.paused
        )
        campaign.remote_create()
        return {'id': campaign.id, 'name': campaign.name}
    
    def meta_track_pixel(self, pixel_id: str, event_name: str, event_data: Dict) -> Dict:
        """追踪 Meta Pixel 事件"""
        from facebook_business.adobjects.pixel import Pixel
        
        pixel = Pixel(pixel_id)
        event = pixel.create_event(
            event_name=event_name,
            event_time=int(time.time()),
            event_source_url=event_data.get('event_source_url', ''),
            custom_data=event_data.get('custom_data', {})
        )
        event.remote_create()
        return {'id': event.id}
    
    # ========== Google Ads 操作 ==========
    
    def google_list_customers(self) -> List[Dict]:
        """列出 Google Ads 客户"""
        client = self.get_client('google')
        customer_service = client.get_service('CustomerService')
        
        query = "SELECT customer.id, customer.descriptive_name FROM customer"
        response = customer_service.search_stream(customer_id='0', query=query)
        
        customers = []
        for batch in response:
            for customer in batch.results:
                customers.append({
                    'id': customer.id,
                    'name': customer.descriptive_name
                })
        return customers
    
    def google_create_campaign(self, customer_id: str, name: str, budget: int) -> Dict:
        """创建 Google Ads 广告系列"""
        client = self.get_client('google')
        campaign_service = client.get_service('CampaignService')
        
        campaign_operation = client.get_type("CampaignOperation")
        campaign = campaign_operation.create
        campaign.resource_name = f"customers/{customer_id}/campaigns/-"
        campaign.name = name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH
        campaign.status = client.enums.CampaignStatus.PAUSED
        
        response = campaign_service.mutate_campaigns(
            customer_id=customer_id,
            operations=[campaign_operation]
        )
        
        return {'resource_name': response.results[0].resource_name}
    
    # ========== DV360 操作 ==========
    
    def dv360_list_advertisers(self) -> List[Dict]:
        """列出 DV360 广告主"""
        service = self.get_client('dv360')
        # 实际实现需要调用 DV360 API
        return []
    
    def dv360_create_line_item(self, advertiser_id: str, name: str, budget: int) -> Dict:
        """创建 DV360 媒体购买"""
        service = self.get_client('dv360')
        # 实际实现需要调用 DV360 API
        return {}
    
    # ========== 通用操作 ==========
    
    def test_connection(self, platform: str) -> bool:
        """测试平台连接"""
        try:
            client = self.get_client(platform)
            if platform == 'tiktok':
                accounts = self.tiktok_list_accounts()
                return len(accounts) > 0
            elif platform == 'meta':
                accounts = self.meta_list_accounts()
                return len(accounts) > 0
            elif platform == 'google':
                customers = self.google_list_customers()
                return len(customers) > 0
            elif platform == 'dv360':
                advertisers = self.dv360_list_advertisers()
                return len(advertisers) > 0
        except Exception as e:
            print(f"❌ {platform} 连接测试失败: {e}")
            return False
    
    def test_all_connections(self) -> Dict[str, bool]:
        """测试所有平台连接"""
        results = {}
        for platform in self.platforms:
            results[platform] = self.test_connection(platform)
        return results
    
    def get_all_accounts(self) -> Dict[str, List[Dict]]:
        """获取所有平台的账户信息"""
        all_accounts = {}
        for platform in self.platforms:
            try:
                if platform == 'tiktok':
                    all_accounts[platform] = self.tiktok_list_accounts()
                elif platform == 'meta':
                    all_accounts[platform] = self.meta_list_accounts()
                elif platform == 'google':
                    all_accounts[platform] = self.google_list_customers()
                elif platform == 'dv360':
                    all_accounts[platform] = self.dv360_list_advertisers()
            except Exception as e:
                print(f"❌ 获取 {platform} 账户失败: {e}")
                all_accounts[platform] = []
        return all_accounts


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="广告平台统一 API 调用")
    parser.add_argument("--platform", type=str, choices=['tiktok', 'meta', 'google', 'dv360'],
                        help="平台名称")
    parser.add_argument("--action", type=str, required=True,
                        help="操作类型 (list_accounts/create_campaign/track_event等)")
    parser.add_argument("--test", action="store_true", help="测试连接")
    parser.add_argument("--all", action="store_true", help="测试所有平台")
    
    args = parser.parse_args()
    
    client = AdPlatformClient()
    
    if args.test or args.all:
        if args.all:
            results = client.test_all_connections()
            print("\n连接测试结果:")
            for platform, status in results.items():
                status_str = "✅ 成功" if status else "❌ 失败"
                print(f"  {platform}: {status_str}")
        elif args.platform:
            status = client.test_connection(args.platform)
            print(f"{args.platform}: {'✅ 成功' if status else '❌ 失败'}")
        return
    
    if args.platform:
        if args.action == 'list_accounts':
            accounts = getattr(client, f"{args.platform}_list_accounts")()
            print(json.dumps(accounts, indent=2, ensure_ascii=False))
        elif args.action == 'create_campaign':
            # 需要额外参数
            print("请提供必要的参数")
        else:
            print(f"不支持的操作: {args.action}")
    else:
        print("请指定 --platform 参数")


if __name__ == "__main__":
    main()
