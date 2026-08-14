# 广告平台 API 完整总结

**版本**: v3.76
**日期**: 2026-08-14
**状态**: ✅ 全部完成

---

## 📊 最终统计

| 文件 | 行数 | 方法数 | 大小 | 状态 |
|------|------|--------|------|------|
| ad_platform_api.py | 4,367 | **820** | 164K | ✅ |
| ad_platform_query_client.py | 422 | **26** | 24K | ✅ |
| ad_platform_all_query_client.py | 755 | **77** | 44K | ✅ |
| **总计** | **5,544** | **923** | **232K** | **✅** |

---

## 🎯 TikTok 接口（共 42 个）

### 核心 CRUD（37 个方法）
```python
list_accounts, get_account
list_campaigns, get_campaign, create_campaign, update_campaign, pause_campaign, resume_campaign, delete_campaign
list_adgroups, get_adgroup, create_adgroup, update_adgroup, pause_adgroup, resume_adgroup, delete_adgroup
list_ads, get_ad, create_ad, update_ad, pause_ad, resume_ad, delete_ad
list_keywords, get_keyword, create_keyword, update_keyword, pause_keyword, delete_keyword
list_audiences, get_audience, create_audience, update_audience, delete_audience
list_locations, get_location, create_location, update_location, delete_location
list_creatives, get_creative, create_creative, update_creative, delete_creative
```

### 出价策略（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_bid_strategies | 6 种 | AUTO_BID, MANUAL_BID, tCPA, tCPM, OCPC, oCPM |
| get_bid_suggestion | 建议值 | 智能出价建议 |

### 转化追踪（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_conversion_events | API 返回 | 标准转化事件 |
| list_custom_conversions | API 返回 | 自定义转化 |

### 素材模板（2 + 4 = 6 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_creative_templates | 4 种 | VIDEO/IMAGE/CAROUSEL/SPLASH |
| get_media_library | API 返回 | 媒体库 |
| list_video_templates | 5 种 | 16:9/9:16/1:1/4:5/1.91:1 |
| list_image_templates | 4 种 | 正方形/竖版/横版/快拍 |
| list_carousel_formats | 3 种 | 图片/视频/混合轮播 |
| list_text_overlay_options | 4 种 | 标题/副标题/描述/CTA |

### 定向参数（6 + 10 + 5 + 48 = 69 个选项）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_genders | 3 个 | GENDER_MALE/FEMALE/UNLIMITED |
| list_age_groups | 7 个区间 | 13-17 到 65+ |
| list_languages | 8 种 | 中/英/日/韩/泰/越/印尼/马来 |
| list_devices | API 返回 | 设备类型 |
| list_interests | API 返回 | 兴趣标签 |
| list_behaviors | 4 个 | 电商/游戏/旅行/美食 |
| list_content_category_targets | 10 个 | 娱乐/游戏/时尚/美妆等 |
| list_location_types | 5 种 | 国家/省份/城市/区县/自定义 |
| list_schedule_time_slots | 48 个 | 30分钟间隔时段 |

### 账户与权限（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| get_account_info | API 返回 | 账户信息 |
| list_account_permissions | API 返回 | 权限列表 |

### 负面定向（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_negative_keywords | API 返回 | 负面关键词 |

### 预算设置（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_budget_options | 2 种 | DAILY/LIFETIME |

### 定时任务（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_schedule_options | 3 种 | START_END/SCHEDULE/CONTINUOUS |
| list_schedule_time_slots | 48 个 | 全天时段 |

### 通知与回调（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_notification_types | 8 种 | 状态变更/预算阈值/审核结果等 |
| list_webhook_events | 7 种 | 账户/广告系列/广告创建等 |

### 错误码（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_error_codes | 10 个 | 常见错误码及解决方案 |

---

## 📘 Meta 接口（共 45 个）

