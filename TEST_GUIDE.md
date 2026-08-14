# 广告平台 API 测试指南

## 准备工作

### 1. 配置凭证
```bash
# 复制凭证模板
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json

# 编辑凭证文件，填入真实的 API 凭证
nano config/ad_platform_credentials.json
```

### 2. 凭证格式
```json
{
  "tiktok": {
    "access_token": "YOUR_TIKTOK_ACCESS_TOKEN",
    "app_key": "YOUR_TIKTOK_APP_KEY",
    "app_secret": "YOUR_TIKTOK_APP_SECRET",
    "base_url": "https://business-api.tiktok.com/ads"
  },
  "meta": {
    "app_id": "YOUR_META_APP_ID",
    "app_secret": "YOUR_META_APP_SECRET",
    "access_token": "YOUR_META_ACCESS_TOKEN",
    "business_unit_id": "act_YOUR_BUSINESS_UNIT_ID"
  },
  "google": {
    "developer_token": "YOUR_GOOGLE_DEVELOPER_TOKEN",
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "refresh_token": "YOUR_GOOGLE_REFRESH_TOKEN",
    "login_customer_id": "YOUR_GOOGLE_LOGIN_CUSTOMER_ID"
  },
  "dv360": {
    "client_id": "YOUR_DV360_CLIENT_ID",
    "client_secret": "YOUR_DV360_CLIENT_SECRET",
    "refresh_token": "YOUR_DV360_REFRESH_TOKEN",
    "advertiser_id": "YOUR_DV360_ADVERTISER_ID"
  }
}
```

## 测试命令示例

### TikTok Ads
```bash
# 列出账户
python3 scripts/ad_platform_api.py --platform tiktok --action list_accounts

# 列出广告系列
python3 scripts/ad_platform_api.py --platform tiktok --action list_campaigns --account-id act_xxx

# 创建广告系列
python3 scripts/ad_platform_api.py --platform tiktok --action create_campaign --account-id act_xxx --name "Test Campaign" --budget 10000

# 查询报表
python3 scripts/ad_platform_api.py --platform tiktok --action query_report --account-id act_xxx --start 2024-01-01 --end 2024-01-31
```

### Meta Marketing API
```bash
# 列出账户
python3 scripts/ad_platform_api.py --platform meta --action list_accounts

# 列出广告系列
python3 scripts/ad_platform_api.py --platform meta --action list_campaigns --account-id act_xxx

# 创建广告系列
python3 scripts/ad_platform_api.py --platform meta --action create_campaign --account-id act_xxx --name "Test Campaign" --objective traffic

# 查询洞察
python3 scripts/ad_platform_api.py --platform meta --action query_insights --account-id act_xxx --date-preset today
```

### Google Ads API
```bash
# 列出客户
python3 scripts/ad_platform_api.py --platform google --action list_customers

# 列出广告系列
python3 scripts/ad_platform_api.py --platform google --action list_campaigns --customer-id 1234567890

# 创建广告系列
python3 scripts/ad_platform_api.py --platform google --action create_campaign --customer-id 1234567890 --name "Test Campaign"

# 下载报表
python3 scripts/ad_platform_api.py --platform google --action download_report --customer-id 1234567890
```

### DV360 API
```bash
# 列出广告主
python3 scripts/ad_platform_api.py --platform dv360 --action list_advertisers

# 列出 Line Items
python3 scripts/ad_platform_api.py --platform dv360 --action list_line_items --advertiser-id 12345

# 创建 Line Item
python3 scripts/ad_platform_api.py --platform dv360 --action create_line_item --advertiser-id 12345 --name "Test Line Item"

# 获取报表
python3 scripts/ad_platform_api.py --platform dv360 --action get_report --advertiser-id 12345
```

## 常见问题

### Q: 如何获取 TikTok Access Token？
A: 
1. 访问 https://business-api.tiktok.com/portal
2. 创建应用获取 App Key 和 App Secret
3. 使用 OAuth 流程获取 Access Token

### Q: 如何获取 Meta Access Token？
A:
1. 访问 https://developers.facebook.com/apps/
2. 创建应用并获取 App ID 和 App Secret
3. 使用 Graph API Explorer 生成 Access Token
4. 确保包含 `ads_management`、`ads_read` 权限

### Q: 如何获取 Google Ads Developer Token？
A:
1. 访问 https://developers.google.com/google-ads/api/docs/start
2. 注册 Google Ads API 账号
3. 申请 Developer Token
4. 使用 OAuth 流程获取 Refresh Token

### Q: 如何获取 DV360 凭证？
A:
1. 访问 Google Marketing Platform 管理界面
2. 创建 Service Account
3. 下载 JSON 密钥文件
4. 在 DV360 中授权该 Service Account

## 测试检查清单

- [ ] TikTok: 能列出账户
- [ ] TikTok: 能创建广告系列
- [ ] TikTok: 能查询报表
- [ ] Meta: 能列出账户
- [ ] Meta: 能创建广告系列
- [ ] Meta: 能查询洞察
- [ ] Meta: Instagram 功能正常
- [ ] Meta: WhatsApp 功能正常
- [ ] Google: 能列出客户
- [ ] Google: 能创建广告系列
- [ ] Google: 能下载报表
- [ ] DV360: 能列出广告主
- [ ] DV360: 能创建 Line Item
- [ ] DV360: 能获取报表

## 下一步

如果以上测试都通过，可以考虑：
1. 实现批量操作功能
2. 添加异步支持
3. 实现错误重试机制
4. 添加监控告警功能
