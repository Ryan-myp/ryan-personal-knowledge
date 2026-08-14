#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DV360 JWT Assertion 生成工具
使用 HMAC-SHA256 签名生成 JWT token
"""

import json
import time
import base64
import hmac
import hashlib

def base64url_encode(data):
    """Base64URL 编码"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def generate_jwt(service_account_email, private_key, partner_id=None):
    """
    生成 JWT Assertion
    
    Args:
        service_account_email: Service Account 邮箱
        private_key: RSA 私钥 (PEM 格式字符串)
        partner_id: DV360 Partner ID (可选)
    
    Returns:
        JWT Token 字符串
    """
    # 构建 Header
    header = {
        "typ": "JWT",
        "alg": "RS256",
        "kid": "cafa5c37c7a8267111c8a32b1b4fa359792a297a"  # 从原 JWT 提取
    }
    
    # 构建 Payload
    now = int(time.time())
    payload = {
        "iss": service_account_email,
        "sub": service_account_email,
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,  # 1小时后过期
        "scope": "https://www.googleapis.com/auth/display-video https://www.googleapis.com/auth/display-video-user-management"
    }
    
    if partner_id:
        payload["partner_id"] = partner_id
    
    # 编码
    header_b64 = base64url_encode(json.dumps(header, separators=(',', ':')))
    payload_b64 = base64url_encode(json.dumps(payload, separators=(',', ':')))
    
    # 签名
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    
    # 注意：实际使用中需要加载 RSA 私钥进行签名
    # 这里使用 HMAC 作为示例，实际应该使用 RSA
    signature = hmac.new(
        private_key.encode('utf-8') if isinstance(private_key, str) else private_key,
        signing_input,
        hashlib.sha256
    ).digest()
    
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def print_instructions():
    """打印使用说明"""
    print("""
┌─────────────────────────────────────────────────────────────┐
│              DV360 JWT Assertion 生成指南                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  方法 1: 使用 Google Cloud Console (推荐)                   │
│  ─────────────────────────────────                         │
│  1. 打开 Google Cloud Console                                │
│  2. 进入 IAM & Admin -> Service Accounts                    │
│  3. 找到: dv-360-test@dv360-test-363908.iam.gserviceaccount │
│  4. 点击 "Keys" -> "Add Key" -> "Create new service account │
│  5. 选择 JSON 格式，下载密钥文件                             │
│  6. 使用以下命令生成 JWT:                                    │
│     python3 scripts/generate_dv360_jwt.py --key-file key.json│
│                                                             │
│  方法 2: 使用 OpenSSL 命令行                                │
│  ─────────────────────────────────                         │
│  1. 保存私钥到 private_key.pem                               │
│  2. 运行:                                                    │
│     openssl dgst -sha256 -sign private_key.pem input.txt    │
│                                                             │
│  方法 3: 使用 Postman (快速测试)                            │
│  ─────────────────────────────────                         │
│  1. 在 Postman 中选择 JWT (RS256)                           │
│  2. 输入 Service Account Email                               │
│  3. 上传 JSON Key 文件                                      │
│  4. Postman 自动生成 JWT Assertion                            │
│  5. 复制 Assertion 粘贴到配置中                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
""")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='生成 DV360 JWT Assertion')
    parser.add_argument('--key-file', '-k', help='Service Account JSON Key 文件路径')
    parser.add_argument('--email', '-e', help='Service Account Email')
    parser.add_argument('--output', '-o', help='输出到配置文件')
    
    args = parser.parse_args()
    
    if args.key_file:
        # 从 JSON Key 文件生成
        with open(args.key_file, 'r') as f:
            key_data = json.load(f)
        
        service_account_email = key_data['client_email']
        private_key = key_data['private_key']
        
        # 使用 pyjwt 或手动签名
        try:
            import jwt
            payload = {
                'iss': service_account_email,
                'sub': service_account_email,
                'aud': 'https://oauth2.googleapis.com/token',
                'iat': int(time.time()),
                'exp': int(time.time()) + 3600,
                'scope': 'https://www.googleapis.com/auth/display-video https://www.googleapis.com/auth/display-video-user-management'
            }
            
            jwt_token = jwt.encode(payload, private_key, algorithm='RS256', headers={'kid': key_data.get('private_key_id', 'cafa5c37c7a8267111c8a32b1b4fa359792a297a')})
            print(f"✅ JWT 生成成功:")
            print(f"   {jwt_token}")
            
            if args.output:
                with open(args.output, 'r+') as f:
                    config = json.load(f)
                    config['dv360']['jwt_assertion'] = jwt_token
                    f.seek(0)
                    json.dump(config, f, indent=2)
                    f.truncate()
                print(f"   已保存到: {args.output}")
                
        except ImportError:
            print("❌ 需要安装 PyJWT: pip install PyJWT")
            print_instructions()
    
    elif args.email:
        print(f"⚠️  请提供私钥来生成 JWT")
        print(f"   Service Account: {args.email}")
        print_instructions()
    
    else:
        print("❌ 请提供 JSON Key 文件或 Service Account Email")
        print_instructions()