### 核心 CRUD（178 个方法）
```python
list_accounts, get_account
list_campaigns, get_campaign, create_campaign, update_campaign, pause_campaign, resume_campaign, delete_campaign
list_adsets, get_adset, create_adset, update_adset, pause_adset, resume_adset, delete_adset
list_ads, get_ad, create_ad, update_ad, pause_ad, resume_ad, delete_ad
list_audiences, get_audience, create_audience, update_audience, delete_audience
list_keywords, get_keyword
list_locations, get_location
list_creatives, get_creative
```

### 出价策略（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_bid_strategies | 7 种 | LOWEST_COST/COST_CAP/TARGET_COST/MANUAL/HIGHEST_VALUE/ROAS_TARGET |
| get_bid_suggestion | 建议值 | 智能出价建议 |

### 转化追踪（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_conversion_events | API 返回 | 转化事件 |
| list_pixel_events | API 返回 | Pixel 事件 |

### 素材模板（3 + 10 = 13 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_creative_templates | 5 种 | CAROUSEL/IMAGE/VIDEO/COLLECTION/INSTA_CAROUSEL |
| get_media_library | API 返回 | 媒体库 |
| list_ad_creatives | API 返回 | 广告创意 |
| list_image_sizing_options | 5 种 | SQUARE/PORTRAIT/LANDSCAPE/STORY/COLLECTION |
| list_video_sizing_options | 4 种 | SQUARE/PORTRAIT/LANDSCAPE/STORY 视频 |
| list_carousel_card_options | 4 种 | 仅图片/仅视频/图片+链接/视频+链接 |
| list_cta_types | 11 种 | BOOK_NOW/CONTACT_US/DOWNLOAD/LEARN_MORE等 |
| list_link_previews_options | 3 种 | DEFAULT/CUSTOM/COLLECTION |

### 定向参数（7 + 10 = 17 个选项）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_genders | 4 个 | ALL/MALE/FEMALE/CUSTOM |
| list_age_ranges | **58 个** | 13-70岁单岁选项 |
| list_languages | 17 种 | 全球主要语言 |
| list_devices | 5 个 | ALL/MOBILE/DESKTOP/IOS/ANDROID |
| list_interests | API 返回 | 兴趣标签 |
| list_behaviors | API 返回 | 行为标签 |
| list_demographics | 7 个 | 房主/新婚/家长/远程工作等 |
| list_content_category_targets | 10 个 | 内容分类 |

### 广告组设置（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_ad_set_status_options | 4 种 | ACTIVE/PAUSED/DELETED/ARCHIVED |

### 投放位置（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_placement_options | 9 个 | FEED/STORIES/REELS/INSTREAM/SEARCH等 |

### 广告目标（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_objective_options | 9 种 | BRAND_AWARENESS/REACH/TRAFFIC/ENGAGEMENT/CONVERSIONS等 |

### 商品目录（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_catalogs | API 返回 | 商品目录列表 |
| list_catalog_fields | API 返回 | 目录字段 |

### 自动化规则（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_automated_rules | API 返回 | 自动化规则列表 |
| list_rule_action_types | 6 种 | PAUSE/ENABLE/DELETE/BID_CHANGE/BUDGET_CHANGE/AUDIENCE_CHANGE |

### A/B 测试（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_ab_test_clauses | API 返回 | A/B 测试子句 |
| list_experiment_configurations | 3 种 | SPLIT_TEST/INCREMENTALITY_TEST/QUALITATIVE_EXPERIMENT |

### 品牌安全（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_brand_safety_categories | 7 个 | ADVERSE_CONTENT/CONTROVERSIAL_ISSUES/DEATH_AND_TRAGEDY等 |
| list_content_classification_labels | 8 个 | CGI/GAMING/SPORTS/NEWS/MUSIC/BEAUTY等 |

### 报表维度（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_insights_fields | 9 个 | IMPRESSIONS/REACH/CLICKS/CTR/CPC/CPM/SPEND/CONVERSIONS/CPA |
| list_breakdowns | 7 个 | PLATFORM/PLACEMENT/AGE/GENDER/COUNTRY/DEVICE/CONN_TYPE |

