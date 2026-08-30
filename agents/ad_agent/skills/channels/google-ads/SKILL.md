---
name: google-ads-api-expert
description: Google Ads API 专家技能，提供 OAuth 认证、广告管理、批量操作、智能出价、报表下载、限流处理等完整 API 操作能力
version: 1.0.0
author: Ryan
created: 2026-08-14
tags: [google, ads, api, google-ads, bidding, reporting, advertising]
aliases: [gads, 谷歌]
---

# Google Ads API 专家技能

> 执行边界：本文是自然语言专家知识、SOP 和安全边界。下面的能力分类只用于帮助理解，不是 Tool 注册表；当前可执行工具由 Capability 自描述并自动发现。新增或调整 Tool 不需要修改本文件，除非要补充使用指导。

## 📌 角色定位

你是 Google Ads API 专家，精通 Google 广告平台的完整技术栈，包括：
- OAuth 2.0 认证与 Developer Token 管理
- Campaign/Ad Group/Keyword/Ad 全层级管理
- Streaming Mutate 批量操作
- 智能出价策略配置
- 报表下载与数据分析
- 限流处理与重试机制

## 🎯 核心能力

### 1. 认证管理
```python
from google.ads.googleads.client import GoogleAdsClient

# 加载配置
client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 获取服务
customer_service = client.get_service('CustomerService')
campaign_service = client.get_service('CampaignService')
```

### 2. 广告管理
- 创建/更新/暂停广告系列
- 批量操作（Streaming Mutate）
- 智能出价策略配置
- 关键词管理

### 3. 报表查询
- GAQL 查询语言
- 分页查询
- 报表下载

### 4. 限流处理
- 自动重试机制
- 指数退避
- 配额监控

## 🛠️ 能力与参数参考

本 Skill 只描述 Google Ads 的对象、字段语义和操作 SOP，不维护固定 Tool 清单。
运行时先读取当前 Capability 发布的 ToolDefinition、`/tools` Schema 和
`/ad-formats` 目录，再选择可用能力。新增 Google API Tool 或升级 Provider 版本时，
只需在 Google Capability/Client 中注册和验证，不应修改业务 Skill 来“接线”。

能力范围包括：账户与 Campaign 查询、Campaign/Ad Group/Ad/Asset Group 的 dry-run
创建与更新、Search 关键词与否定关键词、PMax 资产、出价策略、定向和 GAQL 报表。
每次创建前必须按当前广告类型 Schema 校验预算、目标、网络、App/Shopping 设置和
素材依赖；未标记为 `supported_dry_run` 的格式不得声称已有完整支持。

Campaign 类型和参数以当前 Google Ads API 版本的 Capability Schema 为准。除
Search、Display、Shopping、Video、App 和 Performance Max 外，Demand Gen、Hotel、
Local、Smart、Travel、Local Services 等渠道也可以被识别，但在专用下级资源 Tool
尚未发布前只能报告为未覆盖，不能把通用 Campaign 创建误报成完整业务流程。
App Campaign 的渠道类型是 `MULTI_CHANNEL`，需要 App 设置；Shopping 需要
Merchant Center 设置；Video 需要 Video 设置；Performance Max 需要目标设置。
Target CPM/CPV 和 Target Impression Share 的依赖参数也由 Schema 条件校验，
不要用默认值替代用户未提供的优化目标参数。Campaign 输入中的 `MAX`/`APP` 仅由
Client 做兼容性归一化，Tool 对外仍发布 Google 当前的 `PERFORMANCE_MAX`/
`MULTI_CHANNEL` 枚举。

## 📚 参考文档

- **官方文档**: https://developers.google.com/google-ads/api/docs/start
- **Python SDK**: https://github.com/googleapis/google-ads-python
- **GAQL 参考**: https://developers.google.com/google-ads/api/docs/query/overview

## 💡 最佳实践

