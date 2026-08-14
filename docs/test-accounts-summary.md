# 四平台测试账户汇总

## 测试账户信息

| 平台 | 测试账户 ID | 状态 | 说明 |
|------|------------|------|------|
| Meta | 2806375919473667 | ✅ 可用 | 20 个 Campaigns, PAUSED |
| TikTok | 7397068114548195329 | ✅ 可用 | Campaign 1836521788460274 已验证 |
| Google Ads | 2493002626 (MCC) | ✅ 可用 | 有 46 个子账户 |
| DV360 | 5110831 | ✅ 可用 | 多个 Campaigns |

## 已验证功能

### Meta (2806375919473667)
- ✅ Campaign 列表查询
- ✅ Campaign 详情查询
- ⚠️ Ad Set/Ad 查询需要进一步测试

### TikTok (7397068114548195329)
- ✅ Campaign 查询 (1836521788460274)
- ✅ Ad Groups 查询 (10 个)
- ✅ Ads 查询 (10 个)
- 💡 可用于调研完整层级结构

### Google Ads (2493002626 - MCC)
- ✅ MCC 账户查询
- ✅ 子账户列表查询
- ⚠️ 需要分别查询每个子账户的 Campaigns
- 💡 可调研 Campaign 表现、预算分配

### DV360 (5110831)
- ✅ Partner 信息查询
- ✅ Advertisers 列表查询
- ✅ Campaigns 查询
- 💡 可调研 Line Items 和 Flights

## 配置文件位置
- `config/ad_platform_credentials.json`

## 使用方法
```bash
# Meta
python3 scripts/query_campaign.py meta <CAMPAIGN_ID>

# TikTok
python3 scripts/query_tiktok_campaign.py <campaign_id> <advertiser_id>

# Google Ads
python3 scripts/query_google_campaign.py <CAMPAIGN_RESOURCE_NAME>

# DV360
python3 scripts/query_dv360_campaign.py <CAMPAIGN_ID>
```