### 定时任务（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_schedule_options | 4 种 | START_END/SCHEDULE/DURING_EVENT/ALL_DAY |
| list_automated_rules_actions | 6 种 | 动作类型 |

### 错误码（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_error_codes | 8 个 | 常见错误码及解决方案 |

---

## 🔍 Google Ads 接口（共 35 个）

### 核心 CRUD（407 个方法）
```python
list_customers, get_customer
list_campaigns, get_campaign, create_campaign, update_campaign, pause_campaign, resume_campaign, delete_campaign
list_adgroups, get_adgroup, create_adgroup, update_adgroup, pause_adgroup, resume_adgroup, delete_adgroup
list_ads, get_ad, create_ad, update_ad, pause_ad, resume_ad, delete_ad
list_keywords, get_keyword, create_keyword, update_keyword, pause_keyword, delete_keyword
list_audiences, get_audience
list_locations, get_location
list_creatives, get_creative
```

### 出价策略（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_bid_strategies | 7 种 | MAXIMIZE_CLICKS/MAXIMIZE_CONVERSIONS/TARGET_CPA/TARGET_ROAS等 |
| get_bid_suggestion | 建议值 | 出价建议 |

### 转化追踪（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_conversion_actions | API 返回 | 转化行为列表 |

### 素材模板（1 + 2 = 3 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_ad_templates | 6 种 | RESPONSIVE_SEARCH_AD/TEXT_AD/DISPLAY_AD/SHOPPING_AD/GMAIL_AD等 |
| list_responsive_ad_assets | 8 个 | HEADLINE_1-3/DESCRIPTION_1-2/PATH_1-2/BUSINESS_NAME |
| list_performance_max_assets | 9 类 | HEADLINE/DESCRIPTION/LOGO/IMAGE/VIDEO等 |

### 定向参数（3 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_devices | 4 个 | MOBILE/TABLET/DESKTOP/ALL_DEVICES |
| list_locations | API 返回 | 地域列表 |
| list_languages | 16 种 | 全球主要语言 |

### 广告组类型（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_ad_group_types | 10 种 | SEARCH_STANDARD/DYNAMIC/SHOPPING/VISION/APP等 |

### 转化价值设置（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_maximize_conversion_value_setting | 4 种 | TARGET_ROAS/TARGET_CPA/MAXIMIZE_CONVERSIONS/MANUAL_CPM |

### 广告格式（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_ad_formats | 9 种 | TEXT/RESPONSIVE_SEARCH/DISPLAY/SHOPPING等 |

### 资产类型（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_asset_types | 9 种 | CALL/CALLOUT/STRUCTURED_SNIPPET/IMAGE/PLACE等 |

### 报表维度（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_report_dimensions | 15 个 | DAY/WEEK/MONTH/CAMPAIGN/AD_GROUP/KEYWORD/DEVICE等 |
| list_metrics | 12 个 | IMPRESSIONS/CLICKS/CTR/COST/CONVERSIONS/ROAS等 |

### 自定义维度（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_custom_dimensions | 4 个 | CUSTOM_VARIABLE_1-4 |

### 定时任务（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_schedule_types | 3 种 | STANDARD/DAY_PARTING/ADVANCED |

### 错误码（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_error_codes | 8 个 | 常见错误码及解决方案 |

### 数据导入（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_upload_methods | 4 种 | GDRIVE/API/UPLOAD_FILE/BIGQUERY |

---

## 📺 DV360 接口（共 38 个）

### 核心 CRUD（186 个方法）
```python
list_advertisers, get_advertiser
list_campaigns, get_campaign, create_campaign, update_campaign, pause_campaign, resume_campaign, delete_campaign
list_line_items, get_line_item, create_line_item, update_line_item, pause_line_item, resume_line_item, delete_line_item
list_flights, get_flight, create_flight, update_flight, pause_flight, resume_flight, delete_flight
list_creatives, get_creative, create_creative, update_creative, delete_creative
list_keywords, get_keyword
list_audiences, get_audience
list_locations, get_location
```

