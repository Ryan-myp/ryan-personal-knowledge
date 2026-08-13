# 广告平台专家 Skills 使用指南

> **版本**: v1.0.0
> **更新时间**: 2026-08-14
> **作者**: Ryan

---

## 📌 概述

本指南介绍如何使用四大广告平台的专家 Skills 和 API 工具集，帮助您快速配置和使用 TikTok、Meta、Google Ads、DV360 的完整 API 能力。

---

## 🎯 四大专家 Skills

| Skill | 平台 | 主要功能 | 状态 |
|-------|------|---------|------|
| **tiktok-ads-expert** | TikTok Ads | 认证、Spark Ads、Pixel、CAPI | ✅ 已配置 |
| **meta-marketing-api-expert** | Meta/Facebook | 认证、Campaign 管理、CAPI | ✅ 已配置 |
| **google-ads-api-expert** | Google Ads | 认证、批量操作、智能出价 | ✅ 已配置 |
| **dv360-expert** | Display & Video 360 | 媒体购买、创意管理、报表 | ✅ 已配置 |
| **ad-platform-tools** | 通用工具集 | 统一认证、跨平台同步 | ✅ 已配置 |

---

## 🔧 快速开始

### 1. 配置凭证

```bash
# 复制凭证模板
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json

# 编辑凭证文件（务必保密！）
nano config/ad_platform_credentials.json
```

**凭证文件示例：**
```json
{
  "tiktok": {
    "app_key": "tk-xxxxxxxx",
    "app_secret": "xxxxxxxx",
    "access_token": "access-token-xxxxxxxx"
  },
  "meta": {
    "app_id": "123456789",
    "app_secret": "xxxxxxxx",
    "access_token": "EAABxxxxxxxx"
  },
  "google": {
    "developer_token": "xxxxxxxx",
    "client_id": "xxxxxxxx.apps.googleusercontent.com",
    "client_secret": "xxxxxxxx",
    "refresh_token": "1//xxxxxxxx",
    "customer_id": "123-456-7890"
  },
  "dv360": {
    "service_account_file": "path/to/service-account.json",
    "customer_id": "123456789"
  }
}
```

### 2. 测试连接

```bash
# 测试所有平台
python3 scripts/ad_platform_api.py --all --test

# 测试单个平台
python3 scripts/ad_platform_api.py --platform meta --test
```

### 3. 获取账户列表

```bash
# TikTok
python3 scripts/ad_platform_api.py --platform tiktok --action list_accounts

# Meta
python3 scripts/ad_platform_api.py --platform meta --action list_accounts

# Google Ads
python3 scripts/ad_platform_api.py --platform google --action list_accounts
```

---

## 📚 各平台详细指南

### TikTok Ads API

#### 认证流程
1. 在 TikTok for Business 创建应用
2. 获取 App Key 和 App Secret
3. 使用 OAuth 2.0 获取 Access Token
4. Token 有效期 24 小时，需定期刷新

#### 核心 API
```python
from tiktokads.business.sdk import Client

client = Client(
    access_token='YOUR_TOKEN',
    app_key='YOUR_KEY',
    app_secret='YOUR_SECRET'
)

# 创建广告系列
campaign = client.create_campaign(...)

# 创建 Spark Ads
spark_ad = client.create_spark_ad(
    adgroup_id='adgroup_123',
    video_id='video_456',
    creator_id='creator_789'
)
```

#### 注意事项
- Spark Ads 需要创作者授权
- 每小时 API 调用限制：10,000 次
- 支持沙箱环境测试

---

### Meta Marketing API

#### 认证流程
1. 在 Meta for Developers 创建应用
2. 获取 App ID 和 App Secret
3. 使用 OAuth 2.0 获取 Access Token
4. Token 有效期约 60 天

#### 核心 API
```python
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign

FacebookAdsApi.init(app_id, app_secret, access_token)

# 获取账户
account = AdAccount('act_123456789')

# 创建广告系列
campaign = account.create_campaign(
    name='Summer Sale',
    objective='SALES',
    status=Campaign.Status.paused
)
campaign.remote_create()
```

