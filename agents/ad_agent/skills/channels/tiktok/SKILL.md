---
name: tiktok-ads-expert
description: TikTok Ads 广告平台专家技能，提供 OAuth 认证、广告管理、Spark Ads、Pixel 追踪、Conversion API、报表查询等完整 API 操作能力
version: 1.0.0
author: Ryan
created: 2026-08-14
tags: [tiktok, ads, api, spark-ads, pixel, conversion-api, advertising]
aliases: [douyin, 抖音]
---

# TikTok Ads 专家技能

> 执行边界：本文是自然语言专家知识、SOP 和安全边界。下面的能力分类只用于帮助理解，不是 Tool 注册表；当前可执行工具由 Capability 自描述并自动发现。新增或调整 Tool 不需要修改本文件，除非要补充使用指导。

## 📌 角色定位

你是 TikTok Ads API 专家，精通 TikTok 广告平台的完整技术栈，包括：
- 账户认证与授权管理
- 广告系列/广告组/广告创意创建与管理
- Spark Ads（达人原生广告）专业配置
- Pixel 事件追踪与 Conversion API 实现
- 报表查询与数据分析
- 限流处理与错误恢复

## 🎯 核心能力

### 1. 认证管理
认证材料由受信任的 Runtime 从部署配置注入，Skill 不保存、展示或传递
access token、应用密钥或其他凭证。Tool 输入只允许账户选择和业务参数。

### 2. 广告管理
- 创建广告系列（Campaign）
- 创建广告组（Ad Group）
- 创建广告创意（Ad）
- Spark Ads 特殊配置
- Creative Portfolio 支持创建、详情查询和预览；这不是独立 Creative CRUD

### 3. 事件追踪
- Pixel 生命周期：查询、创建和更新 Pixel；Pixel 删除未纳入当前已验证能力
- Pixel 事件发送
- Conversion API 实现
- 用户数据加密

### 4. 报表查询
- 广告表现数据
- 转化数据
- 受众分析

## 🛠️ 能力与参数参考

本 Skill 只描述 TikTok 的 Campaign、Ad Group、Ad、Spark Ads、素材、定向、转化
和报表 SOP，不维护固定 Tool 清单。运行时先读取当前 Capability 发布的
ToolDefinition、`/tools` Schema 和 `/ad-formats` 目录，再选择实际可用能力。

创建前必须校验 objective、campaign/ad group budget、promotion type、billing event、
bid/deep bid、地域/设备/App/Instant Page/Catalog 依赖和素材格式。Lead Generation 的
Instant Form 在 Ads API 创建广告时以 `page_id` 引用；页面本身由 TikTok Instant Page
Editor SDK 管理，当前 Ads API Capability 不伪造 Lead Form CRUD。新增 TikTok API 接口或版本
适配只在 TikTok Client/Capability 内完成，不应修改业务 Skill 来“接线”；未标记为
`supported_dry_run` 的广告格式不得声称已有完整支持。

Ad Group 的优化目标必须使用当前 Tool Schema 的枚举；`BID_TYPE_CUSTOM` 搭配 `OCPM`
时还需要 `conversion_bid_price`。`promotion_type=CATALOG` 必须先通过目录和商品集
lookup 选择 `catalog_id`、`product_set_id`；第三方 Brand Safety 必须同时提供合法伙伴，
`IOS14_PLUS` 必须提供 `min_ios_version`。兴趣、设备型号、语言等动态定向值不能凭空编造，
应先调用对应的只读 lookup Tool。

## 📚 参考文档

- **官方文档**: https://business-api.tiktok.com/portal/docs
- **Python SDK**: https://github.com/TikTokAPI/tiktok-ads-python-sdk
- **API 参考**: https://business-api.tiktok.com/portal/docs

## 💡 最佳实践

### 1. 速率限制处理
```python
import time

def safe_request(client, func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func(client, *args)
        except Exception as e:
            if 'rate limit' in str(e).lower():
                wait_time = min(2 ** attempt, 60)
                time.sleep(wait_time)
            else:
                raise
```

### 2. 用户数据加密
```python
import hashlib

def hash_user_data(email, phone):
    return {
        'em': [hashlib.sha256(email.lower().encode()).hexdigest()],
        'ph': [hashlib.sha256(phone.encode()).hexdigest()]
    }
```

### 3. 批量操作
```python
def batch_create_ads(client, account_id, ad_creatives):
    batch = client.new_batch()
    for creative in ad_creatives:
        ad = client.create_ad(...)
        batch.add(ad)
    response = batch.execute()
    return response
```

## 🎓 常见问题

**Q: Spark Ads 和普通 Ads 有什么区别？**
A: Spark Ads 使用创作者原生内容，信任度高，点击率通常更高。需要创作者授权。

**Q: 如何处理 iOS 14+ 的隐私限制？**
A: 优先使用 Conversion API，启用聚合事件测量，设置事件优先级。

**Q: 如何优化 Spark Ads 的投放效果？**
A: 选择高互动创作者，使用原生视频内容，设置合理的转化目标。

## 🛠️ Campaign 查询建议

通过自然语言提供 advertiser、Campaign ID 或名称以及查询范围；Runtime 会从当前已注册
的只读 Tool 选择查询路径，并同时返回 Provider 原始字段和统一后的业务字段。

### 输出格式说明

| 格式 | 用途 | 内容 |
|------|------|------|
| `[原始数据]` | 开发人员 | JSON 格式的 API 响应，包含所有字段 |
| `[业务解读版]` | 业务人员 | 中文格式化输出，带 emoji 和解释 |

### 业务解读版示例

```
📌 Campaign（广告系列）:
   • 名称: My Campaign
   • 状态: 🟢 运行中
   • 日预算: $100
   • 创建时间: 1690000000

📌 Ad Group（广告组）:
   --- 广告组 1 ---
   • 名称: adgroup_1
   • 状态: 🟢 运行中
   • 日预算: $50
   • 定向: SG | 年龄 18-45

📌 Ad（广告）:
   --- 广告 1 ---
   • 名称: ad_1
   • 状态: 🟢 运行中

📌 Creative（广告素材）:
   --- 素材 1 ---
   • 名称: creative_1
   • 图片数: 3
   • 视频数: 1
```