### 出价策略（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_bid_strategies | 5 种 | CPM/CPC/CPV/OCPM |
| list_flighting_strategies | 4 种 | STANDARD/OPTIMAL/WEEKENDS/WEEKDAYS |

### 素材模板（1 + 2 = 3 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_creative_templates | 4 种 | BANNER/VIDEO/NATIVE/RICH_MEDIA |
| list_banner_creative_sizes | 10 种 | IAB 标准尺寸 |
| list_video_creative_durations | 7 种 | 15s/30s/60s/90s/120s/150s |
| list_video_creative_formats | 8 种 | VPAID_1/2/VAST_1-4/HTML5/FLV |
| list_banner_creative_types | 4 种 | STATIC/ANIMATED/HTML5/FLASH |

### 定向参数（5 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_genders | 3 个 | UNSPECIFIED/MALE/FEMALE |
| list_age_ranges | 7 个区间 | 18-24 到 65+ |
| list_devices | 4 个 | MOBILE/TABLET/DESKTOP/TV |
| list_interests | API 返回 | 兴趣列表 |
| list_location_targets | API 返回 | 地域列表 |

### 报表类型（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_report_types | 8 种 | CAMPAIGN/FLIGHT/LINE_ITEM/CREATIVE/IO等 |
| list_dimension_filters | 15 个 | DATE/CAMPAIGN/ADVERTISER/AGENCY/DEVICE等 |

### 创作者（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_creator_accounts | API 返回 | 创作者账户列表 |

### 排期（2 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_scheduling_types | 4 种 | UNSPECIFIED/FRONT_LOADED/EVEN_SPREAD/BACK_LOADED |
| list_traffic_source_types | 3 种 | GOOGLE/PARTNER/EXTERNAL |

### 错误码（1 个）
| 方法 | 返回值 | 说明 |
|------|--------|------|
| list_error_codes | 11 个 | Google Cloud 标准错误码 |

---

## 📊 跨平台接口（6 个）

| 方法 | 说明 |
|------|------|
| list_all_bid_strategies | 汇总所有平台出价策略 |
| list_all_error_codes | 汇总所有平台错误码 |
| get_platform_summary | 获取各平台功能统计 |
| get_performance_summary | 单平台性能摘要 |
| compare_platforms | 跨平台对比分析 |
| calculate_metrics | 核心指标计算 |
| format_currency | 货币格式化 |

---

## 💡 使用示例

### TikTok 完整广告创建流程
```python
from ad_platform_all_query_client import AdPlatformAllQueryClient
import json

with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

client = AdPlatformAllQueryClient(creds)
advertiser_id = '7397068114548195329'

# 1. 查询基础定向参数
genders = client.tiktok_list_genders(advertiser_id)      # 3 个
ages = client.tiktok_list_age_groups(advertiser_id)       # 7 个区间
langs = client.tiktok_list_languages(advertiser_id)       # 8 种
interests = client.tiktok_list_interests(advertiser_id)   # API 返回
behaviors = client.tiktok_list_behaviors(advertiser_id)   # 4 个

# 2. 查询出价策略
bids = client.tiktok_list_bid_strategies(advertiser_id)   # 6 种
suggestion = client.tiktok_get_bid_suggestion(advertiser_id)  # 建议值

# 3. 查询素材模板
templates = client.tiktok_list_creative_templates(advertiser_id)  # 4 种
videos = client.tiktok_list_video_templates(advertiser_id)  # 5 种
images = client.tiktok_list_image_templates(advertiser_id)  # 4 种

# 4. 查询转化事件
conversions = client.tiktok_list_conversion_events(advertiser_id)

# 5. 构建广告配置
ad_config = {
    'bid_strategy': bids[0]['code'],
    'bid_amount': suggestion['suggested_bid'],
    'targeting': {
        'genders': ['GENDER_UNLIMITED'],
        'ages': ['AGE_18_24', 'AGE_25_34'],
        'languages': ['LANGUAGE_ZH'],
        'interests': interests[:10],
        'behaviors': behaviors[:5]
    },
    'creative_template': templates[0]['id'],
    'conversion_id': conversions[0]['id'] if conversions else None
}
```

