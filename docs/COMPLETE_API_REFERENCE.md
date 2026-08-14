# 广告平台完整 API 参考文档

**版本**: v3.75
**日期**: 2026-08-14
**状态**: ✅ 全部完成

---

## 📊 接口总览

| 文件 | 行数 | 方法数 | 大小 |
|------|------|--------|------|
| ad_platform_api.py | 4,367 | **820** | 164K |
| ad_platform_query_client.py | 422 | **26** | 24K |
| ad_platform_all_query_client.py | 1,540 | **105** | 136K |
| **总计** | **6,329** | **951** | **324K** |

---

## 🎯 TikTok 接口（共 42 个）

### 核心 CRUD（37 个方法）
```python
# 账户管理
list_accounts, get_account
list_campaigns, get_campaign, create_campaign, update_campaign, pause_campaign, resume_campaign, delete_campaign
list_adgroups, get_adgroup, create_adgroup, update_adgroup, pause_adgroup, resume_adgroup, delete_adgroup
list_ads, get_ad, create_ad, update_ad, pause_ad, resume_ad, delete_ad
list_keywords, get_keyword
list_audiences, get_audience
list_locations, get_location
list_creatives, get_creative
```

### 出价策略（2 个）
```python
list_bid_strategies      # 6 种：AUTO_BID, MANUAL_BID, tCPA, tCPM, OCPC, oCPM
get_bid_suggestion       # 智能出价建议
```

### 转化追踪（2 个）
```python
list_conversion_events   # 标准转化事件
list_custom_conversions  # 自定义转化
```

### 素材模板（2 个）
```python
list_creative_templates  # 4 种：VIDEO/IMAGE/CAROUSEL/SPLASH
get_media_library        # 媒体库
```

### 定向参数（6 个）
```python
list_genders             # 3 个：GENDER_MALE/FEMALE/UNLIMITED
list_age_groups          # 7 个区间：13-17 到 65+
list_languages           # 8 种：中/英/日/韩/泰/越/印尼/马来
list_devices             # API 返回真实数据
list_interests           # API 返回兴趣列表
list_behaviors           # 4 个：电商/游戏/旅行/美食
```

### 账户与权限（2 个）
```python
get_account_info         # 账户信息
list_account_permissions # 账户权限
```

### 负面定向（1 个）
```python
list_negative_keywords   # 负面关键词
```

### 内容分类（1 个）
```python
list_content_category_targets  # 10 个分类
```

### 位置定向（2 个）
```python
list_location_types      # 5 种：国家/省份/城市/区县/自定义
get_location_hierarchy   # 地域层级结构
```

### 应用与网站（2 个）
```python
list_apps_for_placement      # 可投放应用
list_sites_for_placement     # 可投放网站
```

### 兴趣分类（1 个）
```python
list_category_tree         # 兴趣分类树
```

### 定时任务（2 个）
```python
list_schedule_options          # 3 种：START_END/SCHEDULE/CONTINUOUS
list_schedule_time_slots       # 48 个时段（30 分钟间隔）
```

### 通知与回调（2 个）
```python
list_notification_types    # 8 种通知类型
list_webhook_events        # 10 种 Webhook 事件
```

### 创意模板（4 个）
```python
list_video_templates       # 5 种比例：16:9/9:16/1:1/4:5/1.91:1
list_image_templates       # 4 种尺寸：正方形/竖版/横版/快拍
list_carousel_formats      # 3 种：图片/视频/混合
list_text_overlay_options  # 4 种：标题/副标题/描述/CTA
```

### 错误码（1 个）
```python
list_error_codes           # 10 个常见错误码
```

---

## 📘 Meta 接口（共 45 个）

