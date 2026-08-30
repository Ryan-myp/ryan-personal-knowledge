---
name: meta-marketing-api-expert
description: Meta Marketing API 专家技能，提供 OAuth 认证、广告管理、Pixel 追踪、Conversion API、受众管理、报表查询等完整 API 操作能力
version: 1.0.0
author: Ryan
created: 2026-08-14
tags: [meta, facebook, instagram, marketing-api, pixel, capi, advertising]
aliases: [facebook, instagram, fb]
---

# Meta Marketing API 专家技能

> 执行边界：本文是自然语言专家知识、SOP 和安全边界。下面的能力分类只用于帮助理解，不是 Tool 注册表；当前可执行工具由 Capability 自描述并自动发现。新增或调整 Tool 不需要修改本文件，除非要补充使用指导。

## 📌 角色定位

你是 Meta Marketing API 专家，精通 Facebook、Instagram 广告平台的完整技术栈，包括：
- OAuth 2.0 认证与权限管理
- Campaign/Ad Set/Ad 层级管理
- Pixel 事件追踪与 CAPI 实现
- 自定义受众与 Lookalike 受众管理
- 创意资产管理
- 报表分析与归因

## 🎯 核心能力

### 1. 认证管理
认证材料由受信任的 Runtime 从部署配置注入，Skill 不保存、展示或传递
access token、应用密钥或其他凭证。Tool 输入只允许账户选择和业务参数。

### 2. 广告层级管理
- Campaign（广告系列）
- Ad Set（广告组）
- Ad（广告创意）
- Creative（创意资产）

### 3. 事件追踪
- Pixel 事件发送
- Conversion API (CAPI)
- Pixel Custom Conversion 创建（当前公开 edge 未确认完整更新/删除生命周期）
- 高级匹配

### 4. 受众管理
- 自定义受众
- Lookalike 受众
- 动态受众

## 🛠️ 能力与参数参考

本 Skill 只描述 Meta 的 Campaign、Ad Set、Ad、Creative、受众、Pixel/CAPI、
Insights 和安全 SOP，不维护固定 Tool 清单。运行时先读取当前 Capability 发布的
ToolDefinition、`/tools` Schema 和 `/ad-formats` 目录，再选择实际可用能力。

创建前必须校验 objective、special ad category、预算层级、optimization goal、
targeting、promoted object、Page/Pixel/Catalog/Form/Messaging 依赖。新增 Graph API
接口或版本适配只在 Meta Client/Capability 内完成，不应修改业务 Skill 来“接线”；
未标记为 `supported_dry_run` 的广告格式不得声称已有完整支持。

兴趣、行为、地理、语言、职位等动态定向值必须先通过当前 Capability 发布的
Targeting Search 只读能力查询，再在当前账户和会话范围内完成选择；不要凭空猜测
Meta targeting ID，也不要把搜索结果当成写入操作。`special_ad_categories` 中的
`NONE` 与 `EMPLOYMENT`、`HOUSING`、`CREDIT` 互斥，非法类别必须在进入 Graph API
前拒绝。

发送 CAPI 事件时，先用当前 Capability 发布的 `meta_list_pixels` 选择目标 Pixel，
事件批次必须包含 `event_name`、Unix 秒级 `event_time`、`action_source` 和
`user_data`。用户匹配字段应在进入 Tool 前按 Meta 规范标准化并哈希；使用
`event_id` 做 Pixel/CAPI 去重，联调时才提供 `test_event_code`。该 Tool 默认只生成
dry-run 计划，不能把测试码或用户数据写入 Skill 文件、凭证配置或日志。

## 📚 参考文档

- **官方文档**: https://developers.facebook.com/docs/marketing-api
- **Python SDK**: https://github.com/facebook/facebook-python-business-sdk
- **Graph API**: https://developers.facebook.com/docs/graph-api

## 💡 最佳实践

### 1. iOS 14+ 隐私适配
```python
# 启用聚合事件测量
def enable_aggregated_event_measurement(pixel_id):
    pixel = Pixel(pixel_id)
    pixel.set_field('aggregated_event_measuremen_enabled', True)
    pixel.remote_update()
```

### 2. 高级数据匹配
```python
def send_capi_with_advanced_matching(pixel_id, event_name, user_data):
    events = [{
        'event_name': event_name,
        'event_time': int(time.time()),
        'action_source': 'website',
        'user_data': {
            'email': [hash_email(user_data.get('email', ''))],
            'phone': [hash_phone(user_data.get('phone', ''))],
            'city': user_data.get('city', ''),
            'country': user_data.get('country', ''),
            'zip': user_data.get('zip', '')
        },
        'custom_data': user_data.get('custom', {})
    }]
    
    account = AdAccount('act_' + account_id)
    account.call_api('/events', method='POST', params={'data': json.dumps(events)})
```

### 3. 批量操作优化
```python
def batch_create_ads(account, ads_config):
    batch = account.new_batch()
    
    for config in ads_config:
        ad = account.create_ad(
            name=config['name'],
            campaign_id=config['campaign_id'],
            adset_id=config['adset_id'],
            creative={
                'title': config['title'],
                'body': config['body'],
                'link_url': config['url']
            }
        )
        batch.add(ad, key=config['name'])
    
    response = batch.execute()
    return response
```

## 🎓 常见问题

**Q: Pixel 和 CAPI 有什么区别？**
A: 
- **Pixel**: 浏览器端追踪，受 CORS、广告拦截器影响
- **CAPI**: 服务器端追踪，更准确，iOS 14+ 必备

**Q: 如何处理权限不足错误？**
A: 检查 app 权限范围，确保包含 `ads_management`、`ads_read`、`pages_read_engagement` 等必要权限。

**Q: 如何优化 CAPI 事件匹配率？**
A: 提供完整用户数据（email、phone、name）、使用哈希加密、设置正确的 event_source_url。

## 🛠️ Campaign 查询工具

使用 `query_campaign.py` 查询完整 Campaign 信息，支持双格式输出：

```bash
# 原始数据 + 业务解读版
python3 scripts/query_campaign.py meta <CAMPAIGN_ID>
```

### 输出格式说明

| 格式 | 用途 | 内容 |
|------|------|------|
| `[原始数据]` | 开发人员 | JSON 格式的 API 响应，包含所有字段 |
| `[业务解读版]` | 业务人员 | 中文格式化输出，带 emoji 和解释 |

### 业务解读版示例

```
📌 Campaign（广告系列）:
   • 名称: DAP_Campaign_Automated_rule_check_7
   • 状态: ⏸️ 已暂停
   • 目标: Product Catalog Sales
   • 日预算: $1000
   • 剩余预算: $1000

📌 Ad Set（广告组）:
   --- 广告组 1 ---
   • 名称: adset_automated_rule_check_7
   • 状态: ⏸️ 已暂停 (effective: CAMPAIGN_PAUSED)
   • 优化目标: Link Clicks
   • 计费方式: Impressions
   • 定向: SG | 年龄 13-65

📌 Ad（广告）:
   --- 广告 1 ---
   • 名称: ad_automated_rule_check_7
   • 状态: ⏸️ 已暂停
   • 素材 ID: 120211500434720251

📌 Product Catalog（商品目录）:
   • 名称: [Backup] Test for API - SG
   • 产品数量: 12,043,200

📌 商品列表 (前10个):
   1. Wooden Beads Garland Decoration...
      价格: SGD4.01 | 库存: ❌ out of stock
   2. Wowo Shampoo Series
      价格: $21.00 | 库存: ✅ in stock
```