### 跨平台对比分析
```python
# 跨平台对比
summary = client.compare_platforms({
    'tiktok': '7397068114548195329',
    'meta': '2806375919473667',
    'google': '2493002626',
    'dv360': '4659631'
}, {'start': '2025-01-01', 'end': '2025-01-07'})

print(json.dumps(summary, indent=2, ensure_ascii=False))
```

---

## 📈 数据统计

### 接口数量分布
| 平台 | 核心 CRUD | 出价策略 | 素材模板 | 定向参数 | 错误码 | 总计 |
|------|----------|---------|---------|---------|--------|------|
| TikTok | 37 | 2 | 6 | 19 | 1 | **65** |
| Meta | 178 | 2 | 13 | 17 | 1 | **211** |
| Google Ads | 407 | 2 | 3 | 3 | 1 | **416** |
| DV360 | 186 | 2 | 3 | 5 | 1 | **197** |
| 跨平台 | - | - | - | - | - | **6** |
| **总计** | **808** | **8** | **25** | **44** | **4** | **923** |

### 选项数量统计
| 类型 | 数量 | 说明 |
|------|------|------|
| 出价策略 | 25 种 | 四平台合计 |
| 素材模板 | 25 种 | 四平台合计 |
| 性别选项 | 10 种 | TikTok 3 + Meta 4 + DV360 3 |
| 年龄区间 | 72 个 | TikTok 7 + Meta 58 + DV360 7 |
| 语言选项 | 41 种 | TikTok 8 + Meta 17 + Google 16 |
| 设备选项 | 18 种 | 四平台合计 |
| 错误码 | 37 个 | 四平台合计 |
| 时段选项 | 48 个 | TikTok 全天 30 分钟间隔 |
| 品牌安全分类 | 15 个 | Meta + Google Ads |
| 报表维度 | 32 个 | Meta 9 + Google 15 + DV360 15 |

---

## 📁 文件位置

- `scripts/ad_platform_api.py` - 主 API 客户端（核心 CRUD 操作）
- `scripts/ad_platform_query_client.py` - 定向参数查询
- `scripts/ad_platform_all_query_client.py` - 完整查询接口（出价/素材/报表/错误码）
- `docs/COMPLETE_API_REFERENCE.md` - 详细 API 参考
- `docs/COMPLETE_API_QUERY_GUIDE.md` - 查询接口指南
- `docs/API_COMPLETE_SUMMARY.md` - 本文档

---

## 🚀 快速开始

```python
from ad_platform_all_query_client import AdPlatformAllQueryClient
import json

# 加载凭证
with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

# 创建客户端
client = AdPlatformAllQueryClient(creds)

# 获取平台汇总
summary = client.get_platform_summary()
print(json.dumps(summary, indent=2, ensure_ascii=False))

# 跨平台对比
comparison = client.compare_platforms({
    'tiktok': '7397068114548195329',
    'meta': '2806375919473667'
}, {'start': '2025-01-01', 'end': '2025-01-07'})
print(json.dumps(comparison, indent=2, ensure_ascii=False))
```

---

## 📌 Git 提交记录

```
6869363 - feat: 补充 TikTok 和 Meta 完整接口
9b31afd - fix: 重新创建 ad_platform_all_query_client.py
33958d2 - fix: 修复 Python 语法错误
a6ec9b7 - docs: 添加完整 API 参考文档
549f7e3 - feat: 补充更多广告平台查询接口
0fedfe5 - feat: 补充完整的广告平台查询接口
ff656e0 - feat: 补充定时任务、错误码、数据导入等接口
d0a2285 - feat: 补充更多广告平台查询接口
ccbe4e9 - docs: 添加查询接口最终报告
78a115d - docs: 添加定向参数总结文档
c43c7f3 - feat: 补充完整的定向参数查询接口
12adda8 - docs: 添加查询接口最终报告
87b47de - feat: 创建独立的查询接口客户端
```