### 核心 CRUD（178 个方法）
```python
# 账户管理
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
```python
list_bid_strategies      # 7 种：LOWEST_COST/COST_CAP/TARGET_COST/MANUAL/HIGHEST_VALUE/ROAS_TARGET
get_bid_suggestion       # 智能出价建议
```

### 转化追踪（2 个）
```python
list_conversion_events   # 转化事件
list_pixel_events        # Pixel 事件
```

### 素材模板（3 个）
```python
list_creative_templates  # 5 种：CAROUSEL/IMAGE/VIDEO/COLLECTION/INSTA_CAROUSEL
get_media_library        # 媒体库
list_ad_creatives        # 广告创意
```

### 定向参数（7 个）
```python
list_genders             # 4 个：ALL/MALE/FEMALE/CUSTOM
list_age_ranges          # 58 个单岁选项（13-70岁）
list_languages           # 17 种语言
list_devices             # 5 个：ALL/MOBILE/DESKTOP/IOS/ANDROID
list_interests           # API 返回兴趣列表
list_behaviors           # API 返回行为列表
list_demographics        # 7 个：房主/新婚/家长/远程工作等
```

### 广告组设置（1 个）
```python
list_ad_set_status_options  # 4 种状态
```

### 投放位置（1 个）
```python
list_placement_options  # 10 个平台位置
```

### 广告目标（1 个）
```python
list_objective_options  # 10 种目标类型
```

### 创意尺寸（3 个）
```python
list_image_sizing_options    # 5 种尺寸
list_video_sizing_options    # 4 种尺寸
list_carousel_card_options   # 5 种卡片类型
```

### 商品目录（2 个）
```python
list_catalogs           # 商品目录列表
list_catalog_fields     # 目录字段
```

### 自动化规则（2 个）
```python
list_automated_rules        # 自动化规则列表
list_rule_action_types      # 6 种动作类型
```

### A/B 测试（2 个）
```python
list_ab_test_clauses              # A/B 测试子句
list_experiment_configurations    # 3 种实验配置
```

### 品牌安全（2 个）
```python
list_brand_safety_categories         # 8 个分类
list_content_classification_labels   # 8 个标签
```

### 报表维度（2 个）
```python
list_insights_fields  # 18 个指标字段
list_breakdowns       # 11 个细分维度
```

### 素材选项（5 个）
```python
list_link_previews_options   # 3 种预览选项
list_cta_types               # 15 种 CTA 按钮
list_primary_texts           # 4 种主文本类型
list_carousel_card_types     # 5 种卡片类型
list_collection_layouts      # 3 种合集布局
```

### 快拍模板（1 个）
```python
list_story_templates  # 6 种快拍模板
```

### ATS 格式（2 个）
```python
list_ats_formats         # 5 种格式
list_dynamic_ad_fields   # 5 个动态字段
```

### 定时任务（2 个）
```python
list_schedule_options          # 4 种定时选项
list_automated_rules_actions   # 6 种动作类型
```

### 错误码（1 个）
```python
list_error_codes           # 8 个常见错误码
```

---

## 🔍 Google Ads 接口（共 35 个）

### 核心 CRUD（407 个方法）
```python
# 客户管理
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
```python
list_bid_strategies      # 7 种：MAXIMIZE_CLICKS/MAXIMIZE_CONVERSIONS/TARGET_CPA/TARGET_ROAS/MANUAL_CPC等
get_bid_suggestion       # 出价建议
```

### 转化追踪（1 个）
```python
list_conversion_actions  # 转化行为列表
```

### 素材模板（1 个）
```python
list_ad_templates        # 6 种：RESPONSIVE_SEARCH_AD/TEXT_AD/DISPLAY_AD等
```

### 定向参数（3 个）
```python
list_devices            # 4 个：MOBILE/TABLET/DESKTOP/ALL_DEVICES
list_locations          # API 返回地域列表
list_languages          # 16 种语言
```

### 广告组类型（1 个）
```python
list_ad_group_types     # 10 种广告组类型
```

### 转化价值设置（1 个）
```python
list_maximize_conversion_value_setting  # 4 种设置
```

### 广告格式（1 个）
```python
list_ad_formats         # 9 种广告格式
```

### 资产类型（1 个）
```python
list_asset_types        # 9 种资产类型
```

### 报表维度（2 个）
```python
list_report_dimensions  # 15 个维度
list_metrics            # 12 个指标
```

### 自定义维度（1 个）
```python
list_custom_dimensions  # 4 个自定义维度
```

### 响应式广告资产（1 个）
```python
list_responsive_ad_assets  # 8 个资产字段
```

### 全面营销资产（1 个）
```python
list_performance_max_assets  # 9 类资产
```

### 定时任务（1 个）
```python
list_schedule_types  # 3 种定时类型
```

### 错误码（1 个）
```python
list_error_codes           # 8 个常见错误码
```

