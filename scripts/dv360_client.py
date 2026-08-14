#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DV360 API 客户端
OAuth2 流程: JWT -> Refresh Token -> Access Token -> API
"""

import json
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any

CREDENTIALS_FILE = Path(__file__).parent.parent / "config" / "ad_platform_credentials.json"


class DV360Client:
    """DV360 API 客户端"""
    
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE_URL = "https://displayvideo.googleapis.com/v1"
    
    SCOPES = [
        "https://www.googleapis.com/auth/display-video",
        "https://www.googleapis.com/auth/display-video-user-management"
    ]
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.partner_id = config.get('partner_id', '')
        self.service_account_email = config.get('service_account_email', '')
        self.jwt_assertion = config.get('jwt_assertion', '')
        self.refresh_token = config.get('refresh_token', '')
        self.access_token = config.get('access_token', '')
        self.token_expiry = 0
    
    def _load_credentials(self):
        """从配置文件加载凭证"""
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, 'r') as f:
                config = json.load(f)
                dv360_config = config.get('dv360', {})
                self.partner_id = dv360_config.get('partner_id', self.partner_id)
                self.refresh_token = dv360_config.get('refresh_token', self.refresh_token)
                self.access_token = dv360_config.get('access_token', self.access_token)
    
    def _save_credentials(self):
        """保存凭证到配置文件"""
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, 'r') as f:
                config = json.load(f)
            config['dv360']['refresh_token'] = self.refresh_token
            config['dv360']['access_token'] = self.access_token
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    
    def exchange_jwt_for_refresh_token(self) -> bool:
        """
        使用 JWT Assertion 换取 Refresh Token
        
        Returns:
            bool: 是否成功
        """
        if not self.jwt_assertion:
            print("❌ 缺少 JWT Assertion")
            return False
        
        print(f"🔑 正在使用 JWT 换取 Refresh Token...")
        print(f"   Partner ID: {self.partner_id}")
        print()
        
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': self.jwt_assertion
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data, timeout=30)
            result = response.json()
            
            if 'refresh_token' in result:
                self.refresh_token = result['refresh_token']
                if 'access_token' in result:
                    self.access_token = result['access_token']
                    self.token_expiry = int(time.time()) + result.get('expires_in', 3600)
                self._save_credentials()
                print("✅ Refresh Token 获取成功")
                print(f"   Access Token: {self.access_token[:50]}...")
                print()
                return True
            else:
                error = result.get('error', 'Unknown error')
                message = result.get('error_description', '')
                print(f"❌ 获取 Refresh Token 失败: {error}")
                if message:
                    print(f"   {message}")
                print()
                return False
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            print()
            return False
    
    def refresh_access_token(self) -> bool:
        """
        使用 Refresh Token 换取新的 Access Token
        
        Returns:
            bool: 是否成功
        """
        if not self.refresh_token:
            print("❌ 缺少 Refresh Token，请先调用 exchange_jwt_for_refresh_token()")
            return False
        
        # 检查 token 是否过期
        if self.access_token and time.time() < self.token_expiry - 60:
            return True  # Token 还有效
        
        print(f"🔄 正在刷新 Access Token...")
        print()
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': 'dv-360-test@dv360-test-363908.iam.gserviceaccount.com',  # 需要从 JSON key 获取
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data, timeout=30)
            result = response.json()
            
            if 'access_token' in result:
                self.access_token = result['access_token']
                self.token_expiry = int(time.time()) + result.get('expires_in', 3600)
                self._save_credentials()
                print("✅ Access Token 刷新成功")
                print(f"   Token: {self.access_token[:50]}...")
                print()
                return True
            else:
                error = result.get('error', 'Unknown error')
                message = result.get('error_description', '')
                print(f"❌ 刷新 Access Token 失败: {error}")
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
        if not self.access_token or time.time() >= self.token_expiry:
            if not self.refresh_access_token():
                return None
        
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
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
    
    def list_line_items(self, limit: int = 10) -> Optional[Dict]:
        """列出 Line Items"""
        endpoint = f"/partners/{self.partner_id}/lineItems"
        params = {'pageSize': limit}
        print(f"📋 正在查询 Line Items (limit={limit})")
        print()
        return self._make_request('GET', endpoint, params=params)
    
    def list_campaigns(self, limit: int = 10) -> Optional[Dict]:
        """列出 Campaigns（通过 Line Items）"""
        endpoint = f"/partners/{self.partner_id}/lineItems"
        params = {'pageSize': limit}
        print(f"📋 正在查询 Campaigns (limit={limit})")
        print()
        return self._make_request('GET', endpoint, params=params)
    
    def get_campaign(self, line_item_id: str) -> Optional[Dict]:
        """获取单个 Line Item/Campaign 详情"""
        endpoint = f"/partners/{self.partner_id}/lineItems/{line_item_id}"
        print(f"📋 正在查询 Line Item: {line_item_id}")
        print()
        return self._make_request('GET', endpoint)


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
        
        if action == 'init':
            # 初始化：获取 Refresh Token
            client._load_credentials()
            success = client.exchange_jwt_for_refresh_token()
            if success:
                print("✅ 初始化完成，可以使用 API 了")
            sys.exit(0 if success else 1)
        
        elif action == 'partner':
            # 查询 Partner 信息
            client._load_credentials()
            client.refresh_access_token()
            partner = client.get_partner()
            if partner:
                print(json.dumps(partner, indent=2, ensure_ascii=False))
        
        elif action == 'line-items':
            # 查询 Line Items
            client._load_credentials()
            client.refresh_access_token()
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            items = client.list_line_items(limit)
            if items:
                print(json.dumps(items, indent=2, ensure_ascii=False))
        
        elif action == 'campaign':
            # 查询特定 Campaign
            client._load_credentials()
            client.refresh_access_token()
            if len(sys.argv) > 2:
                campaign_id = sys.argv[2]
                campaign = client.get_campaign(campaign_id)
                if campaign:
                    print(json.dumps(campaign, indent=2, ensure_ascii=False))
        
        else:
            print(f"❌ 未知操作: {action}")
            print("可用操作: init, partner, line-items, campaign")
            sys.exit(1)
    
    else:
        # 默认：显示帮助
        print("""
DV360 API 客户端

用法:
  python3 dv360_client.py init              # 初始化：获取 Refresh Token
  python3 dv360_client.py partner           # 查询 Partner 信息
  python3 dv360_client.py line-items [n]    # 查询 Line Items (默认10个)
  python3 dv360_client.py campaign <id>     # 查询特定 Campaign

示例:
  python3 scripts/dv360_client.py init
  python3 scripts/dv360_client.py partner
  python3 scripts/dv360_client.py line-items 5
""")


if __name__ == "__main__":
    main()