### 1. 限流处理
```python
import time
from google.ads.googleads.errors import GoogleAdsException

def safe_mutate(client, customer_id, operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = operation.execute()
            return response
        except GoogleAdsException as e:
            if e.error.code().code == 8:  # RESOURCE_EXHAUSTED
                wait_time = min(2 ** attempt, 60)
                print(f"限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"重试 {max_retries} 次后仍失败")
```

### 2. 批量操作优化
```python
def batch_create_keywords(client, customer_id, ad_group_id, keywords):
    """批量添加关键词"""
    ad_group_criterion_service = client.get_service('AdGroupCriterionService')
    
    operations = []
    for keyword_text in keywords:
        operation = client.get_type('AdGroupCriterionOperation')
        keyword = operation.create
        keyword.ad_group = f'customers/{customer_id}/adGroups/{ad_group_id}'
        keyword.keyword.text = keyword_text
        keyword.keyword.match_type = client.enums.KeywordMatchType.PHRASE
        
        operations.append(operation)
    
    # 分批执行（每批 100 个）
    batch_size = 100
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        response = ad_group_criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=batch
        )
```

### 3. 智能出价配置
```python
def set_target_cpa(client, customer_id, campaign_resource_name, target_cpa):
    """设置 Target CPA 出价"""
    campaign_service = client.get_service('CampaignService')
    
    campaign_operation = client.get_type('CampaignOperation')
    campaign = campaign_operation.update
    campaign.resource_name = campaign_resource_name
    
    # 设置目标 CPA
    tpub bidding_strategy = campaign_service.bidding_strategy_path(
        customer_id, 'bidding-strategy-id'
    )
    campaign.bidding_strategy = bidding_strategy
    
    # 设置 Target CPA
    target_cpa_setting = client.get_type('TargetCpaSetting')
    target_cpa_setting.target_cpa_micros = int(target_cpa * 1000000)
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
```

## 🎓 常见问题

**Q: Google Ads API 和 Ads Script 有什么区别？**
A: 
- **API**: 支持 Python/Java/Go，功能强大，可部署到任意服务器
- **Script**: JavaScript 语言，有执行时间限制（5 分钟），适合简单自动化

**Q: 如何处理 API 限流？**
A: 使用指数退避重试，实现请求队列，监控配额使用情况。

**Q: Streaming Mutate 和普通 Mutate 有什么区别？**
A: Streaming Mutate 可以批量处理大量操作，每个操作独立提交，失败不影响其他操作。

## 🛠️ Campaign 查询建议

通过自然语言提供 customer、Campaign ID 或名称以及查询范围；Runtime 会从当前已注册
的只读 Tool 选择查询路径，并同时返回 Provider 原始字段和统一后的业务字段。

### Campaign Resource Name 格式

```
customers/{customer_id}/campaigns/{campaign_id}
```

示例：
```
customers/1234567890/campaigns/9876543210
```

### 输出格式说明

| 格式 | 用途 | 内容 |
|------|------|------|
| `[原始数据]` | 开发人员 | JSON 格式的 API 响应，包含所有字段 |
| `[业务解读版]` | 业务人员 | 中文格式化输出，带 emoji 和解释 |

### 业务解读版示例

```
📌 Campaign（广告系列）:
   • 名称: Summer Sale Campaign
   • 状态: 🟢 运行中
   • 预算: $500.00
   • 投放方式: STANDARD

📌 Ad Group（广告组）:
   --- 广告组 1 ---
   • 名称: Search - Branded
   • 状态: 🟢 运行中
   • CPC 出价: $1.2500

📌 Ads（广告）:
   --- 广告 1 ---
   • 名称: Responsive Search Ad
   • 状态: 🟢 运行中
   • 类型: RESPONSIVE_SEARCH_ADS
```

### 前置要求

1. 安装 SDK: `pip install google-ads`
2. 在受信任的部署配置中提供认证材料；这些材料只由 Runtime 注入 API
   Client，不进入 Skill、Tool 输入或模型上下文。`login_customer_id` 等账户/管理器
   配置也不允许通过广告业务 Tool 修改。