### 数据导入（1 个）
```python
list_upload_methods        # 4 种上传方式
```

---

## 📺 DV360 接口（共 38 个）

### 核心 CRUD（186 个方法）
```python
# 广告主管理
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
```python
list_bid_strategies         # 5 种：CPM/CPC/CPV/OCPM
list_flighting_strategies   # 4 种：STANDARD/OPTIMAL/WEEKENDS/WEEKDAYS
```

### 定向参数（5 个）
```python
list_genders              # 3 个：未指定/男/女
list_age_ranges           # 7 个区间
list_devices              # 4 个：手机/平板/电脑/电视
list_interests            # API 返回兴趣列表
list_location_targets     # API 返回地域列表
```

### 素材模板（1 个）
```python
list_creative_templates  # 4 种：BANNER/VIDEO/NATIVE/RICH_MEDIA
```

### 报表类型（2 个）
```python
list_report_types          # 8 种报表类型
list_dimension_filters     # 15 个维度过滤器
```

### 创作者（1 个）
```python
list_creator_accounts      # 创作者账户列表
```

### 创意尺寸（2 个）
```python
list_banner_creative_sizes       # 10 种横幅尺寸
list_video_creative_durations    # 7 种视频时长
```

### 创意格式（2 个）
```python
list_video_creative_formats  # 8 种视频格式
list_banner_creative_types   # 4 种横幅类型
```

### 排期（2 个）
```python
list_scheduling_types         # 4 种排期类型
list_traffic_source_types     # 3 种流量来源
```

### 定时任务（0 个）
（DV360 使用排期表管理）

### 错误码（1 个）
```python
list_error_codes           # 11 个常见错误码
```

### 数据导入（0 个）
（DV360 通过 DCM 处理数据导入）

---

## 📊 跨平台接口（6 个）

### 报价策略
```python
list_all_bid_strategies    # 汇总所有平台出价策略
```

### 错误码
```python
list_all_error_codes       # 汇总所有平台错误码
```

### 平台汇总
```python
get_platform_summary       # 获取各平台功能统计
```

### 报表
```python
get_performance_summary    # 单平台性能摘要
compare_platforms          # 跨平台对比分析
```

### 数据导入
```python
tiktok_list_import_formats     # TikTok 导入格式（5种）
meta_list_upload_formats       # Meta 上传格式（5种）
google_list_upload_methods     # Google 上传方式（4种）
```

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
genders = client.tiktok_list_genders(advertiser_id)
ages = client.tiktok_list_age_groups(advertiser_id)
langs = client.tiktok_list_languages(advertiser_id)

# 2. 查询出价策略
bids = client.tiktok_list_bid_strategies(advertiser_id)
suggestion = client.tiktok_get_bid_suggestion(advertiser_id)

# 3. 查询素材模板
templates = client.tiktok_list_creative_templates(advertiser_id)
videos = client.tiktok_list_video_templates(advertiser_id)
images = client.tiktok_list_image_templates(advertiser_id)

# 4. 查询转化事件
conversions = client.tiktok_list_conversion_events(advertiser_id)

# 5. 构建广告配置
ad_config = {
    'bid_strategy': bids[0]['code'],
    'bid_amount': suggestion['suggested_bid'],
    'targeting': {
        'genders': ['GENDER_UNLIMITED'],
        'ages': ['AGE_18_24', 'AGE_25_34'],
        'languages': ['LANGUAGE_ZH']
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

## 📈 统计数据

| 平台 | 接口数 | 出价策略 | 素材模板 | 定向参数 | 错误码 |
|------|--------|---------|---------|---------|--------|
| TikTok | 42 | 2 | 6 | 6 | 1 |
| Meta | 45 | 2 | 8 | 7 | 1 |
| Google Ads | 35 | 2 | 2 | 3 | 1 |
| DV360 | 38 | 2 | 3 | 5 | 1 |
| 跨平台 | 6 | - | - | - | - |
| **总计** | **166** | **8** | **19** | **21** | **4** |

---

## 📁 文件位置

- `scripts/ad_platform_api.py` - 主 API 客户端
- `scripts/ad_platform_query_client.py` - 定向参数查询
- `scripts/ad_platform_all_query_client.py` - 完整查询接口
- `docs/COMPLETE_API_REFERENCE.md` - 本文档

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
```
