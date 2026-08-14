#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DV360 API 客户端 (v4)
OAuth2 流程: JWT -> Access Token -> API
"""

import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"
SERVICE_ACCOUNT_FILE = Path(__file__).parent.parent / "config" / "dv360_service_account.json"
API_BASE_URL = "https://displayvideo.googleapis.com/v4"


class DV360Client:
    """DV360 API v4 客户端"""
    
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.partner_id = config.get('partner_id', '')
        self.service_account_email = config.get('service_account_email', '')
        self.jwt_assertion = config.get('jwt_assertion', '')
        self.access_token = config.get('access_token', '')
        self.token_expiry = 0
    
    def _load_credentials(self):
        """从配置文件加载凭证"""
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, 'r') as f:
                config = json.load(f)
                dv360_config = config.get('dv360', {})
                self.partner_id = dv360_config.get('partner_id', self.partner_id)
                self.access_token = dv360_config.get('access_token', self.access_token)
    
    def _save_credentials(self):
        """保存凭证到配置文件"""
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, 'r') as f:
                config = json.load(f)
            config['dv360']['access_token'] = self.access_token
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    
    def _load_service_account(self) -> Optional[Dict]:
        """加载 Service Account Key"""
        if not SERVICE_ACCOUNT_FILE.exists():
            return None
        with open(SERVICE_ACCOUNT_FILE, 'r') as f:
            return json.load(f)
    
    def refresh_access_token(self) -> bool:
        """
        使用 JWT Assertion 获取 Access Token
        
        Returns:
            bool: 是否成功
        """
        # 检查 token 是否有效
        if self.access_token and time.time() < self.token_expiry - 60:
            return True
        
        sa_key = self._load_service_account()
        if not sa_key:
            print("❌ 缺少 Service Account Key")
            return False
        
        print(f"🔑 正在获取 Access Token...")
        print(f"   Partner ID: {self.partner_id}")
        print()
        
        # 生成 JWT
        import jwt as pyjwt
        now = int(time.time())
        header = {"typ": "JWT", "alg": "RS256", "kid": sa_key['private_key_id']}
        payload = {
            "iss": sa_key['client_email'],
            "sub": sa_key['client_email'],
            "aud": self.TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
            "scope": " ".join(self.config.get('scopes', []))
        }
        
        jwt_token = pyjwt.encode(payload, sa_key['private_key'], algorithm='RS256', headers={'kid': sa_key['private_key_id']})
        
        # 获取 Access Token
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': jwt_token
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data, timeout=30)
            result = response.json()
            
            if 'access_token' in result:
                self.access_token = result['access_token']
                self.token_expiry = now + result.get('expires_in', 3600)
                self._save_credentials()
                print("✅ Access Token 获取成功")
                print(f"   Token: {self.access_token[:50]}...")
                print()
                return True
            else:
                error = result.get('error', 'Unknown error')
                message = result.get('error_description', '')
                print(f"❌ 获取 Access Token 失败: {error}")
                if message:
                    print(f"   {message}")
                print()
                return False
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            print()
            return False
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                      data: Optional[Dict] = None) -> Optional[Dict]:
        """发送 API 请求"""
        if not self.refresh_access_token():
            return None
        
        url = f"{API_BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                print(f"❌ 不支持的 HTTP 方法: {method}")
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ API 请求失败: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    def get_partner(self) -> Optional[Dict]:
        """获取 Partner 信息"""
        endpoint = f"/partners/{self.partner_id}"
        print(f"📋 正在查询 Partner 信息: {self.partner_id}")
        print()
        return self._make_request('GET', endpoint)
    
    def list_partners(self) -> Optional[Dict]:
        """列出所有 Partners"""
        endpoint = "/partners"
        print(f"📋 正在查询 Partners 列表")
        print()
        return self._make_request('GET', endpoint)
    
    def list_advertisers(self, limit: int = 10) -> Optional[Dict]:
        """列出 Advertisers"""
        endpoint = "/advertisers"
        params = {'pageSize': limit, 'partnerId': self.partner_id}
        print(f"📋 正在查询 Advertisers (limit={limit})")
        print()
        return self._make_request('GET', endpoint, params=params)
    
    def get_advertiser(self, advertiser_id: str) -> Optional[Dict]:
        """获取单个 Advertiser 详情"""
        endpoint = f"/advertisers/{advertiser_id}"
        print(f"📋 正在查询 Advertiser: {advertiser_id}")
        print()
        return self._make_request('GET', endpoint)
    
    def list_campaigns(self, advertiser_id: str, limit: int = 10) -> Optional[Dict]:
        """列出 Campaigns"""
        endpoint = f"/advertisers/{advertiser_id}/campaigns"
        params = {'pageSize': limit}
        print(f"📋 正在查询 Campaigns (advertiser_id={advertiser_id}, limit={limit})")
        print()
        return self._make_request('GET', endpoint, params=params)
    
    def get_campaign(self, advertiser_id: str, campaign_id: str) -> Optional[Dict]:
        """获取单个 Campaign 详情"""
        endpoint = f"/advertisers/{advertiser_id}/campaigns/{campaign_id}"
        print(f"📋 正在查询 Campaign: {campaign_id}")
        print()
        return self._make_request('GET', endpoint)
    
    def list_line_items(self, advertiser_id: str, limit: int = 10) -> Optional[Dict]:
        """列出 Line Items"""
        endpoint = f"/advertisers/{advertiser_id}/lineItems"
        params = {'pageSize': limit}
        print(f"📋 正在查询 Line Items (advertiser_id={advertiser_id}, limit={limit})")
        print()
        return self._make_request('GET', endpoint, params=params)


def main():
    """主函数 - 演示用法"""
    import sys
    
    # 加载配置
    if not CREDENTIALS_FILE.exists():
        print(f"❌ 配置文件不存在: {CREDENTIALS_FILE}")
        sys.exit(1)
    
    with open(CREDENTIALS_FILE, 'r') as f:
        config = json.load(f)
    
    dv360_config = config.get('dv360', {})
    
    if not dv360_config:
        print("❌ DV360 配置不存在")
        sys.exit(1)
    
    client = DV360Client(dv360_config)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        action = sys.argv[1]
        
        if action == 'partner':
            # 查询 Partner 信息
            client._load_credentials()
            partner = client.get_partner()
            if partner:
                print(json.dumps(partner, indent=2, ensure_ascii=False))
        
        elif action == 'partners':
            # 列出所有 Partners
            client._load_credentials()
            partners = client.list_partners()
            if partners:
                print(json.dumps(partners, indent=2, ensure_ascii=False))
        
        elif action == 'advertisers':
            # 查询 Advertisers
            client._load_credentials()
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            advertisers = client.list_advertisers(limit)
            if advertisers:
                print(json.dumps(advertisers, indent=2, ensure_ascii=False))
        
        elif action == 'campaigns':
            # 查询 Campaigns
            client._load_credentials()
            if len(sys.argv) > 2:
                advertiser_id = sys.argv[2]
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
                campaigns = client.list_campaigns(advertiser_id, limit)
                if campaigns:
                    print(json.dumps(campaigns, indent=2, ensure_ascii=False))
        
        elif action == 'campaign':
            # 查询特定 Campaign
            client._load_credentials()
            if len(sys.argv) > 3:
                advertiser_id = sys.argv[2]
                campaign_id = sys.argv[3]
                campaign = client.get_campaign(advertiser_id, campaign_id)
                if campaign:
                    print(json.dumps(campaign, indent=2, ensure_ascii=False))
        
        elif action == 'line-items':
            # 查询 Line Items
            client._load_credentials()
            if len(sys.argv) > 2:
                advertiser_id = sys.argv[2]
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
                line_items = client.list_line_items(advertiser_id, limit)
                if line_items:
                    print(json.dumps(line_items, indent=2, ensure_ascii=False))
        
        else:
            print(f"❌ 未知操作: {action}")
            print("可用操作: partner, partners, advertisers, campaigns, campaign, line-items")
            sys.exit(1)
    
    else:
        # 默认：显示帮助
        print("""
DV360 API v4 客户端

用法:
  python3 dv360_client.py partner              # 查询 Partner 信息
  python3 dv360_client.py partners             # 列出所有 Partners
  python3 dv360_client.py advertisers [n]      # 查询 Advertisers (默认10个)
  python3 dv360_client.py campaigns <advertiser_id> [n]  # 查询 Campaigns
  python3 dv360_client.py campaign <adv_id> <camp_id>    # 查询特定 Campaign
  python3 dv360_client.py line-items <advertiser_id> [n] # 查询 Line Items

示例:
  python3 scripts/dv360_client.py partner
  python3 scripts/dv360_client.py advertisers 10
  python3 scripts/dv360_client.py campaigns 123456789 10
""")


if __name__ == "__main__":
    main()