#### 注意事项
- iOS 14+ 需要使用 CAPI
- 支持聚合事件测量
- 建议启用高级数据匹配

---

### Google Ads API

#### 认证流程
1. 在 Google Cloud Console 创建项目
2. 获取 Developer Token
3. 配置 OAuth 2.0 凭据
4. 获取 Refresh Token

#### 核心 API
```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 获取服务
campaign_service = client.get_service('CampaignService')

# 创建广告系列
campaign_operation = client.get_type("CampaignOperation")
campaign = campaign_operation.create
campaign.name = "Summer Sale"
campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH

response = campaign_service.mutate_campaigns(
    customer_id='1234567890',
    operations=[campaign_operation]
)
```

#### 注意事项
- 支持 Streaming Mutate 批量操作
- 每日 Get 请求配额：100,000
- 每日 Mutate 请求配额：10,000

---

### Display & Video 360 API

#### 认证流程
1. 联系 Google 销售团队申请 API 访问
2. 创建服务账号
3. 下载 JSON 密钥文件
4. 配置 OAuth 2.0 服务账号认证

#### 核心 API
```python
from googleapiclient.discovery import build
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    'service-account.json',
    scopes=['https://www.googleapis.com/auth/display-video']
)

service = build('display-video', 'v1', credentials=credentials)

# 创建媒体购买
line_item = {
    'advertiserId': '123456',
    'name': 'Summer Campaign',
    'budgetMicros': '100000000',
    'flight': {
        'startTimeMicros': '1692000000000000',
        'endTimeMicros': '1694678400000000'
    }
}

result = service.lineItems().create(
    advertiserId='123456',
    body=line_item
).execute()
```

#### 注意事项
- 需要客户支持申请
- 适合大型企业级广告主
- 支持 DSP 对接

---

## 🛠️ 常用工具命令

### 账户管理
```bash
# 列出所有账户
python3 scripts/ad_platform_api.py --all --action list_accounts

# 同步账户信息
python3 scripts/ad_platform_api.py --platform meta --action sync_accounts
```

### 广告管理
```bash
# 创建广告系列
python3 scripts/ad_platform_api.py --platform google --action create_campaign --name "Summer Sale" --budget 1000

# 列出广告系列
python3 scripts/ad_platform_api.py --platform meta --action list_campaigns
```

### 报表查询
```bash
# 获取报表数据
python3 scripts/ad_platform_api.py --platform tiktok --action get_report --start 2026-08-01 --end 2026-08-14
```

### 事件追踪
```bash
# 追踪转化事件
python3 scripts/ad_platform_api.py --platform meta --action track_event --pixel_id "123456" --event "Purchase"
```

---

## 📊 技能匹配指南

| 你的需求 | 推荐 Skill | 说明 |
|---------|-----------|------|
| TikTok 达人广告 | tiktok-ads-expert | Spark Ads 专项优化 |
| Facebook/Instagram 投放 | meta-marketing-api-expert | 完整 Campaign 管理 |
| Google Search/Shopping | google-ads-api-expert | 智能出价与批量操作 |
| 程序化广告采购 | dv360-expert | 媒体购买与创意管理 |
| 跨平台数据同步 | ad-platform-tools | 统一账户与报表聚合 |

---

## 🔐 安全建议

1. **凭证管理**
   - 使用环境变量或密钥管理服务
   - 不要将凭证提交到 Git
   - 定期轮换 Access Token

2. **权限控制**
   - 最小权限原则
   - 定期审计 API 权限
   - 使用子账户隔离不同环境

3. **数据安全**
   - 加密传输敏感数据
   - 遵守各平台数据政策
   - 用户数据脱敏处理

---

## 📚 参考资源

- **TikTok Ads API**: https://business-api.tiktok.com/portal/docs
- **Meta Marketing API**: https://developers.facebook.com/docs/marketing-api
- **Google Ads API**: https://developers.google.com/google-ads/api
- **DV360 API**: https://developers.google.com/display-video/api

---

*本指南基于官方文档编写，确保内容准确、实用、合规。*
